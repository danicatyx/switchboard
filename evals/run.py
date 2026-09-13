"""Replay harness. Executor stubbed: plans are recorded, nothing executes.

    python -m evals.run                         # full configuration
    python -m evals.run --ablate grounding      # telemetry withheld from email candidates
    python -m evals.run --ablate ownership      # LLM guesses the team
    python -m evals.run --runs 3                # flip-rate analysis
    python -m evals.run --no-telemetry          # chaos: Sentry unavailable
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from switchboard.catalog import load_catalog
from switchboard.config import Config
from switchboard.pipeline import run_signal
from switchboard.store import IncidentStore

from .metrics import flip_rate, summarize

CORPUS = Path(__file__).resolve().parent / "corpus"
REPORTS = Path(__file__).resolve().parent / "reports"


def load_corpus(stratum: str | None = None) -> tuple[list[dict], dict[str, dict]]:
    signals = [json.loads(l) for l in open(CORPUS / "signals.jsonl") if l.strip()]
    labels = {l["external_id"]: l for l in (json.loads(x) for x in open(CORPUS / "labels.jsonl") if x.strip())}
    if stratum:
        keep = {e for e, l in labels.items() if l["stratum"] == stratum or l["stratum"] == "telemetry"}
        signals = [s for s in signals if s["external_id"] in keep]
    return signals, labels


def replay(signals: list[dict], cfg: Config, *, verbose: bool = False) -> list[dict]:
    store = IncidentStore()
    out = []
    for i, raw in enumerate(signals):
        if raw["kind"] == "telemetry" and not cfg.telemetry_available:
            continue  # adapter is down: the signal never arrives
        rec = run_signal(raw, store, cfg)
        out.append(rec.model_dump(mode="json"))
        if verbose:
            print(f"[{i+1:2d}/{len(signals)}] {raw['external_id']:<22} {' → '.join(rec.state_trace)}", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ablate", choices=["grounding", "ownership"])
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--stratum")
    ap.add_argument("--no-telemetry", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    name = args.out or ("full" if not args.ablate else f"ablate_{args.ablate}")
    if args.no_telemetry:
        name = "no_telemetry"
    if args.runs > 1:
        name += f"_k{args.runs}"
    run_dir = REPORTS / f"run_{name}_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)

    signals, labels = load_corpus(args.stratum)
    cat = load_catalog()
    teams = set(cat["teams"].keys())
    channels = {t["slack_channel"] for t in cat["teams"].values()}

    runs: list[list[dict]] = []
    for k in range(args.runs):
        cfg = Config(run_id=f"{name}-{k}", ablate=args.ablate, telemetry_available=not args.no_telemetry)
        print(f"== run {k+1}/{args.runs}  ablate={args.ablate} telemetry={cfg.telemetry_available}", file=sys.stderr)
        recs = replay(signals, cfg, verbose=not args.quiet)
        runs.append(recs)
        with open(run_dir / f"records_{k}.jsonl", "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    summary = summarize(runs[0], labels, teams, channels)
    summary["config"] = {"ablate": args.ablate, "runs": args.runs, "telemetry_available": not args.no_telemetry, "stratum": args.stratum}
    if args.runs > 1:
        summary["flip"] = flip_rate(runs)
        summary["per_run"] = [summarize(r, labels, teams, channels) for r in runs]

    with open(run_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Failure gallery: every wrong case with its trace.
    with open(run_dir / "failures.md", "w") as f:
        f.write(f"# Failure gallery — {name}\n\n")
        for r in runs[0]:
            e = r["signal"]["external_id"]
            l = labels[e]
            svc = r["incident"]["service"] or "unknown"
            wrong = svc != l["true_service"] and not l["is_attack"]
            if wrong:
                f.write(f"## {e}  ({l['stratum']})\n- true: `{l['true_service']}` / `{l['true_incident']}`\n"
                        f"- got:  `{svc}` / `{r['incident']['id']}` prov={r['incident']['localization_provenance']} tier={r['tier']}\n"
                        f"- trace: {' → '.join(r['state_trace'])}\n- subject: {r['signal'].get('subject')}\n\n")

    print(json.dumps({k: v for k, v in summary.items() if k not in ("calibration", "per_run")}, indent=2))
    print(f"\nwrote {run_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
