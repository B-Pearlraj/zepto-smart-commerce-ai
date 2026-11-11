"""
PostgreSQL (Neon) data access for the document chat feature.

Uses the same `database_connection()` helper as database_repository.py,
so it connects with the DATABASE_URL you already configured.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from database import database_connection

logger = logging.getLogger("zepto_fastapi")

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def vector_literal(values: Sequence[float]) -> str:
    """Format a Python list as a pgvector literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{float(v):.8g}" for v in values) + "]"


# ------------------------------------------------------------
# Schema
# ------------------------------------------------------------
def init_rag_schema() -> None:
    """Run schema.sql (idempotent). Called on application startup."""

    if not SCHEMA_FILE.is_file():
        raise RuntimeError(
            f"schema.sql not found next to main.py ({SCHEMA_FILE}). "
            "Commit schema.sql to your backend repository."
        )

    sql = SCHEMA_FILE.read_text(encoding="utf-8")

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()


def mark_interrupted_documents() -> int:
    """
    A restart can interrupt background vector creation. Documents left in
    'processing' are marked 'partial' (keyword search still works) so the
    admin can press "Re-index" on them.
    """

    query = """
        UPDATE rag_documents d
        SET status = 'partial',
            status_note = 'Vector creation was interrupted by a server restart. Press Re-index.',
            embedded_chunk_count = (
                SELECT COUNT(*) FROM rag_chunks c
                WHERE c.document_id = d.id AND c.embedding IS NOT NULL
            )
        WHERE d.status = 'processing';
    """

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            updated = cursor.rowcount
        connection.commit()

    return updated


# ------------------------------------------------------------
# Documents
# ------------------------------------------------------------
DOCUMENT_COLUMNS = [
    "id",
    "filename",
    "file_type",
    "file_size_bytes",
    "chunk_count",
    "embedded_chunk_count",
    "status",
    "status_note",
    "uploaded_at",
]


def _document_row_to_dict(row) -> Dict[str, Any]:
    record = dict(zip(DOCUMENT_COLUMNS, row))
    if record.get("uploaded_at") is not None:
        record["uploaded_at"] = record["uploaded_at"].isoformat()
    return record


def find_document_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    query = f"""
        SELECT {", ".join(DOCUMENT_COLUMNS)}
        FROM rag_documents
        WHERE content_hash = %s;
    """

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (content_hash,))
            row = cursor.fetchone()

    return _document_row_to_dict(row) if row else None


def create_document_with_chunks(
    filename: str,
    file_type: str,
    file_size_bytes: int,
    content_hash: str,
    chunks: List[str],
) -> int:
    """Insert the document and all its chunks in ONE transaction."""

    with database_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO rag_documents
                    (filename, file_type, file_size_bytes, content_hash,
                     chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, 'processing')
                RETURNING id;
                """,
                (filename, file_type, file_size_bytes, content_hash, len(chunks)),
            )
            document_id = cursor.fetchone()[0]

            cursor.executemany(
                """
                INSERT INTO rag_chunks (document_id, chunk_index, content)
                VALUES (%s, %s, %s);
                """,
                [(document_id, index, text) for index, text in enumerate(chunks)],
            )

        connection.commit()

    return document_id


def get_unembedded_chunks(document_id: int) -> List[Tuple[int, str]]:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, content
                FROM rag_chunks
                WHERE document_id = %s AND embedding IS NULL
                ORDER BY chunk_index;
                """,
                (document_id,),
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]


def save_chunk_embeddings(
    rows: List[Tuple[int, Sequence[float]]],
    model: str,
) -> None:
    if not rows:
        return

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                UPDATE rag_chunks
                SET embedding = %s::vector, embedding_model = %s
                WHERE id = %s;
                """,
                [(vector_literal(vec), model, chunk_id) for chunk_id, vec in rows],
            )
        connection.commit()


def finish_document(document_id: int, note: Optional[str] = None) -> None:
    """Recount vectors and set the final status of a document."""

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE rag_documents d
                SET embedded_chunk_count = sub.embedded,
                    status = CASE
                        WHEN sub.embedded >= d.chunk_count THEN 'ready'
                        ELSE 'partial'
                    END,
                    status_note = CASE
                        WHEN sub.embedded >= d.chunk_count THEN NULL
                        ELSE %s
                    END
                FROM (
                    SELECT COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embedded
                    FROM rag_chunks
                    WHERE document_id = %s
                ) sub
                WHERE d.id = %s;
                """,
                (
                    note or "Some chunks have no vector yet. Keyword search still works. Press Re-index to retry.",
                    document_id,
                    document_id,
                ),
            )
        connection.commit()


def set_document_processing(document_id: int) -> None:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE rag_documents
                SET status = 'processing', status_note = NULL
                WHERE id = %s;
                """,
                (document_id,),
            )
        connection.commit()


def list_documents() -> List[Dict[str, Any]]:
    query = f"""
        SELECT {", ".join(DOCUMENT_COLUMNS)}
        FROM rag_documents
        ORDER BY uploaded_at DESC;
    """

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return [_document_row_to_dict(row) for row in cursor.fetchall()]


def get_document(document_id: int) -> Optional[Dict[str, Any]]:
    query = f"""
        SELECT {", ".join(DOCUMENT_COLUMNS)}
        FROM rag_documents
        WHERE id = %s;
    """

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (document_id,))
            row = cursor.fetchone()

    return _document_row_to_dict(row) if row else None


def delete_document(document_id: int) -> bool:
    """Deletes the document; its chunks go with it (ON DELETE CASCADE)."""

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM rag_documents WHERE id = %s;",
                (document_id,),
            )
            deleted = cursor.rowcount
        connection.commit()

    return deleted > 0


def count_documents() -> int:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM rag_documents;")
            return int(cursor.fetchone()[0])


# ------------------------------------------------------------
# Search
# ------------------------------------------------------------
def search_vector(query_vector: Sequence[float], limit: int) -> List[Dict[str, Any]]:
    """Cosine-similarity search over chunks that have a vector of the same size."""

    literal = vector_literal(query_vector)

    query = """
        SELECT c.id, c.content, d.filename,
               1 - (c.embedding <=> %s::vector) AS score
        FROM rag_chunks c
        JOIN rag_documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
          AND vector_dims(c.embedding) = %s
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
    """

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (literal, len(query_vector), literal, limit))
            return [
                {"id": r[0], "content": r[1], "filename": r[2], "score": float(r[3])}
                for r in cursor.fetchall()
            ]


def search_keyword(tsquery: str, limit: int) -> List[Dict[str, Any]]:
    """
    Keyword search. `tsquery` must already be built from sanitised words
    joined with ' | ' (see rag_service.build_tsquery).
    """

    if not tsquery:
        return []

    query = """
        SELECT c.id, c.content, d.filename,
               ts_rank_cd(c.content_tsv, q) AS score
        FROM rag_chunks c
        JOIN rag_documents d ON d.id = c.document_id,
             to_tsquery('simple', %s) q
        WHERE c.content_tsv @@ q
        ORDER BY score DESC
        LIMIT %s;
    """

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (tsquery, limit))
            return [
                {"id": r[0], "content": r[1], "filename": r[2], "score": float(r[3])}
                for r in cursor.fetchall()
            ]
