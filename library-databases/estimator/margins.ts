#!/usr/bin/env -S deno run -A
/**
 * CKS margin & net-income (P&L) layer — sits on top of the revenue projection
 * in projection.json. Answers: "what does CKS actually take home?"
 *
 * The revenue ceiling (~$7.6M) is NOT the takeaway — net income is, and in a
 * 1099-labor passthrough business it is thin and shows heavy operating leverage
 * (fixed cost drags early years toward breakeven; margin only firms up at scale).
 *
 * Two business models, because they answer differently and we haven't pinned
 * which one CKS runs:
 *   GC / full-ticket : CKS bills the whole job, pays the crew + materials out of
 *                      it. High revenue, THIN margin (specialty-trade economics).
 *   Marketplace / fee: CKS takes a % of job value (GMV); crew/materials paid
 *                      around it. Low revenue, high-% margin on a small base.
 *
 * All cost ratios are [ASSUMPTION] industry-norm benchmarks (Statista has no
 * clean US flooring-contractor margin) — override via env to match CKS's books.
 */

export const P = {
  // GC / full-ticket model (revenue = billed job value)
  gc: {
    subPayoutPct: num("SUB_PCT", 0.48), // 1099 crew's cut of the ticket
    materialsPct: num("MAT_PCT", 0.20), // flooring materials, if CKS supplies
    variableOpexPct: num("GC_VAROPEX", 0.10), // processing, quick-pay cost of capital, per-job ops
    fixedOpexBase: num("GC_FIXED", 250_000), // ops/sales/insurance/software floor
    fixedOpexPerAccount: num("GC_FIXED_PER_ACCT", 1_500), // ops load per managed account
  },
  // Marketplace / take-rate model (projection revenue treated as GMV)
  mp: {
    takeRate: num("TAKE_RATE", 0.18), // CKS fee as % of job value
    grossMarginPct: num("MP_GROSS", 0.85), // after payment/processing on the fee
    variableOpexPct: num("MP_VAROPEX", 0.08),
    fixedOpexBase: num("MP_FIXED", 200_000),
    fixedOpexPerAccount: num("MP_FIXED_PER_ACCT", 1_200),
  },
  taxRate: num("TAX", 0.25),
};

function num(env: string, d: number): number {
  const v = Deno.env.get(env);
  return v != null && v !== "" ? Number(v) : d;
}

export interface PL {
  revenue: number;
  grossProfit: number;
  grossMarginPct: number;
  fixedOpex: number;
  variableOpex: number;
  ebit: number;
  netIncome: number;
  netMarginPct: number;
}

export function gcPL(billedRevenue: number, effAccounts: number): PL {
  const grossMarginPct = 1 - P.gc.subPayoutPct - P.gc.materialsPct;
  const grossProfit = billedRevenue * grossMarginPct;
  const fixedOpex = P.gc.fixedOpexBase + effAccounts * P.gc.fixedOpexPerAccount;
  const variableOpex = billedRevenue * P.gc.variableOpexPct;
  const ebit = grossProfit - fixedOpex - variableOpex;
  const netIncome = ebit > 0 ? ebit * (1 - P.taxRate) : ebit;
  return {
    revenue: billedRevenue,
    grossProfit,
    grossMarginPct,
    fixedOpex,
    variableOpex,
    ebit,
    netIncome,
    netMarginPct: netIncome / billedRevenue,
  };
}

export function mpPL(gmv: number, effAccounts: number): PL {
  const revenue = gmv * P.mp.takeRate; // CKS's actual revenue = the fee
  const grossProfit = revenue * P.mp.grossMarginPct;
  const fixedOpex = P.mp.fixedOpexBase + effAccounts * P.mp.fixedOpexPerAccount;
  const variableOpex = revenue * P.mp.variableOpexPct;
  const ebit = grossProfit - fixedOpex - variableOpex;
  const netIncome = ebit > 0 ? ebit * (1 - P.taxRate) : ebit;
  return {
    revenue,
    grossProfit,
    grossMarginPct: P.mp.grossMarginPct,
    fixedOpex,
    variableOpex,
    ebit,
    netIncome,
    netMarginPct: netIncome / revenue,
  };
}

if (import.meta.main) {
  // deno-lint-ignore no-explicit-any
  const proj: any = JSON.parse(
    await Deno.readTextFile(new URL("./projection.json", import.meta.url)),
  );

  const fmt$ = (n: number) => (n < 0 ? "-" : "") + "$" + (Math.abs(n) / 1e6 >= 1
    ? (Math.abs(n) / 1e6).toFixed(2) + "M"
    : Math.round(Math.abs(n) / 1e3) + "K");
  const pct = (n: number) => (n * 100).toFixed(1) + "%";

  const outRows = proj.rows.map((r: any) => {
  const billed = r.scenarios.baseline.finalRevenue;
  const gc = gcPL(billed, r.effectiveAccounts);
  const mp = mpPL(billed, r.effectiveAccounts);
  return { year: r.year, accounts: r.accountsSigned, billed, gc, mp };
});

console.log(`
CKS NET-INCOME PROJECTION  (revenue ceiling is not the story — take-home is)

  GC / full-ticket model  (gross margin ${pct(1 - P.gc.subPayoutPct - P.gc.materialsPct)}: sub ${pct(P.gc.subPayoutPct)} + materials ${pct(P.gc.materialsPct)} out of every $)
  ┌──────┬──────────┬──────────┬──────────┬──────────┬──────────┬─────────┐
  │ Year │ Billed   │ GrossPft │ FixedOpx │ EBIT     │ NetInc   │ Net %   │`);
console.log("  ├──────┼──────────┼──────────┼──────────┼──────────┼──────────┼─────────┤");
for (const r of outRows) {
  const g = r.gc;
  console.log(
    `  │ Y${String(r.year).padEnd(3)}│ ${fmt$(r.billed).padStart(8)} │ ${fmt$(g.grossProfit).padStart(8)} │ ${fmt$(g.fixedOpex).padStart(8)} │ ${fmt$(g.ebit).padStart(8)} │ ${fmt$(g.netIncome).padStart(8)} │ ${pct(g.netMarginPct).padStart(7)} │`,
  );
}
console.log("  └──────┴──────────┴──────────┴──────────┴──────────┴──────────┴─────────┘");

console.log(`
  Marketplace / ${pct(P.mp.takeRate)}-fee model  (CKS revenue = fee on job value; crew paid around it)
  ┌──────┬──────────┬──────────┬──────────┬──────────┬─────────┐
  │ Year │ GMV      │ Fee Rev  │ FixedOpx │ NetInc   │ Net %   │`);
console.log("  ├──────┼──────────┼──────────┼──────────┼──────────┼─────────┤");
for (const r of outRows) {
  const m = r.mp;
  console.log(
    `  │ Y${String(r.year).padEnd(3)}│ ${fmt$(r.billed).padStart(8)} │ ${fmt$(m.revenue).padStart(8)} │ ${fmt$(m.fixedOpex).padStart(8)} │ ${fmt$(m.netIncome).padStart(8)} │ ${pct(m.netMarginPct).padStart(7)} │`,
  );
}
console.log("  └──────┴──────────┴──────────┴──────────┴──────────┴─────────┘");

// Breakeven year (first year net income > 0) for GC model
const gcBreakeven = outRows.find((r: any) => r.gc.netIncome > 0)?.year ?? null;
const ceilingRow = outRows[outRows.length - 1];
console.log(`
  KEY TAKEAWAYS (GC model):
  • Breakeven: Year ${gcBreakeven ?? "—"} (fixed opex drags early years to/below zero)
  • At the revenue ceiling: net income ${fmt$(ceilingRow.gc.netIncome)}/yr on ${fmt$(ceilingRow.billed)} billed = ${pct(ceilingRow.gc.netMarginPct)} net
  • This is a THIN-margin, operating-leverage business: the value is in
    volume + reliability, not per-job economics. A single market caps take-home
    in the low-to-mid six figures. Multi-market expansion is the lever for
    materially higher net income.
`);

await Deno.writeTextFile(
  new URL("./margins.json", import.meta.url),
  JSON.stringify({ params: P, rows: outRows, gcBreakeven }, null, 2),
);
console.log("Wrote estimator/margins.json");
}
