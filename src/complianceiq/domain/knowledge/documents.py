"""Source-document domain model: Framework → Control → (later) Chunk.

A :class:`CorpusDocument` is a registered regulatory source (e.g. "NIST CSF 2.0"
or "Loi 05-20"), composed of :class:`ControlSummary` records. This is the shape
loaders produce and the ingestion pipeline consumes.

**Copyright policy (non-negotiable rule 6), enforced by shape.** For copyrighted
standards (ISO/IEC), a control record holds only the *identifier*, our *own
summary*, and *references* — never the verbatim normative text. Public sources
(Loi 05-20, DNSSI, NIST) may quote more freely. The model does not carry a
"verbatim_text" field at all, so the forbidden data simply has nowhere to live.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.knowledge.metadata import Jurisdiction, Language
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.domain.value_objects.identifiers import ControlId, NonEmptyStr


class ControlSummary(FrozenModel):
    """One control/article, described in our own words (copyright-safe).

    Attributes:
        control_id: The identifier within the framework (e.g. ``"PR.AC-1"``).
        title: Short human-readable title.
        summary: Our original plain-language summary of the control's intent.
            For copyrighted standards this is authored by us, never copied.
        keywords: Extra searchable terms to help lexical retrieval.
        references: Pointers a licensed reader can consult (section, article).
    """

    control_id: ControlId
    title: NonEmptyStr
    summary: NonEmptyStr
    keywords: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class CorpusDocument(FrozenModel):
    """A registered regulatory source composed of control summaries.

    Attributes:
        framework: Which framework this document represents.
        title: Human-readable source title (used in citations).
        version: The source's own version/year.
        language: Natural language of the content.
        jurisdiction: Authority scope.
        controls: The control summaries that make up the document.
    """

    framework: Framework
    title: NonEmptyStr
    version: NonEmptyStr
    language: Language
    jurisdiction: Jurisdiction
    controls: list[ControlSummary] = Field(min_length=1)
