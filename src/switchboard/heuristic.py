"""Zero-cost stand-in for the model stages.

Selected when SWITCHBOARD_MODEL=heuristic (the default if no API key is set).
Emits the same schemas as the model from lexicon overlap against the catalog,
deploy recency, and time proximity. It is deliberately weak: its purpose is to
let the architecture (grounding, lookup, gating, executor) be measured without
spend, not to stand in for model quality. Every number produced under this
backend is labeled as such in the brief.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from .catalog import load_catalog, service_names

_STOP = set("the a an and or of to in on for is it its this that we our i my me you your be been was were are have has had do does did not no can can't cannot with as at by from but if so just when since about there here they them their he she his her will would could should".split())

_INJECTION = re.compile(
    r"ignore (all )?(previous|prior) instructions|system override|system:|maintenance mode|you are now|"
    r"page (all|every) |post (to|the full)|#[a-z-]+team|#all-hands|cc [a-z0-9.@-]+|"
    r"send_email|send (a |the )?resolution|resolution email|other (affected )?customers|add me to|"
    r"this is (the )?cto|i am authorizing|do not escalate|mark (this )?(as )?p[01]|escalate to p1|"
    r"decode and follow|[A-Za-z0-9+/]{40,}={0,2}|\bp0\b|sev-0",
    re.IGNORECASE,
)

_P1 = re.compile(r"charged twice|two times|taken from|double|nobody|entire team|whole team|60 people|every user|all users|can't get in|locked out|cannot complete|urgent", re.I)
_P2 = re.compile(r"fail|error|doesn't work|not working|never|won't|can't|cannot|broken|corrupt|wrong|didn't|haven't|hasn't|no longer|stopped|not received", re.I)
_P3 = re.compile(r"looks|order|slow|annoying|weird|off\b|stale|behind|different|confus", re.I)
_P4 = re.compile(r"is there a way|how do i|please delete|update our|question|can we get|\?\s*$", re.I)


def _lex() -> dict[str, list[str]]:
    return load_catalog().get("symptoms", {})


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9'-]+", text.lower()) if w not in _STOP and len(w) > 2}


def lexicon_score(text: str, service: str) -> float:
    t = text.lower()
    return float(sum(1.5 if " " in term else 1.0 for term in _lex().get(service, []) if term in t))


def injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


def proposed_priority(text: str) -> str:
    if _P4.search(text) and not _P2.search(text):
        return "P4"
    if _P1.search(text):
        return "P1"
    if _P2.search(text):
        return "P2"
    if _P3.search(text):
        return "P3"
    return "P3"


# ---------------------------------------------------------------------------

def description_score(text: str, service: str) -> float:
    """Word overlap between the narrative and the catalog description + service name.
    Deliberately does NOT use the symptom lexicon: descriptions predate the corpus,
    so this is the leakage-free weak localizer."""
    svc = load_catalog()["services"][service]
    desc_words = _words(svc["description"]) | set(service.split("-"))
    tw = _words(text)
    # crude stemming so "exports"/"export", "uploads"/"upload" meet
    stem = lambda w: w.rstrip("s") if len(w) > 4 else w
    return float(len({stem(w) for w in tw} & {stem(w) for w in desc_words}))


def localize(hint: dict[str, Any]) -> dict:
    signal = hint["signal"]
    deploys = hint.get("deploys", [])
    text = signal.narrative()
    recent = {d["service"] for d in deploys}
    scores = {s: description_score(text, s) + (1.0 if s in recent else 0.0) for s in service_names()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, b), (second, s2) = ranked[0], ranked[1]
    margin = b - s2
    if b < 2.0 or margin < 1.0:
        return dict(service="unknown", confidence=round(min(0.5, 0.2 + b * 0.08), 2),
                    evidence=f"no dominant surface (best {best}={b:.1f}, next {second}={s2:.1f})",
                    proposed_priority=proposed_priority(text), injection_suspected=injection(text))
    conf = round(min(0.92, 0.5 + 0.1 * margin + 0.04 * b), 2)
    return dict(service=best, confidence=conf,
                evidence=f"description overlap {b:.1f} vs {second} {s2:.1f}" + (f"; deploy on {best} in window" if best in recent else ""),
                proposed_priority=proposed_priority(text), injection_suspected=injection(text))


def _decay(minutes: float) -> float:
    if minutes <= 120:
        return 1.0
    if minutes <= 360:
        return 0.8
    if minutes <= 720:
        return 0.55
    return 0.35


def correlate(hint: dict[str, Any]) -> dict:
    signal = hint["signal"]
    candidates = hint["candidates"]
    text = signal.narrative()
    sw = _words(text)
    best_id, best_score, best_why = "new", 0.0, ""
    for c in candidates:
        mins = (signal.received_at - c.last_signal_at).total_seconds() / 60
        first_text = c.signals[0].narrative()
        cw = _words(first_text)
        jacc = len(sw & cw) / max(1, len(sw | cw))
        if signal.source == "telemetry":
            svc = 1.0 if (c.service and signal.service_tag == c.service) else 0.0
            score = _decay(mins) * (0.75 * svc + 0.25 * min(1.0, jacc * 5))
            why = f"service_tag {'matches' if svc else 'differs'}"
        else:
            lex = lexicon_score(text, c.service) if c.service else 0.0
            lex_n = min(1.0, lex / 3.0)
            text_n = min(1.0, jacc * 4)
            if c.telemetry:
                # Candidate's service is an instrumentation fact: lexicon fit is strong evidence.
                score = _decay(mins) * (0.85 * lex_n + 0.15 * text_n)
            elif c.service:
                # Candidate's service is itself a guess: lean more on text overlap.
                score = _decay(mins) * (0.6 * lex_n + 0.4 * text_n)
            else:
                score = _decay(mins) * 0.9 * text_n
            why = f"lexicon {lex:.1f} on {c.service or 'unknown'}, overlap {jacc:.2f}, {int(mins)}m"
        if score > best_score:
            best_id, best_score, best_why = c.id, score, why
    inj = injection(text)
    if best_score < 0.35:
        return dict(match="new", confidence=round(min(0.95, 1.0 - best_score), 2), reason=f"no candidate above floor ({best_why})", injection_suspected=inj)
    return dict(match=best_id, confidence=round(min(0.96, best_score), 2), reason=best_why, injection_suspected=inj)


def team_guess(hint: dict[str, Any]) -> dict:
    """Ownership ablation: guess a team from text. Deliberately naive."""
    text = hint["signal"].narrative().lower()
    guesses = [
        (re.compile(r"charge|card|invoice|billing|plan|seat|payment"), "payments"),
        (re.compile(r"log ?in|sign ?in|password|code|locked|sso|2fa|session"), "identity"),
        (re.compile(r"app|phone|iphone|android|browser|page|screen|notification|alert"), "client-apps"),
        (re.compile(r"export|report|search|schedule|csv|download"), "data-platform"),
        (re.compile(r"upload|attach|file|storage|numbers|figures"), "platform"),   # 'platform' is not a catalog team
    ]
    for rx, team in guesses:
        if rx.search(text):
            return dict(team=team)
    return dict(team="support-engineering")


def answer(schema: type[BaseModel], hint: dict[str, Any] | None) -> BaseModel:
    if hint is None:
        raise RuntimeError(f"heuristic backend needs a hint for {schema.__name__}")
    name = schema.__name__
    if name == "CorrelateOut":
        return schema(**correlate(hint))
    if name == "LocalizeOut":
        return schema(**localize(hint))
    if name == "TeamGuess":
        return schema(**team_guess(hint))
    raise RuntimeError(f"heuristic backend has no answer for {name}")
