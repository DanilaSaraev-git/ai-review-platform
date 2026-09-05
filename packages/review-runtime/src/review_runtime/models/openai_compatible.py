from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from review_runtime.models.config import EndpointPolicy, SecretProvider


@dataclass(frozen=True, slots=True)
class ModelGatewayError(RuntimeError):
    code: str
    retryable: bool

    def __str__(self) -> str:
        return self.code


class OpenAICompatibleModelGateway:
    def __init__(
        self,
        *,
        endpoint: EndpointPolicy,
        model: str,
        secret_ref: str | None = None,
        secrets: SecretProvider | None = None,
        timeout_seconds: float = 30,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint.validate()
        self.model = model
        self.secret_ref = secret_ref
        self.secrets = secrets
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if self.secret_ref is None:
            return {}
        if self.secrets is None:
            raise ModelGatewayError("model_auth_unavailable", False)
        return {"Authorization": f"Bearer {self.secrets.resolve(self.secret_ref)}"}

    async def capabilities(self) -> dict[str, bool]:
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=self.timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.get(f"{self.endpoint}/v1/models", headers=self._headers())
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise ModelGatewayError("model_unavailable", True) from error
        if response.is_redirect:
            raise ModelGatewayError("model_redirect_forbidden", False)
        if response.status_code != 200:
            raise self._error(response.status_code)
        return {"text_generation": True, "native_structured_output": True}

    async def generate(
        self,
        request: dict[str, Any],
        *,
        validate: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": request["messages"],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        last_error: ModelGatewayError | None = None
        for _ in range(self.max_attempts):
            try:
                async with httpx.AsyncClient(
                    transport=self.transport,
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = await client.post(
                        f"{self.endpoint}/v1/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
            except httpx.TimeoutException:
                last_error = ModelGatewayError("model_timeout", True)
                continue
            except httpx.NetworkError:
                last_error = ModelGatewayError("model_unavailable", True)
                continue
            if response.is_redirect:
                raise ModelGatewayError("model_redirect_forbidden", False)
            if response.status_code != 200:
                last_error = self._error(response.status_code)
                if last_error.retryable:
                    continue
                raise last_error
            try:
                content = response.json()["choices"][0]["message"]["content"]
                value = json.loads(content)
            except (ValueError, KeyError, IndexError, TypeError) as error:
                raise ModelGatewayError("model_invalid_response", False) from error
            if not isinstance(value, dict):
                raise ModelGatewayError("model_invalid_response", False)
            if validate is not None:
                try:
                    validate(value)
                except ValueError as error:
                    raise ModelGatewayError("model_semantic_validation_failed", False) from error
            return value
        raise last_error or ModelGatewayError("model_unavailable", True)

    @staticmethod
    def _error(status: int) -> ModelGatewayError:
        if status in {401, 403}:
            return ModelGatewayError("model_auth_failed", False)
        if status == 413:
            return ModelGatewayError("model_context_too_large", False)
        if status == 429:
            return ModelGatewayError("model_rate_limited", True)
        if status >= 500:
            return ModelGatewayError("model_provider_error", True)
        return ModelGatewayError("model_request_rejected", False)
