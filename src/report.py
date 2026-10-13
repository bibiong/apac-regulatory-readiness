#!/usr/bin/env python3
"""Produce the monthly re-verification work item.

    python3 src/report.py                 # markdown to stdout
    python3 src/report.py --links         # also check every cited URL resolves
    python3 src/report.py --case-study    # also check the public case study's figures

This is the half of maintenance that can be automated: working out *what* needs looking
at. It deliberately does not touch `last_verified`, because that field records that a
person read a source and formed a view. A tracker whose freshness dates advance without
anyone reading anything is worse than one that admits it is stale.

Exit code is always 0 — this reports, it does not gate. The validator gates.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate as V  # noqa: E402

DEADLINE_HORIZON = 60  # days ahead to surface on the board
APPROACHING = 7        # days before the freshness window closes

# A 30-day window checked monthly means every entry is just past the window at every
# run — which is the intended workflow (re-verify the set each month), not an alarm.
# So "due" and "overdue" are separated: an entry is only overdue once it has missed a
# whole cycle. Without this split every issue would mark all 17 entries red and the
# signal would be worth nothing, which is how a scheduled check stops being read.
MISSED_CYCLE = 2  # cycles of FRESHNESS_DAYS before an entry counts as overdue


def parse(v):
    return V.parse_date(v)


def collect(today: date):
    entries = V.load_all()

    due, overdue, approaching, mismatches, upcoming, just_passed = [], [], [], [], [], []

    for fname, e in entries:
        eid = e["id"]
        lv = parse(e["last_verified"])
        age = (today - lv).days
        row = {"id": eid, "jur": e["jurisdiction"], "instr": e["instrument"],
               "age": age, "lv": lv, "conf": e.get("confidence", "medium")}

        if age > V.FRESHNESS_DAYS * MISSED_CYCLE:
            overdue.append(row)
        elif age > V.FRESHNESS_DAYS:
            due.append(row)
        elif age > V.FRESHNESS_DAYS - APPROACHING:
            approaching.append(row)

        # A commencement date that has arrived while the status still says "passed" is
        # the exact defect the September 2026 pass caught on Korea. Surface it by name.
        commenced = parse(e.get("commenced"))
        if commenced and commenced <= today and e["status"] == "passed":
            mismatches.append({**row, "why": f"commenced {commenced} but status is still 'passed'"})
        if e["status"] in {"draft", "consultation"}:
            # Drafts move faster than enacted instruments and are the likeliest to have
            # reversed direction since anyone last looked.
            mismatches.append({**row, "why": f"status '{e['status']}' — drafts change direction; re-read the current text"})

        for d in e.get("deadlines") or []:
            dt = parse(d["date"])
            if not dt:
                continue
            delta = (dt - today).days
            item = {**row, "date": dt, "event": " ".join(str(d["event"]).split()),
                    "certainty": d.get("certainty", "fixed"), "in_days": delta}
            if 0 <= delta <= DEADLINE_HORIZON:
                upcoming.append(item)
            elif -31 <= delta < 0:
                just_passed.append(item)

    for lst in (due, overdue, approaching):
        lst.sort(key=lambda r: -r["age"])
    upcoming.sort(key=lambda r: r["in_days"])
    just_passed.sort(key=lambda r: r["in_days"])
    return entries, due, overdue, approaching, mismatches, upcoming, just_passed


def check_links(entries):
    """Reuse the validator's link checking by invoking it and parsing its warnings."""
    import io
    import contextlib

    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["validate.py", "--links"]
    try:
        with contextlib.redirect_stdout(buf):
            V.main()
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return [ln[6:].strip() for ln in buf.getvalue().splitlines()
            if ln.startswith("WARN ") and ("returned" in ln or "blocks automated" in ln)]


def check_case_study(entries):
    """Confirm the public case study still states figures the dataset supports.

    The case study lives in another repository and is hand-written prose, so this
    reports drift rather than editing anything.
    """
    import re
    import urllib.request

    url = "https://brendaong.com/work/apac-regulatory-readiness.html"
    n_instr = len(entries)
    n_jur = len({e["jurisdiction"] for _, e in entries})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; tracker-check)"})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return [f"could not fetch the case study ({type(exc).__name__}) — check it by hand"]

    issues = []
    m = re.search(r"<b>(\d+)</b><span>Instruments tracked</span>", html)
    if m and int(m.group(1)) != n_instr:
        issues.append(f"case study says {m.group(1)} instruments; dataset has {n_instr}")
    m = re.search(r"<b>(\d+)</b><span>Jurisdictions</span>", html)
    if m and int(m.group(1)) != n_jur:
        issues.append(f"case study says {m.group(1)} jurisdictions; dataset has {n_jur}")
    if not re.search(r"\b(ten|10)\b", html, re.I) and n_jur == 10:
        issues.append("case study no longer says ten jurisdictions")
    return issues


def render(today, entries, due, overdue, approaching, mismatches, upcoming, just_passed,
           link_warnings, case_study_issues) -> str:
    n_instr = len(entries)
    n_jur = len({e["jurisdiction"] for _, e in entries})
    L = []
    L.append(f"Scheduled check for **{today:%B %Y}**, run {today.isoformat()}. "
             f"{n_instr} instruments across {n_jur} jurisdictions; freshness window "
             f"{V.FRESHNESS_DAYS} days.")
    L.append("")
    L.append("> This issue lists what needs a human. The job does not re-verify anything "
             "and never writes `last_verified` — that date means a person read a source.")
    L.append("")

    def table(rows):
        L.append("| Entry | Jurisdiction | Last verified | Age | Confidence |")
        L.append("|---|---|---|---:|---|")
        for r in rows:
            L.append(f"| `{r['id']}` | {r['jur']} | {r['lv']} | {r['age']}d | {r['conf']} |")

    if overdue:
        L.append(f"## ⚠ Overdue — missed a cycle, past {V.FRESHNESS_DAYS * MISSED_CYCLE} days ({len(overdue)})")
        L.append("")
        L.append("These were not picked up last cycle. Do these first.")
        L.append("")
        table(overdue)
        L.append("")

    L.append(f"## Due this cycle — past {V.FRESHNESS_DAYS} days ({len(due)})")
    L.append("")
    if due:
        L.append("Expected: the window matches the check interval, so the set comes due each month.")
        L.append("")
        table(due)
    else:
        L.append("None. Every entry is inside the window.")
    L.append("")

    if approaching:
        L.append(f"## Due within {APPROACHING} days ({len(approaching)})")
        L.append("")
        for r in approaching:
            L.append(f"- `{r['id']}` — {r['jur']}, {r['age']}d old")
        L.append("")

    if mismatches:
        L.append(f"## Entries whose status may have moved ({len(mismatches)})")
        L.append("")
        for r in mismatches:
            L.append(f"- `{r['id']}` — {r['instr']}: {r['why']}")
        L.append("")

    if just_passed:
        L.append(f"## Dated events that passed in the last month ({len(just_passed)})")
        L.append("")
        for r in just_passed:
            L.append(f"- **{r['date']}** ({abs(r['in_days'])}d ago) — {r['event']} "
                     f"(`{r['id']}`). Does the entry's status still reflect reality?")
        L.append("")

    L.append(f"## Deadlines in the next {DEADLINE_HORIZON} days ({len(upcoming)})")
    L.append("")
    if upcoming:
        for r in upcoming:
            flag = "" if r["certainty"] == "fixed" else f" _({r['certainty']})_"
            L.append(f"- **{r['date']}** (in {r['in_days']}d) — {r['event']} (`{r['id']}`){flag}")
    else:
        L.append("None.")
    L.append("")

    if link_warnings:
        L.append(f"## Source links needing attention ({len(link_warnings)})")
        L.append("")
        for w in link_warnings:
            L.append(f"- {w}")
        L.append("")

    if case_study_issues:
        L.append("## Case study drift")
        L.append("")
        L.append("The public case study at brendaong.com states figures that no longer match "
                 "the dataset. It is prose in another repository, so fix it by hand.")
        L.append("")
        for i in case_study_issues:
            L.append(f"- {i}")
        L.append("")

    L.append("## To close this issue")
    L.append("")
    L.append("1. Re-read the sources for everything listed above, overdue items first.")
    L.append("2. Update the entry where the facts moved; leave it alone where they did not.")
    L.append("3. Set `last_verified` to today on **every** entry you actually looked at, "
             "including the ones that did not change.")
    L.append("4. Add a dated section to `CHANGELOG.md` recording what moved and what did not. "
             "An entry saying \"checked, nothing changed\" is a real entry — the cadence is the "
             "thing being evidenced.")
    L.append("5. `make validate && make test && make site`, then commit.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", action="store_true")
    ap.add_argument("--case-study", action="store_true")
    ap.add_argument("--today", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    today = V.parse_date(args.today) if args.today else date.today()
    entries, due, overdue, approaching, mismatches, upcoming, just_passed = collect(today)

    link_warnings = check_links(entries) if args.links else []
    case_study_issues = check_case_study(entries) if args.case_study else []

    md = render(today, entries, due, overdue, approaching, mismatches, upcoming, just_passed,
                link_warnings, case_study_issues)
    if args.out:
        Path(args.out).write_text(md)
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
