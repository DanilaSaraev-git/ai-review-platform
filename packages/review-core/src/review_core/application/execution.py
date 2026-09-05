from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Literal, Protocol, TypeVar
from uuid import uuid4

import anyio

RequestT = TypeVar("RequestT")
PreparedT = TypeVar("PreparedT")
GeneratedT = TypeVar("GeneratedT")
PublishedT = TypeVar("PublishedT")
RequestContraT = TypeVar("RequestContraT", contravariant=True)
PreparedContraT = TypeVar("PreparedContraT", contravariant=True)
PublishedContraT = TypeVar("PublishedContraT", contravariant=True)


@dataclass(frozen=True, slots=True)
class ExecutionDeadline:
    monotonic_at: float
    wall_at: datetime

    @classmethod
    def start(
        cls, *, timeout_seconds: float, monotonic_now: float, wall_now: datetime
    ) -> ExecutionDeadline:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if wall_now.tzinfo is None:
            raise ValueError("wall_now must be timezone-aware")
        return cls(
            monotonic_at=monotonic_now + timeout_seconds,
            wall_at=wall_now + timedelta(seconds=timeout_seconds),
        )

    def remaining(self, monotonic_now: float) -> float:
        return max(0.0, self.monotonic_at - monotonic_now)

    def expired(self, monotonic_now: float) -> bool:
        return monotonic_now >= self.monotonic_at

    def admits_terminal_cas(self, database_now: datetime) -> bool:
        if database_now.tzinfo is None:
            raise ValueError("database_now must be timezone-aware")
        return database_now < self.wall_at


@dataclass(frozen=True, slots=True)
class ExecutionAdmission:
    resource_id: str
    execution_id: str
    replay: bool


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    resource_id: str
    execution_id: str
    owner_token: str


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    code: str
    safe_message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ExecutionTerminal:
    resource_id: str
    state: Literal["completed", "failed", "cancelled"]
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionHandle:
    resource_id: str


class CommitOutcomeUnknown(RuntimeError):
    """The terminal CAS may have committed; durable state must be re-read."""


class ExecutionStorage(Protocol[RequestContraT, PreparedContraT, PublishedContraT]):
    """Short synchronous storage phases; every call owns its connection and transaction."""

    def admit(self, request: RequestContraT, deadline_at: datetime) -> ExecutionAdmission: ...

    def claim(self, admission: ExecutionAdmission, owner_token: str) -> ExecutionClaim | None: ...

    def save_prepared(self, claim: ExecutionClaim, prepared: PreparedContraT) -> None: ...

    def publish(
        self, claim: ExecutionClaim, result: PublishedContraT, deadline_at: datetime
    ) -> ExecutionTerminal: ...

    def fail(self, claim: ExecutionClaim, failure: ExecutionFailure) -> ExecutionTerminal: ...

    def read_terminal(self, resource_id: str) -> ExecutionTerminal | None: ...


@dataclass(slots=True)
class _OperationState:
    event: anyio.Event = field(default_factory=anyio.Event)
    terminal: ExecutionTerminal | None = None
    error: BaseException | None = None


class AsyncExecutionCoordinator[RequestT, PreparedT, GeneratedT, PublishedT]:
    """Own accepted operations independently from the lifetime of an HTTP waiter."""

    def __init__(
        self,
        *,
        storage: ExecutionStorage[RequestT, PreparedT, PublishedT],
        prepare: Callable[[RequestT, ExecutionDeadline], PreparedT],
        generate: Callable[[PreparedT, ExecutionDeadline], Awaitable[GeneratedT]],
        validate: Callable[[GeneratedT, ExecutionDeadline], PublishedT],
        timeout_seconds: float,
        finalization_timeout_seconds: float = 10,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        owner_token_factory: Callable[[], str] = lambda: str(uuid4()),
        failure_mapper: Callable[[BaseException], ExecutionFailure] | None = None,
    ) -> None:
        if timeout_seconds <= 0 or finalization_timeout_seconds <= 0:
            raise ValueError("execution timeouts must be positive")
        self._storage = storage
        self._prepare = prepare
        self._generate = generate
        self._validate = validate
        self._timeout_seconds = timeout_seconds
        self._finalization_timeout_seconds = finalization_timeout_seconds
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._owner_token_factory = owner_token_factory
        self._failure_mapper = failure_mapper
        self._task_group: anyio.abc.TaskGroup | None = None
        self._operations: dict[str, _OperationState] = {}
        self._admission_lock = anyio.Lock()

    async def __aenter__(self) -> AsyncExecutionCoordinator[RequestT, PreparedT, GeneratedT, PublishedT]:
        if self._task_group is not None:
            raise RuntimeError("coordinator is already running")
        self._task_group = await anyio.create_task_group().__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.shutdown(exc_type=exc_type, exc=exc, traceback=traceback)

    async def shutdown(
        self,
        *,
        grace_seconds: float = 30,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        """Wait for owned operations, then cancel them so guarded cleanup can finish."""
        if grace_seconds < 0:
            raise ValueError("grace_seconds must be non-negative")
        active_group = self._task_group
        if active_group is None:
            return
        self._task_group = None
        if exc_type is None:
            with anyio.move_on_after(grace_seconds) as grace:
                for state in tuple(self._operations.values()):
                    await state.event.wait()
            if grace.cancel_called:
                active_group.cancel_scope.cancel()
        await active_group.__aexit__(exc_type, exc, traceback)

    async def submit(self, request: RequestT) -> ExecutionHandle:
        task_group = self._task_group
        if task_group is None:
            raise RuntimeError("coordinator must be entered before submit")
        deadline = ExecutionDeadline.start(
            timeout_seconds=self._timeout_seconds,
            monotonic_now=self._monotonic(),
            wall_now=self._wall_clock(),
        )
        async with self._admission_lock:
            admission = await anyio.to_thread.run_sync(
                self._storage.admit, request, deadline.wall_at
            )
            existing = self._operations.get(admission.resource_id)
            if existing is not None:
                return ExecutionHandle(admission.resource_id)
            if admission.replay:
                terminal = await anyio.to_thread.run_sync(
                    self._storage.read_terminal, admission.resource_id
                )
                if terminal is None:
                    raise RuntimeError(
                        "replayed operation is not owned by this process and is not terminal"
                    )
                state = _OperationState(terminal=terminal)
                state.event.set()
                self._operations[admission.resource_id] = state
                return ExecutionHandle(admission.resource_id)
            claim = await anyio.to_thread.run_sync(
                self._storage.claim, admission, self._owner_token_factory()
            )
            if claim is None:
                raise RuntimeError("accepted execution could not be claimed")
            state = _OperationState()
            self._operations[admission.resource_id] = state
            task_group.start_soon(self._execute, request, claim, deadline, state)
        return ExecutionHandle(admission.resource_id)

    async def wait(self, handle: ExecutionHandle) -> ExecutionTerminal:
        state = self._operations.get(handle.resource_id)
        if state is None:
            raise KeyError(handle.resource_id)
        await state.event.wait()
        if state.error is not None:
            raise state.error
        if state.terminal is None:
            raise RuntimeError("operation completed without terminal state")
        return state.terminal

    async def run(self, request: RequestT) -> ExecutionTerminal:
        return await self.wait(await self.submit(request))

    async def _execute(
        self,
        request: RequestT,
        claim: ExecutionClaim,
        deadline: ExecutionDeadline,
        state: _OperationState,
    ) -> None:
        try:
            with anyio.fail_after(deadline.remaining(self._monotonic())):
                prepared = await anyio.to_thread.run_sync(self._prepare, request, deadline)
                await anyio.to_thread.run_sync(self._storage.save_prepared, claim, prepared)
                generated = await self._generate(prepared, deadline)
                published = await anyio.to_thread.run_sync(self._validate, generated, deadline)
                try:
                    terminal = await anyio.to_thread.run_sync(
                        self._storage.publish, claim, published, deadline.wall_at
                    )
                except CommitOutcomeUnknown:
                    durable_terminal = await anyio.to_thread.run_sync(
                        self._storage.read_terminal, claim.resource_id
                    )
                    if durable_terminal is None:
                        raise
                    terminal = durable_terminal
            state.terminal = terminal
        except TimeoutError:
            state.terminal = await self._finalize_failure(
                claim,
                ExecutionFailure(
                    code="deadline_exceeded",
                    safe_message="The operation deadline expired.",
                    retryable=True,
                ),
            )
        except BaseException as error:
            if isinstance(error, anyio.get_cancelled_exc_class()):
                failure = ExecutionFailure(
                    code="process_interrupted",
                    safe_message="The operation was interrupted during shutdown.",
                    retryable=True,
                )
            else:
                failure = (
                    self._failure_mapper(error)
                    if self._failure_mapper is not None
                    else ExecutionFailure(
                        code="internal_error",
                        safe_message="The operation could not be completed.",
                        retryable=True,
                    )
                )
            try:
                state.terminal = await self._finalize_failure(claim, failure)
            except BaseException as finalization_error:
                state.error = finalization_error
            if isinstance(error, anyio.get_cancelled_exc_class()):
                raise
        finally:
            state.event.set()

    async def _finalize_failure(
        self, claim: ExecutionClaim, failure: ExecutionFailure
    ) -> ExecutionTerminal:
        with anyio.fail_after(self._finalization_timeout_seconds, shield=True):
            return await anyio.to_thread.run_sync(self._storage.fail, claim, failure)
