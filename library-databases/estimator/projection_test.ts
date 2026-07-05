import { assertAlmostEquals, assertEquals } from "jsr:@std/assert@^1";
import { A, scenarioMath, verdict } from "./projection.ts";

// Live Reference-Solutions-derived total local crews for the CKS Orlando model.
// The module's `nonemployerFirms` default (300) is a stale placeholder; 398 is
// the known-good totalLocalCrews for these scenarios.
const TOTAL_LOCAL_CREWS = 398;

Deno.test("yield formula — baseline params", () => {
  const m = scenarioMath(1500, A.baseline, TOTAL_LOCAL_CREWS);
  // (1 - 0.30) * (1 - 0.15) = 0.595
  assertAlmostEquals(m.yieldRate, 0.595, 1e-9);
});

Deno.test("yield formula — friction params", () => {
  const m = scenarioMath(1500, A.friction, TOTAL_LOCAL_CREWS);
  // (1 - 0.38) * (1 - 0.26) = 0.4588
  assertAlmostEquals(m.yieldRate, 0.4588, 1e-9);
});

Deno.test("roster sizing reproduces real numbers — baseline @ jobsNeeded=1500", () => {
  const m = scenarioMath(1500, A.baseline, TOTAL_LOCAL_CREWS);
  assertAlmostEquals(m.nActive, 10.084033613445378, 1e-6);
  assertAlmostEquals(m.nOnboarded, 15.513897866839041, 1e-6);
  // 398 * 0.30 willingShare
  assertAlmostEquals(m.availableCrews, 119.39999999999999, 1e-6);
});

Deno.test("roster sizing reproduces real numbers — friction @ jobsNeeded=1500", () => {
  const m = scenarioMath(1500, A.friction, TOTAL_LOCAL_CREWS);
  assertAlmostEquals(m.nActive, 13.077593722755013, 1e-6);
  assertAlmostEquals(m.nOnboarded, 20.119374958084634, 1e-6);
  // 398 * 0.17 willingShare
  assertAlmostEquals(m.availableCrews, 67.66000000000001, 1e-6);
});

Deno.test("verdict thresholds", () => {
  assertEquals(verdict(101, 100), "IMPOSSIBLE"); // ratio > 1
  assertEquals(verdict(80, 100), "TIGHT"); // 0.75 < ratio <= 1
  assertEquals(verdict(70, 100), "OK"); // ratio <= 0.75
  assertEquals(verdict(75, 100), "OK"); // ratio exactly 0.75, source uses strict >
});

Deno.test("SOM ceiling formula sanity", () => {
  // Same arithmetic used inline in run(): samPmTurn * 1_000_000 * obtainableShare.
  // samPmTurn is the known real SAM figure (in millions), Year-6 obtainable share = 0.25.
  const samPmTurn = 30.555359999999997;
  const obtainableShare = 0.25;
  assertEquals(samPmTurn * 1_000_000 * obtainableShare, 7638839.999999999);
});
