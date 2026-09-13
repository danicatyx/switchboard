"""python -m switchboard.demo

Six signals in real-time order: one alert, two vague emails that merge into
it, a second alert, a correlation-poisoning attack aimed at that second alert's
incident, and one unrelated ungrounded email.
Ends with the grounding comparison for the two emails.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .config import Config
from .execute.executor import Executor, WriteCredentials
from .execute.wal import WAL
from .models import DecisionRecord
from .pipeline import run_signal
from .store import IncidentStore

CORPUS = Path(__file__).resolve().parents[2] / "evals" / "corpus" / "signals.jsonl"
DEMO_IDS = ["sentry-inc-01", "msg-inc-01-2", "msg-inc-01-3", "sentry-inc-03", "msg-att-07", "msg-inc-12-2"]

B, D, R = "\033[1m", "\033[2m", "\033[0m"
C = {"auto": "\033[32m", "propose": "\033[33m", "escalate": "\033[31m"}


def head(raw: dict) -> str:
    ts = raw["received_at"][11:19]
    if raw["kind"] == "telemetry":
        return f"{B}── {ts}  SENTRY  {raw['service_tag']}{R}  fp={raw['fingerprint']}  Δerr={raw['error_rate_delta']}×  users={raw['affected_users']}"
    return f"{B}── {ts}  EMAIL   {raw['reporter_email']}{R}  {D}\"{raw['subject']}\"{R}"


def show(rec: DecisionRecord) -> None:
    inc = rec.incident
    t = {s.split(":", 1)[0]: s for s in rec.state_trace}
    print(f"   CORRELATE  {t['CORRELATE'][10:]:<24} LOCALIZE  {inc.service or 'unknown'} ({inc.localization_provenance}, {inc.localization_confidence:.2f})")
    if inc.owner:
        print(f"   OWNERSHIP  {inc.owner.team}  {inc.owner.slack_channel}{'  (stale CODEOWNERS)' if inc.owner.stale else ''}")
    else:
        print(f"   OWNERSHIP - ")
    print(f"   PRIORITY   {t['PRIORITY'][9:]}")
    print(f"   GATE       {C[rec.tier]}{rec.tier}{R} (c_eff {rec.c_eff})" + (f"  {D}injection flagged{R}" if rec.injection_flag else ""))
    print(f"   PLAN       " + " · ".join(f"{a.type}{D}→{a.payload.get('channel') or a.payload.get('to') or a.payload.get('user') or a.payload.get('incident_id')}{R}" for a in rec.plan) or " - ")


def main() -> None:
    raws = {json.loads(l)["external_id"]: json.loads(l) for l in open(CORPUS) if l.strip()}
    store = IncidentStore()
    cfg = Config(run_id="demo")
    wal_path = Path("wal.json")
    if wal_path.exists():
        wal_path.unlink()
    creds = WriteCredentials.from_env()
    executor = Executor(creds, WAL(wal_path), lambda inc_id: store.incidents[inc_id].reporters)

    print(f"\n{B}Switchboard demo{R} - {len(DEMO_IDS)} signals · executor {creds.describe()}\n")
    records: list[DecisionRecord] = []
    for ext in DEMO_IDS:
        raw = raws[ext]
        print(head(raw))
        rec = run_signal(raw, store, cfg)
        show(rec)
        sys.stdout.flush()
        rec.executed = executor.execute(rec.plan)
        sys.stderr.flush()
        failed = [r for r in rec.executed if not r.ok]
        for f in failed:
            print(f"   {C['escalate']}BLOCKED{R}    {f.action.type}: {f.detail}")
        records.append(rec)
        print()
        time.sleep(0.6)

    # Close the loop: resolve the first incident, then retry to show the WAL refuses to double-send.
    from .resolve import resolve
    print(f"{B}── Resolve SB-001{R}  (one email per correlated reporter, via the executor)\n")
    sys.stdout.flush()
    for r in resolve(store.incidents["SB-001"], executor, "Root cause: a timezone change in the export scheduler's 2.14.0 release. Rolled back; your scheduled exports have been re-run."):
        print(f"   {r.action.type} → {r.action.payload['to']}: {r.detail}")
    print(f"   retry → " + ", ".join(r.detail for r in resolve(store.incidents["SB-001"], executor)))
    print()

    # Grounding comparison: re-run the two emails with telemetry withheld from candidates.
    print(f"{B}── Grounding comparison{R}  (same two emails, telemetry withheld from the correlation index)\n")
    store2 = IncidentStore()
    cfg2 = Config(run_id="demo-ablate", ablate="grounding")
    run_signal(raws["sentry-inc-01"], store2, cfg2)
    print(f"   {'signal':<14} {'with alert':<44} {'without alert'}")
    for ext in ("msg-inc-01-2", "msg-inc-01-3"):
        with_ = next(r for r in records if r.signal.external_id == ext)
        wo = run_signal(raws[ext], store2, cfg2)
        a = f"{with_.incident.service} ({with_.incident.localization_provenance}, {with_.incident.localization_confidence:.2f}) → {with_.tier}"
        b = f"{wo.incident.service or 'unknown'} ({wo.incident.localization_provenance}, {wo.incident.localization_confidence:.2f}) → {wo.tier}"
        print(f"   {ext:<14} {a:<44} {b}")
    print()


if __name__ == "__main__":
    main()
