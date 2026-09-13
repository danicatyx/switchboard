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

    # Deterministic shortcut: a reply in an existing thread. Guarded by reporter
    # identity, because In-Reply-To is attacker-controlled: a stranger replying
    # into a thread is a candidate like any other, never an automatic merge.
    if signal.source == "email" and signal.thread_ref and signal.thread_ref != f"thr-{signal.external_id}":
        hit = store.by_thread(signal.thread_ref, signal.received_at)
        if hit is not None and signal.reporter_email in hit.reporters and not (cfg.ablate == "grounding" and hit.telemetry):
            inc = store.merge(signal, hit.id)
            return CorrelationResult(inc, f"thread:{hit.id}", 0.97, None, False, usage)

    # Grounding ablation: emails never see telemetry-backed incidents as candidates.
    exclude_tel = cfg.ablate == "grounding" and signal.source == "email"
    candidates = store.open_within(signal.received_at, exclude_telemetry_backed=exclude_tel)
    candidates = sorted(candidates, key=lambda i: i.last_signal_at, reverse=True)[: cfg.max_candidates]

    if not candidates:
        inc = store.create(signal)
        return CorrelationResult(inc, "new", 1.0, None, False, usage)

    try:
        out, u = call(CorrelateOut, CORRELATE_SYSTEM, correlate_user(signal, candidates),
                      hint={"signal": signal, "candidates": candidates})
        usage.add(u)
    except SchemaFailure:
        inc = store.create(signal)
        return CorrelationResult(inc, "new", 0.0, None, False, usage, schema_failed=True)

    valid_ids = {c.id for c in candidates}
    if out.match != "new" and out.match not in valid_ids:
        # A candidate id the model was not offered. Hard failure, never coerced.
        inc = store.create(signal)
        return CorrelationResult(inc, "new", 0.0, None, out.injection_suspected, usage, schema_failed=True)

    # A signal that reads as an instruction never merges: merging grants it the
    # incident's notification stream, which is what correlation poisoning wants.
    if out.match != "new" and out.confidence >= cfg.merge_threshold and not out.injection_suspected:
        inc = store.merge(signal, out.match)
        return CorrelationResult(inc, f"merge:{out.match}", out.confidence, None, out.injection_suspected, usage)

    inc = store.create(signal)
    relation = out.match if (out.match != "new" and out.confidence >= cfg.relation_threshold) else None
    if relation:
        inc.possible_relations.append(relation)
    # Confidence that creating a new incident was right. A rejected match at
    # confidence c argues against "new" with weight c, halved because a false
    # split costs a minute while a false merge costs hours (README §1.2).
    c_new = out.confidence if out.match == "new" else 1.0 - 0.5 * out.confidence
    return CorrelationResult(inc, "new", c_new, relation, out.injection_suspected, usage)
