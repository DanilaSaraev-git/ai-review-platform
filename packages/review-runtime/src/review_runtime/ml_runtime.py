from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import Any
from uuid import uuid4

from review_core.application.dialogue import (
    DialoguePreparationContext,
    PinnedDialogueSkill,
    prepare_dialogue_generation,
)
from review_core.application.execution import (
    AsyncExecutionCoordinator,
    ExecutionAdmission,
    ExecutionClaim,
    ExecutionDeadline,
    ExecutionFailure,
    ExecutionStorage,
    ExecutionTerminal,
)
from review_core.application.model_retry import generate_with_retry, public_model_error_code
from review_core.application.platform import DocumentRecord
from review_core.application.profiles import ProfileVersion
from review_core.canonical import digest_value
from review_core.dialogue.engine import DialogueEngine
from review_core.ports.models import (
    GenerationRequest,
    GenerationResult,
    ModelAdapter,
    ModelAdapterError,
    ModelCapabilities,
    ModelProfileSnapshot,
)
from review_core.review.engine import MappingContext, ReviewEngine, ReviewFragment
from review_core.review.prompt import PromptBudgetExceeded

from review_runtime.composition import ModelRuntime
from review_runtime.config.model_profiles import ModelProfile, profile_config_digest
from review_runtime.documents.pdf import PdfDocumentParser
from review_runtime.documents.text import TextDocumentParser
from review_runtime.postgres.platform import (
    PostgresReviewExecutionStorage,
    PostgresReviewPlatform,
    ReviewStorageRequest,
    utc_now,
    wire_time,
)
from review_runtime.reports import ModelReviewOutputValidator
from review_runtime.skills.executor import SkillExecutor
from review_runtime.skills.registry import ResolvedSkill


@dataclass(frozen=True, slots=True)
class ReviewOperation:
    storage_request: ReviewStorageRequest
    primary: DocumentRecord
    contexts: tuple[DocumentRecord, ...]
    profile: ProfileVersion
    model_profile: ModelProfile
    created_at: datetime


class _ReviewOperationStorage(
    ExecutionStorage[ReviewOperation, dict[str, Any], dict[str, Any]]
):
    def __init__(self, storage: PostgresReviewExecutionStorage) -> None:
        self._storage = storage

    def admit(self, request: ReviewOperation, deadline_at: datetime) -> ExecutionAdmission:
        return self._storage.admit(request.storage_request, deadline_at)

    def claim(self, admission: ExecutionAdmission, owner_token: str) -> ExecutionClaim | None:
        return self._storage.claim(admission, owner_token)

    def save_prepared(self, claim: ExecutionClaim, prepared: dict[str, Any]) -> None:
        self._storage.save_prepared(claim, prepared)

    def publish(
        self, claim: ExecutionClaim, result: dict[str, Any], deadline_at: datetime
    ) -> ExecutionTerminal:
        return self._storage.publish(claim, result, deadline_at)

    def fail(self, claim: ExecutionClaim, failure: ExecutionFailure) -> ExecutionTerminal:
        return self._storage.fail(claim, failure)

    def read_terminal(self, resource_id: str) -> ExecutionTerminal | None:
        return self._storage.read_terminal(resource_id)


class _RecordingAdapter:
    def __init__(self, adapter: ModelAdapter, storage: PostgresReviewExecutionStorage) -> None:
        self._adapter = adapter
        self._storage = storage

    async def capabilities(self) -> ModelCapabilities:
        return await self._adapter.capabilities()

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        import anyio

        attempt_id = await anyio.to_thread.run_sync(self._storage.begin_model_attempt, request)
        try:
            result = await self._adapter.generate(request)
        except ModelAdapterError as error:
            await anyio.to_thread.run_sync(
                partial(self._storage.finish_model_attempt, attempt_id, error=error)
            )
            raise
        except BaseException:
            await anyio.to_thread.run_sync(
                partial(self._storage.finish_model_attempt, attempt_id, unknown_outcome=True)
            )
            raise
        await anyio.to_thread.run_sync(
            partial(self._storage.finish_model_attempt, attempt_id, result=result)
        )
        return result


class _DialogueRecordingAdapter:
    def __init__(
        self,
        adapter: ModelAdapter,
        platform: PostgresReviewPlatform,
        generation_attempt_id: str,
    ) -> None:
        self._adapter = adapter
        self._platform = platform
        self._generation_attempt_id = generation_attempt_id

    async def capabilities(self) -> ModelCapabilities:
        return await self._adapter.capabilities()

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        import anyio

        attempt_id = await anyio.to_thread.run_sync(
            self._platform.begin_dialogue_model_attempt, self._generation_attempt_id, request
        )
        try:
            result = await self._adapter.generate(request)
        except ModelAdapterError as error:
            await anyio.to_thread.run_sync(
                partial(self._platform.finish_dialogue_model_attempt, attempt_id, error=error)
            )
            raise
        except BaseException:
            await anyio.to_thread.run_sync(
                partial(
                    self._platform.finish_dialogue_model_attempt,
                    attempt_id,
                    unknown_outcome=True,
                )
            )
            raise
        await anyio.to_thread.run_sync(
            partial(self._platform.finish_dialogue_model_attempt, attempt_id, result=result)
        )
        return result


class _SingleResultAdapter:
    """Feed one already generated result through the shared dialogue mapper."""

    def __init__(self, result: GenerationResult) -> None:
        self._result = result

    async def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(True, False, False, None, frozenset())

    async def generate(self, _request: GenerationRequest) -> GenerationResult:
        return self._result


class LLMReviewRuntime:
    """Lifespan-owned async review façade for one exact external model profile."""

    def __init__(
        self,
        *,
        platform: PostgresReviewPlatform,
        model_runtime: ModelRuntime,
        model_profile: ModelProfile,
        skill: ResolvedSkill,
        root: Path,
    ) -> None:
        self.platform = platform
        self.model_runtime = model_runtime
        self.model_profile = model_profile
        self.skill = skill
        self.root = root
        self.review_engine = ReviewEngine()
        self.skill_executor = SkillExecutor(
            {
                "review": json.loads(
                    (
                        root
                        / "specs/004-llm-review-integration/contracts/model-output.review.v1.schema.json"
                    ).read_text()
                ),
                "finding_dialogue": json.loads(
                    (
                        root
                        / "specs/004-llm-review-integration/contracts/model-output.dialogue.v1.schema.json"
                    ).read_text()
                ),
            },
            package=skill,
        )
        self.review_output = ModelReviewOutputValidator(
            root / "specs/004-llm-review-integration/contracts/model-output.review.v1.schema.json"
        )
        self.dialogue_engine = DialogueEngine()
        self._recording_adapter = _RecordingAdapter(
            self.model_runtime.adapter, self.platform.review_storage
        )
        self._coordinator = AsyncExecutionCoordinator[
            ReviewOperation, dict[str, Any], dict[str, Any], dict[str, Any]
        ](
            storage=_ReviewOperationStorage(platform.review_storage),
            prepare=self._prepare,
            generate=self._generate,
            validate=self._validate,
            timeout_seconds=platform.settings.review_deadline_seconds,
            finalization_timeout_seconds=platform.settings.finalization_timeout_seconds,
            failure_mapper=self._failure,
        )
        self._dialogue_task_group: Any = None
        self._dialogue_events: dict[str, Any] = {}

    async def __aenter__(self) -> LLMReviewRuntime:
        await self.model_runtime.__aenter__()
        capabilities = await self.model_runtime.adapter.capabilities()
        if not capabilities.text_generation:
            raise RuntimeError("configured model profile cannot generate text")
        await self._coordinator.__aenter__()
        import anyio

        self._dialogue_task_group = await anyio.create_task_group().__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            group = self._dialogue_task_group
            self._dialogue_task_group = None
            if group is not None:
                import anyio

                if exc_type is None:
                    with anyio.move_on_after(30) as grace:
                        for event in tuple(self._dialogue_events.values()):
                            await event.wait()
                    if grace.cancel_called:
                        group.cancel_scope.cancel()
                await group.__aexit__(exc_type, exc, traceback)
            await self._coordinator.__aexit__(exc_type, exc, traceback)
        finally:
            await self.model_runtime.__aexit__(exc_type, exc, traceback)

    async def create_run(
        self, workspace_id: str, body: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        reference = body["model_profile"]
        if reference == {
            "id": self.platform.model_profile["id"],
            "version": self.platform.model_profile["version"],
        }:
            import anyio

            return await anyio.to_thread.run_sync(
                self.platform.create_run, workspace_id, body, idempotency_key
            )
        if reference != {"id": self.model_profile.id, "version": self.model_profile.version}:
            self.platform.exact_model_profile(reference)
            raise RuntimeError("runtime was not composed for the requested model profile")
        listed = self.platform.list_model_profiles(workspace_id)["items"]
        selected = next(item for item in listed if item["id"] == self.model_profile.id)
        if selected["availability"] != "available":
            from review_core.domain.errors import Conflict

            raise Conflict("model_unavailable", "The selected model profile is unavailable.")
        operation = await self._build_operation(
            workspace_id=workspace_id,
            body=body,
            idempotency_key=idempotency_key,
        )
        terminal = await self._coordinator.run(operation)
        return self.platform.get_run(workspace_id, terminal.resource_id).value

    async def create_dialogue_turn(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        import anyio

        reference = await anyio.to_thread.run_sync(
            self.platform.dialogue_model_reference, workspace_id, run_id, finding_id
        )
        if reference != {"id": self.model_profile.id, "version": self.model_profile.version}:
            return await anyio.to_thread.run_sync(
                self.platform.create_dialogue_turn,
                workspace_id,
                run_id,
                finding_id,
                body,
                idempotency_key,
            )
        deadline_at = datetime.now(UTC) + timedelta(
            seconds=self.platform.settings.dialogue_deadline_seconds
        )
        admission = await anyio.to_thread.run_sync(
            lambda: self.platform.admit_external_dialogue(
                workspace_id,
                run_id,
                finding_id,
                body,
                idempotency_key,
                deadline_at=deadline_at,
            )
        )
        await self._submit_dialogue(
            workspace_id,
            run_id,
            finding_id,
            admission["turn_id"],
            admission["attempt_id"],
            replay=admission["replay"],
        )
        return await anyio.to_thread.run_sync(
            self.platform.get_dialogue, workspace_id, run_id, finding_id
        )

    async def retry_dialogue_turn(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        turn_id: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        import anyio

        reference = await anyio.to_thread.run_sync(
            self.platform.dialogue_model_reference, workspace_id, run_id, finding_id
        )
        if reference != {"id": self.model_profile.id, "version": self.model_profile.version}:
            return await anyio.to_thread.run_sync(
                self.platform.retry_dialogue_turn,
                workspace_id,
                run_id,
                finding_id,
                turn_id,
                body,
                idempotency_key,
            )
        deadline_at = datetime.now(UTC) + timedelta(
            seconds=self.platform.settings.dialogue_deadline_seconds
        )
        admission = await anyio.to_thread.run_sync(
            lambda: self.platform.admit_external_dialogue(
                workspace_id,
                run_id,
                finding_id,
                body,
                idempotency_key,
                retry_turn_id=turn_id,
                deadline_at=deadline_at,
            )
        )
        await self._submit_dialogue(
            workspace_id,
            run_id,
            finding_id,
            turn_id,
            admission["attempt_id"],
            replay=admission["replay"],
        )
        return await anyio.to_thread.run_sync(
            self.platform.get_dialogue, workspace_id, run_id, finding_id
        )

    async def _submit_dialogue(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        turn_id: str,
        attempt_id: str,
        *,
        replay: bool,
    ) -> None:
        import anyio

        event = self._dialogue_events.get(attempt_id)
        if event is None and not replay:
            if self._dialogue_task_group is None:
                raise RuntimeError("dialogue coordinator must be entered before submit")
            event = anyio.Event()
            self._dialogue_events[attempt_id] = event
            self._dialogue_task_group.start_soon(
                self._run_dialogue_owned,
                workspace_id,
                run_id,
                finding_id,
                turn_id,
                attempt_id,
                event,
            )
        if event is not None:
            await event.wait()

    async def _run_dialogue_owned(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        turn_id: str,
        attempt_id: str,
        event: Any,
    ) -> None:
        try:
            await self._execute_dialogue(
                workspace_id, run_id, finding_id, turn_id, attempt_id
            )
        finally:
            event.set()

    async def _execute_dialogue(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        turn_id: str,
        attempt_id: str,
    ) -> None:
        import anyio

        owner_token = str(uuid4())
        claimed = await anyio.to_thread.run_sync(
            self.platform.claim_external_dialogue, attempt_id, owner_token
        )
        if not claimed:
            raise RuntimeError("accepted dialogue generation could not be claimed")
        try:
            with anyio.fail_after(self.platform.settings.dialogue_deadline_seconds):
                prepared = await anyio.to_thread.run_sync(
                    self.platform.dialogue_preparation,
                    workspace_id,
                    run_id,
                    finding_id,
                    turn_id,
                )
                fragments = {
                    fragment_id: ReviewFragment(
                        id=fragment_id,
                        source_id=value["source_id"],
                        document_id=value["document_id"],
                        source_name=value["source_name"],
                        text=value["text"],
                        location=value["location"],
                    )
                    for fragment_id, value in prepared["fragments"].items()
                }
                instructions = self.skill_executor.trusted_instructions("finding_dialogue")
                trusted = "\n\n".join(
                    [instructions.primary]
                    + [item.content.decode("utf-8") for item in instructions.references]
                )
                temperature_value = self.model_profile.request_options.get("temperature")
                request = prepare_dialogue_generation(
                    context=DialoguePreparationContext(
                        run_id=run_id,
                        dialogue_id=prepared["dialogue"]["id"],
                        turn_id=turn_id,
                        turn_ordinal=prepared["turn_ordinal"],
                        member_message_id=f"{turn_id}-member",
                        member_message=prepared["turn"]["member_message"],
                        finding=prepared["finding"],
                        sources=tuple(prepared["sources"]),
                        profile=prepared["profile"],
                        completed_history=tuple(prepared["history"]),
                        follow_up_allowed=True,
                        locale="en-US",
                        execution_snapshot=prepared["snapshot"],
                    ),
                    skill=PinnedDialogueSkill(
                        id=str(self.skill.manifest["id"]),
                        version=str(self.skill.manifest["version"]),
                        package_sha256=self.skill.package_digest,
                        instructions=trusted,
                    ),
                    request_id=str(uuid4()),
                    response_schema=self.skill_executor.output_schemas["finding_dialogue"],
                    max_input_utf8_bytes=self.model_profile.max_input_utf8_bytes,
                    max_output_tokens=self.model_profile.max_output_tokens,
                    timeout_seconds=self.platform.settings.dialogue_deadline_seconds,
                    temperature=(
                        float(temperature_value)
                        if isinstance(temperature_value, int | float)
                        and not isinstance(temperature_value, bool)
                        else None
                    ),
                )

                def request_factory(ordinal: int, remaining: float) -> GenerationRequest:
                    return GenerationRequest(
                        request_id=request.request_id if ordinal == 0 else str(uuid4()),
                        purpose=request.purpose,
                        work_item_id=request.work_item_id,
                        trusted_instructions=request.trusted_instructions,
                        untrusted_input=request.untrusted_input,
                        response_schema=request.response_schema,
                        model_profile=request.model_profile,
                        max_output_tokens=request.max_output_tokens,
                        timeout_seconds=remaining,
                        temperature=request.temperature,
                    )

                result = await generate_with_retry(
                    _DialogueRecordingAdapter(
                        self.model_runtime.adapter, self.platform, attempt_id
                    ),
                    request_factory,
                    deadline=time.monotonic()
                    + self.platform.settings.dialogue_deadline_seconds,
                    clock=time.monotonic,
                )
                response = await self.dialogue_engine.execute(
                    adapter=_SingleResultAdapter(result),
                    request=replace(request, request_id=result.request_id),
                    parse_and_validate=lambda text: self.skill_executor.validate_output(
                        "finding_dialogue", json.loads(text)
                    ),
                    fragments=fragments,
                    skill_snapshot=prepared["snapshot"]["skill"],
                )
                await anyio.to_thread.run_sync(
                    self.platform.publish_external_dialogue,
                    turn_id,
                    attempt_id,
                    owner_token,
                    response,
                )
        except BaseException as error:
            if isinstance(error, anyio.get_cancelled_exc_class()):
                failure = ExecutionFailure(
                    "process_interrupted", "The dialogue generation was interrupted.", True
                )
            elif isinstance(error, TimeoutError):
                failure = ExecutionFailure(
                    "deadline_exceeded", "The dialogue generation deadline expired.", True
                )
            else:
                failure = self._dialogue_failure(error)
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(
                    self.platform.fail_external_dialogue,
                    turn_id,
                    attempt_id,
                    owner_token,
                    failure,
                )
            if isinstance(error, anyio.get_cancelled_exc_class()):
                raise

    @staticmethod
    def _dialogue_failure(error: BaseException) -> ExecutionFailure:
        if isinstance(error, PromptBudgetExceeded):
            return ExecutionFailure("context_limit", "The complete input exceeds the model budget.", False)
        if isinstance(error, ModelAdapterError):
            return ExecutionFailure(
                public_model_error_code(error, purpose="dialogue"),
                "The model request could not be completed.",
                error.retryable,
            )
        if isinstance(error, (ValueError, json.JSONDecodeError)):
            return ExecutionFailure(
                "model_output_invalid", "The model response failed validation.", False
            )
        return ExecutionFailure("internal_error", "The operation could not be completed.", True)

    async def _build_operation(
        self, *, workspace_id: str, body: dict[str, Any], idempotency_key: str
    ) -> ReviewOperation:
        import anyio

        return await anyio.to_thread.run_sync(
            self._build_operation_sync, workspace_id, body, idempotency_key
        )

    def _build_operation_sync(
        self, workspace_id: str, body: dict[str, Any], idempotency_key: str
    ) -> ReviewOperation:
        self.platform._workspace(workspace_id)
        context_ids = body.get("context_document_ids", [])
        if len(context_ids) > 50 or len(context_ids) != len(set(context_ids)):
            from review_core.domain.errors import InvalidRequest

            raise InvalidRequest("context_limit", "Context document selection is invalid.")
        primary = self.platform.get_document(workspace_id, body["document_id"])
        contexts = tuple(self.platform.get_document(workspace_id, item) for item in context_ids)
        with self.platform._connect() as connection:
            profile = self.platform._exact_profile(connection, body["profile"])
        snapshot = self.platform._snapshot(profile, body["model_profile"])
        run_id = str(uuid4())
        created = utc_now()
        run = {
            "id": run_id,
            "workspace_id": workspace_id,
            "state": "queued",
            "progress": {"percent": 0, "message": "Review queued"},
            "document_id": primary.id,
            "context_document_ids": [item.id for item in contexts],
            "execution_snapshot": snapshot,
            "created_by": self.platform.actor,
            "created_at": wire_time(created),
            "started_at": None,
            "finished_at": None,
            "cancel_requested_at": None,
            "report_available": False,
            "error": None,
        }
        documents = (primary, *contexts)
        sources = tuple(
            {
                "source_id": "source-main" if ordinal == 1 else f"source-context-{ordinal - 1}",
                "document_id": document.id,
                "role": "document" if ordinal == 1 else "context",
                "ordinal": ordinal,
            }
            for ordinal, document in enumerate(documents, start=1)
        )
        return ReviewOperation(
            storage_request=ReviewStorageRequest(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                request_body=body,
                run_id=run_id,
                snapshot_id=str(uuid4()),
                snapshot=snapshot,
                run_value=run,
                sources=sources,
            ),
            primary=primary,
            contexts=contexts,
            profile=profile,
            model_profile=self.model_profile,
            created_at=created,
        )

    @staticmethod
    def _stable_fragment(source_id: str, fragment: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        location = fragment["location"]
        if "page" in location:
            stable_id = f"{source_id}-page-{location['page']}"
            input_location = {"page": location["page"]}
        else:
            stable_id = f"{source_id}-lines-{location['line_start']}-{location['line_end']}"
            input_location = {
                "line_start": location["line_start"],
                "line_end": location["line_end"],
            }
        value = {
            "id": stable_id,
            "kind": fragment["kind"],
            "text": fragment["text"],
            "location": input_location,
        }
        if fragment["kind"] == "table_row":
            value["cells"] = fragment["cells"]
        return stable_id, value

    def _prepare(self, operation: ReviewOperation, _deadline: ExecutionDeadline) -> dict[str, Any]:
        sources: list[dict[str, Any]] = []
        fragments: dict[str, ReviewFragment] = {}
        persisted_sources: dict[str, Any] = {}
        documents = (operation.primary, *operation.contexts)
        for ordinal, document in enumerate(documents, start=1):
            source_id = "source-main" if ordinal == 1 else f"source-context-{ordinal - 1}"
            parser = PdfDocumentParser() if document.media_type == "application/pdf" else TextDocumentParser()
            parsed = parser.parse(document.content, source_id=source_id, document_id=document.id)
            input_fragments: list[dict[str, Any]] = []
            for fragment in parsed:
                stable_id, input_fragment = self._stable_fragment(source_id, fragment)
                input_fragments.append(input_fragment)
                fragments[stable_id] = ReviewFragment(
                    id=stable_id,
                    source_id=source_id,
                    document_id=document.id,
                    source_name=document.filename,
                    text=fragment["text"],
                    location=fragment["location"],
                )
            source = {
                "id": source_id,
                "role": "document" if ordinal == 1 else "context",
                "name": document.filename,
                "media_type": document.media_type,
                "sha256": document.sha256,
                "status": "available",
                "diagnostics": [],
                "fragments": input_fragments,
            }
            sources.append(source)
            persisted_sources[source_id] = {
                "document_id": document.id,
                "sha256": document.sha256,
                "status": "available",
                "diagnostics": [],
                "fragment_ids": [item["id"] for item in input_fragments],
            }
        target_fragment_ids = tuple(item["id"] for item in sources[0]["fragments"])
        profile = {
            "id": operation.profile.id,
            "version": operation.profile.version,
            "name": operation.profile.name,
            "role": operation.profile.role,
            "goal": operation.profile.goal,
            "checks": list(operation.profile.checks),
        }
        review_input = {
            "contract_version": "review-input.v1",
            "run_id": operation.storage_request.run_id,
            "document_source_id": "source-main",
            "sources": sources,
            "review_scope": {"target_fragment_ids": list(target_fragment_ids)},
            "profile": profile,
            "options": {"locale": operation.storage_request.request_body["locale"], "max_findings": 500},
        }
        work_item_id = self.platform.review_storage.work_item_id(operation.storage_request.run_id)
        instructions = self.skill_executor.trusted_instructions("review")
        trusted = "\n\n".join(
            [instructions.primary]
            + [item.content.decode("utf-8") for item in instructions.references]
        )
        digest = digest_value(review_input)
        return {
            "prepared_input_digest": digest,
            "sources": persisted_sources,
            "work_item": {"source_ids": [item["id"] for item in sources], "input_digest": digest},
            "work_item_id": work_item_id,
            "review_input": review_input,
            "trusted_instructions": trusted,
            "fragments": fragments,
            "target_fragment_ids": target_fragment_ids,
            "operation": operation,
        }

    async def _generate(
        self, prepared: dict[str, Any], deadline: ExecutionDeadline
    ) -> dict[str, Any]:
        profile = self.model_profile
        snapshot = ModelProfileSnapshot(
            id=profile.id,
            version=profile.version,
            config_sha256=profile_config_digest(profile),
        )
        configured_temperature = profile.request_options.get("temperature")

        def request_factory(_ordinal: int, remaining: float) -> GenerationRequest:
            return self.review_engine.prepare_generation_request(
                review_input=prepared["review_input"],
                skill_instructions=prepared["trusted_instructions"],
                request_id=str(uuid4()),
                work_item_id=prepared["work_item_id"],
                response_schema=self.skill_executor.output_schemas["review"],
                model_profile=snapshot,
                max_input_utf8_bytes=profile.max_input_utf8_bytes,
                max_output_tokens=profile.max_output_tokens,
                timeout_seconds=remaining,
                temperature=(
                    float(configured_temperature)
                    if isinstance(configured_temperature, int | float)
                    and not isinstance(configured_temperature, bool)
                    else None
                ),
            )

        result = await generate_with_retry(
            self._recording_adapter,
            request_factory,
            deadline=deadline.monotonic_at,
            clock=time.monotonic,
        )
        return {"result": result, "prepared": prepared}

    def _validate(self, generated: dict[str, Any], _deadline: ExecutionDeadline) -> dict[str, Any]:
        result: GenerationResult = generated["result"]
        prepared = generated["prepared"]
        operation: ReviewOperation = prepared["operation"]
        compact = self.skill_executor.validate_output(
            "review", self.review_output.parse_and_validate(result.text)
        )
        usage = result.usage
        sources = prepared["review_input"]["sources"]
        provenance = {
            "execution_snapshot": operation.storage_request.snapshot,
            "model": {
                "provider": result.provider,
                "model": result.model,
                "model_version": result.model_version,
                "safe_parameters": result.safe_parameters,
                "usage": {
                    "input_tokens": None if usage is None else usage.input_tokens,
                    "output_tokens": None if usage is None else usage.output_tokens,
                },
            },
            "sources": [
                {
                    "source_id": item["id"],
                    "document_id": document.id,
                    "role": item["role"],
                    "filename": item["name"],
                    "sha256": item["sha256"],
                    "status": item["status"],
                    "diagnostics": item["diagnostics"],
                }
                for item, document in zip(
                    sources, (operation.primary, *operation.contexts), strict=True
                )
            ],
        }
        return self.review_engine.map_model_output(
            compact,
            context=MappingContext(
                run_id=operation.storage_request.run_id,
                report_id=str(uuid4()),
                created_at=wire_time(utc_now()),
                primary_source_id="source-main",
                target_fragment_ids=prepared["target_fragment_ids"],
                fragments=prepared["fragments"],
                provenance=provenance,
            ),
        )

    @staticmethod
    def _failure(error: BaseException) -> ExecutionFailure:
        if isinstance(error, PromptBudgetExceeded):
            return ExecutionFailure("context_limit", "The complete input exceeds the model budget.", False)
        if isinstance(error, ModelAdapterError):
            code = public_model_error_code(error, purpose="review")
            return ExecutionFailure(code, "The model request could not be completed.", error.retryable)
        if isinstance(error, ValueError):
            return ExecutionFailure(
                "model_output_invalid", "The model response failed validation.", False
            )
        return ExecutionFailure("internal_error", "The operation could not be completed.", True)
