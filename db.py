"""
Neon PostgreSQL connection helpers (psycopg 3).

A new connection is opened per operation, which is the safest pattern for
Neon (it scales to zero and closes idle connections) and for Render's free
tier (the service sleeps). Connection attempts are retried a few times
because Neon can need a few seconds to wake up.
"""

import logging
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg

from config import BASE_DIR, DATABASE_URL

logger = logging.getLogger("assistant.db")

SCHEMA_FILE = BASE_DIR / "schema.sql"


class DatabaseNotConfigured(RuntimeError):
    pass


def _validate_url() -> None:
    if not DATABASE_URL:
        raise DatabaseNotConfigured("DATABASE_URL is not configured.")
    if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
        raise DatabaseNotConfigured("DATABASE_URL must be a PostgreSQL connection URL.")


def _connect() -> psycopg.Connection:
    _validate_url()
    last_error = None

    for attempt in range(3):
        try:
            return psycopg.connect(
                DATABASE_URL,
                connect_timeout=15,
                # Neon's pooled endpoint sits behind PgBouncer; disabling
                # automatic server-side prepared statements avoids errors.
                prepare_threshold=None,
            )
        except psycopg.OperationalError as exc:
            last_error = exc
            logger.warning("Database connection attempt %s failed: %s", attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))

    raise last_error


@contextmanager
def connection():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(schema_path: Path = SCHEMA_FILE) -> None:
    """Run schema.sql. Every statement is idempotent (IF NOT EXISTS)."""
    sql = schema_path.read_text(encoding="utf-8")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Database schema is ready.")


def to_vector_literal(values) -> str:
    """Format a list of floats as a pgvector literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{float(v):.7f}" for v in values) + "]"
