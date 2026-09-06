from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from review_runtime.config.model_profiles import ModelProfile, ModelProfileSet


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction_max_attempts: int = Field(default=3, ge=1, le=10)
    review_execution_max_attempts: int = Field(default=3, ge=1, le=10)
    dialogue_execution_max_attempts: int = Field(default=3, ge=1, le=10)
    model_call_max_attempts_per_work_item: int = Field(default=3, ge=1, le=10)
    outbox_publish_max_attempts: int = Field(default=12, ge=1, le=100)
    initial_backoff_seconds: float = Field(default=1, ge=0.1, le=60)
    max_backoff_seconds: float = Field(default=60, ge=1, le=3600)
    backoff_multiplier: float = Field(default=2, ge=1, le=4)
    jitter_ratio: float = Field(default=0.2, ge=0, le=0.5)


class TimeoutPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parser: int = Field(default=120, ge=1, le=1800)
    model_call: int = Field(default=90, ge=1, le=1800)
    outbox_publish: int = Field(default=15, ge=1, le=300)
    database_statement: int = Field(default=30, ge=1, le=300)
    artifact_io: int = Field(default=120, ge=1, le=1800)
    graceful_shutdown: int = Field(default=30, ge=1, le=300)


class Lease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_seconds: int = Field(ge=15, le=3600)
    heartbeat_seconds: int = Field(ge=1, le=300)

    @model_validator(mode="after")
    def heartbeat_fits(self) -> Self:
        if self.heartbeat_seconds * 3 > self.lease_seconds:
            raise ValueError("heartbeat must fit at least three times in lease")
        return self


class Leases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction: Lease = Field(default_factory=lambda: Lease(lease_seconds=180, heartbeat_seconds=30))
    review_execution: Lease = Field(default_factory=lambda: Lease(lease_seconds=180, heartbeat_seconds=30))
    dialogue_execution: Lease = Field(default_factory=lambda: Lease(lease_seconds=180, heartbeat_seconds=30))
    outbox_claim: Lease = Field(default_factory=lambda: Lease(lease_seconds=60, heartbeat_seconds=10))


class RecoveryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scan_interval_seconds: int = Field(default=30, ge=1, le=300)
    staging_orphan_grace_seconds: int = Field(default=3600, ge=300, le=604800)
    promoted_orphan_grace_seconds: int = Field(default=86400, ge=3600, le=2592000)
    collector_batch_size: int = Field(default=100, ge=1, le=1000)


class Budgets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_upload_bytes: int = Field(default=52_428_800, ge=1, le=1_073_741_824)
    max_context_documents: int = Field(default=50, ge=0, le=50)
    max_pages_per_document: int = Field(default=1000, ge=1, le=10_000)
    max_fragments_per_document: int = Field(default=20_000, ge=1, le=100_000)
    max_fragment_codepoints: int = Field(default=20_000, ge=1, le=1_000_000)
    max_review_input_codepoints: int = Field(default=500_000, ge=1, le=10_000_000)
    max_model_output_bytes: int = Field(default=1_048_576, ge=1024, le=104_857_600)
    max_dialogue_message_codepoints: int = Field(default=20_000, ge=1, le=1_000_000)
    max_dialogue_turns: int = Field(default=100, ge=1, le=1000)
    max_parallel_work_items_per_run: int = Field(default=4, ge=1, le=64)
    max_parallel_model_calls: int = Field(default=2, ge=1, le=64)


class OptionalOpenAI(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    model_config = ConfigDict(extra="forbid")
    release_default: Literal["deterministic"] = "deterministic"
    optional_openai_compatible: OptionalOpenAI = Field(default_factory=OptionalOpenAI)
    profiles: tuple[ModelProfile, ...] = ()

    @model_validator(mode="after")
    def exact_profile_identities(self) -> Self:
        ModelProfileSet(profiles=self.profiles)
        return self


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
    model_config = ConfigDict(extra="forbid")
    default_behavior: Literal["no_semantic_analysis"] = "no_semantic_analysis"
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
    expected_output_path: Path | None = None
    report_contract_path: Path = Path("contracts/review-platform/v1/openapi.yaml")
    system_profile_id: str
    model_profile_id: str
    dialogue_policy_id: str
    skill_id: str
    skill_package_sha256: str
    model_profile_path: Path | None = None
    model_credential_path: Path | None = None
    skill_package_path: Path | None = None
    review_deadline_seconds: float = Field(default=300, gt=0)
    dialogue_deadline_seconds: float = Field(default=60, gt=0)
    finalization_timeout_seconds: float = Field(default=10, gt=0, le=30)
    model_max_response_bytes: int = Field(default=1_048_576, gt=0)
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
