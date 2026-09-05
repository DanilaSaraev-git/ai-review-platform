from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from review_core.canonical import digest_value

from review_runtime.models.config import EndpointPolicy

ModelCapability = Literal["text_generation", "vision", "native_structured_output"]
StructuredOutputMode = Literal["plain_json", "native_json_schema"]
ProbeMode = Literal["models", "health"]

_SAFE_PARAMETERS = frozenset(
    {"max_completion_tokens", "max_tokens", "temperature", "top_p", "reasoning_effort", "seed"}
)
_SECRET_PARAMETERS = frozenset(
    {"api_key", "authorization", "credential", "credentials", "password", "secret", "token"}
)


class _FrozenOptions(dict[str, bool | int | float | str | None]):
    def _immutable(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("model profile request options are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable  # type: ignore[assignment]
    setdefault = _immutable
    update = _immutable


class ModelProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: ProbeMode
    url: str
    timeout_seconds: int = Field(default=5, ge=1, le=5)
    success_ttl_seconds: int = Field(default=300, ge=1, le=3600)

    @field_validator("url")
    @classmethod
    def exact_url(cls, value: str) -> str:
        return EndpointPolicy(value).validate()


class ModelProfile(BaseModel):
    """Immutable, secret-free configuration for one exact model endpoint version."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["model-profile.v1"] = "model-profile.v1"
    id: str = Field(pattern=r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$", max_length=128)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
    adapter_kind: Literal["deterministic", "openai_compatible"]
    provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=512)
    checkpoint: str | None = Field(default=None, min_length=1, max_length=512)
    chat_url: str | None = None
    secret_ref: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{1,127}$")
    capabilities: tuple[ModelCapability, ...]
    context_window_tokens: int = Field(gt=0)
    max_input_utf8_bytes: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    structured_output: StructuredOutputMode = "plain_json"
    supported_parameters: tuple[str, ...] = ()
    request_options: dict[str, bool | int | float | str | None] = Field(default_factory=dict)
    probe: ModelProbe | None = None

    @field_validator("chat_url")
    @classmethod
    def exact_chat_url(cls, value: str | None) -> str | None:
        return EndpointPolicy(value).validate() if value is not None else None

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value: tuple[ModelCapability, ...]) -> tuple[ModelCapability, ...]:
        if "text_generation" not in value:
            raise ValueError("model profile must declare text_generation")
        if len(value) != len(set(value)):
            raise ValueError("model capabilities must be unique")
        return value

    @field_validator("supported_parameters")
    @classmethod
    def safe_supported_parameters(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("supported parameters must be unique")
        unsupported = set(value) - _SAFE_PARAMETERS
        if unsupported:
            rendered = ", ".join(sorted(unsupported))
            if any(item.lower() in _SECRET_PARAMETERS for item in unsupported):
                raise ValueError("secret-bearing parameters cannot be stored in a model profile")
            raise ValueError(f"unsupported model parameters: {rendered}")
        return value

    @field_validator("request_options")
    @classmethod
    def immutable_request_options(
        cls, value: dict[str, bool | int | float | str | None]
    ) -> dict[str, bool | int | float | str | None]:
        return _FrozenOptions(value)

    @model_validator(mode="after")
    def exact_semantics(self) -> Self:
        if self.adapter_kind == "openai_compatible" and self.chat_url is None:
            raise ValueError("openai_compatible profile requires an exact chat_url")
        if self.adapter_kind == "deterministic" and any(
            item is not None for item in (self.chat_url, self.secret_ref, self.probe)
        ):
            raise ValueError("deterministic profile cannot declare endpoint, secret, or probe")
        output_parameters = {"max_tokens", "max_completion_tokens"} & set(self.supported_parameters)
        if self.adapter_kind == "openai_compatible" and len(output_parameters) != 1:
            raise ValueError("openai_compatible profile must declare exactly one output token parameter")
        undeclared = set(self.request_options) - set(self.supported_parameters)
        if undeclared:
            raise ValueError(f"request options are not supported by the profile: {sorted(undeclared)}")
        if any(key.lower() in _SECRET_PARAMETERS for key in self.request_options):
            raise ValueError("secret-bearing request options cannot be stored in a model profile")
        if (
            self.structured_output == "native_json_schema"
            and "native_structured_output" not in self.capabilities
        ):
            raise ValueError("native_json_schema requires native_structured_output capability")
        return self


class ModelProfileSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profiles: tuple[ModelProfile, ...] = ()

    @model_validator(mode="after")
    def unique_identity(self) -> Self:
        identities = [(profile.id, profile.version) for profile in self.profiles]
        if len(identities) != len(set(identities)):
            raise ValueError("model profile identity must be unique")
        return self


def profile_config_digest(profile: ModelProfile) -> str:
    return digest_value(profile.model_dump(mode="json"))


def project_availability(observation: dict[str, Any] | None, *, now: datetime | None = None) -> str:
    if observation is None:
        return "unavailable"
    current = now or datetime.now(UTC)
    if hasattr(observation, "public_state"):
        return str(observation.public_state(now=current))
    expires = observation.get("expires_at")
    if not isinstance(expires, datetime) or expires <= current:
        return "unavailable"
    return "available" if observation.get("state") == "available" else "unavailable"
