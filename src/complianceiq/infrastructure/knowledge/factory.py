"""Assemble the knowledge/RAG stack from settings and the AI gateway.

Centralises construction of the retrieval subsystem so the composition root stays
lean. Today it wires the in-memory vector store and keyword index (offline
default); the pgvector-backed store (ADR-0005, Phase 6) implements the same ports
and slots in here without touching the retriever or ingestion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from complianceiq.application.gateway.ai_gateway import AIGateway
from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.embedder import GatewayEmbedder
from complianceiq.application.knowledge.ingestion import IngestionService
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.domain.ports.knowledge import Embedder, KeywordIndex, VectorStore
from complianceiq.infrastructure.config.settings import Settings
from complianceiq.infrastructure.knowledge.keyword_index_memory import InMemoryKeywordIndex
from complianceiq.infrastructure.knowledge.reranker_lexical import LexicalReranker
from complianceiq.infrastructure.knowledge.vector_store_memory import InMemoryVectorStore


def _build_vector_store(settings: Settings) -> VectorStore:
    """Select the vector store backend (``memory`` default, or ``pgvector``)."""
    if settings.vector_store == "pgvector":
        # Imported here so the psycopg driver is only required when selected.
        from complianceiq.infrastructure.knowledge.pgvector_store import PgVectorStore
        from complianceiq.infrastructure.knowledge.psycopg_executor import (
            build_psycopg_executor,
        )

        executor = build_psycopg_executor(settings.database_url.get_secret_value())
        return PgVectorStore(executor)
    return InMemoryVectorStore()


@dataclass(frozen=True, slots=True)
class KnowledgeStack:
    """The wired retrieval subsystem."""

    config: RetrievalConfig
    vector_store: VectorStore
    keyword_index: KeywordIndex
    embedder: Embedder
    retriever: HybridRetriever
    ingestion: IngestionService
    assembler: ContextAssembler
    corpus_dir: Path


def build_knowledge_stack(settings: Settings, gateway: AIGateway) -> KnowledgeStack:
    """Construct the knowledge stack (stores, retriever, ingestion, assembler)."""
    config = RetrievalConfig(
        candidate_multiplier=settings.retrieval_candidate_multiplier,
        rerank_top_k=settings.retrieval_rerank_top_k,
        rrf_k=settings.retrieval_rrf_k,
        mmr_lambda=settings.retrieval_mmr_lambda,
        context_token_budget=settings.retrieval_context_token_budget,
        chunk_max_tokens=settings.retrieval_chunk_max_tokens,
        corpus_version=settings.knowledge_corpus_version,
    )

    vector_store: VectorStore = _build_vector_store(settings)
    keyword_index: KeywordIndex = InMemoryKeywordIndex()
    reranker = LexicalReranker()
    embedder: Embedder = GatewayEmbedder(gateway, feature="knowledge")

    retriever = HybridRetriever(
        embedder=embedder,
        vector_store=vector_store,
        keyword_index=keyword_index,
        reranker=reranker,
        config=config,
    )
    ingestion = IngestionService(
        embedder=embedder,
        vector_store=vector_store,
        keyword_index=keyword_index,
        config=config,
    )

    return KnowledgeStack(
        config=config,
        vector_store=vector_store,
        keyword_index=keyword_index,
        embedder=embedder,
        retriever=retriever,
        ingestion=ingestion,
        assembler=ContextAssembler(),
        corpus_dir=Path(settings.knowledge_corpus_dir),
    )
