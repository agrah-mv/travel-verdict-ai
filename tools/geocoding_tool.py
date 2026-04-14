"""Geocoding tool powered by Open-Meteo geocoding API."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
NON_CITY_TOKENS = {"airport", "station", "junction", "terminal"}


def _normalize_text(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace()).strip()


def _build_query_variants(city: str) -> list[str]:
    """
    Generate safe search variants without hardcoded city aliases.
    """
    normalized = " ".join(city.strip().split())
    variants = [normalized]
    if "," in normalized:
        variants.append(normalized.split(",")[0].strip())
    if len(normalized.split()) == 1:
        variants.append(f"{normalized} city")
    unique: list[str] = []
    for variant in variants:
        if variant and variant.lower() not in {item.lower() for item in unique}:
            unique.append(variant)
    return unique


def _fetch_candidates(query: str, count: int = 20) -> list[Dict[str, Any]]:
    response = requests.get(
        GEOCODING_URL,
        params={"name": query, "count": count, "language": "en", "format": "json"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("results", [])


def _score_candidate(user_city: str, candidate: Dict[str, Any]) -> int:
    """
    Score geocoding candidates so exact textual matches win over fuzzy ones.
    """
    query = _normalize_text(user_city)
    name = _normalize_text(candidate.get("name", ""))
    admin1 = _normalize_text(candidate.get("admin1", ""))
    country = _normalize_text(candidate.get("country", ""))
    population = candidate.get("population") or 0

    score = 0
    if name == query:
        score += 120
    if query in name.split():
        score += 80
    if query and query in name:
        score += 30
    if query == admin1:
        score += 55
    if query and query in admin1:
        score += 18
    if query == country:
        score += 45
    if query and query in country:
        score += 12
    if name.startswith(query):
        score += 12
    score += int(SequenceMatcher(None, query, name).ratio() * 20)
    if any(word in name for word in NON_CITY_TOKENS):
        score -= 80

    # Prefer populated places when semantic score is similar.
    score += min(int(population / 100000), 10)
    return score


def geocode_city(city: str) -> Dict[str, Any]:
    """
    Tool: Convert a city name into latitude and longitude coordinates.
    """
    if not city or not city.strip():
        raise ValueError("City cannot be empty.")

    original_query = city.strip()
    query_variants = _build_query_variants(original_query)
    results: list[Dict[str, Any]] = []
    seen_keys = set()
    for variant in query_variants:
        for candidate in _fetch_candidates(variant, count=20):
            key = (
                _normalize_text(candidate.get("name", "")),
                _normalize_text(candidate.get("country", "")),
                round(candidate.get("latitude", 0), 4),
                round(candidate.get("longitude", 0), 4),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            results.append(candidate)

    if not results:
        raise ValueError(f"No geocoding results found for '{original_query}'.")

    ranked = sorted(
        results,
        key=lambda candidate: _score_candidate(original_query, candidate),
        reverse=True,
    )
    top = ranked[0]
    top_score = _score_candidate(original_query, top)
    if any(word in _normalize_text(top.get("name", "")) for word in NON_CITY_TOKENS):
        clean_candidates = [
            candidate
            for candidate in ranked
            if not any(word in _normalize_text(candidate.get("name", "")) for word in NON_CITY_TOKENS)
        ]
        if clean_candidates:
            clean_top = clean_candidates[0]
            clean_score = _score_candidate(original_query, clean_top)
            if clean_score >= top_score - 60:
                top = clean_top

    # If two countries have nearly identical confidence, ask user to disambiguate.
    if len(ranked) > 1:
        top_score = _score_candidate(original_query, ranked[0])
        second_score = _score_candidate(original_query, ranked[1])
        top_country = _normalize_text(ranked[0].get("country", ""))
        second_country = _normalize_text(ranked[1].get("country", ""))
        if top_country != second_country and abs(top_score - second_score) <= 5:
            options = ", ".join(
                f"{item.get('name', original_query)}, {item.get('country', 'Unknown')}"
                for item in ranked[:3]
            )
            raise ValueError(
                f"Ambiguous location '{original_query}'. Try adding country/state. "
                f"Closest matches: {options}."
            )

    return {
        "name": top.get("name", original_query),
        "country": top.get("country", ""),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
        "query_used": query_variants[0],
    }
