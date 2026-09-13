from switchboard.execute.executor import Executor, WriteCredentials
from switchboard.execute.wal import WAL
from switchboard.models import Action, idempotency_key


def make(tmp_path, reporters):
    w = WriteCredentials()
    ex = Executor(w, WAL(tmp_path / "wal.json"), lambda inc: reporters)
    return ex, w


def test_email_to_non_reporter_is_blocked(tmp_path):
    ex, w = make(tmp_path, {"a@x.com"})
    a = Action(type="send_email_ack", payload={"to": "evil@y.com", "incident_id": "SB-001", "subject": "x"}, idempotency_key="k1")
    r = ex.execute([a])
    assert r[0].ok is False and "allowlist" in r[0].detail
    assert w.gmail.sent == []


def test_slack_to_unknown_channel_is_blocked(tmp_path):
    ex, w = make(tmp_path, set())
    a = Action(type="post_slack", payload={"channel": "#exec-team", "priority": "P1"}, idempotency_key="k2")
    r = ex.execute([a])
    assert r[0].ok is False and w.slack.posted == []


def test_idempotent_retry_does_not_double_send(tmp_path):
    ex, w = make(tmp_path, {"a@x.com"})
    a = Action(type="send_email_ack", payload={"to": "a@x.com", "incident_id": "SB-001", "subject": "x"}, idempotency_key=idempotency_key("s", "send_email_ack", "a@x.com"))
    ex.execute([a])
    ex.execute([a])   # crash-then-retry
    assert len(w.gmail.sent) == 1


def test_wal_resume_picks_up_pending(tmp_path):
    wal = WAL(tmp_path / "wal.json")
    a = Action(type="post_slack", payload={"channel": "#identity-oncall"}, idempotency_key="k3")
    wal.append([a])
    wal2 = WAL(tmp_path / "wal.json")
    assert [p.idempotency_key for p in wal2.pending()] == ["k3"]
