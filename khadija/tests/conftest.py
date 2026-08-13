"""Shared pytest fixtures and test doubles.

The default suite is deterministic and offline: no network, no live provider, no
real database. Fixtures here build the app from explicit test settings so tests
never depend on a developer's local ``.env``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from complianceiq.composition import build_app
from complianceiq.domain.ports.clock import Clock
from complianceiq.infrastructure.config.settings import Environment, Settings


class FrozenClock(Clock):
    """A deterministic :class:`Clock` returning a fixed instant.

    Injected wherever time must be reproducible in assertions.
    """

    def __init__(self, instant: datetime | None = None) -> None:
        self._instant = instant or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._instant


@pytest.fixture
def settings() -> Settings:
    """Deterministic settings for tests (local env, human-readable logs)."""
    return Settings(
        environment=Environment.LOCAL,
        log_json=False,
        log_level="WARNING",  # keep test output quiet
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """The FastAPI app wired from test settings."""
    return build_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A synchronous TestClient over the app."""
    with TestClient(app) as test_client:
        yield test_client
