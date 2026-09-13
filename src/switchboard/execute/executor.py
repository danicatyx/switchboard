"""The Executor is the sole holder of write credentials (README §6.1).

Decision stages are constructed without WriteCredentials and never import this
module; tests/test_credentials.py asserts that. Recipients are restricted to
reporters correlated into the incident, and channels to the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..catalog import load_catalog
from ..integrations.email import SmtpSender
from ..integrations.fakes import FakeGmail, FakeIncidentTracker, FakeSlack
from ..integrations.slack import SlackAdapter
from ..models import Action, ActionResult
from ..plan import TRIAGE_HUMANS, TRIAGE_PROPOSALS
from .wal import WAL

CLOSED_ACTION_SET = {
    "create_incident", "merge_signal_into_incident", "comment_on_incident", "post_slack",
    "page_oncall", "send_email_ack", "send_email_resolution", "escalate_to_human",
}


class AllowlistViolation(Exception):
    pass


@dataclass
class WriteCredentials:
    """Only the Executor is ever handed one of these."""
    slack: FakeSlack | SlackAdapter = field(default_factory=FakeSlack)
    gmail: FakeGmail | SmtpSender = field(default_factory=FakeGmail)
    tracker: FakeIncidentTracker = field(default_factory=FakeIncidentTracker)

    @classmethod
    def from_env(cls) -> "WriteCredentials":
        """Real adapters where configured, fakes (console) otherwise."""
        slack = SlackAdapter()
        smtp = SmtpSender()
        return cls(slack=slack if slack.live else FakeSlack(),
                   gmail=smtp if smtp.live else FakeGmail(),
                   tracker=FakeIncidentTracker())

    def describe(self) -> str:
        return (f"slack={'live' if isinstance(self.slack, SlackAdapter) else 'console'} "
                f"email={'smtp' if isinstance(self.gmail, SmtpSender) else 'console'} tracker=fake")


def _fmt(payload: dict) -> str:
    rules = ",".join(payload.get("applied_rules") or []) or "none"
    return (f"{payload.get('priority')}  {payload.get('service') or 'unknown'}  ({payload.get('provenance')})\n"
            f"incident {payload.get('incident_id')} · {payload.get('signal_count')} signal(s) · "
            f"{payload.get('distinct_accounts')} account(s) · rules: {rules} · c_eff {payload.get('c_eff')}")


class Executor:
    def __init__(self, write: WriteCredentials, wal: WAL, reporters_for: Callable[[str], set[str]]) -> None:
        self.write = write
        self.wal = wal
        self.reporters_for = reporters_for
        cat = load_catalog()
        self.allowed_channels = {t["slack_channel"] for t in cat["teams"].values()} | {TRIAGE_PROPOSALS, TRIAGE_HUMANS}
        self.allowed_users = {t["oncall_user"] for t in cat["teams"].values() if t.get("oncall_user")}

    def execute(self, plan: list[Action]) -> list[ActionResult]:
        self.wal.append(plan)
        results = []
        for a in plan:
            if self.wal.status(a.idempotency_key) == "done":
                results.append(ActionResult(action=a, ok=True, detail="skipped: already done"))
                continue
            try:
                detail = self._do(a)
                self.wal.mark(a.idempotency_key, "done")
                a.status = "done"
                results.append(ActionResult(action=a, ok=True, detail=detail))
            except AllowlistViolation as e:
                self.wal.mark(a.idempotency_key, "failed")
                a.status = "failed"
                results.append(ActionResult(action=a, ok=False, detail=f"allowlist: {e}"))
        return results

    def _do(self, a: Action) -> str:
        p = a.payload
        if a.type not in CLOSED_ACTION_SET:
            raise AllowlistViolation(f"action outside A: {a.type}")
        if a.type == "create_incident":
            self.write.tracker.create(p["incident_id"], p)
            return f"created {p['incident_id']}"
        if a.type == "merge_signal_into_incident":
            self.write.tracker.merge(p["incident_id"], p["signal_id"])
            return f"merged into {p['incident_id']}"
        if a.type in ("post_slack", "escalate_to_human"):
            ch = p["channel"]
            if ch not in self.allowed_channels:
                raise AllowlistViolation(f"channel not in catalog: {ch}")
            head = "PROPOSED (approve / edit)" if p.get("proposal") else ("ESCALATED to humans" if a.type == "escalate_to_human" else "INCIDENT")
            text = f"{head}\n{_fmt(p)}" + (f"\nreasons: {', '.join(p['reasons'])}" if p.get("reasons") else "")
            self.write.slack.post(ch, text, {"idempotency_key": a.idempotency_key})
            return f"posted to {ch}"
        if a.type == "page_oncall":
            if p["user"] not in self.allowed_users:
                raise AllowlistViolation(f"on-call user not in catalog: {p['user']}")
            self.write.slack.post(p["channel"], f"PAGE {p['user']} — P1\n{_fmt(p)}", {"idempotency_key": a.idempotency_key})
            return f"paged {p['user']}"
        if a.type in ("send_email_ack", "send_email_resolution"):
            allowed = self.reporters_for(p["incident_id"])
            if p["to"] not in allowed:
                raise AllowlistViolation(f"recipient {p['to']} not a reporter on {p['incident_id']}")
            body = (f"Thanks for your report. We've opened incident {p['incident_id']} and the owning team is on it. "
                    f"We'll email you again when it's resolved.") if a.type == "send_email_ack" else \
                   (f"The issue you reported ({p['incident_id']}) is resolved. Thanks again for letting us know."
                    + (f"\n\n{p['note']}" if p.get("note") else ""))
            self.write.gmail.send(p["to"], p["subject"] if "subject" in p else f"Update on {p['incident_id']}", body, p.get("thread_ref"))
            return f"emailed {p['to']}"
        raise AllowlistViolation(f"unhandled action {a.type}")
