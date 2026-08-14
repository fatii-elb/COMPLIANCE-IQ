"""Tests for the in-memory metrics sink and its Prometheus rendering."""

from __future__ import annotations

from complianceiq.domain.ports.metrics import NullMetrics
from complianceiq.infrastructure.observability.metrics_memory import InMemoryMetrics


def test_counter_accumulates() -> None:
    m = InMemoryMetrics()
    m.increment("http_requests_total", route="/health", status="200")
    m.increment("http_requests_total", route="/health", status="200")
    m.increment("http_requests_total", route="/health", status="500")
    snap = m.snapshot()
    counters = {(_c["labels"]["status"]): _c["value"] for _c in snap["counters"]}
    assert counters["200"] == 2
    assert counters["500"] == 1


def test_summary_tracks_count_sum_min_max() -> None:
    m = InMemoryMetrics()
    for v in (10.0, 20.0, 30.0):
        m.observe("latency_ms", v, route="/x")
    summary = m.snapshot()["summaries"][0]
    assert summary["count"] == 3
    assert summary["sum"] == 60.0
    assert summary["min"] == 10.0
    assert summary["max"] == 30.0
    assert summary["mean"] == 20.0


def test_render_prometheus_shapes_counter_and_summary() -> None:
    m = InMemoryMetrics()
    m.increment("http_requests_total", route="/health", status="200")
    m.observe("http_request_duration_ms", 5.0, route="/health")
    text = m.render_prometheus()
    assert 'http_requests_total{route="/health",status="200"} 1' in text
    assert 'http_request_duration_ms_count{route="/health"} 1' in text
    assert 'http_request_duration_ms_sum{route="/health"} 5' in text


def test_label_values_are_escaped() -> None:
    m = InMemoryMetrics()
    m.increment("c", route='a"b\\c')
    text = m.render_prometheus()
    assert 'route="a\\"b\\\\c"' in text


def test_null_metrics_is_a_noop() -> None:
    m = NullMetrics()
    m.increment("x")
    m.observe("y", 1.0)  # must not raise


def test_observability_service_combines_metrics_and_usage() -> None:
    from complianceiq.application.services.observability import ObservabilityService

    class _Usage:
        def totals(self) -> dict[str, object]:
            return {
                "calls": 3,
                "cache_hits": 1,
                "input_tokens": 100,
                "output_tokens": 40,
                "cost_usd": "0.00",
            }

    m = InMemoryMetrics()
    m.increment("http_requests_total", route="/health", status="200")
    svc = ObservabilityService(metrics=m, usage=_Usage())

    text = svc.prometheus()
    assert "http_requests_total" in text
    assert "ai_gateway_calls_total 3" in text

    snap = svc.snapshot()
    assert snap["ai_usage"] == {
        "calls": 3,
        "cache_hits": 1,
        "input_tokens": 100,
        "output_tokens": 40,
        "cost_usd": "0.00",
    }
    assert "counters" in snap
