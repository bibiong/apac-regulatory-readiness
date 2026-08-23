# Failure analysis — obligation extraction

Run 2026-08-23. Five open-weight models via Ollama, temperature 0, seed fixed.
12 hand-annotated excerpts, 12 gold obligations. Reproduce with `make eval`.

---

## Headline results (prompt v2)

| model | P | R | F1 | carve-out recall | trigger fidelity | fabricated on empty item |
|---|---:|---:|---:|---:|---:|---:|
| llama3.2:3b | 0.69 | 0.92 | 0.79 | 0.33 (3) | 0.78 (9) | 1/1 |
| llama3.1:8b | 0.92 | 0.92 | 0.92 | 0.50 (4) | 0.67 (9) | 0/1 |
| gemma2:9b | 0.92 | 1.00 | **0.96** | 0.50 (4) | 0.80 (10) | 0/1 |
| mistral-nemo:12b | 0.85 | 0.92 | 0.88 | **0.00** (3) | 0.67 (9) | 0/1 |
| qwen2.5:14b | 0.92 | 1.00 | **0.96** | 0.50 (4) | 0.50 (10) | 0/1 |

**The F1 column is the least useful column here.** Four of five models score 0.88 or above,
which reads as "solved". Carve-out recall on the same runs is 0.00 to 0.50. If this harness
reported F1 alone — as most extraction evaluations do — it would report a capability the
models do not have.

---

## Finding 1 — the actor failure is universal

**`gold-004` failed on 5/5 models.** Not one of them got it right.

The excerpt contains two duties: one on *the Minister* (publish a list of designated
operators), one on *the platform* (publish an annual report). The prompt states explicitly
that a duty on a Minister, court or regulator is not a duty on a regulated entity. Every
model extracted the Minister's duty as a platform obligation anyway.

Every model found the real obligation too — so recall is unaffected and only precision
moves. That is exactly what makes it dangerous: the output looks complete, and the spurious
row is a duty the platform does not have. Downstream, that is engineering effort spent on
an obligation belonging to a government ministry.

**Instruction alone does not fix this.** The prompt already says not to do it. A structural
fix is needed — a separate actor-classification pass, or a validation step that rejects any
extraction whose actor is a public body.

## Finding 2 — carve-out detection depends on the *grammatical form* of the carve-out

This is the result worth the whole exercise. Carve-out recall is not uniformly bad; it is
bimodal, and it splits on syntax rather than difficulty.

| Item | Carve-out expressed as | Models capturing it |
|---|---|---:|
| gold-003 | Explicit — *"Sub-regulation (3) does not apply to…"* | 4/5 |
| gold-011 | Exception clause — *"…unless the direction has been varied"* | 3/5 |
| gold-008 | **Threshold condition** — *"with more than 100,000 regular monthly users"* | **0/5** |
| gold-010 | **Transitional deferral** — *"applies in respect of reporting periods commencing on or after 1 July 2027"* | **0/5** |

Where the text announces a carve-out with carve-out vocabulary, models find it. Where the
limit is carried by a threshold or a commencement date, **no model in the set found it, at
any parameter count.** Scaling from 3B to 14B does not help, because this is not a capacity
problem — it is a schema-mapping problem. The models classify text that *looks like* an
exception into `carve_out` and treat everything else as scope-setting prose.

**Why this specific failure costs money.** Both missed forms are the operationally
expensive ones:

- Missing the **threshold** (gold-008) over-scopes compliance. The duty is reported as
  applying to a service that sits below the user threshold, and remediation is funded for a
  population the law excludes.
- Missing the **transitional deferral** (gold-010) reports a duty as live when it does not
  bite until July 2027. In a readiness plan that becomes a phantom deadline competing for
  the same engineers as a real one.

A missed obligation gets caught in legal review, because counsel is reading for what the
platform must do. A missed carve-out is far more likely to survive review, because the
output is not wrong about the duty — only about its edges.

## Finding 3 — the smallest model fabricates, and the guardrail is what stops it

`gold-006` is a pure purpose clause with no operative duty. The correct answer is an empty list.

`llama3.2:3b` produced an obligation anyway, on v2, with an explicit instruction that an
empty list is correct and preferred. The other four models returned the empty list correctly
under v2. See the v1/v2 comparison below for what the instruction is worth.

`llama3.2:3b` also carries the worst precision in the set (0.69) with recall equal to the
larger models (0.92). It is not missing obligations — it is inventing them. For this task
that is the worse direction: the failure mode of a 3B model here is confident over-extraction.

## Finding 4 — trigger fidelity is mediocre everywhere and worst on the largest model

Trigger fidelity ranges 0.50–0.80, with `qwen2.5:14b` — tied for the best F1 — lowest at 0.50.

`gold-005` is the designed probe. The text says *"circumstances indicating the possibility of
a personal information breach"*. The common formulation in training data is "upon becoming
aware of a breach". Models normalise toward the familiar phrasing, and that single
normalisation moves when the statutory clock starts — which, under Korea's amended PIPA, is
the entire operational content of the provision.

**F1 and trigger fidelity are not correlated in this data.** A model can find every
obligation and be wrong about when each one starts.

---

## The v1 → v2 comparison: what prompt engineering actually bought

The superseded prompt is kept in the repo and is runnable (`make eval-compare`), so this
table can be reproduced rather than believed.

| model | F1 | carve-out recall | trigger fidelity | fabricated on empty item |
|---|---|---|---|---|
| llama3.2:3b | 0.80 → 0.79 | 0.33 → 0.33 | 0.75 → 0.78 | 1/1 → **1/1** |
| llama3.1:8b | 0.85 → **0.92** | 0.25 → **0.50** | 0.44 → **0.67** | 1/1 → **0/1** |
| gemma2:9b | 0.88 → **0.96** | 0.50 → 0.50 | 0.89 → *0.80* | 1/1 → **0/1** |
| mistral-nemo:12b | 0.96 → *0.88* | 0.25 → *0.00* | 0.70 → *0.67* | 0/1 → 0/1 |
| qwen2.5:14b | 0.88 → **0.96** | 0.50 → 0.50 | 0.89 → *0.50* | 1/1 → **0/1** |

**One guardrail worked cleanly. The other did not.**

**Rule 1 (an empty list is a correct and preferred answer) — worked.** Fabrication on the
empty-list item fell from **4/5 models to 1/5**. This is the clearest result in the study:
a single sentence granting permission to return nothing removed the failure on every model
except the 3B. The mechanism is not subtle — under v1 the schema requested a list and the
models supplied one, because nothing told them the list could be empty.

**Rule 6 (do not normalise unfamiliar statutory phrasing) — did not work.** It targets
trigger fidelity directly. Trigger fidelity rose on two models and **fell on three**,
including 0.89 → 0.50 on `qwen2.5:14b`, which is tied for the best F1 in the set. The rule
is retained because the instruction is correct in substance, but the evidence does not
support the claim that it helps, and this repository does not make claims its own harness
contradicts.

**F1 improved on 3 models and regressed on 2.** `mistral-nemo:12b` was the *best* model
under v1 (F1 0.96) and the addition of guardrails made it the second worst (0.88), taking
its carve-out recall from 0.25 to **0.00**. A prompt change evaluated on one model would
have been reported as a straightforward improvement. Evaluated on five, it is a trade.

**The honest summary a hiring manager should take from this section:** prompt engineering
bought one specific, reproducible safety property — the model will now decline to invent an
obligation where none exists — and bought nothing reliable on accuracy. Which is worth
knowing, and is only knowable because the harness exists. Anyone can assert that their
prompt improved. This is what it looks like to check, and find out that it half did.

## What was changed as a result

1. **Rule 1 added to the prompt** (empty list is correct and preferred) — fabrication on the
   empty-list item fell 4/5 → 1/5. Kept.
2. **Rule 6 added** (do not normalise unfamiliar statutory phrasing) — targeted Finding 4 and
   did not achieve it (trigger fidelity down on 3 of 5 models). Kept on substance, flagged as
   unsupported by evidence.
3. **Carve-outs promoted to a first-class scored field**, reported separately from
   precision and recall, because Finding 2 is invisible in an F1 score.
4. **Empty-list items kept in the gold set** despite contributing nothing to F1. They are the
   only direct measurement of fabrication.

## What was *not* fixed, and why that is stated rather than hidden

Findings 1 and 2 are **not fixed by prompting**. The v2 prompt contains explicit instructions
covering both, and both still fail — Finding 1 on 5/5 models. Adding more forceful wording
would produce a prompt that reads as though it had solved the problem while the measurement
says otherwise.

The honest conclusion: **this prompt is not fit to run unreviewed on threshold-conditioned or
transitionally-deferred provisions**, which are common in exactly the age-assurance and
transparency-reporting regimes this tracker covers. The mitigation is procedural, not
technical — extraction output is an input to human review, and the reviewer is told
specifically to check thresholds and commencement dates, because those are the two things
the tool is measured as unable to see.

## Limitations of this evaluation

- **12 items is a small gold set.** Differences of one or two items move F1 by ~0.08. The
  carve-out finding is stated with more confidence than the F1 ranking because it is 0/5 and
  0/5 on two independent items, not a narrow margin.
- **Constructed excerpts, not real statutory text.** Real provisions are longer, carry more
  cross-references, and are harder. These numbers are a ceiling.
- **Single annotator, no inter-annotator agreement.** The gold labels carry one reading with
  no measure of how contestable it is.
- **Lexical matching.** Deliberate — a model-judged matcher would make the score depend on a
  second unevaluated model — but it will occasionally miss a correct paraphrase that shares
  no key terms. The match threshold (0.67) is recorded in `metrics.json` so the result can be
  re-derived at a different setting.
- **Open-weight models only.** Frontier models would likely score higher. Whether they solve
  Finding 2 is an open question and the harness is built to answer it.
