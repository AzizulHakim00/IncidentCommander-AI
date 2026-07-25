from pathlib import Path

from incidentcommander.analyzer import analyze_events
from incidentcommander.history import list_incidents, save_incident, similar_incidents
from incidentcommander.parser import parse_text
from incidentcommander.redaction import audit_sensitive_text, redact_text
from incidentcommander.report import build_json_report, build_markdown_report

SAMPLE = """2026-07-26 02:00:01 ERROR [orders] dependency=db SQLSTATE connection refused database
2026-07-26 02:00:02 ERROR [orders] dependency=db connection pool exhausted
"""


def test_redaction_audit_and_replace():
    text = "email=user@example.com api_key=supersecret123"
    audit = audit_sensitive_text(text)
    assert audit["email"] == 1
    assert audit["api_key"] == 1
    redacted = redact_text(text)
    assert "user@example.com" not in redacted
    assert "supersecret123" not in redacted


def test_history_and_reports(tmp_path: Path):
    result = analyze_events(parse_text(SAMPLE))
    db = tmp_path / "incidents.db"
    saved_id = save_incident(db, result, "sample.log", "resolved")
    assert saved_id == 1
    assert len(list_incidents(db)) == 1
    assert similar_incidents(db, result).iloc[0]["similarity"] > 0
    markdown = build_markdown_report(result, "sample.log")
    json_report = build_json_report(result, "sample.log")
    assert "Blast Radius" not in markdown
    assert "Safety Note" in markdown
    assert '"summary"' in json_report
