"""Deferred queue prototype; excluded from the default local MVP runtime."""

from __future__ import annotations

import os

from review_runtime.queue.procrastinate import create_procrastinate_app

procrastinate_app = create_procrastinate_app(
    os.environ.get(
        "REVIEW_QUEUE_DATABASE_URL",
        "postgresql://review:review@127.0.0.1:55439/review",
    )
)


@procrastinate_app.task(name="review.execute_review")
async def execute_review(**payload: object) -> None:
    from review_runtime.queue.outbox import validate_job_envelope

    validate_job_envelope({"kind": "execute_review", **payload})


@procrastinate_app.task(name="review.generate_dialogue")
async def generate_dialogue(**payload: object) -> None:
    from review_runtime.queue.outbox import validate_job_envelope

    validate_job_envelope({"kind": "generate_dialogue", **payload})
