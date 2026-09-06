from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI
from review_core.domain.errors import DomainError

from review_api.dependencies import build_components
from review_api.docs import mount_offline_docs
from review_api.errors import domain_error_handler
from review_api.guest_access import guest_access_context, guest_access_enabled
from review_api.middleware import request_context
from review_api.routes import bootstrap, documents, findings, health, profiles, reviews


def create_app(
    *,
    composition: str = "fixture",
    model_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    platform, runtime = build_components(composition, model_transport=model_transport)
    guest_access = guest_access_enabled(os.environ.get("REVIEW_GUEST_ACCESS", "false"))
    guest_sessions = None
    guest_contexts = None
    if guest_access:
        from review_runtime.postgres.platform import PostgresReviewPlatform
        from review_runtime.security.guest_contexts import GuestContextRegistry
        from review_runtime.security.guest_sessions import GuestSessionStore
        from review_runtime.security.guest_storage import GuestStorageLimits

        if not isinstance(platform, PostgresReviewPlatform):
            raise ValueError("Guest access requires persistent PostgreSQL storage")
        guest_sessions = GuestSessionStore(
            platform.database_url, str(platform.settings.deployment_id), platform.organization_id
        )
        guest_contexts = GuestContextRegistry(platform, runtime)
        guest_storage_limits = GuestStorageLimits.from_environment()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        import anyio

        startup = getattr(platform, "startup", None)
        shutdown = getattr(platform, "shutdown", None)
        if callable(startup):
            await anyio.to_thread.run_sync(startup)
        try:
            from contextlib import AsyncExitStack

            async with AsyncExitStack() as stack:
                if runtime is not None:
                    await stack.enter_async_context(runtime)
                if guest_contexts is not None and guest_sessions is not None:
                    await stack.enter_async_context(guest_contexts)
                    for session in await anyio.to_thread.run_sync(guest_sessions.workspaces):
                        await guest_contexts.reconcile(session.workspace_id, session.actor_id)
                yield
        finally:
            if callable(shutdown):
                await anyio.to_thread.run_sync(shutdown)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.platform = platform
    app.state.ml_runtime = runtime
    app.state.external_connection_attempts = []
    app.state.guest_access = guest_access
    app.state.guest_sessions = guest_sessions
    app.state.guest_contexts = guest_contexts
    if guest_access:
        app.state.guest_storage_limits = guest_storage_limits
    app.middleware("http")(guest_access_context)
    app.middleware("http")(request_context)
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    for router in (
        bootstrap.router,
        documents.router,
        profiles.router,
        reviews.router,
        findings.router,
        health.router,
    ):
        app.include_router(router)
    mount_offline_docs(app)
    root = Path(__file__).resolve().parents[4]
    contract_family = "guest-v1" if guest_access else "v1"
    canonical = yaml.safe_load(
        (root / f"contracts/review-platform/{contract_family}/openapi.yaml").read_text()
    )
    app.openapi = lambda: canonical  # type: ignore[method-assign]
    return app


app = create_app()
