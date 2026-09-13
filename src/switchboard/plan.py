"""Plan construction (README §3.8). Closed action set A; targets come from own(λ)
so an unroutable service is unrepresentable. Every action carries an
idempotency key.
"""

from __future__ import annotations

from .models import Action, Incident, Signal, Tier, idempotency_key

TRIAGE_PROPOSALS = "#triage-proposals"
TRIAGE_HUMANS = "#triage-humans"


def _act(signal: Signal, type_: str, target: str, payload: dict) -> Action:
    return Action(type=type_, payload=payload, idempotency_key=idempotency_key(signal.id, type_, target))


def build_plan(signal: Signal, inc: Incident, tier: Tier, decision: str, c_eff: float, reasons: list[str]) -> list[Action]:
    actions: list[Action] = []
    is_new = decision == "new"
    summary = {
        "incident_id": inc.id, "service": inc.service, "provenance": inc.localization_provenance,
        "priority": inc.priority, "applied_rules": inc.applied_rules, "signal_count": len(inc.signals),
        "distinct_accounts": inc.distinct_reporting_accounts, "c_eff": c_eff, "tier": tier,
        "possible_relations": inc.possible_relations,
    }

    if tier == "escalate":
        actions.append(_act(signal, "escalate_to_human", TRIAGE_HUMANS,
                            {"channel": TRIAGE_HUMANS, "signal_id": signal.id, "reasons": reasons, **summary}))
        return actions

    if is_new:
        actions.append(_act(signal, "create_incident", inc.id, {**summary, "signal_id": signal.id}))
    else:
        actions.append(_act(signal, "merge_signal_into_incident", inc.id, {"incident_id": inc.id, "signal_id": signal.id}))

    if tier == "propose":
        actions.append(_act(signal, "post_slack", TRIAGE_PROPOSALS,
                            {"channel": TRIAGE_PROPOSALS, "proposal": True, "signal_id": signal.id, **summary}))
        return actions

    # AUTO. Page the owning team once per incident, not once per signal.
    owner = inc.owner
    assert owner is not None, "auto tier requires resolved ownership"
    if not inc.paged:
        actions.append(_act(signal, "post_slack", owner.slack_channel,
                            {"channel": owner.slack_channel, "team": owner.team, **summary}))
        if inc.priority == "P1" and owner.oncall_user:
            actions.append(_act(signal, "page_oncall", owner.oncall_user,
                                {"user": owner.oncall_user, "channel": owner.slack_channel, "escalation_policy": owner.team, **summary}))
    if signal.source == "email" and signal.reporter_email:
        # Ack goes to THIS signal's reporter only; never to other reporters on the incident.
        actions.append(_act(signal, "send_email_ack", signal.reporter_email,
                            {"to": signal.reporter_email, "incident_id": inc.id, "thread_ref": signal.thread_ref,
                             "subject": f"Re: {signal.subject or 'your report'}"}))
    return actions
