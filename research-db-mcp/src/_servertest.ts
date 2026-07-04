// End-to-end MCP test: spawn the server over stdio and exercise every tool.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: "deno",
  args: ["run", "-A", "src/server.ts"],
});
const client = new Client({ name: "e2e-test", version: "1.0.0" });
await client.connect(transport);

// deno-lint-ignore no-explicit-any
const text = (r: any) => r.content?.[0]?.text ?? JSON.stringify(r);

const tools = await client.listTools();
console.log("TOOLS:", tools.tools.map((t) => t.name).join(", "));

console.log("\n--- statista_auth_status ---");
console.log(text(await client.callTool({ name: "statista_auth_status", arguments: {} })));

console.log("\n--- statista_search: 'construction subcontractor labor' ---");
const s = await client.callTool({
  name: "statista_search",
  arguments: { query: "construction subcontractor labor United States", limit: 5 },
});
console.log(text(s).slice(0, 900));

console.log("\n--- statista_get_statistic: vinyl flooring ---");
const g = await client.callTool({
  name: "statista_get_statistic",
  arguments: { url: "https://www.statista.com/statistics/1080454/vinyl-flooring-sales-us/" },
});
console.log(text(g).slice(0, 700));

console.log("\n--- refsol_business_count: NAICS 238330, Orlando 4-county metro ---");
const r = await client.callTool({
  name: "refsol_business_count",
  arguments: {
    naics: "238330",
    state: "FL",
    counties: [
      { name: "Orange", fips: "12095" },
      { name: "Seminole", fips: "12117" },
      { name: "Osceola", fips: "12097" },
      { name: "Lake", fips: "12069" },
    ],
  },
});
console.log(text(r));

await client.close();
