#!/usr/bin/env -S deno run -A
/**
 * Orlando flooring-subcontractor capacity estimator (for the client "CKS").
 *
 * Answers: "How many 1099 flooring-crew accounts can CKS realistically support
 * in the Orlando market?" = min(demand-driven need, local labor supply ceiling).
 *
 *   N_required (roster to serve demand)  vs  N_available (supply that exists)
 *
 * Data sources (pulled live where possible):
 *   • Statista (via the MCP client) — Florida construction wages (wage-acceptance driver)
 *   • BLS OEWS API — Orlando-MSA flooring-trade payroll employment (W-2 supply floor)
 *   • Census Nonemployer Stats — self-employed 1099 flooring firms (the real target
 *     pool). Blocked from this sandbox's network, so passed in as a parameter;
 *     the exact API call to fill it is printed in the report.
 *
 * Model (from the CKS capacity framework):
 *   Y = (1 - refusalRate) * (1 - noShowRate)      # per-day realization / yield
 *   N_active    = V / (C * Y)                       # active crews needed for daily volume V
 *   N_onboarded = N_active / (1 - quarterlyChurn)   # roster to hold that active count
 */

import { StatistaClient } from "../src/client.ts";
import { parseStatistic } from "../src/extractors.ts";

// ---------------------------------------------------------------------------
// Parameters (framework defaults; tweak here or via env)
// ---------------------------------------------------------------------------
const P = {
  // Demand
  V: num("V", 30), // active daily job volume CKS wants to deliver
  C: num("C", 1), // jobs a 2-person crew completes per day (residential turn)
  refusalRate: num("REFUSAL", 0.30), // sub declines an offer (has other work)
  noShowRate: num("NOSHOW", 0.15), // sick / breakdown / ghost
  quarterlyChurn: num("CHURN", 0.35), // roster going dark per quarter (30-40%)

  // Supply
  crewSize: num("CREW_SIZE", 2), // installers per crew
  // Self-employed 1099 flooring firms in the 45-min radius (Census Nonemployer,
  // NAICS 238330, Orange+Seminole+Osceola+Lake). Sandbox can't reach Census;
  // default is an order-of-magnitude placeholder — override with the real value.
  nonemployerFirms: num("NONEMP_FIRMS", 300),
  // Share of the local installer pool realistically willing to take B2B turn
  // work through a platform (vs. locked to existing GCs). The pivotal unknown.
  willingShare: num("WILLING_SHARE", 0.40),
};

function num(env: string, d: number): number {
  const v = Deno.env.get(env);
  return v != null && v !== "" ? Number(v) : d;
}

// ---------------------------------------------------------------------------
// Data acquisition (parallel)
// ---------------------------------------------------------------------------
async function statistaFloridaWage(): Promise<{ weekly: number | null; note: string }> {
  try {
    const client = new StatistaClient();
    const html = await client.fetchHtml(
      "https://www.statista.com/statistics/1290505/wages-in-the-private-construction-sector-in-the-us-by-state/",
    );
    const stat = parseStatistic(html, "");
    const fl = stat.table.rows.find((r) => /florida/i.test(r[0]));
    const weekly = fl ? Number(fl[1].replace(/[^0-9.]/g, "")) : null;
    return { weekly, note: stat.title };
  } catch (e) {
    return { weekly: null, note: `Statista error: ${(e as Error).message}` };
  }
}

async function blsOrlandoInstallers(): Promise<{
  byCode: Record<string, number | "suppressed">;
  knownTotal: number;
  suppressed: string[];
}> {
  const codes = {
    "Carpet installers (47-2041)": "472041",
    "Floor layers (47-2042)": "472042",
    "Floor sanders (47-2043)": "472043",
  };
  const byCode: Record<string, number | "suppressed"> = {};
  const suppressed: string[] = [];
  let knownTotal = 0;
  await Promise.all(
    Object.entries(codes).map(async ([label, occ]) => {
      const sid = `OEUM0036740000000${occ}01`; // Orlando MSA, employment
      try {
        const r = await fetch(
          `https://api.bls.gov/publicAPI/v1/timeseries/data/${sid}`,
        );
        const j = await r.json();
        const data = j?.Results?.series?.[0]?.data ?? [];
        if (data.length) {
          const v = Number(data[0].value);
          byCode[label] = v;
          knownTotal += v;
        } else {
          byCode[label] = "suppressed";
          suppressed.push(label);
        }
      } catch {
        byCode[label] = "suppressed";
        suppressed.push(label);
      }
    }),
  );
  return { byCode, knownTotal, suppressed };
}

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------
function model() {
  const Y = (1 - P.refusalRate) * (1 - P.noShowRate);
  const nActive = P.V / (P.C * Y);
  const nOnboarded = nActive / (1 - P.quarterlyChurn);
  return { Y, nActive, nOnboarded };
}

// N_available: BLS payroll crews (undercount) + 1099 self-employed firms, ×willing
function supplyCeiling(blsKnown: number, suppressedCount: number) {
  // BLS suppressed cells are small; assume ~20 each as a conservative midpoint.
  const blsInstallers = blsKnown + suppressedCount * 20;
  const payrollCrews = blsInstallers / P.crewSize;
  const totalCrews = payrollCrews + P.nonemployerFirms; // 1099 firm ≈ 1 owner-op crew
  const reachable = totalCrews * P.willingShare;
  return { blsInstallers, payrollCrews, totalCrews, reachable };
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------
const pct = (x: number) => `${(x * 100).toFixed(0)}%`;
const r0 = (x: number) => Math.round(x);

const [wage, bls] = await Promise.all([
  statistaFloridaWage(),
  blsOrlandoInstallers(),
]);
const m = model();
const s = supplyCeiling(bls.knownTotal, bls.suppressed.length);

console.log(`
╔══════════════════════════════════════════════════════════════════════╗
║  CKS — Orlando flooring-subcontractor capacity model                  ║
╚══════════════════════════════════════════════════════════════════════╝

DEMAND SIDE  (how many crews CKS needs)
  V  active daily jobs .............. ${P.V}
  C  jobs/crew/day .................. ${P.C}
  Refusal rate ...................... ${pct(P.refusalRate)}
  No-show rate ...................... ${pct(P.noShowRate)}
  → Yield  Y = (1-${pct(P.refusalRate)})(1-${pct(P.noShowRate)}) = ${m.Y.toFixed(3)}
  → N_active    = V / (C·Y) ......... ${r0(m.nActive)} active crews
  Quarterly churn ................... ${pct(P.quarterlyChurn)}
  → N_onboarded = N_active/(1-churn)  ${r0(m.nOnboarded)} vetted accounts to maintain roster

SUPPLY SIDE  (how many crews exist in the 45-min radius)
  Statista — FL private construction wage: $${wage.weekly ?? "?"} / wk
     (${wage.note})
  BLS OEWS — Orlando MSA flooring trades (W-2 payroll only):`);
for (const [k, v] of Object.entries(bls.byCode)) {
  console.log(`     ${k.padEnd(28)} ${v === "suppressed" ? "suppressed (small)" : v}`);
}
console.log(`     → confirmed payroll installers: ${bls.knownTotal}  (+${bls.suppressed.length} suppressed cells)
     ⚠ OEWS counts W-2 employees only — it MISSES the self-employed 1099
        installers that are exactly CKS's target pool.
  Census Nonemployer (1099 firms, NAICS 238330) ... ${P.nonemployerFirms} (assumed — see note)
  Willing to take B2B platform turns .............. ${pct(P.willingShare)} (pivotal assumption)
  → payroll crews ${r0(s.payrollCrews)} + 1099 firms ${P.nonemployerFirms} = ${r0(s.totalCrews)} crews
  → N_available (reachable) = ${r0(s.totalCrews)} × ${pct(P.willingShare)} = ${r0(s.reachable)} crews

╔══════════════════════════════════════════════════════════════════════╗`);
const bound = s.reachable < m.nOnboarded ? "LOCAL LABOR SUPPLY" : "CUSTOMER DEMAND";
console.log(`║  VERDICT                                                              ║
╚══════════════════════════════════════════════════════════════════════╝
  Need (onboarded) .... ${r0(m.nOnboarded)} accounts
  Available (reachable) ${r0(s.reachable)} crews
  → Binding constraint: ${bound}
`);
if (bound === "LOCAL LABOR SUPPLY") {
  console.log(`  CKS CANNOT staff ${r0(m.nOnboarded)} accounts from ~${r0(s.reachable)} reachable crews.
  This VALIDATES the subcontractor-bottleneck thesis: pushing customer
  acquisition first just widens the gap. The lever is raising N_available
  (recruiting reach + willing-share) and Y (quick-pay lowers no-show).`);
} else {
  console.log(`  Supply (~${r0(s.reachable)}) covers the ${r0(m.nOnboarded)}-account roster — demand is the
  near-term constraint. But the margin is thin; watch willing-share and churn.`);
}
console.log(`
  Sensitivity — required onboarded accounts by daily volume V:`);
for (const V of [10, 20, 30, 40, 50]) {
  const na = V / (P.C * m.Y);
  const no = na / (1 - P.quarterlyChurn);
  const flag = no > s.reachable ? "  ← exceeds supply" : "";
  console.log(`     V=${String(V).padStart(2)} → ${r0(no)} onboarded${flag}`);
}
console.log(`
  TO FIRM UP (replace assumptions with real numbers):
  • 1099 supply (biggest lever): Census Nonemployer Stats, NAICS 238330, 4 counties:
      https://api.census.gov/data/2021/nonemp?get=NESTAB&for=county:095,117,097,069&in=state:12&NAICS2017=238330
      then re-run:  NONEMP_FIRMS=<sum> deno run -A estimator/orlando.ts
  • 45-min radius: OSRM/Google Distance Matrix over Orlando ZIPs (7-9am) to confirm
    the reachable geography (tightens which counties count).
  • Demand V: Orlando rental units × turnover × flooring-replacement share ÷ 365
    (Census ACS unit counts + Statista rental-vacancy trend).
`);
