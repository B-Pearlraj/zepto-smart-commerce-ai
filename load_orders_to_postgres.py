import os
import pandas as pd
import psycopg
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured in .env")


# IMPORTANT:
# Change this ONLY if your corrected feature-engineered CSV
# has a different filename/location.
SOURCE_CSV = os.path.join(
    BASE_DIR,
    "data",
    "zepto_orders_fe_corrected.csv"
)


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

    print(f"\nSource file:")
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

    insert_columns = ", ".join(ORDER_COLUMNS)

    placeholders = ", ".join(
        ["%s"] * len(ORDER_COLUMNS)
    )

    insert_sql = f"""
        INSERT INTO orders (
            {insert_columns}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT (order_id)
        DO UPDATE SET
            city = EXCLUDED.city,
            city_tier = EXCLUDED.city_tier,
            customer_lat = EXCLUDED.customer_lat,
            customer_lon = EXCLUDED.customer_lon,
            store_id = EXCLUDED.store_id,
            store_lat = EXCLUDED.store_lat,
            store_lon = EXCLUDED.store_lon,
            delivery_zone = EXCLUDED.delivery_zone,
            distance_km = EXCLUDED.distance_km,
            distance_band = EXCLUDED.distance_band,
            distance_to_radius_ratio = EXCLUDED.distance_to_radius_ratio,
            service_radius_km = EXCLUDED.service_radius_km,
            within_service_radius = EXCLUDED.within_service_radius,
            item_count = EXCLUDED.item_count,
            order_amount = EXCLUDED.order_amount,
            order_amount_band = EXCLUDED.order_amount_band,
            order_weight_kg = EXCLUDED.order_weight_kg,
            order_amount_per_kg = EXCLUDED.order_amount_per_kg,
            order_year = EXCLUDED.order_year,
            order_month = EXCLUDED.order_month,
            order_day = EXCLUDED.order_day,
            order_hour = EXCLUDED.order_hour,
            order_dayofweek = EXCLUDED.order_dayofweek,
            is_month_start = EXCLUDED.is_month_start,
            is_month_end = EXCLUDED.is_month_end,
            is_peak_hour = EXCLUDED.is_peak_hour,
            is_weekend = EXCLUDED.is_weekend,
            time_of_day = EXCLUDED.time_of_day,
            weather_condition = EXCLUDED.weather_condition,
            weather_severity = EXCLUDED.weather_severity,
            rainfall_mm = EXCLUDED.rainfall_mm,
            has_rain = EXCLUDED.has_rain,
            traffic_index = EXCLUDED.traffic_index,
            traffic_level = EXCLUDED.traffic_level,
            road_type = EXCLUDED.road_type,
            current_rider_load = EXCLUDED.current_rider_load,
            previous_acceptance_rate = EXCLUDED.previous_acceptance_rate,
            rider_earnings_today = EXCLUDED.rider_earnings_today,
            rider_experience_months = EXCLUDED.rider_experience_months,
            rider_experience_band = EXCLUDED.rider_experience_band,
            rider_rating = EXCLUDED.rider_rating,
            rider_rating_band = EXCLUDED.rider_rating_band,
            vehicle_type = EXCLUDED.vehicle_type,
            current_incentive = EXCLUDED.current_incentive,
            membership_type = EXCLUDED.membership_type,
            historical_delivery_cost = EXCLUDED.historical_delivery_cost,
            historical_travel_time = EXCLUDED.historical_travel_time,
            demand_level = EXCLUDED.demand_level,
            festival_day_flag = EXCLUDED.festival_day_flag,
            updated_at = CURRENT_TIMESTAMP
    """

    rows = [
        tuple(row)
        for row in df.itertuples(index=False, name=None)
    ]

    print("\nConnecting to PostgreSQL...")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            print("Inserting orders...")

            cur.executemany(
                insert_sql,
                rows
            )

        conn.commit()

    print("\nPostgreSQL insert: PASSED")

    # --------------------------------------------------------
    # Verify
    # --------------------------------------------------------

    with psycopg.connect(DATABASE_URL) as conn:
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