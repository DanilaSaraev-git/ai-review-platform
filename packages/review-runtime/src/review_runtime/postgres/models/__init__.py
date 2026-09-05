from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_column(*, primary_key: bool = False) -> Mapped[str]:
    return mapped_column(String(36), primary_key=primary_key)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = uuid_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[str] = uuid_column(primary_key=True)
    release_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    __tablename__ = "workspaces"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class Actor(Base):
    __tablename__ = "actors"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"], ["workspaces.organization_id", "workspaces.id"]
        ),
    )


class Artifact(Base):
    __tablename__ = "artifacts"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    store_key: Mapped[str] = mapped_column(String(255), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    media_type: Mapped[str] = mapped_column(String(128))
    canonical_codec_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="artifact_nonnegative_size"),
        CheckConstraint(
            "(kind = 'report_canonical' AND canonical_codec_id = 'jcs-rfc8785-0.1.4') OR "
            "(kind <> 'report_canonical' AND canonical_codec_id IS NULL)",
            name="artifact_codec_matches_kind",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"], ["workspaces.organization_id", "workspaces.id"]
        ),
        UniqueConstraint("organization_id", "workspace_id", "store_key", "sha256"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(36))
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    extraction_state: Mapped[str] = mapped_column(String(32), default="pending")
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "artifact_id"],
            ["artifacts.organization_id", "artifacts.workspace_id", "artifacts.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "created_by"],
            ["actors.organization_id", "actors.workspace_id", "actors.id"],
        ),
    )


class Fragment(Base):
    __tablename__ = "fragments"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36))
    extraction_id: Mapped[str] = mapped_column(String(36))
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    location: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            ["document_versions.organization_id", "document_versions.workspace_id", "document_versions.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.id",
            ],
        ),
        UniqueConstraint("organization_id", "workspace_id", "document_id", "ordinal"),
    )


class ReviewProfileFamily(Base):
    __tablename__ = "review_profile_families"
    row_id: Mapped[str] = uuid_column(primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deployment_id: Mapped[str | None] = mapped_column(ForeignKey("deployments.id"), nullable=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True)
    scope: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "(scope = 'system' AND deployment_id IS NOT NULL AND organization_id IS NULL "
            "AND workspace_id IS NULL) OR (scope = 'workspace' AND deployment_id IS NULL "
            "AND organization_id IS NOT NULL AND workspace_id IS NOT NULL)",
            name="review_profile_family_exact_owner",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
        ),
    )


class ReviewProfileVersion(Base):
    __tablename__ = "review_profile_versions"
    family_row_id: Mapped[str] = mapped_column(ForeignKey("review_profile_families.row_id"), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    semantic_digest: Mapped[str] = mapped_column(String(64))
    semantic_codec_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text)
    checks: Mapped[list[str]] = mapped_column(JSON)
    supersedes_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("family_row_id", "semantic_digest"),)


class ReviewProfileHead(Base):
    __tablename__ = "review_profile_heads"
    family_row_id: Mapped[str] = mapped_column(ForeignKey("review_profile_families.row_id"), primary_key=True)
    head_version: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(
            ["family_row_id", "head_version"],
            ["review_profile_versions.family_row_id", "review_profile_versions.version"],
        ),
    )


class VersionedConfig(Base):
    __abstract__ = True
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    codec_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelProfileVersion(VersionedConfig):
    __tablename__ = "model_profile_versions"


class SkillVersion(VersionedConfig):
    __tablename__ = "skill_versions"


class DialoguePolicyVersion(VersionedConfig):
    __tablename__ = "dialogue_policy_versions"


class ModelProfileAvailability(Base):
    __tablename__ = "model_profile_availability"
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"), primary_key=True)
    model_profile_id: Mapped[str] = mapped_column(primary_key=True)
    model_profile_version: Mapped[str] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str | None] = mapped_column(String(128))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(
            ["model_profile_id", "model_profile_version"],
            ["model_profile_versions.id", "model_profile_versions.version"],
        ),
    )


class ExecutionSnapshot(Base):
    __tablename__ = "execution_snapshots"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    codec_id: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
        ),
        UniqueConstraint("organization_id", "workspace_id", "digest"),
    )


class ReviewRun(Base):
    __tablename__ = "review_runs"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','preparing','reviewing','validating','completed','failed','cancelled')",
            name="review_run_state",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            ["document_versions.organization_id", "document_versions.workspace_id", "document_versions.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"], ["workspaces.organization_id", "workspaces.id"]
        ),
    )


class ReviewRunSource(Base):
    __tablename__ = "review_run_sources"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(16))
    ordinal: Mapped[int] = mapped_column(Integer)
    prepared: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["review_runs.organization_id", "review_runs.workspace_id", "review_runs.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            ["document_versions.organization_id", "document_versions.workspace_id", "document_versions.id"],
        ),
        UniqueConstraint("organization_id", "workspace_id", "run_id", "ordinal"),
    )


class ExecutionLease(Base):
    __abstract__ = True
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state: Mapped[str] = mapped_column(String(32))
    checkpoint: Mapped[str] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0)


class DocumentExtraction(ExecutionLease):
    __tablename__ = "document_extractions"
    document_id: Mapped[str] = mapped_column(String(36), unique=True)
    parser_name: Mapped[str] = mapped_column(String(128))
    parser_version: Mapped[str] = mapped_column(String(64))
    settings_digest: Mapped[str] = mapped_column(String(64))
    settings_codec_id: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(128))
    safe_error_message: Mapped[str | None] = mapped_column(String(512))
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','extracting','completed','partial','failed')",
            name="document_extraction_state",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            [
                "document_versions.organization_id",
                "document_versions.workspace_id",
                "document_versions.id",
            ],
        ),
    )


class ReviewRunExecution(ExecutionLease):
    __tablename__ = "review_run_executions"
    run_id: Mapped[str] = mapped_column(String(36), unique=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["review_runs.organization_id", "review_runs.workspace_id", "review_runs.id"],
        ),
    )


class ReviewReport(Base):
    __tablename__ = "review_reports"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True)
    artifact_id: Mapped[str] = mapped_column(String(36))
    canonical_sha256: Mapped[str] = mapped_column(String(64))
    etag: Mapped[str] = mapped_column(String(66))
    codec_id: Mapped[str] = mapped_column(String(64))
    graph: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["review_runs.organization_id", "review_runs.workspace_id", "review_runs.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "artifact_id"],
            ["artifacts.organization_id", "artifacts.workspace_id", "artifacts.id"],
        ),
    )


class Finding(Base):
    __tablename__ = "findings"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "report_id"],
            ["review_reports.organization_id", "review_reports.workspace_id", "review_reports.id"],
        ),
        UniqueConstraint("organization_id", "workspace_id", "id"),
        UniqueConstraint("organization_id", "workspace_id", "report_id", "ordinal"),
    )


class FindingState(Base):
    __tablename__ = "finding_states"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_revision: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "finding_id"],
            ["findings.organization_id", "findings.workspace_id", "findings.id"],
        ),
    )


class FindingDialogue(Base):
    __tablename__ = "finding_dialogues"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(36), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "finding_id"],
            ["findings.organization_id", "findings.workspace_id", "findings.id"],
        ),
    )


class DialogueTurn(Base):
    __tablename__ = "dialogue_turns"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dialogue_id: Mapped[str] = mapped_column(String(36))
    ordinal: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    active_generation_attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dialogue_id"],
            ["finding_dialogues.organization_id", "finding_dialogues.workspace_id", "finding_dialogues.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "id", "active_generation_attempt_id"],
            [
                "generation_attempts.organization_id",
                "generation_attempts.workspace_id",
                "generation_attempts.dialogue_turn_id",
                "generation_attempts.id",
            ],
            name="dialogue_turn_active_generation_same_turn_fkey",
            use_alter=True,
        ),
        UniqueConstraint("organization_id", "workspace_id", "dialogue_id", "ordinal"),
    )


class GenerationAttempt(ExecutionLease):
    __tablename__ = "generation_attempts"
    dialogue_turn_id: Mapped[str] = mapped_column(String(36))
    ordinal: Mapped[int] = mapped_column(Integer)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "dialogue_turn_id"],
            ["dialogue_turns.organization_id", "dialogue_turns.workspace_id", "dialogue_turns.id"],
        ),
        UniqueConstraint("organization_id", "workspace_id", "dialogue_turn_id", "ordinal"),
        UniqueConstraint(
            "organization_id",
            "workspace_id",
            "dialogue_turn_id",
            "id",
            name="uq_generation_attempt_turn_identity",
        ),
    )


class HumanDecision(Base):
    __tablename__ = "human_decisions"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "finding_id"],
            ["findings.organization_id", "findings.workspace_id", "findings.id"],
        ),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    codec_id: Mapped[str] = mapped_column(String(64))
    resource_kind: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
        ),
    )


class JobOutbox(Base):
    __tablename__ = "job_outbox"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    business_key: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=12)
    claim_token: Mapped[str | None] = mapped_column(String(36))
    claimed_by: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
        ),
        UniqueConstraint("organization_id", "workspace_id", "business_key"),
    )


class SourceDiagnostic(Base):
    __tablename__ = "source_diagnostics"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    extraction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(128))
    safe_message: Mapped[str] = mapped_column(String(512))
    location: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "extraction_id"],
            [
                "document_extractions.organization_id",
                "document_extractions.workspace_id",
                "document_extractions.id",
            ],
        ),
        UniqueConstraint("organization_id", "workspace_id", "extraction_id", "ordinal"),
    )


class ReviewWorkItem(Base):
    __tablename__ = "review_work_items"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    fragment_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    state: Mapped[str] = mapped_column(String(32))
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "execution_id"],
            [
                "review_run_executions.organization_id",
                "review_run_executions.workspace_id",
                "review_run_executions.id",
            ],
        ),
        UniqueConstraint("organization_id", "workspace_id", "id"),
        UniqueConstraint("organization_id", "workspace_id", "execution_id", "ordinal"),
    )


class ModelAttempt(Base):
    __tablename__ = "model_attempts"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    work_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    generation_attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        CheckConstraint(
            "(work_item_id IS NOT NULL) <> (generation_attempt_id IS NOT NULL)",
            name="model_attempt_exactly_one_owner",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "work_item_id"],
            ["review_work_items.organization_id", "review_work_items.workspace_id", "review_work_items.id"],
            name="model_attempt_work_item_fkey",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "generation_attempt_id"],
            [
                "generation_attempts.organization_id",
                "generation_attempts.workspace_id",
                "generation_attempts.id",
            ],
            name="model_attempt_generation_attempt_fkey",
        ),
    )


class FindingAnchor(Base):
    __tablename__ = "finding_anchors"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "finding_id"],
            ["findings.organization_id", "findings.workspace_id", "findings.id"],
        ),
    )


class ReportCoverage(Base):
    __tablename__ = "report_coverage"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "report_id"],
            ["review_reports.organization_id", "review_reports.workspace_id", "review_reports.id"],
        ),
    )


class ReportProvenance(Base):
    __tablename__ = "report_provenance"
    organization_id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(primary_key=True)
    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "report_id"],
            ["review_reports.organization_id", "review_reports.workspace_id", "review_reports.id"],
        ),
    )


Index(
    "uq_active_dialogue_turn",
    DialogueTurn.organization_id,
    DialogueTurn.workspace_id,
    DialogueTurn.dialogue_id,
    unique=True,
    postgresql_where=DialogueTurn.state.in_(["queued", "generating"]),
)

Index(
    "uq_model_attempt_review_owner_ordinal",
    ModelAttempt.organization_id,
    ModelAttempt.workspace_id,
    ModelAttempt.work_item_id,
    ModelAttempt.ordinal,
    unique=True,
    postgresql_where=ModelAttempt.work_item_id.is_not(None),
)

Index(
    "uq_model_attempt_generation_owner_ordinal",
    ModelAttempt.organization_id,
    ModelAttempt.workspace_id,
    ModelAttempt.generation_attempt_id,
    ModelAttempt.ordinal,
    unique=True,
    postgresql_where=ModelAttempt.generation_attempt_id.is_not(None),
)
