#!/usr/bin/env -S deno run -A
/**
 * CKS multi-year growth projection: accounts -> revenue -> two independent
 * ceilings (market size / SOM, and local labor supply) -> "when does it
 * become impossible to scale."
 *
 * Three layers, each labeled by source:
 *   [STATISTA]  FL flooring-contractor industry revenue (real, live-fetched)
 *   [BLS]       Orlando MSA payroll installer counts (real, live-fetched)
 *   [ASSUMPTION] everything else (MSA population share, PM-turn segment share,
 *               obtainable-share ramp, ticket size, ramp curve, friction
 *               scenario magnitudes) — clearly separated so they're easy to
 *               swap for the client's real numbers.
 *
 * Revenue in any year is capped at:
 *   min(demand-implied revenue, SOM ceiling, max revenue the available
 *       crew pool can physically fulfill)
 * The friction scenario models the client's field observation — installers
 * avoiding travel/dispatch due to immigration-enforcement fear — as reduced
 * willing-share and higher no-show/refusal. Grounded in one real number:
 * foreign-born workers are 9.8% of construction/extraction occupations vs.
 * 4.2% for native-born (Statista/CPS, 2024) — a ~2.3x overrepresentation,
 * i.e. a materially exposed share of this specific labor pool.
 */

import { StatistaClient } from "../src/client.ts";
import { parseStatistic } from "../src/extractors.ts";

// ---------------------------------------------------------------------------
// [ASSUMPTION] parameters — override via env, e.g. TICKET=2500 deno run ...
// ---------------------------------------------------------------------------
export const A = {
  // Account path: given by the client (20 current / 40 Yr1 / 60 Yr2),
  // extrapolated further at the same +20/yr pace so we can actually locate
  // the point where scaling becomes impossible, not just the first 3 years.
  accountPath: [20, 40, 60, 80, 100, 120, 140, 160, 180, 200],

  // New accounts don't hit full run-rate immediately; assume mid-year signing.
  rampFactor: num("RAMP", 0.5),

  // Revenue model
  ticketSize: num("TICKET", 2000), // $/job, full-ticket billing (see prior convo)
  jobsPerAccountPerYear: num("JOBS_PER_ACCOUNT", 30), // ~1 every ~1.7 weeks

  // --- SOM chain ---
  msaPopShareOfFL: num("MSA_SHARE", 0.12), // Orlando MSA ~2.75M / FL ~23M
  pmTurnShareOfFlooringRevenue: num("PM_SHARE", 0.15), // multifamily-turn slice of all flooring-contractor revenue
  // CKS's obtainable share of that local PM-turn SAM, ramping as reputation
  // builds then plateauing — realistically capped against entrenched
  // competitors (larger installers, incumbent GCs already embedded with PMs).
  obtainableShareByYear: [0.08, 0.12, 0.16, 0.20, 0.22, 0.24, 0.25, 0.25, 0.25, 0.25],

  // --- Labor supply chain (mirrors estimator/orlando.ts) ---
  crewSize: num("CREW_SIZE", 2),
  nonemployerFirms: num("NONEMP_FIRMS", 300), // 1099 flooring firms, 4-county radius (placeholder, see orlando.ts)
  workDaysPerYear: num("WORKDAYS", 250),

  // Baseline vs. deportation-fear-friction scenario
  baseline: { refusalRate: 0.30, noShowRate: 0.15, willingShare: 0.30 },
  friction: { refusalRate: 0.38, noShowRate: 0.26, willingShare: 0.17 },
  quarterlyChurn: num("CHURN", 0.35),
};

function num(env: string, d: number): number {
  const v = Deno.env.get(env);
  return v != null && v !== "" ? Number(v) : d;
}

// Optional: unlock the post-ramp SOM plateau to isolate the pure labor-supply
// crossover (i.e. "if CKS somehow captured way more market share, where would
// labor alone break?"). Leaves the Year 0-3 ramp (the real near-term forecast)
// untouched; only overrides the plateau from Year 4 onward.
const somCapOverride = Deno.env.get("SOM_CAP");
if (somCapOverride) {
  const cap = Number(somCapOverride);
  A.obtainableShareByYear = A.obtainableShareByYear.map((v, i) => (i >= 4 ? cap : v));
}

// ---------------------------------------------------------------------------
// [STATISTA] Florida flooring-contractor industry revenue (real, live)
// ---------------------------------------------------------------------------
async function flFlooringRevenue(): Promise<{ millions: number; year: string; title: string }> {
  const client = new StatistaClient();
  const html = await client.fetchHtml(
    "https://www.statista.com/forecasts/1207545/flooring-contractors-revenue-in-florida/",
  );
  const s = parseStatistic(html, "");
  const latest = s.table.rows[0]; // most recent year first
  return {
    millions: Number(latest[1].replace(/[^0-9.]/g, "")),
    year: latest[0].replace(/\*/g, ""),
    title: s.title,
  };
}

// ---------------------------------------------------------------------------
// [BLS] Orlando MSA flooring-trade payroll employment (real, live)
// ---------------------------------------------------------------------------
async function blsOrlandoInstallers(): Promise<number> {
  const codes = ["472041", "472042", "472043"];
  let known = 0, suppressed = 0;
  await Promise.all(
    codes.map(async (occ) => {
      try {
        const r = await fetch(
          `https://api.bls.gov/publicAPI/v1/timeseries/data/OEUM0036740000000${occ}01`,
        );
        const j = await r.json();
        const data = j?.Results?.series?.[0]?.data ?? [];
        if (data.length) known += Number(data[0].value);
        else suppressed++;
      } catch {
        suppressed++;
      }
    }),
  );
  return known + suppressed * 20; // suppressed cells assumed small (~20 each)
}

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------
interface YearRow {
  year: number;
  accountsSigned: number;
  effectiveAccounts: number;
  demandRevenue: number;
  somCeiling: number;
  cappedRevenueBeforeLabor: number;
  jobsNeeded: number;
  jobsPerDay: number;
  scenarios: Record<string, {
    yield: number;
    nActive: number;
    nOnboarded: number;
    availableCrews: number;
    maxFulfillableRevenue: number;
    finalRevenue: number;
    verdict: "OK" | "TIGHT" | "IMPOSSIBLE";
  }>;
}

export function scenarioMath(
  jobsNeeded: number,
  params: { refusalRate: number; noShowRate: number; willingShare: number },
  totalLocalCrews: number,
) {
  const yieldRate = (1 - params.refusalRate) * (1 - params.noShowRate);
  const jobsPerDay = jobsNeeded / A.workDaysPerYear;
  const nActive = jobsPerDay / yieldRate; // crews needed, active on a given day
  const nOnboarded = nActive / (1 - A.quarterlyChurn); // roster to sustain that
  const availableCrews = totalLocalCrews * params.willingShare;
  const maxJobsPerDay = availableCrews * yieldRate; // capacity ceiling
  const maxFulfillableRevenue = maxJobsPerDay * A.workDaysPerYear * A.ticketSize;
  return { yieldRate, nActive, nOnboarded, availableCrews, maxFulfillableRevenue };
}

export function verdict(nOnboarded: number, availableCrews: number): "OK" | "TIGHT" | "IMPOSSIBLE" {
  const ratio = nOnboarded / availableCrews;
  if (ratio > 1) return "IMPOSSIBLE";
  if (ratio > 0.75) return "TIGHT";
  return "OK";
}

async function run() {
  const [fl, blsInstallers] = await Promise.all([
    flFlooringRevenue(),
    blsOrlandoInstallers(),
  ]);

  const msaFlooringRevenue = fl.millions * A.msaPopShareOfFL; // $M, all segments
  const samPmTurn = msaFlooringRevenue * A.pmTurnShareOfFlooringRevenue; // $M, PM-turn niche

  const payrollCrews = blsInstallers / A.crewSize;
  const totalLocalCrews = payrollCrews + A.nonemployerFirms;

  const rows: YearRow[] = [];
  for (let i = 0; i < A.accountPath.length; i++) {
    const accountsSigned = A.accountPath[i];
    const prior = i > 0 ? A.accountPath[i - 1] : accountsSigned; // year0: treat as fully ramped base
    const netNew = i > 0 ? accountsSigned - prior : 0;
    const fullyRamped = i > 0 ? prior : accountsSigned;
    const effectiveAccounts = fullyRamped + netNew * A.rampFactor;

    const demandRevenue = effectiveAccounts * A.jobsPerAccountPerYear * A.ticketSize;
    const somCeiling = samPmTurn * 1_000_000 * A.obtainableShareByYear[i];
    const cappedRevenueBeforeLabor = Math.min(demandRevenue, somCeiling);
    const jobsNeeded = cappedRevenueBeforeLabor / A.ticketSize;
    const jobsPerDay = jobsNeeded / A.workDaysPerYear;

    const scenarios: YearRow["scenarios"] = {};
    for (const [name, params] of Object.entries({ baseline: A.baseline, friction: A.friction })) {
      const m = scenarioMath(jobsNeeded, params, totalLocalCrews);
      const finalRevenue = Math.min(cappedRevenueBeforeLabor, m.maxFulfillableRevenue);
      scenarios[name] = {
        yield: m.yieldRate,
        nActive: m.nActive,
        nOnboarded: m.nOnboarded,
        availableCrews: m.availableCrews,
        maxFulfillableRevenue: m.maxFulfillableRevenue,
        finalRevenue,
        verdict: verdict(m.nOnboarded, m.availableCrews),
      };
    }

    rows.push({
      year: i,
      accountsSigned,
      effectiveAccounts,
      demandRevenue,
      somCeiling,
      cappedRevenueBeforeLabor,
      jobsNeeded,
      jobsPerDay,
      scenarios,
    });
  }

  return { fl, blsInstallers, msaFlooringRevenue, samPmTurn, totalLocalCrews, rows };
}

if (import.meta.main) {
  const result = await run();

  // ---------------------------------------------------------------------------
  // Console report
  // ---------------------------------------------------------------------------
  const fmt$ = (n: number) => `$${(n / 1_000_000).toFixed(2)}M`;
  const fmt0 = (n: number) => Math.round(n).toLocaleString();

  console.log(`
[STATISTA] FL flooring-contractor industry revenue (${result.fl.year}): $${result.fl.millions}M
  → "${result.fl.title}"
[ASSUMPTION] Orlando MSA share of FL (pop. proxy): ${(A.msaPopShareOfFL * 100).toFixed(0)}%  → ${fmt$(result.msaFlooringRevenue * 1_000_000)} MSA flooring revenue (all segments)
[ASSUMPTION] PM/multifamily-turn share of that: ${(A.pmTurnShareOfFlooringRevenue * 100).toFixed(0)}%  → SAM ${fmt$(result.samPmTurn * 1_000_000)} (the whole local PM-turn niche, all competitors)
[BLS]      Orlando MSA payroll flooring installers: ${result.blsInstallers} → ${fmt0(result.blsInstallers / A.crewSize)} payroll crews
[ASSUMPTION] + ${A.nonemployerFirms} local 1099 firms  → ${fmt0(result.totalLocalCrews)} total local crews (before willing-share)
`);

  for (const row of result.rows) {
    console.log(`── Year ${row.year} ${row.year === 0 ? "(current)" : ""} ──────────────────────────────`);
    console.log(`  Accounts: ${row.accountsSigned} signed → ${row.effectiveAccounts.toFixed(1)} effective (ramp-adjusted)`);
    console.log(`  Demand-implied revenue:  ${fmt$(row.demandRevenue)}`);
    console.log(`  SOM ceiling (obtainable ${(A.obtainableShareByYear[row.year] * 100).toFixed(0)}% of SAM): ${fmt$(row.somCeiling)}`);
    console.log(`  → capped (pre-labor):    ${fmt$(row.cappedRevenueBeforeLabor)}   [${row.demandRevenue > row.somCeiling ? "SOM-CAPPED" : "demand-bound"}]`);
    for (const [name, s] of Object.entries(row.scenarios)) {
      console.log(
        `    [${name.padEnd(8)}] need ${s.nOnboarded.toFixed(0)} crews vs ${s.availableCrews.toFixed(0)} available` +
          ` → ${s.verdict.padEnd(10)} final revenue ${fmt$(s.finalRevenue)}`,
      );
    }
  }

  const crossovers: Record<string, number | null> = { baseline: null, friction: null };
  for (const scen of Object.keys(crossovers)) {
    const hit = result.rows.find((r) => r.scenarios[scen].verdict === "IMPOSSIBLE");
    crossovers[scen] = hit ? hit.year : null;
  }
  console.log(`\n=== WHEN DOES IT BECOME IMPOSSIBLE TO SCALE? ===`);
  for (const [scen, year] of Object.entries(crossovers)) {
    console.log(
      `  ${scen}: ${year === null ? `not reached within the modeled ${A.accountPath.length}-year horizon` : `Year ${year} — required roster exceeds available local crews`}`,
    );
  }

  // Dump structured JSON for the artifact renderer (OUT_FILE lets sensitivity
  // runs, e.g. SOM_CAP=0.6, write to a separate file without overwriting the
  // base case).
  const outFile = Deno.env.get("OUT_FILE") ?? "projection.json";
  await Deno.writeTextFile(
    new URL(`./${outFile}`, import.meta.url),
    JSON.stringify({ params: A, ...result, crossovers }, null, 2),
  );
  console.log(`\nWrote estimator/${outFile}`);
}
