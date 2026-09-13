# Switchboard: System and Reliability Brief

**Team:** ___
**Repo:** ___
**Demo:** ___

---

## What it does

Switchboard turns scattered failure signals into one owned, tracked incident and closes the loop with everyone who reported it.

It ingests from two directions at once: **customer emails** arriving at the support inbox, and **telemetry alerts** from error monitoring. It correlates signals that describe the same underlying failure into a single incident, localizes that incident to the responsible service, resolves the owning team through the ownership metadata the organization already maintains, pages that team once in Slack, and emails every correlated reporter when the issue closes.

The economic work is incident triage in an organization with many teams and many repositories, where the expensive part is not writing the ticket but working out which of forty services broke and who owns it. Measured at `___` minutes per incident today.

---

## The insight the system is built around

**Telemetry knows where. Email knows who and how bad. Neither knows both.**

A stack trace names the failing service for free. A customer writing "exports have been stuck since 6am" does not, and inferring it is the genuinely hard step. Conversely, an alert has no idea that three enterprise accounts are blocked on it.

So the system correlates across sources and lets each fill the other's gap:

- A customer email that correlates to a telemetry alert **inherits the alert's service attribution** at near-certain confidence, rather than relying on the model's guess.
- A telemetry alert that correlates to customer emails **inherits real blast radius**: distinct accounts affected, reported at what time, blocked on what.

We measure this directly. Localization accuracy on email-only signals is reported with and without cross-source grounding. That delta is the central claim of the project.

**Corollary that shaped the architecture:** once you know the service, ownership is a lookup, not a prediction. CODEOWNERS and the service catalog already encode it. Asking a model to guess team names from ticket text is a worse version of a join the organization already has. The model does localization, which is hard. The deterministic layer does ownership, which must be right every time.

---

## External apps

| App | Role | Direction |
| --- | --- | --- |
| **Sentry** | Telemetry signals: fingerprints, stack traces, affected-user counts, error-rate deltas | read |
| **GitHub** | CODEOWNERS and service catalog for ownership resolution; recent deploys as localization evidence | read |
| **Slack** | Pages the owning team once per incident, with correlated blast radius attached | write |
| **Gmail** | Ingests customer reports; sends acknowledgment and resolution notices to every correlated reporter | read + write |

---

## How it works

A fixed pipeline with LLM decision points, not a free-running tool loop. The control flow of triage is known in advance, so we hardcode it and let the model make only the judgment calls.

```
  Gmail ─────┐
             ├──▶ Normalize ──▶ Correlate ──▶ Localize ──▶ Ownership ──▶ Priority
  Sentry ────┘     (→ Signal)   (→ Incident)   (service)    (lookup)     (rules)
                                                                             │
                          ┌──────────────────────────────────────────────────┘
                          ▼
                  Confidence Gate ──▶ Executor ──▶ Issue · Slack page · Reporter email
                 auto/propose/escalate
```

| Stage | Does what | Deterministic? |
| --- | --- | --- |
| **Normalize** | Both sources collapse into one `Signal` type. Email keeps reporter and account; telemetry keeps fingerprint, service tag, stack frames, user count. | yes |
| **Correlate** | Retrieves open incidents (BM25 + embeddings, RRF-fused), judges whether this signal belongs to one. Runs within and across sources. | LLM |
| **Localize** | Maps the incident to a service. Free from a stack trace; inferred from text plus recent deploys otherwise. Inherits from correlated telemetry when available. | LLM, or inherited |
| **Ownership** | service → CODEOWNERS + catalog → team, Slack channel, on-call. | **yes, a lookup** |
| **Priority** | Model proposes; deterministic rules adjust on blast radius, error-rate delta, critical-path flag, repeat occurrence. | rules |

Three properties we test:

1. **Each stage is separately scorable**, so a regression localizes to one prompt.
2. **The model cannot name a service or team that does not exist.** Both enums are fetched live; the model selects or returns `unknown`, which escalates to a human.
3. **Only the executor holds write credentials.** Every decision stage runs read-only, so an injected instruction cannot cause a write even if it escapes the prompt.

---

## How we know it works

### Replay corpus

`___` labeled signals across both sources, with ground truth: actual resolving service and team, actual incident groupings, actual severity at close. Runs with the executor stubbed, so no external effects. Enrichment replays API responses captured at the signal's timestamp, so the system cannot correlate against an incident filed afterward.

### Results

| Metric | Result | Baseline | Note |
| --- | --- | --- | --- |
| **Localization acc@1 (email-only, no grounding)** | | | The hard task |
| **Localization acc@1 (email, cross-source grounded)** | | | The central claim |
| Localization acc@1 (telemetry) | | | Near-free from stack traces |
| Ownership resolution correctness | | n/a | A lookup, reported as such |
| Correlation precision | | | Tuned high, see below |
| Correlation recall | | | |
| Priority within-one | | | |
| **Calibration (ECE)** | | n/a | Lower is better |
| **Flip rate (k=3)** | | n/a | Run-to-run instability |
| Auto-tier rate | | n/a | Fraction fully automated |
| Pages avoided by correlation | | n/a | Signals collapsed into incidents |
| Injection attacks blocked | / `___` | | |

Three of these are the ones we would defend hardest:

**The grounding delta.** The gap between the first two rows is what having both signal sources is worth. It is not an architectural preference, it is a measured number.

**Calibration.** Accuracy alone does not license automation. We bucket predictions by stated confidence and check the empirical hit rate per bucket. The auto-act threshold of 0.85 was read off that reliability diagram, not chosen as a round number. If the model were overconfident, no threshold would be safe and we would say so.

**Flip rate.** Every case runs k=3. A system that is 85% accurate and changes its answer on 20% of reruns is a different product from one that is 85% accurate and stable, because the first cannot be debugged or trusted to act alone. Almost nobody measures this.

### Ablations

| Configuration | Localization acc@1 | Priority within-one |
| --- | --- | --- |
| Full (both sources, correlated) | | |
| **Email only, no telemetry grounding** | | |
| **No ownership lookup (LLM guesses team from text)** | | |
| Free-text services (no enum constraint) | | |

The second row quantifies cross-source grounding. The third quantifies why ownership is a lookup: it counts the misroutes you get when a model guesses at a join the organization already has.

### Correlation is tuned asymmetrically

A false merge folds a live incident into an unrelated one and can delay detection for hours while the wrong team looks at it. A false split pages two teams instead of one and costs a human a minute. We tune for precision, accept mediocre recall, and report the two separately rather than as F1. Auto-merge requires confidence ≥ 0.85; between 0.60 and 0.85 the incident is created separately with a "possible relation" annotation.

### Failure handling

- **Faults injected** at each integration (timeout, 500, 429, partial write). Assertions: no duplicate external effects, no dropped signals, and degraded enrichment **lowers confidence and demotes the tier** rather than proceeding silently. Losing Sentry means email signals fall back to model-only localization, which correctly drops them out of the autonomous tier.
- **Idempotency.** Every action carries `SHA256(signal_id ‖ action_type ‖ target)`, so a retry after a partial failure cannot double-page a team or double-email a reporter.
- **Prompt injection.** Customer email bodies are text written by strangers, and telemetry payloads can carry attacker-controlled strings inside error messages and user input echoed into stack traces. `___` attacks across direct override, authority impersonation, encoded payloads, and second-order delivery through telemetry fields. Defenses are architectural first (read/write credential split, closed action set, recipient allowlist restricted to correlated reporters) and prompt-level second.

### What we did not automate

Three tiers. Above 0.85 the system acts. Between 0.60 and 0.85 it posts the proposed incident to Slack for one-click approval. Below that it escalates with evidence and no proposal. Abstention is a feature: `unknown_rate` is reported as a positive, and the quantity we minimize is severity-weighted misroute cost, not raw error rate.

---

## Known limitations

- The corpus comes from one organization's service topology. Localization accuracy will not transfer without relabeling, though the ownership lookup transfers by construction.
- Correlation recall is deliberately low as a consequence of precision tuning. Genuinely related signals are sometimes split.
- Cross-source grounding depends on the telemetry alert firing first or concurrently. A customer who reports before monitoring notices gets model-only localization.
- Stale CODEOWNERS produces confidently wrong ownership. The lookup is only as good as the metadata, and we do not detect staleness.
- Priority rules are hand-written, not learned.
- Non-English signals escalate to a human by policy.

---

## What we would build next

Feed misroute data back into CODEOWNERS as suggested amendments, so the organization's ownership map improves as a side effect of triage. Then active learning on the propose tier, where every human correction becomes a labeled example, making that tier a data pipeline rather than a cost.
