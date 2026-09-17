"""Google Trends integration — real API with structured fallback."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class TrendTopic:
    title: str
    region: str
    rank: int
    joke_setup: str = ""


def _fallback_trends(symbol: str, seed: int) -> list[TrendTopic]:
    """Structured fallback when no trends API key — still varied via seed."""
    pools = [
        ("AI agents", "US", "Everyone's searching AI agents — ${sym} agents are buying the dip."),
        ("Bitcoin ETF", "global", "ETF flows trending — alt season energy hits ${sym}."),
        ("Solana memecoins", "US", "Solana memes trending — ${sym} is the headline act tonight."),
        ("Pump.fun launches", "global", "Pump.fun is trending — you're watching the right stream."),
        ("Crypto regulation", "UK", "Regulation headlines everywhere — degens stay building on ${sym}."),
        ("Elon tweet", "US", "Elon trending again — one post away from a green candle on ${sym}."),
        ("Fed rate decision", "US", "Macro trending — traders watching charts, we're watching ${sym}."),
        ("NFT comeback", "JP", "NFTs trending in Japan — meme coins never left, ${sym} proves it."),
    ]
    rng = random.Random(seed)
    picks = rng.sample(pools, min(3, len(pools)))
    return [
        TrendTopic(
            title=t[0], region=t[1], rank=i + 1,
            joke_setup=t[2].replace("${sym}", symbol),
        )
        for i, t in enumerate(picks)
    ]


async def fetch_trending_topics(symbol: str = "KWIF", region: str = "US") -> list[TrendTopic]:
    """
    Pull top 3 trending topics. Uses SerpApi/Glimpse when configured;
    otherwise returns seed-varied fallback topics.
    """
    api_key = os.environ.get("SERPAPI_KEY") or os.environ.get("GLIMPSE_API_KEY")
    if api_key:
        try:
            import httpx
            # SerpApi Google Trends
            url = "https://serpapi.com/search"
            params = {"engine": "google_trends_trending_now", "geo": region, "api_key": api_key}
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
            topics: list[TrendTopic] = []
            for i, item in enumerate((data.get("trending_searches") or [])[:3]):
                title = str(item.get("title") or item.get("query") or "trending")
                topics.append(TrendTopic(
                    title=title, region=region, rank=i + 1,
                    joke_setup=f"'{title}' is trending — same energy as ${symbol} right now.",
                ))
            if topics:
                return topics
        except Exception as exc:
            print(f"  trends API fallback: {exc}")

    seed = int(datetime.now(timezone.utc).strftime("%Y%m%d%H")) + hash(symbol) % 1000
    return _fallback_trends(symbol, seed)


def trend_commentary(topics: list[TrendTopic], symbol: str) -> str:
    if not topics:
        return f"Global search trends are buzzing — ${symbol} holders know where the action is."
    lines = [f"Trending now: {t.title} ({t.region})" for t in topics[:3]]
    jokes = [t.joke_setup for t in topics[:2] if t.joke_setup]
    return (
        f"Google Trends check — {'; '.join(lines)}. "
        + (jokes[0] if jokes else f"All eyes on ${symbol} tonight.")
    )
