"""Timeline director — stitches scenes with crossfade transitions."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

import os

from .figures import ParticleField
from .hud_overlay import HudContext, LiveStreamHUD
from .photoreal import PhotorealFX, render_photoreal_frame
from .scenes import SCENE_RENDERERS, SceneState


def _use_photoreal() -> bool:
    return os.environ.get("CINEMA_PROCEDURAL", "0").strip().lower() not in ("1", "true", "yes")


_fx = PhotorealFX()
_hud = LiveStreamHUD()
_demo_hud_ctx = HudContext()


@dataclass
class SceneBlock:
    scene_id: str
    start_sec: float
    duration_sec: float


TIMELINE: list[SceneBlock] = [
    SceneBlock("lake_intro", 0, 18),
    SceneBlock("pump_printer", 18, 20),
    SceneBlock("purple_chart", 38, 18),
    SceneBlock("pink_chat", 56, 14),
    SceneBlock("whale_alert", 70, 12),
    SceneBlock("celebration_dance", 82, 26),
    SceneBlock("fireworks_crown", 108, 16),
    SceneBlock("bonding_science", 124, 18),
    SceneBlock("meme_montage", 142, 16),
    SceneBlock("dance_finale", 158, 22),
    SceneBlock("mint_outro", 180, 25),
]

CROSSFADE_FRAMES = 12


def find_scene(t_sec: float) -> tuple[SceneBlock | None, SceneBlock | None, float]:
    """Return current scene, next scene (if crossfading), local time in scene."""
    current: SceneBlock | None = None
    nxt: SceneBlock | None = None
    for i, block in enumerate(TIMELINE):
        end = block.start_sec + block.duration_sec
        if block.start_sec <= t_sec < end:
            current = block
            local = t_sec - block.start_sec
            if end - t_sec < CROSSFADE_FRAMES / 30.0 and i + 1 < len(TIMELINE):
                nxt = TIMELINE[i + 1]
            return current, nxt, local
    if TIMELINE:
        return TIMELINE[-1], None, TIMELINE[-1].duration_sec
    return None, None, 0.0


def set_demo_hud(ctx: HudContext) -> None:
    """Offline sample video: inject simulated live HUD + chat state."""
    global _demo_hud_ctx
    _demo_hud_ctx = ctx


def render_frame(
    frame_idx: int,
    fps: int,
    width: int,
    height: int,
    state: SceneState,
    hud_ctx: HudContext | None = None,
) -> np.ndarray:
    t_sec = frame_idx / fps
    current, nxt, local_t = find_scene(t_sec)
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    if current is None:
        return frame

    local_f = int(local_t * fps)
    if local_f == 0:
        state.particles = ParticleField()

    ctx = hud_ctx or _demo_hud_ctx
    if _use_photoreal():
        frame = render_photoreal_frame(
            current.scene_id, local_f, width, height, state.symbol, fx=_fx, scene_state=state,
        )
        if nxt is not None:
            block_end = current.start_sec + current.duration_sec
            fade_t = (t_sec - (block_end - CROSSFADE_FRAMES / fps)) / (CROSSFADE_FRAMES / fps)
            fade_t = max(0.0, min(1.0, fade_t))
            if fade_t > 0:
                nxt_frame = render_photoreal_frame(
                    nxt.scene_id, 0, width, height, state.symbol, fx=_fx, scene_state=state,
                )
                frame = cv2.addWeighted(frame, 1.0 - fade_t, nxt_frame, fade_t, 0)
        _hud.draw(frame, state, ctx)
    else:
        renderer = SCENE_RENDERERS[current.scene_id]
        renderer(frame, local_f, fps, state)
        if nxt is not None:
            block_end = current.start_sec + current.duration_sec
            fade_t = (t_sec - (block_end - CROSSFADE_FRAMES / fps)) / (CROSSFADE_FRAMES / fps)
            fade_t = max(0.0, min(1.0, fade_t))
            if fade_t > 0:
                nxt_frame = np.zeros((height, width, 3), dtype=np.uint8)
                SCENE_RENDERERS[nxt.scene_id](nxt_frame, 0, fps, state)
                frame = cv2.addWeighted(frame, 1.0 - fade_t, nxt_frame, fade_t, 0)
        _hud.draw(frame, state, ctx)

    state.phase += 0.016
    state.mcap += 95
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
