"""
Diverse AI-composed songs with custom lyrics — not one loop throughout.

Background rotates through distinct musical sections; milestones get full
celebration songs (new bed + sung chorus + anthem) with background ducked.
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
    _tts_line,
)
from cinema.lyrics import TokenLyrics

# Musical sections: (start_sec, duration, style, bpm)
MUSIC_SECTIONS: list[tuple[float, float, str, float]] = [
    (0.0, 38.0, "ambient_lofi", 78.0),
    (38.0, 32.0, "lake_pop", 92.0),
    (70.0, 12.0, "build_hype", 108.0),
    (108.0, 16.0, "violet_groove", 100.0),
    (124.0, 18.0, "science_chill", 85.0),
    (142.0, 16.0, "meme_energy", 115.0),
    (158.0, 22.0, "finale_trap", 120.0),
    (180.0, 25.0, "outro_soft", 72.0),
]

CELEBRATION_WINDOWS: list[tuple[float, float]] = [
    (82.0, 26.0),
    (138.0, 20.0),
]

# Sung lyric schedule: (start_sec, voice, text_key or raw text)
@dataclass
class VocalLine:
    at_sec: float
    voice: str
    text: str
    is_chorus: bool = False


def _build_vocal_schedule(symbol: str, coin_name: str, mint: str) -> list[VocalLine]:
    lyrics = TokenLyrics(symbol=symbol, coin_name=coin_name, mint=mint)
    return [
        VocalLine(2.0, "en-US-AriaNeural", lyrics.hook_line(0)),
        VocalLine(14.0, "en-US-JennyNeural",
                  f"Lake blue dreams and the chart starts to climb. {symbol} holders unite — right on time."),
        VocalLine(28.0, "en-US-GuyNeural", "Money from the pump machine — green candles on the screen!"),
        VocalLine(48.0, "en-US-AriaNeural",
                  f"Purple skies and the volume explodes. Every buy writes a brand new {symbol} ode."),
        VocalLine(62.0, "en-US-GuyNeural", "Whale alert! Fifty thousand just hit the floor — we want more!"),
        VocalLine(84.0, "en-US-JennyNeural",
                  f"Money raining down — dance with me! {symbol} two forty one K — king of the hill! "
                  f"{lyrics.chorus_line()}", is_chorus=True),
        VocalLine(110.0, "en-US-AriaNeural", "Pink and green and gold collide — dopamine science on our side."),
        VocalLine(125.0, "en-US-GuyNeural", f"Bonding curve climbing on the screen — every frame a {symbol} dream."),
        VocalLine(140.0, "en-US-JennyNeural",
                  f"Dance again — the milestone hit! Hundred dollar bills — every bit! "
                  f"Pump dot fun printing cash for you. {symbol} forever — staying true!", is_chorus=True),
        VocalLine(168.0, "en-US-AriaNeural", f"Thanks for riding the {symbol} wave. Stay locked in — we're just getting started."),
    ]


def _render_style_bed(duration_sec: float, style: str, bpm: float) -> np.ndarray:
    if style in ("build_hype", "finale_trap", "meme_energy"):
        return _render_celebration_bed(duration_sec, bpm=bpm) * 0.5
    if style == "outro_soft":
        return _render_lofi_bed(duration_sec, bpm=bpm) * 0.4
    return _render_lofi_bed(duration_sec, bpm=bpm) * 0.55


def _decode_path(path: str) -> np.ndarray:
    return _decode_mp3(path).astype(np.float64)


async def compose_diverse_soundtrack(
    duration_sec: float,
    symbol: str = "KWIF",
    coin_name: str = "Kitten Wif Hat",
    mint: str = "",
    milestone_anthem_path: str | None = None,
    royalty_bg_path: str | None = None,
    preferred_style: str = "lofi",
) -> np.ndarray:
    """
    Full diverse soundtrack:
    - Rotating background sections (not one loop)
    - Optional royalty-free bed woven between sections
    - Full celebration SONGS at milestones (bed + anthem + sung chorus, bg ducked)
    - Custom AI vocals throughout
    """
    total = int(duration_sec * SAMPLE_RATE)
    master = np.zeros(total, dtype=np.float64)

    # Layer 1: rotating composed sections
    for start_sec, dur, style, bpm in MUSIC_SECTIONS:
        if start_sec >= duration_sec:
            break
        bed = _render_style_bed(min(dur, duration_sec - start_sec), style, bpm)
        s = int(start_sec * SAMPLE_RATE)
        e = min(s + len(bed), total)
        # Skip celebration windows — filled by celebration songs
        for celeb_start, celeb_dur in CELEBRATION_WINDOWS:
            cs, ce = int(celeb_start * SAMPLE_RATE), int((celeb_start + celeb_dur) * SAMPLE_RATE)
            if s < ce and e > cs:
                # Partial overlap — reduce bg in celebration zone
                overlap_s = max(s, cs)
                overlap_e = min(e, ce)
                if overlap_s < overlap_e:
                    master[overlap_s:overlap_e] *= 0.12
        master[s:e] += bed[: e - s]

    # Layer 2: royalty-free bed at low volume between sections for continuity
    if royalty_bg_path and Path(royalty_bg_path).exists():
        bg = _decode_path(royalty_bg_path) * 0.28
        reps = int(np.ceil(total / len(bg))) if len(bg) else 0
        tiled = np.tile(bg, reps)[:total] if reps else np.zeros(total)
        master += tiled

    # Layer 3: CELEBRATION SONGS — distinct from background
    anthem_path = milestone_anthem_path
    for celeb_start, celeb_dur in CELEBRATION_WINDOWS:
        if celeb_start >= duration_sec:
            continue
        celeb_bed = _render_celebration_bed(celeb_dur, bpm=122.0) * 0.82
        s = int(celeb_start * SAMPLE_RATE)
        e = min(s + len(celeb_bed), total)
        # Duck existing mix in celebration window
        master[s:e] *= 0.15
        master[s:e] += celeb_bed[: e - s]
        if anthem_path and Path(anthem_path).exists():
            anthem = _decode_path(anthem_path) * 1.1
            ae = min(s + len(anthem), e)
            master[s:ae] += anthem[: ae - s]

    # Layer 4: AI-sung vocals
    vocals = _build_vocal_schedule(symbol, coin_name, mint or "demo-mint")
    tmpdir = Path(tempfile.mkdtemp(prefix="songs-"))
    for i, v in enumerate(vocals):
        if v.at_sec >= duration_sec:
            continue
        mp3 = tmpdir / f"v{i}.mp3"
        rate = "+8%" if v.is_chorus else "-3%"
        pitch = "+4Hz" if v.is_chorus else "+1Hz"
        import edge_tts
        comm = edge_tts.Communicate(v.text, v.voice, rate=rate, pitch=pitch)
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
    return (master * 32767).astype(np.int16)


def compose_diverse_soundtrack_sync(**kwargs) -> np.ndarray:
    return asyncio.run(compose_diverse_soundtrack(**kwargs))
