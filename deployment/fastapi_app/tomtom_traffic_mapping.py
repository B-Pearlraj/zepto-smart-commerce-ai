"""
Convert TomTom live traffic into ML-ready traffic features.
"""


def map_tomtom_traffic(traffic_data: dict) -> dict:
    """
    Convert live TomTom traffic response into:

        traffic_index
        traffic_level

    The ML pipeline expects traffic_index in the range 0-100.
    """

    flow = traffic_data.get("flowSegmentData")

    if not isinstance(flow, dict):
        raise RuntimeError(
            "TomTom response does not contain flowSegmentData."
        )

    current_speed = flow.get("currentSpeed")
    free_flow_speed = flow.get("freeFlowSpeed")

    if current_speed is None:
        raise RuntimeError(
            "TomTom response does not contain currentSpeed."
        )

    if free_flow_speed is None:
        raise RuntimeError(
            "TomTom response does not contain freeFlowSpeed."
        )

    current_speed = float(current_speed)
    free_flow_speed = float(free_flow_speed)

    if free_flow_speed <= 0:
        raise RuntimeError(
            "TomTom freeFlowSpeed must be greater than zero."
        )

    if current_speed < 0:
        raise RuntimeError(
            "TomTom currentSpeed cannot be negative."
        )

    # --------------------------------------------------------------
    # Traffic congestion index
    # --------------------------------------------------------------

    traffic_index = (
        1.0 - (current_speed / free_flow_speed)
    ) * 100.0

    traffic_index = max(
        0.0,
        min(100.0, traffic_index)
    )

    traffic_index = round(
        traffic_index,
        2
    )

    # --------------------------------------------------------------
    # Traffic level
    # --------------------------------------------------------------

    if traffic_index < 40:
        traffic_level = "low"

    elif traffic_index < 70:
        traffic_level = "medium"

    else:
        traffic_level = "high"

    return {
        # ML fields
        "traffic_index": traffic_index,
        "traffic_level": traffic_level,

        # Live UI fields
        "current_speed_kmh": current_speed,
        "free_flow_speed_kmh": free_flow_speed,

        "source": "tomtom-live",
    }