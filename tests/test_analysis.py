from incidentcommander.analyzer import analyze_events
from incidentcommander.correlation import blast_radius, build_dependency_edges, correlate_episodes
from incidentcommander.parser import parse_text

SAMPLE = """2026-07-26 02:00:00 INFO [api] request_id=r1 dependency=orders request started
2026-07-26 02:00:01 ERROR [orders] request_id=r1 dependency=db SQLSTATE connection refused database
2026-07-26 02:00:02 ERROR [orders] request_id=r2 dependency=db database connection refused
2026-07-26 02:00:03 WARN [api] request_id=r1 dependency=orders upstream timeout
"""


def test_analysis_produces_v2_summary():
    result = analyze_events(parse_text(SAMPLE))
    assert result["summary"]["errors"] == 2
    assert result["summary"]["severity"].startswith("SEV-")
    assert result["summary"]["fingerprint"]
    assert result["root_causes"][0]["cause"] == "Database connectivity or pool exhaustion"
    assert result["quality"]["score"] > 0


def test_dependency_blast_radius_and_episodes():
    result = analyze_events(parse_text(SAMPLE))
    frame = result["frame"]
    assert not build_dependency_edges(frame).empty
    assert not blast_radius(frame).empty
    assert len(correlate_episodes(frame)) == 1
