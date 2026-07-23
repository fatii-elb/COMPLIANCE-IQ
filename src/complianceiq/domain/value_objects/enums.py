"""Enumerations shared across the domain.

Using ``StrEnum`` keeps the wire representation human-readable (``"critical"``
serialises as-is in JSON) while giving the type system a closed set of legal
values. New clouds, frameworks, or domains are added here in one place.
"""

from __future__ import annotations

from enum import StrEnum


class CloudProvider(StrEnum):
    """The cloud platforms whose resources ComplianceIQ scans."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class Framework(StrEnum):
    """Compliance frameworks the knowledge base and mapping engine cover.

    ``ISO_27001`` is present as an identifier only — per the ISO copyright
    policy (docs/COMPLIANCE_NOTES.md) the verbatim standard text is never
    stored; the knowledge base holds control identifiers and original summaries.
    ``LOI_05_20`` (Morocco) and ``DNSSI`` are public sources and are the primary
    quotable material.
    """

    ISO_27001 = "iso_27001"
    LOI_05_20 = "loi_05_20"
    DNSSI = "dnssi"
    NIST_CSF = "nist_csf"
    SOC_2 = "soc_2"


class RiskDomain(StrEnum):
    """Control domains a finding can belong to.

    Mirrors the domains produced by the Core Service's rule engine so findings
    map cleanly onto our knowledge base structure.
    """

    IAM = "iam"
    NETWORK = "network"
    ENCRYPTION = "encryption"
    LOGGING = "logging"
    STORAGE = "storage"


class Severity(StrEnum):
    """Severity of a finding or risk, ordered low → critical.

    :meth:`weight` exposes a numeric rank for aggregation logic (used by the
    risk engine in a later phase) without leaking magic numbers elsewhere.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        """Numeric rank (low=1 … critical=4) for severity aggregation."""
        return _SEVERITY_WEIGHTS[self]


class ComplianceStatus(StrEnum):
    """Outcome of evaluating a resource against a rule."""

    PASS = "pass"
    FAIL = "fail"


_SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
