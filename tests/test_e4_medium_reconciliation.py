"""E4 Step 3.4A — Medium-defect reconciliation guards.

Historical E4 results remain unchanged. These tests bind current R4/B1 behavior
to the narrow remediation/supersession controls for NS-DEF-003, 006 and 007.
NS-DEF-004, 005, 008 and 009 remain evidence/remediation gates and are not
declared closed by this file.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"


def source():
    return MAIN.read_text(encoding="utf-8")


def test_ns_def_003_progress_state_is_read_before_default_write():
    s = source()
    read = "savedProgress=localStorage.getItem(progressKey)"
    write = "localStorage.setItem(progressKey,'opened')"
    assert read in s and write in s
    assert s.index(read) < s.index(write)
    assert "data-progress-state','opened'" in s


def test_ns_def_006_obsolete_search_modal_is_not_reintroduced():
    s = source().lower()
    assert "@app.get('/search'" in s
    assert 'class="searchbox"' in s
    assert 'role="dialog"' not in s
    assert 'aria-modal="true"' not in s


def test_ns_def_007_ai_assurance_claims_remain_calibrated():
    s = source()
    assert "'canonical_content':False" in s
    assert "AI-generated wording is not canonical North Star content." in s
    assert "treat generated wording as canonical content" in s


def test_medium_gate_does_not_claim_production_authorization():
    s = source()
    assert "'production_authorized':False" in s
