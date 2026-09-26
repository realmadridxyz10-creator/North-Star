"""E4 Step 3.4B — remaining Medium control guards.

These tests do not rewrite the historical 19-Aug-2026 E4 result.
They provide current R4/B1 regression evidence for NS-DEF-004, 008 and 009.
NS-DEF-005 remains explicitly open because the current governed corpus is
rendered as text blocks and no authoritative structured-list metadata has been
recovered from which semantic UL/OL structure can safely be reconstructed.
"""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
SEARCH = ROOT / "data" / "search_records.jsonl"
CHUNKS = ROOT / "data" / "retrieval_chunks.jsonl"
ROUTES = ROOT / "data" / "B1_D04_chapter_route_registry.json"


def source():
    return MAIN.read_text(encoding="utf-8")


def test_ns_def_004_canonical_deep_links_are_stable_and_anchor_addressable():
    s = source()
    assert "def normalize_route(r):" in s
    assert "if route.startswith('/modules/'): return route" in s
    assert "id=\"kb-{i:03d}\"" in s
    assert "#kb-{int(m.group(2)):03d}" in s


def test_ns_def_008_runtime_security_header_contract_is_hardened():
    s = source().lower()
    required = [
        "strict-transport-security",
        "cross-origin-opener-policy",
        "cross-origin-resource-policy",
        "x-permitted-cross-domain-policies",
        "object-src 'none'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "upgrade-insecure-requests",
    ]
    for item in required:
        assert item in s


def test_ns_def_009_governed_runtime_inputs_have_reproducible_sha256_provenance():
    for path in (SEARCH, CHUNKS, ROUTES):
        assert path.is_file() and path.stat().st_size > 0
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_ns_def_009_runtime_declares_r4_b1_source_identity():
    s = source()
    assert "'source_release_identity':'R4/B1'" in s
    assert "Governed R4/B1 digital experience" in s


def test_ns_def_005_preserves_only_evidenced_bullet_list_semantics():
    s = source()
    assert "def render_governed_text(text):" in s
    assert "line.startswith(('','•'))" in s
    assert "out.append('<ul>'" in s
    assert "f'<li>{escape(x)}</li>'" in s
    assert "render_governed_text(r.get('text',''))" in s
    # Fail closed: do not infer ordered-list semantics from ambiguous numbering.
    assert "<ol>" not in s
