"""Metadata that travels with every knowledge-base chunk.

Rich, structured metadata is what makes retrieval *precise*. When we enrich a
finding that already declares an ISO control, we don't want to semantically search
the entire corpus — we want to pre-filter to that control's framework first, then
rank. The :class:`ChunkMetadata` carries the fields those filters need, and
:class:`MetadataFilter` expresses a query's constraints.

The corpus is **shared knowledge** (public regulations and our own control
summaries), not tenant data, so chunks are *not* tenant-scoped. Tenant isolation
applies to findings and generated artefacts, not to the regulatory library every
tenant reads.
"""

from __future__ import annotations

from enum import StrEnum

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.domain.value_objects.identifiers import ControlId, NonEmptyStr


class Language(StrEnum):
    """Natural language of a source, so retrieval can prefer the right one.

    Morocco's regulatory context spans Arabic, French, and English; recording the
    language lets later phases answer in, or filter to, the appropriate one.
    """

    EN = "en"
    FR = "fr"
    AR = "ar"


class Jurisdiction(StrEnum):
    """The legal/authority scope a source belongs to."""

    INTERNATIONAL = "international"  # ISO, NIST, SOC 2, CIS, OWASP
    MOROCCO = "morocco"  # Loi 05-20, DNSSI


class ChunkMetadata(FrozenModel):
    """Structured provenance and filtering attributes for a chunk.

    Attributes:
        framework: The framework the chunk belongs to.
        control_id: The control/article the chunk documents.
        title: Human-readable control title.
        version: The source document's own version (e.g. ``"2022"``).
        language: The natural language of the content.
        jurisdiction: The authority scope.
        source: A short source label (e.g. ``"NIST CSF 2.0"``) for citations.
        corpus_version: The ingestion/corpus version tag, used to re-index and
            deprecate old content without downtime.
    """

    framework: Framework
    control_id: ControlId
    title: NonEmptyStr
    version: NonEmptyStr
    language: Language
    jurisdiction: Jurisdiction
    source: NonEmptyStr
    corpus_version: NonEmptyStr


class MetadataFilter(FrozenModel):
    """A set of optional constraints applied *before* ranking.

    Every field is optional; an unset field imposes no constraint. Pushing these
    filters into the store (SQL ``WHERE`` in the pgvector adapter; a predicate in
    the in-memory one) means we never rank irrelevant chunks in the first place.
    """

    framework: Framework | None = None
    control_id: ControlId | None = None
    language: Language | None = None
    jurisdiction: Jurisdiction | None = None
    corpus_version: NonEmptyStr | None = None

    def matches(self, metadata: ChunkMetadata) -> bool:
        """Return whether ``metadata`` satisfies every set constraint."""
        if self.framework is not None and metadata.framework is not self.framework:
            return False
        if self.control_id is not None and metadata.control_id != self.control_id:
            return False
        if self.language is not None and metadata.language is not self.language:
            return False
        if self.jurisdiction is not None and metadata.jurisdiction is not self.jurisdiction:
            return False
        return self.corpus_version is None or metadata.corpus_version == self.corpus_version
