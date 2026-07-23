"""Dependency-injection surface for the presentation layer.

The presentation layer must not import infrastructure (they are independent
sibling adapters). Yet routers need access to the wired application services. We
resolve this with a structural :class:`Container` protocol: presentation declares
*what* it needs (application-layer services and DTOs), and the concrete container
built at the composition root satisfies it structurally — no import from
presentation into infrastructure, and full static typing preserved.

FastAPI resolves the container from ``request.app.state`` via the dependency
providers below, so routers receive typed services through ``Depends`` without
touching global state.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import Request

from complianceiq.application.app_info import AppInfo
from complianceiq.application.services.health import ReadinessService


class Container(Protocol):
    """The services the presentation layer requires from composition.

    Any object exposing these attributes (the composition root's container does)
    can drive the API. This is the Dependency Inversion Principle applied to
    wiring: presentation depends on this abstraction, not on the concrete
    container.
    """

    @property
    def app_info(self) -> AppInfo: ...

    @property
    def readiness_service(self) -> ReadinessService: ...


def get_container(request: Request) -> Container:
    """Resolve the composition container attached to the app at startup."""
    return request.app.state.container  # type: ignore[no-any-return]


def get_app_info(request: Request) -> AppInfo:
    """FastAPI dependency: the application metadata DTO."""
    return get_container(request).app_info


def get_readiness_service(request: Request) -> ReadinessService:
    """FastAPI dependency: the readiness use case."""
    return get_container(request).readiness_service
