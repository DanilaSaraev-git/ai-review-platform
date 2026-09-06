"""Connection-owned upload capacity, converted to a document in one transaction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True, slots=True)
class UploadReservation:
    connection: psycopg.Connection[dict[str, Any]]
    organization_id: str
    workspace_id: str
    id: str

    def release(self) -> None:
        self.connection.execute(
            "DELETE FROM guest_upload_reservations WHERE organization_id=%s AND workspace_id=%s AND id=%s",
            (self.organization_id, self.workspace_id, self.id),
        )

    @contextmanager
    def persist(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        # Use the lease-owning connection: losing it also prevents a late commit
        # after another uploader has reclaimed the abandoned reservation.
        with self.connection.transaction():
            row = self.connection.execute(
                """SELECT id FROM guest_upload_reservations
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s FOR UPDATE""",
                (self.organization_id, self.workspace_id, self.id),
            ).fetchone()
            if row is None:
                raise RuntimeError("Upload reservation is no longer available")
            yield self.connection
            self.release()
