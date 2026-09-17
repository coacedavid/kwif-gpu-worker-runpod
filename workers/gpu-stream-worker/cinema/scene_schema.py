"""Unified JSON scene schema for multi-stream creative engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class VisualLayer:
    background_type: str  # photorealistic_video | chart_overlay | luxury_stock
    prompt: str
    negative_prompt: str
    stock_image: str = ""


@dataclass
class AudioLayer:
    beat_id: str
    song_genre: str
    lyrics_context: str
    voiceover_persona: str
    script: str
    bpm: float = 100.0
    voice: str = "en-US-GuyNeural"
    rate: str = "-3%"
    pitch: str = "+1Hz"
    is_chorus: bool = False


@dataclass
class InteractiveLayer:
    chat_shoutouts: list[dict[str, str]] = field(default_factory=list)
    trend_topic: str = ""
    dominant_sentiment: str = "bullish"
    qa_prompt: str = ""


@dataclass
class UnifiedScene:
    """Single scene unit — matches architecture JSON spec."""
    scene_id: str
    timestamp_utc: str
    stream_theme: str
    start_sec: float
    duration_sec: float
    visual_layer: VisualLayer
    audio_layer: AudioLayer
    interactive_layer: InteractiveLayer = field(default_factory=InteractiveLayer)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioLayerSpec:
    layer_id: str
    genre: str
    bpm: float
    start_sec: float
    duration_sec: float
    asset_hash: str
    prompt: str = ""


@dataclass
class VocalSpec:
    at_sec: float
    persona_id: str
    voice: str
    text: str
    rate: str = "-3%"
    pitch: str = "+1Hz"
    is_chorus: bool = False


@dataclass
class VisualSceneSpec:
    scene_id: str
    start_sec: float
    duration_sec: float
    stock_image: str
    visual_prompt: str
    negative_prompt: str
    overlay: str = ""


@dataclass
class MilestoneSpec:
    at_sec: float
    milestone_type: str
    market_cap_usd: float
    celebration_genre: str
    anthem_prompt: str


@dataclass
class StreamPlan:
    """Full modular plan — unified scenes + legacy layer specs."""
    symbol: str
    coin_name: str
    mint: str
    duration_sec: float
    seed: str
    stream_theme: str = "default"
    timestamp_utc: str = ""
    unified_scenes: list[UnifiedScene] = field(default_factory=list)
    audio_layers: list[AudioLayerSpec] = field(default_factory=list)
    vocals: list[VocalSpec] = field(default_factory=list)
    visual_scenes: list[VisualSceneSpec] = field(default_factory=list)
    milestones: list[MilestoneSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp_utc:
            self.timestamp_utc = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)
