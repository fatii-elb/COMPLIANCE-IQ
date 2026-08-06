"""A psycopg-backed :class:`SqlExecutor` for the pgvector store.

This is the only place the ``psycopg`` driver is used, and it is imported
**lazily** inside :func:`build_psycopg_executor` — so importing this module (and
the whole app) never requires the driver unless ``vector_store=pgvector`` is
actually selected. The executor adapts the store's positional ``$1, $2`` SQL to
psycopg's ``%s`` placeholders.

Wiring a real connection pool at startup/shutdown is a deployment concern; the
factory returns an executor bound to a psycopg ``AsyncConnectionPool`` the caller
owns. In the offline default (``vector_store=memory``) none of this runs.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

# Convert the store's $1,$2,... placeholders to psycopg's %s (in order).
_PLACEHOLDER = re.compile(r"\$\d+")


def _to_psycopg(sql: str) -> str:
    return _PLACEHOLDER.sub("%s", sql)


class PsycopgExecutor:
    """Adapts an async psycopg connection pool to the ``SqlExecutor`` seam."""

    def __init__(self, pool: Any) -> None:
        # ``pool`` is a psycopg_pool.AsyncConnectionPool; typed as Any to avoid a
        # hard import of the optional driver at module load.
        self._pool = pool

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(_to_psycopg(sql), tuple(params))
            return cur.rowcount if cur.rowcount is not None else 0

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(_to_psycopg(sql), tuple(params))
            rows = await cur.fetchall()
            return [tuple(row) for row in rows]

    async def fetch_val(self, sql: str, params: Sequence[Any] = ()) -> Any:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(_to_psycopg(sql), tuple(params))
            row = await cur.fetchone()
            return row[0] if row else None


def build_psycopg_executor(database_url: str) -> PsycopgExecutor:
    """Build a psycopg-backed executor (imports the optional driver lazily)."""
    try:
        from psycopg_pool import AsyncConnectionPool
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "vector_store=pgvector requires the 'psycopg[pool]' driver to be installed"
        ) from exc
    pool = AsyncConnectionPool(conninfo=database_url, open=False)  # pragma: no cover
    return PsycopgExecutor(pool)  # pragma: no cover
