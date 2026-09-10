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
import json
import math
import logging
import time
from datetime import datetime, timezone


# ----------------------------------------------------------------------
# Ensure FastAPI application directory is importable
# ----------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


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

        elapsed_ms = (
            time.perf_counter() - start_time
        ) * 1000

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

        elapsed_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.exception(
            "%s | %s %s | status=500 | "
            "duration_ms=%.2f | error=%s",
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
    Verify that the production inference engine is available.
    """

    try:

        # Verify the inference function exists.
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
        )

    except Exception as exc:

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
    Generate:

    1. Delivery charge prediction
    2. Delivery time prediction
    3. Rider acceptance probability
    4. Rider acceptance classification
    """

    try:

        # --------------------------------------------------------------
        # Convert Pydantic request to dictionary
        # --------------------------------------------------------------

        order_data = request.model_dump(
            exclude_unset=False
        )

        # --------------------------------------------------------------
        # Run production inference
        # --------------------------------------------------------------

        prediction = production_predict_order(
            order_data
        )

        # --------------------------------------------------------------
        # Validate predictions
        # --------------------------------------------------------------

        delivery_charge = float(
            prediction["delivery_charge"]
        )

        delivery_time = float(
            prediction["delivery_time_minutes"]
        )

        acceptance_probability = float(
            prediction[
                "rider_acceptance_probability"
            ]
        )

        acceptance = int(
            prediction["rider_acceptance"]
        )

        values_to_validate = [
            delivery_charge,
            delivery_time,
            acceptance_probability,
        ]

        if not all(
            math.isfinite(value)
            for value in values_to_validate
        ):
            raise ValueError(
                "API generated a non-finite prediction."
            )

        if delivery_charge <= 0:
            raise ValueError(
                "Delivery charge prediction must be positive."
            )

        if delivery_time <= 0:
            raise ValueError(
                "Delivery time prediction must be positive."
            )

        if not 0 <= acceptance_probability <= 1:
            raise ValueError(
                "Acceptance probability must be between 0 and 1."
            )

        if acceptance not in (0, 1):
            raise ValueError(
                "Acceptance prediction must be 0 or 1."
            )

        # --------------------------------------------------------------
        # Return API response
        # --------------------------------------------------------------

        return DeliveryPredictionResponse(
            status="success",
            model_version=MODEL_VERSION,
            delivery_charge=delivery_charge,
            delivery_time_minutes=delivery_time,
            rider_acceptance_probability=(
                acceptance_probability
            ),
            rider_acceptance=acceptance,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except Exception as exc:

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