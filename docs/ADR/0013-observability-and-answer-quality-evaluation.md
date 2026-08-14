# ADR-0013: Observability behind a port, and measured answer quality

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

Phases 1–7 made the system *do* the right things; Phase 8 must make it *provably*
run well in production. Two gaps remained: there was no metrics surface an operator
could scrape (only logs and per-run traces), and answer **quality** — especially
grounding, the product's core guarantee — was asserted by unit tests but never
*measured* as an aggregate, gate-able number.

## Decision

### Metrics behind a `MetricsSink` port

Add a minimal `MetricsSink` domain port with two primitives — `increment` (counters)
and `observe` (value distributions) — and an in-memory adapter that aggregates
counters and lightweight summaries and renders the **Prometheus text format**. A
`MetricsMiddleware` records `http_requests_total` and `http_request_duration_ms` per
**matched route template** (bounded cardinality) and is best-effort (a metrics
failure never breaks a request). A `GET /metrics` endpoint exposes the series plus
`ai_gateway_*` gauges derived from the existing usage ledger.

Keeping metrics behind a port means a real exporter (Prometheus client /
OpenTelemetry) swaps in later with no caller change — the same discipline as every
other port. `/metrics` is operational and unauthenticated (like the health probes)
and carries only **aggregates**, never per-tenant data, so it leaks nothing.

### Answer quality is measured, not hoped

Add a **grounding evaluation** harness (`GroundingEvaluator`) alongside the Phase-3
retrieval eval: given golden findings with their expected citations, it runs the
enrichment capability and computes grounded rate, abstention rate, and citation
precision/recall. It's pure orchestration over an injected `enrich` function, so it
runs offline in CI and via `scripts/evaluate_ai`. Grounding — "cite, verify,
abstain" (rule 3) — thus becomes a number a release can gate on, not a claim.

### A consolidated release-readiness view

Add `docs/RELEASE_READINESS.md` mapping every non-negotiable rule to where it is
enforced and how it is verified, plus the quality gates, operational endpoints, and
the deploy-time settings that must change from their offline defaults. It is the
single sign-off document.

### Alternatives considered

- **Log-only observability.** Rejected: operators need scrapeable metrics and SLO
  latency/throughput series, not just log greps.
- **A heavy metrics dependency now (OpenTelemetry SDK).** Rejected for the offline
  build: the port lets us ship a stdlib in-memory sink and swap the real exporter in
  later, unchanged above the port.
- **Trusting unit tests for grounding quality.** Rejected: unit tests check
  individual behaviours; only an aggregate eval over a golden set tells you the
  *rate* at which the system grounds and abstains correctly.

## Consequences

- The service is scrapeable (`/metrics`), and request + AI-cost signals are visible
  without new infrastructure.
- Grounding and retrieval quality are **measured**, offline, and gate-able in CI.
- Observability and evaluation both sit behind ports/injected functions, so nothing
  above them changes when a production backend is introduced.
- One release-readiness document ties rules, gates, and deploy settings together.
