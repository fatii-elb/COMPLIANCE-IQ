"""Corpus loaders — read source documents from disk into the domain model.

A *loader* is the adapter between raw files and :class:`CorpusDocument`s. Each
JSON file under the corpus directory describes one framework document (its
metadata plus a list of control summaries). Keeping loading here (infrastructure)
means the ingestion use case stays pure — it consumes domain documents and never
touches the filesystem.

The bundled corpus is deliberately copyright-compliant: control identifiers plus
our own summaries and references, never verbatim standard text (rule 6).
"""

from __future__ import annotations

import json
from pathlib import Path

from complianceiq.domain.knowledge.documents import CorpusDocument


def load_corpus_file(path: Path) -> CorpusDocument:
    """Load and validate a single corpus JSON file into a ``CorpusDocument``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return CorpusDocument.model_validate(data)


def load_corpus(directory: Path) -> list[CorpusDocument]:
    """Load every ``*.json`` document under ``directory`` (sorted for determinism).

    Args:
        directory: The corpus directory (e.g. ``corpus/frameworks``).

    Returns:
        The parsed documents. An empty list if the directory has none.
    """
    if not directory.exists():
        return []
    return [load_corpus_file(path) for path in sorted(directory.glob("*.json"))]
