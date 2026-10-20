import os
import time
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv


# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Neon free tier suspends the database after ~5 minutes idle.
# The first connection after that wakes it up, so we retry.
CONNECT_RETRIES = 4
CONNECT_TIMEOUT_SECONDS = 20
RETRY_BACKOFF_SECONDS = 1.5


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
            "DATABASE_URL must be a PostgreSQL connection URL."
        )

    return True


# ------------------------------------------------------------
# Database connection
# ------------------------------------------------------------
def get_connection():
    validate_database_config()

    extra = {}
    # Neon requires SSL. Add it if the URL doesn't already say so.
    if "sslmode=" not in DATABASE_URL and "neon.tech" in DATABASE_URL:
        extra["sslmode"] = "require"

    last_error = None

    for attempt in range(1, CONNECT_RETRIES + 1):
        try:
            return psycopg.connect(
                DATABASE_URL,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                # Safe with Neon's pooled (PgBouncer) connection
                prepare_threshold=None,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                **extra,
            )

        except psycopg.OperationalError as exc:
            last_error = exc

            if attempt < CONNECT_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise last_error


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
        connection.rollback()
        raise

    finally:
        connection.close()


# ------------------------------------------------------------
# Lightweight liveness check (used by /health)
# ------------------------------------------------------------
def ping_database() -> bool:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()

    return True


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
