from database import database_connection


CREATE_PREDICTION_AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS prediction_audit (

    id BIGSERIAL PRIMARY KEY,

    request_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    model_version VARCHAR(50) NOT NULL,

    delivery_charge DOUBLE PRECISION NOT NULL,

    delivery_time_minutes DOUBLE PRECISION NOT NULL,

    rider_acceptance_probability DOUBLE PRECISION NOT NULL,

    rider_acceptance SMALLINT NOT NULL
        CHECK (rider_acceptance IN (0, 1)),

    weather_source VARCHAR(100),

    traffic_source VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


CREATE_PREDICTION_AUDIT_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_prediction_audit_request_timestamp
ON prediction_audit (request_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_audit_model_version
ON prediction_audit (model_version);

CREATE INDEX IF NOT EXISTS idx_prediction_audit_created_at
ON prediction_audit (created_at DESC);
"""


def initialize_database():

    with database_connection() as connection:

        with connection.cursor() as cursor:

            # --------------------------------------------------------
            # Create prediction_audit table
            # --------------------------------------------------------
            cursor.execute(
                CREATE_PREDICTION_AUDIT_TABLE
            )

            # --------------------------------------------------------
            # Create indexes for query optimization
            # --------------------------------------------------------
            cursor.execute(
                CREATE_PREDICTION_AUDIT_INDEXES
            )

            connection.commit()


def verify_database_schema():

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'prediction_audit'
                ORDER BY ordinal_position;
                """
            )

            columns = [
                row[0]
                for row in cursor.fetchall()
            ]

    return columns


def verify_database_indexes():

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'prediction_audit'
                ORDER BY indexname;
                """
            )

            indexes = [
                row[0]
                for row in cursor.fetchall()
            ]

    return indexes


if __name__ == "__main__":

    print("=" * 70)
    print("STEP 16.2 - POSTGRESQL SCHEMA INITIALIZATION")
    print("=" * 70)

    initialize_database()

    columns = verify_database_schema()
    indexes = verify_database_indexes()

    required_columns = [
        "id",
        "request_timestamp",
        "model_version",
        "delivery_charge",
        "delivery_time_minutes",
        "rider_acceptance_probability",
        "rider_acceptance",
        "weather_source",
        "traffic_source",
        "created_at",
    ]

    required_indexes = [
        "idx_prediction_audit_request_timestamp",
        "idx_prediction_audit_model_version",
        "idx_prediction_audit_created_at",
    ]

    print("\nTable: prediction_audit")
    print("\nColumns:")

    for column in required_columns:
        assert column in columns
        print(f"  ✓ {column}")

    print("\nIndexes:")

    for index in required_indexes:
        assert index in indexes
        print(f"  ✓ {index}")

    print("\nPostgreSQL table creation: PASSED")
    print("PostgreSQL index creation: PASSED")
    print("Schema validation: PASSED")

    print("\n" + "=" * 70)
    print("STEP 16.2 RESULT")
    print("=" * 70)

    print("PostgreSQL schema: PASSED")
    print("PostgreSQL indexes: PASSED")
    print("Overall status: PASSED")
    print("=" * 70)