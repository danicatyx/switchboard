"""python -m evals.dashboard [--out evals/reports/dashboard.html]

Builds a self-contained console page from the latest run of each configuration:
replay board with state traces, results charts, attack audit, failure gallery,
and an integrations panel reflecting what `doctor` finds configured. Opens
offline; no server.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from switchboard.catalog import service as catalog_service, service_names
from switchboard.demo import DEMO_IDS
from switchboard.integrations.email import ImapInbox, SmtpSender
from switchboard.integrations.github import GitHubAdapter
from switchboard.integrations.slack import SlackAdapter
from switchboard.llm import MODEL

load_dotenv()

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "dashboard_template.html"


def _latest(pat: str) -> tuple[dict | None, list[dict]]:
    paths = sorted(glob.glob(str(HERE / "reports" / f"run_{pat}_*" / "summary.json")))
    if not paths:
        return None, []
    run = Path(paths[-1]).parent
    recs = [json.loads(l) for l in open(run / "records_0.jsonl") if l.strip()]
    return json.load(open(paths[-1])), recs


def integrations() -> list[dict]:
    slack, imap, smtp, gh = SlackAdapter(), ImapInbox(), SmtpSender(), GitHubAdapter()
    return [
        dict(key="slack", name="Slack", abbr="Sl", direction="write", held_by="executor", live=slack.live,
             detail="bot token" if slack.bot_token else ("incoming webhook" if slack.webhook_url else ""),
             role="Pages the owning team once per incident with correlated blast radius; posts proposals and escalations to triage channels.",
             capabilities=["chat.postMessage", "per-team channels", "idempotency metadata"], transports=["Direct", "MCP"],
             direct_hint="A bot token posts to per-team channels the bot is in; an incoming webhook posts to one fixed channel.",
             fields=[dict(env="SLACK_BOT_TOKEN", label="Bot token", secret=True, placeholder="xoxb-…"),
                     dict(env="SLACK_WEBHOOK_URL", label="Incoming webhook URL (alternative)", placeholder="https://hooks.slack.com/services/…")],
             mcp_fields=[dict(env="SLACK_MCP_URL", label="MCP server URL", placeholder="https://mcp.example/slack"),
                         dict(env="SLACK_MCP_TOKEN", label="MCP bearer token", secret=True)]),
        dict(key="email", name="Email", abbr="@", direction="read + write", held_by="pipeline (IMAP) / executor (SMTP)",
             live=imap.live or smtp.live, detail=("IMAP " if imap.live else "") + ("SMTP" if smtp.live else ""),
             role="Ingests customer reports from the support inbox; sends acknowledgment and resolution notices to every correlated reporter, threaded on the original message.",
             capabilities=["IMAP unseen fetch", "SMTP send", "In-Reply-To threading", "recipient allowlist"], transports=["Direct", "MCP"],
             direct_hint="Gmail works with an app password (2-step verification on). Any IMAP/SMTP provider works the same way.",
             fields=[dict(env="IMAP_HOST", label="IMAP host", placeholder="imap.gmail.com"), dict(env="IMAP_USER", label="IMAP user"),
                     dict(env="IMAP_PASSWORD", label="IMAP password / app password", secret=True),
                     dict(env="SMTP_HOST", label="SMTP host", placeholder="smtp.gmail.com"), dict(env="SMTP_USER", label="SMTP user"),
                     dict(env="SMTP_PASSWORD", label="SMTP password / app password", secret=True)],
             mcp_fields=[dict(env="EMAIL_MCP_URL", label="MCP server URL", placeholder="https://mcp.example/gmail"),
                         dict(env="EMAIL_MCP_TOKEN", label="MCP bearer token", secret=True)]),
        dict(key="github", name="GitHub", abbr="GH", direction="read", held_by="pipeline", live=gh.live,
             detail=f"{gh.repo}@{gh.ref}" if gh.live else "",
             role="CODEOWNERS and the service catalog for ownership resolution; commits touching services/<name>/ as deploy evidence for localization.",
             capabilities=["CODEOWNERS", "catalog.yaml", "deploy history", "staleness check"], transports=["Direct", "MCP"],
             direct_hint="A fine-grained PAT with contents:read on the repo. `python -m switchboard.sync` pulls into a local cache.",
             fields=[dict(env="GITHUB_TOKEN", label="Personal access token", secret=True, placeholder="github_pat_…"),
                     dict(env="GITHUB_REPO", label="Repository", placeholder="owner/name"), dict(env="GITHUB_REF", label="Branch", placeholder="main"),
                     dict(env="GITHUB_CATALOG", label="Catalog path", placeholder="catalog.yaml")],
             mcp_fields=[dict(env="GITHUB_MCP_URL", label="MCP server URL", placeholder="https://api.githubcopilot.com/mcp/"),
                         dict(env="GITHUB_MCP_TOKEN", label="MCP bearer token", secret=True)]),
        dict(key="sentry", name="Sentry", abbr="Se", direction="read", held_by="pipeline", live=False, detail="",
             role="Telemetry signals: fingerprints, stack frames, release, error-rate delta against a 7-day baseline, affected users.",
             capabilities=["issue webhooks", "fingerprint", "release", "affected users"], transports=["Direct", "MCP"],
             direct_hint="Not implemented in this build; telemetry is replayed from a JSONL drop file. An issue-alert webhook receiver is the planned direct path.",
             fields=[dict(env="SENTRY_AUTH_TOKEN", label="Auth token", secret=True), dict(env="SENTRY_ORG", label="Organization slug"),
                     dict(env="SENTRY_WEBHOOK_SECRET", label="Webhook signing secret", secret=True)],
             mcp_fields=[dict(env="SENTRY_MCP_URL", label="MCP server URL", placeholder="https://mcp.sentry.dev/mcp"),
                         dict(env="SENTRY_MCP_TOKEN", label="MCP bearer token", secret=True)]),
        dict(key="linear", name="Linear", abbr="Li", direction="read + write", held_by="pipeline / executor", live=False, detail="",
             role="Incident records: create, merge signals into, and comment on incidents. No action closes, deletes, or reassigns.",
             capabilities=["create issue", "comment", "labels", "no destructive actions"], transports=["Direct", "MCP"],
             direct_hint="Not implemented in this build; incident records live in an in-memory store persisted to state.json.",
             fields=[dict(env="LINEAR_API_KEY", label="API key", secret=True), dict(env="LINEAR_TEAM", label="Team key", placeholder="OPS")],
             mcp_fields=[dict(env="LINEAR_MCP_URL", label="MCP server URL", placeholder="https://mcp.linear.app/mcp"),
                         dict(env="LINEAR_MCP_TOKEN", label="MCP bearer token", secret=True)]),
    ]


def build(out: Path) -> Path:
    full, recs = _latest("full")
    if full is None:
        raise SystemExit("no full run found; run `make eval` first")
    grounding, _ = _latest("ablate_grounding")
    ownership, own_recs = _latest("ablate_ownership")
    no_tel, _ = _latest("no_telemetry")
    k3, _ = _latest("full_k3")
    labels = {json.loads(l)["external_id"]: json.loads(l) for l in open(HERE / "corpus" / "labels.jsonl") if l.strip()}

    # derived slices
    non_attack = [r for r in recs if not labels[r["signal"]["external_id"]]["is_attack"]]
    emails = [r for r in non_attack if r["signal"]["source"] == "email" and labels[r["signal"]["external_id"]]["stratum"].startswith("email")]
    per_service = []
    for svc in service_names():
        rows = [r for r in emails if labels[r["signal"]["external_id"]]["true_service"] == svc]
        if rows:
            ok = sum(1 for r in rows if r["incident"]["service"] == svc)
            per_service.append({"service": svc, "n": len(rows), "acc": round(ok / len(rows), 3)})
    per_service.sort(key=lambda x: (-x["acc"], x["service"]))
    per_vag = []
    for lvl in ("high", "medium", "low"):
        rows = [r for r in emails if labels[r["signal"]["external_id"]].get("vagueness") == lvl]
        if rows:
            ok = sum(1 for r in rows if (r["incident"]["service"] or "unknown") == labels[r["signal"]["external_id"]]["true_service"])
            per_vag.append({"level": f"{lvl} (symptom only)" if lvl == "high" else f"{lvl} (feature named)" if lvl == "medium" else f"{lvl} (endpoint named)", "n": len(rows), "acc": round(ok / len(rows), 3)})
    sizes = Counter(Counter(r["incident"]["id"] for r in non_attack).values())
    incident_sizes = [{"size": k, "count": v} for k, v in sorted(sizes.items())]
    P = ["P1", "P2", "P3", "P4"]
    matrix = [[0] * 4 for _ in P]
    for r in non_attack:
        l = labels[r["signal"]["external_id"]]
        if l["stratum"] == "noise":
            continue
        matrix[P.index(l["true_priority"])][P.index(r["incident"]["priority"])] += 1
    per_day = Counter(r["signal"]["received_at"][:10] for r in recs)
    nonexistent = sum(1 for r in own_recs for t in r["state_trace"] if t.startswith("OWNERSHIP:guessed:NONEXISTENT"))
    times = sorted(r["signal"]["received_at"] for r in recs)

    data = {
        "run_id": recs[0]["run_id"] if recs else "",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "backend": MODEL,
        "n_signals": len(recs),
        "days": len(per_day),
        "t_min": times[0], "t_max": times[-1],
        "per_day": [{"day": d, "n": n} for d, n in sorted(per_day.items())],
        "summary": full,
        "ablate_grounding": grounding,
        "ablate_ownership": ownership,
        "no_telemetry": no_tel,
        "flip": (k3 or {}).get("flip"),
        "records": recs,
        "labels": labels,
        "demo_ids": DEMO_IDS,
        "per_service": per_service,
        "per_vagueness": per_vag,
        "incident_sizes": incident_sizes,
        "priority_matrix": matrix,
        "nonexistent_teams": nonexistent,
        "integrations": integrations(),
    }
    html = TEMPLATE.read_text().replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "reports" / "dashboard.html"))
    args = ap.parse_args()
    build(Path(args.out))


if __name__ == "__main__":
    main()
