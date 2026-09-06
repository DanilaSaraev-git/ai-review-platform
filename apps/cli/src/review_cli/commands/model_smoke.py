from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import anyio
import typer
from review_core.application.model_retry import generate_with_retry
from review_core.canonical import digest_bytes, digest_value, loads_no_duplicates
from review_core.dialogue.engine import DialogueEngine, DialogueMappingContext
from review_core.ports.models import (
    FinishReason,
    GenerationResult,
    JsonValue,
    ModelAdapterError,
    ModelProfileSnapshot,
)
from review_core.review.engine import MappingContext, ReviewEngine, ReviewFragment
from review_core.review.prompt import PromptBudgetExceeded
from review_runtime.composition import compose_model_runtime
from review_runtime.config.model_profiles import ModelProfile, profile_config_digest
from review_runtime.models.config import FileSecretProvider
from review_runtime.reports import CanonicalReportValidator, ModelReviewOutputValidator
from review_runtime.skills.executor import SkillExecutor
from review_runtime.skills.registry import SkillRegistry


class SmokeFailure(Exception):
    """A safe failure classification, without provider text or local configuration."""

    def __init__(self, code: str, phase: str) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase


@contextmanager
def _validate_model_output(phase: str) -> Iterator[None]:
    try:
        yield
    except ValueError:
        raise SmokeFailure("model_output_invalid", phase) from None


def model_smoke(
    profile: Path = typer.Option(..., exists=True, dir_okay=False),
    fixture: Path = typer.Option(..., exists=True, dir_okay=False),
    skill: Path = typer.Option(Path("skills/review-data-spec"), exists=True, file_okay=False),
    credential: Path | None = typer.Option(None, exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, dir_okay=False),
) -> None:
    """Explicitly call one endpoint for review and dialogue compatibility evidence."""
    try:
        evidence = anyio.run(_run_smoke, profile, fixture, skill, credential)
    except SmokeFailure as error:
        typer.echo(
            json.dumps({"status": "failed", "code": error.code, "phase": error.phase}),
            err=True,
        )
        raise typer.Exit(2) from None
    except ModelAdapterError as error:
        typer.echo(
            json.dumps({"status": "failed", "code": error.code.value, "retryable": error.retryable}),
            err=True,
        )
        raise typer.Exit(2) from None
    except PromptBudgetExceeded:
        typer.echo(json.dumps({"status": "failed", "code": "context_limit"}), err=True)
        raise typer.Exit(2) from None
    except (OSError, ValueError):
        typer.echo(
            json.dumps({"status": "failed", "code": "invalid_configuration", "phase": "configuration"}),
            err=True,
        )
        raise typer.Exit(2) from None
    encoded = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    typer.echo(encoded)


async def _run_smoke(
    profile_path: Path, fixture: Path, skill_path: Path, credential_path: Path | None
) -> dict[str, object]:
    root = Path(__file__).resolve().parents[5]
    profile = ModelProfile.model_validate(json.loads(profile_path.read_text(encoding="utf-8")))
    if profile.adapter_kind != "openai_compatible":
        raise ValueError("model smoke requires an external model profile")
    resolved_skill = SkillRegistry(
        root / "contracts/review-platform/v1/schemas/skill-manifest.schema.json",
        engine_version="0.1.0",
        model_capabilities=frozenset(profile.capabilities),
    ).resolve(skill_path)
    schemas = {
        purpose: json.loads(
            (
                root
                / f"specs/004-llm-review-integration/contracts/model-output.{name}.v1.schema.json"
            ).read_text()
        )
        for purpose, name in (("review", "review"), ("finding_dialogue", "dialogue"))
    }
    executor = SkillExecutor(schemas, package=resolved_skill)
    review_output = ModelReviewOutputValidator(
        root / "specs/004-llm-review-integration/contracts/model-output.review.v1.schema.json"
    )
    canonical_report = CanonicalReportValidator(root / "contracts/review-platform/v1/openapi.yaml")
    secrets = None
    if profile.secret_ref is not None:
        if credential_path is None:
            raise ValueError("credential file is required by the profile")
        secrets = FileSecretProvider(profile.secret_ref, credential_path)
    runtime = compose_model_runtime(
        profile=profile, secrets=secrets, max_response_bytes=1_048_576
    )
    snapshot = ModelProfileSnapshot(profile.id, profile.version, profile_config_digest(profile))
    fixture_bytes = fixture.read_bytes()
    text = fixture_bytes.decode("utf-8")
    if not text.strip():
        raise ValueError("model smoke requires a nonempty fixture")
    document_id = str(uuid4())
    fragment = {
        "id": "source-main-lines-1-1",
        "kind": "paragraph",
        "text": text,
        "location": {
            "kind": "text",
            "line_start": 1,
            "line_end": len(text.splitlines()) or 1,
            "char_start": 0,
            "char_end": len(text),
        },
    }
    source = {
        "id": "source-main",
        "role": "document",
        "name": fixture.name,
        "media_type": "text/plain",
        "sha256": digest_bytes(fixture_bytes),
        "status": "available",
        "diagnostics": [],
        "fragments": [fragment],
    }
    profile_input = {
        "id": str(uuid4()),
        "version": "1.0.0",
        "name": "Endpoint smoke",
        "role": "Technical reviewer",
        "goal": "Return contract-valid synthetic results",
        "checks": ["Contract conformance"],
    }
    fragments = {
        str(fragment["id"]): ReviewFragment(
            id=str(fragment["id"]),
            source_id="source-main",
            document_id=document_id,
            source_name=fixture.name,
            text=text,
            location=cast(dict[str, Any], fragment["location"]),
        )
    }
    skill_snapshot = {
        "id": resolved_skill.manifest["id"],
        "version": resolved_skill.manifest["version"],
        "package_sha256": resolved_skill.package_digest,
    }
    dialogue_policy = {"id": "endpoint-smoke", "version": "1.0.0", "max_member_turns": 1}
    execution_snapshot = {
        "profile": {
            "id": profile_input["id"],
            "version": profile_input["version"],
            "digest": digest_value(profile_input),
        },
        "skill": skill_snapshot,
        "model_profile": {
            "id": snapshot.id,
            "version": snapshot.version,
            "config_sha256": snapshot.config_sha256,
        },
        "dialogue_policy": {**dialogue_policy, "digest": digest_value(dialogue_policy)},
        "engine_version": "0.1.0",
    }
    run_id = str(uuid4())
    review_input: dict[str, Any] = {
        "contract_version": "review-input.v1",
        "run_id": run_id,
        "document_source_id": "source-main",
        "sources": [source],
        "review_scope": {"target_fragment_ids": [fragment["id"]]},
        "profile": profile_input,
        "options": {"locale": "en-US", "max_findings": 500},
    }
    trusted_review = _instructions(executor, "review")
    review_engine = ReviewEngine()

    def review_request(_ordinal: int, remaining: float):  # type: ignore[no-untyped-def]
        return review_engine.prepare_generation_request(
            review_input=cast(dict[str, JsonValue], review_input),
            skill_instructions=trusted_review,
            request_id=str(uuid4()),
            work_item_id="endpoint-smoke-review",
            response_schema=executor.output_schemas["review"],
            model_profile=snapshot,
            max_input_utf8_bytes=profile.max_input_utf8_bytes,
            max_output_tokens=profile.max_output_tokens,
            timeout_seconds=remaining,
        )

    started = datetime.now(UTC)
    async with runtime:
        review_result = await generate_with_retry(
            runtime.adapter, review_request, deadline=time.monotonic() + 300, clock=time.monotonic
        )
        with _validate_model_output("review_schema"):
            _require_complete(review_result)
            compact = executor.validate_output("review", review_output.parse_and_validate(review_result.text))
        with _validate_model_output("review_semantics"):
            report = review_engine.map_model_output(
                compact,
                context=MappingContext(
                    run_id=run_id,
                    report_id=str(uuid4()),
                    created_at=datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                    primary_source_id="source-main",
                    target_fragment_ids=(str(fragment["id"]),),
                    fragments=fragments,
                    provenance={
                        "execution_snapshot": execution_snapshot,
                        "model": _model_provenance(review_result),
                        "sources": [{
                            "source_id": source["id"],
                            "document_id": document_id,
                            "role": source["role"],
                            "filename": source["name"],
                            "sha256": source["sha256"],
                            "status": source["status"],
                            "diagnostics": source["diagnostics"],
                        }],
                    },
                ),
            )
            canonical_report.validate(report)
        if not report["findings"]:
            raise SmokeFailure("fixture_no_finding", "dialogue_preparation")
        dialogue_engine = DialogueEngine()
        turn_id = str(uuid4())
        dialogue_input: dict[str, Any] = {
            "contract_version": "finding-dialogue-input.v1",
            "run_id": run_id,
            "dialogue_id": str(uuid4()),
            "finding": report["findings"][0],
            "sources": [source],
            "profile": profile_input,
            "history": [],
            "current_turn": {
                "turn_id": turn_id,
                "ordinal": 1,
                "member_message": {
                    "message_id": str(uuid4()),
                    "content": "Clarify the finding without recording a Human Decision.",
                },
                "follow_up_allowed": True,
            },
            "options": {"locale": "en-US"},
        }

        def dialogue_request(_ordinal: int, remaining: float):  # type: ignore[no-untyped-def]
            return dialogue_engine.prepare_generation_request(
                dialogue_input=cast(dict[str, JsonValue], dialogue_input),
                skill_instructions=_instructions(executor, "finding_dialogue"),
                request_id=str(uuid4()),
                turn_id=turn_id,
                response_schema=executor.output_schemas["finding_dialogue"],
                model_profile=snapshot,
                max_input_utf8_bytes=profile.max_input_utf8_bytes,
                max_output_tokens=profile.max_output_tokens,
                timeout_seconds=remaining,
            )

        dialogue_result = await generate_with_retry(
            runtime.adapter,
            dialogue_request,
            deadline=time.monotonic() + 60,
            clock=time.monotonic,
        )
        with _validate_model_output("dialogue_schema"):
            _require_complete(dialogue_result)
            compact_dialogue = executor.validate_output(
                "finding_dialogue", loads_no_duplicates(dialogue_result.text)
            )
        with _validate_model_output("dialogue_semantics"):
            dialogue_engine.map_model_output(
                compact_dialogue,
                context=DialogueMappingContext(
                    fragments=fragments,
                    provenance={"skill": skill_snapshot, "model": _model_provenance(dialogue_result)},
                ),
            )
    return {
        "status": "verified",
        "checked_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": profile.id,
            "version": profile.version,
            "config_sha256": profile_config_digest(profile),
        },
        "skill": {
            "id": resolved_skill.manifest["id"],
            "version": resolved_skill.manifest["version"],
            "package_sha256": resolved_skill.package_digest,
        },
        "review": _result_evidence(review_result),
        "dialogue": _result_evidence(dialogue_result),
    }


def _instructions(executor: SkillExecutor, purpose: str) -> str:
    instructions = executor.trusted_instructions(purpose)
    return "\n\n".join(
        [instructions.primary]
        + [item.content.decode("utf-8") for item in instructions.references]
    )


def _result_evidence(result: GenerationResult) -> dict[str, object]:
    return {
        "provider": result.provider,
        "model": result.model,
        "model_version": result.model_version,
        "finish_reason": result.finish_reason.value,
        "provider_request_id": result.provider_request_id,
        "latency_ms": result.latency_ms,
        "usage": None
        if result.usage is None
        else {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
        },
    }


def _require_complete(result: GenerationResult) -> None:
    if result.finish_reason is not FinishReason.STOP:
        raise ValueError("model result did not finish completely")


def _model_provenance(result: GenerationResult) -> dict[str, Any]:
    if any(
        not isinstance(value, str | int | float | bool) and value is not None
        for value in result.safe_parameters.values()
    ):
        raise ValueError("model provenance contains a non-public parameter value")
    return {
        "provider": result.provider,
        "model": result.model,
        "model_version": result.model_version,
        "safe_parameters": result.safe_parameters,
        "usage": {
            "input_tokens": None if result.usage is None else result.usage.input_tokens,
            "output_tokens": None if result.usage is None else result.usage.output_tokens,
        },
    }
