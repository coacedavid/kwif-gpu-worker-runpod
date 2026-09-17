"""
Production music pipeline — royalty-free beds, RunPod milestone anthems, loudnorm mix.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100
_WORKER_ROOT = Path(__file__).resolve().parent.parent
_STEMS = _WORKER_ROOT / "assets" / "audio" / "cinema_stems"
BG_CANDIDATES = [
    _STEMS / "bg_lofi.mp3",
    Path("/opt/cursor/artifacts/audio/bg.mp3"),
    Path("/workspace/workers/gpu-stream-worker/assets/audio/cinema_stems/bg_lofi.mp3"),
]
MILESTONE_CANDIDATES = [
    _STEMS / "milestone_anthem.mp3",
    Path("/opt/cursor/artifacts/audio/milestone_anthem.mp3"),
]
MILESTONE_HANDLER = Path(__file__).resolve().parent.parent.parent.parent / "serverless" / "milestone-music-worker" / "handler.py"


def _ffmpeg_decode(path: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    cmd = [
        os.environ.get("FFMPEG_PATH", "ffmpeg"), "-hide_banner", "-loglevel", "error",
        "-i", path, "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(sr), "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    return np.frombuffer(proc.stdout, dtype=np.int16)


def _loop_pcm(pcm: np.ndarray, total_samples: int) -> np.ndarray:
    if len(pcm) == 0:
        return np.zeros(total_samples, dtype=np.int16)
    reps = int(np.ceil(total_samples / len(pcm)))
    return np.tile(pcm, reps)[:total_samples]


def _download_bg_music(dest: Path) -> bool:
    """Fetch royalty-free Carefree (Kevin MacLeod / incompetech) on first run."""
    url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3"
    try:
        import httpx
        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            dest.write_bytes(r.content)
        print(f"  downloaded background bed -> {dest}")
        return True
    except Exception as exc:
        print(f"  bg download failed: {exc}")
        return False


def _find_bg_music() -> str | None:
    for p in BG_CANDIDATES:
        if p.exists():
            return str(p)
    dest = _STEMS / "bg_lofi.mp3"
    if _download_bg_music(dest):
        return str(dest)
    return None


def _find_milestone_anthem() -> str | None:
    for p in MILESTONE_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def generate_milestone_anthem(payload: dict) -> tuple[str, float]:
    """Run production milestone-music-worker handler locally."""
    handler = MILESTONE_HANDLER
    if not handler.exists():
        handler = Path("/workspace/serverless/milestone-music-worker/handler.py")
    proc = subprocess.run(
        [sys.executable, str(handler), json.dumps(payload)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "milestone handler failed")
    # Parse JSON from last { in output
    text = proc.stdout
    start = text.rfind("{")
    data = json.loads(text[start:])
    out = data.get("output") or data
    path = out.get("localPath") or out.get("audioUrl", "").replace("file://", "")
    duration = float(out.get("durationSec") or out.get("duration") or 28)
    return path, duration


async def _tts_line(text: str, voice: str, out_mp3: Path) -> None:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="-3%", pitch="+1Hz")
    await comm.save(str(out_mp3))


async def build_live_soundtrack(
    duration_sec: float,
    symbol: str = "KWIF",
    coin_name: str = "Kitten Wif Hat",
    mint: str = "",
    milestone_times: list[float] | None = None,
    preferred_style: str = "lofi",
) -> np.ndarray:
    """
    Diverse AI-composed soundtrack: rotating musical sections, celebration SONGS
    at milestones (not the same loop), custom sung lyrics throughout.
    """
    from cinema.song_composer import compose_diverse_soundtrack

    bg_path = _find_bg_music()
    anthem_path = _find_milestone_anthem()
    if not anthem_path:
        try:
            anthem_path, _ = generate_milestone_anthem({
                "tokenName": symbol, "tokenMint": mint or "demo-mint",
                "coinName": coin_name, "milestoneType": "MCAP_241K", "marketCapUsd": 241_000,
            })
        except Exception as exc:
            print(f"  milestone anthem gen skipped: {exc}")
            anthem_path = None

    print(f"  diverse song composer: bg={bg_path}, anthem={anthem_path}, style={preferred_style}")
    return await compose_diverse_soundtrack(
        duration_sec,
        symbol=symbol,
        coin_name=coin_name,
        mint=mint,
        milestone_anthem_path=anthem_path,
        royalty_bg_path=bg_path,
        preferred_style=preferred_style,
    )


def build_live_soundtrack_sync(
    duration_sec: float,
    symbol: str = "KWIF",
    coin_name: str = "Kitten Wif Hat",
    mint: str = "",
    milestone_times: list[float] | None = None,
    preferred_style: str = "lofi",
) -> np.ndarray:
    return asyncio.run(
        build_live_soundtrack(duration_sec, symbol, coin_name, mint, milestone_times, preferred_style)
    )


def loudnorm_audio(in_path: Path, out_path: Path) -> None:
    """FFmpeg loudnorm to -14 LUFS — fixes 'silent' playback on mobile."""
    subprocess.run(
        [
            os.environ.get("FFMPEG_PATH", "ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(in_path),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-ar", str(SAMPLE_RATE), "-ac", "2",
            str(out_path),
        ],
        check=True,
        timeout=300,
    )
