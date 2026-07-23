"""Tests for the domain-error → HTTP mapping and the error envelope."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from complianceiq.domain.exceptions import (
    NotFoundError,
    RateLimitError,
    TenantIsolationError,
    ValidationError,
)
from complianceiq.infrastructure.http.middleware import CorrelationIdMiddleware
from complianceiq.presentation.errors import register_exception_handlers


@pytest.fixture
def error_client() -> TestClient:
    """An app whose routes raise chosen domain errors, for handler testing."""
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/boom/not-found")
    async def _not_found() -> None:
        raise NotFoundError("finding not found")

    @app.get("/boom/validation")
    async def _validation() -> None:
        raise ValidationError("bad input", details={"field": "severity"})

    @app.get("/boom/tenant")
    async def _tenant() -> None:
        raise TenantIsolationError("blocked", details={"expected_tenant_id": "a"})

    @app.get("/boom/rate")
    async def _rate() -> None:
        raise RateLimitError("slow down")

    @app.get("/boom/unexpected")
    async def _unexpected() -> None:
        raise RuntimeError("secret internal detail")

    # raise_server_exceptions=False mirrors production: the 500 handler runs and
    # returns a sanitised envelope instead of the exception propagating.
    return TestClient(app, raise_server_exceptions=False)


def test_not_found_maps_to_404_envelope(error_client: TestClient) -> None:
    response = error_client.get("/boom/not-found")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "finding not found"
    assert body["error"]["correlation_id"]


def test_validation_maps_to_422_with_details(error_client: TestClient) -> None:
    response = error_client.get("/boom/validation")
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"field": "severity"}


def test_tenant_isolation_maps_to_403(error_client: TestClient) -> None:
    response = error_client.get("/boom/tenant")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tenant_isolation_violation"


def test_rate_limit_maps_to_429(error_client: TestClient) -> None:
    response = error_client.get("/boom/rate")
    assert response.status_code == 429


def test_unexpected_error_is_sanitised(error_client: TestClient) -> None:
    # The raw exception message must never reach the client.
    response = error_client.get("/boom/unexpected")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert body["error"]["correlation_id"]
