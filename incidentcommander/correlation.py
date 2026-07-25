from __future__ import annotations

import pandas as pd

from .analyzer import ERROR_LEVELS, rank_root_causes


def build_timeline(frame: pd.DataFrame, frequency: str = "1min") -> pd.DataFrame:
    timed = frame.dropna(subset=["timestamp"]).copy()
    if timed.empty:
        return pd.DataFrame(columns=["timestamp", "events", "errors", "warnings", "anomalies", "avg_latency_ms"])
    timed = timed.set_index("timestamp")
    timeline = pd.DataFrame({
        "events": timed["message"].resample(frequency).count(),
        "errors": timed["level"].isin(ERROR_LEVELS).astype(int).resample(frequency).sum(),
        "warnings": (timed["level"] == "WARN").astype(int).resample(frequency).sum(),
        "anomalies": timed["is_anomaly"].astype(int).resample(frequency).sum(),
        "avg_latency_ms": timed["duration_ms"].resample(frequency).mean(),
    }).fillna({"events": 0, "errors": 0, "warnings": 0, "anomalies": 0})
    return timeline.reset_index()


def build_dependency_edges(frame: pd.DataFrame) -> pd.DataFrame:
    dependencies = frame.dropna(subset=["dependency"])
    if dependencies.empty:
        return pd.DataFrame(columns=["source", "target", "events", "errors"])
    rows = []
    for (service, dependency), group in dependencies.groupby(["service", "dependency"]):
        if service == dependency:
            continue
        rows.append({"source": str(service), "target": str(dependency), "events": int(len(group)), "errors": int(group["level"].isin(ERROR_LEVELS).sum())})
    return pd.DataFrame(rows).sort_values(["errors", "events"], ascending=False) if rows else pd.DataFrame(columns=["source", "target", "events", "errors"])


def blast_radius(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for service, group in frame.groupby("service"):
        errors = int(group["level"].isin(ERROR_LEVELS).sum())
        warnings = int((group["level"] == "WARN").sum())
        anomalies = int(group["is_anomaly"].sum())
        dependency_mentions = int((frame["dependency"] == service).sum())
        score = min(100, errors * 18 + warnings * 6 + anomalies * 8 + dependency_mentions * 10)
        if errors or warnings or anomalies or dependency_mentions:
            rows.append({"service": service, "impact_score": score, "errors": errors, "warnings": warnings, "anomalies": anomalies, "dependent_events": dependency_mentions})
    return pd.DataFrame(rows).sort_values("impact_score", ascending=False) if rows else pd.DataFrame(columns=["service", "impact_score", "errors", "warnings", "anomalies", "dependent_events"])


def correlate_episodes(frame: pd.DataFrame, gap_seconds: int = 120) -> pd.DataFrame:
    ordered = frame.sort_values(["timestamp", "line_number"], na_position="last").copy()
    if ordered.empty:
        return pd.DataFrame()
    episode_ids, episode, previous = [], 1, None
    for timestamp in ordered["timestamp"]:
        if pd.notna(timestamp) and previous is not None and (timestamp - previous).total_seconds() > gap_seconds:
            episode += 1
        episode_ids.append(episode)
        if pd.notna(timestamp):
            previous = timestamp
    ordered["episode"] = episode_ids
    rows = []
    for episode_id, group in ordered.groupby("episode"):
        causes = rank_root_causes(group)
        start, end = group["timestamp"].min(), group["timestamp"].max()
        duration = (end - start).total_seconds() if pd.notna(start) and pd.notna(end) else None
        rows.append({"episode": int(episode_id), "start": start, "end": end, "duration_seconds": duration, "events": int(len(group)), "errors": int(group["level"].isin(ERROR_LEVELS).sum()), "services": ", ".join(sorted(group["service"].unique())[:6]), "probable_cause": causes[0]["cause"], "confidence": causes[0]["confidence"]})
    return pd.DataFrame(rows).sort_values(["errors", "events"], ascending=False)


def correlate_changes(frame: pd.DataFrame, changes: pd.DataFrame, window_minutes: int = 10) -> pd.DataFrame:
    if changes.empty or frame["timestamp"].dropna().empty:
        return pd.DataFrame(columns=["timestamp", "service", "change", "errors_after", "events_after", "risk_score"])
    changes = changes.copy()
    changes["timestamp"] = pd.to_datetime(changes["timestamp"], errors="coerce", utc=True)
    changes = changes.dropna(subset=["timestamp"])
    rows = []
    for _, change in changes.iterrows():
        service = str(change.get("service", "all"))
        start = change["timestamp"]
        end = start + pd.Timedelta(minutes=window_minutes)
        mask = frame["timestamp"].between(start, end, inclusive="both")
        if service.lower() not in {"all", "*", "unknown", ""}:
            mask &= (frame["service"] == service) | (frame["dependency"] == service)
        window = frame[mask]
        errors = int(window["level"].isin(ERROR_LEVELS).sum())
        events = int(len(window))
        risk = min(100, errors * 20 + int(window["is_anomaly"].sum()) * 10)
        rows.append({"timestamp": start, "service": service, "change": change.get("change", change.get("version", "deployment/config change")), "errors_after": errors, "events_after": events, "risk_score": risk})
    return pd.DataFrame(rows).sort_values("risk_score", ascending=False)
