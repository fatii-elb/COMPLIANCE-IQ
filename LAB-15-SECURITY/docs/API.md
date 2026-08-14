# HTTP API (Phase 5)

The ComplianceIQ AI Service exposes its capabilities as a JSON HTTP API. This
document describes the surface; the live, interactive contract is always at
`/docs` (Swagger UI) and `/openapi.json`.

## Base URL & versioning

All AI capabilities are under **`/api/v1/ai`**. Operational endpoints
(`/health`, `/health/ready`, `/version`) live at the root and are unauthenticated.

## Authentication

Every `/api/v1/ai/*` endpoint requires a **bearer token**:

```
Authorization: Bearer <jwt>
```

The Core Service issues the token; this service only verifies it and reads the
tenant from its claims. Required claims (map to `AuthContext`):

| Claim | Meaning |
| --- | --- |
| `sub` | The authenticated principal (user or service account) |
| `tenant_id` | The tenant the request acts within — **everything is scoped by this** |
| `roles` | The principal's roles (list of strings) |
| `iss` | Must equal `CIQ_JWT_ISSUER` (default `complianceiq-core`) |
| `aud` | Must equal `CIQ_JWT_AUDIENCE` (default `complianceiq`) |
| `exp` | Expiry (required); `nbf` is honoured if present |

**Signing.** Phase 5 verifies **HS256** tokens with a shared secret
(`CIQ_JWT_HS256_SECRET`) — for local development and testing. Production uses the
Core's **asymmetric** key (RS256/ES256, `CIQ_JWT_PUBLIC_KEY`); that verifier lands
in Phase 6 behind the same port, and no endpoint changes. See ADR-0009.

**Tenant isolation.** A token for tenant A may not act on tenant B's data. Any
finding in a request body whose `tenant_id` differs from the token's is rejected
with `403 tenant_isolation_violation` (non-negotiable rule 1).

## Endpoints

All bodies are JSON. Enum fields use the wire values from
`docs/CORE_SERVICE_HANDOFF.md` §4 (e.g. `framework: "nist_csf"`, `severity: "high"`).

### `POST /api/v1/ai/enrich`
Explain findings, grounded and cited.

- **Body:** `{ "findings": [Finding, …] }` (1–100)
- **Response:** `[EnrichedFinding, …]` — each with an `explanation`, verified
  `citations`, and an authoritative `citation_verified` flag. When retrieval finds
  nothing, the explanation is the abstention and `citation_verified` is `false`.

### `POST /api/v1/ai/ask`
Answer a natural-language question, grounded in the corpus.

- **Body:** `{ "question": "…", "framework": "nist_csf"? }` (framework optional)
- **Response:** `CopilotAnswer` — `{ question, answer, citations, citation_verified,
  abstained }`. If nothing relevant is retrieved, `abstained: true` and `answer` is
  `"Not covered by the provided sources."`

### `POST /api/v1/ai/remediate`
Propose a fix for a finding — **never applied**.

- **Body:** `{ "finding": Finding }`
- **Response:** `RemediationProposal` — `{ finding_id, terraform, justification,
  citations, approved }`. `approved` is **always `false`**; the generated IaC is
  statically validated, and an over-permissive fix is rejected (`500 workflow_error`).

### `POST /api/v1/ai/correlate`
Correlate findings into one grounded systemic-risk narrative.

- **Body:** `{ "findings": [Finding, …] }` (1–100)
- **Response:** `{ "narrative": "…" }`

### `POST /api/v1/ai/map`
Map a finding's control to equivalent controls in other frameworks.

- **Body:** `{ "finding": Finding }`
- **Response:** `ControlMapping` — `{ finding_id, source_framework, source_control_id,
  summary, mappings: [{framework, control_id, reference}], citations, citation_verified }`.
  Each mapped control is a **retrieved, verified** control in a *different* framework;
  when nothing relevant is found, the mapping abstains (`citation_verified: false`).

### `POST /api/v1/ai/financial`
Quantify a finding's monetary exposure in Moroccan Dirham (MAD).

- **Body:** `{ "finding": Finding }`
- **Response:** `FinancialRiskAssessment` — `{ finding_id, min_mad, max_mad, rationale,
  assumptions }`. The **range is computed deterministically** from the finding's
  severity and domain (never by the model); the model only writes the rationale.
  Always a range, never a point estimate; a passing finding yields `0–0`.

### `POST /api/v1/ai/report`
Draft an executive summary over enriched findings.

- **Body:** `{ "findings": [EnrichedFinding, …] }`
- **Response:** `ReportDraft` — `{ tenant_id, executive_summary, finding_count,
  severity_breakdown, generated_at }`. Counts are computed in code, not by the model.

> `/ai/report` is synchronous today; the async-job variant is a later refinement.

## Errors

Every failure returns the same envelope:

```json
{ "error": { "code": "…", "message": "…", "correlation_id": "…", "details": {} } }
```

| Situation | Status | `code` |
| --- | --- | --- |
| Missing/invalid token | 401 | `authentication_error` |
| Cross-tenant access | 403 | `tenant_isolation_violation` |
| Body fails validation | 422 | `validation_error` |
| Injected/unsafe content | 400 | `unsafe_content` |
| Budget/loop/validation in a workflow | 500 | `workflow_error` |
| Upstream provider failure | 502 | `provider_error` |

No stack trace or internal detail ever reaches the client; the `correlation_id`
(also the `X-Correlation-ID` response header) ties a client-visible error to the
server logs.

## Operational endpoints (unauthenticated)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness — the process is up |
| GET | `/health/ready` | Readiness — all dependencies reachable (503 if not) |
| GET | `/version` | Service name, version, environment |
| GET | `/docs`, `/openapi.json` | Interactive contract |

## Example

```bash
curl -sS http://localhost:8000/api/v1/ai/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "How should IAM access keys be managed?"}'
```
