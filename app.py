from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from incidentcommander.analyzer import ERROR_LEVELS, analyze_events
from incidentcommander.correlation import blast_radius, build_dependency_edges, build_timeline, correlate_changes, correlate_episodes
from incidentcommander.history import list_incidents, save_incident, similar_incidents
from incidentcommander.parser import parse_sources
from incidentcommander.redaction import audit_sensitive_text, redact_text
from incidentcommander.report import build_html_report, build_json_report, build_markdown_report

BASE_DIR = Path(__file__).parent
HISTORY_DB = BASE_DIR / "data" / "incidents.db"

st.set_page_config(page_title="IncidentCommander AI v2", page_icon="🚨", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {padding-top: 1.1rem; max-width: 1500px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.07); border: 1px solid rgba(128,128,128,.18); padding: 14px; border-radius: 14px;}
.hero {padding: 24px 28px; border-radius: 22px; background: linear-gradient(135deg, rgba(220,38,38,.20), rgba(37,99,235,.14)); border: 1px solid rgba(220,38,38,.28); margin-bottom: 16px;}
.hero h1 {margin-bottom: 4px;}
.pill {display:inline-block;padding:5px 10px;border-radius:999px;background:rgba(128,128,128,.13);margin-right:6px;font-size:.82rem;}
.small {opacity:.76;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🚨 IncidentCommander AI v2</h1><p class="small">Multi-source incident correlation, anomaly intelligence, blast-radius analysis, deployment-change correlation, and evidence-driven response guidance.</p><span class="pill">Offline AI</span><span class="pill">No paid API</span><span class="pill">Human-in-the-loop</span></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Incident input")
    uploaded = st.file_uploader("Upload one or more log files", type=["log", "txt", "out", "csv", "jsonl"], accept_multiple_files=True)
    demo = st.button("Load multi-service demo", use_container_width=True)
    redact = st.toggle("Redact sensitive values", value=True)
    gap_seconds = st.slider("Episode gap (seconds)", 30, 600, 120, 30)
    st.divider()
    st.subheader("Optional change data")
    change_file = st.file_uploader("Deployment/change CSV", type=["csv"], key="changes")
    st.caption("Columns: timestamp, service, change")
    st.divider()
    st.caption("Accepted logs: plain text, JSON Lines, and CSV with a message column.")

if demo:
    demo_files = [BASE_DIR / "sample_logs" / "demo_incident.log", BASE_DIR / "sample_logs" / "payments.jsonl"]
    st.session_state["sources"] = [(path.name, path.read_text(encoding="utf-8")) for path in demo_files]
elif uploaded:
    st.session_state["sources"] = [(item.name, item.getvalue().decode("utf-8", errors="replace")) for item in uploaded]

sources = st.session_state.get("sources", [])
if not sources:
    st.info("Upload logs or load the multi-service demo to start the incident investigation.")
    st.stop()

raw_joined = "\n".join(text for _, text in sources)
sensitive_audit = audit_sensitive_text(raw_joined)
processed_sources = [(name, redact_text(text) if redact else text) for name, text in sources]
events = parse_sources(processed_sources)
if not events:
    st.error("No valid log events could be parsed from the supplied files.")
    st.stop()

result = analyze_events(events)
frame = result["frame"]
summary = result["summary"]
timeline = build_timeline(frame)
edges = build_dependency_edges(frame)
blast = blast_radius(frame)
episodes = correlate_episodes(frame, gap_seconds=gap_seconds)

change_results = pd.DataFrame()
if change_file:
    try:
        changes = pd.read_csv(change_file)
        required = {"timestamp", "service"}
        if not required.issubset(changes.columns):
            st.sidebar.error("Change CSV needs timestamp and service columns.")
        else:
            change_results = correlate_changes(frame, changes)
    except Exception as exc:
        st.sidebar.error(f"Could not read change CSV: {exc}")

metric_values = [
    ("Severity", summary["severity"]),
    ("Health", f"{summary['health_score']}/100"),
    ("Events", summary["total_events"]),
    ("Errors", summary["errors"]),
    ("Anomalies", summary["anomalies"]),
    ("Impacted", summary["impacted_services"]),
    ("Availability*", f"{summary['availability_proxy']}%"),
    ("P95 latency", f"{summary['p95_latency_ms']} ms" if summary["p95_latency_ms"] is not None else "n/a"),
]
for col, (label, value) in zip(st.columns(8), metric_values):
    col.metric(label, value)
st.caption("*Availability is a log-derived proxy, not a substitute for production SLO telemetry.")

command, correlation, service_map, causes, explorer, history_tab, quality_tab, reports = st.tabs([
    "Command Center", "Timeline & Correlation", "Service Map", "Root Cause & Runbook", "Log Explorer", "Incident History", "Model & Data Quality", "Report Center"
])

with command:
    left, right = st.columns([1.15, .85])
    with left:
        st.subheader("Incident timeline")
        if timeline.empty:
            st.info("No parseable timestamps were found.")
        else:
            long = timeline.melt(id_vars="timestamp", value_vars=["events", "errors", "warnings", "anomalies"], var_name="signal", value_name="count")
            st.plotly_chart(px.line(long, x="timestamp", y="count", color="signal", markers=True), use_container_width=True)
    with right:
        st.subheader("Command summary")
        top_cause = result["root_causes"][0]
        st.markdown(f"**Probable cause:** {top_cause['cause']}")
        st.markdown(f"**Confidence:** {top_cause['confidence']:.0%}")
        st.markdown(f"**Top error service:** `{summary['top_error_service']}`")
        st.markdown(f"**Incident fingerprint:** `{summary['fingerprint']}`")
        if summary["severity"] == "SEV-1":
            st.error("Critical multi-service incident. Escalate and establish an incident channel immediately.")
        elif summary["severity"] == "SEV-2":
            st.warning("Major incident. Assign an incident commander and validate rollback options.")
        else:
            st.info("Investigate using the ranked evidence and correlated episodes.")
    st.subheader("Blast-radius priority")
    if blast.empty:
        st.success("No impacted service could be ranked.")
    else:
        st.dataframe(blast, use_container_width=True, hide_index=True)
    if not change_results.empty:
        st.subheader("Changes most correlated with the incident")
        st.dataframe(change_results, use_container_width=True, hide_index=True)

with correlation:
    st.subheader("Correlated incident episodes")
    st.dataframe(episodes, use_container_width=True, hide_index=True)
    a, b = st.columns(2)
    with a:
        st.subheader("Errors by service")
        counts = frame[frame["level"].isin(ERROR_LEVELS)]["service"].value_counts().rename_axis("service").reset_index(name="errors")
        if counts.empty:
            st.success("No error-level events found.")
        else:
            st.plotly_chart(px.bar(counts, x="errors", y="service", orientation="h"), use_container_width=True)
    with b:
        st.subheader("Latency over time")
        latency = frame.dropna(subset=["timestamp", "duration_ms"])
        if latency.empty:
            st.info("No duration or latency fields were found.")
        else:
            st.plotly_chart(px.scatter(latency, x="timestamp", y="duration_ms", color="service"), use_container_width=True)
    request_ids = frame.dropna(subset=["request_id"])
    if not request_ids.empty:
        st.subheader("Cross-service request traces")
        trace_summary = request_ids.groupby("request_id").agg(
            events=("message", "count"),
            services=("service", lambda values: ", ".join(sorted(set(values)))),
            errors=("level", lambda values: int(pd.Series(values).isin(ERROR_LEVELS).sum())),
        ).reset_index()
        st.dataframe(trace_summary.sort_values(["errors", "events"], ascending=False), use_container_width=True, hide_index=True)

with service_map:
    st.subheader("Observed service dependency map")
    if edges.empty:
        st.info("Add dependency=service or upstream=service metadata to logs to build the map.")
    else:
        nodes = sorted(set(edges["source"]) | set(edges["target"]))
        index = {node: idx for idx, node in enumerate(nodes)}
        fig = go.Figure(go.Sankey(
            node={"label": nodes, "pad": 18, "thickness": 18},
            link={
                "source": [index[item] for item in edges["source"]],
                "target": [index[item] for item in edges["target"]],
                "value": edges["events"].clip(lower=1),
                "label": [f"{row.errors} errors" for row in edges.itertuples()],
            },
        ))
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(edges, use_container_width=True, hide_index=True)
    st.subheader("Service impact matrix")
    if not blast.empty:
        st.plotly_chart(px.bar(blast, x="service", y="impact_score", hover_data=["errors", "warnings", "anomalies", "dependent_events"]), use_container_width=True)

with causes:
    st.subheader("Ranked probable root causes")
    for index, item in enumerate(result["root_causes"], 1):
        with st.expander(f"{index}. {item['cause']} — {item['confidence']:.0%} confidence", expanded=index == 1):
            st.write(f"Evidence hits: **{item['evidence_hits']}**")
            if item.get("evidence"):
                st.markdown("**Evidence samples**")
                for evidence in item["evidence"]:
                    st.code(evidence)
            st.markdown("**Human-reviewed runbook**")
            for step_index, step in enumerate(item["runbook"]):
                st.checkbox(step, key=f"runbook-{summary['fingerprint']}-{index}-{step_index}")
    st.warning("The tool does not execute remediation. Confirm evidence, access, rollback safety, and business impact before production changes.")

with explorer:
    services = ["All"] + sorted(frame["service"].unique().tolist())
    levels = ["All"] + sorted(frame["level"].unique().tolist())
    source_values = ["All"] + sorted(frame["source"].unique().tolist())
    a, b, c, d = st.columns([1, 1, 1, 2])
    service = a.selectbox("Service", services)
    level = b.selectbox("Level", levels)
    selected_source = c.selectbox("Source", source_values)
    query = d.text_input("Search messages, request IDs, or traces")
    anomaly_only = st.toggle("Show anomalies only")
    filtered = frame.copy()
    if service != "All":
        filtered = filtered[filtered["service"] == service]
    if level != "All":
        filtered = filtered[filtered["level"] == level]
    if selected_source != "All":
        filtered = filtered[filtered["source"] == selected_source]
    if anomaly_only:
        filtered = filtered[filtered["is_anomaly"]]
    if query:
        mask = (
            filtered["message"].str.contains(query, case=False, na=False)
            | filtered["request_id"].fillna("").astype(str).str.contains(query, case=False)
            | filtered["trace_id"].fillna("").astype(str).str.contains(query, case=False)
        )
        filtered = filtered[mask]
    columns = ["source", "line_number", "timestamp", "level", "service", "dependency", "request_id", "status_code", "duration_ms", "cluster", "anomaly_score", "is_anomaly", "message"]
    st.dataframe(filtered[columns].sort_values("anomaly_score", ascending=False), use_container_width=True, hide_index=True, height=520)

with history_tab:
    st.subheader("Incident memory")
    note = st.text_input("Resolution or investigation note", placeholder="Example: Rolled back orders service v2.4.1")
    if st.button("Save current incident", type="primary"):
        try:
            incident_id = save_incident(HISTORY_DB, result, ", ".join(name for name, _ in sources), note)
            st.success(f"Incident #{incident_id} saved.")
        except Exception as exc:
            st.error(f"Could not save incident history: {exc}")
    try:
        similar = similar_incidents(HISTORY_DB, result)
        history = list_incidents(HISTORY_DB)
        st.markdown("**Most similar previous incidents**")
        if similar.empty:
            st.info("No saved incidents yet.")
        else:
            st.dataframe(similar[["id", "created_at", "severity", "root_cause", "services", "notes", "similarity"]], use_container_width=True, hide_index=True)
        st.markdown("**Full incident history**")
        st.dataframe(history, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.warning(f"Incident history is unavailable in this environment: {exc}")

with quality_tab:
    st.subheader("Observability quality")
    quality = result["quality"]
    st.progress(quality["score"] / 100, text=f"Overall observability score: {quality['score']}/100")
    quality_frame = pd.DataFrame([
        {"dimension": key.replace("_", " ").title(), "coverage_percent": value}
        for key, value in quality.items() if key != "score"
    ])
    st.plotly_chart(px.bar(quality_frame, x="dimension", y="coverage_percent", range_y=[0, 100]), use_container_width=True)
    a, b = st.columns(2)
    with a:
        st.subheader("Sensitive-data audit")
        audit_frame = pd.DataFrame([{"type": key, "detections": value} for key, value in sensitive_audit.items()])
        st.dataframe(audit_frame, use_container_width=True, hide_index=True)
        st.caption("Redaction applies before parsing and report generation when enabled.")
    with b:
        st.subheader("Cluster diagnostics")
        st.dataframe(result["clusters"], use_container_width=True, hide_index=True)
    st.markdown("**Data-quality recommendations**")
    recommendations = []
    if quality["timestamps"] < 90:
        recommendations.append("Standardize UTC timestamps on every event.")
    if quality["service_names"] < 90:
        recommendations.append("Include a stable service or component name.")
    if quality["request_or_trace_ids"] < 60:
        recommendations.append("Propagate request and trace IDs across service boundaries.")
    if quality["latency_metadata"] < 40:
        recommendations.append("Add duration_ms and status_code fields to request logs.")
    if not recommendations:
        recommendations.append("Metadata coverage is strong; focus next on consistent event schemas and SLO telemetry.")
    for recommendation in recommendations:
        st.write(f"- {recommendation}")

with reports:
    source_name = ", ".join(name for name, _ in sources)
    markdown = build_markdown_report(result, source_name, episodes=episodes, blast=blast, changes=change_results)
    html_report = build_html_report(markdown)
    json_report = build_json_report(result, source_name)
    st.subheader("Incident report preview")
    st.markdown(markdown)
    a, b, c, d = st.columns(4)
    a.download_button("Markdown report", markdown, file_name="incident-report.md", mime="text/markdown", use_container_width=True)
    b.download_button("HTML report", html_report, file_name="incident-report.html", mime="text/html", use_container_width=True)
    c.download_button("JSON report", json_report, file_name="incident-report.json", mime="application/json", use_container_width=True)
    d.download_button("Analyzed events", frame.to_csv(index=False).encode("utf-8"), file_name="analyzed-events.csv", mime="text/csv", use_container_width=True)
