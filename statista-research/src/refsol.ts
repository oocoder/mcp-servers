/**
 * Reference Solutions (Data Axle / ReferenceUSA) via NYPL EZproxy.
 *
 * A second NYPL-licensed data source, alongside Statista (see session.ts),
 * with a different auth mechanism (EZproxy, not Shibboleth) and a different
 * app entirely: legacy ASP.NET MVC, server-side session-stateful search
 * (criteria applied through UI panels + AJAX POSTs, keyed by a GUID in the
 * URL — not a clean JSON API). Unlike StatistaClient's fetch-first design,
 * this MUST stay browser-driven; a fetch-replay module would need to
 * reproduce the sequenced criteria POSTs + session GUID + EZproxy cookies.
 *
 * The DOM sequence below is proven end-to-end by a feasibility probe (see
 * the `refsol-data-axle` project memory and cache/refsol-artifacts/ for the
 * captured evidence): login -> U.S. Businesses > Custom Search -> enable the
 * "Keyword/SIC/NAICS" criteria -> enter a NAICS code -> enable "County" ->
 * pick a state -> double-click counties into the Selected list -> read the
 * total-count widget.
 */

import { type Browser, connect, type Page } from "@astral/astral";
import { getCredentials } from "./secrets.ts";

const IS_MAC = Deno.build.os === "darwin";

function chromePath(): string {
  const override = Deno.env.get("CHROME_PATH");
  if (override) return override;
  return IS_MAC
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : "/usr/bin/chromium";
}

const EZPROXY_LOGIN_URL = Deno.env.get("REFSOL_ENTRY_URL") ??
  "https://login.i.ezproxy.nypl.org/login?qurl=http://www.referenceusa.com%2f";
// EZproxy is a host-rewriting proxy: every referenceusa.com URL becomes
// <host>.i.ezproxy.nypl.org, served over plain http (observed, not guessed).
const BASE_URL = "http://www.referenceusa.com.i.ezproxy.nypl.org";
// Distinct from Statista's SessionManager port (9223) so both can run side
// by side without colliding on the same devtools port / profile dir.
const DEFAULT_PORT = 9224;

export interface CountyFips {
  name: string;
  fips: string; // 5-digit FIPS code, e.g. "12095" for Orange County, FL
}

// The 4-county Orlando metro used in the CKS estimator (see refsol-data-axle
// memory for how these were confirmed against the live Custom Search UI).
export const ORLANDO_METRO_COUNTIES: CountyFips[] = [
  { name: "Orange", fips: "12095" },
  { name: "Seminole", fips: "12117" },
  { name: "Osceola", fips: "12097" },
  { name: "Lake", fips: "12069" },
];

export interface BusinessCountQuery {
  naics: string; // 2-8 digit NAICS code, e.g. "238330"
  state?: string; // 2-letter state code, e.g. "FL" — required if counties given
  counties?: CountyFips[]; // restrict to these counties within `state`
}

export interface BusinessCountResult {
  naics: string;
  state?: string;
  counties?: string[];
  count: number;
  raw: string; // the total-count widget's text, pre-parse (e.g. "398")
  capturedAt: string; // ISO timestamp
}

export interface RefsolSessionConfig {
  port?: number;
  profileDir?: string;
  headless?: boolean;
}

export class RefsolSession {
  #chrome?: Deno.ChildProcess;
  #browser?: Browser;
  #page?: Page;
  #port: number;
  #profileDir: string;
  #headless: boolean;
  #loggingIn?: Promise<void>;

  constructor(cfg: RefsolSessionConfig = {}) {
    this.#port = cfg.port ?? DEFAULT_PORT;
    // Reuses the profile dir from the original feasibility probe (already
    // authenticated) rather than minting a fresh one, so the MCP server's
    // first real use doesn't trigger an unnecessary extra EZproxy login.
    this.#profileDir = cfg.profileDir ??
      new URL("../cache/refsol-profile", import.meta.url).pathname;
    this.#headless = cfg.headless ?? true;
  }

  /** Launch Chrome + connect Astral. Idempotent. */
  async start(): Promise<void> {
    if (this.#browser) return;
    await Deno.mkdir(this.#profileDir, { recursive: true });

    const args = [
      `--remote-debugging-port=${this.#port}`,
      `--user-data-dir=${this.#profileDir}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-blink-features=AutomationControlled",
      "--disable-gpu",
    ];
    if (!IS_MAC) args.push("--disable-dev-shm-usage", "--no-sandbox");
    if (this.#headless) args.push("--headless=new", "--window-size=1400,1600");

    this.#chrome = new Deno.Command(chromePath(), {
      args,
      stdout: "null",
      stderr: "null",
    }).spawn();

    await this.#waitForDevtools();
    this.#browser = await connect({ endpoint: `localhost:${this.#port}` });
    this.#page = await this.#browser.newPage(`${BASE_URL}/UsBusiness/Search`);
    await this.#page.waitForNetworkIdle({ idleTime: 1500 }).catch(() => {});
  }

  async #waitForDevtools(timeoutMs = 20000): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const r = await fetch(`http://localhost:${this.#port}/json/version`);
        if (r.ok) {
          await r.body?.cancel();
          return;
        }
      } catch { /* not up yet */ }
      await new Promise((res) => setTimeout(res, 300));
    }
    throw new Error(`Chrome DevTools never came up on port ${this.#port}`);
  }

  /** Is the current session authenticated (EZproxy let us through to the real site)? */
  async isAuthenticated(): Promise<boolean> {
    const page = this.#requirePage();
    try {
      await page.goto(`${BASE_URL}/UsBusiness/Search`);
      await page.waitForNetworkIdle({ idleTime: 1200 }).catch(() => {});
      const url = await page.evaluate(() => location.href);
      return /referenceusa\.com\.i\.ezproxy\.nypl\.org/i.test(url);
    } catch {
      return false;
    }
  }

  /** Ensure we're logged in, logging in (once, de-duped) if needed. */
  async ensureAuthenticated(): Promise<void> {
    await this.start();
    if (await this.isAuthenticated()) return;
    this.#loggingIn ??= this.#login().finally(() => (this.#loggingIn = undefined));
    await this.#loggingIn;
  }

  async #login(): Promise<void> {
    const page = this.#requirePage();
    const creds = await getCredentials();

    await page.goto(EZPROXY_LOGIN_URL);
    await page.waitForSelector('input[name="user"]', { timeout: 25000 });
    await (await page.$('input[name="user"]'))!.type(creds.account);
    await (await page.$('input[name="pass"]'))!.type(creds.secret);
    await (await page.$('#access-databases input[type="submit"]'))!.click();
    await page.waitForNetworkIdle({ idleTime: 3000 }).catch(() => {});

    if (!(await this.isAuthenticated())) {
      throw new Error(
        "Reference Solutions login failed — check credentials, or NYPL/EZproxy added a step (e.g. CAPTCHA).",
      );
    }
  }

  /**
   * Query the "U.S. Businesses" module for a count of establishments matching
   * a NAICS code, optionally restricted to a state + set of counties. Drives
   * the legacy ASP.NET Custom Search UI directly — see the module doc comment.
   */
  async getBusinessCount(query: BusinessCountQuery): Promise<BusinessCountResult> {
    await this.ensureAuthenticated();
    const page = this.#requirePage();

    // Fresh Custom (Advanced) Search each call — the server assigns a new
    // session GUID, so there's no stale criteria carried over between calls.
    await page.goto(`${BASE_URL}/UsBusiness/Search/Custom/`);
    await page.waitForNetworkIdle({ idleTime: 1200 }).catch(() => {});

    await this.#setNaics(page, query.naics);
    if (query.state && query.counties?.length) {
      await this.#setCounties(page, query.state, query.counties);
    }

    const raw = await this.#readTotalCount(page);
    const count = Number(raw.replace(/[^0-9]/g, ""));
    return {
      naics: query.naics,
      state: query.state,
      counties: query.counties?.map((c) => c.name),
      count,
      raw,
      capturedAt: new Date().toISOString(),
    };
  }

  async #setNaics(page: Page, code: string): Promise<void> {
    await this.#enableCriteria(page, "#cs-YellowPageHeadingOrSic", "#naicsOptionId");
    // "Search All NAICS" mode (as opposed to Primary-NAICS-only).
    await (await page.$("#naicsOptionId"))!.click();
    await page.waitForSelector("#naics_manual .inputGridValue", { timeout: 10000 });
    const box = await page.$("#naics_manual .inputGridValue");
    await box!.type(code);
    // Blur to trigger the site's change handling (it adds the criterion on
    // blur/change, not on keystroke).
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.waitForNetworkIdle({ idleTime: 800 }).catch(() => {});
  }

  async #setCounties(page: Page, state: string, counties: CountyFips[]): Promise<void> {
    await this.#enableCriteria(page, "#cs-County", "#CountyState");
    await page.waitForSelector("#CountyState", { timeout: 10000 });
    await page.evaluate((st) => {
      const sel = document.querySelector("#CountyState") as HTMLSelectElement;
      sel.value = st;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    }, { args: [state] });

    // Selecting the state AJAX-populates the available-county listbox. This
    // is an accessible listbox (each <li> has tabindex + an aria-label of
    // "Use the Spacebar key to select the item"), but empirically the widget
    // moves an item to Selected on click-to-focus + Enter — not a raw
    // dblclick MouseEvent (synthetic dblclick dispatch is silently ignored)
    // and not Space either (confirmed against the live widget).
    await page.waitForSelector("#availableCountyState li.dataLi", { timeout: 15000 });
    for (const c of counties) {
      const li = await page.$(`#availableCountyState li.dataLi[data-value="${c.fips}"]`);
      if (!li) throw new Error(`county FIPS ${c.fips} (${c.name}) not found in available list`);
      await li.click();
      await page.keyboard.press("Enter");
      await page.waitForNetworkIdle({ idleTime: 600 }).catch(() => {});
    }
  }

  /** Check a `cs-*` criteria checkbox if not already checked, then wait for its panel. */
  async #enableCriteria(
    page: Page,
    checkboxSelector: string,
    panelSelector: string,
  ): Promise<void> {
    await page.waitForSelector(checkboxSelector, { timeout: 10000 });
    const already = await page.evaluate(
      (sel) => (document.querySelector(sel) as HTMLInputElement | null)?.checked ?? false,
      { args: [checkboxSelector] },
    );
    if (!already) {
      await (await page.$(checkboxSelector))!.click();
    }
    await page.waitForSelector(panelSelector, { timeout: 10000 });
  }

  async #readTotalCount(page: Page): Promise<string> {
    await (await page.$(".action-update-count"))!.click();
    await page.waitForNetworkIdle({ idleTime: 1000 }).catch(() => {});
    const el = await page.waitForSelector(".totalCount", { timeout: 10000 });
    return (await el.innerText()).trim();
  }

  #requirePage(): Page {
    if (!this.#page) throw new Error("RefsolSession not started");
    return this.#page;
  }

  async close(): Promise<void> {
    try {
      await this.#browser?.disconnect();
    } catch { /* ignore */ }
    try {
      this.#chrome?.kill();
      await this.#chrome?.status;
    } catch { /* ignore */ }
    this.#browser = undefined;
    this.#page = undefined;
    this.#chrome = undefined;
  }
}

// Smoke-test CLI: deno run -A src/refsol.ts [naics] [state]
// e.g. deno run -A src/refsol.ts 238330 FL   -> Orlando 4-county metro count
if (import.meta.main) {
  const naics = Deno.args[0] ?? "238330";
  const state = Deno.args[1] ?? "FL";
  const session = new RefsolSession({ headless: Deno.args.includes("--headed") ? false : true });
  try {
    const result = await session.getBusinessCount({
      naics,
      state,
      counties: ORLANDO_METRO_COUNTIES,
    });
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await session.close();
  }
}
