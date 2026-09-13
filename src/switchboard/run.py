"""python -m switchboard.run --sources gmail,sentry --max-tier propose [--once] [--poll 30]

Live mode. Emails come from the IMAP inbox; telemetry from a JSONL drop file
(--sentry-file), since there is no Sentry receiver in this build. The executor
holds whatever real credentials are configured (see .env.example).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .config import Config
from .execute.executor import Executor, WriteCredentials
from .execute.wal import WAL
from .integrations.email import ImapInbox
from .integrations.github import GitHubAdapter
from .models import Tier
from .pipeline import run_signal
from .store import IncidentStore

load_dotenv()

RANK = {"auto": 0, "propose": 1, "escalate": 2}


def demote(tier: Tier, max_tier: Tier) -> Tier:
    return tier if RANK[tier] >= RANK[max_tier] else max_tier


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="gmail,sentry")
    ap.add_argument("--max-tier", choices=["auto", "propose", "escalate"], default="propose",
                    help="never act above this tier in live mode (default: propose)")
    ap.add_argument("--sentry-file", default="inbox/sentry.jsonl", help="JSONL of telemetry signals to ingest")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll", type=int, default=30)
    ap.add_argument("--no-sync", action="store_true", help="skip GitHub sync at startup")
    args = ap.parse_args()
    sources = set(args.sources.split(","))

    gh = GitHubAdapter()
    if gh.live and not args.no_sync:
        gh.sync()

    inbox = ImapInbox()
    if "gmail" in sources and not inbox.live:
        print("IMAP_HOST/IMAP_USER/IMAP_PASSWORD not set; email source disabled", file=sys.stderr)
        sources.discard("gmail")

    creds = WriteCredentials.from_env()
    store = IncidentStore()
    executor = Executor(creds, WAL("wal.json"), lambda inc_id: store.incidents[inc_id].reporters)
    cfg = Config(run_id=f"live-{int(time.time())}")
    seen_sentry: set[str] = set()
    print(f"switchboard live · sources={sorted(sources)} · max-tier={args.max_tier} · executor {creds.describe()}", file=sys.stderr)

    while True:
        raws: list[dict] = []
        if "gmail" in sources:
            raws += inbox.fetch_unseen()
        if "sentry" in sources and Path(args.sentry_file).exists():
            for line in open(args.sentry_file):
                if line.strip():
                    d = json.loads(line)
                    if d["external_id"] not in seen_sentry:
                        seen_sentry.add(d["external_id"])
                        raws.append(d)
        raws.sort(key=lambda r: r["received_at"])
        for raw in raws:
            rec = run_signal(raw, store, cfg)
            if rec.tier != demote(rec.tier, args.max_tier):
                from .plan import build_plan
                rec.tier = demote(rec.tier, args.max_tier)
                rec.plan = build_plan(rec.signal, rec.incident, rec.tier, rec.correlation_decision, rec.c_eff, ["max_tier"])
                rec.state_trace.append(f"DEMOTED:{rec.tier}")
            rec.executed = executor.execute(rec.plan)
            print(f"{raw['external_id']:<40} {' → '.join(rec.state_trace)}", file=sys.stderr)
        if args.once:
            break
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
