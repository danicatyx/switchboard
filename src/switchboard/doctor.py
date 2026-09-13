"""python -m switchboard.doctor - credential, scope, and enum preflight."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .catalog import FIXTURES, load_catalog, service_names
from .integrations.email import ImapInbox, SmtpSender
from .integrations.github import GitHubAdapter
from .integrations.slack import SlackAdapter
from .llm import MODEL
from .ownership import load_codeowners, own, stale_entries

load_dotenv()


def _check(label: str, fn) -> bool:
    try:
        detail = fn()
        print(f"  {label:<18} ok{('  ' + detail) if detail else ''}")
        return True
    except Exception as e:  # noqa: BLE001 - doctor reports, never raises
        print(f"  !! {label:<15} {type(e).__name__}: {str(e)[:120]}")
        return False


def _slack(a: SlackAdapter) -> str:
    import json, urllib.request
    if a.bot_token:
        req = urllib.request.Request("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {a.bot_token}"}, method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if not r.get("ok"):
            raise RuntimeError(r.get("error"))
        return f"bot token, team={r.get('team')} user={r.get('user')}"
    return "webhook configured (not exercised; posting is the only way to test a webhook)"


def _imap(i: ImapInbox) -> str:
    import imaplib
    with imaplib.IMAP4_SSL(i.host) as m:
        m.login(i.user, i.password)
        status, data = m.select(i.folder, readonly=True)
        return f"{i.user} {i.folder}: {data[0].decode()} messages"


def _smtp(s: SmtpSender) -> str:
    import smtplib
    with smtplib.SMTP(s.host, s.port, timeout=15) as c:
        c.starttls()
        c.login(s.user, s.password)
    return f"{s.user} via {s.host}:{s.port}"


def _github(g: GitHubAdapter) -> str:
    repo = g._get(f"/repos/{g.repo}")
    co = g.codeowners()
    cat = g.file(g.catalog_path)
    return (f"{repo['full_name']}@{g.ref}: CODEOWNERS {'found' if co else 'MISSING'}, "
            f"{g.catalog_path} {'found' if cat else 'MISSING'}")


def main() -> int:
    ok = True
    print("Switchboard doctor\n")
    print(f"  backend            {MODEL}" + ("  (zero-cost stand-in; set ANTHROPIC_API_KEY for the model)" if MODEL == "heuristic" else ""))
    print(f"  metadata source    {FIXTURES}")

    print("\n  integrations (live checks run only where configured)")
    slack, imap, smtp, gh = SlackAdapter(), ImapInbox(), SmtpSender(), GitHubAdapter()
    if slack.live:
        ok &= _check("slack (write)", lambda: _slack(slack))
    else:
        print("  slack (write)      unset → console")
    if imap.live:
        ok &= _check("imap (read)", lambda: _imap(imap))
    else:
        print("  imap (read)        unset → email source disabled in live mode")
    if smtp.live:
        ok &= _check("smtp (write)", lambda: _smtp(smtp))
    else:
        print("  smtp (write)       unset → console")
    if gh.live:
        ok &= _check("github (read)", lambda: _github(gh))
    else:
        print("  github (read)      unset → bundled fixtures/")

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
