"""Date parsing tool to convert natural language to date ranges."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

import dateparser


@dataclass
class ParsedDateRange:
    start_date: date
    end_date: date
    source_text: str

    def as_dict(self) -> dict:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "source_text": self.source_text,
        }


def _next_weekday(base_date: date, weekday: int) -> date:
    """Return the next weekday where Monday=0 ... Sunday=6."""
    days_ahead = weekday - base_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return base_date + timedelta(days=days_ahead)


def _parse_weekend(text: str, reference_date: date) -> Optional[ParsedDateRange]:
    lowered = text.lower().strip()
    if lowered not in {"this weekend", "weekend"}:
        return None

    saturday = _next_weekday(reference_date, 5)
    sunday = saturday + timedelta(days=1)
    return ParsedDateRange(start_date=saturday, end_date=sunday, source_text=text)


def parse_travel_dates(text: str, reference_date: Optional[date] = None) -> ParsedDateRange:
    """
    Tool: Convert free text date intent into an explicit date range.

    Examples:
    - "this weekend" -> Saturday to Sunday
    - "tomorrow" -> one-day range
    - "2026-04-20 to 2026-04-23" -> parsed by dateparser
    """
    if not text or not text.strip():
        raise ValueError("Date text cannot be empty.")

    today = reference_date or date.today()
    weekend_range = _parse_weekend(text, today)
    if weekend_range:
        return weekend_range

    parsed_dt = dateparser.parse(
        text,
        settings={
            "RELATIVE_BASE": datetime.combine(today, time.min),
            "PREFER_DATES_FROM": "future",
        },
    )
    if parsed_dt is None:
        raise ValueError(
            "Could not parse date text. Try phrases like 'this weekend', "
            "'tomorrow', or a date such as 2026-05-10."
        )

    parsed_date = parsed_dt.date()
    return ParsedDateRange(start_date=parsed_date, end_date=parsed_date, source_text=text)
