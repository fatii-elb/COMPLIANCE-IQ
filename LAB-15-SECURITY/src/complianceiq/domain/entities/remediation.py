"""The :class:`RemediationProposal` contract.

The recommendation engine (Phase 5) proposes Infrastructure-as-Code fixes for
findings. Non-negotiable rule 2 — *remediation is NEVER auto-applied* — is
enforced here structurally: ``approved`` is forced to ``False`` on construction
regardless of any value a caller supplies. This service proposes; a human, in
the Core platform, disposes. No code path in this service may set it True or act
on a proposal.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class RemediationProposal(FrozenModel):
    """A proposed IaC fix for a finding. Never auto-applied.

    Attributes:
        finding_id: The finding this proposal remediates.
        terraform: The proposed Terraform (primary IaC target).
        justification: Grounded explanation of why this fix resolves the finding.
        citations: The controls the justification is grounded in.
        approved: Always ``False`` in this service. Structurally enforced — any
            caller-supplied value is ignored. Human approval happens elsewhere.
    """

    finding_id: NonEmptyStr
    terraform: NonEmptyStr
    justification: NonEmptyStr
    citations: list[Citation] = Field(default_factory=list)
    approved: bool = False

    @field_validator("approved", mode="before")
    @classmethod
    def _force_unapproved(cls, _value: Any) -> bool:
        """Ignore any supplied value; a proposal is never approved here.

        This is the structural teeth behind non-negotiable rule 2. Even a caller
        that explicitly passes ``approved=True`` gets ``False``.
        """
        return False
