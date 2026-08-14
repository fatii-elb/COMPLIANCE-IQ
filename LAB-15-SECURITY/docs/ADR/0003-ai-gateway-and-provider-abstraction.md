# ADR-0003: A single AI gateway over a provider-agnostic port

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

The system makes many kinds of model calls (explanation, classification,
reranking, embeddings) across features, tenants, and — eventually — multiple
vendors. Every such call needs the same cross-cutting concerns: rate limiting,
per-tenant budget, retries, timeouts, circuit breaking, caching, cost accounting,
and prompt-injection scanning. If each caller wired these itself, the concerns
would be implemented inconsistently and the code would be locked to one vendor's
SDK.

## Decision

1. Define a **provider-agnostic `LLMProvider` port** in the domain
   (`generate` / `stream` / `embed` / `count_tokens`). No vendor type crosses it.
2. Route **all** model calls through a single **`AIGateway`** use case that
   enforces every cross-cutting concern in one place (the "choke point").
3. Select models by **task class** via a data-driven **routing table** with a
   **fallback chain**; provider capabilities and costs are declared as
   `ModelSpec` data, not hardcoded conditionals.
4. Ship three adapters: **Anthropic (Claude)** primary, an **OpenAI-compatible**
   secondary (also serving embeddings), and a deterministic **fake** default so
   the whole system runs and is fully tested offline.

## Alternatives considered

- **Call SDKs directly from each feature.** Rejected: duplicated, inconsistent
  cross-cutting logic; vendor lock-in; untestable without network/keys.
- **A LangChain-style universal client as the abstraction.** Rejected as the
  *boundary*: we keep the port minimal and our own so domain code never depends
  on a third-party abstraction's types. (LangChain/LangGraph are used where they
  add value — orchestration, Phase 4 — not as the provider boundary.)
- **One model for everything.** Rejected: reasoning-grade models are wasteful for
  classification/reranking; task-based routing controls cost/quality centrally.

## Consequences

- Adding a provider is a small adapter + a routing entry; no caller changes.
- Every model call is uniformly rate-limited, budgeted, retried, cached, and
  cost-accounted, and its untrusted input is injection-scanned.
- The gateway depends only on ports, so it is tested end-to-end with the fake
  provider and in-memory port fakes (no network in the default suite).
- In-memory adapters (rate limiter, cache, ledger) are correct for a single
  instance; Redis/Postgres-backed versions implement the same ports later with no
  gateway change.
