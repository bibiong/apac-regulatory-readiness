# Changelog

Dated entries only. This file exists so that maintenance is visible: a regulatory tracker
is a claim about sustained attention, and a claim about sustained attention should be
checkable against dated evidence rather than asserted.

Every entry records what changed and, where an instrument's facts moved, what the source
was. Format loosely follows Keep a Changelog.

## 2026-08-23 — initial build

**Tracker**
- Seeded 17 instruments across 10 APAC jurisdictions (AU, IN, JP, KR, SG, ID, VN, MY, TH, PH).
- Schema, validator, and link checker.
- Verified against primary and regulator sources on this date. Four facts spot-checked
  against current reporting during the build: Korea PIPA commencement and penalty basis,
  India IT Amendment Rules 2026 effective date and SGI duties, Australia eSafety
  enforcement posture and the five platforms under investigation, Singapore OSC
  commencement.
- Known gap: `www.esafety.gov.au` and `transparency.meta.com` refuse automated link checks.
  Both are flagged for manual verification rather than reported as broken.

**Workflow**
- Intake schema, triage rubric v1.2, response plan template, RACI, pre-submission QA checklist.
- Backwards timeline generator with working-hours arithmetic.
- Two worked fictional examples: a compulsory information notice, and a Friday-evening
  arrival that demonstrates the weekend trap.

**Toolkit**
- Obligation extraction prompt v1 and v2, both runnable.
- Gold standard: 12 hand-annotated constructed excerpts, 12 obligations, 4 with carve-outs,
  1 deliberate empty-list item.
- Evaluation harness running locally against Ollama.
- Full run of both prompts across five models (llama3.2:3b, llama3.1:8b, gemma2:9b,
  mistral-nemo:12b, qwen2.5:14b). Headline results:
  - F1 0.79–0.96 against carve-out recall 0.00–0.50 on the same runs.
  - Threshold-conditioned and transitionally-deferred carve-outs: **0/5 models**, both items.
  - A duty imposed on a Minister extracted as a platform obligation: **5/5 models**.
  - v2 guardrails cut fabrication on the empty-list item from 4/5 models to 1/5, and moved
    nothing else reliably — F1 regressed on 2 of 5, trigger fidelity on 3 of 5.
- Corrected an unsupported claim in the v2 prompt's design notes, which asserted a v1
  failure rate that had not been measured at the time of writing. Now measured and stated
  as 4/5.

**Site**
- Static tracker site generated to `site/`, with a cross-jurisdiction deadline board.
- CI gate fails the build if `site/` is stale relative to `tracker/data/`.

**Readiness**
- Framework and a worked gap assessment against Australia's Social Media Minimum Age regime.
- Scoring tool with owner-concurrency analysis.

---

## Maintenance log

Re-verification passes are recorded here with the date and what moved. An entry saying
"checked, nothing changed" is a real entry and belongs in this list — it is evidence of the
cadence, which is the thing being demonstrated.
