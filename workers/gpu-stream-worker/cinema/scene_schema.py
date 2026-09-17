"""JSON schemas for modular livestream scene assembly."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
    """Full modular plan for one livestream sample — serializable to JSON."""
    symbol: str
    coin_name: str
    mint: str
    duration_sec: float
    seed: str
    audio_layers: list[AudioLayerSpec] = field(default_factory=list)
    vocals: list[VocalSpec] = field(default_factory=list)
    visual_scenes: list[VisualSceneSpec] = field(default_factory=list)
    milestones: list[MilestoneSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)
