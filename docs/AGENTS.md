# Workflows & Agents (Phase 4)

This document describes ComplianceIQ's AI **workflows** (LangGraph state graphs)
and the **bounded agents** that expose them, plus the guardrails that keep
tool-using agents safe. See ADR-0007 (workflows) and ADR-0008 (agents) for the
decisions behind the design.

## Layered picture

```
presentation ──▶ AgentSuite ──▶ Agents ──▶ Graphs ──▶ AI Gateway ──▶ providers
                                  │            │
                                  └─▶ Tools ───┘ (search_corpus over retrieval)
```

Everything below lives in the **application** layer. The domain owns the pure
policies the workflows enforce (grounding, IaC safety, prompt-injection scanning);
LangGraph never leaks into the domain (enforced by the import-linter contracts).

## The four workflows (LangGraph graphs)

Each workflow is an explicit `StateGraph`: typed state, nodes that are injected
bound methods, declared edges (including the grounding *abstain* branch), a
per-node timeout, and a `trace` channel that accumulates one `TraceEvent` per node.

| Graph | Flow | Input → Output | Grounding behaviour |
| --- | --- | --- | --- |
| `EnrichmentGraph` | `retrieve → (empty? abstain : generate)` | `Finding` → `EnrichedFinding` | Abstains (no model call) on empty retrieval; attaches only **verified** citations |
| `CopilotGraph` | `retrieve → (empty? abstain : respond)` | question → `CopilotAnswer` | Same discipline; `abstained`/`citation_verified` flags are authoritative |
| `RemediationGraph` | `retrieve → generate → validate` | `Finding` → `RemediationProposal` | `approved=False` always (rule 2); Terraform statically validated, unsafe → `WorkflowError` |
| `ReportGraph` | `summarize → generate` | `[EnrichedFinding]` → `ReportDraft` | Factual severity counts computed in code; summary told to invent nothing |

Shared node concerns live in `application/graphs/_common.py`:

- `SYSTEM_GROUNDED` — the system instruction pinning the model to numbered
  SOURCES, forbidding instructions hidden in untrusted content, mandating `[n]`
  citations, and prescribing the exact abstention sentence.
- `traced_node(...)` — wraps a node with a hard timeout (`WorkflowError` on
  expiry), structured logging, and trace emission.
- `retrieve_and_assemble(...)` / `finding_summary(...)` — shared retrieval and
  finding-rendering helpers so the model and the retriever see the same text.

**Grounding is structural.** The abstain path is a declared edge taken when the
assembled context is empty; it returns `ABSTENTION_TEXT` and never calls the
model. On the generate path, `verify_citations(claimed, available)` drops any
citation not present in the retrieved sources, and `citation_verified` is
`True` only when every claim verified **and** the context was non-empty.

## The bounded agents

Agents are the uniform entry point per capability. Each subclasses `BoundedAgent`
and is exposed on the `AgentSuite` (wired in the composition root).

| Agent | Method | Wraps / uses | Free tools granted |
| --- | --- | --- | --- |
| `ComplianceAnalystAgent` | `analyze(finding, auth) → EnrichedFinding` | `EnrichmentGraph` | none |
| `RemediationEngineerAgent` | `propose(finding, auth) → RemediationProposal` | `RemediationGraph` | none |
| `ReportWriterAgent` | `write(findings, auth) → ReportDraft` | `ReportGraph` | none |
| `RiskAnalystAgent` | `correlate(findings, auth) → str` | `search_corpus` tool + gateway synthesis | `search_corpus` |

`CopilotGraph` is also exposed on the suite (`agents.copilot`) for direct Q&A.

## The guardrails (`ToolSession`)

Every tool call an agent makes goes through a per-run `ToolSession` that enforces,
in order:

1. **Allow-list** — the tool must be in the agent's granted set, else
   `WorkflowError`. Granting an *unregistered* tool fails fast at construction.
2. **Wall-clock budget** — elapsed time (against the injected `Clock`) must be
   under `AgentBudget.wall_clock_seconds`, else `WorkflowError`.
3. **Iteration budget** — at most `AgentBudget.max_iterations` calls, else
   `WorkflowError`.
4. **Loop detection** — an identical `(tool, args)` signature seen twice →
   `WorkflowError`.
5. **Typed-argument validation** — arguments are validated against the tool's
   Pydantic schema; invalid input → `ValidationError`.
6. **Output injection scan** — the tool's returned text is scanned; a signal at or
   above the severity threshold (default `HIGH`) → `UnsafeContentError`.

Budgets are **per run**: `agent.session()` opens a fresh `ToolSession`, so state
never leaks between concurrent requests.

## Tools

A `Tool` has a name, a description, a Pydantic `args_model`, and an async handler
returning **text**. The `ToolRegistry` is the allow-list source. The built-in
`search_corpus` tool (`SearchCorpusArgs`: `query`, `top_k`, optional `framework`)
runs the hybrid retriever + context assembler and returns the assembled,
citation-numbered context — which the agent layer then injection-scans before
trusting.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `prompts_dir` | `prompts` | Directory of versioned `.prompt` assets |
| `agent_max_iterations` | `8` | Default per-run tool-call cap |
| `agent_wall_clock_seconds` | `60.0` | Default per-run time cap |

## Testing

All workflows and agents are tested **offline and deterministically** with a
duck-typed `FakeGateway`, the stub embedder, and the sample corpus (`tests/
ai_helpers.py`). Coverage includes each grounding branch (abstain, verified
citations), IaC-safety rejection, and every guardrail (allow-list, iteration and
wall-clock budgets, loop detection, injected tool output).
