from switchboard.config import Config
from switchboard.gate import gate

C = Config()


def g(**kw):
    base = dict(c_corr=0.95, c_loc=0.98, c_pi=0.95, confidence_cap=None, service="auth-service",
                injection_flag=False, schema_failed=False, degradations=[], cfg=C)
    base.update(kw)
    return gate(**base)


def test_auto_when_all_high():
    assert g().tier == "auto"


def test_min_not_product():
    r = g(c_corr=0.9, c_loc=0.9, c_pi=0.9)
    assert r.c_eff == 0.9 and r.tier == "auto"


def test_ungrounded_cap_pushes_to_propose():
    r = g(c_loc=0.95, confidence_cap=0.70)
    assert r.c_eff == 0.70 and r.tier == "propose"


def test_unknown_service_escalates_regardless_of_confidence():
    assert g(service=None).tier == "escalate"


def test_injection_escalates():
    assert g(injection_flag=True).tier == "escalate"


def test_degradation_blocks_auto():
    r = g(degradations=[0.15])
    assert r.tier == "propose" and r.c_eff < 0.85


def test_low_confidence_escalates():
    assert g(c_corr=0.5).tier == "escalate"
