"""Typed domain exceptions.

The domain speaks in *domain* terms, never HTTP. Each exception carries a stable
machine-readable ``code`` and a safe ``message``; the presentation layer owns
the single mapping from these types to HTTP status codes and the
``ErrorEnvelope`` wire shape. This keeps the domain framework-free while giving
the API consistent, predictable error semantics.

Design notes:
- ``code`` is a stable slug for clients to switch on (never a raw stack trace).
- ``message`` is safe to return to a client — it must never embed secrets or
  full customer payloads.
- ``details`` carries structured, non-sensitive context for observability.
"""

from __future__ import annotations

from typing import Any


class ComplianceIQError(Exception):
    """Base class for all domain and application errors.

    Attributes:
        code: Stable machine-readable error slug.
        message: Human-readable, client-safe description.
        details: Optional structured, non-sensitive context.
    """

    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class ValidationError(ComplianceIQError):
    """Input failed a business-rule validation (maps to HTTP 422)."""

    code = "validation_error"


class NotFoundError(ComplianceIQError):
    """A requested resource does not exist within the tenant (HTTP 404)."""

    code = "not_found"


class AuthenticationError(ComplianceIQError):
    """The caller could not be authenticated (HTTP 401)."""

    code = "authentication_error"


class AuthorizationError(ComplianceIQError):
    """The caller is authenticated but not permitted (HTTP 403)."""

    code = "authorization_error"


class TenantIsolationError(AuthorizationError):
    """A cross-tenant access was attempted and blocked (HTTP 403).

    Raised whenever code tries to touch data whose ``tenant_id`` differs from the
    authenticated context's. This is a security-critical invariant (non-negotiable
    rule 1); every occurrence is logged and alert-worthy.
    """

    code = "tenant_isolation_violation"


class RateLimitError(ComplianceIQError):
    """The caller exceeded a rate limit or quota (HTTP 429)."""

    code = "rate_limited"


class GroundingError(ComplianceIQError):
    """Generation could not be grounded in retrieved sources (HTTP 422).

    Raised when the grounding guarantee (rule 3) cannot be satisfied and the
    situation is an error rather than a clean abstention.
    """

    code = "grounding_error"


class UnsafeContentError(ComplianceIQError):
    """Input or output tripped a safety control (HTTP 400).

    Covers prompt-injection detection, secret/PII leakage, and unsafe outputs.
    """

    code = "unsafe_content"


class UnsafeTargetError(ComplianceIQError):
    """A potentially-mutating action targeted a non-sandbox environment (HTTP 403).

    Backstops non-negotiable rules 2 and 8: this service never changes a customer
    environment. Any code path that could is gated to raise this off-sandbox.
    """

    code = "unsafe_target"


class ProviderError(ComplianceIQError):
    """An upstream LLM/provider call failed after retries (HTTP 502)."""

    code = "provider_error"


class DependencyUnavailableError(ComplianceIQError):
    """A required downstream dependency is unavailable (HTTP 503)."""

    code = "dependency_unavailable"
