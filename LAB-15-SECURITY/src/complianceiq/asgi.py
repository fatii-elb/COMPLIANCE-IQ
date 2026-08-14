"""ASGI application object for servers (Uvicorn/Gunicorn).

Exposes the module-level ``app`` that process managers import by string
(``complianceiq.asgi:app``). Building it here — rather than at import time in the
composition root — keeps a single, well-known ASGI entry point.
"""

from __future__ import annotations

from complianceiq.composition import build_app

app = build_app()
