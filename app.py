from __future__ import annotations

from pathlib import Path

import plotly.express as px
import streamlit as st

from incidentcommander.analyzer import analyze_events
from incidentcommander.parser import parse_text
from incidentcommander.report import build_markdown_report

st.set_page_config(page_title="IncidentCommander AI", page_icon="🚨", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1400px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.18); padding: 14px; border-radius: 14px;}
.hero {padding: 22px 26px; border-radius: 20px; background: linear-gradient(135deg, rgba(239,68,68,.18), rgba(59,130,246,.12)); border: 1px solid rgba(239,68,68,.25); margin-bottom: 18px;}
.small {opacity:.78;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🚨 IncidentCommander AI</h1><p class="small">Log anomaly detection, error clustering, evidence-based root-cause ranking, and incident runbooks—without paid APIs.</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Input")
    uploaded = st.file_uploader("Upload logs", type=["log", "txt", "out", "csv"])
    use_demo = st.button("Load demo incident", use_container_width=True)
    st.caption("Supported: plain-text application, server, and container logs.")

if use_demo:
    demo_path = Path(__file__).parent / "sample_logs" / "demo_incident.log"
    st.session_state["log_text"] = demo_path.read_text(encoding="utf-8")
    st.session_state["source_name"] = demo_path.name
elif uploaded:
    st.session_state["log_text"] = uploaded.getvalue().decode("utf-8", errors="replace")
    st.session_state["source_name"] = uploaded.name

log_text = st.session_state.get("log_text", "")
source_name = st.session_state.get("source_name", "uploaded.log")
if not log_text:
    st.info("Upload a log file or load the demo incident to begin.")
    st.stop()

events = parse_text(log_text)
result = analyze_events(events)
summary = result["summary"]
frame = result["frame"]

cols = st.columns(6)
metrics = [("Events", summary["total_events"]), ("Errors", summary["errors"]), ("Warnings", summary["warnings"]), ("Anomalies", summary["anomalies"]), ("Services", summary["services"]), ("Health", f"{summary['health_score']}/100")]
for col, (label, value) in zip(cols, metrics):
    col.metric(label, value)

overview, causes, explorer, report_tab = st.tabs(["Overview", "Root Cause", "Log Explorer", "Report"])
with overview:
    left, right = st.columns(2)
    with left:
        st.subheader("Severity distribution")
        severity = frame["level"].value_counts().rename_axis("level").reset_index(name="events")
        st.plotly_chart(px.bar(severity, x="level", y="events"), use_container_width=True)
    with right:
        st.subheader("Errors by service")
        service_errors = frame[frame["level"].isin(["ERROR", "CRITICAL", "FATAL"])]["service"].value_counts().head(10).rename_axis("service").reset_index(name="errors")
        if service_errors.empty:
            st.success("No error-level events found.")
        else:
            st.plotly_chart(px.bar(service_errors, x="errors", y="service", orientation="h"), use_container_width=True)
    st.subheader("Error clusters")
    st.dataframe(result["clusters"], use_container_width=True, hide_index=True)

with causes:
    st.subheader("Ranked probable causes")
    for index, item in enumerate(result["root_causes"], 1):
        with st.expander(f"{index}. {item['cause']} — {item['confidence']:.0%} confidence", expanded=index == 1):
            st.write(f"Evidence hits: **{item['evidence_hits']}**")
            st.write("Recommended checks:")
            for step in item["runbook"]:
                st.write(f"- {step}")
    st.warning("Validate evidence before executing production changes. The system provides decision support, not autonomous remediation.")

with explorer:
    services = ["All"] + sorted(frame["service"].astype(str).unique().tolist())
    levels = ["All"] + sorted(frame["level"].astype(str).unique().tolist())
    a, b, c = st.columns([1, 1, 2])
    service = a.selectbox("Service", services)
    level = b.selectbox("Level", levels)
    query = c.text_input("Search messages")
    filtered = frame.copy()
    if service != "All": filtered = filtered[filtered["service"] == service]
    if level != "All": filtered = filtered[filtered["level"] == level]
    if query: filtered = filtered[filtered["message"].str.contains(query, case=False, na=False)]
    columns = ["line_number", "timestamp", "level", "service", "cluster", "anomaly_score", "is_anomaly", "message"]
    st.dataframe(filtered[columns].sort_values("anomaly_score", ascending=False), use_container_width=True, hide_index=True)

with report_tab:
    markdown = build_markdown_report(result, source_name)
    st.markdown(markdown)
    st.download_button("Download incident report", markdown, file_name="incident-report.md", mime="text/markdown")
    st.download_button("Download analyzed events", frame.to_csv(index=False).encode("utf-8"), file_name="analyzed-events.csv", mime="text/csv")
