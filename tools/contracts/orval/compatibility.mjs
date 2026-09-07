import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import YAML from "yaml";

const parseUnique = (source, label) => {
  const document = YAML.parseDocument(source, { uniqueKeys: true });
  if (document.errors.length) throw new Error(`${label}: ${document.errors.map((error) => error.message).join("; ")}`);
  return document.toJS();
};

const stripDocumentation = (value) => {
  if (Array.isArray(value)) return value.map(stripDocumentation);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value)
      .filter(([key]) => !["description", "summary", "externalDocs"].includes(key))
      .map(([key, child]) => [key, stripDocumentation(child)]));
  }
  return value;
};

const equal = (left, right) => JSON.stringify(stripDocumentation(left)) === JSON.stringify(stripDocumentation(right));
const methods = new Set(["get", "post", "put", "patch", "delete", "options", "head", "trace"]);
const allowedResponses = new Map([
  ["/v1/workspaces/{workspaceId}/documents|get", new Set(["400"])],
  ["/v1/workspaces/{workspaceId}/documents|post", new Set(["404"])],
  ["/v1/workspaces/{workspaceId}/profiles|post", new Set(["409"])],
  ["/v1/workspaces/{workspaceId}/review-runs|get", new Set(["400"])],
]);

export function assertCompatible(baseline, candidate) {
  if (candidate.info?.version !== "1.2.0") throw new Error("candidate info.version is not 1.2.0");
  for (const [route, baselinePath] of Object.entries(baseline.paths)) {
    const candidatePath = candidate.paths[route];
    if (!candidatePath) throw new Error(`${route}: original path removed`);
    if (!equal(baselinePath.parameters, candidatePath.parameters)) throw new Error(`${route}: path parameters changed`);
    const baselineMethods = Object.keys(baselinePath).filter((key) => methods.has(key)).sort();
    const candidateMethods = Object.keys(candidatePath).filter((key) => methods.has(key)).sort();
    if (JSON.stringify(baselineMethods) !== JSON.stringify(candidateMethods)) throw new Error(`${route}: operations changed`);
    for (const method of baselineMethods) {
      const before = baselinePath[method];
      const after = candidatePath[method];
      for (const key of ["operationId", "parameters", "requestBody", "security", "tags"]) {
        if (!equal(before[key], after[key])) throw new Error(`${method.toUpperCase()} ${route}: ${key} changed`);
      }
      for (const [status, response] of Object.entries(before.responses)) {
        if (!(status in after.responses) || !equal(response, after.responses[status])) {
          throw new Error(`${method.toUpperCase()} ${route}: response ${status} changed or removed`);
        }
      }
      const added = Object.keys(after.responses).filter((status) => !(status in before.responses));
      const allowed = allowedResponses.get(`${route}|${method}`) ?? new Set();
      if (added.some((status) => !allowed.has(status)) || added.length !== allowed.size) {
        throw new Error(`${method.toUpperCase()} ${route}: unexpected response delta ${added.join(",")}`);
      }
    }
  }
  for (const section of ["schemas", "parameters", "responses"]) {
    for (const [name, original] of Object.entries(baseline.components?.[section] ?? {})) {
      const current = structuredClone(candidate.components?.[section]?.[name]);
      if (!current) throw new Error(`components.${section}.${name} removed`);
      // v1.2 explicitly permits findings without a verified document link.
      // Permit only removal of finding link cardinality constraints; preserve every
      // field; only document-link cardinality is relaxed.
      if (section === "schemas" && name === "Finding") {
        const expected = structuredClone(original);
        delete expected.allOf;
        if (!equal(expected, current)) throw new Error("Finding has an unapproved breaking shape change");
        current.allOf = original.allOf;
      }
      // Explicitly allow only the approved optional DTO additions.
      // In particular, document IDs, report bytes, required fields and existing
      // status enums must keep their original meaning and shape.
      if (section === "schemas" && name === "ReviewRun" && current.properties?.locale) {
        if (current.required?.includes("locale")) throw new Error("ReviewRun.locale must remain optional");
        if (!equal(current.properties.locale, { type: "string", pattern: "^[a-z]{2}(?:-[A-Z]{2})?$" })) {
          throw new Error("ReviewRun.locale has an unexpected shape");
        }
        delete current.properties.locale;
      }
      if (section === "schemas" && ["DialogueTurn", "CreateDialogueTurn"].includes(name) && current.properties?.attachment_document_ids) {
        if (current.required?.includes("attachment_document_ids")) throw new Error("Attachments must remain optional");
        const shape = structuredClone(current.properties.attachment_document_ids);
        delete shape.description;
        if (!equal(shape, { type: "array", maxItems: 10, uniqueItems: true, items: { type: "string", format: "uuid" } })) {
          throw new Error("Attachment IDs have an unexpected shape");
        }
        delete current.properties.attachment_document_ids;
      }
      if (!equal(original, current)) {
        throw new Error(`components.${section}.${name} has a breaking shape change`);
      }
    }
  }
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const root = path.resolve(import.meta.dirname, "../../..");
  const baselineSource = process.argv[2]
    ? fs.readFileSync(process.argv[2], "utf8")
    : execFileSync("git", ["show", "review-platform-contract-v1.0.1:contracts/review-platform/v1/openapi.yaml"], { cwd: root, encoding: "utf8" });
  const candidatePath = process.argv[3] ?? path.join(root, "contracts/review-platform/v1/openapi.yaml");
  assertCompatible(parseUnique(baselineSource, "baseline"), parseUnique(fs.readFileSync(candidatePath, "utf8"), "candidate"));
  console.log("v1.2.0 matches the approved HTTP changes, including optional finding links: ok");
}
