from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from dataclasses import dataclass, field
from types import TracebackType

import anyio

from review_runtime.ml_runtime import LLMReviewRuntime
from review_runtime.postgres.platform import PostgresReviewPlatform


@dataclass(frozen=True, slots=True)
class GuestContext:
    platform: PostgresReviewPlatform
    runtime: LLMReviewRuntime | None


@dataclass(slots=True)
class _Entry:
    workspace_id: str
    actor_id: str
    references: int = 0
    ready: anyio.Event = field(default_factory=anyio.Event)
    changed: anyio.Event = field(default_factory=anyio.Event)
    context: GuestContext | None = None
    error: BaseException | None = None
    retiring: bool = False


class GuestContextRegistry:
    """Own guest execution lifetimes independently of individual HTTP requests.

    Only verified server-side session identities may enter ``use``. The parent
    platform owns the deployment lock; the parent runtime owns the HTTP client.
    Idle entries are released after their final caller and background operation.
    The bound applies to live contexts, never to persisted guest data.
    """

    def __init__(
        self,
        platform: PostgresReviewPlatform,
        runtime: LLMReviewRuntime | None,
        *,
        max_contexts: int = 128,
    ) -> None:
        if max_contexts < 1:
            raise ValueError("max_contexts must be positive")
        self._platform = platform
        self._runtime = runtime
        self._max_contexts = max_contexts
        self._entries: dict[str, _Entry] = {}
        self._lock = anyio.Lock()
        self._capacity_changed = anyio.Event()
        self._tasks: anyio.abc.TaskGroup | None = None
        self._closing = False
        self._used = False

    async def __aenter__(self) -> GuestContextRegistry:
        if self._tasks is not None or self._closing:
            raise RuntimeError("guest context registry cannot be entered again")
        self._tasks = await anyio.create_task_group().__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        tasks = self._tasks
        if tasks is None:
            return
        with anyio.CancelScope(shield=True):
            async with self._lock:
                self._closing = True
                self._notify_capacity()
                for entry in self._entries.values():
                    self._notify_entry(entry)
        try:
            await tasks.__aexit__(exc_type, exc, traceback)
        finally:
            self._tasks = None

    async def reconcile(self, workspace_id: str, actor_id: str) -> None:
        """Fail interrupted guest work before serving, under the parent's deployment lock."""
        async with self._lock:
            if self._used or self._closing:
                raise RuntimeError("guest reconciliation must precede request handling")
            platform = await anyio.to_thread.run_sync(self._platform.for_guest, workspace_id, actor_id)
            await anyio.to_thread.run_sync(platform.reconcile_interrupted)

    @asynccontextmanager
    async def use(self, workspace_id: str, actor_id: str) -> AsyncIterator[GuestContext]:
        entry = await self._acquire(workspace_id, actor_id)
        try:
            await entry.ready.wait()
            if entry.error is not None:
                raise entry.error
            if entry.context is None:
                raise RuntimeError("guest context was not initialized")
            yield entry.context
        finally:
            with anyio.CancelScope(shield=True):
                async with self._lock:
                    entry.references -= 1
                    self._notify_entry(entry)

    async def _acquire(self, workspace_id: str, actor_id: str) -> _Entry:
        while True:
            async with self._lock:
                if self._tasks is None or self._closing:
                    raise RuntimeError("guest context registry is not running")
                self._used = True
                entry = self._entries.get(workspace_id)
                if entry is not None and entry.actor_id != actor_id:
                    raise ValueError("guest workspace actor does not match its active session")
                if entry is None and len(self._entries) < self._max_contexts:
                    entry = _Entry(workspace_id=workspace_id, actor_id=actor_id)
                    self._entries[workspace_id] = entry
                    self._tasks.start_soon(self._serve, entry)
                if entry is not None and not entry.retiring:
                    entry.references += 1
                    self._notify_entry(entry)
                    return entry
                changed = self._capacity_changed
            await changed.wait()

    async def _serve(self, entry: _Entry) -> None:
        try:
            platform = await anyio.to_thread.run_sync(
                self._platform.for_guest, entry.workspace_id, entry.actor_id
            )
            runtime = None if self._runtime is None else self._runtime.for_platform(platform)
            context = GuestContext(platform=platform, runtime=runtime)
            async with runtime if runtime is not None else nullcontext():
                entry.context = context
                entry.ready.set()
                await self._serve_until_idle(entry, runtime)
        except BaseException as error:
            entry.error = error
            entry.ready.set()
            if isinstance(error, anyio.get_cancelled_exc_class()):
                raise
        finally:
            with anyio.CancelScope(shield=True):
                async with self._lock:
                    self._entries.pop(entry.workspace_id, None)
                    self._notify_capacity()

    async def _serve_until_idle(self, entry: _Entry, runtime: LLMReviewRuntime | None) -> None:
        while True:
            async with self._lock:
                pending = runtime is not None and runtime.has_pending_work
                if self._closing or (entry.references == 0 and not pending):
                    entry.retiring = True
                    return
                changed = entry.changed
                watch_pending = entry.references == 0 and runtime is not None
            if watch_pending and runtime is not None:
                # A new borrower or shutdown can interrupt the idle wait. The
                # owned runtime tasks remain in their separate lifetime scopes.
                async with anyio.create_task_group() as watchers:
                    watchers.start_soon(self._notify_when_idle, runtime, changed)
                    await changed.wait()
                    watchers.cancel_scope.cancel()
            else:
                await changed.wait()

    @staticmethod
    async def _notify_when_idle(runtime: LLMReviewRuntime, changed: anyio.Event) -> None:
        await runtime.wait_idle()
        changed.set()

    @staticmethod
    def _notify_entry(entry: _Entry) -> None:
        entry.changed.set()
        entry.changed = anyio.Event()

    def _notify_capacity(self) -> None:
        self._capacity_changed.set()
        self._capacity_changed = anyio.Event()
