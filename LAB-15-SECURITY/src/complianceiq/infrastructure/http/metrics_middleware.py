"""ASGI middleware that records per-request metrics.

Times every HTTP request and records two series against the :class:`MetricsSink`:
a ``http_requests_total`` counter (by method, route, status class) and a
``http_request_duration_ms`` summary (by method, route). It uses the *matched
route template* (e.g. ``/api/v1/ai/enrich``) rather than the raw path, so metric
cardinality stays bounded even if a path ever carries an id.

A metrics failure must never break a request, so recording is best-effort.
"""

from __future__ import annotations

import time

from starlette.requests import Request
from starlette.types import ASGIApp

from complianceiq.domain.ports.metrics import MetricsSink


class MetricsMiddleware:
    """Records request count and latency per route into a metrics sink."""

    def __init__(self, app: ASGIApp, *, metrics: MetricsSink) -> None:
        self._app = app
        self._metrics = metrics

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        status_holder: dict[str, int] = {"status": 500}

        async def send_wrapper(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        start = time.perf_counter()
        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
            route = self._route_template(scope)
            status = status_holder["status"]
            try:
                self._metrics.increment(
                    "http_requests_total",
                    method=method,
                    route=route,
                    status=str(status),
                )
                self._metrics.observe(
                    "http_request_duration_ms", elapsed_ms, method=method, route=route
                )
            except Exception:
                pass

    @staticmethod
    def _route_template(scope) -> str:  # type: ignore[no-untyped-def]
        route = scope.get("route")
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
        # Unmatched (404) or pre-routing: use the raw path but keep it a constant
        # for anything under an id-bearing prefix would go here in future.
        request = Request(scope)
        return request.url.path
