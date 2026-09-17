"""
Live stream scene director — token-unique rotation + event-driven scene overrides.

Each token mint produces a different scene order, palette emphasis, and rotation
interval so streams are hard to fingerprint as the same production.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

# Core rotation pool — every token gets a shuffled subset/order
ROTATION_SCENES = [
    "lake_intro",
    "pump_printer",
    "purple_chart",
    "pink_chat",
    "bonding_science",
    "meme_montage",
]

# Event-triggered scenes (higher priority than rotation)
EVENT_SCENES: dict[str, tuple[str, float]] = {
    "whale": ("whale_alert", 14.0),
    "milestone": ("celebration_dance", 28.0),
    "koth": ("fireworks_crown", 18.0),
    "engagement": ("pink_chat", 16.0),
    "pump_surge": ("pump_printer", 22.0),
    "chat_viral": ("pink_chat", 12.0),
    "science": ("bonding_science", 18.0),
    "finale": ("dance_finale", 24.0),
}

CROSSFADE_SEC = 0.4


@dataclass
class ActiveScene:
    scene_id: str
    started_at: float
    duration_sec: float
    source: str  # rotation | event


@dataclass
class LiveSceneDirector:
    mint: str
    symbol: str
    coin_name: str = ""
    fps: int = 60
    stream_started_at: float = field(default_factory=time.time)

    _rotation_order: list[str] = field(default_factory=list)
    _rotation_idx: int = 0
    _rotation_interval: float = 20.0
    _last_rotation_at: float = field(default_factory=time.time)
    _active: Optional[ActiveScene] = None
    _pending_event: Optional[ActiveScene] = None
    _local_frame: int = 0
    _scene_started_frame: int = 0

    def __post_init__(self) -> None:
        seed = int(hashlib.sha256(self.mint.encode()).hexdigest()[:8], 16)
        scenes = list(ROTATION_SCENES)
        # Fisher-Yates shuffle seeded by mint
        for i in range(len(scenes) - 1, 0, -1):
            j = seed % (i + 1)
            seed = seed * 1103515245 + 12345
            scenes[i], scenes[j] = scenes[j], scenes[i]
        self._rotation_order = scenes
        self._rotation_interval = 16.0 + (seed % 10)

    def _rotation_scene(self) -> str:
        return self._rotation_order[self._rotation_idx % len(self._rotation_order)]

    def _advance_rotation(self) -> None:
        self._rotation_idx += 1
        self._last_rotation_at = time.time()
        scene_id = self._rotation_scene()
        self._active = ActiveScene(scene_id, time.time(), self._rotation_interval, "rotation")
        self._local_frame = 0
        self._scene_started_frame = 0

    def ensure_scene(self) -> None:
        now = time.time()
        if self._active is None:
            self._advance_rotation()
            return
        elapsed = now - self._active.started_at
        if elapsed >= self._active.duration_sec:
            if self._pending_event:
                self._active = self._pending_event
                self._pending_event = None
            else:
                self._advance_rotation()
            self._local_frame = 0

    def trigger(self, event: str, duration_sec: Optional[float] = None) -> None:
        """Push an event scene — plays immediately or queues after current."""
        spec = EVENT_SCENES.get(event)
        if not spec:
            return
        scene_id, default_dur = spec
        dur = duration_sec or default_dur
        new_scene = ActiveScene(scene_id, time.time(), dur, "event")
        if self._active is None or self._active.source == "rotation":
            self._active = new_scene
            self._local_frame = 0
        else:
            self._pending_event = new_scene

    def tick_frame(self) -> tuple[str, int, Optional[str], float]:
        """
        Returns: (current_scene_id, local_frame, next_scene_id|None, crossfade_t)
        """
        self.ensure_scene()
        assert self._active is not None
        local_f = self._local_frame
        self._local_frame += 1

        elapsed = time.time() - self._active.started_at
        remaining = self._active.duration_sec - elapsed
        nxt: Optional[str] = None
        fade_t = 0.0
        if remaining < CROSSFADE_SEC:
            fade_t = max(0.0, 1.0 - remaining / CROSSFADE_SEC)
            if self._pending_event:
                nxt = self._pending_event.scene_id
            else:
                nxt = self._rotation_scene()

        return self._active.scene_id, local_f, nxt, fade_t

    def stream_elapsed_sec(self) -> float:
        return time.time() - self.stream_started_at
