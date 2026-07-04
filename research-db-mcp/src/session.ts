/**
 * L1 SessionManager — the heart of the MCP.
 *
 * Keeps ONE long-lived headless Chrome alive for the whole server lifetime and
 * drives it via Astral (BYOB). This is the fix the spike proved: Statista/
 * Shibboleth use in-memory *session cookies*, so a browser that is spawned and
 * killed per request loses auth. A single persistent browser keeps the session
 * warm; we only re-login when a health check shows it decayed.
 */

import { type Browser, connect, type Page } from "@astral/astral";
import { type Credentials, getCredentials } from "./secrets.ts";

const IS_MAC = Deno.build.os === "darwin";

// Chrome/Chromium binary — Google Chrome on macOS (dev), chromium on Debian (pensi).
function chromePath(): string {
  const override = Deno.env.get("CHROME_PATH");
  if (override) return override;
  return IS_MAC
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : "/usr/bin/chromium";
}

const LIBRARY_ENTRY_URL = Deno.env.get("STATISTA_ENTRY_URL") ??
  "https://libguides.nypl.org/statista";
const HOMEPAGE = "https://www.statista.com/";

export interface SessionConfig {
  port?: number; // devtools port
  profileDir?: string; // persistent user-data-dir
  headless?: boolean;
}

// Auth signals scraped from any Statista page — used to decide "are we logged in".
export const AUTH_PROBE = () => {
  const bodyText = (document.body?.innerText || "").slice(0, 120000);
  return {
    url: location.href,
    mentionsGetAccess:
      /get (full )?access|buy now|single account|purchase|you need a statista account/i
        .test(bodyText),
    mentionsInstitution: /account of|institution|new york public library/i.test(
      bodyText,
    ),
  };
};

export class SessionManager {
  #chrome?: Deno.ChildProcess;
  #browser?: Browser;
  #page?: Page;
  #port: number;
  #profileDir: string;
  #headless: boolean;
  #creds?: Credentials;
  #loggingIn?: Promise<void>;

  constructor(cfg: SessionConfig = {}) {
    this.#port = cfg.port ?? 9223;
    this.#profileDir = cfg.profileDir ??
      new URL("../cache/chrome-profile", import.meta.url).pathname;
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
    if (!IS_MAC) {
      // Linux/headless-server memory + sandbox flags; not needed (or wanted) on macOS.
      args.push("--disable-dev-shm-usage", "--no-sandbox");
    }
    if (this.#headless) args.push("--headless=new", "--window-size=1400,1600");

    this.#chrome = new Deno.Command(chromePath(), {
      args,
      stdout: "null",
      stderr: "null",
    }).spawn();

    await this.#waitForDevtools();
    this.#browser = await connect({ endpoint: `localhost:${this.#port}` });
    this.#page = await this.#browser.newPage(HOMEPAGE);
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

  /** Is the current session authenticated as an NYPL institutional user? */
  async isAuthenticated(): Promise<boolean> {
    const page = this.#requirePage();
    try {
      await page.goto(HOMEPAGE);
      await page.waitForNetworkIdle({ idleTime: 1200 }).catch(() => {});
      const s = await page.evaluate(AUTH_PROBE);
      return !s.mentionsGetAccess && s.mentionsInstitution;
    } catch {
      return false;
    }
  }

  /** Ensure we're logged in, logging in (once, de-duped) if needed. */
  async ensureAuthenticated(): Promise<void> {
    await this.start();
    if (await this.isAuthenticated()) return;
    // De-dupe concurrent callers so we only run one login at a time.
    this.#loggingIn ??= this.#login().finally(() => (this.#loggingIn = undefined));
    await this.#loggingIn;
  }

  async #login(): Promise<void> {
    const page = this.#requirePage();
    this.#creds ??= await getCredentials();

    await page.goto(LIBRARY_ENTRY_URL);
    await page.waitForSelector("#username-input", { timeout: 25000 });
    await (await page.$("#username-input"))!.type(this.#creds.account);
    await (await page.$("#password-input"))!.type(this.#creds.secret);
    await (await page.$("#login-button"))!.click();
    await page.waitForNetworkIdle({ idleTime: 3000 }).catch(() => {});

    if (!(await this.isAuthenticated())) {
      throw new Error(
        "Login failed — check credentials, or NYPL added a step (e.g. CAPTCHA).",
      );
    }
  }

  /** The live page, guaranteed authenticated. Callers navigate from here. */
  async page(): Promise<Page> {
    await this.ensureAuthenticated();
    return this.#requirePage();
  }

  #requirePage(): Page {
    if (!this.#page) throw new Error("SessionManager not started");
    return this.#page;
  }

  /**
   * The refresher entry point: ensure we're authenticated (cheap re-assert via
   * the persisted profile, or full Keychain login), then export the live
   * statista.com cookies for the lightweight fetch path to replay.
   */
  async refreshCookies() {
    await this.ensureAuthenticated();
    const page = this.#requirePage();
    await page.goto(HOMEPAGE);
    await page.waitForNetworkIdle({ idleTime: 1200 }).catch(() => {});
    const userAgent = await page.evaluate(() => navigator.userAgent);
    const cookies = await page.cookies();
    return { cookies, userAgent };
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
