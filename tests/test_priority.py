from datetime import datetime, timezone

from switchboard.models import Incident, Signal
from switchboard.priority import Ctx, apply_rules
from switchboard.store import IncidentStore

TS = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)


def email(i, account, plan="pro", age=500):
    return Signal(id=f"e{i}", source="email", external_id=f"e{i}", received_at=TS, reporter_email=f"u{i}@{account}.com",
                  account_ref=account, plan=plan, account_age_days=age, subject="x", body="y")


def tel(delta):
    return Signal(id="t1", source="telemetry", external_id="t1", received_at=TS, fingerprint="fp", service_tag="auth-service",
                  error_rate_delta=delta, affected_users=10)


def ctx(signals, service, provenance):
    inc = Incident(id="I", signals=signals, opened_at=TS, service=service, localization_provenance=provenance)
    return Ctx(inc=inc, signal=signals[-1], store=IncidentStore(), service=service, provenance=provenance)


def test_multi_account_blast_escalates():
    r = apply_rules("P3", ctx([email(1, "a"), email(2, "b"), email(3, "c")], "reports-api", "inferred:model"))
    assert r.priority == "P2" and "multi_account_blast" in r.applied_rules


def test_tier0_and_spike_stack():
    r = apply_rules("P3", ctx([tel(8.0)], "auth-service", "grounded:telemetry"))
    assert r.priority == "P1"
    assert r.applied_rules == ["error_rate_spike", "critical_path"]
    assert r.confidence_cap is None


def test_single_free_new_reporter_capped_even_if_urgent():
    r = apply_rules("P1", ctx([email(1, "fresh", plan="free", age=2)], "web-bff", "inferred:model"))
    assert r.priority == "P3"
    assert "single_free_reporter" in r.applied_rules


def test_ungrounded_caps_confidence_not_priority():
    r = apply_rules("P2", ctx([email(1, "a")], "reports-api", "inferred:model"))
    assert r.priority == "P2"
    assert r.confidence_cap == 0.70


def test_grounded_has_no_confidence_cap():
    r = apply_rules("P2", ctx([tel(1.0), email(1, "a")], "auth-service", "grounded:telemetry"))
    assert r.confidence_cap is None
