# OUTLINE.md

> **For LLMs reading this file:** This is a structural outline, not a spec,
> changelog, or implementation plan. Use it to understand the system shape,
> module boundaries, and where details live. Do not treat roadmap notes as
> tasks. When making changes, keep this file short and update code comments
> or the relevant file instead of expanding this outline.

**Project:** `library-databases`  **Updated:** 2026-07-06

Formerly `statista-research`, then briefly `research-db-mcp`. Renamed once
Reference Solutions made it a genuinely multi-source MCP: "library" names
the actual unifying constraint (NYPL library-card-gated access), and the
bare `<domain>-<noun>` form matches this monorepo's sibling convention
(`ai-search/`, `email-validation/`, `pdf-processor/` — none use an `-mcp`
suffix).

---

## 1. Solutions Architect Summary

This repo is a local, stdio [MCP](https://modelcontextprotocol.io) server
that gives Claude direct query access to two NYPL-licensed research
databases that would otherwise require a browser and a library card:
**Statista** (statistics, forecasts, market data) and **Reference
Solutions / Data Axle** (business-establishment counts by NAICS code and
geography). Client-specific business-analysis estimators consume this repo's
clients directly via a `deno.json` import map rather than living here — the
MCP itself stays a general NYPL-database access broker. Three so far:
- **CKS** (Orlando flooring-installer network) —
  `~/projects/clients/cks/demos/cks-poc-order-to-crm/research/` — reuses `src/client.ts` (Statista).
- **Great Bear / WomenAutoKnow** (Queens NY auto shop + a founder-education
  side project) — `~/projects/clients/gbar/research/` — reuses `src/client.ts`
  (Statista) **and** `src/refsol.ts` (`RefsolSession.getBusinessCount`)
  directly, the first downstream consumer to drive Reference Solutions
  outside this server's own `refsol_business_count` tool.
- **Mira Agency** (NYC ops/BD consulting agency; a `company-research`-skill
  test run, not a paid engagement) — `~/projects/clients/mira-agency/research/`
  — reuses `src/client.ts` (Statista); Reference Solutions was queried once
  via `RefsolSession.getBusinessCount` for a firm-count snapshot, then frozen
  as a parameter rather than wired into the estimator's live path (same
  freezing pattern CKS uses for its own Reference Solutions count). First
  consumer built for a business model genuinely unlike CKS's — confirms the
  `company-research` skill's 3-stage estimator *shape* (not CKS's specific
  formulas) generalizes across business types.

The two data sources have fundamentally different access patterns, and
that difference shapes the whole design:

- **Statista is fetch-first.** A headless browser (Astral) is used *only*
  to mint/refresh an authenticated session (NYPL Shibboleth SSO). Every
  actual query is a lightweight `fetch()` replaying cookies — decoding the
  site's Remix `/serp.data` turbo-stream for search, or parsing statistic
  HTML (deno-dom) for data tables.
- **Reference Solutions has no JSON API.** It's a legacy, server-side
  session-stateful ASP.NET app (a GUID-keyed search session, criteria
  applied through AJAX-driven UI panels — e.g. a NAICS code typed into a
  grid, a county moved into a "selected" listbox via click + Enter, not a
  raw dblclick). It stays browser-driven (Astral) for *every* query,
  authenticated via NYPL's EZproxy — a different mechanism from Statista's
  Shibboleth SSO.

Both sources resolve the same NYPL library-card credentials (macOS
Keychain locally, env vars on a server — see `src/secrets.ts`), but run as
independent modules with independent browser sessions, profile
directories, and devtools ports, so they operate side by side without
colliding.

---

## 2. System Diagram

```text
                       Claude Code (stdio MCP client)
                                 |
                                 v
                    src/server.ts (L4 — MCP tool registry)
                 ________________/ \________________
                /            |                       \
   statista_search   statista_get_statistic   refsol_business_count
   statista_auth_status
                \            |                       |
                 \           |                       v
                  v          v                src/refsol.ts
            src/client.ts (L2 — fetch)     (browser-driven —
                  |         ^               every query drives
        fetch()+parse   session stale?      Astral; no fetch
       (cookies replayed,  (401/paywall)     path exists here)
        NO browser per        |                      |
             query)           v                      v
                  |    src/session.ts (L1 —   EZproxy login (once,
                  v     headless Chrome,        de-duped) then the
        src/extractors.ts   Keychain login,     Custom Search UI:
        (L3 — deno-dom       exports cookies)   NAICS grid -> county
         HTML tables,             |             listbox -> read the
         turbo-stream              v              .totalCount widget
         decode)          cache/chrome-profile/          |
                          cache/cookies.json              v
                          (gitignored — live       cache/refsol-profile/
                           Statista session)       (gitignored — live
                                                    Reference Solutions
                                                    session, distinct
                                                    profile + port)

   (Downstream client-analysis estimators live in their own projects, not
    here — client-specific research, not part of this MCP:
      CKS:       ~/projects/clients/cks/demos/cks-poc-order-to-crm/research/
                 reuses src/client.ts (Statista) via import map.
      Great Bear/WomenAutoKnow: ~/projects/clients/gbar/research/
                 reuses src/client.ts (Statista) AND src/refsol.ts
                 (RefsolSession) directly via import map.
      Mira Agency (company-research skill test run):
                 ~/projects/clients/mira-agency/research/
                 reuses src/client.ts (Statista) via import map; Reference
                 Solutions queried once out-of-band, frozen as a parameter.)
```

---

## 3. Module Boundaries

| Module | Owns | Notes |
|---|---|---|
| `src/session.ts` (L1) | Statista auth via headless Chrome + Keychain | Only runs on cookie refresh, not per query |
| `src/client.ts` (L2) | Authenticated `fetch()` + cookie replay + auto-refresh | The Statista fast path |
| `src/extractors.ts` (L3) | HTML/turbo-stream parsing into structured data | No network calls — pure parsing |
| `src/refsol.ts` | Reference Solutions auth (EZproxy) + browser-driven search | Every query drives the browser; `parseCount`/`ORLANDO_METRO_COUNTIES` are the only pure, unit-tested pieces |
| `src/secrets.ts` | NYPL credential resolution (env vars → macOS Keychain) | Shared by `session.ts` and `refsol.ts` |
| `src/cookies.ts` | Statista cookie bundle persistence | Statista-only |
| `src/server.ts` (L4) | MCP tool registration/dispatch | The only file Claude talks to |

---

## 4. Where Details Live

| Topic | Reference |
|---|---|
| Tool list + input schemas | `src/server.ts` (`registerTool` calls) |
| Statista fetch-first flow | `src/session.ts`, `src/client.ts` docstrings |
| Reference Solutions DOM sequence (proven selectors, click+Enter quirk) | `src/refsol.ts` docstring |
| Original Reference Solutions feasibility probe evidence | `cache/refsol-artifacts/` (gitignored) |
| Credential setup (Keychain / env vars) | `src/secrets.ts` docstring |
| Registering the server with a client | `mcp-config.json` |
| Run/check/test commands | `deno.json` `tasks` |
| CKS business-analysis estimator (moved out) | `~/projects/clients/cks/demos/cks-poc-order-to-crm/research/` — reuses `src/client.ts` for live Statista data via import map |
| Great Bear / WomenAutoKnow business-analysis estimator | `~/projects/clients/gbar/research/` — reuses `src/client.ts` (Statista) and `src/refsol.ts` (`RefsolSession`, Reference Solutions) directly via import map |
| Mira Agency business-analysis estimator (`company-research` skill test run) | `~/projects/clients/mira-agency/research/` — reuses `src/client.ts` (Statista) via import map; Reference Solutions queried once out-of-band, frozen as a parameter |
| Unit test coverage | `src/refsol_test.ts` (Reference Solutions pure helpers) |
| Live end-to-end smoke test (spawns the real server, hits live Statista + Reference Solutions) | `src/_servertest.ts` (`deno task test:e2e`) |

---

## 5. Running It

```bash
deno task check      # typecheck
deno task test       # unit tests — pure formulas only, no network/credentials
deno task test:e2e   # live end-to-end MCP smoke test (spawns the real server)
deno task server     # run the MCP server directly (normally launched by the client)
```

Requires: Deno, Google Chrome, and an NYPL library card's barcode + PIN in
the macOS Keychain (service `shibboleth.nypl.org`) or `STATISTA_BARCODE` /
`STATISTA_PIN` env vars on non-macOS hosts (`src/secrets.ts` resolves
either, and both `session.ts` and `refsol.ts` share it).

`cache/` is gitignored — it holds live session cookies and browser
profiles for *both* data sources. Never commit it.

---

## 6. Roadmap Notes

- Cloud/GH-Actions deployment (SOPS secrets, HTTP/SSE transport) for
  scheduled background extraction — the Statista fetch/extract path is
  already host-agnostic (env-var creds). The Reference Solutions path is
  browser-bound by design (no fetch-replay is feasible against its
  session-stateful search UI), so any cloud deployment of it needs a
  headless-Chrome-capable runner, not just a lightweight fetch worker.
- A third NYPL-licensed data source would follow the same shape: a module
  under `src/`, a shared `secrets.ts` credential resolution, and either the
  fetch-first pattern (if it exposes a clean API) or the browser-driven
  pattern (if it doesn't) — see Module Boundaries above.
- Downstream consumers often also hit **BLS's public OEWS API directly**
  (no NYPL license needed, so it bypasses this MCP entirely — see CKS's and
  Great Bear's `projection.ts`). Its unregistered/no-key tier has a low
  **daily** request quota shared per IP; probing several datatype-code
  variants to confirm a series ID (see Great Bear `project-spec.md` §1b) can
  burn the whole day's quota. Freeze captured values as a fallback rather
  than assuming a live re-fetch will always succeed.
