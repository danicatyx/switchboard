"""Losing Sentry must push every email signal out of AUTO (README §5, fault behavior)."""
from evals.run import load_corpus, replay
from switchboard.config import Config

from .conftest import needs_api

pytestmark = needs_api


def test_withholding_telemetry_demotes_every_email():
    signals, labels = load_corpus()
    recs = replay(signals, Config(run_id="chaos", telemetry_available=False))
    emails = [r for r in recs if r["signal"]["source"] == "email"]
    assert emails
    auto = [r["signal"]["external_id"] for r in emails if r["tier"] == "auto"]
    assert auto == [], f"emails still AUTO without telemetry: {auto}"
    assert all("telemetry_unavailable" in r["faults_observed"] or r["signal"]["source"] == "email" for r in recs)
    # No signal dropped: every email in the corpus produced a record.
    assert len(emails) == sum(1 for s in signals if s["kind"] == "email")
