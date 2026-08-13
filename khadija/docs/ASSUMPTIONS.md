# Assumptions

Where a business requirement was not fully specified, a sensible default was
chosen and recorded here (per the working agreement). Each can be revisited.

## Phase 1

1. **Currency.** Financial exposure is expressed in Moroccan Dirham (MAD), per
   the project's local-regulatory focus. `FinancialRiskAssessment` stores
   `Decimal` amounts to avoid floating-point money errors.
2. **JWT verification, not issuance.** The Core Service issues tenant JWTs; this
   service only verifies them. Verification wiring lands in Phase 6; Phase 1
   defines the `AuthContext` contract and the tenant-isolation policy.
3. **`tenant_id` is a non-empty string ≤ 128 chars.** Modelled as a constrained
   string rather than a UUID, because the Core contract specifies a string and
   we must not over-constrain the boundary.
4. **Readiness with no dependencies is "ready".** Phase 1 has no external hard
   dependencies, so readiness is trivially healthy. The probe mechanism exists
   so later phases register real checks.
5. **`RemediationProposal.approved` is always `False` in this service.** Human
   approval happens in the Core platform, out of scope here. The field is forced
   to `False` structurally.
6. **Version string** comes from the package `__version__` (`0.1.0`) rather than
   git metadata, to keep the container build hermetic.
7. **Default LLM provider is the deterministic `fake` provider** so the stack
   runs offline with no API key until Phase 2 wires real providers.
8. **English is the primary language** of generated explanations, with the
   corpus carrying `language`/`jurisdiction` metadata to support French/Arabic
   Moroccan sources in later phases.
