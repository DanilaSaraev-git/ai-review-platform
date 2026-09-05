import asyncio

import httpx
import pytest

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion


async def test_completion_preserves_provider_metadata_and_records_http_request() -> None:
    provider = FakeModelProvider(
        [
            ScriptedReply(
                chat_completion(
                    '{"summary":"Synthetic review"}',
                    model="synthetic-model-v2",
                    finish_reason="length",
                    usage={"prompt_tokens": 17, "completion_tokens": 5, "total_tokens": 22},
                    headers={"x-request-id": "synthetic-request-1"},
                )
            )
        ]
    )
    async with httpx.AsyncClient(transport=provider.transport) as client:
        response = await client.post(
            "https://model.invalid/custom/chat",
            json={"model": "synthetic-model-v2", "messages": [{"role": "user", "content": "Review"}]},
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "synthetic-request-1"
    assert response.json() == {
        "id": "synthetic-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "synthetic-model-v2",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"summary":"Synthetic review"}'},
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 17, "completion_tokens": 5, "total_tokens": 22},
    }
    assert provider.call_count == 1
    request = provider.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://model.invalid/custom/chat"
    assert request.content == (
        b'{"model":"synthetic-model-v2","messages":[{"role":"user","content":"Review"}]}'
    )


async def test_three_calls_wait_independently_and_keep_reply_assignment_when_released_in_reverse() -> None:
    releases = [asyncio.Event() for _ in range(3)]
    replies = [
        ScriptedReply(chat_completion(content), release=release)
        for content, release in zip(["first", "second", "third"], releases, strict=True)
    ]
    provider = FakeModelProvider(replies)
    tasks: list[asyncio.Task[httpx.Response]] = []
    async with httpx.AsyncClient(transport=provider.transport) as client:
        try:
            async with asyncio.timeout(2):
                for index, reply in enumerate(replies):
                    tasks.append(asyncio.create_task(client.post(f"https://model.invalid/chat/{index}")))
                    await reply.entered.wait()

                assert provider.call_count == 3
                assert not any(task.done() for task in tasks)
                for index in [2, 1, 0]:
                    releases[index].set()
                    await tasks[index]

                assert [task.result().json()["choices"][0]["message"]["content"] for task in tasks] == [
                    "first",
                    "second",
                    "third",
                ]
                assert [request.url.path for request in provider.requests] == [
                    "/chat/0",
                    "/chat/1",
                    "/chat/2",
                ]
        finally:
            for release in releases:
                release.set()
            await asyncio.gather(*tasks, return_exceptions=True)


async def test_extra_call_fails_loudly_without_replaying_previous_response() -> None:
    provider = FakeModelProvider([ScriptedReply(chat_completion("only scripted response"))])
    async with httpx.AsyncClient(transport=provider.transport) as client:
        await client.post("https://model.invalid/chat")
        with pytest.raises(AssertionError, match="Unexpected model request #2: script has 1 replies"):
            await client.post("https://model.invalid/chat")

    assert provider.call_count == 2


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout])
async def test_transport_error_is_bound_to_its_request_and_does_not_repeat_implicitly(
    error_type: type[httpx.TransportError],
) -> None:
    provider = FakeModelProvider(
        [ScriptedReply(error_type), ScriptedReply(chat_completion("explicit next attempt"))]
    )
    async with httpx.AsyncClient(transport=provider.transport) as client:
        with pytest.raises(error_type) as error:
            await client.post("https://model.invalid/chat", content=b"synthetic request")
        assert error.value.request.url.path == "/chat"
        assert provider.call_count == 1

        response = await client.post("https://model.invalid/chat")
        assert response.json()["choices"][0]["message"]["content"] == "explicit next attempt"
        assert provider.call_count == 2


async def test_cancelling_a_held_call_consumes_only_its_assigned_reply() -> None:
    release = asyncio.Event()
    held_reply = ScriptedReply(chat_completion("cancelled response"), release=release)
    provider = FakeModelProvider([held_reply, ScriptedReply(chat_completion("next response"))])
    async with httpx.AsyncClient(transport=provider.transport) as client:
        task = asyncio.create_task(client.post("https://model.invalid/held"))
        try:
            async with asyncio.timeout(2):
                await held_reply.entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

                response = await client.post("https://model.invalid/next")
                assert response.json()["choices"][0]["message"]["content"] == "next response"
                assert provider.call_count == 2
                assert not release.is_set()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize(
    ("status", "retry_after"),
    [(429, "3"), (502, "Sat, 05 Sep 2026 12:00:00 GMT"), (503, "invalid"), (504, "0"), (401, None)],
)
async def test_raw_http_failure_preserves_status_body_and_retry_after(
    status: int, retry_after: str | None
) -> None:
    headers = {} if retry_after is None else {"retry-after": retry_after}
    provider = FakeModelProvider(
        [ScriptedReply(httpx.Response(status, content=b"synthetic provider failure", headers=headers))]
    )
    async with httpx.AsyncClient(transport=provider.transport) as client:
        response = await client.post("https://model.invalid/chat")

    assert response.status_code == status
    assert response.content == b"synthetic provider failure"
    assert response.headers.get("retry-after") == retry_after
    assert provider.call_count == 1


@pytest.mark.parametrize("body", [b'{"choices":', b'{"unexpected":"envelope"}'])
async def test_malformed_provider_payload_reaches_caller_unchanged(body: bytes) -> None:
    provider = FakeModelProvider(
        [ScriptedReply(httpx.Response(200, content=body, headers={"content-type": "application/json"}))]
    )
    async with httpx.AsyncClient(transport=provider.transport) as client:
        response = await client.post("https://model.invalid/chat")

    assert response.status_code == 200
    assert response.content == body


async def test_completion_does_not_invent_unknown_token_usage() -> None:
    provider = FakeModelProvider([ScriptedReply(chat_completion("synthetic answer"))])
    async with httpx.AsyncClient(transport=provider.transport) as client:
        response = await client.post("https://model.invalid/chat")

    assert "usage" not in response.json()
