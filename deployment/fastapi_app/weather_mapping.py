"""
Convert OpenWeather current conditions into
the exact weather categories used by the ML models.
"""


def map_openweather_to_ml(weather_data: dict) -> dict:
    """
    Convert OpenWeather response into ML-ready weather features.
    """

    weather_items = weather_data.get("weather", [])

    if not weather_items:
        raise RuntimeError(
            "OpenWeather response contains no weather condition."
        )

    weather_main = str(
        weather_items[0].get("main", "")
    ).strip().lower()

    weather_description = str(
        weather_items[0].get("description", "")
    ).strip().lower()

    weather_id = weather_items[0].get("id")

    # --------------------------------------------------------------
    # Rainfall
    # --------------------------------------------------------------

    rain_data = weather_data.get("rain", {})

    rainfall_mm = float(
        rain_data.get("1h", 0.0) or 0.0
    )

    if rainfall_mm < 0:
        rainfall_mm = 0.0

    # --------------------------------------------------------------
    # Weather classification
    # --------------------------------------------------------------

    if weather_main == "thunderstorm":
        weather_condition = "heavy_rain"

    elif weather_main == "drizzle":
        weather_condition = "light_rain"

    elif weather_main == "rain":

        if rainfall_mm >= 7.5:
            weather_condition = "heavy_rain"

        elif rainfall_mm >= 2.5:
            weather_condition = "moderate_rain"

        else:
            weather_condition = "light_rain"

    elif weather_main == "snow":
        # The training data does not contain snow as a category.
        # Treat it conservatively as heavy weather.
        weather_condition = "heavy_rain"

    elif weather_main == "clear":
        weather_condition = "clear"

    elif weather_main in (
        "clouds",
        "mist",
        "smoke",
        "haze",
        "dust",
        "fog",
        "sand",
        "ash",
        "squall",
        "tornado",
    ):
        weather_condition = "clear"

    else:
        # Unknown OpenWeather condition.
        # Use rainfall to determine the closest ML category.
        if rainfall_mm >= 7.5:
            weather_condition = "heavy_rain"
        elif rainfall_mm >= 2.5:
            weather_condition = "moderate_rain"
        elif rainfall_mm > 0:
            weather_condition = "light_rain"
        else:
            weather_condition = "clear"

    # --------------------------------------------------------------
    # Exact ML severity
    # --------------------------------------------------------------

    weather_severity_map = {
        "clear": 0,
        "light_rain": 1,
        "moderate_rain": 2,
        "heavy_rain": 3,
    }

    weather_severity = weather_severity_map[
        weather_condition
    ]

    has_rain = int(
        weather_condition in (
            "light_rain",
            "moderate_rain",
            "heavy_rain",
        )
        or rainfall_mm > 0
    )

    # --------------------------------------------------------------
    # Additional live values for UI
    # --------------------------------------------------------------

    main_data = weather_data.get("main", {})
    wind_data = weather_data.get("wind", {})
    clouds_data = weather_data.get("clouds", {})

    temperature_c = main_data.get("temp")
    feels_like_c = main_data.get("feels_like")
    humidity_percent = main_data.get("humidity")
    pressure_hpa = main_data.get("pressure")

    wind_speed_mps = wind_data.get("speed")
    wind_direction_deg = wind_data.get("deg")

    cloudiness_percent = clouds_data.get("all")

    city_name = weather_data.get("name")

    return {
        # ML fields
        "weather_condition": weather_condition,
        "weather_severity": weather_severity,
        "rainfall_mm": rainfall_mm,
        "has_rain": has_rain,

        # Live UI information
        "temperature_c": temperature_c,
        "feels_like_c": feels_like_c,
        "humidity_percent": humidity_percent,
        "pressure_hpa": pressure_hpa,
        "wind_speed_mps": wind_speed_mps,
        "wind_direction_deg": wind_direction_deg,
        "cloudiness_percent": cloudiness_percent,
        "description": weather_description,
        "openweather_condition": weather_main,
        "openweather_id": weather_id,
        "location_name": city_name,

        "source": "openweather-live",
    }