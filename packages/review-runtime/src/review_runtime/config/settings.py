from __future__ import annotations

from pathlib import Path
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetryPolicy(BaseModel):
    extraction_max_attempts: int = 3
    review_execution_max_attempts: int = 3
    dialogue_execution_max_attempts: int = 3
    model_call_max_attempts_per_work_item: int = 3
    outbox_publish_max_attempts: int = 12
    initial_backoff_seconds: float = 1
    max_backoff_seconds: float = 60
    backoff_multiplier: float = 2
    jitter_ratio: float = 0.2


class TimeoutPolicy(BaseModel):
    parser: int = 120
    model_call: int = 90
    outbox_publish: int = 15
    database_statement: int = 30
    artifact_io: int = 120
    graceful_shutdown: int = 30


class Lease(BaseModel):
    lease_seconds: int
    heartbeat_seconds: int

    @model_validator(mode="after")
    def heartbeat_fits(self) -> Self:
        if self.heartbeat_seconds * 3 > self.lease_seconds:
            raise ValueError("heartbeat must fit at least three times in lease")
        return self


class Leases(BaseModel):
    extraction: Lease = Field(default_factory=lambda: Lease(lease_seconds=180, heartbeat_seconds=30))
    review_execution: Lease = Field(default_factory=lambda: Lease(lease_seconds=180, heartbeat_seconds=30))
    dialogue_execution: Lease = Field(default_factory=lambda: Lease(lease_seconds=180, heartbeat_seconds=30))
    outbox_claim: Lease = Field(default_factory=lambda: Lease(lease_seconds=60, heartbeat_seconds=10))


class RecoveryPolicy(BaseModel):
    scan_interval_seconds: int = 30
    staging_orphan_grace_seconds: int = 3600
    promoted_orphan_grace_seconds: int = 86400
    collector_batch_size: int = 100


class Budgets(BaseModel):
    max_upload_bytes: int = 52_428_800
    max_context_documents: int = 50
    max_pages_per_document: int = 1000
    max_fragments_per_document: int = 20_000
    max_fragment_codepoints: int = 20_000
    max_review_input_codepoints: int = 500_000
    max_model_output_bytes: int = 1_048_576
    max_dialogue_message_codepoints: int = 20_000
    max_dialogue_turns: int = 100
    max_parallel_work_items_per_run: int = 4
    max_parallel_model_calls: int = 2


class OptionalOpenAI(BaseModel):
    enabled: bool = False
    endpoint: HttpUrl | None = None
    model: str | None = None
    secret_ref: str | None = None
    auto_download: bool = False

    @model_validator(mode="after")
    def safe_endpoint(self) -> Self:
        if self.auto_download:
            raise ValueError("automatic model downloads are forbidden")
        if self.enabled and (self.endpoint is None or not self.model):
            raise ValueError("enabled OpenAI-compatible adapter needs endpoint and model")
        if self.endpoint and (
            self.endpoint.query or self.endpoint.fragment or self.endpoint.username or self.endpoint.password
        ):
            raise ValueError("endpoint cannot contain userinfo, query, or fragment")
        return self


class ModelGatewayPolicy(BaseModel):
    release_default: str = "deterministic"
    optional_openai_compatible: OptionalOpenAI = Field(default_factory=OptionalOpenAI)


class TrustedFixtureBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding_id: str
    primary_document_sha256: str
    review_profile_semantic_digest: str
    skill_package_sha256: str
    parser_settings_digest: str
    engine_version: str
    expected_output_resource_id: str
    expected_output_sha256: str


class DeterministicGatewayPolicy(BaseModel):
    default_behavior: str = "no_semantic_analysis"
    trusted_fixture_bindings: list[TrustedFixtureBinding] = Field(default_factory=list)


class RuntimePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "runtime-config.v1"
    canonical_codec_id: str = "jcs-rfc8785-0.1.4"
    retries: RetryPolicy = Field(default_factory=RetryPolicy)
    timeouts_seconds: TimeoutPolicy = Field(default_factory=TimeoutPolicy)
    leases: Leases = Field(default_factory=Leases)
    recovery: RecoveryPolicy = Field(default_factory=RecoveryPolicy)
    budgets: Budgets = Field(default_factory=Budgets)
    model_gateway: ModelGatewayPolicy = Field(default_factory=ModelGatewayPolicy)
    deterministic_gateway: DeterministicGatewayPolicy = Field(default_factory=DeterministicGatewayPolicy)

    @classmethod
    def from_value(cls, value: dict[str, Any]) -> Self:
        return cls.model_validate(value)

    @model_validator(mode="after")
    def cross_fields(self) -> Self:
        if self.schema_version != "runtime-config.v1" or self.canonical_codec_id != "jcs-rfc8785-0.1.4":
            raise ValueError("unsupported runtime policy version or canonical codec")
        if self.retries.initial_backoff_seconds > self.retries.max_backoff_seconds:
            raise ValueError("initial backoff exceeds maximum")
        shortest = min(
            item.lease_seconds
            for item in (
                self.leases.extraction,
                self.leases.review_execution,
                self.leases.dialogue_execution,
                self.leases.outbox_claim,
            )
        )
        if self.recovery.scan_interval_seconds > shortest:
            raise ValueError("recovery scan interval exceeds shortest lease")
        bindings = self.deterministic_gateway.trusted_fixture_bindings
        ids = [binding.binding_id for binding in bindings]
        if len(ids) != len(set(ids)):
            raise ValueError("trusted fixture binding_id values must be unique")
        selectors = [
            (
                binding.primary_document_sha256,
                binding.review_profile_semantic_digest,
                binding.skill_package_sha256,
                binding.parser_settings_digest,
                binding.engine_version,
            )
            for binding in bindings
        ]
        if len(selectors) != len(set(selectors)):
            raise ValueError("trusted fixture selector tuples must be unique")
        return self


class OperatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REVIEW_", extra="ignore")
    deployment_id: UUID
    organization_id: UUID
    organization_name: str
    workspace_id: UUID
    workspace_name: str
    actor_id: UUID
    actor_display_name: str
    artifact_root: Path
    database_url: str
    queue_database_url: str
    runtime_config_path: Path
    expected_output_path: Path
    report_contract_path: Path = Path("contracts/review-platform/v1/openapi.yaml")
    system_profile_id: str
    model_profile_id: str
    dialogue_policy_id: str
    skill_id: str
    skill_package_sha256: str
    trusted_proxy_bind: str = "127.0.0.1"

    @model_validator(mode="after")
    def complete(self) -> Self:
        for value in (
            self.organization_name,
            self.workspace_name,
            self.actor_display_name,
            self.system_profile_id,
            self.model_profile_id,
            self.dialogue_policy_id,
            self.skill_id,
            self.skill_package_sha256,
        ):
            if not value.strip():
                raise ValueError("configured deployment values cannot be blank")
        if len(self.skill_package_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.skill_package_sha256
        ):
            raise ValueError("skill package digest must be lowercase SHA-256")
        return self
