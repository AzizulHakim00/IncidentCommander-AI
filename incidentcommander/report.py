from __future__ import annotations

from datetime import datetime, timezone


def build_markdown_report(result: dict, source_name: str) -> str:
    summary = result["summary"]
    causes = result["root_causes"]
    lines = [
        "# IncidentCommander AI Incident Report",
        "",
        f"**Source:** {source_name}",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Executive Summary",
        f"- Events analyzed: {summary.get('total_events', 0)}",
        f"- Errors: {summary.get('errors', 0)}",
        f"- Warnings: {summary.get('warnings', 0)}",
        f"- Detected anomalies: {summary.get('anomalies', 0)}",
        f"- Operational health score: {summary.get('health_score', 0)}/100",
        "",
        "## Ranked Root Causes",
    ]
    for idx, item in enumerate(causes, 1):
        lines.extend([
            f"### {idx}. {item['cause']}",
            f"Confidence: {item['confidence']:.1%}; evidence hits: {item['evidence_hits']}",
            "Recommended checks:",
            *[f"- {step}" for step in item["runbook"]],
            "",
        ])
    lines.extend([
        "## Safety Note",
        "This report is decision support. Validate evidence before making production changes.",
    ])
    return "\n".join(lines)
