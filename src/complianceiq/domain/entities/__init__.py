"""Domain entities — the boundary contracts shared with the Core Service.

These types are the *published contract* between the AI Service and the Core
Service (Section 6 of the build spec). They are implemented faithfully,
validated strictly, and never changed unilaterally.
"""

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.financial import FinancialRiskAssessment
from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.entities.pagination import Page
from complianceiq.domain.entities.remediation import RemediationProposal
from complianceiq.domain.entities.resource import NormalizedResource
from complianceiq.domain.entities.risk import CorrelatedRisk
from complianceiq.domain.entities.score import ComplianceScore

__all__ = [
    "AuthContext",
    "ComplianceScore",
    "CorrelatedRisk",
    "EnrichedFinding",
    "FinancialRiskAssessment",
    "Finding",
    "NormalizedResource",
    "Page",
    "RemediationProposal",
]
