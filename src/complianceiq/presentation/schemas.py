"""Wire schemas for the HTTP API.

These Pydantic models define the exact JSON shapes clients see. Keeping them in
the presentation layer (separate from domain entities) means the public API
contract can evolve independently of internal domain models, and lets us control
precisely what is exposed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    """The body of an :class:`ErrorEnvelope`."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Stable machine-readable error slug.")
    message: str = Field(description="Human-readable, client-safe description.")
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing this request in the logs.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured, non-sensitive context about the error.",
    )


class ErrorEnvelope(BaseModel):
    """The single error shape returned by every endpoint on failure.

    A consistent envelope means clients parse errors one way everywhere, and no
    stack trace or internal detail ever leaks to the caller.
    """

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


class HealthResponse(BaseModel):
    """Liveness response — the process is up and serving."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="ok")
    version: str


class ComponentHealth(BaseModel):
    """Health of a single dependency within the readiness response."""

    model_config = ConfigDict(extra="forbid")

    name: str
    healthy: bool
    detail: str = ""


class ReadinessResponse(BaseModel):
    """Readiness response — whether all dependencies are reachable."""

    model_config = ConfigDict(extra="forbid")

    ready: bool
    components: list[ComponentHealth] = Field(default_factory=list)


class VersionResponse(BaseModel):
    """Build/version metadata for operators and clients."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    environment: str
