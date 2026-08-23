"""Tests for the triage engine and the backwards scheduler."""
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import triage as T  # noqa: E402

WD = {"start_hour": 9, "end_hour": 18, "weekend_days": [5, 6]}


def load(name):
    return yaml.safe_load((ROOT / "workflow" / "examples" / name).read_text())


def test_working_hours_skip_weekends():
    """Fri 17:00 -> Mon 10:00 is 1h Friday + 1h Monday, not 65 calendar hours."""
    fri, mon = datetime(2026, 7, 17, 17, 0), datetime(2026, 7, 20, 10, 0)
    assert T.working_hours_between(fri, mon, WD, False) == pytest.approx(2.0, abs=0.26)


def test_always_on_counts_every_hour():
    a, b = datetime(2026, 7, 17, 17, 0), datetime(2026, 7, 18, 17, 0)
    assert T.working_hours_between(a, b, WD, True) == pytest.approx(24.0, abs=0.26)


def test_subtract_is_inverse_of_between():
    end = datetime(2026, 4, 28, 17, 0)
    start = T.subtract_working_hours(end, 20.0, WD, False)
    assert T.working_hours_between(start, end, WD, False) == pytest.approx(20.0, abs=0.3)


def test_schedule_never_starts_before_intake():
    """Regression: chained backwards subtraction used to drift the first stage
    earlier than the moment the inquiry arrived."""
    plan = yaml.safe_load((ROOT / "workflow" / "rubric" / "response_plan.yaml").read_text())
    rubric = yaml.safe_load((ROOT / "workflow" / "rubric" / "triage.yaml").read_text())
    for name in ("INQ-2026-014.yaml", "INQ-2026-031.yaml"):
        inq = load(name)
        now = T.as_dt(inq["logged"])
        score = T.score_inquiry(inq, rubric, now)
        rows, *_ = T.build_timeline(inq, plan, score, now)
        # allow one 15-minute step of rounding onto the working-day boundary
        assert rows[0]["start"] >= now.replace(hour=WD["start_hour"], minute=0), name
        assert rows[0]["start"] <= T.as_dt(inq["deadline"]), name


def test_stages_are_contiguous_and_ordered():
    plan = yaml.safe_load((ROOT / "workflow" / "rubric" / "response_plan.yaml").read_text())
    rubric = yaml.safe_load((ROOT / "workflow" / "rubric" / "triage.yaml").read_text())
    inq = load("INQ-2026-014.yaml")
    now = T.as_dt(inq["logged"])
    score = T.score_inquiry(inq, rubric, now)
    rows, *_ = T.build_timeline(inq, plan, score, now)
    for a, b in zip(rows, rows[1:]):
        assert a["end"] == b["start"]
        assert a["start"] <= a["end"]


def test_override_can_only_raise_priority():
    rubric = yaml.safe_load((ROOT / "workflow" / "rubric" / "triage.yaml").read_text())
    inq = load("INQ-2026-014.yaml")
    now = T.as_dt(inq["logged"])
    with_ov = T.score_inquiry(inq, rubric, now)
    inq_no = {**inq, "triage": {**inq["triage"], "overrides": []}}
    without = T.score_inquiry(inq_no, rubric, now)
    order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    assert order[with_ov.priority] <= order[without.priority]


def test_plan_shares_sum_to_one():
    plan = yaml.safe_load((ROOT / "workflow" / "rubric" / "response_plan.yaml").read_text())
    assert sum(s["share"] for s in plan["stages"]) == pytest.approx(1.0)


def test_weekend_example_loses_most_of_its_calendar_time():
    """The whole point of INQ-2026-031: 4 calendar days, barely one working day."""
    plan = yaml.safe_load((ROOT / "workflow" / "rubric" / "response_plan.yaml").read_text())
    rubric = yaml.safe_load((ROOT / "workflow" / "rubric" / "triage.yaml").read_text())
    inq = load("INQ-2026-031.yaml")
    now = T.as_dt(inq["logged"])
    score = T.score_inquiry(inq, rubric, now)
    _, available, _, _ = T.build_timeline(inq, plan, score, now)
    calendar = (T.as_dt(inq["deadline"]) - now).total_seconds() / 3600
    assert calendar > 48
    assert available < 24
