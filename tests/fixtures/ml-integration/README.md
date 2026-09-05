# Synthetic ML integration fixtures

Authored on 2026-09-05 for feature 004 engineering tests. Every document, quote, proposed schedule, and response is synthetic. These files contain no customer material or credentials and are not model-generated evidence or a production harness.

- `skill/` is a declarative product package consumed by `SkillRegistry`, not an installable Codex skill. Its manifest owns the operation inventory and file hashes.
- `primary.md` supplies one primary fragment, `source-main-lines-1-2`; `context.md` supplies `source-context-1-lines-1-1`.
- `review-response.json` is a compact semantic review response with one finding and complete primary coverage. `dialogue-response.json` is an advisory assistant message with primary and context anchors. A caller can use either JSON object's serialized text as a scripted model reply.

The response fixtures intentionally omit service IDs, offsets, and provenance. `tests/contract/test_ml_fixture_package.py` adds an explicitly authored test envelope and fixed offsets before validating canonical skill output and applicable semantic checks. It is not the future production mapper or the internal response schemas planned in T018/T027.

The primary quote occupies Unicode offsets `[0, 23)` and the context quote `[0, 30)`. Each occurs once in its addressed fragment. The proposed 04:00 schedule is an invented candidate, not a fact extracted from the documents or a Human Decision.
