from __future__ import annotations

import base64
import html
import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics import control_profile, control_snapshot, first_kill_summary
from src.awpy_adapter import load_normalized_bundle
from src.map_geometry import project_frame, radar_image_path
from src.replay import (
    UTILITY_LABELS,
    entry_conversion_summary,
    movement_trails,
    position_snapshot,
    round_kills,
    round_utility,
    score_after_round,
)
from src.round_timeline import build_round_timeline, render_round_timeline
from src.tactics import (
    AREA_GROUP,
    AREA_LABEL,
    ZONE_LABEL,
    build_tactical_findings,
    default_formation_summary,
    opening_contact_evidence,
    round_routes,
    rounds_for_side,
    shape_timeline,
    shape_transitions,
)
from src.team_map_series import series_evidence_summary
from src.team_map_comparison import (
    comparison_evidence,
    compare_opening_profiles,
    opening_profile_for_comparison,
)
from src.loadout_timeline import loadout_payload_for_round
from src.economy import ECONOMY_LABELS, ECONOMY_LABEL_ZH, classify_team_economy
from src.utility_efficiency import utility_efficiency_summary, utility_outcomes
from src.utility_labels import smoke_landing_annotations


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed" / "furia-falcons-mirage"
SHOWCASE_BUNDLE_DIR = BASE_DIR / "data" / "showcase" / "furia-falcons-mirage"
T_COLOR = "#F0AA3C"
CT_COLOR = "#4DA3FF"
KILL_COLOR = "#FF5F65"
UTILITY_COLORS = {
    "smoke": "#AAB4C2",
    "flash": "#FFE47A",
    "molotov": "#FF7B3E",
    "he": "#8ED081",
    "decoy": "#B990FF",
}

WEAPON_NAMES = {
    "ak47": "AK-47",
    "awp": "AWP",
    "deagle": "沙漠之鹰",
    "elite": "双持贝瑞塔",
    "famas": "FAMAS",
    "fiveseven": "Five-SeveN",
    "galilar": "Galil AR",
    "glock": "Glock-18",
    "knife_m9_bayonet": "M9 刺刀",
    "m4a1": "M4A4",
    "m4a1_silencer": "M4A1-S",
    "mp7": "MP7",
    "tec9": "Tec-9",
    "usp_silencer": "USP-S",
}


def weapon_name(internal: str) -> str:
    return WEAPON_NAMES.get(internal, internal)


st.set_page_config(page_title="CS Tactical Lens", page_icon="◎", layout="wide")

# ──────────────────────────────────────────────────────────────────────
# VISUAL — 战术指挥中心 / 赛事转播风格
# 只改动布局、CSS、字体、间距、颜色、图标和响应式
# ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800;900&display=swap');

  :root {
    --bg:      #080b0f;
    --surface: #0e131b;
    --surface2:#171e28;
    --border:  #1c2330;
    --border2: #293040;
    --text:    #e1e7ef;
    --muted:   #78869a;
    --dim:     #4b5769;
    --t:       #f0aa3c;
    --ct:      #4da3ff;
    --kill:    #ff5f65;
    --green:   #47c97e;
    --font:    'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                'PingFang SC','Microsoft YaHei','Noto Sans SC', sans-serif;
    --mono:    'JetBrains Mono','SF Mono','Cascadia Code',ui-monospace,Consolas,monospace;
  }

  /* ── base ── */
  .stApp {
    background: var(--bg);
    background-image:
      radial-gradient(ellipse at 25% 0%, rgba(240,170,60,0.025) 0%, transparent 55%),
      radial-gradient(ellipse at 75% 100%, rgba(77,163,255,0.025) 0%, transparent 55%);
    color: var(--text);
    font-family: var(--font);
  }
  .block-container {
    max-width: 1640px;
    padding: 0.75rem 2rem 3rem;
  }
  [data-testid="stSidebar"] {
    background: #0b0f14;
    border-right: 1px solid var(--border);
  }
  [data-testid="stSidebar"] * { color: var(--text); }
  [data-testid="stSidebar"] hr { border-color: var(--border); margin: 0.8rem 0; }

  h1, h2, h3, h4, h5, h6, p, label, .stCaptionContainer, .st-emotion-caption {
    color: var(--text);
  }

  /* ── streamlit chrome / header / toolbar ── */
  #MainMenu, .stAppDeployButton, div[data-testid="stDecoration"] { display: none; }
  header[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: none !important;
    height: 2.5rem !important;
    min-height: 2.5rem !important;
    overflow: visible !important;
  }
  /* Keep Streamlit's sidebar expand/collapse control available.  The old
     blanket header/toolbar hide made the sidebar impossible to reopen. */
  header[data-testid="stHeader"] > div,
  header[data-testid="stHeader"] nav {
    display: flex !important;
    visibility: visible !important;
  }
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 1000000 !important;
  }
  [data-testid="stToolbar"] { display: flex !important; }
  div[data-testid="stToolbar"] { display: flex !important; }
  section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.75rem;
  }

  /* ── typography ── */
  h1 {
    font-family: var(--font);
    font-weight: 800;
    font-size: 1.45rem;
    letter-spacing: -0.025em;
    margin: 0 0 0.05rem;
  }
  h2 { font-size: 1.05rem; font-weight: 700; letter-spacing: -0.01em; }
  h3 { font-size: 0.88rem; font-weight: 600; color: var(--muted); }

  /* ── brand kicker ── */
  .kicker {
    display: flex; align-items: center; gap: 0.45rem;
    color: var(--dim); font: 600 0.58rem/1.2 var(--mono);
    letter-spacing: 0.24em; text-transform: uppercase; margin-bottom: 0.15rem;
  }
  .kicker .dot {
    display: inline-block; width: 5px; height: 5px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 10px rgba(71,201,126,0.75);
  }

  /* ══════════════════════════════════════════════════════════════════
     SCOREBOARD — 赛事转播覆盖层风格
     ══════════════════════════════════════════════════════════════════ */
  .scoreboard {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: stretch;
    background: #0c1118;
    border: 1px solid var(--border);
    margin: 0.4rem 0 1rem;
    position: relative;
  }
  .scoreboard::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #303a48, #78869a 50%, #303a48);
  }
  .team-block {
    display: flex; align-items: center; gap: 1rem;
    padding: 0.75rem 1.25rem;
  }
  .team-block.right { justify-content: flex-end; text-align: right; }
  .team-info .team-label {
    color: var(--dim); font: 600 0.52rem var(--mono);
    letter-spacing: 0.2em; text-transform: uppercase;
  }
  .team-info .team-name {
    color: #ecf1f7; font-weight: 800; font-size: 1.05rem;
    letter-spacing: 0.04em;
  }
  .team-score-num {
    font: 800 2.3rem/1 var(--mono);
    letter-spacing: -0.04em;
  }
  /* 最终比分跨越上下半场，不使用 T/CT 阵营色。 */
  .team-score-num.t, .team-score-num.ct { color: #eef3f8; }

  .match-badge {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 0.45rem 1.2rem;
    border-left: 1px solid var(--border);
    border-right: 1px solid var(--border);
    text-align: center; white-space: nowrap;
  }
  .match-badge .map-name {
    color: #fff; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.1em;
    font-family: var(--mono);
  }
  .match-badge .match-meta {
    color: var(--dim); font: 0.55rem var(--mono);
    letter-spacing: 0.06em; margin-top: 0.12rem;
  }

  /* ── section label ── */
  .section-label {
    color: var(--dim);
    font: 600 0.62rem var(--mono);
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin: 0 0 0.5rem;
  }

  /* ── radio tab strip ── */
  div[role="radiogroup"] {
    gap: 0;
    background: #0b0f14;
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
    display: inline-flex;
  }
  div[role="radiogroup"] label {
    background: transparent !important;
    border: none !important;
    border-radius: 0;
    padding: 0.4rem 1.1rem;
    margin: 0;
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s;
  }
  div[role="radiogroup"] label:not(:last-child) {
    border-right: 1px solid var(--border) !important;
  }
  div[role="radiogroup"] label:has(input:checked) {
    background: #19212b !important;
    color: #fff;
  }

  /* ── plotly chart ── */
  .stPlotlyChart {
    border: 1px solid var(--border);
    border-radius: 3px;
    overflow: hidden;
  }

  /* ── controls row ── */
  .ctrl-label {
    color: var(--dim) !important;
    font: 600 0.58rem var(--mono) !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    margin-bottom: 0.2rem !important;
  }
  div[data-testid="stSelectbox"] label,
  div[data-testid="stMultiSelect"] label {
    font-size: 0.7rem !important;
    font-weight: 500 !important;
  }
  div[data-baseweb="select"] > div,
  div[data-baseweb="multi-select"] > div {
    background: #0b0f14 !important;
    border-color: var(--border) !important;
    border-radius: 3px !important;
    min-height: 32px !important;
  }
  div[data-baseweb="select"] input,
  div[data-baseweb="multi-select"] input {
    font-size: 0.8rem !important;
  }
  /* slider */
  div[data-testid="stSlider"] label {
    font-size: 0.7rem !important;
  }
  div[data-testid="stSlider"] div[data-baseweb="slider"] {
    padding-top: 0.3rem !important;
  }
  /* toggle */
  div[data-testid="stToggle"] label {
    font-size: 0.78rem !important;
  }

  /* ── round detail event panel ── */
  .round-panel {
    background: #0c1118;
    border: 1px solid var(--border);
    border-left: 3px solid var(--border2);
    padding: 0.9rem 1rem;
    height: 100%;
  }
  .round-header {
    display: flex; justify-content: space-between; align-items: flex-end;
    padding-bottom: 0.6rem; border-bottom: 1px solid var(--border);
    margin-bottom: 0.65rem;
  }
  .round-header .round-no {
    color: var(--dim); font: 600 0.6rem var(--mono); letter-spacing: 0.14em;
  }
  .round-header .winner {
    color: #fff; font-weight: 700; font-size: 0.95rem;
    margin-top: 0.12rem;
  }
  .round-header .running-score {
    color: #fff; font: 800 1.3rem var(--mono); letter-spacing: -0.03em;
  }

  /* event feed — 时间线风格 */
  .event-feed-label {
    color: var(--dim); font: 600 0.55rem var(--mono); letter-spacing: 0.18em;
    text-transform: uppercase; margin-bottom: 0.35rem;
  }
  .event-feed {
    max-height: 560px;
    overflow-y: auto;
    padding-right: 0.35rem;
    scrollbar-color: #3d4756 #0c1118;
    scrollbar-width: thin;
  }
  .event {
    display: grid; grid-template-columns: 36px 14px 1fr;
    gap: 0.3rem; padding: 0.42rem 0;
    border-bottom: 1px solid #161d27;
    align-items: start;
  }
  .event:last-child { border-bottom: none; }
  .event-time {
    color: var(--dim); font: 0.65rem var(--mono);
    padding-top: 0.08rem; text-align: right;
  }
  .event-track {
    display: flex; flex-direction: column; align-items: center; gap: 0;
    height: 100%; min-height: 28px;
  }
  .event-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--dim); z-index: 1;
    flex-shrink: 0; margin-top: 3px;
  }
  .event-line {
    width: 1px; flex: 1; background: #1a212c;
    min-height: 20px;
  }
  .event-body {
    color: #ccd3dc; font-size: 0.8rem; line-height: 1.4;
    padding-top: 0.02rem;
  }
  .event-body b { color: #fff; font-weight: 600; }
  .event.kill .event-dot {
    background: var(--kill);
    box-shadow: 0 0 8px rgba(255,95,101,0.5);
    width: 7px; height: 7px; border-radius: 2px;
  }
  .event.kill .event-body { color: #ebd5d5; }
  .event.utility .event-dot { background: var(--t); }
  .event.utility .event-body { color: #dcd8c8; }
  .event.bomb .event-dot { background: var(--green); }
  .event.bomb .event-body { color: #b8e6c8; }
  .event.smoke .event-dot {
    background: #AAB4C2;
    box-shadow: 0 0 6px rgba(170,180,194,0.4);
  }
  .event.smoke .event-body { color: #d0d8e0; }

  .smoke-disclaimer {
    color: var(--dim); font-size: 0.7rem; padding: 0.2rem 0 0.5rem;
    font-style: italic; border-bottom: 1px solid var(--border);
    margin-bottom: 0.4rem;
  }

  .empty-event {
    color: var(--dim); font-size: 0.8rem; padding: 0.8rem 0;
    font-style: italic;
  }

  /* ── round rail (回合进度条) ── */
  .round-rail {
    display: flex; gap: 2px; align-items: flex-end;
    padding: 0.8rem 0 0.15rem; overflow-x: auto;
  }
  .round-chip {
    flex: 1; min-width: 20px; height: 24px;
    display: flex; align-items: center; justify-content: center;
    color: rgba(12,16,20,0.85);
    font: 700 0.55rem var(--mono);
    border-radius: 2px;
    opacity: 0.7;
    transition: all 0.12s;
  }
  .round-chip.active {
    height: 32px; opacity: 1;
    outline: 2px solid #fff; outline-offset: 1px;
    z-index: 2;
  }
  .round-chip.t { background: var(--t); }
  .round-chip.ct { background: var(--ct); }

  /* ── conversion rows ── */
  .conversion-row {
    display: grid; grid-template-columns: 120px 1fr 75px;
    align-items: center; gap: 0.7rem;
    padding: 0.6rem 0; border-bottom: 1px solid var(--border);
  }
  .conversion-name { color: #fff; font-weight: 600; font-size: 0.85rem; }
  .conversion-track { height: 5px; background: #181f29; border-radius: 20px; overflow: hidden; }
  .conversion-fill { height: 100%; background: linear-gradient(90deg,#3b82f6,#60a5fa); border-radius: 20px; }
  .conversion-value { color: #ccd3dc; font: 0.68rem var(--mono); text-align: right; }

  /* ── insights ── */
  .insight {
    border-left: 3px solid #475569;
    background: #0c1118;
    padding: 0.65rem 1rem;
    margin: 0.45rem 0;
    color: #ccd3dc;
    font-size: 0.85rem;
    line-height: 1.55;
    border-radius: 0 3px 3px 0;
  }
  .tactical-finding {
    background: linear-gradient(100deg, #0c1118, #101722);
    border: 1px solid var(--border);
    border-left: 3px solid var(--ct);
    padding: 0.8rem 1rem;
    margin: 0.65rem 0 0.35rem;
  }
  .tactical-finding .finding-kicker {
    color: var(--dim); font: 600 0.55rem var(--mono);
    letter-spacing: 0.16em; text-transform: uppercase;
  }
  .tactical-finding .finding-title {
    color: #fff; font-size: 0.95rem; font-weight: 700; margin: 0.18rem 0 0.28rem;
  }
  .tactical-finding .finding-summary {
    color: #ccd5df; font-size: 0.84rem; line-height: 1.55;
  }
  .tactical-finding .finding-sample {
    color: var(--dim); font: 0.62rem var(--mono); margin-top: 0.45rem;
  }

  .scope-line {
    display: flex; gap: 0.55rem; align-items: flex-start;
    padding: 0.3rem 0; color: #c5cdd6; font-size: 0.82rem;
  }
  .scope-mark { color: var(--green); font-weight: 800; }
  .scope-mark.out { color: var(--dim); }

  /* ── dataframe / data grid 暗色主题 ── */
  [data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 3px;
    overflow: hidden;
    background: #0c1118 !important;
  }
  [data-testid="stDataFrame"] div {
    background: #0c1118 !important;
  }
  [data-testid="stDataFrame"] table {
    font-family: var(--mono);
    font-size: 0.75rem;
  }
  /* Glide Data Grid — 强制暗色变量，覆盖主题默认值 */
  [data-testid="stDataFrame"] {
    --gdg-bg-cell: #0c1118;
    --gdg-bg-header: #131a23;
    --gdg-bg-bubble: #1a222d;
    --gdg-border-color: #1c2330;
    --gdg-text-dark: #e1e7ef;
    --gdg-text-medium: #78869a;
    --gdg-text-light: #4b5769;
    --gdg-text-group-header: #78869a;
    --gdg-accent-color: #4da3ff;
    --gdg-accent-light: rgba(77,163,255,0.12);
    --gdg-link-color: #4da3ff;
    --gdg-font-family: var(--mono);
    --gdg-header-font-style: 600 0.75rem var(--mono);
    --gdg-editor-font-size: 0.75rem;
  }
  /* Glide Data Grid canvas */
  [data-testid="stDataFrame"] canvas {
    background: #0c1118 !important;
  }
  /* grid header row */
  [data-testid="stDataFrame"] .gdg-header,
  [data-testid="stDataFrame"] [class*="header"],
  [data-testid="stDataFrame"] thead tr,
  [data-testid="stDataFrame"] th {
    background: #131a23 !important;
    color: var(--muted) !important;
    border-bottom: 1px solid var(--border) !important;
    font-weight: 600 !important;
  }
  /* HTML table fallback cells */
  [data-testid="stDataFrame"] tbody tr {
    background: #0c1118 !important;
  }
  [data-testid="stDataFrame"] tbody tr:nth-child(even) {
    background: #0e141c !important;
  }
  [data-testid="stDataFrame"] td {
    color: var(--text) !important;
    border-bottom: 1px solid #181f29 !important;
    padding: 0.3rem 0.6rem !important;
  }
  /* hover and selected state */
  [data-testid="stDataFrame"] tbody tr:hover td {
    background: #161e28 !important;
  }
  [data-testid="stDataFrame"] tbody tr th,
  [data-testid="stDataFrame"] thead th {
    background: #131a23 !important;
    color: var(--muted) !important;
    font-weight: 600 !important;
  }
  /* row index column */
  [data-testid="stDataFrame"] tbody tr th {
    color: var(--dim) !important;
    border-right: 1px solid var(--border) !important;
  }
  /* scrollbar inside grid */
  [data-testid="stDataFrame"] ::-webkit-scrollbar {
    width: 6px; height: 6px;
  }
  [data-testid="stDataFrame"] ::-webkit-scrollbar-track {
    background: #0a0d12;
  }
  [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb {
    background: #2a3340;
    border-radius: 3px;
  }

  /* Stable HTML tables for compact evidence summaries.  Streamlit's canvas
     grid can turn blank when global dark-mode CSS overrides its paint layer. */
  .tactical-table-wrap {
    width: 100%; overflow-x: auto; border: 1px solid var(--border);
    border-radius: 3px; background: #0c1118;
  }
  .tactical-table {
    width: 100%; border-collapse: collapse; font-family: var(--font);
    font-size: 0.84rem; line-height: 1.5; color: var(--text); white-space: nowrap;
  }
  .tactical-table thead th {
    padding: 0.68rem 0.72rem; text-align: left; color: var(--muted);
    background: #131a23; border-bottom: 1px solid var(--border);
    font-size: 0.82rem; font-weight: 700; letter-spacing: 0.01em;
  }
  .tactical-table tbody td {
    padding: 0.68rem 0.72rem; color: #dfe6ef;
    border-bottom: 1px solid #181f29; background: #0c1118;
  }
  .tactical-table tbody tr:nth-child(even) td { background: #0e141c; }
  .tactical-table tbody tr:last-child td { border-bottom: 0; }
  .tactical-table tbody tr:hover td { background: #161e28; }

  /* ── alerts / success / info ── */
  .stAlert {
    background: #0e131b; border-color: var(--border);
    color: var(--text); border-radius: 3px; font-size: 0.82rem;
  }
  .stSuccess { background: rgba(71,201,126,0.07); border-color: var(--green); }
  .stInfo    { background: rgba(77,163,255,0.07); border-color: var(--ct); }

  /* ── sidebar ── */
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.82rem;
  }
  .sidebar-brand {
    font: 600 0.55rem var(--mono); letter-spacing: 0.22em;
    color: var(--dim); text-transform: uppercase;
  }

  /* ── caption ── */
  .stCaptionContainer, [data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
    font: 0.8rem/1.6 var(--font) !important;
    overflow-wrap: anywhere;
    word-break: break-word;
  }

  /* ── metrics (复盘报告首杀统计) ── */
  [data-testid="stMetric"] {
    background: #0c1118;
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.7rem 0.9rem;
  }
  [data-testid="stMetric"] > div {
    background: transparent !important;
  }
  [data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font: 600 0.6rem var(--mono) !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0;
  }
  [data-testid="stMetricValue"] {
    color: #ecf1f7 !important;
    font: 800 1.35rem var(--mono) !important;
    letter-spacing: -0.03em;
    padding: 0;
  }
  [data-testid="stMetricDelta"] {
    color: var(--dim) !important;
    font: 0.68rem var(--mono) !important;
  }

  /* ── buttons (证据跳转 / 回看回合) ── */
  .stButton button {
    background: #111822 !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    color: #c8d0da !important;
    font: 500 0.75rem var(--font) !important;
    padding: 0.35rem 0.7rem !important;
    transition: all 0.12s;
    cursor: pointer;
  }
  .stButton button:hover {
    border-color: #4da3ff !important;
    background: #172333 !important;
    color: #e8edf4 !important;
  }
  .stButton button:active {
    border-color: #3b82f6 !important;
    background: #1e2d42 !important;
  }
  /* 证据折叠区内的按钮更紧凑 */
  div[data-testid="stExpander"] .stButton button {
    font-size: 0.7rem !important;
    padding: 0.25rem 0.5rem !important;
  }

  /* ── tactical-finding 卡片 ── */
  .tactical-finding {
    background: #0c1118;
    border: 1px solid var(--border);
    border-left: 3px solid #475569;
    border-radius: 0 3px 3px 0;
    padding: 0.8rem 1rem;
    margin: 0.45rem 0;
  }
  .finding-kicker {
    color: var(--dim);
    font: 600 0.55rem var(--mono);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 0.15rem;
  }
  .finding-title {
    color: #ecf1f7;
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 0.2rem;
  }
  .finding-summary {
    color: #ccd3dc;
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .finding-sample {
    color: var(--dim);
    font: 0.7rem var(--mono);
    margin-top: 0.3rem;
  }

  /* ── scope / boundary 右侧卡片 ── */
  .scope-card {
    background: #0c1118;
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1rem 1.1rem;
  }
  .scope-card h2 {
    font-size: 0.95rem;
    font-weight: 700;
    color: #ecf1f7;
    margin-bottom: 0.6rem;
  }

  /* ── expander (证据折叠区) ── */
  div[data-testid="stExpander"] {
    border-color: var(--border) !important;
    background: transparent !important;
  }
  div[data-testid="stExpander"] > div[data-testid="stExpander"] > div:first-child {
    background: #0e131b !important;
    border-radius: 3px !important;
  }
  div[data-testid="stExpander"] span {
    color: var(--text) !important;
    font-size: 0.82rem;
  }

  /* ── 多场样本筛选控件与页面一致 ── */
  .st-key-series_match_filter [data-baseweb="select"] > div {
    background: #0b0f14 !important;
    border-color: var(--border) !important;
    min-height: 32px !important;
  }
  .st-key-series_match_filter label {
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: #aeb9c8 !important;
  }

  /* ── prevent horizontal overflow ── */
  .block-container {
    overflow-x: hidden;
  }
  .stPlotlyChart, [data-testid="stDataFrame"], .tactical-table-wrap {
    max-width: 100%;
  }
  .tactical-table td, .tactical-table th {
    white-space: normal;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  /* ── 多场样本摘要统计卡 ── */
  .series-summary {
    display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem;
    background: #0c1118;
    border: 1px solid var(--border);
    border-left: 3px solid var(--border2);
    border-radius: 0 3px 3px 0;
    padding: 0.7rem 1.2rem;
    margin: 0.5rem 0 1.2rem;
    align-items: baseline;
  }
  .series-summary .stat {
    display: flex; align-items: baseline; gap: 0.35rem;
  }
  .series-summary .stat-value {
    color: #ecf1f7;
    font: 800 1.15rem var(--mono);
    letter-spacing: -0.02em;
  }
  .series-summary .stat-label {
    color: #aeb9c8;
    font: 600 0.78rem/1.45 var(--font);
    letter-spacing: 0;
  }
  .series-summary .stat-divider {
    color: var(--border);
    font: 0.62rem var(--mono);
    user-select: none;
  }

  /* ── 系列证据摘要卡片 ── */
  .series-summary-card {
    display: flex; flex-wrap: wrap; gap: 0.4rem 0.8rem;
    align-items: baseline;
    background: #0c1118;
    border: 1px solid var(--border);
    border-left: 3px solid #475569;
    border-radius: 0 3px 3px 0;
    padding: 0.7rem 1rem;
    margin: 0.3rem 0 0.5rem;
  }
  .series-summary-card .ss-item {
    display: flex; align-items: baseline; gap: 0.3rem;
  }
  .series-summary-card .ss-value {
    color: #ecf1f7;
    font: 800 1.05rem var(--mono);
    letter-spacing: -0.02em;
  }
  .series-summary-card .ss-label {
    color: #aeb9c8;
    font: 600 0.78rem/1.45 var(--font);
    letter-spacing: 0;
  }
  .series-summary-card .ss-note {
    width: 100%;
    color: #ccd3dc;
    font-size: 0.82rem;
    line-height: 1.4;
    padding-top: 0.25rem;
    margin-top: 0.15rem;
    border-top: 1px solid var(--border);
  }
  .series-summary-card .ss-top-label {
    color: #aeb9c8;
    font: 600 0.78rem/1.45 var(--font);
    letter-spacing: 0;
  }

  /* ── 筛选摘要行 ── */
  .filter-summary {
    color: #d5dee9;
    font: 600 0.84rem/1.5 var(--font);
    padding: 0.42rem 0 0.36rem;
    letter-spacing: 0.02em;
  }

  /* ── 区块分隔线 ── */
  .section-divider {
    border: none; height: 1px;
    background: var(--border);
    margin: 1.4rem 0 1rem;
  }

  /* ── responsive fine-tune ── */
  @media (max-width: 1200px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .team-block { padding: 0.6rem 0.8rem; }
    .team-score-num { font-size: 1.9rem; }
    .match-badge { padding: 0.35rem 0.8rem; }
  }
  @media (max-width: 1100px) {
    .st-key-checkpoint_maps [data-testid="stHorizontalBlock"] {
      flex-wrap: wrap;
      align-items: flex-start;
    }
    .st-key-checkpoint_maps [data-testid="column"] {
      flex: 0 1 calc(50% - 0.5rem) !important;
      min-width: 290px;
    }
  }
  /* ── V3 跨队比较 ── */
  .v3-status-card {
    background: #0c1118;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem 1.2rem;
    margin: 0.75rem 0;
  }
  .v3-status-card .v3-team-row {
    display: flex; align-items: baseline; gap: 0.6rem;
    padding: 0.35rem 0;
    font-size: 0.85rem;
  }
  .v3-status-card .v3-team-name {
    font-weight: 600; min-width: 6rem; color: var(--text);
  }
  .v3-status-card .v3-status-ok {
    color: var(--green);
  }
  .v3-status-card .v3-status-pending {
    color: var(--t);
  }
  .v3-status-card .v3-status-missing {
    color: var(--kill);
  }
  .v3-threshold-box {
    background: #131a24;
    border: 1px dashed var(--border2);
    border-radius: 3px;
    padding: 0.75rem 1rem;
    margin: 0.75rem 0;
    font-size: 0.82rem;
    line-height: 1.6;
  }
  .v3-threshold-box .v3-threshold-title {
    font-weight: 600; color: var(--muted); margin-bottom: 0.3rem;
  }
  .v3-next-steps {
    background: #131a24;
    border-left: 3px solid var(--t);
    border-radius: 2px;
    padding: 0.7rem 1rem;
    margin: 0.75rem 0;
    font-size: 0.82rem;
    line-height: 1.6;
  }
  /* ── V3 占比差颜色 ── */
  .v3-delta-pos { color: var(--green); font-weight: 600; }
  .v3-delta-neg { color: var(--kill); font-weight: 600; }
  .v3-delta-zero { color: var(--muted); }
  /* ── V3 证据选择预览 ── */
  .v3-evidence-preview {
    background: #0c1118;
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.6rem 0.9rem;
    margin: 0.4rem 0 0.6rem;
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .v3-evidence-preview .v3-ev-label {
    color: var(--dim); font-size: 0.72rem;
  }
  /* ── V3 窄屏适配 ── */
  @media (max-width: 860px) {
    .v3-status-card .v3-team-row {
      flex-wrap: wrap; gap: 0.3rem;
    }
    .v3-status-card .v3-team-name {
      min-width: 4rem;
    }
  }
  @media (max-width: 720px) {
    .st-key-checkpoint_maps [data-testid="column"] {
      flex: 1 1 100% !important;
      min-width: 0;
    }
    /* V3 表格在窄屏下启用水平滚动 */
    .tactical-table-wrap {
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }
    /* V3 摘要指标两列堆叠 */
    [data-testid="column"] .stMetric {
      padding: 0.3rem 0;
    }
  }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_match(bundle_path: str | None = None):
    # Bump this marker whenever the normalized bundle schema changes so a
    # running Streamlit process cannot reuse a MatchData object from an older schema.
    _bundle_schema_version = 2
    del _bundle_schema_version
    path = Path(bundle_path) if bundle_path else DATA_DIR
    return load_normalized_bundle(path)


@st.cache_data
def radar_uri(map_name: str) -> str:
    encoded = base64.b64encode(radar_image_path(map_name).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@st.cache_data(show_spinner=False)
def tactical_findings(team: str):
    return build_tactical_findings(load_match(), team)


@st.cache_data(show_spinner=False)
def utility_outcome_data() -> pd.DataFrame:
    return utility_outcomes(load_match())


_COVERAGE_TIER_LABELS = {
    "standard": "标准样本",
    "exploratory": "探索样本",
    "insufficient": "样本不足",
}


def _research_team_key(team: object) -> str:
    """Collapse display-only prefixes so one organisation is never self-compared."""
    value = str(team).strip().casefold()
    return value[5:] if value.startswith("team ") else value


def _research_profile_label(profile: dict[str, str | int]) -> str:
    """Keep the selector compact while making the evidence scope visible."""
    team = str(profile["team"])
    matches = int(profile["match_count"])
    tier = str(profile.get("coverage_tier", ""))
    if tier:
        return f"{team} · {matches} 场 · {_COVERAGE_TIER_LABELS.get(tier, tier)}"
    return f"{team} · {profile['season']}"


def available_research_profiles() -> tuple[dict[str, str | int], ...]:
    """Discover only complete, locally auditable team-map series.

    A profile becomes selectable only when its manifest, metadata and opening
    sample artifacts are all present.  When the V4 corpus has the same
    organisation/map as an older hand-curated profile, the corpus version wins
    so a team cannot appear twice under two source-era names.
    """
    profiles: list[dict[str, str | int]] = []
    for manifest_path in sorted((BASE_DIR / "data" / "series").glob("*.json")):
        if manifest_path.name.endswith(".example.json"):
            continue
        series_dir = manifest_path.with_suffix("")
        metadata_path = series_dir / "series_metadata.json"
        samples_path = series_dir / "precontact_opening_samples.csv"
        profile_path = series_dir / "precontact_opening_profile.csv"
        if not (metadata_path.is_file() and samples_path.is_file() and profile_path.is_file()):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            continue
        team = str(manifest.get("team", "")).strip()
        map_name = str(manifest.get("map", "")).strip()
        if not team or not map_name:
            continue
        profiles.append(
            {
                "id": manifest_path.stem,
                "team": team,
                "map": map_name,
                "season": str(manifest.get("season", "")).strip(),
                "manifest": str(manifest_path),
                "series_dir": str(series_dir),
                "match_count": int(metadata.get("match_count", 0)),
                "eligible_samples": int(metadata.get("eligible_precontact_samples", 0)),
                "coverage_tier": str(manifest.get("coverage_tier", "")).strip(),
            }
        )
    corpus_keys = {
        (_research_team_key(profile["team"]), str(profile["map"]).casefold())
        for profile in profiles
        if str(profile["id"]).startswith("iem-cologne-2026-")
    }
    if corpus_keys:
        profiles = [
            profile for profile in profiles
            if str(profile["id"]).startswith("iem-cologne-2026-")
            or (_research_team_key(profile["team"]), str(profile["map"]).casefold()) not in corpus_keys
        ]
    return tuple(profiles)


@st.cache_data(show_spinner=False)
def load_research_series(
    series_dir_value: str,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    """Load one already-validated team-map profile without reparsing Demos."""
    series_dir = Path(series_dir_value)
    metadata = json.loads((series_dir / "series_metadata.json").read_text(encoding="utf-8"))
    samples = pd.read_csv(series_dir / "precontact_opening_samples.csv")
    profile = pd.read_csv(series_dir / "precontact_opening_profile.csv")
    return metadata, samples, profile


@st.cache_data(show_spinner=False)
def research_replay_bundle_index(manifest_paths: tuple[str, ...]) -> dict[str, str]:
    """Resolve evidence bundles for the currently selected research profiles."""
    index: dict[str, str] = {}
    for manifest_value in manifest_paths:
        manifest_path = Path(manifest_value)
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for entry in raw.get("matches", []):
            if not isinstance(entry, dict):
                continue
            match_id = str(entry.get("id", "")).strip()
            bundle_value = str(entry.get("bundle", "")).strip()
            if not match_id or not bundle_value:
                continue
            bundle = Path(bundle_value)
            if not bundle.is_absolute():
                bundle = (manifest_path.parent / bundle).resolve()
            if bundle.is_dir():
                index[match_id] = str(bundle)
    return index


@st.cache_data(show_spinner=False)
def _get_smoke_annotations(_data: object) -> pd.DataFrame:
    """Cache smoke landing annotations so they're not recomputed on every interaction."""
    return smoke_landing_annotations(_data)  # type: ignore[arg-type]


def fmt_time(seconds: float) -> str:
    value = max(0, int(seconds))
    return f"{value // 60}:{value % 60:02d}"


def render_dark_table(frame: pd.DataFrame) -> None:
    """Render small evidence tables without relying on a canvas data grid."""
    table = frame.fillna("—").to_html(
        index=False,
        border=0,
        classes="tactical-table",
        escape=True,
    )
    st.markdown(f'<div class="tactical-table-wrap">{table}</div>', unsafe_allow_html=True)


def zone_label_for_side(zone: str, side: str) -> str:
    if zone == "OTHER":
        return "匪家" if side == "T" else "警家"
    return ZONE_LABEL.get(zone, zone)


def zone_sequence_label(sequence: str, side: str) -> str:
    return " → ".join(
        zone_label_for_side(zone, side) for zone in sequence.split("→")
    )


ECONOMY_FILTER_OPTIONS = [ECONOMY_LABEL_ZH[label] for label in ECONOMY_LABELS
                          if label not in ("mixed", "unknown")]

_ECONOMY_TO_ENGLISH = {v: k for k, v in ECONOMY_LABEL_ZH.items()}

# Items to skip in economy evidence panel inventory display
# Observation seconds per economy label (as established by V3.2 data contract)
_OBSERVATION_SECONDS: dict[str, int] = {
    "pistol": 15,
    "full_buy": 20,
    "half_buy": 12,
    "force_buy": 15,
    "eco": 15,
}

def _obs_label(economy_label: str | None) -> str:
    sec = _OBSERVATION_SECONDS.get(economy_label, 20)
    return f"{sec} 秒"


_INVENTORY_SKIP = {    "knife", "karambit", "m9 bayonet", "butterfly knife", "bayonet",
    "flip knife", "gut knife", "huntsman knife", "falchion knife",
    "shadow daggers", "navaja knife", "stiletto knife", "talon knife",
    "skeleton knife", "paracord knife", "survival knife", "nomad knife",
    "classic knife", "c4", "c4 explosive",
}


def jump_to_replay(round_num: int, second: float) -> None:
    """Widget callback: reopen a finding at its exact radar evidence."""
    st.session_state["_pending_screen"] = "回放"
    st.session_state["selected_round"] = int(round_num)
    st.session_state[f"time_r{int(round_num)}"] = int(round(float(second)))


def jump_to_series_replay(bundle_path: str, round_num: int) -> None:
    """Open a concrete cross-series evidence row in its local bundle."""
    st.session_state["active_replay_bundle"] = bundle_path
    st.session_state.pop("manual_replay_bundle", None)
    # Navigation is applied before the next run's radio widget is created;
    # Streamlit otherwise rejects changing a widget key after instantiation.
    st.session_state["_pending_screen"] = "回放"
    st.session_state["selected_round"] = int(round_num)
    st.session_state[f"time_r{int(round_num)}"] = 0


def radar_base(map_name: str, *, height: int = 676) -> go.Figure:
    fig = go.Figure(go.Image(source=radar_uri(map_name)))
    fig.update_xaxes(range=[0, 1024], visible=False, constrain="domain")
    fig.update_yaxes(range=[1024, 0], visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0d1118",
        hoverlabel=dict(
            bgcolor="#171e28",
            bordercolor="#3d4756",
            font=dict(color="#e1e7ef", family="Inter, sans-serif", size=13),
        ),
        showlegend=False,
        dragmode="pan",
    )
    return fig


def add_player_traces(fig: go.Figure, frame: pd.DataFrame, *, labels: bool) -> None:
    for side, color in (("T", T_COLOR), ("CT", CT_COLOR)):
        rows = frame.loc[frame["side"] == side]
        if rows.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=rows.radar_x,
                y=rows.radar_y,
                mode="markers+text" if labels else "markers",
                text=rows.player,
                textposition="top center",
                textfont=dict(color="#e8edf4", size=11, family="Inter, sans-serif"),
                customdata=rows[["player", "team", "health", "area"]].to_numpy(),
                marker=dict(size=15, color=color, line=dict(width=2, color="#080b0f")),
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} · "
                + side
                + "<br>HP %{customdata[2]} · %{customdata[3]}<extra></extra>",
            )
        )


def replay_figure(
    data, round_num: int, second: float, layers: list[str], labels: bool
) -> go.Figure:
    fig = radar_base(data.map_name)

    if "移动轨迹" in layers:
        trails = project_frame(
            movement_trails(data, round_num, second), data.map_name
        )
        for (player, side), rows in trails.groupby(["player", "side"]):
            color = T_COLOR if side == "T" else CT_COLOR
            fig.add_trace(
                go.Scatter(
                    x=rows.radar_x,
                    y=rows.radar_y,
                    mode="lines",
                    line=dict(color=color, width=2),
                    opacity=0.3,
                    hoverinfo="skip",
                )
            )

    if "道具落点" in layers:
        utility = project_frame(
            round_utility(data, round_num, second), data.map_name
        )
        for utility_type, rows in utility.groupby("grenade_type"):
            color = UTILITY_COLORS.get(utility_type, "#cbd4df")
            fig.add_trace(
                go.Scatter(
                    x=rows.radar_x,
                    y=rows.radar_y,
                    mode="markers",
                    customdata=rows[
                        ["utility_label", "thrower", "team", "seconds"]
                    ].to_numpy(),
                    marker=dict(
                        size=11,
                        color=color,
                        symbol="circle-open",
                        line=dict(width=2, color=color),
                    ),
                    hovertemplate="<b>%{customdata[0]}落点</b><br>%{customdata[1]} · %{customdata[2]}<br>%{customdata[3]:.1f} 秒<extra></extra>",
                )
            )

    if "击杀位置" in layers:
        kills = round_kills(data, round_num, second).copy()
        x_col = "victim_x" if "victim_x" in kills else "x"
        y_col = "victim_y" if "victim_y" in kills else "y"
        kills = project_frame(kills, data.map_name, x=x_col, y=y_col)
        if not kills.empty:
            fig.add_trace(
                go.Scatter(
                    x=kills.radar_x,
                    y=kills.radar_y,
                    mode="markers",
                    customdata=kills[
                        ["attacker", "victim", "weapon", "seconds"]
                    ].to_numpy(),
                    marker=dict(
                        size=[18 if first else 13 for first in kills.is_first_kill],
                        color=KILL_COLOR,
                        symbol="x",
                        line=dict(width=3, color=KILL_COLOR),
                    ),
                    hovertemplate="<b>%{customdata[0]} → %{customdata[1]}</b><br>%{customdata[2]} · %{customdata[3]:.1f} 秒<extra></extra>",
                )
            )

    snapshot = project_frame(
        position_snapshot(data, round_num, second), data.map_name
    )
    add_player_traces(fig, snapshot, labels=labels)
    return fig


@st.cache_data(show_spinner=False)
def playback_payload(
    round_num: int,
    layers: tuple[str, ...],
    labels: bool,
    bundle_path: str | None = None,
    *,
    include_loadout: bool = False,
) -> dict[str, object]:
    """Compact 16 Hz samples; browser time is still driven by real wall-clock seconds."""
    data = load_match(bundle_path)
    positions = data.positions.loc[data.positions["round"] == round_num].sort_values("seconds").copy()
    positions["sample_bin"] = (positions["seconds"] * 16).round().astype(int)
    positions = positions.drop_duplicates(["player", "sample_bin"], keep="last")
    positions = project_frame(positions, data.map_name)

    players = []
    for player, rows in positions.groupby("player", sort=False):
        rows = rows.sort_values("seconds")
        first = rows.iloc[0]
        players.append({
            "name": str(player),
            "team": str(first.team),
            "side": str(first.side),
            "path": [
                [round(float(row.seconds), 3), round(float(row.radar_x), 2), round(float(row.radar_y), 2), int(row.health)]
                for row in rows.itertuples()
            ],
        })

    utility_source = round_utility(data, round_num)
    utility_rows = project_frame(utility_source, data.map_name)
    utility_origins = project_frame(utility_source, data.map_name, x="throw_x", y="throw_y")
    if not utility_rows.empty:
        utility_rows["throw_radar_x"] = utility_origins["radar_x"].to_numpy()
        utility_rows["throw_radar_y"] = utility_origins["radar_y"].to_numpy()
    utilities = []
    if "道具落点" in layers:
        for row in utility_rows.itertuples():
            throw_second = float(row.seconds)
            land_second = getattr(row, "land_seconds", None)
            if land_second is None or pd.isna(land_second):
                distance = math.hypot(float(row.x) - float(row.throw_x), float(row.y) - float(row.throw_y))
                land_second = throw_second + min(2.5, max(0.35, distance / 900))
            effect_end = getattr(row, "effect_end_seconds", None)
            trajectory = []
            raw_trajectory = getattr(row, "trajectory", None)
            if isinstance(raw_trajectory, str) and raw_trajectory:
                trajectory_frame = pd.DataFrame(json.loads(raw_trajectory), columns=["seconds", "x", "y"])
                trajectory_frame = project_frame(trajectory_frame, data.map_name)
                trajectory = [
                    [round(float(point.seconds), 4), round(float(point.radar_x), 2), round(float(point.radar_y), 2)]
                    for point in trajectory_frame.itertuples()
                ]
            utilities.append({
                "t": round(throw_second, 3),
                "land": round(max(throw_second, float(land_second)), 3),
                "end": None if effect_end is None or pd.isna(effect_end) else round(float(effect_end), 3),
                "fromX": round(float(row.throw_radar_x), 2),
                "fromY": round(float(row.throw_radar_y), 2),
                "x": round(float(row.radar_x), 2),
                "y": round(float(row.radar_y), 2),
                "path": trajectory,
                "type": str(row.grenade_type),
                "label": str(row.utility_label),
                "thrower": str(row.thrower),
            })

    kill_rows = round_kills(data, round_num).copy()
    kill_x = "victim_x" if "victim_x" in kill_rows else "x"
    kill_y = "victim_y" if "victim_y" in kill_rows else "y"
    kill_rows = project_frame(kill_rows, data.map_name, x=kill_x, y=kill_y)
    kills = []
    if "击杀位置" in layers:
        kills = [
            {
                "t": round(float(row.seconds), 3),
                "x": round(float(row.radar_x), 2),
                "y": round(float(row.radar_y), 2),
                "attacker": str(row.attacker),
                "victim": str(row.victim),
                "weapon": weapon_name(str(row.weapon)),
                "first": bool(row.is_first_kill),
            }
            for row in kill_rows.itertuples()
        ]

    event_seconds = [item["land"] for item in utilities] + [item["t"] for item in kills]
    maximum = max(
        float(positions["seconds"].max()) if not positions.empty else 0,
        max(event_seconds, default=0),
    )
    round_row = data.rounds.loc[data.rounds["round"] == round_num].iloc[0]
    plant_second = round_row.get("bomb_plant_seconds")
    # Any replay with normalized loadout events gets the same OB-style HUD.
    # Evidence replay and manually opened replay must not have different
    # visual capabilities just because they entered through different pages.
    loadout_timeline = (
        loadout_payload_for_round(data.loadout_events, round_num)
        if include_loadout
        else {"available": False, "round": int(round_num), "events": []}
    )
    return {
        "round": int(round_num),
        "maximum": round(maximum, 3),
        "roundClock": 115,
        "bombPlant": None if pd.isna(plant_second) else round(float(plant_second), 3),
        "bombClock": 40,
        "players": players,
        "utilities": utilities,
        "kills": kills,
        "loadoutTimeline": loadout_timeline,
        "labels": bool(labels),
    }


def round_playback_html(
    round_num: int,
    layers: tuple[str, ...],
    labels: bool,
    start_second: float,
    bundle_path: str,
    *,
    include_loadout: bool = False,
) -> str:
    payload = playback_payload(round_num, layers, labels, bundle_path, include_loadout=include_loadout)
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    start = min(max(float(start_second), 0), float(payload["maximum"]))
    template = r"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; background: #080b0f; color: #e1e7ef; font-family: Inter, "Microsoft YaHei", sans-serif; overflow-x: hidden; overflow-y: auto; }
  .shell { width: 100%; padding: 0; }
  .replay-grid { display: grid; grid-template-columns: minmax(0, 650px); grid-template-areas: 'map'; justify-content: center; width: 100%; margin: 0 auto; }
  .stage { grid-area: map; position: relative; width: 100%; aspect-ratio: 1; margin: 0; background: #0d1118; border: 1px solid #1c2330; }
  canvas { display: block; width: 100%; height: 100%; }
  .badge { position: absolute; top: 10px; left: 10px; padding: 5px 8px; background: rgba(8,11,15,.86); border: 1px solid #293040; color: #d9e1ea; font: 600 11px ui-monospace, Consolas, monospace; }
  .controls { display: grid; grid-template-columns: auto auto minmax(0,1fr); align-items: center; gap: 8px; width: min(100%, 650px); margin: 8px auto 0; }
  button { height: 34px; padding: 0 12px; border: 1px solid #293040; border-radius: 3px; background: #111822; color: #e1e7ef; font-weight: 650; cursor: pointer; }
  button:hover, button.active { border-color: #4da3ff; background: #172333; }
  .speeds { display: flex; gap: 4px; }
  .speeds button { padding: 0 9px; color: #8f9bad; font: 600 11px ui-monospace, Consolas, monospace; }
  .timeline-panel { min-width: 0; }
  .timeline-track { position: relative; height: 22px; display: flex; align-items: center; }
  input[type=range] { position: relative; z-index: 2; width: 100%; height: 6px; margin: 0; appearance: none; border-radius: 999px; background: linear-gradient(to right,#4da3ff 0%,#4da3ff 0%,#293040 0%,#293040 100%); cursor: pointer; }
  input[type=range]::-webkit-slider-thumb { appearance: none; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #dbe8f5; background: #4da3ff; box-shadow: 0 0 0 3px rgba(77,163,255,.16); }
  .markers { position: absolute; z-index: 3; left: 7px; right: 7px; top: 0; height: 6px; pointer-events: none; }
  .marker { position: absolute; width: 5px; height: 5px; padding: 0; min-width: 0; border: 0; border-radius: 50%; transform: translateX(-50%); pointer-events: auto; }
  .marker.kill { background: #ff5f65; box-shadow: 0 0 0 2px rgba(255,95,101,.16); }
  .marker.utility { background: #f0aa3c; box-shadow: 0 0 0 2px rgba(240,170,60,.13); }
  .marker.kill:hover { background: #ff5f65; transform: translateX(-50%) scale(1.6); }
  .marker.utility:hover { background: #f0aa3c; transform: translateX(-50%) scale(1.6); }
  .timeline-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 2px; gap: 12px; font-family: ui-monospace,Consolas,monospace; }
  .video-time { color: #eef4fb; font-size: 12px; font-weight: 750; white-space: nowrap; }
  .video-time .total { color: #78869a; font-weight: 600; }
  .clock { color: #9eabbc; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .hint { width: min(100%, 650px); margin: 7px auto 0; color: #596779; font: 10px ui-monospace, Consolas, monospace; text-align: right; }

  /* Dynamic OB HUD — use the otherwise-empty flanks as readable equipment cards. */
  .hud-col { display: none; flex-direction: column; min-width: 0; }
  .replay-grid.hud-visible { grid-template-columns: minmax(250px,.86fr) minmax(460px,700px) minmax(250px,.86fr); grid-template-areas: 't map ct'; gap: 14px; width: min(100%, 1360px); align-items: stretch; }
  .replay-grid.hud-visible .hud-col { display: flex; }
  .hud-col.t { grid-area: t; }
  .hud-col.ct { grid-area: ct; }
  .hud-col.t { border-left: 3px solid #f0aa3c; }
  .hud-col.ct { border-right: 3px solid #4da3ff; }
  .hud-col-header { font: 700 0.68rem ui-monospace,Consolas,monospace; letter-spacing: 0.16em; text-transform: uppercase; padding: 8px 11px; color: #c5d0de; background: #0c1118; border-bottom: 1px solid #293040; }
  .hud-col.ct .hud-col-header { text-align: right; }
  .hud-player { display: flex; flex-direction: column; gap: 4px; padding: 8px 11px; border-bottom: 1px solid #202937; min-height: 66px; justify-content: center; background: linear-gradient(90deg,rgba(19,27,38,.9),rgba(12,17,24,.72)); }
  .hud-col.ct .hud-player { background: linear-gradient(270deg,rgba(19,27,38,.9),rgba(12,17,24,.72)); }
  .hud-player:last-child { border-bottom: none; }
  .hud-row1 { display: flex; align-items: center; gap: 9px; min-height: 1.35rem; }
  .hud-row2 { display: flex; align-items: center; gap: 5px; min-height: 1.35rem; flex-wrap: wrap; }
  .hud-row3 { display: flex; align-items: center; gap: 8px; min-height: 1rem; }
  .hud-col.ct .hud-row1, .hud-col.ct .hud-row2, .hud-col.ct .hud-row3 { justify-content: flex-end; }
  .hp-name { font-weight: 800; color: #f3f7fb; font-size: 0.84rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; flex-shrink: 1; min-width: 0; }
  .hp-weapon { font-weight: 700; color: #d7e1eb; font-size: 0.76rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; max-width: 58%; margin-left: auto; }
  .hud-col.ct .hp-weapon { margin-left: 0; margin-right: auto; order: -1; }
  .hud-utility { display: inline-flex; align-items: center; min-height: 19px; padding: 1px 5px; border: 1px solid #303c4c; border-radius: 3px; background: #141c26; color: #dce5ef; font: 700 0.65rem ui-monospace,Consolas,monospace; white-space: nowrap; }
  .hud-utility.smoke { border-color: #697789; color: #d5dde6; }
  .hud-utility.flash { border-color: #d7b54a; color: #ffe68a; }
  .hud-utility.he { border-color: #5e9d78; color: #9ee2b9; }
  .hud-utility.fire { border-color: #c86e42; color: #ffad7c; }
  .hud-utility.decoy { border-color: #9271bd; color: #c9a9f4; }
  .hp-armor, .hp-equip, .hp-account { color: #aeb9c8; font: 0.67rem ui-monospace,Consolas,monospace; white-space: nowrap; }
  .hp-equip { color: #c5d1df; }
  .hp-account { color: #8f9bad; margin-left: auto; }
  .hud-col.ct .hp-account { margin-left: 0; margin-right: auto; }
  .hud-player.dead { background: rgba(11, 16, 23, 0.45); }
  .hud-player.dead .hp-name { color: #b7c3d1; }
  .hud-player.dead .hp-weapon, .hud-player.dead .hud-utility, .hud-player.dead .hp-armor { color: #718096; }
  .hud-player.dead .hp-account { color: #aeb9c8; }
  .hud-c4 { color: #ff5f65; font-weight: 700; font-size: 0.66rem; }
  .hud-note { display: none; width: min(100%,1360px); margin: 5px auto 0; color: #aeb9c8; font: 0.66rem ui-monospace,Consolas,monospace; padding: 2px 8px; text-align: right; }
  .hud-note.visible { display: block; }

  @media (max-width: 980px) {
    .replay-grid.hud-visible { grid-template-columns: minmax(0,650px); grid-template-areas: 't' 'map' 'ct'; gap: 4px; width: min(100%,650px); }
    .hud-col.ct { border-right: 0; border-left: 3px solid #4da3ff; }
    .hud-col.ct .hud-col-header { text-align: left; }
    .hud-col.ct .hud-row1, .hud-col.ct .hud-row2, .hud-col.ct .hud-row3 { justify-content: flex-start; }
    .hud-col.ct .hp-weapon { margin-right: 0; margin-left: auto; order: 0; }
    .hud-col.ct .hp-account { margin-right: 0; margin-left: auto; }
  }
</style>
</head>
<body>
<div class="shell">
  <div class="replay-grid" id="replay_grid">
    <div class="hud-col t" id="hud_t"><div class="hud-col-header">T</div></div>
    <div class="stage">
      <canvas id="radar" width="1024" height="1024"></canvas>
      <div class="badge" id="badge">R__ROUND__ · 0:00</div>
    </div>
    <div class="hud-col ct" id="hud_ct"><div class="hud-col-header">CT</div></div>
  </div>
  <div class="hud-note" id="hud_note">装备与道具随本回合 Demo 记录更新；余额为冻结结束快照。</div>
  <div class="controls">
    <button id="toggle">▶ 播放</button>
    <div class="speeds">
      <button data-speed="0.5">0.5×</button>
      <button class="active" data-speed="1">1×</button>
      <button data-speed="2">2×</button>
    </div>
    <div class="timeline-panel">
      <div class="timeline-track">
        <input id="timeline" type="range" min="0" max="__MAX__" step="0.01" value="__START__" aria-label="播放进度">
        <div class="markers" id="markers"></div>
      </div>
      <div class="timeline-meta">
        <div class="video-time"><span id="elapsed">0:00</span><span class="total"> / <span id="total">0:00</span></span></div>
        <div class="clock" id="clock">比赛时钟 · 回合 1:55.00</div>
      </div>
    </div>
  </div>
  <div class="hint">红点 = 击杀 · 开启道具图层后显示金点 · 点击标记跳转 · 1× = 现实 1 秒</div>
</div>
<script>
const DATA = __PAYLOAD__;
const COLORS = {T:'#f0aa3c', CT:'#4da3ff', kill:'#ff5f65', smoke:'#aab4c2', flash:'#ffe47a', molotov:'#ff7b3e', he:'#8ed081', decoy:'#b990ff'};
const canvas = document.getElementById('radar');
const ctx = canvas.getContext('2d');
const smokeLayer = document.createElement('canvas');
smokeLayer.width = 1024; smokeLayer.height = 1024;
const smokeCtx = smokeLayer.getContext('2d');
const timeline = document.getElementById('timeline');
const toggle = document.getElementById('toggle');
const clock = document.getElementById('clock');
const badge = document.getElementById('badge');
const elapsed = document.getElementById('elapsed');
const total = document.getElementById('total');
const markers = document.getElementById('markers');
const radar = new Image();
radar.src = '__RADAR__';
let current = __START__;
let speed = 1;
let playing = false;
let previousStamp = null;
let raf = null;

/* ── OB HUD helpers ── */
const HUD_SKIP=new Set(['knife','karambit','m9 bayonet','butterfly knife','bayonet','flip knife','gut knife','huntsman knife','falchion knife','shadow daggers','navaja knife','stiletto knife','talon knife','skeleton knife','paracord knife','survival knife','nomad knife','classic knife']);
const HUD_GREN={'smoke grenade':['烟','smoke'],'flashbang':['闪','flash'],'high explosive grenade':['雷','he'],'molotov':['火','fire'],'incendiary':['火','fire'],'decoy':['诱','decoy']};
const HUD_RIFLE=new Set(['ak-47','m4a4','m4a1-s','awp','famas','galil ar','aug','sg 553','ssg 08','scar-20','g3sg1']);
const HUD_PISTOL=new Set(['usp-s','usp','p2000','glock-18','dual berettas','p250','cz75-auto','five-seven','tec-9','desert eagle','r8 revolver']);
function hudPlayersAt(events,t){const r={};for(const e of events)if(e.seconds<=t)r[e.player]=e;return Object.values(r);}
function hudWeapon(inv){let p='',s='',c4=false;for(const x of inv){const l=x.toLowerCase().trim();if(l==='c4 explosive'||l==='c4'){c4=true;continue}if(HUD_SKIP.has(l))continue;if(HUD_RIFLE.has(l))p=x;else if(!s&&HUD_PISTOL.has(l))s=x;}let o=p||s||'—';if(c4)o+=' <span class=hud-c4>C4</span>';return o;}
function hudGrens(inv){const c={};for(const x of inv){const a=HUD_GREN[x.toLowerCase().trim()];if(a){const k=a[0]+'|'+a[1];c[k]=(c[k]||0)+1;}}return Object.keys(c).sort().map(k=>{const [label,kind]=k.split('|');return '<span class="hud-utility '+kind+'">'+label+' ×'+c[k]+'</span>';}).join('');}
function hudArmor(s){const r=[];if(s.armor!=null)r.push('甲'+s.armor);if(s.has_helmet)r.push('头');if(s.has_defuser)r.push('钳');return r.join(' · ')||'';}
function hudCash(s){return s.freeze_account!=null?'$'+s.freeze_account:'';}
function hudRender(t){if(!DATA.loadoutTimeline.available)return;const ps=hudPlayersAt(DATA.loadoutTimeline.events,t);const g={t:[],ct:[]};for(const p of ps)(g[p.side==='T'?'t':'ct']||g.t).push(p);['t','ct'].forEach(s=>{const col=document.getElementById('hud_'+s);let html='<div class=hud-col-header>'+(s==='t'?'TERRORIST':'CT')+'</div>';for(const p of g[s]){const inv=p.inventory||[];const alive=inv.length>0;const nm=p.player.replace(/[<>&"']/g,function(m){return{'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[m]||m;});html+='<div class=hud-player'+(alive?'':' dead')+'><div class=hud-row1><span class=hp-name title="'+nm+'">'+nm+'</span><span class=hp-weapon>'+(alive?hudWeapon(inv):'—')+'</span></div><div class=hud-row2>';if(alive){const gr=hudGrens(inv);if(gr)html+=gr;}html+='</div><div class=hud-row3>';if(alive){const ar=hudArmor(p);if(ar)html+='<span class=hp-armor>'+ar+'</span>';if(p.current_equip_value!=null)html+='<span class=hp-equip>装 $'+p.current_equip_value+'</span>';}const ac=hudCash(p);if(ac)html+='<span class=hp-account>余 '+ac+'</span>';html+='</div></div>';}col.innerHTML=html;});document.getElementById('replay_grid').classList.add('hud-visible');document.getElementById('hud_note').classList.add('visible');}

function formatTime(value, decimals=true) {
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return minutes + ':' + seconds.toFixed(decimals ? 2 : 0).padStart(decimals ? 5 : 2, '0');
}

function formatVideoTime(value) {
  const whole = Math.max(0, Math.floor(value + .001));
  return Math.floor(whole / 60) + ':' + String(whole % 60).padStart(2, '0');
}

function buildMarkers() {
  const events = [
    ...DATA.kills.map(item => ({t:item.t, kind:'kill', label:item.attacker+' 击杀 '+item.victim})),
    ...DATA.utilities.map(item => ({t:item.t, kind:'utility', label:item.thrower+' 投出'+item.label})),
  ].sort((a,b) => a.t-b.t);
  for (const event of events) {
    const marker = document.createElement('button');
    marker.className = 'marker ' + event.kind;
    marker.style.left = (event.t / Math.max(.01, DATA.maximum) * 100) + '%';
    marker.title = formatTime(event.t, false) + ' · ' + event.label;
    marker.setAttribute('aria-label', marker.title);
    marker.addEventListener('click', () => { current=event.t; previousStamp=null; render(); });
    markers.appendChild(marker);
  }
}

function sample(path, time) {
  if (!path.length || time < path[0][0]) return null;
  let lo = 0, hi = path.length - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (path[mid][0] <= time) lo = mid; else hi = mid - 1;
  }
  const a = path[lo];
  const b = path[Math.min(lo + 1, path.length - 1)];
  if (a[3] <= 0) return null;
  const span = Math.max(b[0] - a[0], 0.0001);
  const ratio = Math.max(0, Math.min(1, (time - a[0]) / span));
  return {x: a[1] + (b[1] - a[1]) * ratio, y: a[2] + (b[2] - a[2]) * ratio, hp: a[3]};
}

function drawTrail(player, time) {
  const start = Math.max(0, time - 3.5);
  const points = player.path.filter(p => p[0] >= start && p[0] <= time && p[3] > 0);
  if (points.length < 2) return;
  ctx.beginPath(); ctx.moveTo(points[0][1], points[0][2]);
  for (const point of points.slice(1)) ctx.lineTo(point[1], point[2]);
  ctx.strokeStyle = player.side === 'T' ? 'rgba(240,170,60,.42)' : 'rgba(77,163,255,.42)';
  ctx.lineWidth = 3; ctx.stroke();
}

function drawUtilityIcon(type, x, y, rotation=0) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rotation);
  const color = COLORS[type] || '#cbd4df';
  ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = 3;
  ctx.strokeStyle = '#071018'; ctx.fillStyle = color;
  if (type === 'flash') {
    ctx.beginPath(); ctx.arc(0, 0, 7, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = color; ctx.lineWidth = 2;
    for (let i=0; i<4; i++) { const a=i*Math.PI/2; ctx.beginPath(); ctx.moveTo(Math.cos(a)*10,Math.sin(a)*10); ctx.lineTo(Math.cos(a)*14,Math.sin(a)*14); ctx.stroke(); }
  } else if (type === 'molotov') {
    ctx.fillStyle = '#d9e1ea'; ctx.strokeStyle = '#071018';
    ctx.fillRect(-4,-8,8,15); ctx.strokeRect(-4,-8,8,15);
    ctx.beginPath(); ctx.moveTo(-3,-8); ctx.lineTo(-3,-12); ctx.lineTo(3,-12); ctx.lineTo(3,-8); ctx.stroke();
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(0,-14,4,0,Math.PI*2); ctx.fill();
  } else {
    ctx.beginPath(); ctx.roundRect(-7,-9,14,18,5); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = '#071018'; ctx.beginPath(); ctx.moveTo(-4,-3); ctx.lineTo(4,-3); ctx.moveTo(-4,3); ctx.lineTo(4,3); ctx.stroke();
    ctx.strokeStyle = color; ctx.beginPath(); ctx.moveTo(3,-10); ctx.lineTo(8,-14); ctx.lineTo(11,-10); ctx.stroke();
  }
  ctx.restore();
}

function projectilePosition(item, time) {
  const path=item.path || [];
  if (!path.length) {
    const progress=Math.max(0,Math.min(1,(time-item.t)/Math.max(.01,item.land-item.t)));
    return {x:item.fromX+(item.x-item.fromX)*progress,y:item.fromY+(item.y-item.fromY)*progress};
  }
  let lo=0, hi=path.length-1;
  while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(path[mid][0]<=time)lo=mid;else hi=mid-1;}
  const a=path[lo], b=path[Math.min(lo+1,path.length-1)];
  const ratio=Math.max(0,Math.min(1,(time-a[0])/Math.max(.0001,b[0]-a[0])));
  return {x:a[1]+(b[1]-a[1])*ratio,y:a[2]+(b[2]-a[2])*ratio};
}

function drawProjectile(item, time) {
  const point=projectilePosition(item,time), priorPoint=projectilePosition(item,Math.max(item.t,time-.12));
  const x=point.x, y=point.y, px=priorPoint.x, py=priorPoint.y;
  ctx.save(); ctx.globalAlpha = .55; ctx.strokeStyle = COLORS[item.type] || '#cbd4df'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(px,py); ctx.lineTo(x,y); ctx.stroke(); ctx.restore();
  drawUtilityIcon(item.type, x, y, (time-item.t) * Math.PI * 3);
}

function drawSmoke(item, age, target=ctx) {
  const duration = item.end === null ? 20 : Math.max(.1, item.end-item.land);
  if (age > duration) return;
  const grow = Math.min(1, age / .7);
  const fade = age > duration-1.5 ? (duration-age)/1.5 : 1;
  target.save(); target.globalAlpha = Math.max(0, fade) * .78;
  for (let i=0; i<13; i++) {
    const angle = i * 2.399 + item.x * .001;
    const ring = i === 0 ? 0 : 11 + (i%4)*5;
    const wobble = Math.sin(age*1.6+i)*2;
    target.beginPath(); target.arc(item.x+Math.cos(angle)*(ring+wobble)*grow, item.y+Math.sin(angle)*(ring+wobble)*grow, (14+(i%3)*4)*grow, 0, Math.PI*2);
    target.fillStyle = i%2 ? '#8f9aa8' : '#b7c0cb'; target.fill();
  }
  target.strokeStyle='rgba(225,231,239,.5)'; target.lineWidth=2; target.beginPath(); target.arc(item.x,item.y,38*grow,0,Math.PI*2); target.stroke(); target.restore();
}

function drawSmokeLayer(time) {
  smokeCtx.clearRect(0,0,1024,1024);
  for (const smoke of DATA.utilities) {
    if (smoke.type==='smoke' && time>=smoke.land) drawSmoke(smoke,time-smoke.land,smokeCtx);
  }
  // Valve describes this as a brief clearing but does not publish an exact
  // duration. Current in-game observations are roughly 2–3 seconds: the hole
  // opens quickly, remains usable, then the volume visibly refills.
  const heSmokeOpen = 0.18;
  const heSmokeHold = 1.75;
  const heSmokeRefill = 0.65;
  const heSmokeTotal = heSmokeOpen + heSmokeHold + heSmokeRefill;
  for (const grenade of DATA.utilities) {
    if (grenade.type!=='he') continue;
    const age=time-grenade.land;
    if (age<0 || age>heSmokeTotal) continue;
    let openness;
    if (age < heSmokeOpen) {
      const p = age / heSmokeOpen;
      openness = 1 - Math.pow(1 - p, 3);
    } else if (age < heSmokeOpen + heSmokeHold) {
      openness = 1;
    } else {
      const p = (age - heSmokeOpen - heSmokeHold) / heSmokeRefill;
      openness = 1 - p * p * (3 - 2 * p);
    }
    const radius=50*Math.max(0,openness);
    smokeCtx.save(); smokeCtx.globalCompositeOperation='destination-out';
    const hole=smokeCtx.createRadialGradient(grenade.x,grenade.y,0,grenade.x,grenade.y,Math.max(1,radius));
    hole.addColorStop(0,'rgba(0,0,0,1)'); hole.addColorStop(.68,'rgba(0,0,0,.96)'); hole.addColorStop(1,'rgba(0,0,0,0)');
    smokeCtx.fillStyle=hole; smokeCtx.beginPath(); smokeCtx.arc(grenade.x,grenade.y,Math.max(1,radius),0,Math.PI*2); smokeCtx.fill(); smokeCtx.restore();
  }
  ctx.drawImage(smokeLayer,0,0);
}

function drawFire(item, age) {
  const duration = item.end === null ? 7 : Math.max(.1, item.end-item.land);
  if (age > duration) return;
  const grow = Math.min(1, age/.35); const fade = age>duration-1 ? duration-age : 1;
  ctx.save(); ctx.globalAlpha=Math.max(.15,fade)*.82;
  for (let i=0;i<12;i++) {
    const angle=i*Math.PI*2/12 + .22*Math.sin(age+i); const radius=(10+(i%4)*7)*grow;
    const x=item.x+Math.cos(angle)*radius, y=item.y+Math.sin(angle)*radius;
    ctx.fillStyle=i%3===0?'#ffd166':i%2?'#ff7b3e':'#e84d2f';
    ctx.beginPath(); ctx.arc(x,y,(5+(i%3)*2)*grow,0,Math.PI*2); ctx.fill();
  }
  ctx.strokeStyle='rgba(255,123,62,.75)';ctx.lineWidth=3;ctx.beginPath();ctx.arc(item.x,item.y,39*grow,0,Math.PI*2);ctx.stroke();ctx.restore();
}

function drawFlash(item, age) {
  if (age > .7) return; const fade=1-age/.7, radius=16+age*72;
  ctx.save(); ctx.globalAlpha=fade; ctx.strokeStyle='#fff4a8'; ctx.fillStyle='rgba(255,255,225,.7)';
  ctx.beginPath();ctx.arc(item.x,item.y,12+age*18,0,Math.PI*2);ctx.fill();ctx.lineWidth=5;
  for(let i=0;i<10;i++){const a=i*Math.PI/5;ctx.beginPath();ctx.moveTo(item.x+Math.cos(a)*18,item.y+Math.sin(a)*18);ctx.lineTo(item.x+Math.cos(a)*radius,item.y+Math.sin(a)*radius);ctx.stroke();}
  ctx.restore();
}

function drawHe(item, age) {
  if (age > .8) return; const fade=1-age/.8, radius=10+age*85;
  ctx.save();ctx.globalAlpha=fade;ctx.fillStyle='rgba(255,174,72,.5)';ctx.strokeStyle='#ffbd66';ctx.lineWidth=5;
  ctx.beginPath();ctx.arc(item.x,item.y,Math.min(25,radius),0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.arc(item.x,item.y,radius,0,Math.PI*2);ctx.stroke();ctx.restore();
}

function drawDecoy(item, age) {
  if (age > 15) return; const pulse=14+(age%1)*20;
  ctx.save();ctx.globalAlpha=.65*(1-age/15);ctx.strokeStyle=COLORS.decoy;ctx.lineWidth=4;
  ctx.beginPath();ctx.arc(item.x,item.y,pulse,0,Math.PI*2);ctx.stroke();ctx.restore();
}

function drawUtility(item, time) {
  if (time < item.t) return;
  if (time < item.land) {
    drawProjectile(item, time); return;
  }
  const age=time-item.land;
  if (item.type==='smoke') drawSmoke(item,age);
  else if (item.type==='molotov') drawFire(item,age);
  else if (item.type==='flash') drawFlash(item,age);
  else if (item.type==='he') drawHe(item,age);
  else drawDecoy(item,age);
}

function roundClock(value) {
  if (DATA.bombPlant !== null && value >= DATA.bombPlant) {
    return {label:'炸弹', value:Math.max(0, DATA.bombClock-(value-DATA.bombPlant))};
  }
  return {label:'回合', value:Math.max(0, DATA.roundClock-value)};
}

function render() {
  ctx.clearRect(0, 0, 1024, 1024);
  ctx.fillStyle = '#0d1118'; ctx.fillRect(0, 0, 1024, 1024);
  if (radar.complete && radar.naturalWidth) ctx.drawImage(radar, 0, 0, 1024, 1024);

  for (const player of DATA.players) drawTrail(player, current);
  drawSmokeLayer(current);
  for (const item of DATA.utilities) {
    if (item.type==='smoke') {
      if (current>=item.t && current<item.land) drawProjectile(item,current);
    } else drawUtility(item,current);
  }
  for (const item of DATA.kills) {
    if (item.t > current) continue;
    const size = item.first ? 13 : 10;
    ctx.beginPath(); ctx.moveTo(item.x-size,item.y-size); ctx.lineTo(item.x+size,item.y+size);
    ctx.moveTo(item.x+size,item.y-size); ctx.lineTo(item.x-size,item.y+size);
    ctx.strokeStyle = COLORS.kill; ctx.lineWidth = 5; ctx.stroke();
  }
  for (const player of DATA.players) {
    const p = sample(player.path, current); if (!p) continue;
    ctx.beginPath(); ctx.arc(p.x, p.y, 11, 0, Math.PI * 2);
    ctx.fillStyle = COLORS[player.side]; ctx.fill();
    ctx.strokeStyle = '#080b0f'; ctx.lineWidth = 3; ctx.stroke();
    if (DATA.labels) {
      ctx.font = '700 15px Inter, Microsoft YaHei, sans-serif';
      ctx.textAlign = 'center'; ctx.lineWidth = 4; ctx.strokeStyle = '#080b0f';
      ctx.strokeText(player.name, p.x, p.y - 16); ctx.fillStyle = '#f2f5f8'; ctx.fillText(player.name, p.x, p.y - 16);
    }
  }
  timeline.value = current.toFixed(2);
  const progress = current / Math.max(.01, DATA.maximum) * 100;
  timeline.style.background = `linear-gradient(to right,#4da3ff 0%,#4da3ff ${progress}%,#293040 ${progress}%,#293040 100%)`;
  elapsed.textContent = formatVideoTime(current);
  const liveClock = roundClock(current);
  clock.textContent = '比赛时钟 · ' + liveClock.label + ' ' + formatTime(liveClock.value, true);
  badge.textContent = 'R' + String(DATA.round).padStart(2,'0') + ' · 已进行 ' + formatTime(current, true);
  hudRender(current);
}

function stop() {
  playing = false; previousStamp = null; toggle.textContent = '▶ 播放';
  if (raf) cancelAnimationFrame(raf); raf = null;
}

function loop(stamp) {
  if (!playing) return;
  if (previousStamp === null) previousStamp = stamp;
  const delta = Math.min((stamp - previousStamp) / 1000, 0.1);
  previousStamp = stamp; current += delta * speed;
  if (current >= DATA.maximum) { current = DATA.maximum; render(); stop(); return; }
  render(); raf = requestAnimationFrame(loop);
}

function togglePlayback() {
  if (playing) { stop(); return; }
  if (current >= DATA.maximum) current = 0;
  playing = true; previousStamp = null; toggle.textContent = 'Ⅱ 暂停';
  raf = requestAnimationFrame(loop);
}

toggle.addEventListener('click', togglePlayback);
timeline.addEventListener('input', () => { current = Number(timeline.value); previousStamp = null; render(); });
document.querySelectorAll('[data-speed]').forEach(button => button.addEventListener('click', () => {
  speed = Number(button.dataset.speed);
  document.querySelectorAll('[data-speed]').forEach(item => item.classList.toggle('active', item === button));
}));
document.addEventListener('keydown', event => { if (event.code === 'Space') { event.preventDefault(); togglePlayback(); } });
radar.onload = render;
total.textContent = formatVideoTime(DATA.maximum);
buildMarkers();
render();
</script>
</body>
</html>
"""
    return (
        template.replace("__PAYLOAD__", payload_json)
        .replace("__RADAR__", radar_uri(str(load_match(bundle_path).map_name)))
        .replace("__ROUND__", f"{round_num:02d}")
        .replace("__MAX__", f"{float(payload['maximum']):.3f}")
        .replace("__START__", f"{start:.3f}")
    )


def event_rows(
    data, round_num: int, second: float, *, include_utility: bool = False
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []

    # ── Kill events ──
    for row in round_kills(data, round_num, second).itertuples():
        weapon_raw = str(getattr(row, "weapon", ""))
        weapon_display = weapon_name(weapon_raw)
        events.append(
            {
                "seconds": float(row.seconds),
                "kind": "kill",
                "body": f"<b>{html.escape(str(row.attacker))}</b> 击杀 {html.escape(str(row.victim))} · {html.escape(weapon_display)}",
            }
        )

    # ── Bomb events (plant / defuse / detonate) ──
    if not data.bomb_events.empty:
        bomb_round = data.bomb_events.loc[data.bomb_events["round"] == round_num]
        for _, row in bomb_round.iterrows():
            if float(row.seconds) > second:
                continue
            parts: list[str] = []
            player = row.get("player", "")
            team = row.get("team", "")
            bombsite = row.get("bombsite", "")
            if pd.notna(player) and str(player).strip():
                parts.append(f"<b>{html.escape(str(player))}</b>")
            if pd.notna(team) and str(team).strip():
                parts.append(f"（{html.escape(str(team))}）")
            ev = str(row.event).lower()
            if "plant" in ev:
                action = "下包"
            elif "defuse" in ev:
                action = "拆包"
            elif "detonate" in ev or "explode" in ev:
                action = "炸弹爆炸"
            elif ev == "drop":
                action = "丢下 C4"
            elif ev == "pickup":
                action = "捡起 C4"
            else:
                action = html.escape(str(row.event))
            parts.append(action)
            if pd.notna(bombsite) and str(bombsite).strip():
                parts.append(f"· {html.escape(str(bombsite))}")
            events.append(
                {
                    "seconds": float(row.seconds),
                    "kind": "bomb",
                    "body": " ".join(parts),
                }
            )

    # ── Evidence-backed smoke landing annotations (always shown when landed) ──
    annotations = _get_smoke_annotations(data)
    smoke_ids_this_round: set[int] = set()
    if not annotations.empty:
        round_named = annotations.loc[
            (annotations["round"] == round_num) & (annotations["is_named"])
        ]
        for _, ann in round_named.iterrows():
            if float(ann.land_seconds) > second:
                continue
            gid = int(ann.grenade_id)
            events.append(
                {
                    "seconds": float(ann.land_seconds),
                    "kind": "smoke",
                    "body": f"<b>{html.escape(str(ann.thrower))}</b> 投出 {html.escape(str(ann.display_name))}",
                }
            )
            smoke_ids_this_round.add(gid)

    # ── Utility events (optional; skip named smokes to avoid duplicate rows) ──
    if include_utility:
        for idx, row in round_utility(data, round_num, second).iterrows():
            if idx in smoke_ids_this_round:
                continue
            events.append(
                {
                    "seconds": float(row.seconds),
                    "kind": "utility",
                    "body": f"<b>{html.escape(str(row.thrower))}</b> 投出{html.escape(str(row.utility_label))}",
                }
            )

    return sorted(events, key=lambda item: float(item["seconds"]), reverse=True)


def event_panel(
    data,
    round_num: int,
    second: float,
    *,
    overview: bool = False,
    include_utility: bool = False,
) -> None:
    row = data.rounds.loc[data.rounds["round"] == round_num].iloc[0]
    score_a, score_b = score_after_round(data, round_num)
    events = event_rows(
        data, round_num, second, include_utility=include_utility
    )
    has_named_smokes = any(e.get("kind") == "smoke" for e in events)
    if not events:
        event_html = (
            '<div class="empty-event">该时刻前无击杀或炸弹事件。</div>'
            if not include_utility and not has_named_smokes
            else '<div class="empty-event">该时刻前无事件。</div>'
        )
    else:
        event_html_lines = []
        for i, event in enumerate(events):
            line = (
                f'<div class="event {event["kind"]}">'
                f'<div class="event-time">{fmt_time(float(event["seconds"]))}</div>'
                f'<div class="event-track">'
                f'<div class="event-dot"></div>'
                f'{"<div class=\"event-line\"></div>" if i < len(events) - 1 else ""}'
                f'</div>'
                f'<div class="event-body">{event["body"]}</div>'
                f"</div>"
            )
            event_html_lines.append(line)
        event_html = "".join(event_html_lines)
    # Build feed label
    if include_utility:
        feed_status = "含全部道具事件"
    elif has_named_smokes:
        feed_status = "含关键落点烟雾"
    else:
        feed_status = "普通道具已隐藏"
    feed_title = (
        "EVENT FEED · 本回合事件总览"
        if overview
        else f"EVENT FEED · 截至 {fmt_time(second)}"
    )
    smoke_disclaimer = (
        '<div class="smoke-disclaimer">烟雾起点与落点按实际坐标识别；社区烟名需结合完整轨迹，不代表投掷目的</div>'
        if has_named_smokes
        else ""
    )
    panel = f"""
        <div class="round-panel">
          <div class="round-header">
            <div>
              <div class="round-no">ROUND {round_num:02d}</div>
              <div class="winner">{html.escape(str(row.winner))} 获胜</div>
            </div>
            <div class="running-score">{score_a} : {score_b}</div>
          </div>
          <div class="event-feed-label">{feed_title} · {feed_status}</div>
          {smoke_disclaimer}
          <div class="event-feed">{event_html}</div>
        </div>
    """
    st.markdown(panel, unsafe_allow_html=True)


def round_rail(data, active_round: int) -> None:
    chips = []
    for row in data.rounds.itertuples():
        winner_side = str(row.winning_side).lower()
        side_class = "t" if winner_side == "t" else "ct"
        active = " active" if row.round == active_round else ""
        chips.append(
            f'<div class="round-chip {side_class}{active}" title="R{row.round} · {html.escape(str(row.winner))} · {winner_side.upper()} 方获胜">{row.round}</div>'
        )
    st.markdown(
        '<div class="round-rail">' + "".join(chips) + "</div>",
        unsafe_allow_html=True,
    )


def position_snapshot_map(
    data, team: str, side: str, second: int, *, height: int = 600
) -> go.Figure:
    rows = project_frame(control_snapshot(data, team, side, second), data.map_name)
    fig = radar_base(data.map_name, height=height)
    if rows.empty:
        return fig
    color = T_COLOR if side == "T" else CT_COLOR
    rows["zone"] = rows["area"].map(AREA_GROUP).fillna("OTHER")
    summary = rows.groupby("zone", as_index=False).agg(
        radar_x=("radar_x", "median"),
        radar_y=("radar_y", "median"),
        observations=("player", "size"),
        rounds=("round", "nunique"),
    )
    dominant_areas = (
        rows.groupby("zone")["area"]
        .agg(lambda values: values.value_counts().index[0])
        .rename("dominant_area")
        .reset_index()
    )
    summary = summary.merge(dominant_areas, on="zone", validate="one_to_one")
    summary["share"] = summary["observations"] / summary["observations"].sum()
    summary["group_label"] = summary["zone"].map(ZONE_LABEL)
    summary["area_label"] = summary["dominant_area"].map(
        lambda value: AREA_LABEL.get(str(value), str(value))
    )
    summary["zone_label"] = summary.apply(
        lambda row: row.area_label if row.zone == "OTHER" else row.group_label,
        axis=1,
    )
    summary["display_label"] = summary.apply(
        lambda row: f"{row.zone_label} {row.share:.0%}", axis=1
    )

    # One aggregate footprint per tactical zone replaces dozens of unrelated
    # player/round dots. The halo and core both scale with observation share.
    fig.add_trace(
        go.Scatter(
            x=summary.radar_x,
            y=summary.radar_y,
            mode="markers",
            marker=dict(
                size=summary["share"].mul(105).add(34),
                color=color,
                opacity=0.13,
                line=dict(width=0),
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summary.radar_x,
            y=summary.radar_y,
            mode="markers+text",
            text=summary["display_label"],
            customdata=summary[["zone_label", "group_label", "area_label", "observations", "rounds", "share"]].to_numpy(),
            marker=dict(
                size=summary["share"].mul(34).add(12),
                color=color,
                opacity=0.82,
                line=dict(width=2, color="#080b0f"),
            ),
            textposition="top center",
            textfont=dict(color="#e8edf4", size=11, family="Inter, sans-serif"),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                "<br>战术分组：%{customdata[1]}"
                "<br>主要细分位置：%{customdata[2]}"
                "<br>位置观测：%{customdata[3]}"
                "<br>覆盖回合：%{customdata[4]}"
                "<br>占比：%{customdata[5]:.0%}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    return fig


def route_matrix_figure(
    data,
    team: str,
    side: str,
    checkpoints: tuple[float, ...] = (20.0, 40.0, 60.0),
) -> go.Figure:
    """Compact round-by-round route comparison without plotting player dots."""
    routes = round_routes(data, team, side, checkpoints)
    rounds = routes["round"].drop_duplicates().astype(int).tolist()
    if not rounds:
        return go.Figure()

    state_code = {
        "MISSING": 0,
        "A": 1,
        "B": 2,
        "MID": 3,
        "MIXED": 4,
        "OTHER": 5,
        "WIN": 6,
        "LOSS": 7,
    }
    state_text = {
        "MISSING": "—",
        "A": "A",
        "B": "B",
        "MID": "中",
        "MIXED": "散",
        "OTHER": "匪" if side == "T" else "警",
        "WIN": "胜",
        "LOSS": "负",
    }
    colors = [
        "#171e28",  # round already ended
        "#b86438",  # A emphasis: orange, separate from loss red
        "#168c83",  # B emphasis: teal, separate from win green
        "#465f9d",  # mid emphasis
        "#626978",  # split shape
        "#363d48",  # back/other
        "#2e673d",  # round won
        "#6b2937",  # round lost
    ]
    color_scale: list[list[object]] = []
    for index, color in enumerate(colors):
        color_scale.extend(
            [[index / len(colors), color], [(index + 1) / len(colors), color]]
        )

    matrix: list[list[int]] = []
    labels: list[list[str]] = []
    hover_rows: list[list[str]] = []
    for round_num in rounds:
        round_rows = routes.loc[routes["round"] == round_num].set_index("seconds")
        z_row: list[int] = []
        text_row: list[str] = []
        hover_row: list[str] = []
        for checkpoint in checkpoints:
            item = round_rows.loc[float(checkpoint)]
            if bool(item["available"]):
                state = str(item["dominant_zone"])
                hover = (
                    f"<b>R{round_num:02d} · {fmt_time(float(checkpoint))}</b>"
                    f"<br>A 区 {int(item['A'])} · B 区 {int(item['B'])}"
                    f" · 中路 {int(item['MID'])}"
                    f" · {'匪家' if side == 'T' else '警家'} {int(item['OTHER'])}"
                    f"<br>存活位置观测 {int(item['A'] + item['B'] + item['MID'] + item['OTHER'])}"
                )
            else:
                state = "MISSING"
                hover = f"<b>R{round_num:02d} · {fmt_time(float(checkpoint))}</b><br>此前回合已经结束"
            z_row.append(state_code[state])
            text_row.append(state_text[state])
            hover_row.append(hover)

        won_round = bool(round_rows["won_round"].iloc[0])
        outcome = "WIN" if won_round else "LOSS"
        z_row.append(state_code[outcome])
        text_row.append(state_text[outcome])
        hover_row.append(
            f"<b>R{round_num:02d}</b><br>{team} {'赢下' if won_round else '输掉'}本回合"
        )
        matrix.append(z_row)
        labels.append(text_row)
        hover_rows.append(hover_row)

    x_labels = [fmt_time(second) for second in checkpoints] + ["结果"]
    figure = go.Figure(
        go.Heatmap(
            z=matrix,
            x=x_labels,
            y=[f"R{round_num:02d}" for round_num in rounds],
            text=labels,
            customdata=hover_rows,
            texttemplate="%{text}",
            textfont=dict(color="#f3f6fa", size=14, family="Inter, sans-serif"),
            hovertemplate="%{customdata}<extra></extra>",
            colorscale=color_scale,
            zmin=-0.5,
            zmax=len(colors) - 0.5,
            showscale=False,
            xgap=6,
            ygap=6,
        )
    )
    figure.update_layout(
        height=max(340, len(rounds) * 44 + 100),
        margin=dict(l=12, r=12, t=12, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dfe7f1", family="Inter, sans-serif"),
        hoverlabel=dict(bgcolor="#101722", bordercolor="#2a3443", font_color="#eef3f8"),
        xaxis=dict(side="top", fixedrange=True, tickfont=dict(size=12), showgrid=False),
        yaxis=dict(autorange="reversed", fixedrange=True, tickfont=dict(size=12), showgrid=False),
    )
    return figure


# ════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ════════════════════════════════════════════════════════════════════

_LEGACY_SCREEN_ALIASES = {
    "跨队比较": "研究工作台",
    "证据回放": "回放",
    "回合复盘": "回放",
    "战术模式": "单场工具",
    "复盘报告": "单场工具",
    "多场样本": "单场工具",
}
pending_screen = st.session_state.pop("_pending_screen", None)
if pending_screen:
    st.session_state["screen"] = _LEGACY_SCREEN_ALIASES.get(pending_screen, pending_screen)

current_nav = _LEGACY_SCREEN_ALIASES.get(
    st.session_state.get("screen", "研究工作台"),
    st.session_state.get("screen", "研究工作台"),
)
if current_nav != st.session_state.get("screen"):
    st.session_state["screen"] = current_nav

is_workspace = current_nav == "研究工作台"
is_replay_view = current_nav == "回放"
is_tool_view = current_nav == "单场工具"

# ── 数据来源：仅两种来源，没有默认比赛 ──
evidence_bundle = st.session_state.get("active_replay_bundle")
manual_bundle = st.session_state.get("manual_replay_bundle")
replay_source = evidence_bundle or (manual_bundle if is_replay_view else None)
tool_source = manual_bundle if is_tool_view else None
data = None
data_loaded = False
if is_replay_view and replay_source:
    data = load_match(str(replay_source))
    data_loaded = True
elif is_tool_view and tool_source:
    data = load_match(str(tool_source))
    data_loaded = True

# ════════════════════════════════════════════════════════════════════
# 只在 data 加载后计算比分/胜者
# ════════════════════════════════════════════════════════════════════
if data_loaded:
    final_round = data.rounds.iloc[-1]
    score_a, score_b = int(final_round.team_a_score), int(final_round.team_b_score)
    winner = data.team_a if score_a > score_b else data.team_b

# ── 侧边栏 ──
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">CS TACTICAL LENS</div>',
        unsafe_allow_html=True,
    )
    if is_workspace:
        st.markdown("### 研究工作台")
        _profile_names = {
            str(profile["id"]): str(profile["team"])
            for profile in available_research_profiles()
        }
        _sid_a = _profile_names.get(str(st.session_state.get("research_team_a", "")), "未选择")
        _sid_b = _profile_names.get(str(st.session_state.get("research_team_b", "")), "未选择")
        st.caption(f"当前范围：{st.session_state.get('research_map','?').replace('de_','').title()} · {_sid_a} vs {_sid_b}")
        st.divider()
        st.caption("同图接触前结构 · 可回到具体回合复核")
        st.divider()
        st.caption(
            "队伍、地图与阵容期只从本地已验证的 series 中出现；具体回合证据可载入本地回放。"
        )
    elif is_replay_view:
        if evidence_bundle and data_loaded:
            st.markdown("### 研究证据回放")
            st.caption(
                f"{data.team_a} vs {data.team_b} · "
                f"{data.map_name.replace('de_', '').upper()}"
            )
            st.divider()
            st.success("当前为跨队证据回放")
            st.caption("此页面只用于复核已选中的具体比较证据回合。")
        elif manual_bundle and data_loaded:
            # Detect showcase bundle
            is_showcase = str(manual_bundle) == str(SHOWCASE_BUNDLE_DIR) if SHOWCASE_BUNDLE_DIR else False
            if is_showcase:
                st.markdown("### 公开 Showcase")
                st.caption(f"{data.team_a} vs {data.team_b} · {data.map_name.replace('de_','').upper()}")
                st.divider()
                st.success("📦 公开演示 · 8 Hz 轻量轨迹")
                st.caption(
                    "这是一个真实比赛的全事件轻量还原，用于快速体验回放交互。"
                    "完整本地 V4 保留更高时基的轨迹；此演示不进入跨队研究结论。"
                )
            else:
                st.markdown("### 手动回放")
                st.caption(f"{data.team_a} vs {data.team_b} · {data.map_name.replace('de_','').upper()}")
                st.divider()
                st.success("手动选择")
                st.caption("选择比赛来源：研究工作台 profile → manifest 中的比赛。")
        else:
            st.markdown("### 回放")
            st.caption("请先选择一个已验证比赛")
            st.divider()
            st.caption("从研究工作台选证据行进入，或在本页手动选择比赛。")
        st.divider()
        if data_loaded:
            st.caption(
                "地图坐标、击杀、选手轨迹和道具落点均来自绑定的 Demo。"
            )
    else:
        st.markdown("### 单场工具")
        st.caption("战术模式 · 复盘报告 · 多场样本")
        st.divider()
        st.caption("这些是单场/单队辅助工具，不构成跨队比较结论。")
        st.divider()
        if data_loaded:
            st.caption(
                "地图坐标、击杀、选手轨迹和道具落点均来自本场 demo，不推及战队长期习惯。"
            )

# ── 头部 / 比分 ──

# ── 头部 / 比分 ──
if is_workspace:
    st.markdown(
        '<div class="kicker"><span class="dot"></span>RESEARCH WORKSPACE · VERIFIED SERIES</div>',
        unsafe_allow_html=True,
    )
    st.title("CS Tactical Lens")
    st.caption("从同图多场样本中筛选可复核的开局结构，再回到具体 Demo 证据核对。")
elif is_replay_view:
    if evidence_bundle and data_loaded:
        st.markdown(
            '<div class="kicker"><span class="dot"></span>EVIDENCE REPLAY · CROSS-TEAM BUNDLE</div>',
            unsafe_allow_html=True,
        )
        st.title("CS Tactical Lens")
        st.caption(
            f"当前页面：{data.team_a} vs {data.team_b} · "
            f"{data.map_name.replace('de_', '').upper()} · 比较证据回放"
        )
    elif manual_bundle and data_loaded:
        st.markdown(
            '<div class="kicker"><span class="dot"></span>MANUAL REPLAY · SELECTED MATCH</div>',
            unsafe_allow_html=True,
        )
        st.title("CS Tactical Lens")
        st.caption(f"当前页面：{data.team_a} vs {data.team_b} · {data.map_name.replace('de_', '').upper()} · 手动回合回放")
    else:
        st.markdown(
            '<div class="kicker"><span class="dot"></span>REPLAY</div>',
            unsafe_allow_html=True,
        )
        st.title("CS Tactical Lens")
        st.caption("请先选择一个已验证比赛开始回放。")
    if data_loaded:
        st.markdown(
            f"""
        <div class="scoreboard">
          <div class="team-block">
            <div class="team-info">
              <div class="team-label">{'胜者' if winner == data.team_a else ''} TEAM A</div>
              <div class="team-name">{html.escape(data.team_a.upper())}</div>
            </div>
            <div class="team-score-num t">{score_a}</div>
          </div>
          <div class="match-badge">
            <div class="map-name">{html.escape(data.map_name.replace('de_', '').upper())}</div>
            <div class="match-meta">PRO MATCH · MAP 1 · {len(data.rounds)} ROUNDS</div>
          </div>
          <div class="team-block right">
            <div class="team-score-num ct">{score_b}</div>
            <div class="team-info">
              <div class="team-label">{'胜者' if winner == data.team_b else ''} TEAM B</div>
              <div class="team-name">{html.escape(data.team_b.upper())}</div>
            </div>
          </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

screen = st.radio(
    "页面", ["研究工作台", "回放", "单场工具"], horizontal=True,
    label_visibility="collapsed", key="screen"
)

tool = ""
if screen == "单场工具":
    st.markdown(
        '<div class="section-label">SINGLE-MATCH TOOLS · 单场/单队辅助分析</div>',
        unsafe_allow_html=True,
    )
    st.caption("这些是单场/单队辅助工具，不构成跨队比较结论。")
    tool = st.radio(
        "工具", ["战术模式", "复盘报告", "多场样本"], horizontal=True,
        key="single_match_tool",
    )

# ════════════════════════════════════════════════════════════════════
# 页面 1 — 回合复盘
# ════════════════════════════════════════════════════════════════════
if screen == "回放":
    if data_loaded and st.button("更换比赛", key="change_replay_source"):
        st.session_state.pop("active_replay_bundle", None)
        st.session_state.pop("manual_replay_bundle", None)
        st.rerun()
    if evidence_bundle:
        replay_event = str(data.metadata.get("event", "跨队证据"))
        replay_date = str(data.metadata.get("date", "")).strip()
        st.info(
            f"当前回放来自研究工作台证据：{data.team_a} vs {data.team_b} · "
            f"{replay_event}{f' · {replay_date}' if replay_date else ''}。"
            "默认单场 Demo 与比较证据 bundle 是两个独立来源；当前页面只用于复核这条已选证据。"
        )
    elif manual_bundle and data_loaded:
        st.info(
            f"当前回放手动选择：{data.team_a} vs {data.team_b} · "
            f"{data.map_name.replace('de_', '').upper()}。"
        )
    else:
        st.info("请先进入'研究工作台'从证据行进入，或在本页手动选择比赛开始回放。")

        # ── Showcase bundle card (public demo without full corpus) ──
        if SHOWCASE_BUNDLE_DIR.is_dir() and (SHOWCASE_BUNDLE_DIR / "metadata.json").is_file():
            try:
                showcase_meta = json.loads((SHOWCASE_BUNDLE_DIR / "metadata.json").read_text(encoding="utf-8"))
                if showcase_meta.get("showcase") and (SHOWCASE_BUNDLE_DIR / "positions.csv.gz").is_file():
                    s_team_a = str(showcase_meta.get("team_a", "?"))
                    s_team_b = str(showcase_meta.get("team_b", "?"))
                    s_map = str(showcase_meta.get("map_name", "?")).replace("de_", "").upper()
                    with st.container(border=True):
                        st.markdown("**📦 公开 Showcase**")
                        st.caption(
                            f"{s_team_a} vs {s_team_b} · {s_map} · "
                            "8 Hz 轨迹轻量演示"
                        )
                        if st.button(
                            f"加载公开 Showcase · {s_team_a} vs {s_team_b} · {s_map}",
                            key="load_showcase_replay",
                        ):
                            st.session_state.pop("active_replay_bundle", None)
                            st.session_state["manual_replay_bundle"] = str(SHOWCASE_BUNDLE_DIR)
                            st.rerun()
                    st.divider()
            except (json.JSONDecodeError, OSError):
                pass

        profiles = list(available_research_profiles())
        if profiles:
            profile_ids = sorted({str(p["id"]) for p in profiles})
            sel_profile_id = st.selectbox(
                "选择队伍 series",
                profile_ids,
                format_func=lambda v: next(
                    f"{p['team']} · {p['season']} · {p['map'].replace('de_','').title()}"
                    for p in profiles if p["id"] == v
                ),
                key="replay_profile_sel",
            )
            sel_profile = next(p for p in profiles if p["id"] == sel_profile_id)
            manifest_path = Path(sel_profile["manifest"])
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    match_list = manifest.get("matches", [])
                    if match_list:
                        # Only show matches whose bundle actually exists locally
                        match_ids = []
                        for m in match_list:
                            bv = str(m.get("bundle", ""))
                            if not bv:
                                continue
                            bp = Path(bv)
                            if not bp.is_absolute():
                                bp = (manifest_path.parent / bp).resolve()
                            if bp.is_dir():
                                match_ids.append(str(m["id"]))
                        if not match_ids:
                            st.caption("此 series 的比赛数据不包含在当前设备中。")
                        else:
                            sel_match_id = st.selectbox(
                                "选择比赛",
                                match_ids,
                                format_func=lambda v: next(
                                    f"{m.get('event','?')} vs {m.get('opponent','?')} ({m.get('date','?')})"
                                    for m in match_list if str(m["id"]) == v
                                ),
                                key="replay_match_sel",
                            )
                            sel_match = next(m for m in match_list if str(m["id"]) == sel_match_id)
                            bundle_value = str(sel_match.get("bundle", ""))
                            if bundle_value:
                                bundle_path = Path(bundle_value)
                                if not bundle_path.is_absolute():
                                    bundle_path = (manifest_path.parent / bundle_path).resolve()
                                if bundle_path.is_dir() and st.button("加载回放", key="load_manual_replay"):
                                    st.session_state.pop("active_replay_bundle", None)
                                    st.session_state["manual_replay_bundle"] = str(bundle_path)
                                    st.rerun()
                except (json.JSONDecodeError, KeyError, TypeError):
                    st.warning("无法读取比赛 manifest。")
        st.stop()

    if data_loaded and (evidence_bundle or manual_bundle):
        st.markdown(
            '<div class="section-label">ROUND REPLAY · 将每个结论放回小地图与时间轴</div>',
            unsafe_allow_html=True,
        )
    control_a, control_b, control_c, control_d = st.columns([0.8, 1.25, 1.35, 0.7])
    with control_a:
        selected_round = st.selectbox(
            "回合",
            data.rounds["round"].tolist(),
            format_func=lambda value: f"R{value:02d}",
            key="selected_round",
        )
    round_positions = data.positions.loc[data.positions["round"] == selected_round]
    event_frames = [
        data.kills.loc[data.kills["round"] == selected_round, ["seconds"]],
        data.grenades.loc[data.grenades["round"] == selected_round, ["seconds"]],
    ]
    if not data.bomb_events.empty:
        event_frames.append(
            data.bomb_events.loc[data.bomb_events["round"] == selected_round, ["seconds"]]
        )
    round_events = pd.concat(event_frames)
    maximum_second = max(
        10,
        int(math.ceil(max(round_positions.seconds.max(), round_events.seconds.max()))),
    )
    time_key = f"time_r{selected_round}"
    if time_key not in st.session_state:
        st.session_state[time_key] = 0
    selected_second = int(st.session_state[time_key])
    with control_b:
        playback_mode = st.toggle("连续播放", value=True, key="playback_mode")
        if playback_mode:
            st.caption("在小地图下方播放、暂停或拖动时间轴")
        else:
            selected_second = st.slider(
                "已进行时间（真实秒）",
                0,
                maximum_second,
                step=1,
                key=time_key,
            )
    with control_c:
        layer_options = ["击杀位置", "道具落点"] if playback_mode else ["移动轨迹", "击杀位置", "道具落点"]
        default_layers = [layer for layer in layer_options if layer != "道具落点"]
        layers = st.multiselect(
            "战术图层",
            layer_options,
            default=default_layers,
        )
    with control_d:
        show_labels = st.toggle("选手名", value=True)
        show_utility_events = st.toggle(
            "显示全部普通道具事件",
            value=False,
            help="长枪局的常规烟、闪、雷默认隐藏；打开后可查看完整投掷事件。",
        )

    if playback_mode:
        # The OB-style loadout panels need the full content width.  Keeping the
        # event feed beside the iframe squeezed it below the 980px breakpoint,
        # which stacked T/CT cards above and below the radar instead of using
        # the radar's empty flanks.
        st.iframe(
            round_playback_html(
                selected_round,
                tuple(layers),
                show_labels,
                selected_second,
                str(replay_source),
                include_loadout=True,
            ),
            height=780,
            width="stretch",
        )
        with st.expander("本回合完整事件列表（可选）", expanded=False):
            event_panel(
                data,
                selected_round,
                maximum_second,
                overview=True,
                include_utility=show_utility_events,
            )
    else:
        map_col, detail_col = st.columns([1.9, 0.85], gap="medium")
        with map_col:
            st.plotly_chart(
                replay_figure(data, selected_round, selected_second, layers, show_labels),
                width="stretch",
                config={"displayModeBar": False},
            )
        with detail_col:
            event_panel(
                data,
                selected_round,
                selected_second,
                overview=False,
                include_utility=show_utility_events,
            )
    round_rail(data, selected_round)
    timeline_events = build_round_timeline(data, selected_round)
    with st.expander("回合走势详情（可选）", expanded=False):
        st.caption(
            "阶梯线只表示双方存活人数；菱形、下包、拆包和爆炸均来自本回合 Demo 事件，"
            "不是胜率模型。点击事件节点可把回放跳到对应时刻。"
        )
        timeline_state = st.plotly_chart(
            render_round_timeline(
                timeline_events,
                end_second=maximum_second,
                selected_second=selected_second,
            ),
            width="stretch",
            config={"displayModeBar": False},
            key=f"round_timeline_{selected_round}",
            on_select="rerun",
            selection_mode="points",
        )
        selected_points = getattr(getattr(timeline_state, "selection", None), "points", [])
        if selected_points:
            clicked_second = int(round(float(selected_points[0]["x"])))
            if st.session_state[time_key] != clicked_second:
                st.session_state[time_key] = clicked_second
                st.rerun()
    if playback_mode:
        tickrate = int(data.metadata.get("tickrate", 64))
        st.caption(f"播放器显示正向进度与本回合总时长；比赛时钟从 1:55 倒计时，下包后切换为 40 秒炸弹时钟。时间按实际比赛时基 {tickrate} tick/s 换算。黄色 = T 方，蓝色 = CT 方；底部回合条严格按获胜阵营着色。道具图层仅用于回放定位，不把常规投掷数量当成效率结论。")
    else:
        tickrate = int(data.metadata.get("tickrate", 64))
        st.caption(f"时间从冻结阶段结束后开始，按实际比赛时基 {tickrate} tick/s 换算为真实经过秒数。黄色 = T 方，蓝色 = CT 方，红叉 = 被击杀者；空心圆 = 道具最终落点。轨迹显示当前时刻前 8 秒。道具图层仅用于回放定位，不把常规投掷数量当成效率结论。")

    # ── 回合经济证据（冻结结束）面板 ──
    # 仅证据回放且 bundle 包含 economy_snapshots 时展示
    if screen == "回放" and data_loaded and evidence_bundle and not data.economy_snapshots.empty:
        round_snaps = data.economy_snapshots.loc[data.economy_snapshots["round"] == selected_round]
        if not round_snaps.empty:
            with st.expander("回合经济证据（冻结结束）", expanded=False):
                st.caption(
                    "这是冻结结束时的可观测装备与账户余额快照。"
                    "它支持复核经济标签，但不单独证明队伍的购买意图。"
                )
                for team_name in (data.team_a, data.team_b):
                    team_snaps = round_snaps.loc[round_snaps["team"] == team_name]
                    if team_snaps.empty:
                        continue
                    # Keep the evidence panel consistent with V3's stored
                    # economy label: each side's first round is a pistol
                    # round, rather than an ordinary low-equipment round.
                    team_side = str(team_snaps["side"].iloc[0]).upper()
                    team_side_rounds = rounds_for_side(data, team_name, team_side)
                    team_econ = classify_team_economy(
                        team_snaps,
                        pistol_round=bool(team_side_rounds)
                        and selected_round == min(team_side_rounds),
                    )
                    st.markdown(
                        f"**{html.escape(team_name)}** — "
                        f"{team_econ['label_zh']}（{team_econ['confidence']}）",
                    )
                    st.caption(team_econ["reason"])
                    player_rows = []
                    for _, ps in team_snaps.iterrows():
                        inv_items: list[str] = []
                        try:
                            raw_inv = json.loads(str(ps.get("inventory", "[]"))) if str(ps.get("inventory", "[]")).strip() else []
                        except (json.JSONDecodeError, TypeError):
                            raw_inv = []
                        primary = ""
                        other_gear: list[str] = []
                        grenades: list[str] = []
                        for item in raw_inv:
                            clean = str(item).strip().lower()
                            if clean in _INVENTORY_SKIP:
                                continue
                            if clean in ("ak-47", "m4a4", "m4a1-s", "awp", "famas", "galil ar", "aug", "sg 553", "ssg 08"):
                                primary = str(item)
                            elif clean in ("smoke grenade", "flashbang", "he grenade", "molotov", "incendiary", "decoy"):
                                grenades.append(str(item))
                            else:
                                other_gear.append(str(item))
                        equip_display = primary
                        if grenades:
                            equip_display += " + " + ", ".join(grenades[:3])
                            if len(grenades) > 3:
                                equip_display += "…"
                        if other_gear:
                            equip_display += " · " + ", ".join(other_gear[:2])
                        equip_val = ps.get("current_equip_value")
                        equip_str = f"${int(equip_val):,}" if pd.notna(equip_val) else "—"
                        armor_val = ps.get("armor")
                        armor_str = f"{int(armor_val)}" if pd.notna(armor_val) else "—"
                        helmet_str = "✓" if ps.get("has_helmet") else "—"
                        defuser_str = "✓" if ps.get("has_defuser") else "—"
                        cash_after = ps.get("cash_after_buy")
                        cash_str = f"${int(cash_after):,}" if pd.notna(cash_after) else "—"
                        player_rows.append([
                            html.escape(str(ps.get("player", ""))),
                            html.escape(equip_display) if equip_display else "仅剩近战",
                            equip_str,
                            armor_str,
                            helmet_str,
                            defuser_str,
                            cash_str,
                        ])
                    rows_html = "".join(
                        f"<tr><td>{r[0]}</td><td style='font-size:0.78rem;'>{r[1]}</td>"
                        f"<td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td></tr>"
                        for r in player_rows
                    )
                    table_html = (
                        '<div class="tactical-table-wrap" style="margin-bottom:0.8rem;">'
                        '<table class="tactical-table">'
                        "<thead><tr>"
                        "<th>选手</th><th>装备</th><th>装备价值</th><th>护甲</th><th>头盔</th><th>拆包器</th><th>余额</th>"
                        "</tr></thead>"
                        f"<tbody>{rows_html}</tbody>"
                        "</table></div>"
                    )
                    st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.caption("当前回合无冻结结束快照数据。")

# ════════════════════════════════════════════════════════════════════
# 页面 2 — 单场工具
# ════════════════════════════════════════════════════════════════════
elif screen == "单场工具" and tool == "战术模式":
    if not data_loaded:
        st.info("请先选择一个已验证比赛，再使用战术模式。")
        st.stop()
    if data.map_name != "de_mirage":
        st.info(
            "当前战术模式的中文区域词典与开局结构划分只完成了 Mirage。"
            "这场比赛仍可在“回放”和“复盘报告”中查看；在对应地图词典完成前，"
            "这里不会套用 Mirage 区域制造错误结论。"
        )
        st.stop()
    st.markdown(
        '<div class="section-label">TACTICAL PATTERNS · 本场证据，不冒充长期战术习惯</div>',
        unsafe_allow_html=True,
    )
    team_col, side_col = st.columns([1.2, 0.75])
    with team_col:
        focus_team = st.selectbox("分析队伍", [data.team_a, data.team_b])
    with side_col:
        selected_side = st.radio("阵营", ["T", "CT"], horizontal=True)
    st.markdown("## 核心：0:20 接触前开局结构")
    st.caption(
        "这是战术模式的主证据：只看首次交火前的 0:20 快照。人数结构按存活选手在 A 区、B 区、中路和本方出生点附近的数量组成；"
        "T 方直接写“匪家”，CT 方直接写“警家”。只有相同人数结构至少出现两次，"
        "才称为本场重复结构。它比较的是区域人数，不要求由同一批选手占据相同点位；它也不解释中期反应或主观战术。"
    )
    early_summary = default_formation_summary(data, focus_team, 20.0)
    default_columns = st.columns(2, gap="medium")
    for row, column in zip(early_summary.itertuples(), default_columns, strict=True):
        with column:
            if int(row.valid_rounds) == 0:
                formation_title = "没有有效样本"
                formation_summary = "没有仍在进行且可定位的回合。"
                formation_evidence = "回合证据：无"
            elif bool(row.is_repeated):
                formation_title = str(row.formation)
                formation_summary = (
                    f"{int(row.valid_rounds)} 个有效回合中，这一人数结构出现 "
                    f"{int(row.count)} 次（{float(row.share):.0%}）。"
                )
                formation_evidence = (
                    "回合证据："
                    + ", ".join(f"R{int(round_num):02d}" for round_num in row.rounds)
                )
            else:
                formation_title = "没有重复阵型"
                formation_summary = (
                    f"{int(row.valid_rounds)} 个有效回合的 0:20 人数结构各不相同；"
                    "不从单个回合制造默认站位。"
                )
                formation_evidence = "当前完整样本中没有重复证据"
            st.markdown(
                f'<div class="tactical-finding">'
                f'<div class="finding-kicker">{row.side} SIDE / 0:20</div>'
                f'<div class="finding-title">{html.escape(formation_title)}</div>'
                f'<div class="finding-summary">{html.escape(formation_summary)}</div>'
                f'<div class="finding-sample">{html.escape(formation_evidence)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("## 首杀转化")
    st.caption(
        "首杀转化只回答本场拿到首杀后是否最终赢下回合，不把它包装成地图控制或战术偏好。"
    )
    conversion = entry_conversion_summary(data)
    for row in conversion.itertuples():
        rate = float(row.conversion_rate)
        st.markdown(
            f'<div class="conversion-row">'
            f'<div class="conversion-name">{html.escape(str(row.team))}</div>'
            f'<div class="conversion-track"><div class="conversion-fill" style="width:{rate:.1%}"></div></div>'
            f'<div class="conversion-value">{int(row.converted)}/{int(row.first_kills)} · {rate:.0%}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    with st.expander(
        "辅助视图：多回合位置观测（不代表战术习惯）",
        expanded=False,
    ):
        time_col, note_col = st.columns([1.1, 2.0])
        with time_col:
            sample_second = st.slider(
                "热区取样时刻（回合开始后）", 15, 85, 50, 5
            )
        with note_col:
            st.caption(
                "黄色/蓝色点是按 A、B、中路和其他区域聚合后的空间概览；"
                "这里不研究每秒站位习惯，只帮助定位值得回放的本场位置证据。"
            )

        snapshot_rows = control_snapshot(
            data, focus_team, selected_side, sample_second
        )
        side_rounds = rounds_for_side(data, focus_team, selected_side)
        left, right = st.columns([1.45, 0.85], gap="large")
        with left:
            st.plotly_chart(
                position_snapshot_map(
                    data, focus_team, selected_side, sample_second
                ),
                width="stretch",
                config={"displayModeBar": False},
            )
            st.caption(
                f"{focus_team} 本场 {selected_side} 方在 {fmt_time(sample_second)} 的跨回合站位："
                "地图按 A 区、B 区、中路与其他区域聚合；圆越大表示该区域的位置观测占比越高。"
            )
        with right:
            st.markdown(f"### {fmt_time(sample_second)} 多回合位置观测")
            profile = (
                control_profile(data, focus_team, selected_side, sample_second)
                .head(8)
                .copy()
            )
            if profile.empty:
                st.info("这个时刻没有仍在进行且可定位的回合。可以把时间向前调整。")
            else:
                profile["area"] = profile["area"].map(
                    lambda value: AREA_LABEL.get(str(value), str(value))
                )
                profile["占比"] = profile.pop("share").map("{:.0%}".format)
                profile = profile.rename(
                    columns={"area": "区域", "observations": "位置观测数", "rounds": "覆盖回合"}
                )
                render_dark_table(profile)
            st.caption(
                "中文区域名采用国内赛事与 [5E 玩家版 Mirage 报点]"
                "(https://csgo.5eplay.com/article/5-eplay-product-mirage-csgo-map-point-table)；"
                "游戏本身没有统一的中文报点词典。"
            )
            covered_rounds = int(snapshot_rows["round"].nunique()) if not snapshot_rows.empty else 0
            st.caption(
                f"把 {focus_team} 作为 {selected_side} 方的 {len(side_rounds)} 个回合都停在 {fmt_time(sample_second)}；"
                f"其中 {covered_rounds} 个回合仍在进行，共得到 {len(snapshot_rows)} 条存活位置观测。"
                "这里统计的是站位分布，不代表视野、地图控制或队伍偏好；它是双方十名选手互动后的结果。"
            )

    st.markdown("## 首次交火证据")
    st.caption(
        f"列出 {focus_team} 作为 {selected_side} 方时每个回合的第一场击杀。"
        "位置只用于帮助回放定位；它不解释双方为什么在那里，也不等于固定战术。"
    )
    contact = opening_contact_evidence(data, focus_team, selected_side)
    if contact.empty:
        st.info("当前阵营没有可定位的首次交火事件。")
    else:
        contact_display = contact.copy()
        contact_display["首杀时间"] = contact_display["seconds"].map(
            lambda value: f"{int(float(value) // 60)}:{float(value) % 60:04.1f}"
        )
        contact_display["首杀方"] = contact_display["first_kill_for"]
        contact_display["位置"] = contact_display.apply(
            lambda row: " → ".join(
                AREA_LABEL.get(str(area), str(area)) if str(area) else "未知"
                for area in (row["killer_area"], row["victim_area"])
            ),
            axis=1,
        )
        contact_display["结果"] = contact_display["won_round"].map(
            {True: "本队获胜", False: "本队失利"}
        )
        render_dark_table(
            contact_display[["round", "首杀时间", "killer", "victim", "首杀方", "位置", "结果"]]
            .rename(columns={"round": "回合", "killer": "击杀者", "victim": "被击杀者"})
        )
        contact_rounds = contact["round"].astype(int).tolist()
        contact_col, contact_button_col, contact_note_col = st.columns([1.1, 0.85, 2.3])
        with contact_col:
            selected_contact_round = st.selectbox(
                "回看首次交火",
                contact_rounds,
                format_func=lambda value: f"R{int(value):02d}",
                key=f"contact_round_{focus_team}_{selected_side}",
            )
        selected_contact = contact.loc[contact["round"] == selected_contact_round].iloc[0]
        with contact_button_col:
            st.write("")
            st.button(
                "打开交火回放",
                key=f"open_contact_{focus_team}_{selected_side}",
                on_click=jump_to_replay,
                args=(int(selected_contact_round), float(selected_contact["seconds"])),
                width="stretch",
            )
        with contact_note_col:
            team_after = (
                f"{int(selected_contact['team_alive_after_5s'])} 人 · "
                f"{zone_label_for_side(str(selected_contact['team_zone_after_5s']), selected_side)}"
                if pd.notna(selected_contact["team_alive_after_5s"])
                and pd.notna(selected_contact["team_zone_after_5s"])
                else "样本不足"
            )
            opponent_side = "CT" if selected_side == "T" else "T"
            opponent_after = (
                f"{int(selected_contact['opponent_alive_after_5s'])} 人 · "
                f"{zone_label_for_side(str(selected_contact['opponent_zone_after_5s']), opponent_side)}"
                if pd.notna(selected_contact["opponent_alive_after_5s"])
                and pd.notna(selected_contact["opponent_zone_after_5s"])
                else "样本不足"
            )
            st.caption(
                f"跳到 R{int(selected_contact_round):02d} 的首次交火（"
                f"{float(selected_contact['seconds']):.1f}s）；首次交火后约 5 秒："
                f"本队 {team_after}，对手 {opponent_after}。这是状态快照，不是意图判断。"
            )

    st.markdown("## 三阶段站位时间线")
    st.caption(
        "把同一批回合分别停在 0:20、0:40、1:00，对比站位密度与多人重心。"
        "它描述可核对的位置变化，不推断队伍主观战术意图。"
    )
    checkpoints = (20.0, 40.0, 60.0)
    timeline_rows = shape_timeline(data, focus_team, selected_side, checkpoints)
    with st.container(key="checkpoint_maps"):
        checkpoint_columns = st.columns(3, gap="medium")
        for checkpoint, column in zip(checkpoints, checkpoint_columns, strict=True):
            with column:
                stage = timeline_rows.loc[timeline_rows["seconds"] == checkpoint]
                st.markdown(f"### {fmt_time(checkpoint)}")
                st.plotly_chart(
                    position_snapshot_map(
                        data, focus_team, selected_side, int(checkpoint), height=330
                    ),
                    width="stretch",
                    config={"displayModeBar": False},
                )
                if stage.empty:
                    st.caption("没有仍在进行且可定位的有效回合。")
                else:
                    zone_counts = stage["dominant_zone"].value_counts()
                    dominant_zone = str(zone_counts.index[0])
                    dominant_count = int(zone_counts.iloc[0])
                    st.caption(
                        f"{len(stage)} 个有效回合中，{dominant_count} 个以"
                        f"{zone_label_for_side(dominant_zone, selected_side)}为多人重心。"
                    )

    st.markdown("## 逐回合路线矩阵")
    st.caption(
        "每行是一个真实回合，每列是同一个经过时刻。单元格只显示当时的多人重心："
        f"A = A 区，B = B 区，中 = 中路，散 = 多区并列，"
        f"{'匪 = 匪家' if selected_side == 'T' else '警 = 警家'}；“—”表示回合已经结束。"
    )
    route_rows = round_routes(data, focus_team, selected_side, checkpoints)
    st.plotly_chart(
        route_matrix_figure(data, focus_team, selected_side, checkpoints),
        width="stretch",
        config={"displayModeBar": False},
    )

    matrix_rounds = route_rows["round"].drop_duplicates().astype(int).tolist()
    if matrix_rounds:
        replay_select_col, replay_button_col, replay_note_col = st.columns([1.1, 0.75, 2.4])
        with replay_select_col:
            matrix_round = st.selectbox(
                "回看矩阵回合",
                matrix_rounds,
                format_func=lambda value: f"R{int(value):02d}",
                key=f"route_round_{focus_team}_{selected_side}",
            )
        selected_route = route_rows.loc[
            (route_rows["round"] == matrix_round) & route_rows["available"]
        ]
        replay_second = float(selected_route["seconds"].max()) if not selected_route.empty else 0.0
        with replay_button_col:
            st.write("")
            st.button(
                "打开回放",
                key=f"open_route_{focus_team}_{selected_side}",
                on_click=jump_to_replay,
                args=(int(matrix_round), replay_second),
                width="stretch",
            )
        with replay_note_col:
            st.caption(
                f"将跳到 R{int(matrix_round):02d} 的 {fmt_time(replay_second)}；"
                "可在播放器时间轴继续逐秒核对人员移动，而不是只看这三个采样点。"
            )

    transitions = shape_transitions(data, focus_team, selected_side, checkpoints)
    repeated_transitions = transitions.loc[transitions["count"] >= 2].copy()
    complete_rounds = int(transitions["count"].sum()) if not transitions.empty else 0
    st.markdown("### 重复出现的站位序列")
    if complete_rounds == 0:
        st.info("没有同时覆盖三个时刻的完整回合，因此不生成重复出现序列。")
    elif repeated_transitions.empty:
        st.info(
            f"{complete_rounds} 个完整回合的三阶段路线全部不同。"
            "本场没有可重复验证的序列，因此不会把它冒充成“典型战术”。"
        )
    else:
        st.caption(
            f"只展示至少出现 2 次的完全相同三阶段路线；分母是 {complete_rounds} 个完整回合。"
            "相同重心序列不代表选手走位和战术细节完全相同。"
        )
        for transition_index, transition in repeated_transitions.head(3).iterrows():
            route_label = zone_sequence_label(str(transition["sequence"]), selected_side)
            evidence_rounds = list(transition["rounds"])
            st.markdown(
                f'<div class="tactical-finding">'
                f'<div class="finding-kicker">REPEATED ROUTE / SINGLE MATCH</div>'
                f'<div class="finding-title">{html.escape(route_label)}</div>'
                f'<div class="finding-summary">{int(transition["count"])} 个完整回合重复出现，'
                f'占完整样本 {float(transition["share"]):.0%}。</div>'
                f'<div class="finding-sample">回合证据：'
                f'{html.escape(", ".join(f"R{int(round_num):02d}" for round_num in evidence_rounds))}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            evidence_columns = st.columns(min(6, len(evidence_rounds)))
            for evidence_index, round_num in enumerate(evidence_rounds):
                with evidence_columns[evidence_index % len(evidence_columns)]:
                    st.button(
                        f"回看 R{int(round_num):02d}",
                        key=(
                            f"repeat_route_{focus_team}_{selected_side}_"
                            f"{transition_index}_{round_num}"
                        ),
                        help="跳到 1:00；可在播放器时间轴继续核对 0:20 与 0:40。",
                        on_click=jump_to_replay,
                        args=(int(round_num), 60.0),
                        width="stretch",
                    )

    st.markdown("## 道具直接事件（有限证据）")
    st.caption(
        "这里只保留 Demo 明确记录的 HE/燃烧弹敌方伤害和闪光助攻。"
        "烟雾的视线阻断、闪光逼退枪位和协助拿空间都没有可靠事件字段，因此不评分；"
        "闪光助攻也只覆盖致盲后形成击杀助攻的极窄场景，不能代表闪光价值。"
        "击杀时间窗、下包关联和“使用道具回合胜率”均已删除。"
    )
    all_utility_outcomes = utility_outcome_data()
    side_utility_outcomes = all_utility_outcomes.loc[
        (all_utility_outcomes["team"] == focus_team)
        & (all_utility_outcomes["side"] == selected_side)
    ].copy()
    efficiency = utility_efficiency_summary(side_utility_outcomes)
    if efficiency.empty:
        st.info("当前队伍与阵营没有可分析的道具事件。")
    else:
        efficiency_table = efficiency.copy()
        efficiency_table["道具"] = efficiency_table["grenade_type"].map(UTILITY_LABELS).fillna(
            efficiency_table["grenade_type"]
        )
        efficiency_table["有直接事件的投掷"] = efficiency_table["direct_event_throws"].astype(int)
        efficiency_table["敌方伤害"] = efficiency_table["damage_health"].round().astype(int)
        efficiency_table = efficiency_table.rename(
            columns={"flash_assists": "闪光助攻"}
        )[
            [
                "道具", "有直接事件的投掷", "敌方伤害", "闪光助攻",
            ]
        ]
        render_dark_table(efficiency_table)

        direct_evidence = side_utility_outcomes.loc[
            side_utility_outcomes["damage_health"].gt(0)
            | side_utility_outcomes["flash_assists"].gt(0)
        ].copy()
        available_utility = [
            value
            for value in ("he", "molotov", "flash")
            if value in set(direct_evidence["grenade_type"])
        ]
        if available_utility:
            selected_utility = st.selectbox(
                "查看直接事件证据",
                available_utility,
                format_func=lambda value: UTILITY_LABELS[value],
                key="utility_direct_evidence_type_v3",
            )
            selected_evidence = direct_evidence.loc[
                direct_evidence["grenade_type"] == selected_utility
            ].sort_values(
                ["flash_assists", "damage_health"], ascending=False
            ).head(8)
            st.markdown(f"### {UTILITY_LABELS[selected_utility]} · 可回放直接事件")
            evidence_columns = st.columns(4, gap="small")
            for evidence_index, item in enumerate(selected_evidence.itertuples()):
                direct_bits = []
                if float(item.damage_health) > 0:
                    direct_bits.append(f"敌方伤害 {float(item.damage_health):.0f}")
                if int(item.flash_assists) > 0:
                    direct_bits.append(f"闪光助攻 {int(item.flash_assists)}")
                direct_text = " · ".join(direct_bits)
                with evidence_columns[evidence_index % 4]:
                    st.markdown(
                        f'<div class="tactical-finding">'
                        f'<div class="finding-kicker">R{int(item.round):02d} / {fmt_time(float(item.land_seconds))}</div>'
                        f'<div class="finding-title">{html.escape(str(item.thrower))}</div>'
                        f'<div class="finding-summary">{html.escape(direct_text)}</div>'
                        f'<div class="finding-sample">Demo 直接记录 · 不推断空间收益或因果</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.button(
                        f"回看 R{int(item.round):02d}",
                        key=f"utility_evidence_{int(item.grenade_id)}",
                        on_click=jump_to_replay,
                        args=(int(item.round), float(item.land_seconds)),
                        width="stretch",
                    )

# ════════════════════════════════════════════════════════════════════
# 页面 3 — 复盘报告
# ════════════════════════════════════════════════════════════════════
elif screen == "单场工具" and tool == "复盘报告":
    if not data_loaded:
        st.info("请先选择一个已验证比赛，再使用复盘报告。")
        st.stop()
    st.markdown(
        '<div class="section-label">AUTO DEBRIEF · 自动生成，逐条可核对</div>',
        unsafe_allow_html=True,
    )
    focus_team = st.selectbox(
        "复盘对象",
        [data.team_a, data.team_b] if data else ["—", "—"],
        key="report_team"
    )
    report_col, scope_col = st.columns([1.25, 0.75], gap="large")
    with report_col:
        st.markdown(f"## {focus_team} · 本场客观摘要")
        st.caption(
            "这里不从下包点、首杀后站位或回合末路线倒推队伍偏好。"
            "既定战术与默认习惯需要同队、同图、多场比赛的接触前样本。"
        )
        contact_frames = []
        if data:
            for report_side in ("T", "CT"):
                side_contact = opening_contact_evidence(data, focus_team, report_side).copy()
            if not side_contact.empty:
                side_contact.insert(1, "side", report_side)
                contact_frames.append(side_contact)
        all_contact = (
            pd.concat(contact_frames, ignore_index=True)
            if contact_frames
            else pd.DataFrame()
        )
        if all_contact.empty:
            st.info("本场首次交火证据不足，无法生成摘要 —— 这不代表没有发生交火，而是数据尚不足以可靠定位每次接触。")
        else:
            own_entries = all_contact.loc[all_contact["first_kill_for"] == "本队"]
            converted = int(own_entries["won_round"].sum())
            summary_cols = st.columns(3, gap="small")
            with summary_cols[0]:
                st.metric("可定位首次交火", f"{len(all_contact)} 回合")
            with summary_cols[1]:
                st.metric("本队拿到首杀", f"{len(own_entries)} 回合")
            with summary_cols[2]:
                rate = converted / len(own_entries) if len(own_entries) else 0
                st.metric("首杀后赢下", f"{converted}/{len(own_entries)} · {rate:.0%}")
            st.caption(
                "这是本场的条件结果：只有在本队实际拿到首杀的回合中统计转化率；"
                "它不解释首杀之后采取了什么战术。"
            )
        findings = tactical_findings(focus_team)
        if not findings:
            st.info("本场没有足够的 T 方先拿首杀样本可汇总；请直接使用回合复盘核对具体过程。")
        for finding_index, finding in enumerate(findings):
            st.markdown(
                f'<div class="tactical-finding">'
                f'<div class="finding-kicker">CONDITIONAL RESULT / SINGLE MATCH</div>'
                f'<div class="finding-title">{html.escape(finding.title)}</div>'
                f'<div class="finding-summary">{html.escape(finding.summary)}</div>'
                f'<div class="finding-sample">样本数 {finding.sample_size} · 点击下方证据回到雷达</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander(f"查看 {len(finding.evidence)} 个回合证据", expanded=finding_index == 0):
                evidence_columns = st.columns(4)
                for evidence_index, item in enumerate(finding.evidence):
                    with evidence_columns[evidence_index % 4]:
                        st.button(
                            f"R{item.round_num:02d} · {fmt_time(item.second)}",
                            help=item.label,
                            key=f"evidence_{focus_team}_{finding.kind}_{evidence_index}_{item.round_num}",
                            on_click=jump_to_replay,
                            args=(item.round_num, item.second),
                            width="stretch",
                        )

        first = first_kill_summary(data)
        st.markdown("### 首杀证据表")
        evidence = first.copy()
        evidence["entry_rate"] = evidence["entry_rate"].map("{:.0%}".format)
        evidence["median_seconds"] = evidence["median_seconds"].map("{:.1f}".format)
        evidence = evidence.rename(
            columns={
                "team": "队伍",
                "first_kills": "首杀",
                "entry_rate": "首杀回合占比",
                "median_seconds": "首接触中位秒数",
            }
        )
        render_dark_table(evidence)

        if not all_contact.empty:
            st.markdown("### 交火证据索引")
            contact_display = all_contact.copy()
            contact_display["首杀时间"] = contact_display["seconds"].map(
                lambda value: f"{int(float(value) // 60)}:{float(value) % 60:04.1f}"
            )
            contact_display["首杀区域"] = contact_display.apply(
                lambda row: " → ".join(
                    AREA_LABEL.get(str(area), str(area)) if str(area) else "未知"
                    for area in (row["killer_area"], row["victim_area"])
                ),
                axis=1,
            )
            contact_display["结果"] = contact_display["won_round"].map(
                {True: "本队获胜", False: "本队失利"}
            )
            render_dark_table(
                contact_display[
                    ["side", "round", "首杀时间", "first_kill_for", "killer", "victim", "首杀区域", "结果"]
                ].rename(
                    columns={
                        "side": "阵营",
                        "round": "回合",
                        "first_kill_for": "首杀方",
                        "killer": "击杀者",
                        "victim": "被击杀者",
                    }
                )
            )
            contact_rounds = all_contact["round"].astype(int).tolist()
            report_select_col, report_button_col, report_note_col = st.columns([1.1, 0.85, 2.3])
            with report_select_col:
                selected_report_round = st.selectbox(
                    "回看报告证据",
                    contact_rounds,
                    format_func=lambda value: f"R{int(value):02d}",
                    key=f"report_contact_round_{focus_team}",
                )
            selected_report = all_contact.loc[
                all_contact["round"] == selected_report_round
            ].iloc[0]
            with report_button_col:
                st.write("")
                st.button(
                    "打开交火回放",
                    key=f"report_open_contact_{focus_team}",
                    on_click=jump_to_replay,
                    args=(int(selected_report_round), float(selected_report["seconds"])),
                    width="stretch",
                )
            with report_note_col:
                after_text = "样本不足"
                if pd.notna(selected_report["team_alive_after_5s"]):
                    team_zone = zone_label_for_side(
                        str(selected_report["team_zone_after_5s"]),
                        "T" if selected_report["side"] == "T" else "CT",
                    )
                    opponent_zone = zone_label_for_side(
                        str(selected_report["opponent_zone_after_5s"]),
                        "CT" if selected_report["side"] == "T" else "T",
                    )
                    after_text = (
                        f"本队 {int(selected_report['team_alive_after_5s'])} 人 · {team_zone}；"
                        f"对手 {int(selected_report['opponent_alive_after_5s'])} 人 · {opponent_zone}"
                    )
                st.caption(
                    f"R{int(selected_report_round):02d} 首次交火后约 5 秒：{after_text}。"
                    "这是状态快照，不是战术意图判断。"
                )
    with scope_col:
        st.markdown("## V2 边界")
        st.markdown(
            '<div class="scope-line"><span class="scope-mark">✓</span><span>一张真实 demo 的雷达复盘</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="scope-line"><span class="scope-mark">✓</span><span>回合、时间、选手轨迹、击杀与道具图层</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="scope-line"><span class="scope-mark">✓</span><span>回合事件与条件结果均可跳回证据</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="scope-line"><span class="scope-mark out">—</span><span>当前缺少：跨比赛默认习惯与既定战术判断</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="scope-line"><span class="scope-mark out">—</span><span>本页不提供：AI 猜测意图、自动评价战术</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="scope-line"><span class="scope-mark out">—</span><span>本页不提供：全地图与在线 demo 下载</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="margin:0.6rem 0 0.2rem;border-top:1px solid var(--border);padding-top:0.45rem;font-weight:600;font-size:0.84rem;line-height:1.5;color:#aeb9c8;">'
            '页面分工</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:0.84rem;line-height:1.55;color:#aeb9c8;padding:0.18rem 0;">'
            '<b>本页</b>：单场 Demo 的客观摘要、首次交火与条件结果</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:0.84rem;line-height:1.55;color:#aeb9c8;padding:0.18rem 0;">'
            '<b>多场样本</b>：同队同图、记录的接触前取样点上的重复结构索引</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:0.84rem;line-height:1.55;color:#aeb9c8;padding:0.18rem 0;">'
            '<b>中期站位变化</b>：十名选手共同作用的快照，不是队伍意图</div>',
            unsafe_allow_html=True,
        )
        st.info(
            f"最终比分已校验：{winner} {max(score_a, score_b)} : {min(score_a, score_b)}。本报告只覆盖 {data.map_name.replace('de_', '').title()}。"
        )

# ════════════════════════════════════════════════════════════════════
# 页面 4 — 多场样本
# ════════════════════════════════════════════════════════════════════
elif screen == "单场工具" and tool == "多场样本":
    st.markdown(
        '<div class="section-label">SERIES EVIDENCE · 同队同图接触前样本</div>',
        unsafe_allow_html=True,
    )
    all_profiles = list(available_research_profiles())
    profile_ids = sorted({str(p["id"]) for p in all_profiles})
    sel_series_id = st.selectbox(
        "选择队伍 series",
        profile_ids,
        format_func=lambda v: next(
            f"{p['team']} · {p['season']} · {p['map'].replace('de_','').title()}"
            for p in all_profiles if p["id"] == v
        ),
        key="series_profile_sel",
    )
    sel_series = next(p for p in all_profiles if p["id"] == sel_series_id)
    try:
        series_meta, opening_samples, opening_profile = load_research_series(str(sel_series["series_dir"]))
    except (FileNotFoundError, json.JSONDecodeError, pd.errors.ParserError) as exc:
        st.error(f"多场样本尚未准备好：{exc}")
    else:
        team_display = html.escape(str(sel_series["team"]))
        season_display = html.escape(str(sel_series["season"]))
        map_display = html.escape(str(sel_series["map"]).replace("de_", "").title())
        st.markdown(f"## {team_display} · {map_display} · {season_display}")
        st.caption(
            "这里只观察首次实际交火前、指定秒数仍在场的站位结构。"
            "首次交火指首个敌我伤害事件（没有伤害记录时回退到首杀）；"
            "人数结构指该样本记录的接触前取样点上仍存活选手的区域计数，二者不是同一时刻。"
            "它是可追溯样本，不是默认战术判定；经济分类已可用，可按整队装备特征筛选。"
        )
        st.caption(
            "这里的“可用样本”不是好回合或坏回合：只表示取样时仍有可定位的存活位置，"
            "且首次交火晚于该取样点。Rush 或早交火回合不是无用，只是不能用于估计接触前开局结构。"
        )
        st.markdown(
            f'<div class="series-summary">'
            f'<span class="stat"><span class="stat-value">{int(series_meta["match_count"])} 场比赛</span></span>'
            f'<span class="stat-divider">|</span>'
            f'<span class="stat"><span class="stat-value">{int(series_meta["total_round_samples"])} 个回合样本</span></span>'
            f'<span class="stat-divider">|</span>'
            f'<span class="stat"><span class="stat-value">{int(series_meta["eligible_precontact_samples"])} 个接触前有效样本</span></span>'
            f'<span class="stat-divider">|</span>'
            f'<span class="stat"><span class="stat-value">{float(series_meta["sample_second"]):.0f}秒取样点</span></span>'
            f'<span class="stat-divider">|</span>'
            f'<span class="stat"><span class="stat-value">已分类</span>'
            f'<span class="stat-label"> 经济范围</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        side = st.radio("查看阵营", ["T", "CT"], horizontal=True, key="series_side")
        side_profile_all = opening_profile.loc[opening_profile["side"] == side].copy()
        side_profile_all = side_profile_all.sort_values(
            ["sample_count", "match_count", "formation"], ascending=[False, False, True]
        )
        # 图表和证据表只展示前 8 种结构；筛选器必须保留完整 profile，不能丢掉其余结构。
        side_profile = side_profile_all.head(8).copy()
        side_samples = opening_samples.loc[opening_samples["side"] == side].copy()
        valid_side = side_samples.loc[side_samples["sample_eligible"]]
        excluded_side = side_samples.loc[~side_samples["sample_eligible"]]
        series_summary = series_evidence_summary(
            side_samples, opening_profile, side
        )

        st.markdown("### 系列证据摘要")
        if series_summary["top_formation"]:
            top_note = (
                f"{series_summary['top_formation']}："
                f"{series_summary['top_formation_count']} 回合 · "
                f"{series_summary['top_formation_matches']} 场"
            )
        else:
            top_note = "—"
        median_val = (
            f"{series_summary['median_contact_second']:.1f}s"
            if series_summary["median_contact_second"] is not None
            else "—"
        )
        st.markdown(
            f'<div class="series-summary-card">'
            f'<div class="ss-item"><span class="ss-value">{series_summary["eligible_samples"]}</span>'
            f'<span class="ss-label">接触前可用样本</span></div>'
            f'<div class="ss-item"><span class="ss-value">{series_summary["coverage_matches"]}</span>'
            f'<span class="ss-label">覆盖比赛</span></div>'
            f'<div class="ss-item"><span class="ss-value">{series_summary["repeated_3_matches"]}</span>'
            f'<span class="ss-label">至少覆盖 3 场比赛</span></div>'
            f'<div class="ss-item"><span class="ss-value">{median_val}</span>'
            f'<span class="ss-label">首次交火中位</span></div>'
            f'<div class="ss-note">'
            f'<span class="ss-top-label">最高频结构：</span>{html.escape(top_note)}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "这是重复格局索引，不是默认战术结论。"
            "上方数字随阵营筛选变化；具体回合可在下方索引中逐条复核。"
        )

        left, right = st.columns([1.45, 0.85], gap="large")
        with left:
            if side_profile.empty:
                st.info(f"{side} 方没有可用的接触前阵型样本。")
            else:
                figure = go.Figure(
                    go.Bar(
                        x=side_profile["sample_count"],
                        y=side_profile["formation"],
                        orientation="h",
                        marker_color=T_COLOR if side == "T" else CT_COLOR,
                        text=side_profile["sample_count"],
                        textposition="outside",
                        hovertemplate="阵型 %{y}<br>有效样本 %{x} 个<extra></extra>",
                    )
                )
                figure.update_layout(
                    height=390,
                    margin=dict(l=0, r=24, t=18, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(title="有效回合数", gridcolor="#293040", zeroline=False),
                    yaxis=dict(title="", autorange="reversed"),
                    font=dict(color="#e1e7ef", family="Inter, sans-serif"),
                    showlegend=False,
                )
                st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
                st.caption(
                    f"{side} 方接触前可用样本 {len(valid_side)} 个，覆盖 "
                    f"{valid_side['match_id'].nunique()} 场比赛；图中只显示出现次数最多的 8 种人数结构。"
                )
        with right:
            st.markdown("### 样本边界")
            boundary_rows = pd.DataFrame(
                [
                    {"项目": "有效接触前样本", "数量": int(len(valid_side))},
                    {"项目": "交火过早而排除", "数量": int((excluded_side["exclusion_reason"] == "contact_before_sample").sum())},
                    {"项目": "结束或缺位置", "数量": int((excluded_side["exclusion_reason"] == "round_ended_or_missing_position").sum())},
                ]
            )
            render_dark_table(boundary_rows)
            st.caption(
                "排除的回合不会用最后位置补齐。早于采样时刻已交火的回合，其位置已受对抗影响，"
                "不能作为接触前开局结构的证据。"
            )

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown("### 🎯 回合样本索引")
        # 可用人数结构列表（来自 profile）
        formation_options = ["全部结构"] + sorted(
            side_profile_all["formation"].dropna().unique().tolist()
        )
        # 至少覆盖 3 场比赛的 formation 集合
        repeated_3_formations = set(
            side_profile_all.loc[
                side_profile_all["match_count"] >= 3, "formation"
            ].dropna().unique()
        )
        # 筛选控件：比赛范围 / 人数结构 / 复选框组
        # 构建人类可读的比赛标签：赛事 · vs 对手 · 日期
        unique_match_ids = sorted(side_samples["match_id"].dropna().unique().tolist())
        match_labels = {}
        for mid in unique_match_ids:
            row = side_samples.loc[side_samples["match_id"] == mid].iloc[0]
            match_labels[mid] = f"{row['event']} · vs {row['opponent']} · {row['date']}"
        filter_top, filter_bottom = st.columns([1.3, 1.0], gap="medium")
        match_options = ["全部比赛"] + unique_match_ids
        with filter_top:
            selected_match = st.selectbox(
                "比赛范围",
                match_options,
                format_func=lambda value: "全部比赛" if value == "全部比赛" else match_labels.get(value, str(value)),
                key=f"series_match_filter_{side}",
            )
        with filter_bottom:
            selected_formation = st.selectbox(
                "人数结构",
                formation_options,
                key=f"series_formation_filter_{side}",
            )
        filter_check_cols = st.columns(2, gap="small")
        with filter_check_cols[0]:
            only_valid = st.checkbox(
                "只看接触前可用样本",
                value=True,
                key=f"series_valid_filter_{side}",
            )
        with filter_check_cols[1]:
            only_repeated = st.checkbox(
                "只看“至少覆盖 3 场比赛”的结构",
                value=False,
                key=f"series_repeated_filter_{side}",
            )
        st.caption(
            "“至少覆盖 3 场比赛”表示同一接触前人数结构在至少 3 场不同比赛出现，"
            "不是一场比赛重复三次，也不代表默认战术。"
        )
        # 组合筛选
        indexed_samples = side_samples.copy()
        if selected_match != "全部比赛":
            indexed_samples = indexed_samples.loc[indexed_samples["match_id"] == selected_match]
        if selected_formation != "全部结构":
            indexed_samples = indexed_samples.loc[indexed_samples["formation"] == selected_formation]
        if only_valid:
            indexed_samples = indexed_samples.loc[indexed_samples["sample_eligible"]]
        if only_repeated:
            indexed_samples = indexed_samples.loc[
                indexed_samples["formation"].isin(repeated_3_formations)
            ]
        # 排序并截断显示
        indexed_samples = indexed_samples.sort_values(["date", "round"]).head(30).copy()
        # 筛选摘要行
        match_count_display = indexed_samples["match_id"].nunique() if not indexed_samples.empty else 0
        st.markdown(
            f'<div class="filter-summary">'
            f'{len(indexed_samples)} 条样本 · 覆盖 {match_count_display} 场比赛'
            f'</div>',
            unsafe_allow_html=True,
        )
        if indexed_samples.empty:
            st.info("当前筛选条件没有样本。尝试放宽比赛或结构筛选，或切换阵营。")
        else:
            indexed_samples["首次交火"] = indexed_samples["contact_second"].map(
                lambda value: "—" if pd.isna(value) else f"{float(value):.1f}s"
            )
            indexed_samples["样本状态"] = indexed_samples["sample_eligible"].map(
                {True: "有效", False: "排除"}
            )
            indexed_samples["接触前人数结构"] = indexed_samples["formation"].fillna("—")
            render_dark_table(
                indexed_samples[
                    ["event", "opponent", "date", "round", "首次交火", "接触前人数结构", "样本状态"]
                ].rename(
                    columns={
                        "event": "赛事",
                        "opponent": "对手",
                        "date": "日期",
                        "round": "回合",
                    }
                )
            )
            st.caption(
                f"当前显示 {len(indexed_samples)} 条样本（最多 30 条）。"
            "这里是跨比赛索引：可看到赛事、回合号、首次交火时间和接触前人数结构；"
            "完整过程请在“回放”中选择对应本地比赛后复核。"
            )

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown("### 📊 阵型证据表")
        if side_profile.empty:
            st.info("没有阵型证据表可显示。")
        else:
            evidence_table = side_profile[["formation", "sample_count", "match_count", "sample_share"]].copy()
            evidence_table["sample_share"] = evidence_table["sample_share"].map("{:.0%}".format)
            evidence_table = evidence_table.rename(
                columns={
                    "formation": "接触前人数结构",
                    "sample_count": "有效回合数",
                    "match_count": "覆盖比赛数",
                    "sample_share": "在本阵营有效样本中的占比",
                }
            )
            render_dark_table(evidence_table)
            st.caption(
                "同一人数结构跨多场出现，只说明它是值得回看的重复格局。"
                "没有经济局分类、暂停信息和队内语音时，不能从姿势分布推断既定战术。"
            )

# ════════════════════════════════════════════════════════════════════
# 页面 5 — 研究工作台（V3 跨队比较）
# ════════════════════════════════════════════════════════════════════
elif screen == "研究工作台":
    st.markdown(
        '<div class="section-label">RESEARCH WORKSPACE · 同图跨队接触前结构比较</div>',
        unsafe_allow_html=True,
    )
    st.markdown("## 比较范围")
    research_profiles = list(available_research_profiles())
    research_ready = len(research_profiles) >= 2
    selected_profile_a: dict[str, str | int] | None = None
    selected_profile_b: dict[str, str | int] | None = None

    if not research_ready:
        st.info("当前没有两份可比较的本地 team-map series。请先导入并校验至少两支队伍在同一地图上的完整样本。")
    else:
        map_values = sorted(
            map_name for map_name in {str(profile["map"]) for profile in research_profiles}
            if len({_research_team_key(profile["team"]) for profile in research_profiles if profile["map"] == map_name}) >= 2
        )
        default_map = "de_mirage" if "de_mirage" in map_values else map_values[0]
        if st.session_state.get("research_map") not in map_values:
            st.session_state["research_map"] = default_map
        scope_top, scope_team_a, scope_vs, scope_team_b = st.columns([0.9, 1.35, 0.25, 1.35], gap="small")
        with scope_top:
            selected_map = st.selectbox(
                "地图",
                map_values,
                format_func=lambda value: str(value).replace("de_", "").title(),
                key="research_map",
            )
        map_profiles = [profile for profile in research_profiles if profile["map"] == selected_map]
        profile_ids = [str(profile["id"]) for profile in map_profiles]
        default_a = next(
            (
                str(profile["id"])
                for profile in map_profiles
                if _research_team_key(profile["team"]) == "falcons"
            ),
            profile_ids[0],
        )
        if st.session_state.get("research_team_a") not in profile_ids:
            st.session_state["research_team_a"] = default_a
        with scope_team_a:
            selected_a_id = st.selectbox(
                "队伍 A",
                profile_ids,
                format_func=lambda value: _research_profile_label(next(
                    profile for profile in map_profiles if profile["id"] == value
                )),
                key="research_team_a",
            )
        selected_profile_a = next(profile for profile in map_profiles if profile["id"] == selected_a_id)
        candidate_b = [
            profile for profile in map_profiles
            if _research_team_key(profile["team"]) != _research_team_key(selected_profile_a["team"])
        ]
        with scope_vs:
            st.markdown("<div style='padding-top:1.8rem;text-align:center;color:var(--muted);font-weight:700;'>VS</div>", unsafe_allow_html=True)
        if candidate_b:
            candidate_b_ids = [str(profile["id"]) for profile in candidate_b]
            default_b = next(
                (
                    str(profile["id"])
                    for profile in candidate_b
                    if _research_team_key(profile["team"]) == "spirit"
                ),
                candidate_b_ids[0],
            )
            if st.session_state.get("research_team_b") not in candidate_b_ids:
                st.session_state["research_team_b"] = default_b
            with scope_team_b:
                selected_b_id = st.selectbox(
                    "队伍 B",
                    candidate_b_ids,
                    format_func=lambda value: _research_profile_label(next(
                        profile for profile in candidate_b if profile["id"] == value
                    )),
                    key="research_team_b",
                )
            selected_profile_b = next(profile for profile in candidate_b if profile["id"] == selected_b_id)
        else:
            research_ready = False
            with scope_team_b:
                st.caption("该地图暂无第二份可比较 series")

    if research_ready and selected_profile_a and selected_profile_b:
        st.markdown(
            f'<div class="series-summary">'
            f'<span class="stat"><span class="stat-value">{html.escape(str(selected_profile_a["team"]))}</span>'
            f'<span class="stat-label"> {int(selected_profile_a["match_count"])} 场 · {int(selected_profile_a["eligible_samples"])} 个有效样本'
            f'{(" · " + _COVERAGE_TIER_LABELS.get(str(selected_profile_a.get("coverage_tier", "")), "")) if selected_profile_a.get("coverage_tier") else ""}</span></span>'
            f'<span class="stat-divider">vs</span>'
            f'<span class="stat"><span class="stat-value">{html.escape(str(selected_profile_b["team"]))}</span>'
            f'<span class="stat-label"> {int(selected_profile_b["match_count"])} 场 · {int(selected_profile_b["eligible_samples"])} 个有效样本'
            f'{(" · " + _COVERAGE_TIER_LABELS.get(str(selected_profile_b.get("coverage_tier", "")), "")) if selected_profile_b.get("coverage_tier") else ""}</span></span>'
            f'<span class="stat-divider">|</span>'
            f'<span class="stat"><span class="stat-value">{html.escape(str(selected_profile_a["map"]).replace("de_", "").title())}</span>'
            f'<span class="stat-label"> 当前地图</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "比较只在同一张地图、相同阵营和接触前取样口径下进行。"
            "队伍与阵容期来自本地已验证的 series；新增队伍或地图后才会自动成为可选范围。"
        )

    side = st.radio("查看阵营", ["T", "CT"], horizontal=True, key="v3_side")

    # ── 经济状态筛选（只影响当前选中的两份 series） ──
    economy_filter = st.selectbox(
        "经济状态",
        ECONOMY_FILTER_OPTIONS,
        key=f"v3_economy_{side}",
    )
    economy_value = _ECONOMY_TO_ENGLISH.get(economy_filter)
    obs_second = _OBSERVATION_SECONDS.get(economy_value, 20)
    st.caption(
        "经济标签描述冻结结束时的装备证据，不等于购买意图或默认战术。"
        f"当前观察秒数：{obs_second} 秒"
        f"（{economy_filter}时取样时刻为冻结后 {obs_second} 秒）。"
    )

    if not research_ready or not selected_profile_a or not selected_profile_b:
        st.info(
            "当前比较范围没有两份可用的同图 series。"
            "先在上方选择两支有本地完整样本的队伍，或导入新的已校验 team-map series。"
        )
    else:
        try:
            _, left_samples, _ = load_research_series(str(selected_profile_a["series_dir"]))
            _, right_samples, _ = load_research_series(str(selected_profile_b["series_dir"]))
        except (FileNotFoundError, json.JSONDecodeError, pd.errors.ParserError, UnicodeError) as exc:
            st.error(f"跨队比较数据读取失败：{exc}")
        else:
            team_samples = {
                str(selected_profile_a["team"]): left_samples,
                str(selected_profile_b["team"]): right_samples,
            }
            missing_teams = [
                team for team, samples in team_samples.items()
                if "economy_label" not in samples.columns
            ]
            if missing_teams:
                st.info(
                    f"⚠ {'、'.join(missing_teams)} 数据的 `economy_label` 列不存在，"
                    "经济状态筛选已跳过。如需经济分类，请运行 Codex 经济快照流程。"
                )
            profiles = {
                team: opening_profile_for_comparison(samples, side)
                for team, samples in team_samples.items()
            }

            def _eligible_count(frame: pd.DataFrame) -> int:
                flag = frame["sample_eligible"].astype(str).str.lower().eq("true")
                mask = (
                    frame["side"].eq(side)
                    & flag
                    & frame["formation"].notna()
                )
                if economy_value and "economy_label" in frame.columns:
                    mask = mask & frame["economy_label"].eq(economy_value)
                return int(len(frame.loc[mask]))

            st.markdown("### 同口径开局结构比较")
            st.caption(
                f"以下只比较 {obs_second} 秒时仍未发生首次交火的有效样本。"
                "频率是描述性分布，不表示默认战术；首次交火时间只作为同一批样本的另一项可核验指标。"
            )
            metric_cols = st.columns(4, gap="medium")
            for column, team in zip(metric_cols[:2], team_samples):
                valid = _eligible_count(team_samples[team])
                coverage_mask = (
                    team_samples[team]["side"].eq(side)
                    & team_samples[team]["sample_eligible"].astype(str).str.lower().eq("true")
                )
                if economy_value and "economy_label" in team_samples[team].columns:
                    coverage_mask = coverage_mask & team_samples[team]["economy_label"].eq(economy_value)
                coverage = int(
                    team_samples[team].loc[coverage_mask]["match_id"].nunique()
                )
                with column:
                    st.metric(f"{team} · {side}", f"{valid} / {coverage} 场")
                    st.caption("有效样本 / 覆盖比赛")
            for column, team in zip(metric_cols[2:], team_samples):
                contact_mask = (
                    team_samples[team]["side"].eq(side)
                    & team_samples[team]["sample_eligible"].astype(str).str.lower().eq("true")
                )
                if economy_value and "economy_label" in team_samples[team].columns:
                    contact_mask = contact_mask & team_samples[team]["economy_label"].eq(economy_value)
                weighted_contact = pd.to_numeric(
                    team_samples[team].loc[contact_mask]["contact_second"],
                    errors="coerce",
                ).dropna()
                with column:
                    st.metric(
                        f"{team} 首次交火中位",
                        f"{weighted_contact.median():.1f}s" if not weighted_contact.empty else "—",
                    )
                    st.caption("有效样本内的接触时间")

            team_names = list(team_samples)
            left_team, right_team = team_names[0], team_names[1]
            left_prefix = left_team.lower().replace(" ", "_")
            right_prefix = right_team.lower().replace(" ", "_")
            left_count_key = f"{left_prefix}_sample_count"
            left_match_key = f"{left_prefix}_match_count"
            left_share_key = f"{left_prefix}_sample_share"
            right_count_key = f"{right_prefix}_sample_count"
            right_match_key = f"{right_prefix}_match_count"
            right_share_key = f"{right_prefix}_sample_share"
            comparison = compare_opening_profiles(team_samples, side, economy=economy_value)
            obs_label = _obs_label(economy_value)
            st.markdown(f"### {obs_label}人数结构并列表")
            if comparison.empty:
                st.info(f"{side} 方暂无可比较的有效结构样本。")
            else:
                table = comparison[
                    [
                        "formation",
                        left_count_key,
                        left_match_key,
                        left_share_key,
                        right_count_key,
                        right_match_key,
                        right_share_key,
                        "share_delta",
                    ]
                ].copy()
                # Build HTML table rows with color-coded share_delta.
                rows_html = ""
                for _, row in table.iterrows():
                    left_cell = (
                        f"{int(row[left_count_key])} · "
                        f"{float(row[left_share_key]):.0%}"
                    )
                    right_cell = (
                        f"{int(row[right_count_key])} · "
                        f"{float(row[right_share_key]):.0%}"
                    )
                    coverage_cell = (
                        f"{int(row[left_match_key])} / "
                        f"{int(row[right_match_key])}"
                    )
                    delta_raw = float(row["share_delta"])
                    if delta_raw > 0:
                        delta_class = "v3-delta-pos"
                        delta_text = f"+{delta_raw:.0%}"
                    elif delta_raw < 0:
                        delta_class = "v3-delta-neg"
                        delta_text = f"{delta_raw:.0%}"
                    else:
                        delta_class = "v3-delta-zero"
                        delta_text = "0%"
                    delta_cell = f'<span class="{delta_class}">{delta_text}</span>'
                    rows_html += (
                        f"<tr>"
                        f"<td>{html.escape(str(row['formation']))}</td>"
                        f"<td>{html.escape(left_cell)}</td>"
                        f"<td>{html.escape(right_cell)}</td>"
                        f"<td>{html.escape(coverage_cell)}</td>"
                        f"<td>{delta_cell}</td>"
                        f"</tr>"
                    )
                table_html = (
                    '<div class="tactical-table-wrap">'
                    '<table class="tactical-table">'
                    "<thead><tr>"
                    f"<th>{obs_label}人数结构</th>"
                    f"<th>{html.escape(left_team)} 样本 · 占比</th>"
                    f"<th>{html.escape(right_team)} 样本 · 占比</th>"
                    f"<th>覆盖场数 {html.escape(left_team)} / {html.escape(right_team)}</th>"
                    f"<th>占比差（{html.escape(left_team)}−{html.escape(right_team)}）</th>"
                    "</tr></thead>"
                    f"<tbody>{rows_html}</tbody>"
                    "</table></div>"
                )
                st.markdown(table_html, unsafe_allow_html=True)
                st.caption(
                    "样本数和占比保留分母与归一化频率；覆盖场数用于判断是否跨比赛重复出现。"
                    f"占比差 = {left_team} 占比 − {right_team} 占比；正值只表示前者在当前样本中占比更高。"
                )

            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
            st.markdown("### 回合证据索引")
            st.caption(
                "这里把比较结果落到赛事、对手、日期和回合号。选中一条后可以载入对应的本地 bundle，回到真实回合复核。"
            )
            formation_options = ["全部结构"] + comparison["formation"].tolist()
            evidence_top, evidence_bottom = st.columns([1.2, 1.0], gap="medium")
            with evidence_top:
                evidence_team = st.selectbox(
                    "证据队伍",
                    ["两队", *team_names],
                    key=f"v3_evidence_team_{side}",
                )
            with evidence_bottom:
                evidence_formation = st.selectbox(
                    "证据结构",
                    formation_options,
                    key=f"v3_evidence_formation_{side}",
                )
            evidence = comparison_evidence(
                team_samples,
                side,
                formation=evidence_formation,
                team=evidence_team,
                economy=economy_value,
                limit=40,
            )
            if evidence.empty:
                team_label = "两队" if evidence_team == "两队" else evidence_team
                structure_note = (
                    f"，结构「{evidence_formation}」" if evidence_formation != "全部结构" else ""
                )
                st.info(
                    f"{side} 方 · {team_label}{structure_note}：没有匹配的具体回合证据。"
                    " 尝试选择「全部结构」或「两队」，或切换到另一阵营。"
                )
            else:
                evidence_display = evidence.copy()
                evidence_display["contact_second"] = evidence_display["contact_second"].map(
                    lambda value: "—" if pd.isna(value) else f"{float(value):.1f}s"
                )
                # Attach economy info from source samples
                evidence_display["economy_label"] = "不确定"
                evidence_display["economy_confidence"] = ""
                for idx, ev_row in evidence.iterrows():
                    src_team = ev_row["team"]
                    src_samples = team_samples.get(src_team)
                    if src_samples is not None and "economy_label" in src_samples.columns:
                        src_match = src_samples.loc[
                            src_samples["match_id"].eq(ev_row["match_id"])
                            & src_samples["round"].eq(ev_row["round"])
                        ]
                        if not src_match.empty:
                            label_raw = src_match["economy_label"].iloc[0]
                            evidence_display.at[idx, "economy_label"] = ECONOMY_LABEL_ZH.get(str(label_raw), str(label_raw))
                            if "economy_confidence" in src_samples.columns:
                                evidence_display.at[idx, "economy_confidence"] = str(src_match["economy_confidence"].iloc[0])
                display_columns = ["team", "event", "opponent", "date", "round", "side", "formation", "economy_label", "economy_confidence", "contact_second"]
                render_dark_table(
                    evidence_display[display_columns].rename(
                        columns={
                            "team": "战队",
                            "event": "赛事",
                            "opponent": "对手",
                            "date": "日期",
                            "round": "回合",
                            "side": "阵营",
                            "formation": f"{obs_label}人数结构",
                            "economy_label": "经济状态",
                            "economy_confidence": "置信度",
                            "contact_second": "首次交火",
                        }
                    )
                )
                bundle_index = research_replay_bundle_index(
                    tuple(
                        str(profile["manifest"])
                        for profile in (selected_profile_a, selected_profile_b)
                    )
                )
                evidence_choices = list(range(len(evidence)))
                selected_evidence = st.selectbox(
                    "选择一条回合证据",
                    evidence_choices,
                    format_func=lambda index: (
                        f"{evidence.iloc[index]['team']} · {evidence.iloc[index]['event']} · "
                        f"vs {evidence.iloc[index]['opponent']} · R{int(evidence.iloc[index]['round']):02d}"
                    ),
                    key=f"v3_evidence_row_{side}",
                )
                selected_row = evidence.iloc[int(selected_evidence)]
                ct_val = selected_row["contact_second"]
                ct_display = "—" if pd.isna(ct_val) else f"{float(ct_val):.1f}s"
                raw_date = selected_row.get("date")
                date_display = (
                    "日期未知"
                    if pd.isna(raw_date)
                    or str(raw_date).strip().casefold() in {"", "nan", "nat", "none"}
                    else html.escape(str(raw_date))
                )
                # Look up economy info for the selected row from source samples
                sel_team = str(selected_row["team"])
                sel_samples = team_samples.get(sel_team)
                sel_econ_label = "不确定"
                sel_econ_conf = ""
                if sel_samples is not None and "economy_label" in sel_samples.columns:
                    sel_match = sel_samples.loc[
                        sel_samples["match_id"].eq(selected_row["match_id"])
                        & sel_samples["round"].eq(selected_row["round"])
                    ]
                    if not sel_match.empty:
                        raw_label = sel_match["economy_label"].iloc[0]
                        sel_econ_label = ECONOMY_LABEL_ZH.get(str(raw_label), str(raw_label))
                        if "economy_confidence" in sel_samples.columns:
                            sel_econ_conf = str(sel_match["economy_confidence"].iloc[0])
                econ_display = f"{sel_econ_label}" + (f" · {sel_econ_conf}" if sel_econ_conf else "")
                st.markdown(
                    f'<div class="v3-evidence-preview">'
                    f'<span class="v3-ev-label">选中记录</span><br>'
                    f"{html.escape(str(selected_row['team']))} · "
                    f"{html.escape(str(selected_row['event']))} · "
                    f"vs {html.escape(str(selected_row['opponent']))} · "
                    f"{date_display} · "
                    f"R{int(selected_row['round']):02d} · "
                    f"{html.escape(str(selected_row['formation']))} · "
                    f"首次交火 {ct_display} · "
                    f"{html.escape(econ_display)}"
                    f'</div>',
                    unsafe_allow_html=True,
                )
                selected_bundle = bundle_index.get(str(selected_row["match_id"]))
                if selected_bundle and st.button(
                    "打开这条回合证据",
                    key=f"v3_open_evidence_{side}",
                    type="primary",
                ):
                    jump_to_series_replay(selected_bundle, int(selected_row["round"]))
                    st.rerun()
                elif not selected_bundle:
                    st.warning("这条记录没有找到对应的本地 bundle，保留索引但不伪造回放入口。")

    # 证据边界 — 无论数据是否就绪都显示
    st.markdown("### 证据边界")
    st.markdown(
        '<div class="scope-line"><span class="scope-mark">✓</span><span>每条发现带比赛数、有效回合数和具体回合索引</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="scope-line"><span class="scope-mark">✓</span><span>接触前人数结构（秒数随经济状态在 12–20 秒之间）与首次交火时间的描述性比较</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="scope-line"><span class="scope-mark out">—</span><span>重复出现的结构不等于默认战术</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="scope-line"><span class="scope-mark out">—</span><span>中期站位变化不做队伍意图推断</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="scope-line"><span class="scope-mark">✓</span><span>经济状态筛选可用：手枪局 / 全起 / 半起 / 刚枪 / 经济局 / 混合 / 不确定</span></div>',
        unsafe_allow_html=True,
    )
