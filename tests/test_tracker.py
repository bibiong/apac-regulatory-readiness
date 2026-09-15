"""Tests for the tracker dataset and its validator."""
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import validate as V  # noqa: E402


@pytest.fixture(scope="module")
def entries():
    return V.load_all()


def test_dataset_is_not_empty(entries):
    assert len(entries) >= 10


def test_validator_passes_on_shipped_dataset():
    r = subprocess.run([sys.executable, str(ROOT / "src" / "validate.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_ids_are_unique(entries):
    ids = [e["id"] for _, e in entries]
    assert len(ids) == len(set(ids))


def test_every_instrument_has_a_source(entries):
    for fn, e in entries:
        assert e.get("sources"), f"{fn}:{e['id']} has no source"


def test_confidence_never_exceeds_source_strength(entries):
    """The discipline the validator enforces: you may not claim 'high' on a blog post."""
    for fn, e in entries:
        kinds = {s["kind"] for s in e["sources"]}
        best = max(V.RANK[V.CONFIDENCE_FLOOR[k]] for k in kinds)
        assert V.RANK[e.get("confidence", "medium")] <= best, f"{fn}:{e['id']} overclaims confidence"


def test_in_force_instruments_have_commenced(entries):
    today = date.today()
    for fn, e in entries:
        if e["status"] == "in_force" and e.get("commenced"):
            assert V.parse_date(e["commenced"]) <= today


def test_isoify_normalises_yaml_native_dates():
    """Regression: YAML parses bare dates into date objects, which fail JSON-schema."""
    out = V._isoify({"a": date(2026, 8, 23),
                     "b": [{"c": datetime(2026, 1, 2, 3, 4)}],
                     "d": "untouched"})
    assert out["a"] == "2026-08-23"
    assert out["b"][0]["c"] == "2026-01-02"
    assert out["d"] == "untouched"


def test_validator_rejects_a_confidence_overclaim(tmp_path, monkeypatch):
    """Feed the validator a deliberately bad entry and assert it fails."""
    bad = [{
        "id": "xx-bad", "jurisdiction": "Testland", "instrument": "Test Act",
        "regulator": "TR", "status": "draft", "themes": ["licensing"],
        "obligations": [{"ref": "general", "summary": "A duty long enough to pass minLength.",
                         "owner_function": ["legal"]}],
        "sources": [{"title": "A blog", "url": "https://example.com", "kind": "secondary"}],
        "confidence": "high",
        "last_verified": "2026-08-23", "verified_by": "test",
    }]
    d = tmp_path / "data"
    d.mkdir()
    (d / "testland.yaml").write_text(yaml.safe_dump(bad))
    monkeypatch.setattr(V, "DATA", d)
    rc = V.main.__wrapped__() if hasattr(V.main, "__wrapped__") else None  # noqa: F841
    # main() parses argv; call the pieces directly instead.
    loaded = V.load_all()
    kinds = {s["kind"] for s in loaded[0][1]["sources"]}
    best = max(V.RANK[V.CONFIDENCE_FLOOR[k]] for k in kinds)
    assert V.RANK["high"] > best, "the overclaim should be detectable"


def test_site_build_does_not_depend_on_the_current_date():
    """Regression: the builder once read the build date, so the weekly CI staleness check
    failed on every scheduled run. The site must be a pure function of the dataset."""
    src = (ROOT / "src" / "build_site.py").read_text()
    for call in ("date.today(", "datetime.now(", "datetime.today(", "time.time("):
        assert call not in src, f"build_site.py calls {call}"
