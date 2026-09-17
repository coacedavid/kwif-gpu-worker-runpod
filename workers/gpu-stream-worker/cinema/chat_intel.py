"""Interactive livechat intelligence — sentiment, Q&A, shoutouts."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from cinema.chat_director import ChatResponsiveDirector, ChatAdjustment


@dataclass
class ChatMessage:
    handle: str
    text: str
    timestamp: float = field(default_factory=time.time)
    sentiment: str = "neutral"  # bullish | bearish | neutral | hype | fomo


@dataclass
class ChatShoutout:
    handle: str
    message: str
    response_script: str
    at_sec: float


_QA_PROMPTS = [
    "Chat, what's the market cap prediction in the next ten minutes? Drop it below!",
    "Who's still holding through this move? Drop a fire emoji if you're diamond hands!",
    "Chat — bull or bear for the next candle? Let me hear you!",
    "What's your price target for this session? Shout it out!",
]

_SENTIMENT_POS = re.compile(r"\b(moon|lfg|bull|buy|pump|hold|diamond|fire|gem|based)\b", re.I)
_SENTIMENT_NEG = re.compile(r"\b(dump|rug|bear|sell|rekt|scam|dead)\b", re.I)
_HANDLE_RE = re.compile(r"^([a-zA-Z0-9_]{2,20}):\s*(.+)")


class ChatIntelEngine:
    """Scores chat, generates Q&A prompts, shoutouts, and spoken responses."""

    def __init__(self) -> None:
        self._director = ChatResponsiveDirector()
        self._messages: list[ChatMessage] = []
        self._dominant_sentiment = "bullish"

    def ingest(self, raw: str) -> ChatMessage | None:
        m = _HANDLE_RE.match(raw.strip())
        if not m:
            return None
        handle, text = m.group(1), m.group(2)
        sentiment = "neutral"
        if _SENTIMENT_POS.search(text):
            sentiment = "hype" if "fire" in text.lower() or "lfg" in text.lower() else "bullish"
        elif _SENTIMENT_NEG.search(text):
            sentiment = "bearish"
        msg = ChatMessage(handle=handle, text=text, sentiment=sentiment)
        self._messages.append(msg)
        self._update_dominant_sentiment()
        return msg

    def _update_dominant_sentiment(self) -> None:
        recent = self._messages[-20:]
        if not recent:
            return
        scores = {"bullish": 0, "bearish": 0, "hype": 0, "neutral": 0}
        for m in recent:
            scores[m.sentiment] = scores.get(m.sentiment, 0) + 1
        self._dominant_sentiment = max(scores, key=scores.get)

    def process_adjustment(self, raw: str) -> ChatAdjustment | None:
        return self._director.process_message(raw)

    def dominant_sentiment(self) -> str:
        return self._dominant_sentiment

    def pick_shoutout(self, symbol: str, at_sec: float) -> ChatShoutout | None:
        candidates = [m for m in self._messages[-30:] if len(m.text) > 5]
        if not candidates:
            return None
        msg = max(candidates, key=lambda m: len(m.text))
        responses = [
            f"@{msg.handle} in chat just said '{msg.text[:40]}' — let's check that {symbol} chart!",
            f"Shoutout to @{msg.handle}: '{msg.text[:50]}' — the chat is alive tonight!",
            f"I see you @{msg.handle} — '{msg.text[:40]}' — {symbol} army heard you loud and clear.",
        ]
        import random
        return ChatShoutout(
            handle=msg.handle, message=msg.text,
            response_script=random.choice(responses), at_sec=at_sec,
        )

    def qa_prompt(self, index: int = 0) -> str:
        return _QA_PROMPTS[index % len(_QA_PROMPTS)]

    def to_interactive_layer(self) -> dict[str, Any]:
        shoutouts = [
            {"handle": m.handle, "text": m.text, "sentiment": m.sentiment}
            for m in self._messages[-5:]
        ]
        return {
            "chat_shoutouts": shoutouts,
            "dominant_sentiment": self._dominant_sentiment,
            "trend_topic": "",
        }
