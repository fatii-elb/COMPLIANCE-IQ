"""Select and build the Core client from settings.

``stub`` (the offline default) returns the seeded in-process client; ``http``
returns the REST adapter pointed at ``core_api_base_url``. Both satisfy the
:class:`CoreClient` port, so the composition root and application never learn
which one they got.
"""

from __future__ import annotations

from complianceiq.domain.ports.core import CoreClient
from complianceiq.infrastructure.config.settings import Settings
from complianceiq.infrastructure.core.http_client import HttpCoreClient
from complianceiq.infrastructure.core.stub_client import StubCoreClient


def build_core_client(settings: Settings) -> CoreClient:
    """Return the configured Core client (``stub`` or ``http``)."""
    if settings.core_client == "http":
        return HttpCoreClient(
            base_url=settings.core_api_base_url,
            timeout=settings.core_request_timeout_seconds,
        )
    return StubCoreClient()
