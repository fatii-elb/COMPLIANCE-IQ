"""Wire schemas for the HTTP API.

These Pydantic models define the exact JSON shapes clients see. Keeping them in
the presentation layer (separate from domain entities) means the public API
contract can evolve independently of internal domain models, and lets us control
precisely what is exposed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.value_objects.enums import Framework


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


# --------------------------------------------------------------------------- #
# AI capability request envelopes (Phase 5).
#
# The response shapes are the domain contracts themselves (EnrichedFinding,
# CopilotAnswer, RemediationProposal, ReportDraft) — the Core Service integration
# handoff treats those models as the canonical wire contract, so we return them
# directly rather than duplicate-and-drift a second set of DTOs. The request
# envelopes below just wrap those contract inputs.
# --------------------------------------------------------------------------- #


class EnrichRequest(BaseModel):
    """Body for ``POST /ai/enrich`` — findings to explain and cite."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = Field(min_length=1, max_length=100)


class AskRequest(BaseModel):
    """Body for ``POST /ai/ask`` — a grounded natural-language question."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    framework: Framework | None = Field(
        default=None, description="Optional framework to scope retrieval to."
    )


class RemediateRequest(BaseModel):
    """Body for ``POST /ai/remediate`` — one finding to propose a fix for."""

    model_config = ConfigDict(extra="forbid")

    finding: Finding


class CorrelateRequest(BaseModel):
    """Body for ``POST /ai/correlate`` — findings to correlate as systemic risk."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = Field(min_length=1, max_length=100)


class CorrelateResponse(BaseModel):
    """Response for ``POST /ai/correlate`` — the grounded risk narrative."""

    model_config = ConfigDict(extra="forbid")

    narrative: str


class ReportRequest(BaseModel):
    """Body for ``POST /ai/report`` — enriched findings to summarise."""

    model_config = ConfigDict(extra="forbid")

    findings: list[EnrichedFinding] = Field(min_length=0, max_length=1000)
