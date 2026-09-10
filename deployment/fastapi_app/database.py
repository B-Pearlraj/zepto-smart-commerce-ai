import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv


# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


# ------------------------------------------------------------
# Validate configuration
# ------------------------------------------------------------
def validate_database_config():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    if not (
        DATABASE_URL.startswith("postgresql://")
        or DATABASE_URL.startswith("postgres://")
    ):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL connection URL."
        )

    return True


# ------------------------------------------------------------
# Database connection
# ------------------------------------------------------------
def get_connection():
    validate_database_config()

    return psycopg.connect(
        DATABASE_URL,
        connect_timeout=10,
    )


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
