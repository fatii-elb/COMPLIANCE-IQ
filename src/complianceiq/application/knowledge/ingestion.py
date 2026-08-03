"""Corpus ingestion — load regulations into the retrievable knowledge base.

The ingestion pipeline is the "write path" of RAG. It takes registered source
documents, chunks them structure-aware, embeds each chunk (via the gateway), and
writes them to both the vector store (for semantic search) and the keyword index
(for lexical search).

Two production properties:

- **Idempotent.** Chunk ids are derived from content, and the vector store upserts
  by id, so re-ingesting an unchanged corpus changes nothing (no duplicates).
- **Versioned.** Every chunk is stamped with a ``corpus_version``; ``replace``
  clears the old version first, enabling clean re-indexing without duplicating.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.domain._base import FrozenModel
from complianceiq.domain.knowledge.chunking import chunk_document
from complianceiq.domain.knowledge.chunks import Chunk, EmbeddedChunk
from complianceiq.domain.knowledge.documents import CorpusDocument
from complianceiq.domain.ports.knowledge import Embedder, KeywordIndex, VectorStore

_EMBED_BATCH = 64


class IngestionReport(FrozenModel):
    """Summary of an ingestion run.

    Attributes:
        documents: Number of source documents processed.
        chunks: Number of chunks produced.
        upserted: Number of chunks written to the vector store.
        corpus_version: The version tag written.
    """

    documents: int = Field(ge=0)
    chunks: int = Field(ge=0)
    upserted: int = Field(ge=0)
    corpus_version: str


class IngestionService:
    """Chunks, embeds, and stores corpus documents into the knowledge base."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        vector_store: VectorStore,
        keyword_index: KeywordIndex,
        config: RetrievalConfig,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._keyword_index = keyword_index
        self._config = config

    async def ingest(
        self,
        documents: Sequence[CorpusDocument],
        *,
        corpus_version: str | None = None,
        replace: bool = False,
    ) -> IngestionReport:
        """Ingest ``documents`` into the vector store and keyword index.

        Args:
            documents: Source documents to ingest.
            corpus_version: Version tag; defaults to the configured version.
            replace: If True, delete the existing version first (clean re-index).
        """
        version = corpus_version or self._config.corpus_version

        if replace:
            await self._vector_store.delete_by_corpus_version(version)
            await self._keyword_index.delete_by_corpus_version(version)

        chunks: list[Chunk] = []
        for document in documents:
            chunks.extend(
                chunk_document(
                    document,
                    corpus_version=version,
                    max_tokens=self._config.chunk_max_tokens,
                )
            )

        if not chunks:
            return IngestionReport(documents=0, chunks=0, upserted=0, corpus_version=version)

        embedded = await self._embed_chunks(chunks)
        upserted = await self._vector_store.upsert(embedded)
        await self._keyword_index.index(chunks)

        return IngestionReport(
            documents=len(documents),
            chunks=len(chunks),
            upserted=upserted,
            corpus_version=version,
        )

    async def _embed_chunks(self, chunks: Sequence[Chunk]) -> list[EmbeddedChunk]:
        """Embed chunk contents in batches and pair vectors with their chunks."""
        embedded: list[EmbeddedChunk] = []
        for start in range(0, len(chunks), _EMBED_BATCH):
            batch = chunks[start : start + _EMBED_BATCH]
            results = await self._embedder.embed([chunk.content for chunk in batch])
            for chunk, result in zip(batch, results, strict=True):
                embedded.append(
                    EmbeddedChunk(
                        chunk=chunk,
                        vector=result.vector,
                        embedding_model=result.model_id,
                        embedding_provider=result.provider,
                    )
                )
        return embedded
