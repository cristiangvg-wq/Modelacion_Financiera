"""
Modelación Financiera · Terminal — Streamlit UI (FinTech Dark)
Lógica de negocio: modelacion_logic.py (intacta).
UI: terminal financiera inmersiva · apoyo a decisión · no es asesoría de inversión.
"""
from __future__ import annotations

import os
import hashlib
import json
import traceback
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

import importlib

import modelacion_logic as L
import portfolio_engine as _portfolio_engine_mod

# Streamlit (y Streamlit Cloud tras un `git pull`) vuelve a ejecutar este script
# SIN reiniciar el proceso: los módulos importados quedan en caché con su versión
# anterior. Si la capa lógica en memoria no tiene la API que este archivo espera,
# se recarga desde disco; así un despliegue nuevo nunca mezcla UI nueva con
# lógica vieja (AttributeError: 'vincular_estado_sesion').
_API_LOGICA_REQUERIDA = (
    "vincular_estado_sesion", "instantanea_precio_mercado",
    "metricas_valoracion_sesion", "limpiar_cache_mercado",
)
if not all(hasattr(L, n) for n in _API_LOGICA_REQUERIDA):
    L = importlib.reload(L)
if not hasattr(_portfolio_engine_mod, "convertir_a_moneda_comun"):
    importlib.reload(_portfolio_engine_mod)

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
    initial_sidebar_state="expanded",  # con "auto" el menú quedó superpuesto al contenido en la prueba de escritorio
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
/* Responsivo: las variantes cols-3/cols-2 tienen más especificidad que la media query
   anterior y mantenían 3 columnas en tablet/móvil (cifras cortadas). */
@media (max-width: 960px) {
  .tf-metrics-row.cols-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
  .tf-metrics-row, .tf-metrics-row.cols-3, .tf-metrics-row.cols-2,
  .tf-kpi-grid { grid-template-columns: minmax(0, 1fr) !important; }
  .tf-metric-tip .m-value, .tf-kpi .value { font-size: 1.15rem; }
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

.tf-manual {
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.22) 0%, rgba(15, 23, 42, 0.9) 100%);
  border: 1px solid rgba(45, 212, 191, 0.55);
  border-radius: 14px;
  padding: 0.85rem 1.1rem;
  color: #ECFDF5;
  font-size: 0.92rem;
  line-height: 1.45;
}
.tf-manual b { color: #99F6E4; }
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

/* Plotly container breathing room. Sin overflow:hidden: recortaba etiquetas de hover,
   la barra de herramientas y leyendas de varias líneas en anchos medios. */
.stPlotlyChart, [data-testid="stPlotlyChart"] {
  border-radius: 14px;
  overflow: visible;
  margin: 0.35rem 0 0.85rem 0 !important;
}
.stPlotlyChart .js-plotly-plot, [data-testid="stPlotlyChart"] .js-plotly-plot { max-width: 100%; }

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
/* Utilidades para tablas HTML con cifras (más específicas que las reglas generales de arriba):
   sin cortes dentro de números ni ids, cifras a la derecha, ancho de columnas fijo cuando se pide. */
.section-card table.tf-fija, .html-container table.tf-fija { table-layout: fixed !important; }
.section-card table th.tf-num, .section-card table td.tf-num,
.html-container table th.tf-num, .html-container table td.tf-num {
  text-align: right !important; white-space: nowrap !important; word-break: normal !important;
  font-variant-numeric: tabular-nums;
}
.section-card table th.tf-centro, .section-card table td.tf-centro,
.html-container table th.tf-centro, .html-container table td.tf-centro {
  text-align: center !important; white-space: nowrap !important; word-break: normal !important;
}
.section-card table th.tf-nowrap, .section-card table td.tf-nowrap,
.html-container table th.tf-nowrap, .html-container table td.tf-nowrap {
  white-space: nowrap !important; word-break: normal !important;
}
.section-card table td.tf-texto, .html-container table td.tf-texto { word-break: normal !important; overflow-wrap: anywhere; }
.section-card table tr.tf-total td, .html-container table tr.tf-total td {
  border-top: 2px solid #14B8A6 !important; font-weight: 800 !important;
}
/* Móvil: las columnas de cifras pasan a un renglón bajo el nombre (sin desplazamiento horizontal). */
.tf-solo-movil { display: none; }
@media (max-width: 640px) {
  .section-card table .tf-movil-oculto, .html-container table .tf-movil-oculto { display: none !important; }
  .section-card table.tf-fija, .html-container table.tf-fija { table-layout: auto !important; min-width: 0 !important; }
  .tf-solo-movil { display: block; }
}
/* st.dataframe: se respeta la alineación nativa (texto izquierda, cifras derecha). */

/* --- Auditoría UI/UX: lectura ejecutiva y alineación --- */
/* Texto largo siempre a la izquierda, con medida de línea legible */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stCaptionContainer"],
.section-card, .result-note, .tf-info {
  text-align: left !important;
  hyphens: manual;
}
.section-card p, .result-note p { max-width: 110ch; }
/* KPI: igual altura por fila, cifras sin recorte */
.tf-kpi-grid { align-items: stretch; }
.tf-kpi { display: flex; flex-direction: column; justify-content: space-between; }
.tf-kpi .value, [data-testid="stMetricValue"] > div {
  overflow-wrap: anywhere;
  white-space: normal !important;
  font-variant-numeric: tabular-nums;
}
[data-testid="stMetricLabel"] p { white-space: normal !important; }
/* Pestañas: no truncar etiquetas en anchos medios */
[data-baseweb="tab-list"] { flex-wrap: wrap; row-gap: 4px; }
[data-baseweb="tab"] p { white-space: nowrap; }
/* Cifras de tablas con dígitos tabulares para comparar columnas */
.section-card table td, [data-testid="stDataFrame"] td { font-variant-numeric: tabular-nums; }
/* Botones de una fila con la misma altura */
.stButton > button { min-height: 2.6rem; }

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
            # Texto largo: soft-wrap en CUALQUIER columna. Antes solo las columnas
            # «de texto» se partían en líneas; en columnas mixtas (p. ej. «Valor» del
            # comité con la fuente financiera) el texto quedaba cortado en la celda.
            max_chars = 320
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            if len(text) > 48:
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
            elif any("<br>" in x for x in vals):
                # Columna mixta con textos largos (ya partidos en líneas de ≤48 caracteres)
                widths.append(260)
            else:
                plain_lens = [len(x.replace("<br>", " ")) for x in vals]
                maxlen = max(plain_lens + [len(c)], default=6)
                widths.append(int(min(140, max(72, maxlen * 8))))

        n_rows = len(d)
        fill = []
        for _ in cols:
            fill.append(["#1E293B" if i % 2 == 0 else "#151C2C" for i in range(n_rows)])

        # Alineación: texto/descripciones a la izquierda; cifras financieras a la
        # derecha para que unidades, miles y decimales queden en columna.
        import re as _re
        _num_re = _re.compile(r"^[\s(+\-−$€£]*[\d.,]+\s*(%|x|×|pp|p\.p\.|COP|USD|M|B)?\)?\s*$", _re.I)

        def _col_numerica(colname, vals):
            if _is_text_col(colname) or _is_year_col(colname):
                return False
            llenos = [v for v in vals if v not in ("—", "")]
            if not llenos:
                return False
            num = sum(1 for v in llenos if _num_re.match(str(v).replace("<br>", " ")))
            return num / len(llenos) >= 0.6

        aligns = ["right" if _col_numerica(c, v) else "left" for c, v in zip(cols, cell_vals)]

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
            # Altura según líneas reales de cada fila: con celdas partidas en varias
            # líneas, una altura fija recortaba las últimas filas de la tabla.
            height=min(48 + header_h + sum(
                max(cell_h, 10 + 18 * max(str(col[i]).count("<br>") + 1 for col in cell_vals))
                for i in range(n_rows)
            ), 900),
        )
        if title:
            st.markdown(
                f'<div class="tf-section-title" style="margin:0.35rem 0 0.5rem 0">{title}</div>',
                unsafe_allow_html=True,
            )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        return True
    except Exception as e:
        st.caption(f"Tabla: {e}")
        return False



def _fmt_celda_num(v):
    """Formato numérico legible para st.dataframe (mismo criterio que la tabla Plotly)."""
    try:
        if v is None or (isinstance(v, float) and (v != v or np.isinf(v))):
            return "—"
        if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
            fv = float(v)
            if abs(fv) >= 100:
                return f"{fv:,.1f}"
            if abs(fv) >= 1:
                return f"{fv:,.2f}"
            return f"{fv:.4g}"
    except Exception:
        pass
    return v


def _tabla_ancha(df, max_cols=7):
    """Una go.Table de Plotly no tiene scroll horizontal: con muchas columnas las
    comprime y los encabezados se solapan (proyección de 10 columnas en móvil).
    Esas tablas se muestran con st.dataframe (scroll, orden y anchos nativos)."""
    try:
        return df is not None and hasattr(df, "columns") and len(df.columns) + (
            0 if isinstance(df.index, pd.RangeIndex) else 1) > max_cols
    except Exception:
        return False


def _dataframe_formateado(df):
    d = df.copy()
    years_idx = False
    try:
        years_idx = (not isinstance(d.index, pd.RangeIndex)) and all(
            1900 <= int(x) <= 2100 for x in d.index)
    except Exception:
        years_idx = False
    if years_idx:
        d.index = [str(int(x)) for x in d.index]
    num_cols = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
    altura = min(38 + 35 * (len(d) + 1), 620)
    try:
        sty = d.style.format(_fmt_celda_num, subset=num_cols) if num_cols else d.style
        st.dataframe(sty, width="stretch", hide_index=not years_idx and isinstance(df.index, pd.RangeIndex),
                     height=altura)
    except Exception:
        # Styler falla con columnas duplicadas o tipos mixtos: mostrar sin formato antes que nada.
        st.dataframe(d, width="stretch", height=altura)


def _show_df(df, label=None, csv_key=None):
    """Tabla Plotly para tablas estrechas/textuales; st.dataframe para tablas anchas
    (scroll horizontal, sin solapamiento). CSV opcional."""
    if df is None:
        return
    title = label or "Datos"
    if _tabla_ancha(df):
        st.markdown(
            f'<div class="tf-section-title" style="margin:0.35rem 0 0.5rem 0">{title}</div>',
            unsafe_allow_html=True,
        )
        _dataframe_formateado(df)
    elif _plotly_table(df, title=title):
        pass
    else:
        if label:
            st.markdown(
                f'<div class="tf-section-title" style="margin:0.35rem 0 0.5rem 0">{title}</div>',
                unsafe_allow_html=True,
            )
        try:
            st.dataframe(df, width="stretch", hide_index=True)
        except TypeError:
            try:
                st.dataframe(df, width="stretch")
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
                width="content",
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
                    msg = "Respaldo curado del catálogo (Yahoo no disponible)"
        except Exception:
            pass
        detalle_fuente = ""
        try:
            est = L.estado_fuente_empresa(empresa) if hasattr(L, "estado_fuente_empresa") else None
            if est and archivo is None:
                detalle_fuente = f" {est.get('detalle', '')}"
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
            f'<b>Calidad de datos · {nivel}</b> — {fuente}.{detalle_fuente} '
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
        st.plotly_chart(fig, width="stretch", key=key)
    else:
        st.plotly_chart(fig, width="stretch")
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


def _liberar_figuras(obj, _prof=0):
    """Desregistra de pyplot las figuras Matplotlib devueltas por las pestañas.

    Las funciones de lógica crean figuras con plt.subplots() (respaldo estático) que
    la UI casi nunca muestra porque usa Plotly nativo; nunca se llamaba plt.close y
    quedaban en el gestor GLOBAL de pyplot, compartido por todas las sesiones del
    proceso: ~6 figuras por «Generar todo» y por usuario hasta reiniciar el contenedor
    (aviso «More than 20 figures have been opened»). plt.close solo las quita del
    gestor: el objeto Figure sigue siendo válido para st.pyplot en el respaldo.
    """
    if not HAS_MPL or obj is None or _prof > 3:
        return
    try:
        from matplotlib.figure import Figure as _Fig
    except Exception:
        return
    if isinstance(obj, _Fig):
        try:
            plt.close(obj)
        except Exception:
            pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _liberar_figuras(v, _prof + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _liberar_figuras(v, _prof + 1)


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


_TAPE_SYMBOLS = [
    ("COP=X", "USD/COP", "COP"),
    ("SPY", "S&P 500", "USD"),
    ("AAPL", "Apple", "USD"),
    ("MSFT", "Microsoft", "USD"),
    ("NVDA", "NVIDIA", "USD"),
    ("GOOGL", "Alphabet", "USD"),
    ("AMZN", "Amazon", "USD"),
    ("JPM", "JPMorgan", "USD"),
    ("ECOPETROL.CL", "Ecopetrol", "COP"),
    ("ISA.CL", "ISA", "COP"),
    ("PFBCOLOM.CL", "Bancolombia pref.", "COP"),
    ("EC", "Ecopetrol ADR", "USD"),
    ("CIB", "Bancolombia ADR", "USD"),
]


def _cierres_desde_download(df, symbols):
    """Extrae columnas Close de yf.download para varios tickers (MultiIndex o plano)."""
    if df is None or getattr(df, "empty", True):
        return {}
    out = {}
    cols = df.columns
    if isinstance(cols, pd.MultiIndex):
        lvl0 = set(cols.get_level_values(0))
        for sym in symbols:
            try:
                ser = df["Close"][sym] if "Close" in lvl0 else df[sym]["Close"]
                out[sym] = pd.to_numeric(ser, errors="coerce").dropna()
            except Exception:
                continue
    elif "Close" in cols and len(symbols) == 1:
        out[symbols[0]] = pd.to_numeric(df["Close"], errors="coerce").dropna()
    return out


def _reiniciar_si_cambia_defecto(key, defecto, extras=()):
    """Si cambió el valor de referencia del control (nuevos datos de la empresa), volver a él.

    El control guarda su valor en session_state y no vuelve a leer el valor por defecto: si los
    parámetros de la empresa se recargan (Yahoo incompleto y luego completo, otro Excel, nueva
    búsqueda), la barra seguía con el dato viejo. Las ediciones del usuario se conservan mientras
    la referencia no cambie.
    """
    k_def = f"{key}__def"
    previo = st.session_state.get(k_def)
    if previo is not None and abs(float(previo) - float(defecto)) > 1e-12:
        for k in (key,) + tuple(extras):
            st.session_state.pop(k, None)
    st.session_state[k_def] = float(defecto)


def _numero_empresa(label, defecto, paso, key, **kw):
    """number_input de un parámetro de la empresa que sigue a su valor de referencia (ver arriba)."""
    defecto = float(defecto or 0)
    _reiniciar_si_cambia_defecto(key, defecto)
    if key not in st.session_state:
        st.session_state[key] = defecto
    return st.number_input(label, step=float(paso), key=key, **kw)


def _slider_y_caja(label, minimo, maximo, defecto, paso, key, formato="%.4f", help=None, paso_caja=None):
    """Barra + casilla para escribir el valor exacto (la barra solo muestra 2 decimales y salta de a «paso»).

    La casilla manda: el modelo usa su valor exacto; la barra se mueve al punto más cercano de su rejilla.
    Ambas se sincronizan por callbacks, sin depender del orden de ejecución.
    """
    minimo, maximo = float(minimo), float(maximo)
    k_caja = f"{key}__caja"
    defecto = min(max(float(defecto), minimo), maximo)
    _reiniciar_si_cambia_defecto(key, defecto, (k_caja,))
    if key not in st.session_state:
        st.session_state[key] = defecto
    if k_caja not in st.session_state:
        st.session_state[k_caja] = float(st.session_state[key])

    def _desde_barra():
        st.session_state[k_caja] = float(st.session_state[key])

    def _desde_caja():
        v = st.session_state.get(k_caja)
        v = minimo if v is None else min(max(float(v), minimo), maximo)
        st.session_state[k_caja] = v
        st.session_state[key] = min(max(round(round(v / paso) * paso, 10), minimo), maximo)

    c_barra, c_caja = st.columns([3, 2], vertical_alignment="bottom")
    with c_barra:
        st.slider(label, minimo, maximo, step=float(paso), key=key, on_change=_desde_barra, help=help)
    with c_caja:
        st.number_input(f"{label} (valor exacto)", min_value=minimo, max_value=maximo, step=float(paso_caja or paso),
                        format=formato, key=k_caja, on_change=_desde_caja, label_visibility="collapsed",
                        help="Escribe el valor exacto; la barra se ajusta al punto más cercano.")
    return float(st.session_state[k_caja])


def _como_dialogo(titulo, width="large"):
    """st.dialog si existe (Streamlit ≥ 1.34); si no, la función se ejecuta en línea.

    Un diálogo es un fragmento: al pulsar un botón dentro de él Streamlit vuelve a ejecutar SOLO la
    función, sin el inicio del script que vincula el estado de la lógica a la sesión. Sin re-vincular,
    lo que guardara iría al almacén por defecto (compartido) y se perdería al recargar.
    """
    d = getattr(st, "dialog", None)

    def envolver(f):
        def con_sesion(*a, **k):
            if hasattr(L, "vincular_estado_sesion"):
                L.vincular_estado_sesion(st.session_state.setdefault("_estado_logica", {}))
            return f(*a, **k)
        con_sesion.__name__ = f.__name__
        return d(titulo, width=width)(con_sesion) if callable(d) else con_sesion
    return envolver


@_como_dialogo("Corregir el histórico con cifras oficiales")
def _dialogo_historico(empresa):
    """Editor del histórico (prellenado con la fuente pública) para corregir partidas puntuales."""
    st.caption("Escribe las cifras de los estados financieros oficiales (miles de millones de la moneda del modelo). "
               "ΔNWC, NOPAT y FCFF se recalculan. Las correcciones valen para esta sesión y se rotulan en el informe.")
    if st.session_state.get("archivo_bytes"):
        st.warning("Hay un Excel cargado: el modelo usa ese archivo y no estas correcciones.")
    try:
        base, msg = L._cargar_y_limpiar_excel_impl(None, empresa, usar_datos_publicos=True)
    except Exception as e:
        st.error(f"No hay histórico para corregir: {e}")
        return
    actual = L.historico_usuario(empresa)
    tabla = base[[c for c in L.HISTORICO_EDITABLE if c in base.columns]].copy()
    if actual:
        tabla = pd.DataFrame(actual["datos"]).sort_index()
        st.info("Correcciones activas: " + ("; ".join(actual["cambios"]) or "ninguna celda distinta"))
    tabla.index.name = "Año"
    nombres = {"Ingresos": "Ingresos", "EBITDA": "EBITDA", "EBIT": "EBIT (utilidad operativa)",
               "Depreciacion": "Depreciación y amortización", "CAPEX": "CAPEX (inversiones)", "NWC": "Capital de trabajo"}
    editado = st.data_editor(
        tabla.reset_index(), hide_index=True, width="stretch", num_rows="fixed", key=f"ed_hist_{empresa[:40]}",
        column_config={"Año": st.column_config.NumberColumn("Año", format="%d", disabled=True),
                       **{c: st.column_config.NumberColumn(nombres[c], format="%.1f") for c in L.HISTORICO_EDITABLE}},
    )
    st.caption(f"Fuente original: {msg[:220]}")
    c1, c2 = st.columns(2)
    if c1.button("Aplicar correcciones", type="primary", width="stretch"):
        try:
            cambios = L.fijar_historico_usuario(empresa, editado, base, fuente_original=msg.split(".")[0],
                                                attrs=dict(getattr(base, "attrs", {}) or {}))
            st.session_state["aviso_ajustes"] = (f"Histórico corregido ({len(cambios)} celda(s)). Ejecuta «Generar todo».")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    if c2.button("Volver a la fuente pública", width="stretch", disabled=not actual):
        L.borrar_historico_usuario(empresa)
        st.session_state["aviso_ajustes"] = "Se restableció el histórico de la fuente pública. Ejecuta «Generar todo»."
        st.rerun()


@_como_dialogo("Narrativa: las palancas de la historia")
def _dialogo_narrativa(empresa, tax_actual):
    """Las cuatro palancas de Damodaran: el modelo propone (por estadística) y el usuario fija con una frase."""
    st.caption("Toda valoración es una historia traducida a números. Aquí ves qué historia supone el modelo para "
               "cada palanca y puedes reemplazarla. Lo que no fijes lo sigue decidiendo el modelo.")
    try:
        base, _msg = L.cargar_y_limpiar_excel(_archivo_para_logic(), empresa, bool(st.session_state.get("usar_publicos", True)))
        base.attrs.pop("narrativa", None)  # propuesta del modelo, sin las palancas ya fijadas
        _dp, meta = L.proyectar_variables_con_meta(base, 5, "drivers", float(tax_actual))
    except Exception as e:
        st.error(f"No hay histórico para proponer la narrativa: {e}")
        return
    actual = L.narrativa_sesion(empresa) or {}
    pal_act, just_act = dict(actual.get("palancas") or {}), dict(actual.get("justificacion") or {})
    propuesta = {f["palanca"]: f for f in meta.get("narrativa") or []}
    nuevas, frases = {}, {}
    formatos = {"g_ingresos": ("%", 100.0), "margen_ebitda": ("%", 100.0), "anios_convergencia": ("años", 1.0),
                "ventas_capital": ("×", 1.0)}
    for k, nombre in L.PALANCAS_NARRATIVA.items():
        f = propuesta.get(k) or {}
        unidad, esc = formatos[k]
        v_mod = f.get("valor")
        st.markdown(f"**{nombre}** — modelo: " + (f"{v_mod * esc:.2f} {unidad}" if isinstance(v_mod, (int, float)) else "no aplica")
                    + f" · _{f.get('frase', '')}_")
        c1, c2 = st.columns([1, 3])
        fijar = c1.checkbox("Fijar", value=k in pal_act, key=f"nar_fijar_{k}")
        if fijar:
            v0 = pal_act.get(k, v_mod if isinstance(v_mod, (int, float)) else (1 if k == "anios_convergencia" else 0.0))
            if k == "anios_convergencia":
                val = c2.number_input(f"{nombre} (años)", 1, 10, int(v0 or 1), 1, key=f"nar_val_{k}")
            else:
                val = c2.number_input(f"{nombre} ({unidad})", value=float(v0 or 0) * esc, step=0.1 if unidad == "%" else 0.01,
                                      format="%.2f", key=f"nar_val_{k}") / esc
            nuevas[k] = val
            frases[k] = st.text_input("¿Qué parte de la historia sostiene este número?", value=just_act.get(k, ""),
                                      key=f"nar_frase_{k}", placeholder="Ej.: 2025 tuvo un cargo regulatorio que no se repite")
    modo_def = pal_act.get("reinversion") or ("ligada" if L.REINVERSION_LIGADA_POR_DEFECTO else "mantenimiento")
    modo = st.radio("Reinversión en los años proyectados", ["ligada", "mantenimiento"], horizontal=True,
                    index=0 if modo_def == "ligada" else 1, key="nar_reinv",
                    format_func=lambda x: ("Ligada al crecimiento (ventas/capital)" if x == "ligada"
                                           else "CAPEX converge al mantenimiento (método anterior)"),
                    help="Ligada: cada año reinvierte lo que exige el crecimiento del siguiente (g = reinversión × ROIC). "
                         "Mantenimiento: el CAPEX converge a ≈ 1,3 × depreciación aunque los ingresos sigan creciendo.")
    if modo != ("ligada" if L.REINVERSION_LIGADA_POR_DEFECTO else "mantenimiento"):
        nuevas["reinversion"] = modo
    c1, c2 = st.columns(2)
    if c1.button("Aplicar narrativa", type="primary", width="stretch"):
        try:
            L.fijar_narrativa(empresa, nuevas, {k: v for k, v in frases.items() if v})
            st.session_state["aviso_ajustes"] = "Narrativa actualizada. Ejecuta «Generar todo»."
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    if c2.button("Volver a la del modelo", width="stretch", disabled=not actual):
        L.fijar_narrativa(empresa, {})
        st.session_state["aviso_ajustes"] = "Se restableció la narrativa del modelo. Ejecuta «Generar todo»."
        st.rerun()


@_como_dialogo("Valorar participadas por separado (suma de partes)")
def _dialogo_suma_partes(empresa, ke_defecto, asociados_actual):
    """Cada participada con su método; el total reemplaza «Asociados» en el puente a equity."""
    st.caption("Útil cuando buena parte del valor está en empresas donde la matriz tiene participación (GEB en Enel "
               "Colombia, Promigas, Vanti…). Cifras en miles de millones de la moneda del modelo; % en porcentaje.")
    ke = st.number_input("Costo del patrimonio (Ke) para descontar las participadas", 0.02, 0.40,
                         float(ke_defecto), 0.0025, format="%.4f",
                         help="Por defecto, el Ke de la matriz. Si una participada tiene otro riesgo, valórala por P/U o mercado.")
    previo = L.suma_partes_sesion(empresa)
    filas = (previo or {}).get("filas") or L.participadas_sugeridas(empresa)
    etiquetas = L.METODOS_PARTICIPADA
    inv = {v: k for k, v in etiquetas.items()}
    df = pd.DataFrame([{**{k: f.get(k) for k in ("participada", "participacion", "utilidad", "dividendo", "valor",
                                                 "pu", "roe", "g", "fuente")},
                        "metodo": etiquetas.get(f.get("metodo") or "capitalizada")} for f in filas] or
                      [{"participada": "", "participacion": 100.0, "metodo": etiquetas["capitalizada"]}])
    cols = ["participada", "participacion", "metodo", "utilidad", "dividendo", "valor", "pu", "roe", "g", "fuente"]
    df = df.reindex(columns=cols)
    for c in ("participacion", "utilidad", "dividendo", "valor", "pu", "roe", "g"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["fuente"] = df["fuente"].fillna("")
    editado = st.data_editor(
        df, hide_index=True, num_rows="dynamic", width="stretch", key=f"ed_sdp_{empresa[:40]}",
        column_config={
            "participada": st.column_config.TextColumn("Participada", required=True),
            "participacion": st.column_config.NumberColumn("Participación %", min_value=0.0, max_value=100.0, format="%.2f"),
            "metodo": st.column_config.SelectboxColumn("Método", options=list(etiquetas.values()), required=True),
            "utilidad": st.column_config.NumberColumn("Utilidad neta 100 %", format="%.1f"),
            "dividendo": st.column_config.NumberColumn("Dividendo recibido", format="%.1f"),
            "valor": st.column_config.NumberColumn("Valor (mercado 100 % o libros)", format="%.1f"),
            "pu": st.column_config.NumberColumn("P/U (x)", format="%.1f"),
            "roe": st.column_config.NumberColumn("ROE %", format="%.1f", help="Vacío = Ke (crecer no crea valor)"),
            "g": st.column_config.NumberColumn("g %", format="%.1f", help="Crecimiento perpetuo nominal; vacío = 0"),
            "fuente": st.column_config.TextColumn("Fuente"),
        },
    )
    filas_n = []
    for r in editado.to_dict("records"):
        r = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in r.items()}
        r["metodo"] = inv.get(r.get("metodo"), "capitalizada")
        filas_n.append(r)
    res = L.suma_de_partes(filas_n, ke)
    if res["detalle"]:
        st.dataframe(pd.DataFrame([{"Participada": d["participada"], "Método": d["metodo"], "Valor": round(d["valor"], 1),
                                    "Cálculo": d["calculo"]} for d in res["detalle"]]), hide_index=True, width="stretch")
    for e in res["errores"]:
        st.warning(e)
    st.metric("Total participadas", f"{res['total']:,.1f}", f"{res['total'] - float(asociados_actual or 0):+,.1f} vs «Asociados» actual")
    c1, c2 = st.columns(2)
    if c1.button("Usar en el puente a equity", type="primary", width="stretch", disabled=not res["detalle"]):
        L.fijar_suma_partes(empresa, filas_n, res, ke)
        st.session_state["aviso_ajustes"] = f"Asociados = {res['total']:,.1f} por suma de partes. Ejecuta «Generar todo»."
        st.rerun()
    if c2.button("Quitar la suma de partes", width="stretch", disabled=previo is None):
        L.borrar_suma_partes(empresa)
        st.session_state["aviso_ajustes"] = "Se quitó la suma de partes. Ejecuta «Generar todo»."
        st.rerun()


@st.cache_data(ttl=300, show_spinner=False)
def _market_tape_quotes():
    """Cinta de mercado: UNA descarga en lote (antes 12 llamadas .info secuenciales,
    principal cuello de botella del primer render). `chg` en puntos porcentuales;
    cada precio lleva su moneda (COP para BVC, USD para NYSE/NASDAQ)."""
    symbols = [x[0] for x in _TAPE_SYMBOLS]
    closes = {}
    try:
        import yfinance as yf
        df = yf.download(
            symbols, period="10d", interval="1d", auto_adjust=True,
            progress=False, group_by="column", threads=True,
        )
        closes = _cierres_desde_download(df, symbols)
    except Exception:
        closes = {}
    rows = []
    for sym, name, cur in _TAPE_SYMBOLS:
        ser = closes.get(sym)
        px = chg = None
        if ser is not None and len(ser) >= 1:
            px = float(ser.iloc[-1])
            if len(ser) >= 2 and float(ser.iloc[-2]) != 0:
                chg = 100.0 * (float(ser.iloc[-1]) / float(ser.iloc[-2]) - 1.0)
        rows.append({"sym": sym.replace(".CL", "").replace("=X", ""), "name": name,
                     "px": px, "chg": chg, "cur": cur})
    return rows


@st.cache_data(ttl=900, show_spinner=False)
def _serie_cop_por_usd(period="5y"):
    """Serie diaria COP por 1 USD (Yahoo ``COP=X``). Fuente única de FX del app."""
    try:
        import yfinance as yf
        df = yf.download("COP=X", period=period, interval="1d", auto_adjust=True, progress=False)
        ser = _cierres_desde_download(df, ["COP=X"]).get("COP=X")
        if ser is None and df is not None and "Close" in getattr(df, "columns", []):
            ser = pd.to_numeric(df["Close"].squeeze(), errors="coerce").dropna()
        if ser is None or ser.empty:
            return None
        ser = ser[(ser > 1000) & (ser < 20000)]  # descarta ticks corruptos de Yahoo
        return ser if not ser.empty else None
    except Exception:
        return None


def _tasa_cop_usd_spot():
    """Última tasa COP/USD (misma que muestra la cinta) o None si no hay datos."""
    ser = _serie_cop_por_usd("1mo")
    try:
        return float(ser.iloc[-1]) if ser is not None and len(ser) else None
    except Exception:
        return None


def _clave_ia_efectiva():
    """(proveedor, api_key) para el comité: widget pestaña 4 → Consulta IA → secrets/env."""
    prov_ia = (
        st.session_state.get("tab4_iaprov")
        or st.session_state.get("iaprov")
        or "gemini"
    )
    key_ui = (st.session_state.get("tab4_iakey") or "").strip() or (st.session_state.get("iakey") or "").strip()
    if prov_ia == "gemini":
        key_eff = _resolve_gemini_key(key_ui or None)
    else:
        key_eff = key_ui or None
    return prov_ia, key_eff


def _contexto_comite_ia(empresa, w=None, de_ratio=None, g=None, moneda=None):
    """Métricas del comité para la empresa seleccionada.

    Fuente única: la corrida de la pestaña 4 (L.metricas_valoracion_sesion). Los
    faltantes quedan en None (N/D) — nunca 0 —, para que la auditoría previa los
    detecte como ausentes en lugar de interpretarlos como valores reales.
    """
    m = None
    try:
        m = L.metricas_valoracion_sesion(empresa) if hasattr(L, "metricas_valoracion_sesion") else None
    except Exception:
        m = None
    if m:
        m["fuente_precio"] = m.get("fuente_precio") or st.session_state.get("fuente_precio_mercado")
        m["fecha_precio"] = m.get("fecha_precio") or st.session_state.get("fecha_precio_mercado")
        return m
    w = w if isinstance(w, dict) else {}
    mon = str(moneda or (st.session_state.get("params") or {}).get("moneda") or "").upper() or None
    mon_px = str(st.session_state.get("moneda_precio_alineada") or mon or "").upper() or None
    px = st.session_state.get("precio_mercado_alineado")
    return {
        "empresa": empresa,
        "ticker": _inferir_ticker_yf(empresa, {}) or None,
        "moneda": mon, "moneda_precio": mon_px,
        "monedas_alineadas": bool(mon and mon_px and mon == mon_px),
        "precio_mercado": float(px) if px else None,
        "vps_modelo": None, "upside": None,
        "wacc_calc": w.get("wacc"), "ke_calc": w.get("ke"), "roic_calc": None,
        "de_ratio": float(de_ratio) if de_ratio is not None else None,
        "g": float(g) if g is not None else None,
        "val_ev": None, "val_equity": None, "decision_modelo": None,
        "unidad_modelo": f"miles de millones de {mon}" if mon else None,
        "unidad_precio": "por acción",
        "fuente_precio": st.session_state.get("fuente_precio_mercado"),
        "fecha_precio": st.session_state.get("fecha_precio_mercado"),
        "fuente_valoracion": None,
    }


def _ejecutar_comite_ia_sesion(empresa, w=None, de_ratio=1.0, g=0.03, moneda="COP", forzar=False):
    """Comité IA (4+). Usado tras tab4 en Generar todo, en Solo pestaña 4 y en el botón
    de la pestaña 4. Retorna (ok, msg). Única implementación del flujo (antes había
    dos copias divergentes de ~250 líneas)."""
    try:
        if not hasattr(L, "generar_recomendacion_comite_ia"):
            return False, "modelacion_logic.py no tiene generar_recomendacion_comite_ia."
        prov_ia, key_eff = _clave_ia_efectiva()
        if prov_ia == "gemini" and not key_eff:
            return False, (
                "Falta la API key de Gemini: pégala en «Proveedor y API key» o define "
                "GEMINI_API_KEY en st.secrets / variables de entorno."
            )
        _metricas = _contexto_comite_ia(empresa, w=w, de_ratio=de_ratio, g=g, moneda=moneda)
        if _metricas.get("vps_modelo") is None:
            return False, "Ejecuta primero la pestaña 4 (o Generar todo): el comité necesita la valoración del modelo."
        _audit_ctx = L.auditar_contexto_comite_ia(_metricas)
        st.session_state["tab4_comite_ia_auditoria"] = _audit_ctx
        if _audit_ctx.get("errors"):
            return False, "Comité IA bloqueado por errores: " + "; ".join(_audit_ctx["errors"])
        # Un veto cuantitativo es un control de calidad, no una recomendación negativa
        # sobre la acción. No llamar a la IA ni conservar una deliberación anterior.
        _vetos = _metricas.get("vetos_calidad") or []
        _decision_motor = str(_metricas.get("decision_modelo") or "").upper()
        _veto_activo = bool(_metricas.get("control_calidad_modelo") or _vetos or "RECALIBRAR MODELO" in _decision_motor)
        if _veto_activo:
            _audit_ctx.setdefault("warnings", []).append(
                "Comité IA pausado por veto de calidad del modelo; recalibrar y ejecutar de nuevo la pestaña 4. El veto no es rating de la acción."
            )
            st.session_state["tab4_comite_ia_auditoria"] = _audit_ctx
            st.session_state["tab4_comite_ia_html"] = None
            st.session_state["tab4_comite_empresa"] = empresa
            return False, (
                f"Comité IA pausado por veto de calidad del modelo. Esto no es una calificación negativa de {empresa} "
                "ni una recomendación de venta. Revisa los vetos/alertas, alinea monedas y unidades (COP/USD), "
                "corrige el puente EV–equity si corresponde y vuelve a ejecutar la pestaña 4."
            )
        respuesta = L.generar_recomendacion_comite_ia(
            empresa, api_key=key_eff, proveedor=prov_ia or "gemini", metricas=_metricas,
            buscar_web=bool(st.session_state.get("tab4_busqueda_web", True)), forzar=bool(forzar),
        )
        _res = L._almacen_estado().get("comite_ia_ultimo") or {}
        st.session_state["tab4_comite_ia_html"] = respuesta
        st.session_state["tab4_comite_empresa"] = empresa
        st.session_state["tab4_comite_ia_res"] = {k: v for k, v in _res.items() if k != "html"}
        if not _res.get("ok"):
            return False, _res.get("error") or "Comité IA sin respuesta válida."
        try:
            _md = _res.get("markdown") or ""
            _struct = L.extraer_resumen_comite_ia(_md)
            _txt = (_struct or {}).get("texto") or _md[:800]
            L.guardar_resultado_tab("comite_ia", empresa, {
                "texto": _txt, "struct": _struct, "proveedor": prov_ia or "gemini",
                "dictamen": _res.get("dictamen"),
            })
            st.session_state["tab4_comite_ia_texto"] = _txt
            st.session_state["tab4_comite_ia_struct"] = _struct
        except Exception:
            pass
        if _res.get("cache"):
            return True, "Dictamen reutilizado: los insumos no cambiaron desde la última corrida."
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
        px_txt = (f"{float(px):,.2f} {d.get('cur', '')}".strip()) if _finite(px) else "—"
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


RUTA_MANUAL_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs",
                               "Manual_Usuario_Modelacion_Financiera.pdf")
NOMBRE_MANUAL_PDF = "Manual_Usuario_Modelacion_Financiera.pdf"


@st.cache_data(show_spinner=False)
def _bytes_manual_usuario(ruta: str, _mtime: float) -> bytes | None:
    """Lee el PDF del manual (se regenera con scripts/generar_manual_pdf.py)."""
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except OSError:
        return None


def _manual_usuario_pdf() -> bytes | None:
    try:
        mtime = os.path.getmtime(RUTA_MANUAL_PDF)
    except OSError:
        return None
    return _bytes_manual_usuario(RUTA_MANUAL_PDF, mtime)


def _tarjeta_manual_usuario():
    """Tarjeta visible al entrar: descarga del manual de usuario en PDF."""
    datos = _manual_usuario_pdf()
    if not datos:
        return
    c_txt, c_btn = st.columns([3, 1], vertical_alignment="center")
    with c_txt:
        st.markdown(
            '<div class="tf-manual">📘 <b>¿Primera vez aquí?</b> Descarga el <b>manual de usuario</b>: '
            "explica cada pestaña en palabras sencillas, con imágenes y un ejemplo completo paso a paso. "
            "No necesitas saber de finanzas.</div>",
            unsafe_allow_html=True,
        )
    with c_btn:
        st.download_button(
            "📘 Descargar manual (PDF)",
            data=datos,
            file_name=NOMBRE_MANUAL_PDF,
            mime="application/pdf",
            type="primary",
            width="stretch",
            key="btn_manual_inicio",
            help=f"Guía para principiantes · PDF de {len(datos) / 1024 / 1024:.1f} MB",
        )


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
        "rf": float(L.CAPM_POR_MERCADO.get("CO", {}).get("rf", 0.13)),
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

    # Precio SOLO desde la instantánea cacheada de la capa lógica: es la misma
    # que leen las pestañas 2/4/7, el comité IA, el simulador y el portafolio.
    # (Antes había aquí un segundo fetch directo a yfinance: la cabecera podía
    # mostrar un precio que las pestañas no veían → cifras contradictorias.)
    precio = None
    _snap = {}
    try:
        if hasattr(L, "instantanea_precio_mercado"):
            _snap = L.instantanea_precio_mercado(nombre) or {}
            precio = _snap.get("precio")
        elif hasattr(L, "resolver_precio_mercado"):
            precio = L.resolver_precio_mercado(nombre)
    except Exception:
        precio = None
    st.session_state["fuente_precio_mercado"] = _snap.get("fuente")
    st.session_state["fecha_precio_mercado"] = _snap.get("fecha")
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
        # Empresas precargadas: se intenta primero la descarga de Yahoo (puede tardar
        # unos segundos); el catálogo curado solo se usa si la descarga falla.
        with st.spinner(f"Obteniendo datos de {str(nombre).split('—')[0].strip()}…"):
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
            for k in ("moneda", "mercado_capm", "deuda_es_bruta", "deuda_fuente", "ticker_yf", "precio", "precio_mercado", "precio_moneda"):
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
        st.session_state["rf"] = float(L.CAPM_POR_MERCADO["CO"]["rf"]) if mon in ("COP", "") else 0.04
    _alinear_moneda_y_precio(nombre)


def _archivo_hash():
    data = st.session_state.get("archivo_bytes")
    return hashlib.sha256(data).hexdigest() if data else None


def _archivo_para_logic():
    """Ruta temporal del Excel/CSV cargado; se reutiliza mientras el contenido no cambie.

    Antes se creaba un archivo temporal nuevo en CADA rerun (fuga de disco) y la
    huella del modelo nunca detectaba cambios de contenido.
    """
    data = st.session_state.get("archivo_bytes")
    name = st.session_state.get("archivo_name") or "upload.xlsx"
    if not data:
        return None
    import tempfile

    h = _archivo_hash()
    prev = st.session_state.get("_archivo_tmp")
    if isinstance(prev, (list, tuple)) and len(prev) == 2 and prev[0] == h and os.path.isfile(prev[1]):
        return prev[1]
    if isinstance(prev, (list, tuple)) and len(prev) == 2:
        try:
            os.unlink(prev[1])
        except OSError:
            pass
    suffix = ".xlsx"
    low = name.lower()
    if low.endswith(".csv"):
        suffix = ".csv"
    elif low.endswith(".xls"):
        suffix = ".xls"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    st.session_state["_archivo_tmp"] = (h, tmp.name)
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
# Claves de st.session_state que pertenecen a UNA empresa y deben purgarse al
# cambiar de activo. Las preferencias del usuario (tour, proveedor/clave IA,
# tema, modo de ejecución) se conservan a propósito.
_CLAVES_ESTADO_EMPRESA = (
    "params", "resultados", "ficha_html", "hero_html", "n_hist",
    "precio_mercado_alineado", "moneda_precio_alineada", "fx_mismatch",
    "fuente_precio_mercado", "fecha_precio_mercado",
    "archivo_bytes", "archivo_name", "_archivo_tmp",
    "_model_fingerprint", "modelo_dirty",
    "tab4_comite_ia_html", "tab4_comite_ia_texto", "tab4_comite_ia_struct", "tab4_comite_empresa",
    "tab4_comite_ia_auditoria",
    "contraste_mercado_actual", "tab6_empresa",
    "portfolio_result", "investment_sim_result", "multiples_valuation_result",
    "sens_wacc", "sens_g",
)
_PREFIJOS_ESTADO_EMPRESA = ("investment_sim_ticker_", "multiples_")


def _purgar_estado_empresa(nueva_empresa):
    """Purga TODO el estado derivado de la empresa anterior.

    Se invoca desde un único punto (centinela `_empresa_estado`), de modo que
    cualquier vía de cambio (selector, búsqueda Yahoo, selector móvil) limpia
    igual: resultados de pestañas, comité IA, contraste de mercado, portafolio,
    simulador, múltiplos, sensibilidad, Excel cargado y caché de huella.
    """
    for k in _CLAVES_ESTADO_EMPRESA:
        st.session_state.pop(k, None)
    for k in [k for k in list(st.session_state.keys()) if str(k).startswith(_PREFIJOS_ESTADO_EMPRESA)]:
        st.session_state.pop(k, None)
    # Nuevo key para el file_uploader: sin esto el widget re-inyecta el Excel de
    # la empresa anterior en el siguiente rerun.
    st.session_state["_uploader_nonce"] = int(st.session_state.get("_uploader_nonce", 0)) + 1
    st.session_state["resultados"] = {}
    st.session_state["params"] = None
    try:
        L.reset_resultados_sesion(nueva_empresa)
    except Exception:
        pass
    st.session_state["_empresa_estado"] = nueva_empresa


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
    # Limpiar TODO el estado de la empresa anterior (evita precio/ticker AAPL en ficha ISA)
    _purgar_estado_empresa(display_name)
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
    st.rerun()


def main():
    # Registros de la capa lógica (empresas descargadas, resultados de pestañas,
    # credenciales del conector) ligados a ESTA sesión: sin esto eran globales del
    # proceso y un usuario veía/heredaba los datos de otro.
    if hasattr(L, "vincular_estado_sesion"):
        L.vincular_estado_sesion(st.session_state.setdefault("_estado_logica", {}))
        try:  # la clave de IA (si la hay) también traduce la descripción de la empresa en el informe PDF
            L._almacen_estado()["clave_ia"] = _clave_ia_efectiva()[1]
        except Exception:
            pass
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

    # Manual de usuario: visible desde el inicio
    try:
        _tarjeta_manual_usuario()
    except Exception:
        pass

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
            if st.button("Descargar datos", type="primary", width="stretch"):
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
            _purgar_estado_empresa(empresa)
            _cargar_params_empresa(empresa)
            st.rerun()
        # Centinela: cualquier otra vía de cambio que no haya purgado lo hace aquí.
        if st.session_state.get("_empresa_estado") != empresa:
            _purgar_estado_empresa(empresa)

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
        up = st.file_uploader(
            "Excel / CSV", type=["xlsx", "xls", "csv"], label_visibility="collapsed",
            key=f"uploader_{st.session_state.get('_uploader_nonce', 0)}",
        )
        if up is not None:
            st.session_state["archivo_bytes"] = up.read()
            st.session_state["archivo_name"] = up.name
            _h_up = _archivo_hash()
            if _h_up and st.session_state.get("_archivo_aplicado") != (empresa, _h_up):
                st.session_state["_archivo_aplicado"] = (empresa, _h_up)
                # Leer el archivo ya (no al generar): si trae hoja Parámetros, la barra lateral debe
                # mostrar sus cifras (deuda, caja, acciones, impuesto); antes el modelo seguía usando
                # las de Yahoo/catálogo aunque el informe dijera «parámetros del archivo».
                try:
                    L._cargar_y_limpiar_excel_impl(_archivo_para_logic(), empresa)
                    if empresa not in getattr(L, "EMPRESAS", {}):
                        _cargar_params_empresa(empresa)
                except Exception as _e_up:
                    st.error(f"El archivo no se pudo leer: {_e_up}")
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
                        width="stretch",
                    )
        except Exception:
            pass

        if st.button("Corregir histórico (cifras oficiales)", width="stretch", key="btn_corregir_hist",
                     help="Ajusta partidas puntuales de la fuente pública con los estados financieros oficiales "
                          "(p. ej. el CAPEX de concesiones de ISA)."):
            _dialogo_historico(empresa)
        if st.button("Narrativa (palancas de la historia)", width="stretch", key="btn_narrativa",
                     help="Crecimiento, margen objetivo, años de convergencia y ventas/capital: qué historia supone el "
                          "modelo y cómo cambiarla (marco de Damodaran)."):
            _dialogo_narrativa(empresa, float((st.session_state.get("params") or {}).get("tax") or 0.25))
        if L.narrativa_sesion(empresa):
            st.caption("✎ Narrativa fijada por el usuario: " + ", ".join(
                L.PALANCAS_NARRATIVA.get(k, k) for k in (L.narrativa_sesion(empresa).get("palancas") or {})))
        if L.historico_usuario(empresa):
            st.caption("✎ Histórico con correcciones del usuario: " + "; ".join(L.historico_usuario(empresa)["cambios"][:3]))

        ek = str(empresa)[:48]
        p = st.session_state.get("params") or {}
        if st.session_state.get("archivo_bytes") and hasattr(L, "parametros_archivo"):
            _pa = L.parametros_archivo(empresa)
            if _pa:  # la hoja Parámetros del Excel manda sobre Yahoo/catálogo en el puente y el impuesto
                p = {**p, **_pa}

        # Parámetros en acordeón cerrado por defecto (menos ruido en el sidebar)
        with st.expander("Parámetros del modelo", expanded=False):
            _h_def = L.horizonte_recomendado(empresa)
            horizonte = st.slider(
                "Horizonte (años)", 3, 10, _h_def, key=f"hor_{ek}",
                help=("Empresa de EE. UU. con consenso de analistas: modelo de tres etapas a 10 años "
                      "(consenso → convergencia → perpetuidad)." if _h_def == 10 else None),
            )
            st.caption("Tasas en fracción (0,1318 = 13,18 %). Escribe el valor exacto en la casilla de la derecha.")
            de_ratio = _slider_y_caja("D/E", 0.0, 5.0, float(p.get("de_ratio", 1.2) or 1.2), 0.01, f"de_{ek}", "%.4f", paso_caja=0.0001)
            kd = _slider_y_caja("Kd", 0.0, 0.25, float(p.get("kd", 0.08) or 0.08), 0.005, f"kd_{ek}", "%.4f", paso_caja=0.0001)
            tax = _slider_y_caja("Tax", 0.0, 0.50, float(p.get("tax", 0.35) or 0.35), 0.01, f"tax_{ek}", "%.4f", paso_caja=0.0001)
            g = _slider_y_caja("g terminal", 0.0, 0.08, float(p.get("g", 0.03) or 0.03), 0.005, f"g_{ek}", "%.4f", paso_caja=0.0001)
            capex_extra = _slider_y_caja("CAPEX extra", 0.0, 8000.0, 0.0, 50.0, f"cx_{ek}", "%.1f", paso_caja=1.0)
            beta_u = _slider_y_caja("β unlevered", 0.0, 3.0, float(p.get("beta_u", 0.5) or 0.5), 0.05, f"bu_{ek}", "%.4f", paso_caja=0.0001)

            st.markdown("**CAPM**")
            rf = _slider_y_caja("rf", 0.02, 0.16, float(st.session_state.get("rf", 0.12)), 0.005, f"rf_{ek}", "%.4f", paso_caja=0.0001)
            # Paso 0,0005: las primas de Damodaran (p. ej. 4,42 %) no son múltiplos de 0,5 pp.
            _mon_flujos = str(p.get("moneda") or "").upper()
            _erp_def, _crp_def = float(st.session_state.get("erp", 0.055)), float(st.session_state.get("crp", 0.0))
            _ops_txt = st.text_input(
                "Ingresos por país (opcional)", key=f"ops_{ek}", placeholder="Ej.: Brasil 40, Colombia 30, Chile 15, Perú 15",
                help="El riesgo país viene de dónde la empresa vende, no de su sede (Damodaran). Con pesos de ingresos "
                     "por país, la prima de riesgo se pondera con las tablas de Damodaran. Vacío = país de la sede.")
            try:
                _pesos_ops = L.leer_pesos_paises(_ops_txt) if _ops_txt.strip() else None
                L.fijar_paises_operacion(empresa, _pesos_ops)
                if _pesos_ops:
                    _ops = L.erp_por_operaciones(_pesos_ops)
                    if _mon_flujos == "COP":  # ERP total ponderada (ya incluye el riesgo país); CRP aparte = 0
                        _erp_def, _crp_def = _ops["erp"], 0.0
                    else:                      # moneda dura: ERP madura + CRP ponderada
                        _erp_def = float(((L.DAMODARAN or {}).get("riesgo_pais") or {}).get("meta", {}).get("erp_madura") or _erp_def)
                        _crp_def = _ops["crp"]
                    st.caption("Prima ponderada por operaciones: " + ", ".join(f"{k} {v:.0%}" for k, v in _ops["pesos"].items())
                               + f" → ERP {_erp_def:.2%}, CRP {_crp_def:.2%}.")
            except ValueError as _e_ops:
                st.warning(str(_e_ops))
            erp = _slider_y_caja("ERP", 0.03, 0.10, _erp_def, 0.0005, f"erp_{ek}", "%.4f", paso_caja=0.0001)
            crp = _slider_y_caja("CRP", 0.0, 0.08, _crp_def, 0.0005, f"crp_{ek}", "%.4f", paso_caja=0.0001)
            if _mon_flujos == "COP" and float(crp or 0) > 0:
                st.warning(f"CRP {crp:.2%} con flujos en pesos: el ERP de Damodaran para Colombia ya incluye el "
                           "riesgo país y rf (TES) ya trae el riesgo soberano. Sumar CRP lo cuenta dos veces; "
                           "déjalo en 0 salvo que uses un ERP de mercado maduro.")
            try:
                _dam_ui = L.damodaran_empresa(empresa) if hasattr(L, "damodaran_empresa") else {}
                _rp_ui = (_dam_ui or {}).get("riesgo_pais") or {}
                _vig_ui = (_dam_ui or {}).get("vigencia") or {}
                if _rp_ui:
                    st.caption(
                        f"Referencia Damodaran ({_rp_ui.get('fecha')}): ERP madura {_rp_ui['erp_madura']:.2%} · "
                        f"{_rp_ui['pais']} {_rp_ui.get('rating')}: riesgo país {_rp_ui['crp']:.2%}, ERP total {_rp_ui['erp_total']:.2%}, "
                        f"spread de default {_rp_ui['spread']:.2%}. En pesos: rf = TES − spread de default y ERP = total "
                        "(ya incluye el riesgo país, por eso CRP = 0). En dólares: ERP madura + CRP."
                    )
                if _vig_ui.get("aviso"):
                    st.caption("⚠ " + _vig_ui["aviso"])
                _tm = L.TASAS_MERCADO
                st.caption(
                    "Tasas de mercado: TES 10a {:.2%} ({}, {}) · Tesoro EE. UU. 10a {:.2%} ({}) · inflación LP CO {:.2%} / "
                    "EE. UU. {:.2%}. Se actualizan cada semana (Tesoro de EE. UU. y OCDE) o con la referencia del código, la más reciente.".format(
                        _tm["co_rf_bruto"]["valor"], _tm["co_rf_bruto"]["origen"], _tm["co_rf_bruto"]["fecha"],
                        _tm["us_rf"]["valor"], _tm["us_rf"]["fecha"], _tm["co_inflacion_lp"]["valor"], _tm["us_inflacion_lp"]["valor"]))
                for _av in L.tasas_vigencia():
                    st.caption("⚠ " + _av)
            except Exception:
                pass

            st.markdown("**Puente a equity**")
            capital_invertido = _numero_empresa("Capital invertido", p.get("capital_invertido", 0), 100.0, f"ci_{ek}")
            deuda_neta = _numero_empresa("Deuda neta", p.get("deuda_neta", 0), 100.0, f"dn_{ek}")
            if abs(float(deuda_neta or 0)) < 1e-9 and float(de_ratio or 0) > 0.2:
                st.warning(f"Deuda neta en 0 con D/E {de_ratio:.2f}: el patrimonio no descuenta deuda y el valor por "
                           "acción sale inflado. Escribe la deuda neta de los estados financieros.")
            elif p.get("deuda_fuente"):
                st.caption(f"Deuda neta: {p['deuda_fuente']}.")
            inversion_inicial = _numero_empresa("Inversión proyecto", p.get("inversion_inicial", 0), 10.0, f"ii_{ek}")
            caja = _numero_empresa("Caja", p.get("caja", 0), 50.0, f"caja_{ek}")
            nci = _numero_empresa("NCI", p.get("nci", 0), 50.0, f"nci_{ek}")
            otros_claims = _numero_empresa("Otros claims", p.get("otros_claims", 0), 50.0, f"oc_{ek}")
            asociados = _numero_empresa("Asociados", p.get("asociados", 0), 50.0, f"as_{ek}")
            if st.button("Valorar participadas por separado", width="stretch", key=f"btn_sdp_{ek}"):
                try:
                    _ke_sdp = L.costo_equity_capm(L.beta_apalancado(beta_u, de_ratio, tax), rf=rf, erp=erp, crp=crp)
                except Exception:
                    _ke_sdp = 0.12
                _dialogo_suma_partes(empresa, _ke_sdp, asociados)
            _sdp = L.suma_partes_sesion(empresa)
            if _sdp:
                st.caption(f"Asociados por suma de partes: {_sdp['total']:,.1f} (reemplaza {asociados:,.1f}; "
                           f"{len(_sdp['detalle'])} participada(s), Ke {_sdp['ke']:.2%}).")
                asociados = float(_sdp["total"])
            _acc0 = p.get("acciones")
            if _acc0 is None or float(_acc0 or 0) <= 0:
                try:
                    _acc0 = L.resolver_acciones_millones(empresa, None)
                except Exception:
                    _acc0 = 0
            acciones = _numero_empresa(
                "Acciones (M)", _acc0, 1.0, f"acc_{ek}",
                help="Millones de acciones diluidas. Si queda en 0, el modelo intenta obtenerlas de Yahoo.",
            )
            exit_multiple = _slider_y_caja("Exit EV/EBITDA", 0.0, 40.0, float(p.get("exit_multiple", 9) or 9), 0.5,
                                           f"em_{ek}", "%.2f", paso_caja=0.01)
            mid_year = st.checkbox("Mid-year", value=True, key=f"my_{ek}")
            g_max_macro = _slider_y_caja(
                "Techo g terminal (nominal)", 0.02, 0.06, float(st.session_state.get("g_max_macro", 0.04)), 0.005,
                f"gmax_{ek}", "%.4f", paso_caja=0.0001,
                help="Crecimiento perpetuo máximo en la moneda del modelo: ~4 % en USD, ~6 % en COP "
                     "(inflación implícita ~6 %). Se aplica también min(techo, WACC − 1 pp).",
            )
            _ronic_opts = {
                "roic": "Converge al ROIC observado (recomendado)",
                "wacc": "Igual al WACC (conservador)",
                "manual": "Manual",
            }
            _ronic_modo = st.selectbox(
                "Retorno de la nueva inversión en perpetuidad (RONIC)", list(_ronic_opts),
                format_func=lambda k: _ronic_opts[k], key=f"ronic_modo_{ek}",
                help="Cuánto rinde lo que la empresa reinvierte para crecer después del horizonte. "
                     "«Converge al ROIC»: WACC + ½ × (ROIC observado − WACC), nunca por debajo del WACC. "
                     "«Igual al WACC»: el crecimiento no crea valor. Afecta a todas las pestañas.",
            )
            ronic_spread = 0.0
            if _ronic_modo == "manual":
                ronic_spread = _slider_y_caja(
                    "Spread RONIC − WACC (perpetuidad)", 0.0, float(L.RONIC_SPREAD_MAX),
                    float(st.session_state.get("ronic_spread", L.RONIC_SPREAD)), 0.01, f"ronic_{ek}", "%.4f", paso_caja=0.0001,
                    help="0 = el crecimiento no crea valor (utilities reguladas, commodities). Franquicias con "
                         "ventajas duraderas (marcas, ecosistemas) justifican 3–10 pp.",
                )
            try:
                if _ronic_modo == "manual":
                    L.fijar_ronic_spread(ronic_spread)
                else:
                    L.fijar_ronic_spread(None)
                    L.fijar_modo_ronic(_ronic_modo)
                _roic_ref = L.roic_referencia_sesion()
                if _ronic_modo == "roic":
                    st.caption(
                        f"ROIC observado: {_roic_ref:.1%}. Si no supera el WACC, el RONIC queda igual al WACC."
                        if _roic_ref is not None else "ROIC observado: se calcula al ejecutar el modelo (requiere capital invertido)."
                    )
            except Exception:
                pass

        with st.expander("Conector de mercado", expanded=False):
            prov = st.selectbox("Proveedor", ["yahoo", "api_key", "manual"])
            api_key = st.text_input("API key", type="password")
            api_url = st.text_input("URL vendor")
            if st.button("Aplicar", width="stretch"):
                try:
                    _html(L.aplicar_config_mercado_ui(prov, api_key, api_url))
                except Exception as e:
                    st.error(str(e))

        # «Modo claro (experimental)» se retiró: inyectaba un <script> que Streamlit no ejecuta
        # (st.markdown no corre JavaScript) y no existía CSS claro, así que no hacía nada.
        st.markdown('<p class="tf-sidebar-label">Experiencia</p>', unsafe_allow_html=True)
        _pdf_manual = _manual_usuario_pdf()
        if _pdf_manual:
            st.download_button(
                "📘 Manual de usuario (PDF)", data=_pdf_manual, file_name=NOMBRE_MANUAL_PDF,
                mime="application/pdf", width="stretch", key="btn_manual_sidebar",
            )
        if st.button("Repetir tour guiado", width="stretch", key="btn_retour"):
            st.session_state["tour_done"] = False
            st.session_state["tour_step"] = 1
            st.rerun()
        with st.expander("Self-test núcleo valoración", expanded=False):
            if st.button("Correr pruebas unitarias", key="btn_self_test", width="stretch"):
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
                empresa.split("—")[0].strip(),
                str(sector).split("/")[0].strip(),
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
            if st.button("Ver impacto en valoración", key="btn_sens", width="stretch", type="primary"):
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
        consultar = st.button("Consultar", type="primary", key="btn_ia", width="stretch")
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

    # Huella de todos los supuestos materiales, incluido el contenido del archivo.
    _hash_archivo = _archivo_hash()
    _model_fingerprint = tuple(repr(x) for x in (
        empresa, horizonte, metodo, tax, de_ratio, kd, g, capex_extra, beta_u,
        deuda_neta, rf, erp, crp, caja, nci, otros_claims, asociados, acciones,
        exit_multiple, mid_year, g_max_macro, usar_publicos,
        capital_invertido, inversion_inicial, _hash_archivo, moneda, ronic_spread, _ronic_modo,
        L.firma_ajustes_usuario(empresa),
    ))
    _prev_fingerprint = st.session_state.get("_model_fingerprint")
    if _prev_fingerprint is not None and _prev_fingerprint != _model_fingerprint:
        st.session_state["resultados"] = {}
        for _k in ("tab4_comite_ia_html", "tab4_comite_ia_texto", "tab4_comite_ia_struct",
                   "contraste_mercado_actual", "hero_html", "investment_sim_result"):
            st.session_state.pop(_k, None)
        try:
            L.reset_resultados_sesion(empresa)
        except Exception:
            pass
        st.session_state["modelo_dirty"] = True
    st.session_state["_model_fingerprint"] = _model_fingerprint
    if st.session_state.get("aviso_ajustes"):
        st.success(st.session_state.pop("aviso_ajustes"))
    if st.session_state.get("modelo_dirty"):
        st.info("Los supuestos cambiaron: se invalidaron resultados anteriores. Ejecuta **Generar todo** para recalcularlos.")
    # Validación de robustez pre-corrida (WACC vs g, finitud)
    try:
        if hasattr(L, "validar_inputs_valoracion"):
            _warns = L.validar_inputs_valoracion(w["wacc"], g, g_max_macro=g_max_macro, acciones=acciones, kd=kd, rf=rf)
            for _m in (_warns or []):
                st.warning(_m)
    except Exception:
        pass

    if st.button("▶ Generar todo", type="primary", key="btn_generar_todo", width="stretch"):
        try:
            _alinear_moneda_y_precio(empresa)
        except Exception:
            pass
        progress = st.progress(0, text="Iniciando…")
        errores = []
        # Orden: 1 → 2 → 3 → 4 → 5 → 6 → Comité IA (usa 2 y 6) → 7 (última)
        pasos = [
            ("1 · Pronóstico FCFF", 1 / 8),
            ("2 · Escenarios DCF", 2 / 8),
            ("3 · Auditoría", 3 / 8),
            ("4 · Recomendación", 4 / 8),
            ("5 · VPN / TIR", 5 / 8),
            ("6 · Sector", 6 / 8),
            ("4+ · Comité de inversión (IA)", 7 / 8),
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
                st.session_state["tab6_empresa"] = empresa
            except Exception as e:
                errores.append(f"Pestaña 6: {e}")

            # Comité IA después de 1–6: usa escenarios (2) y múltiplos de pares (6) como anclas; el 7 lo resume
            progress.progress(pasos[6][1], text=pasos[6][0])
            avisos = []
            try:
                if _clave_ia_efectiva()[1]:
                    ok_c, msg_c = _ejecutar_comite_ia_sesion(
                        empresa, w=w, de_ratio=de_ratio, g=g, moneda=moneda,
                    )
                    if not ok_c:
                        errores.append(f"Comité IA (4+): {msg_c}")
                else:
                    # Sin clave el pipeline cuantitativo sigue siendo válido: aviso, no error.
                    avisos.append("Comité IA omitido: no hay API key configurada (GEMINI_API_KEY).")
            except Exception as e:
                errores.append(f"Comité IA (4+): {e}")

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
            for _a in avisos:
                st.info(_a)
            if errores:
                st.warning("Algunas pestañas fallaron:\n- " + "\n- ".join(errores))
            else:
                st.session_state["modelo_dirty"] = False
                st.success(
                    "Pipeline completo: 1→2→3→4→5→6→Comité IA→7. "
                    "Revisa cada pestaña."
                )
            _liberar_figuras(st.session_state.get("resultados"))
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
                if st.button(_tab_labels[i], key=f"btn_solo_{_tab_keys[i]}", width="stretch"):
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
                        _liberar_figuras(st.session_state.get("resultados"))
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # ----- 10 TABS visibles: escenarios y políticas académicas incluidos -----
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(
        [
            "1 · Pronóstico",
            "2 · Escenarios DCF",
            "3 · Auditoría",
            "4 · Recomendación",
            "5 · VPN / TIR",
            "6 · Sector",
            "7 · Informe PDF",
            "8 · Portafolios",
            "9 · Simular inversión",
            "10 · Escenarios y políticas",
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
        st.markdown("##### 🤖 Comité de inversión IA · modelo + mercado real")
        st.caption(
            "Mismo proveedor/API key que **Consulta IA**. Tres bloques: (1) crítica de los resultados del modelo, "
            "(2) coyuntura de mercado verificada (instantánea + búsqueda web con Gemini) y "
            "(3) recomendación COMPRAR / MANTENER / VENDER con tesis, riesgos y catalizadores."
        )

        def _fmt_or_nd(v, fmt="{:,.2f}", suf=""):
            try:
                return (fmt.format(float(v)) + suf) if v is not None else "N/D"
            except (TypeError, ValueError):
                return "N/D"

        with st.expander("Generar deliberación del comité con IA", expanded=True):
            ctx_preview = _contexto_comite_ia(empresa, w=w, de_ratio=de_ratio, g=g, moneda=moneda)
            _mon_px = ctx_preview.get("moneda_precio") or ""
            _mon_md = ctx_preview.get("moneda") or ""
            _metrics_tip_row([
                (
                    "Precio mercado",
                    f"{_fmt_or_nd(ctx_preview.get('precio_mercado'))} {_mon_px}".strip(),
                    "Último precio negociado (misma instantánea que la cabecera y las pestañas 2, 4 y 7). "
                    "Es lo que paga el mercado hoy, no el valor del modelo.",
                ),
                (
                    "VPS modelo",
                    f"{_fmt_or_nd(ctx_preview.get('vps_modelo'))} {_mon_md}".strip(),
                    "Valor por acción según el DCF de la pestaña 4 con tus supuestos actuales.",
                ),
                (
                    "Upside",
                    _fmt_or_nd(ctx_preview.get("upside"), "{:+.1f}", "%"),
                    "Diferencia porcentual VPS vs. precio. Solo se calcula con monedas idénticas y "
                    "ratio VPS/precio dentro de 1/100–100×.",
                ),
                (
                    "EV / Equity",
                    f"{_fmt_or_nd(ctx_preview.get('val_ev'), '{:,.0f}')} / {_fmt_or_nd(ctx_preview.get('val_equity'), '{:,.0f}')}",
                    f"EV = valor del negocio; Equity = valor para el accionista tras el puente de deuda. "
                    f"Unidad: {ctx_preview.get('unidad_modelo') or 'N/D'}.",
                ),
            ], cols=4)

            _opts = ["gemini", "xai", "openai"]
            _prov_consulta = st.session_state.get("iaprov") or "gemini"
            if _prov_consulta not in _opts:
                _prov_consulta = "gemini"
            if "tab4_iaprov" not in st.session_state:
                st.session_state["tab4_iaprov"] = _prov_consulta

            with st.expander("Proveedor y API key (compartido con Consulta IA)", expanded=False):
                st.selectbox(
                    "Proveedor", _opts, key="tab4_iaprov",
                    help="Por defecto toma el proveedor de Consulta IA; no sobrescribe ese widget.",
                )
                st.text_input(
                    "API key (opcional — vacío = clave de Consulta IA o GEMINI_API_KEY)",
                    type="password", key="tab4_iakey", placeholder="Vacío = Gemini por defecto",
                )
                _prov_now, _key_now = _clave_ia_efectiva()
                st.caption(
                    f"Proveedor activo: **{_prov_now}** · clave "
                    + ("**detectada**" if _key_now else "**no configurada** — define GEMINI_API_KEY en st.secrets")
                    + ". La clave viaja en cabecera HTTP, nunca en la URL."
                )

            _c_tg, _c_tx = st.columns([1, 2])
            with _c_tg:
                st.toggle(
                    "Contexto de mercado en vivo (búsqueda web)", value=True, key="tab4_busqueda_web",
                    help="Solo Gemini: activa la herramienta google_search de la API para contrastar con noticias, "
                         "resultados y macro actuales. La salida lista las fuentes citadas.",
                )
            with _c_tx:
                _wm, _wi, _wp = ctx_preview.get("wacc_calc"), ctx_preview.get("wacc_implicito_mercado"), ctx_preview.get("wacc_paridad_usd")
                st.caption(
                    f"WACC modelo **{_fmt_or_nd(_wm * 100 if _wm is not None else None, '{:.2f}', '%')}** · "
                    f"paridad USD **{_fmt_or_nd(_wp * 100 if _wp is not None else None, '{:.2f}', '%')}** · "
                    f"implícito en el precio **{_fmt_or_nd(_wi * 100 if _wi is not None else None, '{:.2f}', '%')}**. "
                    "Si difieren mucho, el comité debe explicar qué supuesto produce la brecha."
                )
            if hasattr(L, "contexto_mercado_comite") and ctx_preview.get("vps_modelo") is not None:
                with st.expander("Instantánea de mercado que recibe el comité", expanded=False):
                    try:
                        _cm = L.contexto_mercado_comite(empresa, ctx_preview)
                        st.markdown(L._texto_contexto_mercado(_cm, ctx_preview.get("moneda_precio") or ""))
                    except Exception as _e_cm:
                        st.caption(f"Instantánea no disponible: {_e_cm}")

            _tiene_base = ctx_preview.get("vps_modelo") is not None
            if not _tiene_base:
                st.warning(
                    "Ejecuta **Generar todo** o la pestaña 4 antes del comité IA: "
                    "sin la valoración del modelo la deliberación no está anclada."
                )
            elif not ctx_preview.get("monedas_alineadas", False):
                st.warning(
                    f"Moneda del modelo ({_mon_md or 'N/D'}) ≠ cotización ({_mon_px or 'N/D'}): "
                    "el comité tratará el upside como no comparable."
                )
            _cb1, _cb2 = st.columns([3, 1])
            with _cb1:
                _btn_gen = st.button(
                    "▶ Generar dictamen del comité (IA)", type="primary", key="btn_tab4_comite_ia",
                    width="stretch", disabled=not _tiene_base,
                )
            with _cb2:
                _btn_forzar = st.button(
                    "↻ Regenerar", key="btn_tab4_comite_ia_forzar", width="stretch",
                    disabled=not _tiene_base,
                    help="Ignora el dictamen guardado: vuelve a llamar a la IA aunque los insumos no hayan cambiado.",
                )
            if _btn_gen or _btn_forzar:
                with st.spinner("Paso 1: reuniendo hechos de mercado · Paso 2: el comité redacta el dictamen…"):
                    _ok_c, _msg_c = _ejecutar_comite_ia_sesion(
                        empresa, w=w, de_ratio=de_ratio, g=g, moneda=moneda, forzar=bool(_btn_forzar),
                    )
                if not _ok_c:
                    st.error(_msg_c)
                elif "reutilizado" in str(_msg_c):
                    st.info(_msg_c)
            _aud = st.session_state.get("tab4_comite_ia_auditoria") or {}
            if _aud.get("warnings") and st.session_state.get("tab4_comite_ia_html"):
                with st.expander("Advertencias de la auditoría previa", expanded=False):
                    for _wmsg in _aud["warnings"]:
                        st.markdown(f"- {_wmsg}")

            if st.session_state.get("tab4_comite_ia_html") and st.session_state.get("tab4_comite_empresa") == empresa:
                st.markdown("###### Dictamen del comité")
                _html(st.session_state["tab4_comite_ia_html"])
                _res_c = st.session_state.get("tab4_comite_ia_res") or {}
                _aud_d = _res_c.get("auditoria") or {}
                if _aud_d.get("warnings"):
                    with st.expander("Observaciones de la auditoría del dictamen", expanded=False):
                        for _wmsg in _aud_d["warnings"]:
                            st.markdown(f"- {_wmsg}")
                _explain(
                    "<b>Uso:</b> dictamen IA anclado en el modelo y en hechos con fuente. "
                    "No es asesoría de inversión ni orden de compra/venta."
                )

            # Historial de dictámenes de la sesión (comparación con el anterior + descarga)
            _hist = L.comite_historial(empresa) if hasattr(L, "comite_historial") else []
            if _hist:
                with st.expander(f"Historial de dictámenes de esta sesión ({len(_hist)})", expanded=False):
                    _df_h = pd.DataFrame([{
                        "Fecha": h.get("fecha"), "Recomendación": h.get("recomendacion"),
                        "Objetivo 12 m": h.get("precio_objetivo"), "Precio": h.get("precio_mercado"),
                        "VPS modelo": h.get("vps_modelo"),
                        "WACC (%)": (h["wacc"] * 100 if h.get("wacc") is not None else None),
                        "Convicción": h.get("conviccion"), "Hechos web": h.get("hechos_web"),
                        "Proveedor": h.get("proveedor"),
                    } for h in reversed(_hist)])
                    st.dataframe(_df_h, width="stretch", hide_index=True)
                    if len(_hist) >= 2:
                        _a, _b = _hist[-2], _hist[-1]
                        _cambios = []
                        if _a.get("recomendacion") != _b.get("recomendacion"):
                            _cambios.append(f"recomendación {_a.get('recomendacion')} → {_b.get('recomendacion')}")
                        if _a.get("precio_objetivo") and _b.get("precio_objetivo"):
                            _cambios.append(
                                f"objetivo {_a['precio_objetivo']:,.2f} → {_b['precio_objetivo']:,.2f} "
                                f"({(_b['precio_objetivo'] / _a['precio_objetivo'] - 1) * 100:+.1f} %)")
                        if _a.get("wacc") and _b.get("wacc") and abs(_a["wacc"] - _b["wacc"]) > 1e-6:
                            _cambios.append(f"WACC {_a['wacc'] * 100:.2f} % → {_b['wacc'] * 100:.2f} %")
                        st.caption("Frente al dictamen anterior: " + ("; ".join(_cambios) if _cambios else "sin cambios materiales."))
                    st.download_button(
                        "⬇ Descargar historial (JSON)",
                        json.dumps(_hist, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                        file_name="historial_comite_ia.json", mime="application/json",
                        key="dl_hist_comite_ia",
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
            if st.button("↻ Consultar mercado y contrastar VPS", key="btn_contraste_mercado", width="stretch"):
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
                    # No asumir que la cotización comparte moneda con el modelo si el proveedor no la informa.
                    _market_currency = (
                        st.session_state.get("moneda_precio_alineada")
                        or _market.get("moneda")
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
                            width="stretch",
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

    with tab8:
        st.markdown("##### Optimización de portafolios")
        st.caption(
            "MVP cuantitativo: usa rendimientos históricos ajustados para estimar riesgo y retorno. "
            "No convierte automáticamente el upside del DCF en rendimiento esperado."
        )
        st.caption(
            "Universos con activos en COP (BVC) y USD se convierten a la moneda de análisis "
            "con la serie diaria COP/USD (Yahoo COP=X), fecha a fecha: el riesgo cambiario "
            "queda incluido en los retornos. Otras monedas se bloquean."
        )
        # Vincula el portafolio a la empresa seleccionada en el modelo, sin convertir
        # el upside del DCF en retorno esperado estadístico.
        _portfolio_empresa_actual = (
            st.session_state.get("empresa_sel")
            or st.session_state.get("select_empresa")
            or ""
        )
        _portfolio_params_actuales = st.session_state.get("params") or {}
        _portfolio_ticker_actual = (
            _portfolio_params_actuales.get("ticker_yf")
            or _portfolio_params_actuales.get("ticker_bvc")
        )
        if not _portfolio_ticker_actual and _portfolio_empresa_actual:
            try:
                _portfolio_emp_resuelta = L.resolver_empresa(_portfolio_empresa_actual) or {}
                _portfolio_ticker_actual = (
                    _portfolio_emp_resuelta.get("ticker_yf")
                    or _portfolio_emp_resuelta.get("ticker_bvc")
                )
            except Exception:
                _portfolio_ticker_actual = None
        _portfolio_ticker_actual = str(_portfolio_ticker_actual or "").strip().upper() or None
        _portfolio_incluir_empresa = st.checkbox(
            "Incluir automáticamente la empresa que estoy valorando"
            + (f" ({_portfolio_ticker_actual})" if _portfolio_ticker_actual else " (sin ticker disponible)"),
            value=True,
            key="portfolio_include_valued_company",
            disabled=not bool(_portfolio_ticker_actual),
            help="Añade el ticker de la empresa seleccionada al universo que se optimiza. La valoración DCF se presenta como señal independiente; no se transforma en retorno esperado.",
        )
        _ptickers_text = st.text_input("Otros tickers del universo, separados por coma", value="", placeholder="Ej.: MSFT,NVDA", key="portfolio_tickers")
        if _portfolio_ticker_actual:
            st.caption(
                f"Empresa seleccionada para valoración: **{_portfolio_empresa_actual}** · "
                f"ticker detectado: **{_portfolio_ticker_actual}**. "
                "Escribe aquí otros activos para diversificar; si incluyes la empresa valorada, "
                "solo necesitas añadir al menos otro ticker."
            )
        else:
            st.caption(
                "No se detectó ticker para la empresa seleccionada: introduce al menos dos tickers "
                "manualmente o corrige el ticker en la ficha de la empresa."
            )
        _pmax = st.slider(
            "Peso máximo por activo", min_value=0.10, max_value=1.00,
            value=0.60, step=0.05, key="portfolio_max_weight",
        )
        _pobjective = st.selectbox(
            "Objetivo de optimización", ["max_sharpe", "min_volatility"],
            format_func=lambda x: "Maximizar Sharpe" if x == "max_sharpe" else "Minimizar volatilidad",
            key="portfolio_objective",
        )
        _pmodo_ret = st.radio(
            "Retorno esperado de cada activo",
            ["Anclado en riesgo y precio (recomendado)", "Media histórica de la ventana"],
            key="portfolio_modo_retorno", horizontal=True,
            help="Anclado: CAPM de cada activo en su mercado (rf + β × ERP de Damodaran) o, para la empresa valorada, "
                 "el costo del patrimonio que implica su precio; la media histórica entra con el peso que merece su "
                 "precisión. Con 5 años de datos, el error estándar de una media anual es de ±11–16 pp.",
        )
        _pperiod = st.selectbox("Ventana histórica", ["2y", "5y", "10y"], index=1, key="portfolio_period")
        _pbase = st.selectbox(
            "Moneda de análisis", ["USD", "COP"], key="portfolio_base_currency",
            help="Todas las series se expresan en esta moneda antes de calcular retornos y covarianzas.",
        )
        # La tasa libre de riesgo del Sharpe debe estar en la MISMA moneda que los
        # retornos: antes era 4 % fijo también para carteras en COP (TES ~13 %),
        # lo que inflaba el Sharpe y sesgaba la cartera óptima hacia activos COP.
        _rf_def = float(L.CAPM_POR_MERCADO["CO" if _pbase == "COP" else "US"]["rf"])
        _prf = st.number_input(
            f"Tasa libre de riesgo anual en {_pbase} (decimal)", min_value=0.0, max_value=0.50,
            value=_rf_def, step=0.005, format="%.3f", key=f"portfolio_rf_{_pbase}",
            help="Por defecto: bono soberano a 10 años de la moneda de análisis (UST en USD, TES en COP).",
        )

        def _norm_tk_portafolio(x):
            # .CL solo para nemotécnicos BVC del catálogo (NUTRESA → NUTRESA.CL; AAPL intacto).
            x = x.strip().upper()
            try:
                return L.asegurar_sufijo_cl_bvc(x) or x
            except Exception:
                return x

        _portfolio_tickers_manual = tuple(dict.fromkeys(
            _norm_tk_portafolio(x) for x in _ptickers_text.split(",") if x.strip()
        ))
        _portfolio_tickers_final = list(_portfolio_tickers_manual)
        if _portfolio_incluir_empresa and _portfolio_ticker_actual:
            if _portfolio_ticker_actual not in _portfolio_tickers_final:
                _portfolio_tickers_final.insert(0, _portfolio_ticker_actual)
        _portfolio_request = (
            tuple(_portfolio_tickers_final), float(_prf), float(_pmax),
            _pobjective, _pperiod, _pbase, bool(_portfolio_incluir_empresa),
            _portfolio_empresa_actual, _portfolio_ticker_actual,
        )
        if st.button("Optimizar portafolio", key="portfolio_run", type="primary"):
            try:
                import yfinance as _yf
                from portfolio_engine import (
                    preparar_estadisticas as _prep_portfolio,
                    optimizar_portafolio as _opt_portfolio,
                    construir_frontera as _frontier_portfolio,
                    convertir_a_moneda_comun as _fx_portfolio,
                    rendimientos_comunes as _rets_portfolio,
                    metricas_riesgo_historicas as _riesgo_portfolio,
                    retornos_esperados_anclados as _anclar_portfolio,
                    retorno_en_moneda as _fisher_portfolio,
                    evaluar_fuera_de_muestra as _oos_portfolio,
                )
                _ptickers = list(_portfolio_tickers_final)
                if len(_ptickers) < 2:
                    raise ValueError("Introduce al menos dos tickers distintos.")
                _meta, _betas_yf = {}, {}
                for _ticker in _ptickers:
                    try:
                        _info = _yf.Ticker(_ticker).get_info() or {}
                        _meta[_ticker] = _info.get("currency")
                        _betas_yf[_ticker] = L.beta_para_capm(dict(_info, symbol=_ticker))
                    except Exception:
                        _meta[_ticker] = None
                _currencies = {str(v).upper() for v in _meta.values() if v}
                if any(not v for v in _meta.values()):
                    raise ValueError("No se pudo confirmar la moneda de todos los activos; optimización bloqueada.")
                _download = _yf.download(
                    _ptickers, period=_pperiod, interval="1d", auto_adjust=True,
                    progress=False, group_by="column", threads=True,
                )
                if _download is None or _download.empty:
                    raise ValueError("El proveedor no devolvió precios.")
                if isinstance(_download.columns, pd.MultiIndex):
                    if "Close" in _download.columns.get_level_values(0):
                        _prices = _download["Close"]
                    elif "Close" in _download.columns.get_level_values(1):
                        _prices = _download.xs("Close", axis=1, level=1)
                    else:
                        raise ValueError("No se encontró la columna de precios ajustados.")
                else:
                    if "Close" not in _download.columns:
                        raise ValueError("No se encontró la columna Close.")
                    _prices = _download[["Close"]].rename(columns={"Close": _ptickers[0]})
                if isinstance(_prices, pd.Series):
                    _prices = _prices.to_frame(name=_ptickers[0])
                _prices = _prices.dropna(axis=1, how="all")
                _missing_tickers = sorted(set(_ptickers) - set(map(str, _prices.columns)))
                if _missing_tickers:
                    raise ValueError("No hay precios descargables para: " + ", ".join(_missing_tickers))
                _fx_series = None
                if any(str(v).upper() != _pbase for v in _meta.values()):
                    _fx_series = _serie_cop_por_usd("10y" if _pperiod == "10y" else "5y")
                _prices = _fx_portfolio(_prices, _meta, _fx_series, moneda_base=_pbase)
                _mu, _cov = _prep_portfolio(_prices)
                _mu_tabla = None
                if _pmodo_ret.startswith("Anclado"):
                    _anios_ventana = len(_rets_portfolio(_prices)) / 252.0
                    _merc_base = L.MERCADO_POR_MONEDA.get(_pbase, "US")
                    _anclas, _fuentes_ancla = {}, {}
                    for _tk in _mu.index:
                        _cur = str(_meta.get(_tk) or _pbase).upper()
                        _merc = L.MERCADO_POR_MONEDA.get(_cur, "US")
                        _cap = L.CAPM_POR_MERCADO.get(_merc, L.CAPM_POR_MERCADO["DEFAULT"])
                        _r_loc, _fte = None, None
                        if _portfolio_incluir_empresa and _tk == _portfolio_ticker_actual:
                            try:  # costo del patrimonio que implica el precio (DCF inverso de la pestaña 4)
                                _m4 = L.metricas_valoracion_sesion(_portfolio_empresa_actual) or {}
                                _wi, _wc, _ke = _m4.get("wacc_implicito_mercado"), _m4.get("wacc_calc"), _m4.get("ke_calc")
                                _de = float(_m4.get("de_ratio") or 0.0)
                                if None not in (_wi, _wc, _ke):
                                    _r_loc = float(_ke) + (float(_wi) - float(_wc)) * (1.0 + _de)
                                    _fte = "costo del patrimonio implícito en el precio (DCF inverso)"
                                    _merc = L.MERCADO_POR_MONEDA.get(str(_m4.get("moneda") or _cur).upper(), _merc)
                            except Exception:
                                _r_loc = None
                        if _r_loc is None:
                            _b, _bf = _betas_yf.get(_tk) or (1.0, "β 1,00 de mercado")
                            _r_loc = float(_cap["rf"]) + float(_b) * float(_cap["erp"]) + float(_cap.get("crp", 0.0))
                            _fte = f"CAPM {_merc}: rf {_cap['rf']:.2%} + {_bf} × ERP {_cap['erp']:.2%}"
                            if _portfolio_incluir_empresa and _tk == _portfolio_ticker_actual:
                                _fte += " (sin valoración vigente de la empresa: ejecuta «Generar todo» para usar su precio)"
                        if _merc != _merc_base:
                            _r_loc = _fisher_portfolio(_r_loc, L.INFLACION_LP.get(_merc, L.INFLACION_LP["US"]),
                                                       L.INFLACION_LP.get(_merc_base, L.INFLACION_LP["US"]))
                            _fte += f" · llevado a {_pbase} por inflación"
                        _anclas[_tk], _fuentes_ancla[_tk] = _r_loc, _fte
                    _vol_activos = pd.Series(np.sqrt(np.diag(_cov.to_numpy())), index=_cov.index)
                    _mu_tabla = _anclar_portfolio(_mu, _vol_activos, _anios_ventana, pd.Series(_anclas))
                    _mu_tabla["fuente_ancla"] = pd.Series(_fuentes_ancla)
                    _mu = _mu_tabla["esperado"]
                # Recuperar señal DCF de la empresa focal solo como contexto de valoración.
                # No se mezcla con la media histórica de retornos del optimizador.
                _focal_valuation = {}
                if _portfolio_incluir_empresa and _portfolio_ticker_actual:
                    try:
                        _focal_valuation = L._metricas_comite_para_ia(_portfolio_empresa_actual) or {}
                    except Exception as _valuation_context_error:
                        _focal_valuation = {"error": str(_valuation_context_error)}
                _res = _opt_portfolio(
                    _mu, _cov, objetivo=_pobjective,
                    tasa_libre_riesgo=float(_prf), peso_maximo=float(_pmax),
                )
                try:
                    _riesgo = _riesgo_portfolio(_rets_portfolio(_prices), _res["pesos"])
                except Exception as _e_riesgo:
                    _riesgo = {"error": str(_e_riesgo)}
                _riesgo["contraccion_alpha"] = float(getattr(_cov, "attrs", {}).get("contraccion_alpha", 0.0))
                try:
                    _oos = _oos_portfolio(_prices, 0.7, mu_fijo=(_mu if _mu_tabla is not None else None),
                                          objetivo=_pobjective, tasa_libre_riesgo=float(_prf), peso_maximo=float(_pmax))
                    _oos = {"corte": _oos["corte"], "dentro": _oos["dentro"], "fuera": _oos["fuera"]}
                except Exception as _e_oos:
                    _oos = {"error": str(_e_oos)}
                _frontier = _frontier_portfolio(
                    _mu, _cov, tasa_libre_riesgo=float(_prf),
                    peso_maximo=float(_pmax), n_puntos=20,
                )
                st.session_state["portfolio_result"] = {
                    "weights": _res["pesos"].to_dict(),
                    "return": _res["retorno_esperado"],
                    "volatility": _res["volatilidad"],
                    "sharpe": _res["sharpe"],
                    "riesgo": _riesgo,
                    "fuera_de_muestra": _oos,
                    "modo_retorno": _pmodo_ret,
                    "mu_tabla": (_mu_tabla.reset_index().rename(columns={"index": "Activo"}).to_dict(orient="records")
                                 if _mu_tabla is not None else None),
                    "currency": _pbase,
                    "monedas_origen": dict(_meta),
                    "period": _pperiod,
                    "frontier": _frontier.to_dict(orient="records"),
                    "prices_last_date": str(_prices.dropna().index[-1]),
                    "request": _portfolio_request,
                    "focal_company": _portfolio_empresa_actual if _portfolio_incluir_empresa else None,
                    "focal_ticker": _portfolio_ticker_actual if _portfolio_incluir_empresa else None,
                    "focal_valuation": _focal_valuation,
                }
            except Exception as _portfolio_error:
                st.session_state.pop("portfolio_result", None)
                st.error(f"No se pudo optimizar el portafolio: {_portfolio_error}")

        _portfolio_saved = st.session_state.get("portfolio_result")
        if _portfolio_saved and _portfolio_saved.get("request") != _portfolio_request:
            _portfolio_saved = None
            st.info("Los parámetros de cartera cambiaron. Pulsa **Optimizar portafolio** para actualizar los resultados.")
        if _portfolio_saved:
            st.caption(
                f"Moneda de análisis: {_portfolio_saved['currency']} "
                f"(origen: {', '.join(f'{k} {v}' for k, v in (_portfolio_saved.get('monedas_origen') or {}).items())}) · "
                f"Ventana: {_portfolio_saved['period']} · "
                f"Última fecha de datos: {_portfolio_saved['prices_last_date']}"
            )
            _pc1, _pc2, _pc3 = st.columns(3)
            _pc1.metric("Retorno esperado anualizado", f"{_portfolio_saved['return']:.2%}")
            _pc2.metric("Volatilidad anualizada", f"{_portfolio_saved['volatility']:.2%}")
            _psharpe = _portfolio_saved["sharpe"]
            _pc3.metric("Sharpe estimado", f"{_psharpe:.2f}" if _psharpe is not None else "N/D")
            _rz = _portfolio_saved.get("riesgo") or {}
            if _rz and not _rz.get("error"):
                _rc1, _rc2, _rc3, _rc4 = st.columns(4)
                _rc1.metric("Caída máxima histórica", f"{_rz['max_drawdown']:.1%}",
                            help="Mayor caída del capital desde un pico, con estos pesos en la ventana elegida.")
                _rc2.metric(f"VaR diario {_rz['confianza']:.0%}", f"{_rz['var_diario']:.2%}",
                            help="En el 95 % de los días históricos la pérdida diaria no superó este valor.")
                _rc3.metric(f"CVaR diario {_rz['confianza']:.0%}",
                            f"{_rz['cvar_diario']:.2%}" if _rz.get("cvar_diario") is not None else "N/D",
                            help="Pérdida diaria promedio en el 5 % de los peores días (pérdida de cola).")
                _rc4.metric("Rendimiento compuesto anual",
                            f"{_rz['retorno_compuesto_anual']:.2%}" if _rz.get("retorno_compuesto_anual") is not None else "N/D",
                            help="Lo que creció el capital por año con estos pesos. El «retorno esperado» de arriba es la "
                                 "media aritmética que usa el optimizador; con volatilidad, el compuesto es menor.")
                _mt = _portfolio_saved.get("mu_tabla")
                if _mt:
                    st.markdown("###### Retorno esperado por activo")
                    _mtd = pd.DataFrame(_mt)
                    _col0 = _mtd.columns[0]
                    st.dataframe(pd.DataFrame({
                        "Activo": _mtd[_col0],
                        "Media histórica": (_mtd["historico"] * 100).map("{:.1f} %".format),
                        "Error estándar": (_mtd["error_estandar"] * 100).map("± {:.1f} pp".format),
                        "Ancla": (_mtd["ancla"] * 100).map("{:.1f} %".format),
                        "Peso del histórico": (_mtd["peso_historico"] * 100).map("{:.0f} %".format),
                        "Esperado": (_mtd["esperado"] * 100).map("{:.1f} %".format),
                        "Fuente del ancla": _mtd["fuente_ancla"],
                    }), width="stretch", hide_index=True)
                _oos = _portfolio_saved.get("fuera_de_muestra") or {}
                if _oos.get("dentro"):
                    st.markdown("###### Prueba fuera de muestra")
                    st.caption(f"Pesos elegidos con los datos hasta {_oos['corte']} (70 % de la ventana) y medidos en el 30 % "
                               "que el optimizador no vio. Si el resultado de fuera es mucho peor, el de arriba es sobreajuste.")
                    _fm = lambda d: [f"{d['retorno_compuesto_anual']:.1%}", f"{d['max_drawdown']:.1%}", f"{d['var_diario']:.2%}",
                                     f"{d['cvar_diario']:.2%}" if d.get("cvar_diario") is not None else "N/D"]
                    st.dataframe(pd.DataFrame([_fm(_oos["dentro"]), _fm(_oos["fuera"])],
                                              index=["Dentro de la muestra", "Fuera de la muestra"],
                                              columns=["Rend. compuesto anual", "Caída máxima", "VaR diario 95 %", "CVaR diario 95 %"]),
                                 width="stretch")
                elif _oos.get("error"):
                    st.caption(f"Prueba fuera de muestra no disponible: {_oos['error']}")
                st.caption(
                    f"Covarianza con contracción de Ledoit-Wolf (α = {_rz.get('contraccion_alpha', 0):.2f}): reduce el ruido "
                    "de las correlaciones históricas. Todas las cifras describen el pasado (pesos actuales aplicados "
                    "a toda la ventana) y no garantizan pérdidas ni rendimientos futuros."
                )
            st.markdown("###### Pesos sugeridos por el optimizador")
            _weights_df = pd.DataFrame.from_dict(_portfolio_saved["weights"], orient="index", columns=["Peso"])
            _weights_df["Peso (%)"] = _weights_df["Peso"] * 100
            st.dataframe(_weights_df[["Peso (%)"]], width="stretch")
            st.markdown("###### Frontera eficiente aproximada")
            _frontier_df = pd.DataFrame(_portfolio_saved["frontier"])
            if not _frontier_df.empty:
                st.line_chart(
                    _frontier_df.sort_values("Volatilidad").set_index("Volatilidad")[["Retorno esperado"]],
                    width="stretch",
                )
            _focal_ticker = _portfolio_saved.get("focal_ticker")
            _focal_company = _portfolio_saved.get("focal_company")
            _focal_metrics = _portfolio_saved.get("focal_valuation") or {}
            if _focal_ticker:
                st.markdown("###### Recomendación integrada para la empresa valorada")
                _focal_weight = _portfolio_saved["weights"].get(_focal_ticker)
                _focal_upside = _focal_metrics.get("upside")
                _focal_price = _focal_metrics.get("precio_mercado")
                _focal_vps = _focal_metrics.get("vps_modelo")
                _focal_currency = _focal_metrics.get("moneda") or _portfolio_saved.get("currency") or "N/D"
                _focal_c1, _focal_c2, _focal_c3 = st.columns(3)
                _focal_c1.metric(
                    "Peso sugerido en cartera",
                    f"{_focal_weight:.1%}" if _focal_weight is not None else "0.0%",
                )
                _focal_c2.metric(
                    "Upside del modelo DCF",
                    f"{float(_focal_upside):+.1f}%" if isinstance(_focal_upside, (int, float)) else "N/D",
                )
                _focal_c3.metric(
                    "Precio / valor por acción",
                    (
                        f"{float(_focal_price):,.2f} / {float(_focal_vps):,.2f} {_focal_currency}"
                        if isinstance(_focal_price, (int, float)) and isinstance(_focal_vps, (int, float))
                        else "N/D"
                    ),
                )
                if _focal_weight is None:
                    st.warning(
                        f"{_focal_company} ({_focal_ticker}) no recibió peso en la solución óptima. "
                        "No lo interpretes como una recomendación de venta: depende del objetivo, "
                        "de la ventana histórica y de los límites de peso."
                    )
                elif isinstance(_focal_upside, (int, float)):
                    if _focal_upside > 0:
                        st.success(
                            f"{_focal_company}: el modelo DCF estima upside positivo y el optimizador "
                            f"asigna {_focal_weight:.1%}. Contrasta ambas señales con escenarios y calidad de datos."
                        )
                    elif _focal_upside < 0:
                        st.warning(
                            f"{_focal_company}: el modelo DCF estima downside y el optimizador asigna "
                            f"{_focal_weight:.1%} por su perfil histórico de riesgo/retorno. Revisa si "
                            "conviene excluirla o limitar su peso y vuelve a optimizar."
                        )
                    else:
                        st.info(
                            f"{_focal_company}: el DCF no muestra upside ni downside material; "
                            f"el peso histórico optimizado es {_focal_weight:.1%}."
                        )
                else:
                    st.info(
                        f"El peso de {_focal_company} se estima con datos históricos. No se pudo "
                        "obtener una señal DCF válida para complementar la recomendación."
                    )
                st.caption(
                    "La señal DCF es contexto de valoración, no un pronóstico de retorno. "
                    "El peso sugerido sigue dependiendo de rendimientos y covarianzas históricos."
                )
            st.caption(
                "Retornos históricos anualizados, no pronósticos. Los precios se convierten a la moneda de análisis "
                "con la tasa de cambio de cada día. No se incluyen impuestos, costos de transacción ni liquidez. "
                "No es asesoría de inversión."
            )


    with tab9:
        st.markdown("##### Simulador de inversión")
        st.caption(
            "Estima cuánto podría valer una inversión en la empresa seleccionada bajo tres escenarios. "
            "Los escenarios son supuestos editables, no pronósticos ni garantías."
        )
        _sim_empresa = (
            st.session_state.get("empresa_sel")
            or st.session_state.get("select_empresa")
            or ""
        )
        _sim_params = st.session_state.get("params") or {}
        # Resolver siempre el ticker de la empresa actualmente seleccionada.
        # No tomar params de una empresa anterior como fuente principal.
        try:
            _sim_ticker = _inferir_ticker_yf(_sim_empresa, _sim_params)
        except Exception:
            _sim_ticker = None
        _sim_ticker = str(_sim_ticker or "").strip().upper()

        # Streamlit conserva el valor de un widget por su key. Al usar una key
        # específica de la empresa, el ticker manual anterior no contamina la
        # nueva selección y el valor sugerido se actualiza al cambiar de empresa.
        _sim_empresa_key = "".join(
            ch.lower() if ch.isalnum() else "_"
            for ch in str(_sim_empresa or "sin_empresa")
        ).strip("_") or "sin_empresa"
        _sim_ticker_key = f"investment_sim_ticker_{_sim_empresa_key}"
        if _sim_ticker_key not in st.session_state:
            st.session_state[_sim_ticker_key] = _sim_ticker
        _sim_ticker = st.text_input(
            "Ticker de la empresa",
            key=_sim_ticker_key,
            help="Se propone el ticker de la empresa valorada. Puedes corregirlo; cada empresa conserva su propio ticker.",
        ).strip().upper()
        try:
            # .CL solo para nemotécnicos BVC (NUTRESA → NUTRESA.CL; TSLA intacto).
            _sim_ticker = L.asegurar_sufijo_cl_bvc(_sim_ticker) or _sim_ticker
        except Exception:
            pass
        _sim_c1, _sim_c2, _sim_c3 = st.columns(3)
        with _sim_c1:
            _sim_capital = st.number_input(
                "Capital disponible", min_value=1.0, value=10000000.0, step=1000000.0,
                format="%.2f", key="investment_sim_capital",
            )
            _sim_cap_currency = st.selectbox(
                "Moneda de tu capital", ["COP", "USD"], key="investment_sim_cap_currency"
            )
        with _sim_c2:
            _sim_years = st.selectbox(
                "Horizonte de inversión", [1, 2, 3, 5, 10], index=2,
                format_func=lambda x: f"{x} año" if x == 1 else f"{x} años",
                key="investment_sim_years",
            )
            _sim_div_yield = st.number_input(
                "Dividendos anuales estimados (%)", min_value=0.0, max_value=30.0,
                value=2.0, step=0.5, key="investment_sim_dividend",
            )
        with _sim_c3:
            _sim_buy_fee = st.number_input(
                "Costo de compra (%)", min_value=0.0, max_value=10.0, value=0.2,
                step=0.1, key="investment_sim_buy_fee",
            )
            _sim_sell_fee = st.number_input(
                "Costo de venta (%)", min_value=0.0, max_value=10.0, value=0.2,
                step=0.1, key="investment_sim_sell_fee",
            )
            _sim_div_tax = st.number_input(
                "Retención sobre dividendos (%)", min_value=0.0, max_value=100.0,
                value=0.0, step=1.0, key="investment_sim_div_tax",
            )
        st.markdown("###### Supuestos de valorización anual")
        _sim_s1, _sim_s2, _sim_s3 = st.columns(3)
        with _sim_s1:
            _sim_bear = st.number_input(
                "Pesimista (%)", min_value=-90.0, max_value=100.0, value=-15.0,
                step=1.0, key="investment_sim_bear",
            )
        with _sim_s2:
            _sim_base = st.number_input(
                "Base (%)", min_value=-90.0, max_value=100.0, value=8.0,
                step=1.0, key="investment_sim_base",
            )
        with _sim_s3:
            _sim_bull = st.number_input(
                "Optimista (%)", min_value=-90.0, max_value=100.0, value=18.0,
                step=1.0, key="investment_sim_bull",
            )
        _fx_spot = _tasa_cop_usd_spot()
        _sim_fx = st.number_input(
            "Tasa de cambio COP por USD (solo si las monedas difieren)",
            min_value=0.0001, value=float(round(_fx_spot, 2)) if _fx_spot else 4000.0, step=50.0, format="%.4f",
            key="investment_sim_fx",
            help="Se usa para convertir el capital y el resultado a la moneda original. Se supone constante durante el horizonte; no modela riesgo cambiario.",
        )
        _sim_run = st.button(
            "Simular inversión", type="primary", key="investment_sim_run",
            width="stretch",
        )
        if _sim_run:
            try:
                if not _sim_ticker:
                    raise ValueError("Selecciona una empresa con ticker o escribe el ticker manualmente.")
                import yfinance as _sim_yf
                _sim_asset = _sim_yf.Ticker(_sim_ticker)
                _sim_info = _sim_asset.get_info() or {}
                _sim_currency = str(_sim_info.get("currency") or "").upper()
                _sim_market_price = _sim_info.get("currentPrice") or _sim_info.get("regularMarketPrice")
                _sim_hist = _sim_asset.history(period="5d", auto_adjust=True)
                if (_sim_market_price is None or not np.isfinite(float(_sim_market_price)) or float(_sim_market_price) <= 0) and not _sim_hist.empty:
                    _sim_market_price = float(_sim_hist["Close"].dropna().iloc[-1])
                if not _sim_currency:
                    raise ValueError("El proveedor no confirmó la moneda del activo; no se puede simular con seguridad.")
                if _sim_market_price is None or not np.isfinite(float(_sim_market_price)) or float(_sim_market_price) <= 0:
                    raise ValueError("No se pudo obtener un precio de mercado válido para el ticker.")
                _sim_market_price = float(_sim_market_price)
                # Consistencia cruzada: si el ticker es el de la empresa valorada, usar
                # la MISMA instantánea de precio que la cabecera y las pestañas 2/4/7.
                try:
                    _snap_sim = L.instantanea_precio_mercado(_sim_empresa) if _sim_empresa else {}
                    if (
                        _snap_sim.get("precio")
                        and str(_snap_sim.get("ticker") or "").upper() == _sim_ticker
                        and str(_snap_sim.get("moneda") or _sim_currency).upper() == _sim_currency
                    ):
                        _sim_market_price = float(_snap_sim["precio"])
                except Exception:
                    pass
                _sim_dcf = {}
                if _sim_empresa:
                    try:
                        _sim_dcf = L._metricas_comite_para_ia(_sim_empresa) or {}
                    except Exception:
                        _sim_dcf = {}
                from investment_simulator import simular_inversion as _simular_inversion
                _sim_result = _simular_inversion(
                    capital=float(_sim_capital),
                    moneda_capital=_sim_cap_currency,
                    moneda_activo=_sim_currency,
                    tasa_cop_usd=float(_sim_fx),
                    precio_actual=_sim_market_price,
                    horizonte=int(_sim_years),
                    escenarios={
                        "Pesimista": float(_sim_bear) / 100.0,
                        "Base": float(_sim_base) / 100.0,
                        "Optimista": float(_sim_bull) / 100.0,
                    },
                    dividend_yield=float(_sim_div_yield) / 100.0,
                    costo_compra=float(_sim_buy_fee) / 100.0,
                    costo_venta=float(_sim_sell_fee) / 100.0,
                    impuesto_dividendos=float(_sim_div_tax) / 100.0,
                )
                st.session_state["investment_sim_result"] = {
                    "request": (
                        _sim_ticker, float(_sim_capital), _sim_cap_currency, int(_sim_years),
                        float(_sim_bear), float(_sim_base), float(_sim_bull),
                        float(_sim_div_yield), float(_sim_buy_fee), float(_sim_sell_fee),
                        float(_sim_div_tax), float(_sim_fx), _sim_currency, _sim_market_price,
                    ),
                    "ticker": _sim_ticker,
                    "empresa": _sim_empresa or _sim_ticker,
                    "moneda_activo": _sim_currency,
                    "precio": _sim_market_price,
                    "fecha_precio": str(_sim_hist.index[-1].date()) if not _sim_hist.empty else "N/D",
                    "dcf": _sim_dcf,
                    "result": _sim_result,
                }
            except Exception as _sim_error:
                st.session_state.pop("investment_sim_result", None)
                st.error(f"No se pudo simular la inversión: {_sim_error}")

        _sim_saved = st.session_state.get("investment_sim_result")
        _sim_current_request = (
            _sim_ticker, float(_sim_capital), _sim_cap_currency, int(_sim_years),
            float(_sim_bear), float(_sim_base), float(_sim_bull),
            float(_sim_div_yield), float(_sim_buy_fee), float(_sim_sell_fee),
            float(_sim_div_tax), float(_sim_fx),
        )
        if _sim_saved and _sim_saved["request"][:12] != _sim_current_request:
            _sim_saved = None
            st.info("Cambiaste uno o más supuestos. Pulsa **Simular inversión** para recalcular.")
        if _sim_saved:
            _sim_res = _sim_saved["result"]
            _sim_fmt = lambda x, cur: f"{cur} {x:,.2f}"
            st.caption(
                f"Activo: {_sim_saved['empresa']} ({_sim_saved['ticker']}) · "
                f"Precio de referencia: {_sim_fmt(_sim_saved['precio'], _sim_saved['moneda_activo'])} · "
                f"Moneda del activo: {_sim_saved['moneda_activo']} · "
                f"Fecha de precio: {_sim_saved['fecha_precio']}"
            )
            if _sim_cap_currency != _sim_saved["moneda_activo"]:
                st.info(
                    f"Capital convertido a {_sim_saved['moneda_activo']} y resultado convertido de vuelta a "
                    f"{_sim_cap_currency} usando {_sim_fx:,.2f} COP/USD constante. El resultado real también "
                    "dependerá del tipo de cambio futuro."
                )
            _sim_summary = _sim_res["resumen"]
            _sm1, _sm2, _sm3, _sm4 = st.columns(4)
            _sm1.metric("Acciones comprables", f"{_sim_summary['acciones']:,}")
            _sm2.metric("Efectivo residual", _sim_fmt(_sim_summary["efectivo_residual"], _sim_saved["moneda_activo"]))
            _sim_base_row = _sim_summary["escenarios"]["Base"]
            _sm3.metric(
                "Valor final · escenario base",
                _sim_fmt(_sim_base_row["valor_final"], _sim_cap_currency),
            )
            _sm4.metric(
                "Ganancia / pérdida · base",
                _sim_fmt(_sim_base_row["ganancia_neta"], _sim_cap_currency),
                delta=f"{_sim_base_row['rentabilidad_total']:.2%}",
            )
            _sim_chart = pd.DataFrame(_sim_res["trayectoria"])
            if not _sim_chart.empty:
                st.markdown("###### Evolución estimada del capital")
                st.line_chart(_sim_chart.set_index("Año"), width="stretch")
            st.markdown("###### Comparación de escenarios")
            _sim_rows = []
            for _sim_name, _sim_values in _sim_summary["escenarios"].items():
                _sim_rows.append({
                    "Escenario": _sim_name,
                    "Valor final": _sim_fmt(_sim_values["valor_final"], _sim_cap_currency),
                    "Ganancia / pérdida": _sim_fmt(_sim_values["ganancia_neta"], _sim_cap_currency),
                    "Rentabilidad acumulada": f"{_sim_values['rentabilidad_total']:.2%}",
                    "Rentabilidad anualizada": f"{_sim_values['rentabilidad_anualizada']:.2%}",
                })
            st.dataframe(pd.DataFrame(_sim_rows), hide_index=True, width="stretch")
            _sim_upside = (_sim_saved.get("dcf") or {}).get("upside")
            if isinstance(_sim_upside, (int, float)):
                st.markdown("###### Contraste con la valoración de la empresa")
                st.metric("Upside estimado por DCF", f"{float(_sim_upside):+.2f}%")
                st.caption(
                    "El upside del DCF se muestra solo como referencia independiente. No se usa como "
                    "rentabilidad futura garantizada ni reemplaza los escenarios editables."
                )
            _sim_base = _sim_summary["escenarios"]["Base"]
            if _sim_base["ganancia_neta"] > 0:
                st.success(
                    f"Bajo el escenario base, el capital terminaría en "
                    f"{_sim_fmt(_sim_base['valor_final'], _sim_cap_currency)}, equivalente a una "
                    f"rentabilidad acumulada de {_sim_base['rentabilidad_total']:.2%}. "
                    "Es una simulación condicionada a los supuestos ingresados."
                )
            elif _sim_base["ganancia_neta"] < 0:
                st.warning(
                    f"Bajo el escenario base, se produciría una pérdida estimada de "
                    f"{_sim_fmt(abs(_sim_base['ganancia_neta']), _sim_cap_currency)}. "
                    "Revisa el riesgo y compara el escenario pesimista antes de tomar decisiones."
                )
            else:
                st.info("Bajo el escenario base, la inversión terminaría aproximadamente en punto de equilibrio.")
            st.caption(
                "Estimación ilustrativa, no recomendación personalizada. Incluye costos de compra/venta y "
                "retención estimada sobre dividendos según tus supuestos; no incluye inflación ni cambios "
                "futuros del tipo de cambio. Los dividendos no se reinvierten."
            )


    if False:  # Conserva el código para retomarlo en el futuro sin mostrar la pestaña.
        st.markdown("##### Valoración independiente por múltiplos comparables")
        st.caption(
            "Método de mercado complementario al DCF. La valoración usa la mediana de EV/EBITDA "
            "de comparables con múltiplos observados y/o los valores que ingreses manualmente."
        )
        st.info(
            "Las cifras operativas del catálogo se expresan en miles de millones de moneda local. "
            "Revisa la fuente y fecha de cada comparable; empresas con deuda, crecimiento o contabilidad "
            "muy diferentes pueden no ser comparables."
        )
        _mx_empresa = empresa
        _mx_emp = L.resolver_empresa(_mx_empresa) if _mx_empresa else None
        _mx_params = (_mx_emp or {}).get("params") or {}
        _mx_hist_raw = (_mx_emp or {}).get("historico")
        _mx_ebitda_default = 0.0
        try:
            _mx_hist = pd.DataFrame(_mx_hist_raw)
            if not _mx_hist.empty and "EBITDA" in _mx_hist.columns:
                _mx_ebitda_default = float(_mx_hist["EBITDA"].iloc[-1])
        except Exception:
            pass
        if not np.isfinite(_mx_ebitda_default) or _mx_ebitda_default <= 0:
            _mx_ebitda_default = 1.0
        _mx_c1, _mx_c2, _mx_c3 = st.columns(3)
        with _mx_c1:
            _mx_ebitda = st.number_input(
                "EBITDA normalizado de la empresa objetivo",
                min_value=0.000001, value=float(_mx_ebitda_default), step=max(0.1, abs(float(_mx_ebitda_default)) * 0.05),
                format="%.4f", key="multiples_ebitda",
                help="Usa el EBITDA sostenible/normalizado del periodo que corresponda. Puedes modificar el dato histórico propuesto.",
            )
        with _mx_c2:
            _mx_deuda_default = float(_mx_params.get("deuda_neta") or 0.0)
            _mx_deuda_neta = st.number_input(
                "Deuda neta (misma unidad que EBITDA)",
                value=_mx_deuda_default, step=max(0.1, abs(_mx_deuda_default) * 0.05),
                format="%.4f", key="multiples_deuda_neta",
                help="Deuda financiera menos caja. Si es negativa, la empresa tiene caja neta.",
            )
        with _mx_c3:
            # No se precargan acciones del DCF: su escala puede diferir del campo en millones.
            _mx_acciones_millones = st.number_input(
                "Acciones en circulación (millones, opcional)",
                min_value=0.0, value=0.0, step=1.0,
                format="%.4f", key="multiples_acciones_millones",
                help="Si EBITDA/EV están en miles de millones y las acciones en millones, el valor por acción se calcula multiplicando equity por 1.000 y dividiendo por acciones.",
            )
        _mx_manual_text = st.text_input(
            "Múltiplos EV/EBITDA de comparables verificados (opcional, separados por coma)",
            value="", key="multiples_manual_values",
            placeholder="Ej.: 7.2, 8.1, 9.0",
            help="Ingresa únicamente múltiplos observados y verificados por ti. Se combinan con comparables en vivo que superen los filtros de fuente.",
        )
        _mx_auto_rows = []
        _mx_source_notes = {}
        _mx_error = None
        try:
            _mx_df, _mx_notes, _mx_summary = L.construir_tabla_sectorial_live(nombre_empresa_focal=_mx_empresa)
            _mx_source_notes = _mx_notes or {}
            _mx_focal = str((_mx_emp or {}).get("ticker_yf") or "").split(".")[0].upper()
            for _, _mx_row in _mx_df.iterrows():
                _mx_name = str(_mx_row.get("Empresa", ""))
                _mx_multiple = _mx_row.get("EV/EBITDA (x)")
                _mx_note = str(_mx_source_notes.get(_mx_name, _mx_row.get("Fuente múltiplo", "")))
                _mx_is_target = (
                    _mx_name.upper() == _mx_focal
                    or _mx_name.upper() == str(_mx_empresa or "").upper()
                    or (_mx_emp is not None and _mx_name.upper() == str(_mx_emp.get("ticker_yf") or "").split(".")[0].upper())
                )
                _mx_note_low = _mx_note.lower()
                _mx_observed = any(k in _mx_note_low for k in ("yahoo finance", "marketcap", "market cap", "market data", "bvc live"))
                _mx_fallback = any(k in _mx_note_low for k in ("fallback", "sectorial", "estimado", "sin ticker", "error", "no disponible"))
                if not _mx_is_target and _mx_observed and not _mx_fallback:
                    try:
                        _mx_val = float(_mx_multiple)
                        if np.isfinite(_mx_val) and 0 < _mx_val <= 80:
                            _mx_auto_rows.append({
                                "Comparable": _mx_name,
                                "EV/EBITDA (x)": _mx_val,
                                "Fuente / nota": _mx_note,
                            })
                    except (TypeError, ValueError):
                        pass
        except Exception as _mx_exc:
            _mx_error = str(_mx_exc)
        if _mx_error:
            st.warning(f"No se pudo construir la lista automática de comparables: {_mx_error}")
        if _mx_auto_rows:
            st.markdown("###### Comparables con múltiplos de mercado identificados")
            st.dataframe(pd.DataFrame(_mx_auto_rows), hide_index=True, width="stretch")
        else:
            st.warning(
                "No se identificaron comparables automáticos con fuente de mercado suficientemente clara. "
                "Puedes ingresar múltiplos verificados manualmente; no se reemplazan datos ausentes con múltiplos ficticios."
            )
        _mx_manual = []
        if _mx_manual_text.strip():
            try:
                _mx_manual = [float(v.strip()) for v in _mx_manual_text.split(",") if v.strip()]
                if any(not np.isfinite(v) or v <= 0 or v > 80 for v in _mx_manual):
                    raise ValueError("Cada múltiplo debe estar entre 0 y 80.")
            except ValueError as _mx_exc:
                st.error(f"Revisa los múltiplos ingresados: {_mx_exc}")
                _mx_manual = []
        _mx_values = [r["EV/EBITDA (x)"] for r in _mx_auto_rows] + _mx_manual
        if st.button("Calcular valoración por múltiplos", type="primary", key="multiples_calculate"):
            try:
                from multiples_valuation import valoracion_por_multiplos as _mx_calculate
                _mx_result = _mx_calculate(
                    ebitda_objetivo=float(_mx_ebitda),
                    multiples_comparables=_mx_values,
                    deuda_neta=float(_mx_deuda_neta),
                    acciones_millones=float(_mx_acciones_millones) if _mx_acciones_millones > 0 else None,
                )
                st.session_state["multiples_valuation_result"] = {
                    "empresa": _mx_empresa,
                    "request": (
                        _mx_empresa, float(_mx_ebitda), float(_mx_deuda_neta),
                        float(_mx_acciones_millones), tuple(_mx_values),
                    ),
                    "ebitda": float(_mx_ebitda),
                    "deuda_neta": float(_mx_deuda_neta),
                    "acciones": float(_mx_acciones_millones),
                    "multiples": list(_mx_values),
                    "resultado": _mx_result,
                }
            except Exception as _mx_exc:
                st.session_state.pop("multiples_valuation_result", None)
                st.error(f"No se pudo calcular la valoración: {_mx_exc}")
        _mx_saved = st.session_state.get("multiples_valuation_result")
        _mx_current_request = (
            _mx_empresa, float(_mx_ebitda), float(_mx_deuda_neta),
            float(_mx_acciones_millones), tuple(_mx_values),
        )
        if _mx_saved and _mx_saved.get("request") != _mx_current_request:
            _mx_saved = None
            st.info("Cambiaste la empresa o uno de los supuestos. Pulsa **Calcular valoración por múltiplos** para actualizar el resultado.")
        if _mx_saved:
            _mx_res = _mx_saved["resultado"]
            st.markdown("###### Resultado de valoración")
            _mx_a, _mx_b, _mx_c, _mx_d = st.columns(4)
            _mx_a.metric("Múltiplo mediano", f"{_mx_res['multiple_mediano']:.2f}x")
            _mx_b.metric("Valor de empresa (EV)", f"{_mx_res['enterprise_value']:,.2f}")
            _mx_c.metric("Valor del patrimonio", f"{_mx_res['equity_value']:,.2f}")
            if _mx_res.get("valor_por_accion") is not None:
                _mx_d.metric("Valor por acción", f"{_mx_res['valor_por_accion']:,.2f}")
            else:
                _mx_d.metric("Valor por acción", "N/D")
            st.caption(
                f"Comparables utilizados: {_mx_res['n_comparables']} · "
                f"Rango intercuartílico EV/EBITDA: {_mx_res['q1']:.2f}x–{_mx_res['q3']:.2f}x. "
                "El valor del patrimonio se obtiene como EV menos deuda neta. "
                "El valor por acción solo se calcula si ingresaste acciones en millones."
            )
            st.dataframe(pd.DataFrame([
                {"Concepto": "EBITDA objetivo", "Valor": _mx_saved["ebitda"]},
                {"Concepto": "Múltiplo mediano", "Valor": _mx_res["multiple_mediano"]},
                {"Concepto": "EV por múltiplo mediano", "Valor": _mx_res["enterprise_value"]},
                {"Concepto": "Deuda neta", "Valor": _mx_saved["deuda_neta"]},
                {"Concepto": "Equity estimado", "Valor": _mx_res["equity_value"]},
                {"Concepto": "Múltiplo mínimo", "Valor": _mx_res["multiple_min"]},
                {"Concepto": "Múltiplo máximo", "Valor": _mx_res["multiple_max"]},
            ]), hide_index=True, width="stretch")
            st.caption(
                "Resultado indicativo, no recomendación de inversión. Verifica que los comparables compartan "
                "sector, geografía, crecimiento, márgenes, apalancamiento y normas contables. "
                "El múltiplo automático solo se usa cuando la nota de fuente identifica datos de mercado; "
                "los valores manuales dependen de la verificación del usuario."
            )


    with tab10:
        st.markdown("### Escenarios y políticas conectados al modelo de valoración")
        st.caption(
            "Esta pestaña reutiliza la proyección de la pestaña 1 y el WACC, g terminal y puente EV→Equity "
            "de la barra lateral. No genera un pronóstico independiente ni sustituye los resultados de las pestañas 2 y 5."
        )
        with st.expander("Fórmulas y reglas", expanded=False):
            st.markdown(
                "- FCFF = NOPAT + depreciación − CAPEX − variación del capital de trabajo.\n"
                "- Los escenarios aplican los mismos shocks de drivers definidos por el modelo principal.\n"
                "- Las políticas se revaloran con la función DCF y el puente EV→Equity existentes.\n"
                "- La optimización de CAPEX nunca debe recortar mantenimiento, seguridad ni inversión obligatoria.\n"
                "- La dispersión anual de FCFF es descriptiva; no equivale a VaR, CVaR ni a una distribución probabilística."
            )
        fs_forecast = st.session_state.get("resultados", {}).get("tab1")
        fs_proj_display = fs_forecast[2] if isinstance(fs_forecast, (list, tuple)) and len(fs_forecast) > 2 else None
        if not isinstance(fs_proj_display, pd.DataFrame) or fs_proj_display.empty:
            st.warning("Primero configura los datos de la empresa y pulsa **Generar todo**. La pestaña utilizará la proyección real resultante de la pestaña 1.")
        elif st.session_state.get("modelo_dirty"):
            st.warning("Los supuestos del modelo cambiaron y los resultados anteriores están invalidados. Pulsa **Generar todo** antes de simular políticas.")
        else:
            fs_cfg1, fs_cfg2, fs_cfg3 = st.columns(3)
            with fs_cfg1:
                fs_capex_saving = st.number_input(
                    "Ahorro CAPEX (puntos porcentuales de ventas)", min_value=0.0, max_value=30.0,
                    value=1.0, step=0.5, key="fs_capex_saving_connected"
                ) / 100
            with fs_cfg2:
                fs_capex_floor = st.number_input(
                    "CAPEX mínimo / ventas (%)", min_value=0.0, max_value=100.0,
                    value=3.0, step=0.5, key="fs_capex_floor_connected"
                ) / 100
            with fs_cfg3:
                fs_margin_uplift = st.number_input(
                    "Mejora hipotética margen EBIT (p.p.)", min_value=0.0, max_value=20.0,
                    value=1.5, step=0.5, key="fs_margin_uplift_connected"
                ) / 100
            fs_impl_cost = st.number_input(
                "Costo de implementación de eficiencia (% de ingresos del primer año)",
                min_value=0.0, max_value=30.0, value=1.0, step=0.5, key="fs_impl_cost_connected"
            ) / 100
            st.caption(
                f"Base conectada: {empresa} · horizonte {len(fs_proj_display)} años · "
                f"WACC {float(w['wacc']):.2%} · g terminal {float(g):.2%} · moneda del modelo {moneda}."
            )
            if st.button("Recalcular escenarios y políticas con los datos conectados", type="primary",
                         key="btn_fs_calcular_conectado", width="stretch"):
                try:
                    fs_alias = {
                        "Depreciación": "Depreciacion", "Depreciacion": "Depreciacion",
                        "ΔNWC": "Delta_NWC", "Cambio NWC": "Delta_NWC",
                        "Año": "Año",
                    }
                    fs_base_df = fs_proj_display.copy().rename(columns=fs_alias)
                    fs_required = ["Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "Delta_NWC", "NOPAT", "FCFF"]
                    fs_missing = [c for c in fs_required if c not in fs_base_df.columns]
                    if fs_missing:
                        raise ValueError("La proyección no contiene columnas requeridas: " + ", ".join(fs_missing))
                    for fs_col in fs_required:
                        fs_base_df[fs_col] = pd.to_numeric(fs_base_df[fs_col], errors="coerce")
                    if fs_base_df[fs_required].isna().any().any():
                        raise ValueError("La proyección contiene valores ausentes o no numéricos; corrige la pestaña 1 antes de simular.")
                    if not np.isfinite(fs_base_df[fs_required].to_numpy(dtype=float)).all():
                        raise ValueError("La proyección contiene valores no finitos.")
                    fs_base_df = fs_base_df.reset_index(drop=True)
                    fs_base_fcff = fs_base_df["FCFF"].astype(float).tolist()
                    fs_base_nopat = float(fs_base_df["NOPAT"].iloc[-1])
                    fs_base_ebitda = float(fs_base_df["EBITDA"].iloc[-1])
                    fs_base_wacc = float(w["wacc"])
                    fs_base_g = float(g)
                    fs_acciones = L.resolver_acciones_millones(empresa, acciones)
                    fs_bridge = L.params_bridge_desde_ui(
                        deuda_neta, caja, nci, otros_claims, asociados, fs_acciones, exit_multiple
                    )
                    try:
                        fs_empresa_params = L.resolver_empresa(empresa) or {}
                        if (fs_empresa_params.get("params") or {}).get("deuda_es_bruta"):
                            fs_bridge["deuda_es_bruta"] = True
                    except Exception:
                        pass
                    fs_price = L.resolver_precio_mercado(empresa)
                    fs_base_val = L.valorar_con_bridge(
                        fs_base_fcff, fs_base_wacc, fs_base_g, fs_bridge,
                        ebitda_salida=fs_base_ebitda, precio_mercado=fs_price,
                        mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=fs_base_nopat,
                    )
                    fs_shocks = getattr(L, "SHOCKS_ESCENARIOS", {
                        "Pesimista": {"g_ingresos": 0.90, "margen_ebitda": 0.92, "capex_factor": 1.15, "nwc_factor": 1.10},
                        "Base": {"g_ingresos": 1.0, "margen_ebitda": 1.0, "capex_factor": 1.0, "nwc_factor": 1.0},
                        "Optimista": {"g_ingresos": 1.08, "margen_ebitda": 1.06, "capex_factor": 0.92, "nwc_factor": 0.95},
                    })
                    fs_scenario_rows = []
                    for fs_name, fs_wacc, fs_g, fs_wshock in [
                        ("Pesimista", fs_base_wacc + 0.015, max(0.005, fs_base_g - 0.01), "Pesimista"),
                        ("Base", fs_base_wacc, fs_base_g, "Base"),
                        ("Optimista", max(fs_base_wacc - 0.01, 0.06), max(0.005, min(fs_base_g + 0.01, fs_base_wacc - 0.015)), "Optimista"),
                    ]:
                        fs_scenario_df = L.aplicar_shocks_drivers_proyeccion(
                            fs_base_df, tax=tax, shock=fs_shocks.get(fs_wshock, {})
                        )
                        fs_fcff = pd.to_numeric(fs_scenario_df["FCFF"], errors="coerce").astype(float).tolist()
                        fs_nopat = float(fs_scenario_df["NOPAT"].iloc[-1])
                        fs_ebitda = float(fs_scenario_df["EBITDA"].iloc[-1])
                        fs_val = L.valorar_con_bridge(
                            fs_fcff, fs_wacc, fs_g, fs_bridge, ebitda_salida=fs_ebitda,
                            precio_mercado=fs_price, mid_year=bool(mid_year),
                            g_max_macro=float(g_max_macro), nopat_final=fs_nopat,
                        )
                        fs_rev = pd.to_numeric(fs_scenario_df["Ingresos"], errors="coerce")
                        fs_cap = pd.to_numeric(fs_scenario_df["CAPEX"], errors="coerce")
                        fs_nwc = pd.to_numeric(fs_scenario_df["Delta_NWC"], errors="coerce")
                        fs_ebit = pd.to_numeric(fs_scenario_df["EBIT"], errors="coerce")
                        fs_scenario_rows.append({
                            "Escenario": fs_name,
                            "Crecimiento ingresos anualizado (%)": 100 * ((float(fs_rev.iloc[-1]) / float(fs_rev.iloc[0])) ** (1 / max(1, len(fs_rev)-1)) - 1) if len(fs_rev) > 1 and fs_rev.iloc[0] > 0 else None,
                            "Margen EBIT promedio (%)": 100 * float((fs_ebit / fs_rev.replace(0, np.nan)).mean()),
                            "CAPEX / ventas (%)": 100 * float((fs_cap / fs_rev.replace(0, np.nan)).mean()),
                            "ΔNWC / ventas (%)": 100 * float((fs_nwc / fs_rev.replace(0, np.nan)).mean()),
                            "WACC (%)": 100 * fs_wacc, "g terminal (%)": 100 * fs_g,
                            "EV": fs_val.get("EV"), "Equity": fs_val.get("Equity_Value"),
                            "TV / EV (%)": 100 * float(fs_val.get("PV_TV") or 0) / float(fs_val.get("EV") or 1),
                            "FCFF acumulado": sum(fs_fcff),
                        })
                    st.markdown("#### 1. Escenarios conectados al pronóstico y DCF existente")
                    st.dataframe(pd.DataFrame(fs_scenario_rows).round(3), hide_index=True, width="stretch")
                    st.caption(
                        "Los shocks operativos proceden de SHOCKS_ESCENARIOS del modelo principal. WACC y g se modifican "
                        "por escenario; el puente a Equity, método terminal y convención mid-year son los de la valoración existente."
                    )

                    fs_policy_specs = []
                    fs_capex_df = fs_base_df.copy()
                    fs_capex_min = pd.to_numeric(fs_capex_df["Ingresos"], errors="coerce").astype(float) * fs_capex_floor
                    fs_capex_target = pd.to_numeric(fs_capex_df["CAPEX"], errors="coerce").astype(float) - (
                        pd.to_numeric(fs_capex_df["Ingresos"], errors="coerce").astype(float) * fs_capex_saving
                    )
                    fs_capex_df["CAPEX"] = np.maximum(fs_capex_min.to_numpy(), fs_capex_target.to_numpy())
                    fs_capex_df = L.recalcular_fcff(fs_capex_df, tax=tax, capex_extra=0.0)
                    fs_policy_specs.append(("Optimización CAPEX", fs_capex_df, "Reduce CAPEX en el ahorro definido, respetando el piso de inversión."))

                    fs_eff_df = fs_base_df.copy()
                    fs_eff_cost = float(fs_eff_df["Ingresos"].iloc[0]) * fs_impl_cost
                    fs_eff_df.loc[0, "EBIT"] = float(fs_eff_df.loc[0, "EBIT"]) - fs_eff_cost
                    fs_eff_df.loc[0, "EBITDA"] = float(fs_eff_df.loc[0, "EBITDA"]) - fs_eff_cost
                    fs_eff_df["EBIT"] = pd.to_numeric(fs_eff_df["EBIT"], errors="coerce") + (
                        pd.to_numeric(fs_eff_df["Ingresos"], errors="coerce") * fs_margin_uplift
                    )
                    fs_eff_df["EBITDA"] = pd.to_numeric(fs_eff_df["EBITDA"], errors="coerce") + (
                        pd.to_numeric(fs_eff_df["Ingresos"], errors="coerce") * fs_margin_uplift
                    )
                    fs_eff_df = L.recalcular_fcff(fs_eff_df, tax=tax, capex_extra=0.0)
                    fs_policy_specs.append(("Eficiencia operativa", fs_eff_df, "Mejora EBIT por el margen supuesto y descuenta el costo de implementación en el primer año."))

                    fs_policy_rows = [{
                        "Política": "Base actual", "EV": fs_base_val.get("EV"),
                        "Equity": fs_base_val.get("Equity_Value"), "Δ EV vs. base": 0.0,
                        "Δ Equity vs. base": 0.0, "VPN incremental FCFF": 0.0,
                        "TIR proyecto (%)": None, "FCFF acumulado": sum(fs_base_fcff),
                        "Δ FCFF acumulado": 0.0, "Dispersión FCFF": float(np.std(fs_base_fcff, ddof=0)),
                        "Regla": "Caso de referencia",
                    }]
                    fs_policy_detail = []
                    fs_base_ev = float(fs_base_val.get("EV") or 0.0)
                    fs_base_equity = float(fs_base_val.get("Equity_Value") or 0.0)
                    fs_base_std = float(np.std(fs_base_fcff, ddof=0))
                    for fs_name, fs_policy_df, fs_rule in fs_policy_specs:
                        fs_fcff = pd.to_numeric(fs_policy_df["FCFF"], errors="coerce").astype(float).tolist()
                        fs_val = L.valorar_con_bridge(
                            fs_fcff, fs_base_wacc, fs_base_g, fs_bridge,
                            ebitda_salida=float(fs_policy_df["EBITDA"].iloc[-1]),
                            precio_mercado=fs_price, mid_year=bool(mid_year),
                            g_max_macro=float(g_max_macro), nopat_final=float(fs_policy_df["NOPAT"].iloc[-1]),
                        )
                        fs_dcf_incremental = float(fs_val.get("EV") or 0.0) - fs_base_ev
                        fs_project_metrics = L.metricas_proyecto_robustas(
                            fs_fcff, fs_base_wacc, inversion_inicial=float(inversion_inicial or 0.0),
                            capital_invertido=float(capital_invertido or 0.0),
                        )
                        fs_tir = fs_project_metrics.get("tir")
                        fs_tir_pct = 100 * float(fs_tir) if fs_tir is not None and np.isfinite(float(fs_tir)) else None
                        fs_std = float(np.std(fs_fcff, ddof=0))
                        fs_delta_fcff = sum(fs_fcff) - sum(fs_base_fcff)
                        fs_policy_rows.append({
                            "Política": fs_name, "EV": fs_val.get("EV"), "Equity": fs_val.get("Equity_Value"),
                            "Δ EV vs. base": fs_dcf_incremental,
                            "Δ Equity vs. base": float(fs_val.get("Equity_Value") or 0.0) - fs_base_equity,
                            "VPN incremental FCFF": fs_dcf_incremental,
                            "TIR proyecto (%)": fs_tir_pct, "FCFF acumulado": sum(fs_fcff),
                            "Δ FCFF acumulado": fs_delta_fcff, "Dispersión FCFF": fs_std,
                            "Δ dispersión": fs_std - fs_base_std, "Regla": fs_rule,
                        })
                        for fs_i, fs_flow in enumerate(fs_fcff):
                            fs_policy_detail.append({"Año": int(fs_i + 1), "Política": fs_name, "FCFF": fs_flow})
                    st.markdown("#### 2. Efecto de las políticas sobre valoración y flujos")
                    st.dataframe(pd.DataFrame(fs_policy_rows).round(3), hide_index=True, width="stretch")
                    fs_adopt = [row["Política"] for row in fs_policy_rows[1:] if row["VPN incremental FCFF"] > 0]
                    if fs_adopt:
                        st.success("Políticas que aumentan el EV bajo estos supuestos: " + ", ".join(fs_adopt) +
                                   ". La adopción sigue condicionada a validar ejecución, mantenimiento y seguridad.")
                    else:
                        st.warning("Ninguna política aumenta el EV frente al caso base con estos supuestos; no se recomienda adoptarlas automáticamente.")
                    st.markdown("#### 3. FCFF anual comparado")
                    fs_detail_df = pd.DataFrame(fs_policy_detail)
                    if not fs_detail_df.empty:
                        st.dataframe(
                            fs_detail_df.pivot(index="Año", columns="Política", values="FCFF").reset_index().round(3),
                            hide_index=True, width="stretch"
                        )
                    st.caption(
                        f"Moneda: {moneda}. Los importes conservan la unidad/escala del modelo de empresa. "
                        "VPN incremental FCFF se muestra como cambio en EV manteniendo el mismo puente a Equity. "
                        "La TIR es de proyecto y usa la inversión inicial configurada en la barra lateral; no es la TIR de la acción."
                    )
                    st.warning(
                        "Los cambios de CAPEX y margen son supuestos de política, no hechos observados. "
                        "Antes de entregar, documenta su justificación y evita reducir mantenimiento, seguridad o inversiones obligatorias."
                    )
                except (ValueError, ArithmeticError, KeyError, TypeError) as fs_error:
                    st.error(f"No se pudo calcular el modelo conectado: {fs_error}")


    st.markdown(
        '<div class="tf-footer">Herramienta pedagógica · Catálogo / Yahoo Finance · '
        "No es feed oficial BVC ni asesoría de inversión</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
