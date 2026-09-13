"""In-memory incident store. The eval harness builds a fresh one per run."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import Incident, Signal


class IncidentStore:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self._n = 0

    def create(self, signal: Signal) -> Incident:
        self._n += 1
        inc = Incident(id=f"SB-{self._n:03d}", signals=[signal], opened_at=signal.received_at)
        self.incidents[inc.id] = inc
        return inc

    def merge(self, signal: Signal, incident_id: str) -> Incident:
        inc = self.incidents[incident_id]
        inc.signals.append(signal)
        return inc

    def open_within(self, ts: datetime, hours: int = 24, *, exclude_telemetry_backed: bool = False) -> list[Incident]:
        lo = ts - timedelta(hours=hours)
        out = []
        for inc in self.incidents.values():
            if not (lo <= inc.last_signal_at <= ts):
                continue
            if exclude_telemetry_backed and inc.telemetry:
                continue
            out.append(inc)
        return out

    def by_fingerprint(self, fp: str, ts: datetime, hours: int = 24) -> Incident | None:
        for inc in self.open_within(ts, hours):
            if any(s.fingerprint == fp for s in inc.telemetry):
                return inc
        return None

    def similar_within_days(self, service: str | None, ts: datetime, days: int = 30, *, exclude: str) -> bool:
        """Recurrence: a *prior* incident on the same service, opened between `days` ago and 24h ago.
        Incidents from the last 24h are the correlation window, not recurrence. No history fixture,
        so this only sees the current run."""
        if not service:
            return False
        lo, hi = ts - timedelta(days=days), ts - timedelta(hours=24)
        return any(i.service == service and i.id != exclude and lo <= i.opened_at < hi for i in self.incidents.values())

    # -- persistence (live mode and resolve) ---------------------------------
    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"n": self._n, "incidents": {k: v.model_dump(mode="json") for k, v in self.incidents.items()}}, indent=1))

    @classmethod
    def load(cls, path: str | Path) -> "IncidentStore":
        st = cls()
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text())
            st._n = data["n"]
            st.incidents = {k: Incident.model_validate(v) for k, v in data["incidents"].items()}
        return st
