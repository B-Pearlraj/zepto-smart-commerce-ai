import requests

from tomtom_config import (
    TOMTOM_API_KEY,
    TOMTOM_TRAFFIC_URL,
    TOMTOM_TIMEOUT_SECONDS,
    validate_tomtom_config,
)


def get_live_traffic(latitude: float, longitude: float) -> dict:
    """
    Fetch live traffic information from TomTom Traffic Flow API.
    No historical fallback is used.
    """

    validate_tomtom_config()

    params = {
        "key": TOMTOM_API_KEY,
        "point": f"{latitude},{longitude}",
    }

    try:
        response = requests.get(
            TOMTOM_TRAFFIC_URL,
            params=params,
            timeout=TOMTOM_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"TomTom live traffic request failed: {exc}"
        ) from exc

    try:
        traffic_data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "TomTom returned an invalid JSON response."
        ) from exc

    if not isinstance(traffic_data, dict):
        raise RuntimeError(
            "TomTom returned an unexpected response format."
        )

    if "flowSegmentData" not in traffic_data:
        raise RuntimeError(
            "TomTom response does not contain flowSegmentData."
        )

    return traffic_data