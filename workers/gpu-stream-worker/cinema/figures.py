"""Animated characters — dancer, trader at desk, cash particles."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Bill:
    x: float
    y: float
    vy: float
    rot: float
    vr: float
    size: float
    hue: int


@dataclass
class Confetti:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple[int, int, int]
    size: float


@dataclass
class ParticleField:
    bills: list[Bill] = field(default_factory=list)
    confetti: list[Confetti] = field(default_factory=list)

    def spawn_cash_rain(self, w: int, count: int = 40) -> None:
        for _ in range(count):
            self.bills.append(
                Bill(
                    x=np.random.uniform(0, w),
                    y=np.random.uniform(-200, -20),
                    vy=np.random.uniform(3, 9),
                    rot=np.random.uniform(0, 360),
                    vr=np.random.uniform(-4, 4),
                    size=np.random.uniform(0.7, 1.3),
                    hue=np.random.randint(80, 160),
                )
            )

    def spawn_confetti(self, w: int, count: int = 60) -> None:
        colors = [
            (255, 80, 180), (80, 200, 255), (120, 255, 140), (255, 220, 80),
            (200, 120, 255), (255, 140, 80), (100, 255, 220),
        ]
        for _ in range(count):
            self.confetti.append(
                Confetti(
                    x=np.random.uniform(0, w),
                    y=np.random.uniform(-100, 0),
                    vx=np.random.uniform(-2, 2),
                    vy=np.random.uniform(2, 7),
                    color=colors[np.random.randint(0, len(colors))],
                    size=np.random.uniform(4, 10),
                )
            )

    def tick(self, h: int, w: int) -> None:
        alive_b: list[Bill] = []
        for b in self.bills:
            b.y += b.vy
            b.x += math.sin(b.y * 0.02) * 0.8
            b.rot += b.vr
            if b.y < h + 80:
                alive_b.append(b)
        self.bills = alive_b

        alive_c: list[Confetti] = []
        for c in self.confetti:
            c.x += c.vx
            c.y += c.vy
            c.vy += 0.05
            if c.y < h + 20:
                alive_c.append(c)
        self.confetti = alive_c

    def draw(self, frame: np.ndarray) -> None:
        for b in self.bills:
            draw_dollar_bill(frame, int(b.x), int(b.y), b.rot, b.size)
        for c in self.confetti:
            cv2.circle(frame, (int(c.x), int(c.y)), int(c.size), c.color, -1)


def draw_dollar_bill(frame: np.ndarray, x: int, y: int, rot: float, scale: float = 1.0) -> None:
    w, h = int(56 * scale), int(26 * scale)
    overlay = np.zeros((h + 20, w + 20, 3), dtype=np.uint8)
    cv2.rectangle(overlay, (10, 10), (10 + w, 10 + h), (80, 180, 100), -1)
    cv2.rectangle(overlay, (10, 10), (10 + w, 10 + h), (40, 120, 60), 2)
    cv2.putText(overlay, "$100", (16, 10 + h // 2 + 4), cv2.FONT_HERSHEY_DUPLEX, 0.45 * scale, (240, 255, 240), 1, cv2.LINE_AA)
    M = cv2.getRotationMatrix2D((overlay.shape[1] // 2, overlay.shape[0] // 2), rot, 1.0)
    rotated = cv2.warpAffine(overlay, M, (overlay.shape[1], overlay.shape[0]), borderMode=cv2.BORDER_TRANSPARENT)
    _paste_rgba(frame, rotated, x - rotated.shape[1] // 2, y)


def _paste_rgba(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    sh, sw = src.shape[:2]
    dh, dw = dst.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dw, x + sw), min(dh, y + sh)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    patch = src[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)]
    mask = np.any(patch > 10, axis=2)
    dst[y0:y1, x0:x1][mask] = patch[mask]


def draw_dancer(frame: np.ndarray, cx: int, cy: int, phase: float, colors: tuple) -> None:
    """Animated dancing figure — arms/legs swing with beat."""
    skin = (255, 220, 190)
    outfit = colors[0]
    accent = colors[1]
    bounce = int(8 * math.sin(phase * 2))
    cy = cy + bounce
    leg_l = int(30 * math.sin(phase * 2))
    leg_r = int(30 * math.sin(phase * 2 + math.pi))
    cv2.line(frame, (cx, cy + 20), (cx - 20 + leg_l, cy + 80), outfit, 8, cv2.LINE_AA)
    cv2.line(frame, (cx, cy + 20), (cx + 20 + leg_r, cy + 80), accent, 8, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), (22, 32), 0, 0, 360, outfit, -1, cv2.LINE_AA)
    arm_l = int(35 * math.sin(phase * 2 + 0.5))
    arm_r = int(35 * math.sin(phase * 2 + math.pi + 0.5))
    cv2.line(frame, (cx, cy - 10), (cx - 40 + arm_l, cy - 30), skin, 6, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - 10), (cx + 40 + arm_r, cy - 30), skin, 6, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy - 45), 18, skin, -1, cv2.LINE_AA)
    cv2.circle(frame, (cx - 6, cy - 48), 2, (40, 40, 40), -1)
    cv2.circle(frame, (cx + 6, cy - 48), 2, (40, 40, 40), -1)
    pts = np.array([[cx, cy - 75], [cx - 14, cy - 50], [cx + 14, cy - 50]], np.int32)
    cv2.fillPoly(frame, [pts], accent)


def draw_trader_at_desk(frame: np.ndarray, w: int, h: int, phase: float, world) -> None:
    """Person at computer — cash flying from Pump.fun monitor."""
    desk_y = int(h * 0.72)
    cv2.rectangle(frame, (0, desk_y), (w, h), (40, 35, 50), -1)
    mx, my = w // 2 - 120, desk_y - 200
    cv2.rectangle(frame, (mx, my), (mx + 240, my + 160), (30, 30, 40), -1)
    cv2.rectangle(frame, (mx + 8, my + 8), (mx + 232, my + 140), (20, 80, 40), -1)
    for i in range(12):
        bx = mx + 20 + i * 16
        bh = int(20 + 80 * abs(math.sin(phase + i * 0.4)))
        cv2.rectangle(frame, (bx, my + 130 - bh), (bx + 10, my + 130), (60, 255, 100), -1)
    cv2.putText(frame, "pump.fun", (mx + 60, my + 28), cv2.FONT_HERSHEY_DUPLEX, 0.55, (120, 255, 160), 1, cv2.LINE_AA)
    cv2.putText(frame, "$KWIF +420%", (mx + 50, my + 55), cv2.FONT_HERSHEY_DUPLEX, 0.45, world.text, 1, cv2.LINE_AA)
    px = w // 2 - 180
    py = desk_y - 30
    cv2.ellipse(frame, (px, py - 60), (20, 20), 0, 0, 360, (220, 190, 160), -1)
    cv2.rectangle(frame, (px - 25, py - 40), (px + 25, py + 20), world.accent, -1)
    for i in range(8):
        angle = phase * 3 + i * 0.8
        bx = mx + 120 + int(60 * math.cos(angle))
        by = my + 80 + int(40 * math.sin(angle)) - int(phase * 20) % 60
        draw_dollar_bill(frame, bx, by, angle * 40, 0.8)
