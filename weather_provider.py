"""
Live weather provider.

Only OpenWeather live data is accepted.
No historical/default fallback is used.
"""

from weather_service import get_live_weather
from weather_mapping import map_openweather_to_ml


def get_weather(latitude: float, longitude: float):
    """
    Get current live weather.

    If OpenWeather fails, the prediction fails.
    No historical fallback is used.
    """

    raw_weather = get_live_weather(
        latitude=latitude,
        longitude=longitude,
    )

    return map_openweather_to_ml(
        raw_weather
    )