# ADR-0002: PostgreSQL + pgvector as a single store

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The service needs both relational data (enriched findings, mappings, risks,
report jobs, prompt versions, eval runs, audit log) and vector search over the
regulatory corpus for RAG. A common design uses a dedicated vector database
(e.g. Chroma, Pinecone) alongside a relational database.

## Decision

Use **PostgreSQL 16 with the `pgvector` extension** as a single store for both
relational rows and embeddings. Retrieval uses vector similarity **and** SQL
metadata filters in one query. The mandated stack (Section 5) specifies
pgvector; this ADR records why that is a good fit rather than a constraint we
merely accept.

### Alternatives considered

- **Separate vector DB + Postgres.** Rejected for this scope: two datastores to
  operate, back up, secure, and keep consistent; cross-store joins (filter by
  `control_id` *and* vector-rank) become application-side plumbing. pgvector
  keeps metadata pre-filtering in SQL where it belongs.
- **In-memory FAISS only.** Rejected as the system of record: no durability, no
  multi-tenant SQL filtering, no transactions. FAISS remains valuable as an
  abstraction/target behind the `VectorStore` port for offline evaluation.

## Consequences

- One database to run locally (`docker compose up`) and in production.
- Tenant isolation, metadata filtering, and vector search share one transaction
  and one access-control model.
- We must choose an index (HNSW vs IVFFlat) and distance metric deliberately
  (addressed in the Phase 3 RAG ADR).
- The `VectorStore` port keeps the door open to a FAISS or external adapter
  without touching application code.
