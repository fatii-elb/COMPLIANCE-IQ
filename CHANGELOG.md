# Changelog

All notable changes to the ComplianceIQ AI Service are documented here. The
format follows [Keep a Changelog](https://keepachangelog.com/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
