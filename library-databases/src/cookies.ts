/**
 * Cookie store — the handoff between the browser refresher (writes) and the
 * lightweight fetch client (reads). Persisted to a chmod 600 JSON file so the
 * authenticated session survives across MCP process restarts.
 */

export interface StoredCookie {
  name: string;
  value: string;
  domain?: string;
  path?: string;
  expires?: number; // unix seconds; -1 or absent = session cookie
}

export interface CookieBundle {
  savedAt: number; // unix seconds when the refresher last wrote these
  userAgent?: string; // the browser UA to replay alongside the cookies
  cookies: StoredCookie[];
}

const DEFAULT_PATH = new URL("../cache/cookies.json", import.meta.url).pathname;

// deno-lint-ignore no-explicit-any -- Astral's cookie shape is structural
export function normalize(raw: any[]): StoredCookie[] {
  return raw.map((c) => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path,
    expires: typeof c.expires === "number" ? c.expires : undefined,
  })).filter((c) => c.name && c.value);
}

export async function save(
  cookies: StoredCookie[],
  userAgent?: string,
  path = DEFAULT_PATH,
): Promise<void> {
  const bundle: CookieBundle = {
    savedAt: Math.floor(Date.now() / 1000),
    userAgent,
    cookies,
  };
  await Deno.mkdir(new URL(".", `file://${path}`).pathname, { recursive: true })
    .catch(() => {});
  await Deno.writeTextFile(path, JSON.stringify(bundle));
  await Deno.chmod(path, 0o600).catch(() => {}); // best-effort (no-op on some FS)
}

export async function load(path = DEFAULT_PATH): Promise<CookieBundle | null> {
  try {
    return JSON.parse(await Deno.readTextFile(path)) as CookieBundle;
  } catch {
    return null;
  }
}

/** Build a `Cookie:` header value from a bundle. */
export function header(bundle: CookieBundle): string {
  return bundle.cookies.map((c) => `${c.name}=${c.value}`).join("; ");
}

/**
 * Cheap pre-flight staleness check (avoids a doomed fetch). We can't know the
 * server session state, but we can catch obviously-dead bundles: none stored,
 * or a persistent cookie already past its expiry. Real logged-out detection
 * still happens on the fetch response.
 */
export function looksExpired(bundle: CookieBundle | null): boolean {
  if (!bundle || bundle.cookies.length === 0) return true;
  const now = Math.floor(Date.now() / 1000);
  const persistent = bundle.cookies.filter((c) => c.expires && c.expires > 0);
  // If every persistent cookie is expired, the session is surely dead.
  if (persistent.length > 0 && persistent.every((c) => c.expires! < now)) {
    return true;
  }
  return false;
}
