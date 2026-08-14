"""The :class:`Citation` value object.

A citation is the atom of ComplianceIQ's explainability guarantee: every claim
the AI makes must point to a real control in a real framework. A citation is
*produced* by generation but only trusted once it has been *verified* against
retrieved corpus content (the verification lives on :class:`EnrichedFinding`
and the grounding policy, not here — a citation is just the reference itself).
"""

from __future__ import annotations

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.enums import Framework
from complianceiq.domain.value_objects.identifiers import ControlId, NonEmptyStr


class Citation(FrozenModel):
    """A reference to a specific control within a compliance framework.

    Attributes:
        framework: The framework the cited control belongs to.
        control_id: The control/article identifier within that framework.
        reference: A human-readable locator (section title, article number, or
            corpus chunk reference) that lets a human find the source.
    """

    framework: Framework
    control_id: ControlId
    reference: NonEmptyStr
