"""Exception handlers — the single domain-error → HTTP mapping.

Domain and application code raises typed :class:`ComplianceIQError` subclasses
that know nothing about HTTP. This module owns the one place where those errors
become status codes and :class:`ErrorEnvelope` responses. Centralising it means:

- every error looks identical on the wire,
- no stack trace or internal detail ever reaches a client (security),
- adding a new domain error means adding one line here, not touching handlers.

Unexpected (non-domain) exceptions become a generic 500 with a correlation ID
the client can quote to support — the real cause is in the logs, never the body.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from complianceiq.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ComplianceIQError,
    DependencyUnavailableError,
    GroundingError,
    NotFoundError,
    ProviderError,
    RateLimitError,
    TenantIsolationError,
    UnsafeContentError,
    UnsafeTargetError,
    ValidationError,
)
from complianceiq.presentation.schemas import ErrorBody, ErrorEnvelope

# Domain exception type → HTTP status. Subclasses are matched most-specific-first
# by iterating in declaration order, so TenantIsolationError (a subclass of
# AuthorizationError) is mapped before its parent.
_STATUS_BY_EXCEPTION: tuple[tuple[type[ComplianceIQError], int], ...] = (
    (ValidationError, 422),
    (NotFoundError, 404),
    (AuthenticationError, 401),
    (TenantIsolationError, 403),
    (AuthorizationError, 403),
    (RateLimitError, 429),
    (GroundingError, 422),
    (UnsafeContentError, 400),
    (UnsafeTargetError, 403),
    (ProviderError, 502),
    (DependencyUnavailableError, 503),
)


def _correlation_id(request: Request) -> str | None:
    """Read the correlation ID stamped on the request by the middleware."""
    return getattr(request.state, "correlation_id", None)


def _status_for(error: ComplianceIQError) -> int:
    """Resolve the HTTP status for a domain error (default 500)."""
    for exc_type, status in _STATUS_BY_EXCEPTION:
        if isinstance(error, exc_type):
            return status
    return 500


def _envelope(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str | None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Render an error envelope JSON response with the given status."""
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            correlation_id=correlation_id,
            details=details or {},
        )
    )
    return JSONResponse(content=envelope.model_dump(), status_code=status_code)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""

    @app.exception_handler(ComplianceIQError)
    async def _handle_domain_error(request: Request, exc: ComplianceIQError) -> JSONResponse:
        return _envelope(
            status_code=_status_for(exc),
            code=exc.code,
            message=exc.message,
            correlation_id=_correlation_id(request),
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI/Pydantic input validation failure at the boundary.
        return _envelope(
            status_code=422,
            code="validation_error",
            message="request validation failed",
            correlation_id=_correlation_id(request),
            details={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak the exception detail to the client; it is logged server-side.
        return _envelope(
            status_code=500,
            code="internal_error",
            message="an unexpected error occurred",
            correlation_id=_correlation_id(request),
        )
