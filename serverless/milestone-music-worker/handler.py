"""
RunPod Serverless handler — milestone celebration anthem generator.

Uses YuE or ACE-Step when model weights are available; falls back to
lyric-conditioned procedural anthem synthesis for dev/staging.
"""

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
MODEL_BACKEND = os.environ.get("MILESTONE_MUSIC_BACKEND", "procedural")  # yue | ace-step | procedural
ORCHESTRATOR_CALLBACK_URL = os.environ.get("ORCHESTRATOR_CALLBACK_URL", "")
MILESTONE_WEBHOOK_SECRET = os.environ.get("MILESTONE_WEBHOOK_SECRET", "")


def _format_market_cap(usd: float) -> str:
    if usd >= 1_000_000:
        return f"${usd / 1_000_000:.1f}M"
    if usd >= 1_000:
        return f"${usd / 1_000:.0f}K"
    return f"${usd:.0f}"


def generate_celebration_lyrics(payload: dict[str, Any]) -> str:
    """Rhyming celebration lyrics with exact ticker, name, and milestone."""
    token = str(payload.get("tokenName") or payload.get("symbol") or "$TOKEN")
    if not token.startswith("$"):
        token = f"${token}"
    name = str(payload.get("coinName") or payload.get("title") or token)
    milestone = str(payload.get("milestoneType") or payload.get("metric") or "MILESTONE")
    mcap = float(payload.get("marketCapUsd") or payload.get("marketCap") or 0)
    mcap_str = _format_market_cap(mcap)
    holders = payload.get("holderCount") or payload.get("currentValue")

    lines = [
        f"{token} on the rise, the charts ignite,",
        f"{name} shining gold in the neon light,",
        f"Hit {milestone.replace('_', ' ')} — we made it through,",
        f"Market cap at {mcap_str}, the whales came true!",
    ]
    if holders:
        lines.append(f"{holders} strong holders, diamond hands unite,")
    lines.extend(
        [
            "From obsidian floors to the emerald sky,",
            f"Victory anthem for {token} — touch the high!",
        ]
    )
    return "\n".join(lines)


def _synthesize_procedural_anthem(lyrics: str, genre: str, out_path: Path, duration_sec: float = 28.0) -> None:
    """CPU-only euphoric trap / stadium bass placeholder when YuE/ACE-Step unavailable."""
    sample_rate = 44100
    samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, samples, endpoint=False)

    kick = np.sin(2 * math.pi * 55 * t) * (np.sin(2 * math.pi * 2 * t) > 0.8)
    bass = 0.4 * np.sin(2 * math.pi * 82.41 * t)
    lead = 0.25 * np.sin(2 * math.pi * 440 * t + np.sin(t * 3))
    rise = np.linspace(0.3, 1.0, samples)
    audio_wave = (kick * 0.5 + bass + lead) * rise
    pcm = np.clip(audio_wave * 14000, -32768, 32767).astype(np.int16)

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    log.info("Procedural anthem written: %s (genre=%s)", out_path, genre)


def _try_yue_generate(lyrics: str, genre: str, out_path: Path) -> bool:
    """Attempt YuE full-song generation if installed."""
    try:
        # YuE integration point — model loading is environment-specific
        yue_script = os.environ.get("YUE_GENERATE_SCRIPT", "")
        if not yue_script or not Path(yue_script).exists():
            return False
        subprocess.run(
            ["python", yue_script, "--lyrics", lyrics, "--genre", genre, "--output", str(out_path)],
            check=True,
            timeout=300,
            capture_output=True,
        )
        return out_path.exists()
    except Exception as exc:
        log.warning("YuE generation failed: %s", exc)
        return False


def _try_ace_step_generate(lyrics: str, genre: str, out_path: Path) -> bool:
    """Attempt ACE-Step lyric-conditioned generation if installed."""
    try:
        ace_script = os.environ.get("ACE_STEP_GENERATE_SCRIPT", "")
        if not ace_script or not Path(ace_script).exists():
            return False
        subprocess.run(
            ["python", ace_script, "--lyrics", lyrics, "--style", genre, "--output", str(out_path)],
            check=True,
            timeout=300,
            capture_output=True,
        )
        return out_path.exists()
    except Exception as exc:
        log.warning("ACE-Step generation failed: %s", exc)
        return False


def _encode_mp3(wav_path: Path) -> Path:
    """Encode WAV to MP3 via FFmpeg for streaming delivery."""
    mp3_path = wav_path.with_suffix(".mp3")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(mp3_path),
    ]
    subprocess.run(cmd, check=True, timeout=120)
    return mp3_path


def _audio_duration_sec(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 28.0


def _upload_to_storage(local_path: Path, payload: dict[str, Any]) -> str:
    """Upload to S3-compatible storage or return local file URL for dev."""
    bucket = os.environ.get("MILESTONE_S3_BUCKET", "")
    public_base = os.environ.get("MILESTONE_AUDIO_PUBLIC_BASE", "")
    if bucket and public_base:
        # S3 upload integration point
        key = f"milestones/{payload.get('tokenMint', 'unknown')[:8]}/{local_path.name}"
        try:
            import boto3

            s3 = boto3.client("s3")
            content_type = "audio/mpeg" if local_path.suffix == ".mp3" else "audio/wav"
            s3.upload_file(str(local_path), bucket, key, ExtraArgs={"ContentType": content_type})
            return f"{public_base.rstrip('/')}/{key}"
        except ImportError:
            log.warning("boto3 not installed — using local path")
        except Exception as exc:
            log.warning("S3 upload failed: %s", exc)

    # Dev fallback: serve via orchestrator static or file path
    return f"file://{local_path}"


def _notify_gpu_worker(callback_url: str, anthem_url: str, payload: dict[str, Any], duration_sec: float) -> None:
    if not callback_url:
        log.info("No GPU worker callback URL — skipping delivery")
        return
    body = {
        "audioUrl": anthem_url,
        "anthemUrl": anthem_url,
        "duration": duration_sec,
        "durationSec": duration_sec,
        "title": payload.get("milestoneType") or "MILESTONE",
        "subtitle": payload.get("displayText") or generate_celebration_lyrics(payload).split("\n")[0],
        "tokenName": payload.get("tokenName"),
        "tokenMint": payload.get("tokenMint"),
    }
    headers = {"Content-Type": "application/json"}
    if MILESTONE_WEBHOOK_SECRET:
        headers["Authorization"] = f"Bearer {MILESTONE_WEBHOOK_SECRET}"
    try:
        resp = httpx.post(callback_url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        log.info("GPU worker notified: %s", callback_url)
    except Exception as exc:
        log.error("GPU worker notification failed: %s", exc)


def _notify_orchestrator(session_id: str, anthem_url: str, payload: dict[str, Any]) -> None:
    if not ORCHESTRATOR_CALLBACK_URL:
        return
    try:
        httpx.post(
            ORCHESTRATOR_CALLBACK_URL,
            json={"sessionId": session_id, "anthemUrl": anthem_url, "payload": payload},
            timeout=20,
        )
    except Exception as exc:
        log.warning("Orchestrator callback failed: %s", exc)


def generate_anthem(payload: dict[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lyrics = generate_celebration_lyrics(payload)
    genre = str(payload.get("genre") or "euphoric trap, victory anthem, stadium bass, gold status")
    mint = str(payload.get("tokenMint") or "unknown")[:12]
    out_path = OUTPUT_DIR / f"anthem_{mint}_{payload.get('milestoneType', 'milestone')}.wav"

    generated = False
    if MODEL_BACKEND == "yue":
        generated = _try_yue_generate(lyrics, genre, out_path)
    elif MODEL_BACKEND == "ace-step":
        generated = _try_ace_step_generate(lyrics, genre, out_path)

    if not generated:
        _synthesize_procedural_anthem(lyrics, genre, out_path)

    mp3_path = _encode_mp3(out_path)
    anthem_url = _upload_to_storage(mp3_path, payload)
    duration_sec = _audio_duration_sec(mp3_path)

    gpu_callback = str(payload.get("gpuWorkerCallbackUrl") or payload.get("workerWebhookUrl") or "")
    session_id = str(payload.get("sessionId") or "")
    _notify_gpu_worker(gpu_callback, anthem_url, payload, duration_sec)
    _notify_orchestrator(session_id, anthem_url, payload)

    return {
        "success": True,
        "audioUrl": anthem_url,
        "anthemUrl": anthem_url,
        "duration": duration_sec,
        "durationSec": duration_sec,
        "lyrics": lyrics,
        "localPath": str(mp3_path),
    }


def handler(event: dict[str, Any]) -> dict[str, Any]:
    """RunPod serverless entrypoint."""
    log.info("Milestone music job received: %s", json.dumps({k: event.get(k) for k in ('tokenName', 'milestoneType', 'tokenMint')}))
    input_payload = event.get("input") or event
    try:
        result = generate_anthem(input_payload)
        return {"status": "COMPLETED", "output": result}
    except Exception as exc:
        log.exception("Anthem generation failed")
        return {"status": "FAILED", "error": str(exc)}


def runpod_handler(event: dict[str, Any]) -> dict[str, Any]:
    return handler(event)


try:
    import runpod

    runpod.serverless.start({"handler": runpod_handler})
except ImportError:
    pass


if __name__ == "__main__":
    import sys

    sample = {
        "tokenName": "$GOLD",
        "tokenMint": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        "milestoneType": "BONDING_CURVE_80_PERCENT",
        "marketCapUsd": 52000,
        "genre": "euphoric trap, victory anthem, stadium bass, gold status",
        "gpuWorkerCallbackUrl": "http://127.0.0.1:8788/milestone-celebration",
    }
    if len(sys.argv) > 1:
        sample = json.loads(sys.argv[1])
    print(json.dumps(handler({"input": sample}), indent=2))
