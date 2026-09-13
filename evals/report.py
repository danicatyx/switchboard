"""Print the headline table from the latest run of each configuration."""
import glob
import json


def load(pat):
    paths = sorted(glob.glob(f"evals/reports/run_{pat}_*/summary.json"))
    return json.load(open(paths[-1])) if paths else None


def main():
    full, g, o, k3, nt = load("full"), load("ablate_grounding"), load("ablate_ownership"), load("full_k3"), load("no_telemetry")
    L = lambda s: s["localization_by_stratum"]
    P = lambda s: s["localization_email_by_provenance"]
    print(f"signals {full['n_signals']}  incidents {full['n_incidents']}  llm_calls {full['llm_calls']}  cost/incident ${full['cost_usd_per_incident']}")
    print()
    print("LOCALIZATION acc@1 (never blended)")
    print(f"  telemetry                        {L(full)['telemetry']['acc']}   n={L(full)['telemetry']['n']}")
    print(f"  email, grounded stratum   full   {L(full)['email_grounded']['acc']}   n={L(full)['email_grounded']['n']}   (realized grounded:telemetry n={P(full)['grounded:telemetry']['n']} acc={P(full)['grounded:telemetry']['acc']})")
    print(f"  email, grounded stratum  -ground {L(g)['email_grounded']['acc']}   same emails, telemetry withheld from the index")
    print(f"  email, ungrounded stratum        {L(full)['email_ungrounded']['acc']}   n={L(full)['email_ungrounded']['n']}  unknown_rate={L(full)['email_ungrounded']['unknown_rate']}")
    print(f"  email, all               full    {full['localization_email_all']['acc']}    -grounding {g['localization_email_all']['acc']}")
    lift = round(L(full)['email_grounded']['acc'] - L(g)['email_grounded']['acc'], 3)
    print(f"  GROUNDING LIFT (paired, grounded stratum)   {lift:+.3f}")
    print(f"  noise → unknown rate             {L(full)['noise']['unknown_rate']}")
    print()
    print("OWNERSHIP")
    print(f"  lookup success  {full['ownership']['lookup_success']}   team correct {full['ownership']['team_correct']}   misroutes {full['ownership']['misroutes']}   n={full['ownership']['n']}")
    print(f"  -ownership (model guesses team): team correct {o['ownership']['team_correct']}   misroutes {o['ownership']['misroutes']}")
    print()
    c = full["correlation"]
    print("CORRELATION (pairwise)")
    print(f"  precision {c['precision']}  recall {c['recall']}  cross-source recall {c['cross_source_recall']}  false merges {c['false_merges']}  pages avoided {c['pages_avoided']}")
    print(f"  -grounding: cross-source recall {g['correlation']['cross_source_recall']}  pages avoided {g['correlation']['pages_avoided']}")
    print()
    print(f"PRIORITY within-one {full['priority']['within_one']}  exact {full['priority']['exact']}   (-ownership {o['priority']['within_one']})")
    print(f"TIERS {full['tier_distribution']}   emails {full['email_tiers']}")
    if nt:
        print(f"NO-TELEMETRY (chaos) emails {nt['email_tiers']}")
    cal = full["calibration"]
    print(f"CALIBRATION ECE grounded {cal['grounded']['ece']} (n={cal['grounded']['n']})  ungrounded {cal['ungrounded']['ece']} (n={cal['ungrounded']['n']})")
    if k3:
        print(f"FLIP RATE k=3 {k3['flip']}")
    a = full["attacks"]
    print(f"ATTACKS blocked {a['blocked']}/{a['n']}  flagged {a['flagged']}")
    for r in a["rows"]:
        print(f"   {r['external_id']:<14} {r['family']:<24} tier={r['tier']:<9} {r['decision']:<14} {r['priority']}  {r['violations'] or ''}")


if __name__ == "__main__":
    main()
