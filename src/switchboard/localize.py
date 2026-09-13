"""Localization and cross-source grounding (README §3.4). The core mechanism.

If the incident carries any telemetry signal, the service is read from the
instrumentation tag: deterministic, c=0.98, provenance grounded:telemetry.
Otherwise the model selects from the live enum or returns unknown. Hallucinated
services are a schema failure, not a coerced value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, create_model

from .catalog import deploys_near, service_names
from .config import Config
from .llm import SchemaFailure, Usage, call
from .models import Incident, Priority, Signal
from .prompts import LOCALIZE_SYSTEM, localize_user

GROUNDED_CONFIDENCE = 0.98


def _localize_schema() -> type[BaseModel]:
    names = tuple(service_names()) + ("unknown",)
    return create_model(
        "LocalizeOut",
        service=(Literal[names], ...),           # type: ignore[valid-type]
        confidence=(float, Field(ge=0.0, le=1.0)),
        evidence=(str, ...),
        proposed_priority=(Priority, ...),
        injection_suspected=(bool, False),
    )


LocalizeOut = _localize_schema()


@dataclass
class LocalizationResult:
    service: str | None
    confidence: float
    provenance: str
    proposed_priority: Priority
    evidence: str
    injection_suspected: bool
    usage: Usage
    schema_failed: bool = False


def _base_priority_from_telemetry(signal: Signal) -> Priority:
    """Base from affected users only. The error-rate delta belongs to the rule
    layer (`error_rate_spike`); using it here too would count it twice."""
    users = signal.affected_users or 0
    if users >= 1000:
        return "P2"
    if users >= 50:
        return "P3"
    return "P4"


def localize(inc: Incident, signal: Signal, cfg: Config) -> LocalizationResult:
    usage = Usage()

    # Grounded path. Telemetry present ⇒ inherit the instrumentation's attribution.
    tel = [s for s in inc.telemetry if cfg.telemetry_available]
    if tel:
        src = tel[0]
        return LocalizationResult(
            service=src.service_tag,
            confidence=GROUNDED_CONFIDENCE,
            provenance="grounded:telemetry",
            proposed_priority=_base_priority_from_telemetry(src),
            evidence=f"service_tag from {src.external_id}",
            injection_suspected=False,
            usage=usage,
        )

    # Inferred path. Model selects from the enum or abstains.
    try:
        out, u = call(LocalizeOut, LOCALIZE_SYSTEM, localize_user(inc, signal),
                      hint={"incident": inc, "signal": signal, "deploys": deploys_near(signal.received_at, 24)})
        usage.add(u)
    except SchemaFailure as e:
        return LocalizationResult(None, 0.0, "unknown", "P4", f"schema failure: {e}", False, usage, schema_failed=True)

    if out.service == "unknown":
        return LocalizationResult(None, out.confidence, "unknown", out.proposed_priority, out.evidence, out.injection_suspected, usage)
    return LocalizationResult(out.service, out.confidence, "inferred:model", out.proposed_priority, out.evidence, out.injection_suspected, usage)
