"""Operational endpoints: liveness, readiness, and build info.

These are unauthenticated by design (orchestrators and load balancers call them
without credentials) and tenant-agnostic. They expose no customer data.

- ``GET /health``       — liveness: the process is up.
- ``GET /health/ready`` — readiness: all dependencies reachable (503 if not).
- ``GET /version``      — build/identity metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from complianceiq.application.app_info import AppInfo
from complianceiq.application.services.health import ReadinessService
from complianceiq.presentation.container import get_app_info, get_readiness_service
from complianceiq.presentation.schemas import (
    ComponentHealth,
    HealthResponse,
    ReadinessResponse,
    VersionResponse,
)

router = APIRouter(tags=["operations"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(app_info: AppInfo = Depends(get_app_info)) -> HealthResponse:
    """Return liveness. Cheap and dependency-free — only asserts the app runs."""
    return HealthResponse(status="ok", version=app_info.version)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
)
async def readiness(
    response: Response,
    service: ReadinessService = Depends(get_readiness_service),
) -> ReadinessResponse:
    """Return readiness, aggregating all dependency probes.

    Responds 503 when any dependency is unhealthy so orchestrators pull this
    instance out of rotation without terminating it.
    """
    report = await service.check()
    if not report.ready:
        response.status_code = 503
    return ReadinessResponse(
        ready=report.ready,
        components=[
            ComponentHealth(name=c.name, healthy=c.healthy, detail=c.detail)
            for c in report.components
        ],
    )


@router.get("/version", response_model=VersionResponse, summary="Build/version info")
async def version(app_info: AppInfo = Depends(get_app_info)) -> VersionResponse:
    """Return service name, semantic version, and deployment environment."""
    return VersionResponse(
        name=app_info.name,
        version=app_info.version,
        environment=app_info.environment,
    )
