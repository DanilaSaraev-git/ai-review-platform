"""Workspace-scoped document families, lineage and coherent export transactions."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb
from review_core.application.cycle_state import (
    build_cycle,
    empty_cycle,
    revise_link,
    revise_resolution,
    verified_evidence_keys,
)
from review_core.application.document_cycle_memory import now, page
from review_core.application.idempotency import require_idempotency_key
from review_core.application.review_completion import complete, project_completion
from review_core.application.review_cycle import same_review_conditions, same_source_texts
from review_core.domain.errors import Conflict, NotFound

from review_runtime.postgres.artifact_fence import advisory_fence_key


def admit_cycle(connection: Any, organization: str, workspace: str, run_id: str, document_id: str) -> None:
    member = connection.execute(
        """
            SELECT family_id,version_number FROM document_family_versions WHERE organization_id=%s
            AND workspace_id=%s AND document_id=%s
            """,
        (organization, workspace, document_id),
    ).fetchone()
    if member is None:
        raise NotFound()
    baseline = connection.execute(
        """
            SELECT r.run_id FROM review_reports r JOIN review_runs u ON
            (u.organization_id,u.workspace_id,u.id)=(r.organization_id,r.workspace_id,r.run_id) JOIN
            document_family_versions m ON
            (m.organization_id,m.workspace_id,m.document_id)=(u.organization_id,u.workspace_id,u.document_id)
            WHERE r.organization_id=%s AND r.workspace_id=%s AND m.family_id=%s ORDER BY
            COALESCE((u.value->>'finished_at')::timestamptz,r.created_at) DESC,r.run_id DESC LIMIT 1
            """,
        (organization, workspace, member["family_id"]),
    ).fetchone()
    baseline_id = baseline["run_id"] if baseline else None
    value = empty_cycle(run_id, {**member, "document": {"id": document_id}}, baseline_id)
    connection.execute(
        """
            INSERT INTO review_cycles(organization_id,workspace_id,run_id,family_id,baseline_run_id,
            revision,value,lineage,previous) VALUES(%s,%s,%s,%s,%s,0,%s,%s,%s)
            """,
        (
            organization,
            workspace,
            run_id,
            member["family_id"],
            baseline_id,
            Jsonb(value),
            Jsonb({}),
            Jsonb({}),
        ),
    )


class PostgresDocumentCycles:
    def __init__(self, platform: Any) -> None:
        self.platform = platform
        self.organization = platform.organization_id
        self.workspace = platform.workspace_id

    def _scope(self, workspace_id: str) -> None:
        self.platform._workspace(workspace_id)

    @property
    def scope(self) -> tuple[str, str]:
        return self.organization, self.workspace

    def _family(self, connection: Any, family_id: str) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT f.*,a.display_name,m.document_id,m.version_number FROM document_families f JOIN
            actors a ON
            (a.organization_id,a.workspace_id,a.id)=(f.organization_id,f.workspace_id,f.created_by)
            JOIN LATERAL (SELECT document_id,version_number FROM document_family_versions WHERE
            organization_id=f.organization_id AND workspace_id=f.workspace_id AND family_id=f.id
            ORDER BY version_number DESC LIMIT 1) m ON true WHERE f.organization_id=%s AND
            f.workspace_id=%s AND f.id=%s
            """,
            (*self.scope, family_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        return {
            "id": row["id"],
            "workspace_id": self.workspace,
            "name": row["name"],
            "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
            "created_by": {"id": row["created_by"], "display_name": row["display_name"]},
            "latest_version_number": row["version_number"],
            "latest_document_id": row["document_id"],
        }

    def _version(self, connection: Any, document_id: str) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT d.*,m.family_id,m.version_number,m.unchanged_from_previous,a.display_name,
            e.state AS actual_extraction_state FROM document_versions d JOIN
            document_family_versions m ON
            (m.organization_id,m.workspace_id,m.document_id)=(d.organization_id,d.workspace_id,d.id)
            JOIN actors a ON
            (a.organization_id,a.workspace_id,a.id)=(d.organization_id,d.workspace_id,d.created_by)
            LEFT JOIN document_extractions e ON
            (e.organization_id,e.workspace_id,e.document_id)=(d.organization_id,d.workspace_id,d.id)
            WHERE d.organization_id=%s AND d.workspace_id=%s AND d.id=%s
            """,
            (*self.scope, document_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        document = {
            key: row[key] for key in ("id", "workspace_id", "filename", "media_type", "size_bytes", "sha256")
        }
        extraction_state = row["actual_extraction_state"] or row["extraction_state"]
        document.update(
            extraction_state="pending" if extraction_state == "extracting" else extraction_state,
            created_at=row["created_at"].isoformat().replace("+00:00", "Z"),
            created_by={"id": row["created_by"], "display_name": row["display_name"]},
        )
        return {
            "family_id": row["family_id"],
            "version_number": row["version_number"],
            "document": document,
            "unchanged_from_previous": row["unchanged_from_previous"],
        }

    def family(self, workspace_id: str, family_id: str) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            return self._family(connection, family_id)

    def version(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            return self._version(connection, document_id)

    def list_families(self, workspace_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            rows = connection.execute(
                """
            SELECT id FROM document_families WHERE organization_id=%s AND workspace_id=%s ORDER BY
            created_at DESC,id DESC
            """,
                self.scope,
            ).fetchall()
            selected = page(rows, cursor, limit)
            return selected | {"items": [self._family(connection, row["id"]) for row in selected["items"]]}

    def list_versions(
        self, workspace_id: str, family_id: str, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            self._family(connection, family_id)
            rows = connection.execute(
                """
            SELECT document_id FROM document_family_versions WHERE organization_id=%s AND
            workspace_id=%s AND family_id=%s ORDER BY version_number DESC
            """,
                (*self.scope, family_id),
            ).fetchall()
            selected = page(rows, cursor, limit)
            return selected | {
                "items": [self._version(connection, row["document_id"]) for row in selected["items"]]
            }

    def list_runs(self, workspace_id: str, family_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            self._family(connection, family_id)
            rows = connection.execute(
                """
            SELECT r.value FROM review_runs r JOIN document_family_versions m ON
            (m.organization_id,m.workspace_id,m.document_id)=(r.organization_id,r.workspace_id,r.document_id)
            WHERE r.organization_id=%s AND r.workspace_id=%s AND m.family_id=%s ORDER BY
            r.value->>'created_at' DESC,r.id DESC
            """,
                (*self.scope, family_id),
            ).fetchall()
            return page([row["value"] for row in rows], cursor, limit)

    def replay_upload(self, family_id: str, key: str, digest: str, connection: Any = None) -> str | None:
        if connection is None:
            with self.platform._connect() as own:
                return self.replay_upload(family_id, key, digest, own)
        row = connection.execute(
            """
            SELECT request_digest,resource_id FROM idempotency_records WHERE organization_id=%s AND
            workspace_id=%s AND operation=%s AND key=%s
            """,
            (*self.scope, "upload_version", key),
        ).fetchone()
        if row:
            if row["request_digest"] != digest:
                raise Conflict("idempotency_conflict", "The key was already used with another version.")
            return str(row["resource_id"])
        return None

    def prepare_upload(
        self,
        connection: Any,
        family_id: str | None,
        key: str | None,
        digest: str,
        document_id: str,
        filename: str,
        created_at: Any,
    ) -> tuple[str, int, bool, str | None]:
        if family_id is None:
            connection.execute(
                """
            INSERT INTO
            document_families(organization_id,workspace_id,id,name,created_by,created_at)
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
                (*self.scope, document_id, filename, self.platform.actor["id"], created_at),
            )
            return document_id, 1, False, None
        if key is None:
            raise ValueError("Version upload requires an idempotency key")
        require_idempotency_key(key)
        connection.execute(
            "SELECT pg_advisory_xact_lock(%s)", (advisory_fence_key("version-upload", self.workspace, key),)
        )
        family = connection.execute(
            """
            SELECT id FROM document_families WHERE organization_id=%s AND workspace_id=%s AND id=%s
            FOR UPDATE
            """,
            (*self.scope, family_id),
        ).fetchone()
        if family is None:
            raise NotFound()
        replay = self.replay_upload(family_id, key, digest, connection)
        if replay:
            return family_id, 0, False, replay
        row = connection.execute(
            """
            SELECT m.version_number,d.sha256 FROM document_family_versions m JOIN document_versions
            d ON
            (d.organization_id,d.workspace_id,d.id)=(m.organization_id,m.workspace_id,m.document_id)
            WHERE m.organization_id=%s AND m.workspace_id=%s AND m.family_id=%s ORDER BY
            m.version_number DESC LIMIT 1
            """,
            (*self.scope, family_id),
        ).fetchone()
        assert row is not None
        return family_id, row["version_number"] + 1, False, None

    def finish_upload(
        self,
        connection: Any,
        document_id: str,
        family_id: str,
        number: int,
        content_digest: str,
        key: str | None,
        request_digest: str,
    ) -> None:
        previous = connection.execute(
            """
            SELECT d.sha256 FROM document_versions d JOIN document_family_versions m ON
            (m.organization_id,m.workspace_id,m.document_id)=(d.organization_id,d.workspace_id,d.id)
            WHERE m.organization_id=%s AND m.workspace_id=%s AND m.family_id=%s AND
            m.version_number=%s
            """,
            (*self.scope, family_id, number - 1),
        ).fetchone()
        unchanged = previous is not None and previous["sha256"] == content_digest
        connection.execute(
            """
            INSERT INTO
            document_family_versions(organization_id,workspace_id,document_id,family_id,version_number,unchanged_from_previous)
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
            (*self.scope, document_id, family_id, number, unchanged),
        )
        if key is not None:
            connection.execute(
                """
            INSERT INTO
            idempotency_records(organization_id,workspace_id,operation,key,request_digest,
            codec_id,resource_kind,resource_id)
            VALUES(%s,%s,%s,%s,%s,'jcs-rfc8785-0.1.4','document_version',%s)
            """,
                (*self.scope, "upload_version", key, request_digest, document_id),
            )

    def upload_version(
        self, workspace_id: str, family_id: str, filename: str, media_type: str, content: bytes, key: str
    ) -> dict[str, Any]:
        self.family(workspace_id, family_id)
        value = self.platform.upload(
            workspace_id, filename, media_type, content, family_id=family_id, version_key=key
        )
        return self.version(workspace_id, value["id"])

    def _report(self, connection: Any, run_id: str) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT graph FROM review_reports WHERE organization_id=%s AND workspace_id=%s AND
            run_id=%s
            """,
            (*self.scope, run_id),
        ).fetchone()
        return row["graph"] if row else None

    def _sources(self, connection: Any, run_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT
            s.source_id,s.role,s.ordinal,e.parser_name,e.parser_version,e.settings_digest,e.state,
            s.document_id FROM review_run_sources s LEFT JOIN document_extractions e ON
            (e.organization_id,e.workspace_id,e.document_id)=(s.organization_id,s.workspace_id,s.document_id)
            WHERE s.organization_id=%s AND s.workspace_id=%s AND s.run_id=%s ORDER BY s.ordinal
            """,
            (*self.scope, run_id),
        ).fetchall()
        for row in rows:
            fragments = connection.execute(
                """
            SELECT id,text,location FROM fragments WHERE organization_id=%s AND workspace_id=%s AND
            document_id=%s ORDER BY ordinal
            """,
                (*self.scope, row["document_id"]),
            ).fetchall()
            row["text"] = "\n\n".join(fragment["text"] for fragment in fragments)
            row["fragments"] = fragments
        return [dict(row) for row in rows]

    def _locale(self, connection: Any, run_id: str) -> str:
        row = connection.execute(
            """
            SELECT value->>'locale' AS locale FROM review_run_executions WHERE organization_id=%s
            AND workspace_id=%s AND run_id=%s
            """,
            (*self.scope, run_id),
        ).fetchone()
        return str(row["locale"] or "ru-RU") if row else "ru-RU"

    def _row(self, connection: Any, run_id: str, *, lock: bool = True) -> dict[str, Any]:
        query = "SELECT * FROM review_cycles WHERE organization_id=%s AND workspace_id=%s AND run_id=%s"
        if lock:
            query = """
            SELECT * FROM review_cycles WHERE organization_id=%s AND workspace_id=%s AND run_id=%s
            FOR UPDATE
            """
        row = connection.execute(query, (*self.scope, run_id)).fetchone()
        if row is None:
            raise NotFound()
        return dict(row)

    def _save(self, connection: Any, row: dict[str, Any]) -> None:
        connection.execute(
            """
            UPDATE review_cycles SET value=%s,lineage=%s,previous=%s,revision=%s WHERE
            organization_id=%s AND workspace_id=%s AND run_id=%s
            """,
            (
                Jsonb(row["value"]),
                Jsonb(row["lineage"]),
                Jsonb(row["previous"]),
                row["value"]["revision"],
                *self.scope,
                row["run_id"],
            ),
        )

    def _compare(self, connection: Any, run_id: str) -> dict[str, Any]:
        row = self._row(connection, run_id)
        if row["value"]["status"] == "ready":
            return row
        report = self._report(connection, run_id)
        if report is None:
            return row
        baseline = row["baseline_run_id"]
        previous: dict[str, dict[str, Any]] = {}
        previous_report = report
        if baseline:
            old = self._compare(connection, baseline)
            previous = deepcopy(old["lineage"])
            previous_report = self._report(connection, baseline) or report
            for item in previous.values():
                state = connection.execute(
                    """
            SELECT value FROM finding_states WHERE organization_id=%s AND workspace_id=%s AND
            finding_id=%s
            """,
                    (*self.scope, item["finding"]["id"]),
                ).fetchone()
                if state and state["value"]["revision"] > 0:
                    item["decision"] = deepcopy(state["value"])
        old_sources = self._sources(connection, baseline or run_id)
        current_sources = self._sources(connection, run_id)

        def parsers(sources: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
            return [
                (s["parser_name"], s["parser_version"], s["settings_digest"], s["state"]) for s in sources
            ]

        extracted = bool(old_sources and current_sources) and all(
            source["state"] == "completed" for source in old_sources + current_sources
        )
        same_sources = (
            extracted
            and same_source_texts(old_sources, current_sources)
            and parsers(old_sources) == parsers(current_sources)
        )
        contexts_equal = [(s["role"], s["text"]) for s in old_sources if s["role"] == "context"] == [
            (s["role"], s["text"]) for s in current_sources if s["role"] == "context"
        ]
        conditions = (
            extracted
            and same_review_conditions(previous_report, report)
            and contexts_equal
            and parsers(old_sources) == parsers(current_sources)
            and self._locale(connection, baseline or run_id) == self._locale(connection, run_id)
        )
        previous_keys = {}
        for item in previous.values():
            previous_keys.update(
                verified_evidence_keys([item["finding"]], self._sources(connection, item["last_run_id"]))
            )
        value, lineage = build_cycle(
            row["value"],
            report,
            previous,
            same_sources=same_sources,
            same_conditions=conditions,
            compared_at=now(),
            previous_evidence_keys=previous_keys,
            current_evidence_keys=verified_evidence_keys(report["findings"], current_sources),
        )
        row.update(value=value, lineage=lineage, previous=previous)
        self._save(connection, row)
        return row

    def get(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        self._scope(workspace_id)
        try:
            with self.platform._connect() as connection:
                row = self._row(connection, run_id)
                if "comparison_failed" in row["value"]["limitations"]:
                    return dict(row["value"])
                return self._project(connection, self._compare(connection, run_id))
        except (ValueError, RuntimeError, KeyError, TypeError):
            with self.platform._connect() as connection:
                row = self._row(connection, run_id)
                row["value"]["limitations"] = ["comparison_failed"]
                self._save(connection, row)
                return dict(row["value"])

    def _decisions(self, connection: Any, run_id: str) -> dict[str, Any]:
        rows = connection.execute(
            """SELECT s.finding_id,s.value FROM finding_states s JOIN findings f ON
            (s.organization_id,s.workspace_id,s.finding_id)=(f.organization_id,f.workspace_id,f.id)
            JOIN review_reports r ON (f.organization_id,f.workspace_id,f.report_id)=
            (r.organization_id,r.workspace_id,r.id)
            WHERE r.organization_id=%s AND r.workspace_id=%s AND r.run_id=%s FOR SHARE OF s""",
            (*self.scope, run_id),
        ).fetchall()
        return {row["finding_id"]: row["value"] for row in rows}

    def _project(self, connection: Any, row: dict[str, Any]) -> dict[str, Any]:
        return project_completion(
            deepcopy(row["value"]),
            self._report(connection, row["run_id"]),
            self._decisions(connection, row["run_id"]),
        )

    def complete(self, workspace_id: str, run_id: str, expected_revision: int) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            row = self._compare(connection, run_id)
            complete(
                row["value"],
                self._report(connection, run_id),
                self._decisions(connection, run_id),
                expected_revision,
                self.platform.actor,
                now(),
            )
            self._save(connection, row)
            return deepcopy(row["value"])

    def after_publish(self, run_id: str) -> None:
        try:
            self.get(self.workspace, run_id)
        except Exception:
            # Published report success is independent from comparison; the explicit retry is safe.
            with self.platform._connect() as connection:
                row = self._row(connection, run_id)
                if row["value"]["status"] != "ready":
                    row["value"]["limitations"] = ["comparison_failed"]
                    self._save(connection, row)

    def compare(self, workspace_id: str, run_id: str, expected_revision: int) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            row = self._row(connection, run_id)
            if row["value"]["revision"] != expected_revision:
                raise Conflict("revision_conflict", "Review cycle revision changed.")
            return deepcopy(self._compare(connection, run_id)["value"])

    def mutate(
        self, workspace_id: str, run_id: str, resource_id: str, body: dict[str, Any], *, link: bool
    ) -> dict[str, Any]:
        self._scope(workspace_id)
        with self.platform._connect() as connection:
            row = self._compare(connection, run_id)
            before = deepcopy(row["value"])
            if link:
                report = self._report(connection, run_id)
                finding = (
                    next((f for f in report["findings"] if f["id"] == resource_id), None) if report else None
                )
                if finding is None:
                    raise NotFound()
                revise_link(row["value"], row["lineage"], body, finding, row["previous"])
            else:
                revise_resolution(row["value"], row["lineage"], resource_id, body, self.platform.actor, now())
            self._save(connection, row)
            connection.execute(
                """
            INSERT INTO
            review_cycle_events(organization_id,workspace_id,id,run_id,actor_id,created_at,value)
            VALUES(%s,%s,%s,%s,%s,%s,%s)
            """,
                (
                    *self.scope,
                    str(uuid4()),
                    run_id,
                    self.platform.actor["id"],
                    datetime.now(UTC),
                    Jsonb(
                        {
                            "operation": "link" if link else "resolution",
                            "request": body,
                            "before": before,
                            "after": row["value"],
                        }
                    ),
                ),
            )
            return deepcopy(row["value"])

    def export_snapshot(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        self._scope(workspace_id)
        self.get(workspace_id, run_id)
        with self.platform._connect() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = self._row(connection, run_id, lock=False)
            report = self._report(connection, run_id)
            if report is None:
                raise Conflict("report_unavailable", "The review report is not published.")
            run = connection.execute(
                "SELECT value FROM review_runs WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (*self.scope, run_id),
            ).fetchone()
            states = connection.execute(
                """
            SELECT f.id AS finding_id,s.value AS decision,d.value AS dialogue FROM findings f JOIN
            finding_states s ON
            (s.organization_id,s.workspace_id,s.finding_id)=(f.organization_id,f.workspace_id,f.id)
            JOIN finding_dialogues d ON
            (d.organization_id,d.workspace_id,d.finding_id)=(f.organization_id,f.workspace_id,f.id)
            WHERE f.organization_id=%s AND f.workspace_id=%s AND f.report_id=%s ORDER BY f.ordinal
            """,
                (*self.scope, report["id"]),
            ).fetchall()
            for state in states:
                state["dialogue"] = self.platform._dialogue_summary(state["dialogue"])
            return {
                "exported_at": now(),
                "family": self._family(connection, row["family_id"]),
                "version": self._version(connection, row["value"]["document_id"]),
                "run": run["value"],
                "report": report,
                "finding_states": {"items": states},
                "cycle": project_completion(
                    row["value"], report, {s["finding_id"]: s["decision"] for s in states}
                ),
                "previous_findings": {
                    item["finding"]["id"]: item["finding"] for item in row["previous"].values()
                },
            }
