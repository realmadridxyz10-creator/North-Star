"""E4 Step 3.5 — Low-severity defect reconciliation guards.

Historical 19-Aug-2026 E4 findings remain unchanged. These tests reconcile
NS-DEF-010, NS-DEF-011 and NS-DEF-012 against the governed R4/B1 runtime.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "data" / "search_records.jsonl"
MAIN = ROOT / "app" / "main.py"


def records():
    return [json.loads(x) for x in SEARCH.read_text(encoding="utf-8").splitlines() if x.strip()]


def source():
    return MAIN.read_text(encoding="utf-8")


def test_ns_def_010_search_corpus_is_self_consistent_and_r4_bound():
    rows = records()
    assert len(rows) == 1140
    assert len({r["canonical_id"] for r in rows}) == len(rows)
    assert all(r.get("source_baseline") == "R4" for r in rows)
    assert all(r.get("route") for r in rows)


def test_ns_def_011_no_empty_governed_search_sections():
    rows = records()
    assert all((r.get("text") or "").strip() for r in rows)
    assert all((r.get("canonical_id") or "").strip() for r in rows)


def test_ns_def_012_progress_has_one_explicit_current_meaning():
    s = source()
    assert "const progressKey='nsProgress:{module}:{code}'" in s
    assert "savedProgress=localStorage.getItem(progressKey)" in s
    assert "localStorage.setItem(progressKey,'opened')" in s
    assert "data-progress-state','opened'" in s
    # Current runtime intentionally claims only chapter-opened state; it must
    # not infer completion percentage, mastery, certification, or completion.
    lowered = s.lower()
    assert "nsprogresspercent" not in lowered
    assert "nsprogresscomplete" not in lowered
