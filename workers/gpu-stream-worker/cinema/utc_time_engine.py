"""UTC time awareness — new day segments, time announcements, late-night grind."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class UTCSegment:
    segment_type: str  # new_day | time_check | late_night | market_open
    at_sec: float
    script: str
    persona_id: str = "smooth_narrator"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc_time(dt: datetime | None = None) -> str:
    dt = dt or utc_now()
    return dt.strftime("%H:%M UTC")


def is_new_day_window(dt: datetime | None = None, window_minutes: int = 15) -> bool:
    """True if within first N minutes after midnight UTC."""
    dt = dt or utc_now()
    return dt.hour == 0 and dt.minute < window_minutes


def is_late_night_grind(dt: datetime | None = None) -> bool:
    dt = dt or utc_now()
    return dt.hour >= 2 and dt.hour < 6


def build_utc_segments(duration_sec: float, symbol: str, start_offset_sec: float = 0.0) -> list[UTCSegment]:
    """Generate UTC-aware voiceover segments for a stream window."""
    now = utc_now()
    segments: list[UTCSegment] = []

    if is_new_day_window(now):
        segments.append(UTCSegment(
            segment_type="new_day",
            at_sec=2.0 + start_offset_sec,
            script=(
                f"Good morning world, it is {format_utc_time(now)}. "
                f"A brand new trading day begins on Pump.fun — ${symbol} is live and ready. "
                f"Fresh charts, fresh energy, let's build."
            ),
            persona_id="smooth_narrator",
        ))

    if is_late_night_grind(now):
        segments.append(UTCSegment(
            segment_type="late_night",
            at_sec=min(30.0, duration_sec * 0.1) + start_offset_sec,
            script=(
                f"It's {format_utc_time(now)} — the late-night grind crew is still here. "
                f"To every degen awake across the globe watching ${symbol}: "
                f"your dedication is what makes this market move. Stay sharp."
            ),
            persona_id="outro_warm",
        ))

    # Periodic UTC time check (~every 3 min in a long stream)
    check_interval = 180.0
    t = check_interval
    while t < duration_sec - 30:
        projected = now.timestamp() + t
        proj_dt = datetime.fromtimestamp(projected, tz=timezone.utc)
        segments.append(UTCSegment(
            segment_type="time_check",
            at_sec=t + start_offset_sec,
            script=f"Quick time check — it is {proj_dt.strftime('%H:%M UTC')}. ${symbol} stream rolling.",
            persona_id="smooth_narrator",
        ))
        t += check_interval

    return segments
