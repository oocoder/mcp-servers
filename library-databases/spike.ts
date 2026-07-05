#!/usr/bin/env -S deno run -A
/**
 * spike.ts — Feasibility probe for the Statista MCP (NOT the MCP itself).
 *
 * Goal: prove the risky chain end-to-end BEFORE building the real server:
 *   1. login   — spawn real Chrome (persistent profile) so you log in via the
 *                library once. Session persists to ./cache/chrome-profile.
 *   2. check   — reuse that profile, load a Statista page, and observe whether
 *                we are authenticated (premium content unlocked, not paywalled).
 *   3. search  — run a Statista search and pull back real result URLs.
 *   4. stat    — open a statistic page and extract the actual data (DOM tables
 *                + embedded JSON) so we know we can pull numbers, not just HTML.
 *
 * Uses the BYOB pattern: we launch Google Chrome ourselves with a debug port +
 * dedicated user-data-dir, then Astral connect()s to it. Real Chrome = least
 * bot-detectable and handles the library SSO/2FA flow natively.
 *
 * Every run dumps artifacts (screenshot + html + extracted json) into
 * ./cache/artifacts so we can build the real extractors against captured markup.
 *
 * Run:  deno run -A spike.ts login
 *       deno run -A spike.ts check   [url]
 *       deno run -A spike.ts search  "electric vehicles market"
 *       deno run -A spike.ts stat    "https://www.statista.com/statistics/....."
 *       add --headless to check/search/stat to test the background-job path.
 */

import { connect } from "jsr:@astral/astral";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
// NYPL's WAYFless Shibboleth entry link: hitting this auto-fires the SSO chain
// (shibboleth.statista.com → NYPL IdP → back to www.statista.com, authenticated).
const LIBRARY_ENTRY_URL = "https://libguides.nypl.org/statista";
const PORT = 9222;
const CACHE = new URL("./cache/", import.meta.url).pathname;
const PROFILE = CACHE + "chrome-profile";
const ARTIFACTS = CACHE + "artifacts";

await Deno.mkdir(PROFILE, { recursive: true });
await Deno.mkdir(ARTIFACTS, { recursive: true });

// ---------------------------------------------------------------------------
// Chrome lifecycle (BYOB)
// ---------------------------------------------------------------------------

function spawnChrome(headless: boolean, url?: string): Deno.ChildProcess {
  const args = [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
  ];
  if (headless) args.push("--headless=new", "--window-size=1400,1600");
  if (url) args.push(url);

  const cmd = new Deno.Command(CHROME, {
    args,
    stdout: "null",
    stderr: "null",
  });
  return cmd.spawn();
}

/** Poll the DevTools endpoint until Chrome is ready to accept connections. */
async function waitForDevtools(timeoutMs = 15000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(`http://localhost:${PORT}/json/version`);
      if (r.ok) {
        await r.body?.cancel();
        return;
      }
    } catch {
      // not up yet
    }
    await new Promise((res) => setTimeout(res, 300));
  }
  throw new Error("Chrome DevTools endpoint never came up on port " + PORT);
}

// ---------------------------------------------------------------------------
// Extraction (runs inside the page)
// ---------------------------------------------------------------------------

// Returned by evaluate() on any Statista page. Shape kept flat/serializable.
const PAGE_PROBE = () => {
  const bodyText = (document.body?.innerText || "").slice(0, 200000);
  const lower = bodyText.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    h1: document.querySelector("h1")?.textContent?.trim() ?? null,
    tableCount: document.querySelectorAll("table").length,
    tables: Array.from(document.querySelectorAll("table"))
      .slice(0, 3)
      .map((t) => (t as HTMLElement).innerText.slice(0, 4000)),
    jsonLd: Array.from(
      document.querySelectorAll('script[type="application/ld+json"]'),
    ).map((s) => s.textContent ?? "").slice(0, 5),
    hasNextData: !!document.querySelector("#__NEXT_DATA__"),
    // Auth / paywall signals — eyeball these against the screenshot.
    signals: {
      mentionsGetAccess:
        /get (full )?access|buy now|single account|purchase|upgrade to/i.test(
          bodyText,
        ),
      mentionsInstitution: /institution|library|campus|athens|shibboleth/i.test(
        lower,
      ),
      mentionsDownload: /\bdownload\b/i.test(lower),
      mentionsLogin: /\b(log in|sign in|login)\b/i.test(lower),
      accountMenu: !!document.querySelector(
        '[class*="account" i],[class*="user-menu" i],[data-testid*="account" i]',
      ),
    },
  };
};

const SEARCH_PROBE = () => {
  const seen = new Set<string>();
  const results: { text: string; href: string }[] = [];
  for (const a of Array.from(document.querySelectorAll("a"))) {
    const href = (a as HTMLAnchorElement).href;
    const text = a.textContent?.trim() ?? "";
    if (
      href &&
      // Require a numeric content id → real result cards, not nav/popular links.
      /\/(statistics|forecasts|study|studies|infographic|outlook)\/\d+\//
        .test(href) &&
      text.length > 3 &&
      !seen.has(href)
    ) {
      seen.add(href);
      results.push({ text, href });
    }
  }
  return { url: location.href, title: document.title, count: results.length, results: results.slice(0, 40) };
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function save(label: string, name: string, data: string | Uint8Array) {
  const path = `${ARTIFACTS}/${label}.${name}`;
  if (typeof data === "string") await Deno.writeTextFile(path, data);
  else await Deno.writeFile(path, data);
  console.log(`  saved ${path}`);
}

async function withPage(
  headless: boolean,
  url: string,
  fn: (page: import("jsr:@astral/astral").Page) => Promise<void>,
) {
  const chrome = spawnChrome(headless);
  try {
    await waitForDevtools();
    const browser = await connect({ endpoint: `localhost:${PORT}` });
    const page = await browser.newPage(url);
    try {
      await page.waitForNetworkIdle({ idleTime: 1500 }).catch(() => {});
      await fn(page);
    } finally {
      await browser.disconnect();
    }
  } finally {
    try {
      chrome.kill();
      await chrome.status; // let Chrome flush cookies to the profile on exit
    } catch { /* ignore */ }
  }
}

function label(kind: string): string {
  return `${kind}-${new Date().toISOString().replace(/[:.]/g, "-")}`;
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

// Extracts every form field on the current page — used to learn the NYPL IdP
// login form's exact selectors so we can wire Keychain auto-fill later.
const FORM_PROBE = () => {
  const inputs = Array.from(
    document.querySelectorAll("input, button, select"),
  ).map((el) => {
    const e = el as HTMLInputElement;
    return {
      tag: el.tagName.toLowerCase(),
      type: e.type || null,
      name: e.name || null,
      id: el.id || null,
      placeholder: e.placeholder || null,
      ariaLabel: el.getAttribute("aria-label"),
      autocomplete: el.getAttribute("autocomplete"),
      text: el.textContent?.trim().slice(0, 40) || null,
    };
  });
  const forms = Array.from(document.querySelectorAll("form")).map((f) => ({
    action: (f as HTMLFormElement).action,
    method: (f as HTMLFormElement).method,
    id: f.id,
    className: f.className,
  }));
  return { url: location.href, title: document.title, forms, inputs };
};

async function cmdFormProbe(headless: boolean) {
  console.log(`\n=== FORM PROBE: learn NYPL IdP login fields (headless=${headless}) ===`);
  console.log("Opening the NYPL entry link and dumping the login form's fields.");
  console.log("(No credentials used — just reading the public login page.)\n");
  await withPage(headless, LIBRARY_ENTRY_URL, async (page) => {
    // Give the SSO redirect chain time to land on the NYPL IdP form.
    await page.waitForNetworkIdle({ idleTime: 2500 }).catch(() => {});
    const probe = await page.evaluate(FORM_PROBE);
    const lbl = label("formprobe");
    await save(lbl, "png", await page.screenshot());
    await save(lbl, "html", await page.content());
    await save(lbl, "fields.json", JSON.stringify(probe, null, 2));
    console.log("\n  landed on:", probe.url);
    console.log("  title:", probe.title);
    console.log("  forms:", JSON.stringify(probe.forms, null, 2));
    console.log("  fields:");
    for (const f of probe.inputs) {
      console.log(
        `   - <${f.tag} type=${f.type} name=${f.name} id=${f.id} ` +
          `autocomplete=${f.autocomplete} placeholder=${f.placeholder}> ${f.text ?? ""}`,
      );
    }
  });
}

const KEYCHAIN_SERVICE = "shibboleth.nypl.org";

/**
 * Read NYPL creds from the login Keychain. Returns null if the item isn't
 * CLI-readable (e.g. it lives in iCloud Keychain). The secret is read into
 * memory and typed into the form — it is NEVER logged or written to disk.
 */
async function readKeychain(
  service: string,
): Promise<{ account: string; secret: string } | null> {
  const attr = await new Deno.Command("security", {
    args: ["find-generic-password", "-s", service],
    stdout: "piped",
    stderr: "null",
  }).output();
  if (!attr.success) return null;
  const account =
    new TextDecoder().decode(attr.stdout).match(/"acct"<blob>="([^"]*)"/)?.[1] ??
      "";

  const pw = await new Deno.Command("security", {
    args: ["find-generic-password", "-s", service, "-w"],
    stdout: "piped",
    stderr: "null",
  }).output();
  if (!pw.success) return null;
  const secret = new TextDecoder().decode(pw.stdout).replace(/\r?\n$/, "");
  if (!account || !secret) return null;
  return { account, secret };
}

async function cmdLogin() {
  console.log("\n=== STEP 1: LOGIN (one time) ===");
  const creds = await readKeychain(KEYCHAIN_SERVICE);

  const chrome = spawnChrome(false); // headed, blank — Astral drives the flow
  try {
    await waitForDevtools();
    const browser = await connect({ endpoint: `localhost:${PORT}` });
    const page = await browser.newPage(LIBRARY_ENTRY_URL);

    let loggedIn = false;
    if (creds) {
      console.log(
        `  Found NYPL creds in Keychain (barcode …${creds.account.slice(-4)}). Auto-logging in…`,
      );
      try {
        (await page.waitForSelector("#username-input", { timeout: 20000 }))!;
        await (await page.$("#username-input"))!.type(creds.account);
        await (await page.$("#password-input"))!.type(creds.secret);
        await (await page.$("#login-button"))!.click();
        await page.waitForNetworkIdle({ idleTime: 3000 }).catch(() => {});
        loggedIn = true;
      } catch (e) {
        console.log(
          "  Auto-login couldn't complete (extra step / form changed) — falling back to manual.",
          e instanceof Error ? e.message : e,
        );
      }
    } else {
      console.log(
        `  No CLI-readable Keychain item at service "${KEYCHAIN_SERVICE}".`,
      );
      console.log(
        "  (If you stored it in the Passwords app, it's in iCloud Keychain and the",
      );
      console.log("   CLI can't read it — re-add via the security command.)");
    }

    if (!loggedIn) {
      console.log(
        "\n  → Log in manually in the Chrome window, then press ENTER here.",
      );
      const buf = new Uint8Array(8);
      await Deno.stdin.read(buf);
    }

    // Land on statista.com and snapshot the authenticated state.
    await page.goto("https://www.statista.com/");
    await page.waitForNetworkIdle({ idleTime: 1500 }).catch(() => {});
    const probe = await page.evaluate(PAGE_PROBE);
    const cookies = await page.cookies();
    const lbl = label("login");
    await save(lbl, "png", await page.screenshot());
    await save(lbl, "probe.json", JSON.stringify(probe, null, 2));
    console.log(`\n  landed on: ${probe.url}`);
    console.log(`  cookies stored in profile: ${cookies.length}`);
    console.log(`  auth signals:`, JSON.stringify(probe.signals));
    await browser.disconnect();
  } catch (e) {
    console.error("  (login error, but profile may still be saved):", e);
  } finally {
    chrome.kill();
    await chrome.status;
  }
  console.log("\nProfile saved to:", PROFILE);
  console.log("Next:  deno run -A spike.ts check");
}

async function cmdCheck(headless: boolean, url: string) {
  console.log(`\n=== STEP 2: CHECK auth reuse (headless=${headless}) ===`);
  console.log("url:", url);
  await withPage(headless, url, async (page) => {
    const probe = await page.evaluate(PAGE_PROBE);
    const lbl = label("check");
    await save(lbl, "png", await page.screenshot());
    await save(lbl, "html", await page.content());
    await save(lbl, "probe.json", JSON.stringify(probe, null, 2));
    console.log("\n  title:", probe.title);
    console.log("  h1:", probe.h1);
    console.log("  auth signals:", JSON.stringify(probe.signals, null, 2));
    console.log(
      "\n  >>> Authenticated if premium content shows and 'get access' CTAs are ABSENT.",
    );
    console.log("  >>> Open the .png artifact to confirm visually.");
  });
}

async function cmdSearch(headless: boolean, query: string) {
  const url = `https://www.statista.com/serp?q=${encodeURIComponent(query)}`;
  console.log(`\n=== STEP 3: SEARCH (headless=${headless}) ===`);
  console.log("query:", query, "\nurl:", url);
  await withPage(headless, url, async (page) => {
    const probe = await page.evaluate(SEARCH_PROBE);
    const lbl = label("search");
    await save(lbl, "png", await page.screenshot());
    await save(lbl, "html", await page.content());
    await save(lbl, "results.json", JSON.stringify(probe, null, 2));
    console.log(`\n  found ${probe.count} candidate result links:`);
    for (const r of probe.results.slice(0, 12)) {
      console.log(`   - ${r.text.slice(0, 70)}\n       ${r.href}`);
    }
  });
}

async function cmdStat(headless: boolean, url: string) {
  console.log(`\n=== STEP 4: STATISTIC data pull (headless=${headless}) ===`);
  console.log("url:", url);
  await withPage(headless, url, async (page) => {
    const probe = await page.evaluate(PAGE_PROBE);
    const lbl = label("stat");
    await save(lbl, "png", await page.screenshot());
    await save(lbl, "html", await page.content());
    await save(lbl, "probe.json", JSON.stringify(probe, null, 2));
    // The embedded JSON blob often carries the raw series — dump it whole.
    const nextData = await page
      .evaluate(() => document.querySelector("#__NEXT_DATA__")?.textContent ?? "")
      .catch(() => "");
    if (nextData) await save(lbl, "nextdata.json", nextData);
    console.log("\n  title:", probe.title);
    console.log("  h1:", probe.h1);
    console.log("  tables found:", probe.tableCount);
    console.log("  has __NEXT_DATA__ blob:", probe.hasNextData);
    if (probe.tables[0]) {
      console.log("\n  --- first table (raw text) ---");
      console.log(probe.tables[0]);
    }
    console.log(
      "\n  >>> If the table / nextdata carries the real numbers, data pull WORKS.",
    );
  });
}

// Mirrors the real MCP's L1: ONE living browser — log in once, then pull many
// pages without killing Chrome, so the session cookie survives in memory.
async function cmdSession(urls: string[]) {
  console.log(`\n=== SESSION: persistent browser, login once + pull ${urls.length} page(s) ===`);
  const creds = await readKeychain(KEYCHAIN_SERVICE);
  if (!creds) {
    console.error("  No CLI-readable Keychain creds — aborting.");
    return;
  }
  const chrome = spawnChrome(true); // headless
  try {
    await waitForDevtools();
    const browser = await connect({ endpoint: `localhost:${PORT}` });
    const page = await browser.newPage(LIBRARY_ENTRY_URL);

    console.log("  logging in via NYPL SSO…");
    await page.waitForSelector("#username-input", { timeout: 20000 });
    await (await page.$("#username-input"))!.type(creds.account);
    await (await page.$("#password-input"))!.type(creds.secret);
    await (await page.$("#login-button"))!.click();
    await page.waitForNetworkIdle({ idleTime: 3000 }).catch(() => {});

    await page.goto("https://www.statista.com/");
    await page.waitForNetworkIdle({ idleTime: 1500 }).catch(() => {});
    const home = await page.evaluate(PAGE_PROBE);
    console.log("  auth after login:", JSON.stringify(home.signals));

    for (const url of urls) {
      console.log(`\n  → ${url}`);
      await page.goto(url);
      await page.waitForNetworkIdle({ idleTime: 2000 }).catch(() => {});
      // Reveal the data table for chart-type stats if a toggle exists.
      await page
        .evaluate(() => {
          const el = Array.from(document.querySelectorAll("a, button")).find(
            (n) => /show all numbers|show data|data table/i.test(n.textContent || ""),
          ) as HTMLElement | undefined;
          el?.click();
        })
        .catch(() => {});
      await page.waitForNetworkIdle({ idleTime: 800 }).catch(() => {});
      const probe = await page.evaluate(PAGE_PROBE);
      const lbl = label("session");
      await save(lbl, "png", await page.screenshot());
      await save(lbl, "probe.json", JSON.stringify(probe, null, 2));
      const authed = !probe.signals.mentionsGetAccess &&
        probe.signals.mentionsInstitution;
      console.log("    title:", probe.title);
      console.log("    AUTHED:", authed ? "YES ✅" : "no ❌", JSON.stringify(probe.signals));
      if (probe.tables[0]) {
        console.log("    --- data table ---");
        console.log("    " + probe.tables[0].replace(/\n/g, "\n    ").slice(0, 1800));
      }
    }
    await browser.disconnect();
  } finally {
    chrome.kill();
    await chrome.status;
  }
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const [cmd, ...rest] = Deno.args;
const headless = rest.includes("--headless");
const positional = rest.filter((a) => !a.startsWith("--"));

switch (cmd) {
  case "formprobe":
    await cmdFormProbe(headless);
    break;
  case "session":
    if (!positional[0]) {
      console.error("usage: spike.ts session <url> [url2] [url3] …");
      Deno.exit(1);
    }
    await cmdSession(positional);
    break;
  case "login":
    await cmdLogin();
    break;
  case "check":
    await cmdCheck(
      headless,
      positional[0] ?? "https://www.statista.com/",
    );
    break;
  case "search":
    if (!positional[0]) {
      console.error('usage: spike.ts search "your query"');
      Deno.exit(1);
    }
    await cmdSearch(headless, positional[0]);
    break;
  case "stat":
    if (!positional[0]) {
      console.error("usage: spike.ts stat <statistic-url>");
      Deno.exit(1);
    }
    await cmdStat(headless, positional[0]);
    break;
  default:
    console.log(
      "commands: login | check [url] | search <query> | stat <url>   (+ --headless)",
    );
}
