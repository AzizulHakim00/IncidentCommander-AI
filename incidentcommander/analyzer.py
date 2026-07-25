from __future__ import annotations

import hashlib
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
    "Database connectivity or pool exhaustion": [r"connection refused", r"timeout.*database", r"pool.*exhaust", r"too many connections", r"sqlstate", r"deadlock"],
    "Authentication or authorization failure": [r"unauthorized", r"forbidden", r"invalid token", r"jwt", r"authentication failed", r"access denied"],
    "Memory pressure or resource exhaustion": [r"outofmemory", r"heap space", r"cannot allocate memory", r"killed process", r"\boom\b", r"resource exhausted"],
    "Dependency or API outage": [r"502 bad gateway", r"503 service unavailable", r"upstream.*timeout", r"dependency.*failed", r"circuit breaker", r"connection reset"],
    "Application exception": [r"exception", r"traceback", r"nullpointer", r"indexerror", r"keyerror", r"panic", r"segmentation fault"],
    "Disk or filesystem issue": [r"no space left", r"read-only file system", r"disk full", r"i/o error", r"inode"],
    "DNS or network resolution failure": [r"name or service not known", r"dns", r"unknown host", r"temporary failure in name resolution", r"network unreachable"],
    "TLS or certificate failure": [r"certificate.*expired", r"ssl", r"tls", r"handshake failed", r"x509"],
    "Rate limiting or traffic spike": [r"rate limit", r"too many requests", r"\b429\b", r"throttl", r"queue backlog"],
    "Configuration or deployment regression": [r"config.*invalid", r"environment variable", r"migration failed", r"version mismatch", r"rollback", r"deployment failed"],
}
RUNBOOKS = {
    "Database connectivity or pool exhaustion": ["Check database reachability, DNS, and failover status.", "Inspect connection-pool saturation, locks, and slow queries.", "Validate credentials, schema migrations, and recent database changes."],
    "Authentication or authorization failure": ["Check identity-provider health and token expiry.", "Compare failures with recent auth or policy changes.", "Verify clock synchronization, scopes, and signing keys."],
    "Memory pressure or resource exhaustion": ["Inspect memory, CPU, file descriptors, and process limits.", "Capture heap/profile data before restarting when safe.", "Review recent traffic, memory growth, and deployment changes."],
    "Dependency or API outage": ["Check upstream health, latency, and error rate.", "Review circuit-breaker, timeout, and retry behaviour.", "Enable fallback, shed load, or route traffic when available."],
    "Application exception": ["Inspect the earliest stack trace and correlated request or trace ID.", "Compare with the latest release and configuration changes.", "Reproduce using the smallest failing input and add a regression test."],
    "Disk or filesystem issue": ["Check disk, inode, and mount utilisation.", "Inspect log growth, temporary files, and retention settings.", "Verify mount health, permissions, and storage quotas."],
    "DNS or network resolution failure": ["Check DNS resolver health and service records.", "Validate network routes, security groups, and proxy settings.", "Compare failures across hosts and availability zones."],
    "TLS or certificate failure": ["Inspect certificate expiry and trust chain.", "Verify server name, cipher support, and system time.", "Check recent certificate rotation or ingress changes."],
    "Rate limiting or traffic spike": ["Check request rate, concurrency, and queue depth.", "Identify the noisiest clients or endpoints.", "Apply load shedding, caching, or controlled capacity increase."],
    "Configuration or deployment regression": ["Compare the incident start with deployments and configuration changes.", "Validate environment variables, feature flags, and migrations.", "Prepare a controlled rollback if evidence supports it."],
    "Unknown or mixed failure": ["Review the highest-anomaly cluster and earliest error.", "Correlate events by service, trace, and time window.", "Check recent deployments, configuration, capacity, and dependencies."],
}


def _to_frame(events: list[LogEvent]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(e) for e in events])
    columns = ["line_number", "source", "raw", "timestamp", "level", "service", "message", "request_id", "trace_id", "host", "dependency", "duration_ms", "status_code"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    frame["service"] = frame["service"].fillna("unknown").astype(str)
    frame["message"] = frame["message"].fillna("").astype(str)
    return frame


def _cluster_messages(messages: list[str]) -> tuple[np.ndarray, np.ndarray]:
    count = len(messages)
    if count < 2 or len(set(messages)) < 2:
        return np.zeros(count, dtype=int), np.zeros(count)
    vectorizer = TfidfVectorizer(max_features=3500, ngram_range=(1, 2), stop_words="english", min_df=1)
    matrix = vectorizer.fit_transform(messages)
    n_clusters = min(max(2, int(math.sqrt(count))), 8, count, len(set(messages)))
    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(matrix)
    contamination = min(0.18, max(0.03, 4 / max(count, 25)))
    dense = matrix.toarray()
    scores = -IsolationForest(random_state=42, contamination=contamination).fit(dense).decision_function(dense)
    return labels, scores


def rank_root_causes(frame: pd.DataFrame) -> list[dict]:
    evidence_frame = frame[frame["level"].isin(ERROR_LEVELS | {"WARN"})]
    scored: list[dict] = []
    for cause, patterns in SIGNATURES.items():
        matched_rows = []
        hits = 0
        for _, row in evidence_frame.iterrows():
            row_hits = sum(len(re.findall(pattern, row["message"], flags=re.I)) for pattern in patterns)
            if row_hits:
                hits += row_hits
                matched_rows.append(f"[{row['service']}] {row['message'][:180]}")
        if hits:
            severity_boost = int(evidence_frame["level"].isin({"CRITICAL", "FATAL"}).sum()) * 0.04
            score = min(0.99, 0.38 + 0.10 * hits + severity_boost)
            scored.append({"cause": cause, "evidence_hits": hits, "score": score, "evidence": matched_rows[:4]})
    if not scored:
        scored.append({"cause": "Unknown or mixed failure", "evidence_hits": 0, "score": 0.35, "evidence": []})
    scored.sort(key=lambda item: (item["score"], item["evidence_hits"]), reverse=True)
    total = sum(item["score"] for item in scored)
    for item in scored:
        item["confidence"] = round(item["score"] / total, 3)
        item["runbook"] = RUNBOOKS[item["cause"]]
    return scored[:6]


def _incident_severity(frame: pd.DataFrame, impacted_services: int) -> tuple[str, int]:
    errors = int(frame["level"].isin(ERROR_LEVELS).sum())
    critical = int(frame["level"].isin({"CRITICAL", "FATAL"}).sum())
    error_rate = errors / max(len(frame), 1)
    score = min(100, round(error_rate * 55 + critical * 12 + max(0, impacted_services - 1) * 8 + int(frame["is_anomaly"].sum()) * 2))
    if score >= 75:
        return "SEV-1", score
    if score >= 50:
        return "SEV-2", score
    if score >= 25:
        return "SEV-3", score
    return "SEV-4", score


def _observability_quality(frame: pd.DataFrame) -> dict:
    total = max(len(frame), 1)
    fields = {
        "timestamps": float(frame["timestamp"].notna().sum() / total),
        "service_names": float((frame["service"] != "unknown").sum() / total),
        "request_or_trace_ids": float((frame["request_id"].notna() | frame["trace_id"].notna()).sum() / total),
        "host_metadata": float(frame["host"].notna().sum() / total),
        "latency_metadata": float(frame["duration_ms"].notna().sum() / total),
    }
    score = round(100 * (0.3 * fields["timestamps"] + 0.3 * fields["service_names"] + 0.2 * fields["request_or_trace_ids"] + 0.1 * fields["host_metadata"] + 0.1 * fields["latency_metadata"]))
    return {"score": score, **{key: round(value * 100, 1) for key, value in fields.items()}}


def analyze_events(events: list[LogEvent]) -> dict:
    frame = _to_frame(events)
    if frame.empty:
        return {"frame": frame, "summary": {}, "root_causes": [], "clusters": pd.DataFrame(), "quality": {}}
    labels, anomaly_scores = _cluster_messages(frame["message"].tolist())
    frame["cluster"] = labels
    frame["anomaly_score"] = anomaly_scores
    threshold = frame["anomaly_score"].quantile(0.90) if len(frame) >= 10 else frame["anomaly_score"].max()
    frame["is_anomaly"] = frame["anomaly_score"] >= threshold
    error_services = frame.loc[frame["level"].isin(ERROR_LEVELS), "service"].value_counts()
    rows = []
    for cluster_id, group in frame.groupby("cluster"):
        representative = group.sort_values("anomaly_score", ascending=False).iloc[0]
        rows.append({"cluster": int(cluster_id), "events": int(len(group)), "errors": int(group["level"].isin(ERROR_LEVELS).sum()), "services": ", ".join(sorted(group["service"].unique())[:4]), "max_anomaly": round(float(group["anomaly_score"].max()), 4), "representative": representative["message"][:220]})
    clusters = pd.DataFrame(rows).sort_values(["errors", "max_anomaly"], ascending=False)
    impacted_services = int(frame.loc[frame["level"].isin(ERROR_LEVELS | {"WARN"}), "service"].nunique())
    severity, severity_score = _incident_severity(frame, impacted_services)
    errors = int(frame["level"].isin(ERROR_LEVELS).sum())
    warnings = int((frame["level"] == "WARN").sum())
    health = max(0, round(100 - 55 * errors / max(len(frame), 1) - 20 * warnings / max(len(frame), 1) - 4 * impacted_services))
    durations = frame["duration_ms"].dropna()
    root_causes = rank_root_causes(frame)
    fingerprint_input = f"{root_causes[0]['cause']}|{','.join(error_services.head(3).index.astype(str))}|{severity}"
    summary = {
        "total_events": int(len(frame)), "errors": errors, "warnings": warnings,
        "anomalies": int(frame["is_anomaly"].sum()), "services": int(frame["service"].nunique()),
        "impacted_services": impacted_services, "health_score": int(health),
        "top_error_service": error_services.index[0] if not error_services.empty else "none",
        "severity": severity, "severity_score": severity_score,
        "error_rate": round(100 * errors / max(len(frame), 1), 2),
        "p95_latency_ms": round(float(durations.quantile(0.95)), 1) if not durations.empty else None,
        "availability_proxy": round(max(0.0, 100 - 100 * errors / max(len(frame), 1)), 2),
        "fingerprint": hashlib.sha256(fingerprint_input.encode()).hexdigest()[:12],
        "start_time": frame["timestamp"].min(), "end_time": frame["timestamp"].max(),
    }
    return {"frame": frame, "summary": summary, "root_causes": root_causes, "clusters": clusters, "quality": _observability_quality(frame)}
