from incidentcommander.analyzer import analyze_events
from incidentcommander.parser import parse_text
from incidentcommander.report import build_markdown_report

SAMPLE = """2026-07-26 02:00:00 INFO [api] request started
2026-07-26 02:00:01 ERROR [orders] SQLSTATE connection refused database
2026-07-26 02:00:02 ERROR [orders] database connection refused
2026-07-26 02:00:03 WARN [api] upstream timeout
"""


def test_parser_extracts_fields():
    events = parse_text(SAMPLE)
    assert len(events) == 4
    assert events[1].level == "ERROR"
    assert events[1].service == "orders"


def test_analysis_produces_summary_and_clusters():
    result = analyze_events(parse_text(SAMPLE))
    assert result["summary"]["errors"] == 2
    assert not result["clusters"].empty


def test_database_root_cause_is_ranked():
    result = analyze_events(parse_text(SAMPLE))
    assert result["root_causes"][0]["cause"] == "Database connectivity or pool exhaustion"


def test_report_contains_safety_note():
    result = analyze_events(parse_text(SAMPLE))
    report = build_markdown_report(result, "sample.log")
    assert "Safety Note" in report
    assert "sample.log" in report
