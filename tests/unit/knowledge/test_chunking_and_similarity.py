"""Tests for structure-aware chunking and similarity helpers."""

from __future__ import annotations

import pytest

from complianceiq.domain.knowledge.chunking import chunk_document, estimate_tokens
from complianceiq.domain.knowledge.documents import ControlSummary, CorpusDocument
from complianceiq.domain.knowledge.metadata import Jurisdiction, Language
from complianceiq.domain.knowledge.similarity import (
    cosine_similarity,
    jaccard_similarity,
    tokenize,
)
from complianceiq.domain.value_objects.enums import Framework


def _doc(summary: str) -> CorpusDocument:
    return CorpusDocument(
        framework=Framework.NIST_CSF,
        title="Doc",
        version="1",
        language=Language.EN,
        jurisdiction=Jurisdiction.INTERNATIONAL,
        controls=[ControlSummary(control_id="C-1", title="T", summary=summary)],
    )


def test_one_control_yields_one_chunk() -> None:
    chunks = chunk_document(_doc("A short control summary."), corpus_version="v1")
    assert len(chunks) == 1
    assert chunks[0].metadata.control_id == "C-1"
    assert chunks[0].metadata.corpus_version == "v1"
    assert "C-1" in chunks[0].content


def test_chunking_is_deterministic() -> None:
    a = chunk_document(_doc("Same text."), corpus_version="v1")
    b = chunk_document(_doc("Same text."), corpus_version="v1")
    assert a[0].id == b[0].id
    assert a[0].content_hash == b[0].content_hash


def test_long_summary_is_split() -> None:
    long_summary = " ".join(f"Sentence number {i} about encryption keys." for i in range(60))
    chunks = chunk_document(_doc(long_summary), corpus_version="v1", max_tokens=40)
    assert len(chunks) > 1
    # every sub-chunk keeps the control's metadata
    assert all(c.metadata.control_id == "C-1" for c in chunks)


def test_cosine_similarity_and_mismatch() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])


def test_jaccard_and_tokenize() -> None:
    assert tokenize("Public S3 bucket!") == ["public", "s3", "bucket"]
    assert jaccard_similarity("public bucket", "public bucket") == pytest.approx(1.0)
    assert jaccard_similarity("public bucket", "banana bread") == pytest.approx(0.0)


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") >= 1
