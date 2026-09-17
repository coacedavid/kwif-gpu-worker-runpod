"""RunPod Serverless handler — milestone celebration anthem generator."""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import wave
from pathlib import Path
from typing import Any

import httpx
import numpy as np

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("milestone_music")

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/tmp/milestone_output"))
MODEL_BACKEND = os.environ.get("MILESTONE_MUSIC_BACKEND", "procedural")
ORCHESTRATOR_CALLBACK_URL = os.environ.get("ORCHESTRATOR_CALLBACK_URL", "")
MILESTONE_WEBHOOK_SECRET = os.environ.get("MILESTONE_WEBHOOK_SECRET", "")


def _format_market_cap(usd: float) -> str:
    if usd >= 1_000_000:
        return f"${usd / 1_000_000:.1f}M"
    if usd >= 1_000:
        return f"${usd / 1_000:.0f}K"
    return f"${usd:.0f}"


def generate_celebration_lyrics(payload: dict[str, Any]) -> str:
    token = str(payload.get("tokenName") or payload.get("symbol") or "$TOKEN")
    if not token.startswith("$"):
        token = f"${token}"
    name = str(payload.get("coinName") or payload.get("title") or token)
    milestone = str(payload.get("milestoneType") or payload.get("metric") or "MILESTONE")
    mcap = float(payload.get("marketCapUsd") or payload.get("marketCap") or 0)
    mcap_str = _format_market_cap(mcap)
    lines = [f"{token} on the rise, the charts ignite,", f"{name} shining gold in the neon light,",
             f"Hit {milestone.replace('_', ' ')} — we made it through,", f"Market cap at {mcap_str}, the whales came true!",
             "From obsidian floors to the emerald sky,", f"Victory anthem for {token} — touch the high!"]
    return "\n".join(lines)


def _synthesize_procedural_anthem(lyrics: str, genre: str, out_path: Path, duration_sec: float = 28.0) -> None:
    sample_rate = 44100
    samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, samples, endpoint=False)
    kick = np.sin(2 * math.pi * 55 * t) * (np.sin(2 * math.pi * 2 * t) > 0.8)
    bass = 0.4 * np.sin(2 * math.pi * 82.41 * t)
    lead = 0.25 * np.sin(2 * math.pi * 440 * t + np.sin(t * 3))
    pcm = np.clip((kick * 0.5 + bass + lead) * np.linspace(0.3, 1.0, samples) * 14000, -32768, 32767).astype(np.int16)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate); wf.writeframes(pcm.tobytes())


def _encode_mp3(wav_path: Path) -> Path:
    mp3_path = wav_path.with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav_path),
        "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)], check=True, timeout=120)
    return mp3_path


def generate_anthem(payload: dict[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lyrics = generate_celebration_lyrics(payload)
    genre = str(payload.get("genre") or "euphoric trap, victory anthem, stadium bass, gold status")
    mint = str(payload.get("tokenMint") or "unknown")[:12]
    out_path = OUTPUT_DIR / f"anthem_{mint}_{payload.get('milestoneType', 'milestone')}.wav"
    _synthesize_procedural_anthem(lyrics, genre, out_path)
    mp3_path = _encode_mp3(out_path)
    anthem_url = f"file://{mp3_path}"
    return {"success": True, "audioUrl": anthem_url, "anthemUrl": anthem_url, "duration": 28.0,
            "durationSec": 28.0, "lyrics": lyrics, "localPath": str(mp3_path)}


def handler(event: dict[str, Any]) -> dict[str, Any]:
    input_payload = event.get("input") or event
    try:
        return {"status": "COMPLETED", "output": generate_anthem(input_payload)}
    except Exception as exc:
        return {"status": "FAILED", "error": str(exc)}


def runpod_handler(event: dict[str, Any]) -> dict[str, Any]:
    return handler(event)


try:
    import runpod
    runpod.serverless.start({"handler": runpod_handler})
except ImportError:
    pass
