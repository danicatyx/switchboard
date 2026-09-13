"""Service catalog and deploy history loaders. Read-only fixtures."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _resolve_fixtures() -> Path:
    """Ownership metadata source, in priority order: explicit dir, GitHub sync cache, bundled fixtures."""
    import os
    explicit = os.environ.get("SWITCHBOARD_FIXTURES_DIR")
    if explicit:
        return Path(explicit)
    cache = Path(os.environ.get("SWITCHBOARD_CACHE_DIR", ".switchboard-cache"))
    if (cache / "catalog.yaml").exists() and (cache / "CODEOWNERS").exists():
        return cache
    return _DEFAULT_FIXTURES


FIXTURES = _resolve_fixtures()


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with open(FIXTURES / "catalog.yaml") as f:
        cat = yaml.safe_load(f)
    if "symptoms" not in cat and FIXTURES != _DEFAULT_FIXTURES:
        with open(_DEFAULT_FIXTURES / "catalog.yaml") as f:
            cat["symptoms"] = yaml.safe_load(f).get("symptoms", {})
    return cat


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
    path = FIXTURES / "deploys.jsonl"
    if not path.exists():
        return out
    with open(path) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                d["deployed_at"] = datetime.fromisoformat(d["deployed_at"].replace("Z", "+00:00"))
                out.append(d)
    return out


def deploys_near(ts: datetime, hours: int = 24) -> list[dict]:
    lo = ts - timedelta(hours=hours)
    return [d for d in load_deploys() if lo <= d["deployed_at"] <= ts]
