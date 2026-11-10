-- ============================================================================
-- Knowledge-base schema for the portfolio AI Assistant (Neon + pgvector)
--
-- Safe to run many times: every statement uses IF NOT EXISTS. The FastAPI app
-- also runs this file automatically at startup. All table names start with
-- "kb_" so they never collide with other tables in the same database
-- (for example the Zepto "orders" table).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per uploaded file --------------------------------------------------
CREATE TABLE IF NOT EXISTS kb_documents (
    id               BIGSERIAL PRIMARY KEY,
    title            TEXT         NOT NULL,
    filename         TEXT         NOT NULL,
    file_type        VARCHAR(10)  NOT NULL,
    file_size_bytes  INTEGER      NOT NULL,
    content_hash     CHAR(64)     NOT NULL UNIQUE,   -- SHA-256, blocks duplicate uploads
    status           VARCHAR(20)  NOT NULL DEFAULT 'processing'
                     CHECK (status IN ('processing', 'ready', 'failed')),
    error_message    TEXT,
    char_count       INTEGER      NOT NULL DEFAULT 0,
    chunk_count      INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One row per text chunk, with its embedding ----------------------------------
-- vector(768) must match EMBED_DIM in config.py.
CREATE TABLE IF NOT EXISTS kb_chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  BIGINT       NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER      NOT NULL,
    content      TEXT         NOT NULL,
    embedding    vector(768)  NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_document
    ON kb_chunks (document_id);

-- Approximate nearest-neighbour index for cosine distance (<=>)
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
    ON kb_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_kb_documents_status
    ON kb_documents (status);

-- Lightweight log of visitor questions (no names, no IP addresses) ------------
-- Useful for seeing which questions the knowledge base cannot answer.
CREATE TABLE IF NOT EXISTS kb_chat_log (
    id          BIGSERIAL PRIMARY KEY,
    asked_at    TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    question    TEXT         NOT NULL,
    outcome     VARCHAR(20)  NOT NULL,   -- answered | not_in_kb | out_of_scope | greeting | error
    top_score   REAL
);

CREATE INDEX IF NOT EXISTS idx_kb_chat_log_asked_at
    ON kb_chat_log (asked_at DESC);
