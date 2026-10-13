#!/usr/bin/env python3
"""Validate the APAC regulation tracker dataset.

Checks, in order of how badly each one bites:

  1. Schema conformance for every instrument.
  2. Globally unique, stable ids.
  3. Internally coherent dates (passed <= commenced; status matches commencement).
  4. Sourcing discipline — every instrument cited, confidence justified by source kind.
  5. Staleness — entries not re-verified within the freshness window.
  6. Optionally, that every source URL still resolves (--links).

Exit code is non-zero on any error, so CI fails on a bad entry. Warnings do not
fail the build; staleness is a prompt to go and look, not a defect.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tracker" / "data"
SCHEMA = ROOT / "tracker" / "schema" / "instrument.schema.json"

# An entry not looked at within this window is presumed stale. Set to 30 days to match
# the monthly scheduled check: a warning should mean "overdue now", not "overdue a
# fortnight ago". The October 2026 pass is the evidence — 6 of 17 entries had changed
# substantively in seven weeks, and two had become wrong rather than merely dated.
FRESHNESS_DAYS = 30

# confidence must be earned by the strongest source kind actually cited
CONFIDENCE_FLOOR = {"primary": "high", "regulator": "medium", "secondary": "low"}
RANK = {"low": 0, "medium": 1, "high": 2}


def _isoify(node):
    """YAML parses bare 2026-08-23 into a date object; the schema speaks JSON, which has
    no date type. Normalise on load so authors can write dates naturally in the YAML and
    still be validated against `format: date`."""
    if isinstance(node, dict):
        return {k: _isoify(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_isoify(v) for v in node]
    if isinstance(node, datetime):
        return node.date().isoformat()
    if isinstance(node, date):
        return node.isoformat()
    return node


def load_all() -> list[tuple[str, dict]]:
    out = []
    for path in sorted(DATA.glob("*.yaml")):
        entries = yaml.safe_load(path.read_text()) or []
        for e in entries:
            out.append((path.name, _isoify(e)))
    return out


def parse_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", action="store_true", help="also check every source URL resolves")
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD) for tests")
    args = ap.parse_args()

    today = parse_date(args.today) if args.today else date.today()

    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)

    entries = load_all()
    if not entries:
        print("ERROR: no instruments found in tracker/data/")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    # 1. schema
    for fname, e in entries:
        eid = e.get("id", "<no id>")
        for err in sorted(validator.iter_errors(e), key=lambda x: list(x.path)):
            loc = ".".join(str(p) for p in err.path) or "(root)"
            errors.append(f"{fname}:{eid}: schema: {loc}: {err.message}")

    # 2. unique ids
    for eid, n in Counter(e.get("id") for _, e in entries).items():
        if n > 1:
            errors.append(f"duplicate id '{eid}' appears {n} times — ids are stable keys and must never be reused")

    for fname, e in entries:
        eid = e.get("id", "<no id>")
        where = f"{fname}:{eid}"

        # 3. date coherence
        try:
            passed = parse_date(e.get("passed"))
            commenced = parse_date(e.get("commenced"))
        except ValueError as exc:
            errors.append(f"{where}: unparseable date: {exc}")
            passed = commenced = None

        if passed and commenced and passed > commenced:
            errors.append(f"{where}: passed ({passed}) is after commenced ({commenced})")

        status = e.get("status")
        if status == "in_force" and commenced and commenced > today:
            errors.append(f"{where}: status 'in_force' but commencement {commenced} is in the future")
        if status == "passed" and commenced and commenced <= today:
            warnings.append(f"{where}: status 'passed' but commencement {commenced} has arrived — should this be in_force?")
        if status in {"draft", "consultation"} and commenced:
            errors.append(f"{where}: status '{status}' cannot carry a commencement date")

        for d in e.get("deadlines") or []:
            try:
                parse_date(d["date"])
            except (ValueError, KeyError) as exc:
                errors.append(f"{where}: bad deadline: {exc}")

        # 4. sourcing discipline
        sources = e.get("sources") or []
        kinds = {s.get("kind") for s in sources}
        best = max((RANK[CONFIDENCE_FLOOR[k]] for k in kinds if k in CONFIDENCE_FLOOR), default=-1)
        claimed = RANK.get(e.get("confidence", "medium"), 1)
        if best >= 0 and claimed > best:
            strongest = [k for k in kinds if k in CONFIDENCE_FLOOR]
            errors.append(
                f"{where}: confidence '{e.get('confidence')}' exceeds what the sources support "
                f"(strongest source kind: {sorted(strongest)}). Cite a stronger source or lower the claim."
            )

        for sig in e.get("enforcement_signals") or []:
            if not str(sig.get("source", "")).startswith("http"):
                errors.append(f"{where}: enforcement signal on {sig.get('date')} has no resolvable source")

        # 5. staleness
        try:
            lv = parse_date(e.get("last_verified"))
        except ValueError:
            errors.append(f"{where}: unparseable last_verified")
            lv = None
        if lv:
            if lv > today:
                errors.append(f"{where}: last_verified {lv} is in the future")
            age = (today - lv).days
            if age > FRESHNESS_DAYS:
                warnings.append(f"{where}: last verified {age} days ago (window is {FRESHNESS_DAYS}) — re-check before citing")

    # 6. links
    if args.links:
        import urllib.error
        import urllib.parse
        import urllib.request

        # Hosts with bot protection that refuses automated agents regardless of UA.
        # Their links are real but cannot be machine-verified; they are flagged for
        # manual re-check rather than reported as broken, because a false "broken"
        # is worse than an honest "unverified".
        BOT_PROTECTED = {"www.esafety.gov.au", "transparency.meta.com"}

        seen: dict[str, str] = {}
        urls = [(f"{fn}:{e.get('id')}", s["url"]) for fn, e in entries for s in (e.get("sources") or [])]
        urls += [(f"{fn}:{e.get('id')}", s["source"]) for fn, e in entries
                 for s in (e.get("enforcement_signals") or []) if s.get("source")]
        print(f"checking {len(set(u for _, u in urls))} unique URLs...")
        for where, url in urls:
            if url in seen:
                status = seen[url]
            else:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                        )
                    },
                )
                try:
                    with urllib.request.urlopen(req, timeout=20) as r:
                        status = str(r.status)
                except urllib.error.HTTPError as exc:
                    status = str(exc.code)
                except Exception as exc:  # noqa: BLE001 - report, don't crash the run
                    status = type(exc).__name__
                seen[url] = status
            if status in {"200", "301", "302", "403"}:
                # 403 is common for government sites that reject non-browser agents;
                # it proves the host resolves, which is what we are testing for.
                continue
            host = urllib.parse.urlsplit(url).hostname or ""
            if host in BOT_PROTECTED:
                warnings.append(f"{where}: {host} blocks automated checks — verify manually: {url}")
            else:
                warnings.append(f"{where}: source returned {status}: {url}")

    for w in warnings:
        print(f"WARN  {w}")
    for e_ in errors:
        print(f"ERROR {e_}")

    jur = len({e.get("jurisdiction") for _, e in entries})
    print(f"\n{len(entries)} instruments across {jur} jurisdictions — "
          f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
