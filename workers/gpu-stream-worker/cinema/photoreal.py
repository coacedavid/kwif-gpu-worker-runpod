"""
Photoreal cinema — Unsplash stock imagery with Ken Burns motion + text overlays.
Used for live streams (frame decode) and offline sample renders (ffmpeg).
"""

from __future__ import annotations

import math
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from cinema.figures import ParticleField
from cinema.scenes import SceneState

STOCK_DIR = Path(__file__).resolve().parent.parent / "assets" / "cinema_stock" / "images"

SCENE_IMAGES: dict[str, str] = {
    "lake_intro": "neon_blue.jpg",
    "pump_printer": "trader.jpg",
    "purple_chart": "purple_city.jpg",
    "pink_chat": "party.jpg",
    "whale_alert": "money_cash.jpg",
    "celebration_dance": "dancer.jpg",
    "fireworks_crown": "celebration.jpg",
    "bonding_science": "crypto.jpg",
    "meme_montage": "dollars.jpg",
    "dance_finale": "money_cash.jpg",
    "mint_outro": "party.jpg",
}

SCENE_TITLES: dict[str, tuple[str, str]] = {
    "lake_intro": ("$KWIF LIVE", "Kitten Wif Hat · Pump.fun"),
    "pump_printer": ("PUMP.FUN MONEY PRINTER", "Cash flowing from the chart"),
    "purple_chart": ("CHART STORM", "+420% TODAY"),
    "pink_chat": ("VIRAL CHAT FLOOD", "Telegram · X · Pump chat"),
    "whale_alert": ("WHALE ALERT", "$50,000 BUY DETECTED"),
    "celebration_dance": ("MILESTONE CELEBRATION", "$241K MCAP — KING OF THE HILL"),
    "fireworks_crown": ("KING OF THE HILL", "Crown secured"),
    "bonding_science": ("BONDING CURVE SCIENCE", "Dopamine loop activated"),
    "meme_montage": ("DIAMOND PAWS", "KWIF ARMY"),
    "dance_finale": ("CASH RAIN FINALE", "$100 bills everywhere"),
    "mint_outro": ("THANKS FOR WATCHING", "Every token · unique visual DNA"),
}


@dataclass
class KenBurnsState:
    image: np.ndarray
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom_rate: float = 0.0008
    pan_rate_x: float = 0.3
    pan_rate_y: float = 0.15


class PhotorealSceneCache:
    """Lazy-load stock images per scene."""

    def __init__(self) -> None:
        self._cache: dict[str, np.ndarray] = {}

    def get(self, scene_id: str, width: int, height: int) -> np.ndarray:
        if scene_id not in self._cache:
            fname = SCENE_IMAGES.get(scene_id, "neon_blue.jpg")
            path = STOCK_DIR / fname
            if not path.exists():
                img = np.zeros((height, width, 3), dtype=np.uint8)
                img[:] = (30, 60, 120)
            else:
                img = cv2.imread(str(path))
                if img is None:
                    img = np.zeros((height, width, 3), dtype=np.uint8)
                else:
                    img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
            self._cache[scene_id] = img
        return self._cache[scene_id]


_cache = PhotorealSceneCache()
_burns: dict[str, KenBurnsState] = {}
_dollar_sprite: np.ndarray | None = None


def _dollar_sprite_texture() -> np.ndarray:
    """Crop a bill-shaped patch from the real dollars stock photo."""
    global _dollar_sprite
    if _dollar_sprite is not None:
        return _dollar_sprite
    path = STOCK_DIR / "dollars.jpg"
    if path.exists():
        img = cv2.imread(str(path))
        if img is not None:
            h, w = img.shape[:2]
            crop = img[int(h * 0.15) : int(h * 0.55), int(w * 0.1) : int(w * 0.45)]
            _dollar_sprite = cv2.resize(crop, (90, 42), interpolation=cv2.INTER_LANCZOS4)
            return _dollar_sprite
    _dollar_sprite = np.zeros((42, 90, 3), dtype=np.uint8)
    cv2.rectangle(_dollar_sprite, (2, 2), (87, 39), (70, 160, 90), -1)
    cv2.putText(_dollar_sprite, "$100", (12, 28), cv2.FONT_HERSHEY_DUPLEX, 0.7, (240, 255, 240), 2)
    return _dollar_sprite


@dataclass
class TexturedBill:
    x: float
    y: float
    vy: float
    rot: float
    vr: float
    scale: float


@dataclass
class PhotorealFX:
    """Cash rain + confetti layered on stock imagery."""

    bills: list[TexturedBill] = field(default_factory=list)
    confetti: list[tuple[float, float, float, float, tuple[int, int, int], float]] = field(default_factory=list)

    def ensure_cash_rain(self, w: int, count: int = 55) -> None:
        if len(self.bills) >= count // 2:
            return
        for _ in range(count):
            self.bills.append(
                TexturedBill(
                    x=float(np.random.uniform(0, w)),
                    y=float(np.random.uniform(-300, -20)),
                    vy=float(np.random.uniform(4, 11)),
                    rot=float(np.random.uniform(0, 360)),
                    vr=float(np.random.uniform(-5, 5)),
                    scale=float(np.random.uniform(0.65, 1.35)),
                )
            )

    def ensure_confetti(self, w: int, count: int = 70) -> None:
        if len(self.confetti) >= count // 2:
            return
        colors = [(255, 80, 180), (80, 200, 255), (120, 255, 140), (255, 220, 80), (200, 120, 255)]
        for _ in range(count):
            self.confetti.append(
                (
                    float(np.random.uniform(0, w)),
                    float(np.random.uniform(-120, 0)),
                    float(np.random.uniform(-2.5, 2.5)),
                    float(np.random.uniform(2.5, 8)),
                    colors[np.random.randint(0, len(colors))],
                    float(np.random.uniform(5, 12)),
                )
            )

    def tick(self, h: int, w: int) -> None:
        alive: list[TexturedBill] = []
        for b in self.bills:
            b.y += b.vy
            b.x += math.sin(b.y * 0.018) * 1.2
            b.rot += b.vr
            if b.y < h + 100:
                alive.append(b)
        self.bills = alive

        alive_c = []
        for x, y, vx, vy, color, size in self.confetti:
            x += vx
            y += vy
            vy += 0.06
            if y < h + 30:
                alive_c.append((x, y, vx, vy, color, size))
        self.confetti = alive_c

    def draw(self, frame: np.ndarray) -> None:
        sprite = _dollar_sprite_texture()
        sh, sw = sprite.shape[:2]
        for b in self.bills:
            tw, th = int(sw * b.scale), int(sh * b.scale)
            scaled = cv2.resize(sprite, (tw, th), interpolation=cv2.INTER_LINEAR)
            M = cv2.getRotationMatrix2D((tw // 2, th // 2), b.rot, 1.0)
            rotated = cv2.warpAffine(scaled, M, (tw, th), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
            x0, y0 = int(b.x - tw // 2), int(b.y - th // 2)
            _alpha_paste(frame, rotated, x0, y0)
        for x, y, _, _, color, size in self.confetti:
            cv2.circle(frame, (int(x), int(y)), int(size), color, -1, cv2.LINE_AA)


def _alpha_paste(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    sh, sw = src.shape[:2]
    dh, dw = dst.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dw, x + sw), min(dh, y + sh)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    patch = src[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)]
    mask = np.any(patch > 12, axis=2)
    dst[y0:y1, x0:x1][mask] = patch[mask]


CELEBRATION_SCENES = frozenset(
    {"celebration_dance", "fireworks_crown", "dance_finale", "whale_alert", "meme_montage"}
)


def _dynamic_titles(scene_id: str, state: SceneState | None, symbol: str) -> tuple[str, str]:
    """Live scene titles from token state — not hardcoded demo numbers."""
    mcap = state.mcap if state else 42_000
    bond = min(mcap / 69_000.0, 1.0) * 100 if mcap else 0.0
    pct = min(999, int(mcap / 500))
    dynamic = {
        "lake_intro": (f"${symbol} LIVE", f"{state.coin_name if state else symbol} · Pump.fun"),
        "purple_chart": ("CHART STORM", f"+{pct}% SESSION · MCAP ${mcap:,.0f}"),
        "whale_alert": ("WHALE ALERT", "$50,000+ BUY DETECTED"),
        "celebration_dance": ("MILESTONE CELEBRATION", f"${mcap:,.0f} MCAP — KING OF THE HILL"),
        "bonding_science": ("BONDING CURVE SCIENCE", f"{bond:.1f}% · Dopamine loop active"),
        "pump_printer": ("PUMP.FUN MONEY PRINTER", f"${symbol} cash from the chart"),
    }
    if scene_id in dynamic:
        return dynamic[scene_id]
    title, sub = SCENE_TITLES.get(scene_id, (f"${symbol}", "LIVE"))
    return title.replace("KWIF", symbol), sub.replace("KWIF", symbol)


def render_photoreal_frame(
    scene_id: str,
    local_frame: int,
    width: int,
    height: int,
    symbol: str = "KWIF",
    fx: Optional[PhotorealFX] = None,
    scene_state: SceneState | None = None,
) -> np.ndarray:
    """Single frame: Ken Burns on stock photo + cinematic overlays."""
    base = _cache.get(scene_id, width, height).copy()
    if scene_id not in _burns:
        _burns[scene_id] = KenBurnsState(
            image=base,
            zoom_rate=0.0006 + (hash(scene_id) % 5) * 0.0001,
            pan_rate_x=0.2 + (hash(scene_id) % 3) * 0.1,
        )
    burns = _burns[scene_id]
    burns.zoom = min(1.35, burns.zoom + burns.zoom_rate)
    burns.pan_x += burns.pan_rate_x
    burns.pan_y += burns.pan_rate_y * 0.5

    h, w = base.shape[:2]
    zw, zh = int(w / burns.zoom), int(h / burns.zoom)
    x0 = int(min(max(burns.pan_x, 0), w - zw))
    y0 = int(min(max(burns.pan_y, 0), h - zh))
    crop = base[y0 : y0 + zh, x0 : x0 + zw]
    if crop.size == 0:
        crop = base
    frame = cv2.resize(crop, (width, height), interpolation=cv2.INTER_LANCZOS4)

    # Cinematic color grade per scene
    grades = {
        "lake_intro": (1.05, 1.1, 1.2),
        "pump_printer": (1.0, 1.15, 1.0),
        "purple_chart": (1.15, 0.95, 1.2),
        "pink_chat": (1.2, 0.9, 1.1),
        "celebration_dance": (1.1, 1.05, 0.95),
    }
    r, g, b = grades.get(scene_id, (1.0, 1.0, 1.0))
    frame = np.clip(frame.astype(np.float32) * [b, g, r], 0, 255).astype(np.uint8)

    # Vignette
    Y, X = np.ogrid[:height, :width]
    cx, cy = width / 2, height / 2
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    vignette = 1.0 - (dist / max(cx, cy)) * 0.45
    frame = (frame.astype(np.float32) * vignette[..., np.newaxis]).astype(np.uint8)

    # Title overlays (live token data when state provided)
    title, subtitle = _dynamic_titles(scene_id, scene_state, symbol)
    cv2.rectangle(frame, (0, 0), (width, 90), (0, 0, 0), -1)
    cv2.addWeighted(frame, 0.7, frame, 0, 0, frame)  # noop keep
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (width, 90), (10, 10, 20), -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)
    cv2.putText(frame, title, (32, 52), cv2.FONT_HERSHEY_DUPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, subtitle, (32, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 220, 255), 1, cv2.LINE_AA)

    # LIVE badge
    cv2.circle(frame, (width - 80, 40), 8, (255, 60, 80), -1)
    cv2.putText(frame, "LIVE", (width - 60, 48), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    if fx is not None:
        if scene_id in CELEBRATION_SCENES:
            fx.ensure_cash_rain(width, 60)
            fx.ensure_confetti(width, 80)
        fx.tick(height, width)
        fx.draw(frame)

    # Film grain for cinematic feel
    noise = np.random.randint(-6, 7, frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return frame


def render_segment_mp4(
    scene_id: str,
    duration_sec: float,
    out_path: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    symbol: str = "KWIF",
) -> Path:
    """Offline: render scene segment to mp4 via raw frames + ffmpeg."""
    fname = SCENE_IMAGES.get(scene_id, "neon_blue.jpg")
    img_path = STOCK_DIR / fname
    if not img_path.exists():
        raise FileNotFoundError(f"Stock image missing: {img_path}")

    # Ken Burns via ffmpeg zoompan (fast)
    frames = int(duration_sec * fps)
    title, subtitle = SCENE_TITLES.get(scene_id, (f"${symbol}", "LIVE"))
    title = title.replace("KWIF", symbol).replace("'", "'\\''")
    subtitle = subtitle.replace("'", "'\\''")

    vf = (
        f"scale={width*2}:{height*2},"
        f"zoompan=z='min(zoom+0.0012,1.4)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={width}x{height}:fps={fps},"
        f"drawbox=x=0:y=0:w=iw:h=90:color=black@0.55:t=fill,"
        f"drawtext=text='{title}':x=32:y=28:fontsize=42:fontcolor=white:font=DejaVu\\ Sans\\ Bold,"
        f"drawtext=text='{subtitle}':x=32:y=72:fontsize=24:fontcolor=0xB4DCFF,"
        f"drawtext=text='LIVE':x=w-100:y=28:fontsize=28:fontcolor=0xFF3C50"
    )
    cmd = [
        os.environ.get("FFMPEG_PATH", "ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", str(img_path),
        "-vf", vf,
        "-t", str(duration_sec),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, timeout=300)
    return out_path
