"""Email adapters over IMAP (read) and SMTP (write). Works with Gmail via an app
password and with any other provider. No OAuth.

  IMAP_HOST / IMAP_USER / IMAP_PASSWORD / IMAP_FOLDER (default INBOX)
  SMTP_HOST / SMTP_PORT (default 587) / SMTP_USER / SMTP_PASSWORD / SMTP_FROM

The reader is held by the pipeline (read-only). The sender is held by the
executor only.
"""

from __future__ import annotations

import email
import email.utils
import imaplib
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage, Message


def parse_message(msg: Message, uid: str = "") -> dict:
    """RFC822 message → raw signal dict in the corpus format."""
    from_name, from_addr = email.utils.parseaddr(msg.get("From", ""))
    date = email.utils.parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                break
    else:
        payload = msg.get_payload(decode=True)
        body = payload.decode(msg.get_content_charset() or "utf-8", "replace") if payload else ""
    mid = (msg.get("Message-ID") or f"uid-{uid}").strip("<> ")
    domain = from_addr.split("@")[-1].lower() if "@" in from_addr else "unknown"
    return {
        "kind": "email",
        "external_id": mid,
        "received_at": date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reporter_email": from_addr.lower(),
        "account_ref": domain.split(".")[0],
        "plan": None,
        "account_age_days": None,
        "subject": msg.get("Subject", ""),
        "body": body,
        "thread_ref": (msg.get("In-Reply-To") or mid).strip("<> "),
    }


class ImapInbox:
    def __init__(self) -> None:
        self.host = os.environ.get("IMAP_HOST")
        self.user = os.environ.get("IMAP_USER")
        self.password = os.environ.get("IMAP_PASSWORD")
        self.folder = os.environ.get("IMAP_FOLDER", "INBOX")

    @property
    def live(self) -> bool:
        return bool(self.host and self.user and self.password)

    def fetch_unseen(self, mark_seen: bool = True) -> list[dict]:
        with imaplib.IMAP4_SSL(self.host) as m:
            m.login(self.user, self.password)
            m.select(self.folder)
            _, data = m.search(None, "UNSEEN")
            out = []
            for uid in data[0].split():
                _, parts = m.fetch(uid, "(BODY.PEEK[])")
                raw = parts[0][1]
                out.append(parse_message(email.message_from_bytes(raw), uid.decode()))
                if mark_seen:
                    m.store(uid, "+FLAGS", "\\Seen")
            return out


class SmtpSender:
    def __init__(self) -> None:
        self.host = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.sender = os.environ.get("SMTP_FROM") or self.user
        self.sent: list[dict] = []

    @property
    def live(self) -> bool:
        return bool(self.host and self.user and self.password)

    def send(self, to: str, subject: str, body: str, thread_ref: str | None) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body, "thread_ref": thread_ref})
        if not self.live:
            print(f"\n  ┌ EMAIL → {to}  ({subject})\n" + "\n".join(f"  │ {l}" for l in body.splitlines()) + "\n  └", file=sys.stderr)
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        if thread_ref:
            msg["In-Reply-To"] = f"<{thread_ref}>"
            msg["References"] = f"<{thread_ref}>"
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=15) as s:
            s.starttls()
            s.login(self.user, self.password)
            s.send_message(msg)
