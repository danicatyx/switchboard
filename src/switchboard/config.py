from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Config:
    run_id: str = "dev"
    ablate: Literal["grounding", "ownership"] | None = None
    telemetry_available: bool = True       # False simulates losing Sentry (chaos test)
    tau_auto: float = 0.85
    tau_prop: float = 0.60
    merge_threshold: float = 0.85
    relation_threshold: float = 0.60
    degradation_telemetry: float = 0.15    # δ applied when telemetry enrichment is unavailable
    max_candidates: int = 10
    faults: list[str] = field(default_factory=list)
