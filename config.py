import os
from pathlib import Path

from dotenv import load_dotenv


# ======================================================================
# LOAD ENVIRONMENT VARIABLES
# ======================================================================

load_dotenv()


# ======================================================================
# PROJECT PATHS
# ======================================================================

BASE_DIR = Path(__file__).resolve().parent

MODELS_DIR = BASE_DIR / "models"
CONFIG_DIR = BASE_DIR / "config"
REPORTS_DIR = BASE_DIR / "reports"


# ======================================================================
# MODEL CONFIGURATION
# ======================================================================

MODEL_VERSION = os.getenv(
    "MODEL_VERSION",
    "HGB-v1",
).strip()

if not MODEL_VERSION:
    MODEL_VERSION = "HGB-v1"


# ======================================================================
# API CONFIGURATION
# ======================================================================

API_TITLE = os.getenv(
    "API_TITLE",
    "Zepto Smart Commerce AI API",
).strip()

API_DESCRIPTION = os.getenv(
    "API_DESCRIPTION",
    "ML-powered delivery intelligence API for delivery charge, ETA, and rider acceptance prediction.",
).strip()

API_VERSION = os.getenv(
    "API_VERSION",
    "1.0.0",
).strip()

API_HOST = os.getenv(
    "API_HOST",
    "127.0.0.1",
).strip()

API_PORT = int(
    os.getenv(
        "API_PORT",
        "8000",
    )
)


# ======================================================================
# EXTERNAL SERVICES
# ======================================================================

# --- OpenWeather LIVE ---

OPENWEATHER_API_KEY = os.getenv(
    "OPENWEATHER_API_KEY",
    "",
).strip()

OPEN_METEO_TIMEOUT_SECONDS = 5

# --- TomTom ---

TOMTOM_API_KEY = os.getenv(
    "TOMTOM_API_KEY",
    "",
).strip()

TOMTOM_TIMEOUT_SECONDS = int(
    os.getenv(
        "TOMTOM_TIMEOUT_SECONDS",
        "5",
    )
)


# ======================================================================
# VALIDATION
# ======================================================================

if API_PORT < 1 or API_PORT > 65535:
    raise ValueError(
        "API_PORT must be between 1 and 65535."
    )