"""
Cinema compositor — production renderer for live GPU streams.

Drop-in replacement for LuxuryVisualCompositor: multi-scene cinematic frames,
token-unique rotation, event-driven celebrations (dance, cash rain, pump printer).
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import cv2
import numpy as np

from cinema.chat_director import ChatResponsiveDirector
from cinema.figures import ParticleField
from cinema.hud_overlay import HudContext, LiveStreamHUD
from cinema.live_director import LiveSceneDirector
from cinema.photoreal import PhotorealFX, render_photoreal_frame
from cinema.scenes import SCENE_RENDERERS, SceneState
from visual_compositor import TokenState


def _use_photoreal() -> bool:
    return os.environ.get("CINEMA_PROCEDURAL", "0").strip().lower() not in ("1", "true", "yes")


class CinemaCompositor:
    """Multi-scene cinematic renderer — default for ENABLE_CINEMA_MODE streams."""

    def __init__(self, state: TokenState, width: int = 1920, height: int = 1080, fps: int = 60):
        self.state = state
        self.w = width
        self.h = height
        self.fps = fps
        sym = state.symbol or "TOKEN"
        self._scene_state = SceneState(
            symbol=sym,
            coin_name=getattr(state, "coin_name", "") or sym,
            mcap=state.market_cap_usd or 42_000,
        )
        self._director = LiveSceneDirector(
            mint=state.mint or "default-mint",
            symbol=sym,
            coin_name=self._scene_state.coin_name,
            fps=fps,
        )
        self.caption = "High-Roller Cinema initializing…"
        self.mouth_open = 0.0
        self.alert_text = ""
        self.alert_until = 0.0
        self.milestone_title = ""
        self.milestone_subtitle = ""
        self.milestone_until = 0.0
        self.marketing_banner = ""
        self.marketing_banner_until = 0.0
        self._frame_count = 0
        self._photoreal_fx = PhotorealFX()
        self._hud = LiveStreamHUD()
        self._hud_ctx = HudContext()
        self._chat_director = ChatResponsiveDirector()

    # --- API compatible with LuxuryVisualCompositor / stream_worker ---

    async def init_flux(self, subject: str = "") -> None:
        """Photoreal mode uses Unsplash stock; optional RunPod FLUX when configured."""
        if os.environ.get("RUNPOD_FLUX_ENDPOINT_ID"):
            return  # stream_worker may still call FLUX for hero stills
        return

    async def maybe_transition_flux(self) -> None:
        return

    def apply_visual_brief(self, brief: Optional[dict[str, Any]]) -> None:
        if not brief:
            return
        sym = brief.get("tokenSymbol") or brief.get("symbol")
        if sym:
            self.state.symbol = str(sym).lstrip("$")
            self._scene_state.symbol = self.state.symbol
        if brief.get("tokenMint"):
            self.state.mint = str(brief["tokenMint"])
            self._director.mint = self.state.mint
        our = brief.get("ourToken") or {}
        if our.get("coinName"):
            self._scene_state.coin_name = str(our["coinName"])
        segment = brief.get("activeSegment") or {}
        seg_type = str(segment.get("type") or "")
        if seg_type in ("milestone_challenge", "performer_comparison"):
            self._director.trigger("milestone")
        elif seg_type == "rug_recovery":
            self._director.trigger("science")
        placement = brief.get("marketingPlacement") or {}
        overlay = str(placement.get("overlayText") or "").strip()
        if overlay:
            self.set_marketing_banner(overlay, float(placement.get("durationSec") or 12))

    def set_alert(self, text: str, duration: float = 4.0) -> None:
        self.alert_text = text[:80]
        self.alert_until = time.time() + duration
        self._hud_ctx.alert_text = self.alert_text
        self._hud_ctx.alert_until = self.alert_until
        self.state.recent_trades.appendleft(text[:60])
        self._hud_ctx.recent_trades = list(self.state.recent_trades)[:6]
        lower = text.lower()
        if "whale" in lower or "50k" in lower or "50,000" in lower:
            self._director.trigger("whale")
        elif "volume" in lower or "surge" in lower:
            self._director.trigger("pump_surge")
        else:
            self._director.trigger("chat_viral")
        self._scene_state.particles.spawn_confetti(self.w, 30)

    def trigger_milestone(self, title: str, subtitle: str = "", duration: float = 8.0) -> None:
        self.milestone_title = title
        self.milestone_subtitle = subtitle
        self.milestone_until = time.time() + duration
        self._hud_ctx.milestone_title = self.milestone_title
        self._hud_ctx.milestone_subtitle = self.milestone_subtitle
        self._hud_ctx.milestone_until = self.milestone_until
        self._director.trigger("milestone", duration_sec=max(duration, 20))
        self._scene_state.particles.spawn_cash_rain(self.w, 60)
        self._scene_state.particles.spawn_confetti(self.w, 80)

    def set_caption(self, text: str) -> None:
        self.caption = text[:160]
        self._hud_ctx.caption = self.caption

    def add_chat_notification(self, text: str) -> None:
        self.state.chat_notifications.appendleft(text[:80])
        self._hud_ctx.chat_messages = list(self.state.chat_notifications)[:5]
        adj = self._chat_director.process_message(text)
        if adj:
            self._chat_director.apply_to_compositor(self)
            if adj.kind == "show_hud":
                self._hud_ctx.show_enhanced_hud = True
            if adj.kind == "play_celebration":
                self.trigger_milestone("CHAT REQUEST", adj.detail, duration=14.0)
        if len(self.state.chat_notifications) > 3:
            self._director.trigger("chat_viral", duration_sec=10)

    def set_marketing_banner(self, text: str, duration: float = 12.0) -> None:
        if text:
            self.marketing_banner = text[:72]
            self.marketing_banner_until = time.time() + duration

    def update_mouth(self, audio_chunk: Optional[np.ndarray]) -> None:
        if audio_chunk is None or len(audio_chunk) == 0:
            self.mouth_open *= 0.88
            return
        rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
        self.mouth_open = min(rms / 5000.0, 1.0)

    def update_state(self, state: TokenState) -> None:
        self.state = state
        self._scene_state.mcap = state.market_cap_usd or self._scene_state.mcap
        self._scene_state.symbol = state.symbol
        if state.is_koth:
            self._director.trigger("koth")

    def _sync_scene_state(self) -> None:
        self._scene_state.mcap = self.state.market_cap_usd or self._scene_state.mcap
        self._scene_state.symbol = self.state.symbol or self._scene_state.symbol
        self._scene_state.coin_name = getattr(self.state, "coin_name", "") or self._scene_state.coin_name

    def _draw_overlays(self, frame: np.ndarray) -> None:
        """Caption bar, alerts, marketing — on top of any scene."""
        h, w = frame.shape[:2]
        # Bottom caption
        cv2.rectangle(frame, (24, h - 88), (w - 24, h - 24), (20, 20, 30), -1)
        cv2.rectangle(frame, (24, h - 88), (w - 24, h - 24), (100, 180, 255), 1)
        cv2.putText(frame, self.caption[:90], (40, h - 48), cv2.FONT_HERSHEY_DUPLEX, 0.62, (245, 248, 255), 1, cv2.LINE_AA)
        # Live badge
        cv2.circle(frame, (50, 36), 8, (255, 60, 80), -1)
        cv2.putText(frame, f"LIVE ${self.state.symbol}", (68, 44), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
        if time.time() < self.alert_until and self.alert_text:
            cv2.rectangle(frame, (w // 2 - 280, 60), (w // 2 + 280, 110), (255, 80, 120), -1)
            cv2.putText(frame, self.alert_text[:50], (w // 2 - 260, 95), cv2.FONT_HERSHEY_DUPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        if time.time() < self.marketing_banner_until and self.marketing_banner:
            cv2.rectangle(frame, (w - 420, 60), (w - 24, 100), (80, 140, 255), -1)
            cv2.putText(frame, self.marketing_banner[:42], (w - 400, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    def render(self) -> np.ndarray:
        self._sync_scene_state()
        scene_id, local_f, nxt_id, fade_t = self._director.tick_frame()

        if local_f == 0:
            self._scene_state.particles = ParticleField()

        self._hud_ctx.price_usd = self.state.price_usd
        self._hud_ctx.volume_24h = self.state.volume_24h_usd
        self._hud_ctx.is_koth = self.state.is_koth

        if _use_photoreal():
            frame = render_photoreal_frame(
                scene_id, local_f, self.w, self.h, self._scene_state.symbol,
                fx=self._photoreal_fx, scene_state=self._scene_state,
            )
            if nxt_id and fade_t > 0:
                nxt_frame = render_photoreal_frame(
                    nxt_id, 0, self.w, self.h, self._scene_state.symbol,
                    fx=self._photoreal_fx, scene_state=self._scene_state,
                )
                frame = cv2.addWeighted(frame, 1.0 - fade_t, nxt_frame, fade_t, 0)
            self._hud.draw(frame, self._scene_state, self._hud_ctx)
        else:
            frame = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            renderer = SCENE_RENDERERS.get(scene_id)
            if renderer:
                renderer(frame, local_f, self.fps, self._scene_state)
            if nxt_id and fade_t > 0:
                nxt_frame = np.zeros((self.h, self.w, 3), dtype=np.uint8)
                nxt_renderer = SCENE_RENDERERS.get(nxt_id)
                if nxt_renderer:
                    nxt_renderer(nxt_frame, 0, self.fps, self._scene_state)
                frame = cv2.addWeighted(frame, 1.0 - fade_t, nxt_frame, fade_t, 0)

        if not _use_photoreal():
            self._draw_overlays(frame)
        self._scene_state.phase += 0.014
        self._frame_count += 1
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    @property
    def chat_director(self) -> ChatResponsiveDirector:
        return self._chat_director
