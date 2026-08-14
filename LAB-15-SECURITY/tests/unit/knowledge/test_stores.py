"""Tests for the in-memory vector store and keyword index."""

from __future__ import annotations

import pytest

from complianceiq.domain.exceptions import EmbeddingModelMismatchError
from complianceiq.domain.knowledge.chunking import chunk_document
from complianceiq.domain.knowledge.chunks import EmbeddedChunk
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.infrastructure.knowledge.keyword_index_memory import InMemoryKeywordIndex
from complianceiq.infrastructure.knowledge.vector_store_memory import InMemoryVectorStore
from tests.fakes import StubEmbedder
from tests.unit.knowledge.conftest import sample_document


async def _embedded_chunks() -> list[EmbeddedChunk]:
    chunks = chunk_document(sample_document(), corpus_version="v1")
    embedder = StubEmbedder()
    results = await embedder.embed([c.content for c in chunks])
    return [
        EmbeddedChunk(
            chunk=c, vector=r.vector, embedding_model=r.model_id, embedding_provider=r.provider
        )
        for c, r in zip(chunks, results, strict=True)
    ]


# --- vector store ---


async def test_vector_store_upsert_and_count() -> None:
    store = InMemoryVectorStore()
    embedded = await _embedded_chunks()
    assert await store.upsert(embedded) == len(embedded)
    assert await store.count() == len(embedded)
    # idempotent: re-upsert same ids does not grow the store
    await store.upsert(embedded)
    assert await store.count() == len(embedded)


async def test_vector_store_ranks_by_similarity() -> None:
    store = InMemoryVectorStore()
    embedded = await _embedded_chunks()
    await store.upsert(embedded)
    query = (await StubEmbedder().embed(["encryption of storage buckets"]))[0]
    results = await store.search(
        embedding=query.vector,
        embedding_model=query.model_id,
        top_k=1,
        metadata_filter=MetadataFilter(),
    )
    assert results[0].chunk.metadata.control_id == "PR.DS-01"  # the encryption control


async def test_vector_store_metadata_filter() -> None:
    store = InMemoryVectorStore()
    await store.upsert(await _embedded_chunks())
    query = (await StubEmbedder().embed(["iam"]))[0]
    results = await store.search(
        embedding=query.vector,
        embedding_model=query.model_id,
        top_k=10,
        metadata_filter=MetadataFilter(control_id="PR.AA-01"),
    )
    assert results and all(r.chunk.metadata.control_id == "PR.AA-01" for r in results)


async def test_vector_store_rejects_model_mismatch() -> None:
    store = InMemoryVectorStore()
    await store.upsert(await _embedded_chunks())  # model "stub-embed"
    other = (await StubEmbedder(model_id="different-model").embed(["iam"]))[0]
    with pytest.raises(EmbeddingModelMismatchError):
        await store.search(
            embedding=other.vector,
            embedding_model=other.model_id,
            top_k=5,
            metadata_filter=MetadataFilter(),
        )


async def test_vector_store_delete_by_version() -> None:
    store = InMemoryVectorStore()
    await store.upsert(await _embedded_chunks())
    deleted = await store.delete_by_corpus_version("v1")
    assert deleted > 0
    assert await store.count() == 0


# --- keyword index ---


async def test_keyword_index_finds_by_term() -> None:
    index = InMemoryKeywordIndex()
    await index.index(chunk_document(sample_document(), corpus_version="v1"))
    results = await index.search(
        text="firewall network segmentation", top_k=1, metadata_filter=MetadataFilter()
    )
    assert results[0].chunk.metadata.control_id == "PR.IR-01"


async def test_keyword_index_filter_and_delete() -> None:
    index = InMemoryKeywordIndex()
    await index.index(chunk_document(sample_document(), corpus_version="v1"))
    filtered = await index.search(
        text="logging",
        top_k=5,
        metadata_filter=MetadataFilter(framework=Framework.NIST_CSF),
    )
    assert filtered
    assert await index.delete_by_corpus_version("v1") > 0
    assert await index.count() == 0
