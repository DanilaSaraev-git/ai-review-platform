"""Fixture adapter for document families and mutable review-cycle snapshots."""

from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from review_core.application.cycle_state import (
    build_cycle,
    empty_cycle,
    revise_link,
    revise_resolution,
    verified_evidence_keys,
)
from review_core.application.idempotency import require_idempotency_key
from review_core.application.review_cycle import same_review_conditions
from review_core.canonical import digest_value
from review_core.domain.errors import Conflict, InvalidRequest, NotFound


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def page(items: list[dict[str, Any]], cursor: str | None, limit: int) -> dict[str, Any]:
    try:
        offset = 0 if cursor is None else int(base64.urlsafe_b64decode(cursor + "===").decode())
        if offset < 0:
            raise ValueError
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidRequest("invalid_cursor", "Cursor is malformed or unknown.") from error
    return {
        "items": items[offset : offset + limit],
        "next_cursor": (
            base64.urlsafe_b64encode(str(offset + limit).encode()).decode().rstrip("=")
            if len(items) > offset + limit
            else None
        ),
    }


class MemoryDocumentCycles:
    def __init__(self, platform: Any) -> None:
        self.platform = platform
        self.lock = RLock()
        self.families: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, dict[str, Any]] = {}
        self.records: dict[str, dict[str, Any]] = {}
        self.locales: dict[str, str] = {}
        self.keys: dict[tuple[str, str], tuple[str, str]] = {}
        self.history: list[dict[str, Any]] = []

    def register_upload(self, document: dict[str, Any]) -> None:
        with self.lock:
            identifier = document["id"]
            self.families[identifier] = {
                "id": identifier,
                "workspace_id": document["workspace_id"],
                "name": document["filename"],
                "created_at": document["created_at"],
                "created_by": document["created_by"],
                "latest_version_number": 1,
                "latest_document_id": identifier,
            }
            self.versions[identifier] = {
                "family_id": identifier,
                "version_number": 1,
                "document": deepcopy(document),
                "unchanged_from_previous": False,
            }

    def family(self, workspace_id: str, family_id: str) -> dict[str, Any]:
        self.platform._workspace(workspace_id)
        with self.lock:
            if family_id not in self.families:
                raise NotFound()
            return deepcopy(self.families[family_id])

    def version(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        self.platform.get_document(workspace_id, document_id)
        with self.lock:
            value = deepcopy(self.versions[document_id])
            value["document"] = self.platform.document_value(
                self.platform.get_document(workspace_id, document_id)
            )
            return value

    def list_families(self, workspace_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self.platform._workspace(workspace_id)
        with self.lock:
            return page(deepcopy(list(reversed(self.families.values()))), cursor, limit)

    def list_versions(
        self, workspace_id: str, family_id: str, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        self.family(workspace_id, family_id)
        with self.lock:
            return page(
                [
                    self.version(workspace_id, key)
                    for key, value in reversed(self.versions.items())
                    if value["family_id"] == family_id
                ],
                cursor,
                limit,
            )

    def list_runs(self, workspace_id: str, family_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self.family(workspace_id, family_id)
        with self.lock:
            return page(
                [
                    deepcopy(run.value)
                    for run in reversed(self.platform.runs.values())
                    if self.versions[run.value["document_id"]]["family_id"] == family_id
                ],
                cursor,
                limit,
            )

    def upload_version(
        self,
        workspace_id: str,
        family_id: str,
        filename: str,
        media_type: str,
        content: bytes,
        key: str,
    ) -> dict[str, Any]:
        self.family(workspace_id, family_id)
        require_idempotency_key(key)
        digest = digest_value(
            {"family_id": family_id, "filename": filename, "media_type": media_type, "bytes": content.hex()}
        )
        with self.lock:
            existing = self.keys.get(("upload_version", key))
            if existing:
                if existing[0] != digest:
                    raise Conflict("idempotency_conflict", "The key was already used with another version.")
                return self.version(workspace_id, existing[1])
            family = self.families[family_id]
            previous = self.versions[family["latest_document_id"]]["document"]
            uploaded = self.platform.upload(workspace_id, filename, media_type, content)
            self.families.pop(uploaded["id"])
            value = {
                "family_id": family_id,
                "version_number": family["latest_version_number"] + 1,
                "document": uploaded,
                "unchanged_from_previous": previous["sha256"] == uploaded["sha256"],
            }
            self.versions[uploaded["id"]] = value
            family.update(latest_document_id=uploaded["id"], latest_version_number=value["version_number"])
            self.keys[("upload_version", key)] = (digest, uploaded["id"])
            return deepcopy(value)

    def admit(self, run: dict[str, Any], locale: str) -> None:
        with self.lock:
            version = self.version(run["workspace_id"], run["document_id"])
            previous = [
                item.value
                for item in self.platform.runs.values()
                if item.value["report_available"]
                and self.versions[item.value["document_id"]]["family_id"] == version["family_id"]
            ]
            baseline = (
                max(previous, key=lambda item: (item["finished_at"], item["id"]))["id"] if previous else None
            )
            self.records[run["id"]] = {
                "value": empty_cycle(run["id"], version, baseline),
                "lineage": {},
                "previous": {},
            }
            self.locales[run["id"]] = locale

    def _previous(self, workspace_id: str, baseline: str | None) -> dict[str, dict[str, Any]]:
        if baseline is None:
            return {}
        if self.get(workspace_id, baseline)["status"] != "ready":
            raise RuntimeError("Baseline comparison unavailable")
        result = deepcopy(self.records[baseline]["lineage"])
        for item in result.values():
            state = self.platform.finding_states.get((item["last_run_id"], item["finding"]["id"]))
            if state and state["decision"]["revision"] > 0:
                item["decision"] = deepcopy(state["decision"])
        return dict(result)

    def _evidence(self, run_id: str, findings: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
        run = self.platform.runs[run_id].value
        sources = []
        for index, identifier in enumerate([run["document_id"], *run["context_document_ids"]]):
            document = self.platform.documents[identifier]
            sources.append(
                {
                    "source_id": "source-main" if index == 0 else f"source-context-{index}",
                    "role": "document" if index == 0 else "context",
                    "ordinal": index + 1,
                    "fragments": document.fragments,
                }
            )
        return verified_evidence_keys(findings, sources)

    def get(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        self.platform.get_run(workspace_id, run_id)
        with self.lock:
            if "comparison_failed" in self.records[run_id]["value"]["limitations"]:
                return deepcopy(self.records[run_id]["value"])
            try:
                return self._get(workspace_id, run_id)
            except (ValueError, RuntimeError, KeyError, TypeError):
                self.records[run_id]["value"]["limitations"] = ["comparison_failed"]
                return deepcopy(self.records[run_id]["value"])

    def _get(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        run = self.platform.get_run(workspace_id, run_id)
        with self.lock:
            record = self.records[run_id]
            if not run.value["report_available"] or record["value"]["status"] == "ready":
                return deepcopy(record["value"])
            baseline = record["value"]["baseline_run_id"]
            previous = self._previous(workspace_id, baseline)
            report = json.loads(self.platform.report(workspace_id, run_id)[0])
            prior_report = json.loads(self.platform.report(workspace_id, baseline)[0]) if baseline else report
            prior_run = self.platform.get_run(workspace_id, baseline).value if baseline else run.value

            def sources(value: dict[str, Any]) -> list[str]:
                return [
                    self.platform.documents[identifier].sha256
                    for identifier in [value["document_id"], *value["context_document_ids"]]
                ]

            contexts_equal = sources(prior_run)[1:] == sources(run.value)[1:]
            extracted = all(
                self.platform.documents[identifier].extraction_state == "completed"
                for item in (prior_run, run.value)
                for identifier in [item["document_id"], *item["context_document_ids"]]
            )
            conditions = (
                extracted
                and contexts_equal
                and same_review_conditions(prior_report, report)
                and (self.locales.get(baseline or run_id, "ru-RU") == self.locales.get(run_id, "ru-RU"))
            )
            previous_keys = {}
            for item in previous.values():
                previous_keys.update(self._evidence(item["last_run_id"], [item["finding"]]))
            value, lineage = build_cycle(
                record["value"],
                report,
                previous,
                same_sources=extracted and sources(prior_run) == sources(run.value),
                same_conditions=conditions,
                compared_at=now(),
                previous_evidence_keys=previous_keys,
                current_evidence_keys=self._evidence(run_id, report["findings"]),
            )
            record.update(value=value, lineage=lineage, previous=previous)
            return deepcopy(value)

    def compare(self, workspace_id: str, run_id: str, expected_revision: int) -> dict[str, Any]:
        with self.lock:
            self.platform.get_run(workspace_id, run_id)
            record = self.records[run_id]
            if record["value"]["revision"] != expected_revision:
                raise Conflict("revision_conflict", "Review cycle revision changed.")
            if record["value"]["status"] != "ready":
                record["value"]["limitations"] = []
            return self.get(workspace_id, run_id)

    def mutate(
        self, workspace_id: str, run_id: str, resource_id: str, body: dict[str, Any], *, link: bool
    ) -> dict[str, Any]:
        with self.lock:
            self.get(workspace_id, run_id)
            record = self.records[run_id]
            before = deepcopy(record)
            if link:
                report = json.loads(self.platform.report(workspace_id, run_id)[0])
                finding = next((item for item in report["findings"] if item["id"] == resource_id), None)
                if finding is None:
                    raise NotFound()
                revise_link(record["value"], record["lineage"], body, finding, record["previous"])
            else:
                revise_resolution(
                    record["value"], record["lineage"], resource_id, body, self.platform.actor, now()
                )
            self.history.append(
                {
                    "run_id": run_id,
                    "before": before,
                    "after": deepcopy(record),
                    "actor": deepcopy(self.platform.actor),
                    "at": now(),
                }
            )
            return deepcopy(record["value"])

    def export_snapshot(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        with self.lock:
            cycle = self.get(workspace_id, run_id)
            report = json.loads(self.platform.report(workspace_id, run_id)[0])
            version = self.version(workspace_id, cycle["document_id"])
            return deepcopy(
                {
                    "exported_at": now(),
                    "family": self.family(workspace_id, cycle["family_id"]),
                    "version": version,
                    "run": self.platform.get_run(workspace_id, run_id).value,
                    "report": report,
                    "finding_states": self.platform.states(workspace_id, run_id),
                    "cycle": cycle,
                    "previous_findings": {
                        item["finding"]["id"]: item["finding"]
                        for item in self.records[run_id]["previous"].values()
                    },
                }
            )
