-- ============================================================
-- Zepto Smart Commerce AI - Document Chat (RAG) schema
-- Database: Neon PostgreSQL (pgvector)
--
-- This file is safe to run many times (everything is IF NOT EXISTS).
-- The FastAPI backend also runs it automatically on startup, so
-- running it by hand in the Neon SQL Editor is optional.
--
-- Your existing tables (orders, prediction_audit) are NOT touched.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- One row per uploaded document
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag_documents (
    id                    BIGSERIAL PRIMARY KEY,
    filename              TEXT        NOT NULL,
    file_type             VARCHAR(10) NOT NULL,
    file_size_bytes       INTEGER     NOT NULL,
    content_hash          CHAR(64)    NOT NULL UNIQUE,   -- sha256 of the file, blocks duplicates
    chunk_count           INTEGER     NOT NULL DEFAULT 0,
    embedded_chunk_count  INTEGER     NOT NULL DEFAULT 0,
    -- processing : chunks saved, vectors still being created
    -- ready      : every chunk has a vector
    -- partial    : some/all chunks have no vector (keyword search still works)
    -- failed     : nothing usable was saved
    status                VARCHAR(20) NOT NULL DEFAULT 'processing',
    status_note           TEXT,
    uploaded_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Text chunks of each document (+ vector + keyword index)
--
-- `embedding` is declared WITHOUT a fixed size on purpose, so it
-- works with any embedding model (768 / 1536 / 3072 dimensions...).
-- The document set is small, so an exact scan is fast and no
-- vector index is needed.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag_chunks (
    id               BIGSERIAL PRIMARY KEY,
    document_id      BIGINT      NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    chunk_index      INTEGER     NOT NULL,
    content          TEXT        NOT NULL,
    content_tsv      tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    embedding        vector,
    embedding_model  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id
    ON rag_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_tsv
    ON rag_chunks USING GIN (content_tsv);

CREATE INDEX IF NOT EXISTS idx_rag_documents_uploaded_at
    ON rag_documents (uploaded_at DESC);
