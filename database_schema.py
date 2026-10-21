"""
Database schema for the Zepto Smart Commerce AI backend.

This file is the single source of truth for BOTH tables:

    orders             -> order lookup + ML feature set
    prediction_audit   -> log of every prediction

It is safe to run any number of times (everything is
CREATE ... IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

The FastAPI app calls create_all_tables() on startup, so a brand-new
Neon database is set up automatically on the first deploy.
You can also run it by hand:   python database_schema.py
"""

from typing import List

from database import database_connection


# ------------------------------------------------------------
# orders
# ------------------------------------------------------------
CREATE_ORDERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(100) PRIMARY KEY,

    -- Display info (shown in the chatbot before confirming).
    -- Nullable because the CSV loader does not provide them.
    customer_name VARCHAR(100),
    product_name VARCHAR(150),
    order_status VARCHAR(30) DEFAULT 'placed',

    -- Location / store
    city VARCHAR(100) NOT NULL,
    city_tier INTEGER NOT NULL,
    customer_lat DOUBLE PRECISION NOT NULL,
    customer_lon DOUBLE PRECISION NOT NULL,
    store_id VARCHAR(100) NOT NULL,
    store_lat DOUBLE PRECISION NOT NULL,
    store_lon DOUBLE PRECISION NOT NULL,
    delivery_zone VARCHAR(100) NOT NULL,

    -- Distance
    distance_km DOUBLE PRECISION NOT NULL,
    distance_band VARCHAR(50) NOT NULL,
    distance_to_radius_ratio DOUBLE PRECISION NOT NULL,
    service_radius_km DOUBLE PRECISION NOT NULL,
    within_service_radius SMALLINT NOT NULL,

    -- Order
    item_count INTEGER NOT NULL,
    order_amount DOUBLE PRECISION NOT NULL,
    order_amount_band VARCHAR(50) NOT NULL,
    order_weight_kg DOUBLE PRECISION NOT NULL,
    order_amount_per_kg DOUBLE PRECISION NOT NULL,

    -- Date / time
    order_year INTEGER NOT NULL,
    order_month INTEGER NOT NULL,
    order_day INTEGER NOT NULL,
    order_hour INTEGER NOT NULL,
    order_dayofweek INTEGER NOT NULL,
    is_month_start SMALLINT NOT NULL,
    is_month_end SMALLINT NOT NULL,
    is_peak_hour SMALLINT NOT NULL,
    is_weekend SMALLINT NOT NULL,
    time_of_day VARCHAR(50) NOT NULL,

    -- Weather
    weather_condition VARCHAR(100) NOT NULL,
    weather_severity INTEGER NOT NULL,
    rainfall_mm DOUBLE PRECISION NOT NULL,
    has_rain SMALLINT NOT NULL,

    -- Traffic / road
    traffic_index DOUBLE PRECISION NOT NULL,
    traffic_level VARCHAR(50) NOT NULL,
    road_type VARCHAR(100) NOT NULL,

    -- Rider
    current_rider_load DOUBLE PRECISION NOT NULL,
    previous_acceptance_rate DOUBLE PRECISION NOT NULL,
    rider_earnings_today DOUBLE PRECISION NOT NULL,
    rider_experience_months DOUBLE PRECISION NOT NULL,
    rider_experience_band VARCHAR(50) NOT NULL,
    rider_rating DOUBLE PRECISION NOT NULL,
    rider_rating_band VARCHAR(50) NOT NULL,
    vehicle_type VARCHAR(50) NOT NULL,
    current_incentive DOUBLE PRECISION NOT NULL,

    -- Customer / business
    membership_type VARCHAR(100) NOT NULL,
    historical_delivery_cost DOUBLE PRECISION NOT NULL,
    historical_travel_time DOUBLE PRECISION NOT NULL,
    demand_level VARCHAR(100) NOT NULL,
    festival_day_flag SMALLINT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# If an older version of the table already exists (for example one
# created before these columns were added), bring it up to date.
ORDERS_COMPATIBILITY_PATCHES: List[str] = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS product_name VARCHAR(150)",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_status VARCHAR(30) DEFAULT 'placed'",
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
]

ORDERS_INDEX_STATEMENTS: List[str] = [
    "CREATE INDEX IF NOT EXISTS idx_orders_store_id ON orders (store_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_city ON orders (city)",
    "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at)",
]


# ------------------------------------------------------------
# prediction_audit
# ------------------------------------------------------------
CREATE_PREDICTION_AUDIT_TABLE_SQL = """
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

PREDICTION_AUDIT_INDEX_STATEMENTS: List[str] = [
    """CREATE INDEX IF NOT EXISTS idx_prediction_audit_request_timestamp
       ON prediction_audit (request_timestamp DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_prediction_audit_model_version
       ON prediction_audit (model_version)""",
    """CREATE INDEX IF NOT EXISTS idx_prediction_audit_created_at
       ON prediction_audit (created_at DESC)""",
]


SCHEMA_STATEMENTS: List[str] = [
    CREATE_ORDERS_TABLE_SQL,
    *ORDERS_COMPATIBILITY_PATCHES,
    *ORDERS_INDEX_STATEMENTS,
    CREATE_PREDICTION_AUDIT_TABLE_SQL,
    *PREDICTION_AUDIT_INDEX_STATEMENTS,
]


# ------------------------------------------------------------
# Create / verify
# ------------------------------------------------------------
def create_all_tables() -> None:
    """Create both tables (and indexes) if they do not exist yet."""

    with database_connection() as connection:

        with connection.cursor() as cursor:

            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)


def get_table_columns(table_name: str) -> List[str]:

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position;
                """,
                (table_name,),
            )

            return [row[0] for row in cursor.fetchall()]


def get_table_indexes(table_name: str) -> List[str]:

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = %s
                ORDER BY indexname;
                """,
                (table_name,),
            )

            return [row[0] for row in cursor.fetchall()]


if __name__ == "__main__":

    print("=" * 70)
    print("CREATING POSTGRESQL SCHEMA (orders + prediction_audit)")
    print("=" * 70)

    create_all_tables()

    for table in ("orders", "prediction_audit"):
        columns = get_table_columns(table)
        indexes = get_table_indexes(table)

        print(f"\nTable: {table}")
        print(f"  Columns: {len(columns)}")
        print(f"  Indexes: {', '.join(indexes)}")

    print("\nSchema: CREATED / ALREADY EXISTS")
    print("PostgreSQL connection: PASSED")
    print("=" * 70)
