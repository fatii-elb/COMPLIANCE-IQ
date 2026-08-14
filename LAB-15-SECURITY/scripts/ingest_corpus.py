#!/usr/bin/env python
"""Ingest the regulatory corpus into the knowledge base.

A small operational CLI: it loads every document under the corpus directory,
chunks and embeds them (via the configured provider — the offline fake by
default), and writes them to the vector store and keyword index. Idempotent:
re-running does not duplicate chunks. Use ``--replace`` to clear the corpus
version first for a clean re-index.

Usage:
    python -m scripts.ingest_corpus
    python -m scripts.ingest_corpus --replace --corpus-dir corpus/frameworks

Note: with the default in-memory stores this ingests into a throwaway process
(useful for a smoke test / eval). Once the pgvector store lands (Phase 6) the same
command persists the corpus durably.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from complianceiq.composition import build_container
from complianceiq.infrastructure.knowledge import load_corpus


async def _run(corpus_dir: Path, *, replace: bool) -> int:
    container = build_container()
    documents = load_corpus(corpus_dir)
    if not documents:
        print(f"No corpus documents found under {corpus_dir}")
        return 1

    report = await container.knowledge.ingestion.ingest(documents, replace=replace)
    print(
        f"Ingested {report.documents} document(s), {report.chunks} chunk(s) "
        f"into corpus version '{report.corpus_version}'."
    )
    print(f"Vector store now holds {await container.knowledge.vector_store.count()} chunks.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the regulatory corpus.")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("corpus/frameworks"),
        help="Directory of corpus JSON files (default: corpus/frameworks).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete the existing corpus version before ingesting (clean re-index).",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.corpus_dir, replace=args.replace))


if __name__ == "__main__":
    raise SystemExit(main())
