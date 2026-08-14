"""Tests for the /metrics endpoint and the metrics middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.auth_helpers import bearer, mint_token


def test_metrics_endpoint_is_prometheus_text(client: TestClient) -> None:
    client.get("/health")
    client.get("/version")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert 'http_requests_total{method="GET",route="/health",status="200"}' in body
    assert "http_request_duration_ms_count" in body


def test_metrics_include_ai_usage_gauges_after_a_call(client: TestClient) -> None:
    client.post(
        "/api/v1/ai/ask",
        json={"question": "How should IAM access keys be managed?"},
        headers=bearer(mint_token()),
    )
    body = client.get("/metrics").text
    assert "ai_gateway_calls_total" in body
    assert "ai_gateway_input_tokens_total" in body
    assert "ai_gateway_cost_usd_total" in body
    # The AI request should have driven at least one gateway call.
    calls_line = next(
        line for line in body.splitlines() if line.startswith("ai_gateway_calls_total")
    )
    assert int(calls_line.split()[-1]) >= 1


def test_metrics_endpoint_is_unauthenticated(client: TestClient) -> None:
    # Operational endpoint: no bearer token required (like /health).
    assert client.get("/metrics").status_code == 200
