"""Token-specific lyric templates — unique hook per mint, shared structure."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


HOOK_TEMPLATES = [
    "{symbol} on the screen tonight — {name} is live on Pump dot fun!",
    "Lake blue dreams and the chart starts to climb — {symbol} holders unite!",
    "Money from the pump machine — green candles on the screen for {symbol}!",
    "Whale alert on {symbol}! The floor is ours — we want more!",
    "Money raining down — dance with me! {symbol} — king of the hill, feel that thrill!",
    "Bonding curve science on the screen — every frame a different {symbol} dream.",
]

CHORUS_TEMPLATES = [
    "{symbol} {symbol} — celebration time! Cash falling like it's summertime!",
    "Pump dot fun printing cash for you — {symbol} forever, staying true!",
    "Diamond paws on {name} — chart go brr, we never lose!",
]


@dataclass
class TokenLyrics:
    symbol: str
    coin_name: str
    mint: str

    def hook_line(self, index: int) -> str:
        seed = int(hashlib.sha256(f"{self.mint}:hook:{index}".encode()).hexdigest()[:6], 16)
        tpl = HOOK_TEMPLATES[seed % len(HOOK_TEMPLATES)]
        return tpl.format(symbol=self.symbol, name=self.coin_name or self.symbol)

    def chorus_line(self) -> str:
        seed = int(hashlib.sha256(f"{self.mint}:chorus".encode()).hexdigest()[:6], 16)
        tpl = CHORUS_TEMPLATES[seed % len(CHORUS_TEMPLATES)]
        return tpl.format(symbol=self.symbol, name=self.coin_name or self.symbol)

    def milestone_line(self, mcap_usd: float) -> str:
        if mcap_usd >= 200_000:
            return f"{self.symbol} just hit ${mcap_usd:,.0f}! King of the hill — celebration anthem!"
        if mcap_usd >= 100_000:
            return f"One hundred K on {self.symbol}! First milestone — let's dance!"
        return f"Milestone on {self.symbol} — ${mcap_usd:,.0f} market cap and climbing!"
