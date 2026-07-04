// Integration test for L2 (fetch client) + L3 (extractors), incl. auto-refresh.
import { StatistaClient } from "./client.ts";
import { extractSearchResults, parseStatistic, serpDataUrl } from "./extractors.ts";

const client = new StatistaClient();

console.log("=== STATISTIC (fetch + parse, browserless) ===");
const statUrl = "https://www.statista.com/statistics/1080454/vinyl-flooring-sales-us/";
const stat = parseStatistic(await client.fetchHtml(statUrl), statUrl);
console.log("title:", stat.title);
console.log("headers:", stat.table.headers);
console.log("rows[0..3]:", JSON.stringify(stat.table.rows.slice(0, 4)));
console.log("metadata:", JSON.stringify(stat.metadata));

console.log("\n=== SEARCH via /serp.data (turbo-stream, browserless) ===");
const decoded = await client.fetchTurbo(serpDataUrl("flooring installation market"));
const search = extractSearchResults(decoded, 8);
console.log(`total hits: ${search.total} (page ${search.page}/${search.totalPages})`);
for (const r of search.results) {
  console.log(` - [${r.contentType}] ${r.title}  (${r.geos?.join(",") ?? "?"}, ${r.timeframe ?? "?"})`);
  console.log(`     ${r.url}`);
}
