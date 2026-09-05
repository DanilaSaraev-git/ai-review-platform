from review_runtime.postgres.models import Base


def test_metadata_covers_every_durable_entity_group() -> None:
    required = {
        "deployments",
        "organizations",
        "workspaces",
        "actors",
        "artifacts",
        "document_versions",
        "document_extractions",
        "fragments",
        "source_diagnostics",
        "review_profile_families",
        "review_profile_versions",
        "review_profile_heads",
        "model_profile_versions",
        "model_profile_availability",
        "skill_versions",
        "dialogue_policy_versions",
        "execution_snapshots",
        "review_runs",
        "review_run_sources",
        "review_run_executions",
        "review_work_items",
        "model_attempts",
        "review_reports",
        "findings",
        "finding_anchors",
        "report_coverage",
        "report_provenance",
        "finding_states",
        "finding_dialogues",
        "dialogue_turns",
        "generation_attempts",
        "human_decisions",
        "idempotency_records",
        "job_outbox",
    }
    assert required == set(Base.metadata.tables)


def test_workspace_owned_graph_uses_namespace_prefix() -> None:
    exceptions = {
        "deployments",
        "organizations",
        "workspaces",
        "review_profile_families",
        "review_profile_versions",
        "review_profile_heads",
        "model_profile_versions",
        "model_profile_availability",
        "skill_versions",
        "dialogue_policy_versions",
    }
    for name, table in Base.metadata.tables.items():
        if name not in exceptions:
            assert {"organization_id", "workspace_id"} <= set(table.columns.keys()), name
