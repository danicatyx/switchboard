# Switchboard: System and Reliability Brief

**Team:** Danica T (solo)
**Repo:** this repository
**Demo:** `python -m switchboard.demo` (runs in ~5 s, no credentials needed)

---

## What was built in the hackathon

One day, one person, zero API spend. [README.md](../README.md) is the full design; this brief reports what exists and what was measured. Everything listed as cut is stated in the brief rather than implied.

**Built and measured:** the fixed pipeline (normalize → correlate → localize → ownership → priority → gate → plan → execute) with a `state_trace` per signal; cross-source grounding; a live-enum localizer that cannot emit a service outside the catalog; ownership as a CODEOWNERS + catalog join with staleness surfaced; the YAML priority rule layer; three-tier gating with `c_eff = min(·)`; an executor that is the sole holder of write credentials, with a recipient allowlist, catalog-only channels, an idempotency WAL, and crash-safe retry; a 113-signal labeled corpus over five days; the replay harness with sliced metrics, two ablations, k=3 flip rate, ECE, a fault test, a 14-case attack corpus, a regression gate, and a failure gallery; incident resolution that emails every correlated reporter once; `doctor` with live credential checks; the demo.

**Cut, and why:**
- **No model was called.** The two LLM decision points (correlate judge, localizer) run on a deterministic stand-in (`heuristic.py`) behind the same `llm.call()` interface and schemas. Every number below therefore measures the *architecture* — what grounding, the lookup, and the gate do around a localizer — not model ability. Switching to Claude is `ANTHROPIC_API_KEY` in `.env`; nothing else changes.
- Retrieval is "all open incidents in 24 h". No BM25, embeddings, or RRF; at 113 signals over five days the candidate list never exceeds 15.
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

We measure this directly. Localization accuracy on the same fifteen emails is reported with and without cross-source grounding. That delta is the central claim of the project: **+0.171** (0.561 → 0.732) on 41 emails.

**Corollary that shaped the architecture:** once you know the service, ownership is a lookup, not a prediction. CODEOWNERS and the service catalog already encode it. Asking a model to guess team names from ticket text is a worse version of a join the organization already has. Measured: **6 misroutes with the lookup, 26 with a text-based guess**, on the same 68 localized signals.

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
| **Normalize** | Both sources collapse into one `Signal` type. Email keeps reporter and account, strips quoted replies and signatures, and flags non-English text (escalated by policy); telemetry keeps fingerprint, service tag, top frames, user count. | yes |
| **Correlate** | Fingerprint equality is a deterministic merge; so is a reply in an existing thread, but only from a reporter already on the incident, because `In-Reply-To` is attacker-controlled. Otherwise the judge sees open incidents within 24 h with structured features and decides match-or-new. A signal flagged as an injection attempt is never merged, and an incident that contains a flagged signal can never reach AUTO. | LLM (stand-in) |
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

**113 labeled signals** across both sources over five days (8–13 September): 25 telemetry alerts (21 distinct, 4 repeats to exercise the fingerprint shortcut), 41 emails with a correlated alert, 20 emails with no alert, 13 non-defect emails, and 14 attacks. Ground truth is an authored incident script, not derived from a fix: 37 incidents against a catalog of 15 services in 5 teams with deliberately overlapping surfaces (three export services, three identity services, three billing services), most services failing more than once so the recurrence rule has something to fire on. Emails were hand-written to three vagueness levels; most are "high" (symptom only, no feature or service named). Realism includes reply threads, an internal forward, signatures and disclaimers, typos, a Spanish-language report, out-of-office and bounce auto-replies, a sales inquiry, a job application, and a "never mind, it works now" reply in an open thread. One incident's email arrives before its alert, on purpose. Runs with the executor stubbed. Enrichment (deploy history, 46 deploys) is filtered to the 24 h before each signal's timestamp.

The stand-in localizer sees only catalog descriptions and deploy recency, both written before any email, so its numbers are leakage-free. The stand-in correlator additionally matches an email against the candidate incident's service symptom vocabulary and against the incident's earlier emails, which is candidate-side evidence a real judge would also have. The vocabulary was written before the second, larger half of the corpus and was not revised after seeing it.

### Results

| Metric | Result | Baseline | Note |
| --- | --- | --- | --- |
| **Localization acc@1 (email, grounded stratum, telemetry withheld)** | **0.561** | | n = 41. The hard task |
| **Localization acc@1 (email, grounded stratum, cross-source grounded)** | **0.732** | | Same 41 emails. The central claim |
| Localization acc@1 (email, ungrounded stratum) | 0.250 | | n = 20, unknown rate 0.550 |
| Localization acc@1 (telemetry) | 1.000 | | n = 25. Near-free from service tags |
| Realized provenance `grounded:telemetry` | 17 / 61 emails, acc 0.941 | n/a | The rest never correlated to their alert |
| Ownership lookup success | 1.000 | n/a | A lookup, reported as such |
| Ownership team correct | 0.912 (6 misroutes) | 0.618 (26 misroutes) | Baseline = text-based team guess |
| Correlation precision | 0.933 | | 2 false merges, both into second-order-injection alerts |
| Correlation recall | 0.322 | | Deliberately low, see below |
| Cross-source recall | 0.380 | 0.000 | Baseline = telemetry withheld |
| Pages avoided by correlation | 20 | 6 | 99 non-attack signals → 79 incidents |
| Priority within-one | 0.872 | | exact 0.465 |
| **Calibration (ECE)** | 0.076 grounded / 0.032 ungrounded | n/a | n = 42 / 57; thresholds fixed, not derived |
| **Flip rate (k=3)** | 0.000 | n/a | Trivial: the stand-in is deterministic. Meaningful only under a model |
| Auto-tier rate | 0.343 overall; 15 / 61 emails | n/a | |
| Noise → `unknown` | 0.769 | n/a | 3 of 13 non-defect emails were mislocalized |
| Injection attacks blocked | 14 / 14 | | 13 / 14 flagged; the 14th was blocked without being detected |

Three of these are the ones we would defend hardest:

**The grounding delta.** +0.171 on the same 41 emails is what having both signal sources is worth to a localizer this weak, at a cross-source recall of only 0.38. Every email that did correlate to its alert localized at 0.941. The lift is bounded by correlation, not by grounding: under a judge that correlates the other 26, the same mechanism applies to them. The demo shows the two cases side by side: `unknown → escalate` without the alert, `exports-scheduler 0.98 → auto` with it.

**Ownership as a lookup.** The 6 misroutes under the lookup are all upstream localization errors (the lookup itself never failed); of the 26 under the text guess, **11 went to a team that does not exist**. That is the silent failure the README warns about, counted.

**The attack that was not detected.** ATT-10 hides its instruction in a quoted reply. Normalization strips quoted text before any decision stage sees it, so the detector never saw an instruction, flagged nothing, and the signal still could not do anything: `unknown` localization escalates by construction. Detection is defense in depth; the architecture is the defense.

### Ablations

| Configuration | Email loc acc@1 (grounded stratum) | Cross-source recall | Ownership misroutes | Priority within-one |
| --- | --- | --- | --- | --- |
| Full (both sources, correlated) | 0.732 | 0.380 | 6 | 0.872 |
| **Email only, no telemetry grounding** | 0.561 | 0.000 | — | — |
| **No ownership lookup (text guesses team)** | 0.732 | 0.380 | 26 | 0.872 |
| Free-text services (no enum constraint) | not run | | | |

The second row quantifies cross-source grounding. The third quantifies why ownership is a lookup.

### Correlation is tuned asymmetrically

A false merge folds a live incident into an unrelated one and can delay detection for hours while the wrong team looks at it. A false split pages two teams instead of one and costs a human a minute. We tune for precision, accept mediocre recall, and report the two separately rather than as F1. Auto-merge requires confidence ≥ 0.85; between 0.60 and 0.85 the incident is created separately with a "possible relation" annotation. The confidence carried into the gate for a "new" decision that rejected a plausible match is `1 − 0.5·c`: the split penalty is halved because a split is cheap.

Measured: precision 0.933, recall 0.322. Most misses are emails whose vocabulary did not reach the stand-in's merge threshold against the right candidate — typically scoring 0.6–0.75, which lands in the "possible relation" band rather than a merge. One miss is the email that arrived before its alert (correctly not grounded: the alert did not exist yet).

The two false merges are instructive. Both are real customer emails that merged into incidents opened by the *second-order injection* alerts (a stack frame and an error string carrying instructions). Because the injection flag is **sticky on the incident**, neither email could act: both escalated instead of auto-paging. This rule was added after the first eval run exposed one of them reaching AUTO with the wrong service.

### Failure handling

- **Sentry withheld** (`--no-telemetry`): all 61 emails leave the AUTO tier (61 escalate, 0 auto), no email is dropped, and the telemetry signals never arrive. Asserted in `tests/test_chaos.py`.
- **Idempotency.** Every action carries `SHA256(signal_id ‖ action_type ‖ target)` into a write-ahead log. `tests/test_executor.py` executes the same plan twice and asserts one email was sent, and reloads the WAL to assert a pending action survives a crash. The demo resolves an incident, emails both reporters, and shows the retry refused.
- **Regression gate.** `make eval` compares eleven headline numbers against `evals/baseline.json` and fails on a drop of more than 0.02, advisory when the corpus fingerprint has changed.
- **Prompt injection.** 14 attacks: 2 direct override, 1 authority impersonation, 1 base64 payload, 1 hidden HTML comment, 1 zero-width-character override, 1 fake system notification, 1 third-order instruction inside a quoted reply, 3 second-order through telemetry (exception string, stack frame, echoed user-agent), 1 correlation poisoning aimed at the P1 payments incident, 1 thread-header spoof aimed at the SSO incident, 1 claimed urgency from a two-day-old free account. Asserted per attack: no action outside the closed set, no email to a non-reporter, no Slack target outside the catalog, no merge into a real incident, no P1 from claimed urgency. 14 / 14 pass. Defenses are architectural first (credential split, closed action set, recipient allowlist, reporter-guarded thread merge, no-merge-when-flagged, sticky incident flag) and prompt-level second.
- **Cross-customer leakage.** `tests/test_security.py` runs the whole corpus through the executor, resolves every multi-reporter incident, and asserts no outbound email mentions another reporter's address or account.

### What we did not automate

Three tiers. Above 0.85 the system acts. Between 0.60 and 0.85 it posts the proposed incident to Slack for one-click approval. Below that it escalates with evidence and no proposal. Abstention is a feature: 11 of 20 ungrounded emails returned `unknown` and 10 of 13 non-defect emails did, all of which escalated rather than routed; the Spanish-language report escalated by policy. The `ungrounded_localization` rule caps confidence at 0.70, so **no model-inferred localization can reach AUTO** in this build; every one of the 15 auto-tier emails was grounded.

---

## Known limitations

- **No model was evaluated.** The stand-in is a lexicon scorer. Model-dependent rows (ungrounded accuracy, flip rate, ECE) are placeholders for the harness, not claims about Claude.
- The corpus is synthetic and authored by the same person who built the system. The localizer was kept leakage-free by construction (descriptions and deploys predate the emails), but the incident script, emails, and lexicon share an author.
- Correlation recall is deliberately low as a consequence of precision tuning, and the stand-in correlator makes it lower: 26 of 41 grounded-stratum emails were split from their alert.
- Cross-source grounding depends on the telemetry alert firing first or concurrently. The corpus contains one email-before-alert case; it was not grounded, as expected.
- The language guard is a stopword ratio, not a language model. It escalated the one Spanish report and passed every English one, but that is 1 of 1.
- Stale CODEOWNERS produces confidently wrong ownership. One stale entry is in the fixture; `doctor` reports it and the lookup falls back to the catalog with `stale=True`, but nothing at decision time changes behavior on it.
- Priority rules are hand-written, not learned. `recurrence` now fires (the five-day corpus repeats services), but it is a hypothesis about severity, not a measured one: priority-exact is 0.465.
- Non-English signals are not handled.

---

## What we would build next

Put a model behind `llm.call()` and rerun the sweep — that is one environment variable and roughly ten dollars, and it turns three placeholder rows into measurements. Then feed misroute data back into CODEOWNERS as suggested amendments, so the organization's ownership map improves as a side effect of triage. Then active learning on the propose tier, where every human correction becomes a labeled example, making that tier a data pipeline rather than a cost.
