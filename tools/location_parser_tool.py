"""Location parsing tool for extracting destinations from free-form text."""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def _fallback_extract_locations(text: str) -> Dict:
    """
    Heuristic fallback when LLM is unavailable.
    """
    normalized = re.sub(r"[;|]+", ",", text.strip())
    split_pattern = r"\b(?:vs|or|and|between|compare|with)\b|/|,"
    parts = [part.strip(" .!?") for part in re.split(split_pattern, normalized, flags=re.IGNORECASE)]
    destinations = [part for part in parts if len(part) > 1]
    unique_destinations: List[str] = []
    for destination in destinations:
        if destination.lower() not in {item.lower() for item in unique_destinations}:
            unique_destinations.append(destination)

    if not unique_destinations and text.strip():
        unique_destinations = [text.strip()]

    intent = "compare_destinations" if len(unique_destinations) > 1 else "single_destination"
    return {"destinations": unique_destinations[:3], "intent": intent, "source": "fallback"}


def parse_destinations_from_text(text: str, max_locations: int = 3) -> Dict:
    """
    Tool: Extract destination names and travel intent from user text.
    """
    if not text or not text.strip():
        raise ValueError("Location text cannot be empty.")

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return _fallback_extract_locations(text)

    client = Groq(api_key=api_key)
    prompt = f"""
Extract travel destinations from this user text:
"{text}"

Return STRICT JSON only with keys:
- destinations: array of city/place names only (max {max_locations})
- intent: one of single_destination or compare_destinations

Rules:
- Keep only location names, remove filler words.
- If sentence implies comparison between places, set compare_destinations.
- If unsure, return best possible one location.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(response.choices[0].message.content)

    raw_destinations = parsed.get("destinations", [])
    cleaned = []
    for destination in raw_destinations:
        if not isinstance(destination, str):
            continue
        value = destination.strip(" .!?")
        if value and value.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(value)

    if not cleaned:
        return _fallback_extract_locations(text)

    intent = parsed.get("intent", "single_destination")
    if intent not in {"single_destination", "compare_destinations"}:
        intent = "compare_destinations" if len(cleaned) > 1 else "single_destination"

    if len(cleaned) > 1:
        intent = "compare_destinations"

    return {"destinations": cleaned[:max_locations], "intent": intent, "source": "llm"}
