"""GitHub adapter (read-only). Pulls the ownership metadata the org already
maintains and recent deploy history into a local cache the loaders read.

  GITHUB_TOKEN     PAT with contents:read
  GITHUB_REPO      owner/name
  GITHUB_REF       branch, default main
  GITHUB_CATALOG   path to catalog.yaml in the repo, default catalog.yaml

A deploy is a commit on GITHUB_REF that touches services/<name>/ (the same
convention CODEOWNERS uses). Run `python -m switchboard.sync`.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE = Path(os.environ.get("SWITCHBOARD_CACHE_DIR", ".switchboard-cache"))
CODEOWNERS_PATHS = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]


class GitHubAdapter:
    def __init__(self, token: str | None = None, repo: str | None = None, ref: str | None = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or None
        self.repo = repo or os.environ.get("GITHUB_REPO") or None
        self.ref = ref or os.environ.get("GITHUB_REF") or "main"
        self.catalog_path = os.environ.get("GITHUB_CATALOG", "catalog.yaml")

    @property
    def live(self) -> bool:
        return bool(self.token and self.repo)

    def _get(self, path: str, **params) -> dict | list:
        url = f"https://api.github.com{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}",
                                                   "Accept": "application/vnd.github+json",
                                                   "X-GitHub-Api-Version": "2022-11-28"})
        return json.loads(urllib.request.urlopen(req, timeout=15).read())

    def file(self, path: str) -> str | None:
        try:
            data = self._get(f"/repos/{self.repo}/contents/{path}", ref=self.ref)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        return base64.b64decode(data["content"]).decode()

    def codeowners(self) -> str | None:
        for p in CODEOWNERS_PATHS:
            text = self.file(p)
            if text is not None:
                return text
        return None

    def deploys(self, days: int = 3, max_commits: int = 60) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        commits = self._get(f"/repos/{self.repo}/commits", sha=self.ref, since=since, per_page=max_commits)
        out = []
        for c in commits:
            detail = self._get(f"/repos/{self.repo}/commits/{c['sha']}")
            services = {f["filename"].split("/")[1] for f in detail.get("files", [])
                        if f["filename"].startswith("services/") and f["filename"].count("/") >= 2}
            for svc in sorted(services):
                out.append({"service": svc, "release": c["sha"][:7],
                            "deployed_at": c["commit"]["committer"]["date"],
                            "summary": c["commit"]["message"].splitlines()[0][:120]})
        return out

    def sync(self, cache: Path = CACHE) -> Path:
        """Download CODEOWNERS, catalog.yaml and deploy history into `cache`."""
        if not self.live:
            raise RuntimeError("GITHUB_TOKEN and GITHUB_REPO are required")
        cache.mkdir(parents=True, exist_ok=True)
        co = self.codeowners()
        if co is None:
            raise RuntimeError(f"no CODEOWNERS found in {self.repo}@{self.ref} at {CODEOWNERS_PATHS}")
        (cache / "CODEOWNERS").write_text(co)
        cat = self.file(self.catalog_path)
        if cat is None:
            raise RuntimeError(f"no {self.catalog_path} in {self.repo}@{self.ref}")
        (cache / "catalog.yaml").write_text(cat)
        with open(cache / "deploys.jsonl", "w") as f:
            for d in self.deploys():
                f.write(json.dumps(d) + "\n")
        (cache / "synced_at").write_text(datetime.now(timezone.utc).isoformat())
        print(f"synced {self.repo}@{self.ref} → {cache}", file=sys.stderr)
        return cache
