"""add durable LLM execution metadata and ownership

Revision ID: 20260905_0002
Revises: 20260905_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0002"
down_revision = "20260905_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_run_executions",
        sa.Column("value", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.alter_column("review_work_items", "fragment_id", existing_type=sa.String(length=160), nullable=True)
    op.add_column("model_attempts", sa.Column("generation_attempt_id", sa.String(length=36), nullable=True))
    op.drop_constraint(
        "model_attempts_organization_id_workspace_id_work_item_id_or_key",
        "model_attempts",
        type_="unique",
    )
    op.drop_constraint(
        "model_attempts_organization_id_workspace_id_work_item_id_fkey",
        "model_attempts",
        type_="foreignkey",
    )
    op.drop_constraint("model_attempts_pkey", "model_attempts", type_="primary")
    op.alter_column("model_attempts", "work_item_id", existing_type=sa.String(length=36), nullable=True)
    op.create_primary_key(
        "model_attempts_pkey",
        "model_attempts",
        ["organization_id", "workspace_id", "id"],
    )
    op.create_check_constraint(
        "model_attempt_exactly_one_owner",
        "model_attempts",
        "(work_item_id IS NOT NULL) <> (generation_attempt_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "model_attempt_work_item_fkey",
        "model_attempts",
        "review_work_items",
        ["organization_id", "workspace_id", "work_item_id"],
        ["organization_id", "workspace_id", "id"],
    )
    op.create_foreign_key(
        "model_attempt_generation_attempt_fkey",
        "model_attempts",
        "generation_attempts",
        ["organization_id", "workspace_id", "generation_attempt_id"],
        ["organization_id", "workspace_id", "id"],
    )
    op.create_index(
        "uq_model_attempt_review_owner_ordinal",
        "model_attempts",
        ["organization_id", "workspace_id", "work_item_id", "ordinal"],
        unique=True,
        postgresql_where=sa.text("work_item_id IS NOT NULL"),
    )
    op.create_index(
        "uq_model_attempt_generation_owner_ordinal",
        "model_attempts",
        ["organization_id", "workspace_id", "generation_attempt_id", "ordinal"],
        unique=True,
        postgresql_where=sa.text("generation_attempt_id IS NOT NULL"),
    )
    op.create_unique_constraint(
        "uq_generation_attempt_turn_identity",
        "generation_attempts",
        ["organization_id", "workspace_id", "dialogue_turn_id", "id"],
    )
    op.add_column(
        "dialogue_turns",
        sa.Column("active_generation_attempt_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "dialogue_turn_active_generation_same_turn_fkey",
        "dialogue_turns",
        "generation_attempts",
        ["organization_id", "workspace_id", "id", "active_generation_attempt_id"],
        ["organization_id", "workspace_id", "dialogue_turn_id", "id"],
    )
    op.execute("DROP TRIGGER reject_mutation ON review_run_sources")
    op.execute(
        """
        CREATE FUNCTION enforce_review_run_source_prepared_append_once()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.prepared IS NULL
               AND NEW.prepared IS NOT NULL
               AND ROW(
                   NEW.organization_id,
                   NEW.workspace_id,
                   NEW.run_id,
                   NEW.source_id,
                   NEW.document_id,
                   NEW.role,
                   NEW.ordinal
               ) IS NOT DISTINCT FROM ROW(
                   OLD.organization_id,
                   OLD.workspace_id,
                   OLD.run_id,
                   OLD.source_id,
                   OLD.document_id,
                   OLD.role,
                   OLD.ordinal
               )
            THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'immutable relation % does not allow %', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$
        """
    )
    op.execute(
        """CREATE TRIGGER enforce_prepared_append_once
           BEFORE UPDATE OR DELETE ON review_run_sources
           FOR EACH ROW EXECUTE FUNCTION enforce_review_run_source_prepared_append_once()"""
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM review_run_executions WHERE value::jsonb <> '{}'::jsonb
            ) OR EXISTS (
                SELECT 1 FROM review_work_items WHERE fragment_id IS NULL
            ) OR EXISTS (
                SELECT 1 FROM model_attempts WHERE generation_attempt_id IS NOT NULL
            ) OR EXISTS (
                SELECT 1 FROM dialogue_turns WHERE active_generation_attempt_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'downgrade blocked: incompatible LLM execution history requires operator cleanup'
                    USING ERRCODE = 'feature_not_supported';
            END IF;
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER enforce_prepared_append_once ON review_run_sources")
    op.execute("DROP FUNCTION enforce_review_run_source_prepared_append_once()")
    op.execute(
        """CREATE TRIGGER reject_mutation BEFORE UPDATE OR DELETE ON review_run_sources
           FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation()"""
    )
    op.drop_constraint(
        "dialogue_turn_active_generation_same_turn_fkey",
        "dialogue_turns",
        type_="foreignkey",
    )
    op.drop_column("dialogue_turns", "active_generation_attempt_id")
    op.drop_constraint("uq_generation_attempt_turn_identity", "generation_attempts", type_="unique")
    op.drop_index("uq_model_attempt_generation_owner_ordinal", table_name="model_attempts")
    op.drop_index("uq_model_attempt_review_owner_ordinal", table_name="model_attempts")
    op.drop_constraint("model_attempt_generation_attempt_fkey", "model_attempts", type_="foreignkey")
    op.drop_constraint("model_attempt_work_item_fkey", "model_attempts", type_="foreignkey")
    op.drop_constraint("model_attempt_exactly_one_owner", "model_attempts", type_="check")
    op.drop_constraint("model_attempts_pkey", "model_attempts", type_="primary")
    op.alter_column("model_attempts", "work_item_id", existing_type=sa.String(length=36), nullable=False)
    op.create_primary_key(
        "model_attempts_pkey",
        "model_attempts",
        ["organization_id", "workspace_id", "work_item_id", "id"],
    )
    op.create_foreign_key(
        "model_attempts_organization_id_workspace_id_work_item_id_fkey",
        "model_attempts",
        "review_work_items",
        ["organization_id", "workspace_id", "work_item_id"],
        ["organization_id", "workspace_id", "id"],
    )
    op.create_unique_constraint(
        "model_attempts_organization_id_workspace_id_work_item_id_or_key",
        "model_attempts",
        ["organization_id", "workspace_id", "work_item_id", "ordinal"],
    )
    op.drop_column("model_attempts", "generation_attempt_id")
    op.alter_column("review_work_items", "fragment_id", existing_type=sa.String(length=160), nullable=False)
    op.drop_column("review_run_executions", "value")
