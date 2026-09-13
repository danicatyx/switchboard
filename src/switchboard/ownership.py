"""own(λ): service → team, channel, on-call. Deterministic. No model call.

Joins CODEOWNERS with the service catalog. Correctness is bounded by metadata
freshness, which we surface as `stale` rather than hide.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .catalog import FIXTURES, load_catalog, service as catalog_service, team as catalog_team
from .models import Ownership

# Fixture age. In a real deployment this is the mtime of the CODEOWNERS commit.
CODEOWNERS_AGE_DAYS = 41

_LINE = re.compile(r"^/services/([a-z0-9-]+)/\s+@[\w-]+/([\w-]+)\s*$")


@lru_cache(maxsize=1)
def load_codeowners() -> dict[str, str]:
    """service name → team slug, from CODEOWNERS paths."""
    out: dict[str, str] = {}
    with open(FIXTURES / "CODEOWNERS") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            m = _LINE.match(line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def own(service: str | None) -> Ownership | None:
    """Resolve ownership. Returns None only if the service is not in the catalog."""
    if not service:
        return None
    svc = catalog_service(service)
    if svc is None:
        return None

    co_team = load_codeowners().get(service)
    cat_team = svc["team"]

    # CODEOWNERS is authoritative when it names a team that still exists.
    # If it names a team the catalog no longer knows, fall back to the catalog
    # and mark the entry stale. This is the "confidently wrong" case the README
    # warns about, made visible instead of silent.
    if co_team and catalog_team(co_team):
        team_name, source, stale = co_team, "codeowners", False
    else:
        team_name, source, stale = cat_team, "catalog", co_team is not None

    t = catalog_team(team_name)
    return Ownership(
        team=team_name,
        slack_channel=t["slack_channel"],
        oncall_user=t.get("oncall_user"),
        source=source,
        metadata_age_days=CODEOWNERS_AGE_DAYS,
        stale=stale,
    )


def stale_entries() -> list[tuple[str, str]]:
    """(service, codeowners_team) pairs whose team is missing from the catalog. For doctor."""
    return [(s, t) for s, t in load_codeowners().items() if not catalog_team(t)]
