"""Basit JSON durum deposu: görülen sinyaller ve gönderilen uyarılar.

GitHub Actions'ta actions/cache ile çalıştırmalar arasında taşınır;
repo public olduğu için commit edilmez.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path



def _path() -> Path:
    return Path(os.environ.get("RADAR_STATE", "state/state.json"))

KEEP_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


class State:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.seen: dict[str, str] = data.get("seen", {})
        self.alerted: dict[str, str] = data.get("alerted", {})
        self.history: list[dict] = data.get("history", [])

    @classmethod
    def load(cls, path: Path | None = None) -> "State":
        path = path or _path()
        if path.exists():
            try:
                return cls(json.loads(path.read_text()))
            except json.JSONDecodeError:
                pass
        return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or _path()
        self._prune()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"seen": self.seen, "alerted": self.alerted, "history": self.history[-200:]},
                ensure_ascii=False,
                indent=1,
            )
        )

    def is_new(self, key: str) -> bool:
        return key not in self.seen

    def mark_seen(self, keys: list[str]) -> None:
        ts = _now().isoformat()
        for k in keys:
            self.seen.setdefault(k, ts)

    def was_alerted(self, topic_key: str) -> bool:
        return topic_key in self.alerted

    def mark_alerted(self, topic_key: str) -> None:
        self.alerted[topic_key] = _now().isoformat()

    def log(self, entry: dict) -> None:
        self.history.append({"ts": _now().isoformat(), **entry})

    def recent_titles(self, hours: int = 72) -> list[str]:
        cutoff = _now() - timedelta(hours=hours)
        return [
            h["title"]
            for h in self.history
            if "title" in h and datetime.fromisoformat(h["ts"]) >= cutoff
        ]

    def _prune(self) -> None:
        cutoff = _now() - timedelta(days=KEEP_DAYS)
        for d in (self.seen, self.alerted):
            for k in [k for k, ts in d.items() if datetime.fromisoformat(ts) < cutoff]:
                del d[k]
