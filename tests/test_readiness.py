"""Tests for the readiness assessment scorer."""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "readiness"))

import assess as A  # noqa: E402

EXAMPLE = ROOT / "readiness" / "worked-example" / "au-smma-assessment.yaml"


@pytest.fixture(scope="module")
def doc():
    return yaml.safe_load(EXAMPLE.read_text())


def test_worked_example_passes_the_evidence_gate(doc):
    *_, errors = A.analyse(doc)
    assert errors == []


def test_high_maturity_without_evidence_is_rejected(doc):
    bad = {**doc, "obligations": [{**doc["obligations"][0], "maturity": 4, "evidence": "  "}]}
    *_, errors = A.analyse(bad)
    assert errors and "no evidence" in errors[0]


def test_rows_sorted_by_float_ascending(doc):
    *_, rows, _ = A.analyse(doc)
    floats = [r["float"] for r in rows]
    assert floats == sorted(floats)


def test_weighted_gap_is_zero_at_full_maturity(doc):
    full = {**doc, "obligations": [{**o, "maturity": 4, "evidence": "x"} for o in doc["obligations"]]}
    *_, rows, errors = A.analyse(full)
    assert errors == []
    assert all(r["weighted"] == 0 for r in rows)


def test_phases_partition_every_row(doc):
    _, _, _, weeks, rows, _ = A.analyse(doc)
    phased = A.phase(rows, weeks)
    assert sum(len(v) for v in phased.values()) == len(rows)


def test_negative_float_lands_in_phase_zero(doc):
    slow = {**doc, "obligations": [{**o, "remediation_weeks": 500} for o in doc["obligations"]]}
    _, _, _, weeks, rows, _ = A.analyse(slow)
    phased = A.phase(rows, weeks)
    assert len(phased["Phase 0 — negative float (decision required)"]) == len(rows)
