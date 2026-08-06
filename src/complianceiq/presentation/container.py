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

from complianceiq.application.agents import AgentSuite
from complianceiq.application.app_info import AppInfo
from complianceiq.application.services.health import ReadinessService
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import AuthenticationError
from complianceiq.domain.ports.auth import TokenVerifier
from complianceiq.domain.ports.core import CoreClient

#: The scheme prefix on the Authorization header.
_BEARER_PREFIX = "Bearer "


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

    @property
    def agents(self) -> AgentSuite: ...

    @property
    def token_verifier(self) -> TokenVerifier: ...

    @property
    def core_client(self) -> CoreClient: ...


def get_container(request: Request) -> Container:
    """Resolve the composition container attached to the app at startup."""
    return request.app.state.container  # type: ignore[no-any-return]


def get_app_info(request: Request) -> AppInfo:
    """FastAPI dependency: the application metadata DTO."""
    return get_container(request).app_info


def get_readiness_service(request: Request) -> ReadinessService:
    """FastAPI dependency: the readiness use case."""
    return get_container(request).readiness_service


def get_agents(request: Request) -> AgentSuite:
    """FastAPI dependency: the wired agent suite (the AI capabilities)."""
    return get_container(request).agents


def get_core_client(request: Request) -> CoreClient:
    """FastAPI dependency: the Core Service client (findings source)."""
    return get_container(request).core_client


def get_bearer_token(request: Request) -> str:
    """FastAPI dependency: the caller's raw bearer token, to forward to the Core.

    Authentication itself happens in :func:`get_auth_context`; this simply
    surfaces the same token so a downstream Core call can be made on the caller's
    behalf (end-to-end identity propagation).
    """
    header = request.headers.get("Authorization")
    if not header or not header.startswith(_BEARER_PREFIX):
        raise AuthenticationError("missing or malformed Authorization header")
    return header[len(_BEARER_PREFIX) :].strip()


def get_auth_context(request: Request) -> AuthContext:
    """FastAPI dependency: authenticate the caller and return their context.

    Reads the ``Authorization: Bearer <token>`` header and verifies it via the
    wired :class:`TokenVerifier`. The returned :class:`AuthContext` carries the
    tenant every downstream call is scoped by (non-negotiable rule 1).

    Raises:
        AuthenticationError: If the header is missing/malformed or the token
            fails verification (mapped to HTTP 401 by the error handlers).
    """
    header = request.headers.get("Authorization")
    if not header or not header.startswith(_BEARER_PREFIX):
        raise AuthenticationError("missing or malformed Authorization header")
    token = header[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise AuthenticationError("empty bearer token")
    return get_container(request).token_verifier.verify(token)
