"""Confidence aggregation and gating (README §3.7).

c_eff = min(c_ι, c_λ, c_π) · Π(1 − δ_j). Minimum, not product: the stages are
not independent and a product systematically under-reports.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .models import Tier


@dataclass
class GateResult:
    c_eff: float
    tier: Tier
    reasons: list[str]


def gate(*, c_corr: float, c_loc: float, c_pi: float, confidence_cap: float | None, service: str | None,
         injection_flag: bool, schema_failed: bool, degradations: list[float], cfg: Config,
         non_english: bool = False) -> GateResult:
    if confidence_cap is not None:
        c_loc = min(c_loc, confidence_cap)
    c_eff = min(c_corr, c_loc, c_pi)
    for d in degradations:
        c_eff *= (1.0 - d)
    c_eff = round(c_eff, 4)

    reasons: list[str] = []
    if service is None:
        reasons.append("service=unknown")
    if injection_flag:
        reasons.append("injection_flagged")
    if schema_failed:
        reasons.append("schema_failure")
    if non_english:
        reasons.append("non_english_policy")
    if reasons:
        return GateResult(c_eff, "escalate", reasons)

    if c_eff >= cfg.tau_auto and not degradations:
        return GateResult(c_eff, "auto", ["c_eff>=tau_auto"])
    if c_eff >= cfg.tau_prop:
        reasons.append("degraded" if degradations and c_eff >= cfg.tau_auto else "tau_prop<=c_eff<tau_auto")
        return GateResult(c_eff, "propose", reasons)
    return GateResult(c_eff, "escalate", ["c_eff<tau_prop"])
