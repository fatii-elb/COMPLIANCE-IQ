"""API tests for the operational endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from complianceiq import __version__
from complianceiq.infrastructure.http.middleware import CORRELATION_HEADER


def test_health_liveness(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_readiness_is_healthy_with_no_dependencies(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["components"] == []


def test_version_reports_environment(client: TestClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "complianceiq-ai"
    assert body["version"] == __version__
    assert body["environment"] == "local"


def test_correlation_id_is_echoed(client: TestClient) -> None:
    # No inbound ID → the middleware generates one and returns it.
    response = client.get("/health")
    assert response.headers.get(CORRELATION_HEADER)


def test_inbound_correlation_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "trace-xyz"})
    assert response.headers.get(CORRELATION_HEADER) == "trace-xyz"
