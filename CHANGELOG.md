# Changelog

All notable changes to the ComplianceIQ AI Service are documented here. The
format follows [Keep a Changelog](https://keepachangelog.com/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
