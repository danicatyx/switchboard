"""Slack adapter. Two modes, both real:

  SLACK_BOT_TOKEN   chat.postMessage to any channel the bot is in (needed for per-team channels)
  SLACK_WEBHOOK_URL incoming webhook; posts to the webhook's fixed channel and prefixes the intended one

Held by the executor only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


class SlackAdapter:
    def __init__(self, bot_token: str | None = None, webhook_url: str | None = None) -> None:
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN") or None
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL") or None
        self.posted: list[dict] = []

    @property
    def live(self) -> bool:
        return bool(self.bot_token or self.webhook_url)

    def post(self, channel: str, text: str, metadata: dict) -> None:
        self.posted.append({"channel": channel, "text": text, "metadata": metadata})
        if self.bot_token:
            body = {"channel": channel, "text": text,
                    "metadata": {"event_type": "switchboard_action", "event_payload": metadata}}
            req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json; charset=utf-8",
                                                  "Authorization": f"Bearer {self.bot_token}"})
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if not resp.get("ok"):
                raise RuntimeError(f"slack: {resp.get('error')}")
        elif self.webhook_url:
            req = urllib.request.Request(self.webhook_url, data=json.dumps({"text": f"*{channel}*\n{text}"}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
        else:
            print(f"\n  ┌ SLACK {channel}\n" + "\n".join(f"  │ {l}" for l in text.splitlines()) + "\n  └", file=sys.stderr)
