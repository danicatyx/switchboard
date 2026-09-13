"""Correlation runs before any routing decision (README §3.3).

Candidates: all open incidents within 24h (retrieval is trivial at corpus scale;
BM25/dense/RRF are noted as cut in docs/PLAN.md). Telemetry gets a deterministic
fingerprint shortcut. Judgment is one structured LLM call with asymmetric
thresholds because a false merge costs hours and a false split costs a minute.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from .config import Config
from .llm import SchemaFailure, Usage, call
from .models import Incident, Signal
from .prompts import CORRELATE_SYSTEM, correlate_user
from .store import IncidentStore


class CorrelateOut(BaseModel):
    match: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    injection_suspected: bool = False


@dataclass
class CorrelationResult:
    incident: Incident
    decision: str                # "new" | "merge:<id>" | "fingerprint:<id>"
    confidence: float
    possible_relation: str | None
    injection_suspected: bool
    usage: Usage
    schema_failed: bool = False


def correlate(signal: Signal, store: IncidentStore, cfg: Config) -> CorrelationResult:
    usage = Usage()

    # Deterministic shortcut: fingerprint equality. No model call.
    if signal.source == "telemetry" and signal.fingerprint:
        hit = store.by_fingerprint(signal.fingerprint, signal.received_at)
        if hit is not None:
            inc = store.merge(signal, hit.id)
            return CorrelationResult(inc, f"fingerprint:{hit.id}", 0.99, None, False, usage)

    # Grounding ablation: emails never see telemetry-backed incidents as candidates.
    exclude_tel = cfg.ablate == "grounding" and signal.source == "email"
    candidates = store.open_within(signal.received_at, exclude_telemetry_backed=exclude_tel)
    candidates = sorted(candidates, key=lambda i: i.last_signal_at, reverse=True)[: cfg.max_candidates]

    if not candidates:
        inc = store.create(signal)
        return CorrelationResult(inc, "new", 1.0, None, False, usage)

    try:
        out, u = call(CorrelateOut, CORRELATE_SYSTEM, correlate_user(signal, candidates))
        usage.add(u)
    except SchemaFailure:
        inc = store.create(signal)
        return CorrelationResult(inc, "new", 0.0, None, False, usage, schema_failed=True)

    valid_ids = {c.id for c in candidates}
    if out.match != "new" and out.match not in valid_ids:
        # A candidate id the model was not offered. Hard failure, never coerced.
        inc = store.create(signal)
        return CorrelationResult(inc, "new", 0.0, None, out.injection_suspected, usage, schema_failed=True)

    if out.match != "new" and out.confidence >= cfg.merge_threshold:
        inc = store.merge(signal, out.match)
        return CorrelationResult(inc, f"merge:{out.match}", out.confidence, None, out.injection_suspected, usage)

    inc = store.create(signal)
    relation = out.match if (out.match != "new" and out.confidence >= cfg.relation_threshold) else None
    if relation:
        inc.possible_relations.append(relation)
    # Confidence that this is *new* is the complement of the best rejected match.
    c_new = out.confidence if out.match == "new" else 1.0 - out.confidence
    return CorrelationResult(inc, "new", c_new, relation, out.injection_suspected, usage)
