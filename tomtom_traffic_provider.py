"""
Live TomTom traffic provider.

Only live TomTom Traffic Flow data is accepted.
No historical/default fallback is used.
"""

from tomtom_traffic_service import get_live_traffic
from tomtom_traffic_mapping import map_tomtom_traffic


def get_traffic(latitude: float, longitude: float):
    """
    Get current live traffic.

    If TomTom fails, the prediction fails.
    No historical fallback is used.
    """

    raw_traffic = get_live_traffic(
        latitude=latitude,
        longitude=longitude,
    )

    return map_tomtom_traffic(
        raw_traffic
    )