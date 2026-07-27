from __future__ import annotations

import base64
import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from incidentcommander.analyzer import analyze_events
from incidentcommander.correlation import blast_radius, build_dependency_edges, build_timeline, correlate_episodes
from incidentcommander.demo_factory import SCENARIOS, architecture_svg, build_scenario, service_map_svg, timeline_svg
from incidentcommander.parser import parse_sources
from incidentcommander.presentation import health_band, service_scorecards


BASE_DIR = Path(__file__).resolve().parents[1]
ASSET_DIR = BASE_DIR / "assets"

st.set_page_config(page_title="Live Incident Studio · IncidentCommander AI", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

STUDIO_CSS = """
<style>
:root{--bg:#030711;--panel:rgba(8,18,38,.78);--border:rgba(126,160,231,.22);--text:#f6f9ff;--muted:#98a8c8;--cyan:#39dcff;--blue:#5a87ff;--violet:#a06dff;--pink:#ff70d6;--green:#45e8aa;--amber:#ffd166;--red:#ff6476}
@keyframes aurora{0%,100%{transform:translate3d(-3%,-2%,0) scale(1)}50%{transform:translate3d(4%,3%,0) scale(1.08)}}@keyframes scan{0%{transform:translateY(-150%);opacity:0}15%{opacity:.55}80%{opacity:.2}100%{transform:translateY(650%);opacity:0}}@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(69,232,170,.42)}70%{box-shadow:0 0 0 13px rgba(69,232,170,0)}100%{box-shadow:0 0 0 0 rgba(69,232,170,0)}}@keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}@keyframes spin{to{transform:rotate(360deg)}}
html,body,[data-testid="stApp"],[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#050914,#02050c)!important;color:var(--text)}[data-testid="stAppViewContainer"]::before{content:"";position:fixed;inset:-20%;z-index:0;pointer-events:none;background:radial-gradient(circle at 15% 12%,rgba(57,220,255,.2),transparent 25%),radial-gradient(circle at 86% 9%,rgba(160,109,255,.24),transparent 24%),radial-gradient(circle at 60% 85%,rgba(69,232,170,.14),transparent 28%);filter:blur(38px);animation:aurora 14s ease-in-out infinite}[data-testid="stHeader"]{background:transparent}[data-testid="stSidebar"]{background:linear-gradient(180deg,rgba(5,12,26,.98),rgba(3,8,18,.98));border-right:1px solid var(--border)}.block-container{position:relative;z-index:1;max-width:1680px;padding-top:.8rem;padding-bottom:3rem}#MainMenu,footer{visibility:hidden}
.hero{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:1.4rem;align-items:center;padding:1.7rem 1.8rem;border-radius:30px;border:1px solid transparent;background:linear-gradient(145deg,rgba(11,27,56,.94),rgba(5,13,29,.94)) padding-box,linear-gradient(115deg,rgba(57,220,255,.58),rgba(90,135,255,.28),rgba(160,109,255,.55),rgba(255,112,214,.24)) border-box;box-shadow:0 32px 95px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.06);margin-bottom:1rem}.hero::after{content:"";position:absolute;left:0;right:0;top:-25%;height:20%;background:linear-gradient(180deg,transparent,rgba(57,220,255,.14),transparent);animation:scan 6s ease-in-out infinite}.eyebrow{font-size:.73rem;letter-spacing:.18em;text-transform:uppercase;font-weight:900;color:#82eaff}.title{font-size:clamp(2.3rem,5vw,4.8rem);line-height:.98;letter-spacing:-.055em;margin:.4rem 0 .7rem;font-weight:950;background:linear-gradient(100deg,#fff 10%,#bcecff 42%,#c8b7ff 75%,#ffb7e9);-webkit-background-clip:text;background-clip:text;color:transparent}.sub{color:#a9b8d4;font-size:1.02rem;line-height:1.72;max-width:900px}.chips{display:flex;flex-wrap:wrap;gap:.48rem;margin-top:1rem}.chip{display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .72rem;border-radius:999px;border:1px solid rgba(126,158,226,.2);background:rgba(255,255,255,.035);font-size:.75rem;color:#dce7ff}.live{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;animation:pulse 2s ease-out infinite}
.orbit{position:relative;width:245px;height:245px;margin:auto;display:grid;place-items:center}.ring{position:absolute;inset:12px;border-radius:50%;border:1px solid rgba(57,220,255,.32);box-shadow:inset 0 0 50px rgba(57,220,255,.07);animation:spin 13s linear infinite}.ring::before{content:"";position:absolute;width:12px;height:12px;border-radius:50%;top:-6px;left:50%;background:var(--cyan);box-shadow:0 0 22px var(--cyan)}.ring.two{inset:43px;border-color:rgba(160,109,255,.36);animation-direction:reverse;animation-duration:9s}.ring.two::before{background:var(--violet);box-shadow:0 0 20px var(--violet)}.core{width:112px;height:112px;border-radius:34px;display:grid;place-items:center;font-size:2rem;background:linear-gradient(145deg,rgba(57,220,255,.22),rgba(160,109,255,.3));border:1px solid rgba(119,215,255,.36);box-shadow:0 0 70px rgba(79,148,255,.28)}
.card{padding:1rem 1.05rem;border-radius:20px;border:1px solid var(--border);background:linear-gradient(145deg,rgba(12,27,55,.86),rgba(6,15,32,.88));box-shadow:0 18px 55px rgba(0,0,0,.24);height:100%}.k-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:850}.k-value{font-size:1.75rem;font-weight:950;margin:.25rem 0}.k-foot{font-size:.75rem;color:#aab8d4}.ticker{overflow:hidden;white-space:nowrap;border:1px solid rgba(125,157,225,.16);border-radius:15px;background:rgba(6,14,31,.74);margin:.2rem 0 1rem}.ticker-track{display:inline-flex;min-width:200%;padding:.55rem 0;animation:ticker 26s linear infinite}.ticker-item{display:inline-flex;gap:.5rem;margin-right:2.5rem;font-size:.72rem;color:#aebcd7}.ticker-item strong{color:#eef6ff}.scenario{padding:1rem;border-radius:18px;border:1px solid var(--border);background:rgba(8,18,38,.72);transition:.25s ease}.scenario:hover{transform:translateY(-4px);border-color:rgba(57,220,255,.4);box-shadow:0 20px 50px rgba(0,0,0,.25)}.icon{font-size:1.7rem}.name{font-size:1rem;font-weight:900;margin:.3rem 0}.story{font-size:.78rem;color:var(--muted);line-height:1.55}.step{padding:.8rem .9rem;border-left:3px solid var(--blue);background:rgba(10,22,46,.62);border-radius:0 14px 14px 0;margin-bottom:.55rem}.step strong{color:#f2f7ff}.step span{display:block;color:var(--muted);font-size:.78rem;margin-top:.2rem}
[data-testid="stDataFrame"],[data-testid="stImage"],[data-testid="stVideo"]{border-radius:20px;overflow:hidden}.stButton>button,.stDownloadButton>button{border-radius:13px;font-weight:800;border:1px solid rgba(126,158,226,.24)}.stButton>button[kind="primary"]{background:linear-gradient(100deg,var(--blue),var(--violet),var(--pink));border:none;box-shadow:0 14px 38px rgba(90,135,255,.24)}
@media(max-width:900px){.hero{grid-template-columns:1fr}.orbit{width:190px;height:190px}.title{font-size:2.4rem}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
</style>
"""
st.markdown(STUDIO_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🎬 Live Incident Studio")
    st.caption("V5 · Interactive showcase")
    st.divider()
    selected = st.selectbox("Choose a scenario", list(SCENARIOS))
    replay = st.toggle("Autoplay incident replay", value=True)
    st.divider()
    st.caption("Each scenario generates 200+ deterministic multi-service events and is safe for public demonstrations.")

scenario = SCENARIOS[selected]
sources = build_scenario(selected)
events = parse_sources(sources)
result = analyze_events(events)
frame = result["frame"]
summary = result["summary"]
timeline = build_timeline(frame)
blast = blast_radius(frame)
edges = build_dependency_edges(frame)
episodes = correlate_episodes(frame)
cards = service_scorecards(frame, blast)

st.markdown(f"""<div class="hero"><div><div class="eyebrow"><span class="live"></span> Repository-contained interactive demo</div><div class="title">Live Incident Studio</div><div class="sub">{html.escape(scenario['story'])} Watch the incident evolve, inspect the visual evidence, then launch the complete dataset inside the command center.</div><div class="chips"><span class="chip">{scenario['icon']} {html.escape(selected)}</span><span class="chip">{scenario['severity']} scenario</span><span class="chip">{len(frame):,} events</span><span class="chip">{summary['services']} services</span><span class="chip">No external API</span></div></div><div class="orbit"><div class="ring"></div><div class="ring two"></div><div class="core">{scenario['icon']}</div></div></div>""", unsafe_allow_html=True)

ticker_entries = [
    f"<span class='ticker-item'><strong>{summary['severity']}</strong> active scenario</span>",
    f"<span class='ticker-item'><strong>{summary['errors']}</strong> error-level events</span>",
    f"<span class='ticker-item'><strong>{summary['anomalies']}</strong> anomalies</span>",
    f"<span class='ticker-item'><strong>{summary['top_error_service']}</strong> top error service</span>",
    f"<span class='ticker-item'><strong>{summary['p95_latency_ms'] or 'n/a'} ms</strong> P95 latency</span>",
]
ticker = "".join(ticker_entries)
st.markdown(f"<div class='ticker'><div class='ticker-track'>{ticker}{ticker}</div></div>", unsafe_allow_html=True)

kpis = [
    ("Operational health", f"{summary['health_score']}/100", health_band(summary["health_score"])),
    ("Error rate", f"{summary['error_rate']}%", f"{summary['errors']} errors"),
    ("Blast radius", summary["impacted_services"], f"{summary['services']} observed services"),
    ("Anomalies", summary["anomalies"], "Isolation Forest"),
    ("Availability proxy", f"{summary['availability_proxy']}%", "log-derived"),
    ("P95 latency", f"{summary['p95_latency_ms']} ms" if summary["p95_latency_ms"] is not None else "n/a", "parsed durations"),
]
for col, item in zip(st.columns(6), kpis):
    with col:
        st.markdown(f"<div class='card'><div class='k-label'>{item[0]}</div><div class='k-value'>{item[1]}</div><div class='k-foot'>{item[2]}</div></div>", unsafe_allow_html=True)

st.markdown("### 🎥 Incident replay & system picture")
left, right = st.columns([1.15, .85])
with left:
    video_path = ASSET_DIR / "incident_replay.mp4.b64"
    if video_path.exists():
        video_bytes = base64.b64decode(video_path.read_text(encoding="ascii"))
        st.video(video_bytes, format="video/mp4", autoplay=replay, loop=True, muted=True)
    else:
        st.info("Replay asset is unavailable.")
with right:
    architecture_uri = "data:image/svg+xml;base64," + base64.b64encode(architecture_svg().encode()).decode()
    st.image(architecture_uri, use_container_width=True)
    st.caption("Repository-contained architecture artwork—no third-party image dependency.")

launch_col, download_col = st.columns([.7, .3])
with launch_col:
    if st.button("🚀 Launch this scenario in Command Center", type="primary", use_container_width=True):
        st.session_state["sources"] = sources
        st.session_state["selected_services"] = sorted(frame["service"].astype(str).unique().tolist())
        st.switch_page("app.py")
with download_col:
    package_text = "\n\n".join(f"### {name}\n{text}" for name, text in sources)
    st.download_button("Download scenario data", package_text, file_name=f"{selected.lower().replace(' ', '-')}-scenario.txt", use_container_width=True)

st.markdown("### 🧩 Scenario gallery")
scenario_cols = st.columns(len(SCENARIOS))
for col, (name, item) in zip(scenario_cols, SCENARIOS.items()):
    with col:
        st.markdown(f"<div class='scenario'><div class='icon'>{item['icon']}</div><div class='name'>{html.escape(name)}</div><div class='story'>{html.escape(item['story'])}</div><div style='margin-top:.55rem;color:{item['accent']};font-size:.72rem;font-weight:900'>{item['severity']} · {item['format'].upper()}</div></div>", unsafe_allow_html=True)

st.markdown("### 📡 Live visual intelligence")
a, b = st.columns([1.25, .75])
with a:
    long = timeline.melt(id_vars="timestamp", value_vars=["events", "errors", "warnings", "anomalies"], var_name="signal", value_name="count")
    fig = px.area(long, x="timestamp", y="count", color="signal", color_discrete_map={"events":"#5a87ff","errors":"#ff6476","warnings":"#ffd166","anomalies":"#a06dff"})
    fig.update_layout(height=390, margin=dict(l=12,r=12,t=38,b=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#dbe7ff", legend_title_text="")
    fig.update_xaxes(gridcolor="rgba(130,154,205,.1)"); fig.update_yaxes(gridcolor="rgba(130,154,205,.1)")
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo":False})
with b:
    severity_counts = frame["level"].value_counts().reset_index()
    severity_counts.columns = ["level","count"]
    fig = px.pie(severity_counts, names="level", values="count", hole=.68, color="level", color_discrete_map={"INFO":"#5a87ff","WARN":"#ffd166","ERROR":"#ff6476","CRITICAL":"#ff70d6","FATAL":"#a06dff"})
    fig.update_layout(height=390, margin=dict(l=12,r=12,t=38,b=12), paper_bgcolor="rgba(0,0,0,0)", font_color="#dbe7ff", legend_title_text="")
    fig.update_traces(textposition="inside", textinfo="percent")
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo":False})

c, d = st.columns(2)
with c:
    st.markdown("#### Service health wall")
    display = cards[["service","health_score","impact_score","error_rate","p95_latency_ms"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True, height=360, column_config={"health_score":st.column_config.ProgressColumn("Health",min_value=0,max_value=100),"impact_score":st.column_config.ProgressColumn("Impact",min_value=0,max_value=100),"error_rate":st.column_config.NumberColumn("Error rate",format="%.1f%%"),"p95_latency_ms":st.column_config.NumberColumn("P95",format="%.1f ms")})
with d:
    st.markdown("#### Incident story")
    top_cause = result["root_causes"][0]["cause"] if result["root_causes"] else "Unknown"
    steps = [("1 · Baseline","Services begin in a healthy operating state."),("2 · First anomaly",f"Anomaly signals appear around {summary['top_error_service']}"),("3 · Cascade",f"{summary['impacted_services']} services enter the blast radius."),("4 · AI hypothesis",top_cause),("5 · Response","Launch the scenario in Command Center to review evidence and runbooks.")]
    for title, detail in steps:
        st.markdown(f"<div class='step'><strong>{html.escape(title)}</strong><span>{html.escape(str(detail))}</span></div>", unsafe_allow_html=True)

st.markdown("### 🖼️ Visual story gallery")
gallery = [(architecture_svg(), "AI architecture"), (service_map_svg(), "Service blast radius"), (timeline_svg(), "Incident timeline")]
gcols = st.columns(3)
for col, (svg, caption) in zip(gcols, gallery):
    with col:
        uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        st.image(uri, use_container_width=True)
        st.caption(caption)

st.markdown("### 🔬 Explore the scenario data")
tab1, tab2, tab3 = st.tabs(["Highest-risk events","Incident episodes","Dependency edges"])
with tab1:
    risky = frame.sort_values(["is_anomaly","anomaly_score"], ascending=False).head(100)
    st.dataframe(risky[["timestamp","level","service","dependency","status_code","duration_ms","anomaly_score","message"]], use_container_width=True, hide_index=True, height=480)
with tab2:
    st.dataframe(episodes, use_container_width=True, hide_index=True, height=420)
with tab3:
    st.dataframe(edges, use_container_width=True, hide_index=True, height=420)

st.caption("All scenarios, pictures, and replay media are bundled in the repository so the public Render deployment remains reliable.")
