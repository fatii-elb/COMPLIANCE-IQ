"""In-memory keyword index with BM25 scoring (the lexical half of hybrid search).

Implements the :class:`KeywordIndex` port. **BM25** is the classic, battle-tested
ranking function for keyword search: it rewards a chunk for containing the query's
terms, dampens the reward for very frequent terms (a word appearing 10 times isn't
10× as relevant), boosts rare/distinctive terms (**IDF** — inverse document
frequency), and normalises for chunk length so long chunks don't win just by being
long.

Semantic search alone can miss exact identifiers ("PR.AC-4", "article 23"); BM25
catches those, which is exactly why we fuse the two.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from complianceiq.domain.knowledge.chunks import Chunk, RetrievalSource, ScoredChunk
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.knowledge.similarity import tokenize
from complianceiq.domain.ports.knowledge import KeywordIndex

_BM25_K1 = 1.5  # term-frequency saturation
_BM25_B = 0.75  # length-normalisation strength


class _Doc:
    __slots__ = ("chunk", "freqs", "length")

    def __init__(self, chunk: Chunk, freqs: Counter[str], length: int) -> None:
        self.chunk = chunk
        self.freqs = freqs
        self.length = length


class InMemoryKeywordIndex(KeywordIndex):
    """A dict-backed BM25 lexical index."""

    def __init__(self) -> None:
        self._docs: dict[str, _Doc] = {}

    async def index(self, chunks: Sequence[Chunk]) -> int:
        for chunk in chunks:
            tokens = tokenize(chunk.content)
            self._docs[chunk.id] = _Doc(chunk, Counter(tokens), len(tokens))
        return len(chunks)

    async def search(
        self, *, text: str, top_k: int, metadata_filter: MetadataFilter
    ) -> list[ScoredChunk]:
        candidates = [
            doc for doc in self._docs.values() if metadata_filter.matches(doc.chunk.metadata)
        ]
        if not candidates:
            return []

        query_terms = tokenize(text)
        n = len(candidates)
        avg_len = sum(doc.length for doc in candidates) / n

        # Document frequency of each query term within the candidate set.
        doc_freq: dict[str, int] = {}
        for term in set(query_terms):
            doc_freq[term] = sum(1 for doc in candidates if term in doc.freqs)

        scored: list[ScoredChunk] = []
        for doc in candidates:
            score = 0.0
            for term in query_terms:
                freq = doc.freqs.get(term, 0)
                if freq == 0:
                    continue
                idf = math.log(1 + (n - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                denom = freq + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc.length / avg_len)
                score += idf * (freq * (_BM25_K1 + 1)) / denom
            if score > 0.0:
                scored.append(
                    ScoredChunk(chunk=doc.chunk, score=score, retriever=RetrievalSource.LEXICAL)
                )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    async def delete_by_corpus_version(self, corpus_version: str) -> int:
        to_delete = [
            cid
            for cid, doc in self._docs.items()
            if doc.chunk.metadata.corpus_version == corpus_version
        ]
        for cid in to_delete:
            del self._docs[cid]
        return len(to_delete)

    async def count(self) -> int:
        return len(self._docs)
