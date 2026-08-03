"""Shared builders for knowledge/RAG tests."""

from __future__ import annotations

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.ingestion import IngestionService
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.domain.knowledge.documents import ControlSummary, CorpusDocument
from complianceiq.domain.knowledge.metadata import Jurisdiction, Language
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.infrastructure.knowledge.keyword_index_memory import InMemoryKeywordIndex
from complianceiq.infrastructure.knowledge.reranker_lexical import LexicalReranker
from complianceiq.infrastructure.knowledge.vector_store_memory import InMemoryVectorStore
from tests.fakes import StubEmbedder


def sample_document() -> CorpusDocument:
    """A small, deterministic corpus document covering distinct domains."""
    return CorpusDocument(
        framework=Framework.NIST_CSF,
        title="NIST CSF (test)",
        version="2.0",
        language=Language.EN,
        jurisdiction=Jurisdiction.INTERNATIONAL,
        controls=[
            ControlSummary(
                control_id="PR.AA-01",
                title="Identity and credential management",
                summary="Manage IAM identities, credentials, and access key rotation with least privilege.",
                keywords=["iam", "identity", "credential", "access key", "rotation"],
            ),
            ControlSummary(
                control_id="PR.DS-01",
                title="Data-at-rest protection",
                summary="Encrypt stored data in cloud storage buckets and disks using managed keys.",
                keywords=["encryption", "data", "storage", "bucket"],
            ),
            ControlSummary(
                control_id="PR.IR-01",
                title="Network segmentation",
                summary="Restrict inbound network access with firewalls and security groups; avoid public exposure.",
                keywords=["network", "firewall", "segmentation", "public"],
            ),
            ControlSummary(
                control_id="DE.CM-01",
                title="Monitoring and logging",
                summary="Enable audit logging and monitoring to detect anomalous access and changes.",
                keywords=["logging", "audit", "monitoring", "detection"],
            ),
        ],
    )


async def build_ingested_retriever(
    *, config: RetrievalConfig | None = None
) -> tuple[HybridRetriever, InMemoryVectorStore, InMemoryKeywordIndex]:
    """Build a retriever with the sample document already ingested (stub embedder)."""
    config = config or RetrievalConfig()
    embedder = StubEmbedder()
    vector_store = InMemoryVectorStore()
    keyword_index = InMemoryKeywordIndex()
    ingestion = IngestionService(
        embedder=embedder,
        vector_store=vector_store,
        keyword_index=keyword_index,
        config=config,
    )
    await ingestion.ingest([sample_document()])
    retriever = HybridRetriever(
        embedder=embedder,
        vector_store=vector_store,
        keyword_index=keyword_index,
        reranker=LexicalReranker(),
        config=config,
    )
    return retriever, vector_store, keyword_index
