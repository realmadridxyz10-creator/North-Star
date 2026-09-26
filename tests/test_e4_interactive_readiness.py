"""E4 Step 3.6 — interactive UAT readiness guards.

These guards do not claim execution of the historical NS-UAT-176..187 matrix.
They establish that the current R4/B1 runtime exposes the controlled surfaces
needed for targeted browser/device/accessibility/history/performance execution.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"app"/"main.py").read_text(encoding="utf-8")
UAT=(ROOT/"tests"/"r4_readonly_uat.py").read_text(encoding="utf-8")


def test_interactive_target_is_non_production_uat():
    assert "north-star-uat-r4-production.up.railway.app" in UAT
    assert "'production_authorized':False" in MAIN


def test_reader_has_stable_deep_link_and_progress_surfaces():
    assert "def normalize_route(r):" in MAIN
    assert "id=\"kb-{i:03d}\"" in MAIN
    assert "savedProgress=localStorage.getItem(progressKey)" in MAIN
    assert "data-progress-state','opened'" in MAIN


def test_accessibility_and_responsive_controls_are_present_for_manual_execution():
    lowered=MAIN.lower()
    assert "skip" in lowered and "#main" in lowered
    assert "@media" in lowered
    assert "aria-label" in lowered


def test_deployed_boundary_uat_includes_security_and_error_contracts():
    assert "Hardened response-header assurance" in UAT
    assert "Controlled error handling / method and parameter validation." in UAT
    assert "R4 HTTP/security boundary UAT" in UAT


def test_module_route_uses_normalized_chapter_registry():
    """Regression guard for deployed /modules/foundation HTTP 500 found in Step 3.6B."""
    assert "CHAPTER_REGISTRY_RAW=load_json('B1_D04_chapter_route_registry.json')" in MAIN
    assert "for module,rows in CHAPTER_REGISTRY_RAW.items()" in MAIN
    assert "'chapter_code':row[0]" in MAIN
    assert "chapters=[x for x in CHAPTER_REGISTRY if x['module']==module]" in MAIN
