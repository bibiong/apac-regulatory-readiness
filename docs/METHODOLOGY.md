# Methodology

How the dataset is built and maintained, and what it does not claim.

## Scope

**In scope:** instruments that impose operational duties on a consumer social media or
messaging platform — content takedown, age assurance, transparency reporting, data
protection where it bites on platform operations, scam and fraud liability, licensing,
synthetic media labelling, localisation.

**Out of scope:** competition, tax, employment, telecoms carriage, sector-specific
financial regulation. Not because they do not matter, but because a tracker whose scope is
"regulation" is a tracker of nothing. Ten jurisdictions of platform-operational duty is
already at the edge of what one person can keep current, which is the honest constraint.

## Jurisdiction selection

Ten jurisdictions, at deliberately uneven depth:

| Tier | Jurisdictions | Standard |
|---|---|---|
| Depth | Singapore, Australia, India | Instrument-level entries, enforcement signals tracked, primary sources where obtainable |
| Working | Korea, Japan, Indonesia, Malaysia, Vietnam | Named instrument, regulator, core obligations, key dates |
| Monitor | Thailand, Philippines | Presence and direction of travel only |

**Uneven depth is a design decision, not a gap.** Claiming equal command of ten
jurisdictions would be a claim no individual can support. The tiering is stated so a reader
knows which entries to lean on. The Philippines entry is deliberately the thinnest in the
set and says so in its own notes.

## Sourcing rules

1. **Every instrument carries at least one source.** The validator fails the build otherwise.
2. **Confidence is earned by the strongest source cited**, and the validator enforces it:
   - `high` — the instrument text itself was read (e.g. Singapore Statutes Online).
   - `medium` — a regulator publication.
   - `low` — secondary reporting only.
   You cannot mark an entry `high` because you are confident. You mark it `high` because a
   primary source is cited. During the initial build this rule caught a genuine overclaim
   on the Australian minimum-age entry, which was cited to regulator publications and had
   been marked `high`; it is now `medium`.
3. **Enforcement signals require a resolvable URL.** An uncited enforcement claim is a rumour.
4. **`last_verified` is a date a human looked**, not a date a file changed.

## Freshness

Entries are re-verified on a 45-day window; the validator warns past it. The window is set
by the observed cadence of the fastest-moving jurisdictions in the set (Australia and
India), not by convenience.

Re-verification passes are recorded in `CHANGELOG.md` — including passes where nothing
changed, because the cadence is the thing being evidenced and a quiet month is data.

## What "maintained" means here, precisely

This repository was created on 2026-08-23. It does not have, and does not claim, a long
history of sustained monitoring. What it has is the machinery that makes sustained
monitoring cheap: a schema, a validator, a link checker, a staleness warning, and a
changelog discipline. The history accrues from the creation date forward and is checkable
in the commit log.

That distinction is deliberate. A tracker whose value proposition is "months of evidenced
attention" is only worth anything if the months are real.

## Known limitations

- **Not a lawyer's product.** Obligations are a program manager's working summary for
  triage and sequencing, not statements of legal effect.
- **English-language sources dominate.** Local-language primary texts for Japan, Korea,
  Indonesia and Vietnam are cited at regulator level rather than read in full. Those
  entries carry `low` or `medium` confidence accordingly.
- **Two hosts refuse automated link checks** (`www.esafety.gov.au`, `transparency.meta.com`).
  Their links are flagged for manual verification rather than silently reported as healthy
  or broken.
- **Single maintainer, single reading.** No second reviewer. For the eval gold set the same
  limitation applies and is stated there.
