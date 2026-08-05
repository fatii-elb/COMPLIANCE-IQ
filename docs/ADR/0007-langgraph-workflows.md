# ADR-0007: LangGraph state graphs for multi-step AI workflows

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

The AI capabilities are not single model calls — they are multi-step processes
with branches. Enriching a finding is *retrieve → (nothing found? abstain :
generate → verify citations)*; remediation is *retrieve → generate → statically
validate*; a copilot answer must abstain when retrieval is empty. Expressed as
ad-hoc `async` functions with `if`/`else`, this logic is hard to inspect, the
branches (especially the grounding *abstain* branch) are buried, individual steps
are awkward to unit-test, and there is no uniform trace of a run.

## Decision

Model each workflow as an explicit **LangGraph `StateGraph`**: typed state, nodes
that are bound methods of a graph class, and declared edges — including the
conditional *abstain* edges as first-class transitions.

- **Typed state.** Each graph has a `TypedDict` state; the `trace` channel uses an
  `operator.add` reducer so every node appends one structured `TraceEvent`.
- **Nodes are injected bound methods.** Dependencies (retriever, assembler,
  gateway, prompt registry, clock) are constructor-injected, so each node is unit
  tested in isolation and the whole graph runs offline against a fake gateway.
- **Cross-cutting node wrapper.** `traced_node` wraps every node with a hard
  per-node timeout (surfaced as `WorkflowError`), structured logging, and trace
  emission — one place, applied uniformly.
- **Checkpointer.** Graphs compile with a `MemorySaver`, giving each run an
  isolated thread and a checkpoint of state at each step.
- **Grounding lives at the edges.** The *abstain* path is a declared edge taken
  when the assembled context is empty; it returns the canonical abstention answer
  and **never calls the model**. On the *generate* path, citations are verified
  against the retrieved sources before they are attached.

Four graphs: `EnrichmentGraph`, `CopilotGraph`, `RemediationGraph`, `ReportGraph`.
LangGraph is used **only in the application layer** — the import-linter contracts
still forbid the domain from importing it.

### Alternatives considered

- **Plain async function chains.** Rejected: branches and abstention become buried
  `if`s, steps are coupled, and there is no uniform trace or timeout.
- **A generic agent framework driving the whole flow with an LLM planner.**
  Rejected for these fixed pipelines: non-deterministic control flow is the wrong
  tool when the steps are known and must be auditable. (Bounded, tool-using agents
  are introduced separately — see ADR-0008 — for the genuinely open-ended task.)

## Consequences

- Every workflow is inspectable (nodes + edges), each node independently testable,
  and each run emits a trace and is bounded by per-node timeouts.
- The grounding guarantee is structurally visible: abstention is an edge, and the
  model is never called when there is nothing to ground on.
- A small amount of graph-wiring boilerplate per workflow, and a LangGraph
  dependency in the application layer (accepted; it earns its place).
- Node names must not collide with state keys (a LangGraph rule); the copilot
  graph's answer node is named `respond` for exactly this reason.
