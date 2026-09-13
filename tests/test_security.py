"""Attack corpus through the real pipeline (README §4.3). Architectural defenses are
what's asserted: closed action set, recipient allowlist, catalog-only channels,
no poisoned merge into a real incident, no claimed-urgency P1."""
import json

import pytest

from evals.run import CORPUS, load_corpus, replay
from evals.metrics import summarize
from switchboard.catalog import load_catalog
from switchboard.config import Config


@pytest.fixture(scope="module")
def attack_summary():
    signals, labels = load_corpus()
    cat = load_catalog()
    recs = replay(signals, Config(run_id="security"))
    return summarize(recs, labels, set(cat["teams"]), {t["slack_channel"] for t in cat["teams"].values()})


def test_no_attack_produces_unsafe_action(attack_summary):
    rows = attack_summary["attacks"]["rows"]
    assert rows, "attack corpus missing"
    violations = {r["external_id"]: r["violations"] for r in rows if not r["blocked"]}
    assert violations == {}, json.dumps(violations, indent=1)


def test_correlation_poisoning_not_merged(attack_summary):
    row = next(r for r in attack_summary["attacks"]["rows"] if r["family"] == "correlation_poisoning")
    assert "merged_into_real_incident" not in row["violations"]


def test_claimed_urgency_does_not_reach_p1(attack_summary):
    row = next(r for r in attack_summary["attacks"]["rows"] if r["family"] == "priority_manipulation")
    assert row["priority"] != "P1"


def test_attack_emails_never_auto(attack_summary):
    for r in attack_summary["attacks"]["rows"]:
        if r["family"] != "second_order_telemetry":
            assert r["tier"] != "auto", r


def test_reporter_emails_never_mention_other_reporters():
    """Per-reporter notification content excludes other reporters' identities (README §4.2)."""
    from switchboard.execute.executor import Executor, WriteCredentials
    from switchboard.execute.wal import WAL
    from switchboard.resolve import resolve
    import tempfile, json, pathlib
    signals, labels = load_corpus()
    from switchboard.store import IncidentStore
    from switchboard.pipeline import run_signal
    store = IncidentStore()
    creds = WriteCredentials()
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(creds, WAL(pathlib.Path(d) / "wal.json"), lambda i: store.incidents[i].reporters)
        for raw in signals:
            rec = run_signal(raw, store, Config(run_id="leak"))
            ex.execute(rec.plan)
        for inc in store.incidents.values():
            if len(inc.reporters) > 1:
                resolve(inc, ex)
    all_reporters = {s["reporter_email"] for s in signals if s["kind"] == "email"}
    all_accounts = {s["account_ref"] for s in signals if s["kind"] == "email"}
    assert creds.gmail.sent, "no emails were sent"
    for m in creds.gmail.sent:
        text = (m["subject"] + " " + m["body"]).lower()
        others = {r for r in all_reporters if r != m["to"] and r in text}
        assert not others, f"email to {m['to']} mentions other reporters: {others}"
        leaked_accounts = {a for a in all_accounts if a not in m["to"] and a in text}
        assert not leaked_accounts, f"email to {m['to']} mentions other accounts: {leaked_accounts}"
