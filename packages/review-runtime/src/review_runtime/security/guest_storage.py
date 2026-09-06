"""Reserve public upload capacity briefly, then parse and persist concurrently."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import psycopg
from review_core.application.idempotency import require_idempotency_key
from review_core.canonical import digest_value
from review_core.domain.errors import DomainError

from review_runtime.postgres.artifact_fence import advisory_fence_key
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.postgres.upload_reservations import UploadReservation


@dataclass(frozen=True, slots=True)
class GuestStorageLimits:
    per_guest_bytes: int = 200 * 1024 * 1024
    total_bytes: int = 1024 * 1024 * 1024
    per_guest_documents: int = 20
    reserve_bytes: int = 3 * 1024 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> GuestStorageLimits:
        defaults = cls()
        values = {
            field: int(os.environ.get(name, str(getattr(defaults, field))))
            for field, name in (
                ("per_guest_bytes", "REVIEW_GUEST_STORAGE_BYTES"),
                ("total_bytes", "REVIEW_GUEST_TOTAL_STORAGE_BYTES"),
                ("per_guest_documents", "REVIEW_GUEST_DOCUMENT_LIMIT"),
                ("reserve_bytes", "REVIEW_GUEST_DISK_RESERVE_BYTES"),
            )
        }
        if any(value < 1 for value in values.values()):
            raise ValueError("Guest storage limits must be positive integers")
        return cls(**values)


def upload_with_guest_limits(
    platform: PostgresReviewPlatform,
    limits: GuestStorageLimits,
    workspace_id: str,
    filename: str,
    media_type: str,
    content: bytes,
    *,
    family_id: str | None = None,
    version_key: str | None = None,
) -> dict[str, Any]:
    platform._workspace(workspace_id)
    platform._validate_upload(filename, media_type, content, platform.max_upload_bytes)
    with platform._connect() as connection:
        with connection.transaction():
            if family_id is not None and version_key is not None:
                require_idempotency_key(version_key)
                platform.cycles.family(workspace_id, family_id)
                # Only duplicates of this workspace/key wait for the entire upload.
                # The same connection re-enters this lock when persisting the version.
                connection.execute(
                    "SELECT pg_advisory_lock(%s)",
                    (advisory_fence_key("version-upload", workspace_id, version_key),),
                )
                digest = digest_value(
                    {
                        "family_id": family_id,
                        "filename": filename,
                        "media_type": media_type,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
                replay = platform.cycles.replay_upload(family_id, version_key, digest, connection)
                if replay is not None:
                    return platform.document_value(platform.get_document(workspace_id, replay))
            key = advisory_fence_key("guest-storage", platform.organization_id, "v1")
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (key,))
            _reclaim_abandoned(connection, platform.organization_id)
            _check_capacity(connection, platform, limits, len(content))
            reservation_id = str(uuid4())
            lease_key = advisory_fence_key("guest-upload-lease", platform.organization_id, reservation_id)
            connection.execute("SELECT pg_advisory_lock(%s)", (lease_key,))
            connection.execute(
                """INSERT INTO guest_upload_reservations
                   (organization_id,workspace_id,id,size_bytes,lease_key,created_at)
                   VALUES(%s,%s,%s,%s,%s,now())""",
                (platform.organization_id, workspace_id, reservation_id, len(content), lease_key),
            )
        # The shared quota lock is now released. The session lease survives the
        # commit, but no transaction is held open while extracting the document.
        reservation = UploadReservation(connection, platform.organization_id, workspace_id, reservation_id)
        try:
            return platform.upload(
                workspace_id, filename, media_type, content,
                family_id=family_id, version_key=version_key, reservation=reservation,
            )
        finally:
            if not connection.closed:
                with connection.transaction():
                    reservation.release()
            # Closing the connection releases both session locks, even on failure.
            # If it was lost, the next admission reclaims the committed reservation.


def _reclaim_abandoned(connection: psycopg.Connection[dict[str, Any]], organization_id: str) -> None:
    rows = connection.execute(
        "SELECT id,lease_key FROM guest_upload_reservations WHERE organization_id=%s", (organization_id,)
    ).fetchall()
    for row in rows:
        acquired = connection.execute(
            "SELECT pg_try_advisory_xact_lock(%s) AS acquired", (row["lease_key"],)
        ).fetchone()
        if acquired is not None and acquired["acquired"]:
            connection.execute(
                "DELETE FROM guest_upload_reservations WHERE organization_id=%s AND id=%s",
                (organization_id, row["id"]),
            )


def _check_capacity(
    connection: psycopg.Connection[dict[str, Any]],
    platform: PostgresReviewPlatform,
    limits: GuestStorageLimits,
    size: int,
) -> None:
    # Read committed documents and reservations in ONE statement/snapshot: an
    # upload may atomically replace its reservation with a document at any time.
    usage = connection.execute(
        """WITH uploads AS (
             SELECT d.workspace_id,d.size_bytes,false AS reserved FROM document_versions d
             WHERE d.organization_id=%s AND EXISTS (
               SELECT 1 FROM guest_sessions g
               WHERE g.organization_id=d.organization_id AND g.workspace_id=d.workspace_id)
             UNION ALL
             SELECT workspace_id,size_bytes,true FROM guest_upload_reservations WHERE organization_id=%s
           )
           SELECT count(*) FILTER (WHERE workspace_id=%s) AS count,
             COALESCE(sum(size_bytes) FILTER (WHERE workspace_id=%s),0) AS bytes,
             COALESCE(sum(size_bytes),0) AS total_bytes,
             COALESCE(sum(size_bytes) FILTER (WHERE reserved),0) AS reserved_bytes FROM uploads""",
        (platform.organization_id, platform.organization_id, platform.workspace_id, platform.workspace_id),
    ).fetchone()
    assert usage is not None
    if usage["count"] >= limits.per_guest_documents or usage["bytes"] + size > limits.per_guest_bytes:
        raise DomainError(
            "guest_storage_limit", 413, "Лимит загрузок",
            "Лимит файлов гостевого пространства исчерпан. Сохранённые документы доступны в истории.",
        )
    free = shutil.disk_usage(platform.settings.artifact_root).free
    if (
        usage["total_bytes"] + size > limits.total_bytes
        or free < limits.reserve_bytes + 3 * (usage["reserved_bytes"] + size)
    ):
        raise DomainError(
            "storage_unavailable", 503, "Загрузка временно недоступна",
            "Недостаточно места для новых файлов. Сохранённые документы доступны в истории.",
        )
