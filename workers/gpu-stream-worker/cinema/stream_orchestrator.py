"""
Unified stream orchestrator — wires UTC, holidays, trends, news, chat, music, visuals.

Single entry point for building a complete non-repeating stream plan.
"""

from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime, timezone
from typing import Any

from cinema.chat_intel import ChatIntelEngine
from cinema.dynamic_engine import (
    MUSIC_GENRES,
    VISUAL_NEGATIVE,
    VISUAL_SCENES,
    VOICE_PERSONAS,
    DynamicPromptBuilder,
    StreamContext,
    WeightedSelector,
)
from cinema.lyrics import TokenLyrics
from cinema.motivation_engine import build_motivation_segments
from cinema.news_satire_engine import build_satire_segments, fetch_news_headlines, trading_joke
from cinema.scene_schema import (
    AudioLayer,
    AudioLayerSpec,
    InteractiveLayer,
    MilestoneSpec,
    StreamPlan,
    UnifiedScene,
    VisualLayer,
    VisualSceneSpec,
    VocalSpec,
)
from cinema.state_tracker import StateTracker
from cinema.trends_engine import fetch_trending_topics, trend_commentary
from cinema.utc_holidays import active_holiday_theme, holiday_voiceover
from cinema.utc_time_engine import build_utc_segments, is_late_night_grind, utc_now


class StreamOrchestrator:
    """Assembles all sub-modules into a unified StreamPlan."""

    def __init__(self, tracker: StateTracker | None = None) -> None:
        self._tracker = tracker or StateTracker()
        self._chat = ChatIntelEngine()

    @property
    def chat(self) -> ChatIntelEngine:
        return self._chat

    async def build_plan(
        self,
        ctx: StreamContext,
        simulated_chat: list[str] | None = None,
    ) -> StreamPlan:
        seed = hashlib.sha256(f"{ctx.mint}:{time.time():.3f}".encode()).hexdigest()[:12]
        rng = random.Random(int(seed, 16))
        now = utc_now()
        tier = WeightedSelector.milestone_tier(ctx.market_cap_usd)
        lyrics = TokenLyrics(ctx.symbol, ctx.coin_name, ctx.mint)
        holiday = active_holiday_theme(now.date())
        stream_theme = holiday.theme if holiday else "default"

        # Ingest simulated chat
        for line in simulated_chat or []:
            self._chat.ingest(line)

        # Async context feeds
        trends = await fetch_trending_topics(ctx.symbol)
        headlines = await fetch_news_headlines(3)
        trend_text = trend_commentary(trends, ctx.symbol)

        plan = StreamPlan(
            symbol=ctx.symbol,
            coin_name=ctx.coin_name,
            mint=ctx.mint,
            duration_sec=ctx.duration_sec,
            seed=seed,
            stream_theme=stream_theme,
            timestamp_utc=now.isoformat(),
        )

        # ── Audio layers (no-repeat genres) ──
        t = 0.0
        idx = 0
        genres_avail = self._tracker.filter_available("genre", MUSIC_GENRES)
        boost = holiday.song_genre_boost if holiday else tier.get("genre_boost")
        while t < ctx.duration_sec - 8:
            dur = rng.uniform(22.0, 36.0)
            genre = WeightedSelector.pick(genres_avail, rng, boost_id=boost, boost_mult=1.8)
            self._tracker.record("genre", genre["id"])
            self._tracker.record("beat", genre["id"])
            plan.audio_layers.append(AudioLayerSpec(
                layer_id=f"layer_{idx}",
                genre=genre["id"],
                bpm=genre["bpm"] + rng.uniform(-4, 4),
                start_sec=t,
                duration_sec=min(dur, ctx.duration_sec - t),
                asset_hash=hashlib.md5(f"{seed}:{genre['id']}:{idx}".encode()).hexdigest()[:8],
                prompt=DynamicPromptBuilder.build_music_prompt(ctx, genre),
            ))
            t += dur
            idx += 1
            genres_avail = self._tracker.filter_available("genre", MUSIC_GENRES)

        # ── Milestones ──
        for frac, mult in [(0.40, 1.0), (0.67, 1.5)]:
            at = ctx.duration_sec * frac
            mcap = max(ctx.market_cap_usd, tier["threshold"] * mult)
            m_tier = WeightedSelector.milestone_tier(mcap)
            plan.milestones.append(MilestoneSpec(
                at_sec=at,
                milestone_type=m_tier["type"],
                market_cap_usd=mcap,
                celebration_genre=m_tier["genre_boost"],
                anthem_prompt=DynamicPromptBuilder.build_anthem_prompt(ctx, m_tier),
            ))

        # ── Collect all vocal scripts ──
        vocal_queue: list[tuple[float, str, str, str, str, str, bool]] = []

        # UTC segments
        for seg in build_utc_segments(ctx.duration_sec, ctx.symbol):
            persona = next((p for p in VOICE_PERSONAS if p["id"] == seg.persona_id), VOICE_PERSONAS[1])
            vocal_queue.append((seg.at_sec, seg.persona_id, persona["voice"], seg.script,
                                persona["rate"], persona["pitch"], False))

        # Holiday
        if holiday:
            hv = holiday_voiceover(holiday, ctx.symbol, now.hour)
            persona = VOICE_PERSONAS[1]
            vocal_queue.append((5.0, persona["id"], persona["voice"], hv, persona["rate"], persona["pitch"], False))

        # Motivation
        for m in build_motivation_segments(
            ctx.duration_sec, ctx.symbol, ctx.market_cap_usd,
            is_late_night_grind(now), seed,
        ):
            persona = next((p for p in VOICE_PERSONAS if p["id"] == m.persona_id), VOICE_PERSONAS[0])
            vocal_queue.append((m.at_sec, m.persona_id, persona["voice"], m.script,
                                persona["rate"], persona["pitch"], False))

        # News/satire
        for ns in build_satire_segments(headlines, ctx.symbol, ctx.duration_sec, seed):
            persona = next((p for p in VOICE_PERSONAS if p["id"] == ns.persona_id), VOICE_PERSONAS[0])
            vocal_queue.append((ns.at_sec, ns.persona_id, persona["voice"],
                                f"{ns.headline}. {ns.commentary}",
                                persona.get("rate", "-2%"), persona.get("pitch", "+1Hz"), False))

        # Trends
        vocal_queue.append((45.0, "witty_satirist", "en-US-GuyNeural", trend_text, "+4%", "+2Hz", False))

        # Trading joke
        joke = trading_joke(ctx.symbol, ctx.market_cap_usd, trends[0].title if trends else "")
        vocal_queue.append((90.0, "witty_satirist", "en-US-GuyNeural", joke, "+6%", "+2Hz", False))

        # Milestone vocals
        for m in plan.milestones:
            persona = VOICE_PERSONAS[2]
            text = lyrics.milestone_line(m.market_cap_usd) + " " + lyrics.chorus_line()
            vocal_queue.append((m.at_sec + 2, persona["id"], persona["voice"], text,
                                "+10%", "+5Hz", True))

        # Chat Q&A and shoutouts
        vocal_queue.append((60.0, "hype_anchor", "en-US-GuyNeural", self._chat.qa_prompt(0), "+6%", "+3Hz", False))
        shoutout = self._chat.pick_shoutout(ctx.symbol, 75.0)
        if shoutout:
            vocal_queue.append((shoutout.at_sec, "hype_anchor", "en-US-GuyNeural",
                                shoutout.response_script, "+8%", "+3Hz", False))

        # Standard verse/hook vocals
        moments = ["intro", "verse", "whale", "hype", "outro"]
        personas_avail = self._tracker.filter_available("persona", VOICE_PERSONAS)
        for i, moment in enumerate(moments):
            at = [14.0, 28.0, 62.0, 120.0, ctx.duration_sec * 0.88][i]
            if at >= ctx.duration_sec:
                break
            persona = WeightedSelector.pick(personas_avail, rng)
            self._tracker.record("persona", persona["id"])
            personas_avail = self._tracker.filter_available("persona", VOICE_PERSONAS)
            text = DynamicPromptBuilder.build_voiceover(ctx, persona, moment, lyrics, i)
            vocal_queue.append((at, persona["id"], persona["voice"], text,
                                persona["rate"], persona["pitch"], moment in ("hype",)))

        # Dedupe and sort vocals
        vocal_queue.sort(key=lambda x: x[0])
        for at, pid, voice, text, rate, pitch, chorus in vocal_queue:
            if at >= ctx.duration_sec:
                continue
            plan.vocals.append(VocalSpec(at, pid, voice, text, rate, pitch, chorus))

        # ── Visual scenes (daily layout exclusion) ──
        vis_avail = self._tracker.filter_available("visual", VISUAL_SCENES, daily_layout=True)
        vt = 0.0
        while vt < ctx.duration_sec:
            dur = rng.uniform(16.0, 26.0)
            scene = WeightedSelector.pick(vis_avail, rng)
            self._tracker.record("visual", scene["id"])
            self._tracker.record_daily_layout(scene["id"])
            plan.visual_scenes.append(VisualSceneSpec(
                scene_id=scene["id"],
                start_sec=vt,
                duration_sec=min(dur, ctx.duration_sec - vt),
                stock_image=scene["image"],
                visual_prompt=DynamicPromptBuilder.build_visual_prompt(ctx, scene),
                negative_prompt=VISUAL_NEGATIVE,
                overlay=holiday.visual_overlay if holiday and vt < 30 else "",
            ))
            vt += dur
            vis_avail = self._tracker.filter_available("visual", VISUAL_SCENES, daily_layout=True)

        # ── Build unified scenes (one per vocal + visual overlap) ──
        interactive = self._chat.to_interactive_layer()
        interactive["trend_topic"] = trends[0].title if trends else ""

        for i, vocal in enumerate(plan.vocals):
            vis = next(
                (v for v in plan.visual_scenes if v.start_sec <= vocal.at_sec < v.start_sec + v.duration_sec),
                plan.visual_scenes[0] if plan.visual_scenes else None,
            )
            audio_layer = next(
                (a for a in plan.audio_layers if a.start_sec <= vocal.at_sec < a.start_sec + a.duration_sec),
                plan.audio_layers[0] if plan.audio_layers else None,
            )
            scene = UnifiedScene(
                scene_id=f"scene_{i:03d}",
                timestamp_utc=datetime.fromtimestamp(
                    now.timestamp() + vocal.at_sec, tz=timezone.utc,
                ).isoformat(),
                stream_theme=stream_theme,
                start_sec=vocal.at_sec,
                duration_sec=12.0,
                visual_layer=VisualLayer(
                    background_type="luxury_stock",
                    prompt=vis.visual_prompt if vis else "",
                    negative_prompt=VISUAL_NEGATIVE,
                    stock_image=vis.stock_image if vis else "neon_blue.jpg",
                ),
                audio_layer=AudioLayer(
                    beat_id=audio_layer.asset_hash if audio_layer else seed,
                    song_genre=audio_layer.genre if audio_layer else "default",
                    lyrics_context=ctx.symbol,
                    voiceover_persona=vocal.persona_id,
                    script=vocal.text,
                    bpm=audio_layer.bpm if audio_layer else 100.0,
                    voice=vocal.voice,
                    rate=vocal.rate,
                    pitch=vocal.pitch,
                    is_chorus=vocal.is_chorus,
                ),
                interactive_layer=InteractiveLayer(
                    chat_shoutouts=interactive.get("chat_shoutouts", []),
                    trend_topic=interactive.get("trend_topic", ""),
                    dominant_sentiment=interactive.get("dominant_sentiment", "bullish"),
                    qa_prompt=self._chat.qa_prompt(i) if i % 5 == 0 else "",
                ),
            )
            plan.unified_scenes.append(scene)

        return plan

    def celebration_windows(self, plan: StreamPlan) -> list[tuple[float, float]]:
        return [(m.at_sec, 26.0 if i == 0 else 20.0) for i, m in enumerate(plan.milestones)]

    def music_sections(self, plan: StreamPlan) -> list[tuple[float, float, str, float]]:
        return [(l.start_sec, l.duration_sec, l.genre, l.bpm) for l in plan.audio_layers]
