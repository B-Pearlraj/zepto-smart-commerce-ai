import os
from dotenv import load_dotenv

# Load .env from the FastAPI application directory
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "").strip()

TOMTOM_TRAFFIC_URL = (
    "https://api.tomtom.com/traffic/services/4/"
    "flowSegmentData/absolute/10/json"
)

TOMTOM_TIMEOUT_SECONDS = 5


def validate_tomtom_config():
    if not TOMTOM_API_KEY:
        raise RuntimeError(
            "TOMTOM_API_KEY is not configured in the FastAPI .env file."
        )

    return True