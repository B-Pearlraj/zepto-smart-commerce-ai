"""
TomTom Traffic enrichment.

Module:
    ML Delivery Intelligence Engine
"""

import logging

from tomtom_traffic_service import get_live_traffic
from tomtom_traffic_mapping import parse_tomtom_traffic


logger = logging.getLogger(__name__)


def enrich_with_tomtom_traffic(latitude, longitude):
    """
    Fetch and transform live TomTom traffic data.

    Returns:
        dict | None
        ML-ready traffic information when successful.
    """

    traffic_data = get_live_traffic(
        latitude=latitude,
        longitude=longitude,
    )

    if traffic_data is None:
        logger.warning(
            "TomTom traffic enrichment unavailable | "
            "lat=%s | lon=%s",
            latitude,
            longitude,
        )
        return None

    parsed_traffic = parse_tomtom_traffic(traffic_data)

    if parsed_traffic is None:
        logger.warning(
            "TomTom traffic parsing failed | "
            "lat=%s | lon=%s",
            latitude,
            longitude,
        )
        return None

    logger.info(
        "TomTom traffic enrichment completed | "
        "level=%s | index=%s",
        parsed_traffic.get("traffic_level"),
        parsed_traffic.get("traffic_index"),
    )

    return parsed_traffic