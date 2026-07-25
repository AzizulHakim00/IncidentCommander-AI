from __future__ import annotations

import math
import re
from dataclasses import asdict

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer

from .parser import LogEvent

ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}
SIGNATURES = {
    "Database connectivity or pool exhaustion": [r"connection refused", r"timeout.*database", r"pool.*exhaust", r"too many connections", r"sqlstate"],
    "Authentication or authorization failure": [r"unauthorized", r"forbidden", r"invalid token", r"jwt", r"authentication failed"],
    "Memory pressure or resource exhaustion": [r"outofmemory", r"heap space", r"cannot allocate memory", r"killed process", r"oom"],
    "Dependency/API outage": [r"502 bad gateway", r"503 service unavailable", r"upstream.*timeout", r"dependency.*failed", r"circuit breaker"],
    "Application exception": [r"exception", r"traceback", r"nullpointer", r"indexerror", r"keyerror", r"panic"],
    "Disk or filesystem issue": [r"no space left", r"read-only file system", r"disk full", r"i/o error"],
}
RUNBOOKS = {
    "Database connectivity or pool exhaustion": ["Check database reachability and DNS.", "Inspect connection-pool saturation and slow queries.", "Validate credentials and recent database changes."],
    "Authentication or authorization failure": ["Check identity-provider health and token expiry.", "Compare failures with recent auth changes.", "Verify clock synchronization and signing keys."],
    "Memory pressure or resource exhaustion": ["Inspect memory, CPU, and process limits.", "Capture heap/profile data before restarting if safe.", "Review recent traffic and deployment changes."],
    "Dependency/API outage": ["Check upstream service health and latency.", "Review circuit-breaker and retry behavior.", "Enable fallback or reduce traffic if available."],
    "Application exception": ["Inspect the first stack trace and correlated request ID.", "Compare with the latest release and configuration changes.", "Reproduce using the smallest failing input."],
    "Disk or filesystem issue": ["Check free disk space and inode usage.", "Inspect log growth and retention settings.", "Verify mount health and permissions."],
    "Unknown / mixed failure": ["Review the highest-anomaly log cluster.", "Correlate errors by service and time window.", "Check recent deployments, configuration, and dependency status."],
}


def _to_frame(events: list[LogEvent]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(e) for e in events])
    if frame.empty:
        return pd.DataFrame(columns=["line_number", "raw", "timestamp", "level", "service", "message"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    return frame


def _cluster_messages(messages: list[str]) -> tuple[np.ndarray, np.ndarray]:
    if len(messages) < 2:
        return np.zeros(len(messages), dtype=int), np.zeros(len(messages))
    vectorizer = TfidfVectorizer(max_features=2500, ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform(messages)
    n_clusters = min(max(2, int(math.sqrt(len(messages)))), 6, len(messages))
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(matrix)
    contamination = min(0.20, max(0.03, 3 / max(len(messages), 20)))
    dense = matrix.toarray()
    scores = -IsolationForest(random_state=42, contamination=contamination).fit(dense).decision_function(dense)
    return labels, scores


def rank_root_causes(frame: pd.DataFrame) -> list[dict]:
    text = "\n".join(frame.loc[frame["level"].isin(ERROR_LEVELS | {"WARN"}), "message"].astype(str)).lower()
    scored = []
    for cause, patterns in SIGNATURES.items():
        hits = sum(len(re.findall(pattern, text, flags=re.I)) for pattern in patterns)
        if hits:
            scored.append({"cause": cause, "evidence_hits": hits, "score": min(0.98, 0.45 + 0.1 * hits)})
    if not scored:
        scored.append({"cause": "Unknown / mixed failure", "evidence_hits": 0, "score": 0.35})
    scored.sort(key=lambda item: (item["score"], item["evidence_hits"]), reverse=True)
    total = sum(item["score"] for item in scored)
    for item in scored:
        item["confidence"] = round(item["score"] / total, 3)
        item["runbook"] = RUNBOOKS[item["cause"]]
    return scored[:5]


def analyze_events(events: list[LogEvent]) -> dict:
    frame = _to_frame(events)
    if frame.empty:
        return {"frame": frame, "summary": {}, "root_causes": [], "clusters": pd.DataFrame()}
    labels, anomaly_scores = _cluster_messages(frame["message"].astype(str).tolist())
    frame["cluster"] = labels
    frame["anomaly_score"] = anomaly_scores
    frame["is_anomaly"] = frame["anomaly_score"] >= frame["anomaly_score"].quantile(0.9)
    level_counts = frame["level"].value_counts().to_dict()
    service_counts = frame.loc[frame["level"].isin(ERROR_LEVELS), "service"].value_counts().to_dict()
    rows = []
    for cluster_id, group in frame.groupby("cluster"):
        representative = group.sort_values("anomaly_score", ascending=False).iloc[0]
        rows.append({"cluster": int(cluster_id), "events": int(len(group)), "errors": int(group["level"].isin(ERROR_LEVELS).sum()), "max_anomaly": float(group["anomaly_score"].max()), "representative": representative["message"][:220]})
    clusters = pd.DataFrame(rows).sort_values(["errors", "max_anomaly"], ascending=False)
    health = max(0, 100 - 8 * level_counts.get("ERROR", 0) - 14 * level_counts.get("CRITICAL", 0) - 18 * level_counts.get("FATAL", 0) - 2 * level_counts.get("WARN", 0))
    summary = {"total_events": int(len(frame)), "errors": int(frame["level"].isin(ERROR_LEVELS).sum()), "warnings": int((frame["level"] == "WARN").sum()), "anomalies": int(frame["is_anomaly"].sum()), "services": int(frame["service"].nunique()), "health_score": int(health), "top_error_service": next(iter(service_counts), "none")}
    return {"frame": frame, "summary": summary, "root_causes": rank_root_causes(frame), "clusters": clusters}
