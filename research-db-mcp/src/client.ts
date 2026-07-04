/**
 * L2 StatistaClient — the featherweight data path.
 *
 * Fetches Statista with replayed cookies (no browser):
 *   • fetchHtml()  — statistic pages (parsed with deno-dom)
 *   • fetchTurbo() — Remix `.data` endpoints (search), decoded from turbo-stream
 *
 * If a response looks logged-out, it triggers ONE ephemeral browser refresh
 * (login via Keychain → export fresh cookies → close browser) and retries.
 * Between refreshes there is no browser process — just fetch().
 */

import { decode } from "npm:turbo-stream@2";
import { SessionManager } from "./session.ts";
import * as store from "./cookies.ts";

const FALLBACK_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

interface FetchResult {
  status: number;
  body: string;
}

export class StatistaClient {
  #bundle: store.CookieBundle | null = null;
  #refreshing?: Promise<void>;

  /** Fetch a Statista page's HTML (statistic pages), refreshing once if logged out. */
  async fetchHtml(url: string): Promise<string> {
    return (await this.#fetchWithRefresh(url)).body;
  }

  /** Fetch + decode a Remix `.data` (turbo-stream) endpoint, e.g. search. */
  async fetchTurbo(url: string): Promise<unknown> {
    const { body } = await this.#fetchWithRefresh(url);
    const stream = new Response(body).body!;
    const decoded = await decode(stream);
    await decoded.done;
    return decoded.value;
  }

  /**
   * Auth state via the user-data-proxy endpoint, which returns the account's
   * subscription traits as JSON (a reliable SSR signal, unlike the JS-rendered
   * header banner).
   */
  async accountInfo(): Promise<{ authenticated: boolean; traits: Record<string, unknown> }> {
    const UDS = "https://www.statista.com/user-data-proxy?limit=200&include=" +
      "groupCompanyName,subscriptionLevel,subscriptionDateStart,subscriptionDateEnd," +
      "subscriptionProductId,userTypeProduct";
    const { body } = await this.#fetchWithRefresh(UDS);
    try {
      const traits = (JSON.parse(body)?.traits ?? {}) as Record<string, unknown>;
      const end = traits.subscriptionDateEnd
        ? new Date(String(traits.subscriptionDateEnd))
        : null;
      const authenticated = Boolean(traits.email || traits.groupId) &&
        (!end || end.getTime() > Date.now());
      return { authenticated, traits };
    } catch {
      return { authenticated: false, traits: {} };
    }
  }

  async isAuthenticated(): Promise<boolean> {
    return (await this.accountInfo()).authenticated;
  }

  async #fetchWithRefresh(
    url: string,
    opts: { noRetry?: boolean } = {},
  ): Promise<FetchResult> {
    await this.#ensureCookies();
    let res = await this.#rawFetch(url);
    if (!opts.noRetry && this.#loggedOut(res)) {
      await this.#refresh();
      res = await this.#rawFetch(url);
      if (this.#loggedOut(res)) {
        throw new Error(
          `Statista session invalid after refresh (status ${res.status}). ` +
            "Check Keychain credentials.",
        );
      }
    }
    return res;
  }

  async #ensureCookies(): Promise<void> {
    this.#bundle ??= await store.load();
    if (store.looksExpired(this.#bundle)) await this.#refresh();
  }

  async #rawFetch(url: string): Promise<FetchResult> {
    const bundle = this.#bundle;
    const res = await fetch(url, {
      headers: {
        "Cookie": bundle ? store.header(bundle) : "",
        "User-Agent": bundle?.userAgent ?? FALLBACK_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
      redirect: "manual",
    });
    return { status: res.status, body: await res.text() };
  }

  #loggedOut({ status, body }: FetchResult): boolean {
    if (status === 401 || status === 403) return true;
    if (status >= 300 && status < 400) return true; // redirect to /login
    return /you need a statista account|get full access/i.test(body);
  }

  async #refresh(): Promise<void> {
    this.#refreshing ??= this.#doRefresh().finally(
      () => (this.#refreshing = undefined),
    );
    await this.#refreshing;
  }

  async #doRefresh(): Promise<void> {
    const session = new SessionManager({ headless: true });
    try {
      const { cookies, userAgent } = await session.refreshCookies();
      const normalized = store.normalize(cookies);
      await store.save(normalized, userAgent);
      this.#bundle = {
        savedAt: Math.floor(Date.now() / 1000),
        userAgent,
        cookies: normalized,
      };
    } finally {
      await session.close(); // browser is transient — gone between refreshes
    }
  }
}
