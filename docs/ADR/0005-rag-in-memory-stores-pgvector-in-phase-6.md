# ADR-0005: In-memory RAG stores now, pgvector-backed store in Phase 6

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Phase 3 builds the full RAG pipeline: chunking, embedding, a vector store, a
keyword index, hybrid retrieval, reranking, and context assembly. ADR-0002 already
chose **PostgreSQL + pgvector** as the production vector store. But the durable
persistence layer — async SQLAlchemy, Alembic migrations, tenant-scoped
repositories — is scheduled for Phase 6, and a real pgvector store needs all of
it (a database, a driver, migrations, DDL for HNSW indexes).

## Decision

Ship the complete RAG pipeline in Phase 3 behind the `VectorStore`,
`KeywordIndex`, and `Reranker` **ports**, with **in-memory adapters** as the
default implementation:

- `InMemoryVectorStore` — pure-Python cosine similarity with metadata filtering
  and the embedding-model-identity guard.
- `InMemoryKeywordIndex` — BM25 lexical scoring.
- `LexicalReranker` — deterministic query-term-coverage reranking.

The **pgvector-backed `VectorStore`** (and a cross-encoder `Reranker`) implement
the *same ports* and land in Phase 6 alongside the rest of persistence. Switching
is a composition-root change, not a pipeline change.

### Alternatives considered

- **Build the pgvector store now.** Rejected: it would pull the entire database
  stack (driver, migrations, a running Postgres) into Phase 3, and none of it
  could be unit-tested offline here. We do not ship code we cannot run and test.
- **Only ever use in-memory.** Rejected: not durable, single-instance, and no SQL
  metadata filtering at scale. In-memory is the *default and test* backend, not
  the production system of record.

## Consequences

- The whole RAG pipeline runs and is fully tested offline (no DB, no network),
  and `docker compose up` yields a working, queryable knowledge base via startup
  autoload of the bundled corpus.
- Retrieval quality with the offline **fake** embedder is limited on the semantic
  side (its vectors are non-semantic); lexical + rerank + filtering still give
  sensible results, and real embeddings restore full semantic quality with no code
  change.
- **Phase 6 plan (documented now):** a `PgVectorStore` using `vector(N)` columns,
  an **HNSW** index with **cosine** distance, metadata columns for SQL
  pre-filtering, and Alembic migrations — implementing the existing `VectorStore`
  port.
