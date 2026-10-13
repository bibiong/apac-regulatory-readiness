# APAC Regulatory Readiness

**A maintained tracker of platform regulation across ten Asia-Pacific jurisdictions, plus
the three things you build on top of a tracker: a response workflow, a measured AI toolkit,
and a readiness assessment framework.**

📊 **[Browse the tracker →](https://brendaong.com/apac-regulatory-readiness/)**

> Not legal advice. A personal portfolio project, unaffiliated with any employer. Worked
> examples are fictional and labelled. See [DISCLAIMER.md](DISCLAIMER.md).

---

## Why this exists

APAC has no DSA. No single instrument, no single regulator, no harmonised reporting
calendar — instead roughly a dozen sovereign regimes converging on the same four themes
from different legal traditions and at different speeds.

The operational consequence: a single product change can trigger obligations in eight
jurisdictions with eight different deadlines, eight evidentiary standards, and eight
regulators who do not coordinate with one another. **Europe's difficulty is depth. APAC's
difficulty is concurrency** — and concurrency is a program-management problem before it is
a legal one.

This repository is what that program looks like when it is built rather than described.

---

## The four parts

### 1. [Tracker](tracker/) — 17 instruments, 10 jurisdictions

Structured YAML: instrument, regulator, status, obligations with their statutory clocks and
required evidence, deadlines, penalty exposure, public enforcement signals, and cited
sources. Rendered to a [static site](https://brendaong.com/apac-regulatory-readiness/)
with a cross-jurisdiction deadline board.

```bash
make validate     # schema, date coherence, sourcing discipline, staleness
make links        # plus: does every cited URL still resolve
make site         # regenerate the static site
```

The validator enforces a rule worth stating plainly: **an entry's confidence rating may not
exceed the strength of the sources actually cited.** You cannot mark something `high`
because you feel sure; you mark it `high` because you cite the instrument text. During the
initial build this caught a real overclaim on the Australian minimum-age entry.

### 2. [Workflow](workflow/) — the reactive half of the job

Intake schema, triage rubric, RACI, pre-submission QA checklist, and a **backwards timeline
generator** that plans from the deadline in working hours rather than calendar days.

```bash
make triage
```

Two fully worked fictional examples. The second one exists to make a specific point:

```
Time budget: 95.1 calendar hours → 17.2 usable hours

WARNING — weekend-arrival trap: 95 calendar hours reduce to 17.2 working hours
(18% of elapsed time). The calendar reads comfortable and the budget is not.
Decide now, at intake, between requesting the extension and standing up
out-of-hours cover — not on Monday morning, when both options have already shrunk.
```

### 3. [Toolkit](toolkit/) — AI with the measurement attached

Three prompts for regulatory work — obligation extraction, executive briefing,
cross-filing consistency checking — and, more importantly, **an evaluation harness with a
hand-annotated gold standard**, run locally against five open-weight models.

```bash
make eval           # evaluate the current prompt
make eval-compare   # re-run the superseded v1 prompt to reproduce the delta
```

| model | P | R | F1 | carve-out recall | trigger fidelity | fabricated on empty item |
|---|---:|---:|---:|---:|---:|---:|
| llama3.2:3b | 0.69 | 0.92 | 0.79 | 0.33 | 0.78 | 1/1 |
| llama3.1:8b | 0.92 | 0.92 | 0.92 | 0.50 | 0.67 | 0/1 |
| gemma2:9b | 0.92 | 1.00 | **0.96** | 0.50 | 0.80 | 0/1 |
| mistral-nemo:12b | 0.85 | 0.92 | 0.88 | **0.00** | 0.67 | 0/1 |
| qwen2.5:14b | 0.92 | 1.00 | **0.96** | 0.50 | 0.50 | 0/1 |

**The finding: F1 is the least useful column in that table.** Four of five models score 0.88
or better, which reads as solved. Carve-out recall on the same runs is 0.00–0.50.

And the failure is not random — it splits on the *grammar* of the carve-out:

| Carve-out expressed as | Models capturing it |
|---|---:|
| Explicit — *"does not apply to…"* | 4/5 |
| Exception — *"…unless the direction has been varied"* | 3/5 |
| **Threshold** — *"more than 100,000 monthly users"* | **0/5** |
| **Transitional deferral** — *"periods commencing on or after 1 July 2027"* | **0/5** |

No model in the set found either form, at any parameter count. Scaling 3B → 14B does not
help, because it is not a capacity problem. Both missed forms are the expensive ones: a
missed threshold over-scopes compliance to a population the law excludes; a missed deferral
puts a phantom 2027 deadline into a 2026 plan.

Separately, **every model tested (5/5) extracted a duty imposed on a Minister as a platform
obligation** — despite the prompt explicitly instructing otherwise.

#### What the prompt engineering actually bought

The superseded v1 prompt ships alongside v2 and is runnable, so the delta is reproducible:

| | v1 → v2 |
|---|---|
| Fabricated an obligation on a text containing none | **4/5 models → 1/5** |
| F1 | improved on 3 models, **regressed on 2** |
| Trigger fidelity (the thing rule 6 targets) | improved on 2, **fell on 3** |

One guardrail worked cleanly: a single sentence telling the model an empty list is a correct
answer removed the fabrication failure almost everywhere. The other did not — the rule
written specifically to protect trigger fidelity made it *worse* on three of five models,
including a fall from 0.89 to 0.50 on a top-scoring model. `mistral-nemo:12b` was the best
model under v1 and the guardrails made it the second worst.

Evaluated on one model, v2 would have been reported as a clean improvement. Evaluated on
five, it is a trade — and the rule that failed is documented as failing rather than quietly
retained as a success.

Full write-up, including what could not be fixed by prompting and why that is published
rather than buried: **[failure-analysis.md](toolkit/eval/results/failure-analysis.md)**.

### 4. [Readiness](readiness/) — obligation to owner to dated plan

A gap-assessment framework and a worked example against Australia's Social Media Minimum
Age regime.

```bash
make assess
```

The tool computes exposure, maturity gap and float, then phases the work by float ascending
— and checks owner concurrency, which is where the worked example turns interesting:

```
Every gap fits inside the deadline taken one at a time.

But the plan does not survive its own staffing.
Director, Age Assurance Engineering (20w vs 19w available).
Every per-item float above is positive and the aggregate is not.
```

Item-level plans that are each achievable and collectively impossible are the normal way a
remediation roadmap fails, and they fail silently because every individual row looks fine.

---

## Running it

```bash
pip install -r requirements-dev.txt   # or requirements.txt for runtime only
make validate && make test && make site
```

The eval additionally needs [Ollama](https://ollama.com) running locally with the five
models pulled. No API keys, nothing leaves the machine — which also means the numbers above
are reproducible rather than asserted.

## What this claims, and what it does not

This repository was created on **2026-08-23**. It does not claim a long history of sustained
monitoring. What it has is the machinery that makes sustained monitoring cheap — schema,
validator, link checker, staleness warnings, changelog discipline — so the history accrues
from that date forward and is checkable in the commit log.

Coverage depth is deliberately uneven and
[documented as such](docs/METHODOLOGY.md): three depth jurisdictions, five working, two
monitor-only. Claiming equal command of ten jurisdictions is a claim no individual can
support.

---

**Brenda Ong** · [brendaong.com](https://brendaong.com) · Singapore
