"""Domain policies — cross-cutting business rules expressed as pure functions.

Policies encode invariants that several use cases share (tenant isolation now;
grounding/abstention and remediation-safety as their subsystems land). Keeping
them here — pure, dependency-free, individually tested — is what lets the
non-negotiable rules be enforced *structurally* rather than by convention.
"""

from complianceiq.domain.policies.tenant_isolation import assert_same_tenant

__all__ = ["assert_same_tenant"]
