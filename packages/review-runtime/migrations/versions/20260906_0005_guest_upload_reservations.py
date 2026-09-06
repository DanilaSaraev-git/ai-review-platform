"""Reserve guest upload capacity independently of parsing and persistence.

Revision ID: 20260906_0005
Revises: 20260906_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0005"
down_revision = "20260906_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_upload_reservations",
        sa.Column("organization_id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("lease_key", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="guest_reservation_positive_size"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"], ["workspaces.organization_id", "workspaces.id"]
        ),
    )


def downgrade() -> None:
    op.drop_table("guest_upload_reservations")
