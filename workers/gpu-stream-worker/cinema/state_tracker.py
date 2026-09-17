"""Stateful asset rotation — no-repeat within N cycles, daily layout exclusion."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_NO_REPEAT_CYCLES = 10
_HISTORY_PATH = Path("/tmp/kwif_stream_state.json")


class StateTracker:
    """Memory-backed state tracker for beats, genres, visuals, personas, daily layouts."""

    def __init__(self, no_repeat_cycles: int = _NO_REPEAT_CYCLES, path: Path = _HISTORY_PATH) -> None:
        self._no_repeat = no_repeat_cycles
        self._path = path
        self._played: dict[str, deque[str]] = {
            "beat": deque(maxlen=no_repeat_cycles),
            "genre": deque(maxlen=no_repeat_cycles),
            "visual": deque(maxlen=no_repeat_cycles),
            "persona": deque(maxlen=no_repeat_cycles),
            "layout": deque(maxlen=no_repeat_cycles),
        }
        self._daily_layouts: dict[str, list[str]] = {}  # date -> layout ids used today
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for key, ids in data.get("played", {}).items():
                if key in self._played:
                    self._played[key] = deque(ids, maxlen=self._played[key].maxlen)
            self._daily_layouts = data.get("daily_layouts", {})
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps({
                "played": {k: list(v) for k, v in self._played.items()},
                "daily_layouts": self._daily_layouts,
            }))
        except Exception:
            pass

    def _today_utc(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def record(self, pool: str, asset_id: str) -> None:
        if pool in self._played:
            self._played[pool].append(asset_id)
            self._save()

    def record_daily_layout(self, layout_id: str) -> None:
        day = self._today_utc()
        layouts = self._daily_layouts.setdefault(day, [])
        if layout_id not in layouts:
            layouts.append(layout_id)
            self._save()

    def filter_available(
        self,
        pool: str,
        candidates: list[dict[str, Any]],
        daily_layout: bool = False,
    ) -> list[dict[str, Any]]:
        recent = set(self._played.get(pool, []))
        available = [c for c in candidates if c["id"] not in recent]
        if daily_layout:
            used_today = set(self._daily_layouts.get(self._today_utc(), []))
            daily_avail = [c for c in available if c["id"] not in used_today]
            if daily_avail:
                return daily_avail
        return available if available else candidates
