"""
PostgreSQL connection helpers (Neon-ready).

- Reads DATABASE_URL from the environment (Render -> Environment tab)
  or from a local .env file.
- Opens a fresh connection for every operation, so there is never a
  long-lived connection that Neon can close while it is idle.
- Retries the connection, because Neon scales to zero and the first
  connection after an idle period can take a few seconds.
"""

import functools
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv

logger = logging.getLogger("zepto_fastapi")


# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent / ".env"

# Local development: the .env file wins over stale shell variables.
# On Render there is no .env file, so the Environment tab is used.
load_dotenv(dotenv_path=ENV_PATH, override=ENV_PATH.exists())

# .strip("'\"") removes quotes left over when the full
# `psql 'postgresql://...'` command is copied from the Neon dashboard.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip().strip("'\"")

CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT", "15"))
CONNECT_ATTEMPTS = int(os.getenv("DB_CONNECT_ATTEMPTS", "4"))


class DatabaseUnavailableError(RuntimeError):
    """Raised when the database cannot be reached after all retries."""


# Errors that usually mean "the connection dropped" and are worth a retry.
TRANSIENT_ERRORS = (psycopg.OperationalError, psycopg.InterfaceError)


# ------------------------------------------------------------
# Validate configuration
# ------------------------------------------------------------
def validate_database_config():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL connection URL "
            "(it should start with postgresql://)."
        )

    return True


# ------------------------------------------------------------
# Database connection (with retry for Neon wake-up)
# ------------------------------------------------------------
def get_connection():
    validate_database_config()

    last_error = None

    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return psycopg.connect(
                DATABASE_URL,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                # Safe with Neon's pooled (PgBouncer) endpoint.
                prepare_threshold=None,
                # Detect dead connections instead of hanging on them.
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
            )

        except psycopg.OperationalError as exc:
            last_error = exc

            if attempt < CONNECT_ATTEMPTS:
                wait_seconds = min(2 * attempt, 8)

                logger.warning(
                    "Database connection attempt %s/%s failed (%s). "
                    "Retrying in %ss...",
                    attempt,
                    CONNECT_ATTEMPTS,
                    type(exc).__name__,
                    wait_seconds,
                )

                time.sleep(wait_seconds)

    raise DatabaseUnavailableError(
        f"Could not connect to the database after "
        f"{CONNECT_ATTEMPTS} attempts: {last_error}"
    ) from last_error


# ------------------------------------------------------------
# Context-managed connection
# ------------------------------------------------------------
@contextmanager
def database_connection():
    connection = get_connection()

    try:
        yield connection
        connection.commit()

    except Exception:
        try:
            connection.rollback()
        except Exception:
            # The connection is already broken; keep the original error.
            pass
        raise

    finally:
        try:
            connection.close()
        except Exception:
            pass


# ------------------------------------------------------------
# Retry decorator for READ-ONLY queries
# ------------------------------------------------------------
def retry_transient(attempts: int = 3, delay_seconds: float = 1.5):
    """
    Re-run a read-only database function if the connection drops
    mid-query (for example "SSL connection has been closed
    unexpectedly"). Do not use this on INSERT/UPDATE functions.
    """

    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)

                except TRANSIENT_ERRORS as exc:
                    last_error = exc

                    logger.warning(
                        "%s failed on attempt %s/%s (%s).",
                        func.__name__,
                        attempt,
                        attempts,
                        type(exc).__name__,
                    )

                    if attempt < attempts:
                        time.sleep(delay_seconds * attempt)

            raise last_error

        return wrapper

    return decorator


# ------------------------------------------------------------
# Connection test
# ------------------------------------------------------------
def test_database_connection():

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute("SELECT version();")

            result = cursor.fetchone()

            if not result:
                raise RuntimeError(
                    "PostgreSQL connection test returned no result."
                )

            return result[0]


if __name__ == "__main__":

    print("=" * 70)
    print("POSTGRESQL DATABASE CONFIGURATION TEST")
    print("=" * 70)

    validate_database_config()

    version = test_database_connection()

    print("\nDATABASE_URL: CONFIGURED")
    print("PostgreSQL connection: PASSED")
    print(f"PostgreSQL version: {version}")

    print("\n" + "=" * 70)
    print("DATABASE CONFIGURATION: PASSED")
    print("=" * 70)
