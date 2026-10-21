from typing import Any, Dict, List, Optional

from database import database_connection


# ------------------------------------------------------------
# Orders table — column definitions
# ------------------------------------------------------------
# Every ML feature the models need, plus a few human-readable
# fields (customer_name, product_name, order_status) so the
# chatbot has something meaningful to show the user before
# they confirm a prediction.
# ------------------------------------------------------------

ORDER_DISPLAY_COLUMNS: List[str] = [
    "order_id",
    "customer_name",
    "product_name",
    "order_status",
]

ORDER_FEATURE_COLUMNS: List[str] = [
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

ORDER_COLUMNS: List[str] = (
    ORDER_DISPLAY_COLUMNS + ORDER_FEATURE_COLUMNS + ["created_at"]
)


# ------------------------------------------------------------
# Sample seed data (10 orders, ORD1001 - ORD1010)
# ------------------------------------------------------------

SAMPLE_ORDERS: List[Dict[str, Any]] = [
    {
        "order_id": "ORD1001", "customer_name": "Arun Kumar",
        "product_name": "Grocery Essentials Basket", "order_status": "placed",
        "city": "Chennai", "city_tier": 1, "customer_lat": 13.0827, "customer_lon": 80.2707,
        "store_id": "DS001", "store_lat": 13.0800, "store_lon": 80.2700,
        "delivery_zone": "urban", "distance_km": 1.8, "distance_band": "0-2",
        "distance_to_radius_ratio": 0.18, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 5, "order_amount": 450.0, "order_amount_band": "medium",
        "order_weight_kg": 2.0, "order_amount_per_kg": 225.0,
        "order_year": 2026, "order_month": 9, "order_day": 10, "order_hour": 18, "order_dayofweek": 3,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 0, "is_weekend": 0, "time_of_day": "evening",
        "weather_condition": "clear", "weather_severity": 0, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 30.0, "traffic_level": "low", "road_type": "main_road",
        "current_rider_load": 2.0, "previous_acceptance_rate": 0.85, "rider_earnings_today": 850.0,
        "rider_experience_months": 24.0, "rider_experience_band": "experienced",
        "rider_rating": 4.7, "rider_rating_band": "high", "vehicle_type": "bike",
        "current_incentive": 20.0, "membership_type": "pass_plus",
        "historical_delivery_cost": 48.0, "historical_travel_time": 18.0,
        "demand_level": "medium", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1002", "customer_name": "Priya Sharma",
        "product_name": "Weekend Snacks & Beverages Combo", "order_status": "placed",
        "city": "Bengaluru", "city_tier": 1, "customer_lat": 12.9716, "customer_lon": 77.5946,
        "store_id": "DS014", "store_lat": 12.9750, "store_lon": 77.6010,
        "delivery_zone": "urban", "distance_km": 3.4, "distance_band": "2-5",
        "distance_to_radius_ratio": 0.34, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 9, "order_amount": 820.0, "order_amount_band": "high",
        "order_weight_kg": 3.6, "order_amount_per_kg": 227.8,
        "order_year": 2026, "order_month": 9, "order_day": 12, "order_hour": 20, "order_dayofweek": 5,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 1, "is_weekend": 1, "time_of_day": "evening",
        "weather_condition": "clouds", "weather_severity": 1, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 62.0, "traffic_level": "medium", "road_type": "main_road",
        "current_rider_load": 4.0, "previous_acceptance_rate": 0.78, "rider_earnings_today": 610.0,
        "rider_experience_months": 11.0, "rider_experience_band": "intermediate",
        "rider_rating": 4.3, "rider_rating_band": "medium", "vehicle_type": "scooter",
        "current_incentive": 35.0, "membership_type": "pass_plus",
        "historical_delivery_cost": 55.0, "historical_travel_time": 26.0,
        "demand_level": "high", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1003", "customer_name": "Rahul Verma",
        "product_name": "Monthly Pantry Restock", "order_status": "placed",
        "city": "Mumbai", "city_tier": 1, "customer_lat": 19.0760, "customer_lon": 72.8777,
        "store_id": "DS022", "store_lat": 19.0700, "store_lon": 72.8800,
        "delivery_zone": "urban", "distance_km": 6.1, "distance_band": "5-10",
        "distance_to_radius_ratio": 0.61, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 18, "order_amount": 1650.0, "order_amount_band": "high",
        "order_weight_kg": 9.2, "order_amount_per_kg": 179.3,
        "order_year": 2026, "order_month": 9, "order_day": 14, "order_hour": 13, "order_dayofweek": 0,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 0, "is_weekend": 0, "time_of_day": "afternoon",
        "weather_condition": "rain", "weather_severity": 2, "rainfall_mm": 6.5, "has_rain": 1,
        "traffic_index": 71.0, "traffic_level": "high", "road_type": "main_road",
        "current_rider_load": 5.0, "previous_acceptance_rate": 0.66, "rider_earnings_today": 540.0,
        "rider_experience_months": 6.0, "rider_experience_band": "new",
        "rider_rating": 4.1, "rider_rating_band": "medium", "vehicle_type": "bike",
        "current_incentive": 45.0, "membership_type": "none",
        "historical_delivery_cost": 68.0, "historical_travel_time": 34.0,
        "demand_level": "high", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1004", "customer_name": "Sneha Reddy",
        "product_name": "Fresh Fruits & Vegetables Box", "order_status": "placed",
        "city": "Hyderabad", "city_tier": 1, "customer_lat": 17.3850, "customer_lon": 78.4867,
        "store_id": "DS007", "store_lat": 17.3900, "store_lon": 78.4900,
        "delivery_zone": "suburban", "distance_km": 0.9, "distance_band": "0-2",
        "distance_to_radius_ratio": 0.09, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 3, "order_amount": 260.0, "order_amount_band": "low",
        "order_weight_kg": 1.4, "order_amount_per_kg": 185.7,
        "order_year": 2026, "order_month": 9, "order_day": 15, "order_hour": 9, "order_dayofweek": 1,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 0, "is_weekend": 0, "time_of_day": "morning",
        "weather_condition": "clear", "weather_severity": 0, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 22.0, "traffic_level": "low", "road_type": "residential",
        "current_rider_load": 1.0, "previous_acceptance_rate": 0.92, "rider_earnings_today": 210.0,
        "rider_experience_months": 30.0, "rider_experience_band": "experienced",
        "rider_rating": 4.9, "rider_rating_band": "high", "vehicle_type": "bike",
        "current_incentive": 10.0, "membership_type": "pass_plus",
        "historical_delivery_cost": 32.0, "historical_travel_time": 12.0,
        "demand_level": "low", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1005", "customer_name": "Vikram Singh",
        "product_name": "Office Party Supplies", "order_status": "placed",
        "city": "Delhi", "city_tier": 1, "customer_lat": 28.7041, "customer_lon": 77.1025,
        "store_id": "DS031", "store_lat": 28.7100, "store_lon": 77.1100,
        "delivery_zone": "urban", "distance_km": 4.7, "distance_band": "2-5",
        "distance_to_radius_ratio": 0.47, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 22, "order_amount": 3100.0, "order_amount_band": "high",
        "order_weight_kg": 11.5, "order_amount_per_kg": 269.6,
        "order_year": 2026, "order_month": 9, "order_day": 18, "order_hour": 19, "order_dayofweek": 4,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 1, "is_weekend": 0, "time_of_day": "evening",
        "weather_condition": "haze", "weather_severity": 1, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 85.0, "traffic_level": "high", "road_type": "highway",
        "current_rider_load": 6.0, "previous_acceptance_rate": 0.58, "rider_earnings_today": 720.0,
        "rider_experience_months": 15.0, "rider_experience_band": "intermediate",
        "rider_rating": 4.2, "rider_rating_band": "medium", "vehicle_type": "scooter",
        "current_incentive": 60.0, "membership_type": "none",
        "historical_delivery_cost": 75.0, "historical_travel_time": 38.0,
        "demand_level": "high", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1006", "customer_name": "Ananya Iyer",
        "product_name": "Baby Care Bundle", "order_status": "placed",
        "city": "Pune", "city_tier": 2, "customer_lat": 18.5204, "customer_lon": 73.8567,
        "store_id": "DS019", "store_lat": 18.5250, "store_lon": 73.8600,
        "delivery_zone": "suburban", "distance_km": 2.6, "distance_band": "2-5",
        "distance_to_radius_ratio": 0.26, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 7, "order_amount": 690.0, "order_amount_band": "medium",
        "order_weight_kg": 2.8, "order_amount_per_kg": 246.4,
        "order_year": 2026, "order_month": 9, "order_day": 20, "order_hour": 11, "order_dayofweek": 6,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 0, "is_weekend": 1, "time_of_day": "morning",
        "weather_condition": "clear", "weather_severity": 0, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 40.0, "traffic_level": "medium", "road_type": "main_road",
        "current_rider_load": 2.0, "previous_acceptance_rate": 0.88, "rider_earnings_today": 380.0,
        "rider_experience_months": 20.0, "rider_experience_band": "experienced",
        "rider_rating": 4.6, "rider_rating_band": "high", "vehicle_type": "bike",
        "current_incentive": 15.0, "membership_type": "pass_plus",
        "historical_delivery_cost": 40.0, "historical_travel_time": 16.0,
        "demand_level": "medium", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1007", "customer_name": "Karthik Nair",
        "product_name": "Diwali Gifting Hamper", "order_status": "placed",
        "city": "Kolkata", "city_tier": 1, "customer_lat": 22.5726, "customer_lon": 88.3639,
        "store_id": "DS041", "store_lat": 22.5800, "store_lon": 88.3700,
        "delivery_zone": "urban", "distance_km": 5.3, "distance_band": "5-10",
        "distance_to_radius_ratio": 0.53, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 12, "order_amount": 2200.0, "order_amount_band": "high",
        "order_weight_kg": 5.0, "order_amount_per_kg": 440.0,
        "order_year": 2026, "order_month": 10, "order_day": 20, "order_hour": 17, "order_dayofweek": 2,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 1, "is_weekend": 0, "time_of_day": "evening",
        "weather_condition": "clear", "weather_severity": 0, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 78.0, "traffic_level": "high", "road_type": "main_road",
        "current_rider_load": 7.0, "previous_acceptance_rate": 0.50, "rider_earnings_today": 900.0,
        "rider_experience_months": 9.0, "rider_experience_band": "intermediate",
        "rider_rating": 4.0, "rider_rating_band": "medium", "vehicle_type": "scooter",
        "current_incentive": 70.0, "membership_type": "none",
        "historical_delivery_cost": 82.0, "historical_travel_time": 40.0,
        "demand_level": "high", "festival_day_flag": 1,
    },
    {
        "order_id": "ORD1008", "customer_name": "Meera Pillai",
        "product_name": "Home Cleaning Supplies", "order_status": "placed",
        "city": "Ahmedabad", "city_tier": 2, "customer_lat": 23.0225, "customer_lon": 72.5714,
        "store_id": "DS009", "store_lat": 23.0270, "store_lon": 72.5750,
        "delivery_zone": "suburban", "distance_km": 3.9, "distance_band": "2-5",
        "distance_to_radius_ratio": 0.39, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 6, "order_amount": 380.0, "order_amount_band": "low",
        "order_weight_kg": 4.1, "order_amount_per_kg": 92.7,
        "order_year": 2026, "order_month": 9, "order_day": 22, "order_hour": 15, "order_dayofweek": 1,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 0, "is_weekend": 0, "time_of_day": "afternoon",
        "weather_condition": "clear", "weather_severity": 0, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 35.0, "traffic_level": "low", "road_type": "residential",
        "current_rider_load": 2.0, "previous_acceptance_rate": 0.80, "rider_earnings_today": 300.0,
        "rider_experience_months": 14.0, "rider_experience_band": "intermediate",
        "rider_rating": 4.4, "rider_rating_band": "medium", "vehicle_type": "bike",
        "current_incentive": 18.0, "membership_type": "pass_plus",
        "historical_delivery_cost": 38.0, "historical_travel_time": 17.0,
        "demand_level": "low", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1009", "customer_name": "Aditya Joshi",
        "product_name": "Late Night Snack Pack", "order_status": "placed",
        "city": "Chennai", "city_tier": 1, "customer_lat": 13.0674, "customer_lon": 80.2376,
        "store_id": "DS002", "store_lat": 13.0700, "store_lon": 80.2400,
        "delivery_zone": "urban", "distance_km": 1.2, "distance_band": "0-2",
        "distance_to_radius_ratio": 0.12, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 2, "order_amount": 180.0, "order_amount_band": "low",
        "order_weight_kg": 0.8, "order_amount_per_kg": 225.0,
        "order_year": 2026, "order_month": 9, "order_day": 24, "order_hour": 23, "order_dayofweek": 3,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 0, "is_weekend": 0, "time_of_day": "night",
        "weather_condition": "clear", "weather_severity": 0, "rainfall_mm": 0.0, "has_rain": 0,
        "traffic_index": 15.0, "traffic_level": "low", "road_type": "residential",
        "current_rider_load": 1.0, "previous_acceptance_rate": 0.70, "rider_earnings_today": 150.0,
        "rider_experience_months": 4.0, "rider_experience_band": "new",
        "rider_rating": 3.9, "rider_rating_band": "low", "vehicle_type": "bike",
        "current_incentive": 25.0, "membership_type": "none",
        "historical_delivery_cost": 30.0, "historical_travel_time": 14.0,
        "demand_level": "low", "festival_day_flag": 0,
    },
    {
        "order_id": "ORD1010", "customer_name": "Divya Menon",
        "product_name": "Electronics Accessories Order", "order_status": "placed",
        "city": "Bengaluru", "city_tier": 1, "customer_lat": 12.9352, "customer_lon": 77.6245,
        "store_id": "DS017", "store_lat": 12.9400, "store_lon": 77.6300,
        "delivery_zone": "urban", "distance_km": 8.4, "distance_band": "5-10",
        "distance_to_radius_ratio": 0.84, "service_radius_km": 10.0, "within_service_radius": 1,
        "item_count": 4, "order_amount": 1450.0, "order_amount_band": "high",
        "order_weight_kg": 1.6, "order_amount_per_kg": 906.3,
        "order_year": 2026, "order_month": 9, "order_day": 26, "order_hour": 8, "order_dayofweek": 5,
        "is_month_start": 0, "is_month_end": 0, "is_peak_hour": 1, "is_weekend": 1, "time_of_day": "morning",
        "weather_condition": "rain", "weather_severity": 2, "rainfall_mm": 9.2, "has_rain": 1,
        "traffic_index": 66.0, "traffic_level": "medium", "road_type": "highway",
        "current_rider_load": 3.0, "previous_acceptance_rate": 0.75, "rider_earnings_today": 420.0,
        "rider_experience_months": 18.0, "rider_experience_band": "intermediate",
        "rider_rating": 4.3, "rider_rating_band": "medium", "vehicle_type": "scooter",
        "current_incentive": 40.0, "membership_type": "pass_plus",
        "historical_delivery_cost": 62.0, "historical_travel_time": 30.0,
        "demand_level": "medium", "festival_day_flag": 0,
    },
]


# ------------------------------------------------------------
# Ensure orders table exists
# ------------------------------------------------------------
def ensure_orders_table() -> None:
    """
    Create the `orders` table if it does not already exist.
    Safe to call on every application startup.
    """

    query = """
        CREATE TABLE IF NOT EXISTS orders (
            order_id VARCHAR(20) PRIMARY KEY,
            customer_name VARCHAR(100),
            product_name VARCHAR(150),
            order_status VARCHAR(30) DEFAULT 'placed',
            city VARCHAR(50),
            city_tier INTEGER,
            customer_lat DOUBLE PRECISION,
            customer_lon DOUBLE PRECISION,
            store_id VARCHAR(20),
            store_lat DOUBLE PRECISION,
            store_lon DOUBLE PRECISION,
            delivery_zone VARCHAR(30),
            distance_km DOUBLE PRECISION,
            distance_band VARCHAR(20),
            distance_to_radius_ratio DOUBLE PRECISION,
            service_radius_km DOUBLE PRECISION,
            within_service_radius INTEGER,
            item_count INTEGER,
            order_amount DOUBLE PRECISION,
            order_amount_band VARCHAR(20),
            order_weight_kg DOUBLE PRECISION,
            order_amount_per_kg DOUBLE PRECISION,
            order_year INTEGER,
            order_month INTEGER,
            order_day INTEGER,
            order_hour INTEGER,
            order_dayofweek INTEGER,
            is_month_start INTEGER,
            is_month_end INTEGER,
            is_peak_hour INTEGER,
            is_weekend INTEGER,
            time_of_day VARCHAR(20),
            weather_condition VARCHAR(30),
            weather_severity INTEGER,
            rainfall_mm DOUBLE PRECISION,
            has_rain INTEGER,
            traffic_index DOUBLE PRECISION,
            traffic_level VARCHAR(20),
            road_type VARCHAR(30),
            current_rider_load DOUBLE PRECISION,
            previous_acceptance_rate DOUBLE PRECISION,
            rider_earnings_today DOUBLE PRECISION,
            rider_experience_months DOUBLE PRECISION,
            rider_experience_band VARCHAR(20),
            rider_rating DOUBLE PRECISION,
            rider_rating_band VARCHAR(20),
            vehicle_type VARCHAR(20),
            current_incentive DOUBLE PRECISION,
            membership_type VARCHAR(30),
            historical_delivery_cost DOUBLE PRECISION,
            historical_travel_time DOUBLE PRECISION,
            demand_level VARCHAR(20),
            festival_day_flag INTEGER,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(query)

            connection.commit()


# ------------------------------------------------------------
# Seed sample orders (idempotent)
# ------------------------------------------------------------
def seed_sample_orders() -> int:
    """
    Insert the built-in sample orders (ORD1001 - ORD1010),
    skipping any order_id that already exists. Safe to call
    on every application startup.

    Returns the number of newly inserted rows.
    """

    columns = ORDER_DISPLAY_COLUMNS + ORDER_FEATURE_COLUMNS
    column_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    query = f"""
        INSERT INTO orders ({column_list})
        VALUES ({placeholders})
        ON CONFLICT (order_id) DO NOTHING;
    """

    inserted = 0

    with database_connection() as connection:

        with connection.cursor() as cursor:

            for order in SAMPLE_ORDERS:

                values = tuple(order[column] for column in columns)

                cursor.execute(query, values)

                inserted += cursor.rowcount

            connection.commit()

    return inserted


# ------------------------------------------------------------
# Get order by ID
# ------------------------------------------------------------
def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a single order (customer/product info plus the full
    ML feature set) by its order_id. Lookup is case-insensitive
    and trims whitespace, so "ord1001", " ORD1001 " etc. all match.
    """

    query = f"""
        SELECT {", ".join(ORDER_COLUMNS)}
        FROM orders
        WHERE UPPER(order_id) = UPPER(%s);
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (order_id.strip(),),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return dict(zip(ORDER_COLUMNS, row))


# ------------------------------------------------------------
# List recent order IDs (used for UI hints)
# ------------------------------------------------------------
def list_order_ids(limit: int = 20) -> List[str]:

    query = """
        SELECT order_id
        FROM orders
        ORDER BY order_id ASC
        LIMIT %s;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(query, (limit,))

            return [row[0] for row in cursor.fetchall()]


# ------------------------------------------------------------
# Save prediction
# ------------------------------------------------------------
def save_prediction(
    model_version: str,
    delivery_charge: float,
    delivery_time_minutes: float,
    rider_acceptance_probability: float,
    rider_acceptance: int,
    weather_source: Optional[str] = None,
    traffic_source: Optional[str] = None,
) -> int:

    query = """
        INSERT INTO prediction_audit (
            model_version,
            delivery_charge,
            delivery_time_minutes,
            rider_acceptance_probability,
            rider_acceptance,
            weather_source,
            traffic_source
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (
                    model_version,
                    delivery_charge,
                    delivery_time_minutes,
                    rider_acceptance_probability,
                    rider_acceptance,
                    weather_source,
                    traffic_source,
                ),
            )

            result = cursor.fetchone()

            if not result:
                raise RuntimeError(
                    "Prediction insert did not return an ID."
                )

            return int(result[0])


# ------------------------------------------------------------
# Get prediction by ID
# ------------------------------------------------------------
def get_prediction_by_id(
    prediction_id: int,
) -> Optional[Dict[str, Any]]:

    query = """
        SELECT
            id,
            request_timestamp,
            model_version,
            delivery_charge,
            delivery_time_minutes,
            rider_acceptance_probability,
            rider_acceptance,
            weather_source,
            traffic_source,
            created_at
        FROM prediction_audit
        WHERE id = %s;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (prediction_id,),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            columns = [
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

            return dict(zip(columns, row))


# ------------------------------------------------------------
# Get recent predictions
# ------------------------------------------------------------
def get_recent_predictions(
    limit: int = 20,
) -> List[Dict[str, Any]]:

    if limit < 1:
        raise ValueError("limit must be greater than zero.")

    limit = min(limit, 100)

    query = f"""
        SELECT
            id,
            request_timestamp,
            model_version,
            delivery_charge,
            delivery_time_minutes,
            rider_acceptance_probability,
            rider_acceptance,
            weather_source,
            traffic_source,
            created_at
        FROM prediction_audit
        ORDER BY id DESC
        LIMIT {limit};
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(query)

            rows = cursor.fetchall()

            columns = [
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

            return [
                dict(zip(columns, row))
                for row in rows
            ]


# ------------------------------------------------------------
# Count predictions
# ------------------------------------------------------------
def count_predictions() -> int:

    query = """
        SELECT COUNT(*)
        FROM prediction_audit;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(query)

            result = cursor.fetchone()

            if not result:
                return 0

            return int(result[0])


# ------------------------------------------------------------
# Repository validation
# ------------------------------------------------------------
if __name__ == "__main__":

    print("=" * 70)
    print("STEP 16.3 - POSTGRESQL PREDICTION REPOSITORY")
    print("=" * 70)

    print("\n0. Testing orders table + seed data...")

    ensure_orders_table()
    newly_inserted = seed_sample_orders()

    print(f"   Orders table ready. Newly seeded rows: {newly_inserted}")

    sample_order = get_order_by_id("ORD1001")

    assert sample_order is not None
    assert sample_order["order_id"] == "ORD1001"
    assert sample_order["city"] == "Chennai"

    missing_order = get_order_by_id("ORD9999")
    assert missing_order is None

    print("   ORDERS TABLE + LOOKUP: PASSED")

    print("\n1. Testing prediction insert...")

    prediction_id = save_prediction(
        model_version="HGB-v1",
        delivery_charge=23.514602084535156,
        delivery_time_minutes=24.446456288765443,
        rider_acceptance_probability=0.9614576600000068,
        rider_acceptance=1,
        weather_source="openweather-live",
        traffic_source="tomtom",
    )

    assert prediction_id > 0

    print(
        f"   Prediction inserted successfully. "
        f"ID: {prediction_id}"
    )
    print("   INSERT: PASSED")

    # --------------------------------------------------------
    # Retrieve inserted prediction
    # --------------------------------------------------------
    print("\n2. Testing prediction retrieval...")

    prediction = get_prediction_by_id(
        prediction_id
    )

    assert prediction is not None
    assert prediction["id"] == prediction_id
    assert prediction["model_version"] == "HGB-v1"

    assert float(
        prediction["delivery_charge"]
    ) == 23.514602084535156

    assert float(
        prediction["delivery_time_minutes"]
    ) == 24.446456288765443

    assert float(
        prediction["rider_acceptance_probability"]
    ) == 0.9614576600000068

    assert prediction["rider_acceptance"] == 1
    assert prediction["weather_source"] == "openweather-live"
    assert prediction["traffic_source"] == "tomtom"

    print("   SELECT by ID: PASSED")

    # --------------------------------------------------------
    # Recent predictions
    # --------------------------------------------------------
    print("\n3. Testing recent predictions...")

    recent = get_recent_predictions(limit=10)

    assert isinstance(recent, list)
    assert len(recent) >= 1

    print(
        f"   Retrieved {len(recent)} recent prediction(s)."
    )
    print("   RECENT PREDICTIONS: PASSED")

    # --------------------------------------------------------
    # Count
    # --------------------------------------------------------
    print("\n4. Testing prediction count...")

    count = count_predictions()

    assert count >= 1

    print(f"   Total predictions: {count}")
    print("   COUNT: PASSED")

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 16.3 RESULT")
    print("=" * 70)

    print("PostgreSQL INSERT: PASSED")
    print("PostgreSQL SELECT: PASSED")
    print("Recent prediction retrieval: PASSED")
    print("Prediction count: PASSED")

    print("\nOVERALL STATUS: PASSED")
    print("=" * 70)
