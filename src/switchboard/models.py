"""Data model. Mirrors README §6.2."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["email", "telemetry"]
Provenance = Literal["grounded:telemetry", "inferred:model", "unknown"]
Priority = Literal["P1", "P2", "P3", "P4"]
Tier = Literal["auto", "propose", "escalate"]
ActionType = Literal[
    "create_incident",
    "merge_signal_into_incident",
    "comment_on_incident",
    "post_slack",
    "page_oncall",
    "send_email_ack",
    "send_email_resolution",
    "escalate_to_human",
]


def signal_id(source: str, external_id: str) -> str:
    return hashlib.sha256(f"{source}‖{external_id}".encode()).hexdigest()[:16]


def idempotency_key(sig_id: str, action_type: str, target_ref: str) -> str:
    return hashlib.sha256(f"{sig_id}‖{action_type}‖{target_ref}".encode()).hexdigest()[:24]


class Signal(BaseModel):
    id: str
    source: Source
    external_id: str
    received_at: datetime

    # email-only
    reporter_email: str | None = None
    account_ref: str | None = None
    plan: str | None = None
    account_age_days: int | None = None
    subject: str | None = None
    body: str | None = None                      # UNTRUSTED
    thread_ref: str | None = None
    non_english: bool = False                    # policy: non-English signals escalate (README §7)

    # telemetry-only
    fingerprint: str | None = None
    service_tag: str | None = None               # authoritative when present
    stack_frames: list[str] | None = None        # UNTRUSTED (echoes user input)
    error_message: str | None = None             # UNTRUSTED
    release: str | None = None
    error_rate_delta: float | None = None
    affected_users: int | None = None

    def narrative(self) -> str:
        """Untrusted free text used for correlation and localization."""
        if self.source == "email":
            return f"Subject: {self.subject or ''}\n\n{self.body or ''}"
        frames = "\n".join(self.stack_frames or [])
        return f"{self.error_message or ''}\n{frames}"


class Ownership(BaseModel):
    team: str
    slack_channel: str
    oncall_user: str | None = None
    source: Literal["codeowners", "catalog"]
    metadata_age_days: int
    stale: bool = False


class Incident(BaseModel):
    id: str
    signals: list[Signal] = Field(default_factory=list)
    service: str | None = None                   # in catalog or None
    localization_provenance: Provenance = "unknown"
    localization_confidence: float = 0.0
    owner: Ownership | None = None
    priority: Priority = "P4"
    applied_rules: list[str] = Field(default_factory=list)
    opened_at: datetime
    paged: bool = False
    injection_flagged: bool = False
    resolved: bool = False              # sticky: set by any flagged signal, blocks AUTO for all
    possible_relations: list[str] = Field(default_factory=list)

    @property
    def distinct_reporting_accounts(self) -> int:
        return len({s.account_ref for s in self.signals if s.account_ref})

    @property
    def reporters(self) -> set[str]:
        return {s.reporter_email for s in self.signals if s.reporter_email}

    @property
    def telemetry(self) -> list[Signal]:
        return [s for s in self.signals if s.source == "telemetry"]

    @property
    def last_signal_at(self) -> datetime:
        return max(s.received_at for s in self.signals)


class Action(BaseModel):
    type: ActionType
    payload: dict
    idempotency_key: str
    status: Literal["pending", "done", "failed"] = "pending"


class ActionResult(BaseModel):
    action: Action
    ok: bool
    detail: str = ""


class DecisionRecord(BaseModel):
    """One row per signal. The unit of evaluation."""
    signal: Signal
    incident: Incident
    correlation_confidence: float
    correlation_decision: str                    # "new" | "merge:<id>" | "fingerprint:<id>"
    c_eff: float
    tier: Tier
    plan: list[Action]
    executed: list[ActionResult] = Field(default_factory=list)
    state_trace: list[str]
    latency_ms: dict[str, int]
    tokens: dict[str, dict[str, int]]
    cost_usd: float
    faults_observed: list[str] = Field(default_factory=list)
    injection_flag: bool = False
    run_id: str
