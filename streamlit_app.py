"""
Modelación Financiera Multisectorial — Streamlit UI (FinTech Dark)
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

# API key Gemini por defecto (prioridad: Secrets / env → fallback embebido).
# En producción pública preferir st.secrets["GEMINI_API_KEY"] y rotar esta clave.
_DEFAULT_GEMINI_KEY = "AQ.Ab8RN6Lq_5w77l3GlbR4hlmYW9vFRDZjPxv5wn8Iaw4WluWMUA"


def _resolve_gemini_key(ui_key=None):
    """Orden: input UI → st.secrets → env → default embebido."""
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
    return _DEFAULT_GEMINI_KEY


# Exponer al módulo de lógica si no hay variable de entorno
if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
    os.environ["GEMINI_API_KEY"] = _DEFAULT_GEMINI_KEY

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="Modelación Financiera · Multisectorial",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# DESIGN SYSTEM — Dark Slate FinTech
# =============================================================================
FINTECH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
  --bg-deep: #0B1220;
  --bg-panel: #111827;
  --bg-card: #151C2C;
  --bg-elevated: #1A2336;
  --border: #243044;
  --border-soft: rgba(36, 48, 68, 0.85);
  --text: #F1F5F9;
  --text-muted: #CBD5E1;
  --text-dim: #94A3B8;
  --accent: #14B8A6;
  --accent-soft: rgba(20, 184, 166, 0.15);
  --accent-hover: #2DD4BF;
  --blue: #3B82F6;
  --warning: #F59E0B;
  --danger: #EF4444;
  --success: #10B981;
  --radius: 12px;
  --shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
  --font: 'IBM Plex Sans', system-ui, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg-deep) !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
}

.main .block-container {
  padding-top: 1.25rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1440px !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0F172A 0%, #0B1220 100%) !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * {
  color: var(--text) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  color: #E2E8F0 !important;
  font-size: 0.84rem !important;
  font-weight: 500 !important;
}
section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {
  color: #94A3B8 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  padding-top: 0.75rem;
}

/* Headers */
h1, h2, h3, h4 {
  font-family: var(--font) !important;
  letter-spacing: -0.02em !important;
  color: var(--text) !important;
}
h1 { font-weight: 700 !important; font-size: 1.65rem !important; }
h2 { font-weight: 600 !important; font-size: 1.2rem !important; }
h3 { font-weight: 600 !important; font-size: 1.05rem !important; color: #CBD5E1 !important; }

/* Metrics default */
[data-testid="stMetric"] {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.85rem 1rem;
  box-shadow: var(--shadow);
}
[data-testid="stMetricLabel"] {
  color: var(--text-muted) !important;
  font-size: 0.72rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important;
  font-weight: 600 !important;
  color: var(--text) !important;
  font-size: 1.35rem !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.35rem;
  background: transparent;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.25rem;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-muted) !important;
  border-radius: 8px 8px 0 0 !important;
  font-weight: 500 !important;
  font-size: 0.88rem !important;
  padding: 0.55rem 1rem !important;
}
.stTabs [aria-selected="true"] {
  background: var(--accent-soft) !important;
  color: var(--accent) !important;
  border-bottom: 2px solid var(--accent) !important;
}

/* Buttons */
.stButton > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-family: var(--font) !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-elevated) !important;
  color: var(--text) !important;
  transition: all 0.15s ease !important;
  padding: 0.45rem 1.1rem !important;
}
.stButton > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent-hover) !important;
  box-shadow: 0 0 0 1px rgba(20, 184, 166, 0.25);
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
  color: #042F2E !important;
  border: none !important;
  box-shadow: 0 4px 14px rgba(20, 184, 166, 0.35) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
  background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
  color: #042F2E !important;
}

/* Inputs */
.stSelectbox > div > div,
.stNumberInput > div > div > input,
.stTextInput > div > div > input,
.stTextArea textarea {
  background: var(--bg-panel) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
  background: var(--accent) !important;
}

/* Expanders — contraste alto (cabecera y contenido) */
.streamlit-expanderHeader,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details summary,
div[data-testid="stExpander"] > details > summary {
  background: #1A2336 !important;
  border-radius: 10px !important;
  border: 1px solid #334155 !important;
  color: #F1F5F9 !important;
  font-weight: 600 !important;
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
  background: #111827 !important;
  border: 1px solid #334155 !important;
  border-top: none !important;
  border-radius: 0 0 10px 10px !important;
  color: #E8EEF7 !important;
}
/* Sidebar: expanders aún más legibles */
section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
section[data-testid="stSidebar"] .streamlit-expanderHeader {
  background: #1E293B !important;
  border-color: #475569 !important;
  color: #F8FAFC !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
  color: #F8FAFC !important;
}
section[data-testid="stSidebar"] [data-testid="stExpanderDetails"],
section[data-testid="stSidebar"] .streamlit-expanderContent {
  background: #0F172A !important;
  border-color: #334155 !important;
}

/* Dataframes */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  overflow: hidden;
}

/* Alerts */
.stAlert {
  border-radius: 10px !important;
  border: 1px solid var(--border) !important;
}

/* Divider */
hr {
  border-color: var(--border) !important;
  margin: 1.25rem 0 !important;
}

/* Custom components */
.tf-hero {
  background: linear-gradient(135deg, #0B1F33 0%, #163A5F 55%, #0F766E 140%);
  border: 1px solid rgba(153, 246, 228, 0.18);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  margin: 0 0 1.25rem 0;
  box-shadow: var(--shadow);
}
.tf-hero h1 {
  margin: 0 0 0.35rem 0 !important;
  font-size: 1.55rem !important;
  color: #F8FAFC !important;
}
.tf-hero p {
  margin: 0;
  color: #99F6E4;
  font-size: 0.9rem;
  line-height: 1.45;
}
.tf-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 0.75rem;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.2);
  border: 1px solid rgba(153, 246, 228, 0.35);
  color: #CCFBF1;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.tf-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 0.5rem 0 1.25rem 0;
}
@media (max-width: 900px) {
  .tf-kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
.tf-kpi {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow);
  min-height: 88px;
}
.tf-kpi .label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 6px;
}
.tf-kpi .value {
  font-family: var(--mono);
  font-size: 1.35rem;
  font-weight: 600;
  color: #F8FAFC;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.tf-kpi .sub {
  margin-top: 4px;
  font-size: 0.75rem;
  color: #5EEAD4;
}
.tf-kpi.accent {
  border-color: rgba(20, 184, 166, 0.45);
  background: linear-gradient(160deg, #151C2C 0%, rgba(15, 118, 110, 0.18) 100%);
}

.tf-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1rem 1.15rem;
  margin-bottom: 1rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.22);
}
.tf-section-title {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 700;
  margin: 0 0 0.65rem 0;
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
}

.tf-info {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 10px;
  padding: 0.75rem 1rem;
  color: #BFDBFE;
  font-size: 0.88rem;
  margin: 0.5rem 0 1rem 0;
}
.tf-footer {
  text-align: center;
  color: var(--text-dim);
  font-size: 0.78rem;
  padding: 1.5rem 0 0.5rem 0;
}
.tf-sidebar-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94A3B8 !important;
  font-weight: 700;
  margin: 1rem 0 0.4rem 0;
}

/* Mejor contraste en captions y placeholders del main */
.stCaption, [data-testid="stCaptionContainer"] {
  color: #CBD5E1 !important;
}
/* No forzar color en todos los span (rompe widgets); solo markdown del main */
.main .stMarkdown p, .main .stMarkdown li {
  color: #E8EEF7 !important;
}
.main [data-testid="stWidgetLabel"] p {
  color: #E2E8F0 !important;
}
/* File uploader — sin botón blanco ilegible */
section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
  background: transparent !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] section,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] > div > div {
  background: #1A2336 !important;
  border: 1px dashed #64748B !important;
  border-radius: 12px !important;
  padding: 0.75rem !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] section *,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] small,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] span,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] p {
  color: #E2E8F0 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] button,
section[data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="baseButton-secondary"] {
  background: #0F766E !important;
  color: #ECFDF5 !important;
  border: 1px solid #14B8A6 !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] button:hover {
  background: #14B8A6 !important;
  color: #042F2E !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] svg {
  fill: #ECFDF5 !important;
  color: #ECFDF5 !important;
}
/* Download / secondary buttons en sidebar */
section[data-testid="stSidebar"] .stDownloadButton > button,
section[data-testid="stSidebar"] .stButton > button {
  background: #1E293B !important;
  color: #F1F5F9 !important;
  border: 1px solid #475569 !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stDownloadButton > button:hover,
section[data-testid="stSidebar"] .stButton > button:hover {
  border-color: #14B8A6 !important;
  color: #5EEAD4 !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
  color: #042F2E !important;
  border: none !important;
}
/* Checkbox label legible */
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label p,
section[data-testid="stSidebar"] [data-testid="stCheckbox"] span {
  color: #E2E8F0 !important;
}


/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
  background: transparent !important;
}

/* Burbujas flotantes (tooltips) en KPIs y callouts */
.tf-kpi {
  position: relative;
  cursor: help;
}
.tf-kpi[data-tip]:hover::after {
  content: attr(data-tip);
  position: absolute;
  left: 50%;
  bottom: calc(100% + 10px);
  transform: translateX(-50%);
  width: min(260px, 70vw);
  background: #0F172A;
  color: #F1F5F9;
  border: 1px solid #14B8A6;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 0.78rem;
  font-weight: 400;
  line-height: 1.35;
  letter-spacing: 0;
  text-transform: none;
  z-index: 100;
  box-shadow: 0 12px 28px rgba(0,0,0,0.45);
  pointer-events: none;
  white-space: normal;
}
.tf-kpi[data-tip]:hover::before {
  content: "";
  position: absolute;
  left: 50%;
  bottom: calc(100% + 4px);
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #14B8A6;
  z-index: 101;
}
.tf-explain {
  background: rgba(20, 184, 166, 0.08);
  border-left: 3px solid #14B8A6;
  border-radius: 0 10px 10px 0;
  padding: 0.65rem 0.9rem;
  margin: 0.5rem 0 1rem 0;
  color: #CCFBF1;
  font-size: 0.86rem;
  line-height: 1.45;
}
.tf-explain b { color: #5EEAD4; }

/* Cinta de tickers */
.tf-tape-wrap {
  overflow: hidden;
  background: #0F172A;
  border: 1px solid #243044;
  border-radius: 12px;
  margin: 0 0 1rem 0;
  position: relative;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}
.tf-tape-wrap::before {
  content: "MERCADO";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  padding: 0 12px;
  background: linear-gradient(90deg, #0F766E 0%, #0F172A 100%);
  color: #ECFDF5;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
}
.tf-tape {
  display: flex;
  gap: 1.75rem;
  width: max-content;
  padding: 0.55rem 1rem 0.55rem 5.5rem;
  animation: tf-scroll 45s linear infinite;
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
  background: #1A2336;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 0.55rem 0.85rem;
  margin: -0.25rem 0 1rem 0;
  color: #CBD5E1;
  font-size: 0.8rem;
  line-height: 1.4;
}
.tf-chart-tip span {
  color: #5EEAD4;
  font-weight: 600;
  margin-right: 6px;
}

/* Tour */
.tf-tour {
  background: linear-gradient(135deg, #134E4A 0%, #0F172A 100%);
  border: 1px solid #14B8A6;
  border-radius: 14px;
  padding: 1rem 1.15rem;
  margin: 0 0 1rem 0;
  color: #ECFDF5;
  font-size: 0.9rem;
  line-height: 1.45;
}
.tf-tour h4 { margin: 0 0 0.4rem 0; color: #5EEAD4; font-size: 1rem; }
.tf-tour ol { margin: 0.4rem 0 0.6rem 1.2rem; padding: 0; }
.tf-tour li { margin: 0.25rem 0; }

/* Semáforo */
.tf-semaforo {
  display: flex;
  gap: 12px;
  align-items: stretch;
  margin: 0.6rem 0 1rem 0;
  flex-wrap: wrap;
}
.tf-sem-card {
  flex: 1;
  min-width: 140px;
  border-radius: 12px;
  padding: 12px 14px;
  border: 1px solid #334155;
  background: #1A2336;
}
.tf-sem-card .dot {
  width: 12px; height: 12px; border-radius: 50%;
  display: inline-block; margin-right: 8px;
  box-shadow: 0 0 8px currentColor;
}
.tf-sem-card.ok { border-color: rgba(52, 211, 153, 0.5); }
.tf-sem-card.ok .dot { background: #34D399; color: #34D399; }
.tf-sem-card.warn { border-color: rgba(251, 191, 36, 0.5); }
.tf-sem-card.warn .dot { background: #FBBF24; color: #FBBF24; }
.tf-sem-card.bad { border-color: rgba(248, 113, 113, 0.5); }
.tf-sem-card.bad .dot { background: #F87171; color: #F87171; }
.tf-sem-card .ttl { font-weight: 600; color: #F1F5F9; font-size: 0.9rem; }
.tf-sem-card .dsc { color: #94A3B8; font-size: 0.78rem; margin-top: 4px; line-height: 1.35; }

/* Analogías */
.tf-analogy {
  background: #1E293B;
  border: 1px dashed #475569;
  border-radius: 10px;
  padding: 0.55rem 0.85rem;
  margin: 0.4rem 0 0.8rem 0;
  color: #E2E8F0;
  font-size: 0.82rem;
}
.tf-analogy em { color: #5EEAD4; font-style: normal; font-weight: 600; }

/* Chips glosario */
.tf-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0.4rem 0; }
.tf-chip {
  background: #1A2336;
  border: 1px solid #334155;
  color: #E2E8F0;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.78rem;
  font-weight: 500;
}
.tf-chip:hover { border-color: #14B8A6; color: #5EEAD4; }

/* Tema claro */
html[data-theme="light"] body,
html[data-theme="light"] [data-testid="stAppViewContainer"] {
  background: #F8FAFC !important;
  color: #0F172A !important;
}


/* Download buttons en el área principal (no solo sidebar) */
.main .stDownloadButton > button {
  background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
  color: #042F2E !important;
  border: none !important;
  font-weight: 700 !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 14px rgba(20, 184, 166, 0.35) !important;
}
.main .stDownloadButton > button:hover {
  background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
  color: #042F2E !important;
}
.tf-ficha-box {
  background: #1A2336;
  border: 1px solid #14B8A6;
  border-radius: 12px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0 1rem 0;
}
.tf-ficha-box .ttl {
  color: #5EEAD4;
  font-weight: 700;
  font-size: 0.85rem;
  margin-bottom: 0.35rem;
}
.tf-ficha-box .dsc {
  color: #CBD5E1;
  font-size: 0.8rem;
  margin-bottom: 0.5rem;
  line-height: 1.4;
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
    """Tabla Plotly con anchos de columna adaptados (evita index enorme y celdas cortadas)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False
    if df is None or not hasattr(df, "columns"):
        return False
    try:
        d = df.copy()
        # Convertir índice en columna compacta
        if not isinstance(d.index, pd.RangeIndex) or d.index.name:
            try:
                name = d.index.name or "Año"
                d = d.reset_index()
                # Renombrar index feo
                if "index" in d.columns:
                    d = d.rename(columns={"index": name if name != "index" else "Año"})
            except Exception:
                pass
        d = d.head(50)
        cols = [str(c) for c in d.columns]

        def _fmt(v, colname):
            if v is None or (isinstance(v, float) and v != v):
                return "—"
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                fv = float(v)
                # años
                if colname.lower() in ("año", "ano", "year", "index") and 1900 <= fv <= 2100 and abs(fv - round(fv)) < 1e-9:
                    return str(int(round(fv)))
                if abs(fv) >= 100:
                    return f"{fv:,.1f}"
                if abs(fv) >= 1:
                    return f"{fv:,.2f}"
                return f"{fv:.4g}"
            return str(v)[:64]

        cell_vals = []
        for c in d.columns:
            cell_vals.append([_fmt(v, str(c)) for v in d[c].tolist()])

        # Anchos: año/index estrecho; texto medio; números proporcionales
        widths = []
        for c, vals in zip(cols, cell_vals):
            cl = c.lower()
            if cl in ("año", "ano", "year", "index", "t", "periodo"):
                widths.append(55)
            elif cl in ("escenario", "nombre", "empresa", "ticker", "prueba", "indicador", "estado"):
                widths.append(140)
            else:
                maxlen = max((len(x) for x in vals), default=6)
                widths.append(int(min(120, max(70, maxlen * 8))))

        n_rows = len(d)
        # Filas alternadas por columna
        fill = []
        for _ in cols:
            fill.append(["#1E293B" if i % 2 == 0 else "#151C2C" for i in range(n_rows)])

        fig = go.Figure(data=[go.Table(
            columnwidth=widths,
            header=dict(
                values=[f"<b>{c}</b>" for c in cols],
                fill_color="#0F766E",
                font=dict(color="#ECFDF5", size=12, family="IBM Plex Sans"),
                align=["center" if str(c).lower() in ("año", "ano", "year") else "left" for c in cols],
                height=34,
            ),
            cells=dict(
                values=cell_vals,
                fill_color=fill,
                font=dict(color="#F1F5F9", size=12, family="IBM Plex Mono"),
                align=["center" if str(c).lower() in ("año", "ano", "year") else "right"
                       if str(c).lower() not in ("escenario", "nombre", "empresa", "prueba", "indicador", "estado")
                       else "left" for c in cols],
                height=28,
            ),
        )])
        fig.update_layout(
            title=dict(text=title, font=dict(size=14, color="#F8FAFC")),
            paper_bgcolor="#0F172A",
            margin=dict(l=8, r=8, t=42, b=8),
            height=min(140 + 30 * n_rows, 560),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        return True
    except Exception as e:
        st.caption(f"Tabla Plotly: {e}")
        return False


def _show_df(df, label=None):
    """Preferir tabla Plotly; respaldo st.dataframe."""
    if df is None:
        return
    title = label or "Datos"
    if _plotly_table(df, title=title):
        return
    if label:
        st.caption(label)
    try:
        st.dataframe(df, use_container_width=True)
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

        # Limitar a 4 paneles para legibilidad
        items = list(series_map.items())[:4]
        n = len(items)
        fig = make_subplots(
            rows=n, cols=1,
            subplot_titles=[f"{k}: original vs normalizado (hover = valor)" for k, _ in items],
            vertical_spacing=0.08 if n > 1 else 0.12,
        )

        for i, (clave, (s, s_n, mask, years)) in enumerate(items, start=1):
            y0 = [float(v) if v == v else None for v in s.tolist()]
            y1 = [float(v) if v == v else None for v in s_n.tolist()] if s_n is not None else y0
            x = years

            fig.add_trace(go.Scatter(
                x=x, y=y0, mode="lines+markers",
                name=f"{clave} original",
                line=dict(color="#38BDF8", width=2.8),
                marker=dict(size=9),
                hovertemplate=f"<b>{clave} original</b><br>Año %{{x}}<br>Valor: %{{y:,.2f}}<extra></extra>",
                legendgroup=clave,
                showlegend=True,
            ), row=i, col=1)

            fig.add_trace(go.Scatter(
                x=x, y=y1, mode="lines+markers+text",
                name=f"{clave} normalizado",
                line=dict(color="#2DD4BF", width=2.8, dash="dash"),
                marker=dict(size=9),
                text=[f"{v:,.0f}" if v is not None and abs(v) >= 10 else (f"{v:.2f}" if v is not None else "") for v in y1],
                textposition="top center",
                textfont=dict(size=9, color="#CCFBF1"),
                hovertemplate=f"<b>{clave} normalizado</b><br>Año %{{x}}<br>Valor: %{{y:,.2f}}<extra></extra>",
                legendgroup=clave,
                showlegend=True,
            ), row=i, col=1)

            # Atípicos
            try:
                msk = mask.tolist() if hasattr(mask, "tolist") else list(mask)
                xa = [x[j] for j, f in enumerate(msk) if f and j < len(x)]
                ya = [y0[j] for j, f in enumerate(msk) if f and j < len(y0)]
                if xa:
                    fig.add_trace(go.Scatter(
                        x=xa, y=ya, mode="markers",
                        name=f"Atípico {clave}",
                        marker=dict(size=14, color="#F87171", symbol="x", line=dict(width=2, color="#FECACA")),
                        hovertemplate=f"<b>Atípico · {clave}</b><br>Año %{{x}}<br>%{{y:,.2f}}<extra></extra>",
                        legendgroup=clave,
                        showlegend=True,
                    ), row=i, col=1)
            except Exception:
                pass

            if x:
                fig.update_xaxes(
                    title_text="Año" if i == n else "",
                    range=[min(x) - 0.4, max(x) + 0.4],
                    dtick=1, tickmode="linear",
                    row=i, col=1,
                )
            fig.update_yaxes(title_text=str(clave)[:18], row=i, col=1)

        fig.update_layout(**_plotly_layout(title, height=max(380, 280 * n)))
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=11, color="#F8FAFC")),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Línea azul = dato original · línea teal punteada = tras filtro Hampel/winsor · "
            "cruz roja = atípico. Pasa el cursor para ver el valor exacto."
        )
        return True
    except Exception as e:
        st.caption(f"Comparación drivers Plotly: {e}")
        return False


# Alias para llamadas antiguas
def _plotly_atipicos(df_hist, title="Comparación de drivers · original vs normalizado"):
    return _plotly_comparacion_drivers(df_hist, title=title)


def _plotly_informe_panel(resultados, title="Resumen gráfico del informe"):
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
                x=xh, y=yh, mode="lines+markers", name="Histórico",
                line=dict(color="#38BDF8", width=2.5), marker=dict(size=7),
                hovertemplate="Hist %{x}: %{y:,.0f}<extra></extra>",
            ), row=1, col=1)
            any_ok = True
        if c_p and df_p is not None:
            xp, yp = _years_from_df(df_p), [float(v) for v in df_p[c_p].values]
            fig.add_trace(go.Scatter(
                x=xp, y=yp, mode="lines+markers", name="Proyectado",
                line=dict(color="#2DD4BF", width=2.5, dash="dash"), marker=dict(size=7),
                hovertemplate="Proy %{x}: %{y:,.0f}<extra></extra>",
            ), row=1, col=1)
            xs = (xh or []) + (xp or [])
            if xs:
                fig.update_xaxes(range=[min(xs) - 0.4, max(xs) + 0.4], dtick=1, row=1, col=1)
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
                    hovertemplate="EV %{x}: %{y:,.0f}<extra></extra>"), row=1, col=2)
                any_ok = True
            elif "equity" in cl:
                y = pd.to_numeric(df[c], errors="coerce").fillna(0).tolist()
                fig.add_trace(go.Bar(name="Equity", x=x, y=y, marker_color="#38BDF8",
                    text=[f"{v:,.0f}" for v in y], textposition="outside",
                    hovertemplate="Equity %{x}: %{y:,.0f}<extra></extra>"), row=1, col=2)
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
                hovertemplate="%{x}: %{y:,.0f}<extra></extra>"), row=2, col=1)
            any_ok = True
    if t6 and isinstance(t6, (list, tuple)) and len(t6) > 1 and hasattr(t6[1], "columns"):
        df = t6[1]
        name_c = next((c for c in df.columns if str(c).lower() in ("nombre", "empresa", "ticker")), df.columns[0])
        num_c = None
        for c in df.columns:
            if c == name_c:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                num_c = c
                break
            try:
                pd.to_numeric(df[c], errors="raise")
                num_c = c
                break
            except Exception:
                continue
        if num_c is not None:
            labels = df[name_c].astype(str).str.slice(0, 22).tolist()[:12]
            yv = pd.to_numeric(df[num_c], errors="coerce").fillna(0).tolist()[:12]
            fig.add_trace(go.Bar(name=str(num_c)[:20], y=labels, x=yv, orientation="h",
                marker_color="#14B8A6",
                hovertemplate="<b>%{y}</b><br>%{x:.2f}<extra></extra>"), row=2, col=2)
            any_ok = True
    if not any_ok:
        return False
    fig.update_layout(**_plotly_layout(title, height=720))
    fig.update_layout(barmode="group", showlegend=True, legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Ejecuta antes las pestañas 1, 2, 5 y 6 para llenar los cuatro paneles. Hover para ver valores.")
    return True


def _plotly_layout(title="", height=520):
    return dict(
        title=dict(text=title, font=dict(size=16, color="#F8FAFC"), x=0.01),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#1E293B",
        font=dict(color="#F1F5F9", size=13, family="IBM Plex Sans, system-ui, sans-serif"),
        margin=dict(l=60, r=40, t=60, b=60),
        height=height,
        legend=dict(
            bgcolor="rgba(15,23,42,0.95)",
            bordercolor="#64748B",
            borderwidth=1,
            font=dict(size=12, color="#F8FAFC"),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#0F172A", bordercolor="#14B8A6", font=dict(size=13, color="#F8FAFC")),
        xaxis=dict(
            gridcolor="#475569",
            tickfont=dict(size=12, color="#E2E8F0"),
            title_font=dict(size=13, color="#F1F5F9"),
            color="#E2E8F0",
            automargin=True,
        ),
        yaxis=dict(
            gridcolor="#475569",
            tickfont=dict(size=12, color="#E2E8F0"),
            title_font=dict(size=13, color="#F1F5F9"),
            color="#E2E8F0",
            automargin=True,
            zeroline=True,
            zerolinecolor="#64748B",
        ),
    )


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
            hovertemplate="<b>Histórico</b><br>Año %{x}<br>FCFF: %{y:,.1f}<extra></extra>",
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
            hovertemplate="<b>Proyectado</b><br>Año %{x}<br>FCFF: %{y:,.1f}<extra></extra>",
        ))

    if not years_all:
        return False

    y0, y1 = min(years_all), max(years_all)
    fig.update_layout(**_plotly_layout(title, height=540))
    fig.update_xaxes(
        title="Año",
        range=[y0 - 0.4, y1 + 0.4],
        dtick=1,
        tickmode="linear",
        autorange=False,
    )
    fig.update_yaxes(title="FCFF (miles de millones)")
    st.plotly_chart(fig, use_container_width=True)
    return True


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
            hovertemplate="<b>%{x}</b><br>EV: %{y:,.1f}<extra></extra>",
        ))
    if eq_c is not None:
        yeq = pd.to_numeric(df[eq_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            name="Equity (dueños)", x=x, y=yeq,
            marker_color="#38BDF8",
            text=[f"{v:,.0f}" for v in yeq],
            textposition="outside",
            textfont=dict(size=12, color="#F8FAFC"),
            hovertemplate="<b>%{x}</b><br>Equity: %{y:,.1f}<extra></extra>",
        ))
    if not fig.data:
        return False
    fig.update_layout(**_plotly_layout("Escenarios · EV vs Equity", height=480))
    fig.update_layout(barmode="group", uniformtext_minsize=10, uniformtext_mode="hide")
    fig.update_xaxes(title="Escenario")
    fig.update_yaxes(title="Valor (miles de millones)")
    st.plotly_chart(fig, use_container_width=True)
    return True


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
        hovertemplate="<b>%{x}</b><br>Flujo: %{y:,.1f}<extra></extra>",
        name="Flujos",
    ))
    fig.update_layout(**_plotly_layout("Flujos del proyecto · VPN / recuperación", height=480))
    fig.add_hline(y=0, line_color="#94A3B8", line_width=1, line_dash="dot")
    fig.update_xaxes(title="Periodo")
    fig.update_yaxes(title="Flujo / VPN")
    st.plotly_chart(fig, use_container_width=True)
    return True


def _plotly_sector(df):
    """Ranking sectorial horizontal con hover."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return False
    if df is None or not hasattr(df, "columns") or len(df) == 0:
        return False
    name_c = next((c for c in df.columns if str(c).lower() in ("nombre", "empresa", "ticker", "emisor")), df.columns[0])
    labels = df[name_c].astype(str).str.slice(0, 28).tolist()
    margen_c = next((c for c in df.columns if "margen" in str(c).lower()), None)
    mult_c = next((c for c in df.columns if "ev/ebitda" in str(c).lower() or "múltiplo" in str(c).lower() or "multiplo" in str(c).lower()), None)
    score_c = next((c for c in df.columns if "score" in str(c).lower() or "puntaje" in str(c).lower() or "ranking" in str(c).lower()), None)

    if score_c is not None and margen_c is None and mult_c is None:
        yv = pd.to_numeric(df[score_c], errors="coerce").fillna(0).tolist()
        fig = go.Figure(go.Bar(
            y=labels, x=yv, orientation="h",
            marker_color="#14B8A6",
            text=[f"{v:.2f}" for v in yv],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Score: %{x:.2f}<extra></extra>",
        ))
        fig.update_layout(**_plotly_layout("Ranking sectorial", height=max(400, 40 * len(labels) + 120)))
        fig.update_xaxes(title="Score")
        st.plotly_chart(fig, use_container_width=True)
        return True

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Margen EBITDA %", "EV/EBITDA (x)"))
    if margen_c is not None:
        ym = pd.to_numeric(df[margen_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            y=labels, x=ym, orientation="h", marker_color="#14B8A6", name="Margen",
            text=[f"{v:.1f}" for v in ym], textposition="outside",
            hovertemplate="<b>%{y}</b><br>Margen: %{x:.1f}%<extra></extra>",
        ), row=1, col=1)
    if mult_c is not None:
        yx = pd.to_numeric(df[mult_c], errors="coerce").fillna(0).tolist()
        fig.add_trace(go.Bar(
            y=labels, x=yx, orientation="h", marker_color="#38BDF8", name="Múltiplo",
            text=[f"{v:.1f}x" for v in yx], textposition="outside",
            hovertemplate="<b>%{y}</b><br>EV/EBITDA: %{x:.1f}x<extra></extra>",
        ), row=1, col=2)
    if not fig.data:
        return False
    fig.update_layout(**_plotly_layout("Comparables del sector", height=max(420, 36 * len(labels) + 140)))
    fig.update_layout(showlegend=False)
    fig.update_xaxes(gridcolor="#475569")
    fig.update_yaxes(gridcolor="#475569")
    st.plotly_chart(fig, use_container_width=True)
    return True


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
    """Cinta de mercado: tickers globales + Colombia. Cache 5 min."""
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

    for sym, name in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if hist is None or len(hist) < 2:
                info = getattr(t, "info", {}) or {}
                px = info.get("regularMarketPrice") or info.get("currentPrice")
                chg = info.get("regularMarketChangePercent")
                rows.append({"sym": sym.split(".")[0], "name": name, "px": px, "chg": chg})
                continue
            px = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            chg = 100.0 * (px - prev) / prev if prev else 0.0
            rows.append({"sym": sym.split(".")[0], "name": name, "px": px, "chg": chg})
        except Exception:
            rows.append({"sym": sym.split(".")[0], "name": name, "px": None, "chg": None})
    return rows


def _render_market_tape() -> None:
    data = _market_tape_quotes()
    parts = []
    for d in data:
        chg = d.get("chg")
        px = d.get("px")
        if chg is None:
            cls, chg_txt = "tf-flat", "—"
        elif chg > 0.05:
            cls, chg_txt = "tf-up", f"+{chg:.2f}%"
        elif chg < -0.05:
            cls, chg_txt = "tf-down", f"{chg:.2f}%"
        else:
            cls, chg_txt = "tf-flat", f"{chg:.2f}%"
        px_txt = f"{px:,.2f}" if isinstance(px, (int, float)) else "—"
        parts.append(
            f'<span class="tf-tick"><b>{d["sym"]}</b> {d["name"]} '
            f'{px_txt} <span class="{cls}">{chg_txt}</span></span>'
        )
    # Duplicar para loop infinito suave
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


def _ficha_una_pagina(empresa, moneda, w, g, horizonte, sector, resultados):
    """Texto plano didáctico para descargar."""
    lines = [
        f"FICHA RÁPIDA (1 página) — {empresa}",
        f"Moneda del modelo: {moneda} · Sector: {sector}",
        f"WACC: {w['wacc']*100:.2f}% · Ke: {w['ke']*100:.2f}% · βL: {w['beta_l']:.2f}",
        f"g terminal: {g*100:.2f}% · Horizonte: {horizonte} años",
        "",
        "EN PALABRAS SIMPLES",
        f"- WACC: {ANALOGIAS['WACC']}",
        f"- FCFF: {ANALOGIAS['FCFF']}",
        f"- Equity: {ANALOGIAS['Equity']}",
        "",
        "QUÉ HACER AHORA",
        "1) Genera el Pronóstico (pestaña 1).",
        "2) Mira Escenarios (pestaña 2): ¿el equity se mantiene en el caso pesimista?",
        "3) Revisa el semáforo de Auditoría (pestaña 3).",
        "4) Lee la Recomendación (pestaña 4) sin tomarla como orden de compra.",
        "",
        "Aviso: herramienta pedagógica. No es asesoría de inversión.",
    ]
    return "\n".join(lines)



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
            if len(out) > 15:
                st.session_state["rf"] = out[15]
            if len(out) > 16:
                st.session_state["erp"] = out[16]
            if len(out) > 17:
                st.session_state["crp"] = out[17]
            if len(out) > 18:
                st.session_state["g_max_macro"] = out[18]
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
    p = emp.get("params", {})
    st.session_state["params"] = dict(p)
    st.session_state["ficha_html"] = f"<b>{nombre}</b> · {emp.get('sector', '')}"
    mon = p.get("moneda") or emp.get("moneda") or "COP"
    st.session_state["rf"] = 0.12 if mon == "COP" else 0.04


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
    try:
        if hasattr(L, "calcular_wacc"):
            return L.calcular_wacc(de_ratio, kd, tax, beta_u, rf=rf, erp=erp, crp=crp)
    except Exception:
        pass
    de = max(float(de_ratio), 0.0)
    we = 1.0 / (1.0 + de)
    wd = de / (1.0 + de)
    beta_l = float(beta_u) * (1.0 + (1.0 - float(tax)) * de)
    ke = float(rf) + beta_l * float(erp) + float(crp)
    wacc = we * ke + wd * float(kd) * (1.0 - float(tax))
    return {"wacc": wacc, "ke": ke, "beta_l": beta_l}


# =============================================================================
# MAIN
# =============================================================================
def main():
    _init_state()

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
                    st.session_state["empresa_sel"] = display_name
                    st.session_state["select_empresa"] = display_name
                    if params_tuple and len(params_tuple) >= 14:
                        keys = [
                            "de_ratio", "kd", "tax", "g", "beta_u",
                            "capital_invertido", "deuda_neta", "inversion_inicial",
                            "caja", "nci", "otros_claims", "asociados",
                            "acciones", "exit_multiple",
                        ]
                        st.session_state["params"] = {k: params_tuple[i] for i, k in enumerate(keys)}
                    _cargar_params_empresa(display_name)
                    st.session_state["resultados"] = {}
                    st.success("Cargada")
                    st.rerun()
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
            acciones = st.number_input(
                "Acciones (M)", value=float(p.get("acciones") or 0), step=1.0, key=f"acc_{ek}"
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

    w = _wacc_quick(de_ratio, kd, tax, beta_u, rf, erp, crp)
    moneda = (st.session_state.get("params") or {}).get("moneda", "COP")
    try:
        emp_obj = L.resolver_empresa(empresa) if hasattr(L, "resolver_empresa") else None
        if emp_obj:
            moneda = emp_obj.get("params", {}).get("moneda") or emp_obj.get("moneda") or moneda
            sector = emp_obj.get("sector", "—")
        else:
            sector = "—"
    except Exception:
        sector = "—"

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

    st.markdown(
        f'<div class="tf-info"><b>{empresa}</b> · modelo en <b>{moneda}</b> '
        f"(miles de millones). Calibra supuestos antes de interpretar.</div>",
        unsafe_allow_html=True,
    )

    # Semáforo en vivo (supuestos) + ficha 1 página
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

    ficha_txt = _ficha_una_pagina(empresa, moneda, w, g, horizonte, sector, st.session_state.get("resultados") or {})
    st.markdown(
        '<div class="tf-ficha-box">'
        '<div class="ttl">📄 Ficha simple (1 página)</div>'
        '<div class="dsc">Resumen en lenguaje cotidiano para compartir con alguien no financiero. '
        'No reemplaza el informe PDF de la pestaña 7: es un “elevator pitch” del caso.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.download_button(
        "Descargar ficha simple (.txt)",
        data=ficha_txt.encode("utf-8"),
        file_name=f"ficha_{empresa.split('—')[0].strip().replace(' ', '_')[:24]}.txt",
        mime="text/plain",
        key="dl_ficha",
        type="primary",
        use_container_width=False,
    )

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
            with st.expander("Glosario completo (técnico)", expanded=False):
                try:
                    _html(L.glosario_html())
                except Exception:
                    st.caption("FCFF · WACC · ROIC · EV · Equity · VPN · TIR · g · Beta")

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
                    key_eff = _resolve_gemini_key(ckey) if (cprov or "gemini") == "gemini" else (ckey or None)
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

    # ----- 7 TABS -----
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
        metodo = st.radio(
            "Método",
            [
                "Drivers + identidad FCFF (recomendado)",
                "ETS / Holt (suavizado exponencial)",
                "ARIMA (benchmark estadístico)",
            ],
            horizontal=True,
            label_visibility="collapsed",
        )
        if st.button("Generar proyección y Fan Chart", type="primary", key="btn1"):
            with st.spinner("Proyectando…"):
                try:
                    st.session_state["resultados"]["tab1"] = L.tab1_carga_y_pronostico(
                        empresa, archivo, horizonte, metodo, tax, usar_publicos
                    )
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
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
            if len(r) > 5 and r[5]:
                _html(r[5])
            _chart_tip(
                "La zona sombreada es el rango probable del dinero libre (FCFF). "
                "La línea del medio es el caso más típico. Si el pasado queda muy fuera, revisa si hubo un año raro."
            )
            _explain(
                "<b>En palabras simples:</b> el FCFF es el efectivo que queda después de operar e invertir. "
                "Proyectarlo es imaginar cuánto efectivo generará la empresa en los próximos años. "
                "El fan chart muestra incertidumbre: no es una sola cifra, sino un rango."
            )

    with tab2:
        st.markdown("##### Escenarios pesimista · base · optimista")
        if st.button("Simular escenarios", type="primary", key="btn2"):
            with st.spinner("Simulando…"):
                try:
                    st.session_state["resultados"]["tab2"] = L.tab2_simulacion_politicas(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        deuda_neta, rf, erp, crp, usar_publicos,
                        caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                    )
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
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
                "Barras altas de Equity = más valor para el accionista en ese escenario. "
                "Si Equity es bajo o negativo, la deuda y otros pasivos pesan mucho."
            )
            _explain(
                "<b>En palabras simples:</b> el modelo pregunta “¿cuánto valdría la empresa si el futuro va mal, normal o bien?”. "
                "<b>EV</b> es el valor de todo el negocio; <b>Equity</b> es lo que queda para los dueños después de restar deudas. "
                "Úsalo para ver si el resultado es robusto o solo se sostiene en el caso optimista."
            )

    with tab3:
        st.markdown("##### Coherencia de supuestos")
        if st.button("Ejecutar auditoría", type="primary", key="btn3"):
            with st.spinner("Auditando…"):
                try:
                    st.session_state["resultados"]["tab3"] = L.tab3_auditoria_teorica(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, beta_u,
                        capital_invertido, rf, erp, crp, usar_publicos,
                    )
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
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
        if st.button("Generar recomendación", type="primary", key="btn4"):
            with st.spinner("Generando…"):
                try:
                    st.session_state["resultados"]["tab4"] = L.tab4_recomendacion(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        capital_invertido, deuda_neta, rf, erp, crp, usar_publicos,
                        caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                    )
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
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
            # Semáforo de gobernanza rápido
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

    with tab5:
        st.markdown("##### VPN · TIR · Payback")
        if st.button("Calcular proyecto", type="primary", key="btn5"):
            with st.spinner("Calculando…"):
                try:
                    st.session_state["resultados"]["tab5"] = L.tab5_vpn_tir(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        inversion_inicial, rf, erp, crp, usar_publicos,
                    )
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
        r = st.session_state.get("resultados", {}).get("tab5")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Flujos")
                if not _plotly_vpn_flows(r[1]):
                    if len(r) > 2:
                        _show_fig(r[2], "Recuperación")
            elif len(r) > 2:
                _show_fig(r[2], "Recuperación")
            _chart_tip(
                "Barras verdes = dinero que entra; rojas = inversión inicial. "
                "El payback es cuándo se recupera lo invertido (sin medir si ‘valía la pena’ del todo)."
            )
            _explain(
                "<b>En palabras simples:</b> <b>VPN &gt; 0</b> significa que el proyecto deja más de lo que ‘cuesta’ el capital. "
                "La <b>TIR</b> es la rentabilidad implícita del proyecto. El <b>payback</b> solo dice en cuántos años recuperas la plata, "
                "no si el riesgo valía la pena."
            )

    with tab6:
        st.markdown("##### Ranking sectorial")
        if st.button("Generar ranking", type="primary", key="btn6"):
            with st.spinner("Comparando…"):
                try:
                    st.session_state["resultados"]["tab6"] = L.tab6_comparacion_sectorial(empresa)
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
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
                "Compara márgenes y múltiplos con empresas del mismo oficio. "
                "Un múltiplo muy bajo puede ser oportunidad… o una señal de problemas."
            )
            _explain(
                "<b>En palabras simples:</b> aquí no se mira la empresa sola, sino frente a ‘vecinas’ del sector. "
                "Si gana más por cada peso invertido (ROIC) que lo que cuesta el capital (WACC), suele crear valor. "
                "Pasa el cursor por los KPIs de arriba para ver definiciones rápidas."
            )

    with tab7:
        st.markdown("##### Informe ejecutivo")
        st.caption(
            "En pantalla el panel usa el gráfico generado por el modelo. "
            "Las pestañas 1–6 tienen gráficos Plotly con hover, nombres y valores. "
            "El PDF sigue siendo estático (con títulos y cifras anotadas)."
        )
        if st.button("Generar informe y PDF", type="primary", key="btn7"):
            with st.spinner("Informe…"):
                try:
                    st.session_state["resultados"]["tab7"] = L.tab7_informe_ejecutivo(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        capital_invertido, deuda_neta, inversion_inicial, rf, erp, crp, usar_publicos,
                        caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                    )
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
        r = st.session_state.get("resultados", {}).get("tab7")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "KPIs del informe")
            # Panel resumen en Plotly (misma estética); requiere corridas previas
            if not _plotly_informe_panel(st.session_state.get("resultados") or {}, title="Resumen gráfico · informe"):
                if len(r) > 2:
                    _show_fig(r[2], "Panel (respaldo estático)")
            if len(r) > 3 and r[3]:
                pdf_path = r[3]
                if isinstance(pdf_path, str) and os.path.isfile(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "Descargar PDF",
                            f,
                            file_name=f"informe_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            type="primary",
                        )

    st.markdown(
        '<div class="tf-footer">Herramienta pedagógica · Catálogo / Yahoo Finance · '
        "No es feed oficial BVC ni asesoría de inversión</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
