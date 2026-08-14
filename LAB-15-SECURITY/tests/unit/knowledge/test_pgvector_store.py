"""Tests for the pgvector store's SQL construction and row mapping (offline).

There is no live Postgres here, so these drive :class:`PgVectorStore` through an
in-memory fake :class:`SqlExecutor`: they assert the adapter builds the right SQL
and parameters, maps rows back to domain objects, and enforces the embedding-model
guard. End-to-end similarity ranking is pgvector's job and is exercised in a real
deployment, not this suite.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from complianceiq.domain.exceptions import EmbeddingModelMismatchError
from complianceiq.domain.knowledge.chunks import Chunk, EmbeddedChunk
from complianceiq.domain.knowledge.metadata import (
    ChunkMetadata,
    Jurisdiction,
    Language,
    MetadataFilter,
)
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.infrastructure.knowledge.pgvector_store import (
    PgVectorStore,
    to_pgvector_literal,
)


class FakeExecutor:
    """Records SQL calls and returns programmed results."""

    def __init__(
        self,
        *,
        stored_model: str | None = None,
        rows: list[tuple[Any, ...]] | None = None,
        count_value: int = 0,
        delete_count: int = 0,
    ) -> None:
        self.calls: list[tuple[str, list[Any]]] = []
        self._stored_model = stored_model
        self._rows = rows or []
        self._count = count_value
        self._delete_count = delete_count

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        self.calls.append((sql, list(params)))
        return self._delete_count if sql.strip().startswith("DELETE") else 1

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        self.calls.append((sql, list(params)))
        return self._rows

    async def fetch_val(self, sql: str, params: Sequence[Any] = ()) -> Any:
        self.calls.append((sql, list(params)))
        if "COUNT(*)" in sql:
            return self._count
        if "embedding_model" in sql:
            return self._stored_model
        return None


def _embedded(chunk_id: str = "chunk-1", model: str = "stub-embed") -> EmbeddedChunk:
    metadata = ChunkMetadata(
        framework=Framework.NIST_CSF,
        control_id="PR.AA-01",
        title="Identity and credential management",
        version="2.0",
        language=Language.EN,
        jurisdiction=Jurisdiction.INTERNATIONAL,
        source="NIST CSF 2.0",
        corpus_version="v1",
    )
    chunk = Chunk(
        id=chunk_id, content="Manage IAM identities.", metadata=metadata, content_hash="h"
    )
    return EmbeddedChunk(
        chunk=chunk,
        vector=[0.1, 0.2, 0.3],
        embedding_model=model,
        embedding_provider=ProviderName.FAKE,
    )


def _search_row(score: float = 0.87) -> tuple[Any, ...]:
    return (
        "chunk-1",
        "Manage IAM identities.",
        "h",
        "nist_csf",
        "PR.AA-01",
        "Identity and credential management",
        "2.0",
        "en",
        "international",
        "NIST CSF 2.0",
        "v1",
        "stub-embed",
        "fake",
        score,
    )


def test_to_pgvector_literal() -> None:
    assert to_pgvector_literal([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"


async def test_upsert_issues_insert_on_conflict() -> None:
    executor = FakeExecutor()
    store = PgVectorStore(executor)
    n = await store.upsert([_embedded()])
    assert n == 1
    insert_calls = [c for c in executor.calls if c[0].startswith("INSERT")]
    assert len(insert_calls) == 1
    sql, params = insert_calls[0]
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert params[0] == "chunk-1"
    assert params[-1] == "[0.1,0.2,0.3]"  # vector literal is the last value


async def test_upsert_rejects_mixed_models() -> None:
    store = PgVectorStore(FakeExecutor())
    with pytest.raises(EmbeddingModelMismatchError):
        await store.upsert([_embedded(model="model-a"), _embedded(chunk_id="c2", model="model-b")])


async def test_upsert_rejects_model_differing_from_store() -> None:
    store = PgVectorStore(FakeExecutor(stored_model="model-a"))
    with pytest.raises(EmbeddingModelMismatchError):
        await store.upsert([_embedded(model="model-b")])


async def test_search_builds_ranked_sql_and_maps_rows() -> None:
    executor = FakeExecutor(stored_model="stub-embed", rows=[_search_row(0.9)])
    store = PgVectorStore(executor)
    results = await store.search(
        embedding=[0.1, 0.2, 0.3],
        embedding_model="stub-embed",
        top_k=5,
        metadata_filter=MetadataFilter(),
    )
    assert len(results) == 1
    assert results[0].chunk.id == "chunk-1"
    assert results[0].chunk.metadata.framework is Framework.NIST_CSF
    assert results[0].score == pytest.approx(0.9)
    search_sql = next(c for c in executor.calls if c[0].startswith("SELECT id"))[0]
    assert "ORDER BY embedding <=>" in search_sql
    assert "LIMIT" in search_sql


async def test_search_applies_metadata_filter() -> None:
    executor = FakeExecutor(stored_model="stub-embed", rows=[])
    store = PgVectorStore(executor)
    await store.search(
        embedding=[0.1, 0.2, 0.3],
        embedding_model="stub-embed",
        top_k=5,
        metadata_filter=MetadataFilter(framework=Framework.NIST_CSF),
    )
    sql, params = next(c for c in executor.calls if c[0].startswith("SELECT id"))
    assert "WHERE framework =" in sql
    assert "nist_csf" in params


async def test_search_builds_all_filter_conditions() -> None:
    executor = FakeExecutor(stored_model="stub-embed", rows=[])
    store = PgVectorStore(executor)
    await store.search(
        embedding=[0.1],
        embedding_model="stub-embed",
        top_k=3,
        metadata_filter=MetadataFilter(
            framework=Framework.NIST_CSF,
            control_id="PR.AA-01",
            language=Language.EN,
            jurisdiction=Jurisdiction.INTERNATIONAL,
            corpus_version="v1",
        ),
    )
    sql, params = next(c for c in executor.calls if c[0].startswith("SELECT id"))
    for column in ("framework", "control_id", "language", "jurisdiction", "corpus_version"):
        assert f"{column} =" in sql
    assert {"nist_csf", "PR.AA-01", "en", "international", "v1"} <= set(params)


async def test_search_rejects_model_mismatch() -> None:
    store = PgVectorStore(FakeExecutor(stored_model="model-a"))
    with pytest.raises(EmbeddingModelMismatchError):
        await store.search(
            embedding=[0.1],
            embedding_model="model-b",
            top_k=5,
            metadata_filter=MetadataFilter(),
        )


async def test_delete_and_count() -> None:
    executor = FakeExecutor(count_value=7, delete_count=3)
    store = PgVectorStore(executor)
    assert await store.delete_by_corpus_version("v1") == 3
    assert await store.count() == 7
