"""News, influencer mentions, and satirical commentary engine."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class NewsSegment:
    category: str  # macro | crypto | influencer | satire
    headline: str
    commentary: str
    persona_id: str
    at_sec: float = 0.0


SATIRE_PERSONAS = [
    {"id": "wall_street_anchor", "voice": "en-US-GuyNeural", "rate": "-2%", "pitch": "+1Hz", "style": "professional anchor"},
    {"id": "hype_broadcaster", "voice": "en-US-JennyNeural", "rate": "+8%", "pitch": "+4Hz", "style": "high-energy crypto broadcaster"},
    {"id": "philosophical_degen", "voice": "en-US-AriaNeural", "rate": "-5%", "pitch": "+0Hz", "style": "thoughtful degen philosopher"},
    {"id": "witty_satirist", "voice": "en-US-GuyNeural", "rate": "+4%", "pitch": "+2Hz", "style": "dry witty satirist"},
]

_FALLBACK_HEADLINES = [
    ("crypto", "Bitcoin holds key support as altcoins rotate", "Rotation season — alts like {sym} get the spotlight when BTC rests."),
    ("macro", "Fed speakers signal data-dependent path", "Macro traders hedging — memecoin degens? Full send on {sym}."),
    ("tech", "AI infrastructure spending hits new highs", "AI money flowing — meme coins are the retail AI play. {sym} knows."),
    ("influencer", "Major crypto figure posts about memecoin season", "When influencers tweet, charts move. Watch {sym} volume."),
]


async def fetch_news_headlines(limit: int = 3) -> list[dict[str, str]]:
    """Fetch crypto/macro headlines. Uses NewsAPI when key set, else fallback."""
    api_key = os.environ.get("NEWSAPI_KEY")
    if api_key:
        try:
            import httpx
            url = "https://newsapi.org/v2/top-headlines"
            params = {"category": "business", "language": "en", "pageSize": limit, "apiKey": api_key}
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                articles = r.json().get("articles") or []
            return [
                {"category": "macro", "headline": a.get("title", ""), "source": a.get("source", {}).get("name", "")}
                for a in articles[:limit]
            ]
        except Exception as exc:
            print(f"  news API fallback: {exc}")

    rng = random.Random(int(datetime.now(timezone.utc).strftime("%Y%m%d%H")))
    return [
        {"category": cat, "headline": hl, "source": "stream_feed"}
        for cat, hl, _ in rng.sample(_FALLBACK_HEADLINES, min(limit, len(_FALLBACK_HEADLINES)))
    ]


def build_satire_segments(
    headlines: list[dict[str, str]],
    symbol: str,
    duration_sec: float,
    seed: str = "",
) -> list[NewsSegment]:
    rng = random.Random(hash(seed) % 2**32)
    segments: list[NewsSegment] = []
    interval = max(90.0, duration_sec / 4)
    t = interval

    for i, item in enumerate(headlines):
        persona = rng.choice(SATIRE_PERSONAS)
        hl = item.get("headline", "Markets in focus")
        cat = item.get("category", "crypto")
        template = next((c for _, h, c in _FALLBACK_HEADLINES if cat in h.lower()), "Markets moving — {sym} holders watching closely.")
        commentary = template.format(sym=symbol)
        if cat == "influencer":
            commentary = (
                f"Breaking: influential figure mentions the space. "
                f"Whenever that happens, volume spikes — {symbol} chart loading."
            )
        segments.append(NewsSegment(
            category=cat, headline=hl, commentary=commentary,
            persona_id=persona["id"], at_sec=t,
        ))
        t += interval

    return segments


def trading_joke(symbol: str, mcap: float, trend: str = "") -> str:
    jokes = [
        f"Why did {symbol} cross the bonding curve? To get to the other side — of six figures.",
        f"{symbol} MCAP at ${mcap:,.0f}? That's not a chart, that's a staircase to Valhalla.",
        f"They said memecoins were dead. {symbol} said 'hold my cat.'",
    ]
    if trend:
        jokes.append(f"'{trend}' is trending and so is {symbol}. Coincidence? The chart says no.")
    return random.choice(jokes)
