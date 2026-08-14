"""The :class:`ControlMapping` contract — cross-framework control equivalence.

A single finding is raised against one control in one framework (say NIST CSF
``PR.AA-01``). Auditors and multi-framework programmes need the *equivalent*
controls in other frameworks (ISO 27001, SOC 2, Loi 05-20 …). This capability
produces that mapping — **grounded**: each mapped control is one that was actually
retrieved from the corpus and verified, never an invented cross-reference. The
``citation_verified`` flag is the visible outcome of that guarantee (rule 3).
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.domain.value_objects.identifiers import ControlId, NonEmptyStr


class MappedControl(FrozenModel):
    """One equivalent control in another framework.

    Attributes:
        framework: The framework the equivalent control belongs to.
        control_id: The equivalent control's identifier within that framework.
        reference: A human-readable locator (from the retrieved source) so a
            reviewer can find and check the equivalence.
    """

    framework: Framework
    control_id: ControlId
    reference: NonEmptyStr


class ControlMapping(FrozenModel):
    """A finding's control mapped to equivalent controls across frameworks.

    Attributes:
        finding_id: The finding whose control is being mapped.
        source_framework: The framework of the finding's own control.
        source_control_id: The finding's own control identifier.
        summary: A grounded, plain-language explanation of the equivalences.
        mappings: Equivalent controls in *other* frameworks (each backed by a
            verified citation).
        citations: The controls the mapping is grounded in.
        citation_verified: True only if every cited control was verified against
            retrieved corpus content. False signals the mapping is not
            authoritative (e.g. an abstention when nothing relevant was found).
    """

    finding_id: NonEmptyStr
    source_framework: Framework
    source_control_id: ControlId
    summary: NonEmptyStr
    mappings: list[MappedControl] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    citation_verified: bool
