"""Weather tool using Open-Meteo forecast API."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

import requests

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather_forecast(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
    timezone: str = "auto",
) -> Dict[str, Any]:
    """
    Tool: Fetch weather forecast and aggregate key travel metrics.
    """
    response = requests.get(
        WEATHER_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode,windspeed_10m_max",
            "timezone": timezone,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        raise ValueError("No weather data returned for requested date range.")

    precipitation_probs = daily.get("precipitation_probability_max", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    wind_max = daily.get("windspeed_10m_max", [])

    avg_temp = (
        sum((high + low) / 2 for high, low in zip(t_max, t_min)) / len(t_max)
        if t_max and t_min
        else None
    )

    return {
        "dates": dates,
        "temperature_max": t_max,
        "temperature_min": t_min,
        "precipitation_probability_max": precipitation_probs,
        "weather_code": daily.get("weathercode", []),
        "windspeed_max": wind_max,
        "summary": {
            "avg_temp_c": round(avg_temp, 1) if avg_temp is not None else None,
            "max_rain_probability": max(precipitation_probs) if precipitation_probs else None,
            "max_wind_kmh": max(wind_max) if wind_max else None,
        },
    }
