"""python -m switchboard.doctor — credential, scope, and enum preflight."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .catalog import load_catalog, service_names
from .llm import MODEL
from .ownership import load_codeowners, own, stale_entries

load_dotenv()


def main() -> int:
    ok = True
    print("Switchboard doctor\n")
    print(f"  backend            {MODEL}" + ("  (zero-cost stand-in; set ANTHROPIC_API_KEY for the model)" if MODEL == "heuristic" else ""))
    print(f"  slack webhook      {'set' if os.environ.get('SLACK_WEBHOOK_URL') else 'unset → executor prints to console'}")

    cat = load_catalog()
    svcs = service_names()
    co = load_codeowners()
    print(f"\n  services           {len(svcs)} in catalog, {len(co)} in CODEOWNERS")
    missing = [s for s in svcs if s not in co]
    if missing:
        ok = False
        print(f"  !! no CODEOWNERS entry: {missing}")
    extra = [s for s in co if s not in svcs]
    if extra:
        print(f"  !! CODEOWNERS paths not in catalog: {extra}")
    for s in svcs:
        if own(s) is None:
            ok = False
            print(f"  !! unresolvable: {s}")
    stale = stale_entries()
    print(f"  ownership          {len(svcs) - len(stale)}/{len(svcs)} resolve via CODEOWNERS; {len(stale)} stale → catalog fallback")
    for s, t in stale:
        print(f"     stale: {s} → @{t} (team not in catalog; using catalog team {cat['services'][s]['team']})")
    lex = cat.get("symptoms", {})
    nolex = [s for s in svcs if s not in lex]
    if nolex:
        print(f"  !! services without symptom lexicon: {nolex}")
    print("\n  " + ("OK" if ok else "PROBLEMS FOUND"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
