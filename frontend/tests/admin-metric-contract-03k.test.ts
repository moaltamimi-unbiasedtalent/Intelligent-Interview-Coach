import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import * as C from "@/lib/admin/metricContract";

// 03K: the hand-written TypeScript contract must match the JSON schema generated from the Python models (committed beside it).
const schema = JSON.parse(readFileSync(join(__dirname, "..", "lib", "admin", "metricContract.schema.json"), "utf-8")) as Record<string, any>;

function defs(): Record<string, any> {
  return Object.assign({}, ...Object.values(schema).map((s: any) => s.$defs ?? {}));
}
const props = (name: string) => Object.keys((schema[name] ?? defs()[name]).properties).sort();
function enumOf(p: any): string[] {
  if (p.enum) return p.enum;
  if (p.$ref) return enumOf(defs()[p.$ref.split("/").pop() as string]);
  if (p.items) return enumOf(p.items);
  return (p.anyOf ?? []).flatMap(enumOf);
}

describe("admin metric contract 03K: TS mirrors the Python schema", () => {
  for (const [name, keys] of Object.entries(C.CONTRACT_KEYS)) {
    it(`${name} has exactly the schema's fields`, () => {
      expect(Object.keys(keys).sort()).toEqual(props(name));
    });
  }

  it("enumerations match", () => {
    expect([...C.METRIC_STATES].sort()).toEqual(enumOf(schema.MetricResult.properties.state).sort());
    expect([...C.UNITS].sort()).toEqual(enumOf(schema.MetricDefinition.properties.unit).sort());
    expect([...C.CHART_KINDS].sort()).toEqual(enumOf(defs().ChartSpec.properties.kind).sort());
    expect([...C.PERIOD_KINDS].sort()).toEqual(enumOf(schema.MetricResult.properties.period).sort());
    expect([...C.MISSING_BEHAVIOURS].sort()).toEqual(enumOf(schema.MetricDefinition.properties.missing_behaviour).sort());
    expect([...C.AGGREGATIONS].sort()).toEqual(enumOf(defs().Quantity.properties.aggregation).sort());
  });

  it("every contract model forbids extra properties", () => {
    for (const s of [...Object.values(schema), ...Object.values(defs())]) expect((s as any).additionalProperties).toBe(false);
  });

  it("a missing metric never displays as zero", () => {
    for (const state of ["suppressed", "unavailable", "not_captured"] as const) {
      const text = C.displayMetric({ state, value: null }, "count");
      expect(text).not.toBe("0");
      expect(text).not.toMatch(/^0/);
    }
    expect(C.displayMetric({ state: "ok", value: 0 }, "count")).toBe("0");
    expect(C.displayMetric({ state: "ok", value: 12.5 }, "percent")).toBe("12.5%");
  });
});
