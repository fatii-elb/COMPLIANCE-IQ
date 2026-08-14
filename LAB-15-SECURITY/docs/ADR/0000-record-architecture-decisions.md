# ADR-0000: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

This is a graduation project that must be defended before software architects
and security professionals. Significant technical choices need a durable,
reviewable rationale — not tribal knowledge in someone's head.

## Decision

We record every significant architectural decision as an Architecture Decision
Record (ADR) in `docs/ADR/`, using the lightweight Michael-Nygard format:
Context → Decision → Consequences. ADRs are immutable once accepted; a reversal
is a new ADR that supersedes the old one.

## Consequences

- The "why" behind the codebase is auditable and presentable at the defense.
- New contributors (and the examiner) can reconstruct the reasoning quickly.
- A small ongoing discipline: non-trivial choices come with an ADR.
