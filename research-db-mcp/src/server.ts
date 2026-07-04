#!/usr/bin/env -S deno run -A
/**
 * L4 — research MCP server (local, stdio). Two NYPL-licensed data sources.
 *
 * Tools:
 *   statista_search          — browserless search (Remix /serp.data turbo-stream)
 *   statista_get_statistic   — browserless statistic data (fetch + deno-dom)
 *   statista_auth_status     — session health + cookie age
 *   refsol_business_count    — Reference Solutions (Data Axle) business counts
 *
 * Statista is fetch-first: the browser only runs for the rare cookie refresh
 * (login via macOS Keychain), every query is a lightweight fetch(). Reference
 * Solutions has no JSON API, so it stays browser-driven for every query (see
 * refsol.ts) — a persistent Chrome instance, separate from Statista's, lives
 * for the server's lifetime. stdout is the JSON-RPC channel — all diagnostics
 * go to stderr.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { StatistaClient } from "./client.ts";
import { extractSearchResults, parseStatistic, serpDataUrl } from "./extractors.ts";
import * as store from "./cookies.ts";
import { RefsolSession } from "./refsol.ts";

const client = new StatistaClient();
const refsol = new RefsolSession();

const json = (data: unknown) => ({
  content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
});
const fail = (msg: string) => ({
  content: [{ type: "text" as const, text: `Error: ${msg}` }],
  isError: true,
});

const server = new McpServer({ name: "research-db-mcp", version: "0.2.0" });

server.registerTool(
  "statista_search",
  {
    title: "Search Statista",
    description:
      "Search Statista's database (statistics, forecasts, studies, market outlooks). " +
      "Returns structured results with titles, URLs, descriptions, geographies and timeframes. " +
      "Optionally narrow by country (ISO3), contentType, and year range. " +
      "Use the returned url with statista_get_statistic to pull the underlying data.",
    inputSchema: {
      query: z.string().describe("Search query, e.g. 'flooring installation market United States'"),
      limit: z.number().int().min(1).max(50).optional().describe("Max results (default 15)"),
      page: z.number().int().min(1).optional().describe("Results page (default 1)"),
      country: z.string().optional().describe(
        "Filter by country — ISO3 code, e.g. 'USA', 'DEU', 'GBR'.",
      ),
      contentType: z.enum([
        "statistic",
        "outlook",
        "report",
        "infographic",
        "topic",
        "gcs",
      ]).optional().describe("Filter by content type."),
      yearFrom: z.number().int().optional().describe("Earliest covered year (inclusive)."),
      yearTo: z.number().int().optional().describe("Latest covered year (inclusive)."),
    },
  },
  async (
    { query, limit, page, country, contentType, yearFrom, yearTo }: {
      query: string;
      limit?: number;
      page?: number;
      country?: string;
      contentType?: string;
      yearFrom?: number;
      yearTo?: number;
    },
  ) => {
    try {
      const url = serpDataUrl(query, page ?? 1, {
        geoCode2: country,
        contentType,
        timeframeFrom: yearFrom,
        timeframeTo: yearTo,
      });
      const decoded = await client.fetchTurbo(url);
      const res = extractSearchResults(decoded, limit ?? 15);
      return json(res);
    } catch (e) {
      return fail(e instanceof Error ? e.message : String(e));
    }
  },
);

server.registerTool(
  "statista_get_statistic",
  {
    title: "Get Statista statistic data",
    description:
      "Fetch a single Statista statistic page and return its underlying data table " +
      "(headers + rows) plus metadata (title, description, dates), and an `available` flag " +
      "(false when the statistic is paywalled/out-of-tier). Pass the full statistic URL.",
    inputSchema: {
      url: z.string().url().describe(
        "Full statistic URL, e.g. https://www.statista.com/statistics/1080454/vinyl-flooring-sales-us/",
      ),
    },
  },
  async ({ url }: { url: string }) => {
    try {
      if (!/statista\.com\//.test(url)) return fail("Not a statista.com URL");
      const html = await client.fetchHtml(url);
      const stat = parseStatistic(html, url);
      if (stat.table.rows.length === 0 && !stat.metadata.name) {
        return fail("No data table found — the page may not be a standard statistic.");
      }
      return json(stat);
    } catch (e) {
      return fail(e instanceof Error ? e.message : String(e));
    }
  },
);

server.registerTool(
  "statista_auth_status",
  {
    title: "Statista session status",
    description:
      "Check whether the Statista session is authenticated (via the NYPL library account) " +
      "and how old the stored cookies are. Triggers a login refresh if needed.",
    inputSchema: {},
  },
  async () => {
    try {
      const { authenticated, traits } = await client.accountInfo();
      const bundle = await store.load();
      const ageSec = bundle ? Math.floor(Date.now() / 1000) - bundle.savedAt : null;
      return json({
        authenticated,
        account: authenticated ? (traits.email ?? "NYPL") : null,
        subscriptionEnds: traits.subscriptionDateEnd ?? null,
        cookiesAgeSeconds: ageSec,
        cookieCount: bundle?.cookies.length ?? 0,
      });
    } catch (e) {
      return fail(e instanceof Error ? e.message : String(e));
    }
  },
);

server.registerTool(
  "refsol_business_count",
  {
    title: "Reference Solutions business count",
    description:
      "Count U.S. businesses by NAICS code via NYPL's Reference Solutions (Data Axle / " +
      "ReferenceUSA) database — a second NYPL-licensed data source alongside Statista. " +
      "Optionally restrict to a state and specific counties (by 5-digit FIPS code). " +
      "Browser-driven (the underlying search UI has no JSON API), so this is slower than " +
      "the statista_* tools — expect several seconds per call.",
    inputSchema: {
      naics: z.string().regex(/^\d{2,8}$/).describe(
        "2-8 digit NAICS code, e.g. '238330' for Flooring Contractors.",
      ),
      state: z.string().length(2).optional().describe(
        "2-letter state code, e.g. 'FL'. Required if `counties` is set.",
      ),
      counties: z.array(z.object({
        name: z.string().describe("County name, e.g. 'Orange'"),
        fips: z.string().regex(/^\d{5}$/).describe("5-digit county FIPS code, e.g. '12095'"),
      })).optional().describe(
        "Restrict to these counties within `state`. Omit for a statewide/nationwide count.",
      ),
    },
  },
  async (
    { naics, state, counties }: {
      naics: string;
      state?: string;
      counties?: { name: string; fips: string }[];
    },
  ) => {
    try {
      const result = await refsol.getBusinessCount({ naics, state, counties });
      return json(result);
    } catch (e) {
      return fail(e instanceof Error ? e.message : String(e));
    }
  },
);

await server.connect(new StdioServerTransport());
console.error("[research-db-mcp] MCP server ready on stdio");
