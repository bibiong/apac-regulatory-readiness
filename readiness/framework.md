# Readiness assessment framework

A method for turning one regulatory regime into a dated, owned, costed remediation plan.

The output is not a compliance opinion. It is a **program management artefact**: which
obligations are met, which are not, who owns each gap, how long each fix takes, and
whether that fits inside the enforcement deadline. Whether the organisation *is* compliant
is a legal judgement made by counsel using this as an input.

---

## 1. Decompose the regime into assessable obligations

One row per obligation, at the granularity where a **single named owner** can say yes or no.

If a row needs two functions to answer it, it is two rows. This is the step most gap
assessments get wrong: an obligation stated at the level of "we must take reasonable steps
on age assurance" cannot be assessed, only debated.

## 2. Score maturity, 0–4

Scored on **evidence available today**, not on intent or on work in flight. Work in flight
is captured in the remediation plan, where it belongs.

| Score | Label | Test |
|---:|---|---|
| 0 | Absent | No control exists. |
| 1 | Ad hoc | Something happens, undocumented, dependent on specific people. |
| 2 | Defined | Documented process exists. Not consistently followed, not measured. |
| 3 | Operating | Followed consistently and measured. Evidence exists but is assembled on request. |
| 4 | Evidenced | Operating, measured, and evidence is retained continuously in a form a regulator could be shown tomorrow. |

**Why the bar for 4 is evidence retention, not performance.** Under an effort standard —
Australia's "reasonable steps", Japan's disclosure-completeness supervision — an
organisation that complies perfectly but cannot demonstrate it is in the same position as
one that did not comply. Evidence retention is a program deliverable, not administration.

## 3. Weight by exposure

`exposure = consequence × likelihood_of_scrutiny`

Likelihood of scrutiny is not a guess. Public enforcement signals — investigations opened,
notices issued, compliance updates published — are recorded per instrument in the tracker
and drive this factor directly. An obligation the regulator has publicly said it is
investigating is not a theoretical risk.

## 4. Compute time-to-remediate against the enforcement deadline

For each gap: estimated remediation duration, then **float** = time to deadline minus
remediation duration.

**Negative float is the finding.** Not the gap itself — the gap plus the fact that the
remaining time cannot accommodate the fix. This is the number that changes decisions,
because it converts "we have a gap" into "we have a gap and a date by which the decision
to accept it will have been made by default."

## 5. Sequence into phases

Ordered by float ascending, not by severity descending. A severe gap with nine months of
float is not this quarter's problem; a moderate gap with negative float is.

## 6. Assign owners and reassess on a fixed cadence

Every gap gets one named individual and a review date. The assessment is re-run on a
schedule, not when someone remembers — the whole failure mode this framework exists to
prevent is readiness work quietly losing to response work.

---

## Running it

```bash
python3 readiness/assess.py readiness/worked-example/au-smma-assessment.yaml
```

The tool computes scores, float, and phasing from the assessment data. The judgement is in
the inputs; the arithmetic should not also be a judgement call.

## The honest limitation

Maturity scores are self-assessed. A framework like this measures what an organisation
believes about itself, and every such framework flatters its subject unless the evidence
test at score 4 is applied strictly. The single most useful discipline is refusing to score
anything a 3 or 4 without naming the artefact that proves it — which is why `evidence` is a
required field and the tool fails the run when a high score lacks one.
