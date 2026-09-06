from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, Self

import httpx

from review_runtime.config.model_profiles import ModelProfile
from review_runtime.models.config import SecretProvider
from review_runtime.models.headers import provider_headers

AvailabilityState = Literal["available", "unavailable", "degraded", "unknown"]
ObservationSource = Literal["probe", "manual", "generation"]
GenerationOutcome = Literal[
    "success",
    "authentication_failed",
    "model_not_found",
    "unavailable",
    "rate_limited",
]


@dataclass(frozen=True, slots=True)
class AvailabilityObservation:
    profile_id: str
    profile_version: str
    state: AvailabilityState
    reason_code: str | None
    checked_at: datetime
    expires_at: datetime
    source: ObservationSource

    def __post_init__(self) -> None:
        if self.checked_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("availability timestamps must be timezone-aware")
        if self.expires_at <= self.checked_at:
            raise ValueError("expires_at must be after checked_at")

    def is_fresh(self, *, now: datetime | None = None) -> bool:
        return self.expires_at > (now or datetime.now(UTC))

    def public_state(self, *, now: datetime | None = None) -> Literal["available", "unavailable"]:
        if not self.is_fresh(now=now):
            return "unavailable"
        return "available" if self.state == "available" else "unavailable"


@dataclass(frozen=True, slots=True)
class ProbeRequest:
    mode: Literal["models", "health"]
    url: str
    model: str
    secret_ref: str | None
    timeout_seconds: int
    provider: str = "openai"


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    state: Literal["available", "unavailable", "degraded"]
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class ProbeResponse:
    status_code: int
    json_value: Any = None


class ProbeTransport(Protocol):
    async def observe(self, request: ProbeRequest) -> ProbeResponse: ...


class HTTPProbeTransport:
    """Bounded, non-generative transport for one operator-declared availability URL."""

    def __init__(
        self,
        *,
        secrets: SecretProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        max_response_bytes: int = 1_048_576,
    ) -> None:
        if max_response_bytes <= 0:
            raise ValueError("probe response byte limit must be positive")
        self._secrets = secrets
        self._transport = transport
        self._max_response_bytes = max_response_bytes

    async def observe(self, request: ProbeRequest) -> ProbeResponse:
        headers = {"Accept": "application/json"}
        secret = None
        if request.secret_ref is not None:
            if self._secrets is None:
                raise ValueError("model probe credential is unavailable")
            try:
                secret = self._secrets.resolve(request.secret_ref)
            except (KeyError, ValueError):
                raise ValueError("model probe credential is unavailable") from None
        headers.update(provider_headers(provider=request.provider, model=request.model, secret=secret))
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                async with client.stream(
                    "GET",
                    request.url,
                    headers=headers,
                    timeout=request.timeout_seconds,
                ) as response:
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > self._max_response_bytes:
                            return ProbeResponse(status_code=502)
                    json_value = None
                    if request.mode == "models" and response.status_code == 200:
                        try:
                            json_value = json.loads(content)
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            return ProbeResponse(status_code=502)
                    return ProbeResponse(status_code=response.status_code, json_value=json_value)
        except httpx.HTTPError:
            return ProbeResponse(status_code=503)


class AvailabilityService:
    async def refresh(
        self,
        profile: ModelProfile,
        transport: ProbeTransport,
        *,
        now: datetime | None = None,
    ) -> AvailabilityObservation:
        probe = profile.probe
        if probe is None:
            raise ValueError("model profile does not declare a non-generative probe")
        checked_at = now or datetime.now(UTC)
        request = ProbeRequest(
            mode=probe.mode,
            url=probe.url,
            model=profile.model,
            secret_ref=profile.secret_ref,
            timeout_seconds=probe.timeout_seconds,
            provider=profile.provider,
        )
        response = await transport.observe(request)
        outcome = self._evaluate(request, response)
        return AvailabilityObservation(
            profile_id=profile.id,
            profile_version=profile.version,
            state=outcome.state,
            reason_code=outcome.reason_code,
            checked_at=checked_at,
            expires_at=checked_at + timedelta(seconds=probe.success_ttl_seconds),
            source="probe",
        )

    @staticmethod
    def _evaluate(request: ProbeRequest, response: ProbeResponse) -> ProbeOutcome:
        if response.status_code in {401, 403}:
            return ProbeOutcome(state="unavailable", reason_code="authentication_failed")
        if response.status_code == 429:
            return ProbeOutcome(state="degraded", reason_code="rate_limited")
        if response.status_code != 200:
            return ProbeOutcome(state="unavailable", reason_code="probe_failed")
        if request.mode == "health":
            return ProbeOutcome(state="available", reason_code=None)
        value = response.json_value
        if not isinstance(value, dict) or not isinstance(value.get("data"), list):
            return ProbeOutcome(state="unavailable", reason_code="invalid_probe_response")
        model_ids = {
            item.get("id")
            for item in value["data"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if request.model not in model_ids:
            return ProbeOutcome(state="unavailable", reason_code="model_not_found")
        return ProbeOutcome(state="available", reason_code=None)


def manual_observation(
    profile: ModelProfile,
    *,
    state: AvailabilityState,
    reason_code: str | None,
    checked_at: datetime,
    expires_at: datetime,
) -> AvailabilityObservation:
    return AvailabilityObservation(
        profile_id=profile.id,
        profile_version=profile.version,
        state=state,
        reason_code=reason_code,
        checked_at=checked_at,
        expires_at=expires_at,
        source="manual",
    )


def generation_observation(
    profile: ModelProfile,
    *,
    outcome: GenerationOutcome,
    now: datetime | None = None,
    retry_after_seconds: int | None = None,
) -> AvailabilityObservation:
    checked_at = now or datetime.now(UTC)
    reason_code: str | None
    if outcome == "success":
        state: AvailabilityState = "available"
        reason_code = None
        ttl = 300
    elif outcome == "rate_limited":
        state = "degraded"
        reason_code = outcome
        ttl = retry_after_seconds if retry_after_seconds is not None else 1
    else:
        state = "unavailable"
        reason_code = outcome
        ttl = 300
    if ttl <= 0:
        raise ValueError("availability TTL must be positive")
    return AvailabilityObservation(
        profile_id=profile.id,
        profile_version=profile.version,
        state=state,
        reason_code=reason_code,
        checked_at=checked_at,
        expires_at=checked_at + timedelta(seconds=ttl),
        source="generation",
    )


CompatibilityStatus = Literal["unverified", "verified", "failed"]


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    profile_digest: str
    skill_digest: str
    engine_version: str
    backend_version: str
    suite_version: str
    status: CompatibilityStatus
    checked_at: datetime | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        for digest in (self.profile_digest, self.skill_digest):
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError("compatibility digests must be lowercase SHA-256")
        if self.status == "unverified" and self.checked_at is not None:
            raise ValueError("unverified compatibility has no checked_at")
        if self.status != "unverified" and self.checked_at is None:
            raise ValueError("verified compatibility outcome requires checked_at")

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.profile_digest,
            self.skill_digest,
            self.engine_version,
            self.backend_version,
            self.suite_version,
        )

    @classmethod
    def unverified(
        cls,
        *,
        profile_digest: str,
        skill_digest: str,
        engine_version: str,
        backend_version: str,
        suite_version: str,
    ) -> Self:
        return cls(
            profile_digest=profile_digest,
            skill_digest=skill_digest,
            engine_version=engine_version,
            backend_version=backend_version,
            suite_version=suite_version,
            status="unverified",
        )
