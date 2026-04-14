"""WeatherAgent obtains weather data through explicit tool calls."""

from __future__ import annotations

from datetime import date
from typing import Dict, List

from tools import fetch_weather_forecast, geocode_city


class WeatherAgent:
    """Fetches and structures weather for one destination."""

    def run(self, destination: str, start_date: date, end_date: date) -> Dict:
        react_steps: List[str] = []
        react_steps.append(f"Thought: Need coordinates for {destination}.")
        react_steps.append("Action: Call Geocoding Tool")
        geocode_result = geocode_city(destination)
        react_steps.append(
            "Observation: Received lat/lon "
            f"({geocode_result['latitude']}, {geocode_result['longitude']})."
        )

        react_steps.append("Thought: Fetch weather forecast for travel dates.")
        react_steps.append("Action: Call Weather Tool")
        weather_result = fetch_weather_forecast(
            latitude=geocode_result["latitude"],
            longitude=geocode_result["longitude"],
            start_date=start_date,
            end_date=end_date,
            timezone=geocode_result.get("timezone", "auto"),
        )
        react_steps.append(
            "Observation: Weather fetched with max rain probability "
            f"{weather_result['summary']['max_rain_probability']}%."
        )

        return {
            "destination": geocode_result["name"],
            "country": geocode_result["country"],
            "coordinates": {
                "latitude": geocode_result["latitude"],
                "longitude": geocode_result["longitude"],
            },
            "weather": weather_result,
            "react_steps": react_steps,
        }
