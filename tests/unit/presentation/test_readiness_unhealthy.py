"""Readiness endpoint returns 503 when a dependency is unhealthy."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from complianceiq.application.app_info import AppInfo
from complianceiq.application.services.health import ReadinessService
from complianceiq.domain.ports.health import HealthProbe, HealthResult
from complianceiq.presentation.app import create_app


class _UnhealthyProbe(HealthProbe):
    @property
    def name(self) -> str:
        return "database"

    async def check(self) -> HealthResult:
        return HealthResult(name="database", healthy=False, detail="connection refused")


@dataclass(frozen=True)
class _Container:
    app_info: AppInfo
    readiness_service: ReadinessService


def test_readiness_returns_503_when_dependency_unhealthy() -> None:
    container = _Container(
        app_info=AppInfo(name="complianceiq-ai", version="0.1.0", environment="local"),
        readiness_service=ReadinessService([_UnhealthyProbe()]),
    )
    client = TestClient(create_app(container))

    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    assert body["components"][0]["name"] == "database"
    assert body["components"][0]["healthy"] is False
