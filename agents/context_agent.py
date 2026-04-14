"""ContextAgent prepares structured context from user input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from tools import geocode_city, parse_destinations_from_text, parse_travel_dates


@dataclass
class ContextResult:
    destinations: List[str]
    date_context: Dict
    intent: str
    user_query: str
    react_steps: List[str]


class ContextAgent:
    """Parses natural language date and intent from the user's request."""

    def prepare_context(self, location_input: str, date_input: str, user_query: str) -> ContextResult:
        react_steps: List[str] = []

        react_steps.append("Thought: Extract destination names from user text robustly.")
        react_steps.append("Action: Call Location Parsing Tool")
        parsed_locations = parse_destinations_from_text(location_input, max_locations=3)
        destinations = parsed_locations["destinations"]
        intent = parsed_locations["intent"]
        react_steps.append(
            f"Observation: Parsed destinations {destinations} with intent {intent} ({parsed_locations['source']})."
        )

        react_steps.append("Thought: Validate extracted destinations through geocoding.")
        validated_destinations: List[str] = []
        geocoding_errors: List[str] = []
        for destination in destinations:
            try:
                geocoded = geocode_city(destination)
                validated_destinations.append(geocoded.get("name", destination))
            except ValueError as error:
                geocoding_errors.append(f"{destination}: {error}")
                if "Ambiguous location" in str(error):
                    raise ValueError(f"Please clarify destination '{destination}'. {error}") from error
            except Exception:
                continue

        if not validated_destinations:
            if geocoding_errors:
                raise ValueError(geocoding_errors[0])
            raise ValueError(
                "Could not identify a valid destination from your input. "
                "Try entering place names like 'Chennai and Munnar' or 'Goa vs Idukki'."
            )

        validated_unique: List[str] = []
        for destination in validated_destinations:
            if destination.lower() not in {item.lower() for item in validated_unique}:
                validated_unique.append(destination)

        if intent == "compare_destinations" and len(validated_unique) < 2:
            raise ValueError(
                "I could identify only one destination. Please provide two places to compare, "
                "for example: 'Chennai and Munnar'."
            )
        if len(validated_unique) > 1:
            intent = "compare_destinations"
        else:
            intent = "single_destination"
        react_steps.append(f"Observation: Valid destinations after geocoding: {validated_unique}.")

        react_steps.append("Thought: Convert natural language date into an actual date range.")
        react_steps.append("Action: Call Date Parsing Tool")
        parsed_range = parse_travel_dates(date_input)
        react_steps.append(
            "Observation: Parsed date range "
            f"{parsed_range.start_date.isoformat()} to {parsed_range.end_date.isoformat()}."
        )

        return ContextResult(
            destinations=validated_unique,
            date_context=parsed_range.as_dict(),
            intent=intent,
            user_query=user_query,
            react_steps=react_steps,
        )
