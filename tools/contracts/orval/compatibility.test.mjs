import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import YAML from "yaml";
import { assertCompatible } from "./compatibility.mjs";

const root = path.resolve(import.meta.dirname, "../../..");
const baseline = YAML.parse(execFileSync("git", [
  "show", "review-platform-contract-v1.0.1:contracts/review-platform/v1/openapi.yaml",
], { cwd: root, encoding: "utf8" }));
const current = YAML.parse(fs.readFileSync(
  path.join(root, "contracts/review-platform/v1/openapi.yaml"), "utf8",
));

test("document cycle is additive to the original consumer contract", () => {
  assert.doesNotThrow(() => assertCompatible(baseline, current));
});

for (const [name, mutate] of [
  ["removed original endpoint", (schema) => { delete schema.paths["/v1/bootstrap"]; }],
  ["changed version identifier", (schema) => {
    schema.components.schemas.Document.properties.id = { type: "integer" };
  }],
  ["fix state inserted into validity decision", (schema) => {
    schema.components.schemas.HumanDecision.properties.status.enum.push("resolved");
  }],
  ["new required locale on old runs", (schema) => {
    schema.components.schemas.ReviewRun.required.push("locale");
  }],
  ["mutating the original report DTO", (schema) => {
    schema.components.schemas.ReviewReport.properties.resolution = { type: "string" };
  }],
]) {
  test(`rejects ${name}`, () => {
    const changed = structuredClone(current);
    mutate(changed);
    assert.throws(() => assertCompatible(baseline, changed));
  });
}
