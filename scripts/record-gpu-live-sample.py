#!/usr/bin/env python3
"""
Record a sample video on RunPod using the production creative path:
  CinemaCompositor (photoreal + live HUD) + diverse AI songs with sung lyrics.

NOT the old AudioEngine single-loop path — this uses song_composer with
rotating musical sections, token-context lyrics, and celebration songs.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

WORKER = Path(__file__).resolve().parent.parent / "workers" / "gpu-stream-worker"
sys.path.insert(0, str(WORKER))

from cinema.dynamic_engine import ScenePlanner, StreamContext
from cinema.music_pipeline import SAMPLE_RATE, build_live_soundtrack, loudnorm_audio
from cinema.song_composer import compose_diverse_soundtrack
from cinema_compositor import CinemaCompositor
from token_state import TokenState

WIDTH = int(os.environ.get("WIDTH", "1280"))
HEIGHT = int(os.environ.get("HEIGHT", "720"))
FPS = int(os.environ.get("FPS", "30"))
DURATION_SEC = float(os.environ.get("RECORD_DURATION_SEC", "205"))
OUT_PATH = Path(os.environ.get("OUTPUT_MP4", "/tmp/runpod-live-sample.mp4"))
SYMBOL = os.environ.get("TOKEN_SYMBOL", "KWIF")
COIN_NAME = os.environ.get("COIN_NAME", "Kitten Wif Hat")
MINT = os.environ.get("TOKEN_MINT", "demo-kwif-mint-runpod")
MUSIC_STYLE = os.environ.get("MUSIC_STYLE", "hype")


def _write_stereo_wav(path: Path, pcm_mono: np.ndarray) -> None:
    stereo = np.column_stack([pcm_mono, pcm_mono]).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(stereo.tobytes())


async def _schedule_live_events(compositor: CinemaCompositor) -> None:
    """Simulate whale buy, milestones, and chat feedback during recording."""
    await asyncio.sleep(25)
    compositor.add_chat_notification("trader99: can't see the mcap numbers??")
    compositor.set_caption("Chat asked for numbers — live HUD activated!")

    await asyncio.sleep(45)  # ~70s
    compositor.set_alert("🐋 WHALE BUY — $52,400 DETECTED", duration=14)
    compositor._director.trigger("whale")

    await asyncio.sleep(12)  # ~82s
    compositor.trigger_milestone("MILESTONE — $241K MCAP", "Celebration song playing!", duration=26)
    compositor._director.trigger("milestone", duration_sec=28)

    await asyncio.sleep(56)  # ~138s
    compositor.trigger_milestone("SECOND MILESTONE", "Cash rain — new celebration song!", duration=20)
    compositor._director.trigger("milestone", duration_sec=24)

    await asyncio.sleep(30)
    compositor.add_chat_notification("kwif_army: LOVE this celebration song!!")
    compositor.set_caption("Chat loves the vibe — playing more hype tracks!")


async def record() -> Path:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CINEMA_PROCEDURAL", "0")

    ctx = StreamContext(
        symbol=SYMBOL, coin_name=COIN_NAME, mint=MINT,
        market_cap_usd=241_000, chat_sentiment="hype", duration_sec=DURATION_SEC,
    )
    planner = ScenePlanner()
    stream_plan = planner.plan(ctx)
    plan_path = Path("/tmp/runpod-stream-plan.json")
    plan_path.write_text(stream_plan.to_json())
    print(f"==> Dynamic stream plan seed={stream_plan.seed} -> {plan_path}")
    print(f"    genres: {[l.genre for l in stream_plan.audio_layers]}")
    print(f"    personas: {[v.persona_id for v in stream_plan.vocals]}")

    print(f"==> Building diverse AI soundtrack ({DURATION_SEC:.0f}s) — modular plan + sung lyrics")
    master_pcm, _ = await compose_diverse_soundtrack(
        DURATION_SEC,
        symbol=SYMBOL,
        coin_name=COIN_NAME,
        mint=MINT,
        preferred_style=MUSIC_STYLE,
        plan=stream_plan,
    )
    audio_raw = Path(tempfile.mktemp(suffix=".wav"))
    audio_norm = Path(tempfile.mktemp(suffix="_norm.wav"))
    _write_stereo_wav(audio_raw, master_pcm)
    print("==> Loudnorm to -14 LUFS")
    loudnorm_audio(audio_raw, audio_norm)
    audio_raw.unlink(missing_ok=True)

    state = TokenState(symbol=SYMBOL, mint=MINT, market_cap_usd=42_000)
    compositor = CinemaCompositor(state, WIDTH, HEIGHT, FPS)
    await compositor.init_flux()

    samples_per_frame = SAMPLE_RATE // FPS
    total_frames = int(DURATION_SEC * FPS)
    video_only = Path(tempfile.mktemp(suffix="_video.mp4"))
    ffmpeg = os.environ.get("FFMPEG_PATH", "ffmpeg")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        str(video_only),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    events_task = asyncio.create_task(_schedule_live_events(compositor))
    frame_interval = 1.0 / FPS
    next_frame = time.perf_counter()
    start_mcap = 42_000.0
    pcm_offset = 0

    try:
        for i in range(total_frames):
            t = i / FPS
            state.market_cap_usd = start_mcap + t * 950
            if t >= 82:
                state.market_cap_usd = max(state.market_cap_usd, 241_000)
                state.is_koth = True
            state.bonding_progress = min(state.market_cap_usd / 69_000.0, 1.0)
            state.price_usd = 0.000042 + t * 0.0000008
            compositor.update_state(state)

            # Slice pre-rendered soundtrack (mono int16) per frame
            end = min(pcm_offset + samples_per_frame, len(master_pcm))
            chunk = master_pcm[pcm_offset:end]
            if len(chunk) < samples_per_frame:
                chunk = np.pad(chunk, (0, samples_per_frame - len(chunk)))
            pcm_offset = end
            compositor.update_mouth(chunk)

            rgb = compositor.render()
            proc.stdin.write(rgb.tobytes())

            if i % (FPS * 30) == 0:
                print(f"  frame {i}/{total_frames} mcap=${state.market_cap_usd:,.0f}")

            next_frame += frame_interval
            sleep = next_frame - time.perf_counter()
            if sleep > 0:
                await asyncio.sleep(sleep)
            else:
                next_frame = time.perf_counter()
    finally:
        proc.stdin.close()
        events_task.cancel()
        if proc.wait(timeout=900) != 0:
            raise RuntimeError("ffmpeg video encode failed")

    print("==> Muxing stereo audio + video")
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-i", str(video_only), "-i", str(audio_norm),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart", str(OUT_PATH),
        ],
        check=True, timeout=300,
    )
    video_only.unlink(missing_ok=True)
    audio_norm.unlink(missing_ok=True)

    mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"RECORDED {OUT_PATH} ({mb:.1f} MB)")
    return OUT_PATH


def _telegram_video_path(video: Path) -> Path:
    """Telegram bot limit is 50MB — compress if needed (205s @ 720p can be ~70MB)."""
    max_bytes = 48 * 1024 * 1024
    if video.stat().st_size <= max_bytes:
        return video
    out = video.with_name(f"{video.stem}-telegram.mp4")
    ffmpeg = os.environ.get("FFMPEG_PATH", "ffmpeg")
    print(f"Compressing {video.stat().st_size / 1024 / 1024:.1f} MB for Telegram upload...")
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-i", str(video),
            "-c:v", "libx264", "-crf", "28", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(out),
        ],
        check=True, timeout=600,
    )
    print(f"Compressed to {out.stat().st_size / 1024 / 1024:.1f} MB")
    return out


def send_telegram(video: Path) -> None:
    token = (
        os.environ.get("TELEGRAM_OPS_BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
    )
    chat = (
        os.environ.get("TELEGRAM_OPS_ADMIN_CHAT_ID")
        or os.environ.get("TELEGRAM_GROUP_CHAT_ID")
    )
    if not token or not chat:
        print("Telegram credentials missing — video saved locally only")
        return
    if not video.is_file() or video.stat().st_size < 10_000:
        raise RuntimeError(f"Video too small or missing: {video}")
    import urllib.request
    import urllib.parse

    upload = _telegram_video_path(video)
    msg = (
        f"🎬 RunPod GPU Live Sample — {DURATION_SEC:.0f}s\n"
        f"Diverse AI songs + sung {SYMBOL} lyrics + photoreal scenes + live HUD\n"
        f"(NOT the old single-beat loop — full song_composer pipeline)"
    )
    urllib.request.urlopen(
        urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode(),
        )
    )
    proc = subprocess.run(
        [
            "curl", "-fsS", "-X", "POST", f"https://api.telegram.org/bot{token}/sendVideo",
            "-F", f"chat_id={chat}",
            "-F", f"video=@{upload}",
            "-F", "supports_streaming=true",
            "-F", f"caption=RunPod — {DURATION_SEC:.0f}s diverse songs + AI vocals + photoreal HUD",
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Telegram upload failed: {proc.stderr or proc.stdout}")
    print("Sent to Telegram")


async def main() -> None:
    print(
        f"==> Recording {DURATION_SEC}s — CinemaCompositor + song_composer "
        f"(rotating sections, AI vocals, celebration songs)"
    )
    path = await record()
    send_telegram(path)
    Path("/tmp/runpod_job_complete").write_text(str(path))


if __name__ == "__main__":
    asyncio.run(main())
