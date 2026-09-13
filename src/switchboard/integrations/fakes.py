"""Fake adapters. No pipeline component imports a vendor SDK. The only live
call in this build is an optional Slack incoming webhook.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


class FakeSlack:
    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL") or None
        self.posted: list[dict] = []

    def post(self, channel: str, text: str, metadata: dict) -> None:
        self.posted.append({"channel": channel, "text": text, "metadata": metadata})
        if self.webhook_url:
            body = json.dumps({"text": f"*{channel}*\n{text}"}).encode()
            req = urllib.request.Request(self.webhook_url, data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
        else:
            print(f"\n  ┌ SLACK {channel}\n" + "\n".join(f"  │ {l}" for l in text.splitlines()) + "\n  └", file=sys.stderr)


class FakeGmail:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str, thread_ref: str | None) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body, "thread_ref": thread_ref})
        print(f"\n  ┌ EMAIL → {to}  ({subject})\n" + "\n".join(f"  │ {l}" for l in body.splitlines()) + "\n  └", file=sys.stderr)


class FakeIncidentTracker:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def create(self, incident_id: str, payload: dict) -> None:
        self.records[incident_id] = {"payload": payload, "signals": [payload.get("signal_id")]}

    def merge(self, incident_id: str, signal_id: str) -> None:
        self.records.setdefault(incident_id, {"payload": {}, "signals": []})["signals"].append(signal_id)
