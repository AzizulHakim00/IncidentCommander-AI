from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}
SEVERITY_RANK = {"SEV-1": 4, "SEV-2": 3, "SEV-3": 2, "SEV-4": 1}


def health_band(score: float | int) -> str:
    """Return a concise operational status label for a 0-100 health score."""
    value = float(score)
    if value >= 85:
        return "Healthy"
    if value >= 65:
        return "Degraded"
    if value >= 40:
        return "High risk"
    return "Critical"


def severity_rank(label: str) -> int:
    return SEVERITY_RANK.get(str(label).upper(), 0)


def service_scorecards(frame: pd.DataFrame, blast: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build service-level health, reliability, and impact metrics for the UI."""
    columns = [
        "service",
        "status",
        "health_score",
        "impact_score",
        "events",
        "errors",
        "warnings",
        "anomalies",
        "error_rate",
        "p95_latency_ms",
        "server_errors",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    for service, group in frame.groupby("service", dropna=False):
        events = int(len(group))
        errors = int(group["level"].isin(ERROR_LEVELS).sum())
        warnings = int((group["level"] == "WARN").sum())
        anomalies = int(group.get("is_anomaly", pd.Series(False, index=group.index)).fillna(False).sum())
        status_codes = pd.to_numeric(group.get("status_code"), errors="coerce")
        server_errors = int(status_codes.ge(500).sum()) if status_codes is not None else 0
        latency = pd.to_numeric(group.get("duration_ms"), errors="coerce").dropna()
        p95 = round(float(latency.quantile(0.95)), 1) if not latency.empty else None
        error_rate = round(100 * errors / max(events, 1), 1)
        health = max(
            0,
            round(
                100
                - error_rate * 1.35
                - min(24, warnings * 2.5)
                - min(22, anomalies * 4)
                - min(16, server_errors * 4)
            ),
        )
        rows.append(
            {
                "service": str(service),
                "status": health_band(health),
                "health_score": int(health),
                "events": events,
                "errors": errors,
                "warnings": warnings,
                "anomalies": anomalies,
                "error_rate": error_rate,
                "p95_latency_ms": p95,
                "server_errors": server_errors,
            }
        )

    cards = pd.DataFrame(rows)
    if blast is not None and not blast.empty and {"service", "impact_score"}.issubset(blast.columns):
        cards = cards.merge(blast[["service", "impact_score"]], on="service", how="left")
    else:
        cards["impact_score"] = 0
    cards["impact_score"] = cards["impact_score"].fillna(0).astype(int)
    return cards[columns].sort_values(
        ["impact_score", "errors", "health_score"], ascending=[False, False, True]
    )


def anomaly_heatmap(frame: pd.DataFrame, frequency: str = "5min") -> pd.DataFrame:
    """Return service x time risk intensity for a heatmap."""
    if frame.empty or "timestamp" not in frame.columns:
        return pd.DataFrame()
    timed = frame.dropna(subset=["timestamp"]).copy()
    if timed.empty:
        return pd.DataFrame()
    timed["timestamp"] = pd.to_datetime(timed["timestamp"], errors="coerce", utc=True)
    timed = timed.dropna(subset=["timestamp"])
    timed["time_bucket"] = timed["timestamp"].dt.floor(frequency)
    timed["risk_weight"] = 1
    timed.loc[timed["level"] == "WARN", "risk_weight"] = 2
    timed.loc[timed["level"].isin(ERROR_LEVELS), "risk_weight"] = 5
    if "is_anomaly" in timed.columns:
        timed.loc[timed["is_anomaly"].fillna(False), "risk_weight"] += 3
    return timed.pivot_table(
        index="service", columns="time_bucket", values="risk_weight", aggfunc="sum", fill_value=0
    )


def root_cause_table(root_causes: Iterable[dict]) -> pd.DataFrame:
    rows = []
    for rank, item in enumerate(root_causes, 1):
        rows.append(
            {
                "rank": rank,
                "cause": item.get("cause", "Unknown"),
                "confidence_percent": round(float(item.get("confidence", 0)) * 100, 1),
                "evidence_hits": int(item.get("evidence_hits", 0)),
            }
        )
    return pd.DataFrame(rows)


def executive_actions(result: dict, blast: pd.DataFrame, changes: pd.DataFrame) -> list[dict]:
    """Generate deterministic, evidence-backed next actions for responders."""
    summary = result.get("summary", {})
    causes = result.get("root_causes", [])
    actions: list[dict] = []

    if causes:
        top = causes[0]
        first_step = top.get("runbook", ["Validate the highest-confidence evidence."])[0]
        actions.append(
            {
                "priority": "P0" if summary.get("severity") == "SEV-1" else "P1",
                "title": f"Validate {top.get('cause', 'probable root cause')}",
                "detail": first_step,
                "evidence": f"{top.get('evidence_hits', 0)} signature hits · {float(top.get('confidence', 0)):.0%} confidence",
            }
        )

    if not blast.empty:
        top_service = blast.iloc[0]
        actions.append(
            {
                "priority": "P1",
                "title": f"Stabilize {top_service['service']}",
                "detail": "Inspect saturation, upstream dependencies, and recent changes before broad remediation.",
                "evidence": f"Impact score {int(top_service['impact_score'])}/100",
            }
        )

    if changes is not None and not changes.empty and float(changes.iloc[0].get("risk_score", 0)) > 0:
        change = changes.iloc[0]
        actions.append(
            {
                "priority": "P1",
                "title": "Review the highest-risk recent change",
                "detail": str(change.get("change", "Deployment or configuration change")),
                "evidence": f"Risk score {int(change.get('risk_score', 0))}/100",
            }
        )

    if float(summary.get("p95_latency_ms") or 0) >= 1000:
        actions.append(
            {
                "priority": "P2",
                "title": "Reduce latency amplification",
                "detail": "Trace slow requests across the noisiest dependency path and inspect timeout/retry fan-out.",
                "evidence": f"P95 latency {summary.get('p95_latency_ms')} ms",
            }
        )

    if not actions:
        actions.append(
            {
                "priority": "P3",
                "title": "Validate telemetry coverage",
                "detail": "Confirm timestamps, service names, and trace IDs before drawing a production conclusion.",
                "evidence": "No dominant operational signal found",
            }
        )
    return actions[:4]


def compare_incident(current_summary: dict, historical_row: pd.Series | dict) -> pd.DataFrame:
    """Prepare a two-column comparison between the active incident and one stored incident."""
    row = dict(historical_row)
    metrics = [
        ("Severity", current_summary.get("severity"), row.get("severity")),
        ("Health score", current_summary.get("health_score"), row.get("health_score")),
        ("Events", current_summary.get("total_events"), row.get("event_count")),
        ("Fingerprint", current_summary.get("fingerprint"), row.get("fingerprint")),
        ("Root cause", current_summary.get("top_root_cause", "Current analysis"), row.get("root_cause")),
    ]
    return pd.DataFrame(metrics, columns=["metric", "current", "historical"])
