from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from review_core.application.platform import DocumentRecord
from review_core.domain import ServerId
from review_core.review.validation import validate_report

from review_runtime.config.settings import TrustedFixtureBinding
from review_runtime.config.trusted_fixtures import TrustedFixtureRegistry
from review_runtime.config.verify import verify
from review_runtime.documents.pdf import PdfDocumentParser
from review_runtime.documents.text import TextDocumentParser
from review_runtime.models.deterministic import DeterministicModelGateway


class TrustedFixtureReviewExecutor:
    def __init__(
        self,
        root: Path,
        *,
        runtime_config_path: Path | None = None,
        expected_output_path: Path | None = None,
    ) -> None:
        self.root = root
        self.parser = TextDocumentParser()
        trusted = root / "tests/fixtures/synthetic-review/synthetic-spec.md"
        self.trusted_document_sha256 = hashlib.sha256(trusted.read_bytes()).hexdigest()
        self.runtime_config_path = runtime_config_path
        self.expected_output_path = expected_output_path or (
            root / "tests/fixtures/synthetic-review/trusted-fixture-expected-output.v1.json"
        )
        self.schema_path = (
            root
            / "specs/003-backend-implementation/contracts/trusted-fixture-expected-output.v1.schema.json"
        )
        self.gateway, self.templates = self._load_configuration()

    def _load_configuration(
        self,
    ) -> tuple[DeterministicModelGateway, dict[str, dict[str, Any]]]:
        if self.runtime_config_path is None:
            gateway = DeterministicModelGateway.from_manifest(
                self.root / "tests/fixtures/synthetic-review/trusted-manifest.v1.json"
            )
            bindings = [TrustedFixtureBinding.model_validate(value) for value in gateway.bindings]
        else:
            policy = verify(self.runtime_config_path)
            bindings = policy.deterministic_gateway.trusted_fixture_bindings
            if not bindings:
                raise ValueError("runtime config has no trusted fixture bindings")
            gateway = DeterministicModelGateway.from_bindings(
                [binding.model_dump() for binding in bindings]
            )
        registry = TrustedFixtureRegistry(
            self.schema_path,
            {
                binding.expected_output_resource_id: self.expected_output_path
                for binding in bindings
            },
        )
        templates = {
            binding.expected_output_resource_id: registry.resolve(binding).value
            for binding in bindings
        }
        return gateway, templates

    def check_configuration(self) -> bool:
        self._load_configuration()
        return True

    def check_release_configuration(
        self,
        *,
        review_profile_semantic_digest: str,
        skill_package_sha256: str,
        engine_version: str,
    ) -> bool:
        gateway, _ = self._load_configuration()
        binding = gateway.match(
            primary_document_sha256=self.trusted_document_sha256,
            review_profile_semantic_digest=review_profile_semantic_digest,
            skill_package_sha256=skill_package_sha256,
            parser_settings_digest=self.parser.settings_digest,
            engine_version=engine_version,
        )
        if binding is None:
            raise ValueError("runtime config does not bind the release trusted fixture")
        return True

    def execute(
        self,
        *,
        run_id: str,
        report_id: str,
        document: DocumentRecord,
        context: list[DocumentRecord],
        snapshot: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        self.gateway, self.templates = self._load_configuration()
        parser = PdfDocumentParser() if document.media_type == "application/pdf" else self.parser
        primary = parser.parse(document.content, source_id="source-main", document_id=document.id)
        document.fragments = primary
        document.extraction_state = "completed"
        sources = [
            {
                "source_id": "source-main",
                "document_id": document.id,
                "role": "document",
                "filename": document.filename,
                "sha256": document.sha256,
                "status": "available",
                "diagnostics": [],
            }
        ]
        for index, source in enumerate(context, start=1):
            context_parser = PdfDocumentParser() if source.media_type == "application/pdf" else self.parser
            context_parser.parse(source.content, source_id=f"source-context-{index}", document_id=source.id)
            source.extraction_state = "completed"
            sources.append(
                {
                    "source_id": f"source-context-{index}",
                    "document_id": source.id,
                    "role": "context",
                    "filename": source.filename,
                    "sha256": source.sha256,
                    "status": "available",
                    "diagnostics": [],
                }
            )
        target = [fragment["id"] for fragment in primary]
        selector = {
            "primary_document_sha256": document.sha256,
            "review_profile_semantic_digest": snapshot["profile"]["digest"],
            "skill_package_sha256": snapshot["skill"]["package_sha256"],
            "parser_settings_digest": parser.settings_digest,
            "engine_version": snapshot["engine_version"],
        }
        binding = self.gateway.match(**selector)
        trusted = binding is not None
        findings: list[dict[str, Any]] = []
        if trusted:
            assert binding is not None
            expected_output_resource_id = binding["expected_output_resource_id"]
            expected_output_sha256 = binding["expected_output_sha256"]
            trusted_template = self.templates[expected_output_resource_id]
            template = trusted_template["findings"][0]
            anchor_template = template["anchors"][0]
            fragment = primary[anchor_template["primary_fragment_ordinal"] - 1]
            quote = anchor_template["quote"]
            offset = -1
            cursor = 0
            for _ in range(anchor_template["occurrence"]):
                offset = fragment["text"].find(quote, cursor)
                if offset < 0:
                    raise ValueError("Trusted expected-output quote does not resolve.")
                cursor = offset + len(quote)
            findings = [
                {
                    "id": str(ServerId.new()),
                    "ordinal": 1,
                    "kind": template["kind"],
                    "title": template["title"],
                    "problem": template["problem"],
                    "reason": template["reason"],
                    "question": template["question"],
                    "priority": template["priority"],
                    "anchors": [
                        {
                            "source_id": "source-main",
                            "document_id": document.id,
                            "source_name": document.filename,
                            "fragment_id": fragment["id"],
                            "quote": quote,
                            "quote_start": offset,
                            "quote_end": offset + len(quote),
                            "location": fragment["location"],
                        }
                    ],
                    "scope": [fragment["id"]],
                }
            ]
            coverage = {
                "status": "complete",
                "target_fragment_ids": target,
                "reviewed_fragment_ids": target,
                "gaps": [],
            }
            summary = trusted_template["summary"]
            limitations = trusted_template["limitations"]
        else:
            expected_output_sha256 = None
            coverage = {
                "status": "partial",
                "target_fragment_ids": target,
                "reviewed_fragment_ids": [],
                "gaps": [
                    {
                        "source_id": "source-main",
                        "fragment_id": fragment_id,
                        "code": "other",
                        "reason": "semantic_analysis_not_performed",
                    }
                    for fragment_id in target
                ],
            }
            summary = "No semantic analysis was performed by the deterministic adapter."
            limitations = ["deterministic_mode_no_semantic_analysis"]
        report = {
            "id": report_id,
            "run_id": run_id,
            "created_at": created_at,
            "summary": summary,
            "coverage": coverage,
            "findings": findings,
            "limitations": limitations,
            "provenance": {
                "execution_snapshot": snapshot,
                "model": {
                    "provider": "deterministic",
                    "model": "trusted-fixture-or-gap",
                    "model_version": "1.0.0",
                    "safe_parameters": {
                        "binding_id": binding["binding_id"] if binding is not None else "unbound",
                        "expected_output_sha256": expected_output_sha256,
                    },
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
                "sources": sources,
            },
        }
        validate_report(
            report, {fragment["id"]: fragment for fragment in primary}, primary_source_id="source-main"
        )
        return report
