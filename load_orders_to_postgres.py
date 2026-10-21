"""
Load the feature-engineered orders CSV into PostgreSQL (Neon).

Run it from your own computer (not on Render):

    python load_orders_to_postgres.py

It uses DATABASE_URL from your .env file, creates the tables if they
are missing, and upserts the rows in batches, so it is safe to run
again if it is interrupted.
"""

import os

import pandas as pd

from database import database_connection
from database_schema import create_all_tables


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Change this ONLY if your corrected feature-engineered CSV
# has a different filename/location (or set ORDERS_CSV_PATH).
SOURCE_CSV = os.getenv(
    "ORDERS_CSV_PATH",
    os.path.join(BASE_DIR, "data", "zepto_orders_fe_corrected.csv"),
)

BATCH_SIZE = 1000


# ============================================================
# REQUIRED DATABASE COLUMNS
# ============================================================

ORDER_COLUMNS = [
    "order_id",
    "city",
    "city_tier",
    "customer_lat",
    "customer_lon",
    "store_id",
    "store_lat",
    "store_lon",
    "delivery_zone",

    "distance_km",
    "distance_band",
    "distance_to_radius_ratio",
    "service_radius_km",
    "within_service_radius",

    "item_count",
    "order_amount",
    "order_amount_band",
    "order_weight_kg",
    "order_amount_per_kg",

    "order_year",
    "order_month",
    "order_day",
    "order_hour",
    "order_dayofweek",
    "is_month_start",
    "is_month_end",
    "is_peak_hour",
    "is_weekend",
    "time_of_day",

    "weather_condition",
    "weather_severity",
    "rainfall_mm",
    "has_rain",

    "traffic_index",
    "traffic_level",
    "road_type",

    "current_rider_load",
    "previous_acceptance_rate",
    "rider_earnings_today",
    "rider_experience_months",
    "rider_experience_band",
    "rider_rating",
    "rider_rating_band",
    "vehicle_type",
    "current_incentive",

    "membership_type",
    "historical_delivery_cost",
    "historical_travel_time",
    "demand_level",
    "festival_day_flag",
]


# ============================================================
# VALIDATION
# ============================================================

def validate_source(df):
    print("\nValidating source data...")

    missing_columns = [
        col for col in ORDER_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required columns:\n"
            + "\n".join(missing_columns)
        )

    if df["order_id"].isna().any():
        raise ValueError("order_id contains NULL values")

    duplicate_order_ids = df["order_id"].duplicated().sum()

    if duplicate_order_ids > 0:
        raise ValueError(
            f"Duplicate order_id values found: {duplicate_order_ids}"
        )

    print("Required columns: PASSED")
    print("Order ID null check: PASSED")
    print("Order ID uniqueness: PASSED")


# ============================================================
# SQL
# ============================================================

def build_upsert_sql() -> str:

    insert_columns = ", ".join(ORDER_COLUMNS)
    placeholders = ", ".join(["%s"] * len(ORDER_COLUMNS))

    update_columns = [c for c in ORDER_COLUMNS if c != "order_id"]

    update_clause = ",\n            ".join(
        f"{column} = EXCLUDED.{column}"
        for column in update_columns
    )

    return f"""
        INSERT INTO orders (
            {insert_columns}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT (order_id)
        DO UPDATE SET
            {update_clause},
            updated_at = CURRENT_TIMESTAMP
    """


# ============================================================
# LOAD
# ============================================================

def load_orders():
    print("=" * 70)
    print("LOADING ZEPTO ORDERS INTO POSTGRESQL")
    print("=" * 70)

    if not os.path.exists(SOURCE_CSV):
        raise FileNotFoundError(
            f"Source CSV not found:\n{SOURCE_CSV}"
        )

    print("\nSource file:")
    print(SOURCE_CSV)

    df = pd.read_csv(SOURCE_CSV)

    print(f"\nSource rows: {len(df):,}")
    print(f"Source columns: {len(df.columns)}")

    validate_source(df)

    df = df[ORDER_COLUMNS].copy()

    print(f"\nRows selected for PostgreSQL: {len(df):,}")
    print(f"Columns selected: {len(df.columns)}")

    # --------------------------------------------------------
    # Convert NumPy / pandas values to PostgreSQL-safe values
    # --------------------------------------------------------

    df = df.astype(object).where(pd.notna(df), None)

    rows = [
        tuple(row)
        for row in df.itertuples(index=False, name=None)
    ]

    insert_sql = build_upsert_sql()

    # --------------------------------------------------------
    # Make sure the tables exist (fresh Neon database)
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL (Neon may take a few seconds to wake)...")

    create_all_tables()

    print("Tables: READY")

    # --------------------------------------------------------
    # Insert in batches
    # --------------------------------------------------------

    print("\nInserting orders...")

    with database_connection() as conn:
        with conn.cursor() as cur:

            for start in range(0, len(rows), BATCH_SIZE):

                batch = rows[start:start + BATCH_SIZE]

                cur.executemany(insert_sql, batch)

                done = min(start + BATCH_SIZE, len(rows))
                print(f"  {done:,} / {len(rows):,}")

    print("\nPostgreSQL insert: PASSED")

    # --------------------------------------------------------
    # Verify
    # --------------------------------------------------------

    with database_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT COUNT(*) FROM orders")
            database_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(DISTINCT order_id) FROM orders"
            )
            unique_count = cur.fetchone()[0]

            cur.execute(
                """
                SELECT order_id, city, store_id,
                       distance_km, order_amount,
                       item_count, vehicle_type,
                       membership_type
                FROM orders
                ORDER BY order_id
                LIMIT 5
                """
            )

            sample_rows = cur.fetchall()

    print("\n" + "=" * 70)
    print("POSTGRESQL ORDERS VALIDATION")
    print("=" * 70)

    print(f"Database row count: {database_count:,}")
    print(f"Unique order IDs:   {unique_count:,}")

    print("\nSample orders:")
    for row in sample_rows:
        print(row)

    if database_count != unique_count:
        raise RuntimeError(
            "Validation failed: duplicate Order IDs exist in database."
        )

    print("\nOrder table validation: PASSED")
    print("=" * 70)


if __name__ == "__main__":
    load_orders()
