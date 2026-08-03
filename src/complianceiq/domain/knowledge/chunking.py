"""Structure-aware chunking (pure domain service).

Naive RAG chops text into fixed-size windows, which cuts rules in half and blurs
retrieval. We chunk **by structure** instead: one control/article becomes one
chunk, so a retrieved chunk maps cleanly to a single citable rule ("one chunk ≈
one rule"). Only when a single control's text is too large for the embedding
budget do we split it into overlapping sub-chunks, so no rule is silently
truncated.

Everything here is pure and deterministic: the same document and version always
produce the same chunks with the same ids, which is what makes re-ingestion
idempotent.
"""

from __future__ import annotations

import hashlib
import re

from complianceiq.domain.knowledge.chunks import Chunk
from complianceiq.domain.knowledge.documents import ControlSummary, CorpusDocument
from complianceiq.domain.knowledge.metadata import ChunkMetadata

# ~4 characters per token (see Phase 2, Chapter 3). Used only for budgeting.
_CHARS_PER_TOKEN = 4
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def estimate_tokens(text: str) -> int:
    """Rough token estimate for budgeting (≈ 4 chars/token)."""
    return max(1, len(text) // _CHARS_PER_TOKEN) if text else 0


def _content_hash(text: str) -> str:
    """Stable SHA-256 hex digest of ``text`` (for ids and dedup)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _render(control: ControlSummary, part: str) -> str:
    """Compose the embeddable text for a control (title + summary [+ keywords])."""
    lines = [f"{control.control_id} — {control.title}", part]
    if control.keywords:
        lines.append("Keywords: " + ", ".join(control.keywords))
    return "\n".join(lines)


def _split_summary(summary: str, max_tokens: int, overlap_sentences: int) -> list[str]:
    """Split an over-long summary into overlapping sentence groups."""
    if estimate_tokens(summary) <= max_tokens:
        return [summary]

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(summary) if s.strip()]
    if not sentences:
        return [summary]

    groups: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*current, sentence])
        if current and estimate_tokens(candidate) > max_tokens:
            groups.append(" ".join(current))
            # Start the next group with an overlap tail for context continuity.
            current = current[-overlap_sentences:] if overlap_sentences else []
            current.append(sentence)
        else:
            current.append(sentence)
    if current:
        groups.append(" ".join(current))
    return groups


def chunk_document(
    document: CorpusDocument,
    *,
    corpus_version: str,
    max_tokens: int = 400,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    """Turn a :class:`CorpusDocument` into structure-aware :class:`Chunk`s.

    Args:
        document: The source document to chunk.
        corpus_version: The ingestion version tag stamped on every chunk.
        max_tokens: Soft cap per chunk; larger controls are split.
        overlap_sentences: Sentences repeated between split sub-chunks for
            continuity.

    Returns:
        A deterministic list of chunks (one per control, more if a control was
        split). Ids are derived from content, so re-running is idempotent.
    """
    chunks: list[Chunk] = []
    for control in document.controls:
        parts = _split_summary(control.summary, max_tokens, overlap_sentences)
        for index, part in enumerate(parts):
            content = _render(control, part)
            content_hash = _content_hash(content)
            metadata = ChunkMetadata(
                framework=document.framework,
                control_id=control.control_id,
                title=control.title,
                version=document.version,
                language=document.language,
                jurisdiction=document.jurisdiction,
                source=document.title,
                corpus_version=corpus_version,
            )
            chunk_id = _content_hash(
                f"{document.framework.value}:{control.control_id}:{index}:{content_hash}"
            )[:32]
            chunks.append(
                Chunk(
                    id=chunk_id,
                    content=content,
                    metadata=metadata,
                    content_hash=content_hash,
                )
            )
    return chunks
