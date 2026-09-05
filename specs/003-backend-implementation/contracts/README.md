# Internal MVP contracts

The only public API contract remains `contracts/review-platform/v1`. Feature 003 does not fork or modify it.

Active internal contracts for the local MVP:

- `runtime-config.v1.schema.json`: deterministic budgets/policy and exact trusted fixture binding.
- `trusted-fixture-expected-output.v1.schema.json`: packaged expected synthetic result.
- `canonicalization.md`: RFC 8785 bytes, SHA-256 and strong ETag rules.
- `runtime-semantics.md`: synchronous one-process execution and persistence semantics.
- `test-matrix.md`: active MVP FR/SC evidence mapping.

Deferred compatibility artifacts remain versioned but are not default-runtime dependencies:

- `job-envelope.v1.schema.json`: future queue boundary.
- `poc-import-view.v1.schema.json` and `poc-v1-mapping.md`: retained CLI/PoC adapter.

No internal schema may expand or contradict canonical HTTP v1 response bodies.
