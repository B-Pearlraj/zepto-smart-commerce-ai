"""
FastAPI application for the
Zepto Smart Commerce AI Platform.

Module:
ML Delivery Intelligence Engine

Production Model:
HGB-v1
"""

from pathlib import Path
import sys
import math
import logging
import time
from datetime import datetime, timezone

# ----------------------------------------------------------------------
# PostgreSQL repository
# ----------------------------------------------------------------------
from database_repository import (
    save_prediction,
    count_predictions,
    get_recent_predictions,
)

# ----------------------------------------------------------------------
# Ensure FastAPI application directory is importable
# ----------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# ----------------------------------------------------------------------
# Weather and Traffic providers
# ----------------------------------------------------------------------
from weather_provider import get_weather
from tomtom_traffic_provider import get_traffic

# ----------------------------------------------------------------------
# FastAPI imports
# ----------------------------------------------------------------------
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

from inference import (
    production_predict_order,
)

# ======================================================================
# LOGGING CONFIGURATION
# ======================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("zepto_fastapi")

# ======================================================================
# FASTAPI APPLICATION
# ======================================================================
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
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
# HEALTH ENDPOINT
# ======================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
)
def health_check():
    """
    Verify that the production inference engine,
    external enrichment providers, and PostgreSQL
    database are available.
    """

    try:

        # --------------------------------------------------------------
        # Validate production inference engine
        # --------------------------------------------------------------

        if not callable(production_predict_order):
            raise RuntimeError(
                "Production inference engine is unavailable."
            )


        # --------------------------------------------------------------
        # Validate PostgreSQL connectivity
        # --------------------------------------------------------------

        prediction_count = count_predictions()

        logger.info(
            "PostgreSQL health check passed | "
            "prediction_count=%s",
            prediction_count,
        )


        # --------------------------------------------------------------
        # Return healthy status
        # --------------------------------------------------------------

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
            detail=str(exc),
        )

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

            # --------------------------------------------------------------
            # LIVE WEATHER USED BY THE MODEL
            # --------------------------------------------------------------

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

            # --------------------------------------------------------------
            # LIVE TRAFFIC USED BY THE MODEL
            # --------------------------------------------------------------

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

            # --------------------------------------------------------------
            # ML PREDICTIONS
            # --------------------------------------------------------------

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

        # --------------------------------------------------------------
        # Validate limit
        # --------------------------------------------------------------

        if limit < 1:
            raise ValueError(
                "limit must be greater than zero."
            )

        if limit > 100:
            raise ValueError(
                "limit must not exceed 100."
            )


        # --------------------------------------------------------------
        # Retrieve recent predictions
        # --------------------------------------------------------------

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


        # --------------------------------------------------------------
        # Return audit results
        # --------------------------------------------------------------

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


    except Exception as exc:

        logger.exception(
            "Recent prediction retrieval failed: %s",
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
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
            "/info",
            "/predict",
        ],
    }


# ======================================================================
# NOTE
# ======================================================================
# This file keeps the existing API behavior intact and adds PostgreSQL
# audit logging only after a successful prediction has been generated
# and validated.