"""Write-ahead log keyed by idempotency key. A crash mid-plan resumes at the
first incomplete action instead of re-sending everything (README §3.8).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Action


class WAL:
    def __init__(self, path: Path | str = "wal.json") -> None:
        self.path = Path(path)
        self._entries: dict[str, dict] = {}
        if self.path.exists():
            self._entries = json.loads(self.path.read_text() or "{}")

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._entries, indent=1))

    def append(self, plan: list[Action]) -> None:
        for a in plan:
            self._entries.setdefault(a.idempotency_key, {"type": a.type, "payload": a.payload, "status": "pending"})
        self._flush()

    def status(self, key: str) -> str | None:
        e = self._entries.get(key)
        return e["status"] if e else None

    def mark(self, key: str, status: str) -> None:
        self._entries[key]["status"] = status
        self._flush()

    def pending(self) -> list[Action]:
        return [Action(type=e["type"], payload=e["payload"], idempotency_key=k, status="pending")
                for k, e in self._entries.items() if e["status"] == "pending"]
