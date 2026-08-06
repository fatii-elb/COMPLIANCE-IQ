# Changelog

All notable changes to the ComplianceIQ AI Service are documented here. The
format follows [Keep a Changelog](https://keepachangelog.com/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
