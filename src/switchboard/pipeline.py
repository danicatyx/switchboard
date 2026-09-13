"""run_signal: the StateFlow path for one signal.

NORMALIZE → CORRELATE → LOCALIZE → OWNERSHIP → PRIORITY → GATE → PLAN.
Each stage appends to state_trace. Backward transitions in this build are the
one schema-validation retry inside llm.call; a second failure is ESCALATE.
"""

from __future__ import annotations

import time

from pydantic import BaseModel

from .catalog import team as catalog_team
from .config import Config
from .correlate import correlate
from .gate import gate
from .llm import SchemaFailure, Usage, call
from .localize import localize
from .models import DecisionRecord, Signal
from .normalize import normalize
from .ownership import own
from .plan import build_plan
from .priority import Ctx, apply_rules
from .prompts import OWNERSHIP_ABLATION_SYSTEM, ownership_ablation_user
from .store import IncidentStore


class TeamGuess(BaseModel):
    team: str


class _Clock:
    def __init__(self) -> None:
        self.t = time.perf_counter()
        self.ms: dict[str, int] = {}

    def lap(self, stage: str) -> None:
        now = time.perf_counter()
        self.ms[stage] = int((now - self.t) * 1000)
        self.t = now


def run_signal(raw: dict, store: IncidentStore, cfg: Config) -> DecisionRecord:
    trace: list[str] = []
    clock = _Clock()
    tokens: dict[str, dict[str, int]] = {}
    total = Usage()
    faults: list[str] = list(cfg.faults)

    def record(stage: str, u: Usage) -> None:
        tokens[stage] = {"input": u.input_tokens, "output": u.output_tokens}
        total.add(u)

    # NORMALIZE
    signal: Signal = normalize(raw)
    trace.append("NORMALIZE")
    clock.lap("normalize")

    if signal.source == "telemetry" and not cfg.telemetry_available:
        faults.append("telemetry_unavailable")

    # CORRELATE
    corr = correlate(signal, store, cfg)
    inc = corr.incident
    record("correlate", corr.usage)
    trace.append(f"CORRELATE:{corr.decision}" + (f"~{corr.possible_relation}" if corr.possible_relation else ""))
    clock.lap("correlate")

    # LOCALIZE
    loc = localize(inc, signal, cfg)
    record("localize", loc.usage)
    if inc.service is None or loc.provenance == "grounded:telemetry":
        # A merged signal keeps the incident's attribution unless grounding upgrades it.
        inc.service = loc.service
        inc.localization_provenance = loc.provenance  # type: ignore[assignment]
        inc.localization_confidence = loc.confidence
    trace.append(f"LOCALIZE:{inc.localization_provenance}:{inc.service or 'unknown'}")
    clock.lap("localize")

    # OWNERSHIP (lookup; or the ablation's model guess)
    if cfg.ablate == "ownership" and inc.service is not None:
        try:
            guess, u = call(TeamGuess, OWNERSHIP_ABLATION_SYSTEM, ownership_ablation_user(signal), hint={"signal": signal})
            record("ownership_ablation", u)
            t = catalog_team(guess.team.strip().lower())
            if t:
                from .models import Ownership
                inc.owner = Ownership(team=guess.team.strip().lower(), slack_channel=t["slack_channel"],
                                      oncall_user=t.get("oncall_user"), source="catalog", metadata_age_days=0)
                trace.append(f"OWNERSHIP:guessed:{inc.owner.team}")
            else:
                inc.owner = None
                trace.append(f"OWNERSHIP:guessed:NONEXISTENT:{guess.team}")
        except SchemaFailure:
            inc.owner = None
            trace.append("OWNERSHIP:guess_failed")
    else:
        inc.owner = own(inc.service)
        trace.append("OWNERSHIP:" + (f"ok:{inc.owner.team}" + (":stale" if inc.owner.stale else "") if inc.owner else "none"))
    clock.lap("ownership")

    # PRIORITY
    ctx = Ctx(inc=inc, signal=signal, store=store, service=inc.service, provenance=inc.localization_provenance)
    pr = apply_rules(loc.proposed_priority, ctx)
    inc.priority = pr.priority
    inc.applied_rules = pr.applied_rules
    trace.append(f"PRIORITY:{loc.proposed_priority}->{pr.priority}[{','.join(pr.applied_rules)}]")
    clock.lap("priority")

    # GATE
    injection = corr.injection_suspected or loc.injection_suspected
    degradations = [cfg.degradation_telemetry] if (not cfg.telemetry_available and signal.source == "email") else []
    g = gate(c_corr=corr.confidence, c_loc=inc.localization_confidence, c_pi=pr.c_pi, confidence_cap=pr.confidence_cap,
             service=inc.service if inc.owner is not None else None, injection_flag=injection,
             schema_failed=corr.schema_failed or loc.schema_failed, degradations=degradations, cfg=cfg)
    trace.append(f"GATE:{g.tier}:{g.c_eff}")
    clock.lap("gate")

    # PLAN
    plan = build_plan(signal, inc, g.tier, corr.decision, g.c_eff, g.reasons)
    if g.tier == "auto" and any(a.type == "post_slack" for a in plan):
        inc.paged = True
    trace.append(f"PLAN:{len(plan)}")
    clock.lap("plan")

    return DecisionRecord(
        signal=signal, incident=inc,
        correlation_confidence=corr.confidence, correlation_decision=corr.decision,
        c_eff=g.c_eff, tier=g.tier, plan=plan, state_trace=trace,
        latency_ms=clock.ms, tokens=tokens, cost_usd=round(total.cost_usd, 5),
        faults_observed=faults, injection_flag=injection, run_id=cfg.run_id,
    )
