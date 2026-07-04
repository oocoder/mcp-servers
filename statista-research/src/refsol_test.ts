import { assertEquals } from "jsr:@std/assert@^1";
import { ORLANDO_METRO_COUNTIES, parseCount } from "./refsol.ts";

Deno.test("parseCount strips thousands separators", () => {
  assertEquals(parseCount("398"), 398);
  assertEquals(parseCount("33,156"), 33156);
  assertEquals(parseCount("18,604,342"), 18604342);
});

Deno.test("parseCount handles a zero/empty-ish result", () => {
  assertEquals(parseCount("0"), 0);
});

Deno.test("ORLANDO_METRO_COUNTIES is the proven 4-county Orlando metro set", () => {
  assertEquals(ORLANDO_METRO_COUNTIES.length, 4);
  const byName = Object.fromEntries(ORLANDO_METRO_COUNTIES.map((c) => [c.name, c.fips]));
  assertEquals(byName["Orange"], "12095");
  assertEquals(byName["Seminole"], "12117");
  assertEquals(byName["Osceola"], "12097");
  assertEquals(byName["Lake"], "12069");
});
