"""
Modular runtime variation engine — enforces diversity via pools, weights, and state.

No hardcoded loops. All music sections, voices, genres, and visual scenes are
selected from weighted pools with stateful no-repeat tracking.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cinema.lyrics import TokenLyrics
from cinema.scene_schema import (
    AudioLayerSpec,
    MilestoneSpec,
    StreamPlan,
    VisualSceneSpec,
    VocalSpec,
)
from cinema.state_tracker import StateTracker

# ── Asset pools ──────────────────────────────────────────────────────────────

MUSIC_GENRES: list[dict[str, Any]] = [
    {"id": "synthwave_neon", "bpm": 108.0, "weight": 1.0, "render": "lofi"},
    {"id": "hiphop_hype", "bpm": 112.0, "weight": 1.3, "render": "celebration"},
    {"id": "cinematic_orchestral", "bpm": 90.0, "weight": 0.9, "render": "lofi"},
    {"id": "edm_drop", "bpm": 128.0, "weight": 1.2, "render": "celebration"},
    {"id": "lofi_lake", "bpm": 78.0, "weight": 1.0, "render": "lofi"},
    {"id": "trap_finale", "bpm": 120.0, "weight": 1.4, "render": "celebration"},
    {"id": "violet_groove", "bpm": 100.0, "weight": 1.0, "render": "lofi"},
    {"id": "meme_energy", "bpm": 115.0, "weight": 1.1, "render": "celebration"},
    {"id": "ambient_chill", "bpm": 72.0, "weight": 0.8, "render": "lofi"},
    {"id": "stadium_anthem", "bpm": 122.0, "weight": 1.5, "render": "celebration"},
    {"id": "afrobeat_groove", "bpm": 105.0, "weight": 1.1, "render": "lofi"},
    {"id": "jazz_fusion", "bpm": 95.0, "weight": 0.9, "render": "lofi"},
]

VOICE_PERSONAS: list[dict[str, Any]] = [
    {"id": "hype_anchor", "voice": "en-US-GuyNeural", "rate": "+6%", "pitch": "+3Hz", "tone": "hyped"},
    {"id": "smooth_narrator", "voice": "en-US-AriaNeural", "rate": "-2%", "pitch": "+1Hz", "tone": "professional"},
    {"id": "celebration_host", "voice": "en-US-JennyNeural", "rate": "+8%", "pitch": "+4Hz", "tone": "dramatic"},
    {"id": "whale_alert", "voice": "en-US-GuyNeural", "rate": "+12%", "pitch": "+2Hz", "tone": "urgent"},
    {"id": "outro_warm", "voice": "en-US-AriaNeural", "rate": "-5%", "pitch": "+0Hz", "tone": "warm"},
]

VISUAL_SCENES: list[dict[str, str]] = [
    {"id": "lake_intro", "image": "neon_blue.jpg", "mood": "neon city night, luxury skyline"},
    {"id": "pump_printer", "image": "trader.jpg", "mood": "trading floor, Bloomberg terminals, money printer"},
    {"id": "purple_chart", "image": "purple_city.jpg", "mood": "purple neon city, chart storm, bull market"},
    {"id": "pink_chat", "image": "party.jpg", "mood": "VIP party, champagne, viral social energy"},
    {"id": "whale_alert", "image": "money_cash.jpg", "mood": "stacks of cash, whale buy, high stakes"},
    {"id": "celebration_dance", "image": "dancer.jpg", "mood": "nightclub celebration, milestone dance"},
    {"id": "fireworks_crown", "image": "celebration.jpg", "mood": "fireworks, king of the hill, crown moment"},
    {"id": "bonding_science", "image": "crypto.jpg", "mood": "crypto trading desk, bonding curve charts"},
    {"id": "meme_montage", "image": "dollars.jpg", "mood": "hundred dollar bills raining, diamond hands"},
    {"id": "dance_finale", "image": "money_cash.jpg", "mood": "cash rain finale, euphoric celebration"},
]

VISUAL_NEGATIVE = (
    "cartoon, 3d render, toy, miniature, anime, low resolution, blurry, "
    "plastic, fake, clip art, emoji, stick figure, childish, pixel art, "
    "abstract shapes, solid color background, empty screen"
)

MILESTONE_TIERS: list[dict[str, Any]] = [
    {"type": "MCAP_10K", "threshold": 10_000, "weight": 1.0, "genre_boost": "lofi_lake"},
    {"type": "MCAP_50K", "threshold": 50_000, "weight": 1.2, "genre_boost": "hiphop_hype"},
    {"type": "MCAP_100K", "threshold": 100_000, "weight": 1.4, "genre_boost": "edm_drop"},
    {"type": "MCAP_241K", "threshold": 241_000, "weight": 1.6, "genre_boost": "stadium_anthem"},
    {"type": "MCAP_1M", "threshold": 1_000_000, "weight": 2.0, "genre_boost": "trap_finale"},
]

_NO_REPEAT_CYCLES = 10


@dataclass
class StreamContext:
    symbol: str
    coin_name: str
    mint: str
    market_cap_usd: float = 42_000.0
    volume_24h: float = 0.0
    milestone_type: str = "MCAP_241K"
    chat_sentiment: str = "bullish"  # bullish | neutral | hype | fomo
    duration_sec: float = 205.0


# TrackHistory alias for backward compatibility
TrackHistory = StateTracker


class WeightedSelector:
    """Weighted random selection with milestone severity boost."""

    @staticmethod
    def pick(
        candidates: list[dict[str, Any]],
        rng: random.Random,
        weight_key: str = "weight",
        boost_id: str | None = None,
        boost_mult: float = 1.8,
    ) -> dict[str, Any]:
        weights = []
        for c in candidates:
            w = float(c.get(weight_key, 1.0))
            if boost_id and c.get("id") == boost_id:
                w *= boost_mult
            weights.append(w)
        return rng.choices(candidates, weights=weights, k=1)[0]

    @staticmethod
    def milestone_tier(mcap_usd: float) -> dict[str, Any]:
        tier = MILESTONE_TIERS[0]
        for t in MILESTONE_TIERS:
            if mcap_usd >= t["threshold"]:
                tier = t
        return tier


class DynamicPromptBuilder:
    """Construct multi-layered prompts from live token metadata."""

    @staticmethod
    def build_music_prompt(ctx: StreamContext, genre: dict[str, Any]) -> str:
        tier = WeightedSelector.milestone_tier(ctx.market_cap_usd)
        sentiment = ctx.chat_sentiment
        return (
            f"Generate a {genre['id']} celebration track for ${ctx.symbol} ({ctx.coin_name}). "
            f"Market cap: ${ctx.market_cap_usd:,.0f}, milestone: {tier['type']}, "
            f"sentiment: {sentiment}. BPM ~{genre['bpm']}. "
            f"High-energy Pump.fun livestream anthem — no repetitive loops, distinct sections."
        )

    @staticmethod
    def build_visual_prompt(ctx: StreamContext, scene: dict[str, str]) -> str:
        return (
            f"Photorealistic cinematic {scene['mood']} for ${ctx.symbol} livestream. "
            f"Market cap ${ctx.market_cap_usd:,.0f}. Luxury, high-stakes trading, real photography. "
            f"16:9, film grain, dramatic lighting."
        )

    @staticmethod
    def build_anthem_prompt(ctx: StreamContext, milestone: dict[str, Any]) -> str:
        return (
            f"Celebration anthem: {milestone['type']} reached on ${ctx.symbol}. "
            f"Coin: {ctx.coin_name}. MCAP ${ctx.market_cap_usd:,.0f}. "
            f"Genre: {milestone.get('genre_boost', 'stadium_anthem')}. Euphoric, singable chorus."
        )

    @staticmethod
    def build_voiceover(
        ctx: StreamContext,
        persona: dict[str, Any],
        moment: str,
        lyrics: TokenLyrics,
        hook_idx: int = 0,
    ) -> str:
        sym, name = ctx.symbol, ctx.coin_name
        mcap = ctx.market_cap_usd
        scripts = {
            "intro": lyrics.hook_line(hook_idx),
            "verse": (
                f"Chart climbing on {sym} — {name} holders see the green. "
                f"Volume surging, MCAP at ${mcap:,.0f}, this is the dream."
            ),
            "whale": (
                f"Whale alert on {sym}! Massive buy just hit the floor — "
                f"fifty thousand dollars, we want more!"
            ),
            "milestone": lyrics.milestone_line(mcap) + " " + lyrics.chorus_line(),
            "hype": (
                f"Pump dot fun is printing — {sym} on fire tonight! "
                f"Diamond paws, chart go vertical, feel that hype!"
            ),
            "outro": (
                f"Thanks for riding the {sym} wave with us. "
                f"Stay locked in — the next milestone is loading."
            ),
        }
        return scripts.get(moment, lyrics.hook_line(hook_idx))


class ScenePlanner:
    """Delegates to StreamOrchestrator for full multi-module planning."""

    def __init__(self, history: StateTracker | None = None) -> None:
        from cinema.stream_orchestrator import StreamOrchestrator
        self._orchestrator = StreamOrchestrator(history)

    def plan(self, ctx: StreamContext, simulated_chat: list[str] | None = None) -> StreamPlan:
        import asyncio
        return asyncio.run(self._orchestrator.build_plan(ctx, simulated_chat))

    async def plan_async(self, ctx: StreamContext, simulated_chat: list[str] | None = None) -> StreamPlan:
        return await self._orchestrator.build_plan(ctx, simulated_chat)

    def celebration_windows(self, plan: StreamPlan) -> list[tuple[float, float]]:
        return self._orchestrator.celebration_windows(plan)

    def music_sections(self, plan: StreamPlan) -> list[tuple[float, float, str, float]]:
        return self._orchestrator.music_sections(plan)
