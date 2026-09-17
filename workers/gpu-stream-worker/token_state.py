"""Minimal token state — no heavy compositor imports."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque


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
