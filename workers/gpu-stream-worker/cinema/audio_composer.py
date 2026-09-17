"""Custom lyrics + pleasant chord-based music + edge-tts vocal performance."""

from __future__ import annotations

import asyncio
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100

# Custom lyrics written for KWIF demo stream
LYRIC_SECTIONS: list[tuple[float, str, str, str]] = [
    # (start_sec, section_id, voice, text)
    (2.0, "intro", "en-US-AriaNeural", "Kitten Wif Hat on the screen tonight — KWIF is live on Pump dot fun!"),
    (14.0, "verse1", "en-US-JennyNeural", "Lake blue dreams and the chart starts to climb. Holders unite — we're right on time."),
    (28.0, "hook1", "en-US-GuyNeural", "Money from the pump machine — green candles on the screen!"),
    (48.0, "verse2", "en-US-AriaNeural", "Purple skies and the volume explodes. Every buy writes a brand new ode."),
    (62.0, "whale", "en-US-GuyNeural", "Whale alert! Fifty K just hit the floor. KWIF army — we want more!"),
    (82.0, "chorus", "en-US-JennyNeural",
     "Money raining down — dance with me! Two forty one K — king of the hill, feel that thrill! "
     "KWIF KWIF — celebration time! Cash falling like it's summertime!"),
    (108.0, "bridge", "en-US-AriaNeural", "Pink and green and gold collide. Addiction science — dopamine ride."),
    (125.0, "science", "en-US-GuyNeural", "Bonding curve science on the screen. Every frame a different dream."),
    (142.0, "chorus2", "en-US-JennyNeural",
     "Dance again — the milestone hit! Hundred dollar bills — every bit! "
     "Pump dot fun printing cash for you. KWIF forever — staying true!"),
    (168.0, "outro", "en-US-AriaNeural", "Thanks for riding the KWIF wave. See you on the next livestream — stay brave."),
]

NOTE = {
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99,
}


def _chord_freqs(names: list[str]) -> list[float]:
    return [NOTE[n] for n in names]


def _soft_tone(freq: float, t: np.ndarray, amp: float = 1.0) -> np.ndarray:
    """Warm pad tone — filtered saw simulation via harmonics."""
    w = np.zeros_like(t)
    for h, a in [(1, 1.0), (2, 0.35), (3, 0.15), (4, 0.08)]:
        w += a * np.sin(2 * math.pi * freq * h * t)
    env = 0.5 + 0.5 * np.sin(2 * math.pi * t * 0.25)
    return w * amp * env / 2.2


def _render_lofi_bed(duration_sec: float, bpm: float = 82.0) -> np.ndarray:
    """Soft lo-fi pop bed — I-V-vi-IV feel, gentle kick."""
    n = int(duration_sec * SAMPLE_RATE)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    beat = 60.0 / bpm
    # C - G - Am - F
    prog = [
        _chord_freqs(["C4", "E4", "G4"]),
        _chord_freqs(["G4", "B4", "D5"]),
        _chord_freqs(["A4", "C5", "E5"]),
        _chord_freqs(["F4", "A4", "C5"]),
    ]
    bed = np.zeros(n, dtype=np.float64)
    bar_samples = int(beat * 4 * SAMPLE_RATE)
    for i in range(0, n, bar_samples):
        chord = prog[(i // bar_samples) % len(prog)]
        seg_len = min(bar_samples, n - i)
        seg_t = t[i : i + seg_len] - t[i]
        layer = sum(_soft_tone(f, seg_t, 0.12) for f in chord)
        bed[i : i + seg_len] += layer
    # Soft kick on beats
    for beat_i in range(int(duration_sec / beat)):
        start = int(beat_i * beat * SAMPLE_RATE)
        kick_len = int(0.08 * SAMPLE_RATE)
        if start + kick_len > n:
            break
        kt = np.linspace(0, 0.08, kick_len, endpoint=False)
        kick = np.sin(2 * math.pi * 80 * kt) * np.exp(-kt * 40) * 0.18
        bed[start : start + kick_len] += kick
    return bed


def _render_celebration_bed(duration_sec: float, bpm: float = 118.0) -> np.ndarray:
    """Uplifting dance-pop celebration — major key, bright melody."""
    n = int(duration_sec * SAMPLE_RATE)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    beat = 60.0 / bpm
    prog = [
        _chord_freqs(["C4", "E4", "G4"]),
        _chord_freqs(["F4", "A4", "C5"]),
        _chord_freqs(["G4", "B4", "D5"]),
        _chord_freqs(["C4", "E4", "G4"]),
    ]
    melody_notes = ["E5", "G5", "E5", "C5", "D5", "E5", "G5", "E5"]
    bed = np.zeros(n, dtype=np.float64)
    bar_samples = int(beat * SAMPLE_RATE)
    for i in range(0, n, bar_samples):
        chord = prog[(i // bar_samples) % len(prog)]
        seg_len = min(bar_samples, n - i)
        seg_t = t[i : i + seg_len] - t[i]
        layer = sum(_soft_tone(f, seg_t, 0.14) for f in chord)
        mel_idx = (i // bar_samples) % len(melody_notes)
        layer += _soft_tone(NOTE[melody_notes[mel_idx]], seg_t, 0.09)
        bed[i : i + seg_len] += layer
    for beat_i in range(int(duration_sec / beat)):
        start = int(beat_i * beat * SAMPLE_RATE)
        kick_len = int(0.06 * SAMPLE_RATE)
        if start + kick_len > n:
            break
        kt = np.linspace(0, 0.06, kick_len, endpoint=False)
        kick = np.sin(2 * math.pi * 100 * kt) * np.exp(-kt * 50) * 0.28
        bed[start : start + kick_len] += kick
        # hi-hat
        hh_start = start + int(beat * 0.5 * SAMPLE_RATE)
        if hh_start + 800 < n:
            bed[hh_start : hh_start + 800] += np.random.randn(800) * 0.015
    swell = np.minimum(1.0, t / 1.5) * (1.0 - np.maximum(0, (t - duration_sec + 2) / 2))
    return bed * swell


def _decode_mp3(path: str) -> np.ndarray:
    cmd = [
        os.environ.get("FFMPEG_PATH", "ffmpeg"), "-hide_banner", "-loglevel", "error",
        "-i", path, "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    return np.frombuffer(proc.stdout, dtype=np.int16)


async def _tts_line(text: str, voice: str, out_mp3: Path) -> None:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="-5%", pitch="+2Hz")
    await comm.save(str(out_mp3))


async def build_master_audio(duration_sec: float) -> np.ndarray:
    """Full soundtrack: lo-fi base + celebration overlays + sung/spoken lyrics."""
    total = int(duration_sec * SAMPLE_RATE)
    master = np.zeros(total, dtype=np.float64)

    lofi = _render_lofi_bed(duration_sec) * 0.55
    master += lofi

    # Celebration sections overlay brighter bed
    for start_sec, dur in [(78.0, 32.0), (138.0, 30.0)]:
        celeb = _render_celebration_bed(dur) * 0.65
        s = int(start_sec * SAMPLE_RATE)
        e = min(s + len(celeb), total)
        master[s:e] += celeb[: e - s]

    tmpdir = Path(tempfile.mkdtemp(prefix="kwif-vox-"))
    for i, (at_sec, _sid, voice, text) in enumerate(LYRIC_SECTIONS):
        mp3 = tmpdir / f"vox_{i}.mp3"
        await _tts_line(text, voice, mp3)
        pcm = _decode_mp3(str(mp3)).astype(np.float64)
        # Gentle compression + presence
        pcm = pcm * 1.8
        start = int(at_sec * SAMPLE_RATE)
        end = min(start + len(pcm), total)
        n = end - start
        if n > 0:
            master[start:end] += pcm[:n]

    peak = np.max(np.abs(master))
    if peak > 0:
        master = master / peak * 0.88
    return (master * 32767).astype(np.int16)


def build_master_audio_sync(duration_sec: float) -> np.ndarray:
    return asyncio.run(build_master_audio(duration_sec))
