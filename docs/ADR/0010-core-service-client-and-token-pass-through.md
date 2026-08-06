# ADR-0010: Core Service client with token pass-through

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

The Core Service owns cloud scanning, the rule engine, tenancy, and the
findings/scores API; this AI service *consumes* findings and returns
intelligence. Through Phase 5, callers posted finding *bodies* to our endpoints.
Phase 6 lets the AI service *fetch* the authoritative findings from the Core
itself (handoff §6.1), which raises two questions: how do we call the Core
without coupling to it, and whose identity do we call it with?

## Decision

**A `CoreClient` port with two adapters.** Define `CoreClient` in the domain
(`get_finding`, `list_findings`), returning domain `Finding`/`Page[Finding]`. Two
implementations satisfy it:
- **`StubCoreClient`** — seeded, in-process, tenant-scoped; the **offline
  default**, so the whole pipeline (fetch → enrich) runs with no live Core, and
  the test suite needs no network.
- **`HttpCoreClient`** — calls the Core's REST API over an injectable
  `httpx.AsyncClient` (so its mapping is tested offline with `MockTransport`),
  translating HTTP failures into the domain exceptions the API already renders
  (404 → `NotFoundError`, 401 → `AuthenticationError`, 5xx/network →
  `DependencyUnavailableError`).

`build_core_client(settings)` selects between them (`core_client=stub|http`).

**Token pass-through.** The HTTP client forwards the *caller's own JWT* to the
Core (a `get_bearer_token` dependency surfaces it), rather than using an ambient
service credential. The Core then authorizes the request against the same
identity — end-to-end tenant propagation, and no long-lived god credential in the
AI service.

**Defense-in-depth tenant check.** Even though the Core is trusted, every finding
it returns is re-verified against the caller's tenant (`assert_same_tenant`)
before we use it. A Core bug or compromise can therefore never leak another
tenant's finding *through us* (rule 1). In the stub, a foreign-tenant id simply
reads as `NotFoundError` — never the data.

**One new endpoint.** `POST /api/v1/ai/enrich/by-ids` takes finding *ids*, pulls
them from the Core (tenant-scoped, token forwarded), and enriches them —
demonstrating the integration without disturbing the body-based endpoints.

### Alternatives considered

- **A single service credential for Core calls.** Rejected: it detaches the Core
  call from the caller's identity and concentrates a high-value secret; pass-through
  keeps authorization coherent across both services.
- **Trusting the Core's tenant scoping alone.** Rejected: cross-service isolation
  is too important to depend on a single side; we re-check on receipt.
- **No stub (always call a real Core).** Rejected: it would make local dev and the
  test suite depend on a running Core; the stub keeps everything offline.

## Consequences

- The AI service can source authoritative findings from the Core while staying
  fully offline-testable (stub default; HTTP adapter tested with `MockTransport`).
- Identity flows end to end; no ambient god credential.
- Tenant isolation holds even against a misbehaving Core.
- Swapping stub ↔ HTTP is a settings change; application and presentation code is
  untouched.
