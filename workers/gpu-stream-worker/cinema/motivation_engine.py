"""Motivational monologues — traders, founders, late-night grind."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MotivationalSegment:
    audience: str  # trader | founder | late_night
    at_sec: float
    script: str
    persona_id: str


_TRADER_SCRIPTS = [
    "Every dip is a test. Every green candle is proof. Hold your conviction — the chart rewards patience.",
    "Degens who survive the chop are the ones who print. Read the volume, trust your thesis, manage your risk.",
    "The market doesn't care about your feelings — but it respects discipline. Stack, hold, repeat.",
]

_FOUNDER_SCRIPTS = [
    "To every builder launching on Pump.fun: you're not just minting a token — you're creating a movement.",
    "Founders who show up live, answer chat, and ship updates — that's how market caps compound.",
    "Building in public is the ultimate alpha. Your community sees everything. Make it count.",
]

_LATE_NIGHT_SCRIPTS = [
    "3 AM UTC and you're still here? That's not addiction — that's dedication. The night shift builds empires.",
    "Tokyo waking up, London winding down, New York still grinding — this global market never sleeps. Neither do we.",
    "Late night on the chart is when legends are made. One whale, one candle, one moment.",
]


def build_motivation_segments(
    duration_sec: float,
    symbol: str,
    market_cap_usd: float,
    is_late_night: bool = False,
    seed: str = "",
) -> list[MotivationalSegment]:
    rng = random.Random(hash(seed or symbol) % 2**32)
    segments: list[MotivationalSegment] = []

    # Trader motivation at ~25% and ~75%
    for frac, audience, pool, persona in [
        (0.25, "trader", _TRADER_SCRIPTS, "hype_anchor"),
        (0.50, "founder", _FOUNDER_SCRIPTS, "smooth_narrator"),
        (0.75, "trader", _TRADER_SCRIPTS, "celebration_host"),
    ]:
        at = duration_sec * frac
        if at >= duration_sec - 10:
            continue
        script = rng.choice(pool).replace("token", symbol)
        script = f"${symbol} at ${market_cap_usd:,.0f} MCAP — {script}"
        segments.append(MotivationalSegment(audience, at, script, persona))

    if is_late_night:
        segments.append(MotivationalSegment(
            "late_night", duration_sec * 0.15,
            rng.choice(_LATE_NIGHT_SCRIPTS),
            "outro_warm",
        ))

    return segments
