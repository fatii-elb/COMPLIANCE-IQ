# ADR-0006: Hybrid retrieval with structure-aware chunking

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Retrieval quality is the single biggest lever on answer quality in a RAG system —
"when an answer is wrong, check retrieval first." Two design choices dominate it:
how we split the corpus into chunks, and how we search them.

## Decision

**Structure-aware chunking.** Chunk the corpus **by control/article** — one
control becomes one chunk — rather than by fixed-size windows. A retrieved chunk
therefore maps cleanly to a single citable rule, which is exactly what the
grounding guarantee needs. Only when a control's text exceeds the embedding budget
do we split it into overlapping sub-chunks so no rule is silently truncated.

**Hybrid retrieval.** Combine two complementary searches and sharpen the result:
1. **Semantic** (vector cosine similarity) — matches meaning across different
   wording.
2. **Lexical** (BM25) — matches exact identifiers and rare terms semantic search
   blurs (`PR.AC-4`, `article 23`).
3. **Reciprocal Rank Fusion** merges the two rankings using ranks, not raw scores
   (robust to their different scales).
4. **Reranking** re-scores fused candidates by deep query relevance (a
   cross-encoder in production; a deterministic lexical reranker offline).
5. **MMR** trims to a diverse, non-redundant final set.
6. A **score threshold** enforces abstention: nothing relevant → empty result →
   the caller declines to answer.

Metadata filters are pushed into each search so irrelevant frameworks are never
ranked.

### Alternatives considered

- **Fixed-size chunking.** Rejected: cuts rules in half, blurs citations, and
  retrieves fragments that don't map to a single control.
- **Semantic-only retrieval.** Rejected: misses exact identifiers and rare terms;
  lexical search is cheap insurance against that class of miss.
- **Lexical-only retrieval.** Rejected: misses paraphrases and conceptual matches
  that don't share words.
- **No reranking / no MMR.** Rejected: first-pass rankings are noisy, and without
  MMR the top-k is often near-duplicates.

## Consequences

- One retrieved chunk = one citable rule, supporting verified citations.
- The pipeline is measurable in isolation (retrieval evaluation: recall@k,
  precision@k, MRR, hit-rate) so retrieval failures are distinguishable from
  generation failures.
- More moving parts (two searches, fusion, rerank, MMR), all pure and unit-tested,
  and all swappable behind ports (e.g. a real cross-encoder reranker).
