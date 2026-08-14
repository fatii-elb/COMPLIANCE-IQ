# ADR-0011: Standard-library RS256 verification and the pgvector store

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

Two Phase-6 hardening tasks share a constraint: the target runtime here has no
working compiled crypto stack (`cryptography`/OpenSSL panics) and no database
driver or live PostgreSQL. Yet Phase 6 must deliver **production JWT verification**
(the Core signs asymmetrically; we verify with its public key) and the
**pgvector** backend promised in ADR-0005 — both in a way that stays offline and
fully testable.

## Decision

### RS256 verification, standard-library only

Add `RS256TokenVerifier` behind the existing `TokenVerifier` port. RSA signature
*verification* is a short, well-specified integer computation — interpret the
signature as an integer `s`, compute `m = sᵉ mod n`, and compare `m` to the
PKCS#1 v1.5 (EMSA-PKCS1-v1_5, SHA-256) encoding of the signing input — so we
implement it directly with `pow()` and `hashlib`, no crypto package. The public
key is supplied as a **JWK** (`{"n":…, "e":…}`), exactly what a JWKS endpoint
serves.

Both verifiers now share a single claim-validation pipeline
(`BaseJwtVerifier`): split → **pin algorithm** → verify signature (the only
differing step) → `exp`/`nbf`/`iss`/`aud` → project to `AuthContext`. Pinning to
`RS256` closes the `none` downgrade and the RS↔HS confusion attack; the recovered
PKCS#1 block is compared in constant time.

The composition root selects the verifier automatically: a public **JWK** in
`jwt_public_key` → RS256 (production); otherwise the HS256 secret (dev/testing).

### pgvector behind a thin SQL-executor seam

Add `PgVectorStore` implementing the Phase-3 `VectorStore` port with SQL, and a
`migrations/0001_knowledge_pgvector.sql` (extension, table, ivfflat cosine index).
All SQL goes through a minimal `SqlExecutor` protocol; the real psycopg-backed
executor is imported **lazily** and built only when `vector_store=pgvector`, so
the module (and the app) import cleanly with no driver present. Similarity ranking
is delegated to pgvector's `<=>` operator; the embedding-model-identity guard
(ADR-0005) is enforced in the adapter. The default remains the in-memory store.

### Alternatives considered

- **Require `cryptography`/PyJWT for RS256.** Rejected here: unavailable in this
  runtime, and hand-verifying RSA (verification only, public key only) is small,
  auditable, and offline-testable. A production build may still swap in a
  library-backed verifier behind the same port.
- **Defer pgvector to "a real environment."** Rejected: the adapter, migration,
  and mapping/guard logic are exactly what ADR-0005 promised; the executor seam
  lets us build and unit-test them now, gated off by default.
- **Test pgvector against a live Postgres in CI.** Out of scope for the offline
  suite; the seam tests the SQL construction, row mapping, and model guard, and
  end-to-end ranking is exercised in a real deployment.

## Consequences

- Production-style RS256 verification works and is tested offline (tests mint
  RS256 tokens with a pure-Python signer and a small test keypair); the algorithm
  pin and forgery/expiry/issuer paths are all covered.
- The pgvector backend exists behind the same `VectorStore` port, with a migration
  shipped in the image; enabling it is a settings change plus applying the SQL.
- Two clearly-scoped caveats, documented: the RS256 verifier is a from-scratch
  implementation (auditable, and swappable for a library-backed one), and the
  pgvector similarity path is exercised in a real Postgres, not the offline suite.
- `psycopg[binary,pool]` is an **optional** dependency, needed only for
  `vector_store=pgvector`.
