"""Scripted external HTTP seam; never opens a socket or calls a real model."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx


@dataclass
class ScriptedReply:
    """One outcome, optionally held until release; entered signals its claim."""

    outcome: httpx.Response | type[httpx.TransportError]
    release: asyncio.Event | None = None
    entered: asyncio.Event = field(default_factory=asyncio.Event, init=False)


class FakeModelProvider:
    """Inject ``transport`` into an AsyncClient within one asyncio loop.

    Requests claim their script entry before awaiting its release event. There
    is no concurrency cap, fallback response, retry, or real network transport.
    Cancellation consumes the assigned entry. Use fresh replies per provider.
    """

    def __init__(self, replies: Sequence[ScriptedReply]) -> None:
        self._replies = tuple(replies)
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        index = self.call_count
        self.requests.append(request)
        if index >= len(self._replies):
            raise AssertionError(
                f"Unexpected model request #{index + 1}: script has {len(self._replies)} replies"
            )
        reply = self._replies[index]
        reply.entered.set()
        if reply.release is not None:
            await reply.release.wait()
        if isinstance(reply.outcome, httpx.Response):
            return reply.outcome
        raise reply.outcome("Synthetic external model transport failure", request=request)


def chat_completion(
    content: str,
    *,
    model: str = "synthetic-model",
    finish_reason: str = "stop",
    usage: Mapping[str, int] | None = None,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """A synthetic envelope; pass a raw Response for malformed-provider cases."""
    body: dict[str, object] = {
        "id": "synthetic-completion",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage is not None:
        body["usage"] = dict(usage)
    return httpx.Response(200, json=body, headers=headers)
