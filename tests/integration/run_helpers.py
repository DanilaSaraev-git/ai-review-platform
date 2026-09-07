from __future__ import annotations

import asyncio
import time
from typing import Any

_TERMINAL_STATES = {"completed", "failed", "cancelled"}


def wait_for_run_terminal(
    client: Any, workspace_id: str, run_id: str, *, timeout: float = 5
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    url = f"/v1/workspaces/{workspace_id}/review-runs/{run_id}"
    while True:
        response = client.get(url)
        response.raise_for_status()
        run = response.json()
        if run["state"] in _TERMINAL_STATES:
            return run
        if time.monotonic() >= deadline:
            raise TimeoutError(f"review run {run_id} did not reach a terminal state")
        time.sleep(0.01)


async def wait_for_run_terminal_async(
    client: Any, workspace_id: str, run_id: str, *, deadline_seconds: float = 5
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + deadline_seconds
    url = f"/v1/workspaces/{workspace_id}/review-runs/{run_id}"
    while True:
        response = await client.get(url)
        response.raise_for_status()
        run = response.json()
        if run["state"] in _TERMINAL_STATES:
            return run
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"review run {run_id} did not reach a terminal state")
        await asyncio.sleep(0.01)
