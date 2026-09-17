"""Distinct color worlds — every scene feels like a different production."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorWorld:
    id: str
    bg_a: tuple[int, int, int]
    bg_b: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent2: tuple[int, int, int]
    glow: tuple[int, int, int]
    text: tuple[int, int, int]
    cash: tuple[int, int, int]


WORLDS: dict[str, ColorWorld] = {
    "lake_blue": ColorWorld("lake_blue", (12, 42, 88), (24, 120, 168), (100, 210, 255), (180, 240, 255), (60, 180, 255), (240, 250, 255), (120, 220, 160)),
    "ocean_cyan": ColorWorld("ocean_cyan", (8, 55, 75), (0, 140, 160), (0, 230, 210), (120, 255, 240), (80, 255, 220), (235, 255, 252), (100, 200, 140)),
    "violet_dream": ColorWorld("violet_dream", (35, 12, 68), (88, 28, 140), (200, 120, 255), (255, 160, 240), (180, 100, 255), (250, 245, 255), (160, 255, 180)),
    "hot_pink": ColorWorld("hot_pink", (68, 8, 48), (180, 30, 100), (255, 80, 180), (255, 140, 210), (255, 60, 160), (255, 245, 250), (180, 255, 120)),
    "emerald_rush": ColorWorld("emerald_rush", (6, 42, 28), (20, 120, 70), (60, 255, 140), (140, 255, 180), (80, 255, 120), (240, 255, 248), (255, 220, 80)),
    "gold_celebration": ColorWorld("gold_celebration", (48, 28, 8), (140, 90, 20), (255, 210, 60), (255, 240, 140), (255, 180, 40), (255, 252, 240), (120, 220, 100)),
    "sunset_blaze": ColorWorld("sunset_blaze", (80, 20, 40), (220, 80, 40), (255, 140, 80), (255, 200, 120), (255, 100, 60), (255, 250, 245), (200, 255, 160)),
    "midnight_purple": ColorWorld("midnight_purple", (18, 8, 42), (50, 20, 90), (140, 80, 255), (200, 140, 255), (100, 60, 220), (245, 240, 255), (255, 200, 100)),
    "mint_fresh": ColorWorld("mint_fresh", (16, 55, 55), (40, 140, 130), (120, 255, 220), (180, 255, 240), (80, 255, 200), (240, 255, 252), (255, 220, 120)),
    "electric_blue": ColorWorld("electric_blue", (10, 20, 80), (30, 60, 180), (80, 140, 255), (140, 200, 255), (60, 120, 255), (245, 248, 255), (100, 255, 180)),
}
