-- ======================================================================
-- Zepto Smart Commerce AI - document chatbot schema (Neon PostgreSQL)
--
-- Run this once in:  Neon console -> SQL Editor  (branch: production)
-- It is idempotent (IF NOT EXISTS). The FastAPI backend also runs the
-- same statements automatically on startup, so this file is mainly for
-- manual setup / documentation. Your existing `orders` and
-- `prediction_audit` tables are not touched.
--
--   kb_documents  one row per uploaded document
--   kb_chunks     searchable text pieces (full-text search via GIN index)
--   chatbot_logs  every question asked + whether it was answered
-- ======================================================================

CREATE TABLE IF NOT EXISTS kb_documents (
    id            BIGSERIAL PRIMARY KEY,
    title         VARCHAR(255) NOT NULL,
    filename      VARCHAR(255),
    file_type     VARCHAR(20),
    char_count    INTEGER NOT NULL DEFAULT 0,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id            BIGSERIAL PRIMARY KEY,
    document_id   BIGINT NOT NULL
                  REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    search_vector TSVECTOR
                  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_search
    ON kb_chunks USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_document_id
    ON kb_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_kb_documents_uploaded_at
    ON kb_documents (uploaded_at DESC);

CREATE TABLE IF NOT EXISTS chatbot_logs (
    id                   BIGSERIAL PRIMARY KEY,
    asked_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    question             TEXT NOT NULL,
    answer               TEXT,
    source_document_ids  BIGINT[],
    answered_from_docs   BOOLEAN NOT NULL DEFAULT FALSE,
    response_ms          INTEGER
);

CREATE INDEX IF NOT EXISTS idx_chatbot_logs_asked_at
    ON chatbot_logs (asked_at DESC);
