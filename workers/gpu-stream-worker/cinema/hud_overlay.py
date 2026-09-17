"""
Live data HUD — market cap, bonding %, charts, whale alerts, chat panel.

Layered on top of photoreal cinema so viewers always see live numbers.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from cinema.scenes import SceneState


@dataclass
class HudContext:
    alert_text: str = ""
    alert_until: float = 0.0
    milestone_title: str = ""
    milestone_subtitle: str = ""
    milestone_until: float = 0.0
    caption: str = ""
    chat_messages: list[str] = field(default_factory=list)
    marketing_banner: str = ""
    marketing_until: float = 0.0
    recent_trades: list[str] = field(default_factory=list)
    price_usd: float = 0.0
    volume_24h: float = 0.0
    is_koth: bool = False
    show_enhanced_hud: bool = True


class LiveStreamHUD:
    """Persistent HUD with animated charts and live token metrics."""

    def __init__(self) -> None:
        self._mcap_history: list[float] = [0.3] * 48
        self._bond_history: list[float] = [0.5] * 48
        self._start_mcap: float | None = None
        self._phase = 0.0

    def update(self, state: SceneState, ctx: HudContext) -> float:
        if self._start_mcap is None and state.mcap > 0:
            self._start_mcap = state.mcap
        mcap_norm = min(state.mcap / 300_000.0, 1.0) if state.mcap else 0.2
        self._mcap_history.append(mcap_norm)
        if len(self._mcap_history) > 64:
            self._mcap_history = self._mcap_history[-64:]
        bond = min(state.mcap / 69_000.0, 1.0) if state.mcap else 0.0
        self._bond_history.append(bond)
        if len(self._bond_history) > 64:
            self._bond_history = self._bond_history[-64:]
        self._phase += 0.014
        if self._start_mcap and self._start_mcap > 0:
            return max(0.0, (state.mcap - self._start_mcap) / self._start_mcap * 100)
        return min(420.0, state.mcap / 500)

    def draw(self, frame: np.ndarray, state: SceneState, ctx: HudContext) -> None:
        if not ctx.show_enhanced_hud:
            return
        h, w = frame.shape[:2]
        pct = self.update(state, ctx)
        now = time.time()
        bar_h = 72
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_h), (12, 14, 22), -1)
        frame[:] = cv2.addWeighted(overlay, 0.72, frame, 0.28, 0)
        cv2.line(frame, (0, bar_h), (w, bar_h), (80, 160, 255), 2)
        sym = state.symbol or "TOKEN"
        mcap_str = f"${state.mcap:,.0f}" if state.mcap else "$—"
        price_str = f"${ctx.price_usd:.8f}" if ctx.price_usd else "—"
        bond_pct = min(state.mcap / 69_000.0, 1.0) * 100 if state.mcap else 0.0
        cv2.putText(frame, f"${sym}  MCAP {mcap_str}  |  {price_str}", (20, 30), cv2.FONT_HERSHEY_DUPLEX, 0.62, (120, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"BONDING {bond_pct:.1f}%  |  +{pct:.0f}% SESSION", (20, 58), cv2.FONT_HERSHEY_DUPLEX, 0.5, (100, 255, 160), 1, cv2.LINE_AA)
        if ctx.is_koth or state.mcap >= 69_000:
            cv2.putText(frame, "👑 KOTH", (w - 120, 36), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 220, 80), 2, cv2.LINE_AA)
        cx, cy, cw, ch = w - 340, h - 200, 300, 120
        cv2.rectangle(frame, (cx, cy), (cx + cw, cy + ch), (20, 24, 36), -1)
        cv2.rectangle(frame, (cx, cy), (cx + cw, cy + ch), (100, 180, 255), 1)
        cv2.putText(frame, "MCAP PULSE", (cx + 10, cy + 22), cv2.FONT_HERSHEY_DUPLEX, 0.42, (180, 200, 255), 1, cv2.LINE_AA)
        pts = []
        for i, v in enumerate(self._mcap_history[-40:]):
            px = cx + 10 + int(i * (cw - 20) / max(len(self._mcap_history[-40:]) - 1, 1))
            py = cy + ch - 12 - int(v * (ch - 36))
            pts.append([px, py])
        if len(pts) > 1:
            cv2.polylines(frame, [np.array(pts, np.int32)], False, (80, 255, 140), 2, cv2.LINE_AA)
        gx, gy = cx + 10, cy + ch + 28
        cv2.rectangle(frame, (gx, gy), (gx + cw - 20, gy + 14), (40, 44, 60), -1)
        fill_w = int((cw - 20) * bond_pct / 100)
        cv2.rectangle(frame, (gx, gy), (gx + fill_w, gy + 14), (80, 220, 120), -1)
        cv2.putText(frame, f"Bonding {bond_pct:.1f}%", (gx, gy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 220, 255), 1, cv2.LINE_AA)
        if ctx.chat_messages:
            chat_x, chat_y = 20, h - 210
            cv2.rectangle(frame, (chat_x, chat_y), (chat_x + 300, chat_y + 150), (16, 18, 28), -1)
            cv2.rectangle(frame, (chat_x, chat_y), (chat_x + 300, chat_y + 150), (255, 120, 200), 1)
            cv2.putText(frame, "LIVE CHAT", (chat_x + 10, chat_y + 22), cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 160, 220), 1, cv2.LINE_AA)
            for j, msg in enumerate(ctx.chat_messages[:4]):
                cv2.putText(frame, msg[:38], (chat_x + 10, chat_y + 48 + j * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 240), 1, cv2.LINE_AA)
        cv2.rectangle(frame, (0, h - 36), (w, h), (10, 12, 20), -1)
        ticker = "   •   ".join(ctx.recent_trades[:5]) or "Awaiting whale activity…"
        cv2.putText(frame, ticker[:120], (16, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100, 255, 160), 1, cv2.LINE_AA)
        if ctx.alert_text and now < ctx.alert_until:
            pulse = 0.85 + 0.15 * math.sin(now * 8)
            bx0, by0 = w // 2 - 280, 88
            cv2.rectangle(frame, (bx0, by0), (bx0 + 560, by0 + 52), (255, 60, 100), -1)
            cv2.rectangle(frame, (bx0, by0), (bx0 + 560, by0 + 52), (255, 200, 220), 2)
            cv2.putText(frame, ctx.alert_text[:52], (bx0 + 16, by0 + 36), cv2.FONT_HERSHEY_DUPLEX, 0.62 * pulse, (255, 255, 255), 2, cv2.LINE_AA)
        if ctx.milestone_title and now < ctx.milestone_until:
            dim = frame.copy()
            cv2.rectangle(dim, (0, 0), (w, h), (0, 0, 0), -1)
            frame[:] = cv2.addWeighted(dim, 0.45, frame, 0.55, 0)
            mx0, my0 = w // 2 - 340, h // 2 - 70
            cv2.rectangle(frame, (mx0, my0), (mx0 + 680, my0 + 120), (255, 200, 80), 3)
            cv2.rectangle(frame, (mx0 + 4, my0 + 4), (mx0 + 676, my0 + 116), (20, 22, 32), -1)
            pulse = 0.9 + 0.1 * math.sin(now * 6)
            cv2.putText(frame, ctx.milestone_title[:48], (mx0 + 24, my0 + 52), cv2.FONT_HERSHEY_DUPLEX, 0.95 * pulse, (255, 220, 100), 2, cv2.LINE_AA)
            if ctx.milestone_subtitle:
                cv2.putText(frame, ctx.milestone_subtitle[:56], (mx0 + 24, my0 + 92), cv2.FONT_HERSHEY_DUPLEX, 0.55, (120, 255, 180), 1, cv2.LINE_AA)
        if ctx.marketing_banner and now < ctx.marketing_until:
            cv2.rectangle(frame, (w - 380, 82), (w - 20, 118), (80, 140, 255), -1)
            cv2.putText(frame, ctx.marketing_banner[:40], (w - 364, 106), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        if ctx.caption:
            cv2.rectangle(frame, (24, h - 88), (w - 24, h - 44), (16, 18, 28), -1)
            cv2.rectangle(frame, (24, h - 88), (w - 24, h - 44), (100, 180, 255), 1)
            cv2.putText(frame, ctx.caption[:90], (40, h - 56), cv2.FONT_HERSHEY_DUPLEX, 0.55, (245, 248, 255), 1, cv2.LINE_AA)
