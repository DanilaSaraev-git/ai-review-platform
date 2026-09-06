"""Persist isolated guest browser sessions without storing bearer credentials.

Revision ID: 20260906_0003
Revises: 20260905_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0003"
down_revision = "20260905_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("token_sha256", sa.String(64), primary_key=True),
        sa.Column("deployment_id", sa.String(36), sa.ForeignKey("deployments.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "actor_id"],
            ["actors.organization_id", "actors.workspace_id", "actors.id"],
        ),
        sa.UniqueConstraint("deployment_id", "organization_id", "workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("guest_sessions")
