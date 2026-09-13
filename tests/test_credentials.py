"""The read/write credential split is asserted, not left to convention (README §6.1)."""
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "switchboard"


def test_decision_stages_never_reference_write_credentials():
    offenders = []
    for py in SRC.rglob("*.py"):
        # Entry points (demo, run) are allowed to construct the executor; decision stages are not.
        if "execute" in py.parts or py.name in ("demo.py", "run.py", "resolve.py"):
            continue
        text = py.read_text()
        if "WriteCredentials" in text or "from .execute" in text or "switchboard.execute" in text:
            offenders.append(str(py.relative_to(SRC)))
    assert offenders == [], f"decision-stage modules touch write credentials: {offenders}"


def test_no_vendor_sdk_outside_integrations_and_llm():
    offenders = []
    for py in SRC.rglob("*.py"):
        if py.name in ("llm.py",) or "integrations" in py.parts:
            continue
        text = py.read_text()
        if any(tok in text for tok in ("import slack_sdk", "import sentry_sdk", "googleapiclient", "import anthropic")):
            offenders.append(str(py.relative_to(SRC)))
    assert offenders == []
