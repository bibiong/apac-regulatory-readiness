#!/usr/bin/env python3
"""Score a regulatory inquiry against the triage rubric and plan backwards from its deadline.

    python3 src/triage.py workflow/examples/INQ-2026-014.yaml
    python3 src/triage.py workflow/examples/INQ-2026-014.yaml --markdown

The scoring half answers "how hard should this hit the queue". The planning half
answers "when does each stage have to start for the filing to be on time" — computed
backwards from the deadline over working hours only, so a Friday-evening notice with a
Monday deadline reports the negative float it actually has instead of looking comfortable.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUBRIC = ROOT / "workflow" / "rubric" / "triage.yaml"
PLAN = ROOT / "workflow" / "rubric" / "response_plan.yaml"


def load_yaml(p: Path):
    return yaml.safe_load(p.read_text())


def as_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)


# ---------------------------------------------------------------- working time

def is_working(dt: datetime, wd: dict, always_on: bool) -> bool:
    if always_on:
        return True
    if dt.weekday() in wd["weekend_days"]:
        return False
    return wd["start_hour"] <= dt.hour < wd["end_hour"]


def working_hours_between(start: datetime, end: datetime, wd: dict, always_on: bool) -> float:
    """Working hours between two datetimes, stepped at 15-minute resolution.

    Deliberately a simple stepper rather than closed-form arithmetic: the calendar
    rules here (weekends, working-day windows, a 24/7 override) are exactly the sort
    that closed-form implementations get subtly wrong at boundaries, and this runs on
    inputs measured in days.
    """
    if end <= start:
        return 0.0
    step = timedelta(minutes=15)
    total = 0.0
    cur = start
    while cur < end:
        if is_working(cur, wd, always_on):
            total += 0.25
        cur += step
    return total


def subtract_working_hours(end: datetime, hours: float, wd: dict, always_on: bool) -> datetime:
    """Walk backwards from `end` until `hours` of working time has been consumed."""
    step = timedelta(minutes=15)
    remaining = hours
    cur = end
    # Bound the walk so a misconfigured calendar cannot spin forever.
    limit = 400_000
    while remaining > 0 and limit > 0:
        cur -= step
        if is_working(cur, wd, always_on):
            remaining -= 0.25
        limit -= 1
    return cur


# ---------------------------------------------------------------- scoring

@dataclass
class Score:
    total: int
    priority: str
    band: dict
    breakdown: list[tuple[str, str, int]]
    fired: list[dict]


def bucket_time(hours: float) -> str:
    if hours < 4:
        return "under_4_hours"
    if hours < 24:
        return "under_24_hours"
    if hours < 72:
        return "under_72_hours"
    if hours < 24 * 14:
        return "under_2_weeks"
    return "over_2_weeks"


def score_inquiry(inq: dict, rubric: dict, now: datetime) -> Score:
    triage = inq.get("triage", {})
    factors = rubric["factors"]
    breakdown: list[tuple[str, str, int]] = []

    # time_to_deadline is derived from the record, never hand-entered — a coordinator
    # under pressure should not be asked to bucket a number they can miscount.
    calendar_hours = (as_dt(inq["deadline"]) - now).total_seconds() / 3600
    derived = {"time_to_deadline": bucket_time(calendar_hours)}

    for fname, fdef in factors.items():
        level = derived.get(fname) or triage.get(fname)
        if level is None:
            raise SystemExit(f"triage factor '{fname}' not set on {inq['id']} — intake is incomplete")
        if level not in fdef["levels"]:
            raise SystemExit(f"unknown level '{level}' for factor '{fname}' on {inq['id']}")
        breakdown.append((fname, level, fdef["levels"][level]))

    total = sum(v for _, _, v in breakdown)
    band = next(b for b in rubric["bands"] if total >= b["min"])
    priority = band["priority"]

    fired = []
    declared = set(triage.get("overrides", []))
    order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    for ov in rubric["overrides"]:
        if ov["when"] in declared:
            fired.append(ov)
            if order[ov["force"]] < order[priority]:
                priority = ov["force"]
    if fired:
        band = next(b for b in rubric["bands"] if b["priority"] == priority)

    return Score(total, priority, band, breakdown, fired)


# ---------------------------------------------------------------- planning

def build_timeline(inq: dict, plan: dict, score: Score, now: datetime):
    wd = plan["working_day"]
    always_on = score.priority == "P1"
    deadline = as_dt(inq["deadline"])

    available = working_hours_between(now, deadline, wd, always_on)
    buffer_h = available * plan["filing_buffer_pct"] / 100
    usable = max(available - buffer_h, 0.0)

    # Anchor every boundary to a single point and a cumulative offset. Chaining
    # subtractions stage by stage lets the 15-minute stepping round in the same
    # direction eight times, which is enough drift to push the first stage's start
    # earlier than the inquiry actually arrived.
    anchor = subtract_working_hours(deadline, buffer_h, wd, always_on)

    cumulative, offsets = 0.0, []
    for stage in reversed(plan["stages"]):
        dur = usable * stage["share"]
        cumulative += dur
        offsets.append((stage, dur, cumulative))

    boundaries = {c: subtract_working_hours(anchor, c, wd, always_on) for _, _, c in offsets}

    rows = []
    for stage, dur, cum in offsets:
        start = boundaries[cum]
        end = anchor if len(rows) == 0 else rows[-1]["start"]
        rows.append({
            "name": stage["name"], "owner": stage["owner"],
            "start": start, "end": end, "hours": dur,
            "exit_criteria": stage["exit_criteria"],
        })
    rows.reverse()
    return rows, available, buffer_h, always_on


# ---------------------------------------------------------------- reporting

def fmt(dt: datetime) -> str:
    return dt.strftime("%a %d %b %H:%M")


def render(inq, score, rows, available, buffer_h, always_on, now, markdown=False):
    b = "**" if markdown else ""
    L = []
    hdr = f"{inq['id']} — {inq['jurisdiction']} / {inq['regulator']}"
    L.append(f"{'## ' if markdown else ''}{hdr}")
    L.append("")
    L.append(f"{b}Subject{b}: {inq['subject']}")
    L.append(f"{b}Received{b}: {fmt(as_dt(inq['received']))}   {b}Deadline{b}: {fmt(as_dt(inq['deadline']))}")
    L.append(f"{b}Legal basis{b}: {inq['legal_basis']}   {b}Compelled{b}: {'yes' if inq['compelled'] else 'no'}")
    L.append("")
    L.append(f"{b}Priority {score.priority}{b}  (score {score.total}/100)")
    L.append("")

    if markdown:
        L.append("| Factor | Level | Points |")
        L.append("|---|---|---:|")
        for f, lv, v in score.breakdown:
            L.append(f"| {f} | {lv} | {v} |")
        L.append(f"| | **Total** | **{score.total}** |")
    else:
        for f, lv, v in score.breakdown:
            L.append(f"    {f:<24} {lv:<32} {v:>3}")
        L.append(f"    {'TOTAL':<24} {'':<32} {score.total:>3}")
    L.append("")

    for ov in score.fired:
        L.append(f"{b}Override fired{b}: {ov['when']} → forces {ov['force']}")
        L.append(f"    {' '.join(ov['why'].split())}")
        L.append("")

    L.append(f"{b}Response{b}: {score.band['response']}")
    L.append(f"{b}Escalation{b}: {score.band['escalation']}")
    L.append("")

    calendar_h = (as_dt(inq["deadline"]) - now).total_seconds() / 3600
    mode = "24/7 (P1)" if always_on else "working hours only"
    L.append(f"{b}Time budget{b}: {calendar_h:.1f} calendar hours → "
             f"{available:.1f} usable hours under {mode}; {buffer_h:.1f}h held as filing buffer")
    # The trap is a ratio, not an absolute. A notice arriving Friday evening with a
    # Tuesday deadline shows ~4 calendar days and barely one working day. Fire when the
    # calendar reads comfortable (>48h) but the usable budget does not survive contact
    # with a normal working week.
    if calendar_h > 48 and available < 24:
        L.append("")
        L.append(f"{b}WARNING — weekend-arrival trap{b}: {calendar_h:.0f} calendar hours reduce to "
                 f"{available:.1f} working hours ({available / calendar_h:.0%} of elapsed time). "
                 "The calendar reads comfortable and the budget is not. Decide now, at intake, "
                 "between requesting the extension and standing up out-of-hours cover — "
                 "not on Monday morning, when both options have already shrunk.")
        if inq.get("extension_available"):
            L.append(f"    Intake recorded an extension as available. That is the cheaper option and it expires with time.")
    L.append("")

    L.append(f"{'### ' if markdown else ''}Backwards schedule")
    L.append("")
    if markdown:
        L.append("| Stage | Owner | Start | Must finish | Hours |")
        L.append("|---|---|---|---|---:|")
        for r in rows:
            L.append(f"| {r['name']} | {r['owner']} | {fmt(r['start'])} | {fmt(r['end'])} | {r['hours']:.1f} |")
    else:
        for r in rows:
            L.append(f"    {r['name']}")
            L.append(f"        {r['owner']:<22} {fmt(r['start'])}  ->  {fmt(r['end'])}   ({r['hours']:.1f}h)")
    L.append("")

    unresourced = [c for c in inq.get("commitments_made", []) or [] if not c.get("resourced")]
    if unresourced:
        L.append(f"{b}Unresourced commitments{b} — these were promised to a regulator and nobody has funded them:")
        for c in unresourced:
            L.append(f"    - {c['commitment']} (owner {c['owner']}, due {c['due']})")
        L.append("")

    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inquiry")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--now", default=None, help="override current time (ISO) for reproducible output")
    args = ap.parse_args()

    inq = load_yaml(Path(args.inquiry))
    rubric, plan = load_yaml(RUBRIC), load_yaml(PLAN)
    now = as_dt(args.now) if args.now else (as_dt(inq.get("logged") or inq["received"]))

    score = score_inquiry(inq, rubric, now)
    rows, available, buffer_h, always_on = build_timeline(inq, plan, score, now)
    print(render(inq, score, rows, available, buffer_h, always_on, now, args.markdown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
