"""Knowledge-base domain model — the regulatory corpus and retrieval vocabulary.

Models the shared library of compliance knowledge (Framework → Control → Chunk),
the embedded chunks retrieval ranks, and the queries/results/context of the RAG
pipeline. The corpus is shared across tenants (public regulations and our own
control summaries), so chunks are not tenant-scoped; tenant isolation applies to
findings and generated artefacts, not the regulatory library.
"""

from complianceiq.domain.knowledge.chunking import chunk_document, estimate_tokens
from complianceiq.domain.knowledge.chunks import (
    Chunk,
    EmbeddedChunk,
    RetrievalSource,
    ScoredChunk,
)
from complianceiq.domain.knowledge.documents import ControlSummary, CorpusDocument
from complianceiq.domain.knowledge.metadata import (
    ChunkMetadata,
    Jurisdiction,
    Language,
    MetadataFilter,
)
from complianceiq.domain.knowledge.queries import (
    AssembledContext,
    RetrievalQuery,
    RetrievalResult,
)

__all__ = [
    "AssembledContext",
    "Chunk",
    "ChunkMetadata",
    "ControlSummary",
    "CorpusDocument",
    "EmbeddedChunk",
    "Jurisdiction",
    "Language",
    "MetadataFilter",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalSource",
    "ScoredChunk",
    "chunk_document",
    "estimate_tokens",
]
