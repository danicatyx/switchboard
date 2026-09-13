"""In-memory incident store. The eval harness builds a fresh one per run."""

from __future__ import annotations

from datetime import datetime, timedelta

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
        """Recurrence: another incident on the same service opened within `days`. No history fixture, so this only sees the current run."""
        if not service:
            return False
        lo = ts - timedelta(days=days)
        return any(i.service == service and i.id != exclude and lo <= i.opened_at < ts for i in self.incidents.values())
