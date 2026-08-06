-- Migration 0001 — knowledge base on PostgreSQL + pgvector (Phase 6).
--
-- Creates the extension and the chunk table the PgVectorStore reads/writes. The
-- vector dimension is fixed at ingestion time by the embedding model; adjust the
-- `vector(N)` dimension to match the configured embedding model before applying.
-- Run against the database at CIQ_DATABASE_URL, e.g.:
--   psql "$CIQ_DATABASE_URL" -f migrations/0001_knowledge_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id                 text PRIMARY KEY,
    content            text NOT NULL,
    content_hash       text NOT NULL,
    framework          text NOT NULL,
    control_id         text NOT NULL,
    title              text NOT NULL,
    version            text NOT NULL,
    language           text NOT NULL,
    jurisdiction       text NOT NULL,
    source             text NOT NULL,
    corpus_version     text NOT NULL,
    embedding_model    text NOT NULL,
    embedding_provider text NOT NULL,
    embedding          vector(1536) NOT NULL
);

-- Pre-filter columns (metadata filters are pushed into the WHERE clause).
CREATE INDEX IF NOT EXISTS knowledge_chunks_framework_idx      ON knowledge_chunks (framework);
CREATE INDEX IF NOT EXISTS knowledge_chunks_corpus_version_idx ON knowledge_chunks (corpus_version);

-- Approximate-nearest-neighbour index for cosine distance (<=>). Tune `lists`
-- to roughly sqrt(row_count); build it after the initial bulk ingest.
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
    ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
