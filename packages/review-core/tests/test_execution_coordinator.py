from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import pytest
from review_core.application.execution import (
    AsyncExecutionCoordinator,
    CommitOutcomeUnknown,
    ExecutionAdmission,
    ExecutionClaim,
    ExecutionDeadline,
    ExecutionFailure,
    ExecutionTerminal,
)


@dataclass
class FakeStorage:
    terminal: ExecutionTerminal | None = None
    fail_calls: int = 0

    def admit(self, request: object, deadline_at: datetime) -> ExecutionAdmission:
        del request, deadline_at
        return ExecutionAdmission(resource_id="run-1", execution_id="execution-1", replay=False)

    def claim(self, admission: ExecutionAdmission, owner_token: str) -> ExecutionClaim | None:
        return ExecutionClaim(
            resource_id=admission.resource_id,
            execution_id=admission.execution_id,
            owner_token=owner_token,
        )

    def save_prepared(self, claim: ExecutionClaim, prepared: object) -> None:
        del claim, prepared

    def publish(
        self, claim: ExecutionClaim, result: object, deadline_at: datetime
    ) -> ExecutionTerminal:
        del claim, result, deadline_at
        self.terminal = ExecutionTerminal(resource_id="run-1", state="completed")
        return self.terminal

    def fail(self, claim: ExecutionClaim, failure: ExecutionFailure) -> ExecutionTerminal:
        del claim
        self.fail_calls += 1
        self.terminal = ExecutionTerminal(
            resource_id="run-1", state="failed", error_code=failure.code
        )
        return self.terminal

    def read_terminal(self, resource_id: str) -> ExecutionTerminal | None:
        assert resource_id == "run-1"
        return self.terminal


def test_deadline_uses_one_monotonic_budget_and_persists_wall_clock() -> None:
    deadline = ExecutionDeadline.start(
        timeout_seconds=60,
        monotonic_now=10.0,
        wall_now=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert deadline.remaining(25.5) == pytest.approx(44.5)
    assert deadline.wall_at == datetime(2026, 9, 5, 0, 1, tzinfo=UTC)
    assert not deadline.expired(69.999)
    assert deadline.expired(70.0)


async def test_waiter_cancellation_does_not_cancel_accepted_operation() -> None:
    storage = FakeStorage()
    entered = anyio.Event()
    release = anyio.Event()

    def prepare(request: object, deadline: ExecutionDeadline) -> object:
        del deadline
        return request

    async def generate(prepared: object, deadline: ExecutionDeadline) -> object:
        del deadline
        entered.set()
        await release.wait()
        return prepared

    async with AsyncExecutionCoordinator(
        storage=storage,
        prepare=prepare,
        generate=generate,
        validate=lambda value, deadline: value,
        timeout_seconds=60,
        owner_token_factory=lambda: "owner-1",
    ) as coordinator:
        handle = await coordinator.submit({"document": "synthetic"})
        await entered.wait()
        with anyio.move_on_after(0) as waiter_scope:
            await coordinator.wait(handle)
        assert waiter_scope.cancel_called

        release.set()
        terminal = await coordinator.wait(handle)

    assert terminal.state == "completed"
    assert storage.fail_calls == 0


async def test_three_operations_reach_generate_without_application_limiter() -> None:
    entered = [anyio.Event() for _ in range(3)]
    release = anyio.Event()

    class MultiStorage(FakeStorage):
        next_id = 0

        def admit(self, request: object, deadline_at: datetime) -> ExecutionAdmission:
            del request, deadline_at
            self.next_id += 1
            value = str(self.next_id)
            return ExecutionAdmission(
                resource_id=f"run-{value}", execution_id=f"execution-{value}", replay=False
            )

        def publish(
            self, claim: ExecutionClaim, result: object, deadline_at: datetime
        ) -> ExecutionTerminal:
            del result, deadline_at
            return ExecutionTerminal(resource_id=claim.resource_id, state="completed")

    async def generate(prepared: object, deadline: ExecutionDeadline) -> object:
        del deadline
        assert isinstance(prepared, str)
        entered[int(prepared) - 1].set()
        await release.wait()
        return prepared

    async with AsyncExecutionCoordinator(
        storage=MultiStorage(),
        prepare=lambda request, deadline: request,
        generate=generate,
        validate=lambda value, deadline: value,
        timeout_seconds=60,
        owner_token_factory=lambda: "owner",
    ) as coordinator:
        handles = [await coordinator.submit(str(index)) for index in range(1, 4)]
        for event in entered:
            with anyio.fail_after(1):
                await event.wait()
        release.set()
        terminals = [await coordinator.wait(handle) for handle in handles]

    assert [terminal.state for terminal in terminals] == ["completed"] * 3


async def test_deadline_failure_is_bounded_and_published_once() -> None:
    storage = FakeStorage()

    async def generate(prepared: object, deadline: ExecutionDeadline) -> Any:
        del prepared, deadline
        await anyio.sleep(0.05)
        return "late"

    async with AsyncExecutionCoordinator(
        storage=storage,
        prepare=lambda request, deadline: request,
        generate=generate,
        validate=lambda value, deadline: value,
        timeout_seconds=0.01,
        finalization_timeout_seconds=1,
        owner_token_factory=lambda: "owner-1",
    ) as coordinator:
        terminal = await coordinator.run("request")

    assert terminal == ExecutionTerminal(
        resource_id="run-1", state="failed", error_code="deadline_exceeded"
    )
    assert storage.fail_calls == 1


def test_terminal_wall_clock_boundary_is_strict() -> None:
    deadline = ExecutionDeadline.start(
        timeout_seconds=60,
        monotonic_now=0,
        wall_now=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert deadline.admits_terminal_cas(deadline.wall_at - timedelta(microseconds=1))
    assert not deadline.admits_terminal_cas(deadline.wall_at)


async def test_unknown_commit_outcome_is_resolved_from_durable_terminal_state() -> None:
    class UnknownCommitStorage(FakeStorage):
        def publish(
            self, claim: ExecutionClaim, result: object, deadline_at: datetime
        ) -> ExecutionTerminal:
            del claim, result, deadline_at
            self.terminal = ExecutionTerminal(resource_id="run-1", state="completed")
            raise CommitOutcomeUnknown

    storage = UnknownCommitStorage()

    async def generate(prepared: object, deadline: ExecutionDeadline) -> object:
        del deadline
        await anyio.lowlevel.checkpoint()
        return prepared

    async with AsyncExecutionCoordinator(
        storage=storage,
        prepare=lambda request, deadline: request,
        generate=generate,
        validate=lambda value, deadline: value,
        timeout_seconds=60,
        owner_token_factory=lambda: "owner-1",
    ) as coordinator:
        terminal = await coordinator.run("request")

    assert terminal == ExecutionTerminal(resource_id="run-1", state="completed")
    assert storage.fail_calls == 0


async def test_shutdown_cancels_after_grace_and_runs_guarded_failure_cleanup() -> None:
    storage = FakeStorage()
    entered = anyio.Event()

    async def generate(prepared: object, deadline: ExecutionDeadline) -> object:
        del prepared, deadline
        entered.set()
        await anyio.sleep_forever()
        raise AssertionError("unreachable")

    async with AsyncExecutionCoordinator(
        storage=storage,
        prepare=lambda request, deadline: request,
        generate=generate,
        validate=lambda value, deadline: value,
        timeout_seconds=60,
        owner_token_factory=lambda: "owner-1",
    ) as coordinator:
        handle = await coordinator.submit("request")
        await entered.wait()
        await coordinator.shutdown(grace_seconds=0)
        terminal = await coordinator.wait(handle)

    assert terminal == ExecutionTerminal(
        resource_id="run-1", state="failed", error_code="process_interrupted"
    )
    assert storage.fail_calls == 1
