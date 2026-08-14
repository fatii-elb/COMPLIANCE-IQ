"""Tests for the remediation-approval invariant (non-negotiable rule 2).

``RemediationProposal.approved`` must be ``False`` in this service no matter what
a caller supplies. These are non-skippable security gates.
"""

from __future__ import annotations

import pytest

from complianceiq.domain.entities.remediation import RemediationProposal
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import Framework


def _proposal(**overrides: object) -> RemediationProposal:
    defaults: dict[str, object] = {
        "finding_id": "finding-1",
        "terraform": 'resource "aws_s3_bucket_public_access_block" "b" {}',
        "justification": "Blocks public access to satisfy the storage control.",
    }
    defaults.update(overrides)
    return RemediationProposal(**defaults)  # type: ignore[arg-type]


@pytest.mark.security
def test_approved_defaults_to_false() -> None:
    assert _proposal().approved is False


@pytest.mark.security
def test_approved_true_is_forced_to_false() -> None:
    # Even an explicit approved=True from a caller must be ignored.
    assert _proposal(approved=True).approved is False


@pytest.mark.security
def test_approved_truthy_values_are_forced_to_false() -> None:
    for truthy in (1, "yes", ["x"], object()):
        assert _proposal(approved=truthy).approved is False


def test_proposal_carries_citations() -> None:
    citation = Citation(framework=Framework.LOI_05_20, control_id="art-23", reference="Article 23")
    proposal = _proposal(citations=[citation])
    assert proposal.citations == [citation]
    # Frozen: proposals are immutable value objects.
    with pytest.raises(Exception):  # noqa: B017 - pydantic raises on frozen assignment
        proposal.approved = True  # type: ignore[misc]
