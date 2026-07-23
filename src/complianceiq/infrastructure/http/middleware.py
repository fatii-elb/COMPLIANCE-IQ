"""ASGI middleware for cross-cutting HTTP concerns.

Middleware belongs to infrastructure: it adapts the ASGI transport and the
logging subsystem, both outside the business core. The composition root attaches
these to the FastAPI app, so the presentation layer never imports them.

Two middlewares:

- :class:`CorrelationIdMiddleware` — assigns/propagates a correlation ID, binds
  it (and later the tenant) into the structured-logging context, records a
  structured access log with latency, and echoes the ID back in a response
  header. This is the backbone of the audit trail (non-negotiable rule 7).
- :class:`RequestSizeLimitMiddleware` — rejects over-large request bodies early
  (defence against resource-exhaustion), returning a consistent error envelope.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from complianceiq.infrastructure.logging.context import (
    bind_correlation_id,
    clear_context,
    new_correlation_id,
)
from complianceiq.infrastructure.logging.setup import get_logger

CORRELATION_HEADER = "X-Correlation-ID"

_RequestHandler = Callable[[Request], Awaitable[Response]]

_logger = get_logger("http.access")


class CorrelationIdMiddleware:
    """Assign a correlation ID, bind logging context, and emit an access log."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        correlation_id = request.headers.get(CORRELATION_HEADER) or new_correlation_id()

        # Bind for every log line produced while handling this request, and make
        # it available to presentation error handlers via request.state.
        bind_correlation_id(correlation_id)
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        start = time.perf_counter()
        status_holder: dict[str, int] = {"status": 500}

        async def send_wrapper(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((CORRELATION_HEADER.encode(), correlation_id.encode()))
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            _logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=status_holder["status"],
                duration_ms=elapsed_ms,
            )
            clear_context()


class RequestSizeLimitMiddleware:
    """Reject requests whose declared body exceeds ``max_bytes``."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = 0
            if declared > self._max_bytes:
                correlation_id = scope.get("state", {}).get("correlation_id")
                response = _too_large(self._max_bytes, correlation_id)
                await response(scope, receive, send)
                return

        await self._app(scope, receive, send)


def _too_large(max_bytes: int, correlation_id: str | None) -> JSONResponse:
    """Build the 413 error envelope for an over-large request."""
    return JSONResponse(
        status_code=413,
        content={
            "error": {
                "code": "request_too_large",
                "message": f"request body exceeds the {max_bytes}-byte limit",
                "correlation_id": correlation_id,
                "details": {"max_bytes": max_bytes},
            }
        },
    )
