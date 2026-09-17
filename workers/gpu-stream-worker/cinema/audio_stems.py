"""Pleasant chord-based background stems for cinema mode (replaces harsh procedural loops)."""

from __future__ import annotations

import logging
from pathlib import Path

from cinema.audio_composer import _render_celebration_bed, _render_lofi_bed

log = logging.getLogger("cinema.audio_stems")

STEMS_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio" / "cinema_stems"
CELEBRATION_PATH = STEMS_DIR / "celebration_anthem.wav"


def _write_wav(path: Path, pcm) -> None:
    import wave
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(pcm.astype(np.int16).tobytes())


def ensure_cinema_stems() -> list[Path]:
    """Return royalty-free bg mp3 when bundled; else generate pleasant lo-fi stems."""
    STEMS_DIR.mkdir(parents=True, exist_ok=True)
    bg_mp3 = STEMS_DIR / "bg_lofi.mp3"
    if bg_mp3.exists():
        return [bg_mp3]
    stems: list[Path] = []
    moods = [
        ("lofi_lake", 130, 45.0),
        ("lofi_violet", 98, 48.0),
        ("lofi_mint", 165, 42.0),
        ("lofi_pink", 110, 50.0),
    ]
    for name, _freq, dur in moods:
        path = STEMS_DIR / f"{name}.wav"
        if not path.exists():
            import numpy as np

            bed = _render_lofi_bed(dur)
            peak = np.max(np.abs(bed))
            if peak > 0:
                bed = bed / peak * 0.85
            pcm = (bed * 32767 * 0.55).astype(np.int16)
            _write_wav(path, pcm)
            log.info("Wrote cinema stem %s", path.name)
        stems.append(path)

    if not CELEBRATION_PATH.exists():
        import numpy as np

        celeb = _render_celebration_bed(32.0)
        peak = np.max(np.abs(celeb))
        if peak > 0:
            celeb = celeb / peak * 0.9
        pcm = (celeb * 32767).astype(np.int16)
        _write_wav(CELEBRATION_PATH, pcm)
        log.info("Wrote celebration anthem")

    return stems


def celebration_anthem_path() -> Path:
    ensure_cinema_stems()
    return CELEBRATION_PATH
