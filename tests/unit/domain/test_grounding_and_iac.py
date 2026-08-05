"""Tests for the grounding and IaC-safety policies (pure, deterministic).

These are two of the non-negotiable guarantees: citations are trusted only when
verified against retrieved sources (rule 3), and a generated remediation is
rejected if it is overly permissive (rule 2/8).
"""

from __future__ import annotations

from complianceiq.domain.policies.grounding import (
    ABSTENTION_TEXT,
    verify_citations,
)
from complianceiq.domain.policies.iac_safety import validate_terraform
from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import Framework


def _cite(control_id: str, framework: Framework = Framework.NIST_CSF) -> Citation:
    return Citation(framework=framework, control_id=control_id, reference=f"{control_id} ref")


def test_verify_accepts_matching_citations() -> None:
    available = [_cite("PR.AA-01"), _cite("PR.DS-01")]
    result = verify_citations([_cite("PR.AA-01")], available)
    assert result.all_verified is True
    assert result.has_verified is True
    assert [c.control_id for c in result.verified] == ["PR.AA-01"]


def test_verify_rejects_invented_citation() -> None:
    available = [_cite("PR.AA-01")]
    claimed = [_cite("PR.AA-01"), _cite("XX.99")]  # second is invented
    result = verify_citations(claimed, available)
    assert result.all_verified is False
    assert [c.control_id for c in result.verified] == ["PR.AA-01"]
    assert [c.control_id for c in result.unverified] == ["XX.99"]


def test_verify_rejects_cross_framework_match() -> None:
    available = [_cite("PR.AA-01", Framework.NIST_CSF)]
    claimed = [_cite("PR.AA-01", Framework.SOC_2)]  # same id, wrong framework
    result = verify_citations(claimed, available)
    assert result.all_verified is False
    assert result.unverified


def test_verify_dedupes_duplicate_claims() -> None:
    available = [_cite("PR.AA-01")]
    result = verify_citations([_cite("PR.AA-01"), _cite("PR.AA-01")], available)
    assert len(result.verified) == 1


def test_abstention_text_is_stable() -> None:
    assert ABSTENTION_TEXT == "Not covered by the provided sources."


def test_iac_safe_snippet_passes() -> None:
    safe = 'resource "aws_iam_policy" "p" {\n  statement { actions = ["iam:GetUser"] }\n}'
    assert validate_terraform(safe) == []


def test_iac_prose_about_public_access_does_not_trip() -> None:
    prose = "This remediation removes public read-write access and wildcard principals."
    assert validate_terraform(prose) == []


def test_iac_open_cidr_is_flagged() -> None:
    assert "open-cidr-ipv4" in validate_terraform('cidr_blocks = ["0.0.0.0/0"]')


def test_iac_wildcard_principal_is_flagged() -> None:
    tf = 'resource "aws_iam_policy" "p" { Principal = "*" }'
    assert "wildcard-principal" in validate_terraform(tf)


def test_iac_public_acl_is_flagged() -> None:
    assert "public-acl" in validate_terraform('acl = "public-read-write"')
