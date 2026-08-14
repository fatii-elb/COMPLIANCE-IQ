"""Value objects — small, immutable, self-validating domain concepts.

A value object has no identity of its own; it is defined entirely by its
attributes (two ``Citation`` objects with the same framework/control/reference
are interchangeable). Encoding concepts like severity, cloud, and framework as
value objects — rather than bare strings — makes illegal states unrepresentable
and pushes validation to the boundary.
"""

from complianceiq.domain.value_objects.citation import Citation
from complianceiq.domain.value_objects.enums import (
    CloudProvider,
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)
from complianceiq.domain.value_objects.identifiers import (
    ControlId,
    NonEmptyStr,
    ResourceId,
    TenantId,
)

__all__ = [
    "Citation",
    "CloudProvider",
    "ComplianceStatus",
    "ControlId",
    "Framework",
    "NonEmptyStr",
    "ResourceId",
    "RiskDomain",
    "Severity",
    "TenantId",
]
