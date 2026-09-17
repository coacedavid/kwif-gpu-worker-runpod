#!/usr/bin/env python3
"""
Record a sample video using the SAME code path as the live GPU stream worker:
  CinemaCompositor.render() + AudioEngine.get_mixed_frame() + milestone ducking.

No RTMP — writes MP4 via ffmpeg. Intended to run ON a RunPod GPU pod.
"""

from __future__ import annotations

import asyncio
import json
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

from audio_engine import AudioEngine
from cinema_compositor import CinemaCompositor
from visual_compositor import TokenState

WIDTH = int(os.environ.get("WIDTH", "1280"))
HEIGHT = int(os.environ.get("HEIGHT", "720"))
FPS = int(os.environ.get("FPS", "30"))
DURATION_SEC = float(os.environ.get("RECORD_DURATION_SEC", "205"))
SAMPLE_RATE = 44100
OUT_PATH = Path(os.environ.get("OUTPUT_MP4", "/tmp/runpod-live-sample.mp4"))
SYMBOL = os.environ.get("TOKEN_SYMBOL", "KWIF")
MINT = os.environ.get("TOKEN_MINT", "demo-kwif-mint-runpod")


def _generate_milestone_anthem() -> str:
    handler = Path(__file__).resolve().parent.parent / "serverless" / "milestone-music-worker" / "handler.py"
    payload = {
        "tokenName": SYMBOL,
        "tokenMint": MINT,
        "coinName": "Kitten Wif Hat",
        "milestoneType": "MCAP_241K",
        "marketCapUsd": 241_000,
    }
    proc = subprocess.run(
        [sys.executable, str(handler), json.dumps(payload)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "milestone handler failed")
    start = proc.stdout.rfind("{")
    data = json.loads(proc.stdout[start:])
    out = data.get("output") or data
    return out.get("localPath") or out.get("audioUrl", "").replace("file://", "")


async def _schedule_live_events(compositor: CinemaCompositor, audio: AudioEngine) -> None:
    """Simulate whale buy, milestones, and chat feedback during recording."""
    await asyncio.sleep(25)
    compositor.add_chat_notification("trader99: can't see the mcap numbers??")
    compositor.set_caption("Chat asked for numbers — live HUD activated!")

    await asyncio.sleep(45)  # ~70s
    compositor.set_alert("🐋 WHALE BUY — $52,400 DETECTED", duration=14)
    compositor._director.trigger("whale")

    await asyncio.sleep(12)  # ~82s
    compositor.trigger_milestone("MILESTONE — $241K MCAP", "Celebration anthem playing!", duration=26)
    compositor._director.trigger("milestone", duration_sec=28)
    try:
        anthem = _generate_milestone_anthem()
        await audio.duck_for_celebration(f"file://{anthem}", duration_sec=28)
    except Exception as exc:
        print(f"milestone anthem fallback: {exc}")

    await asyncio.sleep(56)  # ~138s
    compositor.trigger_milestone("SECOND MILESTONE", "Cash rain — new celebration song!", duration=20)
    compositor._director.trigger("milestone", duration_sec=24)
    try:
        anthem = _generate_milestone_anthem()
        await audio.duck_for_celebration(f"file://{anthem}", duration_sec=24)
    except Exception as exc:
        print(f"milestone 2 fallback: {exc}")

    await asyncio.sleep(30)
    compositor.add_chat_notification("kwif_army: LOVE this celebration song!!")
    compositor.set_caption("Chat loves the vibe — playing more hype tracks!")


async def record() -> Path:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = TokenState(symbol=SYMBOL, mint=MINT, market_cap_usd=42_000)
    compositor = CinemaCompositor(state, WIDTH, HEIGHT, FPS)
    audio_engine = AudioEngine(SAMPLE_RATE)
    await audio_engine.start()
    await compositor.init_flux()

    samples_per_frame = SAMPLE_RATE // FPS
    video_only = Path(tempfile.mktemp(suffix="_video.mp4"))
    audio_pcm: list[np.ndarray] = []
    ffmpeg = os.environ.get("FFMPEG_PATH", "ffmpeg")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        str(video_only),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    events_task = asyncio.create_task(_schedule_live_events(compositor, audio_engine))
    total_frames = int(DURATION_SEC * FPS)
    frame_interval = 1.0 / FPS
    next_frame = time.perf_counter()
    start_mcap = 42_000.0

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

            audio_out = audio_engine.get_mixed_frame(samples_per_frame, None)
            audio_pcm.append(audio_out)
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
        try:
            events_task.cancel()
        except Exception:
            pass
        if proc.wait(timeout=900) != 0:
            raise RuntimeError("ffmpeg video encode failed")

    audio_wav = Path(tempfile.mktemp(suffix=".wav"))
    pcm = np.concatenate(audio_pcm)
    with wave.open(str(audio_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())

    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
            "-i", str(video_only), "-i", str(audio_wav),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-shortest", "-movflags", "+faststart", str(OUT_PATH),
        ],
        check=True, timeout=300,
    )
    video_only.unlink(missing_ok=True)
    audio_wav.unlink(missing_ok=True)

    mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"RECORDED {OUT_PATH} ({mb:.1f} MB)")
    return OUT_PATH


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

    msg = (
        "🎬 RunPod GPU Live Sample — REAL worker code path\n"
        "CinemaCompositor + AudioEngine + milestone ducking on RunPod GPU"
    )
    urllib.request.urlopen(
        urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode(),
        )
    )
    # curl is more reliable for large video upload
    subprocess.run(
        [
            "curl", "-fsS", "-X", "POST", f"https://api.telegram.org/bot{token}/sendVideo",
            "-F", f"chat_id={chat}",
            "-F", f"video=@{video}",
            "-F", "supports_streaming=true",
            "-F", "caption=RunPod GPU — real CinemaCompositor + AudioEngine live sample",
        ],
        check=True,
        timeout=300,
    )
    print("Sent to Telegram")


async def main() -> None:
    print(f"==> Recording {DURATION_SEC}s on GPU using live worker compositor + audio engine")
    path = await record()
    send_telegram(path)
    Path("/tmp/runpod_job_complete").write_text(str(path))


if __name__ == "__main__":
    asyncio.run(main())
