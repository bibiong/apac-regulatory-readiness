#!/usr/bin/env python3
"""Score a readiness assessment and phase its remediation against the enforcement deadline.

    python3 readiness/assess.py readiness/worked-example/au-smma-assessment.yaml
    python3 readiness/assess.py <file> --markdown

Computes, per obligation: exposure, gap size, remediation float. Sequences by float
ascending, because the binding constraint is time remaining, not severity.

Fails the run if any obligation scored 3 or 4 has no evidence recorded. A maturity
framework with no evidence test measures optimism.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

MAX_MATURITY = 4
LABELS = {0: "Absent", 1: "Ad hoc", 2: "Defined", 3: "Operating", 4: "Evidenced"}


def as_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return datetime.strptime(str(v), "%Y-%m-%d").date()


def analyse(doc: dict):
    meta = doc["assessment"]
    assessed = as_date(meta["assessed_on"])
    deadline = as_date(meta["enforcement_deadline"])
    weeks_available = (deadline - assessed).days / 7

    errors, rows = [], []
    for ob in doc["obligations"]:
        m = ob["maturity"]
        if m >= 3 and not (ob.get("evidence") or "").strip():
            errors.append(f"{ob['id']}: maturity {m} claimed with no evidence recorded")
        if not 0 <= m <= MAX_MATURITY:
            errors.append(f"{ob['id']}: maturity {m} out of range 0-{MAX_MATURITY}")

        exposure = ob["consequence"] * ob["likelihood"]          # 1..25
        gap = MAX_MATURITY - m                                    # 0..4
        # Risk-weighted gap: exposure means nothing where there is no gap, and a gap
        # means little where nothing is watching. The product is what ranks work.
        weighted = exposure * gap
        weeks = ob.get("remediation_weeks", 0) or 0
        float_weeks = weeks_available - weeks
        rows.append({**ob, "exposure": exposure, "gap": gap, "weighted": weighted,
                     "weeks": weeks, "float": float_weeks,
                     "finish": assessed + timedelta(weeks=weeks)})

    rows.sort(key=lambda r: (r["float"], -r["weighted"]))
    return meta, assessed, deadline, weeks_available, rows, errors


def phase(rows, weeks_available):
    """Three phases by float. Negative float is its own phase because it is a decision,
    not a schedule — either the scope shrinks, the date moves, or the risk is accepted."""
    out = {"Phase 0 — negative float (decision required)": [],
           "Phase 1 — must start now": [],
           "Phase 2 — schedulable": []}
    for r in rows:
        if r["float"] < 0:
            out["Phase 0 — negative float (decision required)"].append(r)
        elif r["float"] < weeks_available * 0.34:
            out["Phase 1 — must start now"].append(r)
        else:
            out["Phase 2 — schedulable"].append(r)
    return out


def render(meta, assessed, deadline, weeks_available, rows, md: bool) -> str:
    b = "**" if md else ""
    L = [f"{'# ' if md else ''}Readiness assessment — {meta['subject']}", ""]
    L.append(f"{b}Regime{b}: {meta['regime']}  ({meta['instrument_id']})")
    L.append(f"{b}Assessed{b}: {assessed}   {b}Enforcement deadline{b}: {deadline}   "
             f"({weeks_available:.0f} weeks available)")
    L.append(f"{b}Next review{b}: {meta['next_review']}")
    L.append("")

    total_gap = sum(r["gap"] for r in rows)
    max_gap = MAX_MATURITY * len(rows)
    mean_m = sum(r["maturity"] for r in rows) / len(rows)
    L.append(f"{b}Overall maturity{b}: {mean_m:.1f} / {MAX_MATURITY}  "
             f"({max_gap - total_gap}/{max_gap} of available maturity achieved)")
    L.append("")

    if md:
        L.append("| # | Obligation | Owner | Maturity | Exposure | Weighted gap | Weeks | Float |")
        L.append("|---|---|---|---:|---:|---:|---:|---:|")
        for r in rows:
            L.append(f"| {r['id']} | {r['obligation']} | {r['owner']} | "
                     f"{r['maturity']} ({LABELS[r['maturity']]}) | {r['exposure']} | "
                     f"{r['weighted']} | {r['weeks']} | {r['float']:+.0f}w |")
    else:
        for r in rows:
            L.append(f"  {r['id']}  {r['obligation']}")
            L.append(f"        owner={r['owner']}")
            L.append(f"        maturity={r['maturity']} ({LABELS[r['maturity']]})   "
                     f"exposure={r['exposure']}   weighted gap={r['weighted']}   "
                     f"remediation={r['weeks']}w   float={r['float']:+.0f}w")
    L.append("")

    L.append(f"{'## ' if md else ''}Phased plan")
    L.append("")
    for name, group in phase(rows, weeks_available).items():
        L.append(f"{b}{name}{b}")
        if not group:
            L.append("    (none)")
        for r in group:
            L.append(f"    {r['id']}  {r['obligation']}")
            L.append(f"        {r['owner']} · {r['weeks']}w · finishes {r['finish']} · float {r['float']:+.0f}w")
            L.append(f"        Action: {' '.join(r['remediation'].split())}")
        L.append("")

    # Owner concurrency. Remediation estimates are per-workstream and assume the owner is
    # free; where one person owns several, the plan silently assumes parallelism that does
    # not exist. This is the most common way a phased plan is wrong on the first day.
    load: dict[str, list] = {}
    for r in rows:
        load.setdefault(r["owner"], []).append(r)
    overloaded = {o: rs for o, rs in load.items() if len(rs) > 1}
    if overloaded:
        L.append(f"{'## ' if md else ''}Owner concurrency")
        L.append("")
        L.append("Remediation estimates assume the owner is free. Where one owner holds "
                 "several workstreams, serialised duration is the honest number:")
        L.append("")
        for owner, rs in sorted(overloaded.items(), key=lambda kv: -sum(x["weeks"] for x in kv[1])):
            serial = sum(x["weeks"] for x in rs)
            longest = max(x["weeks"] for x in rs)
            serial_float = weeks_available - serial
            marker = "" if serial_float >= 0 else "   <-- exceeds the deadline if serialised"
            L.append(f"    {b}{owner}{b} — {len(rs)} workstreams, "
                     f"{longest}w if parallel, {serial}w if serialised "
                     f"(float {serial_float:+.0f}w){marker}")
            for x in rs:
                L.append(f"        {x['id']} · {x['weeks']}w · {x['obligation'][:64]}")
        L.append("")

    worst = rows[0]
    L.append(f"{'## ' if md else ''}Finding")
    L.append("")
    if worst["float"] < 0:
        L.append(f"{b}{worst['id']} cannot be remediated before the deadline.{b} "
                 f"{worst['weeks']} weeks of work against {weeks_available:.0f} weeks available "
                 f"— float {worst['float']:+.0f} weeks. This is a decision, not a schedule: "
                 "reduce scope, move the date, or accept and document the residual risk. "
                 "Deciding nothing accepts it by default, on a date already fixed.")
    else:
        highest = max(rows, key=lambda r: r["weighted"])
        strained = [(o, sum(x["weeks"] for x in rs)) for o, rs in load.items()
                    if sum(x["weeks"] for x in rs) > weeks_available]
        L.append(f"Every gap fits inside the deadline {b}taken one at a time{b}. "
                 f"Highest weighted gap is {b}{highest['id']}{b} "
                 f"(exposure {highest['exposure']}, gap {highest['gap']}) — "
                 f"{' '.join(highest['remediation'].split())}")
        L.append("")
        if strained:
            names = ", ".join(f"{o} ({w}w vs {weeks_available:.0f}w available)" for o, w in strained)
            L.append(f"{b}But the plan does not survive its own staffing.{b} {names}. "
                     "Every per-item float above is positive and the aggregate is not, which is "
                     "the failure mode this section exists to catch: item-level plans that are "
                     "each achievable and collectively impossible. Resolve by adding capacity or "
                     "by explicitly sequencing and accepting the later finish date.")
        else:
            L.append(f"{b}The plan also survives its own staffing{b} — no owner's serialised "
                     "workload exceeds the time available. The binding constraint is execution, "
                     "not capacity or time.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("assessment")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    doc = yaml.safe_load(Path(args.assessment).read_text())
    meta, assessed, deadline, weeks, rows, errors = analyse(doc)

    if errors:
        for e in errors:
            print(f"ERROR {e}")
        print("\nAssessment rejected. A maturity score of 3 or above requires named evidence.")
        return 1

    print(render(meta, assessed, deadline, weeks, rows, args.markdown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
