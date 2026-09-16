from typing import Any, Dict, List, Optional

from database import database_connection


# ------------------------------------------------------------
# Orders table — column definitions
# ------------------------------------------------------------
# Mirrors the schema created by create_orders_table.py and
# populated by load_orders_to_postgres.py: order_id plus the
# full ML feature set used by inference.py. There is no
# separate "orders" lookup layer here — this module just reads
# the same table those scripts already create/populate.
# ------------------------------------------------------------

ORDER_COLUMNS: List[str] = [
    "order_id",

    # Location / store
    "city",
    "city_tier",
    "customer_lat",
    "customer_lon",
    "store_id",
    "store_lat",
    "store_lon",
    "delivery_zone",

    # Distance
    "distance_km",
    "distance_band",
    "distance_to_radius_ratio",
    "service_radius_km",
    "within_service_radius",

    # Order
    "item_count",
    "order_amount",
    "order_amount_band",
    "order_weight_kg",
    "order_amount_per_kg",

    # Date / time
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

    # Weather
    "weather_condition",
    "weather_severity",
    "rainfall_mm",
    "has_rain",

    # Traffic / road
    "traffic_index",
    "traffic_level",
    "road_type",

    # Rider
    "current_rider_load",
    "previous_acceptance_rate",
    "rider_earnings_today",
    "rider_experience_months",
    "rider_experience_band",
    "rider_rating",
    "rider_rating_band",
    "vehicle_type",
    "current_incentive",

    # Customer / business
    "membership_type",
    "historical_delivery_cost",
    "historical_travel_time",
    "demand_level",
    "festival_day_flag",
]

# All feature columns except order_id itself — this is exactly
# the set of keys the ML feature payload (DEFAULT_PAYLOAD in
# app.py) needs.
ORDER_FEATURE_COLUMNS: List[str] = ORDER_COLUMNS[1:]

# Columns returned by a full order lookup (adds the two
# metadata timestamp columns from create_orders_table.py).
ORDER_SELECT_COLUMNS: List[str] = ORDER_COLUMNS + ["created_at", "updated_at"]


# ------------------------------------------------------------
# Get order by ID
# ------------------------------------------------------------
def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a single order (full ML feature set) by its order_id.

    Tries an exact match first (uses the order_id primary key
    index directly). Falls back to a case-insensitive match if
    that misses, so "ord00042" still finds "ORD00042".
    """

    normalized = (order_id or "").strip()

    if not normalized:
        return None

    columns_sql = ", ".join(ORDER_SELECT_COLUMNS)

    exact_query = f"""
        SELECT {columns_sql}
        FROM orders
        WHERE order_id = %s;
    """

    fallback_query = f"""
        SELECT {columns_sql}
        FROM orders
        WHERE UPPER(order_id) = UPPER(%s)
        LIMIT 1;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(exact_query, (normalized,))
            row = cursor.fetchone()

            if row is None:
                cursor.execute(fallback_query, (normalized,))
                row = cursor.fetchone()

            if row is None:
                return None

            return dict(zip(ORDER_SELECT_COLUMNS, row))


# ------------------------------------------------------------
# List recent order IDs (used for UI hints)
# ------------------------------------------------------------
def list_order_ids(limit: int = 5) -> List[str]:
    """
    Return the most recently loaded order_ids, for showing a
    few example IDs in the chatbot UI.
    """

    query = """
        SELECT order_id
        FROM orders
        ORDER BY created_at DESC
        LIMIT %s;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(query, (limit,))

            return [row[0] for row in cursor.fetchall()]


# ------------------------------------------------------------
# Count orders (used for a startup / health sanity check)
# ------------------------------------------------------------
def count_orders() -> int:

    query = """
        SELECT COUNT(*)
        FROM orders;
    """

    with database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(query)

            result = cursor.fetchone()

            if not result:
                return 0

            return int(result[0])



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

    print("\n0. Testing orders lookup against the real orders table...")

    order_count = count_orders()
    print(f"   Orders table currently has {order_count:,} row(s).")

    if order_count > 0:

        sample_id = list_order_ids(limit=1)[0]
        sample_order = get_order_by_id(sample_id)

        assert sample_order is not None
        assert sample_order["order_id"] == sample_id

        missing_order = get_order_by_id("THIS_ORDER_ID_DOES_NOT_EXIST")
        assert missing_order is None

        print(f"   Looked up order '{sample_id}' successfully.")
        print("   ORDERS LOOKUP: PASSED")

    else:
        print(
            "   Orders table is empty — run create_orders_table.py and "
            "load_orders_to_postgres.py first to load real order data."
        )

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
