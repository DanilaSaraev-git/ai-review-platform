import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import SwaggerParser from "@apidevtools/swagger-parser";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import YAML from "yaml";
import { execFileSync } from "node:child_process";
import { assertCompatible } from "./compatibility.mjs";

const root = path.resolve(import.meta.dirname, "../../..");
const contractRoot = path.join(root, "contracts/review-platform/v1");
const internalRoot = path.join(root, "specs/003-backend-implementation/contracts");
const openapiPath = path.join(contractRoot, "openapi.yaml");

const source = fs.readFileSync(openapiPath, "utf8");
const parsedDocument = YAML.parseDocument(source, { uniqueKeys: true });
if (parsedDocument.errors.length) {
  throw new Error(parsedDocument.errors.map((error) => error.message).join("; "));
}
const openapi = parsedDocument.toJS();
await SwaggerParser.validate(openapiPath);
const baselineDocument = YAML.parseDocument(
  execFileSync("git", ["show", "review-platform-contract-v1.0.1:contracts/review-platform/v1/openapi.yaml"], { cwd: root, encoding: "utf8" }),
  { uniqueKeys: true },
);
if (baselineDocument.errors.length) throw new Error("v1.0.1 baseline YAML is invalid");
assertCompatible(baselineDocument.toJS(), openapi);

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);

const readJson = (file) => {
  const document = YAML.parseDocument(fs.readFileSync(file, "utf8"), { uniqueKeys: true });
  if (document.errors.length) throw new Error(`${file}: ${document.errors.map((error) => error.message).join("; ")}`);
  return document.toJS();
};

const validate = (schema, value, label) => {
  const validator = ajv.compile(schema);
  if (!validator(value)) {
    throw new Error(`${label}: ${ajv.errorsText(validator.errors, { separator: "; " })}`);
  }
};

const skillExamples = {
  "review-input.json": "review-input.schema.json",
  "review-output.json": "review-output.schema.json",
  "finding-dialogue-input.json": "finding-dialogue-input.schema.json",
  "finding-dialogue-output.json": "finding-dialogue-output.schema.json",
  "skill-manifest.json": "skill-manifest.schema.json",
};
for (const [exampleName, schemaName] of Object.entries(skillExamples)) {
  validate(
    readJson(path.join(contractRoot, "schemas", schemaName)),
    readJson(path.join(contractRoot, "examples/skill", exampleName)),
    exampleName,
  );
}

const httpExamples = {
  "bootstrap.json": "Bootstrap",
  "document.json": "Document",
  "profiles.json": { items: "ReviewProfile" },
  "model-profiles.json": { items: "ModelProfile" },
  "create-review-run.json": "CreateReviewRun",
  "review-run.queued.json": "ReviewRun",
  "review-run.completed.json": "ReviewRun",
  "review-run.failed.json": "ReviewRun",
  "report.json": "ReviewReport",
  "report.partial.json": "ReviewReport",
  "finding-states.json": "FindingStateList",
  "dialogue.open.json": "FindingDialogue",
  "dialogue.generating.json": "FindingDialogue",
  "dialogue.failed.json": "FindingDialogue",
  "create-dialogue-turn.json": "CreateDialogueTurn",
  "retry-dialogue-turn.json": "RetryDialogueTurn",
  "decision.json": "HumanDecision",
  "put-decision.json": "PutFindingDecision",
  "problem.json": "Problem",
  "document-family.json": "DocumentFamily",
  "document-families.json": "DocumentFamilyPage",
  "document-family-version.json": "DocumentFamilyVersion",
  "document-family-versions.json": "DocumentFamilyVersionPage",
  "review-cycle.first.json": "ReviewCycle",
  "review-cycle.persisting.json": "ReviewCycle",
  "review-cycle.partial.json": "ReviewCycle",
  "review-cycle.unavailable.json": "ReviewCycle",
  "compare-review-cycle.json": "CompareReviewCycle",
  "put-review-cycle-link.json": "PutReviewCycleLink",
  "put-issue-resolution.json": "PutIssueResolution"
};
for (const [exampleName, componentName] of Object.entries(httpExamples)) {
  const value = readJson(path.join(contractRoot, "examples/http", exampleName));
  const rootSchema = typeof componentName === "string"
    ? { $ref: `#/components/schemas/${componentName}` }
    : {
        type: "object",
        additionalProperties: false,
        required: ["items"],
        properties: { items: { type: "array", items: { $ref: `#/components/schemas/${componentName.items}` } } },
      };
  validate({ $schema: "https://json-schema.org/draft/2020-12/schema", ...rootSchema, components: openapi.components }, value, exampleName);
}

for (const schemaName of [
  "job-envelope.v1.schema.json",
  "poc-import-view.v1.schema.json",
  "runtime-config.v1.schema.json",
  "trusted-fixture-expected-output.v1.schema.json",
]) {
  const schema = readJson(path.join(internalRoot, schemaName));
  ajv.compile(schema);
}

if (openapi.info.version !== "1.1.0") throw new Error("OpenAPI version must be 1.1.0");
if (openapi.security?.length !== 0 || openapi.components?.securitySchemes) {
  throw new Error("No-auth v1 must not publish security schemes");
}
const serialized = JSON.stringify(openapi);
if (/\"401\"|\"403\"/.test(serialized)) throw new Error("No-auth v1 must not publish 401/403 responses");

console.log("contract schemas, references, examples, and no-auth boundary: ok");
