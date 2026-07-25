from incidentcommander.parser import parse_sources, parse_text


def test_text_parser_extracts_operational_metadata():
    event = parse_text("2026-07-26 02:00:01 ERROR [orders] request_id=r1 trace_id=t1 dependency=db duration_ms=150 status=500 failure", "a.log")[0]
    assert event.service == "orders"
    assert event.request_id == "r1"
    assert event.trace_id == "t1"
    assert event.dependency == "db"
    assert event.duration_ms == 150
    assert event.status_code == 500


def test_json_lines_and_multiple_sources():
    json_line = '{"timestamp":"2026-07-26T04:00:00Z","level":"ERROR","service":"api","message":"boom","request_id":"r2"}'
    events = parse_sources([("one.jsonl", json_line), ("two.log", "2026-07-26 04:00:01 INFO [worker] ok")])
    assert len(events) == 2
    assert events[0].service == "api"
    assert events[1].source == "two.log"
