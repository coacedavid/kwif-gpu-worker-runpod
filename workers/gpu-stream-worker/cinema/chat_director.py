"""
Chat-responsive livestream director — reads viewer chat and adjusts visuals + audio.

If viewers complain (no numbers, boring music, too quiet), the AI fixes it live.
If viewers praise a song or vibe, the stream plays more of that style.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Literal

MusicStyle = Literal["lofi", "trap", "celebration", "ambient", "hype"]


@dataclass
class ChatAdjustment:
    """Single actionable change from chat analysis."""

    kind: str  # show_hud | boost_music | play_celebration | fix_audio | switch_style | acknowledge
    detail: str = ""
    music_style: MusicStyle | None = None
    duration_sec: float = 30.0


@dataclass
class ChatDirectorState:
    style_scores: dict[str, int] = field(default_factory=lambda: {
        "lofi": 1, "trap": 0, "celebration": 0, "ambient": 0, "hype": 0,
    })
    complaints: list[str] = field(default_factory=list)
    preferred_style: MusicStyle = "lofi"
    force_enhanced_hud: bool = False
    force_louder_audio: bool = False
    request_more_celebration: bool = False
    last_adjustment_at: float = 0.0
    last_ack: str = ""

    def dominant_style(self) -> MusicStyle:
        best = max(self.style_scores.items(), key=lambda x: x[1])
        return best[0] if isinstance(best[0], str) else "lofi"


# Complaint patterns → fixes
_COMPLAINT_PATTERNS: list[tuple[re.Pattern[str], ChatAdjustment]] = [
    (re.compile(r"\b(no numbers|can't see|cant see|where.*mcap|no chart|no data)\b", re.I),
     ChatAdjustment("show_hud", "Enhanced live metrics HUD activated from chat feedback")),
    (re.compile(r"\b(boring|same (music|song|beat)|repetitive|monotone)\b", re.I),
     ChatAdjustment("switch_style", "Rotating music style per chat request", music_style="trap")),
    (re.compile(r"\b(too quiet|can't hear|cant hear|no (music|sound|audio)|silent)\b", re.I),
     ChatAdjustment("fix_audio", "Boosting stream audio volume")),
    (re.compile(r"\b(more (music|songs|beats)|play (a )?song|want lyrics|sing)\b", re.I),
     ChatAdjustment("switch_style", "More vocal songs queued", music_style="hype")),
    (re.compile(r"\b(celebration|anthem|milestone song|dance)\b", re.I),
     ChatAdjustment("play_celebration", "Celebration song requested by chat")),
    (re.compile(r"\b(chill|relax|lofi|smooth)\b", re.I),
     ChatAdjustment("switch_style", "Chill vibe from chat", music_style="lofi")),
    (re.compile(r"\b(hype|banger|fire|lit)\b", re.I),
     ChatAdjustment("switch_style", "Hype track from chat", music_style="hype")),
]

_LIKE_PATTERNS: list[tuple[re.Pattern[str], MusicStyle]] = [
    (re.compile(r"\b(love|like|fire|banger|this (beat|song|music|vibe))\b", re.I), "hype"),
    (re.compile(r"\b(chill|smooth|vibing|relaxing)\b", re.I), "lofi"),
    (re.compile(r"\b(celebration|anthem|milestone)\b", re.I), "celebration"),
    (re.compile(r"\b(trap|bass|hard)\b", re.I), "trap"),
]


class ChatResponsiveDirector:
    """Analyzes live chat and drives compositor + audio adjustments."""

    def __init__(self) -> None:
        self.state = ChatDirectorState()
        self._cooldown_sec = 12.0

    def process_message(self, text: str) -> ChatAdjustment | None:
        text = text.strip()
        if not text:
            return None
        now = time.time()
        if now - self.state.last_adjustment_at < self._cooldown_sec:
            # Still track likes during cooldown
            for pattern, style in _LIKE_PATTERNS:
                if pattern.search(text):
                    self.state.style_scores[style] = self.state.style_scores.get(style, 0) + 1
            return None

        for pattern, adj in _COMPLAINT_PATTERNS:
            if pattern.search(text):
                self._apply(adj)
                self.state.last_adjustment_at = now
                self.state.last_ack = adj.detail
                self.state.complaints.append(text[:80])
                return adj

        for pattern, style in _LIKE_PATTERNS:
            if pattern.search(text):
                self.state.style_scores[style] = self.state.style_scores.get(style, 0) + 2
                self.state.preferred_style = self.state.dominant_style()
                self.state.last_adjustment_at = now
                ack = ChatAdjustment(
                    "switch_style",
                    f"Chat loves the {style} vibe — playing more!",
                    music_style=style,
                )
                self.state.last_ack = ack.detail
                return ack

        return None

    def _apply(self, adj: ChatAdjustment) -> None:
        if adj.kind == "show_hud":
            self.state.force_enhanced_hud = True
        elif adj.kind == "fix_audio":
            self.state.force_louder_audio = True
        elif adj.kind == "play_celebration":
            self.state.request_more_celebration = True
        elif adj.kind == "switch_style" and adj.music_style:
            self.state.style_scores[adj.music_style] = self.state.style_scores.get(adj.music_style, 0) + 3
            self.state.preferred_style = adj.music_style

    def apply_to_compositor(self, compositor) -> None:
        """Push chat-driven state into CinemaCompositor."""
        if self.state.force_enhanced_hud and hasattr(compositor, "_hud_ctx"):
            compositor._hud_ctx.show_enhanced_hud = True
        if self.state.last_ack and hasattr(compositor, "set_caption"):
            compositor.set_caption(self.state.last_ack)
        if self.state.request_more_celebration and hasattr(compositor, "trigger_milestone"):
            compositor.trigger_milestone("CHAT REQUEST", "Celebration anthem — as you asked!", duration=12.0)
            self.state.request_more_celebration = False

    def preferred_music_style(self) -> MusicStyle:
        return self.state.preferred_style

    def audio_gain_multiplier(self) -> float:
        return 1.35 if self.state.force_louder_audio else 1.0
