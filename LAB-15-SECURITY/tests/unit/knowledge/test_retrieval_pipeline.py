"""Tests for fusion, reranking, the hybrid retriever, and context assembly."""

from __future__ import annotations

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.fusion import mmr_select, reciprocal_rank_fusion
from complianceiq.domain.knowledge.chunks import (
    Chunk,
    RetrievalSource,
    ScoredChunk,
)
from complianceiq.domain.knowledge.metadata import ChunkMetadata, Jurisdiction, Language
from complianceiq.domain.knowledge.queries import RetrievalQuery
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.infrastructure.knowledge.reranker_lexical import LexicalReranker
from tests.unit.knowledge.conftest import build_ingested_retriever


def _chunk(cid: str, content: str) -> Chunk:
    meta = ChunkMetadata(
        framework=Framework.NIST_CSF,
        control_id=cid,
        title=cid,
        version="1",
        language=Language.EN,
        jurisdiction=Jurisdiction.INTERNATIONAL,
        source="test",
        corpus_version="v1",
    )
    return Chunk(id=cid, content=content, metadata=meta, content_hash=cid)


def _scored(cid: str, content: str, score: float, source: RetrievalSource) -> ScoredChunk:
    return ScoredChunk(chunk=_chunk(cid, content), score=score, retriever=source)


# --- fusion ---


def test_rrf_rewards_agreement() -> None:
    semantic = [
        _scored("a", "x", 0.9, RetrievalSource.SEMANTIC),
        _scored("b", "y", 0.8, RetrievalSource.SEMANTIC),
    ]
    lexical = [
        _scored("b", "y", 5.0, RetrievalSource.LEXICAL),
        _scored("c", "z", 1.0, RetrievalSource.LEXICAL),
    ]
    fused = reciprocal_rank_fusion([semantic, lexical])
    # 'b' appears in both lists → should rank first
    assert fused[0].chunk.id == "b"
    assert all(s.retriever is RetrievalSource.HYBRID for s in fused)


def test_mmr_prefers_diversity() -> None:
    candidates = [
        _scored("a", "encryption of storage buckets", 1.0, RetrievalSource.RERANK),
        _scored("b", "encryption of storage buckets", 0.99, RetrievalSource.RERANK),  # near-dup
        _scored("c", "network firewall segmentation", 0.9, RetrievalSource.RERANK),
    ]
    selected = mmr_select(candidates, lambda_param=0.5, top_k=2)
    ids = {s.chunk.id for s in selected}
    # should not pick both near-duplicates a & b; c adds diversity
    assert "c" in ids


# --- reranker ---


async def test_lexical_reranker_scores_by_coverage() -> None:
    reranker = LexicalReranker()
    candidates = [
        _scored("hit", "iam identity credential rotation", 0.1, RetrievalSource.HYBRID),
        _scored("miss", "banana bread recipe", 0.9, RetrievalSource.HYBRID),
    ]
    ranked = await reranker.rerank(query="iam credential rotation", candidates=candidates, top_k=2)
    assert ranked[0].chunk.id == "hit"
    assert ranked[0].retriever is RetrievalSource.RERANK


# --- retriever end-to-end ---


async def test_retriever_finds_relevant_control() -> None:
    retriever, _, _ = await build_ingested_retriever()
    result = await retriever.retrieve(
        RetrievalQuery(text="encrypt data stored in cloud storage buckets", top_k=2)
    )
    control_ids = [c.chunk.metadata.control_id for c in result.chunks]
    assert "PR.DS-01" in control_ids
    assert result.embedding_model == "stub-embed"


async def test_retriever_respects_metadata_filter() -> None:
    from complianceiq.domain.knowledge.metadata import MetadataFilter

    retriever, _, _ = await build_ingested_retriever()
    result = await retriever.retrieve(
        RetrievalQuery(text="iam access", top_k=5, filter=MetadataFilter(control_id="PR.AA-01"))
    )
    assert result.chunks
    assert all(c.chunk.metadata.control_id == "PR.AA-01" for c in result.chunks)


async def test_retriever_abstains_when_threshold_unmet() -> None:
    retriever, _, _ = await build_ingested_retriever()
    result = await retriever.retrieve(
        RetrievalQuery(text="completely unrelated quantum banana", top_k=3, min_score=0.99)
    )
    assert result.is_empty  # nothing clears the high threshold → abstain


# --- context assembly ---


async def test_context_assembly_builds_citations_and_dedupes() -> None:
    retriever, _, _ = await build_ingested_retriever()
    result = await retriever.retrieve(RetrievalQuery(text="iam credential rotation", top_k=3))
    ctx = ContextAssembler().assemble(result, token_budget=1000)
    assert ctx.text
    assert len(ctx.citations) == len(ctx.chunk_ids)
    assert ctx.token_estimate > 0
    # numbered markers present
    assert "[1]" in ctx.text


async def test_context_assembly_respects_budget() -> None:
    retriever, _, _ = await build_ingested_retriever()
    result = await retriever.retrieve(
        RetrievalQuery(text="iam encryption network logging", top_k=4)
    )
    ctx = ContextAssembler().assemble(result, token_budget=20)  # tiny budget
    # at least one chunk always included, but budget keeps it small
    assert 1 <= len(ctx.chunk_ids) <= 2


def test_retrieval_config_defaults() -> None:
    config = RetrievalConfig()
    assert config.mmr_lambda == 0.5
    assert config.rrf_k == 60
