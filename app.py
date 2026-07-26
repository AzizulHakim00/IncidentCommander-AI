from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from incidentcommander.analyzer import ERROR_LEVELS, analyze_events
from incidentcommander.correlation import (
    blast_radius,
    build_dependency_edges,
    build_timeline,
    correlate_changes,
    correlate_episodes,
)
from incidentcommander.history import list_incidents, save_incident, similar_incidents
from incidentcommander.parser import parse_sources
from incidentcommander.presentation import (
    anomaly_heatmap,
    compare_incident,
    executive_actions,
    health_band,
    root_cause_table,
    service_scorecards,
)
from incidentcommander.redaction import audit_sensitive_text, redact_text
from incidentcommander.report import build_html_report, build_json_report, build_markdown_report

BASE_DIR = Path(__file__).parent
HISTORY_DB = BASE_DIR / "data" / "incidents.db"
PAGE_TITLE = "IncidentCommander AI"

st.set_page_config(
    page_title=f"{PAGE_TITLE} · Operations Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root {
  --ic-bg: #060b18;
  --ic-panel: rgba(13, 23, 46, .74);
  --ic-panel-soft: rgba(17, 31, 60, .55);
  --ic-border: rgba(130, 154, 205, .18);
  --ic-text: #f4f7ff;
  --ic-muted: #91a0bd;
  --ic-cyan: #33d6ff;
  --ic-blue: #5985ff;
  --ic-violet: #9c6cff;
  --ic-green: #42e6a4;
  --ic-amber: #ffca64;
  --ic-red: #ff6b7a;
}
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
  background:
    radial-gradient(circle at 10% -10%, rgba(52, 96, 255, .18), transparent 28%),
    radial-gradient(circle at 95% 0%, rgba(156, 108, 255, .15), transparent 24%),
    linear-gradient(180deg, #071020 0%, #050913 100%) !important;
  color: var(--ic-text);
}
[data-testid="stHeader"] {background: transparent;}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(8, 15, 30, .98), rgba(7, 12, 25, .98));
  border-right: 1px solid var(--ic-border);
}
.block-container {padding-top: 1.15rem; padding-bottom: 3rem; max-width: 1600px;}
#MainMenu, footer {visibility: hidden;}
.ic-shell {
  padding: 1.2rem 1.3rem;
  border: 1px solid var(--ic-border);
  border-radius: 24px;
  background: linear-gradient(145deg, rgba(17, 29, 55, .78), rgba(8, 15, 32, .8));
  box-shadow: 0 18px 60px rgba(0,0,0,.28);
  margin-bottom: 1rem;
}
.ic-kicker {font-size: .74rem; letter-spacing: .16em; text-transform: uppercase; color: var(--ic-cyan); font-weight: 800;}
.ic-title {font-size: clamp(2rem, 4vw, 3.6rem); line-height: 1.02; margin: .35rem 0 .55rem; font-weight: 850;}
.ic-subtitle {color: var(--ic-muted); max-width: 900px; font-size: 1.02rem;}
.ic-badge {display:inline-flex; align-items:center; gap:.4rem; padding:.35rem .7rem; margin:.25rem .35rem .1rem 0; border-radius:999px; border:1px solid var(--ic-border); background:rgba(255,255,255,.04); color:#dce6ff; font-size:.78rem;}
.ic-live-dot {width:8px;height:8px;border-radius:50%;background:var(--ic-green);box-shadow:0 0 12px var(--ic-green);display:inline-block;}
.ic-metric {
  min-height: 122px; padding: 1rem 1.05rem; border-radius: 18px;
  background: linear-gradient(145deg, rgba(17, 30, 58, .9), rgba(9, 17, 35, .92));
  border: 1px solid var(--ic-border); box-shadow: inset 0 1px 0 rgba(255,255,255,.025);
}
.ic-metric-label {color: var(--ic-muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; font-weight:700;}
.ic-metric-value {font-size:1.75rem; font-weight:850; margin:.25rem 0 .15rem;}
.ic-metric-foot {color:#a9b6cf; font-size:.76rem;}
.ic-section-title {font-size:1.02rem; font-weight:800; margin:.2rem 0 .75rem;}
.ic-card {padding: 1rem 1.05rem; border-radius: 18px; background: var(--ic-panel); border:1px solid var(--ic-border); margin-bottom:.65rem;}
.ic-action-priority {font-size:.68rem; font-weight:850; letter-spacing:.08em; color:var(--ic-amber); text-transform:uppercase;}
.ic-action-title {font-size:1rem; font-weight:800; margin:.15rem 0 .25rem;}
.ic-action-detail,.ic-muted {color:var(--ic-muted);}
.ic-action-evidence {font-size:.75rem; color:#c7d3ec; margin-top:.45rem;}
.ic-severity {display:inline-flex;padding:.38rem .72rem;border-radius:999px;font-weight:850;font-size:.76rem;letter-spacing:.05em;}
.ic-sev1 {background:rgba(255,107,122,.16);color:#ff9aa5;border:1px solid rgba(255,107,122,.35)}
.ic-sev2 {background:rgba(255,202,100,.14);color:#ffd98c;border:1px solid rgba(255,202,100,.35)}
.ic-sev3 {background:rgba(89,133,255,.15);color:#9ab7ff;border:1px solid rgba(89,133,255,.35)}
.ic-sev4 {background:rgba(66,230,164,.13);color:#82f0be;border:1px solid rgba(66,230,164,.32)}
[data-testid="stMetric"] {background:var(--ic-panel-soft); border:1px solid var(--ic-border); padding:14px; border-radius:16px;}
[data-testid="stDataFrame"] {border:1px solid var(--ic-border); border-radius:16px; overflow:hidden;}
[data-baseweb="tab-list"] {gap:.45rem;}
[data-baseweb="tab"] {border-radius:10px; padding:.5rem .75rem;}
.stButton > button, .stDownloadButton > button {border-radius:12px; border:1px solid var(--ic-border); font-weight:750;}
.stButton > button[kind="primary"] {background:linear-gradient(90deg,var(--ic-blue),var(--ic-violet)); border:none;}
hr {border-color:var(--ic-border)!important;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

PLOTLY_CONFIG = {"displaylogo": False, "responsive": True}


def style_figure(fig: go.Figure, height: int = 380, *, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=42, b=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dce6ff", family="Inter, Arial, sans-serif"),
        xaxis=dict(gridcolor="rgba(130,154,205,.12)", zeroline=False),
        yaxis=dict(gridcolor="rgba(130,154,205,.12)", zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)") if legend else None,
    )
    return fig


def severity_css(severity: str) -> str:
    return {"SEV-1": "ic-sev1", "SEV-2": "ic-sev2", "SEV-3": "ic-sev3", "SEV-4": "ic-sev4"}.get(severity, "ic-sev3")


def render_metric(label: str, value: str | int | float, foot: str) -> None:
    st.markdown(
        f"<div class='ic-metric'><div class='ic-metric-label'>{label}</div><div class='ic-metric-value'>{value}</div><div class='ic-metric-foot'>{foot}</div></div>",
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <div class='ic-shell'>
          <div class='ic-kicker'>Operations intelligence workspace</div>
          <div class='ic-title'>Turn noisy logs into an incident command plan.</div>
          <div class='ic-subtitle'>Upload application, infrastructure, JSON Lines, or structured CSV logs. IncidentCommander correlates services, ranks evidence, maps blast radius, and creates a human-reviewed response plan—without a paid API.</div>
          <div style='margin-top:.8rem'>
            <span class='ic-badge'><span class='ic-live-dot'></span> Offline-first analysis</span>
            <span class='ic-badge'>Multi-source correlation</span>
            <span class='ic-badge'>Explainable root cause</span>
            <span class='ic-badge'>Incident memory</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    a, b, c = st.columns(3)
    with a:
        st.markdown("<div class='ic-card'><div class='ic-section-title'>1 · Ingest</div><div class='ic-muted'>Upload multiple text, CSV, or JSONL files and optionally add deployment-change data.</div></div>", unsafe_allow_html=True)
    with b:
        st.markdown("<div class='ic-card'><div class='ic-section-title'>2 · Correlate</div><div class='ic-muted'>Group errors into episodes, trace cross-service requests, and calculate blast radius.</div></div>", unsafe_allow_html=True)
    with c:
        st.markdown("<div class='ic-card'><div class='ic-section-title'>3 · Respond</div><div class='ic-muted'>Validate ranked evidence, follow a safe runbook, and export a complete incident report.</div></div>", unsafe_allow_html=True)
    st.info("Use **Load guided demo** in the sidebar to explore the complete experience.")


with st.sidebar:
    st.markdown("### ⚡ IncidentCommander")
    st.caption("Hybrid V3 · Operations intelligence")
    st.divider()
    uploaded = st.file_uploader(
        "Incident log sources",
        type=["log", "txt", "out", "csv", "jsonl"],
        accept_multiple_files=True,
        help="Upload multiple sources from application, gateway, database, or infrastructure services.",
    )
    c1, c2 = st.columns(2)
    demo = c1.button("Load guided demo", use_container_width=True, type="primary")
    clear = c2.button("Clear", use_container_width=True)
    redact = st.toggle("Redact sensitive values", value=True)
    gap_seconds = st.slider("Episode separation", 30, 600, 120, 30, format="%d sec")
    st.divider()
    change_file = st.file_uploader("Deployment/change CSV", type=["csv"], key="changes")
    st.caption("Expected columns: timestamp, service, change")

if clear:
    for key in ["sources", "selected_services", "analyst_notes"]:
        st.session_state.pop(key, None)
    st.rerun()

if demo:
    demo_files = [BASE_DIR / "sample_logs" / "demo_incident.log", BASE_DIR / "sample_logs" / "payments.jsonl"]
    st.session_state["sources"] = [(path.name, path.read_text(encoding="utf-8")) for path in demo_files]
elif uploaded:
    st.session_state["sources"] = [(item.name, item.getvalue().decode("utf-8", errors="replace")) for item in uploaded]

sources = st.session_state.get("sources", [])
if not sources:
    render_empty_state()
    st.stop()

raw_joined = "\n".join(text for _, text in sources)
sensitive_audit = audit_sensitive_text(raw_joined)
processed_sources = [(name, redact_text(text) if redact else text) for name, text in sources]
all_events = parse_sources(processed_sources)
if not all_events:
    st.error("No valid log events could be parsed. Confirm that each source contains a message and, ideally, a timestamp and service name.")
    st.stop()

all_services = sorted({event.service for event in all_events})
with st.sidebar:
    st.divider()
    selected_services = st.multiselect(
        "Service scope",
        options=all_services,
        default=st.session_state.get("selected_services", all_services),
        help="Narrow every chart and insight to selected services.",
    )
    st.session_state["selected_services"] = selected_services
    focus_anomalies = st.toggle("Analyst focus mode", value=False, help="Prioritize anomalous and error-level events in investigation views.")

events = [event for event in all_events if not selected_services or event.service in selected_services]
result = analyze_events(events)
frame = result["frame"]
summary = result["summary"]
timeline = build_timeline(frame)
edges = build_dependency_edges(frame)
blast = blast_radius(frame)
episodes = correlate_episodes(frame, gap_seconds=gap_seconds)
service_cards = service_scorecards(frame, blast)
heatmap = anomaly_heatmap(frame)
root_causes = root_cause_table(result["root_causes"])

change_results = pd.DataFrame()
if change_file:
    try:
        changes = pd.read_csv(change_file)
        if not {"timestamp", "service"}.issubset(changes.columns):
            st.sidebar.error("Change CSV requires timestamp and service columns.")
        else:
            change_results = correlate_changes(frame, changes)
    except Exception as exc:
        st.sidebar.error(f"Could not read change CSV: {exc}")

actions = executive_actions(result, blast, change_results)

with st.sidebar:
    st.divider()
    page = st.radio(
        "Workspace",
        [
            "Command Center",
            "Investigation",
            "Service Topology",
            "Response Center",
            "Log Explorer",
            "Incident Memory",
            "Data Quality",
            "Reports",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(f"Fingerprint · {summary['fingerprint']}")
    st.caption(f"Sources · {len(sources)} · Events · {summary['total_events']}")

st.markdown(
    f"""
    <div class='ic-shell'>
      <div style='display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap'>
        <div>
          <div class='ic-kicker'>Active incident workspace</div>
          <div style='font-size:2rem;font-weight:850;margin:.22rem 0'>Operations Intelligence</div>
          <div class='ic-subtitle'>Evidence-first incident correlation across {summary['services']} observed services and {len(sources)} source files.</div>
        </div>
        <div style='text-align:right'>
          <span class='ic-severity {severity_css(summary['severity'])}'>{summary['severity']}</span>
          <div class='ic-muted' style='font-size:.76rem;margin-top:.45rem'>Health band · {health_band(summary['health_score'])}</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_items = [
    ("Operational health", f"{summary['health_score']}/100", health_band(summary["health_score"])),
    ("Error rate", f"{summary['error_rate']}%", f"{summary['errors']} error-level events"),
    ("Blast radius", summary["impacted_services"], f"of {summary['services']} observed services"),
    ("Detected anomalies", summary["anomalies"], "Isolation Forest outliers"),
    ("Availability proxy", f"{summary['availability_proxy']}%", "Log-derived, not SLO telemetry"),
    ("P95 latency", f"{summary['p95_latency_ms']} ms" if summary["p95_latency_ms"] is not None else "n/a", "Across parsed duration fields"),
]
for column, item in zip(st.columns(6), metric_items):
    with column:
        render_metric(*item)

if page == "Command Center":
    st.markdown("### Command Center")
    left, middle, right = st.columns([1.3, .78, .92])
    with left:
        st.markdown("<div class='ic-section-title'>Incident signal timeline</div>", unsafe_allow_html=True)
        if timeline.empty:
            st.info("No parseable timestamps were found.")
        else:
            long = timeline.melt(
                id_vars="timestamp",
                value_vars=["events", "errors", "warnings", "anomalies"],
                var_name="signal",
                value_name="count",
            )
            fig = px.area(
                long,
                x="timestamp",
                y="count",
                color="signal",
                color_discrete_map={"events": "#5985ff", "errors": "#ff6b7a", "warnings": "#ffca64", "anomalies": "#9c6cff"},
            )
            st.plotly_chart(style_figure(fig, 390), use_container_width=True, config=PLOTLY_CONFIG)
    with middle:
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=summary["health_score"],
                number={"suffix": "/100", "font": {"size": 32}},
                title={"text": "Operational health", "font": {"size": 15}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#33d6ff"},
                    "bgcolor": "rgba(255,255,255,.04)",
                    "bordercolor": "rgba(130,154,205,.18)",
                    "steps": [
                        {"range": [0, 40], "color": "rgba(255,107,122,.25)"},
                        {"range": [40, 65], "color": "rgba(255,202,100,.20)"},
                        {"range": [65, 85], "color": "rgba(89,133,255,.18)"},
                        {"range": [85, 100], "color": "rgba(66,230,164,.18)"},
                    ],
                },
            )
        )
        st.plotly_chart(style_figure(gauge, 390, legend=False), use_container_width=True, config=PLOTLY_CONFIG)
    with right:
        st.markdown("<div class='ic-section-title'>Root-cause confidence</div>", unsafe_allow_html=True)
        if root_causes.empty:
            st.info("No root-cause evidence available.")
        else:
            fig = px.bar(
                root_causes.sort_values("confidence_percent"),
                x="confidence_percent",
                y="cause",
                orientation="h",
                text="confidence_percent",
                color="confidence_percent",
                color_continuous_scale=["#24375e", "#5985ff", "#9c6cff"],
            )
            fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_figure(fig, 390, legend=False), use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("### What needs attention now")
    action_cols = st.columns(len(actions))
    for col, action in zip(action_cols, actions):
        with col:
            st.markdown(
                f"<div class='ic-card' style='min-height:185px'><div class='ic-action-priority'>{action['priority']}</div><div class='ic-action-title'>{action['title']}</div><div class='ic-action-detail'>{action['detail']}</div><div class='ic-action-evidence'>{action['evidence']}</div></div>",
                unsafe_allow_html=True,
            )

    a, b = st.columns([1.25, .75])
    with a:
        st.markdown("### Service health scorecards")
        st.dataframe(
            service_cards,
            use_container_width=True,
            hide_index=True,
            height=365,
            column_config={
                "health_score": st.column_config.ProgressColumn("Health", min_value=0, max_value=100, format="%d"),
                "impact_score": st.column_config.ProgressColumn("Impact", min_value=0, max_value=100, format="%d"),
                "error_rate": st.column_config.NumberColumn("Error rate", format="%.1f%%"),
                "p95_latency_ms": st.column_config.NumberColumn("P95 latency", format="%.1f ms"),
            },
        )
    with b:
        st.markdown("### Blast-radius leaders")
        if blast.empty:
            st.success("No impacted service could be ranked.")
        else:
            fig = px.scatter(
                blast,
                x="impact_score",
                y="errors",
                size="dependent_events",
                color="anomalies",
                hover_name="service",
                text="service",
                size_max=48,
                color_continuous_scale=["#33d6ff", "#9c6cff", "#ff6b7a"],
            )
            fig.update_traces(textposition="top center")
            st.plotly_chart(style_figure(fig, 365, legend=False), use_container_width=True, config=PLOTLY_CONFIG)

elif page == "Investigation":
    st.markdown("### Deep Investigation")
    a, b = st.columns([1.15, .85])
    with a:
        st.markdown("#### Correlated incident episodes")
        if episodes.empty:
            st.info("No incident episodes were created.")
        else:
            st.dataframe(
                episodes,
                use_container_width=True,
                hide_index=True,
                column_config={"confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="%.0%%")},
            )
    with b:
        st.markdown("#### Risk intensity heatmap")
        if heatmap.empty:
            st.info("Timestamp coverage is insufficient for a heatmap.")
        else:
            fig = go.Figure(
                data=go.Heatmap(
                    z=heatmap.values,
                    x=[str(value) for value in heatmap.columns],
                    y=heatmap.index.tolist(),
                    colorscale=[[0, "#101a31"], [.35, "#274977"], [.65, "#7255c8"], [1, "#ff6b7a"]],
                    colorbar={"title": "Risk"},
                )
            )
            st.plotly_chart(style_figure(fig, 370, legend=False), use_container_width=True, config=PLOTLY_CONFIG)

    c, d = st.columns(2)
    with c:
        st.markdown("#### Latency and failure bands")
        latency = frame.dropna(subset=["timestamp", "duration_ms"]).copy()
        if latency.empty:
            st.info("No duration metadata was found.")
        else:
            fig = px.scatter(
                latency,
                x="timestamp",
                y="duration_ms",
                color="service",
                symbol="level",
                hover_data=["status_code", "request_id", "message"],
                size=[10 if value else 6 for value in latency["is_anomaly"]],
            )
            if summary["p95_latency_ms"] is not None:
                fig.add_hline(y=summary["p95_latency_ms"], line_dash="dash", line_color="#ffca64", annotation_text="P95")
            st.plotly_chart(style_figure(fig, 390), use_container_width=True, config=PLOTLY_CONFIG)
    with d:
        st.markdown("#### Highest-priority evidence")
        evidence = frame.copy()
        if focus_anomalies:
            evidence = evidence[evidence["is_anomaly"] | evidence["level"].isin(ERROR_LEVELS)]
        evidence = evidence.sort_values(["is_anomaly", "anomaly_score"], ascending=False).head(12)
        st.dataframe(
            evidence[["timestamp", "level", "service", "dependency", "request_id", "anomaly_score", "message"]],
            use_container_width=True,
            hide_index=True,
            height=390,
        )

    st.markdown("#### Cross-service request traces")
    request_ids = frame.dropna(subset=["request_id"])
    if request_ids.empty:
        st.info("No request IDs were found. Add request_id or trace_id metadata to improve causal investigation.")
    else:
        trace_summary = request_ids.groupby("request_id").agg(
            events=("message", "count"),
            services=("service", lambda values: ", ".join(sorted(set(values)))),
            errors=("level", lambda values: int(pd.Series(values).isin(ERROR_LEVELS).sum())),
            max_latency_ms=("duration_ms", "max"),
        ).reset_index().sort_values(["errors", "events"], ascending=False)
        st.dataframe(trace_summary, use_container_width=True, hide_index=True)

    if not change_results.empty:
        st.markdown("#### Change correlation")
        st.dataframe(
            change_results,
            use_container_width=True,
            hide_index=True,
            column_config={"risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%d")},
        )

elif page == "Service Topology":
    st.markdown("### Service Topology & Impact")
    a, b = st.columns([1.2, .8])
    with a:
        st.markdown("#### Observed dependency flow")
        if edges.empty:
            st.info("Add dependency=service or upstream=service metadata to build the dependency map.")
        else:
            nodes = sorted(set(edges["source"]) | set(edges["target"]))
            index = {node: idx for idx, node in enumerate(nodes)}
            fig = go.Figure(
                go.Sankey(
                    arrangement="snap",
                    node={
                        "label": nodes,
                        "pad": 22,
                        "thickness": 18,
                        "color": ["#5985ff" if node in set(edges["source"]) else "#9c6cff" for node in nodes],
                        "line": {"color": "rgba(255,255,255,.18)", "width": 1},
                    },
                    link={
                        "source": [index[item] for item in edges["source"]],
                        "target": [index[item] for item in edges["target"]],
                        "value": edges["events"].clip(lower=1),
                        "label": [f"{row.errors} errors · {row.events} events" for row in edges.itertuples()],
                        "color": ["rgba(255,107,122,.28)" if row.errors else "rgba(51,214,255,.18)" for row in edges.itertuples()],
                    },
                )
            )
            st.plotly_chart(style_figure(fig, 540, legend=False), use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        st.markdown("#### Impact ranking")
        if blast.empty:
            st.success("No impact signals found.")
        else:
            fig = px.bar(
                blast.sort_values("impact_score"),
                x="impact_score",
                y="service",
                orientation="h",
                color="impact_score",
                color_continuous_scale=["#24375e", "#5985ff", "#ff6b7a"],
                text="impact_score",
                hover_data=["errors", "warnings", "anomalies", "dependent_events"],
            )
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_figure(fig, 540, legend=False), use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("#### Service reliability matrix")
    st.dataframe(
        service_cards,
        use_container_width=True,
        hide_index=True,
        column_config={
            "health_score": st.column_config.ProgressColumn("Health", min_value=0, max_value=100, format="%d"),
            "impact_score": st.column_config.ProgressColumn("Impact", min_value=0, max_value=100, format="%d"),
            "error_rate": st.column_config.NumberColumn("Error rate", format="%.1f%%"),
        },
    )

elif page == "Response Center":
    st.markdown("### Response Center")
    top = result["root_causes"][0] if result["root_causes"] else None
    if top:
        st.markdown(
            f"<div class='ic-shell'><div class='ic-kicker'>Leading hypothesis</div><div style='font-size:1.7rem;font-weight:850;margin:.2rem 0'>{top['cause']}</div><div class='ic-muted'>{top['confidence']:.0%} normalized confidence · {top['evidence_hits']} evidence hits</div></div>",
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.05, .95])
    with left:
        st.markdown("#### Ranked root-cause hypotheses")
        for index, item in enumerate(result["root_causes"], 1):
            with st.expander(f"{index}. {item['cause']} · {item['confidence']:.0%}", expanded=index == 1):
                if item.get("evidence"):
                    st.markdown("**Evidence samples**")
                    for evidence in item["evidence"]:
                        st.code(evidence, language=None)
                st.markdown("**Human-reviewed runbook**")
                for step_index, step in enumerate(item["runbook"]):
                    st.checkbox(step, key=f"runbook-{summary['fingerprint']}-{index}-{step_index}")
    with right:
        st.markdown("#### Investigation notes")
        analyst_notes = st.text_area(
            "Notes",
            value=st.session_state.get("analyst_notes", ""),
            height=180,
            placeholder="Document decisions, checks, rollback conditions, and confirmed evidence.",
            label_visibility="collapsed",
        )
        st.session_state["analyst_notes"] = analyst_notes
        st.markdown("#### Action queue")
        for item in actions:
            st.markdown(
                f"<div class='ic-card'><div class='ic-action-priority'>{item['priority']}</div><div class='ic-action-title'>{item['title']}</div><div class='ic-action-detail'>{item['detail']}</div></div>",
                unsafe_allow_html=True,
            )
        if st.button("Save incident to memory", type="primary", use_container_width=True):
            try:
                incident_id = save_incident(HISTORY_DB, result, ", ".join(name for name, _ in sources), analyst_notes)
                st.success(f"Incident #{incident_id} saved to local memory.")
            except Exception as exc:
                st.error(f"Could not save incident: {exc}")

    st.warning("IncidentCommander provides decision support only. Validate permissions, telemetry, rollback safety, and business impact before production changes.")

elif page == "Log Explorer":
    st.markdown("### Log Explorer")
    services = ["All"] + sorted(frame["service"].astype(str).unique().tolist())
    levels = ["All"] + sorted(frame["level"].astype(str).unique().tolist())
    source_values = ["All"] + sorted(frame["source"].astype(str).unique().tolist())
    a, b, c, d = st.columns([1, 1, 1, 2])
    service = a.selectbox("Service", services)
    level = b.selectbox("Level", levels)
    selected_source = c.selectbox("Source", source_values)
    query = d.text_input("Search message, request ID, trace ID, or dependency")
    anomaly_only = st.toggle("Anomalies only", value=focus_anomalies)

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
        query_columns = ["message", "request_id", "trace_id", "dependency", "host"]
        mask = pd.Series(False, index=filtered.index)
        for column in query_columns:
            if column in filtered:
                mask |= filtered[column].fillna("").astype(str).str.contains(query, case=False, regex=False)
        filtered = filtered[mask]

    st.caption(f"Showing {len(filtered):,} of {len(frame):,} events")
    columns = ["timestamp", "level", "service", "dependency", "request_id", "trace_id", "status_code", "duration_ms", "cluster", "anomaly_score", "is_anomaly", "message"]
    st.dataframe(filtered[columns].sort_values("anomaly_score", ascending=False), use_container_width=True, hide_index=True, height=600)

elif page == "Incident Memory":
    st.markdown("### Incident Memory & Comparison")
    try:
        history = list_incidents(HISTORY_DB)
        similar = similar_incidents(HISTORY_DB, result)
    except Exception as exc:
        st.warning(f"Incident memory is unavailable in this environment: {exc}")
        history = pd.DataFrame()
        similar = pd.DataFrame()

    a, b = st.columns([.9, 1.1])
    with a:
        st.markdown("#### Most similar incidents")
        if similar.empty:
            st.info("Save the current incident to create comparison history.")
        else:
            st.dataframe(similar[["id", "created_at", "severity", "root_cause", "services", "notes", "similarity"]], use_container_width=True, hide_index=True)
    with b:
        st.markdown("#### Compare current vs historical")
        if history.empty:
            st.info("No historical incidents are stored yet.")
        else:
            labels = {int(row.id): f"#{row.id} · {row.severity} · {row.root_cause}" for row in history.itertuples()}
            selected_id = st.selectbox("Historical incident", options=list(labels), format_func=labels.get)
            row = history[history["id"] == selected_id].iloc[0]
            current_summary = {**summary, "top_root_cause": result["root_causes"][0]["cause"] if result["root_causes"] else "Unknown"}
            comparison = compare_incident(current_summary, row)
            st.dataframe(comparison, use_container_width=True, hide_index=True)
            if row.get("notes"):
                st.info(f"Historical notes: {row['notes']}")

    st.markdown("#### Full incident archive")
    st.dataframe(history, use_container_width=True, hide_index=True, height=390)

elif page == "Data Quality":
    st.markdown("### Model & Observability Quality")
    quality = result["quality"]
    a, b = st.columns([.8, 1.2])
    with a:
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=quality["score"],
                number={"suffix": "/100"},
                title={"text": "Observability score"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#42e6a4"},
                    "steps": [
                        {"range": [0, 40], "color": "rgba(255,107,122,.2)"},
                        {"range": [40, 70], "color": "rgba(255,202,100,.18)"},
                        {"range": [70, 100], "color": "rgba(66,230,164,.16)"},
                    ],
                },
            )
        )
        st.plotly_chart(style_figure(gauge, 390, legend=False), use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        dimensions = [key for key in quality if key != "score"]
        radar_values = [quality[key] for key in dimensions]
        fig = go.Figure(
            go.Scatterpolar(
                r=radar_values + [radar_values[0]],
                theta=[key.replace("_", " ").title() for key in dimensions] + [dimensions[0].replace("_", " ").title()],
                fill="toself",
                line={"color": "#33d6ff"},
                fillcolor="rgba(51,214,255,.16)",
            )
        )
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor="rgba(130,154,205,.15)"), bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(style_figure(fig, 390, legend=False), use_container_width=True, config=PLOTLY_CONFIG)

    c, d = st.columns(2)
    with c:
        st.markdown("#### Sensitive-data audit")
        audit_frame = pd.DataFrame([{"type": key, "detections": value} for key, value in sensitive_audit.items()])
        st.dataframe(audit_frame, use_container_width=True, hide_index=True)
        st.caption("Redaction is applied before parsing and report generation when enabled.")
    with d:
        st.markdown("#### Cluster diagnostics")
        st.dataframe(result["clusters"], use_container_width=True, hide_index=True)

    st.markdown("#### Recommended telemetry improvements")
    recommendations = []
    if quality["timestamps"] < 90:
        recommendations.append("Standardize UTC timestamps on every event.")
    if quality["service_names"] < 90:
        recommendations.append("Include a stable service or component name.")
    if quality["request_or_trace_ids"] < 60:
        recommendations.append("Propagate request and trace IDs across service boundaries.")
    if quality["latency_metadata"] < 40:
        recommendations.append("Add duration_ms and status_code to request logs.")
    if quality["host_metadata"] < 40:
        recommendations.append("Include host, node, or availability-zone metadata for infrastructure correlation.")
    if not recommendations:
        recommendations.append("Metadata coverage is strong. Add SLO telemetry and deployment markers next.")
    for recommendation in recommendations:
        st.markdown(f"- {recommendation}")

elif page == "Reports":
    st.markdown("### Report Center")
    source_name = ", ".join(name for name, _ in sources)
    markdown = build_markdown_report(result, source_name, episodes=episodes, blast=blast, changes=change_results)
    html_report = build_html_report(markdown)
    json_report = build_json_report(result, source_name)
    executive_payload = {
        "fingerprint": summary["fingerprint"],
        "severity": summary["severity"],
        "health_score": summary["health_score"],
        "root_cause": result["root_causes"][0]["cause"] if result["root_causes"] else "Unknown",
        "actions": actions,
    }

    st.markdown("#### Executive snapshot")
    a, b, c = st.columns(3)
    a.metric("Severity", summary["severity"])
    b.metric("Health", summary["health_score"])
    c.metric("Fingerprint", summary["fingerprint"])
    st.markdown(f"**Leading hypothesis:** {executive_payload['root_cause']}")
    for action in actions:
        st.markdown(f"- **{action['priority']} · {action['title']}** — {action['detail']}")

    st.markdown("#### Download investigation package")
    a, b, c, d, e = st.columns(5)
    a.download_button("Markdown", markdown, file_name=f"incident-{summary['fingerprint']}.md", mime="text/markdown", use_container_width=True)
    b.download_button("HTML", html_report, file_name=f"incident-{summary['fingerprint']}.html", mime="text/html", use_container_width=True)
    c.download_button("JSON", json_report, file_name=f"incident-{summary['fingerprint']}.json", mime="application/json", use_container_width=True)
    d.download_button("Events CSV", frame.to_csv(index=False).encode("utf-8"), file_name=f"events-{summary['fingerprint']}.csv", mime="text/csv", use_container_width=True)
    e.download_button("Executive JSON", json.dumps(executive_payload, indent=2), file_name=f"executive-{summary['fingerprint']}.json", mime="application/json", use_container_width=True)

    with st.expander("Preview full Markdown report"):
        st.markdown(markdown)
