"""Service catalog and deploy history loaders. Read-only fixtures."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with open(FIXTURES / "catalog.yaml") as f:
        return yaml.safe_load(f)


def service_names() -> list[str]:
    return sorted(load_catalog()["services"].keys())


def service(name: str) -> dict | None:
    return load_catalog()["services"].get(name)


def team(name: str) -> dict | None:
    return load_catalog()["teams"].get(name)


def services_block() -> str:
    """Rendered for the <enum name="services"> prompt section."""
    svcs = load_catalog()["services"]
    return "\n".join(f"- {n} ({s['tier']}): {s['description']}" for n, s in sorted(svcs.items()))


@lru_cache(maxsize=1)
def load_deploys() -> list[dict]:
    out = []
    with open(FIXTURES / "deploys.jsonl") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                d["deployed_at"] = datetime.fromisoformat(d["deployed_at"].replace("Z", "+00:00"))
                out.append(d)
    return out


def deploys_near(ts: datetime, hours: int = 24) -> list[dict]:
    lo = ts - timedelta(hours=hours)
    return [d for d in load_deploys() if lo <= d["deployed_at"] <= ts]
