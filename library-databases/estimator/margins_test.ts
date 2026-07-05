import { assertAlmostEquals, assertEquals } from "jsr:@std/assert@^1";
import { gcPL, mpPL, P } from "./margins.ts";

// Guard: these tests assume the DEFAULT config (no env overrides).
Deno.test("default config matches assumed benchmarks", () => {
  assertEquals(P.gc.subPayoutPct, 0.48);
  assertEquals(P.gc.materialsPct, 0.20);
  assertEquals(P.mp.takeRate, 0.18);
  assertEquals(P.mp.grossMarginPct, 0.85);
  assertEquals(P.taxRate, 0.25);
});

Deno.test("gcPL gross margin is always 1 - sub - materials, independent of inputs", () => {
  const expected = 1 - 0.48 - 0.20; // 0.32
  assertAlmostEquals(gcPL(1_000_000, 10).grossMarginPct, expected, 1e-12);
  assertAlmostEquals(gcPL(7_638_840, 130).grossMarginPct, expected, 1e-12);
  assertAlmostEquals(gcPL(500_000, 20).grossMarginPct, expected, 1e-12);
});

Deno.test("gcPL reproduces Year-6 numbers from projection.json", () => {
  const pl = gcPL(7638839.999999999, 130);
  assertAlmostEquals(pl.ebit, 1235544.7999999998, 1e-4);
  assertAlmostEquals(pl.netIncome, 926658.5999999999, 1e-4);
  assertAlmostEquals(pl.netMarginPct, 0.12130881128548313, 1e-4);
});

Deno.test("gcPL crosses from loss to profit as scale increases", () => {
  const small = gcPL(500_000, 20);
  assertEquals(
    small.netIncome < 0,
    true,
    "small billed revenue should not cover fixed opex",
  );
  const year6 = gcPL(7638839.999999999, 130);
  assertEquals(
    year6.netIncome > 0,
    true,
    "at Year-6 scale the model should be profitable",
  );
});

Deno.test("mpPL revenue = GMV * takeRate", () => {
  assertEquals(mpPL(1_000_000, 10).revenue, 1_000_000 * 0.18);
  assertEquals(mpPL(7638839.999999999, 130).revenue, 7638839.999999999 * 0.18);
});

Deno.test("mpPL reproduces Year-6 numbers from projection.json", () => {
  const pl = mpPL(7638839.999999999, 130);
  assertAlmostEquals(pl.revenue, 1374991.1999999997, 1e-4);
  assertAlmostEquals(pl.netIncome, 527057.4179999998, 1e-4);
  assertAlmostEquals(pl.netMarginPct, 0.3833169390465917, 1e-4);
});

Deno.test("tax is only applied when profitable — a loss passes through untaxed", () => {
  const pl = gcPL(100_000, 20);
  assertEquals(pl.ebit < 0, true, "tiny billed revenue should yield negative EBIT");
  // netIncome = ebit > 0 ? ebit * (1 - taxRate) : ebit  -> loss is unmodified
  assertEquals(pl.netIncome, pl.ebit);

  const plMp = mpPL(100_000, 20);
  assertEquals(plMp.ebit < 0, true, "tiny GMV should yield negative EBIT");
  assertEquals(plMp.netIncome, plMp.ebit);
});
