"""Retrieval query, result, and assembled-context value objects.

These are the inputs and outputs of the RAG (Retrieval-Augmented Generation)
pipeline's *retrieval* half. A :class:`RetrievalQuery` says what to look for and
how; a :class:`RetrievalResult` returns the ranked evidence; an
:class:`AssembledContext` is that evidence packed into a token-budgeted block plus
the citations that make every future claim traceable.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.knowledge.chunks import ScoredChunk
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class RetrievalQuery(FrozenModel):
    """A request to retrieve the most relevant corpus chunks.

    Attributes:
        text: The natural-language query (a question, or a finding description).
        top_k: How many chunks to return after ranking.
        filter: Optional metadata pre-filter (e.g. restrict to one framework).
        min_score: Chunks below this final score are dropped; if nothing clears
            it, the result is empty and the caller must *abstain* (rule 3).
    """

    text: NonEmptyStr
    top_k: int = Field(default=5, ge=1, le=50)
    filter: MetadataFilter = Field(default_factory=MetadataFilter)
    min_score: float = Field(default=0.0, ge=0.0)


class RetrievalResult(FrozenModel):
    """The ranked evidence returned for a query.

    Attributes:
        query: The original query text (for tracing/eval).
        chunks: The ranked, filtered chunks (may be empty → abstain).
        embedding_model: The model used to embed the query, recorded so results
            are auditable and comparable.
    """

    query: NonEmptyStr
    chunks: list[ScoredChunk] = Field(default_factory=list)
    embedding_model: NonEmptyStr

    @property
    def is_empty(self) -> bool:
        """Whether retrieval found nothing above threshold (abstain signal)."""
        return len(self.chunks) == 0


class AssembledContext(FrozenModel):
    """Retrieved evidence packed for a prompt, with citations preserved.

    Attributes:
        text: The concatenated, token-budgeted context block. Each chunk is
            labelled with a citation marker so the model (and a human) can trace
            claims to sources.
        citations: The citations for the included chunks, in order.
        chunk_ids: The ids of the chunks that were included (for audit).
        token_estimate: Approximate token size of ``text`` (budget accounting).
    """

    text: str
    citations: list[Citation] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    token_estimate: int = Field(ge=0)

    @property
    def is_empty(self) -> bool:
        """Whether no context was assembled (nothing retrieved)."""
        return len(self.chunk_ids) == 0
