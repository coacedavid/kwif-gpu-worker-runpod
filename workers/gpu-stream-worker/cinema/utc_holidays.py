"""UTC holiday & observance calendar — triggers themed stream segments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class HolidayEvent:
    name: str
    category: str  # religious | cultural | international | national
    theme: str
    song_genre_boost: str
    visual_overlay: str


# Fixed-date observances (month, day)
_FIXED_HOLIDAYS: list[tuple[tuple[int, int], HolidayEvent]] = [
    ((1, 1), HolidayEvent("New Year's Day", "international", "new_year", "stadium_anthem", "fireworks_crown")),
    ((2, 14), HolidayEvent("Valentine's Day", "international", "love_hype", "violet_groove", "pink_chat")),
    ((3, 14), HolidayEvent("Pi Day", "international", "science_meme", "science_chill", "bonding_science")),
    ((3, 8), HolidayEvent("International Women's Day", "international", "empowerment", "cinematic_orchestral", "celebration_dance")),
    ((4, 22), HolidayEvent("Earth Day", "international", "green_future", "ambient_chill", "lake_intro")),
    ((7, 4), HolidayEvent("USA Independence Day", "national", "patriotic_hype", "stadium_anthem", "fireworks_crown")),
    ((10, 31), HolidayEvent("Halloween", "international", "spooky_hype", "trap_finale", "purple_chart")),
    ((11, 29), HolidayEvent("Black Friday", "international", "shopping_surge", "edm_drop", "money_cash")),
    ((12, 25), HolidayEvent("Christmas", "religious", "christmas_celebration", "cinematic_orchestral", "celebration_dance")),
    ((12, 31), HolidayEvent("New Year's Eve", "international", "countdown", "stadium_anthem", "fireworks_crown")),
]

# Approximate lunar/cultural dates (checked by month-day ranges for demo; production uses proper calendar lib)
_APPROXIMATE_HOLIDAYS: list[tuple[tuple[int, int, int, int], HolidayEvent]] = [
    # Diwali typically Oct-Nov
    ((10, 20, 11, 15), HolidayEvent("Diwali", "religious", "festival_of_lights", "afrobeat_groove", "fireworks_crown")),
    # Lunar New Year typically Jan-Feb
    ((1, 20, 2, 20), HolidayEvent("Lunar New Year", "cultural", "lunar_celebration", "afrobeat_groove", "celebration_dance")),
    # Hanukkah typically Dec
    ((12, 1, 12, 31), HolidayEvent("Hanukkah", "religious", "festival_lights", "cinematic_orchestral", "purple_chart")),
]


def get_holidays_for_date(d: date | None = None) -> list[HolidayEvent]:
    """Return all holidays matching the given UTC date."""
    d = d or datetime.now(timezone.utc).date()
    found: list[HolidayEvent] = []
    for (m, day), event in _FIXED_HOLIDAYS:
        if d.month == m and d.day == day:
            found.append(event)
    for (m1, d1, m2, d2), event in _APPROXIMATE_HOLIDAYS:
        start = date(d.year, m1, d1)
        end = date(d.year, m2, d2)
        if start <= d <= end:
            found.append(event)
    return found


def active_holiday_theme(d: date | None = None) -> HolidayEvent | None:
    holidays = get_holidays_for_date(d)
    return holidays[0] if holidays else None


def holiday_voiceover(holiday: HolidayEvent, symbol: str, utc_hour: int) -> str:
    time_greet = "morning" if utc_hour < 12 else ("afternoon" if utc_hour < 18 else "evening")
    return (
        f"Good {time_greet} world — today we celebrate {holiday.name}! "
        f"${symbol} is riding the {holiday.theme.replace('_', ' ')} wave on Pump.fun. "
        f"Let's make this milestone unforgettable."
    )
