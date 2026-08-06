"""PostgreSQL + pgvector vector store (production backend, Phase 6).

Implements the :class:`VectorStore` port with SQL, fulfilling the promise of
ADR-0005: the in-memory store (offline default) and this one share the exact port,
so switching is a composition change, not a code change.

To keep this adapter importable and unit-testable **without** a database driver or
a live Postgres, all SQL goes through a tiny :class:`SqlExecutor` seam. The real
psycopg-backed executor is built lazily only when ``vector_store=pgvector`` is
configured (see :mod:`psycopg_executor`); tests drive the adapter with an
in-memory fake. Similarity ranking itself is delegated to pgvector's ``<=>``
distance operator in the DB.

The **embedding-model-identity guard** (ADR-0005) is enforced here too: all stored
chunks must share one embedding model, and a query embedded with a different model
is rejected rather than silently compared.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from complianceiq.domain.exceptions import EmbeddingModelMismatchError
from complianceiq.domain.knowledge.chunks import (
    Chunk,
    EmbeddedChunk,
    RetrievalSource,
    ScoredChunk,
)
from complianceiq.domain.knowledge.metadata import (
    ChunkMetadata,
    Jurisdiction,
    Language,
    MetadataFilter,
)
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.ports.knowledge import VectorStore
from complianceiq.domain.value_objects.enums import Framework

_TABLE = "knowledge_chunks"


class SqlExecutor(Protocol):
    """The minimal async database surface the pgvector store needs.

    A real implementation wraps a psycopg async connection/pool; the tests supply
    an in-memory fake. Params are positional; the executor adapts them to the
    driver's placeholder style.
    """

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a statement, returning the affected row count."""
        ...

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        """Run a query, returning all rows as tuples."""
        ...

    async def fetch_val(self, sql: str, params: Sequence[Any] = ()) -> Any:
        """Run a query, returning the first column of the first row (or ``None``)."""
        ...


def to_pgvector_literal(vector: Sequence[float]) -> str:
    """Render a vector as a pgvector text literal, e.g. ``[0.1,0.2,0.3]``."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _build_filter(metadata_filter: MetadataFilter, params: list[Any]) -> str:
    """Append WHERE conditions for a metadata filter; return the SQL fragment."""
    conditions: list[str] = []
    if metadata_filter.framework is not None:
        conditions.append(f"framework = ${len(params) + 1}")
        params.append(metadata_filter.framework.value)
    if metadata_filter.control_id is not None:
        conditions.append(f"control_id = ${len(params) + 1}")
        params.append(metadata_filter.control_id)
    if metadata_filter.language is not None:
        conditions.append(f"language = ${len(params) + 1}")
        params.append(metadata_filter.language.value)
    if metadata_filter.jurisdiction is not None:
        conditions.append(f"jurisdiction = ${len(params) + 1}")
        params.append(metadata_filter.jurisdiction.value)
    if metadata_filter.corpus_version is not None:
        conditions.append(f"corpus_version = ${len(params) + 1}")
        params.append(metadata_filter.corpus_version)
    return (" WHERE " + " AND ".join(conditions)) if conditions else ""


#: Column order shared by upsert and the search SELECT (excluding the score).
_COLUMNS = (
    "id",
    "content",
    "content_hash",
    "framework",
    "control_id",
    "title",
    "version",
    "language",
    "jurisdiction",
    "source",
    "corpus_version",
    "embedding_model",
    "embedding_provider",
)


def _row_to_scored_chunk(row: tuple[Any, ...]) -> ScoredChunk:
    """Map a search row (``_COLUMNS`` fields + trailing score) to a ScoredChunk."""
    (
        chunk_id,
        content,
        content_hash,
        framework,
        control_id,
        title,
        version,
        language,
        jurisdiction,
        source,
        corpus_version,
        _embedding_model,
        _embedding_provider,
        score,
    ) = row
    metadata = ChunkMetadata(
        framework=Framework(framework),
        control_id=control_id,
        title=title,
        version=version,
        language=Language(language),
        jurisdiction=Jurisdiction(jurisdiction),
        source=source,
        corpus_version=corpus_version,
    )
    chunk = Chunk(id=chunk_id, content=content, metadata=metadata, content_hash=content_hash)
    return ScoredChunk(chunk=chunk, score=float(score), retriever=RetrievalSource.SEMANTIC)


class PgVectorStore(VectorStore):
    """A PostgreSQL + pgvector implementation of the VectorStore port."""

    def __init__(self, executor: SqlExecutor) -> None:
        self._sql = executor

    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> int:
        await self._guard_upsert_models(chunks)
        columns = ", ".join([*_COLUMNS, "embedding"])
        updates = ", ".join(f"{col} = EXCLUDED.{col}" for col in (*_COLUMNS[1:], "embedding"))
        for embedded in chunks:
            values = self._chunk_values(embedded)
            placeholders = ", ".join(f"${i + 1}" for i in range(len(values)))
            await self._sql.execute(
                f"INSERT INTO {_TABLE} ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT (id) DO UPDATE SET {updates}",
                values,
            )
        return len(chunks)

    async def search(
        self,
        *,
        embedding: Sequence[float],
        embedding_model: str,
        top_k: int,
        metadata_filter: MetadataFilter,
    ) -> list[ScoredChunk]:
        await self._guard_query_model(embedding_model)
        params: list[Any] = [to_pgvector_literal(embedding)]
        where = _build_filter(metadata_filter, params)
        params.append(top_k)
        select_cols = ", ".join(_COLUMNS)
        sql = (
            f"SELECT {select_cols}, 1 - (embedding <=> $1::vector) AS score "
            f"FROM {_TABLE}{where} "
            f"ORDER BY embedding <=> $1::vector ASC LIMIT ${len(params)}"
        )
        rows = await self._sql.fetch_all(sql, params)
        return [_row_to_scored_chunk(row) for row in rows]

    async def delete_by_corpus_version(self, corpus_version: str) -> int:
        return await self._sql.execute(
            f"DELETE FROM {_TABLE} WHERE corpus_version = $1", [corpus_version]
        )

    async def count(self) -> int:
        value = await self._sql.fetch_val(f"SELECT COUNT(*) FROM {_TABLE}")
        return int(value or 0)

    # ------------------------------------------------------------ model guard

    async def _stored_model(self) -> str | None:
        return await self._sql.fetch_val(f"SELECT embedding_model FROM {_TABLE} LIMIT 1")

    async def _guard_upsert_models(self, chunks: Sequence[EmbeddedChunk]) -> None:
        models = {c.embedding_model for c in chunks}
        if len(models) > 1:
            raise EmbeddingModelMismatchError(
                "cannot upsert chunks from multiple embedding models",
                details={"models": sorted(models)},
            )
        stored = await self._stored_model()
        if stored is not None and models and stored not in models:
            raise EmbeddingModelMismatchError(
                "cannot mix embedding models in one store",
                details={"store_model": stored, "chunk_model": next(iter(models))},
            )

    async def _guard_query_model(self, embedding_model: str) -> None:
        stored = await self._stored_model()
        if stored is not None and stored != embedding_model:
            raise EmbeddingModelMismatchError(
                "query embedding model does not match the stored corpus",
                details={"store_model": stored, "query_model": embedding_model},
            )

    @staticmethod
    def _chunk_values(embedded: EmbeddedChunk) -> list[Any]:
        chunk = embedded.chunk
        meta = chunk.metadata
        provider = (
            embedded.embedding_provider.value
            if isinstance(embedded.embedding_provider, ProviderName)
            else str(embedded.embedding_provider)
        )
        return [
            chunk.id,
            chunk.content,
            chunk.content_hash,
            meta.framework.value,
            meta.control_id,
            meta.title,
            meta.version,
            meta.language.value,
            meta.jurisdiction.value,
            meta.source,
            meta.corpus_version,
            embedded.embedding_model,
            provider,
            to_pgvector_literal(embedded.vector),
        ]
