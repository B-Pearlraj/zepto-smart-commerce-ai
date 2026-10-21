"""
FastAPI application for the
Zepto Smart Commerce AI Platform.

Module:
ML Delivery Intelligence Engine

Production Model:
HGB-v1
"""

import logging
import math
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------------------------------------------------
# Ensure FastAPI application directory is importable
# (must happen before the project imports below)
# ----------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import psycopg
from fastapi import FastAPI, HTTPException

from config import (
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    MODEL_VERSION,
)

from schemas import (
    DeliveryPredictionRequest,
    DeliveryPredictionResponse,
    HealthResponse,
    ErrorResponse,
)

from inference import production_predict_order

# ----------------------------------------------------------------------
# Weather and Traffic providers
# ----------------------------------------------------------------------
from weather_provider import get_weather
from tomtom_traffic_provider import get_traffic

# ----------------------------------------------------------------------
# PostgreSQL (Neon) repository
# ----------------------------------------------------------------------
from database import DatabaseUnavailableError

from database_repository import (
    save_prediction,
    count_predictions,
    get_recent_predictions,
    ensure_database_schema,
    seed_sample_orders,
    get_order_by_id,
)

# ======================================================================
# LOGGING CONFIGURATION
# ======================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("zepto_fastapi")

# Errors that mean "the database could not be reached right now".
DB_UNAVAILABLE_ERRORS = (
    DatabaseUnavailableError,
    psycopg.OperationalError,
    psycopg.InterfaceError,
)

DB_UNAVAILABLE_MESSAGE = (
    "The database is temporarily unavailable. "
    "Please try again in a few seconds."
)


# ======================================================================
# STARTUP: ENSURE TABLES EXIST + SEED SAMPLE ORDERS
# ======================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Create the `orders` and `prediction_audit` tables if they don't
    exist yet and seed the sample orders (ORD1001 - ORD1010).
    Both steps are idempotent, so this is safe on every restart and
    makes a brand-new Neon database work on the first deploy.
    """

    try:
        ensure_database_schema()
        newly_seeded = seed_sample_orders()

        logger.info(
            "Database schema ready | newly_seeded=%s",
            newly_seeded,
        )

    except Exception as exc:
        # Do not stop the API from starting; the first request that
        # touches the database will report the problem clearly.
        logger.exception(
            "Database setup failed: %s",
            str(exc),
        )

    yield


# ======================================================================
# FASTAPI APPLICATION
# ======================================================================
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
)


# ======================================================================
# HTTP REQUEST LOGGING MIDDLEWARE
# ======================================================================
@app.middleware("http")
async def log_requests(request, call_next):
    """
    Log API requests without logging request payloads.

    Logged information:
        - UTC timestamp
        - HTTP method
        - endpoint path
        - response status
        - request processing time

    Request payloads are intentionally not logged.
    """
    start_time = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "%s | %s %s | status=%s | duration_ms=%.2f",
            timestamp,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.exception(
            "%s | %s %s | status=500 | duration_ms=%.2f | error=%s",
            timestamp,
            request.method,
            request.url.path,
            elapsed_ms,
            str(exc),
        )

        raise


# ======================================================================
# ROOT ENDPOINT
# ======================================================================
@app.get("/")
def root():
    """
    API root endpoint.
    """
    return {
        "status": "success",
        "application": API_TITLE,
        "module": "ML Delivery Intelligence Engine",
        "model_version": MODEL_VERSION,
        "api_version": API_VERSION,
    }


# ======================================================================
# HEALTH ENDPOINTS
# ======================================================================
@app.get(
    "/health",
    response_model=HealthResponse,
)
def health_check():
    """
    Lightweight health check used by the Streamlit sidebar.

    It does NOT query the database on purpose: Neon scales to zero
    when idle, and pinging the database from a frequent health check
    would keep it awake and use up your compute allowance.
    Use /health/db to test the database connection.
    """

    try:

        if not callable(production_predict_order):
            raise RuntimeError(
                "Production inference engine is unavailable."
            )

        return HealthResponse(
            status="healthy",
            model_version=MODEL_VERSION,
            delivery_charge_model="loaded",
            delivery_time_model="loaded",
            rider_acceptance_model="loaded",
            weather_provider="available",
            traffic_provider="available",
        )

    except Exception as exc:

        logger.exception(
            "Health check failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=503,
            detail="Service is not healthy.",
        )


@app.get("/health/db")
def database_health_check():
    """
    Deep health check: opens a real connection to PostgreSQL (Neon)
    and runs a query. Open this URL in a browser to test the database.
    """

    try:
        prediction_count = count_predictions()

        logger.info(
            "PostgreSQL health check passed | prediction_count=%s",
            prediction_count,
        )

        return {
            "status": "healthy",
            "database": "connected",
            "prediction_count": prediction_count,
        }

    except DB_UNAVAILABLE_ERRORS as exc:

        logger.exception(
            "Database health check failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=503,
            detail=DB_UNAVAILABLE_MESSAGE,
        )

    except Exception as exc:

        logger.exception(
            "Database health check failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail="Database check failed. See the server logs.",
        )


# ======================================================================
# ORDER LOOKUP ENDPOINT
# ======================================================================
@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """
    Look up a single order by order_id.

    Used by the chatbot's "type an order ID -> see the order's
    details -> confirm -> predict" flow. Returns the order's
    customer/product info plus the full ML feature set stored
    for that order.
    """

    try:
        order = get_order_by_id(order_id)

    except DB_UNAVAILABLE_ERRORS as exc:
        logger.exception(
            "Order lookup failed (database unavailable) | "
            "order_id=%s | error=%s",
            order_id,
            str(exc),
        )

        raise HTTPException(
            status_code=503,
            detail=DB_UNAVAILABLE_MESSAGE,
        )

    except Exception as exc:
        logger.exception(
            "Order lookup failed | order_id=%s | error=%s",
            order_id,
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail="Unexpected error while looking up the order.",
        )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail=f"No order found with ID '{order_id}'.",
        )

    return {
        "status": "success",
        "order": order,
    }


# ======================================================================
# PREDICTION ENDPOINT
# ======================================================================
@app.post(
    "/predict",
    response_model=DeliveryPredictionResponse,
)
def predict(
    request: DeliveryPredictionRequest,
):
    """
    Generate a complete LIVE delivery prediction.

    Processing:

    1. User provides order/customer/rider information.
    2. Current weather is retrieved from OpenWeather.
    3. Current traffic is retrieved from TomTom Traffic Flow.
    4. Live weather and traffic are injected into the ML input.
    5. HGB-v1 predicts:
       - Delivery charge
       - Estimated delivery time
       - Rider acceptance probability
       - Rider acceptance classification
    6. The live conditions and predictions are stored in PostgreSQL.

    No historical weather or traffic fallback is used.
    """
    try:
        # --------------------------------------------------------------
        # Convert Pydantic request to dictionary
        # --------------------------------------------------------------
        order_data = request.model_dump(exclude_unset=False)

        # --------------------------------------------------------------
        # Live weather enrichment
        # --------------------------------------------------------------
        weather_data = get_weather(
            latitude=request.customer_lat,
            longitude=request.customer_lon,
        )

        logger.info(
            "Weather enrichment completed | source=%s | "
            "condition=%s | severity=%s | rainfall_mm=%s",
            weather_data.get("source"),
            weather_data.get("weather_condition"),
            weather_data.get("weather_severity"),
            weather_data.get("rainfall_mm"),
        )

        # --------------------------------------------------------------
        # Update ML input with live/fallback weather
        # --------------------------------------------------------------
        order_data["weather_condition"] = weather_data["weather_condition"]
        order_data["weather_severity"] = weather_data["weather_severity"]
        order_data["rainfall_mm"] = weather_data["rainfall_mm"]
        order_data["has_rain"] = weather_data["has_rain"]

        # --------------------------------------------------------------
        # Live TomTom traffic enrichment
        # --------------------------------------------------------------
        traffic_data = get_traffic(
            latitude=request.customer_lat,
            longitude=request.customer_lon,
        )

        logger.info(
            "Traffic enrichment completed | source=%s | "
            "level=%s | index=%s",
            traffic_data.get("source"),
            traffic_data.get("traffic_level"),
            traffic_data.get("traffic_index"),
        )

        # --------------------------------------------------------------
        # Update ML input with live/fallback traffic
        # --------------------------------------------------------------
        order_data["traffic_index"] = traffic_data["traffic_index"]
        order_data["traffic_level"] = traffic_data["traffic_level"]

        # --------------------------------------------------------------
        # Run production inference
        # --------------------------------------------------------------
        prediction = production_predict_order(order_data)

        # --------------------------------------------------------------
        # Validate predictions
        # --------------------------------------------------------------
        delivery_charge = float(prediction["delivery_charge"])
        delivery_time = float(prediction["delivery_time_minutes"])
        acceptance_probability = float(
            prediction["rider_acceptance_probability"]
        )
        acceptance = int(prediction["rider_acceptance"])

        values_to_validate = [
            delivery_charge,
            delivery_time,
            acceptance_probability,
        ]

        if not all(math.isfinite(value) for value in values_to_validate):
            raise ValueError("API generated a non-finite prediction.")

        if delivery_charge <= 0:
            raise ValueError("Delivery charge prediction must be positive.")

        if delivery_time <= 0:
            raise ValueError("Delivery time prediction must be positive.")

        if not 0 <= acceptance_probability <= 1:
            raise ValueError(
                "Acceptance probability must be between 0 and 1."
            )

        if acceptance not in (0, 1):
            raise ValueError("Acceptance prediction must be 0 or 1.")

        # --------------------------------------------------------------
        # Build API response
        # --------------------------------------------------------------
        prediction_response = DeliveryPredictionResponse(
            status="success",
            model_version=MODEL_VERSION,

            # ----------------------------------------------------------
            # LIVE WEATHER USED BY THE MODEL
            # ----------------------------------------------------------
            weather={
                "source": weather_data["source"],
                "location_name": weather_data.get(
                    "location_name"
                ),
                "weather_condition": weather_data[
                    "weather_condition"
                ],
                "description": weather_data[
                    "description"
                ],
                "temperature_c": weather_data.get(
                    "temperature_c"
                ),
                "feels_like_c": weather_data.get(
                    "feels_like_c"
                ),
                "humidity_percent": weather_data.get(
                    "humidity_percent"
                ),
                "pressure_hpa": weather_data.get(
                    "pressure_hpa"
                ),
                "rainfall_mm": weather_data[
                    "rainfall_mm"
                ],
                "has_rain": weather_data[
                    "has_rain"
                ],
                "weather_severity": weather_data[
                    "weather_severity"
                ],
            },

            # ----------------------------------------------------------
            # LIVE TRAFFIC USED BY THE MODEL
            # ----------------------------------------------------------
            traffic={
                "source": traffic_data["source"],
                "current_speed_kmh": traffic_data[
                    "current_speed_kmh"
                ],
                "free_flow_speed_kmh": traffic_data[
                    "free_flow_speed_kmh"
                ],
                "traffic_index": traffic_data[
                    "traffic_index"
                ],
                "traffic_level": traffic_data[
                    "traffic_level"
                ],
            },

            # ----------------------------------------------------------
            # ML PREDICTIONS
            # ----------------------------------------------------------
            delivery_charge=delivery_charge,

            delivery_time_minutes=delivery_time,

            rider_acceptance_probability=(
                acceptance_probability
            ),

            rider_acceptance=acceptance,
        )

        # --------------------------------------------------------------
        # PostgreSQL prediction audit logging
        # --------------------------------------------------------------
        try:
            prediction_id = save_prediction(
                model_version=MODEL_VERSION,
                delivery_charge=delivery_charge,
                delivery_time_minutes=delivery_time,
                rider_acceptance_probability=acceptance_probability,
                rider_acceptance=acceptance,
                weather_source=weather_data.get("source"),
                traffic_source=traffic_data.get("source"),
            )

            logger.info(
                "Prediction saved to PostgreSQL | prediction_id=%s",
                prediction_id,
            )

        except Exception as database_error:
            # Database failure must NOT cause a valid
            # ML prediction request to fail.
            logger.exception(
                "PostgreSQL audit logging failed: %s",
                str(database_error),
            )

        # --------------------------------------------------------------
        # Return API response
        # --------------------------------------------------------------
        return prediction_response

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception(
            "Prediction request failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ======================================================================
# PREDICTION AUDIT ENDPOINT
# ======================================================================
@app.get(
    "/predictions/recent",
)
def recent_predictions(limit: int = 20):
    """
    Return recent prediction audit records from PostgreSQL.

    Parameters:
        limit:
            Number of recent records to return.
            Maximum allowed value is 100.
    """

    try:

        if limit < 1:
            raise ValueError(
                "limit must be greater than zero."
            )

        if limit > 100:
            raise ValueError(
                "limit must not exceed 100."
            )

        predictions = get_recent_predictions(
            limit
        )

        # --------------------------------------------------------------
        # Convert database records into JSON-safe values
        # --------------------------------------------------------------
        results = []

        for prediction in predictions:

            record = dict(prediction)

            if record.get("request_timestamp") is not None:
                record["request_timestamp"] = (
                    record["request_timestamp"].isoformat()
                )

            if record.get("created_at") is not None:
                record["created_at"] = (
                    record["created_at"].isoformat()
                )

            results.append(record)

        return {
            "status": "success",
            "count": len(results),
            "predictions": results,
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except DB_UNAVAILABLE_ERRORS as exc:

        logger.exception(
            "Recent prediction retrieval failed "
            "(database unavailable): %s",
            str(exc),
        )

        raise HTTPException(
            status_code=503,
            detail=DB_UNAVAILABLE_MESSAGE,
        )

    except Exception as exc:

        logger.exception(
            "Recent prediction retrieval failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail="Unexpected error while loading recent predictions.",
        )


# ======================================================================
# APPLICATION INFORMATION
# ======================================================================
@app.get("/info")
def application_info():
    """
    Return basic application and model information.
    """
    return {
        "application": API_TITLE,
        "description": API_DESCRIPTION,
        "api_version": API_VERSION,
        "model_version": MODEL_VERSION,
        "endpoints": [
            "/",
            "/health",
            "/health/db",
            "/info",
            "/orders/{order_id}",
            "/predict",
            "/predictions/recent",
        ],
    }
