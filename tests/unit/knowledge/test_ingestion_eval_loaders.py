"""Tests for ingestion, retrieval evaluation, loaders, and the health probe."""

from __future__ import annotations

from pathlib import Path

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.evaluation import (
    RetrievalEvalCase,
    evaluate_retrieval,
)
from complianceiq.application.knowledge.ingestion import IngestionService
from complianceiq.domain.knowledge.chunking import chunk_document
from complianceiq.infrastructure.knowledge.health import VectorStoreHealthProbe
from complianceiq.infrastructure.knowledge.keyword_index_memory import InMemoryKeywordIndex
from complianceiq.infrastructure.knowledge.loaders import load_corpus
from complianceiq.infrastructure.knowledge.vector_store_memory import InMemoryVectorStore
from tests.fakes import StubEmbedder
from tests.unit.knowledge.conftest import build_ingested_retriever, sample_document

# --- ingestion ---


async def test_ingestion_is_idempotent() -> None:
    embedder = StubEmbedder()
    store = InMemoryVectorStore()
    index = InMemoryKeywordIndex()
    service = IngestionService(
        embedder=embedder, vector_store=store, keyword_index=index, config=RetrievalConfig()
    )
    report_1 = await service.ingest([sample_document()])
    count_1 = await store.count()
    report_2 = await service.ingest([sample_document()])
    assert report_1.chunks == report_2.chunks
    assert await store.count() == count_1  # no duplicates on re-ingest


async def test_ingestion_replace_clears_old_version() -> None:
    embedder = StubEmbedder()
    store = InMemoryVectorStore()
    index = InMemoryKeywordIndex()
    service = IngestionService(
        embedder=embedder, vector_store=store, keyword_index=index, config=RetrievalConfig()
    )
    await service.ingest([sample_document()], corpus_version="v1")
    await service.ingest([sample_document()], corpus_version="v1", replace=True)
    # replace deletes v1 then re-adds it → still the same count, not doubled
    expected = len(chunk_document(sample_document(), corpus_version="v1"))
    assert await store.count() == expected


# --- retrieval evaluation ---


async def test_evaluate_retrieval_reports_metrics() -> None:
    retriever, _, _ = await build_ingested_retriever()
    cases = [
        RetrievalEvalCase(
            query="iam credential access key rotation", expected_control_ids=["PR.AA-01"]
        ),
        RetrievalEvalCase(query="encrypt data storage bucket", expected_control_ids=["PR.DS-01"]),
        RetrievalEvalCase(
            query="network firewall segmentation public", expected_control_ids=["PR.IR-01"]
        ),
        RetrievalEvalCase(
            query="audit logging monitoring detection", expected_control_ids=["DE.CM-01"]
        ),
    ]
    metrics = await evaluate_retrieval(retriever, cases, k=3)
    assert metrics.cases == 4
    # with strong lexical signal, every query should hit its target
    assert metrics.hit_rate == 1.0
    assert metrics.recall_at_k == 1.0
    assert 0.0 < metrics.mrr <= 1.0


async def test_evaluate_empty_cases() -> None:
    retriever, _, _ = await build_ingested_retriever()
    metrics = await evaluate_retrieval(retriever, [], k=5)
    assert metrics.cases == 0


# --- loaders & health ---


def test_load_bundled_corpus() -> None:
    docs = load_corpus(Path("corpus/frameworks"))
    assert len(docs) >= 4
    frameworks = {d.framework for d in docs}
    assert len(frameworks) >= 4  # multiple frameworks present
    assert all(d.controls for d in docs)


def test_load_missing_directory_returns_empty() -> None:
    assert load_corpus(Path("corpus/does-not-exist")) == []


async def test_vector_store_health_probe() -> None:
    store = InMemoryVectorStore()
    probe = VectorStoreHealthProbe(store)
    result = await probe.check()
    assert result.name == "knowledge:vector_store"
    assert result.healthy is True
    assert "0 chunks" in result.detail
