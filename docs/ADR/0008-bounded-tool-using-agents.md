# ADR-0008: Bounded, tool-using agents with enforced guardrails

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

Some capabilities benefit from an agent that calls tools on demand — e.g.
correlating a set of findings by looking each one up in the knowledge base. But a
tool-using agent is a liability if it is unbounded: a bug or an adversarial input
could make it loop forever (burning time and money), call tools it should not, or
trust poisoned tool output as if it were an instruction. "No red-team / no
autonomous change" (rules 2 and 8) and prompt-injection defence (rule 4) all bear
directly on this layer.

## Decision

Introduce a `BoundedAgent` base class whose every tool call goes through a
per-run `ToolSession` that enforces **five** guardrails, by construction:

1. **Allow-list.** An agent is granted a *subset* of the registered tools and can
   call nothing else. Granting an unregistered tool fails fast at construction.
2. **Iteration budget.** A hard cap on the number of tool calls per run
   (`AgentBudget.max_iterations`).
3. **Wall-clock budget.** A hard cap on elapsed time per run, measured against the
   injected `Clock` (deterministic in tests).
4. **Loop detection.** The same tool called with identical arguments twice is
   treated as a non-terminating loop and stopped.
5. **Output scanning.** Every tool result is scanned for prompt injection
   (`scan_for_injection`); output at or above the severity threshold raises
   `UnsafeContentError` before the agent can trust it — defence-in-depth on top of
   the gateway's input scanning (ADR-0004).

Tools are **typed**: a `Tool` carries a Pydantic argument schema, so malformed
calls are rejected before the handler runs, and tools return **text** (never live
objects), keeping the trust boundary narrow. A `ToolSession` holds all per-run
state (iteration count, start time, seen-call signatures), so budgets are per-run
and never leak between concurrent requests.

Four concrete agents ship: three (`ComplianceAnalystAgent`,
`RemediationEngineerAgent`, `ReportWriterAgent`) wrap a single graph and grant no
free tools; `RiskAnalystAgent` exercises the bounded tool layer directly, calling
`search_corpus` (allow-listed) once per finding under its budget before
synthesising one grounded narrative.

### Alternatives considered

- **Let a model plan and call tools freely (ReAct-style, unbounded).** Rejected:
  no hard stop on iterations/time, no allow-list, and tool output implicitly
  trusted — every failure mode we must prevent.
- **Trust tool output because it came from our own corpus.** Rejected: the corpus
  is untrusted content by policy; a poisoned document must not become an
  instruction. Output scanning stays on.
- **Global budgets on a shared agent instance.** Rejected: budgets must be
  per-run; a `ToolSession` per run is the isolation boundary.

## Consequences

- Every tool-using run is bounded in calls and time, restricted to an explicit
  tool set, protected against loops, and defended against injected tool output —
  all enforced centrally, not re-implemented per agent.
- Agents are a uniform entry point per capability for the presentation layer, and
  richer tool-using behaviour can be added later without weakening the guarantees.
- A little more indirection (registry, session) than calling a graph directly;
  the safety properties justify it.
