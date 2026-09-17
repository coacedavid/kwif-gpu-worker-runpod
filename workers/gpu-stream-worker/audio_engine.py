"""
24/7 background audio orchestrator with celebration ducking.

Runs entirely on CPU — zero GPU VRAM. Mixes continuous wealth-building stems
with programmatic volume ducking when milestone celebration anthems arrive.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

log = logging.getLogger("audio_engine")

STEMS_DIR = Path(__file__).resolve().parent / "assets" / "audio" / "background_stems"
DUCK_TARGET = 0.12
DUCK_RAMP_SEC = 1.5
RESTORE_RAMP_SEC = 2.0
BACKGROUND_VOLUME = 0.22
COMMENTARY_GAIN = 1.0
MIN_STEM_SAMPLES = 44100  # at least 1s of audio per stem
STEM_CROSSFADE_SAMPLES = 2205  # ~50ms at 44.1kHz for seamless rotation
STEM_SILENCE_RMS = 8.0


def _cinema_mode_enabled() -> bool:
    return os.environ.get("ENABLE_CINEMA_MODE", "1").strip().lower() in ("1", "true", "yes")


def _ensure_stems() -> list[Path]:
    """Return available stem files; generate procedural placeholders if none exist."""
    if _cinema_mode_enabled():
        try:
            from cinema.audio_stems import ensure_cinema_stems

            cinema = ensure_cinema_stems()
            if cinema:
                log.info("Cinema mode: loaded %d pleasant chord stems", len(cinema))
                return cinema
        except Exception as exc:
            log.warning("Cinema stems unavailable (%s) — falling back", exc)

    STEMS_DIR.mkdir(parents=True, exist_ok=True)
    stems = sorted(STEMS_DIR.glob("*.wav")) + sorted(STEMS_DIR.glob("*.mp3"))
    if stems:
        return stems

    log.info("No background stems found — generating procedural mood lounge loops")
    mood_stems = [
        (98, "obsidian_pulse"),
        (130, "emerald_drift"),
        (165, "gold_trap"),
        (185, "violet_wave"),
        (210, "teal_steady"),
        (240, "amber_challenge"),
        (155, "crimson_calm"),
        (175, "cyan_cosmic"),
    ]
    for i, (freq, name) in enumerate(mood_stems):
        path = STEMS_DIR / f"{name}.wav"
        if path.exists():
            stems.append(path)
            continue
        _write_procedural_stem(path, base_freq=freq, seed=i)
        stems.append(path)
    return stems


def _write_procedural_stem(path: Path, base_freq: float, seed: int, duration_sec: float = 32.0) -> None:
    """Write a seamless-ish synth loop (synthwave / luxury trap feel) as mono s16le WAV."""
    sample_rate = 44100
    samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, samples, endpoint=False)
    phase = 2 * math.pi * base_freq * t
    # Layered harmonics + slow amplitude envelope for lounge energy
    wave = (
        0.35 * np.sin(phase)
        + 0.2 * np.sin(phase * 2.01 + seed)
        + 0.12 * np.sin(phase * 0.5)
        + 0.08 * np.sin(phase * 3.3 + seed * 0.7)
    )
    envelope = 0.55 + 0.45 * np.sin(2 * math.pi * t / 8.0 + seed)
    pcm = (wave * envelope * 6500).astype(np.int16)

    import wave

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def _decode_audio_to_pcm(path: str, sample_rate: int) -> np.ndarray:
    cmd = [
        os.environ.get("FFMPEG_PATH", "ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        path,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True, timeout=60)
    return np.frombuffer(proc.stdout, dtype=np.int16)


class AudioEngine:
    """Continuous background loop + celebration anthem ducking mixer."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._stems: list[np.ndarray] = []
        self._stem_idx = 0
        self._stem_offset = 0
        self._volume = BACKGROUND_VOLUME
        self._target_volume = BACKGROUND_VOLUME
        self._mood_idx = 0
        self._duck_ramp_samples = int(DUCK_RAMP_SEC * sample_rate)
        self._restore_ramp_samples = int(RESTORE_RAMP_SEC * sample_rate)
        self._ramp_pos = 0
        self._ramping_down = False

        self._celebration_pcm: Optional[np.ndarray] = None
        self._celebration_offset = 0
        self._celebration_active = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        loop = asyncio.get_event_loop()
        stems = _ensure_stems()
        for stem_path in stems:
            try:
                pcm = await loop.run_in_executor(None, _decode_audio_to_pcm, str(stem_path), self.sample_rate)
                if len(pcm) < MIN_STEM_SAMPLES:
                    log.warning("Stem %s too short (%d samples) — skipped", stem_path.name, len(pcm))
                    continue
                rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                if rms < STEM_SILENCE_RMS:
                    log.warning("Stem %s near-silent (rms=%.2f) — skipped", stem_path.name, rms)
                    continue
                self._stems.append(pcm)
                log.info("Loaded background stem: %s (%d samples, rms=%.1f)", stem_path.name, len(pcm), rms)
            except Exception as exc:
                log.warning("Failed to load stem %s: %s", stem_path, exc)

        if not self._stems:
            log.warning("No valid audio stems — generating emergency procedural loop")
            emergency = STEMS_DIR / "_emergency_loop.wav"
            if not emergency.exists():
                _write_procedural_stem(emergency, base_freq=110.0, seed=99, duration_sec=48.0)
            pcm = await loop.run_in_executor(None, _decode_audio_to_pcm, str(emergency), self.sample_rate)
            self._stems.append(pcm)

    def set_mood(self, mood_id: str) -> None:
        """Rotate stem selection based on visual theme mood."""
        if not self._stems:
            return
        key = sum(ord(c) for c in mood_id) % len(self._stems)
        self._mood_idx = key
        self._stem_idx = key
        self._stem_offset = 0

    def _advance_background(self, n: int) -> np.ndarray:
        if not self._stems:
            return np.zeros(n, dtype=np.int16)

        out = np.zeros(n, dtype=np.int32)
        remaining = n
        while remaining > 0:
            stem = self._stems[self._stem_idx]
            available = len(stem) - self._stem_offset
            take = min(remaining, available)
            chunk = stem[self._stem_offset : self._stem_offset + take].astype(np.int32)
            out[n - remaining : n - remaining + take] = chunk
            self._stem_offset += take
            remaining -= take
            if self._stem_offset >= len(stem):
                self._stem_offset = 0
                self._stem_idx = (self._stem_idx + 1) % len(self._stems)
        return np.clip(out, -32768, 32767).astype(np.int16)

    def _update_duck_envelope(self, n: int) -> None:
        if abs(self._volume - self._target_volume) < 0.001:
            self._volume = self._target_volume
            return
        step = n / (self._duck_ramp_samples if self._ramping_down else self._restore_ramp_samples)
        if self._target_volume < self._volume:
            self._volume = max(self._target_volume, self._volume - step)
        else:
            self._volume = min(self._target_volume, self._volume + step)

    def get_mixed_frame(self, n: int, commentary: Optional[np.ndarray] = None) -> np.ndarray:
        """Return n samples of mixed audio: background (ducked) + celebration + commentary."""
        bg = self._advance_background(n)
        self._update_duck_envelope(n)
        mixed = (bg.astype(np.int32) * self._volume).astype(np.int32)

        if self._celebration_active and self._celebration_pcm is not None:
            end = self._celebration_offset + n
            celeb = self._celebration_pcm[self._celebration_offset : end]
            if len(celeb) < n:
                pad = np.zeros(n - len(celeb), dtype=np.int16)
                celeb = np.concatenate([celeb, pad])
                self._celebration_active = False
                self._target_volume = BACKGROUND_VOLUME
                self._ramping_down = False
                log.info("Celebration anthem finished — restoring background volume")
            self._celebration_offset = end
            mixed = mixed + celeb.astype(np.int32)

        if commentary is not None and len(commentary) > 0:
            c = commentary[:n] if len(commentary) >= n else np.pad(commentary, (0, n - len(commentary)))
            mixed = mixed + c.astype(np.int32)

        return np.clip(mixed, -32768, 32767).astype(np.int16)

    async def duck_for_celebration(self, anthem_url: str, duration_sec: float = 30.0) -> None:
        """Download celebration anthem, duck background, and play anthem over the mix."""
        async with self._lock:
            log.info("Ducking background for celebration: %s", anthem_url[:80])
            self._target_volume = BACKGROUND_VOLUME * DUCK_TARGET
            self._ramping_down = True

            tmp_path: Optional[str] = None
            try:
                loop = asyncio.get_event_loop()
                if _cinema_mode_enabled() and not anthem_url.startswith("file://"):
                    try:
                        from cinema.audio_stems import celebration_anthem_path

                        local_celeb = str(celebration_anthem_path())
                        pcm = await loop.run_in_executor(
                            None, _decode_audio_to_pcm, local_celeb, self.sample_rate
                        )
                    except Exception:
                        local_path = anthem_url[7:] if anthem_url.startswith("file://") else anthem_url
                        pcm = await loop.run_in_executor(
                            None, _decode_audio_to_pcm, local_path, self.sample_rate
                        )
                elif anthem_url.startswith("file://"):
                    local_path = anthem_url[7:]
                    pcm = await loop.run_in_executor(
                        None, _decode_audio_to_pcm, local_path, self.sample_rate
                    )
                else:
                    async with httpx.AsyncClient(timeout=120) as client:
                        resp = await client.get(anthem_url)
                        resp.raise_for_status()
                        suffix = ".mp3" if "mpeg" in resp.headers.get("content-type", "") else ".wav"
                        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                            tmp.write(resp.content)
                            tmp_path = tmp.name
                    pcm = await loop.run_in_executor(
                        None, _decode_audio_to_pcm, tmp_path, self.sample_rate
                    )
                max_samples = int(duration_sec * self.sample_rate)
                if len(pcm) > max_samples:
                    pcm = pcm[:max_samples]

                self._celebration_pcm = pcm
                self._celebration_offset = 0
                self._celebration_active = True
                log.info("Celebration anthem loaded (%d samples, ~%.1fs)", len(pcm), len(pcm) / self.sample_rate)
            except Exception as exc:
                log.error("Celebration anthem load failed: %s", exc)
                self._target_volume = BACKGROUND_VOLUME
                self._ramping_down = False
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
