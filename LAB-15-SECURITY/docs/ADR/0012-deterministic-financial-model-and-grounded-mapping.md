# ADR-0012: Deterministic financial model, and grounded control mapping

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

Phase 7 adds the last two AI capabilities from the build spec: **control mapping**
(`/ai/map`) and **financial risk** (`/ai/financial`). Each raises a "who is allowed
to produce this number/claim?" question that the grounding and no-hallucination
rules answer differently.

## Decision

### Financial exposure is computed in code, not by the model

Money is the one output an auditor will challenge line by line, and a language
model's figures are unverifiable. So the monetary range is produced by a **pure,
deterministic domain policy** (`estimate_exposure`): a per-**severity** base band
in MAD, scaled by a per-**domain** multiplier, rounded to whole dirham, with the
**assumptions returned alongside** the number. The model's only job (the
`narrate` node of `FinancialGraph`) is to explain that pre-computed range in
prose, under a system instruction forbidding it to invent, widen, narrow, or add
any figure. This is the same "facts in code, prose from the model" split the
report graph uses — here applied to money, where it matters most.

Two deliberate choices reinforce auditability:
- The output is always a **range**, never a point estimate — precision we cannot
  justify would be dishonest.
- A **passing** finding yields `0–0` exposure with an explicit assumption, rather
  than a spurious band.

The bands and multipliers are explicit constants, unit-tested, and easy to tune;
they are planning figures (they exclude regulatory fines and reputational loss,
stated in the assumptions).

### Control mapping is grounded exactly like enrichment

`/ai/map` maps a finding's control to equivalents in *other* frameworks. A model
asked this unaided would happily invent plausible cross-references — the classic
hallucination that discredits a compliance product. So `MappingGraph` reuses the
grounding discipline: retrieve corpus controls, and build the equivalence list
**only from verified citations in a framework different from the source**. Nothing
that wasn't retrieved and verified can appear as a mapping; an empty retrieval
abstains without calling the model, and `citation_verified` reports the outcome.

### Alternatives considered

- **Let the model estimate the cost.** Rejected: unverifiable, non-reproducible,
  and indefensible in an audit. A transparent model beats a confident guess.
- **A single point estimate.** Rejected: implies false precision; a range with
  assumptions is honest.
- **Let the model list cross-framework mappings freely.** Rejected: that's the
  hallucination we exist to prevent; mappings must be retrieved-and-verified.

## Consequences

- Financial numbers are deterministic, reproducible, and reviewable (challenge the
  band/multiplier, not a black box); tests assert exact figures independent of the
  model's text.
- Control mappings carry the same verified-citation guarantee as every other
  grounded output; `citation_verified` is authoritative.
- Both capabilities are new graphs + bounded agents + endpoints, wired like the
  Phase-4 ones — no change to the guardrail, grounding, or tenancy machinery.
- The financial bands are Morocco-context planning figures; tuning them is a
  constant change in one policy, fully covered by tests.
