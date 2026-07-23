"""FastAPI application factory.

Builds the ASGI app from an already-constructed container. The factory is
deliberately ignorant of *how* the container's services were built (which
database, which provider) — it only knows the :class:`Container` protocol. This
keeps presentation independent of infrastructure; the composition root supplies
the concrete container and attaches infrastructure middleware.
"""

from __future__ import annotations

from fastapi import FastAPI

from complianceiq import __version__
from complianceiq.presentation.container import Container
from complianceiq.presentation.errors import register_exception_handlers
from complianceiq.presentation.routers import health


def create_app(container: Container) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        container: The wired services satisfying the presentation
            :class:`Container` protocol. Stored on ``app.state`` for dependency
            resolution.

    Returns:
        A configured :class:`FastAPI` instance. Infrastructure middleware is
        attached separately by the composition root.
    """
    app = FastAPI(
        title="ComplianceIQ AI Service",
        version=__version__,
        description=(
            "Grounded, multi-tenant GRC intelligence over multi-cloud findings. "
            "Every AI claim is cited and verified; the service proposes "
            "remediations but never applies them."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.container = container

    register_exception_handlers(app)

    # Operational endpoints live at the root (unauthenticated, tenant-agnostic).
    app.include_router(health.router)

    return app
