from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol

from review_core.application.findings import next_decision
from review_core.application.idempotency import require_idempotency_key
from review_core.application.profiles import (
    ProfileConflict,
    ProfileStore,
    ProfileVersion,
    SystemProfileImmutable,
)
from review_core.canonical import canonical_bytes, digest_value, strong_etag
from review_core.dialogue.engine import deterministic_dialogue_response
from review_core.domain import ServerId
from review_core.domain.errors import Conflict, InvalidRequest, NotFound, PayloadTooLarge


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class ReviewExecutor(Protocol):
    def execute(
        self,
        *,
        run_id: str,
        report_id: str,
        document: DocumentRecord,
        context: list[DocumentRecord],
        snapshot: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class DocumentRecord:
    id: str
    workspace_id: str
    filename: str
    media_type: str
    content: bytes
    sha256: str
    created_at: str
    extraction_state: str = "pending"
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RunRecord:
    value: dict[str, Any]
    report_bytes: bytes | None = None
    report_etag: str | None = None


class ReviewPlatform:
    def __init__(self, executor: ReviewExecutor, *, max_upload_bytes: int = 52_428_800) -> None:
        self.executor = executor
        self.max_upload_bytes = max_upload_bytes
        self.organization_id = "30000000-0000-4000-8000-000000000001"
        self.workspace_id = "20000000-0000-4000-8000-000000000001"
        self.actor = {"id": "10000000-0000-4000-8000-000000000001", "display_name": "Synthetic Analyst"}
        self.documents: dict[str, DocumentRecord] = {}
        self.runs: dict[str, RunRecord] = {}
        self.idempotency: dict[tuple[str, str], tuple[str, str]] = {}
        self.profiles = ProfileStore()
        self.system_profile = self.profiles.seed_system(
            profile_id="50000000-0000-4000-8000-000000000001",
            name="Base data specification review",
            role="Analyst with developer and tester viewpoints",
            goal="Find ambiguity before implementation",
            checks=["Sources and fields", "Transformations and schedules"],
        )
        self.model_profile = {
            "id": "deterministic-v1",
            "version": "1.0.0",
            "name": "Deterministic offline",
            "description": "Offline technical conformance profile without semantic model claims.",
            "capabilities": ["text_generation", "native_structured_output"],
            "availability": "available",
        }
        self.dialogue_policy = {
            "id": "default-dialogue",
            "version": "1.0.0",
            "digest": hashlib.sha256(b"default-dialogue-v1").hexdigest(),
            "max_member_turns": None,
        }
        self.finding_states: dict[tuple[str, str], dict[str, Any]] = {}
        self.dialogues: dict[tuple[str, str], dict[str, Any]] = {}
        self.dialogue_idempotency: dict[tuple[str, str], tuple[str, str]] = {}
        self.review_executions: dict[str, dict[str, Any]] = {}
        self.outbox: dict[str, dict[str, Any]] = {}
        self._dialogue_lock = Lock()

    def _workspace(self, workspace_id: str) -> None:
        if workspace_id != self.workspace_id:
            raise NotFound()

    def bootstrap(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "workspace": {
                "id": self.workspace_id,
                "organization_id": self.organization_id,
                "organization_name": "Synthetic Organization",
                "name": "Synthetic Workspace",
            },
            "limits": {"document_upload_max_bytes": self.max_upload_bytes, "max_context_documents": 50},
        }

    def upload(self, workspace_id: str, filename: str, media_type: str, content: bytes) -> dict[str, Any]:
        self._workspace(workspace_id)
        if not content:
            raise InvalidRequest("empty_document", "Zero-byte documents are not accepted.")
        if len(content) > self.max_upload_bytes:
            raise PayloadTooLarge("Document exceeds configured byte limit.")
        allowed = {
            "text/markdown": (".md", ".markdown"),
            "text/plain": (".txt",),
            "application/pdf": (".pdf",),
        }
        suffix_ok = any(filename.lower().endswith(suffix) for suffix in allowed.get(media_type, ()))
        bytes_ok = (
            content.startswith(b"%PDF-")
            if media_type == "application/pdf"
            else media_type in {"text/markdown", "text/plain"}
        )
        if not suffix_ok or not bytes_ok:
            raise InvalidRequest(
                "media_type_mismatch", "Declared media type does not match filename or bytes."
            )
        if media_type != "application/pdf":
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise InvalidRequest("invalid_utf8", "Text document is not valid UTF-8.") from error
        record = DocumentRecord(
            id=str(ServerId.new()),
            workspace_id=workspace_id,
            filename=filename,
            media_type=media_type,
            content=bytes(content),
            sha256=hashlib.sha256(content).hexdigest(),
            created_at=utc_now(),
        )
        self.documents[record.id] = record
        return self.document_value(record)

    def document_value(self, record: DocumentRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "workspace_id": record.workspace_id,
            "filename": record.filename,
            "media_type": record.media_type,
            "size_bytes": len(record.content),
            "sha256": record.sha256,
            "extraction_state": record.extraction_state,
            "created_by": self.actor,
            "created_at": record.created_at,
        }

    def get_document(self, workspace_id: str, document_id: str) -> DocumentRecord:
        self._workspace(workspace_id)
        record = self.documents.get(document_id)
        if record is None or record.workspace_id != workspace_id:
            raise NotFound()
        return record

    def list_documents(self, workspace_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self._workspace(workspace_id)
        try:
            offset = 0 if cursor is None else int(base64.urlsafe_b64decode(cursor + "===").decode())
        except (ValueError, UnicodeDecodeError) as error:
            raise InvalidRequest("invalid_cursor", "Cursor is malformed or unknown.") from error
        records = sorted(self.documents.values(), key=lambda item: item.created_at, reverse=True)
        page = records[offset : offset + limit]
        next_offset = offset + len(page)
        next_cursor = (
            base64.urlsafe_b64encode(str(next_offset).encode()).decode().rstrip("=")
            if next_offset < len(records)
            else None
        )
        return {"items": [self.document_value(item) for item in page], "next_cursor": next_cursor}

    @staticmethod
    def profile_value(profile: ProfileVersion, workspace_id: str) -> dict[str, Any]:
        return {
            "id": profile.id,
            "workspace_id": None if profile.scope == "system" else workspace_id,
            "scope": profile.scope,
            "version": profile.version,
            "digest": profile.digest,
            "name": profile.name,
            "role": profile.role,
            "goal": profile.goal,
            "checks": list(profile.checks),
            "supersedes": None
            if profile.supersedes is None
            else {"id": profile.supersedes[0], "version": profile.supersedes[1]},
            "created_at": "2026-09-05T00:00:00.000000Z",
        }

    def list_profiles(self, workspace_id: str) -> dict[str, Any]:
        self._workspace(workspace_id)
        return {"items": [self.profile_value(item, workspace_id) for item in self.profiles.list_heads()]}

    def create_profile(self, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._workspace(workspace_id)
        supersedes = body.get("supersedes")
        pair = None if supersedes is None else (supersedes["id"], supersedes["version"])
        try:
            profile = self.profiles.create(
                name=body["name"],
                role=body["role"],
                goal=body["goal"],
                checks=body["checks"],
                supersedes=pair,
            )
        except KeyError as error:
            raise NotFound() from error
        except SystemProfileImmutable as error:
            raise InvalidRequest("invalid_supersedes", str(error)) from error
        except ProfileConflict as error:
            code = "profile_content_unchanged" if "unchanged" in str(error) else "profile_version_conflict"
            raise Conflict(code, str(error)) from error
        return self.profile_value(profile, workspace_id)

    def _snapshot(self, profile: ProfileVersion) -> dict[str, Any]:
        return {
            "profile": {"id": profile.id, "version": profile.version, "digest": profile.digest},
            "skill": {
                "id": "review-data-spec",
                "version": "1.0.0",
                "package_sha256": "dda6f8e1dbbabb94132ee4530e0f592ec3164347a567999d97a6f613a3ea78e5",
            },
            "model_profile": {
                "id": self.model_profile["id"],
                "version": "1.0.0",
                "config_sha256": hashlib.sha256(b"deterministic-v1").hexdigest(),
            },
            "dialogue_policy": self.dialogue_policy,
            "engine_version": "1.0.0",
        }

    def create_run(self, workspace_id: str, body: dict[str, Any], key: str) -> dict[str, Any]:
        self._workspace(workspace_id)
        require_idempotency_key(key)
        if len(body.get("context_document_ids", [])) > 50:
            raise InvalidRequest("context_limit", "At most 50 context documents are accepted.")
        digest = digest_value(body)
        existing = self.idempotency.get(("create_run", key))
        if existing:
            old_digest, resource_id = existing
            if old_digest != digest:
                raise Conflict("idempotency_conflict", "The key was already used with a different request.")
            return self.runs[resource_id].value
        primary = self.get_document(workspace_id, body["document_id"])
        contexts = [self.get_document(workspace_id, item) for item in body.get("context_document_ids", [])]
        if len(set(body.get("context_document_ids", []))) != len(body.get("context_document_ids", [])):
            raise InvalidRequest("duplicate_context", "Context document IDs must be unique.")
        profile_ref = body["profile"]
        try:
            profile = self.profiles.get(profile_ref["id"], profile_ref["version"])
        except KeyError as error:
            raise NotFound() from error
        model_ref = body["model_profile"]
        if model_ref != {"id": self.model_profile["id"], "version": self.model_profile["version"]}:
            raise NotFound()
        run_id = str(ServerId.new())
        execution_id = str(ServerId.new())
        outbox_id = str(ServerId.new())
        created_at = utc_now()
        run = {
            "id": run_id,
            "workspace_id": workspace_id,
            "state": "queued",
            "progress": {"percent": 0, "message": "Review queued"},
            "document_id": primary.id,
            "context_document_ids": [item.id for item in contexts],
            "execution_snapshot": self._snapshot(profile),
            "created_by": self.actor,
            "created_at": created_at,
            "started_at": None,
            "finished_at": None,
            "cancel_requested_at": None,
            "report_available": False,
            "error": None,
        }
        record = RunRecord(run)
        self.runs[run_id] = record
        self.review_executions[execution_id] = {
            "id": execution_id,
            "review_run_id": run_id,
            "state": "ready",
            "attempt_count": 0,
            "checkpoint": "queued",
            "lease_token": None,
        }
        self.outbox[outbox_id] = {
            "id": outbox_id,
            "kind": "execute_review",
            "business_key": execution_id,
            "state": "pending",
            "payload": {"review_run_id": run_id, "review_execution_id": execution_id},
        }
        self.idempotency[("create_run", key)] = (digest, run_id)
        self._execute_run(record, primary, contexts)
        self.review_executions[execution_id].update(
            state="completed", attempt_count=1, checkpoint="published"
        )
        self.outbox[outbox_id]["state"] = "published"
        return run

    def _execute_run(
        self, record: RunRecord, primary: DocumentRecord, contexts: list[DocumentRecord]
    ) -> None:
        run = record.value
        run.update(
            state="preparing", started_at=utc_now(), progress={"percent": 20, "message": "Preparing sources"}
        )
        try:
            report = self.executor.execute(
                run_id=run["id"],
                report_id=str(ServerId.new()),
                document=primary,
                context=contexts,
                snapshot=run["execution_snapshot"],
                created_at=utc_now(),
            )
            run.update(state="validating", progress={"percent": 90, "message": "Validating report"})
            value = canonical_bytes(report)
            record.report_bytes = value
            record.report_etag = strong_etag(value)
            for finding in report["findings"]:
                self._seed_finding(run["id"], finding["id"])
            run.update(
                state="completed",
                progress={"percent": 100, "message": "Review completed"},
                finished_at=utc_now(),
                report_available=True,
            )
        except ValueError as error:
            primary.extraction_state = "failed"
            run.update(
                state="failed",
                progress={"percent": 35, "message": "Source preparation failed"},
                finished_at=utc_now(),
                error={"code": "extraction_failed", "message": str(error), "retryable": False},
            )

    def _seed_finding(self, run_id: str, finding_id: str) -> None:
        dialogue_id = str(ServerId.new())
        decision = {
            "status": "unreviewed",
            "revision": 0,
            "actor": None,
            "reason": None,
            "resolution": None,
            "decided_at": None,
        }
        dialogue = {
            "id": dialogue_id,
            "run_id": run_id,
            "finding_id": finding_id,
            "revision": 0,
            "state": "open",
            "turn_count": 0,
            "can_send_message": True,
            "blocked_reason": None,
            "policy": self.dialogue_policy,
            "turns": [],
        }
        self.finding_states[(run_id, finding_id)] = {
            "finding_id": finding_id,
            "decision": decision,
            "dialogue": {
                key: value
                for key, value in dialogue.items()
                if key not in {"id", "run_id", "finding_id", "turns"}
            }
            | {"dialogue_id": dialogue_id},
        }
        self.dialogues[(run_id, finding_id)] = dialogue

    def list_runs(self, workspace_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self._workspace(workspace_id)
        if cursor is not None:
            raise InvalidRequest("invalid_cursor", "Cursor is malformed or unknown.")
        return {
            "items": [item.value for item in reversed(list(self.runs.values()))][:limit],
            "next_cursor": None,
        }

    def get_run(self, workspace_id: str, run_id: str) -> RunRecord:
        self._workspace(workspace_id)
        record = self.runs.get(run_id)
        if record is None or record.value["workspace_id"] != workspace_id:
            raise NotFound()
        return record

    def cancel_run(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        record = self.get_run(workspace_id, run_id)
        if record.value["state"] in {"completed", "failed", "cancelled"}:
            raise Conflict("run_terminal", "A terminal review run cannot be cancelled.")
        record.value.update(state="cancelled", cancel_requested_at=utc_now(), finished_at=utc_now())
        return record.value

    def report(self, workspace_id: str, run_id: str) -> tuple[bytes, str]:
        record = self.get_run(workspace_id, run_id)
        if record.report_bytes is None or record.report_etag is None:
            raise Conflict("report_unavailable", "The review report is not published.")
        return record.report_bytes, record.report_etag

    def states(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        record = self.get_run(workspace_id, run_id)
        if not record.value["report_available"]:
            raise Conflict("report_unavailable", "The review report is not published.")
        items = []
        for (rid, finding_id), value in self.finding_states.items():
            if rid == run_id:
                value["dialogue"] = self._dialogue_summary(self.dialogues[(rid, finding_id)])
                items.append(value)
        return {"items": items}

    def _get_finding_dialogue(self, workspace_id: str, run_id: str, finding_id: str) -> dict[str, Any]:
        record = self.get_run(workspace_id, run_id)
        if not record.value["report_available"]:
            raise Conflict("report_unavailable", "The review report is not published.")
        dialogue = self.dialogues.get((run_id, finding_id))
        if dialogue is None:
            raise NotFound()
        return dialogue

    @staticmethod
    def _dialogue_summary(dialogue: dict[str, Any]) -> dict[str, Any]:
        return {
            "dialogue_id": dialogue["id"],
            "revision": dialogue["revision"],
            "state": dialogue["state"],
            "turn_count": dialogue["turn_count"],
            "can_send_message": dialogue["can_send_message"],
            "blocked_reason": dialogue["blocked_reason"],
            "policy": dialogue["policy"],
        }

    def get_dialogue(self, workspace_id: str, run_id: str, finding_id: str) -> dict[str, Any]:
        return self._get_finding_dialogue(workspace_id, run_id, finding_id)

    def _report_finding(self, run_id: str, finding_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self.runs[run_id]
        if record.report_bytes is None:
            raise NotFound()
        report = json.loads(record.report_bytes)
        for finding in report["findings"]:
            if finding["id"] == finding_id:
                return finding, report["provenance"]["execution_snapshot"]
        raise NotFound()

    def create_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        require_idempotency_key(key)
        with self._dialogue_lock:
            return self._create_dialogue_turn(workspace_id, run_id, finding_id, body, key)

    def _create_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        dialogue = self._get_finding_dialogue(workspace_id, run_id, finding_id)
        digest = digest_value(body)
        idempotency_key = (dialogue["id"], key)
        existing = self.dialogue_idempotency.get(idempotency_key)
        if existing:
            if existing[0] != digest:
                raise Conflict("idempotency_conflict", "The key was already used with a different request.")
            return dialogue
        if body.get("expected_revision") != dialogue["revision"]:
            raise Conflict("revision_conflict", "Dialogue revision changed.")
        if not dialogue["can_send_message"]:
            raise Conflict("dialogue_blocked", "Dialogue cannot accept a new turn.")
        message = body.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 8000:
            raise InvalidRequest(
                "invalid_message", "Dialogue message must be non-empty and at most 8000 characters."
            )
        turn_id = str(ServerId.new())
        turn = {
            "id": turn_id,
            "ordinal": len(dialogue["turns"]) + 1,
            "state": "generating",
            "actor": self.actor,
            "member_message": message,
            "created_at": utc_now(),
            "assistant_response": None,
            "error": None,
            "finished_at": None,
        }
        dialogue["turns"].append(turn)
        dialogue.update(
            revision=dialogue["revision"] + 1,
            state="generating",
            turn_count=len(dialogue["turns"]),
            can_send_message=False,
            blocked_reason="generation_in_progress",
        )
        self.dialogue_idempotency[idempotency_key] = (digest, turn_id)
        finding, snapshot = self._report_finding(run_id, finding_id)
        turn["assistant_response"] = deterministic_dialogue_response(snapshot, finding["anchors"])
        turn.update(state="completed", finished_at=utc_now())
        dialogue.update(
            revision=dialogue["revision"] + 1, state="open", can_send_message=True, blocked_reason=None
        )
        return dialogue

    def retry_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, turn_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        require_idempotency_key(key)
        dialogue = self._get_finding_dialogue(workspace_id, run_id, finding_id)
        digest = digest_value(body)
        idempotency_key = (f"retry:{turn_id}", key)
        existing = self.dialogue_idempotency.get(idempotency_key)
        if existing:
            if existing[0] != digest:
                raise Conflict("idempotency_conflict", "The key was already used with a different request.")
            return dialogue
        if body.get("expected_revision") != dialogue["revision"]:
            raise Conflict("revision_conflict", "Dialogue revision changed.")
        turn = next((item for item in dialogue["turns"] if item["id"] == turn_id), None)
        if turn is None:
            raise NotFound()
        if turn["state"] != "failed":
            raise Conflict("turn_not_retryable", "Only failed turns can be retried.")
        self.dialogue_idempotency[idempotency_key] = (digest, turn_id)
        finding, snapshot = self._report_finding(run_id, finding_id)
        turn.update(
            state="completed",
            assistant_response=deterministic_dialogue_response(snapshot, finding["anchors"]),
            error=None,
            finished_at=utc_now(),
        )
        dialogue.update(
            revision=dialogue["revision"] + 2, state="open", can_send_message=True, blocked_reason=None
        )
        return dialogue

    def put_decision(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        dialogue = self._get_finding_dialogue(workspace_id, run_id, finding_id)
        state = self.finding_states[(run_id, finding_id)]
        try:
            decision = next_decision(state["decision"], body, actor=self.actor, decided_at=utc_now())
        except ValueError as error:
            if "stale" in str(error):
                raise Conflict("revision_conflict", str(error)) from error
            raise InvalidRequest("invalid_decision", str(error)) from error
        state["decision"] = decision
        if decision["status"] == "unreviewed":
            dialogue.update(state="open", can_send_message=True, blocked_reason=None)
        else:
            dialogue.update(state="closed", can_send_message=False, blocked_reason="human_decision_recorded")
        dialogue["revision"] += 1
        return decision
