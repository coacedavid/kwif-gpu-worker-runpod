"""
Diverse AI-composed songs — driven by dynamic_engine.ScenePlanner.

No hardcoded section lists. Each run produces a unique StreamPlan with
weighted genre selection, rotating voice personas, and milestone-aware prompts.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cinema.audio_composer import (
    SAMPLE_RATE,
    _decode_mp3,
    _render_celebration_bed,
    _render_lofi_bed,
)
from cinema.dynamic_engine import StreamContext
from cinema.stream_orchestrator import StreamOrchestrator
from cinema.scene_schema import StreamPlan, VocalSpec

# Render style mapping: genre id prefix → synthesis function
_CELEBRATION_GENRES = frozenset({
    "hiphop_hype", "edm_drop", "trap_finale", "meme_energy", "stadium_anthem",
})


@dataclass
class VocalLine:
    at_sec: float
    voice: str
    text: str
    rate: str = "-3%"
    pitch: str = "+1Hz"
    is_chorus: bool = False


def _render_style_bed(duration_sec: float, genre_id: str, bpm: float) -> np.ndarray:
    if genre_id in _CELEBRATION_GENRES or "trap" in genre_id or "edm" in genre_id:
        return _render_celebration_bed(duration_sec, bpm=bpm) * 0.5
    if "ambient" in genre_id or "chill" in genre_id or "lofi" in genre_id:
        return _render_lofi_bed(duration_sec, bpm=bpm) * 0.4
    return _render_lofi_bed(duration_sec, bpm=bpm) * 0.55


def _decode_path(path: str) -> np.ndarray:
    return _decode_mp3(path).astype(np.float64)


def _vocals_from_plan(plan: StreamPlan) -> list[VocalLine]:
    return [
        VocalLine(v.at_sec, v.voice, v.text, v.rate, v.pitch, v.is_chorus)
        for v in plan.vocals
    ]


async def compose_diverse_soundtrack(
    duration_sec: float,
    symbol: str = "KWIF",
    coin_name: str = "Kitten Wif Hat",
    mint: str = "",
    milestone_anthem_path: str | None = None,
    royalty_bg_path: str | None = None,
    preferred_style: str = "hype",
    plan: StreamPlan | None = None,
) -> tuple[np.ndarray, StreamPlan]:
    """
    Full diverse soundtrack from a dynamic StreamPlan:
    - Weighted genre sections (no repeat within N cycles)
    - Celebration songs at milestone windows
    - AI vocals with rotating personas
    """
    ctx = StreamContext(
        symbol=symbol,
        coin_name=coin_name,
        mint=mint or "demo-mint",
        market_cap_usd=241_000 if preferred_style == "hype" else 42_000,
        chat_sentiment="hype" if preferred_style == "hype" else "bullish",
        duration_sec=duration_sec,
    )
    orchestrator = StreamOrchestrator()
    if plan is None:
        plan = await orchestrator.build_plan(ctx)

    music_sections = orchestrator.music_sections(plan)
    celebration_windows = orchestrator.celebration_windows(plan)
    vocals = _vocals_from_plan(plan)

    print(f"  dynamic plan seed={plan.seed} genres={[l.genre for l in plan.audio_layers]}")
    print(f"  personas={[v.persona_id for v in plan.vocals]} milestones={len(plan.milestones)}")

    total = int(duration_sec * SAMPLE_RATE)
    master = np.zeros(total, dtype=np.float64)

    # Layer 1: dynamic genre sections
    for start_sec, dur, genre_id, bpm in music_sections:
        if start_sec >= duration_sec:
            break
        bed = _render_style_bed(min(dur, duration_sec - start_sec), genre_id, bpm)
        s = int(start_sec * SAMPLE_RATE)
        e = min(s + len(bed), total)
        for celeb_start, celeb_dur in celebration_windows:
            cs = int(celeb_start * SAMPLE_RATE)
            ce = int((celeb_start + celeb_dur) * SAMPLE_RATE)
            if s < ce and e > cs:
                overlap_s, overlap_e = max(s, cs), min(e, ce)
                if overlap_s < overlap_e:
                    master[overlap_s:overlap_e] *= 0.12
        master[s:e] += bed[: e - s]

    # Layer 2: royalty-free bed at low volume
    if royalty_bg_path and Path(royalty_bg_path).exists():
        bg = _decode_path(royalty_bg_path) * 0.22
        reps = int(np.ceil(total / len(bg))) if len(bg) else 0
        tiled = np.tile(bg, reps)[:total] if reps else np.zeros(total)
        master += tiled

    # Layer 3: celebration songs at milestone windows
    for celeb_start, celeb_dur in celebration_windows:
        if celeb_start >= duration_sec:
            continue
        celeb_bed = _render_celebration_bed(celeb_dur, bpm=122.0) * 0.82
        s = int(celeb_start * SAMPLE_RATE)
        e = min(s + len(celeb_bed), total)
        master[s:e] *= 0.15
        master[s:e] += celeb_bed[: e - s]
        if milestone_anthem_path and Path(milestone_anthem_path).exists():
            anthem = _decode_path(milestone_anthem_path) * 1.1
            ae = min(s + len(anthem), e)
            master[s:ae] += anthem[: ae - s]

    # Layer 4: AI-sung vocals (edge-tts)
    tmpdir = Path(tempfile.mkdtemp(prefix="songs-"))
    for i, v in enumerate(vocals):
        if v.at_sec >= duration_sec:
            continue
        mp3 = tmpdir / f"v{i}.mp3"
        import edge_tts
        comm = edge_tts.Communicate(v.text, v.voice, rate=v.rate, pitch=v.pitch)
        await comm.save(str(mp3))
        pcm = _decode_path(str(mp3))
        gain = 2.2 if v.is_chorus else 1.7
        pcm *= gain
        start = int(v.at_sec * SAMPLE_RATE)
        end = min(start + len(pcm), total)
        master[start:end] += pcm[: end - start]

    peak = np.max(np.abs(master))
    if peak > 0:
        master = master / peak * 0.91
    return (master * 32767).astype(np.int16), plan


def compose_diverse_soundtrack_sync(**kwargs) -> tuple[np.ndarray, StreamPlan]:
    return asyncio.run(compose_diverse_soundtrack(**kwargs))
