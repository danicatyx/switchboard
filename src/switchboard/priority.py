"""Priority from blast radius (README §3.6).

The model proposes a base priority; this ordered, logged rule layer adjusts it
using correlated evidence. Conditions are implemented here by rule id and the
YAML carries order, action, and rationale, so the layer is auditable and
ablatable without touching a prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import yaml

from .catalog import _DEFAULT_FIXTURES as FIXTURES, service as catalog_service
from .models import Incident, Priority, Signal
from .store import IncidentStore

_ORDER: list[Priority] = ["P1", "P2", "P3", "P4"]


def _idx(p: Priority) -> int:
    return _ORDER.index(p)


@lru_cache(maxsize=1)
def load_rules() -> list[dict]:
    with open(FIXTURES / "priority_rules.yaml") as f:
        return yaml.safe_load(f)["priority_rules"]


@dataclass
class Ctx:
    inc: Incident
    signal: Signal
    store: IncidentStore
    service: str | None
    provenance: str


def _tel_delta(ctx: Ctx) -> float:
    return max((s.error_rate_delta or 0.0) for s in ctx.inc.telemetry) if ctx.inc.telemetry else 0.0


CONDITIONS: dict[str, Callable[[Ctx], bool]] = {
    "multi_account_blast": lambda c: c.inc.distinct_reporting_accounts >= 3,
    "error_rate_spike": lambda c: _tel_delta(c) > 5.0,
    "critical_path": lambda c: bool(c.service) and (catalog_service(c.service) or {}).get("tier") == "tier-0",
    "recurrence": lambda c: c.store.similar_within_days(c.service, c.inc.opened_at, 30, exclude=c.inc.id),
    "single_free_reporter": lambda c: (len(c.inc.signals) == 1 and c.signal.source == "email"
                                       and c.signal.plan == "free" and (c.signal.account_age_days or 999) < 7),
    "ungrounded_localization": lambda c: c.provenance == "inferred:model",
}


@dataclass
class PriorityResult:
    priority: Priority
    applied_rules: list[str]
    confidence_cap: float | None      # from cap_confidence(x)
    c_pi: float


def apply_rules(base: Priority, ctx: Ctx) -> PriorityResult:
    p = _idx(base)
    applied: list[str] = []
    cap_conf: float | None = None
    blast_rule_fired = False
    for rule in load_rules():
        rid = rule["id"]
        if not CONDITIONS[rid](ctx):
            continue
        action = rule["then"]
        if action.startswith("escalate("):
            n = int(action[9:-1])
            p = max(0, p - n)
            blast_rule_fired = True
        elif action.startswith("cap_at("):
            floor = _idx(action[7:-1])
            p = max(p, floor)
        elif action.startswith("cap_confidence("):
            cap_conf = float(action[15:-1])
        applied.append(rid)
    # c_π: rules over measured blast radius add certainty; a bare model proposal has less.
    c_pi = 0.95 if blast_rule_fired else 0.90
    return PriorityResult(_ORDER[p], applied, cap_conf, c_pi)
