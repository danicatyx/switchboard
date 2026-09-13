# Switchboard: System and Reliability Brief

**Team:** Danica T (solo)
**Repo:** this repository
**Demo:** `python -m switchboard.demo` (runs in ~5 s, no credentials needed)

---

## What was built in the hackathon

One day, one person, zero API spend. [README.md](../README.md) is the full design; this brief reports what exists and what was measured. Everything listed as cut is stated in the brief rather than implied.

**Built and measured:** the fixed pipeline (normalize → correlate → localize → ownership → priority → gate → plan → execute) with a `state_trace` per signal; cross-source grounding; a live-enum localizer that cannot emit a service outside the catalog; ownership as a CODEOWNERS + catalog join with staleness surfaced; the YAML priority rule layer; three-tier gating with `c_eff = min(·)`; an executor that is the sole holder of write credentials, with a recipient allowlist, catalog-only channels, an idempotency WAL, and crash-safe retry; a 46-signal labeled corpus; the replay harness with sliced metrics, two ablations, k=3 flip rate, ECE, a fault test, an 8-case attack corpus, and a failure gallery; `doctor`; the demo.

**Cut, and why:**
- **No model was called.** The two LLM decision points (correlate judge, localizer) run on a deterministic stand-in (`heuristic.py`) behind the same `llm.call()` interface and schemas. Every number below therefore measures the *architecture* — what grounding, the lookup, and the gate do around a localizer — not model ability. Switching to Claude is `ANTHROPIC_API_KEY` in `.env`; nothing else changes.
- Retrieval is "all open incidents in 24 h". No BM25, embeddings, or RRF; at 46 signals the candidate list never exceeds 12.
- The Evaluation Agent's backward transitions are schema validation with one retry; a second failure is `ESCALATE`.
- One fault test (Sentry withheld), not a per-adapter chaos matrix.
- **Slack, email, and GitHub have real adapters** (`integrations/slack.py`, `email.py`, `github.py`; stdlib only, configured by `.env`). The eval harness never uses them: it runs against the corpus with the executor stubbed. Sentry has no receiver; telemetry is fixture-fed. Linear is a fake.
- `−enum` and `−rules` ablations were not run.
- Thresholds (`τ_auto = 0.85`, `τ_prop = 0.60`) are the README's values, not re-derived from the reliability curve; the corpus is too small to bin honestly.

---

## What it does

Switchboard turns scattered failure signals into one owned, tracked incident and closes the loop with everyone who reported it.

It ingests from two directions at once: **customer emails** arriving at the support inbox, and **telemetry alerts** from error monitoring. It correlates signals that describe the same underlying failure into a single incident, localizes that incident to the responsible service, resolves the owning team through the ownership metadata the organization already maintains, pages that team once in Slack, and emails every correlated reporter when the issue closes.

The economic work is incident triage in an organization with many teams and many repositories, where the expensive part is not writing the ticket but working out which of fifteen (here) or forty (there) services broke and who owns it. Current cost per incident: not measured; the corpus is synthetic.

---

## The insight the system is built around

**Telemetry knows where. Email knows who and how bad. Neither knows both.**

A stack trace names the failing service for free. A customer writing "the files we get every morning at 6 haven't shown up today" does not, and inferring it is the genuinely hard step. Conversely, an alert has no idea that three enterprise accounts are blocked on it.

So the system correlates across sources and lets each fill the other's gap:

- A customer email that correlates to a telemetry alert **inherits the alert's service attribution** at near-certain confidence, rather than relying on the model's guess.
- A telemetry alert that correlates to customer emails **inherits real blast radius**: distinct accounts affected, reported at what time, blocked on what.

We measure this directly. Localization accuracy on the same fifteen emails is reported with and without cross-source grounding. That delta is the central claim of the project: **+0.333** (0.467 → 0.800).

**Corollary that shaped the architecture:** once you know the service, ownership is a lookup, not a prediction. CODEOWNERS and the service catalog already encode it. Asking a model to guess team names from ticket text is a worse version of a join the organization already has. Measured: **2 misroutes with the lookup, 10 with a text-based guess**, on the same 30 localized signals.

---

## External apps

| App | Role | Direction | In this build |
| --- | --- | --- | --- |
| **Slack** | Pages the owning team once per incident, with correlated blast radius attached; proposals and escalations to triage channels | write | `SLACK_BOT_TOKEN` (chat.postMessage, per-team channels) or `SLACK_WEBHOOK_URL`; console when unset |
| **Email** | Ingests customer reports; sends acknowledgment and resolution notices to every correlated reporter | read + write | IMAP read (`ImapInbox.fetch_unseen`) and SMTP send with `In-Reply-To` threading; Gmail via app password, no OAuth |
| **GitHub** | CODEOWNERS and service catalog for ownership resolution; recent deploys as localization evidence | read | `python -m switchboard.sync` pulls `CODEOWNERS`, `catalog.yaml`, and commits touching `services/<name>/` into a cache the loaders prefer over `fixtures/` |
| **Sentry** | Telemetry signals: fingerprints, stack traces, affected-user counts, error-rate deltas | read | no receiver; JSONL drop file in live mode, corpus rows in eval |

Credentials live in `.env` (see `.env.example`). Read credentials (IMAP, GitHub) are constructed by the pipeline; write credentials (Slack, SMTP) are constructed only inside `WriteCredentials.from_env()` and handed only to the executor. Live mode is `python -m switchboard.run --sources gmail,sentry --max-tier propose`, which caps every decision at PROPOSE by default so nothing external happens without a human click.

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
| **Normalize** | Both sources collapse into one `Signal` type. Email keeps reporter and account and strips quoted replies and signatures; telemetry keeps fingerprint, service tag, top frames, user count. | yes |
| **Correlate** | Fingerprint equality is a deterministic merge. Otherwise the judge sees open incidents within 24 h with structured features and decides match-or-new. A signal flagged as an injection attempt is never merged, and an incident that contains a flagged signal can never reach AUTO. | LLM (stand-in) |
| **Localize** | Inherits `service_tag` from any correlated telemetry at 0.98. Otherwise selects from the live enum or returns `unknown`. | LLM (stand-in), or inherited |
| **Ownership** | service → CODEOWNERS + catalog → team, Slack channel, on-call. Stale CODEOWNERS entries fall back to the catalog and are flagged. | **yes, a lookup** |
| **Priority** | Model proposes; six ordered YAML rules adjust on blast radius, error-rate delta, tier-0, recurrence, new-free-reporter, and ungrounded localization (which caps confidence, not priority). | rules |

Three properties we test:

1. **Each stage is separately scorable**, so a regression localizes to one prompt. Every `DecisionRecord` carries a `state_trace`.
2. **The model cannot name a service or team that does not exist.** The localizer's output schema is a `Literal` built from the catalog at call time; team is a lookup. Schema-invalid output is a logged failure, never coerced.
3. **Only the executor holds write credentials.** `tests/test_credentials.py` greps every decision-stage module for `WriteCredentials` and fails if any references it.

---

## How we know it works

### Replay corpus

**46 labeled signals** across both sources: 10 telemetry alerts (8 distinct, 2 repeats to exercise the fingerprint shortcut), 15 emails with a correlated alert, 9 emails with no alert, 4 non-defect emails, and 8 attacks. Ground truth is an authored incident script, not derived from a fix: 15 incidents over 36 hours against a catalog of 15 services in 5 teams with deliberately overlapping surfaces (three export services, three identity services, three billing services). Emails were hand-written to three vagueness levels; most are "high" (symptom only, no feature or service named). One incident's email arrives before its alert, on purpose. Runs with the executor stubbed. Enrichment (deploy history) is filtered to the 24 h before each signal's timestamp.

The stand-in localizer sees only catalog descriptions and deploy recency, both written before any email, so its numbers are leakage-free. The stand-in correlator additionally matches an email against the candidate incident's service symptom vocabulary, which is candidate-side evidence a real judge would also have.

### Results

| Metric | Result | Baseline | Note |
| --- | --- | --- | --- |
| **Localization acc@1 (email, grounded stratum, telemetry withheld)** | **0.467** | | n = 15. The hard task |
| **Localization acc@1 (email, grounded stratum, cross-source grounded)** | **0.800** | | Same 15 emails. The central claim |
| Localization acc@1 (email, ungrounded stratum) | 0.444 | | n = 9, unknown rate 0.222 |
| Localization acc@1 (telemetry) | 1.000 | | n = 10. Near-free from service tags |
| Realized provenance `grounded:telemetry` | 11 / 24 emails, acc 0.909 | n/a | 9 of 15 grounded-stratum emails correlated; 2 ungrounded-stratum emails merged into attack alerts (see below) |
| Ownership lookup success | 1.000 | n/a | A lookup, reported as such |
| Ownership team correct | 0.933 (2 misroutes) | 0.667 (10 misroutes) | Baseline = text-based team guess |
| Correlation precision | 0.882 | | 2 false merges, both into second-order-injection alerts |
| Correlation recall | 0.455 | | Deliberately low, see below |
| Cross-source recall | 0.550 | 0.000 | Baseline = telemetry withheld |
| Pages avoided by correlation | 11 | 2 | 38 non-attack signals → 27 incidents |
| Priority within-one | 0.941 | | exact 0.618 |
| **Calibration (ECE)** | 0.022 grounded / 0.051 ungrounded | n/a | n = 21 / 17; too few per bin to derive thresholds |
| **Flip rate (k=3)** | 0.000 | n/a | Trivial: the stand-in is deterministic. Meaningful only under a model |
| Auto-tier rate | 0.474 overall; 9 / 24 emails | n/a | |
| Noise → `unknown` | 0.75 | n/a | 1 of 4 non-defect emails was mislocalized |
| Injection attacks blocked | 8 / 8 | | 8 / 8 also flagged and escalated |

Three of these are the ones we would defend hardest:

**The grounding delta.** +0.333 on the same fifteen emails is what having both signal sources is worth to a localizer this weak. Under a stronger localizer the delta shrinks in absolute terms — a strong model gets more of the ungrounded cases right — but the mechanism is the same: the email inherits a fact instead of earning a guess. The demo shows the two cases side by side: `unknown → escalate` without the alert, `exports-scheduler 0.98 → auto` with it.

**Ownership as a lookup.** The 2 misroutes under the lookup are both upstream localization errors (the lookup itself never failed); of the 10 under the text guess, **7 went to a team that does not exist**. That is the silent failure the README warns about, counted.

**Flip rate, honestly.** It is 0.000 because the stand-in is deterministic. This row is in the table because it is the one almost nobody measures and the harness measures it; it becomes a real number the moment a model is behind `llm.call()`.

### Ablations

| Configuration | Email loc acc@1 (grounded stratum) | Cross-source recall | Ownership misroutes | Priority within-one |
| --- | --- | --- | --- | --- |
| Full (both sources, correlated) | 0.800 | 0.550 | 2 | 0.941 |
| **Email only, no telemetry grounding** | 0.467 | 0.000 | — | — |
| **No ownership lookup (text guesses team)** | 0.800 | 0.550 | 10 | 0.941 |
| Free-text services (no enum constraint) | not run | | | |

The second row quantifies cross-source grounding. The third quantifies why ownership is a lookup.

### Correlation is tuned asymmetrically

A false merge folds a live incident into an unrelated one and can delay detection for hours while the wrong team looks at it. A false split pages two teams instead of one and costs a human a minute. We tune for precision, accept mediocre recall, and report the two separately rather than as F1. Auto-merge requires confidence ≥ 0.85; between 0.60 and 0.85 the incident is created separately with a "possible relation" annotation. The confidence carried into the gate for a "new" decision that rejected a plausible match is `1 − 0.5·c`: the split penalty is halved because a split is cheap.

Measured: precision 0.882, recall 0.455. The six grounded-stratum emails that did not correlate include the one that arrived before its alert (correctly not grounded: the alert did not exist yet) and five whose vocabulary did not reach the stand-in's merge threshold; three of those returned `unknown` and escalated, two were inferred correctly and proposed.

The two false merges are instructive. Both are real customer emails that merged into incidents opened by the *second-order injection* alerts (a stack frame and an error string carrying instructions). One landed on the right service by coincidence, one on the wrong one. Because the injection flag is **sticky on the incident**, neither email could act: both escalated instead of auto-paging. This rule was added after the first eval run exposed one of them reaching AUTO with the wrong service.

### Failure handling

- **Sentry withheld** (`--no-telemetry`): all 24 emails leave the AUTO tier (24 escalate, 0 auto), no email is dropped, and the telemetry signals never arrive. Asserted in `tests/test_chaos.py`.
- **Idempotency.** Every action carries `SHA256(signal_id ‖ action_type ‖ target)` into a write-ahead log. `tests/test_executor.py` executes the same plan twice and asserts one email was sent, and reloads the WAL to assert a pending action survives a crash.
- **Prompt injection.** 8 attacks: 2 direct override, 1 authority impersonation, 1 base64 payload, 2 second-order through telemetry (payload inside an exception string and a stack frame), 1 correlation poisoning aimed at the P1 payments incident, 1 claimed urgency from a two-day-old free account. Asserted per attack: no action outside the closed set, no email to a non-reporter, no Slack target outside the catalog, no merge into a real incident, no P1 from claimed urgency. 8 / 8 pass. Defenses are architectural first (credential split, closed action set, recipient allowlist, no-merge-when-flagged) and prompt-level second.

### What we did not automate

Three tiers. Above 0.85 the system acts. Between 0.60 and 0.85 it posts the proposed incident to Slack for one-click approval. Below that it escalates with evidence and no proposal. Abstention is a feature: 2 of 9 ungrounded emails returned `unknown` and 3 of 4 non-defect emails did, all of which escalated rather than routed. The `ungrounded_localization` rule caps confidence at 0.70, so **no model-inferred localization can reach AUTO** in this build; every one of the 9 auto-tier emails was grounded.

---

## Known limitations

- **No model was evaluated.** The stand-in is a lexicon scorer. Model-dependent rows (ungrounded accuracy, flip rate, ECE) are placeholders for the harness, not claims about Claude.
- The corpus is synthetic and authored by the same person who built the system. The localizer was kept leakage-free by construction (descriptions and deploys predate the emails), but the incident script, emails, and lexicon share an author.
- Correlation recall is deliberately low as a consequence of precision tuning. Six genuinely related emails were split.
- Cross-source grounding depends on the telemetry alert firing first or concurrently. The corpus contains one email-before-alert case; it was not grounded, as expected.
- Stale CODEOWNERS produces confidently wrong ownership. One stale entry is in the fixture; `doctor` reports it and the lookup falls back to the catalog with `stale=True`, but nothing at decision time changes behavior on it.
- Priority rules are hand-written, not learned. The `recurrence` rule never fires because there is no incident history fixture.
- Non-English signals are not handled.

---

## What we would build next

Put a model behind `llm.call()` and rerun the sweep — that is one environment variable and roughly ten dollars, and it turns three placeholder rows into measurements. Then feed misroute data back into CODEOWNERS as suggested amendments, so the organization's ownership map improves as a side effect of triage. Then active learning on the propose tier, where every human correction becomes a labeled example, making that tier a data pipeline rather than a cost.
