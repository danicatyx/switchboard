"""Both sources collapse into one Signal (README §3.2). Deterministic."""

from __future__ import annotations

import re
from datetime import datetime

from .models import Signal, signal_id

_QUOTED_HEADER = re.compile(r"^On .{5,120} wrote:\s*$", re.MULTILINE)
_SIG_MARKER = re.compile(r"^--\s*$", re.MULTILINE)
_SENT_FROM = re.compile(r"^Sent from my .*$", re.MULTILINE | re.IGNORECASE)


_EN = set("the a an and or of to in on for is it its this that we our i my me you your be are was were have has had do does did not no can with as at by from but if so just when since about there here they them their will would could should please thanks hi hello".split())


def looks_non_english(text: str) -> bool:
    """Crude guard: too few common English function words among the tokens.
    Short texts are assumed English (not enough evidence to escalate on)."""
    words = re.findall(r"[a-záéíóúñüçàèìòùâêîôûäöß']+", (text or "").lower())
    if len(words) < 12:
        return False
    return sum(1 for w in words if w in _EN) / len(words) < 0.08


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def strip_email_body(body: str) -> str:
    """Drop quoted replies and signatures; keep the author's own text."""
    text = body or ""
    m = _QUOTED_HEADER.search(text)
    if m:
        text = text[: m.start()]
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))
    m = _SIG_MARKER.search(text)
    if m:
        text = text[: m.start()]
    text = _SENT_FROM.sub("", text)
    return text.strip()


def from_email(raw: dict) -> Signal:
    return Signal(
        id=signal_id("email", raw["external_id"]),
        source="email",
        external_id=raw["external_id"],
        received_at=_ts(raw["received_at"]),
        reporter_email=raw["reporter_email"],
        account_ref=raw.get("account_ref"),
        plan=raw.get("plan"),
        account_age_days=raw.get("account_age_days"),
        subject=raw.get("subject"),
        body=strip_email_body(raw.get("body", "")),
        thread_ref=raw.get("thread_ref"),
        non_english=looks_non_english(strip_email_body(raw.get("body", ""))),
    )


def from_telemetry(raw: dict) -> Signal:
    return Signal(
        id=signal_id("telemetry", raw["external_id"]),
        source="telemetry",
        external_id=raw["external_id"],
        received_at=_ts(raw["received_at"]),
        fingerprint=raw["fingerprint"],
        service_tag=raw["service_tag"],
        stack_frames=list(raw.get("stack_frames", []))[:5],
        error_message=raw.get("error_message"),
        release=raw.get("release"),
        error_rate_delta=raw.get("error_rate_delta"),
        affected_users=raw.get("affected_users"),
    )


def normalize(raw: dict) -> Signal:
    kind = raw.get("kind")
    if kind == "email":
        return from_email(raw)
    if kind == "telemetry":
        return from_telemetry(raw)
    raise ValueError(f"unknown signal kind: {kind!r}")
