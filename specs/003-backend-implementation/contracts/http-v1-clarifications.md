# HTTP v1 implementation clarifications

Status: normative for the feature-003 public HTTP surface. Baseline payload schema is `review-platform-contract-v1.0.1`; the additive/documentary changes below became root contract `v1.0.2`. Internal execution follows [runtime-semantics.md](runtime-semantics.md): the local MVP is synchronous, while queue/outbox/lease behavior is deferred.

## Required v1.0.2 delta

1. Set `openapi.info.version` to `1.0.2`; `/v1` path remains unchanged.
2. Add `400 BadRequest` to `listDocuments` and `listReviewRuns` for malformed/unknown cursors; cursor validation is not silently treated as an empty page.
3. Add `404 NotFound` to `uploadDocument`, because every workspace-scoped operation applies configured namespace matching.
4. Add `409 Conflict` to `createReviewProfile` for stale head and unchanged-content races.
5. Describe `CreateReviewProfile.supersedes` and `ReviewProfile.id/version` with the profile rules below, including immutable version rows, a separate CAS family-head pointer and deployment-scoped system profile.
6. Describe `Document.extraction_state=pending` as accepted immutable bytes awaiting or currently undergoing `preparing`; upload itself does not parse the document. Internal extraction `pending|extracting` maps to canonical HTTP `pending`, while `completed|partial|failed` maps one-to-one. Internal model availability `available` maps to HTTP `available`; `unavailable|degraded|unknown`, missing or expired observation maps to HTTP `unavailable`. Requested sources are snapshotted at create-run, while terminal prepared-source status/fragments/diagnostics are fixed append-once after extraction.
7. Define report/content ETag as quoted strong SHA-256 of exact immutable bytes and canonical report timestamps as UTC `YYYY-MM-DDTHH:mm:ss.ffffffZ`; conditional GET is not added in v1.0.2.
8. Package Swagger/API-doc assets for offline runtime. This changes release assets, not DTO.
9. Make conformance evidence enumerate every existing or newly added `400/404/409` branch shown below; no canonical negative response may be omitted merely because its schema is shared.
10. Update root `README.md`, `CHANGELOG.md`, affected examples/tests and tag `review-platform-contract-v1.0.2` together. FastAPI export comparison, old example validation and Orval generation/typecheck through the exact-pinned backend-owned `tools/contracts/orval/` harness must pass before dependent backend code treats v1.0.2 as baseline; this gate neither reads nor changes `apps/web/`.

If a change requires a new mandatory request/response field, removes a field/enum, changes an existing status meaning or URL, it is breaking and MUST NOT enter this patch.

## Operation conformance

| operationId | Application use case | Required negative evidence |
| --- | --- | --- |
| `getBootstrap` | read configured deployment projection | unhealthy/missing config is readiness failure, not alternate tenant selection |
| `listDocuments` | cursor list immutable versions | invalid cursor `400`, workspace mismatch `404` |
| `uploadDocument` | stage/hash/promote/register immutable bytes | invalid/empty/type mismatch `400`, namespace `404`, size `413` |
| `getDocument` | read immutable metadata | resource/namespace `404` |
| `downloadDocument` | stream saved exact bytes | resource/namespace `404`; strong content ETag |
| `listReviewProfiles` | list system + configured workspace versions | namespace `404` |
| `createReviewProfile` | create family/version | malformed/system target `400`, namespace/missing ref `404`, stale/unchanged `409` |
| `listModelProfiles` | list safe selectable metadata | namespace `404`; never credentials |
| `listReviewRuns` | stable cursor history | invalid cursor `400`, namespace `404` |
| `createReviewRun` | requested sources + exact config snapshot + synchronous local execution | malformed request/ref `400`, missing/namespace ref `404`, idempotency/body conflict `409` |
| `getReviewRun` | read state/progress/error | resource/namespace `404` |
| `cancelReviewRun` | request cooperative cancel | resource/namespace `404`, terminal/publish-won `409` |
| `getReviewReport` | stream exact canonical bytes | resource/namespace `404`, not published `409`; stable ETag |
| `listFindingStates` | mutable overlay list | resource/namespace `404`, report unavailable `409` |
| `getFindingDialogue` | read ordered dialogue projection | resource/namespace `404`, report unavailable `409` |
| `createFindingDialogueTurn` | create one member turn + synchronous local response | malformed body `400`, resource/namespace `404`, stale/blocked/key conflict `409` |
| `retryFindingDialogueTurn` | add attempt to failed turn | malformed body `400`, resource/namespace `404`, stale/non-failed/key conflict `409` |
| `putFindingDecision` | CAS human decision | malformed/invalid decision body `400`, resource/namespace `404`, stale/state conflict `409` |

All errors use `application/problem+json` with stable `code` and safe `request_id`. Stack traces, paths, document/message contents, raw provider output and secrets are forbidden in Problem Details. This restriction does not remove the exact bytes, evidence quotes, member messages or assistant content from their purpose-built canonical document/report/dialogue success responses; metadata-only responses, queue payloads and diagnostics remain content-free.

## Configured namespace

- Path `workspaceId` must equal configured workspace UUID before use-case execution.
- A resource UUID that exists elsewhere is indistinguishable from absent and returns the same `404` Problem.
- There are no `401/403`, security schemes, caller identity, account, role or permission branches.
- Actor returned by bootstrap is attribution only and is applied server-side to accepted actions.

## Profile versioning

Public `ReviewProfile.id` is the logical family UUID.

### New family

`supersedes=null` creates a workspace family at `1.0.0`. A separate call with the same name is still a separate family; names are display values, not identity. The default system profile is deployment-scoped release data, visible to the configured workspace but neither owned nor mutable through this endpoint.

### Next version

`supersedes={id,version}` is valid only when:

- the family/version exists in configured workspace;
- scope is `workspace`;
- the version is current head;
- canonical semantic digest of the requested `name/role/goal/checks` differs.

The server inserts the next immutable patch version under the same ID and CAS-updates a separate mutable family-head pointer; no existing version row is changed. Missing/foreign namespace is `404`; attempting to supersede a visible system profile is `400 invalid_supersedes`; stale head is `409 profile_version_conflict`; unchanged semantic content is `409 profile_content_unchanged`.

Client cannot choose SemVer in v1. A future major/minor workflow requires an additive operation or a new contract decision.

## Document extraction projection

- Upload response `201` means exact bytes, metadata and deterministic extraction result are durable in the synchronous local MVP. The canonical `pending` value remains reserved for a future asynchronous profile.
- Create run snapshots requested source identity/order/role, immutable extraction fragments and exact config refs before synchronous review execution.
- `completed|partial|failed` extraction results are immutable and visible on subsequent `get/list`.
- A partial primary with usable fragments contributes source-level `CoverageGap(code=source_partial, fragment_id=null, reason=primary_source_partial)` plus the exact reviewed-or-gap partition of every known primary fragment. A primary with no usable fragment makes run failed. Optional context partial/failed becomes provenance/gap as defined by the skill contract.
- In deterministic mode, input outside the trusted fixture digest/config allowlist yields a zero-finding partial report: every known primary target fragment is a fragment-level `CoverageGap(code=other, reason=semantic_analysis_not_performed)` and `reviewed_fragment_ids` is empty.

## Immutable representations

- Document content GET returns stored original bytes and `ETag: "<sha256>"`.
- Report GET returns stored JCS bytes and `ETag: "<sha256>"`.
- Timestamp strings included in a canonical report are normalized before JCS to UTC `YYYY-MM-DDTHH:mm:ss.ffffffZ` with exactly six fractional digits.
- Dialogue and decisions are never embedded into or used to regenerate report bytes.
- `If-None-Match` behavior is out of contract until explicitly added; clients may cache using ETag but cannot assume `304` in v1.0.2.

## Export compatibility gate

CI exports FastAPI OpenAPI, normalizes non-semantic framework metadata, and compares every path, operation, parameter, response, schema, required field and enum to root canonical v1.0.2. Backend may be stricter only for documented semantic validation; it may not expose undocumented required input or endpoint.
