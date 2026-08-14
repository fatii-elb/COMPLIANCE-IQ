# Release Readiness (Phase 8)

This is the capstone checklist for the ComplianceIQ AI subsystem: every
non-negotiable rule mapped to **where it is enforced** and **how it is verified**,
plus the quality gates, operational surface, and the deploy-time settings that must
change from their offline defaults. If a reviewer reads one document before signing
off, it is this one.

## Non-negotiable rules → enforcement → verification

| # | Rule | Enforced in | Verified by |
| --- | --- | --- | --- |
| 1 | **Tenant isolation is absolute** | `assert_same_tenant` policy; every `/ai/*` endpoint checks each finding's tenant against the token; the HTTP Core client re-checks returned findings (defense-in-depth) | `test_tenant_isolation`, endpoint `*_cross_tenant_*` tests, `test_core_client` cross-tenant tests |
| 2 | **Remediation is never auto-applied** | `RemediationProposal.approved` is force-set `False` on construction; `validate_terraform` rejects over-permissive IaC (`WorkflowError`) | `test_remediation`, `test_grounding_and_iac`, remediation graph tests |
| 3 | **Grounding: cite, verify, abstain** | `grounding` policy (`verify_citations`, `ABSTENTION_TEXT`); every grounded graph attaches only verified citations and abstains on empty retrieval; **measured** by the grounding eval | `test_grounding_and_iac`, graph tests, `test_grounding_eval`, `scripts/evaluate_ai` |
| 4 | **Prompt-injection defence** | `scan_for_injection` at the gateway; `wrap_untrusted` on all retrieved context; `ToolSession` scans tool output | `test_prompt_safety`, `test_ai_gateway` injection gate, agent output-scan tests |
| 5 | **Secrets never in source/logs** | `SecretStr` for all keys; errors never echo tokens/secrets; JWT verifiers never log the token | settings tests; auth verifier tests assert generic error messages |
| 6 | **ISO copyright compliance** | Corpus stores *our* control summaries + metadata, never verbatim standard text | corpus files + `docs/COMPLIANCE_NOTES.md` |
| 7 | **Audit trail** | Correlation ID per request (bound to logs, echoed in responses/errors); usage ledger records every model call | correlation-id middleware; `test_ai_gateway` ledger tests; `/metrics` |
| 8 | **No red-team / no autonomous change** | Agents propose only; bounded tools (allow-list, budgets, loop detection); the service never mutates a customer environment | agent guardrail tests; remediation `approved=False` |

## Additional integrity guarantees

- **Financial figures are computed, never hallucinated** — deterministic
  `estimate_exposure`; the model only narrates (`test_financial_model`, financial
  graph tests).
- **Control mappings are verified, cross-framework only** — never invented
  (`test_mapping_financial_graphs`).
- **Embedding-model guard** — vectors from different models are never compared
  (in-memory and pgvector stores).

## Quality gates (all green)

| Gate | Command | Status |
| --- | --- | --- |
| Tests + coverage (≥85%) | `python -m pytest --cov=complianceiq` | 282 passing, ~95% |
| Lint | `python -m ruff check src tests` | clean |
| Format | `python -m black --check src tests` | clean |
| Types (strict) | `python -m mypy src/complianceiq/domain src/complianceiq/application` | clean |
| Architecture | `lint-imports` | 4 contracts kept |

The architecture contracts (import-linter) enforce the Clean Architecture
dependency rule: domain imports nothing outward, application imports no adapters,
presentation and infrastructure never import each other.

## Operational surface

- `GET /health`, `GET /health/ready`, `GET /version` — liveness / readiness / build.
- `GET /metrics` — Prometheus exposition (request + AI-usage series). See
  `docs/OBSERVABILITY.md`.
- `GET /docs`, `GET /openapi.json` — the live API contract.
- All `/api/v1/ai/*` capability endpoints are JWT-protected and tenant-scoped
  (`docs/API.md`).

## Deploy-time settings (change from offline defaults)

| Setting | Offline default | Production |
| --- | --- | --- |
| `CIQ_JWT_PUBLIC_KEY` | *(empty → HS256 dev)* | the Core's RSA public **JWK** → RS256 |
| `CIQ_JWT_HS256_SECRET` | `dev-insecure-…` | unset in prod (RS256 used) |
| `CIQ_CORE_CLIENT` | `stub` | `http` (+ `CIQ_CORE_API_BASE_URL`) |
| `CIQ_VECTOR_STORE` | `memory` | `pgvector` (+ apply `migrations/0001_…`) |
| `CIQ_LLM_PRIMARY_PROVIDER` | `fake` | `anthropic` / `openai_compatible` (+ keys) |
| `CIQ_DATABASE_URL` | local placeholder | the managed Postgres URL |
| `CIQ_LOG_JSON` | `false` | `true` |

## Release checklist

- [ ] All five quality gates pass locally and in CI.
- [ ] Grounding eval (`python -m scripts.evaluate_ai`) meets the target grounded/
      abstention thresholds for the release corpus.
- [ ] Production settings above are set; **no dev secret** ships.
- [ ] `migrations/0001_knowledge_pgvector.sql` applied; corpus ingested
      (`python -m scripts.ingest_corpus`).
- [ ] The Core's JWT public key is configured and a smoke token verifies.
- [ ] `/health/ready` returns `200` against real dependencies.
- [ ] `/metrics` scrapes cleanly; dashboards/alerts wired.
- [ ] `CHANGELOG.md` updated; version bumped.

## Known, documented limitations (offline environment)

- The **RS256 verifier** is a dependency-free, standard-library implementation
  (verification only), thoroughly tested but swappable for a library-backed one
  behind the `TokenVerifier` port — see ADR-0011.
- The **pgvector** similarity ranking runs in a real Postgres; the offline suite
  tests the adapter's SQL, mapping, and model guard, not end-to-end ranking — ADR-0011.
