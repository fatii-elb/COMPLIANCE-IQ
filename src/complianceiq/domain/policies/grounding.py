"""Grounding policy — cite, verify, abstain (non-negotiable rule 3).

The grounding guarantee has three parts, all enforced here or by the graphs that
use this module:

1. **Cite** — every generated answer carries citations to specific controls.
2. **Verify** — a citation is trusted only if it actually appears in the sources
   that were retrieved and shown to the model. :func:`verify_citations` checks
   claimed citations against the available (retrieved) ones and rejects the rest.
3. **Abstain** — when retrieval yields nothing relevant, the correct output is a
   first-class abstention ("not covered by the provided sources"), never a
   guess. :data:`ABSTENTION_TEXT` is that answer.

This is pure and deterministic, so the guarantee is unit-testable in isolation.
"""

from __future__ import annotations

from collections.abc import Sequence

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.citation import Citation

#: The canonical answer when nothing relevant was retrieved (rule 3).
ABSTENTION_TEXT = "Not covered by the provided sources."


class CitationVerification(FrozenModel):
    """The outcome of verifying claimed citations against retrieved sources.

    Attributes:
        verified: Claimed citations that were found in the retrieved sources.
        unverified: Claimed citations that could NOT be found (rejected).
    """

    verified: list[Citation]
    unverified: list[Citation]

    @property
    def all_verified(self) -> bool:
        """True if every claimed citation was verified (none rejected)."""
        return len(self.unverified) == 0

    @property
    def has_verified(self) -> bool:
        """True if at least one citation was verified."""
        return len(self.verified) > 0


def verify_citations(
    claimed: Sequence[Citation], available: Sequence[Citation]
) -> CitationVerification:
    """Verify ``claimed`` citations against the ``available`` (retrieved) ones.

    A claimed citation is *verified* iff an available citation shares its
    ``framework`` and ``control_id``. Unverifiable citations are rejected — this
    is what stops a model from inventing a plausible-looking reference. Duplicate
    claims are collapsed.

    Args:
        claimed: Citations the answer asserts.
        available: Citations for the sources actually retrieved and shown.

    Returns:
        A :class:`CitationVerification` splitting claimed into verified/unverified.
    """
    available_keys = {(c.framework, c.control_id) for c in available}

    verified: list[Citation] = []
    unverified: list[Citation] = []
    seen: set[tuple[str, str]] = set()

    for citation in claimed:
        key = (citation.framework.value, citation.control_id)
        if key in seen:
            continue
        seen.add(key)
        if (citation.framework, citation.control_id) in available_keys:
            verified.append(citation)
        else:
            unverified.append(citation)

    return CitationVerification(verified=verified, unverified=unverified)
