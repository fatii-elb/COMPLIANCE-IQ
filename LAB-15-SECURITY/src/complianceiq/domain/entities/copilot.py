"""The :class:`CopilotAnswer` — a grounded answer to a natural-language question.

Produced by the copilot graph: a plain-language answer backed by verified
citations, or an explicit abstention when the sources don't cover the question.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class CopilotAnswer(FrozenModel):
    """A grounded answer with its citations and grounding status.

    Attributes:
        question: The question that was asked.
        answer: The generated answer (or the abstention text).
        citations: The verified citations backing the answer.
        citation_verified: Whether the answer is grounded in verified sources.
        abstained: True if the copilot declined for lack of relevant sources.
    """

    question: NonEmptyStr
    answer: NonEmptyStr
    citations: list[Citation] = Field(default_factory=list)
    citation_verified: bool
    abstained: bool
