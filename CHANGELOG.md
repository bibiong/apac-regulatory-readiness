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

### 2026-09-15 — re-verification pass

**Changed**
- `kr-pipa-2026-amendments`: `passed` → `in_force`. The 11 September 2026 commencement arrived;
  the validator flagged the entry on its own ("status 'passed' but commencement has arrived").
  Re-checked against current secondary reporting: no postponement reported. Not yet confirmed
  against a PIPC primary notice, so confidence stays `medium`. Added Hunton source.

**Fixed**
- The weekly scheduled CI run had failed on 7 and 14 September. Cause: the site generator stamped
  the build date and counted days-to-deadline from it, so a scheduled build on any later day
  differed from the committed site and the staleness check failed regardless of the data. The
  build is now a pure function of the dataset (anchored on the latest `last_verified` date);
  day counts are computed in the reader's browser. Regression test added.

**Not changed**
- All other entries remain at `last_verified: 2026-08-23`, inside the 45-day freshness window
  until 2026-10-07. A full pass on the remaining 16 entries is due before that date.

### 2026-10-13 — full re-verification pass (all 17 entries)

The first complete pass. Every entry re-checked against current sources and re-dated; the
16 entries still at 2026-08-23 had passed the 45-day freshness window on 2026-10-07 and the
validator was warning on all of them.

**Substantive changes**
- `vn-draft-decree-minor-posting-2026`: the draft changed direction. The August entry recorded
  a posting ban for under-16s; September reporting has the ministry stepping back to parental
  registration and supervision, with the posting ban falling to under-13s. Added the draft
  gaming provisions (age verification, guardian registration, 60-minute daily cap). Still
  consultation stage. The obligation as recorded in August would now be wrong in both scope
  and age threshold.
- `my-online-safety-act-2025`: the initial entry missed the two subsidiary codes. The Risk
  Mitigation Code and Child Protection Code took effect 2026-06-01 and carry the substantive
  systemic duties. Added, with citation Act 866.
- `th-etda-advertiser-kyc-2026`: instrument properly identified as the Notification on Measures
  for Prevention of Technology Crime for Online Social Media, published 2026-05-05, effective
  180 days later. Two missed details added: verification lapses after one year, making this a
  recurring cycle rather than a one-off check, and the duty can reach agencies and foreign
  advertisers, not only the account holder. Nearest live deadline in the tracker.
- `in-it-amendment-rules-2026`: added the quarterly user-advisory duty, which the initial entry
  missed. Noted that the labelling standard is qualitative rather than the proposed
  10%-surface-area watermark.
- `ph-anti-financial-scamming`: identified as RA 12010 (signed July 2024), operationalised via
  BSP circulars with a 2026-06-30 institutional deadline. Primary citation added, confidence
  raised `low` → `medium`. Monitor posture unchanged: the duties sit on financial institutions,
  not platforms.
- `au-strengthening-enforcement-2026`: penalty recorded as AUD 99m / 60,000 penalty units as
  drafted, against the current AUD 49.5m / 30,000 units. Referred to a parliamentary inquiry
  due to report 2026-08-25; no passage recorded, so status stays `draft`. A press summary
  giving 150,000 units / AUD 54.6m conflicts with this and was not used — flagged in the entry.

**Enforcement signals added**
- `id-pp-tunas-2025`: Komdigi pressed Meta on under-16 deactivation (2026-09-30) and publicly
  flagged gaps in Meta's child-safety compliance, naming Threads for filing no reports
  (2026-10-09). Now the most actively enforced entry against Meta specifically.
- `jp-idpa`: the July 2026 corrective recommendation is confirmed, dated 2026-07-24, with all
  five recipients named — X, Google, Meta, Shonan Seibu Home and Dwango.
- `au-smma-2024`: investigations into the five platforms remain open with no published
  enforcement decision, past the mid-2026 date eSafety had indicated.

**Checked, no change found**
- All four Singapore entries, `in-dpdp-2023`, `au-bose`, `vn-decree-147-2024`. Recorded because
  the cadence is the thing being evidenced and a quiet entry is a result.

**Note on what this pass cost**
Six of the seventeen entries changed substantively in seven weeks, and two of those changes
(Vietnam's reversal, Malaysia's subsidiary codes) would have made the entry actively
misleading rather than merely stale. That is the argument for the freshness window existing
at all.

