"""Tests for HTTP middleware behaviour."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from complianceiq.infrastructure.http.middleware import (
    CorrelationIdMiddleware,
    RequestSizeLimitMiddleware,
)


def _app(max_bytes: int) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=max_bytes)
    app.add_middleware(CorrelationIdMiddleware)

    @app.post("/echo")
    async def _echo(payload: dict) -> dict:
        return payload

    return TestClient(app)


def test_oversized_request_is_rejected_with_413() -> None:
    client = _app(max_bytes=16)
    response = client.post("/echo", json={"data": "x" * 100})
    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "request_too_large"
    assert body["error"]["details"]["max_bytes"] == 16


def test_within_limit_request_passes() -> None:
    client = _app(max_bytes=10_000)
    response = client.post("/echo", json={"data": "ok"})
    assert response.status_code == 200
    assert response.json() == {"data": "ok"}
