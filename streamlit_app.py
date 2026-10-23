"""
Modelación Financiera · Terminal — Streamlit UI (FinTech Dark)
Lógica de negocio: modelacion_logic.py (intacta).
UI: terminal financiera inmersiva · apoyo a decisión · no es asesoría de inversión.
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

import modelacion_logic as L

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    plt = None

# API key Gemini: UI → Streamlit Secrets → variable de entorno.
# Nunca incluir secretos en el repositorio. Si antes se versionó una clave,
# revocarla/rotarla en el proveedor aunque ya se haya quitado del código.
def _resolve_gemini_key(ui_key=None):
    """Orden: input UI → st.secrets → env; no hay clave embebida de respaldo."""
    if ui_key and str(ui_key).strip():
        return str(ui_key).strip()
    try:
        if hasattr(st, "secrets") and st.secrets.get("GEMINI_API_KEY"):
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    env = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if env:
        return env
    return None



# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="Modelación Financiera · Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Terminal de modelación financiera multisectorial · apoyo a decisión · no es asesoría de inversión.",
    },
)

# =============================================================================
# DESIGN SYSTEM — Dark Slate FinTech
# =============================================================================
FINTECH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
  --bg-deep: #070B14;
  --bg-panel: #0B1220;
  --bg-card: rgba(21, 28, 44, 0.72);
  --bg-elevated: #1A2336;
  --bg-glass: rgba(15, 23, 42, 0.55);
  --border: #243044;
  --border-soft: rgba(36, 48, 68, 0.9);
  --border-glow: rgba(20, 184, 166, 0.35);
  --text: #F1F5F9;
  --text-muted: #CBD5E1;
  --text-dim: #94A3B8;
  --accent: #14B8A6;
  --accent-soft: rgba(20, 184, 166, 0.14);
  --accent-hover: #2DD4BF;
  --blue: #3B82F6;
  --warning: #F59E0B;
  --danger: #EF4444;
  --success: #10B981;
  --radius: 14px;
  --radius-sm: 10px;
  --shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
  --shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.28);
  --font: 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
}

/* —— App shell —— */
html, body, [data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(20, 184, 166, 0.08), transparent 55%),
    radial-gradient(900px 500px at 90% 0%, rgba(59, 130, 246, 0.07), transparent 50%),
    var(--bg-deep) !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
}
[data-testid="stAppViewContainer"] > .main {
  background: transparent !important;
}
.main .block-container {
  padding-top: 1.1rem !important;
  padding-bottom: 3rem !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
  max-width: 1480px !important;
}

/* —— Sidebar —— */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0A1020 0%, #070B14 100%) !important;
  border-right: 1px solid var(--border) !important;
  box-shadow: 8px 0 32px rgba(0,0,0,0.35);
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  color: #E2E8F0 !important;
  font-size: 0.84rem !important;
  font-weight: 500 !important;
}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] small { color: #94A3B8 !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 0.85rem; }

/* —— Typography —— */
h1, h2, h3, h4 {
  font-family: var(--font) !important;
  letter-spacing: -0.025em !important;
  color: var(--text) !important;
  font-weight: 600 !important;
}
h1 { font-size: 1.55rem !important; font-weight: 700 !important; }
h2 { font-size: 1.15rem !important; }
h3 { font-size: 1.02rem !important; color: #CBD5E1 !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: #94A3B8 !important; }
.main .stMarkdown p, .main .stMarkdown li { color: #E8EEF7 !important; line-height: 1.55 !important; }
.main [data-testid="stWidgetLabel"] p { color: #E2E8F0 !important; }

/* —— Metrics —— */
[data-testid="stMetric"] {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.95rem 1.1rem;
  box-shadow: var(--shadow-soft);
  transition: border-color 0.2s ease, transform 0.2s ease;
}
[data-testid="stMetric"]:hover {
  border-color: var(--border-glow);
  transform: translateY(-1px);
}
[data-testid="stMetricLabel"] {
  color: var(--text-muted) !important;
  font-size: 0.7rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important;
  font-weight: 600 !important;
  color: var(--text) !important;
  font-size: 1.4rem !important;
  font-variant-numeric: tabular-nums !important;
}

/* —— Tabs —— */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.4rem;
  background: transparent;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.35rem;
  margin-bottom: 0.75rem;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-dim) !important;
  border-radius: 10px 10px 0 0 !important;
  font-weight: 500 !important;
  font-size: 0.88rem !important;
  padding: 0.6rem 1.05rem !important;
  transition: color 0.15s ease, background 0.15s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
  color: var(--text-muted) !important;
  background: rgba(30, 41, 59, 0.5) !important;
}
.stTabs [aria-selected="true"] {
  background: var(--accent-soft) !important;
  color: var(--accent) !important;
  border-bottom: 2px solid var(--accent) !important;
  font-weight: 600 !important;
}

/* —— Buttons —— */
.stButton > button {
  border-radius: 11px !important;
  font-weight: 600 !important;
  font-family: var(--font) !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-elevated) !important;
  color: var(--text) !important;
  transition: all 0.2s ease !important;
  padding: 0.5rem 1.15rem !important;
  letter-spacing: 0.01em !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
}
.stButton > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent-hover) !important;
  box-shadow: 0 0 0 1px rgba(20, 184, 166, 0.3), 0 4px 16px rgba(20, 184, 166, 0.12) !important;
  transform: translateY(-1px);
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #0F766E 0%, #14B8A6 55%, #2DD4BF 140%) !important;
  color: #042F2E !important;
  border: none !important;
  box-shadow: 0 6px 20px rgba(20, 184, 166, 0.4) !important;
  font-weight: 700 !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
  background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
  color: #042F2E !important;
  box-shadow: 0 8px 28px rgba(45, 212, 191, 0.45) !important;
}

/* —— Inputs —— */
.stSelectbox > div > div,
.stNumberInput > div > div > input,
.stTextInput > div > div > input,
.stTextArea textarea {
  background: var(--bg-panel) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.stSelectbox > div > div:focus-within,
.stNumberInput > div > div > input:focus,
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.2) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
  background: var(--accent) !important;
  box-shadow: 0 0 10px rgba(20, 184, 166, 0.45);
}

/* —— Expanders —— */
.streamlit-expanderHeader,
[data-testid="stExpander"] summary,
div[data-testid="stExpander"] > details > summary {
  background: linear-gradient(135deg, #1A2336 0%, #151C2C 100%) !important;
  border-radius: 12px !important;
  border: 1px solid #334155 !important;
  color: #F1F5F9 !important;
  font-weight: 600 !important;
  padding: 0.65rem 0.9rem !important;
  transition: border-color 0.15s ease !important;
}
.streamlit-expanderHeader:hover,
[data-testid="stExpander"] summary:hover {
  border-color: var(--accent) !important;
}
.streamlit-expanderHeader p,
.streamlit-expanderHeader span,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
div[data-testid="stExpander"] summary svg {
  color: #F1F5F9 !important;
  fill: #F1F5F9 !important;
}
.streamlit-expanderContent,
[data-testid="stExpanderDetails"],
div[data-testid="stExpander"] > details > div {
  background: rgba(17, 24, 39, 0.92) !important;
  border: 1px solid #334155 !important;
  border-top: none !important;
  border-radius: 0 0 12px 12px !important;
  color: #E8EEF7 !important;
  padding: 0.85rem 1rem !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  background: #1E293B !important;
  border-color: #475569 !important;
}

/* —— Dataframes —— */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}

/* —— Alerts —— */
.stAlert {
  border-radius: 12px !important;
  border: 1px solid var(--border) !important;
  backdrop-filter: blur(8px);
}

hr {
  border-color: var(--border) !important;
  margin: 1.35rem 0 !important;
  opacity: 0.85;
}

/* —— Custom: Hero —— */
.tf-hero {
  background:
    linear-gradient(135deg, rgba(11, 31, 51, 0.95) 0%, rgba(22, 58, 95, 0.88) 50%, rgba(15, 118, 110, 0.55) 140%);
  border: 1px solid rgba(153, 246, 228, 0.2);
  border-radius: 18px;
  padding: 1.35rem 1.6rem;
  margin: 0 0 1.35rem 0;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}
.tf-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(600px 200px at 80% 0%, rgba(45, 212, 191, 0.12), transparent 60%);
  pointer-events: none;
}
.tf-hero h1 {
  margin: 0 0 0.4rem 0 !important;
  font-size: 1.5rem !important;
  color: #F8FAFC !important;
  position: relative;
}
.tf-hero p {
  margin: 0;
  color: #99F6E4;
  font-size: 0.92rem;
  line-height: 1.5;
  position: relative;
  max-width: 72ch;
}
.tf-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 0.85rem;
  padding: 5px 14px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.22);
  border: 1px solid rgba(153, 246, 228, 0.4);
  color: #CCFBF1;
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  position: relative;
}

/* —— KPI grid (glass) —— */
.tf-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 0.6rem 0 1.35rem 0;
}
@media (max-width: 960px) {
  .tf-kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
.tf-kpi {
  background: var(--bg-card);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  box-shadow: var(--shadow-soft);
  min-height: 92px;
  position: relative;
  cursor: help;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.tf-kpi:hover {
  border-color: var(--border-glow);
  box-shadow: 0 8px 28px rgba(20, 184, 166, 0.12);
  transform: translateY(-2px);
}
.tf-kpi .label {
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 8px;
}
.tf-kpi .value {
  font-family: var(--mono);
  font-size: 1.38rem;
  font-weight: 600;
  color: #F8FAFC;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.tf-kpi .sub {
  margin-top: 6px;
  font-size: 0.74rem;
  color: #5EEAD4;
}
.tf-kpi.accent {
  border-color: rgba(20, 184, 166, 0.5);
  background: linear-gradient(160deg, rgba(21, 28, 44, 0.9) 0%, rgba(15, 118, 110, 0.22) 100%);
}

.tf-section {
  background: var(--bg-card);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.1rem 1.25rem;
  margin-bottom: 1.1rem;
  box-shadow: var(--shadow-soft);
}
.tf-section-title {
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--text-muted);
  font-weight: 700;
  margin: 0 0 0.75rem 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.tf-section-title::before {
  content: "";
  width: 3px;
  height: 14px;
  background: var(--accent);
  border-radius: 2px;
  box-shadow: 0 0 8px rgba(20, 184, 166, 0.5);
}

.tf-info {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: 12px;
  padding: 0.8rem 1.05rem;
  color: #BFDBFE;
  font-size: 0.88rem;
  margin: 0.55rem 0 1.05rem 0;
  line-height: 1.45;
}
.tf-footer {
  text-align: center;
  color: var(--text-dim);
  font-size: 0.76rem;
  padding: 1.75rem 0 0.75rem 0;
  letter-spacing: 0.02em;
}
.tf-sidebar-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #94A3B8 !important;
  font-weight: 700;
  margin: 1.1rem 0 0.45rem 0;
}

/* File uploader */
section[data-testid="stSidebar"] [data-testid="stFileUploader"] section,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] > div > div {
  background: #1A2336 !important;
  border: 1px dashed #64748B !important;
  border-radius: 14px !important;
  padding: 0.85rem !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] section *,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] small,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] span,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] p {
  color: #E2E8F0 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
  background: #0F766E !important;
  color: #ECFDF5 !important;
  border: 1px solid #14B8A6 !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stDownloadButton > button,
section[data-testid="stSidebar"] .stButton > button {
  background: #1E293B !important;
  color: #F1F5F9 !important;
  border: 1px solid #475569 !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
  color: #042F2E !important;
  border: none !important;
}

/* Tooltips KPI y métricas (hover) */
.tf-kpi[data-tip],
.tf-metric-tip[data-tip] {
  cursor: help;
  position: relative;
}
.tf-kpi[data-tip]:hover::after,
.tf-metric-tip[data-tip]:hover::after {
  content: attr(data-tip);
  position: absolute;
  left: 50%;
  bottom: calc(100% + 12px);
  transform: translateX(-50%);
  width: min(320px, 82vw);
  max-width: 340px;
  background: #0F172A;
  color: #F1F5F9;
  border: 1px solid #14B8A6;
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 0.8rem;
  font-weight: 400;
  line-height: 1.45;
  letter-spacing: 0;
  text-transform: none;
  z-index: 10050;
  box-shadow: 0 16px 36px rgba(0,0,0,0.55);
  pointer-events: none;
  white-space: normal;
  text-align: left;
}
.tf-kpi[data-tip]:hover::before,
.tf-metric-tip[data-tip]:hover::before {
  content: "";
  position: absolute;
  left: 50%;
  bottom: calc(100% + 5px);
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #14B8A6;
  z-index: 10051;
}
.tf-metric-tip {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.85rem 1rem;
  box-shadow: var(--shadow-soft);
  min-height: 78px;
  transition: border-color 0.2s ease, transform 0.2s ease;
}
.tf-metric-tip:hover {
  border-color: var(--border-glow);
  transform: translateY(-1px);
}
.tf-metric-tip .m-label {
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 6px;
}
.tf-metric-tip .m-value {
  font-family: var(--mono);
  font-size: 1.2rem;
  font-weight: 600;
  color: #F8FAFC;
  font-variant-numeric: tabular-nums;
  line-height: 1.25;
}
.tf-metric-tip .m-hint {
  margin-top: 4px;
  font-size: 0.68rem;
  color: #5EEAD4;
  opacity: 0.85;
}
.tf-metrics-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 0.5rem 0 1rem 0;
}
@media (max-width: 960px) {
  .tf-metrics-row { grid-template-columns: repeat(2, 1fr); }
}
.tf-metrics-row.cols-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.tf-metrics-row.cols-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.tf-explain {
  background: rgba(20, 184, 166, 0.09);
  border-left: 3px solid #14B8A6;
  border-radius: 0 12px 12px 0;
  padding: 0.75rem 1rem;
  margin: 0.55rem 0 1.1rem 0;
  color: #CCFBF1;
  font-size: 0.86rem;
  line-height: 1.5;
}
.tf-explain b { color: #5EEAD4; }

/* Ticker tape */
.tf-tape-wrap {
  overflow: hidden;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid #243044;
  border-radius: 14px;
  margin: 0 0 1.15rem 0;
  position: relative;
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(8px);
}
.tf-tape-wrap::before {
  content: "MERCADO";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  padding: 0 14px;
  background: linear-gradient(90deg, #0F766E 0%, #0F172A 100%);
  color: #ECFDF5;
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.tf-tape {
  display: flex;
  gap: 1.85rem;
  width: max-content;
  padding: 0.6rem 1rem 0.6rem 5.75rem;
  animation: tf-scroll 48s linear infinite;
  font-family: var(--mono);
  font-size: 0.82rem;
  white-space: nowrap;
}
.tf-tape:hover { animation-play-state: paused; }
@keyframes tf-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
.tf-tick { color: #E2E8F0; }
.tf-tick b { color: #F8FAFC; margin-right: 6px; }
.tf-up { color: #34D399; }
.tf-down { color: #F87171; }
.tf-flat { color: #94A3B8; }

.tf-chart-tip {
  background: rgba(26, 35, 54, 0.9);
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 0.6rem 0.95rem;
  margin: -0.15rem 0 1.05rem 0;
  color: #CBD5E1;
  font-size: 0.8rem;
  line-height: 1.45;
}
.tf-chart-tip span {
  color: #5EEAD4;
  font-weight: 600;
  margin-right: 6px;
}

.tf-tour {
  background: linear-gradient(135deg, rgba(19, 78, 74, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
  border: 1px solid #14B8A6;
  border-radius: 16px;
  padding: 1.1rem 1.25rem;
  margin: 0 0 1.15rem 0;
  color: #ECFDF5;
  font-size: 0.9rem;
  line-height: 1.5;
  box-shadow: 0 8px 28px rgba(15, 118, 110, 0.2);
}
.tf-tour h4 { margin: 0 0 0.45rem 0; color: #5EEAD4; font-size: 1rem; }
.tf-tour ol { margin: 0.45rem 0 0.65rem 1.2rem; padding: 0; }
.tf-tour li { margin: 0.3rem 0; }

.tf-semaforo {
  display: flex;
  gap: 12px;
  align-items: stretch;
  margin: 0.7rem 0 1.15rem 0;
  flex-wrap: wrap;
}
.tf-sem-card {
  flex: 1;
  min-width: 148px;
  border-radius: 14px;
  padding: 14px 16px;
  border: 1px solid #334155;
  background: rgba(26, 35, 54, 0.85);
  backdrop-filter: blur(8px);
  transition: border-color 0.2s ease;
}
.tf-sem-card .dot {
  width: 11px; height: 11px; border-radius: 50%;
  display: inline-block; margin-right: 8px;
  box-shadow: 0 0 10px currentColor;
}
.tf-sem-card.ok { border-color: rgba(52, 211, 153, 0.55); }
.tf-sem-card.ok .dot { background: #34D399; color: #34D399; }
.tf-sem-card.warn { border-color: rgba(251, 191, 36, 0.55); }
.tf-sem-card.warn .dot { background: #FBBF24; color: #FBBF24; }
.tf-sem-card.bad { border-color: rgba(248, 113, 113, 0.55); }
.tf-sem-card.bad .dot { background: #F87171; color: #F87171; }
.tf-sem-card .ttl { font-weight: 600; color: #F1F5F9; font-size: 0.9rem; }
.tf-sem-card .dsc { color: #94A3B8; font-size: 0.78rem; margin-top: 5px; line-height: 1.4; }

.tf-analogy {
  background: rgba(30, 41, 59, 0.7);
  border: 1px dashed #475569;
  border-radius: 12px;
  padding: 0.75rem 1rem;
  margin: 0.5rem 0 1rem 0;
  color: #CBD5E1;
  font-size: 0.84rem;
  line-height: 1.45;
}

/* Plotly container breathing room */
.stPlotlyChart, [data-testid="stPlotlyChart"] {
  border-radius: 14px;
  overflow: hidden;
  margin: 0.35rem 0 0.85rem 0 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #0B1220; }
::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 8px;
  border: 2px solid #0B1220;
}
::-webkit-scrollbar-thumb:hover { background: #14B8A6; }

/* —— Control para REABRIR el sidebar (flecha nativa) —— */
/* No ocultar header/toolbar: ahí vive el botón cuando el menú está cerrado. */
header[data-testid="stHeader"] {
  background: rgba(7, 11, 20, 0.55) !important;
  visibility: visible !important;
  opacity: 1 !important;
  height: 2.75rem !important;
  min-height: 2.75rem !important;
  display: block !important;
  z-index: 100020 !important;
}
div[data-testid="stToolbar"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
}
/* Selectores de la flecha según versión de Streamlit */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stExpandSidebarButton"],
button[kind="header"],
button[data-testid="baseButton-header"],
button[data-testid="baseButton-headerNoPadding"],
button[data-testid="stBaseButton-headerNoPadding"] {
  display: inline-flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  z-index: 100025 !important;
}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
  position: fixed !important;
  left: 0.4rem !important;
  top: 0.4rem !important;
  width: 2.4rem !important;
  height: 2.4rem !important;
  background: rgba(15, 23, 42, 0.95) !important;
  border: 1px solid #14B8A6 !important;
  border-radius: 10px !important;
  box-shadow: 0 2px 12px rgba(0,0,0,0.4) !important;
  align-items: center !important;
  justify-content: center !important;
}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg,
[data-testid="stExpandSidebarButton"] svg {
  fill: #5EEAD4 !important;
  color: #5EEAD4 !important;
  stroke: #5EEAD4 !important;
}


/* Hide solo menú hamburger y footer; NO ocultar header/toolbar (flecha del sidebar) */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Radio / horizontal controls */
div[role="radiogroup"] label {
  background: rgba(26, 35, 54, 0.6) !important;
  border: 1px solid #334155 !important;
  border-radius: 10px !important;
  padding: 0.45rem 0.85rem !important;
  margin: 0.2rem !important;
  transition: border-color 0.15s ease, background 0.15s ease !important;
}
div[role="radiogroup"] label:has(input:checked) {
  border-color: #14B8A6 !important;
  background: rgba(20, 184, 166, 0.15) !important;
  color: #5EEAD4 !important;
  font-weight: 600 !important;
}

/* Progress bar */
.stProgress > div > div {
  background: linear-gradient(90deg, #0F766E, #14B8A6) !important;
  border-radius: 6px !important;
}

/* Success / warning / error soft polish */
[data-testid="stNotification"] {
  border-radius: 12px !important;
}

/* —— Tablas HTML embebidas —— */
.tf-table-wrap { overflow-x: auto; margin: 0.5rem 0 1rem 0; border-radius: 12px; border: 1px solid #243044; }
.tf-table-wrap table, .section-card table, .html-container table {
  width: 100% !important;
  border-collapse: collapse !important;
  table-layout: auto !important;
  font-size: 0.86rem !important;
}
.tf-table-wrap th, .section-card table th, .html-container table th {
  text-align: left !important;
  background: #0F766E !important;
  color: #ECFDF5 !important;
  padding: 10px 12px !important;
  font-weight: 600 !important;
  white-space: normal !important;
  vertical-align: top !important;
}
.tf-table-wrap td, .section-card table td, .html-container table td {
  text-align: left !important;
  padding: 8px 12px !important;
  border-bottom: 1px solid #243044 !important;
  color: #E8EEF7 !important;
  vertical-align: top !important;
  white-space: normal !important;
  word-break: break-word !important;
}
.tf-table-wrap tr:nth-child(even) td, .section-card table tr:nth-child(even) td {
  background: rgba(30, 41, 59, 0.55) !important;
}
[data-testid="stDataFrame"] table th,
[data-testid="stDataFrame"] table td {
  text-align: left !important;
}

</style>
"""


st.markdown(FINTECH_CSS, unsafe_allow_html=True)

# =============================================================================
# UI HELPERS
# =============================================================================
def _html(x, max_chars=120000):
    if x is None:
        return
    s = str(x)
    if len(s) > max_chars:
        s = s[: max_chars] + " …[recortado]"
    st.markdown(s, unsafe_allow_html=True)



def _strip_contraste_html(html) -> str:
    """Elimina el bloque MÓDULO IA · CONTRASTE MODELO vs MERCADO de HTML (pestaña 4)."""
    if html is None:
        return html
    s = str(html)
    up = s.upper().replace("Ó", "O")
    if "CONTRASTE MODELO" not in s and "CONTRASTE MODELO" not in up and "MODULO IA" not in up:
        return s
    import re
    # Contenedor exterior del módulo (plantilla con borde #1E40AF) o cualquier div que abra el título
    start_m = re.search(
        r'<div[^>]*>\s*<div[^>]*>\s*M[ÓO]DULO\s+IA\s*[·.\-–]\s*CONTRASTE\s+MODELO\s+vs\s+MERCADO',
        s,
        flags=re.I | re.S,
    )
    if not start_m:
        start_m = re.search(
            r'M[ÓO]DULO\s+IA\s*[·.\-–]\s*CONTRASTE\s+MODELO\s+vs\s+MERCADO',
            s,
            flags=re.I,
        )
        if not start_m:
            return s
        start = s.rfind("<div", 0, start_m.start())
        if start < 0:
            start = start_m.start()
    else:
        start = start_m.start()

    # Cierre: disclaimer + </div> del contenedor exterior
    end_pat = re.compile(
        r"Este\s+m[oó]dulo\s+no\s+constituye\s+asesor[ií]a\s+de\s+inversi[oó]n.*?</p>\s*</div>",
        re.I | re.S,
    )
    em = end_pat.search(s, start)
    if em:
        return (s[:start] + "\n" + s[em.end():]).strip()

    # Balanceo de <div> desde start
    i = start
    depth = 0
    opened = False
    while i < len(s):
        if s.startswith("<div", i):
            depth += 1
            opened = True
            gt = s.find(">", i)
            i = len(s) if gt < 0 else gt + 1
            continue
        if s.startswith("</div>", i):
            depth -= 1
            i += 6
            if opened and depth <= 0:
                return (s[:start] + "\n" + s[i:]).strip()
            continue
        i += 1
    return s[:start].strip()


def _plotly_table(df, title="Tabla"):
    """Tabla Plotly: texto a la izquierda, sin celdas vacías, anchos legibles, título sin cortar."""
    try:
        import plotly.graph_objects as go
        import pandas as pd
        import numpy as np
    except ImportError:
        return False
    if df is None:
        return False
    try:
        d = df.copy()
        if not isinstance(d, pd.DataFrame):
            d = pd.DataFrame(d)
        if d.empty:
            return False
        # Índice con nombre útil (años, etc.)
        if not isinstance(d.index, pd.RangeIndex) or (d.index.name is not None):
            try:
                name = d.index.name or "Año"
                d = d.reset_index()
                if "index" in d.columns:
                    d = d.rename(columns={"index": name if name != "index" else "Año"})
            except Exception:
                pass
        d = d.head(60)
        cols = [str(c) for c in d.columns]

        TEXT_KEYS = (
            "interpretación", "interpretacion", "lectura sencilla", "lectura", "detalle",
            "comentario", "mensaje", "descripción", "descripcion", "motivo", "nota", "prueba",
            "indicador", "escenario", "nombre", "empresa", "ticker", "estado", "resultado",
            "veredicto", "fuente", "origen", "recomend",
        )

        def _is_text_col(colname):
            cl = str(colname).lower().strip()
            return any(t in cl for t in TEXT_KEYS)

        def _is_year_col(colname):
            cl = str(colname).lower().strip()
            return cl in ("año", "ano", "year", "t", "periodo", "index")

        def _fmt(v, colname):
            # Celdas vacías / NaN → guión legible
            if v is None:
                return "—"
            try:
                if isinstance(v, float) and (v != v or np.isinf(v)):
                    return "—"
            except Exception:
                pass
            if isinstance(v, str) and not v.strip():
                return "—"
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                fv = float(v)
                if _is_year_col(colname) and 1900 <= fv <= 2100 and abs(fv - round(fv)) < 1e-9:
                    return str(int(round(fv)))
                if abs(fv) >= 1000:
                    return f"{fv:,.1f}"
                if abs(fv) >= 100:
                    return f"{fv:,.2f}"
                if abs(fv) >= 1:
                    return f"{fv:,.2f}"
                return f"{fv:.4g}"
            text = str(v).strip()
            if not text:
                return "—"
            # Texto largo: soft-wrap, sin truncar demasiado
            max_chars = 320 if _is_text_col(colname) else 120
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            if _is_text_col(colname) and len(text) > 48:
                parts, line, n = [], "", 0
                for w in text.split():
                    if n + len(w) + 1 > 48 and line:
                        parts.append(line)
                        line, n = w, len(w)
                    else:
                        line = (line + " " + w).strip()
                        n = len(line)
                if line:
                    parts.append(line)
                return "<br>".join(parts) if parts else "—"
            return text

        cell_vals = []
        for c in d.columns:
            cell_vals.append([_fmt(v, str(c)) for v in d[c].tolist()])

        # Anchos relativos (Plotly los normaliza). Priorizar columnas de texto.
        widths = []
        for c, vals in zip(cols, cell_vals):
            cl = c.lower().strip()
            if _is_year_col(c):
                widths.append(56)
            elif _is_text_col(c):
                plain = max((len(x.replace("<br>", " ")) for x in vals), default=12)
                # lectura / interpretación más ancha
                if any(k in cl for k in ("lectura", "interpret", "detalle", "comentario", "mensaje")):
                    widths.append(int(min(340, max(200, plain * 6))))
                else:
                    widths.append(int(min(220, max(120, plain * 7))))
            else:
                plain_lens = [len(x.replace("<br>", " ")) for x in vals]
                maxlen = max(plain_lens + [len(c)], default=6)
                widths.append(int(min(140, max(72, maxlen * 8))))

        n_rows = len(d)
        fill = []
        for _ in cols:
            fill.append(["#1E293B" if i % 2 == 0 else "#151C2C" for i in range(n_rows)])

        # Alineación: preferencia izquierda (títulos y celdas)
        aligns = ["left"] * len(cols)

        has_wrap = any("<br>" in str(x) for col in cell_vals for x in col)
        cell_h = 40 if has_wrap else 30
        header_h = 36

        fig = go.Figure(data=[go.Table(
            columnwidth=widths,
            header=dict(
                values=[f"<b>{c}</b>" for c in cols],
                fill_color="#0F766E",
                font=dict(color="#ECFDF5", size=12, family="IBM Plex Sans"),
                align=aligns,
                height=header_h,
            ),
            cells=dict(
                values=cell_vals,
                fill_color=fill,
                font=dict(color="#F1F5F9", size=12, family="IBM Plex Sans"),
                align=aligns,
                height=cell_h,
            ),
        )])
        # Título fuera del plotly (evita cortes); solo caption en layout mínimo
        fig.update_layout(
            paper_bgcolor="#0F172A",
            plot_bgcolor="#0F172A",
            margin=dict(l=4, r=4, t=8, b=4),
            height=min(48 + header_h + cell_h * n_rows, 780),
        )
        if title:
            st.markdown(
                f'<div class="tf-section-title" style="margin:0.35rem 0 0.5rem 0">{title}</div>',
                unsafe_allow_html=True,
            )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        return True
    except Exception as e:
        st.caption(f"Tabla: {e}")
        return False



def _show_df(df, label=None, csv_key=None):
    """Preferir tabla Plotly; respaldo st.dataframe con ancho completo. CSV opcional."""
    if df is None:
        return
    title = label or "Datos"
    if _plotly_table(df, title=title):
        pass
    else:
        if label:
            st.markdown(
                f'<div class="tf-section-title" style="margin:0.35rem 0 0.5rem 0">{title}</div>',
                unsafe_allow_html=True,
            )
        try:
            st.dataframe(df, use_container_width=True, hide_index=True)
        except TypeError:
            try:
                st.dataframe(df, use_container_width=True)
            except Exception:
                st.write(df)
        except Exception:
            st.write(df)
    # Export CSV
    if csv_key and hasattr(df, "to_csv"):
        try:
            csv_bytes = df.to_csv(index=True).encode("utf-8")
            st.download_button(
                f"⬇ CSV · {title}",
                csv_bytes,
                file_name=f"{csv_key}.csv",
                mime="text/csv",
                key=f"dl_{csv_key}",
                use_container_width=False,
            )
        except Exception:
            pass


def _banner_calidad_datos(empresa, archivo=None, usar_publicos=True):
    """Banner persistente de calidad/origen de datos."""
    try:
        msg = ""
        tk = None
        try:
            emp = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
            if emp:
                tk = emp.get("ticker_yf") or emp.get("ticker_bvc")
                if emp.get("fuente"):
                    msg = str(emp.get("fuente"))
                elif empresa in getattr(L, "EMPRESAS", {}):
                    msg = "Serie de catálogo/curada (ilustrativa)"
        except Exception:
            pass
        if archivo is not None:
            msg = "Estados / Excel del usuario"
        if not msg:
            msg = "Mixto / revisar fuente"
        try:
            proc = L.procedencia_datos(msg, ticker_yf=tk, mkt=None)
            nivel = proc.get("nivel_calidad", "MEDIA")
            fuente = proc.get("fuente_financiera", msg)
        except Exception:
            nivel, fuente = "MEDIA", msg
        color = {"ALTA": "#34D399", "MEDIA": "#FBBF24", "MEDIA-BAJA": "#F59E0B", "BAJA": "#F87171"}.get(nivel, "#94A3B8")
        st.markdown(
            f'<div class="tf-info" style="border-color:{color}">'
            f'<b>Calidad de datos · {nivel}</b> — {fuente}. '
            f'El acabado profesional no implica EEFF auditados. Valida supuestos antes de decidir.'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass


def _wizard_flujo():
    """Strip de 4 pasos (workflow)."""
    st.markdown(
        """
        <div class="tf-kpi-grid" style="margin-bottom:0.85rem">
          <div class="tf-kpi"><div class="label">Paso 1</div><div class="value" style="font-size:1rem">Emisor / datos</div><div class="sub">Catálogo · Yahoo · Excel</div></div>
          <div class="tf-kpi"><div class="label">Paso 2</div><div class="value" style="font-size:1rem">Capital y WACC</div><div class="sub">D/E · CAPM · g · bridge</div></div>
          <div class="tf-kpi accent"><div class="label">Paso 3</div><div class="value" style="font-size:1rem">Generar modelo</div><div class="sub">Todo o por pestaña</div></div>
          <div class="tf-kpi"><div class="label">Paso 4</div><div class="value" style="font-size:1rem">Informe</div><div class="sub">Auditoría · PDF · comité</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _mostrar_reconciliacion_deuda(deuda_neta, caja, deuda_es_bruta=False):
    try:
        if hasattr(L, "reconciliar_deuda_bridge"):
            rec = L.reconciliar_deuda_bridge(deuda_neta=deuda_neta, caja=caja, deuda_es_bruta=deuda_es_bruta)
            with st.expander("Reconciliación deuda · puente EV→Equity", expanded=False):
                st.caption("Evita doble conteo de caja. Preferible pasar deuda ya neta.")
                _show_df(rec.get("df"), "Puente de deuda", csv_key="reconciliacion_deuda")
    except Exception:
        pass


def _plotly_comparacion_drivers(df_hist, title="Comparación de drivers · original vs normalizado"):
    """
    Gráficos Plotly (mismo estilo que fan chart) para drivers:
    línea original + normalizada + atípicos marcados, con hover.
    Siempre muestra al menos FCFF / Ingresos / EBITDA si existen.
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return False
    if df_hist is None or not hasattr(df_hist, "columns"):
        return False

    try:
        d = df_hist.copy()
        if "Año" in d.columns:
            d = d.set_index("Año")
        # Asegurar índice numérico de años
        try:
            d.index = d.index.astype(int)
        except Exception:
            pass

        series_map = {}  # nombre -> (y_orig, y_norm, mask, years)

        def _hampel_pair(s):
            s = pd.to_numeric(s, errors="coerce")
            med = float(s.median()) if s.notna().any() else 0.0
            mad = float((s - med).abs().median()) or 1e-9
            thr = 3.5 * 1.4826 * mad
            mask = (s - med).abs() > thr
            lo, hi = med - thr, med + thr
            s_n = s.clip(lower=lo, upper=hi)
            return s, s_n, mask

        # 1) Intentar detección formal (puede fallar si faltan columnas)
        try:
            if hasattr(L, "detectar_atipicos_drivers"):
                det = L.detectar_atipicos_drivers(d) or {}
                for clave, info in det.items():
                    s = info.get("serie_orig")
                    s_n = info.get("serie_norm")
                    mask = info.get("mask")
                    if s is None:
                        continue
                    years = [int(i) for i in (s.index.tolist() if hasattr(s, "index") else range(len(s)))]
                    series_map[str(clave)] = (s, s_n, mask, years)
        except Exception:
            pass

        # 2) Siempre añadir series contables disponibles (comparación visual)
        for col in ("FCFF", "Ingresos", "EBITDA", "CAPEX", "EBIT"):
            if col not in d.columns:
                continue
            if col in series_map:
                continue
            try:
                s, s_n, mask = _hampel_pair(d[col])
                years = [int(i) for i in s.index.tolist()]
                series_map[col] = (s, s_n, mask, years)
            except Exception:
                continue

        if not series_map:
            return False

        # Hasta 4 series en grilla 2×2 (compacto: dos por fila)
        items = list(series_map.items())[:4]
        n = len(items)
        nrows = (n + 1) // 2
        ncols = 2 if n > 1 else 1
        titles = []
        for k, _ in items:
            titles.append(f"{k}")
        while len(titles) < nrows * ncols:
            titles.append("")
        fig = make_subplots(
            rows=nrows, cols=ncols,
            subplot_titles=titles,
            vertical_spacing=0.16 if nrows > 1 else 0.12,
            horizontal_spacing=0.10,
        )

        for idx, (clave, (s, s_n, mask, years)) in enumerate(items):
            row = idx // ncols + 1
            col = idx % ncols + 1
            y0 = [float(v) if v == v else None for v in s.tolist()]
            y1 = [float(v) if v == v else None for v in s_n.tolist()] if s_n is not None else y0
            x = years

            fig.add_trace(go.Scatter(
                x=x, y=y0, mode="lines+markers",
                name="Original" if idx == 0 else f"{clave} orig",
                line=dict(color="#38BDF8", width=2.4),
                marker=dict(size=7),
                hovertemplate=(
                    f"<b>{clave} · dato real</b><br>Año %{{x}}<br>Valor: <b>%{{y:,.2f}}</b><br>"
                    "<i>Así se reportó en los estados financieros.</i>"
                    "<extra></extra>"
                ),
                showlegend=(idx == 0),
                legendgroup="orig",
            ), row=row, col=col)

            fig.add_trace(go.Scatter(
                x=x, y=y1, mode="lines+markers",
                name="Normalizado" if idx == 0 else f"{clave} norm",
                line=dict(color="#2DD4BF", width=2.4, dash="dash"),
                marker=dict(size=7),
                hovertemplate=(
                    f"<b>{clave} · suavizado</b><br>Año %{{x}}<br>Valor: <b>%{{y:,.2f}}</b><br>"
                    "<i>Versión sin picos extremos, más útil para proyectar.</i>"
                    "<extra></extra>"
                ),
                showlegend=(idx == 0),
                legendgroup="norm",
            ), row=row, col=col)

            try:
                msk = mask.tolist() if hasattr(mask, "tolist") else list(mask)
                xa = [x[j] for j, f in enumerate(msk) if f and j < len(x)]
                ya = [y0[j] for j, f in enumerate(msk) if f and j < len(y0)]
                if xa:
                    fig.add_trace(go.Scatter(
                        x=xa, y=ya, mode="markers",
                        name="Atípico" if idx == 0 else f"Atíp. {clave}",
                        marker=dict(size=11, color="#F87171", symbol="x", line=dict(width=1.5, color="#FECACA")),
                        hovertemplate=(
                            f"<b>Año raro · {clave}</b><br>Año %{{x}}<br>Valor: <b>%{{y:,.2f}}</b><br>"
                            "<i>Punto muy lejos del resto. Puede ser un evento único (venta, crisis, etc.).</i>"
                            "<extra></extra>"
                        ),
                        showlegend=(idx == 0),
                        legendgroup="atip",
                    ), row=row, col=col)
            except Exception:
                pass

            if x:
                fig.update_xaxes(
                    range=[min(x) - 0.4, max(x) + 0.4],
                    dtick=1, tickmode="linear",
                    title_text="Año" if row == nrows else "",
                    row=row, col=col,
                )
            fig.update_yaxes(title_text="", row=row, col=col)

        _finish_plotly(fig, title=title, height=max(360, 280 * nrows))
        st.caption(
            "Azul = dato real · teal punteado = suavizado (sin picos extremos) · cruz roja = año atípico. "
            "Pasa el cursor: cada punto te explica en lenguaje simple qué estás viendo."
        )
        return True
    except Exception as e:
        st.caption(f"Comparación drivers Plotly: {e}")
        return False


# Alias para llamadas antiguas
def _plotly_atipicos(df_hist, title="Comparación de drivers · original vs normalizado"):
    return _plotly_comparacion_drivers(df_hist, title=title)


def _plotly_informe_panel(resultados, title="Resumen gráfico del informe", chart_key=None):
    """Panel 2×2 en Plotly a partir de resultados de sesión."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return False
    res = resultados or {}
    t1 = res.get("tab1")
    t2 = res.get("tab2")
    t5 = res.get("tab5")
    t6 = res.get("tab6")
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "A) FCFF historia y proyección",
            "B) Escenarios EV / Equity",
            "C) Flujos del proyecto",
            "D) Ranking sectorial",
        ),
        vertical_spacing=0.14,
        horizontal_spacing=0.10,
    )
    any_ok = False
    if t1 and isinstance(t1, (list, tuple)) and len(t1) > 2:
        df_h, df_p = t1[1], t1[2]
        c_h, c_p = _col_fcff(df_h), _col_fcff(df_p)
        xh = yh = []
        if c_h and df_h is not None:
            xh, yh = _years_from_df(df_h), [float(v) for v in df_h[c_h].values]
            fig.add_trace(go.Scatter(
                x=xh, y=yh, mode="lines+markers+text", name="Histórico",
                line=dict(color="#38BDF8", width=3),
                marker=dict(size=9, color="#38BDF8"),
                text=[f"{v:,.0f}" for v in yh],
                textposition="top center",
                textfont=dict(size=9, color="#E0F2FE"),
                hovertemplate=(
                    "<b>Lo que ya pasó · Año %{x}</b><br>"
                    "Dinero libre (FCFF): <b>%{y:,.1f}</b><br>"
                    "<i>Efectivo que sobró después de operar e invertir.</i>"
                    "<extra></extra>"
                ),
            ), row=1, col=1)
            any_ok = True
        if c_p and df_p is not None:
            xp, yp = _years_from_df(df_p), [float(v) for v in df_p[c_p].values]
            fig.add_trace(go.Scatter(
                x=xp, y=yp, mode="lines+markers+text", name="Proyectado",
                line=dict(color="#2DD4BF", width=3, dash="dash"),
                marker=dict(size=9, color="#2DD4BF"),
                text=[f"{v:,.0f}" for v in yp],
                textposition="top center",
                textfont=dict(size=9, color="#CCFBF1"),
                hovertemplate=(
                    "<b>Proyección · Año %{x}</b><br>"
                    "FCFF esperado: <b>%{y:,.1f}</b><br>"
                    "<i>Caso típico del modelo.</i>"
                    "<extra></extra>"
                ),
            ), row=1, col=1)
            xs = (xh or []) + (xp or [])
            if xs:
                fig.update_xaxes(range=[min(xs) - 0.4, max(xs) + 0.4], dtick=1, tickmode="linear", row=1, col=1)
            any_ok = True
    if t2 and isinstance(t2, (list, tuple)) and len(t2) > 1 and hasattr(t2[1], "columns"):
        df = t2[1]
        cols = {str(c).lower(): c for c in df.columns}
        esc = cols.get("escenario") or cols.get("nombre") or df.columns[0]
        x = [str(v) for v in df[esc].tolist()]
        for c in df.columns:
            cl = str(c).lower()
            if cl == str(esc).lower():
                continue
            if "ev" in cl and "ebitda" not in cl:
                y = pd.to_numeric(df[c], errors="coerce").fillna(0).tolist()
                fig.add_trace(go.Bar(name="EV", x=x, y=y, marker_color="#14B8A6",
                    text=[f"{v:,.0f}" for v in y], textposition="outside",
                    textfont=dict(size=11, color="#F8FAFC"),
                    hovertemplate=(
                        "<b>Escenario: %{x}</b><br>"
                        "Valor del negocio (EV): <b>%{y:,.1f}</b><br>"
                        "<i>Precio de toda la empresa, antes de restar deudas.</i>"
                        "<extra></extra>"
                    )), row=1, col=2)
                any_ok = True
            elif "equity" in cl:
                y = pd.to_numeric(df[c], errors="coerce").fillna(0).tolist()
                fig.add_trace(go.Bar(name="Equity", x=x, y=y, marker_color="#38BDF8",
                    text=[f"{v:,.0f}" for v in y], textposition="outside",
                    textfont=dict(size=11, color="#F8FAFC"),
                    hovertemplate=(
                        "<b>Escenario: %{x}</b><br>"
                        "Valor para dueños (Equity): <b>%{y:,.1f}</b><br>"
                        "<i>Lo que quedaría a los accionistas tras pagar deudas.</i>"
                        "<extra></extra>"
                    )), row=1, col=2)
    if t5 and isinstance(t5, (list, tuple)) and len(t5) > 1 and hasattr(t5[1], "columns"):
        df = t5[1]
        xcol = df.columns[0]
        ycol = next((c for c in df.columns if any(k in str(c).lower() for k in ("flujo", "fcff", "vpn", "flow"))), None)
        if ycol is None and len(df.columns) > 1:
            ycol = df.columns[1]
        if ycol is not None:
            x = [str(v) for v in df[xcol].tolist()]
            y = pd.to_numeric(df[ycol], errors="coerce").fillna(0).tolist()
            colors = ["#F87171" if v < 0 else "#34D399" for v in y]
            fig.add_trace(go.Bar(name="Flujos", x=x, y=y, marker_color=colors,
                text=[f"{v:,.0f}" for v in y], textposition="outside",
                textfont=dict(size=10, color="#F8FAFC"),
                hovertemplate=(
                    "<b>Periodo %{x}</b><br>"
                    "Flujo de caja: <b>%{y:,.1f}</b><br>"
                    "<i>Verde = entra dinero · Rojo = sale (inversión).</i>"
                    "<extra></extra>"
                )), row=2, col=1)
            any_ok = True
    if t6 and isinstance(t6, (list, tuple)) and len(t6) > 1 and hasattr(t6[1], "columns"):
        df = t6[1].copy()
        name_c = next((c for c in df.columns if str(c).lower() in ("nombre", "empresa", "ticker")), df.columns[0])
        # Preferir Score compuesto (no Ranking ni margen)
        score_c = next((c for c in df.columns if str(c).lower() == "score" or str(c).lower() == "puntaje"), None)
        if score_c is None:
            score_c = next((c for c in df.columns if "score" in str(c).lower()), None)
        rank_c = next((c for c in df.columns if str(c).lower() == "ranking"), None)
        if score_c is not None:
            df = df.assign(_sc=pd.to_numeric(df[score_c], errors="coerce")).dropna(subset=["_sc"])
            df = df.sort_values("_sc", ascending=False).head(12)
            labels = []
            for i, row in df.iterrows():
                emp = str(row[name_c])[:20]
                rk = int(row[rank_c]) if rank_c and pd.notna(row.get(rank_c)) else None
                labels.append(f"#{rk} · {emp}" if rk else emp)
            yv = df["_sc"].tolist()
            fig.add_trace(go.Bar(
                name="Score", y=labels, x=yv, orientation="h",
                marker_color="#14B8A6",
                text=[f"{v:.2f}" for v in yv],
                textposition="outside",
                textfont=dict(size=10, color="#F8FAFC"),
                hovertemplate=(
                    "<b>%{y}</b><br>Score compuesto: <b>%{x:.2f}</b><br>"
                    "<i>Mayor score = mejor posición relativa en el sector "
                    "(margen, ROIC, WACC, crecimiento, múltiplo).</i>"
                    "<extra></extra>"
                ),
            ), row=2, col=2)
            fig.update_yaxes(autorange="reversed", row=2, col=2)
            any_ok = True
    if not any_ok:
        return False
    ok = _finish_plotly(fig, title=title, height=740, key=chart_key or "tab7_informe_panel", barmode="group")
    st.caption(
        "Ejecuta antes las pestañas 1, 2, 5 y 6 para llenar los cuatro paneles. "
        "Pasa el cursor: cada punto o barra te explica el resultado en lenguaje simple."
    )
    return ok


def _plotly_layout(title="", height=520, legend_bottom=True):
    """Layout unificado: título limpio, leyenda sin solaparse, hover legible."""
    margin_t = 72 if title else 48
    margin_b = 88 if legend_bottom else 56
    legend = dict(
        bgcolor="rgba(15,23,42,0.92)",
        bordercolor="#64748B",
        borderwidth=1,
        font=dict(size=12, color="#F8FAFC"),
        orientation="h",
        x=0.5,
        xanchor="center",
    )
    if legend_bottom:
        legend.update(yanchor="top", y=-0.18)
    else:
        legend.update(yanchor="bottom", y=1.08, x=0, xanchor="left")
        margin_t = 100

    return dict(
        title=dict(
            text=title or "",
            font=dict(size=15, color="#F8FAFC", family="IBM Plex Sans"),
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(t=4, b=8),
        ),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#1E293B",
        font=dict(color="#F1F5F9", size=12, family="IBM Plex Sans, system-ui, sans-serif"),
        margin=dict(l=56, r=28, t=margin_t, b=margin_b),
        height=height,
        legend=legend,
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#0F172A",
            bordercolor="#14B8A6",
            font=dict(size=12, color="#F8FAFC"),
        ),
        xaxis=dict(
            gridcolor="#475569",
            tickfont=dict(size=11, color="#E2E8F0"),
            title_font=dict(size=12, color="#F1F5F9"),
            color="#E2E8F0",
            automargin=True,
            zerolinecolor="#64748B",
        ),
        yaxis=dict(
            gridcolor="#475569",
            tickfont=dict(size=11, color="#E2E8F0"),
            title_font=dict(size=12, color="#F1F5F9"),
            color="#E2E8F0",
            automargin=True,
            zeroline=True,
            zerolinecolor="#64748B",
        ),
    )


def _finish_plotly(fig, title="", height=520, key=None, **extra):
    """Aplica chrome unificado + subtítulos alineados + render."""
    layout = _plotly_layout(title, height=height, legend_bottom=True)
    layout.update(extra)
    fig.update_layout(**layout)
    # Subtítulos de make_subplots (anotaciones)
    try:
        fig.update_annotations(
            font=dict(size=13, color="#E2E8F0", family="IBM Plex Sans"),
            yshift=4,
        )
    except Exception:
        pass
    # Ejes secundarios en subplots
    try:
        fig.update_xaxes(
            gridcolor="#475569",
            tickfont=dict(size=11, color="#E2E8F0"),
            color="#E2E8F0",
            automargin=True,
        )
        fig.update_yaxes(
            gridcolor="#475569",
            tickfont=dict(size=11, color="#E2E8F0"),
            color="#E2E8F0",
            automargin=True,
            zeroline=True,
            zerolinecolor="#64748B",
        )
    except Exception:
        pass
    if key is not None:
        st.plotly_chart(fig, use_container_width=True, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True)
    return True



def _years_from_df(df):
    """Extrae años enteros del índice o columna Año."""
    if df is None:
        return []
    if "Año" in getattr(df, "columns", []):
        return [int(x) for x in df["Año"].tolist()]
    try:
        return [int(x) for x in df.index.tolist()]
    except Exception:
        return list(range(len(df)))


def _col_fcff(df):
    if df is None:
        return None
    for c in df.columns:
        if str(c).upper().replace(" ", "") in ("FCFF", "FCFF."):
            return c
        if "FCFF" in str(c).upper():
            return c
    return None


def _plotly_fan_fcff(df_hist, df_proj, title="Fan chart · FCFF"):
    """Gráfico nativo: histórico + proyección + banda simple. Eje = años reales."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False
    fig = go.Figure()
    years_all = []

    c_h = _col_fcff(df_hist)
    if df_hist is not None and c_h is not None:
        yh = _years_from_df(df_hist)
        vh = [float(v) for v in df_hist[c_h].values]
        years_all += yh
        fig.add_trace(go.Scatter(
            x=yh, y=vh, mode="lines+markers+text", name="FCFF histórico",
            line=dict(color="#38BDF8", width=3),
            marker=dict(size=10, color="#38BDF8"),
            text=[f"{v:,.0f}" for v in vh],
            textposition="top center",
            textfont=dict(size=10, color="#E0F2FE"),
            hovertemplate=(
                "<b>Lo que ya pasó · Año %{x}</b><br>"
                "Dinero libre (FCFF): <b>%{y:,.1f}</b><br>"
                "<i>Es el efectivo que sobró después de operar e invertir.</i>"
                "<extra></extra>"
            ),
        ))

    c_p = _col_fcff(df_proj)
    if df_proj is not None and c_p is not None:
        yp = _years_from_df(df_proj)
        vp = [float(v) for v in df_proj[c_p].values]
        years_all += yp
        # Banda de incertidumbre ±12% (lectura didáctica; MC detallado está en el fan MPL)
        lo = [v * 0.88 for v in vp]
        hi = [v * 1.12 for v in vp]
        fig.add_trace(go.Scatter(
            x=yp + yp[::-1], y=hi + lo[::-1],
            fill="toself", fillcolor="rgba(45,212,191,0.22)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Banda ≈ ±12%",
            hoverinfo="skip",
            showlegend=True,
        ))
        fig.add_trace(go.Scatter(
            x=yp, y=vp, mode="lines+markers+text", name="FCFF proyectado",
            line=dict(color="#2DD4BF", width=3, dash="dash"),
            marker=dict(size=10, color="#2DD4BF"),
            text=[f"{v:,.0f}" for v in vp],
            textposition="top center",
            textfont=dict(size=10, color="#CCFBF1"),
            hovertemplate=(
                "<b>Proyección · Año %{x}</b><br>"
                "FCFF esperado: <b>%{y:,.1f}</b><br>"
                "<i>Caso típico. La zona sombreada es un rango probable (±12%).</i>"
                "<extra></extra>"
            ),
        ))

    if not years_all:
        return False

    y0, y1 = min(years_all), max(years_all)
    fig.update_xaxes(
        title="Año",
        range=[y0 - 0.4, y1 + 0.4],
        dtick=1,
        tickmode="linear",
        autorange=False,
    )
    fig.update_yaxes(title="FCFF (miles de millones)")
    return _finish_plotly(fig, title=title, height=540)


def _plotly_escenarios(df):
    """Barras EV vs Equity con nombres y valores."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False
    if df is None or not hasattr(df, "columns"):
        return False
    cols = {str(c).lower(): c for c in df.columns}
    esc = None
    for k in ("escenario", "scenario", "nombre"):
        if k in cols:
            esc = cols[k]
            break
    if esc is None:
        esc = df.columns[0]
    ev_c = None
    eq_c = None
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("ev", "enterprise value", "valor empresa") or (cl.startswith("ev") and "ebitda" not in cl):
            ev_c = c
        if "equity" in cl or "dueño" in cl or "patrimonio" in cl:
            eq_c = c
    # fallback por posición
    nums = [c for c in df.columns if c != esc]
    if ev_c is None and len(nums) >= 1:
        ev_c = nums[0]
    if eq_c is None and len(nums) >= 2:
        eq_c = nums[1]
    x = [str(v) for v in df[esc].tolist()]
    fig = go.Figure()
    if ev_c is not None:
        yev = pd.to_numeric(df[ev_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            name="EV (negocio)", x=x, y=yev,
            marker_color="#14B8A6",
            text=[f"{v:,.0f}" for v in yev],
            textposition="outside",
            textfont=dict(size=12, color="#F8FAFC"),
            hovertemplate=(
                "<b>Escenario: %{x}</b><br>"
                "Valor del negocio (EV): <b>%{y:,.1f}</b><br>"
                "<i>Como el precio de toda la empresa, antes de restar deudas.</i>"
                "<extra></extra>"
            ),
        ))
    if eq_c is not None:
        yeq = pd.to_numeric(df[eq_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            name="Equity (dueños)", x=x, y=yeq,
            marker_color="#38BDF8",
            text=[f"{v:,.0f}" for v in yeq],
            textposition="outside",
            textfont=dict(size=12, color="#F8FAFC"),
            hovertemplate=(
                "<b>Escenario: %{x}</b><br>"
                "Valor para dueños (Equity): <b>%{y:,.1f}</b><br>"
                "<i>Lo que quedaría a los accionistas tras pagar deudas y otros compromisos.</i>"
                "<extra></extra>"
            ),
        ))
    if not fig.data:
        return False
    fig.update_xaxes(title="Escenario")
    fig.update_yaxes(title="Valor (miles de millones)")
    return _finish_plotly(fig, title="Escenarios · EV vs Equity", height=480, barmode="group",
                          uniformtext_minsize=10, uniformtext_mode="hide")


def _plotly_vpn_flows(df):
    """Flujos del proyecto con valores."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False
    if df is None or not hasattr(df, "columns") or len(df) == 0:
        return False
    xcol = df.columns[0]
    ycol = None
    for c in df.columns:
        cl = str(c).lower()
        if any(k in cl for k in ("flujo", "flow", "fcff", "cash", "vpn")):
            ycol = c
            break
    if ycol is None:
        for c in df.columns[1:]:
            if pd.api.types.is_numeric_dtype(df[c]):
                ycol = c
                break
    if ycol is None:
        return False
    x = [str(v) for v in df[xcol].tolist()]
    y = pd.to_numeric(df[ycol], errors="coerce").fillna(0).tolist()
    colors = ["#F87171" if v < 0 else "#34D399" for v in y]
    fig = go.Figure(go.Bar(
        x=x, y=y, marker_color=colors,
        text=[f"{v:,.0f}" for v in y],
        textposition="outside",
        textfont=dict(size=11, color="#F8FAFC"),
        hovertemplate=(
            "<b>Periodo %{x}</b><br>"
            "Flujo de caja: <b>%{y:,.1f}</b><br>"
            "<i>Verde = entra dinero · Rojo = sale (inversión). "
            "El payback es cuándo se recupera lo invertido.</i>"
            "<extra></extra>"
        ),
        name="Flujos",
    ))
    fig.add_hline(y=0, line_color="#94A3B8", line_width=1, line_dash="dot")
    fig.update_xaxes(title="Periodo")
    fig.update_yaxes(title="Flujo / VPN")
    return _finish_plotly(fig, title="Flujos del proyecto · VPN / recuperación", height=480)


def _plotly_valor_proyecto(df, wacc=None, chart_key=None):
    """
    Evolución del valor del proyecto = VPN acumulada con los flujos disponibles.
    Descuenta cada flujo al WACC: VPN_t = Σ CF_i / (1+WACC)^i
    Área roja: VPN acumulada < 0 (aún no recupera en valor presente).
    Área verde: VPN acumulada ≥ 0 (ya recuperó y crea valor).
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False
    if df is None or not hasattr(df, "columns") or len(df) == 0:
        return False

    xcol = df.columns[0]
    ycol = None
    for c in df.columns:
        cl = str(c).lower()
        if any(k in cl for k in ("flujo", "flow", "fcff", "cash")) and "acum" not in cl and "vpn" not in cl:
            ycol = c
            break
    if ycol is None:
        for c in df.columns:
            cl = str(c).lower()
            if any(k in cl for k in ("flujo", "flow", "fcff", "cash", "vpn")):
                ycol = c
                break
    if ycol is None:
        for c in df.columns[1:]:
            if pd.api.types.is_numeric_dtype(df[c]):
                ycol = c
                break
    if ycol is None:
        return False

    x_labels = [str(v) for v in df[xcol].tolist()]
    flujos = pd.to_numeric(df[ycol], errors="coerce").fillna(0).astype(float).tolist()
    n = len(flujos)
    if n == 0:
        return False

    # WACC efectivo
    try:
        r = float(wacc) if wacc is not None else 0.10
    except Exception:
        r = 0.10
    if r <= -0.99:
        r = 0.10

    # VPN period by period (descuento fin de año: t=0 sin descuento o con índice 0)
    # Convención: primer flujo en t=0 (inversión), luego t=1..n-1
    vpn_acum = []
    vpn = 0.0
    for t, cf in enumerate(flujos):
        vpn += float(cf) / ((1.0 + r) ** t)
        vpn_acum.append(vpn)

    vpn_final = vpn_acum[-1] if vpn_acum else 0.0

    # TIR (IRR) con los flujos disponibles
    tir = None
    try:
        tir_val = np.irr(flujos) if hasattr(np, "irr") else None
    except Exception:
        tir_val = None
    if tir_val is None:
        try:
            # Newton simple para IRR
            rate = 0.1
            for _ in range(50):
                npv = sum(cf / ((1 + rate) ** t) for t, cf in enumerate(flujos))
                dnpv = sum(-t * cf / ((1 + rate) ** (t + 1)) for t, cf in enumerate(flujos) if t > 0)
                if abs(dnpv) < 1e-12:
                    break
                rate_new = rate - npv / dnpv
                if abs(rate_new - rate) < 1e-8:
                    rate = rate_new
                    break
                rate = rate_new
            if -0.99 < rate < 5:
                tir = rate
        except Exception:
            tir = None
    else:
        tir = float(tir_val)

    # Payback en valor presente (primer t con vpn_acum >= 0)
    payback = None
    for t, v in enumerate(vpn_acum):
        if v >= 0:
            payback = t
            break

    # KPIs rápidos encima del gráfico
    try:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("VPN (datos disponibles)", f"{vpn_final:,.2f}", help=f"Descontada al WACC {r*100:.2f}%")
        with c2:
            st.metric("TIR", f"{tir*100:.2f}%" if tir is not None else "—")
        with c3:
            st.metric("Payback (VP)", f"t={payback}" if payback is not None else "No recupera en el horizonte")
    except Exception:
        pass

    fig = go.Figure()
    y_pos = [max(v, 0) for v in vpn_acum]
    y_neg = [min(v, 0) for v in vpn_acum]
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_pos, mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(52, 211, 153, 0.35)",
        name="Ya recuperó y gana (VPN≥0)", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x_labels, y=y_neg, mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(248, 113, 113, 0.35)",
        name="Aún no recupera (VPN<0)", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x_labels, y=vpn_acum, mode="lines+markers+text",
        name="VPN acumulada",
        line=dict(color="#1E3A5F", width=3),
        marker=dict(size=11, color="#1E3A5F"),
        text=[f"{v:,.1f}" for v in vpn_acum],
        textposition="top center",
        textfont=dict(size=10, color="#E2E8F0"),
        hovertemplate=(
            "<b>Periodo %{x}</b><br>"
            "VPN acumulada: <b>%{y:,.2f}</b><br>"
            f"<i>Flujos descontados al WACC {r*100:.2f}%. "
            "Cuando cruza cero, el proyecto recuperó la inversión en valor presente.</i>"
            "<extra></extra>"
        ),
    ))
    fig.add_hline(y=0, line_color="#94A3B8", line_width=1.5, line_dash="dash")
    fig.update_xaxes(title="Periodo")
    fig.update_yaxes(title="VPN acumulada (valor presente)")
    ok = _finish_plotly(
        fig,
        title=f"Cómo evoluciona el valor del proyecto · WACC {r*100:.2f}%",
        height=480,
        key=chart_key or "tab5_valor_proyecto",
    )
    return ok



def _plotly_sector(df):
    """Ranking sectorial por Score compuesto (mayor = mejor)."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return False
    if df is None or not hasattr(df, "columns") or len(df) == 0:
        return False
    d = df.copy()
    name_c = next((c for c in d.columns if str(c).lower() in ("nombre", "empresa", "ticker", "emisor")), d.columns[0])
    score_c = next((c for c in d.columns if str(c).lower() in ("score", "puntaje")), None)
    if score_c is None:
        score_c = next((c for c in d.columns if "score" in str(c).lower() and "rank" not in str(c).lower()), None)
    rank_c = next((c for c in d.columns if str(c).lower() == "ranking"), None)
    margen_c = next((c for c in d.columns if "margen" in str(c).lower()), None)
    mult_c = next((c for c in d.columns if "ev/ebitda" in str(c).lower() or "múltiplo" in str(c).lower() or "multiplo" in str(c).lower()), None)

    if score_c is not None:
        d["_sc"] = pd.to_numeric(d[score_c], errors="coerce")
        d = d.dropna(subset=["_sc"]).sort_values("_sc", ascending=False)
        labels = []
        for _, row in d.iterrows():
            emp = str(row[name_c])[:26]
            rk = int(row[rank_c]) if rank_c and pd.notna(row.get(rank_c)) else None
            labels.append(f"#{rk} · {emp}" if rk else emp)
        yv = d["_sc"].tolist()
        fig = go.Figure(go.Bar(
            y=labels, x=yv, orientation="h",
            marker_color="#14B8A6",
            text=[f"{v:.2f}" for v in yv],
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>Score compuesto: <b>%{x:.2f}</b><br>"
                "<i>Más alto = mejor posición relativa (margen, ROIC, WACC, crecimiento, múltiplo).</i>"
                "<extra></extra>"
            ),
        ))
        fig.update_xaxes(title="Score compuesto")
        fig.update_yaxes(autorange="reversed")
        return _finish_plotly(fig, title="Ranking sectorial por Score", height=max(400, 40 * len(labels) + 120))

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Margen EBITDA %", "EV/EBITDA (x)"))
    if margen_c is not None:
        ym = pd.to_numeric(df[margen_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            y=labels, x=ym, orientation="h", marker_color="#14B8A6", name="Margen",
            text=[f"{v:.1f}" for v in ym], textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>Margen EBITDA: <b>%{x:.1f}%</b><br>"
                "<i>De cada 100 de ventas, cuánto queda como utilidad operativa bruta.</i>"
                "<extra></extra>"
            ),
        ), row=1, col=1)
    if mult_c is not None:
        yx = pd.to_numeric(df[mult_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            y=labels, x=yx, orientation="h", marker_color="#38BDF8", name="Múltiplo",
            text=[f"{v:.1f}x" for v in yx], textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>EV/EBITDA: <b>%{x:.1f}x</b><br>"
                "<i>Cuántas veces el mercado paga la utilidad operativa. "
                "Muy bajo puede ser oportunidad o señal de riesgo.</i>"
                "<extra></extra>"
            ),
        ), row=1, col=2)
    if not fig.data:
        return False
    return _finish_plotly(fig, title="Comparables del sector",
                          height=max(420, 36 * len(labels) + 140), showlegend=False)


def _show_fig(fig, caption=None):
    """Respaldo estático Matplotlib si no hay Plotly nativo."""
    if fig is None:
        return
    if caption:
        st.caption(caption)
    if not HAS_MPL:
        st.warning("matplotlib no disponible")
        return
    try:
        fig.patch.set_facecolor("#F1F5F9")
        for ax in fig.get_axes():
            ax.set_facecolor("#FFFFFF")
            ax.tick_params(colors="#334155", labelsize=9)
            # Ajustar xlim a datos reales si hay líneas
            try:
                xs = []
                for line in ax.get_lines():
                    xs.extend([float(v) for v in line.get_xdata() if np.isfinite(v)])
                if xs:
                    x0, x1 = min(xs), max(xs)
                    if 1900 <= x0 <= 2100:
                        ax.set_xlim(x0 - 0.4, x1 + 0.4)
            except Exception:
                pass
    except Exception:
        pass
    st.pyplot(fig, clear_figure=False)
    try:
        plt.close(fig)
    except Exception:
        pass



def _listar_empresas():
    try:
        return L.listar_empresas_disponibles()
    except Exception:
        base = list(getattr(L, "EMPRESAS", {}).keys())
        extra = list(getattr(L, "EMPRESAS_RUNTIME", {}).keys())
        return base + [e for e in extra if e not in base]


def _kpi_card(label: str, value: str, sub: str = "", accent: bool = False, tip: str = "") -> str:
    cls = "tf-kpi accent" if accent else "tf-kpi"
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    tip_attr = f' data-tip="{tip}"' if tip else ""
    return (
        f'<div class="{cls}"{tip_attr}>'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}</div>"
    )


def _kpi_row(items: list[tuple]) -> None:
    """items: (label, value, sub?, accent?, tip?)"""
    cards = []
    for it in items:
        label, value = it[0], it[1]
        sub = it[2] if len(it) > 2 else ""
        accent = it[3] if len(it) > 3 else False
        tip = it[4] if len(it) > 4 else ""
        cards.append(_kpi_card(label, value, sub, accent, tip))
    st.markdown(f'<div class="tf-kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _esc_tip(tip: str) -> str:
    """Escapa comillas para atributo data-tip HTML."""
    if not tip:
        return ""
    s = str(tip).replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#39;")
    s = s.replace("<", "").replace(">", "")
    return s


def _metric_tip_card(label: str, value: str, tip: str, hint: str = "Pasa el cursor") -> str:
    tip_a = _esc_tip(tip)
    val = str(value) if value is not None else "—"
    return (
        f'<div class="tf-metric-tip" data-tip="{tip_a}">'
        f'<div class="m-label">{label}</div>'
        f'<div class="m-value">{val}</div>'
        f'<div class="m-hint">{hint}</div></div>'
    )


def _metrics_tip_row(items: list[tuple], cols: int = 4) -> None:
    """Fila de métricas con explicación al pasar el cursor.
    items: (label, value, tip)
    """
    cards = []
    for it in items:
        label, value = it[0], it[1]
        tip = it[2] if len(it) > 2 else ""
        cards.append(_metric_tip_card(label, value, tip))
    if cols == 3:
        cls = "tf-metrics-row cols-3"
    elif cols == 2:
        cls = "tf-metrics-row cols-2"
    else:
        cls = "tf-metrics-row"
    st.markdown(f'<div class="{cls}">{"".join(cards)}</div>', unsafe_allow_html=True)
    st.caption("💡 Pasa el cursor sobre cada número para leer qué significa, en palabras simples.")


def _explain(text: str) -> None:
    """Callout didáctico bajo resultados clave."""
    st.markdown(f'<div class="tf-explain">{text}</div>', unsafe_allow_html=True)


def _chart_tip(text: str) -> None:
    """Texto simple bajo una gráfica."""
    st.markdown(
        f'<div class="tf-chart-tip"><span>¿Qué mirar?</span>{text}</div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _market_tape_quotes():
    """Cinta de mercado: tickers globales + Colombia.

    `chg` siempre en **puntos porcentuales del día** (ej. -0.31 = −0,31 %).
    Nunca se devuelve fracción para evitar doble escalado en el render.
    """
    symbols = [
        ("AAPL", "Apple"),
        ("MSFT", "Microsoft"),
        ("NVDA", "NVIDIA"),
        ("GOOGL", "Alphabet"),
        ("AMZN", "Amazon"),
        ("META", "Meta"),
        ("JPM", "JPMorgan"),
        ("XOM", "Exxon"),
        ("EC", "Ecopetrol"),
        ("ISA.CL", "ISA"),
        ("CIB", "Bancolombia"),
        ("SPY", "S&P 500"),
    ]
    rows = []
    try:
        import yfinance as yf
    except ImportError:
        return [{"sym": s, "name": n, "px": None, "chg": None} for s, n in symbols]

    def _f(x):
        try:
            if x is None:
                return None
            v = float(x)
            if v != v or abs(v) == float("inf"):
                return None
            return v
        except Exception:
            return None

    blue_chips = {"AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "XOM", "SPY"}

    for sym, name in symbols:
        try:
            t = yf.Ticker(sym)
            px = None
            chg = None

            info = {}
            try:
                info = getattr(t, "info", {}) or {}
            except Exception:
                info = {}

            try:
                fi = getattr(t, "fast_info", None)
                if fi is not None:
                    px = _f(getattr(fi, "last_price", None) or (fi.get("last_price") if hasattr(fi, "get") else None))
                    prev_fi = _f(getattr(fi, "previous_close", None) or (fi.get("previous_close") if hasattr(fi, "get") else None))
                    if px is not None and prev_fi is not None and prev_fi != 0:
                        chg = 100.0 * (px - prev_fi) / prev_fi
            except Exception:
                pass

            if px is None:
                px = _f(info.get("regularMarketPrice") or info.get("currentPrice"))

            prev = _f(info.get("regularMarketPreviousClose") or info.get("previousClose"))
            if chg is None and px is not None and prev is not None and prev != 0:
                chg = 100.0 * (px - prev) / prev

            # yfinance: regularMarketChangePercent ya en puntos % (ej. -0.31)
            if chg is None:
                chg = _f(info.get("regularMarketChangePercent"))

            if chg is None:
                delta = _f(info.get("regularMarketChange"))
                if delta is not None and prev is not None and prev != 0:
                    chg = 100.0 * delta / prev

            if px is None or chg is None:
                try:
                    hist = t.history(period="10d", auto_adjust=True)
                    if hist is not None and len(hist) >= 2:
                        closes = [_f(v) for v in hist["Close"].tolist()]
                        closes = [c for c in closes if c is not None]
                        if len(closes) >= 2:
                            if px is None:
                                px = closes[-1]
                            if chg is None and closes[-2] != 0:
                                chg = 100.0 * (closes[-1] - closes[-2]) / closes[-2]
                except Exception:
                    pass

            if chg is not None and abs(chg) > 25.0 and sym.split(".")[0] in blue_chips:
                try:
                    hist = t.history(period="5d", auto_adjust=True)
                    if hist is not None and len(hist) >= 2:
                        c0 = _f(hist["Close"].iloc[-1])
                        c1 = _f(hist["Close"].iloc[-2])
                        if c0 is not None and c1 is not None and c1 != 0:
                            chg2 = 100.0 * (c0 - c1) / c1
                            if abs(chg2) <= 25.0:
                                chg = chg2
                                if px is None:
                                    px = c0
                except Exception:
                    pass

            rows.append({"sym": sym.split(".")[0], "name": name, "px": px, "chg": chg})
        except Exception:
            rows.append({"sym": sym.split(".")[0], "name": name, "px": None, "chg": None})
    return rows



def _ejecutar_comite_ia_sesion(empresa, w=None, de_ratio=1.0, g=0.03, moneda="COP"):
    """Comité IA (4+). Usado tras tab4 en Generar todo y en Solo pestaña 4. Retorna (ok, msg)."""
    try:
        prov_ia = (
            st.session_state.get("tab4_iaprov")
            or st.session_state.get("iaprov")
            or "gemini"
        )
        key_ui = (st.session_state.get("tab4_iakey") or "").strip() or (st.session_state.get("iakey") or "")
        key_eff = (
            _resolve_gemini_key(key_ui)
            if (prov_ia or "gemini") == "gemini"
            else ((key_ui or "").strip() or None)
        )
        if prov_ia == "gemini" and not key_eff:
            key_eff = _resolve_gemini_key(None)

        def _sf(x, default=0.0):
            try:
                if x is None:
                    return default
                if isinstance(x, str):
                    s = x.strip().replace("%", "").replace(",", "")
                    if not s or s in ("—", "-", "N/A", "n/a"):
                        return default
                    return float(s)
                v = float(x)
                if v != v or abs(v) == float("inf"):
                    return default
                return v
            except Exception:
                return default

        res = st.session_state.get("resultados") or {}
        w = w if isinstance(w, dict) else {}
        wacc_calc = float(w.get("wacc", 0.10) or 0.10)
        ke_calc = float(w.get("ke", 0.12) or 0.12)
        roic_calc = None  # Ausencia de ROIC no equivale a rentabilidad nula.
        val_ev = val_equity = vps_modelo = precio_mercado = upside = 0.0
        mon_m = str(moneda or "COP").upper()
        try:
            _alinear_moneda_y_precio(empresa)
        except Exception:
            pass
        try:
            if hasattr(L, "resolver_precio_mercado"):
                precio_mercado = _sf(L.resolver_precio_mercado(empresa), 0.0)
        except Exception:
            pass
        if precio_mercado <= 0:
            precio_mercado = _sf(st.session_state.get("precio_mercado_alineado"), 0.0)
        mon_px = str(
            st.session_state.get("moneda_precio_alineada")
            or (st.session_state.get("params") or {}).get("precio_moneda")
            or mon_m
        ).upper()

        t7 = res.get("tab7")
        kpi_map = {}
        if t7 and isinstance(t7, (list, tuple)) and len(t7) > 1:
            kpi_df = t7[1]
            if kpi_df is not None and hasattr(kpi_df, "columns"):
                cols = list(kpi_df.columns)
                if "Indicador" in cols and "Valor" in cols:
                    try:
                        for _, row in kpi_df.iterrows():
                            kpi_map[str(row["Indicador"])] = row["Valor"]
                    except Exception:
                        pass

        def _k(name, *alts):
            for n in (name,) + alts:
                if n in kpi_map:
                    return kpi_map[n]
            return None

        val_ev = _sf(_k("EV base", "EV"), val_ev)
        val_equity = _sf(_k("Equity base", "Equity"), val_equity)
        vps_modelo = _sf(_k("VPS modelo", "VPS", "Precio modelo"), vps_modelo)
        if precio_mercado <= 0:
            precio_mercado = _sf(_k("Precio mercado", "Precio actual", "Precio"), 0.0)
        up_raw = _k("Upside %", "Upside")
        if up_raw is not None:
            upside = _sf(up_raw, 0.0)
        wacc_k = _k("WACC %", "WACC")
        if wacc_k is not None:
            ww = _sf(wacc_k, wacc_calc * 100)
            wacc_calc = ww / 100.0 if ww > 1.0 else ww
        roic_k = _k("ROIC %", "ROIC")
        if roic_k is not None:
            rr = _sf(roic_k, 0.0)
            roic_calc = rr / 100.0 if rr > 1.0 else rr

        t2 = res.get("tab2")
        if t2 and isinstance(t2, (list, tuple)) and len(t2) > 1 and hasattr(t2[1], "columns"):
            df2 = t2[1]
            try:
                cols = {str(c).lower(): c for c in df2.columns}
                esc_c = cols.get("escenario") or cols.get("nombre") or df2.columns[0]
                for _, row in df2.iterrows():
                    label = str(row[esc_c]).lower()
                    if "base" not in label and "central" not in label:
                        continue
                    for c in df2.columns:
                        cl = str(c).lower()
                        if cl == str(esc_c).lower():
                            continue
                        if ("ev" in cl or "empresa" in cl) and "ebitda" not in cl and val_ev == 0:
                            val_ev = _sf(row[c], val_ev)
                        if ("equity" in cl or "dueño" in cl or "patrimonio" in cl) and val_equity == 0:
                            val_equity = _sf(row[c], val_equity)
            except Exception:
                pass

        t4 = res.get("tab4")
        # Prefer tab2 escenarios if tab7 aún no existe (orden 4+ antes de tab7)
        monedas_ok = mon_m.replace("$", "") == mon_px.replace("$", "")
        if not monedas_ok:
            upside = None  # Monedas incompatibles: no presentar 0% como si fuera calculado.
        # Fuente única de verdad para VPS/upside: misma conversión y guardas que el DCF.
        acciones_ctx = (st.session_state.get("params") or {}).get("acciones") or acciones
        if vps_modelo <= 0 and val_equity > 0 and acciones_ctx:
            vps_info = L.calcular_vps_y_upside(
                val_equity, acciones_ctx, precio_mercado=None,
                moneda_modelo=mon_m, moneda_precio=mon_m,
            )
            vps_modelo = vps_info.get("value_per_share") or 0.0
        if precio_mercado > 0 and vps_modelo > 0 and monedas_ok:
            # No inventar un upside de 0% cuando no había dato previo.
            upside_info = L.calcular_vps_y_upside(
                val_equity, acciones_ctx, precio_mercado=precio_mercado,
                moneda_modelo=mon_m, moneda_precio=mon_px,
            ) if val_equity > 0 and acciones_ctx else {}
            if upside_info.get("upside_pct") is not None:
                upside = upside_info["upside_pct"]

        ticker_ctx = "—"
        try:
            ticker_ctx = _inferir_ticker_yf(empresa, {}) or "—"
        except Exception:
            pass

        _metricas = {
            "empresa": empresa, "ticker": ticker_ctx, "moneda": mon_m,
            "moneda_precio": mon_px, "monedas_alineadas": monedas_ok,
            "precio_mercado": precio_mercado, "vps_modelo": vps_modelo, "upside": upside,
            "wacc_calc": wacc_calc, "ke_calc": ke_calc, "roic_calc": roic_calc,
            "de_ratio": float(de_ratio or 0), "g": float(g or 0),
            "val_ev": val_ev, "val_equity": val_equity, "decision_modelo": "—",
            # Declarar la escala estándar del DCF; si el usuario define otra, respetarla.
            "unidad_modelo": (st.session_state.get("params") or {}).get("unidad_modelo")
                or f"miles de millones de {mon_m}",
            "unidad_precio": "por acción",
            "fuente_precio": st.session_state.get("fuente_precio_mercado"),
            "fecha_precio": st.session_state.get("fecha_precio_mercado"),
            "fuente_valoracion": st.session_state.get("version_modelo_valoracion")
                or "DCF propio · modelacion_logic.py · escenarios base",
        }

        if not hasattr(L, "generar_recomendacion_comite_ia"):
            return False, (
                "modelacion_logic.py no tiene generar_recomendacion_comite_ia. "
                "Actualiza el archivo y reinicia Streamlit."
            )

        _audit_ctx = L.auditar_contexto_comite_ia(_metricas) if hasattr(L, "auditar_contexto_comite_ia") else {"ok": True, "errors": [], "warnings": []}
        if _audit_ctx.get("errors"):
            return False, "Comité IA bloqueado por errores: " + "; ".join(_audit_ctx["errors"])
        respuesta = L.generar_recomendacion_comite_ia(
            empresa, api_key=key_eff, proveedor=prov_ia or "gemini", metricas=_metricas,
        )
        _audit_resp = L.auditar_respuesta_comite_ia(respuesta) if hasattr(L, "auditar_respuesta_comite_ia") else {"ok": True, "errors": [], "warnings": []}
        if _audit_resp.get("errors"):
            return False, "Salida IA inválida: " + "; ".join(_audit_resp["errors"])
        if hasattr(L, "_sanear_salida_comite_ia"):
            try:
                plain = L._html_a_texto(respuesta, 20000) if hasattr(L, "_html_a_texto") else str(respuesta)
                plain = L._sanear_salida_comite_ia(plain)
                if plain and not str(plain).strip().startswith("<"):
                    import html as _html_mod
                    respuesta = (
                        '<div class="section-card" style="border-left:4px solid #14B8A6">'
                        f"<pre style='white-space:pre-wrap;color:#E8EEF7'>"
                        f"{_html_mod.escape(str(plain))}</pre></div>"
                    )
            except Exception:
                pass

        st.session_state["tab4_comite_ia_html"] = respuesta
        try:
            _struct = L.extraer_resumen_comite_ia(respuesta) if hasattr(L, "extraer_resumen_comite_ia") else {}
            _txt = (_struct or {}).get("texto") or (
                L._html_a_texto(respuesta, 800) if hasattr(L, "_html_a_texto") else str(respuesta)[:800]
            )
            L.guardar_resultado_tab("comite_ia", empresa, {
                "texto": _txt, "struct": _struct, "proveedor": prov_ia or "gemini",
            })
            st.session_state["tab4_comite_ia_texto"] = _txt
            st.session_state["tab4_comite_ia_struct"] = _struct
        except Exception:
            pass
        return True, "Comité IA generado."
    except Exception as e:
        st.session_state["tab4_comite_ia_html"] = None
        return False, str(e)


def _render_market_tape() -> None:
    data = _market_tape_quotes()
    parts = []

    def _finite(x):
        try:
            if x is None:
                return False
            v = float(x)
            return v == v and abs(v) != float("inf")
        except Exception:
            return False

    for d in data:
        chg = d.get("chg")
        px = d.get("px")
        # `chg` ya viene en puntos porcentuales (NO multiplicar otra vez).
        if not _finite(chg):
            cls, chg_txt = "tf-flat", "—"
        else:
            chg = float(chg)
            if chg > 0.02:
                cls, chg_txt = "tf-up", f"+{chg:.2f}%"
            elif chg < -0.02:
                cls, chg_txt = "tf-down", f"{chg:.2f}%"
            else:
                cls, chg_txt = "tf-flat", f"{chg:.2f}%"
        px_txt = f"{float(px):,.2f}" if _finite(px) else "—"
        parts.append(
            f'<span class="tf-tick"><b>{d["sym"]}</b> {d["name"]} '
            f'{px_txt} <span class="{cls}">{chg_txt}</span></span>'
        )
    inner = " ".join(parts + parts)
    st.markdown(
        f'<div class="tf-tape-wrap"><div class="tf-tape">{inner}</div></div>',
        unsafe_allow_html=True,
    )


def _section_start(title: str) -> None:
    st.markdown(
        f'<div class="tf-section"><div class="tf-section-title">{title}</div>',
        unsafe_allow_html=True,
    )


def _section_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)




# --- Didáctica: analogías, semáforo, tour, glosario ---
ANALOGIAS = {
    "WACC": "Como la tasa de interés de un préstamo: es lo mínimo que la empresa debe ‘ganar’ para que dueños y bancos queden contentos.",
    "Ke": "Lo que piden los accionistas por arriesgar su dinero (suele ser más alto que el costo de la deuda).",
    "FCFF": "El efectivo que sobra después de pagar la operación y las inversiones necesarias. Es la ‘plata libre’ del negocio.",
    "EV": "El valor de todo el negocio, como el precio de una casa antes de restar la hipoteca.",
    "Equity": "Lo que les quedaría a los dueños si se vendiera el negocio y se pagaran deudas y otros compromisos.",
    "g": "Qué tan rápido crece el efectivo a largo plazo. No puede ser más alto que la economía de forma sostenible.",
    "VPN": "Si es positivo, el proyecto deja más valor del que ‘cuesta’ el capital. Si es negativo, destruye valor con estos supuestos.",
    "TIR": "La rentabilidad anual implícita del proyecto. Se compara con el WACC: TIR > WACC suele ser buena señal.",
    "ROIC": "Cuánto gana la empresa por cada peso invertido en el negocio. Si supera al WACC, crea valor.",
    "D/E": "Cuánta deuda hay por cada peso de patrimonio. Más deuda = más riesgo y suele subir el costo del equity.",
}


def _analogy(term: str) -> None:
    t = ANALOGIAS.get(term)
    if t:
        st.markdown(
            f'<div class="tf-analogy"><em>{term}:</em> {t}</div>',
            unsafe_allow_html=True,
        )


def _semaforo(items):
    """items: list of (estado, titulo, detalle) estado in ok|warn|bad."""
    parts = []
    for estado, titulo, detalle in items:
        parts.append(
            f'<div class="tf-sem-card {estado}">'
            f'<div class="ttl"><span class="dot"></span>{titulo}</div>'
            f'<div class="dsc">{detalle}</div></div>'
        )
    st.markdown(f'<div class="tf-semaforo">{"".join(parts)}</div>', unsafe_allow_html=True)


def _semaforo_desde_checks(g, wacc, de_ratio, n_hist, tax):
    items = []
    # g vs WACC
    if g < wacc - 0.01:
        items.append(("ok", "Crecimiento (g)", f"g ({g*100:.1f}%) por debajo del WACC ({wacc*100:.1f}%): coherente."))
    elif g < wacc:
        items.append(("warn", "Crecimiento (g)", f"g ({g*100:.1f}%) muy cerca del WACC. El valor terminal se infla."))
    else:
        items.append(("bad", "Crecimiento (g)", f"g ≥ WACC. El modelo puede explotar: revisa g o el WACC."))
    # D/E
    if de_ratio <= 2.0:
        items.append(("ok", "Apalancamiento", f"D/E = {de_ratio:.2f}: nivel moderado."))
    elif de_ratio <= 3.0:
        items.append(("warn", "Apalancamiento", f"D/E = {de_ratio:.2f}: elevado; el equity es más sensible."))
    else:
        items.append(("bad", "Apalancamiento", f"D/E = {de_ratio:.2f}: muy alto para muchos sectores."))
    # Historia
    if n_hist >= 5:
        items.append(("ok", "Historia", f"{n_hist} años de datos: base razonable."))
    elif n_hist >= 3:
        items.append(("warn", "Historia", f"Solo {n_hist} años: las proyecciones son más frágiles."))
    else:
        items.append(("bad", "Historia", f"Muy poca historia ({n_hist}). Usa Excel propio o más años."))
    # Tax
    if 0.15 <= tax <= 0.40:
        items.append(("ok", "Impuestos", f"Tasa {tax*100:.0f}% en rango habitual."))
    else:
        items.append(("warn", "Impuestos", f"Tasa {tax*100:.0f}% atípica: confirma jurisdicción."))
    return items


def _tour_guiado():
    if st.session_state.get("tour_done"):
        return
    step = int(st.session_state.get("tour_step", 1))
    textos = {
        1: (
            "Paso 1 de 4 · Elige la empresa",
            "En la barra izquierda selecciona un emisor del catálogo o descárgalo de Yahoo (ticker como AAPL o EC). "
            "La <b>Ficha</b> resume sector y datos base.",
        ),
        2: (
            "Paso 2 de 4 · Revisa los parámetros",
            "Abre <b>Parámetros del modelo</b>. No hace falta ser experto: WACC y g son los dos más sensibles. "
            "Pasa el cursor por los KPIs verdes para ver definiciones.",
        ),
        3: (
            "Paso 3 de 4 · Genera el pronóstico",
            "Ve a la pestaña <b>1 · Pronóstico</b> y pulsa el botón principal. "
            "Sin esta proyección, las demás pestañas de valoración no tienen FCFF.",
        ),
        4: (
            "Paso 4 de 4 · Interpreta con semáforos",
            "Usa <b>Auditoría</b> y <b>Recomendación</b>. Los semáforos (verde / ámbar / rojo) resumen si los supuestos son sanos. "
            "La cinta de mercado de arriba es solo contexto del día.",
        ),
    }
    titulo, cuerpo = textos.get(step, textos[1])
    st.markdown(
        f'<div class="tf-tour"><h4>🧭 Tour rápido · {titulo}</h4><div>{cuerpo}</div></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if step > 1 and st.button("← Anterior", key="tour_prev"):
            st.session_state["tour_step"] = step - 1
            st.rerun()
    with c2:
        if step < 4 and st.button("Siguiente →", key="tour_next", type="primary"):
            st.session_state["tour_step"] = step + 1
            st.rerun()
        elif step >= 4 and st.button("Listo, empezar", key="tour_done_btn", type="primary"):
            st.session_state["tour_done"] = True
            st.rerun()
    with c3:
        if st.button("Saltar tour", key="tour_skip"):
            st.session_state["tour_done"] = True
            st.rerun()


def _glosario_chips():
    st.markdown('<div class="tf-chips">' + "".join(
        f'<span class="tf-chip">{k}</span>' for k in ANALOGIAS.keys()
    ) + "</div>", unsafe_allow_html=True)
    term = st.selectbox(
        "Explicar término",
        options=["(elige)"] + list(ANALOGIAS.keys()),
        key="gloss_term",
        label_visibility="collapsed",
    )
    if term and term != "(elige)":
        _analogy(term)



def _init_state():
    defaults = {
        "empresa_sel": None,
        "params": None,
        "rf": 0.12,
        "erp": 0.055,
        "crp": 0.0,
        "g_max_macro": 0.04,
        "archivo_bytes": None,
        "archivo_name": None,
        "usar_publicos": True,
        "resultados": {},
        "ficha_html": None,
        "hero_html": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state["empresa_sel"] is None:
        cats = _listar_empresas()
        st.session_state["empresa_sel"] = cats[0] if cats else ""


def _inferir_ticker_yf(nombre, p=None):
    """
    Ticker Yahoo de LA empresa `nombre` (nunca el de otra empresa en session).
    Orden: catálogo/runtime por nombre → heurística del nombre → params solo si
    el ticker de params es coherente con esa empresa.
    """
    def _norm(t):
        if t is None:
            return None
        t = str(t).strip().upper()
        if hasattr(L, "asegurar_sufijo_cl_bvc"):
            return L.asegurar_sufijo_cl_bvc(t)
        return t

    def _base(t):
        t = str(t or "").upper()
        if t.endswith(".CL"):
            return t[:-3]
        return t.split(".")[0]

    nombre = str(nombre or "").strip()
    tk_nombre = None

    # 1) Fuente de verdad: lógica / catálogo de ESTA empresa
    try:
        if hasattr(L, "ticker_canonico_empresa"):
            tk_nombre = L.ticker_canonico_empresa(nombre)
        elif hasattr(L, "ticker_yf_empresa"):
            tk_nombre = L.ticker_yf_empresa(nombre)
    except Exception:
        tk_nombre = None
    if not tk_nombre:
        try:
            emp = L.resolver_empresa(nombre) if hasattr(L, "resolver_empresa") else None
            if emp:
                tk_nombre = emp.get("ticker_yf") or emp.get("ticker_bvc")
        except Exception:
            pass

    # 2) Heurística desde el nombre visible ("ISA — Interconexión", "Apple Inc. — AAPL")
    if not tk_nombre and nombre:
        if "—" in nombre:
            part = nombre.split("—")[-1].strip().upper().replace(" ", "")
            if 1 <= len(part) <= 12 and part.replace(".", "").replace("-", "").isalnum():
                tk_nombre = part
        if not tk_nombre:
            head = nombre.split("—")[0].strip().upper()
            if head in ("ISA", "GEB", "CELSIA", "ECOPETROL", "EPM", "BVC", "ENELAM",
                        "PFBCOLOM", "GRUPOSURA", "NUTRESA"):
                tk_nombre = head

    tk_nombre = _norm(tk_nombre) if tk_nombre else None

    # 3) Params de sesión: solo si coinciden con el ticker de esta empresa
    p = p or {}
    tk_params = None
    for k in ("ticker_yf", "ticker_bvc", "ticker", "symbol"):
        t = p.get(k)
        if t and str(t).strip():
            tk_params = _norm(t)
            break
    if tk_nombre and tk_params:
        if _base(tk_nombre) == _base(tk_params):
            return tk_nombre
        # Params de OTRA empresa (p.ej. AAPL tras elegir ISA) → ignorar
        return tk_nombre
    if tk_nombre:
        return tk_nombre
    return tk_params


def _es_mercado_us(moneda=None, mercado=None, ticker=None, nombre=None):
    mon = str(moneda or "").upper().replace("$", "")
    merc = str(mercado or "").upper()
    if mon in ("USD", "US") or merc in ("US", "USA", "NYSE", "NASDAQ"):
        return True
    t = str(ticker or "").upper()
    # Tickers US típicos sin sufijo local (.CL, .MX, .SA, .L, etc.)
    if t and "." not in t and t.isalpha() and 1 <= len(t) <= 5:
        # Si el nombre/catalog sugiere Colombia, no forzar
        n = str(nombre or "").upper()
        if any(x in n for x in ("ECOPETROL", "BANCOLOMBIA", "ISA ", "NUTRESA", "CEMEX COL")):
            return False
        return True
    return False


def _alinear_moneda_y_precio(nombre):
    """
    Alinea moneda/precio de LA empresa `nombre`.
    No reutiliza ticker ni precio de otra empresa (p.ej. AAPL tras elegir ISA).
    """
    # Ticker siempre desde el nombre (ignora params de otra empresa)
    ticker = _inferir_ticker_yf(nombre, {})
    if hasattr(L, "asegurar_sufijo_cl_bvc") and ticker:
        ticker = L.asegurar_sufijo_cl_bvc(ticker) or ticker

    # Params base: catálogo de ESTA empresa, no el session completo de otra
    p = {}
    try:
        if hasattr(L, "params_empresa"):
            p = dict(L.params_empresa(nombre) or {})
    except Exception:
        p = {}
    # Conservar overrides del usuario solo si son de la misma empresa
    prev = dict(st.session_state.get("params") or {})
    prev_tk = str(prev.get("ticker_yf") or prev.get("ticker") or "").upper()
    same = False
    if ticker and prev_tk:
        b1 = prev_tk[:-3] if prev_tk.endswith(".CL") else prev_tk.split(".")[0]
        b2 = str(ticker).upper()
        b2 = b2[:-3] if b2.endswith(".CL") else b2.split(".")[0]
        same = (b1 == b2)
    if same:
        # mismos overrides de valoración del usuario
        for k in ("de_ratio", "kd", "tax", "g", "capex_extra", "beta_u", "capital_invertido",
                  "deuda_neta", "caja", "nci", "otros_claims", "asociados", "acciones",
                  "exit_multiple", "horizonte"):
            if k in prev and prev[k] is not None:
                p[k] = prev[k]
    # else: partimos limpio del catálogo de la empresa actual

    mm, mp = "COP", "COP"
    try:
        if hasattr(L, "monedas_alineadas_por_ticker"):
            emp = L.resolver_empresa(nombre) if hasattr(L, "resolver_empresa") else None
            mm, mp = L.monedas_alineadas_por_ticker(ticker=ticker, nombre_empresa=nombre, emp=emp or {})
        elif ticker and str(ticker).upper().endswith(".CL"):
            mm, mp = "COP", "COP"
        elif ticker and "." not in str(ticker):
            mm, mp = "USD", "USD"
    except Exception:
        if ticker and str(ticker).upper().endswith(".CL"):
            mm, mp = "COP", "COP"
        else:
            mm, mp = "USD", "USD"

    # Precio fresco SOLO del ticker de esta empresa
    precio = None
    try:
        if hasattr(L, "resolver_precio_mercado"):
            precio = L.resolver_precio_mercado(nombre)
        if (precio is None or float(precio) <= 0) and ticker:
            import yfinance as yf
            t = yf.Ticker(str(ticker))
            info = {}
            try:
                info = getattr(t, "info", None) or {}
            except Exception:
                info = {}
            for key in ("regularMarketPrice", "currentPrice", "previousClose"):
                try:
                    v = info.get(key)
                    if v is not None and float(v) == float(v) and float(v) > 0:
                        precio = float(v)
                        break
                except Exception:
                    continue
            if precio is None:
                try:
                    hist = t.history(period="5d", auto_adjust=True)
                    if hist is not None and len(hist) > 0:
                        precio = float(hist["Close"].iloc[-1])
                except Exception:
                    pass
    except Exception:
        pass
    try:
        precio = float(precio) if precio is not None else None
        if precio is not None and precio <= 0:
            precio = None
    except Exception:
        precio = None

    p["moneda"] = mm
    p["precio_moneda"] = mp
    p["moneda_precio"] = mp
    if ticker:
        p["ticker_yf"] = ticker
    # Borrar precio ajeno; solo guardar el de este ticker
    p.pop("precio", None)
    p.pop("precio_mercado", None)
    if precio is not None:
        p["precio"] = precio
        p["precio_mercado"] = precio

    # CAPM según mercado
    if mm == "USD":
        p["mercado_capm"] = p.get("mercado_capm") or "US"
        try:
            if float(st.session_state.get("rf", 0.12)) >= 0.08:
                st.session_state["rf"] = 0.045
            if float(st.session_state.get("erp", 0.055)) > 0.07:
                st.session_state["erp"] = 0.05
            st.session_state["crp"] = 0.0
        except Exception:
            pass
        try:
            if float(p.get("tax") or 0) >= 0.33:
                p["tax"] = 0.21
        except Exception:
            pass
    else:
        p["mercado_capm"] = p.get("mercado_capm") or "CO"

    st.session_state["params"] = p
    st.session_state["precio_mercado_alineado"] = p.get("precio_mercado") or p.get("precio")
    st.session_state["moneda_precio_alineada"] = mp
    st.session_state["fx_mismatch"] = False  # forzamos alineación

    try:
        emp = L.resolver_empresa(nombre) if hasattr(L, "resolver_empresa") else None
        if emp is None:
            emp = getattr(L, "EMPRESAS_RUNTIME", {}).get(nombre) or getattr(L, "EMPRESAS", {}).get(nombre)
        if emp and isinstance(emp, dict):
            if hasattr(L, "aplicar_monedas_a_empresa"):
                L.aplicar_monedas_a_empresa(nombre, emp)
            else:
                emp["moneda"] = mm
                emp["moneda_precio"] = mp
                emp.setdefault("params", {})["moneda"] = mm
                emp["params"]["precio_moneda"] = mp
            if ticker:
                emp["ticker_yf"] = ticker
            if precio is not None:
                emp["precio"] = precio
    except Exception:
        pass
    return p



def _cargar_params_empresa(nombre):
    try:
        out = L.al_cambiar_empresa(nombre)
        if isinstance(out, (list, tuple)) and len(out) >= 15:
            st.session_state["ficha_html"] = out[0]  # se regenera en cada run en el panel
            st.session_state["params"] = {
                "de_ratio": out[1],
                "kd": out[2],
                "tax": out[3],
                "g": out[4],
                "beta_u": out[5],
                "capital_invertido": out[6],
                "deuda_neta": out[7],
                "inversion_inicial": out[8],
                "caja": out[9],
                "nci": out[10],
                "otros_claims": out[11],
                "asociados": out[12],
                "acciones": out[13],
                "exit_multiple": out[14],
            }
            if len(out) > 15 and out[15] is not None:
                st.session_state["rf"] = float(out[15])
            if len(out) > 16 and out[16] is not None:
                st.session_state["erp"] = float(out[16])
            if len(out) > 17 and out[17] is not None:
                st.session_state["crp"] = float(out[17])
            if len(out) > 18 and out[18] is not None:
                st.session_state["g_max_macro"] = float(out[18])
            p_full = {}
            try:
                if hasattr(L, "params_empresa"):
                    p_full = L.params_empresa(nombre) or {}
            except Exception:
                p_full = {}
            mon = str(p_full.get("moneda") or (st.session_state.get("params") or {}).get("moneda") or "").upper()
            merc = str(p_full.get("mercado_capm") or "").upper()
            p = st.session_state.get("params") or {}
            for k in ("moneda", "mercado_capm", "deuda_es_bruta", "ticker_yf", "precio", "precio_mercado", "precio_moneda"):
                if k in p_full and p_full.get(k) is not None:
                    p[k] = p_full[k]
            st.session_state["params"] = p
            # Alinear moneda del modelo y del precio (corrige AAPL USD vs COP, etc.)
            _alinear_moneda_y_precio(nombre)
            return
    except Exception as e:
        st.session_state["ficha_html"] = f"<div>No se pudieron cargar params: {e}</div>"

    emp = None
    if hasattr(L, "resolver_empresa"):
        emp = L.resolver_empresa(nombre)
    if emp is None:
        emp = getattr(L, "EMPRESAS", {}).get(nombre) or getattr(L, "EMPRESAS_RUNTIME", {}).get(nombre)
    if not emp:
        return
    p = dict(emp.get("params", {}) or {})
    if emp.get("moneda") and not p.get("moneda"):
        p["moneda"] = emp.get("moneda")
    st.session_state["params"] = p
    st.session_state["ficha_html"] = f"<b>{nombre}</b> · {emp.get('sector', '')}"
    mon = str(p.get("moneda") or emp.get("moneda") or "").upper()
    if _es_mercado_us(moneda=mon, nombre=nombre):
        st.session_state["rf"] = 0.045
        st.session_state["erp"] = min(float(st.session_state.get("erp", 0.05)), 0.05)
        st.session_state["crp"] = 0.0
    else:
        st.session_state["rf"] = 0.12 if mon in ("COP", "") else 0.04
    _alinear_moneda_y_precio(nombre)


def _archivo_para_logic():
    data = st.session_state.get("archivo_bytes")
    name = st.session_state.get("archivo_name") or "upload.xlsx"
    if not data:
        return None
    import tempfile

    suffix = ".xlsx"
    low = name.lower()
    if low.endswith(".csv"):
        suffix = ".csv"
    elif low.endswith(".xls"):
        suffix = ".xls"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return tmp.name


def _wacc_quick(de_ratio, kd, tax, beta_u, rf, erp, crp):
    """CAPM + WACC alineado con modelacion_logic (beta_apalancado, costo_equity_capm, calcular_wacc)."""
    de = max(float(de_ratio), 0.0)
    t = float(tax)
    try:
        beta_l = float(L.beta_apalancado(float(beta_u), de, t)) if hasattr(L, "beta_apalancado") else float(beta_u) * (1.0 + (1.0 - t) * de)
    except Exception:
        beta_l = float(beta_u) * (1.0 + (1.0 - t) * de)
    try:
        ke = float(L.costo_equity_capm(beta_l, rf=float(rf), erp=float(erp), crp=float(crp or 0))) if hasattr(L, "costo_equity_capm") else float(rf) + beta_l * float(erp) + float(crp or 0)
    except Exception:
        ke = float(rf) + beta_l * float(erp) + float(crp or 0)
    try:
        out = L.calcular_wacc(de, float(kd), ke, t)
        wacc = float(out[0]) if isinstance(out, (tuple, list)) else float(out)
    except Exception:
        we = 1.0 / (1.0 + de)
        wd = de / (1.0 + de)
        wacc = we * ke + wd * float(kd) * (1.0 - t)
    return {"wacc": wacc, "ke": ke, "beta_l": beta_l}


# =============================================================================
# MAIN
# =============================================================================
def _aplicar_empresa_pendiente():
    """Aplica cambio de empresa ANTES de crear widgets (evita StreamlitWidgetAlreadyInstantiatedError)."""
    pend = st.session_state.pop("_pending_empresa", None)
    if not pend:
        return
    st.session_state["empresa_sel"] = pend
    # Solo tocar keys de widgets si aún no se instanciaron en este run (estamos al inicio)
    st.session_state["select_empresa"] = pend
    st.session_state["mobile_select_empresa"] = pend


def _solicitar_cambio_empresa(display_name, params_tuple=None, cargar_params=True):
    """Programa cambio de empresa para el próximo run (no mutar keys de widgets ya creados)."""
    st.session_state["_pending_empresa"] = display_name
    st.session_state["empresa_sel"] = display_name
    # Limpiar datos de la empresa anterior (evita precio/ticker AAPL en ficha ISA)
    for _k in (
        "precio_mercado_alineado", "moneda_precio_alineada", "fx_mismatch",
        "tab4_comite_ia_html", "tab4_comite_empresa", "resultados",
    ):
        st.session_state.pop(_k, None)
    st.session_state["resultados"] = {}
    st.session_state["params"] = {}
    if params_tuple is not None and len(params_tuple) >= 14:
        keys = [
            "de_ratio", "kd", "tax", "g", "beta_u",
            "capital_invertido", "deuda_neta", "inversion_inicial",
            "caja", "nci", "otros_claims", "asociados",
            "acciones", "exit_multiple",
        ]
        st.session_state["params"] = {k: params_tuple[i] for i, k in enumerate(keys)}
    if cargar_params:
        try:
            _cargar_params_empresa(display_name)
        except Exception:
            pass
    st.session_state["resultados"] = {}
    try:
        L.reset_resultados_sesion(display_name)
    except Exception:
        pass
    st.rerun()


def main():
    _init_state()
    _aplicar_empresa_pendiente()

    # ----- Hero -----
    st.markdown(
        """
        <div class="tf-hero">
          <h1>◈ Modelación Financiera y Riesgo</h1>
          <p>Proyección · DCF · Auditoría · VPN/TIR · Sector · Informe · Consulta asistida</p>
          <span class="tf-badge">Apoyo a decisión · No es asesoría de inversión</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Workflow 4 pasos
    try:
        _wizard_flujo()
    except Exception:
        pass

    # Cinta de mercado (tickers + variación del día)
    try:
        _render_market_tape()
    except Exception:
        pass

    # Tour guiado (primera visita)
    if "tour_done" not in st.session_state:
        st.session_state["tour_done"] = False
    if "tour_step" not in st.session_state:
        st.session_state["tour_step"] = 1
    _tour_guiado()

    # ========== SIDEBAR ==========
    with st.sidebar:
        st.markdown("### Terminal")
        st.markdown('<p class="tf-sidebar-label">Empresa</p>', unsafe_allow_html=True)

        with st.expander("Buscar Yahoo Finance", expanded=False):
            tq = st.text_input("Ticker", placeholder="AAPL · EC · ISA.CL", label_visibility="collapsed")
            peers = st.text_input("Peers", placeholder="MSFT,GOOGL", label_visibility="collapsed")
            if st.button("Descargar datos", type="primary", use_container_width=True):
                with st.spinner("Yahoo Finance…"):
                    try:
                        ok, html, display_name, params_tuple = L.buscar_y_descargar_empresa(
                            tq, peers_tickers=peers or ""
                        )
                    except Exception as e:
                        ok, html, display_name, params_tuple = False, str(e), None, None
                if ok and display_name:
                    st.success("Cargada")
                    _solicitar_cambio_empresa(display_name, params_tuple=params_tuple)
                    try:
                        _alinear_moneda_y_precio(display_name)
                    except Exception:
                        pass
                else:
                    st.error("Sin datos")
                    _html(html)

        catalogo = _listar_empresas()
        if st.session_state["empresa_sel"] not in catalogo and catalogo:
            st.session_state["empresa_sel"] = catalogo[0]
        if "select_empresa" not in st.session_state or st.session_state["select_empresa"] not in catalogo:
            st.session_state["select_empresa"] = st.session_state["empresa_sel"]

        empresa = st.selectbox("Emisor", options=catalogo, key="select_empresa", label_visibility="collapsed")
        if empresa != st.session_state.get("empresa_sel"):
            # No asignar select_empresa aquí (el widget ya existe). Solo sincronizar estado y recargar.
            st.session_state["empresa_sel"] = empresa
            _cargar_params_empresa(empresa)
            st.session_state["resultados"] = {}
            try:
                L.reset_resultados_sesion(empresa)
            except Exception:
                pass
            st.rerun()

        if st.session_state.get("params") is None:
            _cargar_params_empresa(empresa)

        # Ficha siempre visible como acordeón abierto por defecto
        with st.expander("Ficha", expanded=True):
            # Ficha SIEMPRE regenerada (no HTML cacheado con métricas N/D o ticker ajeno)
            try:
                _ficha_live = L.card_empresa_seleccionada(empresa)
                st.session_state["ficha_html"] = _ficha_live
                _html(_ficha_live)
            except Exception as _e_ficha:
                if st.session_state.get("ficha_html"):
                    _html(st.session_state["ficha_html"])
                else:
                    st.caption(f"No se pudo generar la ficha: {_e_ficha}")

        st.markdown('<p class="tf-sidebar-label">Estados financieros</p>', unsafe_allow_html=True)
        up = st.file_uploader("Excel / CSV", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
        if up is not None:
            st.session_state["archivo_bytes"] = up.read()
            st.session_state["archivo_name"] = up.name
        st.session_state["usar_publicos"] = st.checkbox(
            "Datos públicos si no hay Excel",
            value=st.session_state.get("usar_publicos", True),
        )
        try:
            ruta = getattr(L, "RUTA_PLANTILLA_EEFF", None) or L.asegurar_plantilla_excel()
            if ruta and os.path.isfile(ruta):
                with open(ruta, "rb") as f:
                    st.download_button(
                        "Plantilla EEFF",
                        f,
                        file_name="Plantilla_EEFF.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
        except Exception:
            pass

        ek = str(empresa)[:48]
        p = st.session_state.get("params") or {}

        # Parámetros en acordeón cerrado por defecto (menos ruido en el sidebar)
        with st.expander("Parámetros del modelo", expanded=False):
            horizonte = st.slider("Horizonte (años)", 3, 10, 5, key=f"hor_{ek}")
            de_ratio = st.slider("D/E", 0.0, 5.0, float(p.get("de_ratio", 1.2) or 1.2), 0.01, key=f"de_{ek}")
            kd = st.slider("Kd", 0.0, 0.25, float(p.get("kd", 0.08) or 0.08), 0.005, key=f"kd_{ek}")
            tax = st.slider("Tax", 0.0, 0.50, float(p.get("tax", 0.35) or 0.35), 0.01, key=f"tax_{ek}")
            g = st.slider("g terminal", 0.0, 0.08, float(p.get("g", 0.03) or 0.03), 0.005, key=f"g_{ek}")
            capex_extra = st.slider("CAPEX extra", 0, 8000, 0, 50, key=f"cx_{ek}")
            beta_u = st.slider("β unlevered", 0.0, 3.0, float(p.get("beta_u", 0.5) or 0.5), 0.05, key=f"bu_{ek}")

            st.markdown("**CAPM**")
            rf = st.slider("rf", 0.02, 0.16, float(st.session_state.get("rf", 0.12)), 0.005, key=f"rf_{ek}")
            erp = st.slider("ERP", 0.03, 0.10, float(st.session_state.get("erp", 0.055)), 0.005, key=f"erp_{ek}")
            crp = st.slider("CRP", 0.0, 0.05, float(st.session_state.get("crp", 0.0)), 0.005, key=f"crp_{ek}")

            st.markdown("**Puente a equity**")
            capital_invertido = st.number_input(
                "Capital invertido", value=float(p.get("capital_invertido", 0) or 0), step=100.0, key=f"ci_{ek}"
            )
            deuda_neta = st.number_input(
                "Deuda neta", value=float(p.get("deuda_neta", 0) or 0), step=100.0, key=f"dn_{ek}"
            )
            inversion_inicial = st.number_input(
                "Inversión proyecto", value=float(p.get("inversion_inicial", 0) or 0), step=10.0, key=f"ii_{ek}"
            )
            caja = st.number_input("Caja", value=float(p.get("caja", 0) or 0), step=50.0, key=f"caja_{ek}")
            nci = st.number_input("NCI", value=float(p.get("nci", 0) or 0), step=50.0, key=f"nci_{ek}")
            otros_claims = st.number_input(
                "Otros claims", value=float(p.get("otros_claims", 0) or 0), step=50.0, key=f"oc_{ek}"
            )
            asociados = st.number_input(
                "Asociados", value=float(p.get("asociados", 0) or 0), step=50.0, key=f"as_{ek}"
            )
            _acc0 = p.get("acciones")
            if _acc0 is None or float(_acc0 or 0) <= 0:
                try:
                    _acc0 = L.resolver_acciones_millones(empresa, None)
                except Exception:
                    _acc0 = 0
            acciones = st.number_input(
                "Acciones (M)", value=float(_acc0 or 0), step=1.0, key=f"acc_{ek}",
                help="Millones de acciones diluidas. Si queda en 0, el modelo intenta obtenerlas de Yahoo.",
            )
            exit_multiple = st.slider(
                "Exit EV/EBITDA", 0.0, 40.0, float(p.get("exit_multiple", 9) or 9), 0.5, key=f"em_{ek}"
            )
            mid_year = st.checkbox("Mid-year", value=True, key=f"my_{ek}")
            g_max_macro = st.slider(
                "Techo g", 0.02, 0.06, float(st.session_state.get("g_max_macro", 0.04)), 0.005, key=f"gmax_{ek}"
            )

        with st.expander("Conector de mercado", expanded=False):
            prov = st.selectbox("Proveedor", ["yahoo", "api_key", "manual"])
            api_key = st.text_input("API key", type="password")
            api_url = st.text_input("URL vendor")
            if st.button("Aplicar", use_container_width=True):
                try:
                    _html(L.aplicar_config_mercado_ui(prov, api_key, api_url))
                except Exception as e:
                    st.error(str(e))

        st.markdown('<p class="tf-sidebar-label">Experiencia</p>', unsafe_allow_html=True)
        tema = st.toggle("Modo claro (experimental)", value=False, key="tema_claro")
        if tema:
            st.markdown(
                "<script>document.documentElement.setAttribute('data-theme','light');</script>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<script>document.documentElement.setAttribute('data-theme','dark');</script>",
                unsafe_allow_html=True,
            )
        if st.button("Repetir tour guiado", use_container_width=True, key="btn_retour"):
            st.session_state["tour_done"] = False
            st.session_state["tour_step"] = 1
            st.rerun()
        with st.expander("Self-test núcleo valoración", expanded=False):
            if st.button("Correr pruebas unitarias", key="btn_self_test", use_container_width=True):
                try:
                    if hasattr(L, "self_test_valuation_core"):
                        rows = L.self_test_valuation_core()
                        import pandas as _pd
                        df_t = _pd.DataFrame(
                            [{"Prueba": n, "OK": "✓" if ok else "✗", "Detalle": d} for n, ok, d in rows]
                        )
                        _show_df(df_t, "Resultado self-test")
                        if all(ok for _, ok, _ in rows):
                            st.success("Núcleo WACC / g / DCF / bridge OK.")
                        else:
                            st.error("Alguna prueba falló — revisa el motor.")
                    else:
                        st.warning(
                            "self_test_valuation_core no está en el modelacion_logic que carga la app. "
                            "Sustituye modelacion_logic.py por la versión actualizada de artifacts "
                            "(debe incluir def self_test_valuation_core) y reinicia Streamlit."
                        )
                except Exception as e:
                    st.error(str(e))

    # Re-bind from session if expanders caused scope issues — always compute from widgets via session keys
    # Streamlit widgets already wrote to session; read explicit values we set above in this run
    archivo = _archivo_para_logic()
    usar_publicos = st.session_state.get("usar_publicos", True)

    # Resolver acciones/precio si el slider quedó en 0 (empresas Yahoo recién cargadas)
    try:
        if acciones is None or float(acciones or 0) <= 0:
            acciones = L.resolver_acciones_millones(empresa, acciones) or 0.0
            if acciones and acciones > 0:
                st.session_state.setdefault("params", {})["acciones"] = float(acciones)
    except Exception:
        pass

    try:
        if hasattr(L, "_restaurar_entrada_catalogo"):
            L._restaurar_entrada_catalogo(empresa)
    except Exception:
        pass
    # Re-alinear moneda/precio en cada run (evita USD modelo vs COP precio en AAPL y similares)
    try:
        _alinear_moneda_y_precio(empresa)
    except Exception:
        pass

    w = _wacc_quick(de_ratio, kd, tax, beta_u, rf, erp, crp)
    moneda = str((st.session_state.get("params") or {}).get("moneda") or "COP").upper()
    moneda_precio = str(
        st.session_state.get("moneda_precio_alineada")
        or (st.session_state.get("params") or {}).get("precio_moneda")
        or moneda
    ).upper()
    try:
        emp_obj = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
        if emp_obj:
            moneda = str(
                emp_obj.get("params", {}).get("moneda") or emp_obj.get("moneda") or moneda
            ).upper()
            sector = emp_obj.get("sector", "—")
        else:
            sector = "—"
    except Exception:
        sector = "—"

    # Forzar misma moneda modelo/precio según emisor (elimina aviso USD vs COP falso)
    try:
        if hasattr(L, "monedas_alineadas_por_ticker"):
            _tk = (st.session_state.get("params") or {}).get("ticker_yf")
            moneda, moneda_precio = L.monedas_alineadas_por_ticker(
                ticker=_tk, nombre_empresa=empresa,
                emp=(L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None) or {},
            )
        else:
            moneda_precio = moneda
        pfix = st.session_state.get("params") or {}
        pfix["moneda"] = moneda
        pfix["precio_moneda"] = moneda_precio
        st.session_state["params"] = pfix
        st.session_state["moneda_precio_alineada"] = moneda_precio
        st.session_state["fx_mismatch"] = False
        try:
            emp_fix = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
            if emp_fix and isinstance(emp_fix, dict):
                if hasattr(L, "aplicar_monedas_a_empresa"):
                    L.aplicar_monedas_a_empresa(empresa, emp_fix)
                else:
                    emp_fix["moneda"] = moneda
                    emp_fix["moneda_precio"] = moneda_precio
        except Exception:
            pass
    except Exception:
        st.session_state["fx_mismatch"] = False


    # ----- KPI strip (con burbujas al pasar el cursor) -----
    _kpi_row(
        [
            (
                "WACC",
                f"{w['wacc']*100:.2f}%",
                "costo capital",
                True,
                "Es el costo promedio del dinero de la empresa: lo que exigen quienes prestaron (deuda) y los dueños (acciones). "
                "Si el negocio gana más que este porcentaje (ROIC > WACC), suele estar creando valor.",
            ),
            (
                "Ke (CAPM)",
                f"{w['ke']*100:.2f}%",
                f"βL {w['beta_l']:.2f}",
                False,
                "Es la rentabilidad que piden los accionistas por el riesgo de esta empresa. "
                "Se calcula con tasa libre de riesgo + riesgo de mercado (beta) + prima del país si aplica.",
            ),
            (
                "Horizonte",
                f"{horizonte} a",
                f"g {g*100:.1f}%",
                False,
                "Cuántos años proyectamos el dinero libre (FCFF) año a año. "
                "Después se estima un valor a largo plazo (valor terminal) con un crecimiento g moderado.",
            ),
            (
                "Emisor",
                empresa.split("—")[0].strip()[:18],
                str(sector)[:22],
                False,
                f"Empresa que estás analizando: {empresa}. "
                "El sector sirve para compararla con empresas parecidas (peers).",
            ),
        ]
    )

    _px = st.session_state.get("precio_mercado_alineado")
    _px_txt = f"{float(_px):,.2f} {moneda_precio}" if _px else "—"
    _align_ok = str(moneda).upper().replace("$", "") == str(moneda_precio).upper().replace("$", "")
    _fx_flag = bool(st.session_state.get("fx_mismatch")) and not _align_ok
    _align_msg = (
        f"Moneda alineada · precio {_px_txt}"
        if _align_ok
        else (
            f"Desalineación FX · modelo {moneda} vs cotización {_px_txt}. "
            "El upside se anula hasta convertir al mismo numeraire."
            if _fx_flag or not _align_ok
            else f"Revisar FX · modelo {moneda} vs precio {_px_txt}"
        )
    )
    st.markdown(
        f'<div class="tf-info"><b>{empresa}</b> · modelo en <b>{moneda}</b> '
        f"(miles de millones). {_align_msg}. Calibra supuestos antes de interpretar.</div>",
        unsafe_allow_html=True,
    )
    try:
        _banner_calidad_datos(empresa, archivo=archivo, usar_publicos=usar_publicos)
    except Exception:
        pass
    try:
        _deuda_bruta_flag = bool((st.session_state.get("params") or {}).get("deuda_es_bruta", False))
        _mostrar_reconciliacion_deuda(deuda_neta, caja, deuda_es_bruta=_deuda_bruta_flag)
    except Exception:
        pass

    # Semáforo en vivo (supuestos)
    try:
        n_hist = 0
        emp_o = None
        try:
            emp_o = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
        except Exception:
            emp_o = None
        if emp_o and emp_o.get("historico") is not None:
            try:
                import pandas as _pd
                n_hist = len(_pd.DataFrame(emp_o["historico"]))
            except Exception:
                n_hist = 0
        st.session_state["n_hist"] = n_hist
        _semaforo(_semaforo_desde_checks(g, w["wacc"], de_ratio, n_hist, tax))
        _analogy("WACC")
    except Exception:
        pass


    # ----- Tools strip: Sensibilidad + Glosario en fila; Consulta IA a ancho completo debajo -----
    t1, t2 = st.columns(2)
    with t1:
        with st.expander("⚡ Sensibilidad WACC · g (antes → después)", expanded=False):
            st.caption("Mueve los sliders y compara el valor base con el nuevo (sin reproyectar FCFF).")
            sw = st.slider("WACC de prueba", 0.06, 0.18, float(w["wacc"]), 0.0025, key="sens_wacc")
            sg = st.slider("g de prueba", 0.005, 0.06, float(g), 0.0025, key="sens_g")
            _metrics_tip_row([
                (
                    "WACC de prueba",
                    f"{sw*100:.2f}% ({(sw - w['wacc'])*100:+.2f} pp)",
                    "Costo de capital que estás probando. Si lo subes, el valor del negocio suele bajar "
                    "porque el futuro 'vale menos' en pesos de hoy.",
                ),
                (
                    "g de prueba",
                    f"{sg*100:.2f}% ({(sg - g)*100:+.2f} pp)",
                    "Crecimiento de largo plazo que estás probando. Si lo subes, el valor terminal suele subir, "
                    "pero si se acerca mucho al WACC el resultado se vuelve frágil e inestable.",
                ),
            ], cols=2)
            _analogy("WACC")
            if st.button("Ver impacto en valoración", key="btn_sens", use_container_width=True, type="primary"):
                try:
                    st.session_state["hero_html"] = L.sensibilidad_rapida_ui(
                        empresa, sw, sg, horizonte, tax,
                        deuda_neta, caja, nci, otros_claims, asociados, acciones,
                        mid_year, g_max_macro,
                    )
                except Exception as e:
                    st.session_state["hero_html"] = f"<div>Error: {e}</div>"
            if st.session_state.get("hero_html"):
                _html(st.session_state["hero_html"])
                _explain(
                    "<b>Antes → después:</b> subir el WACC suele bajar el valor (el futuro se ‘descuenta’ más fuerte). "
                    "Subir g suele subir el valor terminal, pero si g se acerca al WACC el resultado se vuelve frágil."
                )
    with t2:
        with st.expander("📚 Glosario en palabras simples", expanded=False):
            _glosario_chips()

    with st.expander("🤖 Consulta IA", expanded=False):
        st.caption(
            "Pregunta en lenguaje natural sobre el modelo, el emisor o definiciones. "
            "Gemini viene configurado por defecto; puedes cambiar proveedor o clave abajo."
        )
        pregunta = st.text_area(
            "Pregunta",
            height=90,
            placeholder="¿Qué es el WACC? · ¿Precio y upside? · Resumen para el comité",
            label_visibility="collapsed",
            key="ia_pregunta",
        )
        with st.expander("Proveedor y API key", expanded=False):
            cprov = st.selectbox(
                "Proveedor",
                ["gemini", "xai", "openai"],
                index=0,
                key="iaprov",
                help="Gemini usa la clave por defecto de la app salvo que indiques otra.",
            )
            ckey = st.text_input(
                "API key (opcional — deja vacío para usar la de Gemini por defecto)",
                type="password",
                key="iakey",
                placeholder="Vacío = Gemini por defecto",
            )
            st.caption("Prioridad: clave escrita aquí → Secrets/env → clave Gemini embebida.")
        consultar = st.button("Consultar", type="primary", key="btn_ia", use_container_width=True)
        if consultar:
            with st.spinner("Consultando…"):
                try:
                    key_eff = _resolve_gemini_key(ckey) if (cprov or "gemini") == "gemini" else ((ckey or "").strip() or None)
                    if cprov == "gemini" and not key_eff:
                        key_eff = _resolve_gemini_key(None)
                    _html(
                        L.asistente_consulta_financiera(
                            pregunta,
                            empresa,
                            api_key=key_eff,
                            proveedor=cprov or "gemini",
                        )
                    )
                except Exception as e:
                    st.error(str(e))


    # ----- Generar todo (único botón) -----
    st.markdown("##### Ejecución del modelo")
    st.caption(
        "Calcula las 7 pestañas de una vez o solo la que necesites. "
        "CAPM se alinea al mercado del emisor (US/CO/…). Validaciones de WACC vs g y bridge deuda neta mejoran la exactitud."
    )
    modo_ejec = st.radio(
        "Alcance",
        ["Todo el modelo (7 pestañas)", "Solo pestaña seleccionada abajo"],
        horizontal=True,
        key="modo_ejecucion",
    )
    metodo = st.radio(
        "Método de pronóstico (pestaña 1)",
        [
            "Drivers + identidad FCFF (recomendado)",
            "ETS / Holt (suavizado exponencial)",
            "ARIMA (benchmark estadístico)",
        ],
        horizontal=True,
        key="metodo_global",
    )

    # Invalidar salidas calculadas cuando cambie cualquier supuesto que altere el DCF.
    _model_fingerprint = tuple(repr(x) for x in (
        empresa, horizonte, metodo, tax, de_ratio, kd, g, capex_extra, beta_u,
        deuda_neta, rf, erp, crp, caja, nci, otros_claims, asociados, acciones,
        exit_multiple, mid_year, g_max_macro, usar_publicos,
        getattr(archivo, "name", None), getattr(archivo, "size", None), moneda,
    ))
    _prev_fingerprint = st.session_state.get("_model_fingerprint")
    if _prev_fingerprint is not None and _prev_fingerprint != _model_fingerprint:
        st.session_state["resultados"] = {}
        st.session_state.pop("tab4_comite_ia_html", None)
        st.session_state.pop("contraste_mercado_actual", None)
        st.session_state["modelo_dirty"] = True
    st.session_state["_model_fingerprint"] = _model_fingerprint
    if st.session_state.get("modelo_dirty"):
        st.info("Los supuestos cambiaron: se invalidaron resultados anteriores. Ejecuta **Generar todo** para recalcularlos.")
    # Validación de robustez pre-corrida (WACC vs g, finitud)
    try:
        if hasattr(L, "validar_inputs_valoracion"):
            _warns = L.validar_inputs_valoracion(w["wacc"], g, g_max_macro=g_max_macro, acciones=acciones)
            for _m in (_warns or []):
                st.warning(_m)
    except Exception:
        pass

    if st.button("▶ Generar todo", type="primary", key="btn_generar_todo", use_container_width=True):
        try:
            _alinear_moneda_y_precio(empresa)
        except Exception:
            pass
        progress = st.progress(0, text="Iniciando…")
        errores = []
        # Orden: 1 → 2 → 3 → 4 → 4+ (Comité IA) → 5 → 6 → 7 (última)
        pasos = [
            ("1 · Pronóstico FCFF", 1 / 8),
            ("2 · Escenarios DCF", 2 / 8),
            ("3 · Auditoría", 3 / 8),
            ("4 · Recomendación", 4 / 8),
            ("4+ · Comité interdisciplinario (IA)", 5 / 8),
            ("5 · VPN / TIR", 6 / 8),
            ("6 · Sector", 7 / 8),
            ("7 · Informe PDF", 8 / 8),
        ]
        try:
            progress.progress(pasos[0][1], text=pasos[0][0])
            try:
                st.session_state["resultados"]["tab1"] = L.tab1_carga_y_pronostico(
                    empresa, archivo, horizonte, metodo, tax, usar_publicos
                )
            except Exception as e:
                errores.append(f"Pestaña 1: {e}")

            progress.progress(pasos[1][1], text=pasos[1][0])
            try:
                st.session_state["resultados"]["tab2"] = L.tab2_simulacion_politicas(
                    empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                    deuda_neta, rf, erp, crp, usar_publicos,
                    caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                )
            except Exception as e:
                errores.append(f"Pestaña 2: {e}")

            progress.progress(pasos[2][1], text=pasos[2][0])
            try:
                st.session_state["resultados"]["tab3"] = L.tab3_auditoria_teorica(
                    empresa, archivo, horizonte, de_ratio, kd, tax, g, beta_u,
                    capital_invertido, rf, erp, crp, usar_publicos,
                )
            except Exception as e:
                errores.append(f"Pestaña 3: {e}")

            progress.progress(pasos[3][1], text=pasos[3][0])
            try:
                st.session_state["resultados"]["tab4"] = L.tab4_recomendacion(
                    empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                    capital_invertido, deuda_neta, rf, erp, crp, usar_publicos,
                    caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                )
            except Exception as e:
                errores.append(f"Pestaña 4: {e}")

            # 4+ Comité IA inmediatamente después de la pestaña 4
            progress.progress(pasos[4][1], text=pasos[4][0])
            try:
                ok_c, msg_c = _ejecutar_comite_ia_sesion(
                    empresa, w=w, de_ratio=de_ratio, g=g, moneda=moneda,
                )
                if not ok_c:
                    errores.append(f"Comité IA (4+): {msg_c}")
            except Exception as e:
                errores.append(f"Comité IA (4+): {e}")

            progress.progress(pasos[5][1], text=pasos[5][0])
            try:
                st.session_state["resultados"]["tab5"] = L.tab5_vpn_tir(
                    empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                    inversion_inicial, rf, erp, crp, usar_publicos,
                )
            except Exception as e:
                errores.append(f"Pestaña 5: {e}")

            progress.progress(pasos[6][1], text=pasos[6][0])
            try:
                st.session_state["resultados"]["tab6"] = L.tab6_comparacion_sectorial(empresa)
                st.session_state["tab6_empresa"] = empresa
            except Exception as e:
                errores.append(f"Pestaña 6: {e}")

            # 7 Informe PDF — última ejecución
            progress.progress(pasos[7][1], text=pasos[7][0])
            try:
                st.session_state["resultados"]["tab7"] = L.tab7_informe_ejecutivo(
                    empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                    capital_invertido, deuda_neta, inversion_inicial, rf, erp, crp, usar_publicos,
                    caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                )
            except Exception as e:
                errores.append(f"Pestaña 7: {e}")

            progress.progress(1.0, text="Listo")
            if errores:
                st.warning("Algunas pestañas fallaron:\n- " + "\n- ".join(errores))
            else:
                st.session_state["modelo_dirty"] = False
                st.success(
                    "Pipeline completo: 1→2→3→4→4+(Comité IA)→5→6→7. "
                    "Revisa cada pestaña."
                )
            st.rerun()
        except Exception as e:
            st.error(str(e))
            st.code(traceback.format_exc())

    # ----- Ejecución por pestaña (opcional) -----
    if st.session_state.get("modo_ejecucion", "").startswith("Solo"):
        st.markdown("###### Ejecutar una sola pestaña")
        ctabs = st.columns(7)
        _tab_labels = ["1 FCFF", "2 DCF", "3 Aud.", "4 Rec.", "5 VPN", "6 Sec.", "7 Inf."]
        _tab_keys = ["tab1", "tab2", "tab3", "tab4", "tab5", "tab6", "tab7"]
        for i, col in enumerate(ctabs):
            with col:
                if st.button(_tab_labels[i], key=f"btn_solo_{_tab_keys[i]}", use_container_width=True):
                    try:
                        _alinear_moneda_y_precio(empresa)
                    except Exception:
                        pass
                    try:
                        if i == 0:
                            st.session_state.setdefault("resultados", {})["tab1"] = L.tab1_carga_y_pronostico(
                                empresa, archivo, horizonte, metodo, tax, usar_publicos
                            )
                        elif i == 1:
                            st.session_state.setdefault("resultados", {})["tab2"] = L.tab2_simulacion_politicas(
                                empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                                deuda_neta, rf, erp, crp, usar_publicos,
                                caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                            )
                        elif i == 2:
                            st.session_state.setdefault("resultados", {})["tab3"] = L.tab3_auditoria_teorica(
                                empresa, archivo, horizonte, de_ratio, kd, tax, g, beta_u,
                                capital_invertido, rf, erp, crp, usar_publicos,
                            )
                        elif i == 3:
                            st.session_state.setdefault("resultados", {})["tab4"] = L.tab4_recomendacion(
                                empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                                capital_invertido, deuda_neta, rf, erp, crp, usar_publicos,
                                caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                            )
                            try:
                                ok_c, msg_c = _ejecutar_comite_ia_sesion(
                                    empresa, w=w, de_ratio=de_ratio, g=g, moneda=moneda,
                                )
                                if not ok_c:
                                    st.warning(f"Comité IA (4+): {msg_c}")
                            except Exception as _e_c:
                                st.warning(f"Comité IA (4+): {_e_c}")
                        elif i == 4:
                            st.session_state.setdefault("resultados", {})["tab5"] = L.tab5_vpn_tir(
                                empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                                inversion_inicial, rf, erp, crp, usar_publicos,
                            )
                        elif i == 5:
                            st.session_state.setdefault("resultados", {})["tab6"] = L.tab6_comparacion_sectorial(empresa)
                        elif i == 6:
                            st.session_state.setdefault("resultados", {})["tab7"] = L.tab7_informe_ejecutivo(
                                empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                                capital_invertido, deuda_neta, inversion_inicial, rf, erp, crp, usar_publicos,
                                caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                            )
                        st.success(f"Pestaña {_tab_labels[i]} lista.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # ----- 7 TABS (visualización; datos con «Generar todo» o botones individuales) -----
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "1 · Pronóstico",
            "2 · Escenarios DCF",
            "3 · Auditoría",
            "4 · Recomendación",
            "5 · VPN / TIR",
            "6 · Sector",
            "7 · Informe PDF",
        ]
    )

    with tab1:
        st.markdown("##### Proyección de FCFF")
        st.caption(f"Método usado: **{metodo}**. Usa el botón «Generar todo» arriba para calcular.")
        _metrics_tip_row([
            (
                "FCFF",
                "Dinero libre",
                "Free Cash Flow to Firm: el efectivo que sobra después de operar e invertir. "
                "Es la 'plata libre' del negocio antes de pagar intereses a la deuda.",
            ),
            (
                "Histórico",
                "Años pasados",
                "Cifras ya ocurridas (estados financieros o catálogo). Sirven de base para proyectar.",
            ),
            (
                "Proyección",
                "Años futuros",
                "Estimación del modelo para los próximos años del horizonte. No es una promesa: es un escenario central.",
            ),
            (
                "Fan chart",
                "Rango probable",
                "La línea del medio es el caso típico; la sombra muestra que el futuro es un rango, no un número exacto.",
            ),
        ], cols=4)
        r = st.session_state.get("resultados", {}).get("tab1")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            c_a, c_b = st.columns(2)
            with c_a:
                if len(r) > 1:
                    _show_df(r[1], "Historial", csv_key="tab1_historial")
            with c_b:
                if len(r) > 2:
                    _show_df(r[2], "Proyección", csv_key="tab1_proyeccion")
            # Fan chart Plotly nativo (histórico + proyección + banda)
            df_h = r[1] if len(r) > 1 else None
            df_p = r[2] if len(r) > 2 else None
            if not _plotly_fan_fcff(df_h, df_p, title="Fan chart · FCFF (historia → proyección)"):
                if len(r) > 3:
                    _show_fig(r[3], "Fan chart FCFF")
            # Comparación drivers / atípicos — mismo estilo Plotly
            if not _plotly_comparacion_drivers(df_h, title="Comparación de drivers · original vs normalizado"):
                if len(r) > 4 and r[4] is not None:
                    _show_fig(r[4], "Atípicos (respaldo estático)")
            else:
                _explain(
                    "<b>Burbuja de lectura · Drivers:</b> la línea azul es el número tal como salió en los libros. "
                    "La línea teal es la misma serie “calmada” (sin picos extremos). "
                    "Las cruces rojas marcan años raros: venta de activos, crisis, cambio contable, etc. "
                    "Para proyectar, suele ser más sano apoyarse en la serie suavizada."
                )
            if len(r) > 5 and r[5]:
                _html(r[5])
            _chart_tip(
                "Pasa el cursor sobre cada punto: verás el año y el dinero libre en lenguaje claro. "
                "La zona sombreada es el rango probable; la línea del medio es el caso más típico. "
                "Si un año del pasado queda muy fuera de la línea, puede haber sido un evento único."
            )
            _explain(
                "<b>Burbuja de lectura · Fan chart:</b> piensa en el FCFF como la “plata libre” del negocio "
                "(después de pagar operación e inversiones). La línea azul es lo que ya ocurrió; la teal es "
                "lo que el modelo espera. No es una bola de cristal: la sombra muestra que el futuro es un rango, no un número exacto."
            )

    with tab2:
        st.markdown("##### Escenarios pesimista · base · optimista")
        st.caption("Resultados generados con «Generar todo».")
        _metrics_tip_row([
            (
                "EV",
                "Valor empresa",
                "Precio teórico de todo el negocio (como el de una casa antes de la hipoteca).",
            ),
            (
                "Equity",
                "Valor dueños",
                "Lo que quedaría a los accionistas después de pagar deudas y otros reclamos.",
            ),
            (
                "TV / EV",
                "% terminal",
                "Qué parte del valor viene del 'después del horizonte'. Si es muy alto, el resultado depende mucho de g y WACC.",
            ),
        ], cols=3)
        r = st.session_state.get("resultados", {}).get("tab2")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Por escenario", csv_key="tab2_escenarios")
                if not _plotly_escenarios(r[1]):
                    if len(r) > 2:
                        _show_fig(r[2], "EV vs Equity")
            elif len(r) > 2:
                _show_fig(r[2], "EV vs Equity")
            _chart_tip(
                "Pasa el cursor por cada barra: te explica qué es EV y Equity en ese escenario. "
                "Barras altas de Equity = más valor para el accionista. Si Equity es bajo o negativo, la deuda pesa mucho."
            )
            _explain(
                "<b>Burbuja de lectura · Escenarios:</b> es como preguntar “¿y si va mal, normal o bien?”. "
                "Ahora los escenarios también mueven <b>drivers</b> (ingresos, margen EBITDA, CAPEX, NWC), "
                "no solo escalan el FCFF. "
                "<b>EV</b> = precio de toda la empresa (como el de una casa antes de la hipoteca). "
                "<b>Equity</b> = lo que les quedaría a los dueños tras pagar deudas. "
                "Revisa la columna <b>TV / EV %</b> y el <b>método de valor terminal</b>: si el TV domina, el caso es sensible a g y WACC."
            )

    with tab3:
        st.markdown("##### Coherencia de supuestos")
        st.caption("Resultados generados con «Generar todo».")
        _metrics_tip_row([
            (
                "Auditoría",
                "Lista de chequeo",
                "Revisa si los supuestos son razonables: por ejemplo si el crecimiento g no está demasiado cerca del WACC, "
                "o si hay suficiente historia de datos.",
            ),
            (
                "g vs WACC",
                "Regla clave",
                "El crecimiento de largo plazo (g) debe ser menor que el costo de capital (WACC). "
                "Si no, la fórmula del valor terminal se rompe o se vuelve explosiva.",
            ),
            (
                "Semáforo",
                "Verde / ámbar / rojo",
                "Resumen visual de alertas. Rojo no es 'no inviertas': es 'revisa este supuesto antes de decidir'.",
            ),
        ], cols=3)
        r = st.session_state.get("resultados", {}).get("tab3")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Pruebas", csv_key="tab3_pruebas")
            _explain(
                "<b>En palabras simples:</b> la auditoría es una lista de chequeo. "
                "Si muchas pruebas salen en rojo (por ejemplo g casi igual al WACC, o poca historia), "
                "el modelo puede estar ‘forzado’ y conviene ajustar supuestos antes de decidir."
            )
            _semaforo(_semaforo_desde_checks(g, w["wacc"], de_ratio, st.session_state.get("n_hist", 0), tax))
            _analogy("g")

    with tab4:
        st.markdown("##### Recomendación de comité")
        st.caption("Resultados generados con «Generar todo».")
        _metrics_tip_row([
            (
                "Decisión",
                "Marco de discusión",
                "Resumen de si, con estos números, vale la pena llevar el caso a un comité. "
                "No es una orden de comprar o vender la acción.",
            ),
            (
                "Gobernanza",
                "Reglas y alertas",
                "Lista de apoyos y vetos del motor (por ejemplo g cerca del WACC o apalancamiento alto). "
                "Sirve para no olvidar riesgos de supuestos.",
            ),
            (
                "Comité IA",
                "Deliberación opcional",
                "Simulación con roles (CFO, mercado, riesgos) usando los números ya calculados. "
                "Complementa el análisis; no sustituye due diligence ni asesoría profesional.",
            ),
        ], cols=3)
        r = st.session_state.get("resultados", {}).get("tab4")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(_strip_contraste_html(r[0]))
            if len(r) > 1:
                _show_df(r[1], "Gobernanza")
            if len(r) > 2:
                _html(_strip_contraste_html(r[2]))
            _explain(
                "<b>En palabras simples:</b> la recomendación resume si, con estos números, tiene sentido "
                "llevar el caso a un comité. No es una orden de compra: es un marco para discutir riesgos y valor. "
                "El módulo de contraste automático modelo vs mercado ya no se muestra aquí; la lectura de mercado "
                "queda a cargo del comité IA (abajo) y del informe de la pestaña 7."
            )
            alerts = []
            if g >= w["wacc"] - 0.005:
                alerts.append(("bad", "Supuesto g", "g demasiado cerca del WACC: valor terminal poco fiable."))
            else:
                alerts.append(("ok", "Supuesto g", "g por debajo del WACC con margen razonable."))
            if de_ratio > 2.5:
                alerts.append(("warn", "Riesgo financiero", "Apalancamiento alto: el equity puede moverse mucho."))
            else:
                alerts.append(("ok", "Riesgo financiero", "Apalancamiento en zona manejable para el ejercicio."))
            alerts.append(("ok", "Uso del output", "Esto apoya la discusión; no es una orden de compra/venta."))
            _semaforo(alerts)
            _analogy("Equity")
        else:
            st.info(
                "Aún no hay recomendación cuantitativa. Configura parámetros y pulsa **Generar todo**. "
                "Puedes generar la deliberación IA del comité abajo."
            )

        st.markdown("---")
        st.markdown("##### 🤖 Recomendación IA · Comité interdisciplinario")
        st.caption(
            "Mismo proveedor/API key que **Consulta IA**. "
            "Deliberación CFO + Analista de Mercado + CRO con los números del modelo (moneda alineada)."
        )

        def _safe_float(x, default=0.0):
            try:
                if x is None:
                    return default
                if isinstance(x, str):
                    s = x.strip().replace("%", "").replace(",", "").replace("×", "").replace("x", "")
                    if not s or s in ("—", "-", "N/A", "n/a"):
                        return default
                    return float(s)
                v = float(x)
                if v != v or abs(v) == float("inf"):
                    return default
                return v
            except Exception:
                return default

        def _extraer_kpis_comite():
            """KPIs y precio de la empresa actualmente seleccionada (sidebar), no de otra."""
            res = st.session_state.get("resultados") or {}
            wacc_calc = float(w.get("wacc", 0.10) if isinstance(w, dict) else 0.10)
            ke_calc = float(w.get("ke", 0.12) if isinstance(w, dict) else 0.12)
            roic_calc = None
            val_ev = 0.0
            val_equity = 0.0
            vps_modelo = 0.0
            # Precio y ticker de ESTA empresa (nunca session de AAPL si estamos en ISA)
            try:
                _alinear_moneda_y_precio(empresa)
            except Exception:
                pass
            precio_mercado = 0.0
            try:
                if hasattr(L, "resolver_precio_mercado"):
                    precio_mercado = _safe_float(L.resolver_precio_mercado(empresa), 0.0)
            except Exception:
                precio_mercado = 0.0
            if precio_mercado <= 0:
                precio_mercado = _safe_float(st.session_state.get("precio_mercado_alineado"), 0.0)
            upside = 0.0
            mon_m = str((st.session_state.get("params") or {}).get("moneda") or moneda or "COP").upper()

            t7 = res.get("tab7")
            kpi_map = {}
            if t7 and isinstance(t7, (list, tuple)) and len(t7) > 1:
                kpi_df = t7[1]
                if kpi_df is not None and hasattr(kpi_df, "columns"):
                    cols = list(kpi_df.columns)
                    if "Indicador" in cols and "Valor" in cols:
                        try:
                            for _, row in kpi_df.iterrows():
                                kpi_map[str(row["Indicador"])] = row["Valor"]
                        except Exception:
                            pass

            def _k(name, *alts):
                for n in (name,) + alts:
                    if n in kpi_map:
                        return kpi_map[n]
                return None

            val_ev = _safe_float(_k("EV base", "EV"), val_ev)
            val_equity = _safe_float(_k("Equity base", "Equity"), val_equity)
            vps_modelo = _safe_float(_k("VPS modelo", "VPS", "Precio modelo"), vps_modelo)
            if precio_mercado <= 0:
                precio_mercado = _safe_float(_k("Precio mercado", "Precio actual", "Precio"), 0.0)
            upside_raw = _k("Upside %", "Upside")
            if upside_raw is not None:
                upside = _safe_float(upside_raw, 0.0)
            wacc_k = _k("WACC %", "WACC")
            if wacc_k is not None:
                ww = _safe_float(wacc_k, wacc_calc * 100)
                wacc_calc = ww / 100.0 if ww > 1.0 else ww
            roic_k = _k("ROIC %", "ROIC")
            if roic_k is not None:
                rr = _safe_float(roic_k, None)
                if rr is not None:
                    roic_calc = rr / 100.0 if rr > 1.0 else rr

            t2 = res.get("tab2")
            if t2 and isinstance(t2, (list, tuple)) and len(t2) > 1 and hasattr(t2[1], "columns"):
                df2 = t2[1]
                try:
                    cols = {str(c).lower(): c for c in df2.columns}
                    esc_c = cols.get("escenario") or cols.get("nombre") or df2.columns[0]
                    for _, row in df2.iterrows():
                        label = str(row[esc_c]).lower()
                        if "base" not in label and "central" not in label:
                            continue
                        for c in df2.columns:
                            cl = str(c).lower()
                            if cl == str(esc_c).lower():
                                continue
                            if ("ev" in cl or "empresa" in cl) and "ebitda" not in cl and val_ev == 0:
                                val_ev = _safe_float(row[c], val_ev)
                            if ("equity" in cl or "dueño" in cl or "patrimonio" in cl) and val_equity == 0:
                                val_equity = _safe_float(row[c], val_equity)
                except Exception:
                    pass

            if precio_mercado <= 0:
                try:
                    if hasattr(L, "precio_mercado_actual"):
                        precio_mercado = _safe_float(L.precio_mercado_actual(empresa), 0.0)
                except Exception:
                    pass

            if vps_modelo <= 0 and val_equity > 0:
                try:
                    acc = (st.session_state.get("params") or {}).get("acciones") or acciones
                    if acc and float(acc) > 0:
                        vps_info = L.calcular_vps_y_upside(
                            val_equity, float(acc), precio_mercado=None,
                            moneda_modelo=mon_m, moneda_precio=mon_m,
                        )
                        vps_modelo = vps_info.get("value_per_share") or 0.0
                except (TypeError, ValueError, AttributeError):
                    vps_modelo = 0.0

            mon_px = str(
                st.session_state.get("moneda_precio_alineada")
                or (st.session_state.get("params") or {}).get("precio_moneda")
                or mon_m
            ).upper()
            monedas_ok = mon_m.replace("$", "") == mon_px.replace("$", "")
            acciones_ctx = (st.session_state.get("params") or {}).get("acciones") or acciones
            if precio_mercado > 0 and vps_modelo > 0 and monedas_ok and val_equity > 0 and acciones_ctx:
                vps_info = L.calcular_vps_y_upside(
                    val_equity, acciones_ctx, precio_mercado=precio_mercado,
                    moneda_modelo=mon_m, moneda_precio=mon_px,
                )
                if vps_info.get("upside_pct") is not None:
                    upside = vps_info["upside_pct"]
                elif upside == 0.0:
                    upside = None
            if not monedas_ok:
                upside = None  # no comparable sin FX
            decision_modelo = "—"
            t4 = res.get("tab4")
            if t4 and isinstance(t4, (list, tuple)) and len(t4) > 0 and t4[0]:
                # Extraer etiqueta cualitativa del HTML de tab4 si existe
                decision_modelo = "Ver salida cuantitativa tab4"
            t7 = res.get("tab7")
            if t7 and isinstance(t7, (list, tuple)) and len(t7) > 1:
                try:
                    kdf = t7[1]
                    if kdf is not None and hasattr(kdf, "columns") and "Indicador" in list(kdf.columns):
                        for _, row in kdf.iterrows():
                            if str(row.get("Indicador", "")).lower() in ("decisión", "decision"):
                                decision_modelo = str(row.get("Valor", "—"))
                                break
                except Exception:
                    pass
            ticker_ctx = _inferir_ticker_yf(empresa, {}) or "—"
            return {
                "empresa": empresa,
                "ticker": ticker_ctx,
                "moneda": mon_m,
                "moneda_precio": mon_px,
                "monedas_alineadas": monedas_ok,
                "precio_mercado": precio_mercado,
                "vps_modelo": vps_modelo,
                "upside": upside,
                "wacc_calc": wacc_calc,
                "ke_calc": ke_calc,
                "roic_calc": roic_calc,
                "de_ratio": float(de_ratio),
                "g": float(g),
                "val_ev": val_ev,
                "val_equity": val_equity,
                "decision_modelo": decision_modelo,
            }

        def _prompt_comite_ia(ctx: dict) -> str:
            roic_text = f"{ctx['roic_calc']*100:.2f}%" if ctx.get("roic_calc") is not None else "N/D (sin datos suficientes)"
            upside_text = f"{ctx['upside']:+.2f}%" if ctx.get("upside") is not None else "N/D (monedas distintas o datos faltantes)"
            return (
                "Actúa como un Comité Interdisciplinario de Inversión de alto nivel compuesto por tres expertos senior:\n"
                "1. **Director Financiero (CFO / Experto en Valuation):** Especialista en valoración intrínseca (DCF/FCFF), "
                "costo de capital (WACC, Ke, CAPM), estructura de deuda y sostenibilidad de flujos.\n"
                "2. **Analista de Mercado y Estratega Competitivo:** Especialista en dinámicas sectoriales, lectura de "
                "múltiplos comparables (EV/EBITDA, P/E), posición competitiva (ROIC vs WACC) y contexto macroeconómico.\n"
                "3. **Chief Risk Officer (CRO / Gestor de Riesgos):** Especialista en auditoría de supuestos (g vs WACC, "
                "apalancamiento D/E), análisis de sensibilidad, valoración de escenarios y detección de eventos atípicos.\n"
                "---\n"
                "### CONTEXTO DE ENTRADA (Calculado por el Modelo Cuantitativo)\n"
                f"- **Empresa Objetivo:** {ctx['empresa']} · **Ticker:** {ctx.get('ticker', '—')}\n"
                f"- **Moneda del modelo (EEFF):** {ctx.get('moneda', 'USD')} | "
                f"**Moneda de cotización:** {ctx.get('moneda_precio', ctx.get('moneda', 'USD'))} | "
                f"**Alineadas:** {'SÍ' if ctx.get('monedas_alineadas', True) else 'NO — no uses upside sin FX'}\n"
                f"- **Decisión cuantitativa del modelo (tab4/tab7):** {ctx.get('decision_modelo', '—')}\n"
                f"- **Precio Actual de Mercado:** {ctx['precio_mercado']:,.2f}\n"
                f"- **Valor por Acción Según el Modelo (VPS):** {ctx['vps_modelo']:,.2f} "
                f"(Upside calculado: {upside_text} — válido solo si monedas alineadas)\n"
                f"- **WACC Calculado:** {ctx['wacc_calc']*100:.2f}% | **Ke (CAPM):** {ctx['ke_calc']*100:.2f}% | "
                f"**ROIC:** {roic_text}\n"
                f"- **Estructura D/E:** {ctx['de_ratio']:.2f} | **Crecimiento Terminal (g):** {ctx['g']*100:.2f}%\n"
                f"- **Valor del Negocio (EV Base):** {ctx['val_ev']:,.2f}\n"
                f"- **Valor del Equity Base:** {ctx['val_equity']:,.2f}\n"
                "---\n"
                "### INSTRUCCIONES Y FORMATO DE SALIDA\n"
                "Simula una deliberación crítica entre los tres miembros del comité contrastando estos números con la "
                "realidad del mercado. Entrega el resultado estrictamente bajo este formato:\n\n"
                "## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO\n"
                "- **Aportes del CFO (Estructura y DCF):** [...]\n"
                "- **Aportes del Analista de Mercado (Sector y Competencia):** [...]\n"
                "- **Aportes del CRO (Riesgos y Sensibilidad):** [...]\n\n"
                "## 2. ANÁLISIS DE BRECHA (MODELO VS. MERCADO ACTUAL)\n"
                "- **Brecha Detectada:** [...]\n"
                "- **Factores de Mercado no Contemplados:** [...]\n\n"
                "## 3. DECISIÓN FINAL DE INVERSIÓN\n"
                "- **RECOMENDACIÓN FINAL:** [INVERTIR / NO INVERTIR / INVERTIR CONDICIONALMENTE]\n"
                "- **PUNTAJE DE VIABILIDAD:** [Escala 1 a 10]\n"
                "- **PRECIO OBJETIVO DE CONSENSO (Rango Ajustado):** [...]\n"
                "- **TESIS Y JUSTIFICACIÓN ESTRATÉGICA:** [...]\n\n"
                "## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO\n"
                "1. [...]\n"
                "2. [...]\n"
            )

        with st.expander("Generar deliberación del comité con IA", expanded=True):
            ctx_preview = _extraer_kpis_comite()
            _metrics_tip_row([
                (
                    "Precio mercado",
                    f"{ctx_preview['precio_mercado']:,.2f} {ctx_preview.get('moneda', '')}",
                    "Último precio al que se negoció la acción en el mercado (fuente pública). "
                    "Es lo que pagan/compran los inversionistas hoy, no el valor del modelo.",
                ),
                (
                    "VPS modelo",
                    f"{ctx_preview['vps_modelo']:,.2f}",
                    "Valor por acción según el DCF de esta herramienta. "
                    "Si está muy por encima del precio de mercado, el modelo ve la acción 'barata' (y al revés).",
                ),
                (
                    "Upside",
                    f"{ctx_preview['upside']:+.1f}%" if ctx_preview.get("upside") is not None else "N/D",
                    "Porcentaje de diferencia entre VPS del modelo y precio de mercado. "
                    "Solo es comparable si ambas cifras están en la misma moneda. No garantiza que el precio se mueva.",
                ),
                (
                    "EV / Equity",
                    f"{ctx_preview['val_ev']:,.0f} / {ctx_preview['val_equity']:,.0f}",
                    "EV = valor del negocio completo. Equity = lo de los dueños tras deudas. "
                    "Unidades del modelo (p. ej. miles de millones de la moneda del emisor).",
                ),
            ], cols=4)

            # Leer config de Consulta IA sin mutar keys de widgets ya creados (iaprov/iakey).
            # Streamlit prohíbe asignar session_state[key] de un widget tras instanciarlo.
            _opts = ["gemini", "xai", "openai"]
            _prov_consulta = st.session_state.get("iaprov") or "gemini"
            if _prov_consulta not in _opts:
                _prov_consulta = "gemini"
            # Inicializar tab4 solo si aún no existe (antes del widget)
            if "tab4_iaprov" not in st.session_state:
                st.session_state["tab4_iaprov"] = _prov_consulta

            with st.expander("Proveedor y API key (compartido con Consulta IA)", expanded=False):
                prov_ia = st.selectbox(
                    "Proveedor",
                    _opts,
                    key="tab4_iaprov",
                    help="Por defecto toma el proveedor de Consulta IA; no sobrescribe ese widget.",
                )
                key_ui = st.text_input(
                    "API key (opcional — vacío = Gemini por defecto / clave de Consulta IA)",
                    type="password",
                    key="tab4_iakey",
                    placeholder="Vacío = Gemini por defecto",
                )
                st.caption(
                    "Si dejas la API key vacía se usa la de **Consulta IA** (si la escribiste arriba) "
                    "o st.secrets / variable de entorno GEMINI_API_KEY."
                )

            # Proveedor efectivo: tab4 si el usuario lo cambió; si no, el de Consulta IA
            prov_ia = st.session_state.get("tab4_iaprov") or st.session_state.get("iaprov") or "gemini"
            key_ui = (st.session_state.get("tab4_iakey") or "").strip() or (st.session_state.get("iakey") or "")

            _res_ok = st.session_state.get("resultados") or {}
            _tiene_base = bool(_res_ok.get("tab2") or _res_ok.get("tab7") or _res_ok.get("tab4"))
            if not _tiene_base:
                st.warning(
                    "Ejecuta **Generar todo** (o al menos pestañas 2 / 4 / 7) antes del comité IA. "
                    "Sin números del modelo la deliberación no está anclada."
                )
            if st.button(
                "▶ Deliberar en el comité (IA)",
                type="primary",
                key="btn_tab4_comite_ia",
                use_container_width=True,
                disabled=not _tiene_base,
            ):
                ctx = _extraer_kpis_comite()
                if not ctx.get("monedas_alineadas", True):
                    st.warning(
                        f"Moneda del modelo ({ctx.get('moneda')}) ≠ cotización ({ctx.get('moneda_precio')}). "
                        "El comité tratará el upside como no comparable hasta alinear FX."
                    )
                    st.info("Comité bloqueado parcialmente: puedes continuar, pero el upside se fuerza a 0 en el prompt.")
                with st.spinner("El comité interdisciplinario está deliberando…"):
                    try:
                        key_eff = (
                            _resolve_gemini_key(key_ui)
                            if (prov_ia or "gemini") == "gemini"
                            else ((key_ui or "").strip() or None)
                        )
                        if prov_ia == "gemini" and not key_eff:
                            key_eff = _resolve_gemini_key(None)
                        # Usar el endpoint dedicado del comité (no asistente_consulta_financiera):
                        # ese último imprime «Consulta: …» + el prompt completo en el HTML.
                        _metricas = {
                            "empresa": ctx.get("empresa") or empresa,
                            "ticker": ctx.get("ticker"),
                            "moneda": ctx.get("moneda"),
                            "precio_mercado": ctx.get("precio_mercado"),
                            "vps_modelo": ctx.get("vps_modelo"),
                            "upside": ctx.get("upside"),
                            "wacc_calc": ctx.get("wacc_calc"),
                            "ke_calc": ctx.get("ke_calc"),
                            "roic_calc": ctx.get("roic_calc"),
                            "de_ratio": ctx.get("de_ratio"),
                            "g": ctx.get("g"),
                            "val_ev": ctx.get("val_ev"),
                            "val_equity": ctx.get("val_equity"),
                            # Trazabilidad explícita: el UI no presume unidad ni fuente si no están documentadas.
                            "unidad_modelo": (st.session_state.get("params") or {}).get("unidad_modelo")
                                or f"miles de millones de {str(ctx.get('moneda') or 'COP').upper()}",
                            "unidad_precio": "por acción",
                            "fuente_precio": st.session_state.get("fuente_precio_mercado"),
                            "fecha_precio": st.session_state.get("fecha_precio_mercado"),
                            "fuente_valoracion": st.session_state.get("version_modelo_valoracion")
                                or "DCF propio · modelacion_logic.py · escenarios base",
                        }
                        _audit_ia = L.auditar_contexto_comite_ia(_metricas) if hasattr(L, "auditar_contexto_comite_ia") else {"ok": True, "errors": [], "warnings": []}
                        if _audit_ia.get("errors"):
                            st.error("Comité IA bloqueado por errores matemáticos: " + "; ".join(_audit_ia["errors"]))
                            st.session_state["tab4_comite_ia_html"] = None
                            st.stop()
                        if _audit_ia.get("warnings"):
                            st.warning("Auditoría previa del comité: " + "; ".join(_audit_ia["warnings"]))
                        if hasattr(L, "generar_recomendacion_comite_ia"):
                            respuesta = L.generar_recomendacion_comite_ia(
                                empresa,
                                api_key=key_eff,
                                proveedor=prov_ia or "gemini",
                                metricas=_metricas,
                            )
                        else:
                            # Fallback: no pasar el prompt como «pregunta» al asistente genérico
                            respuesta = L.asistente_consulta_financiera(
                                "Resume la tesis de inversión de esta empresa en 4 apartados "
                                "(CFO, mercado, riesgos, decisión) sin repetir el prompt.",
                                empresa,
                                api_key=key_eff,
                                proveedor=prov_ia or "gemini",
                            )
                        _audit_resp = L.auditar_respuesta_comite_ia(respuesta) if hasattr(L, "auditar_respuesta_comite_ia") else {"ok": True, "errors": [], "warnings": []}
                        if _audit_resp.get("errors"):
                            st.error("Salida IA no válida: " + "; ".join(_audit_resp["errors"]))
                            st.session_state["tab4_comite_ia_html"] = None
                            st.stop()
                        if _audit_resp.get("warnings"):
                            st.warning("Auditoría de salida IA: " + "; ".join(_audit_resp["warnings"]))
                        st.session_state["tab4_comite_ia_html"] = respuesta
                        try:
                            _struct = (
                                L.extraer_resumen_comite_ia(respuesta)
                                if hasattr(L, "extraer_resumen_comite_ia")
                                else {}
                            )
                            _txt = (_struct or {}).get("texto") or (
                                L._html_a_texto(respuesta, 800) if hasattr(L, "_html_a_texto") else str(respuesta)[:800]
                            )
                            # Evitar guardar el prompt si por algún motivo llegó al HTML
                            _up = (_txt or "").upper()
                            if "ACTÚA COMO UN COMITÉ" in _up or "ACTUA COMO UN COMITE" in _up or "CONTEXTO DE ENTRADA" in _up:
                                _txt = (_struct or {}).get("texto") or ""
                                if not _txt and _struct:
                                    partes = []
                                    if _struct.get("recomendacion"):
                                        partes.append(f"Recomendación final: {_struct['recomendacion']}")
                                    if _struct.get("puntaje"):
                                        partes.append(f"Puntaje: {_struct['puntaje']}")
                                    for i, p in enumerate((_struct.get("monitoreo") or [])[:3], 1):
                                        partes.append(f"{i}. {p}")
                                    _txt = "\n".join(partes)
                            L.guardar_resultado_tab("comite_ia", empresa, {
                                "texto": _txt,
                                "struct": _struct,
                                "proveedor": prov_ia or "gemini",
                            })
                            st.session_state["tab4_comite_ia_texto"] = _txt
                            st.session_state["tab4_comite_ia_struct"] = _struct
                        except Exception:
                            pass
                    except Exception as e:
                        st.error(str(e))
                        st.session_state["tab4_comite_ia_html"] = None

            if st.session_state.get("tab4_comite_ia_html"):
                st.markdown("###### Salida del comité")
                _html(st.session_state["tab4_comite_ia_html"])
                _explain(
                    "<b>Uso:</b> deliberación IA complementaria. No es asesoría de inversión ni orden de compra/venta."
                )

    with tab5:
        st.markdown("##### VPN · TIR · Payback")
        st.caption("Resultados generados con «Generar todo».")
        _metrics_tip_row([
            (
                "VPN",
                "Valor hoy",
                "Suma de los flujos futuros traídos a pesos de hoy, menos la inversión inicial. "
                "Si es positiva, el proyecto aporta valor con estos supuestos.",
            ),
            (
                "TIR",
                "Rentabilidad %",
                "Tasa de retorno anual implícita del proyecto. Se compara con el WACC: "
                "si la TIR es mayor, el proyecto suele verse atractivo en papel.",
            ),
            (
                "Payback",
                "Años",
                "Cuántos años tardas en recuperar la plata invertida contando los flujos. "
                "No dice si el riesgo o el costo de capital valían la pena.",
            ),
        ], cols=3)
        r = st.session_state.get("resultados", {}).get("tab5")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Flujos", csv_key="tab5_flujos")
                if not _plotly_vpn_flows(r[1]):
                    if len(r) > 2:
                        _show_fig(r[2], "Recuperación")
                # Gráfica de evolución del valor acumulado (payback visual)
                if not _plotly_valor_proyecto(r[1], wacc=w.get("wacc") if isinstance(w, dict) else None, chart_key="tab5_valor_proyecto"):
                    if len(r) > 2 and r[2] is not None:
                        pass  # ya se mostró respaldo de flujos si aplica
            elif len(r) > 2:
                _show_fig(r[2], "Recuperación")
            _chart_tip(
                "Barras = flujo de cada periodo (datos financieros disponibles). "
                "La segunda gráfica calcula la VPN descontando esos flujos al WACC: "
                "zona roja = VPN acumulada negativa; zona verde = ya recuperaste en valor presente."
            )
            _explain(
                "<b>Burbuja de lectura · VPN / TIR:</b> "
                "<b>VPN &gt; 0</b> = el proyecto deja más valor del que “cuesta” el capital (buena señal con estos supuestos). "
                "<b>TIR</b> = la rentabilidad anual implícita; se compara con el WACC (si TIR &gt; WACC suele ser atractivo). "
                "<b>Payback</b> solo dice en cuántos años recuperas la plata; no dice si el riesgo valía la pena."
            )

    with tab6:
        st.markdown("##### Ranking sectorial")
        st.caption("Resultados generados con «Generar todo».")
        _metrics_tip_row([
            (
                "Score",
                "Puntaje relativo",
                "Nota compuesta frente a pares del sector (márgenes, ROIC, WACC, crecimiento, múltiplos). "
                "Más alto suele indicar mejor posición relativa, no una orden de compra.",
            ),
            (
                "Margen EBITDA",
                "De cada 100",
                "De cada 100 de ventas, cuánto queda como utilidad operativa bruta antes de depreciaciones fuertes e intereses.",
            ),
            (
                "EV / EBITDA",
                "Múltiplo",
                "Cuántas veces el mercado (o el modelo) paga la utilidad operativa. "
                "Un múltiplo muy bajo puede ser oportunidad… o señal de problemas.",
            ),
        ], cols=3)
        r = st.session_state.get("resultados", {}).get("tab6")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Comparables", csv_key="tab6_sector")
                if not _plotly_sector(r[1]):
                    if len(r) > 2:
                        _show_fig(r[2], "Sector")
            elif len(r) > 2:
                _show_fig(r[2], "Sector")
            _chart_tip(
                "Pasa el cursor por cada empresa: verás margen y múltiplo en palabras simples. "
                "Compara con ‘vecinas’ del mismo oficio. Un múltiplo muy bajo puede ser oportunidad… o señal de problemas."
            )
            _explain(
                "<b>Burbuja de lectura · Sector:</b> no mires la empresa sola: compárala con pares. "
                "<b>Margen EBITDA</b> = de cada 100 de ventas, cuánto queda como utilidad operativa bruta. "
                "<b>EV/EBITDA</b> = cuántas veces el mercado paga esa utilidad. "
                "Si el ROIC supera al WACC, el negocio suele crear valor para los dueños."
            )

    with tab7:
        st.markdown("##### Dashboard ejecutivo - Resumen para comite")
        st.caption(
            "Vista gerencial: decision, valoracion, escenarios, proyecto y sector. "
            "Misma data que el PDF. Generado con Generar todo."
        )
        r = st.session_state.get("resultados", {}).get("tab7")
        if r and isinstance(r, (list, tuple)):
            kpi_df = r[1] if len(r) > 1 else None
            kpi_map = {}
            if kpi_df is not None and hasattr(kpi_df, "columns"):
                cols = list(kpi_df.columns)
                if "Indicador" in cols and "Valor" in cols:
                    try:
                        for _, row in kpi_df.iterrows():
                            kpi_map[str(row["Indicador"])] = str(row["Valor"])
                    except Exception:
                        kpi_map = {}

            def _k(name, default="—"):
                return kpi_map.get(name, default)

            decision = _k("Decision", _k("Decisión", "—"))
            puntaje = _k("Puntaje", "—")
            banner = (
                '<div class="tf-section" style="border-color:rgba(20,184,166,0.45);margin-bottom:1rem">'
                '<div class="tf-section-title">Tesis y recomendacion</div>'
                f'<div style="font-size:1.25rem;font-weight:700;color:#5EEAD4;margin:0.25rem 0 0.5rem 0">{decision}</div>'
                f'<div style="color:#CBD5E1;font-size:0.9rem">Puntaje de viabilidad: '
                f'<b style="color:#F1F5F9">{puntaje}</b> · Apoyo a decision · no es orden de compra/venta</div></div>'
            )
            st.markdown(banner, unsafe_allow_html=True)
            st.caption("Pasa el cursor por la decisión y por cada indicador: verás una explicación en lenguaje simple.")

            def _pct_label(raw):
                s = str(raw).strip()
                if not s or s == "—":
                    return "—"
                return s if s.endswith("%") else f"{s}%"

            _metrics_tip_row([
                (
                    "EV base",
                    _k("EV base"),
                    "Valor de toda la empresa (negocio completo), antes de restar deudas. "
                    "Piénsalo como el precio de una casa sin quitar todavía la hipoteca.",
                ),
                (
                    "Equity base",
                    _k("Equity base"),
                    "Lo que les quedaría a los dueños (accionistas) si se valora el negocio y se pagan deudas y otros reclamos. "
                    "Es la parte del pastel para quien tiene acciones.",
                ),
                (
                    "VPS modelo",
                    _k("VPS modelo"),
                    "Valor por acción según este modelo (equity dividido entre el número de acciones). "
                    "Se compara con el precio de mercado para ver si el modelo ve la acción cara o barata.",
                ),
                (
                    "Upside",
                    _k("Upside %", _k("Upside")),
                    "Diferencia porcentual entre el valor por acción del modelo y el precio de mercado. "
                    "Solo tiene sentido si modelo y cotización están en la misma moneda. "
                    "No es una promesa de ganancia ni una orden de compra.",
                ),
            ], cols=4)

            _metrics_tip_row([
                (
                    "WACC",
                    _pct_label(_k("WACC %")),
                    "Costo promedio del capital: lo mínimo que debería rendir el negocio para satisfacer a prestamistas y dueños. "
                    "Más WACC = el futuro se descuenta más fuerte y el valor suele bajar.",
                ),
                (
                    "ROIC",
                    _pct_label(_k("ROIC %")),
                    "Rentabilidad del capital que ya está invertido en el negocio. "
                    "Si ROIC es mayor que WACC, en general el negocio crea valor; si es menor, puede estar destruyendo valor.",
                ),
                (
                    "VPN proyecto",
                    _k("VPN proyecto", _k("VPN")),
                    "Valor presente neto del proyecto: trae los flujos futuros a pesos de hoy y resta la inversión inicial. "
                    "VPN positivo = con estos supuestos el proyecto aporta valor; negativo = no compensa el capital.",
                ),
                (
                    "TIR / Payback",
                    f"{_k('TIR')} · {_k('Payback')}",
                    "TIR: rentabilidad anual implícita del proyecto (se compara con el WACC). "
                    "Payback: en cuántos años recuperas la inversión en efectivo (no mide si el riesgo valía la pena).",
                ),
            ], cols=4)

            st.markdown("###### Contraste de mercado (consulta bajo demanda)")
            st.caption("La cotización y los múltiplos provienen del proveedor disponible; no se presentan como feed oficial BVC. Se muestran fecha y fuente cuando el proveedor las informa.")
            if st.button("↻ Consultar mercado y contrastar VPS", key="btn_contraste_mercado", use_container_width=True):
                try:
                    _emp_market = L.resolver_empresa(empresa) or {}
                    _ticker_yf = _emp_market.get("ticker_yf") or (
                        L.ticker_yf_empresa(empresa) if hasattr(L, "ticker_yf_empresa") else None
                    )
                    _ticker_bvc = _emp_market.get("ticker_bvc")
                    _market = L.obtener_datos_mercado_bvc(_ticker_yf, ticker_bvc=_ticker_bvc) if _ticker_yf else {}
                    _price = L.resolver_precio_mercado(empresa) if hasattr(L, "resolver_precio_mercado") else None
                    def _parse_num_market(raw):
                        try:
                            clean = str(raw).replace(",", "").replace("$", "").replace("COP", "").replace("USD", "").replace("%", "").strip()
                            value = float(clean)
                            return value if np.isfinite(value) else None
                        except (TypeError, ValueError):
                            return None
                    _equity_kpi = _parse_num_market(_k("Equity base", "—"))
                    _vps_kpi = _parse_num_market(_k("VPS modelo", "—"))
                    _shares = (st.session_state.get("params") or {}).get("acciones") or acciones
                    _market_currency = (
                        st.session_state.get("moneda_precio_alineada")
                        or _market.get("moneda")
                        or moneda
                    )
                    _vps_market = _vps_kpi
                    if _equity_kpi is not None and _shares:
                        _vps_market = L.calcular_vps_y_upside(
                            _equity_kpi, _shares, precio_mercado=None,
                            moneda_modelo=moneda, moneda_precio=_market_currency,
                        ).get("value_per_share")
                    _compare = L.calcular_vps_y_upside(
                        _equity_kpi if _equity_kpi is not None else 0,
                        _shares, precio_mercado=_price,
                        moneda_modelo=moneda, moneda_precio=_market_currency,
                    ) if _equity_kpi is not None and _shares else {}
                    st.session_state["contraste_mercado_actual"] = {
                        "ticker": _ticker_yf, "market": _market, "price": _price,
                        "vps": _vps_market, "upside": _compare.get("upside_pct"),
                        "nota": _compare.get("nota_vps"),
                    }
                except Exception as _market_error:
                    st.warning(f"No se pudo completar el contraste de mercado: {_market_error}")
            _market_saved = st.session_state.get("contraste_mercado_actual")
            if _market_saved:
                _m = _market_saved.get("market") or {}
                _price_saved = _market_saved.get("price")
                _vps_saved = _market_saved.get("vps")
                _upside_saved = _market_saved.get("upside")
                _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                _mc1.metric("Precio mercado", f"{_price_saved:,.2f}" if _price_saved is not None else "N/D")
                _mc2.metric("VPS modelo", f"{_vps_saved:,.2f}" if _vps_saved is not None else "N/D")
                _mc3.metric("Upside comparable", f"{_upside_saved:+.2f}%" if _upside_saved is not None else "N/D")
                _pe_market = _m.get("pe")
                _mc4.metric("P/E mercado", f"{_pe_market:.2f}x" if _pe_market is not None else "N/D")
                _market_date = _m.get("fecha_precio") or "fecha no informada"
                _market_source = _m.get("fuente") or _m.get("proveedor") or "fuente no informada"
                st.caption(f"Ticker: {_market_saved.get('ticker') or 'N/D'} · Fuente: {_market_source} · Fecha del cierre: {_market_date} · Moneda reportada: {_m.get('moneda') or 'N/D'}")
                if _market_saved.get("nota"):
                    st.warning(_market_saved["nota"])
                if _market_saved.get("upside") is None and _price_saved is not None:
                    st.warning("Upside no disponible: revisar moneda, escala de VPS y acciones en circulación.")
                _ev_ebitda_market = _m.get("enterprise_to_ebitda")
                _ev_ebitda_label = f"{_ev_ebitda_market:.2f}x" if _ev_ebitda_market is not None else "N/D"
                st.caption(f"EV/EBITDA de mercado: {_ev_ebitda_label} · No se infiere un múltiplo sectorial cuando no hay comparables observados.")
            st.markdown("###### Escenarios de equity")
            _metrics_tip_row([
                (
                    "Pesimista",
                    _k("Equity pesimista"),
                    "Valor para los dueños si las cosas salen peor de lo normal: menos ventas o márgenes, más costo de capital. "
                    "Si aquí el equity sigue positivo, hay cierto colchón de resiliencia.",
                ),
                (
                    "Base",
                    _k("Equity base"),
                    "Caso central o más probable según los supuestos actuales del modelo. "
                    "Es el número de referencia para discutir en un comité.",
                ),
                (
                    "Optimista",
                    _k("Equity optimista"),
                    "Valor para los dueños si el negocio va mejor (mejores márgenes o menor costo de capital). "
                    "Si solo este escenario se ve bien, la tesis puede ser frágil.",
                ),
            ], cols=3)

            with st.expander("Detalle de KPIs y lectura sencilla", expanded=False):
                if kpi_df is not None:
                    _show_df(kpi_df, "KPIs ejecutivos", csv_key="tab7_kpis")
            # Narrativa HTML completa retirada: el dashboard + PDF cubren la lectura ejecutiva.

            st.markdown("###### Resumen grafico")
            if not _plotly_informe_panel(
                st.session_state.get("resultados") or {},
                title="Resumen grafico · comite",
                chart_key="tab7_exec_panel",
            ):
                if len(r) > 2 and r[2] is not None:
                    _show_fig(r[2], "Panel resumen")
            else:
                _chart_tip(
                    "A) FCFF  B) Escenarios  C) Flujos / VPN  D) Sector. "
                    "Mismos numeros clave que el PDF ejecutivo (sin narrativa larga)."
                )

            st.markdown("###### Exportar para directivos")
            if len(r) > 3 and r[3]:
                pdf_path = r[3]
                if isinstance(pdf_path, str) and os.path.isfile(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "Descargar informe ejecutivo (PDF)",
                            f,
                            file_name=f"informe_ejecutivo_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                        )
                    st.caption(
                        "PDF v2.1 · dashboard (decisión, KPIs, escenarios, auditoría, sector; "
                        "extracto comité IA solo si lo generaste en pestaña 4). "
                        "Si ves un PDF viejo: pulsa otra vez **Generar todo** o la pestaña 7 tras actualizar modelacion_logic.py."
                    )
                else:
                    st.info("PDF no disponible en esta corrida.")
            else:
                st.info("Ejecuta Generar todo para consolidar el informe y el PDF.")
        else:
            st.info(
                "Aun no hay informe. Configura parametros en la barra lateral y pulsa **Generar todo**."
            )

    st.markdown(
        '<div class="tf-footer">Herramienta pedagógica · Catálogo / Yahoo Finance · '
        "No es feed oficial BVC ni asesoría de inversión</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
