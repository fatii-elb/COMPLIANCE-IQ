"""LOCAL-only development sign-in (mint a test token).

Exposes ``POST /api/v1/auth/dev-token`` so a developer or a client tester can
obtain a valid JWT for the frontend without running a script. It mints an HS256
token carrying the tenant/subject/roles the caller asks for.

This router is **only mounted in non-production environments** (see
``composition.build_app``). To honour the architecture's layer boundaries
(presentation must not import infrastructure), the actual token-minting is
injected as a callable by the composition root — this module stays free of any
infrastructure import. It is a testing convenience, never a way to bypass the
real, Core-issued authentication used in staging/production.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

#: A token minter: ``(subject, tenant_id, roles, ttl_seconds) -> (token, expires_at)``.
TokenMinter = Callable[[str, str, Sequence[str], int], tuple[str, int]]


class DevTokenRequest(BaseModel):
    """Body for ``POST /api/v1/auth/dev-token``."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant-a", min_length=1, max_length=128)
    subject: str = Field(default="demo.analyst@acme.example", min_length=1, max_length=256)
    roles: list[str] = Field(default_factory=lambda: ["analyst"], max_length=20)
    ttl_minutes: int = Field(default=120, ge=1, le=1440)


class DevTokenResponse(BaseModel):
    """The minted token and the identity it carries."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "Bearer"
    expires_at: int
    subject: str
    tenant_id: str
    roles: list[str]


def build_dev_auth_router(mint: TokenMinter) -> APIRouter:
    """Build the dev-login router around an injected token minter."""
    router = APIRouter(prefix="/api/v1/auth", tags=["auth (dev)"])

    @router.post("/dev-token", response_model=DevTokenResponse, summary="Mint a test token")
    async def dev_token(body: DevTokenRequest) -> DevTokenResponse:
        """Mint a short-lived token for local testing (never mounted in production)."""
        token, expires_at = mint(body.subject, body.tenant_id, body.roles, body.ttl_minutes * 60)
        return DevTokenResponse(
            access_token=token,
            expires_at=expires_at,
            subject=body.subject,
            tenant_id=body.tenant_id,
            roles=body.roles,
        )

    return router
