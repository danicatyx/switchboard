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
        dict(key="datadog", name="Datadog", abbr="DD", direction="read", held_by="pipeline", live=bool(os.environ.get("DD_API_KEY") and os.environ.get("DD_APP_KEY")),
             detail=os.environ.get("DD_SITE", "") if os.environ.get("DD_API_KEY") else "",
             role="Telemetry from monitors and APM: monitor alerts as signals, service tags from APM, error-rate deltas from metrics queries, deploy markers as localization evidence.",
             capabilities=["monitor webhooks", "APM service tags", "metrics query", "deploy events"], transports=["Direct", "MCP"],
             direct_hint="API and application keys with monitors_read and apm_read scopes. Monitor alerts arrive through a webhook; error-rate deltas come from a metrics query at signal time.",
             fields=[dict(env="DD_API_KEY", label="API key", secret=True), dict(env="DD_APP_KEY", label="Application key", secret=True),
                     dict(env="DD_SITE", label="Site", placeholder="datadoghq.com"), dict(env="DD_WEBHOOK_SECRET", label="Webhook signing secret", secret=True)],
             mcp_fields=[dict(env="DD_MCP_URL", label="MCP server URL", placeholder="https://mcp.datadoghq.com/api/unstable/mcp-server/mcp"),
                         dict(env="DD_MCP_TOKEN", label="MCP bearer token", secret=True)]),
        dict(key="linear", name="Linear", abbr="Li", direction="read + write", held_by="pipeline / executor", live=False, detail="",
             role="Incident records: create, merge signals into, and comment on incidents. No action closes, deletes, or reassigns.",
             capabilities=["create issue", "comment", "labels", "no destructive actions"], transports=["Direct", "MCP"],
             direct_hint="Not implemented in this build; incident records live in an in-memory store persisted to state.json.",
             fields=[dict(env="LINEAR_API_KEY", label="API key", secret=True), dict(env="LINEAR_TEAM", label="Team key", placeholder="OPS")],
             mcp_fields=[dict(env="LINEAR_MCP_URL", label="MCP server URL", placeholder="https://mcp.linear.app/mcp"),
                         dict(env="LINEAR_MCP_TOKEN", label="MCP bearer token", secret=True)]),
    ]


IMPACT_DEFAULTS = {
    # Every figure is an assumption. The page exposes all of them as inputs.
    "rate": 150,            # loaded engineer cost per hour, USD
    "manual_min": 45,       # minutes a human spends triaging one signal by hand (read, localize, find owner, page, reply)
    "auto_min": 1,          # minutes to glance at an auto-tier decision
    "propose_min": 4,       # minutes to approve or edit a proposal
    "escalate_min": 15,     # minutes for an escalation (same as manual)
    "page_min": 30,         # on-call minutes lost per avoidable page (interruption + context switch)
    "arr_enterprise": 120000, "arr_pro": 9600, "arr_free": 0,   # annual revenue per account by plan
    "churn_P1": 0.03, "churn_P2": 0.015, "churn_P3": 0.005, "churn_P4": 0.001,   # churn risk from an unacknowledged report
    "loop_auto": 1.0, "loop_propose": 0.7, "loop_escalate": 0.4,                  # share of that risk removed by closing the loop at each tier
    "misroute_min": 45,     # minutes a misrouted incident sits with the wrong team
    "down_P1": 400, "down_P2": 80, "down_P3": 10, "down_P4": 0,                  # cost per minute of an unresolved incident by priority
    "exp_correlation_poisoning": 75000, "exp_thread_spoof_poisoning": 75000,     # cross-customer data exposure
    "exp_fake_system_message": 40000, "exp_direct_override": 40000,              # mass mis-email or wrong-channel disclosure
    "exp_authority_impersonation": 15000, "exp_encoded_payload": 15000, "exp_hidden_html_comment": 15000,
    "exp_zero_width_override": 15000, "exp_third_order_quoted": 15000,           # wasted response + wrong pages
    "exp_second_order_telemetry": 10000,                                          # instructions smuggled through error payloads
    "exp_priority_manipulation": 2500,                                            # one wasted P1 response
}


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
    # Signals the text-based guess misrouted that the lookup routed correctly: the lookup's per-signal value.
    misrouted_by_guess = []
    full_ok = {r["signal"]["external_id"]: (r["incident"]["owner"] or {}).get("team") for r in recs}
    for r in own_recs:
        e = r["signal"]["external_id"]
        l = labels[e]
        if l["is_attack"] or l["true_service"] == "unknown":
            continue
        true_team = (catalog_service(l["true_service"]) or {}).get("team")
        got = (r["incident"]["owner"] or {}).get("team")
        if got != true_team and full_ok.get(e) == true_team:
            misrouted_by_guess.append(e)
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
        "n_non_attack": len(non_attack),
        "misrouted_by_guess": misrouted_by_guess,
        "impact_defaults": IMPACT_DEFAULTS,
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
