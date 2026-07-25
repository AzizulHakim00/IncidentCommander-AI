from __future__ import annotations

import html
import json
from datetime import datetime, timezone


def _serialise(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_markdown_report(result: dict, source_name: str, episodes=None, blast=None, changes=None) -> str:
    summary = result["summary"]
    causes = result["root_causes"]
    lines = [
        "# IncidentCommander AI — Incident Intelligence Report", "",
        f"**Source:** {source_name}",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Fingerprint:** `{summary.get('fingerprint', 'n/a')}`", "",
        "## Executive Summary",
        f"- Incident severity: **{summary.get('severity', 'n/a')}** ({summary.get('severity_score', 0)}/100)",
        f"- Operational health score: **{summary.get('health_score', 0)}/100**",
        f"- Events analyzed: {summary.get('total_events', 0)}",
        f"- Errors / warnings / anomalies: {summary.get('errors', 0)} / {summary.get('warnings', 0)} / {summary.get('anomalies', 0)}",
        f"- Impacted services: {summary.get('impacted_services', 0)}",
        f"- Error rate: {summary.get('error_rate', 0)}%",
        f"- Availability proxy: {summary.get('availability_proxy', 0)}%",
        f"- P95 latency: {summary.get('p95_latency_ms') or 'not available'} ms", "",
        "## Ranked Root Causes",
    ]
    for idx, item in enumerate(causes, 1):
        lines.extend([f"### {idx}. {item['cause']}", f"Confidence: {item['confidence']:.1%}; evidence hits: {item['evidence_hits']}"])
        if item.get("evidence"):
            lines.append("Evidence:")
            lines.extend(f"- {evidence}" for evidence in item["evidence"])
        lines.append("Recommended checks:")
        lines.extend(f"- [ ] {step}" for step in item["runbook"])
        lines.append("")
    if blast is not None and not blast.empty:
        lines.extend(["## Blast Radius", ""])
        for _, row in blast.head(10).iterrows():
            lines.append(f"- **{row['service']}** — impact {row['impact_score']}/100; errors {row['errors']}; warnings {row['warnings']}")
        lines.append("")
    if episodes is not None and not episodes.empty:
        lines.extend(["## Correlated Episodes", ""])
        for _, row in episodes.head(10).iterrows():
            lines.append(f"- Episode {row['episode']}: {row['events']} events, {row['errors']} errors, probable cause: {row['probable_cause']}")
        lines.append("")
    if changes is not None and not changes.empty:
        lines.extend(["## Change Correlation", ""])
        for _, row in changes.head(10).iterrows():
            lines.append(f"- {row['service']} — {row['change']}: risk {row['risk_score']}/100, errors after change {row['errors_after']}")
        lines.append("")
    lines.extend(["## Observability Quality", f"- Overall score: {result.get('quality', {}).get('score', 0)}/100", "", "## Safety Note", "This report provides decision support. Validate evidence, permissions, rollback plans, and business impact before making production changes."])
    return "\n".join(lines)


def build_json_report(result: dict, source_name: str) -> str:
    payload = {
        "source": source_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {key: _serialise(value) for key, value in result["summary"].items()},
        "root_causes": result["root_causes"],
        "quality": result.get("quality", {}),
        "clusters": result["clusters"].to_dict(orient="records"),
    }
    return json.dumps(payload, indent=2, default=_serialise)


def build_html_report(markdown_text: str) -> str:
    escaped = html.escape(markdown_text)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>IncidentCommander AI Report</title>
<style>body{{font-family:Arial,sans-serif;max-width:980px;margin:40px auto;line-height:1.5;padding:0 20px}}pre{{white-space:pre-wrap;background:#f5f5f5;padding:24px;border-radius:12px}}</style></head><body><pre>{escaped}</pre></body></html>"""
