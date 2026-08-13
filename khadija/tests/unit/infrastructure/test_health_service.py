"""Tests for the readiness aggregation use case."""

from __future__ import annotations

import pytest

from complianceiq.application.services.health import ReadinessService
from complianceiq.domain.ports.health import HealthProbe, HealthResult


class _StubProbe(HealthProbe):
    def __init__(self, name: str, *, healthy: bool, raises: bool = False) -> None:
        self._name = name
        self._healthy = healthy
        self._raises = raises

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> HealthResult:
        if self._raises:
            raise RuntimeError("probe exploded")
        return HealthResult(name=self._name, healthy=self._healthy)


async def test_empty_probe_set_is_ready() -> None:
    report = await ReadinessService([]).check()
    assert report.ready is True
    assert report.components == []


async def test_all_healthy_is_ready() -> None:
    service = ReadinessService([_StubProbe("db", healthy=True), _StubProbe("cache", healthy=True)])
    report = await service.check()
    assert report.ready is True
    assert len(report.components) == 2


async def test_one_unhealthy_makes_not_ready() -> None:
    service = ReadinessService([_StubProbe("db", healthy=True), _StubProbe("cache", healthy=False)])
    report = await service.check()
    assert report.ready is False


async def test_raising_probe_is_reported_unhealthy_not_fatal() -> None:
    # A misbehaving probe must not abort the whole readiness check.
    service = ReadinessService(
        [_StubProbe("db", healthy=True), _StubProbe("bad", healthy=True, raises=True)]
    )
    report = await service.check()
    assert report.ready is False
    bad = next(c for c in report.components if c.name == "bad")
    assert bad.healthy is False


@pytest.mark.parametrize("healthy", [True, False])
async def test_single_probe_determines_readiness(healthy: bool) -> None:
    report = await ReadinessService([_StubProbe("only", healthy=healthy)]).check()
    assert report.ready is healthy
