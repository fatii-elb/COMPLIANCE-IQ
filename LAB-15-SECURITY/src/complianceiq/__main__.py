"""Executable entry point: ``python -m complianceiq``.

Boots the ASGI app under Uvicorn using environment-driven settings. Kept thin —
all wiring lives in the composition root. The Docker image invokes this module.
"""

from __future__ import annotations

import uvicorn

from complianceiq.infrastructure.config.settings import get_settings


def main() -> None:
    """Run the service under Uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "complianceiq.asgi:app",
        host=settings.host,
        port=settings.port,
        log_config=None,  # we own logging via structlog
        access_log=False,  # access logging is handled by CorrelationIdMiddleware
    )


if __name__ == "__main__":
    main()
