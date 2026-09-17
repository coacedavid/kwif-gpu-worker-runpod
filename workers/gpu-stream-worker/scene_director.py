"""Visual scene director — unpredictable layouts per token/segment."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from meme_renderer import meme_text_for_segment
from theme_registry import (
    VisualTheme,
    build_flux_subject,
    pick_emotion,
    pick_layout,
    pick_meme_template,
    pick_theme,
)


CHART_STYLES = ["ohlc_bars", "line_trend", "donut_gauge", "dual_panel"]


@dataclass
class VisualSceneState:
    theme_id: str = "obsidian_gold"
    layout_id: str = "split_chart_hero"
    emotion: str = "education_calm"
    meme_template: str = "top_bottom"
    meme_top: str = ""
    meme_bottom: str = ""
    chart_style: str = "ohlc_bars"
    bg_style: str = "radial"
    flux_subject: str = ""
    show_emotion_panel: bool = True
    show_meme: bool = False
    show_depth_grid: bool = False
    show_orbs: bool = False
    variation_seed: int = 0
    applied_at: float = 0.0


class SceneDirector:
    def __init__(self, mint: str = "", symbol: str = "TOKEN"):
        self.mint = mint
        self.symbol = symbol
        self.narrative = "trending"
        self.state = VisualSceneState()
        self._theme: Optional[VisualTheme] = None
        self._last_tick = -1

    def apply_brief(self, brief: Optional[dict[str, Any]]) -> None:
        if not brief or not isinstance(brief, dict):
            return

        visual = brief.get("visualBrief")
        if not isinstance(visual, dict):
            segment = brief.get("activeSegment") or {}
            seg_type = str(segment.get("type") or "reactive")
            tick = int(brief.get("variationTick") or 0)
            self._auto_scene(seg_type, tick, brief)
            return

        self.state.theme_id = str(visual.get("themeId") or self.state.theme_id)
        self.state.layout_id = str(visual.get("layoutId") or self.state.layout_id)
        self.state.emotion = str(visual.get("emotion") or self.state.emotion)
        self.state.meme_template = str(visual.get("memeTemplate") or self.state.meme_template)
        self.state.meme_top = str(visual.get("memeTop") or "")
        self.state.meme_bottom = str(visual.get("memeBottom") or "")
        self.state.chart_style = str(visual.get("chartStyle") or self.state.chart_style)
        self.state.bg_style = str(visual.get("bgStyle") or self.state.bg_style)
        self.state.flux_subject = str(visual.get("fluxSubject") or "")
        self.state.show_emotion_panel = bool(visual.get("showEmotionPanel", True))
        self.state.show_meme = bool(visual.get("showMeme", False))
        self.state.show_depth_grid = bool(visual.get("showDepthGrid", False))
        self.state.show_orbs = bool(visual.get("showOrbs", False))
        self.state.variation_seed = int(visual.get("variationSeed") or 0)
        self.state.applied_at = time.time()

        our = brief.get("ourToken") or {}
        if our.get("narrativeKey"):
            self.narrative = str(our["narrativeKey"])
        if brief.get("tokenSymbol"):
            self.symbol = str(brief["tokenSymbol"]).lstrip("$")

    def _auto_scene(self, segment_type: str, tick: int, brief: dict[str, Any]) -> None:
        if tick == self._last_tick:
            return
        self._last_tick = tick

        our = brief.get("ourToken") or {}
        if our.get("narrativeKey"):
            self.narrative = str(our["narrativeKey"])
        sym = str(brief.get("tokenSymbol") or self.symbol).lstrip("$")
        mint = str(brief.get("tokenMint") or self.mint)

        theme = pick_theme(segment_type, mint, tick)
        layout = pick_layout(segment_type, mint, tick)
        emotion = pick_emotion(segment_type, mint, tick)
        meme_tpl = pick_meme_template(mint, tick)

        performers = brief.get("performers") or []
        rugged = brief.get("rugged") or []
        perf_sym = performers[0].get("symbol") if performers else None
        rug_sym = rugged[0].get("symbol") if rugged else None
        top, bottom = meme_text_for_segment(segment_type, sym, perf_sym, rug_sym)

        seed = int(hashlib.sha256(f"{mint}:{tick}:{segment_type}".encode()).hexdigest()[:8], 16)
        chart = CHART_STYLES[seed % len(CHART_STYLES)]
        bg = ["radial", "diagonal", "linear"][seed % 3]

        self.state = VisualSceneState(
            theme_id=theme.id,
            layout_id=layout,
            emotion=emotion,
            meme_template=meme_tpl,
            meme_top=top,
            meme_bottom=bottom,
            chart_style=chart,
            bg_style=bg,
            flux_subject=build_flux_subject(theme, sym, self.narrative, emotion),
            show_emotion_panel=segment_type not in ("reactive", "chat_engagement"),
            show_meme=segment_type in ("performer_comparison", "rug_recovery", "milestone_challenge", "multilingual_spark"),
            show_depth_grid=layout in ("depth_grid_stage", "cinema_letterbox"),
            show_orbs=layout in ("floating_orbs", "hero_meme_panel"),
            variation_seed=seed,
            applied_at=time.time(),
        )

    def get_theme(self) -> VisualTheme:
        from theme_registry import get_theme

        self._theme = get_theme(self.state.theme_id)
        return self._theme

    def should_refresh_flux(self, min_interval_sec: float = 65.0) -> bool:
        return time.time() - self.state.applied_at < 3.0 and bool(self.state.flux_subject)

    def flux_subject(self) -> str:
        if self.state.flux_subject:
            return self.state.flux_subject
        theme = self.get_theme()
        return build_flux_subject(theme, self.symbol, self.narrative, self.state.emotion)
