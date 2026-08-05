"""Domain policies — cross-cutting business rules expressed as pure functions.

Policies encode invariants that several use cases share: tenant isolation, and
prompt-injection detection/neutralisation (risk/grounding policies land with
their subsystems). Keeping them here — pure, dependency-free, individually
tested — is what lets the non-negotiable rules be enforced *structurally* rather
than by convention.
"""

from complianceiq.domain.policies.grounding import (
    ABSTENTION_TEXT,
    CitationVerification,
    verify_citations,
)
from complianceiq.domain.policies.iac_safety import validate_terraform
from complianceiq.domain.policies.prompt_safety import (
    InjectionScanResult,
    InjectionSignal,
    scan_for_injection,
    wrap_untrusted,
)
from complianceiq.domain.policies.tenant_isolation import assert_same_tenant

__all__ = [
    "ABSTENTION_TEXT",
    "CitationVerification",
    "InjectionScanResult",
    "InjectionSignal",
    "assert_same_tenant",
    "scan_for_injection",
    "validate_terraform",
    "verify_citations",
    "wrap_untrusted",
]
