# Changelog

All notable changes to the ComplianceIQ AI Service are documented here. The
format follows [Keep a Changelog](https://keepachangelog.com/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Phase 7: Control mapping & financial risk
- **Control mapping** (`POST /api/v1/ai/map`): a `MappingGraph` + `ControlMapperAgent`
  that map a finding's control to **equivalent controls in other frameworks**,
  grounded like enrichment — each mapped control is a retrieved, *verified* citation
  in a *different* framework than the source; empty retrieval abstains without calling
  the model. New `ControlMapping`/`MappedControl` domain contracts.
- **Financial risk** (`POST /api/v1/ai/financial`): a deterministic domain policy
  `estimate_exposure` computes a monetary **range in MAD** from the finding's severity
  and domain (per-severity base bands × per-domain multiplier; a passing finding →
  `0–0`), returning explicit **assumptions**; a `FinancialGraph` + `FinancialAnalystAgent`
  let the model only *narrate* the pre-computed range (never invent a figure), filling
  the existing `FinancialRiskAssessment` contract.
- Two new prompts (`control_mapping`, `financial_rationale`); `AgentSuite` gains
  `control_mapper` and `financial_analyst`; both wired in `build_agent_suite`.
- Presentation: `MapRequest`/`FinancialRequest` envelopes; `/map` and `/financial`
  endpoints (JWT-protected, tenant-scoped); `docs/API.md`, `docs/AGENTS.md`, and
  ADR-0012 updated.
- New offline tests (deterministic financial model incl. banding/multiplier/pass-zero;
  mapping graph incl. cross-framework filtering + abstain; financial graph incl.
  model-independent numbers + fallback; agents; `/map` and `/financial` endpoints) —
  268 total, ~95% coverage; mypy --strict and the four architecture contracts remain
  clean.

### Added — Phase 6: Core Service client, RS256 auth, pgvector
- **Core Service client**: a `CoreClient` port with a seeded in-process
  `StubCoreClient` (offline default) and an `HttpCoreClient` (httpx) that calls the
  Core's REST findings API, **forwards the caller's JWT** (token pass-through), and
  maps HTTP failures to domain exceptions. Every returned finding is re-checked
  against the caller's tenant (defense-in-depth, rule 1). New endpoint
  `POST /api/v1/ai/enrich/by-ids` fetches findings from the Core and enriches them.
- **RS256 (asymmetric) JWT verification**: `RS256TokenVerifier` — a dependency-free,
  standard-library RSASSA-PKCS1-v1_5/SHA-256 verifier consuming the Core's public
  key as a JWK. HS256 and RS256 now share one claim-validation pipeline
  (`BaseJwtVerifier`); the composition root auto-selects RS256 when a public JWK is
  configured, else HS256. Algorithm pinning, constant-time compare, and the
  forgery/expiry/issuer paths are all covered.
- **PostgreSQL + pgvector store**: `PgVectorStore` implementing the Phase-3
  `VectorStore` port via a thin async `SqlExecutor` seam (real psycopg executor
  imported lazily; in-memory fake in tests), with the embedding-model guard and a
  `migrations/0001_knowledge_pgvector.sql` (extension, table, ivfflat cosine index).
  Selected by `CIQ_VECTOR_STORE=memory|pgvector` (memory default).
- Settings `core_client`, `core_request_timeout_seconds`, `vector_store`; container
  exposes `core_client`; `get_core_client`/`get_bearer_token` dependencies.
  `AgentSuite` unchanged. `requirements.txt` adds langgraph (Phase 4) and optional
  `psycopg[binary,pool]`; migrations shipped in the Docker image; `.env.example`
  extended. ADR-0010 (Core client + token pass-through) and ADR-0011 (stdlib RS256
  + pgvector behind an executor seam).
- New offline tests (RS256 verifier incl. forgery/alg-pin; Core stub + HTTP adapter
  via `MockTransport`; pgvector SQL/mapping/guard via a fake executor; RS256-wired
  app; Core-fetch endpoint) — 251 total, ~94% coverage; mypy --strict and the four
  architecture contracts remain clean.

### Added — Phase 5: Presentation / HTTP API
- **AI capability endpoints** under `/api/v1/ai`, exposing the Phase-4 agents:
  `POST /enrich` (→ `[EnrichedFinding]`), `POST /ask` (→ `CopilotAnswer`),
  `POST /remediate` (→ `RemediationProposal`, `approved:false`), `POST /correlate`
  (→ grounded narrative), `POST /report` (→ `ReportDraft`). Response shapes are the
  domain contracts themselves (no drift); only thin request envelopes are added.
- **Authentication seam**: a `TokenVerifier` port with a dependency-free **HS256**
  verifier (Phase 5, dev/testing) that validates signature + `exp`/`nbf`/`iss`/`aud`
  and projects `sub`/`tenant_id`/`roles` into an `AuthContext`. Algorithm is pinned
  (rejects the `none`-downgrade / algorithm-confusion attack), signature comparison
  is constant-time, and errors never leak the token or secret. Phase 6 swaps in the
  Core's asymmetric RS256/ES256 key behind the same port.
- **Tenant isolation at the boundary**: every AI endpoint is JWT-protected; any
  finding whose `tenant_id` differs from the token's is rejected with
  `403 tenant_isolation_violation` (rule 1).
- `Container` protocol extended with `agents` and `token_verifier`; `AgentSuite`
  moved into the application layer so presentation can depend on it without crossing
  into composition. New `get_auth_context`/`get_agents` FastAPI dependencies.
- `CIQ_JWT_HS256_SECRET` setting (+ `.env.example`); ADR-0009; `docs/API.md`.
- New tests (auth verifier incl. security-critical rejections; end-to-end endpoint
  tests over the fake provider + sample corpus) — 218 total, ~95% coverage;
  mypy --strict and the four architecture contracts remain clean.

### Added — Phase 4: LangGraph Workflows & Agents
- Four explicit **LangGraph** state graphs (typed state, injected bound-method
  nodes, declared edges, per-node timeout, and a `trace` channel): `EnrichmentGraph`
  (Finding → grounded `EnrichedFinding`), `CopilotGraph` (question → `CopilotAnswer`),
  `RemediationGraph` (Finding → validated, never-applied `RemediationProposal`),
  and `ReportGraph` (enriched findings → `ReportDraft`).
- **Grounding made structural**: the *abstain* branch is a first-class edge (no
  model call on empty retrieval); `verify_citations` drops any citation not in the
  retrieved sources; `citation_verified` is authoritative. Domain policies added:
  `grounding` (cite/verify/abstain) and `iac_safety` (static over-permissive-IaC
  scan; unsafe remediation → `WorkflowError`).
- **Prompts as versioned assets**: `PromptTemplate` (pure, strict `{{ var }}`
  rendering), `.prompt` file loader (dependency-free frontmatter), and a
  `PromptRegistry` serving the latest version by default; five bundled prompts.
  Every generation is attributable to an `id@version` key.
- **Bounded, tool-using agents**: `BoundedAgent` + per-run `ToolSession` enforcing
  a tool allow-list, iteration and wall-clock budgets, loop detection, typed
  argument validation, and **injection scanning of tool output** (defence-in-depth
  on top of the gateway). Typed `Tool`/`ToolRegistry` and the built-in
  `search_corpus` tool over the retrieval stack.
- Four agents: `ComplianceAnalystAgent`, `RemediationEngineerAgent`,
  `ReportWriterAgent` (each wrapping a graph), and `RiskAnalystAgent` (exercises
  the bounded tool layer to correlate findings into one grounded narrative).
- New domain entities `CopilotAnswer` and `ReportDraft`; new exceptions
  `PromptError` and `WorkflowError`.
- Composition-root wiring (`AgentSuite`, `build_agent_suite`), prompt/agent
  settings, and `prompts/` shipped in the Docker image.
- ADR-0007 (LangGraph workflows) and ADR-0008 (bounded agents); `docs/AGENTS.md`
  and `docs/PROMPTS.md`.
- New offline, deterministic tests (workflows, agents, guardrails, grounding, IaC
  safety, prompts, tools) — 191 total, ~95% coverage; mypy --strict and the four
  architecture contracts remain clean.

### Added — Phase 3: Knowledge Base & RAG
- Knowledge-base domain model (`CorpusDocument` → `ControlSummary`; `Chunk`,
  `EmbeddedChunk`, `ScoredChunk`, `RetrievalQuery`/`Result`, `AssembledContext`,
  metadata + filters) — the corpus is shared, not tenant-scoped.
- Structure-aware chunking (one control ≈ one chunk; overlap split for long
  controls; deterministic, idempotent ids).
- `Embedder`/`VectorStore`/`KeywordIndex`/`Reranker` ports with offline in-memory
  adapters: cosine vector store (with the **embedding-model-identity guard**),
  BM25 keyword index, and a deterministic lexical reranker.
- Hybrid retrieval: semantic + lexical + Reciprocal Rank Fusion + reranking + MMR
  diversity + score-threshold abstention, with metadata pre-filtering.
- Context assembly: token-budgeted, de-duplicated, numbered blocks with citations.
- Ingestion service (chunk → embed via the gateway → upsert; idempotent; versioned
  with `replace`); corpus loaders; `scripts/ingest_corpus.py` CLI; startup autoload.
- Retrieval evaluation harness (recall@k, precision@k, MRR, hit-rate) + golden set.
- Copyright-compliant sample corpus (NIST CSF, Loi 05-20, DNSSI, ISO 27001, SOC 2).
- Vector-store readiness probe; knowledge settings; `.env.example` extended;
  corpus shipped in the Docker image.
- ADR-0005 (in-memory stores now, pgvector in Phase 6) and ADR-0006 (hybrid
  retrieval + structure-aware chunking); `docs/RAG.md`; corpus README.
- New tests (143 total, ~94% coverage); mypy --strict and the four architecture
  contracts remain clean.

### Added — Phase 2: AI Gateway & Providers
- Provider-agnostic `LLMProvider` port (`generate`/`stream`/`embed`/`count_tokens`)
  and a full domain LLM vocabulary (messages, model specs, requests, responses,
  usage) with no vendor types.
- `AIGateway` — a single choke point enforcing, per call: per-tenant rate
  limiting and spend budget, prompt-injection scanning, tenant-scoped
  content-addressed caching, task-based model routing with a fallback chain,
  retries (exponential backoff + full jitter), per-call timeouts, circuit
  breaking, and token/cost accounting.
- Three provider adapters: **Anthropic (Claude)** primary, an **OpenAI-compatible**
  secondary (with embeddings), and a deterministic **fake** default (offline).
- In-memory adapters for the gateway ports (token-bucket rate limiter, TTL cache,
  usage ledger, async sleeper) — each swappable for a Redis/Postgres version.
- Rule-based prompt-injection detection policy (pure, deterministic) plus
  untrusted-content delimiting; enforced at the gateway (non-negotiable rule 4).
- Provider health probe registered with readiness; `/health/ready` now reports
  each configured provider.
- Gateway configuration surfaced via settings; `.env.example` extended.
- ADR-0003 (AI gateway & provider abstraction), ADR-0004 (prompt-injection
  defence). New tests across domain/application/infrastructure (114 total, 94%
  coverage); mypy --strict and the four architecture contracts remain clean.

### Added — Phase 1: Foundation
- Clean Architecture skeleton with four layers (domain, application,
  infrastructure, presentation) and a composition root.
- Domain model implementing the Section 6 data contracts: `NormalizedResource`,
  `Finding`, `EnrichedFinding`, `ComplianceScore`, `CorrelatedRisk`,
  `FinancialRiskAssessment`, `RemediationProposal`, `AuthContext`, `Page[T]`,
  plus `Citation` and the shared enums.
- Structural enforcement of two non-negotiable rules:
  `RemediationProposal.approved` is forced to `False`; a tenant-isolation policy
  guard with dedicated security tests.
- Typed domain exception hierarchy and a single presentation-layer mapping to a
  consistent `ErrorEnvelope`.
- Configuration via `pydantic-settings` with `SecretStr` secret hygiene.
- Structured JSON logging (structlog) with correlation-ID propagation.
- Health/readiness/version endpoints; readiness aggregates dependency probes.
- Request-size-limit and correlation-ID ASGI middleware.
- Multi-stage, non-root Dockerfile; docker-compose stack (AI service + pgvector
  Postgres).
- CI pipeline (ruff, black, mypy --strict, import-linter, pytest+coverage,
  dependency audit, container build) and pre-commit hooks.
- Automated Clean Architecture enforcement via import-linter contracts.
- Initial documentation set (architecture, ADRs, assumptions, compliance notes).

[Unreleased]: https://example.com/complianceiq/ai-service/tree/main
