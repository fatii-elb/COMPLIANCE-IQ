# ADR-0001: Clean Architecture with automated enforcement

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The AI Service integrates many volatile technologies: LLM providers, a vector
store, a relational database, an external Core API, and a web framework. If
business rules (grounding, tenant isolation, risk scoring) become entangled with
any of these, the system becomes hard to test, hard to reason about, and locked
to today's vendors. It must also be defensible: reviewers will ask "how do you
keep the core clean?"

## Decision

Adopt **Clean Architecture** with four layers (domain, application,
infrastructure, presentation) and a strict inward dependency rule. The domain
depends only on the standard library and Pydantic. All external capabilities are
expressed as **ports** (interfaces) in the domain and implemented as **adapters**
in infrastructure (Ports & Adapters / Hexagonal).

Crucially, the dependency rule is **enforced automatically** by import-linter
contracts (`.importlinter`) run in CI and pre-commit — not left to reviewer
diligence.

### Alternatives considered

- **Layered-but-unenforced / "pragmatic" structure.** Rejected: architecture
  that is not enforced decays under deadline pressure. The enforcement is the
  point.
- **Framework-centric (FastAPI-first) structure**, e.g. business logic in
  routers/services coupled to FastAPI and SQLAlchemy. Rejected: it couples the
  core to the delivery mechanism and the ORM, making unit testing require a web
  server and a database, and making a provider swap a rewrite.
- **Full DDD with aggregates/repositories/domain events everywhere.** Deferred:
  we take DDD's tactical patterns where they pay off (value objects, entities,
  policies, ports) without ceremony that this scope does not need.

## Consequences

- The domain is unit-testable with no I/O; provider/DB choices are swappable.
- A new engineer can learn "what may depend on what" from one config file.
- Small cost: some indirection (ports, a composition root, a structural
  container protocol to keep presentation and infrastructure independent).
- Pydantic is deliberately allowed in the domain: it provides validation and
  immutability at the boundary with no framework lock-in, and keeps contracts
  DRY. (This is why the flake8-type-checking lint rules are disabled — Pydantic
  needs annotations available at runtime.)
