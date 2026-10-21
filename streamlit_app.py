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

# API key Gemini: UI → Secrets → env → fallback prestablecido.
_DEFAULT_GEMINI_API_KEY = "AQ.Ab8RN6Lq_5w77l3GlbR4hlmYW9vFRDZjPxv5wn8Iaw4WluWMUA"

def _resolve_gemini_key(ui_key=None):
    """Orden: input UI → st.secrets → env → clave prestablecida."""
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
    return _DEFAULT_GEMINI_API_KEY



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

/* Tooltips KPI */
.tf-kpi[data-tip]:hover::after {
  content: attr(data-tip);
  position: absolute;
  left: 50%;
  bottom: calc(100% + 12px);
  transform: translateX(-50%);
  width: min(280px, 72vw);
  background: #0F172A;
  color: #F1F5F9;
  border: 1px solid #14B8A6;
  border-radius: 12px;
  padding: 11px 13px;
  font-size: 0.78rem;
  font-weight: 400;
  line-height: 1.4;
  letter-spacing: 0;
  text-transform: none;
  z-index: 100;
  box-shadow: 0 16px 36px rgba(0,0,0,0.5);
  pointer-events: none;
  white-space: normal;
}
.tf-kpi[data-tip]:hover::before {
  content: "";
  position: absolute;
  left: 50%;
  bottom: calc(100% + 5px);
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #14B8A6;
  z-index: 101;
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



def _show_df(df, label=None):
    """Preferir tabla Plotly; respaldo st.dataframe con ancho completo."""
    if df is None:
        return
    title = label or "Datos"
    if _plotly_table(df, title=title):
        return
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
    """Obtiene ticker Yahoo a partir de params, nombre o catálogo."""
    p = p or {}
    for k in ("ticker_yf", "ticker", "symbol"):
        t = p.get(k)
        if t and str(t).strip():
            return str(t).strip().upper()
    try:
        if hasattr(L, "params_empresa"):
            pf = L.params_empresa(nombre) or {}
            for k in ("ticker_yf", "ticker", "symbol"):
                t = pf.get(k)
                if t and str(t).strip():
                    return str(t).strip().upper()
    except Exception:
        pass
    try:
        emp = L.resolver_empresa(nombre) if hasattr(L, "resolver_empresa") else None
        if emp:
            for k in ("ticker_yf", "ticker", "symbol"):
                t = (emp.get("params") or {}).get(k) or emp.get(k)
                if t and str(t).strip():
                    return str(t).strip().upper()
    except Exception:
        pass
    # Heurística: "AAPL — Apple" → AAPL; nombres con .CL / .NYSE
    base = str(nombre or "").split("—")[0].split("-")[0].strip().upper()
    if base and 1 <= len(base) <= 12 and " " not in base:
        return base
    return None


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
    Asegura que moneda del modelo y del precio de mercado coincidan.
    - Emisores US / Yahoo en USD → modelo USD, precio en USD, CAPM US (rf/erp/crp).
    - Emisores CO / .CL → COP.
    Escribe en session_state['params'] y, si existe, en el dict de la empresa en L.
    """
    p = dict(st.session_state.get("params") or {})
    mon = str(p.get("moneda") or "").upper()
    merc = str(p.get("mercado_capm") or "").upper()
    ticker = _inferir_ticker_yf(nombre, p)

    precio = None
    moneda_precio = None
    try:
        if ticker:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = {}
            try:
                info = getattr(t, "info", None) or {}
            except Exception:
                info = {}
            moneda_precio = str(
                info.get("currency")
                or info.get("financialCurrency")
                or ""
            ).upper()
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
                    fi = getattr(t, "fast_info", None)
                    if fi is not None:
                        lp = getattr(fi, "last_price", None) or (fi.get("last_price") if hasattr(fi, "get") else None)
                        if lp is not None and float(lp) > 0:
                            precio = float(lp)
                        if not moneda_precio:
                            moneda_precio = str(
                                getattr(fi, "currency", None)
                                or (fi.get("currency") if hasattr(fi, "get") else "")
                                or ""
                            ).upper()
                except Exception:
                    pass
            if precio is None:
                try:
                    hist = t.history(period="5d", auto_adjust=True)
                    if hist is not None and len(hist) > 0:
                        precio = float(hist["Close"].iloc[-1])
                except Exception:
                    pass
    except Exception:
        pass

    # Inferir mercado US si Yahoo reporta USD o el ticker/nombre lo indican
    if not moneda_precio and mon in ("USD", "US$"):
        moneda_precio = "USD"
    us = _es_mercado_us(moneda=mon or moneda_precio, mercado=merc, ticker=ticker, nombre=nombre)
    if moneda_precio in ("USD", "US$") or (ticker and "." not in str(ticker) and us):
        us = True
        moneda_precio = moneda_precio or "USD"

    if us:
        p["moneda"] = "USD"
        p["mercado_capm"] = p.get("mercado_capm") or "US"
        if ticker:
            p["ticker_yf"] = ticker
        if precio is not None and precio > 0:
            p["precio"] = precio
            p["precio_mercado"] = precio
            p["precio_moneda"] = "USD"
        # CAPM US: no dejar rf de Colombia
        if float(st.session_state.get("rf", 0.12)) >= 0.08:
            st.session_state["rf"] = 0.045
        if float(st.session_state.get("erp", 0.055)) > 0.07:
            st.session_state["erp"] = 0.05
        st.session_state["crp"] = 0.0
        em = float(p.get("exit_multiple") or 0)
        if em < 12:
            p["exit_multiple"] = 22.0
        # Tax corporativo US por defecto si venía 35% CO
        try:
            if float(p.get("tax") or 0) >= 0.33:
                p["tax"] = 0.21
        except Exception:
            pass
    else:
        # Colombia / local
        if not mon or mon in ("", "NONE"):
            p["moneda"] = "COP"
        if moneda_precio in ("COP", "COL"):
            p["precio_moneda"] = "COP"
            if precio is not None and precio > 0:
                p["precio"] = precio
                p["precio_mercado"] = precio
        if ticker:
            p["ticker_yf"] = ticker

    st.session_state["params"] = p
    st.session_state["precio_mercado_alineado"] = p.get("precio_mercado") or p.get("precio")
    st.session_state["moneda_precio_alineada"] = p.get("precio_moneda") or p.get("moneda")

    # Propagar al objeto empresa en la lógica (evita warning modelo USD vs precio COP)
    try:
        emp = None
        if hasattr(L, "resolver_empresa"):
            emp = L.resolver_empresa(nombre)
        if emp is None:
            emp = getattr(L, "EMPRESAS_RUNTIME", {}).get(nombre) or getattr(L, "EMPRESAS", {}).get(nombre)
        if emp and isinstance(emp, dict):
            ep = emp.setdefault("params", {})
            for k in ("moneda", "mercado_capm", "ticker_yf", "precio", "precio_mercado", "precio_moneda", "tax", "exit_multiple"):
                if k in p and p[k] is not None:
                    ep[k] = p[k]
            emp["moneda"] = p.get("moneda") or emp.get("moneda")
            if p.get("precio") is not None:
                emp["precio"] = p["precio"]
        # Hooks opcionales de la lógica
        if hasattr(L, "actualizar_precio_y_moneda") and p.get("precio") is not None:
            try:
                L.actualizar_precio_y_moneda(nombre, p["precio"], p.get("moneda") or "USD")
            except Exception:
                pass
        if hasattr(L, "set_moneda_modelo"):
            try:
                L.set_moneda_modelo(nombre, p.get("moneda") or "USD")
            except Exception:
                pass
    except Exception:
        pass
    return p


def _cargar_params_empresa(nombre):
    try:
        out = L.al_cambiar_empresa(nombre)
        if isinstance(out, (list, tuple)) and len(out) >= 15:
            st.session_state["ficha_html"] = out[0]
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
            if st.session_state.get("ficha_html"):
                _html(st.session_state["ficha_html"])
            else:
                st.caption("Selecciona o descarga una empresa para ver la ficha.")

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

    # Si aún hay desalineación residual, forzar etiqueta de precio = moneda del modelo
    if moneda in ("USD", "US$") and moneda_precio in ("COP", "COL"):
        moneda_precio = "USD"
        pfix = st.session_state.get("params") or {}
        pfix["precio_moneda"] = "USD"
        pfix["moneda"] = "USD"
        st.session_state["params"] = pfix
        st.session_state["moneda_precio_alineada"] = "USD"
        try:
            emp_fix = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
            if emp_fix and isinstance(emp_fix, dict):
                emp_fix.setdefault("params", {})["moneda"] = "USD"
                emp_fix["params"]["precio_moneda"] = "USD"
                emp_fix["moneda"] = "USD"
        except Exception:
            pass
    elif moneda in ("COP", "COL") and moneda_precio in ("USD", "US$"):
        # ADR / dual listing: EEFF en COP, cotización en USD → no forzar FX; anular upside implícito
        st.session_state["fx_mismatch"] = True
        st.session_state["moneda_precio_alineada"] = moneda_precio
    else:
        st.session_state["fx_mismatch"] = False


    # ----- KPI strip (con burbujas al pasar el cursor) -----
    _kpi_row(
        [
            (
                "WACC",
                f"{w['wacc']*100:.2f}%",
                "costo capital",
                True,
                "WACC: rentabilidad mínima exigida por deuda y equity. Si el ROIC supera el WACC, el negocio crea valor.",
            ),
            (
                "Ke (CAPM)",
                f"{w['ke']*100:.2f}%",
                f"βL {w['beta_l']:.2f}",
                False,
                "Ke (CAPM): costo del equity = rf + β apalancado × ERP + CRP. Es la rentabilidad que piden los accionistas.",
            ),
            (
                "Horizonte",
                f"{horizonte} a",
                f"g {g*100:.1f}%",
                False,
                "Años de proyección explícita de FCFF. Después se aplica valor terminal (Gordon) con g ≤ techo macro.",
            ),
            (
                "Emisor",
                empresa.split("—")[0].strip()[:18],
                str(sector)[:22],
                False,
                f"Empresa en análisis: {empresa}. Sector/industria usados para peers y ranking comparativo.",
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
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("WACC base → prueba", f"{sw*100:.2f}%", delta=f"{(sw - w['wacc'])*100:+.2f} pp")
            with col_b:
                st.metric("g base → prueba", f"{sg*100:.2f}%", delta=f"{(sg - g)*100:+.2f} pp")
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
    st.caption("Un solo botón calcula las 7 pestañas. CAPM se alinea al mercado del emisor (US/CO/…). Validaciones de WACC vs g y bridge deuda neta mejoran la exactitud.")
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
        pasos = [
            ("1 · Pronóstico FCFF", 1 / 7),
            ("2 · Escenarios DCF", 2 / 7),
            ("3 · Auditoría", 3 / 7),
            ("4 · Recomendación", 4 / 7),
            ("5 · VPN / TIR", 5 / 7),
            ("6 · Sector", 6 / 7),
            ("7 · Informe PDF", 7 / 7),
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

            progress.progress(pasos[4][1], text=pasos[4][0])
            try:
                st.session_state["resultados"]["tab5"] = L.tab5_vpn_tir(
                    empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                    inversion_inicial, rf, erp, crp, usar_publicos,
                )
            except Exception as e:
                errores.append(f"Pestaña 5: {e}")

            progress.progress(pasos[5][1], text=pasos[5][0])
            try:
                st.session_state["resultados"]["tab6"] = L.tab6_comparacion_sectorial(empresa)
            except Exception as e:
                errores.append(f"Pestaña 6: {e}")

            progress.progress(pasos[6][1], text=pasos[6][0])
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
                st.success("Todos los resultados generados. Revisa cada pestaña.")
            st.rerun()
        except Exception as e:
            st.error(str(e))
            st.code(traceback.format_exc())

    # ----- 7 TABS (solo visualización; los datos se generan con «Generar todo») -----
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
        r = st.session_state.get("resultados", {}).get("tab1")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            c_a, c_b = st.columns(2)
            with c_a:
                if len(r) > 1:
                    _show_df(r[1], "Historial")
            with c_b:
                if len(r) > 2:
                    _show_df(r[2], "Proyección")
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
        r = st.session_state.get("resultados", {}).get("tab2")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Por escenario")
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
                "<b>EV</b> = precio de toda la empresa (como el de una casa antes de la hipoteca). "
                "<b>Equity</b> = lo que les quedaría a los dueños tras pagar deudas. "
                "Si solo el escenario optimista se ve bien, el caso es frágil: conviene revisar supuestos."
            )

    with tab3:
        st.markdown("##### Coherencia de supuestos")
        st.caption("Resultados generados con «Generar todo».")
        r = st.session_state.get("resultados", {}).get("tab3")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Pruebas")
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
        r = st.session_state.get("resultados", {}).get("tab4")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Gobernanza")
            if len(r) > 2:
                _html(r[2])
            _explain(
                "<b>En palabras simples:</b> la recomendación resume si, con estos números, tiene sentido "
                "llevar el caso a un comité. No es una orden de compra: es un marco para discutir riesgos y valor."
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
            f"Empresa en análisis: **{empresa}**. "
            "Mismo proveedor/API key que Consulta IA. "
            "La salida es una recomendación ejecutiva en lenguaje sencillo, basada en los números del modelo."
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

        def _precio_mercado_empresa_actual(nombre_emp):
            """Precio de cotización fresco y en escala correcta (BVC en COP por acción)."""
            px = 0.0
            mon_px = "COP"
            fuente = ""
            try:
                # 1) Session alineada (si es razonable)
                px_ss = _safe_float(st.session_state.get("precio_mercado_alineado"), 0.0)
                mon_ss = str(
                    st.session_state.get("moneda_precio_alineada")
                    or (st.session_state.get("params") or {}).get("precio_moneda")
                    or ""
                ).upper()
                # 2) Conector de lógica (Yahoo / .CL)
                px_logic = 0.0
                if hasattr(L, "resolver_precio_mercado"):
                    try:
                        px_logic = _safe_float(L.resolver_precio_mercado(nombre_emp), 0.0)
                    except Exception:
                        px_logic = 0.0
                if px_logic <= 0 and hasattr(L, "precio_mercado_actual"):
                    try:
                        px_logic = _safe_float(L.precio_mercado_actual(nombre_emp), 0.0)
                    except Exception:
                        pass
                # 3) Ticker explícito .CL vía Yahoo
                tk = None
                try:
                    if hasattr(L, "ticker_yf_empresa"):
                        tk = L.ticker_yf_empresa(nombre_emp)
                    if not tk and hasattr(L, "asegurar_sufijo_cl_bvc"):
                        emp_o = L.resolver_empresa(nombre_emp) if hasattr(L, "resolver_empresa") else None
                        if emp_o:
                            tk = emp_o.get("ticker_yf") or emp_o.get("ticker_bvc")
                        if tk and hasattr(L, "asegurar_sufijo_cl_bvc"):
                            tk = L.asegurar_sufijo_cl_bvc(tk)
                except Exception:
                    tk = None
                px_yf = 0.0
                mon_yf = ""
                if tk:
                    try:
                        import yfinance as yf
                        t = yf.Ticker(str(tk))
                        info = {}
                        try:
                            info = t.info or {}
                        except Exception:
                            info = {}
                        mon_yf = str(info.get("currency") or "").upper().replace("US$", "USD")
                        for key in ("regularMarketPrice", "currentPrice", "previousClose"):
                            v = info.get(key)
                            if v is not None and float(v) == float(v) and float(v) > 0:
                                px_yf = float(v)
                                break
                        if px_yf <= 0:
                            hist = t.history(period="10d", auto_adjust=True)
                            if hist is not None and len(hist) > 0 and "Close" in hist.columns:
                                closes = [float(c) for c in hist["Close"].tolist() if c == c and float(c) > 0]
                                if closes:
                                    px_yf = closes[-1]
                        if str(tk).upper().endswith(".CL"):
                            mon_yf = "COP"
                    except Exception:
                        pass

                # Elegir el precio más creíble
                candidatos = []
                if px_yf > 0:
                    candidatos.append((px_yf, mon_yf or mon_ss or "COP", "yahoo"))
                if px_logic > 0:
                    candidatos.append((px_logic, mon_ss or mon_yf or "COP", "logic"))
                if px_ss > 0:
                    candidatos.append((px_ss, mon_ss or "COP", "session"))

                # Para BVC (.CL): precio por acción suele estar en miles de COP (p.ej. ISA ~20k–35k).
                # Descartar valores absurdamente bajos si hay un candidato mejor.
                es_bvc = bool(tk and str(tk).upper().endswith(".CL"))
                if es_bvc and candidatos:
                    buenos = [c for c in candidatos if c[0] >= 500]
                    if buenos:
                        # Preferir yahoo fresco
                        buenos.sort(key=lambda x: (0 if x[2] == "yahoo" else 1, -x[0]))
                        px, mon_px, fuente = buenos[0]
                    else:
                        px, mon_px, fuente = max(candidatos, key=lambda x: x[0])
                elif candidatos:
                    candidatos.sort(key=lambda x: (0 if x[2] == "yahoo" else 1, -x[0]))
                    px, mon_px, fuente = candidatos[0]

                if px > 0:
                    st.session_state["precio_mercado_alineado"] = px
                    st.session_state["moneda_precio_alineada"] = mon_px or "COP"
                    ptmp = st.session_state.get("params") or {}
                    ptmp["precio"] = px
                    ptmp["precio_mercado"] = px
                    ptmp["precio_moneda"] = mon_px or "COP"
                    st.session_state["params"] = ptmp
            except Exception:
                pass
            return px, (mon_px or "COP"), fuente

        def _extraer_kpis_comite():
            """KPIs del emisor actualmente seleccionado (sidebar), no de otra sesión."""
            res = st.session_state.get("resultados") or {}
            wacc_calc = float(w.get("wacc", 0.10) if isinstance(w, dict) else 0.10)
            ke_calc = float(w.get("ke", 0.12) if isinstance(w, dict) else 0.12)
            roic_calc = 0.0
            val_ev = 0.0
            val_equity = 0.0
            vps_modelo = 0.0
            upside = 0.0
            mon_m = str((st.session_state.get("params") or {}).get("moneda") or moneda or "COP").upper()
            mon_m = "COP" if mon_m in ("COL",) else mon_m

            # Precio fresco de ESTA empresa
            precio_mercado, mon_px, fuente_px = _precio_mercado_empresa_actual(empresa)
            mon_px = str(mon_px or mon_m).upper()
            if mon_px in ("COL",):
                mon_px = "COP"

            # Ticker / sector de la empresa actual
            ticker = "—"
            sector_txt = "—"
            try:
                if hasattr(L, "ticker_yf_empresa"):
                    ticker = L.ticker_yf_empresa(empresa) or "—"
                emp_o = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
                if emp_o:
                    sector_txt = str(emp_o.get("sector") or "—")
                    if ticker == "—":
                        ticker = emp_o.get("ticker_yf") or emp_o.get("ticker_bvc") or "—"
            except Exception:
                pass

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
            upside_raw = _k("Upside %", "Upside")
            if upside_raw is not None:
                upside = _safe_float(upside_raw, 0.0)
            wacc_k = _k("WACC %", "WACC")
            if wacc_k is not None:
                ww = _safe_float(wacc_k, wacc_calc * 100)
                wacc_calc = ww / 100.0 if ww > 1.0 else ww
            roic_k = _k("ROIC %", "ROIC")
            if roic_k is not None:
                rr = _safe_float(roic_k, 0.0)
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

            # VPS correcto: equity (miles M) * 1000 / acciones (millones) = COP (o USD) por acción
            acc = float(acciones or 0)
            if acc <= 0:
                try:
                    acc = float(L.resolver_acciones_millones(empresa, None) or 0)
                except Exception:
                    acc = 0.0
            if vps_modelo <= 0 and val_equity > 0 and acc > 0:
                # Convención del modelo: VPS = equity_mm * 1000 / acciones_m
                vps_modelo = (val_equity * 1000.0) / acc
            # Si el VPS quedó ~1000× más chico que el precio BVC, corregir factor
            if (
                precio_mercado >= 1000
                and vps_modelo > 0
                and vps_modelo < precio_mercado * 0.05
                and val_equity > 0
                and acc > 0
            ):
                vps_alt = (val_equity * 1000.0) / acc
                if abs(vps_alt - precio_mercado) < abs(vps_modelo - precio_mercado):
                    vps_modelo = vps_alt

            monedas_ok = mon_m.replace("$", "") == mon_px.replace("$", "")
            if monedas_ok and precio_mercado > 0 and vps_modelo > 0:
                upside = 100.0 * (vps_modelo - precio_mercado) / precio_mercado
            elif not monedas_ok:
                upside = 0.0

            decision_modelo = "—"
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
            t4 = res.get("tab4")
            if decision_modelo == "—" and t4 and isinstance(t4, (list, tuple)) and len(t4) > 0 and t4[0]:
                decision_modelo = "Ver salida cuantitativa de la pestaña 4"

            return {
                "empresa": empresa,
                "ticker": ticker,
                "sector": sector_txt,
                "moneda": mon_m,
                "moneda_precio": mon_px,
                "monedas_alineadas": monedas_ok,
                "precio_mercado": precio_mercado,
                "fuente_precio": fuente_px,
                "vps_modelo": vps_modelo,
                "upside": upside,
                "wacc_calc": wacc_calc,
                "ke_calc": ke_calc,
                "roic_calc": roic_calc,
                "de_ratio": float(de_ratio),
                "g": float(g),
                "val_ev": val_ev,
                "val_equity": val_equity,
                "acciones_m": acc,
                "decision_modelo": decision_modelo,
            }

        def _prompt_comite_ia(ctx: dict) -> str:
            emp = ctx.get("empresa") or "la empresa seleccionada"
            tk = ctx.get("ticker") or "—"
            return (
                f"Eres el comité de inversión que analiza ÚNICAMENTE a: **{emp}** (ticker {tk}).\n"
                "No hables de otras empresas. No inventes datos fuera del contexto numérico.\n"
                "Responde en español, en lenguaje sencillo (como si explicaras a un director no financiero).\n"
                "Sé breve, ejecutivo y concreto: máximo ~350 palabras.\n"
                "---\n"
                "### DATOS DEL MODELO (úsalos tal cual)\n"
                f"- Empresa: {emp}\n"
                f"- Ticker: {tk} · Sector: {ctx.get('sector', '—')}\n"
                f"- Moneda modelo: {ctx.get('moneda', 'COP')} · Moneda precio: {ctx.get('moneda_precio', 'COP')} · "
                f"Alineadas: {'SÍ' if ctx.get('monedas_alineadas', True) else 'NO'}\n"
                f"- Precio de mercado actual: {ctx['precio_mercado']:,.2f} {ctx.get('moneda_precio', '')}\n"
                f"- Valor por acción del modelo (VPS): {ctx['vps_modelo']:,.2f}\n"
                f"- Upside modelo vs mercado: {ctx['upside']:+.1f}% "
                f"{'(no comparable: monedas distintas)' if not ctx.get('monedas_alineadas', True) else ''}\n"
                f"- WACC: {ctx['wacc_calc']*100:.2f}% · Ke: {ctx['ke_calc']*100:.2f}% · ROIC: {ctx['roic_calc']*100:.2f}%\n"
                f"- D/E: {ctx['de_ratio']:.2f} · g terminal: {ctx['g']*100:.2f}%\n"
                f"- EV base: {ctx['val_ev']:,.1f} · Equity base: {ctx['val_equity']:,.1f} "
                f"(miles de millones {ctx.get('moneda', '')})\n"
                f"- Decisión cuantitativa previa del sistema: {ctx.get('decision_modelo', '—')}\n"
                "---\n"
                "### FORMATO OBLIGATORIO DE RESPUESTA (respeta los títulos)\n"
                f"## Veredicto sobre {emp}\n"
                "**Recomendación:** INVERTIR / NO INVERTIR / INVERTIR CON CONDICIONES\n"
                "**En una frase:** [por qué, en palabras simples]\n\n"
                "## Qué dicen los números\n"
                "- [Precio de mercado vs valor del modelo, en lenguaje claro]\n"
                "- [Si el negocio crea valor: ROIC vs WACC]\n"
                "- [Riesgo principal en una línea]\n\n"
                "## Condiciones o señales a vigilar\n"
                "1. ...\n"
                "2. ...\n\n"
                "## Nota\n"
                "Esto apoya la discusión del comité; no es una orden de compra ni asesoría personalizada.\n"
            )

        def _fallback_ejecutivo(ctx: dict) -> str:
            """Respuesta local si la IA falla: veredicto simple con los KPIs."""
            emp = ctx.get("empresa") or "la empresa"
            px = ctx.get("precio_mercado") or 0
            vps = ctx.get("vps_modelo") or 0
            up = ctx.get("upside") or 0
            wacc = (ctx.get("wacc_calc") or 0) * 100
            roic = (ctx.get("roic_calc") or 0) * 100
            mon = ctx.get("moneda_precio") or ctx.get("moneda") or ""
            ok_fx = ctx.get("monedas_alineadas", True)
            crea_valor = roic > wacc if (roic and wacc) else None

            if not ok_fx:
                rec = "INVERTIR CON CONDICIONES"
                frase = "Hay que alinear la moneda del modelo con la del precio antes de usar el upside."
            elif px > 0 and vps > 0 and up >= 15 and (crea_valor is not False):
                rec = "INVERTIR"
                frase = f"El modelo ve la acción por encima del mercado (~{up:+.0f}%) y el negocio parece crear valor."
            elif px > 0 and vps > 0 and up <= -15:
                rec = "NO INVERTIR"
                frase = f"El mercado cotiza por encima de lo que el modelo justifica (~{up:+.0f}%)."
            elif px > 0 and vps > 0:
                rec = "INVERTIR CON CONDICIONES"
                frase = "El valor del modelo y el precio están cerca; conviene revisar supuestos y riesgos."
            else:
                rec = "INVERTIR CON CONDICIONES"
                frase = "Faltan precio o valor por acción confiables; completa Generar todo y revisa el precio de mercado."

            roic_txt = (
                f"El ROIC ({roic:.1f}%) {'supera' if crea_valor else 'no supera'} al WACC ({wacc:.1f}%), "
                f"o sea {'crea' if crea_valor else 'no crea claramente'} valor con estos supuestos."
                if crea_valor is not None else
                f"WACC del modelo: {wacc:.1f}%."
            )
            return (
                f"<div class='tf-section'>"
                f"<div class='tf-section-title'>Veredicto sobre {emp}</div>"
                f"<p style='font-size:1.15rem;font-weight:700;color:#5EEAD4;margin:0.4rem 0'>{rec}</p>"
                f"<p style='color:#E2E8F0'><b>En una frase:</b> {frase}</p>"
                f"<p style='color:#CBD5E1'><b>Qué dicen los números</b><br>"
                f"· Precio de mercado: <b>{px:,.2f} {mon}</b> · VPS modelo: <b>{vps:,.2f}</b> · "
                f"Upside: <b>{up:+.1f}%</b><br>"
                f"· {roic_txt}</p>"
                f"<p style='color:#94A3B8;font-size:0.85rem'>Apoyo a decisión · no es orden de compra ni asesoría de inversión.</p>"
                f"</div>"
            )

        with st.expander("Generar deliberación del comité con IA", expanded=True):
            # Reset salida si cambió la empresa
            if st.session_state.get("tab4_comite_empresa") != empresa:
                st.session_state["tab4_comite_ia_html"] = None
                st.session_state["tab4_comite_empresa"] = empresa

            ctx_preview = _extraer_kpis_comite()
            st.markdown(
                f"<div class='tf-info'><b>{ctx_preview.get('empresa','')}</b> · "
                f"Ticker <b>{ctx_preview.get('ticker','—')}</b> · "
                f"{ctx_preview.get('sector','—')}</div>",
                unsafe_allow_html=True,
            )
            c_prev1, c_prev2, c_prev3, c_prev4 = st.columns(4)
            _px = ctx_preview.get("precio_mercado") or 0
            _mon = ctx_preview.get("moneda_precio") or ctx_preview.get("moneda") or ""
            _fuente = ctx_preview.get("fuente_precio") or ""
            c_prev1.metric(
                "Precio mkt",
                f"{_px:,.2f} {_mon}" if _px > 0 else "—",
                help=f"Fuente: {_fuente or 'n/d'}. Para ISA.CL el precio BVC suele estar en miles de COP por acción.",
            )
            c_prev2.metric("VPS modelo", f"{ctx_preview['vps_modelo']:,.2f}" if ctx_preview.get("vps_modelo") else "—")
            c_prev3.metric("Upside", f"{ctx_preview['upside']:+.1f}%")
            c_prev4.metric(
                "EV / Equity",
                f"{ctx_preview['val_ev']:,.0f} / {ctx_preview['val_equity']:,.0f}",
            )
            if _px > 0 and _px < 500 and str(ctx_preview.get("ticker") or "").upper().endswith(".CL"):
                st.warning(
                    f"El precio {_px:,.2f} {_mon} parece bajo para un listado BVC (.CL). "
                    "Revisa el ticker (debe terminar en .CL) o vuelve a pulsar Generar todo / Deliberar."
                )

            _opts = ["gemini", "xai", "openai"]
            _prov_consulta = st.session_state.get("iaprov") or "gemini"
            if _prov_consulta not in _opts:
                _prov_consulta = "gemini"
            if "tab4_iaprov" not in st.session_state:
                st.session_state["tab4_iaprov"] = _prov_consulta

            with st.expander("Proveedor y API key (compartido con Consulta IA)", expanded=False):
                prov_ia = st.selectbox(
                    "Proveedor",
                    _opts,
                    key="tab4_iaprov",
                    help="Por defecto toma el proveedor de Consulta IA.",
                )
                key_ui = st.text_input(
                    "API key (opcional — vacío = Gemini por defecto / clave de Consulta IA)",
                    type="password",
                    key="tab4_iakey",
                    placeholder="Vacío = Gemini por defecto",
                )
                st.caption(
                    "Si dejas la API key vacía se usa la de Consulta IA o st.secrets / GEMINI_API_KEY."
                )

            prov_ia = st.session_state.get("tab4_iaprov") or st.session_state.get("iaprov") or "gemini"
            key_ui = (st.session_state.get("tab4_iakey") or "").strip() or (st.session_state.get("iakey") or "")

            if st.button("▶ Deliberar en el comité (IA)", type="primary", key="btn_tab4_comite_ia", use_container_width=True):
                ctx = _extraer_kpis_comite()
                st.session_state["tab4_comite_empresa"] = empresa
                if not ctx.get("monedas_alineadas", True):
                    st.warning(
                        f"Moneda del modelo ({ctx.get('moneda')}) ≠ cotización ({ctx.get('moneda_precio')}). "
                        "El veredicto tratará el upside con cautela."
                    )
                if (ctx.get("precio_mercado") or 0) <= 0:
                    st.warning("No hay precio de mercado usable. El comité se basará solo en el modelo.")
                prompt = _prompt_comite_ia(ctx)
                with st.spinner(f"El comité analiza {empresa}…"):
                    try:
                        key_eff = (
                            _resolve_gemini_key(key_ui)
                            if (prov_ia or "gemini") == "gemini"
                            else ((key_ui or "").strip() or None)
                        )
                        if prov_ia == "gemini" and not key_eff:
                            key_eff = _resolve_gemini_key(None)
                        respuesta = L.asistente_consulta_financiera(
                            prompt, empresa, api_key=key_eff, proveedor=prov_ia or "gemini",
                        )
                        # Si la IA no devolvió texto útil, fallback ejecutivo local
                        plain = str(respuesta or "")
                        if (
                            not plain
                            or len(plain) < 40
                            or "error" in plain.lower()[:80]
                            or "api key" in plain.lower()
                        ):
                            st.session_state["tab4_comite_ia_html"] = _fallback_ejecutivo(ctx)
                        else:
                            st.session_state["tab4_comite_ia_html"] = respuesta
                    except Exception as e:
                        st.error(str(e))
                        st.session_state["tab4_comite_ia_html"] = _fallback_ejecutivo(ctx)

            if st.session_state.get("tab4_comite_ia_html") and st.session_state.get("tab4_comite_empresa") == empresa:
                st.markdown("###### Salida del comité")
                _html(st.session_state["tab4_comite_ia_html"])
                _explain(
                    "<b>Uso:</b> veredicto ejecutivo sobre <b>esta</b> empresa. "
                    "No es asesoría de inversión ni orden de compra/venta."
                )
            elif st.session_state.get("tab4_comite_ia_html"):
                st.info("La salida anterior era de otra empresa. Pulsa de nuevo Deliberar para esta.")

    with tab5:
        st.markdown("##### VPN · TIR · Payback")
        st.caption("Resultados generados con «Generar todo».")
        r = st.session_state.get("resultados", {}).get("tab5")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Flujos")
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
        r = st.session_state.get("resultados", {}).get("tab6")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Comparables")
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

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("EV base", _k("EV base"))
            c2.metric("Equity base", _k("Equity base"))
            c3.metric("VPS modelo", _k("VPS modelo"))
            c4.metric("Upside", _k("Upside %", _k("Upside")))

            c5, c6, c7, c8 = st.columns(4)
            def _pct_label(raw):
                s = str(raw).strip()
                if not s or s == "—":
                    return "—"
                return s if s.endswith("%") else f"{s}%"
            c5.metric("WACC", _pct_label(_k("WACC %")))
            c6.metric("ROIC", _pct_label(_k("ROIC %")))
            c7.metric("VPN proyecto", _k("VPN proyecto", _k("VPN")))
            c8.metric("TIR / Payback", f"{_k('TIR')} · {_k('Payback')}")

            st.markdown("###### Escenarios de equity")
            e1, e2, e3 = st.columns(3)
            e1.metric("Pesimista", _k("Equity pesimista"))
            e2.metric("Base", _k("Equity base"))
            e3.metric("Optimista", _k("Equity optimista"))

            with st.expander("Detalle de KPIs y lectura sencilla", expanded=False):
                if kpi_df is not None:
                    _show_df(kpi_df, "KPIs ejecutivos")
            with st.expander("Narrativa completa del informe", expanded=False):
                if len(r) > 0:
                    _html(r[0])

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
                    "Mismos numeros que el PDF ejecutivo."
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
                    st.caption("El PDF incluye decision, KPIs, escenarios, auditoria, sector y graficos.")
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
