# statista-research MCP

A local [MCP](https://modelcontextprotocol.io) server that queries **Statista**
through a New York Public Library (NYPL) subscription and returns real data —
search results, statistic data tables, and account status.

## How it works — fetch-first, browser-only-for-auth

The expensive part of Statista access is the **login** (NYPL Shibboleth SSO +
anti-bot), not the data. So the browser is used *only* to mint a session; all
data retrieval is a lightweight `fetch()`.

```
Claude ──stdio──▶ MCP (Deno)
                   │  fetch() + parse  (cookies replayed, NO browser)   ← every query
                   │      • statistic pages → deno-dom HTML table + JSON-LD metadata
                   │      • search → Remix /serp.data (turbo-stream) → structured JSON
                   │
                   └─ session stale? (401 / paywall)  ── rare, brief ──▶
                        headless Chrome (Astral) logs in via macOS Keychain,
                        exports fresh cookies → cache/cookies.json → closes.
```

- **L1 `session.ts`** — the cookie refresher: one headless Chrome, auto-login
  from Keychain, exports cookies, then exits. Runs only when cookies go stale.
- **L2 `client.ts`** — authenticated `fetch()` with cookie replay + one-shot
  auto-refresh on logged-out responses.
- **L3 `extractors.ts`** — deno-dom for statistic tables/metadata; turbo-stream
  decode for search.
- **L4 `server.ts`** — the MCP (stdio) exposing the tools below.

Cookies + the browser profile live in `cache/` (gitignored — holds your live
session).

## Tools

| Tool | What it does |
|---|---|
| `statista_search` | Search Statista; returns structured results (title, url, type, description, geos, timeframe). |
| `statista_get_statistic` | Fetch a statistic URL; returns its data table (headers + rows) + metadata. |
| `statista_auth_status` | Report auth state, account email, and subscription end date. |

## Credentials (macOS Keychain)

The refresher reads NYPL creds from the login Keychain:

```bash
# barcode in the account field, PIN as the secret (typed hidden)
security add-generic-password -a "<NYPL_BARCODE>" -s "shibboleth.nypl.org" \
  -l "shibboleth.nypl.org" -T /usr/bin/security -U -w
```

On non-macOS hosts, set `STATISTA_BARCODE` / `STATISTA_PIN` env vars instead
(handled by `getCredentials()` in `secrets.ts`).

## Register with Claude Code

```bash
claude mcp add statista-research --scope user -- \
  deno run -A \
  --config /Users/alexmaldonado/projects/mcp-servers/statista-research/deno.json \
  /Users/alexmaldonado/projects/mcp-servers/statista-research/src/server.ts
```

Then restart your client. (Or copy `mcp-config.json` into your client config.)

## Dev

```bash
deno task check          # typecheck
deno run -A src/_servertest.ts   # end-to-end MCP smoke test (spawns the server)
```

Requires: Deno, Google Chrome (for the refresh step), an NYPL card in Keychain.

## Roadmap

- Cloud/GH-Actions deployment (SOPS secrets, HTTP/SSE transport) for scheduled
  background extraction — the fetch/extract code is host-agnostic and already
  supports env-var creds.
