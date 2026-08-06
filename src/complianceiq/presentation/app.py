"""FastAPI application factory.

Builds the ASGI app from an already-constructed container. The factory is
deliberately ignorant of *how* the container's services were built (which
database, which provider) — it only knows the :class:`Container` protocol. This
keeps presentation independent of infrastructure; the composition root supplies
the concrete container and attaches infrastructure middleware.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI

from complianceiq import __version__
from complianceiq.presentation.container import Container
from complianceiq.presentation.errors import register_exception_handlers
from complianceiq.presentation.routers import ai, health

#: A startup hook is a zero-arg coroutine run once when the app boots (e.g. to
#: seed the corpus). Built by the composition root; presentation just runs them.
StartupHook = Callable[[], Awaitable[None]]


def create_app(container: Container, *, on_startup: Sequence[StartupHook] | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        container: The wired services satisfying the presentation
            :class:`Container` protocol. Stored on ``app.state`` for dependency
            resolution.
        on_startup: Optional coroutines run once at boot (via the ASGI lifespan),
            e.g. corpus autoload. Presentation runs them without knowing what they
            do — the composition root supplies the behaviour.

    Returns:
        A configured :class:`FastAPI` instance. Infrastructure middleware is
        attached separately by the composition root.
    """
    hooks = list(on_startup or [])

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        for hook in hooks:
            await hook()
        yield

    app = FastAPI(
        lifespan=lifespan,
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
    # AI capabilities live under /api/v1/ai (JWT-protected, tenant-scoped).
    app.include_router(ai.router)

    return app
