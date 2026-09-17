"""Full-frame cinematic scenes — each scene is a completely different production."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from .figures import ParticleField, draw_dancer, draw_trader_at_desk
from .palettes import ColorWorld, WORLDS


@dataclass
class SceneState:
    symbol: str = "KWIF"
    coin_name: str = "Kitten Wif Hat"
    mcap: float = 42000
    phase: float = 0.0
    particles: ParticleField = field(default_factory=ParticleField)
    chart: list[float] = field(default_factory=lambda: [0.3] * 32)


def _gradient(frame: np.ndarray, world: ColorWorld, phase: float, style: str = "radial") -> None:
    h, w = frame.shape[:2]
    if style == "radial":
        cx, cy = w // 2, int(h * 0.35)
        max_r = int(math.hypot(w, h))
        for r in range(max_r, 0, -8):
            t = r / max_r + 0.05 * math.sin(phase + r * 0.01)
            color = tuple(
                int(world.bg_a[i] + (world.bg_b[i] - world.bg_a[i]) * min(1, t)) for i in range(3)
            )
            cv2.circle(frame, (cx, cy), r, color, -1)
    elif style == "diagonal":
        for y in range(0, h, 3):
            t = y / h + 0.08 * math.sin(phase + y * 0.015)
            color = tuple(
                int(world.bg_a[i] + (world.bg_b[i] - world.bg_a[i]) * (t % 1)) for i in range(3)
            )
            cv2.line(frame, (0, y), (w, y + int(w * 0.12)), color, 2)
    else:
        for y in range(h):
            t = y / h
            color = tuple(int(world.bg_a[i] + (world.bg_b[i] - world.bg_a[i]) * t) for i in range(3))
            frame[y, :] = color
    # Scan line accent
    sy = int((math.sin(phase * 1.5) * 0.5 + 0.5) * h)
    cv2.line(frame, (0, sy), (w, sy), world.glow, 1)


def _draw_token_title(frame: np.ndarray, state: SceneState, world: ColorWorld, scale: float = 1.0) -> None:
    h, w = frame.shape[:2]
    cv2.putText(
        frame, f"${state.symbol}", (int(w * 0.08), int(h * 0.22)),
        cv2.FONT_HERSHEY_DUPLEX, 2.2 * scale, world.accent, 4, cv2.LINE_AA,
    )
    cv2.putText(
        frame, state.coin_name, (int(w * 0.08), int(h * 0.30)),
        cv2.FONT_HERSHEY_DUPLEX, 0.9 * scale, world.text, 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, f"MCAP ${state.mcap:,.0f}", (int(w * 0.08), int(h * 0.38)),
        cv2.FONT_HERSHEY_DUPLEX, 0.7 * scale, world.accent2, 2, cv2.LINE_AA,
    )


def scene_lake_intro(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["lake_blue"]
    phase = local_f / fps + state.phase
    _gradient(frame, world, phase, "radial")
    h, w = frame.shape[:2]
    # Pulsing rings
    for i in range(5):
        r = int(60 + i * 50 + 30 * math.sin(phase * 2 + i))
        cv2.circle(frame, (w // 2, int(h * 0.45)), r, world.glow, 2, cv2.LINE_AA)
    _draw_token_title(frame, state, world)
    cv2.putText(frame, "LIVE ON PUMP.FUN", (int(w * 0.08), int(h * 0.48)),
                cv2.FONT_HERSHEY_DUPLEX, 0.8, world.glow, 2, cv2.LINE_AA)
    cv2.putText(frame, "● REC", (w - 140, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 60, 80), 2, cv2.LINE_AA)


def scene_pump_printer(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["emerald_rush"]
    phase = local_f / fps + state.phase
    _gradient(frame, world, phase, "linear")
    h, w = frame.shape[:2]
    draw_trader_at_desk(frame, w, h, phase, world)
    cv2.putText(frame, "PUMP.FUN MONEY PRINTER", (40, 50), cv2.FONT_HERSHEY_DUPLEX, 0.85, world.accent, 2, cv2.LINE_AA)
    cv2.putText(frame, "Cash flowing from the chart...", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.65, world.text, 1, cv2.LINE_AA)
    if local_f % 20 == 0:
        state.particles.spawn_cash_rain(w, 8)
    state.particles.tick(h, w)
    state.particles.draw(frame)


def scene_purple_chart(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["violet_dream"]
    phase = local_f / fps + state.phase
    _gradient(frame, world, phase, "diagonal")
    h, w = frame.shape[:2]
    state.mcap += 180
    val = min(1.0, state.mcap / 250000)
    state.chart.append(val)
    if len(state.chart) > 48:
        state.chart = state.chart[-48:]
    # Full-width chart
    cx, cy, cw, ch = 60, 120, w - 120, h - 220
    cv2.rectangle(frame, (cx, cy), (cx + cw, cy + ch), world.accent2, 2)
    pts = []
    for i, v in enumerate(state.chart):
        px = cx + int(i * cw / max(len(state.chart) - 1, 1))
        py = cy + ch - int(v * ch * 0.9)
        pts.append([px, py])
    if len(pts) > 1:
        cv2.polylines(frame, [np.array(pts, np.int32)], False, world.accent, 3, cv2.LINE_AA)
        fill = pts + [[cx + cw, cy + ch], [cx, cy + ch]]
        overlay = frame.copy()
        cv2.fillPoly(overlay, [np.array(fill, np.int32)], world.glow)
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
    cv2.putText(frame, "CHART STORM", (cx, cy - 20), cv2.FONT_HERSHEY_DUPLEX, 1.0, world.text, 2, cv2.LINE_AA)
    cv2.putText(frame, f"+{int(val*420)}% TODAY", (cx, cy + ch + 40), cv2.FONT_HERSHEY_DUPLEX, 0.8, world.accent, 2, cv2.LINE_AA)


def scene_pink_chat(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["hot_pink"]
    _gradient(frame, world, local_f / fps, "radial")
    h, w = frame.shape[:2]
    msgs = [
        "KWIF TO THE MOON 🚀", "just aped 5 SOL", "chart is INSANE", "LFG!!!",
        "whale incoming", "diamond paws", "this is addictive fr", "pump it",
        "marketing live", "telegram gang", "100K soon", "best stream ever",
    ]
    cv2.putText(frame, "VIRAL CHAT FLOOD", (40, 60), cv2.FONT_HERSHEY_DUPLEX, 1.0, world.text, 2, cv2.LINE_AA)
    for i in range(10):
        idx = (local_f // 8 + i) % len(msgs)
        y = 100 + i * 55 + (local_f % 8) * 3
        if y > h - 40:
            break
        alpha = 0.3 + 0.7 * (i / 10)
        color = tuple(int(world.accent[j] * alpha + world.bg_b[j] * (1 - alpha)) for j in range(3))
        cv2.rectangle(frame, (30, y - 30), (w - 30, y + 10), world.accent2, -1)
        cv2.putText(frame, msgs[idx], (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)


def scene_whale_alert(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["ocean_cyan"]
    phase = local_f / fps
    _gradient(frame, world, phase, "radial")
    h, w = frame.shape[:2]
    # Whale shape (simple)
    cx, cy = w // 2, int(h * 0.45)
    pulse = int(20 * math.sin(phase * 4))
    cv2.ellipse(frame, (cx, cy), (180 + pulse, 80 + pulse // 2), 0, 0, 360, world.accent, -1, cv2.LINE_AA)
    cv2.circle(frame, (cx + 120, cy - 20), 12, world.text, -1)
    cv2.putText(frame, "WHALE ALERT", (w // 2 - 160, 80), cv2.FONT_HERSHEY_DUPLEX, 1.4, world.text, 3, cv2.LINE_AA)
    cv2.putText(frame, "$50,000 BUY DETECTED", (w // 2 - 200, 130), cv2.FONT_HERSHEY_DUPLEX, 0.8, world.accent2, 2, cv2.LINE_AA)


def scene_celebration_dance(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["gold_celebration"]
    phase = local_f / fps * 3
    _gradient(frame, world, phase, "diagonal")
    h, w = frame.shape[:2]
    if local_f < 5:
        state.particles.spawn_cash_rain(w, 50)
        state.particles.spawn_confetti(w, 80)
    if local_f % 15 == 0:
        state.particles.spawn_cash_rain(w, 12)
    state.particles.tick(h, w)
    state.particles.draw(frame)
    draw_dancer(frame, w // 2, int(h * 0.55), phase, (world.accent, world.accent2))
    cv2.putText(frame, "MILESTONE CELEBRATION", (40, 60), cv2.FONT_HERSHEY_DUPLEX, 1.0, world.text, 2, cv2.LINE_AA)
    cv2.putText(frame, "$241K MCAP — KING OF THE HILL!", (40, 110), cv2.FONT_HERSHEY_DUPLEX, 0.75, world.accent, 2, cv2.LINE_AA)
    # Firework bursts
    for i in range(4):
        fx = int(w * (0.2 + i * 0.2))
        fy = int(h * 0.25 + 30 * math.sin(phase + i))
        cv2.circle(frame, (fx, fy), int(8 + 6 * math.sin(phase * 2 + i)), world.glow, 2)


def scene_fireworks_crown(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["sunset_blaze"]
    phase = local_f / fps
    _gradient(frame, world, phase, "radial")
    h, w = frame.shape[:2]
    cx, cy = w // 2, int(h * 0.38)
    # Crown
    for i in range(-2, 3):
        pts = np.array([[cx + i * 40, cy + 30], [cx + i * 40 - 15, cy - 20], [cx + i * 40 + 15, cy - 20]], np.int32)
        cv2.fillPoly(frame, [pts], world.accent)
    cv2.putText(frame, "KING OF THE HILL", (w // 2 - 200, cy + 80), cv2.FONT_HERSHEY_DUPLEX, 1.0, world.text, 2, cv2.LINE_AA)
    # Fireworks
    for i in range(12):
        angle = phase * 2 + i * (math.pi / 6)
        dist = 80 + 40 * math.sin(phase * 3 + i)
        fx = int(cx + math.cos(angle) * dist)
        fy = int(cy - 60 + math.sin(angle) * dist)
        cv2.circle(frame, (fx, fy), 4, world.glow, -1)


def scene_bonding_science(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["electric_blue"]
    phase = local_f / fps
    _gradient(frame, world, phase, "linear")
    h, w = frame.shape[:2]
    cv2.putText(frame, "BONDING CURVE SCIENCE", (40, 55), cv2.FONT_HERSHEY_DUPLEX, 0.9, world.text, 2, cv2.LINE_AA)
    # 3D-ish curve
    base_y = h - 100
    px, py = 80, base_y
    for i in range(60):
        t = i / 60
        x = int(80 + t * (w - 160))
        y = int(base_y - (t ** 1.8) * (h - 200) - 20 * math.sin(phase * 2 + t * 8))
        cv2.circle(frame, (x, y), 4, world.accent, -1)
        if i > 0:
            cv2.line(frame, (px, py), (x, y), world.glow, 2, cv2.LINE_AA)
        px, py = x, y
    progress = min(0.99, 0.4 + local_f / fps * 0.02)
    cv2.putText(frame, f"BONDING {progress*100:.0f}%", (40, 100), cv2.FONT_HERSHEY_DUPLEX, 0.7, world.accent2, 2, cv2.LINE_AA)
    cv2.putText(frame, "Dopamine loop: chart up → buy → celebrate → repeat", (40, h - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, world.text, 1, cv2.LINE_AA)


def scene_meme_montage(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    worlds = list(WORLDS.values())
    wi = (local_f // (fps * 2)) % len(worlds)
    world = worlds[wi]
    _gradient(frame, world, local_f / fps, ["radial", "diagonal", "linear"][wi % 3])
    h, w = frame.shape[:2]
    templates = [
        ("WHEN KWIF PUMPS", "STONKS"), ("DIAMOND PAWS", "HODL"), ("WHALE WATCH", "LFG"),
        ("PUMP.FUN", "PRINTING"), ("CHART GO BRR", "MOON"),
    ]
    ti = (local_f // (fps // 2)) % len(templates)
    top, bottom = templates[ti]
    # Meme card
    mx, my, mw, mh = w // 2 - 200, h // 2 - 120, 400, 240
    cv2.rectangle(frame, (mx, my), (mx + mw, my + mh), world.accent, 4)
    cv2.rectangle(frame, (mx + 4, my + 4), (mx + mw - 4, my + mh // 2), world.bg_b, -1)
    cv2.rectangle(frame, (mx + 4, my + mh // 2), (mx + mw - 4, my + mh - 4), world.bg_a, -1)
    cv2.putText(frame, top, (mx + 30, my + mh // 4), cv2.FONT_HERSHEY_DUPLEX, 0.8, world.text, 2, cv2.LINE_AA)
    cv2.putText(frame, bottom, (mx + 30, my + 3 * mh // 4), cv2.FONT_HERSHEY_DUPLEX, 0.8, world.accent2, 2, cv2.LINE_AA)


def scene_dance_finale(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["midnight_purple"]
    phase = local_f / fps * 4
    _gradient(frame, world, phase, "radial")
    h, w = frame.shape[:2]
    if local_f % 10 == 0:
        state.particles.spawn_cash_rain(w, 15)
        state.particles.spawn_confetti(w, 20)
    state.particles.tick(h, w)
    state.particles.draw(frame)
    draw_dancer(frame, w // 2 - 100, int(h * 0.55), phase, (world.accent, world.glow))
    draw_dancer(frame, w // 2 + 100, int(h * 0.55), phase + math.pi, (world.accent2, world.accent))
    cv2.putText(frame, "CASH RAIN FINALE", (40, 60), cv2.FONT_HERSHEY_DUPLEX, 1.0, world.text, 2, cv2.LINE_AA)
    cv2.putText(frame, "$100 BILLS EVERYWHERE", (40, 110), cv2.FONT_HERSHEY_DUPLEX, 0.75, world.accent, 2, cv2.LINE_AA)


def scene_mint_outro(frame: np.ndarray, local_f: int, fps: int, state: SceneState) -> None:
    world = WORLDS["mint_fresh"]
    _gradient(frame, world, local_f / fps, "radial")
    h, w = frame.shape[:2]
    _draw_token_title(frame, state, world, 1.2)
    cv2.putText(frame, "Every token gets a unique visual DNA", (40, int(h * 0.55)),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, world.text, 2, cv2.LINE_AA)
    cv2.putText(frame, "See you on the next livestream", (40, int(h * 0.62)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, world.accent2, 1, cv2.LINE_AA)


SCENE_RENDERERS = {
    "lake_intro": scene_lake_intro,
    "pump_printer": scene_pump_printer,
    "purple_chart": scene_purple_chart,
    "pink_chat": scene_pink_chat,
    "whale_alert": scene_whale_alert,
    "celebration_dance": scene_celebration_dance,
    "fireworks_crown": scene_fireworks_crown,
    "bonding_science": scene_bonding_science,
    "meme_montage": scene_meme_montage,
    "dance_finale": scene_dance_finale,
    "mint_outro": scene_mint_outro,
}
