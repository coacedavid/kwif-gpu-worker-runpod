"""
Rich 1080p60 visual compositor — varied themes, 2D/3D-style graphics, charts, memes.

Layers adapt per scene director: backgrounds, charts, emotion panels, memes,
FLUX/procedural hero, HUD, particles, captions.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Optional

import cv2
import numpy as np

from flux_generator import FluxGenerator
from meme_renderer import render_meme_overlay
from procedural_graphics import (
    draw_depth_grid,
    draw_donut_gauge,
    draw_emotion_scene,
    draw_glow_orb,
    draw_gradient_background,
    draw_line_chart,
    draw_ohlc_chart,
    draw_pseudo_3d_card,
)
from scene_director import SceneDirector


@dataclass
class TokenState:
    symbol: str = "TOKEN"
    mint: str = ""
    price_usd: float = 0.0
    market_cap_usd: float = 0.0
    volume_24h_usd: float = 0.0
    bonding_progress: float = 0.0
    is_koth: bool = False
    top_holders: list[str] = field(default_factory=list)
    recent_trades: Deque[str] = field(default_factory=lambda: deque(maxlen=8))
    chat_notifications: Deque[str] = field(default_factory=lambda: deque(maxlen=5))


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple[int, int, int]
    size: float


class LuxuryVisualCompositor:
    """Theme-aware rich compositor for 1920×1080 @ 60fps."""

    def __init__(self, state: TokenState, width: int = 1920, height: int = 1080):
        self.state = state
        self.w = width
        self.h = height
        self.flux = FluxGenerator(width=560, height=560)
        self.director = SceneDirector(mint=state.mint, symbol=state.symbol)
        self._flux_ready = False
        self._pending_flux_subject: Optional[str] = None

        self.alert_text = ""
        self.alert_until = 0.0
        self.milestone_title = ""
        self.milestone_subtitle = ""
        self.milestone_until = 0.0
        self.caption = "High-Roller Livestream initializing…"
        self.mouth_open = 0.0
        self._phase = 0.0
        self._particles: list[Particle] = []
        self._value_history: list[float] = [0.5] * 48
        self._mcap_history: list[float] = [0.3] * 48
        self.marketing_banner = ""
        self.marketing_banner_until = 0.0

    def set_marketing_banner(self, text: str, duration: float = 12.0) -> None:
        if text:
            self.marketing_banner = text[:72]
            self.marketing_banner_until = time.time() + duration

    def apply_visual_brief(self, brief: Optional[dict[str, Any]]) -> None:
        if not brief:
            return
        self.director.apply_brief(brief)
        placement = brief.get("marketingPlacement") or {}
        overlay = str(placement.get("overlayText") or "").strip()
        if overlay and placement.get("type") != "none":
            duration = float(placement.get("durationSec") or 10)
            self.set_marketing_banner(overlay, duration)
        if brief.get("tokenMint"):
            self.director.mint = str(brief["tokenMint"])
        if brief.get("tokenSymbol"):
            self.state.symbol = str(brief["tokenSymbol"]).lstrip("$")
        if self.director.should_refresh_flux():
            self._pending_flux_subject = self.director.flux_subject()

    async def init_flux(self, subject: str = "abstract luxury crypto art, original, no text") -> None:
        await self.flux.transition_to(subject, theme_prefix="")
        self._flux_ready = True

    async def maybe_transition_flux(self) -> None:
        if self._pending_flux_subject:
            subj = self._pending_flux_subject
            self._pending_flux_subject = None
            theme = self.director.get_theme()
            await self.flux.transition_to(subj, theme_prefix=theme.flux_prefix)

    def set_alert(self, text: str, duration: float = 4.0) -> None:
        self.alert_text = text
        self.alert_until = time.time() + duration
        self.state.recent_trades.appendleft(text)

    def trigger_milestone(self, title: str, subtitle: str = "", duration: float = 8.0) -> None:
        self.milestone_title = title
        self.milestone_subtitle = subtitle
        self.milestone_until = time.time() + duration
        self._spawn_particle_burst(200)

    def set_caption(self, text: str) -> None:
        self.caption = text[:160]

    def add_chat_notification(self, text: str) -> None:
        self.state.chat_notifications.appendleft(text[:80])

    def update_mouth(self, audio_chunk: Optional[np.ndarray]) -> None:
        if audio_chunk is None or len(audio_chunk) == 0:
            self.mouth_open *= 0.88
            return
        rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
        self.mouth_open = min(rms / 5000.0, 1.0)

    def update_state(self, state: TokenState) -> None:
        self.state = state

    def _spawn_particle_burst(self, count: int) -> None:
        theme = self.director.get_theme()
        cx, cy = self.w // 2, self.h // 2
        for _ in range(count):
            angle = np.random.uniform(0, 2 * math.pi)
            speed = np.random.uniform(2, 16)
            color = theme.particle_a if np.random.random() > 0.35 else theme.particle_b
            self._particles.append(
                Particle(
                    x=float(cx),
                    y=float(cy),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed - 4,
                    life=1.0,
                    color=color,
                    size=float(np.random.uniform(2, 7)),
                )
            )

    def _update_histories(self) -> None:
        self._value_history.append(self.state.bonding_progress)
        if len(self._value_history) > 64:
            self._value_history = self._value_history[-64:]
        mcap_norm = min(self.state.market_cap_usd / 100_000.0, 1.0) if self.state.market_cap_usd else 0.2
        self._mcap_history.append(mcap_norm)
        if len(self._mcap_history) > 64:
            self._mcap_history = self._mcap_history[-64:]

    def _draw_background(self, frame: np.ndarray) -> None:
        self._phase += 0.014
        theme = self.director.get_theme()
        bg_style = self.director.state.bg_style
        draw_gradient_background(frame, theme, self._phase, style=bg_style)
        if self.director.state.show_depth_grid:
            draw_depth_grid(frame, theme, self._phase, int(self.h * 0.62))
        if self.director.state.show_orbs:
            for i, (ox, oy) in enumerate([(180, 200), (self.w - 180, 260), (self.w // 2, 140)]):
                r = 40 + int(12 * math.sin(self._phase * 2 + i))
                draw_glow_orb(frame, ox, oy, r, theme, self._phase + i)

    def _draw_charts(self, frame: np.ndarray, layout: str) -> None:
        theme = self.director.get_theme()
        style = self.director.state.chart_style

        if layout == "fullscreen_chart":
            draw_ohlc_chart(frame, 48, 100, self.w - 96, 420, self._value_history, theme, "BONDING CURVE")
            draw_line_chart(frame, 48, 540, self.w - 96, 200, self._mcap_history, theme, "MCAP PULSE")
            return

        if layout == "dashboard_cards":
            draw_pseudo_3d_card(
                frame, 48, 110, 240, 90, theme, "MCAP", f"${self.state.market_cap_usd:,.0f}"
            )
            draw_pseudo_3d_card(frame, 48, 220, 240, 90, theme, "BONDING", f"{self.state.bonding_progress * 100:.1f}%")
            draw_pseudo_3d_card(frame, 48, 330, 240, 90, theme, "24H VOL", f"${self.state.volume_24h_usd:,.0f}")
            chart_x, chart_y, chart_w, chart_h = 320, 110, 560, 310
        else:
            chart_x, chart_y, chart_w, chart_h = 48, 110, 520, 220

        if style == "line_trend":
            draw_line_chart(frame, chart_x, chart_y, chart_w, chart_h, self._mcap_history, theme)
        elif style == "donut_gauge":
            draw_donut_gauge(
                frame, chart_x + chart_w // 2, chart_y + chart_h // 2, 80, self.state.bonding_progress, theme, "BONDING"
            )
        elif style == "dual_panel":
            draw_ohlc_chart(
                frame, chart_x, chart_y, chart_w // 2 - 8, chart_h, self._value_history, theme, "CURVE"
            )
            draw_line_chart(
                frame, chart_x + chart_w // 2 + 8, chart_y, chart_w // 2 - 8, chart_h, self._mcap_history, theme, "MCAP"
            )
        else:
            draw_ohlc_chart(frame, chart_x, chart_y, chart_w, chart_h, self._value_history, theme)

        if self.state.is_koth:
            cv2.putText(
                frame, "KING OF THE HILL", (chart_x + 12, chart_y + chart_h - 8),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, theme.chart_up, 1, cv2.LINE_AA,
            )

    def _draw_emotion_and_meme(self, frame: np.ndarray, layout: str) -> None:
        theme = self.director.get_theme()
        scene = self.director.state

        if scene.show_emotion_panel and layout in ("emotion_split", "split_chart_hero", "hero_meme_panel", "dashboard_cards"):
            ex, ey, ew, eh = self.w - 400, 110, 340, 240
            if layout == "emotion_split":
                ex, ey, ew, eh = 48, 360, 400, 280
            draw_emotion_scene(frame, ex, ey, ew, eh, scene.emotion, theme, self._phase, self.caption[:36])

        if scene.show_meme:
            mx = (self.w - 380) // 2
            my = 120 if layout == "hero_meme_panel" else self.h - 380
            mw, mh = 380, 200
            render_meme_overlay(
                frame, mx, my, mw, mh, scene.meme_template, scene.meme_top, scene.meme_bottom, theme
            )

    def _draw_visual_box(self, frame: np.ndarray, layout: str) -> None:
        theme = self.director.get_theme()
        if layout == "fullscreen_chart":
            return

        if layout == "cinema_letterbox":
            box_y = 120
            box_h = 340
        elif layout == "hero_meme_panel":
            box_y = 340
            box_h = 480
        else:
            box_y = 360
            box_h = 520

        box_w = 560
        box_x = (self.w - box_w) // 2
        box_h = min(box_h, self.h - box_y)

        cv2.rectangle(frame, (box_x - 4, box_y - 4), (box_x + box_w + 4, box_y + box_h + 4), theme.accent_secondary, 3)
        overlay = np.full((box_h, box_w, 3), theme.card_surface, dtype=np.uint8)

        flux_img = self.flux.get_frame()
        if flux_img is not None:
            overlay = cv2.resize(flux_img, (box_w, box_h))
        else:
            draw_glow_orb(overlay, box_w // 2, box_h // 2, min(box_w, box_h) // 3, theme, self._phase)
            cv2.putText(
                overlay, "GENERATING VISUAL…", (80, box_h // 2),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, theme.accent_primary, 2, cv2.LINE_AA,
            )

        if self.mouth_open > 0.05:
            mouth_y = box_h - 70
            mouth_h = int(10 + self.mouth_open * 36)
            cv2.ellipse(overlay, (box_w // 2, mouth_y), (48, mouth_h), 0, 0, 360, theme.bg_top, -1)

        frame[box_y : box_y + box_h, box_x : box_x + box_w] = overlay

    def _draw_hud(self, frame: np.ndarray) -> None:
        theme = self.director.get_theme()
        cv2.rectangle(frame, (0, 0), (self.w, 72), theme.bg_top, -1)
        cv2.line(frame, (0, 72), (self.w, 72), theme.accent_secondary, 2)
        title = f"${self.state.symbol}  |  MCAP ${self.state.market_cap_usd:,.0f}  |  ${self.state.price_usd:.8f}"
        cv2.putText(frame, title, (24, 48), cv2.FONT_HERSHEY_DUPLEX, 0.82, theme.accent_primary, 2, cv2.LINE_AA)

        mood = self.director.state.emotion.replace("_", " ").upper()[:18]
        cv2.putText(frame, mood, (self.w - 220, 48), cv2.FONT_HERSHEY_DUPLEX, 0.5, theme.accent_glow, 1, cv2.LINE_AA)

        cards = [
            ("24H VOLUME", f"${self.state.volume_24h_usd:,.0f}"),
            ("MINT", f"{self.state.mint[:6]}…{self.state.mint[-4:]}" if len(self.state.mint) > 12 else self.state.mint or "—"),
            ("HOLDERS", ", ".join(self.state.top_holders[:3]) or "—"),
        ]
        card_x = self.w - 360
        for i, (label, value) in enumerate(cards):
            cy = 88 + i * 68
            draw_pseudo_3d_card(frame, card_x, cy, 320, 58, theme, label, value[:30], depth=5)

        chat_x, chat_y = 48, self.h - 420
        cv2.rectangle(frame, (chat_x, chat_y), (chat_x + 320, chat_y + 180), theme.card_surface, -1)
        cv2.rectangle(frame, (chat_x, chat_y), (chat_x + 320, chat_y + 180), theme.accent_glow, 1)
        cv2.putText(frame, "LIVE CHAT", (chat_x + 12, chat_y + 24), cv2.FONT_HERSHEY_DUPLEX, 0.48, theme.accent_glow, 1, cv2.LINE_AA)
        for j, msg in enumerate(list(self.state.chat_notifications)[:4]):
            cv2.putText(
                frame, msg[:40], (chat_x + 12, chat_y + 50 + j * 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, theme.text_muted, 1, cv2.LINE_AA,
            )

    def _draw_particles(self, frame: np.ndarray) -> None:
        alive: list[Particle] = []
        for p in self._particles:
            p.x += p.vx
            p.y += p.vy
            p.vy += 0.14
            p.life -= 0.016
            if p.life <= 0:
                continue
            alpha = p.life
            color = tuple(int(c * alpha) for c in p.color)
            cv2.circle(frame, (int(p.x), int(p.y)), max(1, int(p.size * alpha)), color, -1)
            alive.append(p)
        self._particles = alive

    def _draw_milestone_modal(self, frame: np.ndarray) -> None:
        if time.time() >= self.milestone_until:
            return
        theme = self.director.get_theme()
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (self.w, self.h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        cx, cy = self.w // 2, self.h // 2
        cv2.rectangle(frame, (cx - 420, cy - 120), (cx + 420, cy + 120), theme.accent_secondary, 3)
        cv2.rectangle(frame, (cx - 416, cy - 116), (cx + 416, cy + 116), theme.card_surface, -1)

        pulse = 0.85 + 0.15 * math.sin(time.time() * 6)
        cv2.putText(
            frame, self.milestone_title[:48], (cx - 380, cy - 20),
            cv2.FONT_HERSHEY_DUPLEX, 1.2 * pulse, theme.accent_primary, 3, cv2.LINE_AA,
        )
        if self.milestone_subtitle:
            cv2.putText(
                frame, self.milestone_subtitle[:64], (cx - 360, cy + 40),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, theme.chart_up, 2, cv2.LINE_AA,
            )

    def _draw_marketing_banner(self, frame: np.ndarray) -> None:
        if time.time() >= self.marketing_banner_until or not self.marketing_banner:
            return
        theme = self.director.get_theme()
        bx, by = self.w - 420, 88
        cv2.rectangle(frame, (bx, by), (self.w - 24, by + 44), theme.accent_primary, -1)
        cv2.rectangle(frame, (bx, by), (self.w - 24, by + 44), theme.accent_glow, 2)
        cv2.putText(
            frame,
            self.marketing_banner[:42],
            (bx + 12, by + 28),
            cv2.FONT_HERSHEY_DUPLEX,
            0.52,
            theme.bg_top,
            2,
            cv2.LINE_AA,
        )

    def _draw_caption_and_ticker(self, frame: np.ndarray) -> None:
        theme = self.director.get_theme()
        cv2.rectangle(frame, (48, self.h - 200), (self.w - 48, self.h - 128), theme.card_surface, -1)
        cv2.rectangle(frame, (48, self.h - 200), (self.w - 48, self.h - 128), theme.accent_secondary, 1)
        cv2.putText(frame, self.caption, (64, self.h - 158), cv2.FONT_HERSHEY_DUPLEX, 0.68, theme.text_primary, 2, cv2.LINE_AA)

        cv2.rectangle(frame, (0, self.h - 56), (self.w, self.h), theme.bg_top, -1)
        cv2.line(frame, (0, self.h - 56), (self.w, self.h - 56), theme.accent_glow, 2)
        ticker = "   •   ".join(list(self.state.recent_trades)[:6]) or "Awaiting whale activity…"
        cv2.putText(frame, ticker[:140], (24, self.h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, theme.chart_up, 1, cv2.LINE_AA)

        if time.time() < self.alert_until and self.alert_text:
            cv2.rectangle(frame, (self.w // 2 - 320, 78), (self.w // 2 + 320, 138), theme.accent_primary, -1)
            cv2.putText(
                frame, self.alert_text[:56], (self.w // 2 - 300, 118),
                cv2.FONT_HERSHEY_DUPLEX, 0.72, theme.text_primary, 2, cv2.LINE_AA,
            )

    def render(self) -> np.ndarray:
        self._update_histories()
        layout = self.director.state.layout_id
        frame = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        self._draw_background(frame)
        self._draw_charts(frame, layout)
        self._draw_emotion_and_meme(frame, layout)
        self._draw_visual_box(frame, layout)
        self._draw_hud(frame)
        self._draw_marketing_banner(frame)
        self._draw_particles(frame)
        self._draw_milestone_modal(frame)
        self._draw_caption_and_ticker(frame)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
