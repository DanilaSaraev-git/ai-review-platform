"""Persistent opaque browser credentials; workspace IDs are never credentials."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg

COOKIE_NAME = "review_guest"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


@dataclass(frozen=True, slots=True)
class GuestSession:
    workspace_id: str
    actor_id: str


class GuestSessionStore:
    def __init__(self, database_url: str, deployment_id: str, organization_id: str) -> None:
        self.database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self.deployment_id = deployment_id
        self.organization_id = organization_id

    def create(self) -> tuple[str, GuestSession]:
        token = secrets.token_urlsafe(32)
        session = GuestSession(str(uuid4()), str(uuid4()))
        now = datetime.now(UTC)
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "INSERT INTO workspaces(organization_id,id,name) VALUES(%s,%s,%s)",
                (self.organization_id, session.workspace_id, "Мои документы"),
            )
            connection.execute(
                "INSERT INTO actors(organization_id,workspace_id,id,display_name) VALUES(%s,%s,%s,%s)",
                (self.organization_id, session.workspace_id, session.actor_id, "Гость"),
            )
            connection.execute(
                """INSERT INTO guest_sessions
                   (token_sha256,deployment_id,organization_id,workspace_id,actor_id,
                    created_at,last_seen_at,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    hashlib.sha256(token.encode("ascii")).hexdigest(),
                    self.deployment_id,
                    self.organization_id,
                    session.workspace_id,
                    session.actor_id,
                    now,
                    now,
                    now + timedelta(seconds=SESSION_TTL_SECONDS),
                ),
            )
        return token, session

    def resolve(self, token: str | None) -> GuestSession | None:
        if token is None or _TOKEN_PATTERN.fullmatch(token) is None:
            return None
        now = datetime.now(UTC)
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """UPDATE guest_sessions SET last_seen_at=%s, expires_at=%s
                   WHERE token_sha256=%s AND deployment_id=%s AND organization_id=%s
                     AND expires_at > %s
                   RETURNING workspace_id,actor_id""",
                (
                    now,
                    now + timedelta(seconds=SESSION_TTL_SECONDS),
                    hashlib.sha256(token.encode("ascii")).hexdigest(),
                    self.deployment_id,
                    self.organization_id,
                    now,
                ),
            ).fetchone()
        return GuestSession(*row) if row else None

    def workspaces(self) -> list[GuestSession]:
        # Expired sessions still own data and possibly interrupted work.
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """SELECT workspace_id,actor_id FROM guest_sessions
                   WHERE deployment_id=%s AND organization_id=%s""",
                (self.deployment_id, self.organization_id),
            ).fetchall()
        return [GuestSession(*row) for row in rows]
