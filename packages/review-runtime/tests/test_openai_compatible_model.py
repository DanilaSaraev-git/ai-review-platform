from __future__ import annotations

import json

import httpx
import pytest
from review_runtime.models.config import EndpointPolicy
from review_runtime.models.openai_compatible import ModelGatewayError, OpenAICompatibleModelGateway


def gateway(handler, *, attempts: int = 2) -> OpenAICompatibleModelGateway:  # type: ignore[no-untyped-def]
    return OpenAICompatibleModelGateway(
        endpoint=EndpointPolicy("http://127.0.0.1:9999"),
        model="local",
        max_attempts=attempts,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_structured_output_and_capabilities() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "local"}]})
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    model = gateway(handler)
    assert (await model.capabilities())["native_structured_output"]
    assert await model.generate({"messages": [{"role": "user", "content": "data"}]}) == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "model_auth_failed", False),
        (413, "model_context_too_large", False),
        (429, "model_rate_limited", True),
        (500, "model_provider_error", True),
    ],
)
async def test_normalized_safe_errors(status: int, code: str, retryable: bool) -> None:
    async def run() -> None:
        await gateway(lambda _: httpx.Response(status, text="secret provider body"), attempts=1).generate(
            {"messages": []}
        )

    with pytest.raises(ModelGatewayError) as caught:
        await run()
    assert (caught.value.code, caught.value.retryable) == (code, retryable)
    assert "secret provider body" not in str(caught.value)


@pytest.mark.asyncio
async def test_redirect_is_never_followed() -> None:
    with pytest.raises(ModelGatewayError, match="model_redirect_forbidden"):
        await gateway(lambda _: httpx.Response(307, headers={"location": "http://example.com"})).generate(
            {"messages": []}
        )
