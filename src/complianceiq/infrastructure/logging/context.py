"""Correlation-ID context propagation.

Every request is assigned a correlation ID that is bound into a context variable
and automatically attached to every log line emitted while handling that request
— across middleware, use cases, and (later) graph nodes and provider calls. This
is what lets an operator reconstruct a single request's entire journey from the
logs, satisfying the audit-trail requirement (non-negotiable rule 7).

``contextvars`` are async-safe: each request/task gets its own isolated binding,
so concurrent requests never bleed correlation IDs into one another.
"""

from __future__ import annotations

import uuid

import structlog

CORRELATION_ID_KEY = "correlation_id"


def new_correlation_id() -> str:
    """Generate a fresh, unique correlation ID."""
    return uuid.uuid4().hex


def bind_correlation_id(correlation_id: str) -> None:
    """Bind ``correlation_id`` so it appears on all subsequent log lines."""
    structlog.contextvars.bind_contextvars(**{CORRELATION_ID_KEY: correlation_id})


def bind_tenant(tenant_id: str) -> None:
    """Bind the acting ``tenant_id`` onto the logging context.

    Tenant is part of the audit trail; binding it here means it is stamped on
    every log line without each call site having to pass it.
    """
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id)


def clear_context() -> None:
    """Clear all context-local bindings at the end of a request."""
    structlog.contextvars.clear_contextvars()
