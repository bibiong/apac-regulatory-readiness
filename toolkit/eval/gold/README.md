# Gold standard — obligation extraction

## What these excerpts are

Each `text` block is a **constructed** statutory excerpt written in the drafting style of
the instrument named in `modelled_on`. They are not verbatim quotations. That is a
deliberate design choice, for two reasons:

1. **Eval control.** A gold set assembled from whatever real provisions happened to be
   convenient tests whatever difficulty those provisions happened to contain. Constructing
   the excerpts lets each item probe one specific failure mode — a carve-out, a duty
   resting on a different actor, a recital that reads like a duty but is not one.
2. **Reuse.** Constructed text carries no reproduction question, so the set can be
   published, forked, and extended.

The trade-off is real and worth stating: performance on constructed text is not proof of
performance on real statutes, which are longer, messier, and full of cross-references to
provisions not in the excerpt. This measures a **necessary** capability, not a sufficient
one. See `toolkit/eval/results/failure-analysis.md`.

## Annotation protocol

Annotated by hand, one pass, then re-read cold after 24 hours with the model outputs
hidden. Where the two passes disagreed, the excerpt was rewritten rather than adjudicated —
if the annotator cannot agree with themselves about what the text requires, the item is
testing ambiguity rather than extraction, and it does not belong in a gold set.

Single-annotator. That is a genuine limitation: no inter-annotator agreement figure can be
computed, so the gold labels carry the annotator's reading and no measure of how
contestable it is. A second annotator is the highest-value next addition to this repo.

## Fields

| Field | Meaning |
|---|---|
| `probe` | The one failure mode this item is designed to expose |
| `obligations` | Gold obligations. An empty list is a valid and important answer |
| `key_terms` | Terms that must appear in a prediction for it to be matched to this gold obligation. Matching is lexical and auditable rather than model-judged, so scoring cannot drift |
| `carve_out` | Where the duty does *not* apply. Missing one is scored separately from missing the duty, because the operational consequence differs |
| `distractors` | Text placed to invite a specific wrong extraction |
