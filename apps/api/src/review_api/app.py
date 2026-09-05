from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import FastAPI
from review_core.domain.errors import DomainError

from review_api.dependencies import build_platform
from review_api.docs import mount_offline_docs
from review_api.errors import domain_error_handler
from review_api.middleware import request_context
from review_api.routes import bootstrap, documents, findings, health, profiles, reviews


def create_app(*, composition: str = "fixture") -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.platform = build_platform(composition)
    app.state.external_connection_attempts = []
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
    canonical = yaml.safe_load((root / "contracts/review-platform/v1/openapi.yaml").read_text())
    app.openapi = lambda: canonical  # type: ignore[method-assign]
    return app


app = create_app()
