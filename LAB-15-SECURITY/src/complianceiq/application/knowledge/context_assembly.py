"""Context assembly — turn retrieved chunks into a citable prompt block.

Retrieval gives us ranked chunks; generation needs them as a single text block
that (a) fits the token budget, (b) contains no duplicates, and (c) is labelled so
every sentence the model later writes can be traced to a source. This service does
exactly that, emitting both the packed ``text`` and the ordered
:class:`Citation`s — the raw material for the grounding guarantee (rule 3).
"""

from __future__ import annotations

from complianceiq.domain.knowledge.chunking import estimate_tokens
from complianceiq.domain.knowledge.queries import AssembledContext, RetrievalResult
from complianceiq.domain.value_objects.citation import Citation


class ContextAssembler:
    """Packs retrieved chunks into a token-budgeted, cited context block."""

    def assemble(self, result: RetrievalResult, *, token_budget: int) -> AssembledContext:
        """Assemble ``result`` into an :class:`AssembledContext`.

        Chunks are added in ranked order, skipping content-hash duplicates, until
        adding the next chunk would exceed ``token_budget`` (at least one chunk is
        always included if any were retrieved, so a tight budget still yields the
        top result). Each block is numbered so the model can reference ``[1]``,
        ``[2]`` and we can map those back to citations.
        """
        blocks: list[str] = []
        citations: list[Citation] = []
        chunk_ids: list[str] = []
        seen_hashes: set[str] = set()
        used_tokens = 0

        for scored in result.chunks:
            chunk = scored.chunk
            if chunk.content_hash in seen_hashes:
                continue

            marker = len(blocks) + 1
            meta = chunk.metadata
            block = (
                f"[{marker}] {chunk.content}\n"
                f"(Source: {meta.source} · {meta.framework.value} {meta.control_id})"
            )
            block_tokens = estimate_tokens(block)

            # Budget check — but always include the first (top-ranked) chunk.
            if blocks and used_tokens + block_tokens > token_budget:
                break

            blocks.append(block)
            chunk_ids.append(chunk.id)
            seen_hashes.add(chunk.content_hash)
            used_tokens += block_tokens
            citations.append(
                Citation(
                    framework=meta.framework,
                    control_id=meta.control_id,
                    reference=f"{meta.source} · {meta.title}",
                )
            )

        text = "\n\n".join(blocks)
        return AssembledContext(
            text=text,
            citations=citations,
            chunk_ids=chunk_ids,
            token_estimate=estimate_tokens(text),
        )
