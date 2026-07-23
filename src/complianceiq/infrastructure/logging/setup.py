"""structlog configuration.

Produces structured logs that are machine-parseable in production (JSON, for log
aggregation and the audit trail) and human-readable in local development
(coloured console). Correlation IDs and tenant bindings from
:mod:`complianceiq.infrastructure.logging.context` are merged into every event
automatically.

Call :func:`configure_logging` exactly once, at startup (the composition root
does this). It is idempotent, so repeated calls in tests are harmless.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog and the stdlib logging bridge.

    Args:
        level: Minimum level to emit (e.g. ``"INFO"``).
        json_output: When True, render JSON (production/audit). When False,
            render a coloured console format for local development.
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):  # unknown level name → default
        numeric_level = logging.INFO

    # Route stdlib logging (uvicorn, libraries) through the same handler so all
    # logs share one format and destination.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # correlation_id, tenant_id, …
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, optionally named after a module."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
