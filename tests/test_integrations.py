"""Offline tests for the real adapters: parsing and selection, no network."""
import email
from email.message import EmailMessage

from switchboard.execute.executor import WriteCredentials
from switchboard.integrations.email import ImapInbox, SmtpSender, parse_message
from switchboard.integrations.fakes import FakeGmail, FakeSlack
from switchboard.integrations.github import GitHubAdapter
from switchboard.integrations.slack import SlackAdapter
from switchboard.normalize import normalize


def test_parse_multipart_email_to_signal(monkeypatch):
    msg = EmailMessage()
    msg["From"] = "Dana Whitfield <dana@acme-corp.com>"
    msg["To"] = "support@example.com"
    msg["Subject"] = "Nothing has come through"
    msg["Date"] = "Thu, 11 Sep 2026 06:09:36 +0000"
    msg["Message-ID"] = "<abc123@acme-corp.com>"
    msg["In-Reply-To"] = "<thread0@acme-corp.com>"
    msg.set_content("The spinner keeps going.\n\nDana\n\nOn Thu, Sep 11, 2026 at 7:12 AM Tom wrote:\n> old")
    msg.add_alternative("<p>The spinner keeps going.</p>", subtype="html")
    raw = parse_message(email.message_from_bytes(bytes(msg)))
    assert raw["kind"] == "email"
    assert raw["external_id"] == "abc123@acme-corp.com"
    assert raw["reporter_email"] == "dana@acme-corp.com"
    assert raw["account_ref"] == "acme-corp"
    assert raw["thread_ref"] == "thread0@acme-corp.com"
    assert raw["received_at"] == "2026-09-11T06:09:36Z"
    sig = normalize(raw)
    assert sig.body == "The spinner keeps going.\n\nDana"    # quoted reply stripped
    assert sig.plan is None and sig.account_age_days is None


def test_adapters_are_inert_without_env(monkeypatch):
    for k in ("SLACK_BOT_TOKEN", "SLACK_WEBHOOK_URL", "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD",
              "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "GITHUB_TOKEN", "GITHUB_REPO"):
        monkeypatch.delenv(k, raising=False)
    assert not SlackAdapter().live and not ImapInbox().live and not SmtpSender().live and not GitHubAdapter().live
    creds = WriteCredentials.from_env()
    assert isinstance(creds.slack, FakeSlack) and isinstance(creds.gmail, FakeGmail)


def test_from_env_selects_real_adapters(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/x")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    creds = WriteCredentials.from_env()
    assert isinstance(creds.slack, SlackAdapter) and isinstance(creds.gmail, SmtpSender)
    assert "slack=live" in creds.describe() and "email=smtp" in creds.describe()
