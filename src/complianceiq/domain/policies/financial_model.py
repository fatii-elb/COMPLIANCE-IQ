"""Financial exposure model — a *deterministic*, auditable MAD estimate.

Money is the one output a compliance product must never hallucinate. So the
monetary range is computed here, in a pure domain policy, from the finding's
**severity** and **domain** — not by a language model. The model (in the
financial workflow) only *narrates* the range this policy produced; it never
invents a figure. Every band and multiplier is explicit and unit-tested, and the
assumptions behind the number are returned alongside it so a reviewer can
challenge the inputs rather than a black box.

The output is deliberately a **range** in Moroccan Dirham (MAD): a single point
estimate would imply a precision we cannot justify in an audit.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.value_objects.enums import ComplianceStatus, RiskDomain, Severity

# Base exposure band per severity, in MAD. Planning ranges, not actuarial figures.
_BASE_BANDS_MAD: dict[Severity, tuple[Decimal, Decimal]] = {
    Severity.LOW: (Decimal("5000"), Decimal("25000")),
    Severity.MEDIUM: (Decimal("25000"), Decimal("150000")),
    Severity.HIGH: (Decimal("150000"), Decimal("750000")),
    Severity.CRITICAL: (Decimal("750000"), Decimal("4000000")),
}

# Per-domain impact multiplier — data-bearing domains carry more exposure.
_DOMAIN_MULTIPLIER: dict[RiskDomain, Decimal] = {
    RiskDomain.STORAGE: Decimal("1.3"),
    RiskDomain.IAM: Decimal("1.2"),
    RiskDomain.ENCRYPTION: Decimal("1.2"),
    RiskDomain.NETWORK: Decimal("1.1"),
    RiskDomain.LOGGING: Decimal("1.0"),
}

_WHOLE = Decimal("1")


class ExposureBand(FrozenModel):
    """A computed monetary exposure range with its explicit assumptions.

    Attributes:
        min_mad: Lower bound of exposure in MAD (>= 0).
        max_mad: Upper bound of exposure in MAD (>= min_mad).
        assumptions: The explicit inputs/caveats the range depends on.
    """

    min_mad: Decimal
    max_mad: Decimal
    assumptions: list[str]


def estimate_exposure(finding: Finding) -> ExposureBand:
    """Compute a deterministic MAD exposure band for ``finding``.

    A compliant (``pass``) finding carries no residual exposure. Otherwise the
    band is the severity base range scaled by the domain multiplier, rounded to
    whole dirham.
    """
    if finding.status is ComplianceStatus.PASS:
        return ExposureBand(
            min_mad=Decimal(0),
            max_mad=Decimal(0),
            assumptions=[
                "The resource passes this control, so no residual exposure is attributed.",
            ],
        )

    base_min, base_max = _BASE_BANDS_MAD[finding.severity]
    multiplier = _DOMAIN_MULTIPLIER.get(finding.domain, Decimal("1.0"))
    min_mad = (base_min * multiplier).quantize(_WHOLE, rounding=ROUND_HALF_UP)
    max_mad = (base_max * multiplier).quantize(_WHOLE, rounding=ROUND_HALF_UP)
    assumptions = [
        f"Severity '{finding.severity.value}' maps to a base exposure band of "
        f"{base_min:f}–{base_max:f} MAD.",
        f"Domain '{finding.domain.value}' applies a {multiplier:f}x impact multiplier.",
        "The figure is a planning range, not an actuarial estimate; it excludes "
        "regulatory fines and reputational loss.",
        "A single affected resource is assumed; scale the range for fleet-wide exposure.",
    ]
    return ExposureBand(min_mad=min_mad, max_mad=max_mad, assumptions=assumptions)
