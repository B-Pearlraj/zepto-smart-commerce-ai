from typing import Any, Dict, List, Optional

from database import database_connection


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
