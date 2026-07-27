from __future__ import annotations

import html
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
VERSION = "Cinematic V4"

st.set_page_config(
    page_title=f"{PAGE_TITLE} · Incident Operations",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CINEMATIC_CSS = """
<style>
:root {
  --ic-bg: #030711;
  --ic-bg-soft: #071021;
  --ic-panel: rgba(8, 18, 38, .76);
  --ic-panel-strong: rgba(10, 22, 46, .93);
  --ic-border: rgba(132, 167, 255, .19);
  --ic-border-hot: rgba(51, 214, 255, .44);
  --ic-text: #f7f9ff;
  --ic-muted: #9aa9c7;
  --ic-cyan: #39dcff;
  --ic-blue: #5a87ff;
  --ic-violet: #a06dff;
  --ic-pink: #ff70d6;
  --ic-green: #45e8aa;
  --ic-amber: #ffd166;
  --ic-red: #ff6476;
  --ic-shadow: 0 30px 90px rgba(0,0,0,.42);
}

@keyframes auroraShift {
  0% {transform: translate3d(-4%, -2%, 0) scale(1); opacity:.72;}
  50% {transform: translate3d(5%, 3%, 0) scale(1.08); opacity:1;}
  100% {transform: translate3d(-4%, -2%, 0) scale(1); opacity:.72;}
}
@keyframes gridDrift {
  from {background-position: 0 0, 0 0;}
  to {background-position: 48px 48px, -48px 48px;}
}
@keyframes pulseRing {
  0% {box-shadow: 0 0 0 0 rgba(69,232,170,.42), 0 0 18px rgba(69,232,170,.55);}
  70% {box-shadow: 0 0 0 12px rgba(69,232,170,0), 0 0 24px rgba(69,232,170,.3);}
  100% {box-shadow: 0 0 0 0 rgba(69,232,170,0), 0 0 18px rgba(69,232,170,.55);}
}
@keyframes cardFloat {
  0%, 100% {transform: translateY(0);}
  50% {transform: translateY(-5px);}
}
@keyframes orbit {
  from {transform: rotate(0deg);}
  to {transform: rotate(360deg);}
}
@keyframes orbitReverse {
  from {transform: rotate(360deg);}
  to {transform: rotate(0deg);}
}
@keyframes scan {
  0% {transform: translateY(-120%); opacity:0;}
  18% {opacity:.6;}
  82% {opacity:.32;}
  100% {transform: translateY(620%); opacity:0;}
}
@keyframes shimmer {
  from {transform: translateX(-140%) skewX(-18deg);}
  to {transform: translateX(420%) skewX(-18deg);}
}
@keyframes riseIn {
  from {opacity:0; transform:translateY(16px);}
  to {opacity:1; transform:translateY(0);}
}
@keyframes tickerMove {
  from {transform:translateX(0);}
  to {transform:translateX(-50%);}
}

html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
  background: linear-gradient(180deg, #050914 0%, #02050c 100%) !important;
  color: var(--ic-text);
}
[data-testid="stAppViewContainer"] {position:relative;overflow:hidden;}
[data-testid="stAppViewContainer"]::before {
  content:"";position:fixed;inset:-18% -12%;pointer-events:none;z-index:0;
  background:radial-gradient(circle at 18% 18%, rgba(45,132,255,.30), transparent 25%),radial-gradient(circle at 82% 14%, rgba(160,109,255,.26), transparent 24%),radial-gradient(circle at 58% 80%, rgba(32,218,199,.18), transparent 28%),radial-gradient(circle at 20% 82%, rgba(255,70,160,.10), transparent 22%);
  filter:blur(34px);animation:auroraShift 13s ease-in-out infinite;
}
[data-testid="stAppViewContainer"]::after {
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.18;
  background-image:linear-gradient(rgba(95,130,200,.10) 1px, transparent 1px),linear-gradient(90deg, rgba(95,130,200,.10) 1px, transparent 1px);
  background-size:48px 48px;mask-image:linear-gradient(to bottom, rgba(0,0,0,.75), transparent 82%);animation:gridDrift 18s linear infinite;
}
[data-testid="stHeader"] {background:transparent;z-index:5;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,rgba(5,12,26,.98),rgba(3,8,18,.98));border-right:1px solid rgba(120,151,220,.17);box-shadow:18px 0 55px rgba(0,0,0,.22);}
[data-testid="stSidebar"] > div:first-child {padding-top:.8rem;}
.block-container {position:relative;z-index:1;padding-top:.75rem;padding-bottom:3rem;max-width:1680px;animation:riseIn .55s ease both;}
#MainMenu, footer {visibility:hidden;}
.ic-brand {display:flex;align-items:center;gap:.8rem;padding:.72rem .75rem;margin:.2rem 0 .7rem;border:1px solid rgba(123,153,220,.17);border-radius:18px;background:linear-gradient(145deg,rgba(18,35,68,.82),rgba(7,16,34,.92));box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 14px 42px rgba(0,0,0,.25);}
.ic-brand-mark {width:42px;height:42px;border-radius:14px;display:grid;place-items:center;font-size:1.15rem;font-weight:900;background:linear-gradient(145deg,rgba(57,220,255,.24),rgba(160,109,255,.30));border:1px solid rgba(86,214,255,.34);box-shadow:0 0 28px rgba(57,220,255,.18);}
.ic-brand-title {font-size:.98rem;font-weight:900;letter-spacing:-.02em;}.ic-brand-sub{color:var(--ic-muted);font-size:.68rem;margin-top:.08rem;}
.ic-live-row{display:flex;align-items:center;gap:.48rem;color:#a8b6d0;font-size:.72rem;}.ic-live-dot{width:8px;height:8px;border-radius:50%;display:inline-block;background:var(--ic-green);animation:pulseRing 2s ease-out infinite;}
.ic-hero {position:relative;overflow:hidden;min-height:245px;display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:1.5rem;align-items:center;padding:1.7rem 1.8rem;margin:.25rem 0 1rem;border:1px solid transparent;border-radius:30px;background:linear-gradient(145deg,rgba(12,27,55,.92),rgba(5,13,29,.93)) padding-box,linear-gradient(115deg,rgba(57,220,255,.62),rgba(90,135,255,.28),rgba(160,109,255,.58),rgba(255,112,214,.28)) border-box;box-shadow:var(--ic-shadow),inset 0 1px 0 rgba(255,255,255,.055);}
.ic-hero::before{content:"";position:absolute;inset:-90% 46% -90% -25%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.055),transparent);animation:shimmer 6.8s linear infinite;}.ic-hero::after{content:"";position:absolute;left:0;right:0;top:-20%;height:22%;background:linear-gradient(180deg,transparent,rgba(57,220,255,.15),transparent);animation:scan 5.8s ease-in-out infinite;}
.ic-hero-copy{position:relative;z-index:2;}.ic-eyebrow{display:inline-flex;align-items:center;gap:.5rem;font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;font-weight:900;color:#83e9ff;}.ic-hero-title{font-size:clamp(2.2rem,4.6vw,4.45rem);line-height:.98;letter-spacing:-.055em;margin:.45rem 0 .75rem;font-weight:950;background:linear-gradient(100deg,#fff 8%,#bcecff 42%,#c8b7ff 76%,#ffb6e9);-webkit-background-clip:text;background-clip:text;color:transparent;}.ic-hero-sub{color:#a9b8d4;max-width:910px;font-size:1.02rem;line-height:1.72;}
.ic-chip-row{display:flex;flex-wrap:wrap;gap:.48rem;margin-top:1rem;}.ic-chip{display:inline-flex;align-items:center;gap:.45rem;padding:.42rem .74rem;border-radius:999px;border:1px solid rgba(126,158,226,.20);background:rgba(255,255,255,.035);color:#dce7ff;font-size:.75rem;backdrop-filter:blur(12px);}
.ic-orbit{position:relative;width:220px;height:220px;margin:auto;display:grid;place-items:center;z-index:2;}.ic-orbit-ring,.ic-orbit-ring-two{position:absolute;border-radius:50%;border:1px solid rgba(77,214,255,.30);box-shadow:inset 0 0 38px rgba(57,220,255,.07),0 0 34px rgba(90,135,255,.08);}.ic-orbit-ring{inset:12px;animation:orbit 12s linear infinite;}.ic-orbit-ring-two{inset:36px;border-color:rgba(160,109,255,.34);animation:orbitReverse 8s linear infinite;}.ic-orbit-ring::before,.ic-orbit-ring-two::before{content:"";position:absolute;width:10px;height:10px;border-radius:50%;top:-5px;left:50%;background:var(--ic-cyan);box-shadow:0 0 20px var(--ic-cyan);}.ic-orbit-ring-two::before{background:var(--ic-violet);box-shadow:0 0 18px var(--ic-violet);}.ic-core{width:96px;height:96px;border-radius:30px;display:grid;place-items:center;font-size:1.55rem;font-weight:950;letter-spacing:-.05em;background:linear-gradient(145deg,rgba(57,220,255,.22),rgba(160,109,255,.30));border:1px solid rgba(119,215,255,.35);box-shadow:0 0 60px rgba(79,148,255,.24),inset 0 1px 0 rgba(255,255,255,.12);animation:cardFloat 4s ease-in-out infinite;}.ic-scan-lines{position:absolute;inset:48px;border-radius:50%;background:repeating-radial-gradient(circle,rgba(90,135,255,.08) 0 1px,transparent 1px 13px);opacity:.55;}
.ic-active-hero{position:relative;overflow:hidden;display:flex;justify-content:space-between;gap:1.4rem;align-items:center;flex-wrap:wrap;padding:1.2rem 1.35rem;margin:.2rem 0 .9rem;border-radius:22px;border:1px solid rgba(126,157,224,.20);background:linear-gradient(135deg,rgba(11,25,52,.88),rgba(8,17,37,.88));box-shadow:0 18px 54px rgba(0,0,0,.25),inset 0 1px 0 rgba(255,255,255,.04);}.ic-active-hero::after{content:"";position:absolute;width:320px;height:320px;border-radius:50%;right:-150px;top:-165px;background:radial-gradient(circle,rgba(57,220,255,.20),transparent 68%);}.ic-active-title{font-size:1.65rem;font-weight:950;letter-spacing:-.035em;margin:.15rem 0;}.ic-muted{color:var(--ic-muted);}
.ic-severity{position:relative;z-index:2;display:inline-flex;align-items:center;gap:.45rem;padding:.48rem .82rem;border-radius:999px;font-size:.76rem;font-weight:950;letter-spacing:.07em;}.ic-severity::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 12px currentColor;}.ic-sev1{color:#ff9eaa;border:1px solid rgba(255,100,118,.42);background:rgba(255,100,118,.14);animation:pulseRing 2.4s ease-out infinite;}.ic-sev2{color:#ffda86;border:1px solid rgba(255,209,102,.40);background:rgba(255,209,102,.12);}.ic-sev3{color:#a8c0ff;border:1px solid rgba(90,135,255,.40);background:rgba(90,135,255,.13);}.ic-sev4{color:#83f1c0;border:1px solid rgba(69,232,170,.37);background:rgba(69,232,170,.12);}
.ic-ticker{overflow:hidden;white-space:nowrap;border:1px solid rgba(125,157,225,.16);border-radius:15px;background:rgba(6,14,31,.74);margin:0 0 .95rem;}.ic-ticker-track{display:inline-flex;min-width:200%;padding:.55rem 0;animation:tickerMove 24s linear infinite;}.ic-ticker-item{display:inline-flex;align-items:center;gap:.5rem;color:#acbbd7;font-size:.72rem;margin-right:2.6rem;}.ic-ticker-item strong{color:#ecf5ff;}.ic-ticker-dot{width:5px;height:5px;border-radius:50%;background:var(--ic-cyan);box-shadow:0 0 10px var(--ic-cyan);}
.ic-metric{position:relative;overflow:hidden;min-height:132px;padding:1rem 1.05rem;border-radius:20px;border:1px solid rgba(126,159,230,.19);background:linear-gradient(145deg,rgba(15,31,61,.89),rgba(7,16,35,.94));box-shadow:0 16px 44px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.04);transition:transform .26s ease,border-color .26s ease,box-shadow .26s ease;animation:riseIn .48s ease both;}.ic-metric:hover{transform:translateY(-5px);border-color:rgba(57,220,255,.43);box-shadow:0 22px 58px rgba(0,0,0,.35),0 0 34px rgba(57,220,255,.08);}.ic-metric::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:linear-gradient(90deg,transparent,var(--accent),transparent);}.ic-metric-top{display:flex;justify-content:space-between;align-items:center;gap:.6rem;}.ic-metric-icon{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 16%,transparent);border:1px solid color-mix(in srgb,var(--accent) 30%,transparent);box-shadow:0 0 20px color-mix(in srgb,var(--accent) 12%,transparent);font-size:.95rem;}.ic-metric-label{color:#94a6c6;font-size:.68rem;text-transform:uppercase;letter-spacing:.10em;font-weight:850;}.ic-metric-value{font-size:1.72rem;font-weight:950;letter-spacing:-.035em;margin:.45rem 0 .15rem;}.ic-metric-foot{color:#a9b7d0;font-size:.72rem;white-space:normal;}.ic-mini-track{height:3px;border-radius:999px;background:rgba(255,255,255,.06);margin-top:.65rem;overflow:hidden;}.ic-mini-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),rgba(255,255,255,.72));box-shadow:0 0 14px var(--accent);}
.ic-section-head{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;flex-wrap:wrap;margin:1.2rem 0 .7rem;}.ic-section-kicker{font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:#6edfff;font-weight:900;}.ic-section-title{font-size:1.36rem;font-weight:950;letter-spacing:-.03em;margin:.12rem 0;}.ic-section-copy{color:#97a8c7;font-size:.82rem;max-width:760px;}
.ic-card{position:relative;overflow:hidden;padding:1rem 1.05rem;border-radius:19px;background:linear-gradient(145deg,rgba(13,28,55,.86),rgba(7,16,34,.90));border:1px solid rgba(126,158,225,.18);box-shadow:0 14px 42px rgba(0,0,0,.20),inset 0 1px 0 rgba(255,255,255,.035);transition:transform .24s ease,border-color .24s ease,box-shadow .24s ease;margin-bottom:.65rem;}.ic-card:hover{transform:translateY(-3px);border-color:rgba(90,183,255,.37);box-shadow:0 18px 48px rgba(0,0,0,.30);}.ic-card-glow::after{content:"";position:absolute;width:130px;height:130px;border-radius:50%;right:-65px;top:-70px;background:radial-gradient(circle,color-mix(in srgb,var(--accent) 28%,transparent),transparent 70%);}.ic-action-priority{position:relative;z-index:1;font-size:.64rem;font-weight:950;letter-spacing:.12em;color:var(--accent);text-transform:uppercase;}.ic-action-title{position:relative;z-index:1;font-size:.98rem;font-weight:900;margin:.24rem 0 .32rem;}.ic-action-detail,.ic-action-evidence{position:relative;z-index:1;color:#9eacc6;font-size:.78rem;line-height:1.55;}.ic-action-evidence{margin-top:.55rem;color:#c9d6ec;}
.ic-service-card{position:relative;overflow:hidden;padding:.95rem;border-radius:18px;background:linear-gradient(145deg,rgba(15,31,61,.86),rgba(7,16,34,.92));border:1px solid rgba(125,157,222,.17);min-height:170px;transition:transform .24s ease,border-color .24s ease;}.ic-service-card:hover{transform:translateY(-4px);border-color:rgba(57,220,255,.36);}.ic-service-top{display:flex;justify-content:space-between;gap:.6rem;align-items:center;}.ic-service-name{font-weight:900;font-size:.94rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.ic-health-ring{--score:50;width:56px;height:56px;border-radius:50%;display:grid;place-items:center;flex:0 0 auto;background:conic-gradient(var(--ring) calc(var(--score)*1%),rgba(255,255,255,.055) 0);position:relative;box-shadow:0 0 22px color-mix(in srgb,var(--ring) 15%,transparent);}.ic-health-ring::before{content:"";position:absolute;inset:6px;border-radius:50%;background:#091327;}.ic-health-ring span{position:relative;font-size:.72rem;font-weight:950;}.ic-service-stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.42rem;margin-top:.8rem;}.ic-service-stat{padding:.42rem;border-radius:11px;background:rgba(255,255,255,.035);text-align:center;}.ic-service-stat strong{display:block;font-size:.88rem;}.ic-service-stat small{color:#8fa0be;font-size:.61rem;text-transform:uppercase;letter-spacing:.06em;}.ic-service-status{display:inline-flex;margin-top:.65rem;padding:.28rem .52rem;border-radius:999px;font-size:.62rem;font-weight:850;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.07);color:#cbd7ec;}
.ic-empty-step{min-height:164px;padding:1.1rem;border-radius:20px;background:rgba(8,18,39,.72);border:1px solid rgba(120,154,220,.16);transition:transform .24s ease,border-color .24s ease;}.ic-empty-step:hover{transform:translateY(-5px);border-color:rgba(57,220,255,.35);}.ic-step-number{font-size:2rem;font-weight:950;color:rgba(119,215,255,.32);line-height:1;}.ic-step-title{font-size:1rem;font-weight:900;margin:.45rem 0 .3rem;}.ic-step-copy{color:#97a7c3;font-size:.8rem;line-height:1.55;}
[data-testid="stDataFrame"]{border:1px solid rgba(126,158,225,.18);border-radius:18px;overflow:hidden;box-shadow:0 13px 40px rgba(0,0,0,.20);}[data-testid="stPlotlyChart"]{border:1px solid rgba(126,158,225,.15);border-radius:20px;background:linear-gradient(145deg,rgba(11,24,49,.72),rgba(6,14,31,.78));box-shadow:0 16px 46px rgba(0,0,0,.20),inset 0 1px 0 rgba(255,255,255,.025);overflow:hidden;animation:riseIn .5s ease both;}[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(13,28,55,.82),rgba(7,16,34,.88));border:1px solid rgba(126,158,225,.17);border-radius:17px;padding:13px;}[data-testid="stExpander"]{border:1px solid rgba(126,158,225,.17)!important;border-radius:17px!important;background:rgba(7,16,35,.68)!important;overflow:hidden;}
[data-baseweb="radio"] > div{gap:.34rem;}[data-baseweb="radio"] label{border-radius:12px;padding:.45rem .55rem;transition:background .22s ease,transform .22s ease;}[data-baseweb="radio"] label:hover{background:rgba(90,135,255,.10);transform:translateX(3px);}.stButton > button,.stDownloadButton > button{border-radius:13px;border:1px solid rgba(126,158,225,.22);font-weight:820;background:linear-gradient(145deg,rgba(18,35,68,.88),rgba(8,18,38,.92));transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease;}.stButton > button:hover,.stDownloadButton > button:hover{transform:translateY(-2px);border-color:rgba(57,220,255,.45);box-shadow:0 10px 28px rgba(0,0,0,.28),0 0 24px rgba(57,220,255,.08);}.stButton > button[kind="primary"]{background:linear-gradient(100deg,#477dff,#8b67ff,#d35fc2);border:none;box-shadow:0 12px 30px rgba(91,111,255,.24);background-size:180% 180%;animation:auroraShift 6s ease-in-out infinite;}.stTextInput input,.stTextArea textarea,[data-baseweb="select"] > div{border-radius:13px!important;border-color:rgba(126,158,225,.19)!important;background:rgba(6,14,30,.72)!important;}hr{border-color:rgba(126,158,225,.15)!important;}
@media (max-width:980px){.ic-hero{grid-template-columns:1fr;min-height:unset;}.ic-orbit{display:none;}.ic-hero-title{font-size:2.65rem;}.ic-metric{min-height:118px;}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;}}
</style>
"""
st.markdown(CINEMATIC_CSS, unsafe_allow_html=True)

PLOTLY_CONFIG = {"displaylogo": False, "responsive": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def safe(value: object) -> str:
    return html.escape(str(value), quote=True)


def style_figure(fig: go.Figure, height: int = 390, *, legend: bool = True, hovermode: str | None = None) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=48, b=22), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#dce7ff", family="Inter, ui-sans-serif, system-ui, sans-serif"), xaxis=dict(gridcolor="rgba(130,161,225,.10)", zeroline=False, linecolor="rgba(130,161,225,.14)"), yaxis=dict(gridcolor="rgba(130,161,225,.10)", zeroline=False, linecolor="rgba(130,161,225,.14)"), legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.08, x=0) if legend else None, hoverlabel=dict(bgcolor="#091329", bordercolor="rgba(57,220,255,.32)", font_color="#edf5ff"), hovermode=hovermode, transition=dict(duration=450, easing="cubic-in-out"), uirevision="incidentcommander-v4")
    return fig


def severity_css(severity: str) -> str:
    return {"SEV-1": "ic-sev1", "SEV-2": "ic-sev2", "SEV-3": "ic-sev3", "SEV-4": "ic-sev4"}.get(severity, "ic-sev3")


def severity_color(severity: str) -> str:
    return {"SEV-1": "#ff6476", "SEV-2": "#ffd166", "SEV-3": "#5a87ff", "SEV-4": "#45e8aa"}.get(severity, "#5a87ff")


def metric_card(label: str, value: object, foot: str, icon: str, accent: str, progress: float | None = None) -> None:
    bounded = max(0.0, min(100.0, float(progress))) if progress is not None else 0.0
    bar = f"<div class='ic-mini-track'><div class='ic-mini-fill' style='width:{bounded:.1f}%'></div></div>" if progress is not None else ""
    st.markdown(f"<div class='ic-metric' style='--accent:{accent}'><div class='ic-metric-top'><div class='ic-metric-label'>{safe(label)}</div><div class='ic-metric-icon'>{icon}</div></div><div class='ic-metric-value'>{safe(value)}</div><div class='ic-metric-foot'>{safe(foot)}</div>{bar}</div>", unsafe_allow_html=True)


def section_header(kicker: str, title: str, copy: str = "", meta: str = "") -> None:
    st.markdown(f"<div class='ic-section-head'><div><div class='ic-section-kicker'>{safe(kicker)}</div><div class='ic-section-title'>{safe(title)}</div><div class='ic-section-copy'>{safe(copy)}</div></div><div class='ic-muted' style='font-size:.72rem'>{safe(meta)}</div></div>", unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(f"<div class='ic-brand'><div class='ic-brand-mark'>⚡</div><div><div class='ic-brand-title'>IncidentCommander</div><div class='ic-brand-sub'>{VERSION} · Explainable operations AI</div></div></div><div class='ic-live-row'><span class='ic-live-dot'></span>Analysis engine ready</div>", unsafe_allow_html=True)


def render_orbit() -> str:
    return "<div class='ic-orbit'><div class='ic-orbit-ring'></div><div class='ic-orbit-ring-two'></div><div class='ic-scan-lines'></div><div class='ic-core'>IC·AI</div></div>"


def render_empty_state() -> None:
    st.markdown(f"<div class='ic-hero'><div class='ic-hero-copy'><div class='ic-eyebrow'><span class='ic-live-dot'></span> Autonomous incident intelligence</div><div class='ic-hero-title'>See the failure.<br/>Trace the impact.<br/>Command the response.</div><div class='ic-hero-sub'>Convert noisy application and infrastructure logs into correlated incident episodes, animated service-impact views, evidence-ranked root causes, and a safe human-reviewed response plan.</div><div class='ic-chip-row'><span class='ic-chip'>✦ Multi-source ingestion</span><span class='ic-chip'>◉ Anomaly intelligence</span><span class='ic-chip'>⌁ Service topology</span><span class='ic-chip'>↗ Incident memory</span></div></div>{render_orbit()}</div>", unsafe_allow_html=True)
    columns = st.columns(3)
    steps = [("01", "Ingest the evidence", "Upload application, gateway, database, container, JSONL, or structured CSV logs."), ("02", "Correlate the incident", "Group signals into episodes, trace requests, map dependencies, and calculate blast radius."), ("03", "Command the response", "Review ranked evidence, validate a safe runbook, save incident memory, and export reports.")]
    for column, (number, title, copy) in zip(columns, steps):
        with column:
            st.markdown(f"<div class='ic-empty-step'><div class='ic-step-number'>{number}</div><div class='ic-step-title'>{title}</div><div class='ic-step-copy'>{copy}</div></div>", unsafe_allow_html=True)
    st.info("Open the sidebar and select **Load cinematic demo** to explore every page with multi-service data.")


def render_active_header(summary: dict, sources: list[tuple[str, str]], top_cause: str) -> None:
    st.markdown(f"<div class='ic-active-hero'><div><div class='ic-eyebrow'><span class='ic-live-dot'></span> Live incident command workspace</div><div class='ic-active-title'>Operations Intelligence · {safe(summary['fingerprint'])}</div><div class='ic-muted'>Correlating {summary['total_events']:,} events across {summary['services']} services and {len(sources)} evidence sources.</div></div><div style='text-align:right;position:relative;z-index:2'><span class='ic-severity {severity_css(summary['severity'])}'>{safe(summary['severity'])}</span><div class='ic-muted' style='font-size:.72rem;margin-top:.5rem'>Health band · {safe(health_band(summary['health_score']))}</div></div></div>", unsafe_allow_html=True)
    ticker_items = [f"<span class='ic-ticker-item'><span class='ic-ticker-dot'></span>Leading hypothesis <strong>{safe(top_cause)}</strong></span>", f"<span class='ic-ticker-item'><span class='ic-ticker-dot'></span>Error rate <strong>{safe(summary['error_rate'])}%</strong></span>", f"<span class='ic-ticker-item'><span class='ic-ticker-dot'></span>Blast radius <strong>{safe(summary['impacted_services'])} services</strong></span>", f"<span class='ic-ticker-item'><span class='ic-ticker-dot'></span>Anomalies <strong>{safe(summary['anomalies'])}</strong></span>", f"<span class='ic-ticker-item'><span class='ic-ticker-dot'></span>Availability proxy <strong>{safe(summary['availability_proxy'])}%</strong></span>"]
    st.markdown(f"<div class='ic-ticker'><div class='ic-ticker-track'>{''.join(ticker_items + ticker_items)}</div></div>", unsafe_allow_html=True)


def render_action_card(action: dict, accent: str) -> None:
    st.markdown(f"<div class='ic-card ic-card-glow' style='--accent:{accent};min-height:188px'><div class='ic-action-priority'>{safe(action.get('priority','Priority'))}</div><div class='ic-action-title'>{safe(action.get('title','Investigate'))}</div><div class='ic-action-detail'>{safe(action.get('detail',''))}</div><div class='ic-action-evidence'>{safe(action.get('evidence',''))}</div></div>", unsafe_allow_html=True)


def render_service_cards(cards: pd.DataFrame, limit: int = 4) -> None:
    if cards.empty:
        st.info("No service scorecards are available.")
        return
    shown = cards.head(limit)
    columns = st.columns(len(shown))
    for column, row in zip(columns, shown.to_dict("records")):
        health = int(row.get("health_score", 0) or 0)
        ring = "#45e8aa" if health >= 80 else "#5a87ff" if health >= 60 else "#ffd166" if health >= 40 else "#ff6476"
        status = row.get("status", health_band(health))
        with column:
            st.markdown(f"<div class='ic-service-card'><div class='ic-service-top'><div><div class='ic-section-kicker'>Service intelligence</div><div class='ic-service-name'>{safe(row.get('service','unknown'))}</div></div><div class='ic-health-ring' style='--score:{health};--ring:{ring}'><span>{health}</span></div></div><div class='ic-service-stat-grid'><div class='ic-service-stat'><strong>{safe(row.get('errors',0))}</strong><small>Errors</small></div><div class='ic-service-stat'><strong>{safe(row.get('anomalies',0))}</strong><small>Anomalies</small></div><div class='ic-service-stat'><strong>{safe(row.get('impact_score',0))}</strong><small>Impact</small></div></div><span class='ic-service-status'>{safe(status)}</span></div>", unsafe_allow_html=True)


with st.sidebar:
    render_brand()
    st.divider()
    uploaded = st.file_uploader("Incident evidence sources", type=["log","txt","out","csv","jsonl"], accept_multiple_files=True, help="Upload application, gateway, database, infrastructure, or container logs.")
    left_button, right_button = st.columns(2)
    demo = left_button.button("Load cinematic demo", use_container_width=True, type="primary")
    clear = right_button.button("Clear", use_container_width=True)
    redact = st.toggle("Redact sensitive values", value=True)
    gap_seconds = st.slider("Episode separation", 30, 600, 120, 30, format="%d sec")
    st.divider()
    change_file = st.file_uploader("Deployment/change CSV", type=["csv"], key="changes")
    st.caption("Required columns: timestamp, service, change")

if clear:
    for key in ["sources","selected_services","analyst_notes"]:
        st.session_state.pop(key, None)
    st.rerun()
if demo:
    demo_files = [BASE_DIR / "sample_logs" / "demo_incident.log", BASE_DIR / "sample_logs" / "payments.jsonl"]
    st.session_state["sources"] = [(path.name, path.read_text(encoding="utf-8")) for path in demo_files]
elif uploaded:
    st.session_state["sources"] = [(item.name, item.getvalue().decode("utf-8", errors="replace")) for item in uploaded]

sources = st.session_state.get("sources", [])
if not sources:
    render_empty_state(); st.stop()
raw_joined = "\n".join(text for _, text in sources)
sensitive_audit = audit_sensitive_text(raw_joined)
processed_sources = [(name, redact_text(text) if redact else text) for name, text in sources]
all_events = parse_sources(processed_sources)
if not all_events:
    st.error("No valid log events could be parsed. Include a message and, ideally, timestamp and service metadata."); st.stop()
all_services = sorted({event.service for event in all_events})
with st.sidebar:
    st.divider()
    selected_services = st.multiselect("Global service scope", options=all_services, default=st.session_state.get("selected_services", all_services), help="Every chart, root-cause score, and report follows this scope.")
    st.session_state["selected_services"] = selected_services
    focus_anomalies = st.toggle("Analyst focus mode", value=False)
    st.divider()
    page_labels = {"⚡ Command Center":"Command Center","🔎 Investigation":"Investigation","⌁ Service Topology":"Service Topology","🛟 Response Center":"Response Center","⌘ Log Explorer":"Log Explorer","◫ Incident Memory":"Incident Memory","◈ Data Quality":"Data Quality","⇩ Report Center":"Reports"}
    page_label = st.radio("Workspace", list(page_labels), label_visibility="collapsed")
    page = page_labels[page_label]

events = [event for event in all_events if not selected_services or event.service in selected_services]
result = analyze_events(events)
frame = result["frame"]; summary = result["summary"]
timeline = build_timeline(frame); edges = build_dependency_edges(frame); blast = blast_radius(frame); episodes = correlate_episodes(frame, gap_seconds=gap_seconds)
service_cards = service_scorecards(frame, blast); heatmap = anomaly_heatmap(frame); root_causes = root_cause_table(result["root_causes"])
change_results = pd.DataFrame()
if change_file:
    try:
        changes = pd.read_csv(change_file)
        if not {"timestamp","service"}.issubset(changes.columns): st.sidebar.error("Change CSV requires timestamp and service columns.")
        else: change_results = correlate_changes(frame, changes)
    except Exception as exc: st.sidebar.error(f"Could not read change CSV: {exc}")
actions = executive_actions(result, blast, change_results)
top_cause = result["root_causes"][0]["cause"] if result["root_causes"] else "Unknown or mixed failure"
with st.sidebar:
    st.divider(); st.caption(f"Fingerprint · {summary['fingerprint']}"); st.caption(f"Evidence · {len(sources)} sources · {summary['total_events']:,} events"); st.caption("Human-in-the-loop · No autonomous remediation")

render_active_header(summary, sources, top_cause)
metric_items = [("Operational health",f"{summary['health_score']}/100",health_band(summary["health_score"]),"♥","#39dcff",summary["health_score"]),("Error rate",f"{summary['error_rate']}%",f"{summary['errors']} error-level events","!","#ff6476",summary["error_rate"]),("Blast radius",summary["impacted_services"],f"of {summary['services']} observed services","⌁","#a06dff",min(100,summary["impacted_services"]*20)),("Anomalies",summary["anomalies"],"Isolation Forest outliers","◉","#ff70d6",min(100,summary["anomalies"]*10)),("Availability proxy",f"{summary['availability_proxy']}%","Derived from parsed log outcomes","↟","#45e8aa",summary["availability_proxy"]),("P95 latency",f"{summary['p95_latency_ms']} ms" if summary["p95_latency_ms"] is not None else "n/a","Across parsed duration fields","⌛","#ffd166",None)]
for column, item in zip(st.columns(6), metric_items):
    with column: metric_card(*item)

if page == "Command Center":
    section_header("Executive operations view","Incident Command Center","Animated situation awareness, evidence ranking, and service-level impact in one workspace.",f"{summary['severity']} · {summary['fingerprint']}")
    left,middle,right = st.columns([1.35,.72,.86])
    with left:
        if timeline.empty: st.info("No parseable timestamps were found.")
        else:
            long = timeline.melt(id_vars="timestamp",value_vars=["events","errors","warnings","anomalies"],var_name="signal",value_name="count")
            fig = px.area(long,x="timestamp",y="count",color="signal",color_discrete_map={"events":"#5a87ff","errors":"#ff6476","warnings":"#ffd166","anomalies":"#a06dff"}); fig.update_traces(line=dict(width=2.2),opacity=.78)
            st.plotly_chart(style_figure(fig,410,hovermode="x unified"),use_container_width=True,config=PLOTLY_CONFIG)
    with middle:
        gauge = go.Figure(go.Indicator(mode="gauge+number",value=summary["health_score"],number={"suffix":"/100","font":{"size":34,"color":"#f7fbff"}},title={"text":"Operational health","font":{"size":14,"color":"#9eb0ce"}},gauge={"axis":{"range":[0,100],"tickcolor":"rgba(255,255,255,.18)"},"bar":{"color":"#39dcff","thickness":.28},"bgcolor":"rgba(255,255,255,.035)","bordercolor":"rgba(130,160,225,.16)","steps":[{"range":[0,40],"color":"rgba(255,100,118,.22)"},{"range":[40,65],"color":"rgba(255,209,102,.18)"},{"range":[65,85],"color":"rgba(90,135,255,.17)"},{"range":[85,100],"color":"rgba(69,232,170,.16)"}]}))
        st.plotly_chart(style_figure(gauge,410,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    with right:
        severity_counts = frame["level"].value_counts().rename_axis("level").reset_index(name="events")
        fig = px.pie(severity_counts,values="events",names="level",hole=.68,color="level",color_discrete_map={"ERROR":"#ff6476","CRITICAL":"#ff365d","FATAL":"#d4145a","WARN":"#ffd166","INFO":"#5a87ff","DEBUG":"#39dcff","TRACE":"#45e8aa"}); fig.update_traces(textposition="inside",textinfo="percent",marker=dict(line=dict(color="#071021",width=2))); fig.add_annotation(text=f"<b>{summary['total_events']}</b><br>events",x=.5,y=.5,showarrow=False,font=dict(size=17,color="#eef6ff"))
        st.plotly_chart(style_figure(fig,410,legend=True),use_container_width=True,config=PLOTLY_CONFIG)
    a,b = st.columns([1.02,.98])
    with a:
        section_header("Explainable AI","Root-cause confidence","Normalized confidence is based on matched evidence patterns and incident severity.")
        if root_causes.empty: st.info("No root-cause evidence available.")
        else:
            fig = px.bar(root_causes.sort_values("confidence_percent"),x="confidence_percent",y="cause",orientation="h",text="confidence_percent",color="confidence_percent",color_continuous_scale=["#1d3157","#5a87ff","#a06dff","#ff70d6"]); fig.update_traces(texttemplate="%{text:.0f}%",textposition="outside",marker_line_width=0); fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_figure(fig,365,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    with b:
        section_header("Priority queue","What needs attention now","Evidence-backed actions only; every production change remains human-reviewed.")
        action_columns = st.columns(max(1,len(actions))); accents=["#ff6476","#ffd166","#39dcff","#a06dff"]
        for column,action,accent in zip(action_columns,actions,accents):
            with column: render_action_card(action,accent)
    section_header("Service intelligence","Health and blast-radius scorecards","Hover each card to inspect the visual health state. Full numeric detail remains available below.")
    render_service_cards(service_cards,limit=min(4,len(service_cards)))
    a,b = st.columns([1.22,.78])
    with a:
        st.dataframe(service_cards,use_container_width=True,hide_index=True,height=360,column_config={"health_score":st.column_config.ProgressColumn("Health",min_value=0,max_value=100,format="%d"),"impact_score":st.column_config.ProgressColumn("Impact",min_value=0,max_value=100,format="%d"),"error_rate":st.column_config.NumberColumn("Error rate",format="%.1f%%"),"p95_latency_ms":st.column_config.NumberColumn("P95 latency",format="%.1f ms")})
    with b:
        if blast.empty: st.success("No impacted service could be ranked.")
        else:
            fig = px.scatter(blast,x="impact_score",y="errors",size="dependent_events",color="anomalies",hover_name="service",text="service",size_max=52,color_continuous_scale=["#39dcff","#a06dff","#ff6476"]); fig.update_traces(textposition="top center",marker=dict(line=dict(color="rgba(255,255,255,.25)",width=1)))
            st.plotly_chart(style_figure(fig,360,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
elif page == "Investigation":
    section_header("Forensic workspace","Deep Investigation","Correlated episodes, anomaly intensity, latency bands, traces, and change risk.")
    a,b = st.columns([1.12,.88])
    with a: st.dataframe(episodes,use_container_width=True,hide_index=True,height=355,column_config={"confidence":st.column_config.ProgressColumn("Confidence",min_value=0,max_value=1,format="%.0%%")})
    with b:
        if heatmap.empty: st.info("Timestamp coverage is insufficient for a heatmap.")
        else:
            fig = go.Figure(data=go.Heatmap(z=heatmap.values,x=[str(value) for value in heatmap.columns],y=heatmap.index.tolist(),colorscale=[[0,"#081329"],[.30,"#1e4679"],[.62,"#6d52c7"],[1,"#ff6476"]],colorbar={"title":"Risk"},hoverongaps=False))
            st.plotly_chart(style_figure(fig,355,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    c,d = st.columns(2)
    with c:
        section_header("Performance signal","Latency and failure bands","Anomaly size, log level symbol, and P95 reference line.")
        latency = frame.dropna(subset=["timestamp","duration_ms"]).copy()
        if latency.empty: st.info("No duration metadata was found.")
        else:
            fig = px.scatter(latency,x="timestamp",y="duration_ms",color="service",symbol="level",hover_data=["status_code","request_id","message"],size=[11 if value else 7 for value in latency["is_anomaly"]])
            if summary["p95_latency_ms"] is not None: fig.add_hline(y=summary["p95_latency_ms"],line_dash="dash",line_color="#ffd166",annotation_text="P95")
            st.plotly_chart(style_figure(fig,410),use_container_width=True,config=PLOTLY_CONFIG)
    with d:
        section_header("Evidence ranking","Highest-priority events","Sorted by anomaly state and model anomaly score.")
        evidence = frame.copy()
        if focus_anomalies: evidence = evidence[evidence["is_anomaly"] | evidence["level"].isin(ERROR_LEVELS)]
        evidence = evidence.sort_values(["is_anomaly","anomaly_score"],ascending=False).head(14)
        st.dataframe(evidence[["timestamp","level","service","dependency","request_id","anomaly_score","message"]],use_container_width=True,hide_index=True,height=410)
    section_header("Distributed trace view","Cross-service request traces","Trace propagation reveals which request crossed the largest failure surface.")
    request_ids = frame.dropna(subset=["request_id"])
    if request_ids.empty: st.info("No request IDs were found. Add request_id or trace_id metadata to improve causal investigation.")
    else:
        trace_summary = request_ids.groupby("request_id").agg(events=("message","count"),services=("service",lambda values:", ".join(sorted(set(values)))),errors=("level",lambda values:int(pd.Series(values).isin(ERROR_LEVELS).sum())),max_latency_ms=("duration_ms","max")).reset_index().sort_values(["errors","events"],ascending=False)
        st.dataframe(trace_summary,use_container_width=True,hide_index=True)
    if not change_results.empty:
        section_header("Change intelligence","Deployment correlation","Changes are ranked by errors and anomalies observed in the configured post-change window.")
        st.dataframe(change_results,use_container_width=True,hide_index=True,column_config={"risk_score":st.column_config.ProgressColumn("Risk",min_value=0,max_value=100,format="%d")})
elif page == "Service Topology":
    section_header("Dependency intelligence","Service Topology & Impact","Observed dependency flow, blast-radius ranking, and service reliability.")
    a,b = st.columns([1.18,.82])
    with a:
        if edges.empty: st.info("Add dependency=service or upstream=service metadata to build the dependency map.")
        else:
            nodes=sorted(set(edges["source"])|set(edges["target"])); node_index={node:index for index,node in enumerate(nodes)}
            fig=go.Figure(go.Sankey(arrangement="snap",node={"label":nodes,"pad":24,"thickness":20,"color":["#5a87ff" if node in set(edges["source"]) else "#a06dff" for node in nodes],"line":{"color":"rgba(255,255,255,.22)","width":1}},link={"source":[node_index[item] for item in edges["source"]],"target":[node_index[item] for item in edges["target"]],"value":edges["events"].clip(lower=1),"label":[f"{row.errors} errors · {row.events} events" for row in edges.itertuples()],"color":["rgba(255,100,118,.34)" if row.errors else "rgba(57,220,255,.20)" for row in edges.itertuples()]}))
            st.plotly_chart(style_figure(fig,570,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    with b:
        if blast.empty: st.success("No impact signals found.")
        else:
            fig=px.bar(blast.sort_values("impact_score"),x="impact_score",y="service",orientation="h",color="impact_score",color_continuous_scale=["#1b3158","#5a87ff","#a06dff","#ff6476"],text="impact_score",hover_data=["errors","warnings","anomalies","dependent_events"]); fig.update_layout(coloraxis_showscale=False); fig.update_traces(marker_line_width=0)
            st.plotly_chart(style_figure(fig,570,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    section_header("Reliability matrix","All observed services","Use progress bars for rapid comparison, then inspect raw evidence in Log Explorer.")
    render_service_cards(service_cards,limit=min(4,len(service_cards)))
    st.dataframe(service_cards,use_container_width=True,hide_index=True,column_config={"health_score":st.column_config.ProgressColumn("Health",min_value=0,max_value=100,format="%d"),"impact_score":st.column_config.ProgressColumn("Impact",min_value=0,max_value=100,format="%d"),"error_rate":st.column_config.NumberColumn("Error rate",format="%.1f%%")})
elif page == "Response Center":
    section_header("Human-in-the-loop response","Response Center","Validate hypotheses, document decisions, complete a safe runbook, and preserve incident memory.")
    top=result["root_causes"][0] if result["root_causes"] else None
    if top: st.markdown(f"<div class='ic-card ic-card-glow' style='--accent:{severity_color(summary['severity'])};padding:1.25rem 1.3rem'><div class='ic-section-kicker'>Leading hypothesis</div><div style='font-size:1.65rem;font-weight:950;letter-spacing:-.035em;margin:.25rem 0'>{safe(top['cause'])}</div><div class='ic-muted'>{top['confidence']:.0%} normalized confidence · {top['evidence_hits']} evidence hits</div></div>",unsafe_allow_html=True)
    left,right=st.columns([1.08,.92])
    with left:
        for index,item in enumerate(result["root_causes"],1):
            with st.expander(f"{index}. {item['cause']} · {item['confidence']:.0%}",expanded=index==1):
                if item.get("evidence"):
                    st.markdown("**Evidence samples**")
                    for evidence in item["evidence"]: st.code(evidence,language=None)
                st.markdown("**Human-reviewed runbook**")
                for step_index,step in enumerate(item["runbook"]): st.checkbox(step,key=f"runbook-{summary['fingerprint']}-{index}-{step_index}")
    with right:
        analyst_notes=st.text_area("Investigation notes",value=st.session_state.get("analyst_notes",""),height=190,placeholder="Document confirmed evidence, rollback conditions, owners, and decisions."); st.session_state["analyst_notes"]=analyst_notes
        section_header("Action orchestration","Current response queue","Prioritized actions derived from incident evidence.")
        for item,accent in zip(actions,["#ff6476","#ffd166","#39dcff","#a06dff"]): render_action_card(item,accent)
        if st.button("Save incident to memory",type="primary",use_container_width=True):
            try: st.success(f"Incident #{save_incident(HISTORY_DB,result,', '.join(name for name,_ in sources),analyst_notes)} saved to local memory.")
            except Exception as exc: st.error(f"Could not save incident: {exc}")
    st.warning("Decision support only. Validate permissions, telemetry, rollback safety, and business impact before production changes.")
elif page == "Log Explorer":
    section_header("Evidence browser","Log Explorer","Filter every parsed field, isolate anomalies, and search distributed trace identifiers.")
    services=["All"]+sorted(frame["service"].astype(str).unique().tolist()); levels=["All"]+sorted(frame["level"].astype(str).unique().tolist()); source_values=["All"]+sorted(frame["source"].astype(str).unique().tolist())
    a,b,c,d=st.columns([1,1,1,2]); service=a.selectbox("Service",services); level=b.selectbox("Level",levels); selected_source=c.selectbox("Source",source_values); query=d.text_input("Search message, request ID, trace ID, dependency, or host"); anomaly_only=st.toggle("Anomalies only",value=focus_anomalies)
    filtered=frame.copy()
    if service!="All": filtered=filtered[filtered["service"]==service]
    if level!="All": filtered=filtered[filtered["level"]==level]
    if selected_source!="All": filtered=filtered[filtered["source"]==selected_source]
    if anomaly_only: filtered=filtered[filtered["is_anomaly"]]
    if query:
        mask=pd.Series(False,index=filtered.index)
        for column in ["message","request_id","trace_id","dependency","host"]:
            if column in filtered: mask|=filtered[column].fillna("").astype(str).str.contains(query,case=False,regex=False)
        filtered=filtered[mask]
    st.caption(f"Showing {len(filtered):,} of {len(frame):,} events")
    columns=["timestamp","level","service","dependency","request_id","trace_id","status_code","duration_ms","cluster","anomaly_score","is_anomaly","message"]
    st.dataframe(filtered[columns].sort_values("anomaly_score",ascending=False),use_container_width=True,hide_index=True,height=650)
elif page == "Incident Memory":
    section_header("Operational learning","Incident Memory & Comparison","Retrieve related failures, compare severity and health, and reuse documented resolution knowledge.")
    try: history=list_incidents(HISTORY_DB); similar=similar_incidents(HISTORY_DB,result)
    except Exception as exc: st.warning(f"Incident memory is unavailable in this environment: {exc}"); history=pd.DataFrame(); similar=pd.DataFrame()
    a,b=st.columns([.92,1.08])
    with a:
        if similar.empty: st.info("Save the current incident to create comparison history.")
        else: st.dataframe(similar[["id","created_at","severity","root_cause","services","notes","similarity"]],use_container_width=True,hide_index=True)
    with b:
        if history.empty: st.info("No historical incidents are stored yet.")
        else:
            labels={int(row.id):f"#{row.id} · {row.severity} · {row.root_cause}" for row in history.itertuples()}; selected_id=st.selectbox("Historical incident",options=list(labels),format_func=labels.get); row=history[history["id"]==selected_id].iloc[0]; comparison=compare_incident({**summary,"top_root_cause":top_cause},row); st.dataframe(comparison,use_container_width=True,hide_index=True)
            if row.get("notes"): st.info(f"Historical notes: {row['notes']}")
    section_header("Incident archive","Full operational memory","Newest incidents appear first."); st.dataframe(history,use_container_width=True,hide_index=True,height=410)
elif page == "Data Quality":
    section_header("Model trust layer","Observability & Data Quality","Measure metadata coverage, inspect clustering, and improve the evidence supplied to the analysis engine.")
    quality=result["quality"]; a,b=st.columns([.76,1.24])
    with a:
        gauge=go.Figure(go.Indicator(mode="gauge+number",value=quality["score"],number={"suffix":"/100","font":{"size":34}},title={"text":"Observability quality"},gauge={"axis":{"range":[0,100]},"bar":{"color":"#45e8aa","thickness":.28},"steps":[{"range":[0,40],"color":"rgba(255,100,118,.20)"},{"range":[40,70],"color":"rgba(255,209,102,.17)"},{"range":[70,100],"color":"rgba(69,232,170,.15)"}]})); st.plotly_chart(style_figure(gauge,400,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    with b:
        dimensions=[key for key in quality if key!="score"]; radar_values=[quality[key] for key in dimensions]; fig=go.Figure(go.Scatterpolar(r=radar_values+[radar_values[0]],theta=[key.replace("_"," ").title() for key in dimensions]+[dimensions[0].replace("_"," ").title()],fill="toself",line={"color":"#39dcff","width":2.4},fillcolor="rgba(57,220,255,.15)",marker={"color":"#a06dff","size":7})); fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,100],gridcolor="rgba(130,160,225,.14)"),angularaxis=dict(gridcolor="rgba(130,160,225,.12)"),bgcolor="rgba(0,0,0,0)")); st.plotly_chart(style_figure(fig,400,legend=False),use_container_width=True,config=PLOTLY_CONFIG)
    c,d=st.columns(2)
    with c: st.dataframe(pd.DataFrame([{"type":key,"detections":value} for key,value in sensitive_audit.items()]),use_container_width=True,hide_index=True); st.caption("Redaction is applied before parsing and report generation when enabled.")
    with d: st.dataframe(result["clusters"],use_container_width=True,hide_index=True)
    section_header("Telemetry roadmap","Recommended evidence improvements","Recommendations are generated from actual metadata coverage.")
    recommendations=[]
    if quality["timestamps"]<90: recommendations.append("Standardize UTC timestamps on every event.")
    if quality["service_names"]<90: recommendations.append("Include a stable service or component name.")
    if quality["request_or_trace_ids"]<60: recommendations.append("Propagate request and trace IDs across service boundaries.")
    if quality["latency_metadata"]<40: recommendations.append("Add duration_ms and status_code to request logs.")
    if quality["host_metadata"]<40: recommendations.append("Include host, node, or availability-zone metadata.")
    if not recommendations: recommendations.append("Metadata coverage is strong. Add SLO telemetry and deployment markers next.")
    for column,recommendation in zip(st.columns(min(3,len(recommendations))),recommendations):
        with column: st.markdown(f"<div class='ic-card'><div class='ic-action-title'>Telemetry improvement</div><div class='ic-action-detail'>{safe(recommendation)}</div></div>",unsafe_allow_html=True)
elif page == "Reports":
    section_header("Export and communication","Incident Report Center","Generate technical evidence packages and executive-ready summaries from the active service scope.")
    source_name=", ".join(name for name,_ in sources); markdown=build_markdown_report(result,source_name,episodes=episodes,blast=blast,changes=change_results); html_report=build_html_report(markdown); json_report=build_json_report(result,source_name); executive_payload={"fingerprint":summary["fingerprint"],"severity":summary["severity"],"health_score":summary["health_score"],"root_cause":top_cause,"actions":actions}
    snapshot=st.columns(4); snapshot_items=[("Severity",summary["severity"],"Incident classification","⚠",severity_color(summary["severity"]),None),("Health",summary["health_score"],health_band(summary["health_score"]),"♥","#39dcff",summary["health_score"]),("Fingerprint",summary["fingerprint"],"Stable incident signature","⌁","#a06dff",None),("Leading cause",top_cause,"Evidence-ranked hypothesis","◉","#ff70d6",None)]
    for column,item in zip(snapshot,snapshot_items):
        with column: metric_card(*item)
    section_header("Investigation package","Download every report format","HTML for sharing, JSON for automation, CSV for deeper analysis.")
    buttons=st.columns(5); buttons[0].download_button("Markdown",markdown,file_name=f"incident-{summary['fingerprint']}.md",mime="text/markdown",use_container_width=True); buttons[1].download_button("HTML",html_report,file_name=f"incident-{summary['fingerprint']}.html",mime="text/html",use_container_width=True); buttons[2].download_button("JSON",json_report,file_name=f"incident-{summary['fingerprint']}.json",mime="application/json",use_container_width=True); buttons[3].download_button("Events CSV",frame.to_csv(index=False).encode("utf-8"),file_name=f"events-{summary['fingerprint']}.csv",mime="text/csv",use_container_width=True); buttons[4].download_button("Executive JSON",json.dumps(executive_payload,indent=2),file_name=f"executive-{summary['fingerprint']}.json",mime="application/json",use_container_width=True)
    with st.expander("Preview full Markdown report"): st.markdown(markdown)
