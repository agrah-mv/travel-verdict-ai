"""Distance tool for estimating trip distance between two cities."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Dict

from .geocoding_tool import geocode_city


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_km * c


def calculate_distance_km(origin_city: str, destination_city: str) -> Dict:
    """
    Tool: Estimate straight-line distance in km between origin and destination.
    """
    origin = geocode_city(origin_city)
    destination = geocode_city(destination_city)
    distance_km = _haversine_distance_km(
        origin["latitude"],
        origin["longitude"],
        destination["latitude"],
        destination["longitude"],
    )
    return {
        "origin_resolved": f"{origin['name']}, {origin.get('country', '')}".strip(", "),
        "destination_resolved": f"{destination['name']}, {destination.get('country', '')}".strip(", "),
        "distance_km": round(distance_km, 1),
    }
