"""Core Service client adapters (Phase 6).

- :class:`StubCoreClient` — an in-process, seeded client (offline default), so
  the AI service develops and tests without a live Core.
- :class:`HttpCoreClient` — calls the real Core over REST, forwarding the
  caller's JWT.

:func:`build_core_client` selects between them from settings.
"""

from complianceiq.infrastructure.core.factory import build_core_client
from complianceiq.infrastructure.core.http_client import HttpCoreClient
from complianceiq.infrastructure.core.stub_client import StubCoreClient, sample_findings

__all__ = [
    "HttpCoreClient",
    "StubCoreClient",
    "build_core_client",
    "sample_findings",
]
