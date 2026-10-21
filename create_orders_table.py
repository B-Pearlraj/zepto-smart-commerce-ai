import os
import psycopg
from dotenv import load_dotenv

# Load FastAPI .env
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured in .env")

CREATE_ORDERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(100) PRIMARY KEY,

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

CREATE INDEX IF NOT EXISTS idx_orders_store_id
    ON orders(store_id);

CREATE INDEX IF NOT EXISTS idx_orders_city
    ON orders(city);

CREATE INDEX IF NOT EXISTS idx_orders_created_at
    ON orders(created_at);
"""


def create_orders_table():
    print("=" * 70)
    print("CREATING POSTGRESQL ORDERS TABLE")
    print("=" * 70)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_ORDERS_TABLE_SQL)

        conn.commit()

    print("Orders table: CREATED / ALREADY EXISTS")
    print("Indexes: CREATED / ALREADY EXISTS")
    print("PostgreSQL connection: PASSED")


if __name__ == "__main__":
    create_orders_table()