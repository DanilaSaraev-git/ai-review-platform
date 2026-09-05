from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType

import httpx
from review_core.ports.models import (
    GenerationRequest,
    GenerationResult,
    ModelAdapter,
    ModelCapabilities,
)

from review_runtime.config.model_profiles import ModelProfile
from review_runtime.models.config import SecretProvider
from review_runtime.models.openai_compatible import OpenAICompatibleModelAdapter


class AsyncFixtureModelAdapter:
    """Async ModelAdapter seam around a deterministic, in-process fixture handler."""

    def __init__(
        self,
        *,
        handler: Callable[[GenerationRequest], GenerationResult],
        declared_capabilities: ModelCapabilities,
    ) -> None:
        self._handler = handler
        self._declared_capabilities = declared_capabilities

    async def capabilities(self) -> ModelCapabilities:
        return self._declared_capabilities

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        return self._handler(request)


@dataclass(slots=True)
class ModelRuntime:
    adapter: ModelAdapter
    _owned_client: httpx.AsyncClient | None = None

    @property
    def network_enabled(self) -> bool:
        return self._owned_client is not None

    async def __aenter__(self) -> ModelAdapter:
        return self.adapter

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._owned_client is not None:
            await self._owned_client.aclose()


def compose_model_runtime(
    *,
    profile: ModelProfile | None = None,
    fixture: AsyncFixtureModelAdapter | None = None,
    secrets: SecretProvider | None = None,
    max_response_bytes: int | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ModelRuntime:
    """Build an explicitly offline fixture runtime or one opt-in HTTP runtime."""
    if profile is None or profile.adapter_kind == "deterministic":
        if fixture is None:
            raise ValueError("offline composition requires an async fixture adapter")
        if transport is not None:
            raise ValueError("offline composition cannot receive a network transport")
        return ModelRuntime(adapter=fixture)
    if fixture is not None:
        raise ValueError("external model composition cannot also use a fixture adapter")
    if max_response_bytes is None or max_response_bytes <= 0:
        raise ValueError("external model composition requires a positive response byte budget")
    selected_transport = transport or httpx.AsyncHTTPTransport(retries=0)
    client = httpx.AsyncClient(
        transport=selected_transport,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=None),
    )
    adapter = OpenAICompatibleModelAdapter(
        profile=profile,
        client=client,
        secrets=secrets,
        max_response_bytes=max_response_bytes,
    )
    return ModelRuntime(adapter=adapter, _owned_client=client)
