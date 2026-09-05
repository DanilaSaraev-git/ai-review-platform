from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from review_runtime.config.model_profiles import project_availability
from review_runtime.models.config import EndpointPolicy


def test_exact_endpoint_rejects_credentials_query_and_fragment() -> None:
    for value in ("http://user:pass@127.0.0.1", "http://127.0.0.1?a=1", "http://127.0.0.1/#x"):
        with pytest.raises(ValueError):
            EndpointPolicy(value).validate()


def test_dns_allowlist_is_exact() -> None:
    assert EndpointPolicy("http://127.0.0.1:11434", frozenset({"127.0.0.1"})).validate()
    with pytest.raises(ValueError):
        EndpointPolicy("http://127.0.0.1:11434", frozenset({"127.0.0.2"})).validate()


def test_only_fresh_available_projects_available() -> None:
    now = datetime.now(UTC)
    assert (
        project_availability({"state": "available", "expires_at": now + timedelta(seconds=1)}, now=now)
        == "available"
    )
    for state in ("unavailable", "degraded", "unknown", "missing"):
        assert (
            project_availability({"state": state, "expires_at": now + timedelta(seconds=1)}, now=now)
            == "unavailable"
        )
    assert project_availability({"state": "available", "expires_at": now}, now=now) == "unavailable"
    assert project_availability(None, now=now) == "unavailable"
