"""Deferred JSON-snapshot prototype; never used by the default MVP composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import psycopg
from review_core.application.platform import DocumentRecord, ReviewPlatform, RunRecord
from review_core.application.profiles import ProfileStore, ProfileVersion
from review_core.domain.errors import Conflict

from review_runtime.artifacts.posix import PosixArtifactStore


def psycopg_dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


class DurableReviewPlatform(ReviewPlatform):
    """Canonical application facade persisted as one CAS-protected aggregate snapshot.

    Normalized repositories remain the durable worker seam. The aggregate snapshot is the
    restart-safe composition seam used by the small HTTP process and never contains document
    or report bytes; those are immutable POSIX artifacts addressed by opaque keys.
    """

    def __init__(
        self, executor, *, database_url: str, artifact_root: Path, max_upload_bytes: int = 52_428_800
    ):  # type: ignore[no-untyped-def]
        self.database_url = psycopg_dsn(database_url)
        self.artifacts = PosixArtifactStore(artifact_root)
        self._document_keys: dict[str, str] = {}
        self._report_keys: dict[str, str] = {}
        self._durable_revision = 0
        super().__init__(executor, max_upload_bytes=max_upload_bytes)
        self._load()

    def _connect(self):  # type: ignore[no-untyped-def]
        return psycopg.connect(self.database_url)

    def _load(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT revision, payload FROM runtime_state WHERE singleton = TRUE")
            row = cursor.fetchone()
        if row is None:
            self._save()
            return
        self._durable_revision, payload = row
        self._restore(payload)

    def _snapshot_state(self) -> dict[str, Any]:
        for document_id, document in self.documents.items():
            if document_id not in self._document_keys:
                self._document_keys[document_id] = self.artifacts.put(self.workspace_id, document.content)
        for run_id, record in self.runs.items():
            if record.report_bytes is not None and run_id not in self._report_keys:
                self._report_keys[run_id] = self.artifacts.put(self.workspace_id, record.report_bytes)
        profiles = [asdict(value) for value in self.profiles._versions.values()]
        documents = {
            key: {
                "id": value.id,
                "workspace_id": value.workspace_id,
                "filename": value.filename,
                "media_type": value.media_type,
                "sha256": value.sha256,
                "created_at": value.created_at,
                "extraction_state": value.extraction_state,
                "fragments": value.fragments,
                "artifact_key": self._document_keys[key],
            }
            for key, value in self.documents.items()
        }
        runs = {
            key: {
                "value": value.value,
                "report_key": self._report_keys.get(key),
                "report_etag": value.report_etag,
            }
            for key, value in self.runs.items()
        }
        return {
            "documents": documents,
            "runs": runs,
            "profiles": profiles,
            "profile_heads": self.profiles._heads,
            "idempotency": [[*key, *value] for key, value in self.idempotency.items()],
            "finding_states": [[*key, value] for key, value in self.finding_states.items()],
            "dialogues": [[*key, value] for key, value in self.dialogues.items()],
            "dialogue_idempotency": [[*key, *value] for key, value in self.dialogue_idempotency.items()],
            "review_executions": self.review_executions,
            "outbox": self.outbox,
        }

    def _restore(self, payload: dict[str, Any]) -> None:
        self._document_keys = {}
        self.documents = {}
        for key, value in payload["documents"].items():
            artifact_key = value.pop("artifact_key")
            self._document_keys[key] = artifact_key
            self.documents[key] = DocumentRecord(content=self.artifacts.get(artifact_key), **value)
        self._report_keys = {}
        self.runs = {}
        for key, value in payload["runs"].items():
            report_key = value["report_key"]
            if report_key is not None:
                self._report_keys[key] = report_key
            self.runs[key] = RunRecord(
                value=value["value"],
                report_bytes=None if report_key is None else self.artifacts.get(report_key),
                report_etag=value["report_etag"],
            )
        self.profiles = ProfileStore()
        for value in payload["profiles"]:
            value["checks"] = tuple(value["checks"])
            supersedes = value.get("supersedes")
            value["supersedes"] = None if supersedes is None else tuple(supersedes)
            profile = ProfileVersion(**value)
            self.profiles._versions[(profile.id, profile.version)] = profile
        self.profiles._heads = payload["profile_heads"]
        self.system_profile = next(
            item for item in self.profiles._versions.values() if item.scope == "system"
        )
        self.idempotency = {(row[0], row[1]): (row[2], row[3]) for row in payload["idempotency"]}
        self.finding_states = {(row[0], row[1]): row[2] for row in payload["finding_states"]}
        self.dialogues = {(row[0], row[1]): row[2] for row in payload["dialogues"]}
        self.dialogue_idempotency = {
            (row[0], row[1]): (row[2], row[3]) for row in payload["dialogue_idempotency"]
        }
        self.review_executions = payload["review_executions"]
        self.outbox = payload["outbox"]

    def _save(self) -> None:
        payload = self._snapshot_state()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT revision FROM runtime_state WHERE singleton = TRUE FOR UPDATE")
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO runtime_state(singleton, revision, payload) VALUES(TRUE, 0, %s)",
                    (psycopg.types.json.Jsonb(payload),),
                )
                self._durable_revision = 0
                return
            if row[0] != self._durable_revision:
                raise Conflict("durable_revision_conflict", "Durable application state changed.")
            cursor.execute(
                "UPDATE runtime_state SET revision = revision + 1, payload = %s WHERE singleton = TRUE",
                (psycopg.types.json.Jsonb(payload),),
            )
            self._durable_revision += 1

    def _mutate(self, operation: Callable[[], Any]) -> Any:
        result = operation()
        self._save()
        return result

    def upload(self, workspace_id: str, filename: str, media_type: str, content: bytes) -> dict[str, Any]:
        return self._mutate(
            lambda: super(DurableReviewPlatform, self).upload(workspace_id, filename, media_type, content)
        )

    def create_profile(self, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._mutate(lambda: super(DurableReviewPlatform, self).create_profile(workspace_id, body))

    def create_run(self, workspace_id: str, body: dict[str, Any], key: str) -> dict[str, Any]:
        return self._mutate(lambda: super(DurableReviewPlatform, self).create_run(workspace_id, body, key))

    def cancel_run(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        return self._mutate(lambda: super(DurableReviewPlatform, self).cancel_run(workspace_id, run_id))

    def create_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: super(DurableReviewPlatform, self).create_dialogue_turn(
                workspace_id, run_id, finding_id, body, key
            )
        )

    def retry_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, turn_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: super(DurableReviewPlatform, self).retry_dialogue_turn(
                workspace_id, run_id, finding_id, turn_id, body, key
            )
        )

    def put_decision(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: super(DurableReviewPlatform, self).put_decision(workspace_id, run_id, finding_id, body)
        )
