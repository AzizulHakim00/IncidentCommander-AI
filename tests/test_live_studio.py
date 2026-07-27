from __future__ import annotations

import base64
from pathlib import Path

from incidentcommander.demo_factory import SCENARIOS, architecture_svg, build_scenario, service_map_svg, timeline_svg
from incidentcommander.parser import parse_sources


ROOT = Path(__file__).resolve().parents[1]


def test_scenario_library_contains_large_mixed_format_demos():
    assert len(SCENARIOS) >= 4
    suffixes = set()
    for name in SCENARIOS:
        sources = build_scenario(name)
        events = parse_sources(sources)
        assert len(events) >= 200
        suffixes.update(Path(source_name).suffix for source_name, _ in sources)
    assert {".log", ".jsonl", ".csv"}.issubset(suffixes)


def test_repository_media_assets_are_valid():
    for svg in [architecture_svg(), service_map_svg(), timeline_svg()]:
        assert svg.lstrip().startswith("<svg")
    payload = base64.b64decode((ROOT / "assets" / "incident_replay.mp4.b64").read_text(encoding="ascii"))
    assert b"ftyp" in payload[:64]
    assert len(payload) > 10_000


def test_live_studio_page_has_launch_and_media_controls():
    source = (ROOT / "pages" / "9_Live_Incident_Studio.py").read_text(encoding="utf-8")
    compile(source, "9_Live_Incident_Studio.py", "exec")
    for marker in ["st.video", "st.image", "st.switch_page", "Launch this scenario", "Scenario gallery"]:
        assert marker in source
