"""Regression gate. `make eval` fails if any headline number drops more than
TOLERANCE against evals/baseline.json (README §6.4). --write-baseline freezes
the current numbers instead.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

BASELINE = Path(__file__).resolve().parent / "baseline.json"
TOLERANCE = 0.02

# (label, run pattern, path into summary, higher_is_better)
HEADLINE = [
    ("localization telemetry", "full", ("localization_by_stratum", "telemetry", "acc"), True),
    ("localization email grounded stratum", "full", ("localization_by_stratum", "email_grounded", "acc"), True),
    ("localization email ungrounded stratum", "full", ("localization_by_stratum", "email_ungrounded", "acc"), True),
    ("grounding ablation: email grounded stratum", "ablate_grounding", ("localization_by_stratum", "email_grounded", "acc"), None),
    ("ownership team correct", "full", ("ownership", "team_correct"), True),
    ("correlation precision", "full", ("correlation", "precision"), True),
    ("correlation recall", "full", ("correlation", "recall"), True),
    ("cross-source recall", "full", ("correlation", "cross_source_recall"), True),
    ("priority within one", "full", ("priority", "within_one"), True),
    ("attacks blocked fraction", "full", ("attacks", "blocked_fraction"), True),
    ("no-telemetry emails in auto", "no_telemetry", ("email_tiers", "auto"), False),
]


def _latest(pat: str) -> dict | None:
    paths = sorted(glob.glob(f"evals/reports/run_{pat}_*/summary.json"))
    return json.load(open(paths[-1])) if paths else None


def _get(summary: dict, path: tuple) -> float | None:
    cur: object = summary
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            if path[-1] == "blocked_fraction" and isinstance(cur, dict) and "blocked" in cur:
                return cur["blocked"] / cur["n"] if cur["n"] else None
            if path[-1] == "auto" and isinstance(cur, dict):
                return float(cur.get("auto", 0))
            return None
        cur = cur[k]
    return cur  # type: ignore[return-value]


def current() -> dict[str, float | None]:
    out = {}
    for label, pat, path, _ in HEADLINE:
        s = _latest(pat)
        out[label] = _get(s, path) if s else None
    return out


def main() -> int:
    now = current()
    if "--write-baseline" in sys.argv:
        BASELINE.write_text(json.dumps(now, indent=2))
        print(f"baseline written: {BASELINE}")
        return 0
    if not BASELINE.exists():
        print("no baseline; run `make baseline` to freeze the current numbers", file=sys.stderr)
        return 0
    base = json.loads(BASELINE.read_text())
    failed = []
    print(f"{'metric':<44} {'baseline':>9} {'now':>9}")
    for label, _, _, higher in HEADLINE:
        b, n = base.get(label), now.get(label)
        flag = ""
        if b is not None and n is not None and higher is not None:
            drop = (b - n) if higher else (n - b)
            if drop > TOLERANCE:
                flag = "  REGRESSION"
                failed.append(label)
        print(f"{label:<44} {b if b is not None else '-':>9} {n if n is not None else '-':>9}{flag}")
    if failed:
        print(f"\nFAILED: {len(failed)} headline number(s) dropped more than {TOLERANCE}", file=sys.stderr)
        return 1
    print("\ngate: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
