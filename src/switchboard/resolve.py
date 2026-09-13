"""python -m switchboard.resolve <incident_id> [--state state.json] [--note "..."]

Closes the loop: one resolution email to every reporter correlated into the
incident, through the executor (allowlist + WAL, so a retry cannot double-send).
No action closes, deletes, or reassigns the incident record itself; resolution
is a notification, and the incident is marked resolved locally.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from .execute.executor import Executor, WriteCredentials
from .execute.wal import WAL
from .models import Action, Incident, idempotency_key
from .store import IncidentStore

load_dotenv()


def resolution_plan(inc: Incident, note: str = "") -> list[Action]:
    """One send_email_resolution per distinct reporter. Content is per-reporter and
    never includes other reporters' identities (README §4.2, cross-customer leakage)."""
    plan = []
    for sig in inc.signals:
        if not sig.reporter_email or any(a.payload["to"] == sig.reporter_email for a in plan):
            continue
        plan.append(Action(
            type="send_email_resolution",
            payload={"to": sig.reporter_email, "incident_id": inc.id, "thread_ref": sig.thread_ref,
                     "subject": f"Re: {sig.subject or 'your report'}", "note": note},
            idempotency_key=idempotency_key(inc.id, "send_email_resolution", sig.reporter_email),
        ))
    return plan


def resolve(inc: Incident, executor: Executor, note: str = "") -> list:
    results = executor.execute(resolution_plan(inc, note))
    inc.resolved = True
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("incident_id")
    ap.add_argument("--state", default="state.json")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    store = IncidentStore.load(args.state)
    inc = store.incidents.get(args.incident_id)
    if inc is None:
        print(f"no incident {args.incident_id} in {args.state}", file=sys.stderr)
        sys.exit(2)
    creds = WriteCredentials.from_env()
    executor = Executor(creds, WAL("wal.json"), lambda i: store.incidents[i].reporters)
    for r in resolve(inc, executor, args.note):
        print(f"  {'ok ' if r.ok else 'ERR'} {r.action.type} → {r.action.payload['to']}: {r.detail}")
    store.save(args.state)


if __name__ == "__main__":
    main()
