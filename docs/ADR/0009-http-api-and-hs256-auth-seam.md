# ADR-0009: HTTP API surface and the token-verification seam

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

Phase 4 produced the AI capabilities (four bounded agents plus the copilot graph)
but no way to call them over the network. Phase 5 adds the presentation layer: the
HTTP endpoints the Core Service (and the dashboard, via the Core) will call. Two
decisions dominate it: **how requests are authenticated and tenant-scoped**, and
**what the request/response contract is**.

Authentication is genuinely a *Core Service* responsibility — the Core issues
tenant JWTs; we only verify them and read the tenant from the claims
(`docs/CORE_SERVICE_HANDOFF.md` §5). Production tokens will be **asymmetric**
(RS256/ES256): the Core signs with its private key and hands us only the public
key. But that verifier needs a crypto dependency and the Core's key material,
neither of which belongs in Phase 5 — and an API with no authentication at all is
not shippable or testable.

## Decision

**A `TokenVerifier` port with a swappable adapter.** Define a domain port
`TokenVerifier.verify(token) -> AuthContext`. Presentation depends only on the
port (via the `Container` protocol); the composition root supplies the concrete
verifier. This is the seam that lets the signing scheme change without touching a
single caller.

**Phase 5 ships an HS256 (symmetric) verifier, standard-library only.** HMAC-SHA256
is a legitimate, secure scheme for local development and offline testing (a shared
secret both mints and verifies), and it needs nothing but `hmac`/`hashlib`/`base64`
— no crypto package, no cffi. The verifier validates the signature and the standard
claims (`exp`, `nbf`, `iss`, `aud`) before trusting anything, then projects
`sub`/`tenant_id`/`roles` into an `AuthContext`. **Phase 6 adds an RS256/ES256
verifier** using the Core's public key, implementing the same port; nothing else
changes.

Security properties baked into the verifier:
- The algorithm is **pinned to HS256**; a token whose header says `none` or
  `RS256` is rejected. This closes the classic *algorithm-confusion* downgrade.
- Signature comparison is **constant-time** (`hmac.compare_digest`).
- Errors never echo the token, the secret, or the computed signature.

**Tenant scoping is enforced at the boundary.** Every endpoint depends on
`get_auth_context`; endpoints that accept findings call `assert_same_tenant` for
each one, so a token for tenant A can never act on tenant B's finding (rule 1),
returning `403 tenant_isolation_violation`.

**The response contract is the domain model itself.** `POST /ai/enrich` returns
`EnrichedFinding`s, `/ai/remediate` a `RemediationProposal`, and so on — the exact
Pydantic contracts the Core integrates against (handoff §2). We do not duplicate a
parallel set of response DTOs that could drift; only thin *request envelopes*
(`EnrichRequest`, …) live in the presentation layer.

### Endpoints (all under `/api/v1/ai`, JWT-protected)

`POST /enrich`, `POST /ask`, `POST /remediate`, `POST /correlate`, `POST /report`.
`/ai/map` and `/ai/financial` are intentionally **not** exposed yet — those
capabilities land in Phase 7. `/ai/report` is synchronous here (returns a
`ReportDraft`); the async-job variant in the handoff is a later refinement.

### Alternatives considered

- **RS256 verification now.** Rejected for Phase 5: needs a crypto dependency and
  the Core's key material (a Phase 6 concern). The port makes deferring it free.
- **A hand-waved "trust a header" dev auth.** Rejected: an unauthenticated or
  trivially-forgeable seam in a *security* product sets the wrong pattern and
  can't test the real rejection paths. HS256 exercises genuine signature checks.
- **A second set of response DTOs.** Rejected: the domain models *are* the
  published contract; a parallel set only invites drift.

## Consequences

- The API is authenticated, tenant-scoped, and fully **offline-testable** today
  (tests mint HS256 tokens with no JWT library); the security-critical rejection
  paths — tampered signature, expiry, `none`-downgrade, wrong issuer/audience — are
  unit-tested.
- Phase 6 swaps in RS256/ES256 by implementing the same port and wiring the Core's
  public key; presentation, routers, and tests are untouched.
- The HS256 shared secret is a **development** credential; production must set the
  asymmetric key. `.env.example` says so, and the default secret is clearly marked
  insecure.
