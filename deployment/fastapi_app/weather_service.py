"""
Live OpenWeather service.

This service retrieves current weather conditions using:
    OPENWEATHER_API_KEY

The API uses the customer's latitude and longitude.
No historical/default fallback is used.
"""

import os
import requests
from dotenv import load_dotenv


load_dotenv()


OPENWEATHER_API_KEY = os.getenv(
    "OPENWEATHER_API_KEY",
    ""
).strip()

OPENWEATHER_URL = (
    "https://api.openweathermap.org/data/2.5/weather"
)

OPENWEATHER_TIMEOUT_SECONDS = 5


def validate_openweather_config():
    """
    Validate OpenWeather configuration.
    """

    if not OPENWEATHER_API_KEY:
        raise RuntimeError(
            "OPENWEATHER_API_KEY environment variable "
            "is not configured."
        )

    return True


def get_live_weather(latitude: float, longitude: float):
    """
    Retrieve current weather from OpenWeather.

    Parameters
    ----------
    latitude : float
        Customer latitude.

    longitude : float
        Customer longitude.

    Returns
    -------
    dict
        Raw OpenWeather response.

    Raises
    ------
    RuntimeError
        If configuration, network request, API response,
        or response structure is invalid.
    """

    validate_openweather_config()

    params = {
        "lat": latitude,
        "lon": longitude,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(
            OPENWEATHER_URL,
            params=params,
            timeout=OPENWEATHER_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"OpenWeather live request failed: {exc}"
        ) from exc

    except ValueError as exc:
        raise RuntimeError(
            "OpenWeather returned invalid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "OpenWeather response is not a JSON object."
        )

    if "weather" not in data or not data["weather"]:
        raise RuntimeError(
            "OpenWeather response does not contain weather data."
        )

    if "main" not in data:
        raise RuntimeError(
            "OpenWeather response does not contain main weather data."
        )

    return data