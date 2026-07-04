/**
 * L3 Extractors — parse Statista HTML into structured data with deno-dom.
 * No browser: these operate on the raw HTML the fetch client returns.
 */

import { DOMParser, type Element } from "jsr:@b-fuze/deno-dom";

export interface StatisticData {
  url: string;
  title: string;
  subtitle?: string;
  // false when the statistic is paywalled/out-of-tier even while authenticated
  // (locked banner, or masked "***" table cells instead of real numbers).
  available: boolean;
  table: { headers: string[]; rows: string[][] };
  metadata: Record<string, string>;
}

export interface SearchResult {
  contentId: string;
  contentType: string; // statistic | forecast | study | infographic | topic | ...
  title: string;
  subtitle?: string;
  description?: string;
  url: string;
  premium?: boolean;
  released?: string;
  geos?: string[];
  timeframe?: string;
}

export interface SearchResponse {
  total: number;
  page: number;
  totalPages: number;
  results: SearchResult[];
}

// Optional /serp.data facet filters (param names verified empirically against
// the SERP loader — these are the aggregation keys Statista's search accepts).
export interface SearchFilters {
  geoCode2?: string; // ISO3 country code, e.g. "USA", "DEU"
  contentType?: string; // statistic | outlook | report | infographic | topic | gcs
  timeframeFrom?: number; // earliest covered year (inclusive)
  timeframeTo?: number; // latest covered year (inclusive)
}

/** Build the browserless Remix search endpoint URL. */
export function serpDataUrl(query: string, page = 1, filters: SearchFilters = {}): string {
  const u = new URL("https://www.statista.com/serp.data");
  u.searchParams.set("q", query);
  if (page > 1) u.searchParams.set("p", String(page));
  if (filters.geoCode2) u.searchParams.set("geoCode2", filters.geoCode2);
  if (filters.contentType) u.searchParams.set("contentType", filters.contentType);
  if (filters.timeframeFrom) u.searchParams.set("timeframeFrom", String(filters.timeframeFrom));
  if (filters.timeframeTo) u.searchParams.set("timeframeTo", String(filters.timeframeTo));
  return u.toString();
}

const clean = (s: string | null | undefined) => (s ?? "").replace(/\s+/g, " ").trim();

function parseTable(table: Element | null): { headers: string[]; rows: string[][] } {
  if (!table) return { headers: [], rows: [] };
  const trs = Array.from(table.querySelectorAll("tr"));
  const grid = trs
    .map((tr) =>
      Array.from(tr.querySelectorAll("th, td")).map((c) => clean(c.textContent))
    )
    .filter((r) => r.some((c) => c.length > 0));
  return { headers: grid[0] ?? [], rows: grid.slice(1) };
}

// Flatten JSON-LD (arrays + @graph) into a flat list of schema.org nodes.
// deno-lint-ignore no-explicit-any
function flattenGraph(data: any): any[] {
  const out: any[] = [];
  const visit = (n: any) => {
    if (Array.isArray(n)) return n.forEach(visit);
    if (n && typeof n === "object") {
      out.push(n);
      if (n["@graph"]) visit(n["@graph"]);
    }
  };
  visit(data);
  return out;
}

// Statista embeds clean metadata in a JSON-LD block — far more reliable than
// scraping the sidebar. Pull the WebPage/Article node's fields.
function parseMetadata(
  doc: ReturnType<DOMParser["parseFromString"]>,
): Record<string, string> {
  const meta: Record<string, string> = {};
  const raw = doc?.querySelector('script[type="application/ld+json"]')?.textContent;
  if (!raw) return meta;
  try {
    for (const node of flattenGraph(JSON.parse(raw))) {
      const t = node["@type"];
      if (t !== "WebPage" && t !== "Article") continue;
      if (node.name) meta.name ??= clean(node.name);
      if (node.description) meta.description ??= clean(node.description);
      if (node.datePublished) meta.datePublished ??= String(node.datePublished);
      if (node.dateModified) meta.dateModified ??= String(node.dateModified);
      if (node.isAccessibleForFree != null) {
        meta.isAccessibleForFree ??= String(node.isAccessibleForFree);
      }
    }
  } catch { /* malformed JSON-LD — skip */ }
  return meta;
}

export function parseStatistic(html: string, url: string): StatisticData {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const h1 = clean(doc?.querySelector("h1")?.textContent);
  const title = h1 || clean(doc?.querySelector("title")?.textContent);
  // Subtitle is usually the unit line right after the h1 (e.g. "(in million U.S. dollars)").
  const subtitle = clean(
    doc?.querySelector("h1 + p, h1 + div, [class*='subtitle' i]")?.textContent,
  ) || undefined;

  const table = parseTable(doc?.querySelector("table") ?? null);
  // Out-of-tier detection: an upsell banner, or masked "***" cells where the
  // real numbers would be. In-tier authenticated pages have neither.
  const paywalled = /you need a statista account|get full access/i.test(html);
  // A locked value renders as a cell that is *only* asterisks ("***"). Trailing
  // asterisks on a label ("2023***", "LVT*") are footnote markers, not masks.
  const masked = table.rows.some((r) => r.some((c) => /^\*+$/.test(c.trim())));

  return {
    url,
    title,
    subtitle,
    available: !paywalled && !masked,
    table,
    metadata: parseMetadata(doc),
  };
}

// Walk the decoded turbo-stream value to the searchResponse object.
function findSearchResponse(o: unknown, depth = 0): Record<string, unknown> | undefined {
  if (!o || typeof o !== "object" || depth > 10) return undefined;
  const obj = o as Record<string, unknown>;
  if (obj.searchResponse && typeof obj.searchResponse === "object") {
    return obj.searchResponse as Record<string, unknown>;
  }
  for (const k of Object.keys(obj)) {
    const found = findSearchResponse(obj[k], depth + 1);
    if (found) return found;
  }
  return undefined;
}

const abs = (p: string) => p.startsWith("http") ? p : `https://www.statista.com${p}`;

// Some search fields are nested objects ({name}, {from,to}); reduce to a string.
function scalarize(v: unknown): string {
  if (v == null) return "";
  if (typeof v !== "object") return String(v);
  const o = v as Record<string, unknown>;
  if (o.name || o.label || o.title) return String(o.name ?? o.label ?? o.title);
  if (o.from || o.to) return `${o.from ?? "?"}–${o.to ?? "?"}`;
  return "";
}

/** Extract structured search results from a decoded /serp.data turbo-stream value. */
export function extractSearchResults(decoded: unknown, limit = 25): SearchResponse {
  const sr = findSearchResponse(decoded);
  const raw = (sr?.results ?? []) as Record<string, unknown>[];
  const results: SearchResult[] = raw.slice(0, limit).map((r) => ({
    contentId: String(r.contentId ?? r.id ?? ""),
    contentType: String(r.contentType ?? "unknown"),
    title: clean(r.title as string),
    subtitle: r.subtitle ? clean(r.subtitle as string) : undefined,
    description: r.description ? clean(r.description as string) : undefined,
    url: r.urlPath ? abs(String(r.urlPath)) : "",
    premium: typeof r.premium === "boolean" ? r.premium : undefined,
    released: r.released ? String(r.released) : undefined,
    geos: Array.isArray(r.coveredGeos)
      ? (r.coveredGeos as unknown[]).map(scalarize).filter(Boolean)
      : undefined,
    timeframe: r.coveredTimeframe ? scalarize(r.coveredTimeframe) : undefined,
  }));
  return {
    total: Number(sr?.totalExactHits ?? sr?.totalHits ?? results.length),
    page: Number(sr?.currentPage ?? 1),
    totalPages: Number(sr?.totalPages ?? 1),
    results,
  };
}
