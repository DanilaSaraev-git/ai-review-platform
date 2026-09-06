"""Bound public uploads before staging bytes; existing files remain readable."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Any

from review_core.domain.errors import DomainError

from review_runtime.postgres.artifact_fence import advisory_fence_key
from review_runtime.postgres.platform import PostgresReviewPlatform


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
) -> dict[str, Any]:
    platform._workspace(workspace_id)
    # All guest uploads share a transaction lock. It spans the platform's own
    # commit, so concurrent requests cannot both spend the last quota bytes.
    with platform._connect() as connection:
        key = advisory_fence_key("guest-storage", platform.organization_id, "v1")
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (key,))
        usage = connection.execute(
            """SELECT count(*) AS count, COALESCE(sum(size_bytes),0) AS bytes
               FROM document_versions WHERE organization_id=%s AND workspace_id=%s""",
            (platform.organization_id, workspace_id),
        ).fetchone()
        assert usage is not None
        if (
            usage["count"] >= limits.per_guest_documents
            or usage["bytes"] + len(content) > limits.per_guest_bytes
        ):
            raise DomainError(
                "guest_storage_limit",
                413,
                "Лимит загрузок",
                "Лимит файлов гостевого пространства исчерпан. Сохранённые документы доступны в истории.",
            )
        total = connection.execute(
            """SELECT COALESCE(sum(d.size_bytes),0) AS bytes FROM document_versions d
               JOIN guest_sessions g ON g.organization_id=d.organization_id AND g.workspace_id=d.workspace_id
               WHERE g.organization_id=%s""",
            (platform.organization_id,),
        ).fetchone()
        assert total is not None
        free = shutil.disk_usage(platform.settings.artifact_root).free
        if total["bytes"] + len(content) > limits.total_bytes or free < limits.reserve_bytes + 3 * len(
            content
        ):
            raise DomainError(
                "storage_unavailable",
                503,
                "Загрузка временно недоступна",
                "Недостаточно места для новых файлов. Сохранённые документы доступны в истории.",
            )
        return platform.upload(workspace_id, filename, media_type, content)
