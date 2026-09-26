"""E4 Step 3.3C — regression guards for superseded High defects.

These tests do not rewrite the historical 19-Aug-2026 E4 result. They prove that
the current R4/B1 runtime does not silently reintroduce the two obsolete failure
surfaces:
  NS-DEF-001 / NS-UAT-128 — LockedTable mobile column-context loss
  NS-DEF-002 / NS-UAT-150 — title-only alternatives on D001-D037 diagrams

If a future runtime introduces publication tables or information-bearing images,
these guards deliberately fail until a governed accessible renderer/equivalent
description contract is added and the tests are updated with that evidence.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"


def _runtime_source() -> str:
    return MAIN.read_text(encoding="utf-8")


def _chapter_reader_source(source: str) -> str:
    marker = "@app.get('/modules/{module_slug}/chapters/{chapter_code}'"
    assert marker in source, "Canonical R4/B1 chapter reader route is missing."
    return source.split(marker, 1)[1]


def test_ns_def_001_obsolete_locked_table_renderer_is_absent():
    """The current reader must not restore the failed E4 LockedTable renderer."""
    source = _runtime_source()
    assert "LockedTable" not in source
    assert "@media max-width 620px" not in source


def test_ns_def_001_current_reader_has_no_ungoverned_publication_table_surface():
    """Fail closed if the current reader starts emitting raw publication tables.

    A future table feature must replace this absence guard with tests proving
    caption/header semantics plus mobile column-context preservation.
    """
    reader = _chapter_reader_source(_runtime_source()).lower()
    forbidden = ("<table", "<thead", "<tbody", "<th", "<td")
    assert not any(token in reader for token in forbidden)


def test_ns_def_002_current_reader_has_no_information_bearing_image_surface():
    """Fail closed if the reader starts rendering images/figures without a governed
    equivalent-description contract.
    """
    reader = _chapter_reader_source(_runtime_source()).lower()
    forbidden = ("<img", "<figure", "<picture")
    assert not any(token in reader for token in forbidden)


def test_ns_def_002_legacy_d001_d037_title_only_mapping_is_not_reintroduced():
    """The superseded E4 D001-D037 placement model must not silently return."""
    source = _runtime_source()
    legacy_ids = [f"D{i:03d}" for i in range(1, 38)]
    assert not any(diagram_id in source for diagram_id in legacy_ids)


def test_high_defect_guards_are_bound_to_governed_r4_b1_reader():
    """Keep the supersession evidence tied to the current governed runtime."""
    source = _runtime_source()
    assert "source_release_identity':'R4/B1'" in source
    assert "Governed R4/B1 digital experience" in source
    assert re.search(r"Canonical digital reading view", source)
