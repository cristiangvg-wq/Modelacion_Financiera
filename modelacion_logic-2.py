"""
Lógica completa — Modelación Financiera Multisectorial
Extraída del notebook/Gradio original (todas las funciones de negocio).
No contiene la UI de Gradio; pensado para Streamlit u otro frontend.
"""
from pathlib import Path
# =============================================================================
# PLATAFORMA MULTISECTORIAL DE MODELACIÓN FINANCIERA Y RIESGO
# Empresas cotizadas o privadas: Excel/CSV propio, datos públicos cuando estén disponibles
# Los emisores BVC son ejemplos de referencia, no el límite de la plataforma
# =============================================================================

import warnings
# No ocultar advertencias globalmente: son relevantes para la calidad del modelo.
# Si alguna librería genera ruido, filtrar solo esa advertencia de forma específica.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.holtwinters import ExponentialSmoothing
try:
    import gradio as gr
except ImportError:
    gr = None  # UI Gradio no requerida en Streamlit

def _upd(**kwargs):
    """Compat: en Gradio era gr.update; en Streamlit devolvemos dict o el value."""
    if not kwargs:
        return None
    if set(kwargs.keys()) <= {"value", "visible", "choices"}:
        return kwargs.get("value", kwargs)
    return kwargs


import traceback
from scipy.optimize import brentq
from datetime import datetime
import tempfile
import os
import re
import unicodedata

try:
    import numpy_financial as npf
    HAS_NPF = True
except ImportError:
    HAS_NPF = False

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

# =============================================================================
# API KEYS (IA asistente)
# En Hugging Face Spaces: añade GEMINI_API_KEY / XAI_API_KEY / OPENAI_API_KEY
# en Settings → Repository secrets. No hardcodees claves aquí.
# También puedes pegar la key en la UI (acordeón «Consulta asistida»).
# =============================================================================
# import os
# # --- Gemini (Google AI Studio) — cuota gratuita habitual ---
# # GEMINI_API_KEY se lee desde Secrets de Hugging Face (no hardcodear)
# os.environ["GEMINI_MODEL"] = "gemini-2.5-flash-lite"  # opcional
# # --- xAI (Grok Inference) — de pago ---
# # XAI_API_KEY se lee desde Secrets de Hugging Face
# # --- OpenAI — de pago ---
# # OPENAI_API_KEY se lee desde Secrets de Hugging Face
#
# También puedes pegar la key en la UI (acordeón «Consulta asistida» → Configuración de IA).
# =============================================================================


plt.style.use("seaborn-v0_8-whitegrid")
sns.set_palette(["#0A2540", "#00A3A1", "#1B6CA8", "#F59E0B", "#10B981"])
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["axes.titleweight"] = "bold"
plt.rcParams["figure.facecolor"] = "#F8FAFC"
plt.rcParams["axes.facecolor"] = "#FFFFFF"
plt.rcParams["axes.edgecolor"] = "#E2E8F0"
plt.rcParams["grid.color"] = "#E2E8F0"
plt.rcParams["grid.alpha"] = 0.7

COLOR_PRIMARY = "#0A2540"
COLOR_ACCENT = "#00A3A1"
COLOR_SUCCESS = "#10B981"
COLOR_WARNING = "#F59E0B"
COLOR_DANGER = "#EF4444"

# =============================================================================
# CATÁLOGO DE EMPRESAS (BVC + sector)
# Valores financieros en miles de millones COP (reportes públicos) para catálogo BVC
# Precio de mercado: Yahoo Finance (tickers BVC .CL)
# =============================================================================
EMPRESAS = {
    "ISA — Interconexión Eléctrica": {
        "ticker_bvc": "ISA", "ticker_yf": "ISA.CL",
        "sector": "Transmisión de energía / Infraestructura",
        "descripcion": "Transporta electricidad a alta tensión en Colombia y Latinoamérica. También opera carreteras y telecomunicaciones.",
        "params": {"de_ratio": 1.20, "kd": 0.08, "tax": 0.22, "g": 0.03, "beta_u": 0.42,
                   "capital_invertido": 45000, "deuda_neta": 40350, "inversion_inicial": 5000, "caja": 4610, "nci": 10400, "otros_claims": 0, "asociados": 4500, "acciones": 1108, "exit_multiple": 8.4, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [7200, 7800, 8400, 9045, 10180, 11117, 13356, 14171, 14935, 15918],
            "EBITDA": [4100, 4500, 4850, 5200, 5850, 6884, 7772.6, 8866.0, 9506.8, 8495.2],
            "EBIT": [3200, 3550, 3800, 4100, 4650, 6072, 6766.3, 7598.0, 8479.5, 7415.0],
            "Depreciacion": [700, 750, 800, 850, 900, 812, 1006.3, 1268.0, 1027.2, 1080.2],
            "CAPEX": [1800, 1950, 2050, 2100, 2311, 761, 1832.9, 4632.0, 1578.1, 1706.3],
            "NWC": [950, 1050, 1120, 1200, 1350, 1450, 1068.5, 1130.7, 1194.8, 1273.4],
            "Delta_NWC": [0.0, 100.0, 70.0, 80.0, 150.0, 100.0, 0.0, 62.2, 64.1, 78.7],
            "NOPAT": [2080.0, 2307.5, 2470.0, 2665.0, 3022.5, 3946.8, 4398.1, 4938.7, 5511.7, 4819.8],
            "FCFF": [980.0, 1007.5, 1150.0, 1335.0, 1461.5, 3897.8, 3571.5, 1512.5, 4896.7, 4115.0],
        },
    },
    "GEB — Grupo Energía Bogotá": {
        "ticker_bvc": "GEB", "ticker_yf": "GEB.CL",
        "sector": "Transmisión y distribución de energía / Gas",
        "descripcion": "Grupo energético de Bogotá: transmisión eléctrica, gas natural y distribución.",
        "params": {"de_ratio": 0.95, "kd": 0.075, "tax": 0.35, "g": 0.032, "beta_u": 0.40,
                   "capital_invertido": 38000, "deuda_neta": 17170, "inversion_inicial": 3500, "caja": 2430, "nci": 1500, "otros_claims": 0, "asociados": 800, "acciones": 9181, "exit_multiple": 13.6, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [4800, 5200, 5700, 6200, 6500, 6700, 6874.6, 7953.7, 7971.6, 8015.6],
            "EBITDA": [2400, 2600, 2850, 3100, 3300, 3500, 5400.0, 5737.8, 5394.8, 6153.3],
            "EBIT": [1850, 2000, 2200, 2400, 2600, 2800, 4563.8, 4758.9, 4425.7, 5118.5],
            "Depreciacion": [380, 420, 460, 500, 550, 600, 836.2, 979.0, 969.1, 1034.8],
            "CAPEX": [900, 1000, 1100, 1200, 1100, 1300, 1906.7, 1351.5, 1896.3, 1973.3],
            "NWC": [650, 700, 750, 800, 850, 900, 550.0, 636.3, 637.7, 641.3],
            "Delta_NWC": [0.0, 50.0, 50.0, 50.0, 50.0, 50.0, 0.0, 86.3, 1.4, 3.5],
            "NOPAT": [1202.5, 1300.0, 1430.0, 1560.0, 1690.0, 1820.0, 2966.5, 3093.3, 2876.7, 3327.1],
            "FCFF": [682.5, 670.0, 740.0, 810.0, 990.0, 1120.0, 1896.0, 2634.4, 1948.1, 2385.0],
        },
    },
    "CELSIA — Celsia S.A. E.S.P.": {
        "ticker_bvc": "CELSIA", "ticker_yf": "CELSIA.CL",
        "sector": "Generación renovable y distribución",
        "descripcion": "Genera y vende electricidad con énfasis en renovables (solar, eólica, hídrica). Parte del Grupo Argos.",
        "params": {"de_ratio": 1.10, "kd": 0.085, "tax": 0.35, "g": 0.028, "beta_u": 0.45,
                   "capital_invertido": 18000, "deuda_neta": 5030, "inversion_inicial": 2000, "caja": 300, "nci": 200, "otros_claims": 0, "asociados": 100, "acciones": 1033, "exit_multiple": 7.9, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [3000, 3200, 3500, 3800, 4100, 4500, 5584.5, 6229.9, 6806.7, 5395.1],
            "EBITDA": [900, 1000, 1100, 1200, 1300, 1500, 1710.1, 1751.7, 1481.5, 1580.1],
            "EBIT": [650, 750, 820, 900, 1000, 1150, 1281.7, 1370.3, 1075.4, 1140.7],
            "Depreciacion": [220, 240, 260, 280, 300, 320, 428.5, 381.4, 406.1, 439.4],
            "CAPEX": [600, 650, 720, 800, 900, 1000, 2083.8, 1219.4, 1751.1, 1331.8],
            "NWC": [320, 350, 380, 400, 420, 450, 446.8, 498.4, 544.5, 431.6],
            "Delta_NWC": [0.0, 30.0, 30.0, 20.0, 20.0, 30.0, 0.0, 51.6, 46.1, -112.9],
            "NOPAT": [422.5, 487.5, 533.0, 585.0, 650.0, 747.5, 833.1, 890.7, 699.0, 741.5],
            "FCFF": [42.5, 47.5, 43.0, 45.0, 30.0, 37.5, -822.3, 1.1, -692.1, -38.0],
        },
    },
    "EPM — Empresas Públicas de Medellín": {
        "ticker_bvc": "EPM", "ticker_yf": None,
        "sector": "Generación, distribución, agua y gas",
        "descripcion": "Empresa pública de Medellín. Genera y distribuye energía, agua y gas.",
        "params": {"de_ratio": 1.45, "kd": 0.09, "tax": 0.35, "g": 0.025, "beta_u": 0.45,
                   "capital_invertido": 70000, "deuda_neta": 42000, "inversion_inicial": 8000, "caja": 4000, "nci": 0, "otros_claims": 0, "asociados": 0, "acciones": None, "exit_multiple": 8.0, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [14000, 15200, 16500, 18000, 19500, 21000, 24000, 25500, 27000, 28500],
            "EBITDA": [4800, 5200, 5700, 6200, 6800, 7400, 8500, 9000, 9400, 9800],
            "EBIT": [3700, 4000, 4400, 4800, 5300, 5800, 6800, 7200, 7500, 7800],
            "Depreciacion": [900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800],
            "CAPEX": [2800, 3000, 3200, 3500, 3800, 4000, 4200, 4500, 4800, 5000],
            "NWC": [1900, 2100, 2300, 2500, 2700, 2900, 3100, 3300, 3500, 3700],
            "Delta_NWC": [0.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0],
            "NOPAT": [2405.0, 2600.0, 2860.0, 3120.0, 3445.0, 3770.0, 4420.0, 4680.0, 4875.0, 5070.0],
            "FCFF": [505.0, 400.0, 560.0, 620.0, 745.0, 970.0, 1520.0, 1580.0, 1575.0, 1670.0],
        },
    },
    "ENEL Colombia": {
        "ticker_bvc": "ENELAM", "ticker_yf": None,  # ENELAM.CL no cotiza en Yahoo (404)
        "sector": "Generación y distribución eléctrica",
        "descripcion": "Operación colombiana del grupo Enel. Genera y distribuye electricidad.",
        "params": {"de_ratio": 1.30, "kd": 0.082, "tax": 0.35, "g": 0.027, "beta_u": 0.58,
                   "capital_invertido": 28000, "deuda_neta": 15000, "inversion_inicial": 3000, "caja": 1500, "nci": 500, "otros_claims": 0, "asociados": 0, "acciones": None, "exit_multiple": 8.0, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [7200, 7800, 8500, 9200, 9800, 10500, 11800, 12500, 13200, 14000],
            "EBITDA": [2800, 3000, 3300, 3600, 3900, 4200, 4800, 5100, 5400, 5700],
            "EBIT": [2100, 2300, 2500, 2800, 3000, 3300, 3800, 4000, 4300, 4500],
            "Depreciacion": [550, 600, 650, 700, 750, 800, 900, 950, 1000, 1050],
            "CAPEX": [1400, 1500, 1600, 1800, 1900, 2000, 2200, 2400, 2500, 2600],
            "NWC": [900, 980, 1050, 1100, 1200, 1300, 1400, 1500, 1600, 1700],
            "Delta_NWC": [0.0, 80.0, 70.0, 50.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "NOPAT": [1365.0, 1495.0, 1625.0, 1820.0, 1950.0, 2145.0, 2470.0, 2600.0, 2795.0, 2925.0],
            "FCFF": [515.0, 515.0, 605.0, 670.0, 700.0, 845.0, 1070.0, 1050.0, 1195.0, 1275.0],
        },
    },
    "BVC — Bolsa de Valores de Colombia": {
        "ticker_bvc": "BVC", "ticker_yf": "BVC.CL",
        "sector": "Servicios financieros / Bolsa de valores",
        "descripcion": "Opera la Bolsa de Valores de Colombia: compra-venta de acciones, bonos y otros títulos.",
        "params": {"de_ratio": 0.35, "kd": 0.07, "tax": 0.35, "g": 0.04, "beta_u": 0.35,
                   "capital_invertido": 800, "deuda_neta": 61, "inversion_inicial": 100, "caja": 148, "nci": 0, "otros_claims": 0, "asociados": 0, "acciones": 60.5, "exit_multiple": 5.5, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [180, 190, 200, 210, 195, 199.8, 239.0, 287.4, 320.0, 359.8],
            "EBITDA": [70, 75, 80, 85, 70, 76.0, 86.1, 129.6, 160.0, 210.5],
            "EBIT": [55, 58, 62, 65, 52, 59.5, 65.9, 108.9, 140.0, 186.0],
            "Depreciacion": [15, 16, 17, 18, 16, 16.5, 20.2, 20.7, 22.0, 24.4],
            "CAPEX": [20, 22, 24, 25, 22, 22.0, 17.4, 17.0, 15.0, 12.7],
            "NWC": [14, 15, 15.5, 16, 15.5, 16.0, 19.1, 23.0, 26.0, 28.8],
            "Delta_NWC": [0.0, 1.0, 0.5, 0.5, -0.5, 0.5, 3.1, 3.9, 3.0, 2.8],
            "NOPAT": [35.8, 37.7, 40.3, 42.2, 33.8, 38.7, 42.8, 70.8, 91.0, 120.9],
            "FCFF": [30.8, 31.7, 33.3, 34.7, 28.3, 33.2, 42.6, 70.7, 95.0, 126.9],
        },
    },
    "ECOPETROL": {
        "ticker_bvc": "ECOPETROL", "ticker_yf": "ECOPETROL.CL",
        "sector": "Petróleo, gas y energía",
        "descripcion": "La petrolera más grande de Colombia. Explora, produce y refina petróleo y gas. Controla ISA.",
        "params": {"de_ratio": 1.00, "kd": 0.09, "tax": 0.35, "g": 0.02, "beta_u": 0.75,
                   "capital_invertido": 150000, "deuda_neta": 93726, "inversion_inicial": 15000, "caja": 11192, "nci": 3000, "otros_claims": 0, "asociados": 2000, "acciones": 41117, "exit_multiple": 4.8, "moneda": "COP"},
                        "historico": {
            "Año": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
            "Ingresos": [48000, 55000, 68000, 71000, 50000, 92000, 159611.1, 143189.0, 133330.0, 119694.0],
            "EBITDA": [14000, 18000, 25000, 28000, 12000, 38000, 73813.5, 59832.0, 55747.0, 45128.0],
            "EBIT": [9000, 12000, 18000, 20000, 5000, 28000, 61684.5, 46020.0, 40550.0, 29021.0],
            "Depreciacion": [5000, 5500, 6000, 6500, 7000, 8000, 12129.0, 13812.0, 15197.0, 16107.0],
            "CAPEX": [8000, 9000, 10000, 14000, 9000, 13000, 21877.8, 24090.0, 20928.0, 20827.0],
            "NWC": [6000, 6500, 7000, 7500, 8000, 9000, 12768.9, 11455.1, 10666.4, 9575.5],
            "Delta_NWC": [0.0, 500.0, 500.0, 500.0, 500.0, 1000.0, 0.0, -1313.8, -788.7, -1090.9],
            "NOPAT": [5850.0, 7800.0, 11700.0, 13000.0, 3250.0, 18200.0, 40094.9, 29913.0, 26357.5, 18863.6],
            "FCFF": [2850.0, 3800.0, 7200.0, 5000.0, 750.0, 12200.0, 30346.2, 20948.8, 21415.2, 15234.5],
        },
    },
}

# ---------------------------------------------------------------------------
# Registro en tiempo de ejecución: empresas descargadas vía Yahoo Finance
# (tickers arbitrarios fuera del catálogo BVC)
# ---------------------------------------------------------------------------
EMPRESAS_RUNTIME = {}  # nombre_display -> mismo shape que EMPRESAS[k]

# Snapshot inmutable del catálogo BVC al importar el módulo.
# Evita que una sesión (p.ej. AAPL) corrompa ticker_yf de ISA en memoria.
import copy as _copy_mod
_EMPRESAS_CATALOGO_INMUTABLE = _copy_mod.deepcopy(EMPRESAS)


def _restaurar_entrada_catalogo(nombre_empresa):
    """Restaura ticker/moneda del catálogo si se contaminó en sesión."""
    if not nombre_empresa or nombre_empresa not in _EMPRESAS_CATALOGO_INMUTABLE:
        return
    orig = _EMPRESAS_CATALOGO_INMUTABLE[nombre_empresa]
    vivo = EMPRESAS.get(nombre_empresa)
    if not isinstance(vivo, dict):
        return
    for k in ("ticker_yf", "ticker_bvc", "moneda", "moneda_precio", "sector", "descripcion", "fuente"):
        if k in orig:
            vivo[k] = _copy_mod.deepcopy(orig[k])
    op = _copy_mod.deepcopy(orig.get("params") or {})
    cur = vivo.get("params") or {}
    for nk in (
        "de_ratio", "kd", "tax", "g", "capex_extra", "beta_u", "capital_invertido",
        "deuda_neta", "inversion_inicial", "caja", "nci", "otros_claims", "asociados",
        "acciones", "exit_multiple",
    ):
        if nk in cur and cur[nk] is not None:
            op[nk] = cur[nk]
    op["moneda"] = (orig.get("params") or {}).get("moneda") or orig.get("moneda") or "COP"
    op["precio_moneda"] = op.get("moneda")
    vivo["params"] = op


# ---------------------------------------------------------------------------
# BVC (.CL) vs resto del mundo — tickers y monedas alineadas
# ---------------------------------------------------------------------------
_TICKERS_BVC = {
    "ISA", "GEB", "CELSIA", "EPM", "ENELAM", "BVC", "ECOPETROL",
    "PFBCOLOM", "GRUPOSURA", "PFGRUPSURA", "NUTRESA", "CEMARGOS", "CLH",
    "CORFICOLCF", "PFDAVVNDA", "BANCOLOMBIA", "EXITO", "ETB", "TERPEL",
    "PROMIGAS", "CNEC", "CONCONCRET", "BOGOTA", "OCCIDENTE", "PREVER",
    "MINEROS", "FABRICATO", "TABLEMAC", "ELCONDOR", "PFBANCOLOMBIA",
    "GRUPOARGOS", "PFGRUPOARGOS", "PFAVAL", "CIBEST",
}
_TICKERS_NUNCA_CL = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "NFLX",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "BRK-B", "BRK.B",
    "XOM", "CVX", "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "NEE", "DUK",
    "SO", "D", "AEP", "EXC", "ORCL", "CRM", "ADBE", "INTC", "AMD", "TSM",
    "AVGO", "QCOM", "KO", "PEP", "WMT", "COST", "HD", "MCD", "NKE", "DIS",
    "T", "VZ", "IBM", "CSCO", "BA", "CAT", "GE", "HON", "SPY", "QQQ",
}


def _tickers_bvc_conocidos():
    s = set(_TICKERS_BVC)
    for emp in list(EMPRESAS.values()) + list(EMPRESAS_RUNTIME.values()):
        for key in ("ticker_bvc", "ticker_yf"):
            raw = emp.get(key)
            if not raw:
                continue
            u = str(raw).upper().strip()
            base = u[:-3] if u.endswith(".CL") else u.split(".")[0]
            if base and base not in _TICKERS_NUNCA_CL:
                s.add(base)
    return s


def es_ticker_bvc(ticker):
    if not ticker:
        return False
    t = str(ticker).strip().upper()
    base = t[:-3] if t.endswith(".CL") else t.split(".")[0]
    if base in _TICKERS_NUNCA_CL:
        return False
    if t.endswith(".CL"):
        return True
    return base in _tickers_bvc_conocidos()


def asegurar_sufijo_cl_bvc(ticker, forzar_si_bvc=True):
    """ISA→ISA.CL; AAPL→AAPL; AAPL.CL→AAPL."""
    if ticker is None:
        return None
    t = str(ticker).strip().upper().replace(" ", "")
    if not t:
        return t
    _OTROS = (
        ".MX", ".SA", ".BA", ".L", ".T", ".HK", ".TO", ".PA", ".DE", ".SW",
        ".MI", ".AS", ".BR", ".OL", ".ST", ".AX", ".SI", ".KS", ".KQ", ".TW",
        ".JK", ".NS", ".BO", ".US",
    )
    if any(t.endswith(s) for s in _OTROS):
        return t
    if t.endswith(".CL"):
        base = t[:-3]
        if base in _TICKERS_NUNCA_CL:
            return base
        return t
    base = t.split(".")[0]
    if base in _TICKERS_NUNCA_CL:
        return base
    if forzar_si_bvc and base in _tickers_bvc_conocidos():
        return f"{base}.CL"
    return t


def candidatos_ticker_yf(query):
    q = (query or "").strip().upper().replace(" ", "")
    if not q:
        return []
    if "." in q:
        return [asegurar_sufijo_cl_bvc(q)]
    base = q.split(".")[0]
    if base in _TICKERS_NUNCA_CL:
        return [base]
    if base in _tickers_bvc_conocidos():
        return [f"{base}.CL", base]
    return [base]


def monedas_alineadas_por_ticker(ticker=None, nombre_empresa=None, emp=None):
    """
    Devuelve (moneda_modelo, moneda_precio) SIEMPRE iguales según el emisor.
    BVC / .CL / catálogo CO → (COP, COP)
    US / AAPL… → (USD, USD)
    """
    tk = ticker
    if emp is None and nombre_empresa:
        emp = resolver_empresa(nombre_empresa) if "resolver_empresa" in globals() else None
    emp = emp or {}
    if not tk:
        tk = emp.get("ticker_yf") or emp.get("ticker_bvc")
    if tk:
        tk = asegurar_sufijo_cl_bvc(tk)
    # Catálogo BVC estático
    if nombre_empresa and (nombre_empresa in _EMPRESAS_CATALOGO_INMUTABLE or nombre_empresa in EMPRESAS):
        return "COP", "COP"
    if emp and (emp.get("ticker_bvc") or str(tk or "").endswith(".CL") or es_ticker_bvc(tk)):
        if str(tk or "").endswith(".CL") or emp.get("ticker_bvc") or es_ticker_bvc(tk):
            # Si es claramente BVC
            if str(tk or "").endswith(".CL") or (emp.get("ticker_bvc") and es_ticker_bvc(emp.get("ticker_bvc"))):
                return "COP", "COP"
    if tk and str(tk).upper().endswith(".CL"):
        return "COP", "COP"
    if tk:
        base = str(tk).upper().split(".")[0]
        if base in _TICKERS_NUNCA_CL or (base.isalpha() and 1 <= len(base) <= 5 and "." not in str(tk)):
            # bare US-style ticker
            if base in _TICKERS_NUNCA_CL or not es_ticker_bvc(base):
                if base in _TICKERS_NUNCA_CL:
                    return "USD", "USD"
    # País / moneda ya en ficha
    pais = str(emp.get("pais") or "").upper()
    if "COLOMBIA" in pais or pais in ("CO", "COL"):
        return "COP", "COP"
    mon = str(emp.get("moneda") or (emp.get("params") or {}).get("moneda") or "").upper()
    if mon in ("COP", "COL"):
        return "COP", "COP"
    if mon in ("USD", "US$", "U$S"):
        return "USD", "USD"
    # Default: si tiene ticker_bvc → COP; si Yahoo sin .CL → USD
    if emp.get("ticker_bvc"):
        return "COP", "COP"
    if emp.get("fuente", "").startswith("Yahoo"):
        return "USD", "USD"
    return "COP", "COP"


def aplicar_monedas_a_empresa(nombre_empresa=None, emp=None):
    """Monedas alineadas. Restaura catálogo y usa ticker canónico (no AAPL en ISA)."""
    if nombre_empresa and nombre_empresa in _EMPRESAS_CATALOGO_INMUTABLE:
        _restaurar_entrada_catalogo(nombre_empresa)
    if emp is None and nombre_empresa:
        emp = resolver_empresa(nombre_empresa)
    if not emp or not isinstance(emp, dict):
        return emp
    tk = ticker_canonico_empresa(nombre_empresa) if nombre_empresa else None
    if not tk:
        tk = asegurar_sufijo_cl_bvc(emp.get("ticker_yf") or emp.get("ticker_bvc"))
    mm, mp = monedas_alineadas_por_ticker(ticker=tk, nombre_empresa=nombre_empresa, emp=emp)
    emp["moneda"] = mm
    emp["moneda_precio"] = mp
    emp.setdefault("params", {})
    emp["params"]["moneda"] = mm
    emp["params"]["precio_moneda"] = mp
    emp["params"]["moneda_precio"] = mp
    if tk:
        emp["ticker_yf"] = tk
    return emp


# ---------------------------------------------------------------------------
# Resultados de pestañas en la sesión (consulta asistida + reset al cambiar empresa)
# ---------------------------------------------------------------------------
RESULTADOS_SESION = {
    "empresa": None,
    "tabs": {},  # "1".."7" -> dict serializable
}


def reset_resultados_sesion(nombre_empresa=None):
    """Limpia todo lo generado en pestañas (cambio de empresa o inicio)."""
    RESULTADOS_SESION["empresa"] = nombre_empresa
    RESULTADOS_SESION["tabs"] = {}


def guardar_resultado_tab(tab_id, nombre_empresa, payload):
    """Guarda un resumen estructurado de la pestaña para el asistente."""
    if not isinstance(payload, dict):
        return
    emp_act = RESULTADOS_SESION.get("empresa")
    if emp_act and nombre_empresa and str(emp_act) != str(nombre_empresa):
        RESULTADOS_SESION["tabs"] = {}
    RESULTADOS_SESION["empresa"] = nombre_empresa
    RESULTADOS_SESION["tabs"][str(tab_id)] = payload


def _html_a_texto(html, max_len=2500):
    if html is None:
        return ""
    import re
    t = str(html)
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", t)
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</p>", "\n", t)
    t = re.sub(r"(?is)<li[^>]*>", "• ", t)
    t = re.sub(r"(?is)<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"&lt;", "<", t)
    t = re.sub(r"&gt;", ">", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) > max_len:
        t = t[: max_len - 20] + " …[recortado]"
    return t



def extraer_resumen_comite_ia(html_o_texto, max_monitoreo=3):
    """
    Extrae del output del Comité IA solo lo útil para el PDF ejecutivo:
      - Recomendación final
      - Puntaje de viabilidad
      - Hasta N puntos de monitoreo / factores críticos
    Devuelve dict + texto plano corto listo para informe.
    """
    import re
    raw = _html_a_texto(html_o_texto, max_len=12000) if html_o_texto else ""
    if not raw:
        return {
            "recomendacion": None,
            "puntaje": None,
            "monitoreo": [],
            "texto": "",
            "ok": False,
        }
    # Si el texto es el prompt del comité (eco del asistente genérico), no usarlo
    _ru = raw.upper().replace("Ó", "O").replace("Í", "I")
    if (
        "ACTUA COMO UN COMITE INTERDISCIPLINARIO" in _ru
        or "CONTEXTO DE ENTRADA (CALCULADO POR EL MODELO" in _ru
        or ("INSTRUCCIONES Y FORMATO DE SALIDA" in _ru and "RECOMENDACION FINAL" in _ru and "APORTES DEL CFO" in _ru and len(raw) < 3500)
    ):
        # Puede ser solo el prompt sin deliberación real
        if "APORTES DEL CFO" in _ru and "[...]" in raw:
            return {
                "recomendacion": None,
                "puntaje": None,
                "monitoreo": [],
                "texto": "",
                "ok": False,
            }

    def _limpia(s):
        s = re.sub(r"[*#_`]+", "", str(s or "")).strip()
        s = re.sub(r"\s+", " ", s)
        return s.strip(" -:;|")

    recomendacion = None
    puntaje = None
    monitoreo = []

    # RECOMENDACIÓN FINAL
    for pat in (
        r"RECOMENDACI[ÓO]N\s+FINAL\s*[:：]\s*([^\n]+)",
        r"Recomendaci[oó]n\s+final\s*[:：]\s*([^\n]+)",
        r"\b(INVERTIR\s+CONDICIONALMENTE|NO\s+INVERTIR|INVERTIR)\b",
    ):
        mm = re.search(pat, raw, flags=re.I)
        if mm:
            recomendacion = _limpia(mm.group(1) if mm.lastindex else mm.group(0))
            break

    # PUNTAJE
    for pat in (
        r"PUNTAJE\s+DE\s+VIABILIDAD\s*[:：]\s*([^\n]+)",
        r"Puntaje\s+de\s+viabilidad\s*[:：]\s*([^\n]+)",
        r"PUNTAJE\s*[:：]\s*([0-9]+(?:\s*/\s*10)?)",
        r"\b([0-9]{1,2})\s*/\s*10\b",
    ):
        mm = re.search(pat, raw, flags=re.I)
        if mm:
            puntaje = _limpia(mm.group(1))
            # normalizar a "x/10" si solo es número
            if re.fullmatch(r"[0-9]{1,2}", puntaje or ""):
                puntaje = f"{puntaje}/10"
            break

    # Bloque de monitoreo / factores críticos
    bloque = None
    for pat in (
        r"(?:FACTORES\s+CR[IÍ]TICOS|PUNTOS\s+DE\s+MONITOREO|Puntos\s+de\s+monitoreo|"
        r"Factores\s+cr[ií]ticos)[^\n]*\n(.*?)(?=\n\s*##|\n\s*[A-ZÁÉÍÓÚ]{3,}\s*$|$)",
        r"(?:FACTORES\s+CR[IÍ]TICOS|PUNTOS\s+DE\s+MONITOREO)[:\s]*(.*)",
    ):
        mm = re.search(pat, raw, flags=re.I | re.S)
        if mm:
            bloque = mm.group(1)
            break

    if bloque:
        lineas = []
        for ln in bloque.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            # bullets / numeración
            ln2 = re.sub(r"^[•\-\*\d\.)\(]+\s*", "", ln).strip()
            if len(ln2) < 8:
                continue
            if re.match(r"^(DELIBERACI|AN[AÁ]LISIS|DECISI[OÓ]N|RECOMENDACI)", ln2, re.I):
                break
            lineas.append(_limpia(ln2))
            if len(lineas) >= int(max_monitoreo):
                break
        monitoreo = lineas

    # Fallback monitoreo: buscar frases con "monitore" o "riesgo" cerca del final
    if not monitoreo:
        cand = re.findall(
            r"(?:^|\n)\s*(?:\d+[\.\)]\s*|•\s*|\-\s*)([^\n]{20,180})",
            raw[-2500:],
        )
        for c in cand:
            c2 = _limpia(c)
            if c2 and c2 not in monitoreo:
                monitoreo.append(c2)
            if len(monitoreo) >= int(max_monitoreo):
                break

    partes = []
    if recomendacion:
        partes.append(f"Recomendación final: {recomendacion}")
    if puntaje:
        partes.append(f"Puntaje de viabilidad: {puntaje}")
    if monitoreo:
        partes.append("Puntos de monitoreo:")
        for i, p in enumerate(monitoreo, 1):
            partes.append(f"  {i}. {p}")
    texto = "\n".join(partes).strip()
    ok = bool(recomendacion or puntaje or monitoreo)
    if not ok:
        # último recurso: primeras ~400 chars del texto plano
        texto = (raw[:400] + "…") if len(raw) > 400 else raw
    return {
        "recomendacion": recomendacion,
        "puntaje": puntaje,
        "monitoreo": monitoreo,
        "texto": texto,
        "ok": ok,
    }



def _df_a_registros(df, max_rows=12):
    try:
        if df is None:
            return None
        import pandas as _pd
        if not isinstance(df, _pd.DataFrame) or df.empty:
            return None
        return df.head(max_rows).round(4).to_dict(orient="records")
    except Exception:
        return None


def texto_resultados_sesion_para_asistente(nombre_empresa=None, max_chars=14000):
    """Texto/JSON compacto de lo ya ejecutado en pestañas (si coincide la empresa)."""
    import json as _json
    emp = RESULTADOS_SESION.get("empresa")
    tabs = RESULTADOS_SESION.get("tabs") or {}
    if not tabs:
        return {
            "estado": "sin_corridas",
            "detalle": "Aún no se ha ejecutado ninguna pestaña en esta sesión. Solo hay parámetros/histórico de la ficha.",
        }
    if nombre_empresa and emp and str(nombre_empresa) != str(emp):
        return {
            "estado": "empresa_distinta",
            "empresa_resultados": emp,
            "empresa_pregunta": nombre_empresa,
            "detalle": "Los resultados en memoria son de otra empresa. Ejecute de nuevo las pestañas.",
        }
    labels = {
        "1": "Pronóstico (FCFF / fan chart)",
        "2": "Escenarios DCF",
        "3": "Auditoría de supuestos",
        "4": "Recomendación de comité",
        "5": "VPN / TIR / Payback",
        "6": "Comparación sectorial",
        "7": "Informe ejecutivo",
    }
    out = {
        "estado": "ok",
        "empresa": emp,
        "pestañas_ejecutadas": [labels.get(k, k) for k in sorted(tabs.keys(), key=lambda x: int(x) if str(x).isdigit() else 99)],
        "resultados": {},
    }
    for k in sorted(tabs.keys(), key=lambda x: int(x) if str(x).isdigit() else 99):
        out["resultados"][labels.get(k, f"Pestaña {k}")] = tabs[k]
    raw = _json.dumps(out, ensure_ascii=False, default=str)
    if len(raw) > max_chars:
        out["resultados"] = {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in list(v.items())[:8]})
                             for k, v in list(out["resultados"].items())}
        raw = _json.dumps(out, ensure_ascii=False, default=str)
        if len(raw) > max_chars:
            return {"estado": "ok_recortado", "empresa": emp,
                    "pestañas_ejecutadas": out["pestañas_ejecutadas"],
                    "extracto": raw[:max_chars]}
    return out



# Peers de referencia por sector Yahoo / industria (tickers líquidos, multisectorial).
# Se usan cuando la empresa focal no trae peers manuales.
# Claves = subcadenas normalizadas de sector o industry.
PEERS_POR_SECTOR = {
    # Energía / petróleo / utilities (alineado con catálogo BVC)
    "energy": ["XOM", "CVX", "BP", "SHEL", "TTE", "EC"],
    "oil": ["XOM", "CVX", "BP", "EC", "PBR", "EQNR"],
    "gas": ["XOM", "CVX", "EQNR", "EC", "SLB"],
    "utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC"],
    "electric": ["NEE", "DUK", "SO", "AEP", "EXC", "ED"],
    "renewable": ["NEE", "ENPH", "FSLR", "BEP", "CWEN"],
    "transmisión": ["NEE", "DUK", "SO", "AEP"],
    "infraestructura": ["NEE", "DUK", "WM", "RSG"],
    # Tecnología
    "technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "ORCL"],
    "software": ["MSFT", "ORCL", "ADBE", "CRM", "NOW", "INTU"],
    "semiconductor": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM"],
    "information technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "ORCL"],
    # Salud
    "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY"],
    "pharma": ["PFE", "JNJ", "MRK", "ABBV", "LLY", "AZN"],
    "biotechnology": ["AMGN", "GILD", "REGN", "VRTX", "BIIB"],
    # Finanzas
    "financial": ["JPM", "BAC", "WFC", "GS", "MS", "C"],
    "banks": ["JPM", "BAC", "WFC", "C", "USB", "PNC"],
    "insurance": ["BRK-B", "MET", "PRU", "AIG", "ALL"],
    "capital markets": ["GS", "MS", "SCHW", "BLK", "SPGI"],
    # Consumo
    "consumer cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX"],
    "consumer defensive": ["PG", "KO", "PEP", "WMT", "COST", "CL"],
    "retail": ["AMZN", "WMT", "COST", "TGT", "HD"],
    "automotive": ["TSLA", "F", "GM", "TM", "HMC"],
    # Industriales / materiales
    "industrials": ["CAT", "GE", "HON", "UPS", "BA", "RTX"],
    "aerospace": ["BA", "RTX", "LMT", "NOC", "GD"],
    "basic materials": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM"],
    "mining": ["BHP", "RIO", "VALE", "FCX", "NEM"],
    "steel": ["NUE", "X", "STLD", "CLF"],
    # Telecom / media
    "communication": ["GOOGL", "META", "DIS", "NFLX", "T", "VZ"],
    "telecom": ["T", "VZ", "TMUS", "CMCSA"],
    # Real estate
    "real estate": ["AMT", "PLD", "CCI", "EQIX", "SPG", "O"],
    "reit": ["AMT", "PLD", "CCI", "EQIX", "O", "SPG"],
    # Colombia / LatAm frecuentes
    "colombia": ["EC", "CIB", "BVN"],
    "petróleo": ["EC", "XOM", "PBR", "CVX"],
    "bancos": ["JPM", "BAC", "C", "WFC"],
}


def _normalizar_texto_sector(texto):
    """Normaliza acentos, guiones Unicode y espacios para comparar sectores."""
    if texto is None:
        return ""
    raw = str(texto).replace("—", "-").replace("–", "-").replace("−", "-").replace("‑", "-")
    t = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", t).strip()


def obtener_tickers_peers_sector(sector, industry="", exclude_ticker=None, max_peers=6):
    """
    Resuelve tickers comparables del mismo sector/industria.
    Prioridad: claves PEERS_POR_SECTOR que coincidan con sector o industry.
    Incluye alias de industrias Yahoo frecuentes (Consumer Electronics → technology, etc.).
    """
    blob = _normalizar_texto_sector(f"{sector} {industry}")
    # Alias industria/sector Yahoo → claves de PEERS_POR_SECTOR
    _ALIAS = {
        "consumer electronics": "technology",
        "internet content": "communication",
        "internet content & information": "communication",
        "software—infrastructure": "software",
        "software—application": "software",
        "software infrastructure": "software",
        "software application": "software",
        "semiconductors": "semiconductor",
        "semiconductor equipment": "semiconductor",
        "drug manufacturers": "pharma",
        "biotechnology": "biotechnology",
        "banks—diversified": "banks",
        "banks diversified": "banks",
        "banks—regional": "banks",
        "oil & gas integrated": "oil",
        "oil & gas e&p": "oil",
        "oil & gas midstream": "gas",
        "utilities—regulated electric": "electric",
        "utilities regulated electric": "electric",
        "utilities—renewable": "renewable",
        "auto manufacturers": "automotive",
        "discount stores": "retail",
        "internet retail": "retail",
        "telecom services": "telecom",
        "reits": "reit",
        "specialty retail": "retail",
        "packaged foods": "consumer defensive",
        "household & personal products": "consumer defensive",
        "aerospace & defense": "aerospace",
        "capital markets": "capital markets",
        "credit services": "financial",
        "asset management": "capital markets",
        "information technology services": "information technology",
        "scientific & technical instruments": "technology",
        "electronic components": "semiconductor",
        "computer hardware": "technology",
    }
    for alias, key in _ALIAS.items():
        if alias in blob and key not in blob:
            blob = f"{blob} {key}"

    exclude = set()
    if exclude_ticker:
        ex = str(exclude_ticker).upper().strip()
        exclude.add(ex)
        exclude.add(ex.split(".")[0])

    found = []
    seen = set()
    claves = sorted(PEERS_POR_SECTOR.keys(), key=len, reverse=True)
    matched_keys = []
    for k in claves:
        if k in blob:
            matched_keys.append(k)
    if not matched_keys:
        for k in claves:
            for token in k.split():
                if len(token) >= 4 and token in blob:
                    matched_keys.append(k)
                    break
    # Último recurso: primeras palabras del sector Yahoo genérico
    if not matched_keys:
        for token in ("technology", "healthcare", "financial", "energy", "utilities",
                      "consumer", "industrial", "communication", "basic materials", "real estate"):
            if token in blob and token in PEERS_POR_SECTOR:
                matched_keys.append(token)

    for k in matched_keys:
        for t in PEERS_POR_SECTOR.get(k, []):
            tu = t.upper()
            if tu in seen or tu in exclude or tu.split(".")[0] in exclude:
                continue
            seen.add(tu)
            found.append(tu)
            if len(found) >= max_peers:
                return found, matched_keys[:3]
    return found, matched_keys[:3]


def filtrar_empresas_mismo_sector(sector_focal, industry_focal=""):
    """Empresas del catálogo + runtime cuyo sector solapa con el focal."""
    tokens_f = set(_normalizar_texto_sector(f"{sector_focal} {industry_focal}").split())
    # tokens genéricos poco útiles (permitir tech-like de 3+ letras si son claves de sector)
    stop = {"de", "y", "the", "and", "or", "a", "la", "el", "/", "-", "no", "clasificado", "none"}
    tokens_f = {t for t in tokens_f if (len(t) >= 4 or t in PEERS_POR_SECTOR) and t not in stop}
    # Añadir claves PEERS que estén contenidas en el texto del sector
    blob_f = _normalizar_texto_sector(f"{sector_focal} {industry_focal}")
    for k in PEERS_POR_SECTOR:
        if k in blob_f:
            tokens_f.add(k)
    matches = {}
    for nombre, emp in list(EMPRESAS.items()) + list(EMPRESAS_RUNTIME.items()):
        sec = _normalizar_texto_sector(emp.get("sector", ""))
        if not tokens_f:
            continue
        # solape de tokens o subcadena
        hit = any(t in sec for t in tokens_f) or any(
            t in sec for t in ("energy", "utilit", "oil", "electric", "gas", "petroleo")
            if any(x in _normalizar_texto_sector(sector_focal) for x in ("energy", "utilit", "oil", "electric", "gas", "petroleo", "energia", "transmision"))
        )
        # match más general: alguna palabra clave compartida de PEERS
        if not hit:
            for k in PEERS_POR_SECTOR:
                if k in _normalizar_texto_sector(sector_focal) and k in sec:
                    hit = True
                    break
        if hit:
            matches[nombre] = emp
    return matches


def _scale_yf_to_miles_millones(value, currency="USD"):
    """Convierte cifras yfinance a miles de millones de la moneda reportada.
    Yahoo reporta montos absolutos; el catálogo BVC usa miles de millones (moneda del emisor).
    Para empresas internacionales dejamos la unidad en miles de millones de su moneda.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    return v / 1e9


def buscar_y_descargar_empresa(query, peers_tickers=""):
    """
    Busca una empresa por ticker Yahoo Finance (ej. AAPL, MSFT, EC, ISA.CL, PFE)
    o por nombre parcial, descarga financieros + parámetros de mercado y los
    registra en EMPRESAS_RUNTIME para que el resto de pestañas los use.

    peers_tickers: lista separada por comas de tickers comparables (opcional).
    Retorna (ok, mensaje_html, nombre_display, params_tuple para UI).
    """
    from html import escape
    if not HAS_YF:
        return False, "<div class='result-note'><b>yfinance no está instalado.</b> Ejecuta la celda de pip e inténtalo de nuevo.</div>", None, None

    q = (query or "").strip()
    if not q:
        return False, "<div class='result-note'>Escribe un ticker (ej. <code>AAPL</code>, <code>EC</code>, <code>ISA.CL</code>) o un nombre.</div>", None, None

    ticker_candidates = candidatos_ticker_yf(q)

    info = None
    used_ticker = None
    t_obj = None
    for cand in ticker_candidates:
        try:
            t_obj = yf.Ticker(cand)
            info = t_obj.info or {}
            # Validar que haya algo útil
            if info.get("regularMarketPrice") or info.get("currentPrice") or info.get("shortName") or info.get("longName"):
                used_ticker = cand
                break
            # financials como fallback de validez
            fin = getattr(t_obj, "financials", None)
            if fin is not None and not fin.empty:
                used_ticker = cand
                break
        except Exception:
            continue

    if not used_ticker:
        return False, f"<div class='result-note'><b>No se encontró</b> «{escape(q)}» en Yahoo Finance. Prueba el ticker exacto (ej. EC para Ecopetrol, ISA.CL, AAPL).</div>", None, None

    # Descargar financieros
    df_fin, msg_fin = descargar_financieros_yfinance(used_ticker)
    if df_fin is None or len(df_fin) < 2:
        # Intentar con balance/cashflow mínimos
        msg_extra = msg_fin or "sin serie suficiente"
        return False, f"<div class='result-note'><b>{escape(used_ticker)}</b> encontrado, pero {escape(msg_extra)}. Carga un Excel/CSV o elige otro ticker.</div>", None, None

    # descargar_financieros_yfinance YA devuelve cifras en miles de millones de la moneda local.
    # NO volver a dividir por 1e9 (doble escalado → valores ~0 y DCF inservible).
    df_mm = df_fin.copy()
    if "Ingresos" in df_mm.columns:
        df_mm = df_mm[df_mm["Ingresos"].apply(lambda x: abs(float(x)) > 1e-9)]
    # No incluir el año calendario en curso
    anio_actual = datetime.now().year
    df_mm = df_mm[df_mm.index.astype(int) < anio_actual]

    ticker_sym = str(used_ticker).split(".")[0].upper()
    name = (info.get("longName") or info.get("shortName") or ticker_sym)
    name = str(name).strip()
    # Evitar duplicar el ticker si Yahoo ya lo incluye en el nombre
    if name.upper().endswith(ticker_sym) and " " in name:
        pass  # se unifica abajo como "Nombre — TICKER"
    sector = info.get("sector") or "No clasificado"
    industry = info.get("industry") or ""
    descripcion = (info.get("longBusinessSummary") or "")[:280] or f"Empresa cotizada ({used_ticker}). Datos vía Yahoo Finance."

    # Parámetros 100% desde esta empresa (histórico + info Yahoo). Sin catálogo BVC.
    try:
        # Adjuntar balance sheet para NCI / asociados de esta empresa
        try:
            bs = getattr(t_obj, "balance_sheet", None)
            if bs is not None and not getattr(bs, "empty", True):
                info = dict(info)
                info["_balance_sheet"] = bs
        except Exception:
            pass
        params = derivar_params_desde_cero(df_mm, info=info, ticker_yf=used_ticker)
    except Exception as e:
        # No registrar una empresa con parámetros vacíos: podría producir una valoración aparentemente válida.
        return False, (
            f"<div class='result-note'><b>No fue posible derivar parámetros financieros para "
            f"{escape(used_ticker)}.</b> {escape(str(e))}. Verifica los datos de Yahoo o carga un archivo propio.</div>"
        ), None, None

    # Histórico en formato catálogo
    hist = {"Año": list(df_mm.index.astype(int))}
    for col in ["Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC", "Delta_NWC", "NOPAT", "FCFF"]:
        if col in df_mm.columns:
            # Los faltantes permanecen explícitos; cero es un dato económico, no un valor por defecto.
            hist[col] = [float(x) if pd.notna(x) else None for x in df_mm[col].values]
        else:
            hist[col] = [None] * len(hist["Año"])

    # Peers: manuales del usuario, o automáticos del mismo sector/industry
    peers = []
    if peers_tickers:
        peers = [p.strip().upper() for p in peers_tickers.replace(";", ",").split(",") if p.strip()]
    if not peers:
        auto_peers, _keys = obtener_tickers_peers_sector(
            sector, industry, exclude_ticker=used_ticker, max_peers=5
        )
        peers = auto_peers

    # Nombre completo + abreviatura Yahoo (ticker base)
    display_name = f"{name} — {ticker_sym}"
    if display_name in EMPRESAS or display_name in EMPRESAS_RUNTIME:
        display_name = f"{name} — {used_ticker}"

    # financialCurrency = moneda de los EEFF (modelo); currency = moneda del precio de cotización.
    # En ADRs (ej. EC) pueden diferir: EEFF en COP, precio en USD → upside no comparable sin FX.
    fin_cur = (info.get("financialCurrency") or info.get("currency") or "USD")
    px_cur = (info.get("currency") or fin_cur)
    if isinstance(fin_cur, str) and fin_cur.upper() in ("US$", "U$S"):
        fin_cur = "USD"
    if isinstance(px_cur, str) and px_cur.upper() in ("US$", "U$S"):
        px_cur = "USD"
    # Propagar moneda también dentro de params (UI / CAPM / VPS)
    # Alinear monedas por ticker (BVC .CL → COP/COP; US → USD/USD)
    used_ticker = asegurar_sufijo_cl_bvc(used_ticker) or used_ticker
    if str(used_ticker).upper().endswith(".CL") or es_ticker_bvc(used_ticker):
        fin_cur, px_cur = "COP", "COP"
    elif str(used_ticker).split(".")[0].upper() in _TICKERS_NUNCA_CL:
        fin_cur, px_cur = "USD", "USD"
    else:
        # respetar Yahoo si no es BVC/US conocido
        fin_cur = fin_cur if fin_cur else "USD"
        px_cur = px_cur if px_cur else fin_cur
        # No cambiar la etiqueta de moneda sin convertir los estados financieros.
        # Si difieren, las funciones de valoración deben bloquear el upside hasta convertir por FX.
    params["moneda"] = fin_cur
    params["moneda_precio"] = px_cur
    params["precio_moneda"] = px_cur
    params["currency"] = px_cur
    EMPRESAS_RUNTIME[display_name] = {
        "ticker_bvc": used_ticker.split(".")[0] if str(used_ticker).endswith(".CL") else None,
        "ticker_yf": used_ticker,
        "sector": f"{sector}" + (f" / {industry}" if industry else ""),
        "descripcion": descripcion,
        "params": params,
        "historico": hist,
        "peers": peers,
        "fuente": f"Yahoo Finance ({used_ticker})",
        "moneda": fin_cur,
        "moneda_precio": px_cur,
        "pais": info.get("country") or "",
    }

    precio = info.get("regularMarketPrice") or info.get("currentPrice")
    precio_txt = f"{precio:,.2f} {info.get('currency', '')}" if precio else "N/D"
    html = f"""
    <div class='section-card'>
      <b>✅ Empresa descargada:</b> {escape(display_name)}<br>
      <b>Sector:</b> {escape(str(sector))} {escape(str(industry))}<br>
      <b>Ticker:</b> {escape(used_ticker)} · <b>Precio:</b> {precio_txt}<br>
      <b>Histórico:</b> {len(df_mm)} años · EEFF en <b>miles de millones {escape(str(info.get('financialCurrency') or info.get('currency') or 'N/D'))}</b>
      · cotización en <b>{escape(str(info.get('currency') or 'N/D'))}</b>
      (sin re-escalar; si EEFF≠cotización, p.ej. ADR, el upside se anula hasta convertir FX).<br>
      {escape(msg_fin)}<br>
      <span style='color:#065F46'>Parámetros derivados <b>desde cero</b> con datos de esta empresa (Yahoo + histórico propio); no se usan cifras del catálogo BVC.
      <b>Importante:</b> EV/Equity/CAPEX están en miles de millones de la moneda del ticker, no en COP si la empresa reporta en USD u otra divisa.
      Revísalos antes de valorar. La comparación sectorial usará este emisor y peers del <b>mismo sector</b>.</span>
    </div>
    """
    # Tuple de params para rellenar UI (mismo orden que al_cambiar_empresa)
    p = params
    params_tuple = (
        p["de_ratio"], p["kd"], p["tax"], p["g"], p["beta_u"],
        p["capital_invertido"], p["deuda_neta"], p["inversion_inicial"],
        p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0),
        p.get("acciones"), p.get("exit_multiple", 10.0),
    )
    return True, html, display_name, params_tuple


def resolver_empresa(nombre_empresa):
    """Busca primero en catálogo estático, luego en runtime descargado."""
    if nombre_empresa in _EMPRESAS_CATALOGO_INMUTABLE:
        _restaurar_entrada_catalogo(nombre_empresa)
    if nombre_empresa in EMPRESAS:
        return EMPRESAS[nombre_empresa]
    if nombre_empresa in EMPRESAS_RUNTIME:
        return EMPRESAS_RUNTIME[nombre_empresa]
    # match parcial runtime
    if nombre_empresa and len(str(nombre_empresa).strip()) >= 4:
        q = str(nombre_empresa).strip().lower()
        hits = [v for k, v in EMPRESAS_RUNTIME.items() if q in k.lower() or k.lower() in q]
        if len(hits) == 1:  # solo si es inequívoco: evita mezclar datos de otra empresa
            return hits[0]
    return None


def listar_empresas_disponibles():
    """Choices del dropdown: catálogo + descargadas en sesión."""
    base = list(EMPRESAS.keys())
    extra = [k for k in EMPRESAS_RUNTIME.keys() if k not in EMPRESAS]
    return base + extra



DATOS_SECTOR = {
    "Empresa": ["ISA", "EPM", "GEB", "Celsia", "Enel Colombia"],
    "Ingresos (miles M)": [16034, 28500, 9800, 6200, 11200],
    "EBITDA (miles M)": [7902, 9800, 5100, 2100, 3800],
    "Margen EBITDA (%)": [49.3, 34.4, 52.0, 33.9, 33.9],
    "ROIC (%)": [11.8, 9.5, 10.2, 8.7, 9.1],
    "WACC estimado (%)": [8.9, 9.4, 8.7, 9.8, 9.2],
    "D/E": [1.20, 1.45, 0.95, 1.10, 1.30],
    "EV/EBITDA (x)": [8.5, 7.8, 9.2, 7.1, 8.0],
    "Crecimiento Ingresos 3a (%)": [6.8, 5.2, 7.5, 4.1, 5.9],
    "FCFF (miles M)": [2200, 3100, 1800, 650, 1400],
}
df_sector = pd.DataFrame(DATOS_SECTOR)


def float_tip(label, explanation):
    """Texto con tooltip flotante al pasar el cursor."""
    return (
        f'<span class="tip-wrap">{label}'
        f'<span class="tip-float">{explanation}</span></span>'
    )


def tip(texto):
    """Caja de explicación de resultados — siempre visible, alto contraste."""
    return (
        '<div class="tip-box">'
        '<div class="tip-title">💡 En palabras sencillas</div>'
        f'<div class="tip-body">{texto}</div>'
        "</div>"
    )


def help_chip(texto):
    """Ayuda compacta bajo un control (slider/archivo). HTML seguro para gr.HTML."""
    t = texto or ""
    return f'<div class="help-chip">{t}</div>'


def chart_bubble(titulo, texto, visible=True):
    """Nota bajo un gráfico: título + explicación didáctica."""
    return (
        f'<div class="result-note" style="margin-top:8px">'
        f'<b>{titulo}</b><br>{texto}'
        f'</div>'
    )


def anotar_grafico(ax, texto, loc="lower left"):
    """Leyenda didáctica dentro de un eje Matplotlib (esquina, caja semitransparente)."""
    if ax is None or not texto:
        return
    loc_map = {
        "lower left": (0.02, 0.02, "left", "bottom"),
        "lower right": (0.98, 0.02, "right", "bottom"),
        "upper left": (0.02, 0.98, "left", "top"),
        "upper right": (0.98, 0.98, "right", "top"),
    }
    x, y, ha, va = loc_map.get(loc, loc_map["lower left"])
    ax.text(
        x, y, str(texto),
        transform=ax.transAxes,
        fontsize=8,
        ha=ha, va=va,
        color="#E2E8F0",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#0F172A", edgecolor="#334155", alpha=0.85),
        family="sans-serif",
        linespacing=1.35,
        zorder=10,
    )


def result_note(titulo, texto):
    """Nota explicativa adicional sobre un resultado numérico concreto."""
    return (
        f'<div class="result-note">'
        f'<b>{titulo}</b><br>{texto}'
        f"</div>"
    )


GLOSARIO_ITEMS = [
    ("Ingresos", "Todo el dinero que entra por ventas o servicios."),
    ("EBITDA", "Ganancia operativa antes de depreciaciones, intereses e impuestos. Mide qué tan rentable es el día a día."),
    ("EBIT", "Ganancia operativa después de depreciaciones (desgaste de equipos)."),
    ("CAPEX", "Plata invertida en torres, plantas, equipos (activos de largo plazo)."),
    ("NWC / Capital de trabajo", "Dinero amarrado en el día a día (inventarios, cuentas por cobrar menos por pagar)."),
    ("FCFF", "Flujo de caja libre = dinero que queda después de operar e invertir. Es lo que se puede repartir a dueños y acreedores."),
    ("WACC", "Costo promedio del dinero de la empresa (mezcla de deuda y capital de los dueños)."),
    ("ROIC", "Qué tanto rinde cada peso invertido en el negocio."),
    ("D/E", "Cuánta deuda hay por cada peso de capital de los dueños."),
    ("EV (Enterprise Value)", "Valor total del negocio, como si lo compraras completo (incluyendo deuda)."),
    ("Equity Value", "Lo que les quedaría a los dueños después de pagar la deuda neta."),
    ("VPN", "Si un proyecto deja más (o menos) valor del que cuesta, medido en pesos de hoy."),
    ("TIR", "La rentabilidad anual que “paga” el proyecto."),
    ("Payback", "Cuántos años tarda en recuperarse la inversión inicial."),
    ("g", "Ritmo al que se espera que crezcan los flujos en el largo plazo."),
    ("Beta", "Qué tanto se mueve la acción respecto al mercado. Cerca de 1 = similar; menor a 1 = más estable."),
]


def glosario_html():
    items = "".join(
        f'<div class="gloss-item"><span class="gloss-term">{t}</span>'
        f'<span class="gloss-def">{d}</span></div>'
        for t, d in GLOSARIO_ITEMS
    )
    return f"""
<div class="glossary-panel">
  <div class="glossary-intro">
    Consulta este panel cuando veas una sigla o término que no reconozcas.
    Puedes <b>minimizarlo</b> haciendo clic en la barra del acordeón (arriba).
  </div>
  <div class="glossary-grid">{items}</div>
</div>
"""



# =============================================================================
# CONECTOR DE MERCADO POR CAPAS (BVC / Colombia)
# Proveedores: yahoo (default) | api_key (gancho) | manual
# =============================================================================

# Estado de configuración del conector (se actualiza desde la UI)
MERCADO_CONFIG = {
    "proveedor": "yahoo",          # yahoo | api_key | manual
    "api_key": "",
    "api_base_url": "",            # opcional: endpoint propio del vendor
    "api_timeout": 12,
}


def _validar_url_vendor(url):
    """Solo https y hosts públicos: evita SSRF (metadata cloud, localhost, redes internas)."""
    import ipaddress
    import socket
    import urllib.parse
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise ValueError("La URL del vendor debe empezar por https://")
    host = u.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal")):
        raise ValueError("Host no permitido")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"No se pudo resolver el host: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("La URL apunta a una dirección interna/no pública")
    return url


def configurar_mercado(proveedor="yahoo", api_key="", api_base_url="", api_timeout=12):
    """Actualiza el proveedor activo del conector de mercado."""
    prov = (proveedor or "yahoo").strip().lower()
    if prov not in ("yahoo", "api_key", "manual"):
        prov = "yahoo"
    MERCADO_CONFIG["proveedor"] = prov
    MERCADO_CONFIG["api_key"] = (api_key or "").strip()
    MERCADO_CONFIG["api_base_url"] = ""
    MERCADO_CONFIG["url_error"] = ""
    if (api_base_url or "").strip():
        try:
            MERCADO_CONFIG["api_base_url"] = _validar_url_vendor((api_base_url or "").strip())
        except ValueError as exc:
            MERCADO_CONFIG["url_error"] = str(exc)
    try:
        MERCADO_CONFIG["api_timeout"] = int(api_timeout or 12)
    except Exception:
        MERCADO_CONFIG["api_timeout"] = 12
    return dict(MERCADO_CONFIG)


def _respuesta_mercado_vacia(mensaje, proveedor="none"):
    return {
        "ok": False,
        "mensaje": mensaje,
        "precio": None,
        "moneda": "COP",
        "cambio_pct": None,
        "market_cap": None,
        "beta": None,
        "pe": None,
        "enterprise_to_ebitda": None,
        "proveedor": proveedor,
        "fuente": proveedor,
    }


def _finite_or_none(x):
    """Convierte a float finito o None (NaN/inf de Yahoo no deben llegar a la UI como 'nan')."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or abs(v) == float("inf"):  # NaN o ±inf
        return None
    return v


def _yf_info_dict(t):
    """Obtiene el dict info de yfinance con varios fallbacks (info a menudo vacío en .CL)."""
    info = {}
    for getter in (
        lambda: getattr(t, "info", None),
        lambda: t.get_info() if hasattr(t, "get_info") else None,
    ):
        try:
            d = getter()
            if isinstance(d, dict) and d:
                info = d
                break
        except Exception:
            continue
    return info or {}


def _yf_fast_get(fi, *keys):
    if fi is None:
        return None
    for k in keys:
        try:
            if hasattr(fi, "get"):
                v = fi.get(k)
            else:
                v = getattr(fi, k, None)
            v = _finite_or_none(v)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def _proveedor_yahoo(ticker_yf):
    """Yahoo Finance. .CL solo BVC. Métricas con cascada (info / fast_info / cálculo)."""
    ticker_yf = asegurar_sufijo_cl_bvc(ticker_yf)
    if not HAS_YF or not ticker_yf:
        return _respuesta_mercado_vacia(
            "Sin datos Yahoo: falta yfinance o ticker.",
            proveedor="yahoo",
        )
    try:
        t = yf.Ticker(ticker_yf)
        info = _yf_info_dict(t)
        fi = None
        try:
            fi = getattr(t, "fast_info", None)
        except Exception:
            fi = None

        precio = None
        cambio_pct = None
        # 1) Histórico de cierres
        try:
            hist = t.history(period="15d", auto_adjust=True)
        except Exception:
            hist = None
        if hist is not None and len(hist) > 0 and "Close" in hist.columns:
            closes = [_finite_or_none(v) for v in hist["Close"].tolist()]
            closes_ok = [c for c in closes if c is not None and c > 0]
            if closes_ok:
                precio = closes_ok[-1]
                if len(closes_ok) > 1 and closes_ok[-2]:
                    cambio_pct = (precio / closes_ok[-2] - 1.0) * 100.0
        # 2) info / fast_info
        if precio is None:
            for key in (
                "currentPrice", "regularMarketPrice", "fulldayPrice",
                "previousClose", "regularMarketPreviousClose", "postMarketPrice",
            ):
                precio = _finite_or_none(info.get(key))
                if precio is not None and precio > 0:
                    break
        if precio is None:
            precio = _yf_fast_get(
                fi, "last_price", "lastPrice", "regular_market_price",
                "previous_close", "regular_market_previous_close",
            )

        if cambio_pct is None:
            ch = _finite_or_none(info.get("regularMarketChangePercent"))
            if ch is None:
                ch = _yf_fast_get(fi, "regular_market_change_percent", "change_percent")
            if ch is not None:
                cambio_pct = ch * 100.0 if abs(ch) < 1.0 else ch

        # --- Capitalización ---
        mcap = _finite_or_none(info.get("marketCap")) or _finite_or_none(info.get("enterpriseValue"))
        if mcap is None:
            mcap = _yf_fast_get(fi, "market_cap", "marketCap")
        if mcap is None and precio and precio > 0:
            shares = (
                _finite_or_none(info.get("sharesOutstanding"))
                or _finite_or_none(info.get("impliedSharesOutstanding"))
                or _yf_fast_get(fi, "shares", "shares_outstanding")
            )
            if shares and shares > 0:
                mcap = shares * precio

        # --- Beta ---
        beta = (
            _finite_or_none(info.get("beta"))
            or _finite_or_none(info.get("beta3Year"))
            or _finite_or_none((info.get("defaultKeyStatistics") or {}).get("beta") if isinstance(info.get("defaultKeyStatistics"), dict) else None)
        )

        # --- P/E ---
        pe = (
            _finite_or_none(info.get("trailingPE"))
            or _finite_or_none(info.get("forwardPE"))
            or _finite_or_none(info.get("pegRatio"))
        )
        if pe is None and precio and precio > 0:
            eps = (
                _finite_or_none(info.get("trailingEps"))
                or _finite_or_none(info.get("epsTrailingTwelveMonths"))
                or _finite_or_none(info.get("epsCurrentYear"))
            )
            if eps and eps > 0:
                pe = precio / eps

        ev_ebitda = _finite_or_none(info.get("enterpriseToEbitda"))

        ok = precio is not None and precio > 0
        extras = []
        if mcap:
            extras.append("cap")
        if beta is not None:
            extras.append("β")
        if pe is not None:
            extras.append("P/E")
        detalle = (" · " + ", ".join(extras)) if extras else ""
        return {
            "ok": ok,
            "mensaje": (
                f"Yahoo Finance ({ticker_yf}) · precio en vivo / retrasado según Yahoo{detalle}."
                if ok else f"Yahoo no devolvió precio usable para {ticker_yf}."
            ),
            "precio": precio,
            "moneda": (
                "COP" if str(ticker_yf or "").upper().endswith(".CL")
                else (info.get("currency") or "USD")
            ),
            "cambio_pct": cambio_pct,
            "market_cap": mcap,
            "beta": beta,
            "pe": pe,
            "enterprise_to_ebitda": ev_ebitda,
            "proveedor": "yahoo",
            "fuente": f"yahoo:{ticker_yf}",
            "ticker": ticker_yf,
        }
    except Exception as e:
        return _respuesta_mercado_vacia(f"Error Yahoo ({ticker_yf}): {e}", proveedor="yahoo")


def _proveedor_api_key(ticker_yf, ticker_bvc=None):
    """
    Capa 2 (gancho profesional): vendor con API key.

    Contrato esperado del endpoint (GET):
      {API_BASE_URL}?symbol=ISA.CL   (o el path que configure el vendor)
      Header:  Authorization: Bearer <API_KEY>   ó   X-API-Key: <API_KEY>

    JSON de respuesta (campos flexibles):
      price | precio | last | close
      currency | moneda
      change_pct | cambio_pct | changePercent
      market_cap | marketCap
      beta, pe | trailingPE
      enterpriseToEbitda | ev_ebitda

    Si no hay base_url o api_key, falla de forma explícita para caer al siguiente proveedor.
    """
    api_key = MERCADO_CONFIG.get("api_key") or ""
    base = MERCADO_CONFIG.get("api_base_url") or ""
    timeout = MERCADO_CONFIG.get("api_timeout", 12)

    if not api_key:
        return _respuesta_mercado_vacia(
            "Proveedor api_key activo pero sin API key. Configúrala en el panel de mercado.",
            proveedor="api_key",
        )
    if not base:
        return _respuesta_mercado_vacia(
            "Proveedor api_key activo pero sin URL base. "
            "Ejemplo: https://tu-vendor.com/v1/quotes",
            proveedor="api_key",
        )

    symbol = ticker_yf or ticker_bvc
    if not symbol:
        return _respuesta_mercado_vacia("Sin símbolo para consultar al vendor.", proveedor="api_key")

    try:
        import urllib.parse
        import urllib.request
        import json as _json

        # Construir URL: si base ya trae query, anexar; si no, ?symbol=
        sep = "&" if ("?" in base) else "?"
        url = f"{base}{sep}symbol={urllib.parse.quote(str(symbol))}"
        if ticker_bvc:
            url += f"&ticker_bvc={urllib.parse.quote(str(ticker_bvc))}"

        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "ISA-Valuador/2.0 (conector-mercado)")
        # Dos convenciones habituales de auth
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("X-API-Key", api_key)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = _json.loads(raw)
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return _respuesta_mercado_vacia(
                f"Respuesta del vendor no es un objeto JSON ({type(data).__name__}).",
                proveedor="api_key",
            )

        def pick(*keys):
            for k in keys:
                if k in data and data[k] is not None:
                    return data[k]
            # nested common patterns
            for nest in ("data", "quote", "result"):
                sub = data.get(nest)
                if isinstance(sub, dict):
                    for k in keys:
                        if k in sub and sub[k] is not None:
                            return sub[k]
            return None

        precio = pick("price", "precio", "last", "close", "regularMarketPrice", "lastPrice")
        cambio = pick("change_pct", "cambio_pct", "changePercent", "change_percent", "variation")
        mcap = pick("market_cap", "marketCap", "marketcap")
        beta = pick("beta")
        pe = pick("pe", "trailingPE", "forwardPE", "p_e")
        ev_ebitda = pick("enterpriseToEbitda", "ev_ebitda", "evEbitda", "EV_EBITDA")
        moneda = pick("currency", "moneda") or "COP"

        try:
            precio = float(precio) if precio is not None else None
        except Exception:
            precio = None

        ok = precio is not None
        return {
            "ok": ok,
            "mensaje": (
                f"Vendor API key ({symbol}) · URL configurada por el usuario."
                if ok else f"Vendor respondió sin precio usable para {symbol}."
            ),
            "precio": precio,
            "moneda": str(moneda),
            "cambio_pct": float(cambio) if cambio is not None else None,
            "market_cap": float(mcap) if mcap is not None else None,
            "beta": float(beta) if beta is not None else None,
            "pe": float(pe) if pe is not None else None,
            "enterprise_to_ebitda": float(ev_ebitda) if ev_ebitda is not None else None,
            "proveedor": "api_key",
            "fuente": f"api_key:{symbol}",
        }
    except Exception as e:
        return _respuesta_mercado_vacia(f"Error vendor API key: {e}", proveedor="api_key")


def _proveedor_manual(ticker_yf=None, ticker_bvc=None):
    """Capa 3: no consulta red; el usuario aporta precio vía UI si se desea ampliar después."""
    return _respuesta_mercado_vacia(
        "Proveedor manual activo: no se consulta red. Usa Yahoo o API key, o carga Excel/fundamentales.",
        proveedor="manual",
    )


def obtener_datos_mercado_bvc(ticker_yf, ticker_bvc=None, proveedor=None):
    """
    Fachada del conector por capas.

    Orden según proveedor elegido:
      - yahoo:   solo Yahoo
      - api_key: intenta vendor; si falla, cae a Yahoo (fallback)
      - manual:  no red

    No afirma ser 'BVC oficial'. Etiqueta siempre el proveedor real usado.
    """
    if not ticker_yf and ticker_bvc:
        ticker_yf = asegurar_sufijo_cl_bvc(ticker_bvc)
    else:
        ticker_yf = asegurar_sufijo_cl_bvc(ticker_yf)
    prov = (proveedor or MERCADO_CONFIG.get("proveedor") or "yahoo").strip().lower()

    if prov == "manual":
        return _proveedor_manual(ticker_yf, ticker_bvc)

    if prov == "api_key":
        res = _proveedor_api_key(ticker_yf, ticker_bvc=ticker_bvc)
        if res.get("ok"):
            return res
        # Fallback a Yahoo si el vendor falla
        y = _proveedor_yahoo(ticker_yf)
        if y.get("ok"):
            y["mensaje"] = (
                f"Fallback Yahoo tras fallo/ausencia del vendor. "
                f"Detalle vendor: {res.get('mensaje', '')}"
            )
            y["proveedor"] = "yahoo_fallback"
            y["fuente"] = y.get("fuente", "yahoo") + "|fallback"
            return y
        res["mensaje"] = (
            f"{res.get('mensaje', '')} | Yahoo también falló: {y.get('mensaje', '')}"
        )
        return res

    # default: yahoo
    return _proveedor_yahoo(ticker_yf)


def aplicar_config_mercado_ui(proveedor, api_key, api_base_url):
    """Callback UI: guarda config y devuelve mensaje de estado."""
    cfg = configurar_mercado(proveedor, api_key, api_base_url)
    prov = cfg["proveedor"]
    if prov == "yahoo":
        msg = "✅ Proveedor activo: <b>Yahoo Finance</b> (default). Tickers BVC vía sufijo .CL"
    elif prov == "api_key":
        has_key = "sí" if cfg["api_key"] else "no"
        has_url = "sí" if cfg["api_base_url"] else ("no · rechazada: " + cfg.get("url_error", "") if cfg.get("url_error") else "no")
        msg = (
            f"✅ Proveedor activo: <b>API key (vendor)</b>. "
            f"API key: {has_key} · URL: {has_url}. "
            "Si el vendor falla, se usa Yahoo como respaldo."
        )
    else:
        msg = "✅ Proveedor activo: <b>manual</b> (sin consultas de red a mercado)."
    return f"<div class='section-card'>{msg}<br><span style='color:#94A3B8;font-size:0.9rem'>Esto no es un feed oficial de la BVC; es un conector por capas con fuente etiquetada.</span></div>"


# (formatear_market_cap: definición única más abajo; se eliminó la copia duplicada)



# ---------------------------------------------------------------------------
# Módulo: descarga de cifras financieras públicas (sin Excel obligatorio)
# ---------------------------------------------------------------------------

# Series curadas a partir de EEFF / informes públicos (miles de millones (moneda del emisor)).
# Se usan si yfinance no devuelve suficientes líneas.
DATOS_PUBLICOS_CURADOS = {
    "ISA — Interconexión Eléctrica": {
        "fuente": "EEFF e informes ISA (isa.co) + cruce público; 2016-2018 backcast; NWC/FCFF en parte estimados",
        "años": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
        "Ingresos": [7200, 7800, 8400, 9045, 10180, 11117, 13356, 14171, 14935, 15918],
        "EBITDA": [4100, 4500, 4850, 5200, 5850, 6884, 7821, 9114, 9747, 8680],
        "EBIT": [3200, 3550, 3800, 4100, 4650, 6072, 6869, 7598, 8409, 7336],
        "Depreciacion": [700, 750, 800, 850, 900, 812, 952, 1516, 1338, 1344],
        "CAPEX": [1800, 1950, 2050, 2100, 2311, 761, 953, 4600, 4785, 6278],
        "NWC": [950, 1050, 1120, 1200, 1350, 1450, 1600, 1750, 1850, 1950],
    },
    "GEB — Grupo Energía Bogotá": {
        "fuente": "Serie ilustrativa ampliada 10 años (respaldo pedagógico; validar con EEFF)",
        "años": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
        "Ingresos": [4800, 5200, 5700, 6200, 6800, 7500, 8200, 8900, 9400, 9800],
        "EBITDA": [2400, 2600, 2850, 3100, 3400, 3800, 4200, 4600, 4900, 5100],
        "EBIT": [1850, 2000, 2200, 2400, 2700, 3000, 3400, 3700, 4000, 4200],
        "Depreciacion": [380, 420, 460, 500, 550, 600, 650, 700, 750, 800],
        "CAPEX": [900, 1000, 1100, 1200, 1100, 1300, 1400, 1500, 1600, 1700],
        "NWC": [650, 700, 750, 800, 850, 900, 950, 1000, 1050, 1100],
    },
    "CELSIA — Celsia S.A. E.S.P.": {
        "fuente": "Serie ilustrativa ampliada 10 años (respaldo pedagógico; validar con EEFF)",
        "años": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
        "Ingresos": [3000, 3200, 3500, 3800, 4100, 4500, 5000, 5500, 5800, 6200],
        "EBITDA": [900, 1000, 1100, 1200, 1300, 1500, 1700, 1900, 2000, 2100],
        "EBIT": [650, 750, 820, 900, 1000, 1150, 1300, 1450, 1550, 1600],
        "Depreciacion": [220, 240, 260, 280, 300, 320, 350, 380, 400, 420],
        "CAPEX": [600, 650, 720, 800, 900, 1000, 1100, 1200, 1300, 1400],
        "NWC": [320, 350, 380, 400, 420, 450, 480, 500, 520, 550],
    },
}



def _yf_pick_row(df, candidates):
    """Busca la primera fila cuyo índice coincida (case-insensitive) con candidatos."""
    if df is None or getattr(df, "empty", True):
        return None
    idx_map = {_norm_col(i): i for i in df.index}
    # 1) coincidencia exacta; 2) palabra completa (nunca subcadena: 'EBIT' no debe tomar 'EBITDA'
    #    ni 'Normalized EBITDA').
    for cand in candidates:
        c = _norm_col(cand)
        if c in idx_map:
            return df.loc[idx_map[c]]
    for cand in candidates:
        patron = re.compile(rf"(?<![a-z0-9]){re.escape(_norm_col(cand))}(?![a-z0-9])")
        for k, original in idx_map.items():
            if "normalized" not in k and patron.search(k):
                return df.loc[original]
    return None


def _factor_escala_yf(row):
    """Un único divisor para TODA la serie/estado (antes se decidía valor por valor).

    Yahoo reporta estados en unidades de la moneda local (USD, COP, etc.).
    Umbrales orientativos:
      - max >= 1e8  → ya son unidades completas → /1e9 → miles de millones
      - max >= 1e4  → posiblemente miles       → /1e3
      - menor       → ya parece pre-escalado  → 1.0
    Nunca se decide fila a fila: evita mezclar escalas dentro del mismo estado.
    """
    vals = [abs(float(v)) for v in getattr(row, "values", []) if v is not None and v == v]
    m = max(vals) if vals else 0.0
    if m >= 1e8:
        return 1e9
    if m >= 1e4:
        return 1e3
    return 1.0


def _series_from_yf_row(row, factor=None):
    """Convierte una fila de yfinance (columnas = fechas) en dict año -> valor en miles de millones.

    Yahoo reporta montos en moneda local unitaria (COP, USD, etc.).
    Se normaliza a *miles de millones* de esa moneda:
      - |v| >= 1e8  →  v / 1e9   (estados financieros en unidades)
      - |v| >= 1e4  →  v / 1e3   (a veces miles)
      - menor       →  se deja igual (ya escalado)
    No se escribe 0 por NaN: el año simplemente no entra en el dict.
    """
    out = {}
    if row is None:
        return out
    for col, val in row.items():
        try:
            if hasattr(col, "year"):
                year = int(col.year)
            else:
                year = int(str(col)[:4])
            if val is None:
                continue
            v = float(val)
            if v != v:  # NaN
                continue
            out[year] = float(v / (factor if factor else _factor_escala_yf(row)))
        except Exception:
            continue
    return out


def descargar_financieros_yfinance(ticker_yf, tax_efectiva=None):
    """
    Arma Ingresos, EBITDA, EBIT, CAPEX, NWC y FCFF desde yfinance.
    Descarta años incompletos o en cero y el año calendario en curso.
    CORRECCIÓN (auditoría AAPL 2026):
      - tax ya NO está hard-codeada al 35 %; usa effectiveTaxRate de Yahoo
        o default jurisdiccional (US≈21 %, CO≈35 %, residual 25 %).
      - CAPEX proxy 4 % de ingresos (antes 12 %); NWC proxy 5 % (antes 8 %).
      - Preferir CAPEX real del cashflow cuando exista.
    Retorna DataFrame indexado por año o None, y mensaje de procedencia.
    """
    ticker_yf = asegurar_sufijo_cl_bvc(ticker_yf)
    if not HAS_YF or not ticker_yf:
        return None, "yfinance no disponible o sin ticker"
    try:
        t = yf.Ticker(ticker_yf)
        fin = getattr(t, "financials", None)
        cf = getattr(t, "cashflow", None)
        info = t.info or {}
        if fin is None or fin.empty:
            return None, f"Sin estado de resultados en Yahoo para {ticker_yf}"

        # --- Tasa impositiva efectiva (crítica para NOPAT/FCFF) ---
        if tax_efectiva is None:
            etr = _safe_float(info.get("effectiveTaxRate"))
            if etr is not None and 0.0 < etr < 0.55:
                tax_efectiva = float(etr)
            else:
                country = (info.get("country") or info.get("countryCode") or "").upper()
                if country in ("COLOMBIA", "COL", "CO"):
                    tax_efectiva = 0.35
                elif country in ("UNITED STATES", "USA", "US"):
                    tax_efectiva = 0.21
                elif country in ("BRAZIL", "BRA", "BR"):
                    tax_efectiva = 0.34
                elif country in ("MEXICO", "MEX", "MX"):
                    tax_efectiva = 0.30
                elif country in ("CHILE", "CHL", "CL"):
                    tax_efectiva = 0.27
                elif country in ("UNITED KINGDOM", "GBR", "GB", "UK"):
                    tax_efectiva = 0.25
                else:
                    tax_efectiva = 0.25
        tax_efectiva = float(np.clip(float(tax_efectiva), 0.0, 0.55))

        row_rev = _yf_pick_row(fin, ["Total Revenue", "Revenue", "Ingresos totales"])
        fac = _factor_escala_yf(row_rev)  # misma escala para ingresos, EBIT, EBITDA, D&A y CAPEX
        rev = _series_from_yf_row(row_rev, fac)
        ebit = _series_from_yf_row(_yf_pick_row(fin, ["EBIT", "Operating Income", "Ingresos operativos"]), fac)
        ebitda = _series_from_yf_row(_yf_pick_row(fin, ["EBITDA"]), fac)
        dep = _series_from_yf_row(_yf_pick_row(fin, ["Reconciled Depreciation", "Depreciation", "Depreciación"]), fac)

        capex = {}
        if cf is not None and not cf.empty:
            raw_capex = _series_from_yf_row(_yf_pick_row(cf, [
                "Capital Expenditure", "Purchase Of PPE",
                "Net PPE Purchase And Sale", "Capital Expenditures",
            ]), fac)
            for y, v in raw_capex.items():
                if v is not None and abs(float(v)) > 0:
                    capex[y] = abs(float(v))

        years = sorted(set(rev.keys()) | set(ebit.keys()) | set(ebitda.keys()))
        if len(years) < 2:
            return None, f"Yahoo devolvió pocos años ({len(years)}) para {ticker_yf}"

        # No usar el año calendario en curso ni futuros (estados anuales aún no cerrados)
        anio_actual = datetime.now().year
        years = [y for y in years if y < anio_actual]

        rows = []
        prev_nwc = None
        omitidos = []
        for y in years:
            ing = rev.get(y)
            eb = ebit.get(y)
            ebd = ebitda.get(y)
            # Exigir ingresos reales: None o ~0 = año incompleto / columna vacía de Yahoo
            if ing is None or (isinstance(ing, (int, float)) and abs(float(ing)) < 1e-9):
                omitidos.append(y)
                continue
            ing = float(ing)
            if eb is None and ebd is None:
                omitidos.append(y)
                continue
            eb = float(eb) if eb is not None else float(ebd) * 0.85
            ebd = float(ebd) if ebd is not None else float(eb) * 1.15
            d_raw = dep.get(y)
            d = float(d_raw) if d_raw is not None else max(ebd - eb, abs(ebd) * 0.10)
            cx_raw = capex.get(y)
            # Proxy CAPEX más realista (tech/hardware ~3–4 %; antes 12 % sesgaba FCFF a la baja)
            cx = float(cx_raw) if cx_raw is not None else abs(ing) * 0.04
            # NWC proxy 5 % (antes 8 %); muchas empresas tech tienen NWC bajo o negativo
            nwc = abs(ing) * 0.05
            delta = 0.0 if prev_nwc is None else nwc - prev_nwc
            nopat = eb * (1.0 - tax_efectiva)  # ← CORRECCIÓN: ya no * 0.65 fijo
            fcff = nopat + d - cx - delta
            rows.append({
                "Año": int(y),
                "Ingresos": ing,
                "EBITDA": ebd,
                "EBIT": eb,
                "Depreciacion": d,
                "CAPEX": cx,
                "NWC": nwc,
                "Delta_NWC": delta,
                "NOPAT": nopat,
                "FCFF": fcff,
            })
            prev_nwc = nwc

        if len(rows) < 3:
            return None, (
                f"No se pudo construir serie usable desde Yahoo ({ticker_yf}). "
                f"Años omitidos por datos vacíos/cero: {omitidos or 'N/D'}."
            )
        df = pd.DataFrame(rows).sort_values("Año").set_index("Año")
        while len(df) > 3 and abs(float(df["Ingresos"].iloc[-1])) < 1e-9:
            df = df.iloc[:-1]
        extra = f" Omitidos {omitidos}." if omitidos else ""
        return df, (
            f"Descargado desde Yahoo Finance ({ticker_yf}), {len(df)} años "
            f"({int(df.index.min())}–{int(df.index.max())}). "
            f"Tax efectiva usada={tax_efectiva:.1%}. "
            f"NWC/CAPEX: real cuando disponible, proxy documentado si no.{extra}"
        )
    except Exception as e:
        return None, f"Error yfinance: {e}"


def descargar_financieros_curados(nombre_empresa):
    """Serie pública curada (ISA y otras si se agregan)."""
    block = DATOS_PUBLICOS_CURADOS.get(nombre_empresa)
    if not block:
        # match parcial por nombre corto
        short = nombre_empresa.split("—")[0].strip().upper()
        for k, v in DATOS_PUBLICOS_CURADOS.items():
            if short in k.upper():
                block = v
                nombre_empresa = k
                break
    if not block:
        return None, "No hay serie pública curada para esta empresa"

    años = block["años"]
    rows = []
    prev_nwc = None
    for i, y in enumerate(años):
        ing = float(block["Ingresos"][i])
        ebd = float(block["EBITDA"][i])
        eb = float(block["EBIT"][i])
        d = float(block["Depreciacion"][i])
        cx = float(block["CAPEX"][i])
        nwc = float(block["NWC"][i])
        delta = 0.0 if prev_nwc is None else nwc - prev_nwc
        # Series curadas BVC (Colombia): tax estatutaria 35 % es coherente con el catálogo local
        nopat = eb * (1.0 - 0.35)
        fcff = nopat + d - cx - delta
        rows.append({
            "Año": y, "Ingresos": ing, "EBITDA": ebd, "EBIT": eb,
            "Depreciacion": d, "CAPEX": cx, "NWC": nwc,
            "Delta_NWC": delta, "NOPAT": nopat, "FCFF": fcff,
        })
        prev_nwc = nwc
    df = pd.DataFrame(rows).set_index("Año")
    msg = (
        f"Serie pública curada para {nombre_empresa} ({len(df)} años). "
        f"Fuente: {block['fuente']}. NWC/FCFF con componentes estimados."
    )
    return df, msg


def _historico_sin_ceros_cola(df):
    """Elimina años finales con ingresos numéricos iguales a cero; conserva los faltantes."""
    if df is None or df.empty or "Ingresos" not in df.columns:
        return df
    out = df.sort_index().copy()
    while len(out) > 0:
        try:
            ingreso_final = float(out["Ingresos"].iloc[-1])
        except (TypeError, ValueError):
            break
        # Un faltante no equivale a cero y no debe provocar una excepción ni borrar el año.
        if not np.isfinite(ingreso_final) or abs(ingreso_final) >= 1e-9:
            break
        out = out.iloc[:-1]
    return out


def _filtrar_historico_proyectable(df):
    """Devuelve años con los componentes financieros mínimos completos y finitos."""
    if df is None or df.empty:
        return df
    required = ["Ingresos", "EBITDA", "EBIT", "CAPEX", "NWC"]
    if any(col not in df.columns for col in required):
        return df.iloc[0:0].copy()
    numeric = df[required].apply(pd.to_numeric, errors="coerce")
    mask = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
    out = df.loc[mask].copy()
    # Sustituir columna por columna evita que pandas intente asignar una serie
    # float a una columna int64 preexistente mediante .loc (Pandas 3.x lo rechaza).
    for col in required:
        out[col] = numeric.loc[mask, col].astype(float).to_numpy()
    return out


def obtener_datos_financieros_publicos(nombre_empresa, preferir_yahoo=True):
    """
    Orquesta la descarga de cifras sin Excel.

    Orden de prioridad:
      1) Histórico runtime (empresa descargada en sesión), limpio de ceros
      2) Histórico del catálogo (curado) si la empresa está en EMPRESAS — más fiable que Yahoo incompleto
      3) yfinance (años con ingresos reales; se omiten ceros / año en curso)
      4) Serie curada alternativa
    """
    emp = resolver_empresa(nombre_empresa) or {}
    mensajes = []

    # 1) Runtime
    if nombre_empresa in EMPRESAS_RUNTIME or (emp and str(emp.get("fuente", "")).startswith("Yahoo")):
        hist = emp.get("historico")
        if hist and hist.get("Año") and len(hist["Año"]) >= 2:
            df_raw = _historico_sin_ceros_cola(pd.DataFrame(hist).set_index("Año"))
            n_cola = len(hist["Año"]) - len(df_raw)
            df = _filtrar_historico_proyectable(df_raw)
            n_incompletos = len(df_raw) - len(df)
            if df is not None and len(df) >= 2:
                # Persistir solo filas utilizables y conservar faltantes opcionales sin convertirlos a float.
                if nombre_empresa in EMPRESAS_RUNTIME and (n_cola > 0 or n_incompletos > 0):
                    limpio = {"Año": [int(a) for a in df.index]}
                    for c in df.columns:
                        limpio[c] = [float(x) if pd.notna(x) else None for x in df[c].values]
                    EMPRESAS_RUNTIME[nombre_empresa]["historico"] = limpio
                aviso = []
                if n_cola:
                    aviso.append(f"{n_cola} año(s) final(es) con ingresos cero omitidos")
                if n_incompletos:
                    aviso.append(f"{n_incompletos} año(s) con componentes financieros incompletos omitidos")
                detalle = f" ({'; '.join(aviso)})" if aviso else ""
                return df, f"Histórico en sesión ({emp.get('ticker_yf') or nombre_empresa}), {len(df)} años válidos{detalle}.", "PUBLICA_RUNTIME"

    # 2) Catálogo estático: SIEMPRE priorizar sobre Yahoo (evita cola en cero / unidades raras)
    if nombre_empresa in EMPRESAS and "historico" in EMPRESAS[nombre_empresa]:
        df_cat = df_historico_empresa(nombre_empresa)
        df_cat = _historico_sin_ceros_cola(df_cat)
        df_cat = _filtrar_historico_proyectable(df_cat)
        if df_cat is not None and not df_cat.empty and len(df_cat) >= 3:
            return (
                df_cat.copy(),
                f"Histórico curado del catálogo para {nombre_empresa} "
                f"({int(df_cat.index.min())}–{int(df_cat.index.max())}). "
                f"Yahoo no sustituye el catálogo en pestaña 1 para evitar años en cero.",
                "PUBLICA_CATALOGO",
            )

    # 3) Solo Yahoo (empresa fuera de catálogo)
    ticker = emp.get("ticker_yf")
    if preferir_yahoo and ticker:
        df, msg = descargar_financieros_yfinance(ticker)
        mensajes.append(msg)
        if df is not None and len(df) >= 3:
            # Ya viene en miles de millones (descargar_financieros_yfinance); no re-escalar.
            df2 = _historico_sin_ceros_cola(df.copy())
            df2 = _filtrar_historico_proyectable(df2)
            if df2 is not None and len(df2) >= 3:
                return df2, msg, "PUBLICA_YAHOO"

    df, msg = descargar_financieros_curados(nombre_empresa)
    mensajes.append(msg)
    if df is not None and len(df) >= 3:
        df_curado = _filtrar_historico_proyectable(_historico_sin_ceros_cola(df))
        if df_curado is not None and len(df_curado) >= 3:
            return df_curado, msg, "PUBLICA_CURADA"

    return None, " | ".join(mensajes) if mensajes else "Sin datos públicos", None


def formatear_market_cap(mc, moneda="COP"):
    if mc is None:
        return "N/D"
    try:
        mc = float(mc)
    except Exception:
        return "N/D"
    if mc >= 1e12:
        return f"{mc/1e12:.2f} billones {moneda}"
    if mc >= 1e9:
        return f"{mc/1e9:.2f} mil millones {moneda}"
    if mc >= 1e6:
        return f"{mc/1e6:.1f} M {moneda}"
    return f"{mc:,.0f} {moneda}"


def moneda_empresa(nombre_o_emp):
    """Moneda del modelo. Siempre alineada con la cotización del emisor (BVC=COP, US=USD)."""
    if isinstance(nombre_o_emp, dict):
        emp = nombre_o_emp
        nombre = None
    else:
        nombre = nombre_o_emp
        emp = resolver_empresa(nombre_o_emp) or {}
    mm, _mp = monedas_alineadas_por_ticker(
        ticker=emp.get("ticker_yf") or emp.get("ticker_bvc"),
        nombre_empresa=nombre,
        emp=emp,
    )
    return mm


def moneda_precio_empresa(nombre_o_emp, mkt=None):
    """Moneda del precio: igual que el modelo salvo ADR explícito no BVC.
    Para BVC/.CL siempre COP (ignora currency rara de Yahoo).
    """
    if isinstance(nombre_o_emp, dict):
        emp = nombre_o_emp
        nombre = None
    else:
        nombre = nombre_o_emp
        emp = resolver_empresa(nombre_o_emp) or {}
    _mm, mp = monedas_alineadas_por_ticker(
        ticker=emp.get("ticker_yf") or emp.get("ticker_bvc"),
        nombre_empresa=nombre,
        emp=emp,
    )
    # Si el snapshot de mercado confirma la misma moneda, usarla
    if mkt and mkt.get("moneda"):
        m = str(mkt["moneda"]).upper().replace("US$", "USD").replace("COL", "COP")
        if m == mp:
            return mp
        # No dejar que Yahoo diga USD en un .CL
        if mp == "COP":
            return "COP"
        if mp == "USD" and m == "USD":
            return "USD"
    return mp


def etiqueta_unidad(moneda=None, nombre_empresa=None):
    """Texto corto para ejes/HTML: 'miles de millones USD' / COP / etc."""
    mon = (moneda or "").upper()
    if not mon and nombre_empresa is not None:
        mon = moneda_empresa(nombre_empresa)
    mon = mon or "COP"
    return f"miles de millones {mon}"


def normalizar_serie_robusta(serie, metodo="hampel", k=3.5):
    """
    Capa unificada de saneamiento de atípicos para histórico y peers.
    - hampel/winsor: recorte (series temporales; conserva el año).
    - mediana: sustituye por mediana (comparables transversales).
    - iqr: Tukey 1.5·IQR como respaldo explícito.
    """
    s = pd.Series(serie, dtype=float)
    if metodo in ("mediana", "median"):
        out, mask = normalizar_atipicos(s, k=k, reemplazo="mediana")
    elif metodo in ("iqr", "tukey"):
        vals = s.to_numpy(dtype=float)
        ok = np.isfinite(vals)
        if ok.sum() < 4:
            return s, pd.Series(False, index=s.index)
        q1, q3 = np.percentile(vals[ok], [25, 75])
        iqr = q3 - q1
        if iqr <= 0:
            return s, pd.Series(False, index=s.index)
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = ok & ((vals < lo) | (vals > hi))
        out = s.clip(lower=lo, upper=hi)
        return out, pd.Series(mask, index=s.index)
    else:
        out, mask = normalizar_atipicos(s, k=k, reemplazo="winsor")
    return out, mask





def enriquecer_metricas_ficha(nombre_empresa=None, emp=None, ticker=None, mkt=None, precio=None, mon="COP"):
    """
    Completa market_cap / beta / P/E para la ficha de forma determinista.
    1) Yahoo (mkt / segundo fetch)
    2) Cap = acciones_catálogo × precio
    3) Beta = βu apalancada del catálogo si Yahoo no trae
    """
    emp = emp if isinstance(emp, dict) else {}
    mkt = mkt if isinstance(mkt, dict) else {}
    out = {
        "market_cap": _finite_or_none(mkt.get("market_cap")),
        "beta": _finite_or_none(mkt.get("beta")),
        "pe": _finite_or_none(mkt.get("pe")),
        "beta_nota": "",
        "pe_nota": "",
        "mcap_nota": "",
    }
    precio = _finite_or_none(precio if precio is not None else mkt.get("precio"))
    ticker = ticker or emp.get("ticker_yf") or emp.get("ticker_bvc")
    try:
        if ticker and "asegurar_sufijo_cl_bvc" in globals():
            ticker = asegurar_sufijo_cl_bvc(ticker)
    except Exception:
        pass

    # Segundo fetch Yahoo
    if (out["market_cap"] is None or out["beta"] is None or out["pe"] is None):
        if ticker and globals().get("HAS_YF"):
            try:
                m2 = _proveedor_yahoo(ticker)
                if isinstance(m2, dict) and m2.get("ok"):
                    if out["market_cap"] is None:
                        out["market_cap"] = _finite_or_none(m2.get("market_cap"))
                    if out["beta"] is None:
                        out["beta"] = _finite_or_none(m2.get("beta"))
                    if out["pe"] is None:
                        out["pe"] = _finite_or_none(m2.get("pe"))
                    if precio is None:
                        precio = _finite_or_none(m2.get("precio"))
            except Exception:
                pass

    # Parámetros de catálogo (acciones, beta_u, de_ratio, tax)
    params = dict(emp.get("params") or {})
    try:
        if nombre_empresa and "_EMPRESAS_CATALOGO_INMUTABLE" in globals():
            cat = _EMPRESAS_CATALOGO_INMUTABLE.get(nombre_empresa)
            if not cat and nombre_empresa:
                for k, v in _EMPRESAS_CATALOGO_INMUTABLE.items():
                    if nombre_empresa in k or k in str(nombre_empresa):
                        cat = v
                        break
            if cat:
                for kk, vv in (cat.get("params") or {}).items():
                    params.setdefault(kk, vv)
        if nombre_empresa:
            try:
                p2 = params_empresa(nombre_empresa) or {}
                for kk, vv in p2.items():
                    if vv is not None:
                        params.setdefault(kk, vv)
            except Exception:
                pass
    except Exception:
        pass

    # Capitalización
    if out["market_cap"] is None and precio and precio > 0:
        acc_m = _finite_or_none(params.get("acciones"))
        if acc_m and acc_m > 0:
            if acc_m >= 1e5:
                out["market_cap"] = acc_m * precio
            else:
                out["market_cap"] = acc_m * 1e6 * precio
            out["mcap_nota"] = " ≈"

    # Beta de modelo (apalancada)
    if out["beta"] is None:
        bu = _finite_or_none(params.get("beta_u"))
        de = _finite_or_none(params.get("de_ratio"))
        tax = _finite_or_none(params.get("tax"))
        if tax is None:
            tax = 0.35
        if bu is not None:
            if de is not None and de >= 0:
                out["beta"] = float(bu) * (1.0 + (1.0 - float(tax)) * float(de))
            else:
                out["beta"] = float(bu)
            out["beta_nota"] = " *"

    # P/E de respaldo: precio / EPS estimado desde histórico (NOPAT o EBIT*(1-tax))
    # cuando Yahoo no publica trailingPE (frecuente en tickers BVC .CL).
    if out["pe"] is None and precio and precio > 0:
        try:
            acc = _finite_or_none(params.get("acciones"))
            nopat = None
            # 1) histórico de la ficha
            hist = emp.get("historico") if isinstance(emp, dict) else None
            if isinstance(hist, dict) and hist.get("NOPAT"):
                try:
                    vals = [float(x) for x in hist["NOPAT"] if x is not None]
                    if vals:
                        nopat = vals[-1]
                except Exception:
                    nopat = None
            # 2) df histórico vía catálogo
            if nopat is None and nombre_empresa:
                try:
                    dfh = df_historico_empresa(nombre_empresa)
                    if dfh is not None and not dfh.empty and "NOPAT" in dfh.columns:
                        nopat = float(dfh["NOPAT"].dropna().iloc[-1])
                except Exception:
                    pass
            # 3) EBIT * (1-tax) del último año
            if nopat is None and isinstance(hist, dict) and hist.get("EBIT"):
                try:
                    ebit = float(hist["EBIT"][-1])
                    tax_e = float(params.get("tax") if params.get("tax") is not None else 0.35)
                    nopat = ebit * (1.0 - tax_e)
                except Exception:
                    pass
            if nopat is not None and abs(nopat) > 1e-9 and acc and acc > 0:
                # Unidades catálogo BVC: cifras en miles de millones; acciones en millones
                # EPS ≈ (NOPAT * 1e9) / (acciones * 1e6) = NOPAT * 1000 / acciones
                if acc < 1e5:
                    eps = (float(nopat) * 1000.0) / float(acc)
                else:
                    # acciones ya en unidades absolutas
                    eps = (float(nopat) * 1e9) / float(acc)
                if eps and eps > 0:
                    pe_est = float(precio) / eps
                    # Guardrail razonable para múltiplos accionarios
                    if 0.5 <= pe_est <= 120:
                        out["pe"] = pe_est
                        out["pe_nota"] = " ≈"
        except Exception:
            pass

    return out


def card_empresa_seleccionada(nombre_empresa):
    """Ficha de empresa. Métricas siempre enriquecidas (cap/beta/P/E)."""
    from html import escape

    # Restaurar catálogo si estaba contaminado
    try:
        if nombre_empresa in globals().get("_EMPRESAS_CATALOGO_INMUTABLE", {}):
            _restaurar_entrada_catalogo(nombre_empresa)
    except Exception:
        pass

    emp = resolver_empresa(nombre_empresa)
    if emp is None:
        safe_name = escape(str(nombre_empresa or "Empresa personalizada"))
        return (
            f"<div class='section-card'><b>{safe_name}</b><br>"
            "Empresa <b>no predefinida</b>: descarga un ticker en Yahoo o carga un Excel/CSV.</div>"
        )

    try:
        emp = aplicar_monedas_a_empresa(nombre_empresa, emp) or emp
    except Exception:
        pass

    # Ticker canónico
    _tk_card = None
    try:
        _tk_card = ticker_canonico_empresa(nombre_empresa)
    except Exception:
        _tk_card = None
    if not _tk_card:
        try:
            _tk_card = asegurar_sufijo_cl_bvc(emp.get("ticker_yf") or emp.get("ticker_bvc"))
        except Exception:
            _tk_card = emp.get("ticker_yf") or emp.get("ticker_bvc")
    if _tk_card:
        emp["ticker_yf"] = _tk_card

    # Mercado
    try:
        mkt = obtener_datos_mercado_bvc(_tk_card, ticker_bvc=emp.get("ticker_bvc")) or {}
    except Exception:
        mkt = {}

    _px = _finite_or_none(mkt.get("precio"))
    mon = str(mkt.get("moneda") or emp.get("moneda_precio") or emp.get("moneda") or "COP")
    if str(_tk_card or "").upper().endswith(".CL"):
        mon = "COP"

    # === MÉTRICAS (siempre pasar por enriquecer) ===
    met = enriquecer_metricas_ficha(
        nombre_empresa=nombre_empresa,
        emp=emp,
        ticker=_tk_card,
        mkt=mkt,
        precio=_px,
        mon=mon,
    )
    _mcap = met.get("market_cap")
    _beta = met.get("beta")
    _pe = met.get("pe")

    precio_txt = f"{_px:,.2f} {mon}" if _px is not None else "No disponible"
    _ch = _finite_or_none(mkt.get("cambio_pct"))
    if _ch is not None:
        signo = "+" if _ch >= 0 else ""
        color = COLOR_SUCCESS if _ch >= 0 else COLOR_DANGER
        cambio_txt = f'<span style="color:{color};font-weight:700">{signo}{_ch:.2f}%</span>'
    else:
        cambio_txt = '<span style="color:#94A3B8">—</span>'

    beta_txt = f"{_beta:.2f}{met.get('beta_nota') or ''}" if _beta is not None else "N/D"
    pe_txt = f"{_pe:.1f}x{met.get('pe_nota') or ''}" if _pe is not None else "N/D"
    mc_txt = formatear_market_cap(_mcap, mon)
    if _mcap is not None and met.get("mcap_nota"):
        mc_txt = f"{mc_txt}{met.get('mcap_nota')}"

    ticker = _tk_card or emp.get("ticker_yf") or emp.get("ticker_bvc") or "—"
    es_bvc = bool(str(ticker).upper().endswith(".CL") or (
        nombre_empresa in globals().get("_EMPRESAS_CATALOGO_INMUTABLE", {})
        or (nombre_empresa in EMPRESAS and emp.get("ticker_bvc"))
    ))
    etiqueta_mercado = "Bolsa de Valores de Colombia (BVC)" if es_bvc else "Mercado (Yahoo Finance)"
    etiqueta_precio = "Precio de mercado (BVC)" if es_bvc else "Precio de mercado"
    encabezado = f"EMPRESA SELECCIONADA · {ticker}"

    desc = (emp.get("descripcion") or "").strip()
    fuente = str(emp.get("fuente") or "")
    if fuente.startswith("Yahoo") or (desc and _texto_parece_ingles(desc)):
        sector = emp.get("sector") or "No clasificado"
        desc_es = (
            f"Empresa cotizada (<b>{escape(str(ticker))}</b>). "
            f"Sector: <b>{escape(str(sector))}</b>. "
            f"Resumen de Yahoo Finance: {escape(desc[:320])}{'…' if len(desc) > 320 else ''}"
        )
    else:
        desc_es = escape(desc) if desc else "Sin descripción disponible."

    sector_txt = escape(str(emp.get("sector") or "No clasificado"))
    nombre_safe = escape(str(nombre_empresa))
    msg_mkt = escape(str(mkt.get("mensaje") or ""))

    return f"""
<div style="background:linear-gradient(135deg,#0A2540 0%,#1B6CA8 70%,#00A3A1 100%);
            padding:16px 18px;border-radius:12px;margin-bottom:10px;
            box-shadow:0 10px 28px rgba(10,37,64,0.28)" class="dark-card">
  <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;align-items:flex-start">
    <div>
      <div style="font-size:13px;color:#E2E8F0 !important">{encabezado}</div>
      <h2 style="margin:4px 0 6px 0;color:#5EEAD4 !important;font-size:1.3rem">{nombre_safe}</h2>
      <p style="margin:0;color:#FFFFFF !important;max-width:640px;line-height:1.45">{desc_es}</p>
      <p style="margin:8px 0 0 0;font-size:0.9rem;color:#E2E8F0 !important">
        <b style="color:#FFFFFF !important">Sector:</b> {sector_txt}
      </p>
    </div>
    <div style="background:rgba(255,255,255,0.12);border-radius:12px;padding:14px 18px;min-width:200px">
      <div style="font-size:12px;color:#E2E8F0 !important">{etiqueta_precio}</div>
      <div style="font-size:1.6rem;font-weight:700;margin:4px 0;color:#FFFFFF !important">{precio_txt}</div>
      <div style="font-size:0.95rem;color:#FFFFFF !important">{cambio_txt}</div>
      <div style="margin-top:10px;font-size:0.88rem;color:#E2E8F0 !important;line-height:1.45">
        <div><b>Capitalización:</b> {mc_txt}</div>
        <div><b>Beta:</b> {beta_txt} · <b>P/E:</b> {pe_txt}</div>
      </div>
    </div>
  </div>
  <p style="margin:12px 0 0 0;font-size:0.82rem;color:#CBD5E1 !important">
    {etiqueta_mercado} · {msg_mkt}
  </p>
</div>
{tip("<b>Precio</b> = cotización de una acción. <b>Capitalización</b> = precio × acciones (≈ si se estima con el catálogo). <b>Beta *</b> = estimada del modelo si Yahoo no la publica. <b>P/E ≈</b> = Yahoo trailingPE o, si no hay, precio / EPS estimado con el último NOPAT del histórico.")}
"""


def _texto_parece_ingles(texto):
    """Heurística simple: muchas palabras típicas en inglés y pocas tildes."""
    t = (texto or "").lower()
    if not t or len(t) < 40:
        return False
    marcadores = (
        " the ", " and ", " company ", " provides ", " offers ", " operates ",
        " designs ", " manufactures ", " engages ", " based in ", " products ",
        " services ", " worldwide ", " subsidiary ",
    )
    hits = sum(1 for m in marcadores if m in f" {t} ")
    tiene_tilde = any(c in t for c in "áéíóúñü")
    return hits >= 2 and not tiene_tilde



def df_historico_empresa(nombre_empresa):
    """Respaldo histórico: catálogo estático o empresa descargada en sesión."""
    emp = resolver_empresa(nombre_empresa)
    if not emp or "historico" not in emp:
        return pd.DataFrame(columns=["Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC", "Delta_NWC", "NOPAT", "FCFF"])
    return pd.DataFrame(emp["historico"]).set_index("Año")


# Supuestos de mercado por país/cotización (no son params de ISA; se eligen según la empresa).
# rf/ERP orientativos para modelación; el usuario puede editarlos en la UI.
# Anclas CAPM orientativas (comité · oct-2026). Editables en UI.
# CO: TES 10a ~13% y tasa BanRep 12% (coyuntura fiscal); rf local ya incorpora riesgo soberano
#     → CRP=0 si rf es TES (evitar doble conteo). ERP sobre bono local ~5–6%.
#     g_max: PIB real ~2,2% (FMI) + inflación de largo plazo moderada → techo nominal ~4%.
# US: T-bond + mature ERP (Damodaran ~4,2–5%).
CAPM_POR_MERCADO = {
    "US": {"rf": 0.045, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.015},
    "CO": {"rf": 0.12,  "erp": 0.055, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.025},
    "BR": {"rf": 0.12,  "erp": 0.055, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.025},
    "MX": {"rf": 0.09,  "erp": 0.055, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.02},
    "CL": {"rf": 0.055, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.035, "kd_spread": 0.015},
    "GB": {"rf": 0.04,  "erp": 0.05, "crp": 0.0, "g_max_macro": 0.035, "kd_spread": 0.015},
    "DEFAULT": {"rf": 0.05, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.02},
}
CAPM_AS_OF = "2026-10"  # US rf~4.5% / ERP~5%; CO rf~12%. Revisar en cada ciclo de FOMC/BanRep.



def _codigo_mercado(country, currency=None, ticker_yf=None):
    """Resuelve código de mercado CAPM. Prioridad: país explícito > sufijo ticker > moneda."""
    c = (country or "").upper()
    cur = (currency or "").upper()
    t = (ticker_yf or "").upper()
    # Sufijos locales primero (evita clasificar ISA.CL como US por currency=COP raramente mal leída)
    if t.endswith(".CL"):
        return "CO"
    if t.endswith(".SA"):
        return "BR"
    if t.endswith(".MX"):
        return "MX"
    if t.endswith(".SN"):
        return "CL"
    if t.endswith(".L"):
        return "GB"
    if c in ("COLOMBIA", "COL", "CO"):
        return "CO"
    if c in ("BRAZIL", "BRA", "BR"):
        return "BR"
    if c in ("MEXICO", "MEX", "MX"):
        return "MX"
    if c in ("CHILE", "CHL"):
        return "CL"
    if c in ("UNITED KINGDOM", "GBR", "GB", "UK"):
        return "GB"
    if c in ("UNITED STATES", "USA", "US"):
        return "US"
    # Ticker sin sufijo + USD → US (AAPL, MSFT, …)
    if cur == "USD" and t and "." not in t:
        return "US"
    if cur == "USD" and c in ("", "UNITED STATES", "USA", "US"):
        return "US"
    return "DEFAULT"



def ticker_canonico_empresa(nombre_empresa):
    """
    Ticker Yahoo canónico, a prueba de contaminación.
    Catálogo BVC → siempre snapshot (ISA.CL, nunca AAPL).
    Runtime → ticker con el que se registró la descarga.
    """
    nombre = str(nombre_empresa or "").strip()
    if not nombre:
        return None
    # Catálogo exacto
    if nombre in _EMPRESAS_CATALOGO_INMUTABLE:
        _restaurar_entrada_catalogo(nombre)
        orig = _EMPRESAS_CATALOGO_INMUTABLE[nombre]
        tk = orig.get("ticker_yf") or orig.get("ticker_bvc")
        return asegurar_sufijo_cl_bvc(tk) if tk else None
    # Match parcial catálogo
    for k, orig in _EMPRESAS_CATALOGO_INMUTABLE.items():
        if nombre == k or (len(nombre) > 3 and (nombre in k or k in nombre)):
            _restaurar_entrada_catalogo(k)
            tk = orig.get("ticker_yf") or orig.get("ticker_bvc")
            return asegurar_sufijo_cl_bvc(tk) if tk else None
    # Runtime Yahoo
    emp = EMPRESAS_RUNTIME.get(nombre)
    if emp:
        tk = emp.get("ticker_yf") or emp.get("ticker_bvc")
        return asegurar_sufijo_cl_bvc(tk) if tk else None
    for k, emp in EMPRESAS_RUNTIME.items():
        if nombre == k or nombre in k or k in nombre:
            tk = emp.get("ticker_yf") or emp.get("ticker_bvc")
            return asegurar_sufijo_cl_bvc(tk) if tk else None
    # Heurística display
    if "—" in nombre:
        part = nombre.split("—")[-1].strip().upper().replace(" ", "")
        if 1 <= len(part) <= 12 and part.replace(".", "").replace("-", "").isalnum():
            return asegurar_sufijo_cl_bvc(part)
    head = nombre.split("—")[0].strip().upper()
    if head in _tickers_bvc_conocidos():
        return asegurar_sufijo_cl_bvc(head)
    if nombre and len(nombre) <= 12 and nombre.replace(".", "").isalnum():
        return asegurar_sufijo_cl_bvc(nombre.upper())
    return None


def ticker_yf_empresa(nombre_empresa):
    """Alias: siempre el ticker canónico de la empresa."""
    return ticker_canonico_empresa(nombre_empresa)


def resolver_acciones_millones(nombre_empresa=None, acciones_ui=None, info=None):
    """Número de acciones en **millones** para VPS.

    Prioridad: UI (>0) → params de la empresa → sharesOutstanding de Yahoo info → marketCap/precio.
    """
    # UI
    try:
        if acciones_ui is not None and str(acciones_ui).strip() not in ("", "None", "nan"):
            a = float(acciones_ui)
            if a > 0 and a == a:
                return float(a)
    except Exception:
        pass
    # Params empresa
    try:
        emp = resolver_empresa(nombre_empresa) if nombre_empresa else None
        if emp:
            a = (emp.get("params") or {}).get("acciones")
            if a is not None and float(a) > 0:
                return float(a)
    except Exception:
        emp = None
    # Yahoo info
    info = info or {}
    try:
        sh = _safe_float(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))
        if sh is not None and sh > 0:
            if sh >= 1e6:
                return round(sh / 1e6, 4)
            if sh >= 1e3:
                return round(sh / 1e3, 4)
            return round(sh, 4)
    except Exception:
        pass
    # marketCap / precio
    try:
        mcap = _safe_float(info.get("marketCap"))
        px = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
        if mcap and px and px > 0:
            sh = mcap / px
            return round(sh / 1e6, 4) if sh >= 1e6 else round(sh, 4)
    except Exception:
        pass
    # Live Yahoo si hay ticker (incluye parseo de "Nombre — TICKER")
    try:
        tk = ticker_yf_empresa(nombre_empresa) if nombre_empresa else None
        if tk and HAS_YF:
            t_obj = yf.Ticker(tk)
            inf = {}
            try:
                inf = t_obj.info or {}
            except Exception:
                inf = {}
            sh = _safe_float(inf.get("sharesOutstanding") or inf.get("impliedSharesOutstanding"))
            if sh is None:
                try:
                    fi = getattr(t_obj, "fast_info", None)
                    if fi is not None:
                        sh = _safe_float(getattr(fi, "shares", None) or (fi.get("shares") if hasattr(fi, "get") else None))
                except Exception:
                    pass
            if sh is not None and sh > 0:
                if sh >= 1e6:
                    return round(sh / 1e6, 4)
                if sh >= 1e3:
                    return round(sh / 1e3, 4)
                return round(float(sh), 4)
            mcap = _safe_float(inf.get("marketCap"))
            px = _safe_float(inf.get("regularMarketPrice") or inf.get("currentPrice"))
            if (mcap is None or px is None):
                try:
                    fi = getattr(t_obj, "fast_info", None)
                    if fi is not None:
                        if mcap is None:
                            mcap = _safe_float(getattr(fi, "market_cap", None) or (fi.get("market_cap") if hasattr(fi, "get") else None))
                        if px is None:
                            px = _safe_float(getattr(fi, "last_price", None) or (fi.get("last_price") if hasattr(fi, "get") else None))
                except Exception:
                    pass
            if mcap and px and px > 0:
                return round((mcap / px) / 1e6, 4)
    except Exception:
        pass
    return None


def resolver_precio_mercado(nombre_empresa=None, precio_ui=None):
    """Precio de mercado en moneda de cotización. UI → conector Yahoo/runtime."""
    try:
        if precio_ui is not None and float(precio_ui) > 0:
            return float(precio_ui)
    except Exception:
        pass
    emp = resolver_empresa(nombre_empresa) if nombre_empresa else None
    emp = emp or {}
    tk = emp.get("ticker_yf") or (ticker_yf_empresa(nombre_empresa) if nombre_empresa else None)
    if not tk:
        return None
    try:
        mkt = obtener_datos_mercado_bvc(tk, ticker_bvc=emp.get("ticker_bvc"))
        if mkt and mkt.get("ok") and mkt.get("precio") is not None:
            return float(mkt["precio"])
    except Exception:
        pass
    return None


def calcular_vps_y_upside(equity, acciones_millones, precio_mercado=None, moneda_modelo=None, moneda_precio=None):
    """VPS y upside con recalibración de unidades.

    Convención:
      equity          → miles de millones (moneda del modelo)
      acciones_millones → millones de acciones
      VPS = equity * 1e9 / (acciones * 1e6) = equity * 1000 / acciones

    Si el VPS queda órdenes de magnitud lejos del precio, prueba reescalar acciones
    (error típico: Yahoo en unidades vs ya-en-millones).
    """
    vps = None
    upside = None
    acciones_used = None
    nota = None
    try:
        eq = float(equity)
        if acciones_millones is None or float(acciones_millones) <= 0:
            return {"value_per_share": None, "upside_pct": None, "acciones": None, "nota_vps": "Sin acciones: no se calcula VPS."}
        acc = float(acciones_millones)
        acciones_used = acc
        vps = (eq * 1000.0) / acc

        mm = (moneda_modelo or "").upper().strip()
        mp = (moneda_precio or "").upper().strip()
        monedas_ok = (not mm or not mp or mm == mp)

        if precio_mercado is not None and float(precio_mercado) > 0:
            px = float(precio_mercado)
            # Recalibrar acciones si VPS está muy lejos del precio (error de escala)
            if vps is not None and px > 0 and (vps < 0.01 * px or vps > 100.0 * px):
                # Inferir acciones desde equity y precio: acc_mm = equity*1000/px
                acc_alt = (eq * 1000.0) / px if px else None
                if acc_alt and acc_alt > 0:
                    # Probar factores comunes de error de escala en acciones
                    candidatos = [acc, acc * 1000.0, acc / 1000.0, acc * 1e6, acc / 1e6, acc_alt]
                    best = acc
                    best_vps = vps
                    best_score = abs(np.log(max(vps, 1e-12) / px))
                    for a in candidatos:
                        if a is None or a <= 0:
                            continue
                        v = (eq * 1000.0) / a
                        if v <= 0:
                            continue
                        score = abs(np.log(max(v, 1e-12) / px))
                        if score < best_score:
                            best_score, best, best_vps = score, a, v
                    if best != acc:
                        nota = (
                            f"Acciones recalibradas de {acc:,.2f} a {best:,.2f} M "
                            f"(VPS alineado al orden del precio de mercado)."
                        )
                        acc = best
                        acciones_used = best
                        vps = best_vps

            if monedas_ok and vps is not None and px > 0:
                upside = (vps / px - 1.0) * 100.0
                if not np.isfinite(upside):
                    upside = None
                # Solo anular upside en explosiones numéricas (> 1000 pp); mostrar el resto
                elif abs(upside) > 1000.0:
                    nota = (nota or "") + (
                        f" Upside extremo ({upside:+.0f} pp): revisa WACC, g, bridge o escala de EEFF."
                    )
                    # Aún así devolver el número para transparencia (el UI puede matizarlo)
            elif not monedas_ok:
                nota = (nota or "") + (
                    f" Moneda modelo ({mm}) ≠ cotización ({mp}): upside no comparable sin FX."
                )
                upside = None
    except Exception as e:
        nota = f"VPS no calculable: {e}"
        vps, upside = None, None

    return {
        "value_per_share": float(vps) if vps is not None and np.isfinite(vps) else None,
        "upside_pct": float(upside) if upside is not None and np.isfinite(upside) else None,
        "acciones": acciones_used,
        "nota_vps": nota,
    }



def forzar_vps_upside(val, nombre_empresa=None, acciones_ui=None, precio=None):
    """Garantiza VPS/upside en el dict de valoración cuando hay equity.

    Se usa al final de tab2/tab4/tab7 para no dejar N/D si faltó un eslabón intermedio.
    """
    if not isinstance(val, dict):
        return val
    eq = val.get("Equity_Value")
    vps = val.get("value_per_share")
    upside = val.get("upside_pct")
    acc = val.get("acciones")
    px = precio if precio is not None else val.get("precio_mercado")

    try:
        if acc is None or float(acc or 0) <= 0:
            acc = resolver_acciones_millones(nombre_empresa, acciones_ui)
    except Exception:
        pass
    try:
        if px is None or float(px or 0) <= 0:
            px = resolver_precio_mercado(nombre_empresa)
    except Exception:
        pass

    mm = moneda_empresa(nombre_empresa) if nombre_empresa else None
    mp = moneda_precio_empresa(nombre_empresa) if nombre_empresa else None

    need = (
        vps is None
        or (isinstance(vps, float) and not np.isfinite(vps))
        or (upside is None and px is not None)
    )
    if need and eq is not None and acc is not None and float(acc) > 0:
        vu = calcular_vps_y_upside(
            eq, acc, precio_mercado=px, moneda_modelo=mm, moneda_precio=mp
        )
        if vu.get("value_per_share") is not None:
            val["value_per_share"] = vu["value_per_share"]
            vps = vu["value_per_share"]
        if vu.get("upside_pct") is not None:
            val["upside_pct"] = vu["upside_pct"]
            upside = vu["upside_pct"]
        if vu.get("acciones") is not None:
            val["acciones"] = vu["acciones"]
        if vu.get("nota_vps"):
            val["nota_vps"] = vu["nota_vps"]
            br = val.get("bridge") or {}
            br["Nota VPS"] = vu["nota_vps"]
            val["bridge"] = br

    # Último recurso: solo upside si ya hay VPS y precio
    if (val.get("upside_pct") is None) and vps is not None and px is not None:
        try:
            px = float(px)
            vps = float(vps)
            if px > 0 and np.isfinite(vps):
                # Solo si monedas alineadas o desconocidas
                if (not mm or not mp or str(mm).upper() == str(mp).upper()):
                    val["upside_pct"] = (vps / px - 1.0) * 100.0
        except Exception:
            pass
    if px is not None:
        val["precio_mercado"] = px
    return val


def params_en_blanco():

    """Pizarra en cero para empresas no predefinidas: sin supuestos del catálogo BVC."""
    return {
        "de_ratio": 0.0,
        "kd": 0.0,
        "tax": 0.0,
        "g": 0.0,
        "beta_u": 0.0,
        "capital_invertido": 0.0,
        "deuda_neta": 0.0,
        "inversion_inicial": 0.0,
        "caja": 0.0,
        "nci": 0.0,
        "otros_claims": 0.0,
        "asociados": 0.0,
        "acciones": None,
        "exit_multiple": 0.0,
        "origen_params": "blanco",
    }


def _cagr_serie(valores, floor_g=0.0, cap_g=0.12):
    """CAGR simple entre primer y último valor positivo."""
    s = [float(v) for v in valores if v is not None and float(v) > 0]
    if len(s) < 2:
        return 0.0
    n = len(s) - 1
    g = (s[-1] / s[0]) ** (1 / max(n, 1)) - 1
    return float(np.clip(g, floor_g, cap_g))


def capital_invertido_operativo_yahoo(info):
    """Estima capital invertido contable en miles de millones desde el balance Yahoo.

    Fórmula de aproximación: deuda financiera + patrimonio atribuible a accionistas
    - efectivo y equivalentes. No sustituye un cálculo detallado de activos operativos
    netos; devuelve None si faltan partidas esenciales, en vez de inventar una base.
    """
    info = info or {}
    bs = info.get("_balance_sheet")
    def safe(value):
        try:
            value = float(value)
            return value if np.isfinite(value) else None
        except (TypeError, ValueError):
            return None
    def balance_value(names):
        if bs is None or not hasattr(bs, "index"):
            return None
        index = [(str(row).strip().lower(), row) for row in bs.index]
        for name in names:
            needle = name.lower()
            for normalized, original in index:
                if normalized == needle:
                    try:
                        values = bs.loc[original]
                        for value in values.values:
                            number = safe(value)
                            if number is not None:
                                return number
                    except Exception:
                        continue
        return None

    debt = safe(info.get("totalDebt"))
    if debt is None:
        debt = balance_value(["total debt", "long term debt", "current debt"])
    equity = safe(info.get("totalStockholderEquity"))
    if equity is None:
        equity = balance_value([
            "stockholders equity", "common stock equity",
            "total stockholder equity", "total equity gross minority interest",
        ])
    cash = safe(info.get("totalCash"))
    if cash is None:
        cash = safe(info.get("cash"))
    if cash is None:
        cash = balance_value(["cash and cash equivalents", "cash cash equivalents and short term investments"])

    # No calcular una base con partidas incompletas o con magnitudes no positivas.
    if debt is None or equity is None or cash is None:
        return None
    capital = debt + equity - cash
    if not np.isfinite(capital) or capital <= 0:
        return None
    return round(capital / 1e9, 4)


def derivar_params_desde_cero(df_hist, info=None, ticker_yf=None):
    """
    Construye TODOS los parámetros de modelación solo a partir de:
      - el histórico propio de la empresa (df_hist)
      - metadatos de mercado de ESA empresa (info Yahoo), si existen
    No usa D/E, β, g, tax ni capital del catálogo BVC.
    """
    info = info or {}
    p = params_en_blanco()
    p["origen_params"] = "derivado_desde_cero"

    # --- Tax: preferir effectiveTaxRate de Yahoo; si no, estatutaria por país ---
    # (AAPL ~15–16 % efectivo; hardcode 35 % o 21 % sin ETR sesgaba NOPAT/FCFF)
    country = (info.get("country") or info.get("countryCode") or "").upper()
    etr = _safe_float(info.get("effectiveTaxRate"))
    if etr is not None and 0.0 < etr < 0.55:
        p["tax"] = round(float(etr), 4)
        p["tax_fuente"] = "yahoo_effectiveTaxRate"
    elif country in ("COLOMBIA", "COL", "CO"):
        p["tax"] = 0.35
        p["tax_fuente"] = "estatutaria_CO"
    elif country in ("UNITED STATES", "USA", "US"):
        p["tax"] = 0.21
        p["tax_fuente"] = "estatutaria_US"
    elif country in ("BRAZIL", "BRA", "BR"):
        p["tax"] = 0.34
        p["tax_fuente"] = "estatutaria_BR"
    elif country in ("MEXICO", "MEX", "MX"):
        p["tax"] = 0.30
        p["tax_fuente"] = "estatutaria_MX"
    elif country in ("CHILE", "CHL", "CL"):
        p["tax"] = 0.27
        p["tax_fuente"] = "estatutaria_CL"
    elif country in ("UNITED KINGDOM", "GBR", "GB", "UK"):
        p["tax"] = 0.25
        p["tax_fuente"] = "estatutaria_GB"
    else:
        p["tax"] = 0.25
        p["tax_fuente"] = "default_25"

    # --- Balance / mercado de ESTA empresa ---
    total_debt = _safe_float(info.get("totalDebt"))
    cash = _safe_float(info.get("totalCash") or info.get("cash"))
    mcap = _safe_float(info.get("marketCap"))
    beta = _safe_float(info.get("beta"))
    shares = _safe_float(info.get("sharesOutstanding"))
    book = _safe_float(info.get("bookValue"))  # a veces por acción
    enterprise_to_ebitda = _safe_float(info.get("enterpriseToEbitda"))

    if cash is not None:
        p["caja"] = round(cash / 1e9, 4)
    if total_debt is not None:
        # deuda_neta = deuda − caja (ya neta). El puente NO debe sumar caja otra vez.
        p["deuda_neta"] = round((total_debt - (cash or 0)) / 1e9, 4)
        p["deuda_es_bruta"] = False
        p["deuda_bruta"] = round(total_debt / 1e9, 4)
    if shares is not None and shares > 0:
        # Yahoo sharesOutstanding casi siempre en unidades (AAPL ~1.5e10).
        # Convertir siempre a **millones de acciones** para VPS = equity_mm * 1000 / acc_m.
        sh = float(shares)
        if sh >= 1e6:
            p["acciones"] = round(sh / 1e6, 4)  # unidades → millones
        elif sh >= 100:  # ya parece millones (p.ej. 15100) o miles grandes
            # Si marketCap/precio implica otro orden, confiar en mcap
            px_tmp = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
            if mcap is not None and px_tmp and px_tmp > 0:
                implied_m = (mcap / px_tmp) / 1e6
                # Si sh está cerca de implied en millones, usar sh; si no, implied
                if implied_m > 0 and (sh / implied_m < 0.1 or sh / implied_m > 10):
                    p["acciones"] = round(implied_m, 4)
                else:
                    p["acciones"] = round(sh, 4)
            else:
                p["acciones"] = round(sh, 4)
        else:
            p["acciones"] = round(sh, 4)
        # Cross-check con marketCap / precio (más fiable en mega-caps)
        px_chk = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
        if mcap is not None and px_chk and px_chk > 0:
            implied = (mcap / px_chk) / 1e6  # millones
            if implied > 0 and p.get("acciones"):
                ratio = p["acciones"] / implied
                if ratio < 0.05 or ratio > 20:
                    p["acciones"] = round(implied, 4)
                    p["acciones_fuente"] = "marketCap/precio"
                else:
                    p["acciones_fuente"] = "sharesOutstanding"
        # Guardrail absurdo
        if p.get("acciones") and p["acciones"] > 500_000:
            p["acciones"] = round(p["acciones"] / 1000.0, 4)

    # NCI (interés minoritario) y asociados: solo datos de ESTA empresa
    nci_val = _safe_float(
        info.get("minorityInterest")
        or info.get("minorityInterests")
        or info.get("nonControllingInterest")
        or info.get("noncontrollingInterest")
    )
    asociados_val = _safe_float(
        info.get("investmentsInOtherVenturesUnderEquityMethod")
        or info.get("longTermEquityInvestment")
    )
    # Balance sheet Yahoo (si el caller pasó _balance_sheet en info)
    bs = info.get("_balance_sheet")
    if bs is not None and hasattr(bs, "index"):
        try:
            def _bs_first(candidates):
                idx_map = {str(i).strip().lower(): i for i in bs.index}
                for cand in candidates:
                    c = cand.lower()
                    for k, original in idx_map.items():
                        if c == k or c in k:
                            series = bs.loc[original]
                            for v in series.values:
                                fv = _safe_float(v)
                                if fv is not None:
                                    return fv
                return None
            # Minority interest explícito
            mi = _bs_first([
                "Minority Interest",
                "Noncontrolling Interest",
                "Non Controlling Interest",
                "Minority Interests",
            ])
            if mi is not None:
                nci_val = abs(mi)
            else:
                # Proxy: Total Equity Gross Minority − Stockholders Equity
                gross = _bs_first([
                    "Total Equity Gross Minority Interest",
                    "Total Equity Gross Minority Interests",
                ])
                she = _bs_first([
                    "Stockholders Equity",
                    "Common Stock Equity",
                    "Total Stockholder Equity",
                ])
                if gross is not None and she is not None:
                    diff = float(gross) - float(she)
                    if abs(diff) > 1e6:  # material
                        nci_val = abs(diff)
                    else:
                        nci_val = 0.0  # p.ej. AAPL: gross ≈ stockholders → NCI ≈ 0
            inv = _bs_first([
                "Investments And Advances",
                "Long Term Equity Investment",
                "Investmentin AssociatedampAffiliatedCompanies",
                "Investments in Associates",
            ])
            if inv is not None and asociados_val is None:
                asociados_val = inv
        except Exception:
            pass
    if nci_val is not None:
        p["nci"] = round(abs(float(nci_val)) / 1e9, 4)
    if asociados_val is not None:
        p["asociados"] = round(abs(float(asociados_val)) / 1e9, 4)

    # D/E solo con cifras de esta empresa
    if total_debt is not None and mcap is not None and mcap > 0:
        p["de_ratio"] = round(max(0.0, total_debt / mcap), 4)
    elif total_debt is not None and book is not None and shares and book * shares > 0:
        equity_book = book * shares
        p["de_ratio"] = round(max(0.0, total_debt / equity_book), 4)

    # Capital invertido operativo: deuda financiera + patrimonio - efectivo.
    # No sustituir por activos totales, capitalización bursátil o múltiplos de ingresos:
    # esas magnitudes no son una base contable equivalente para el ROIC.
    capital_operativo = capital_invertido_operativo_yahoo(info)
    if capital_operativo is not None:
        p["capital_invertido"] = capital_operativo
        p["capital_invertido_fuente"] = "yahoo_balance_debt_plus_equity_minus_cash"
    else:
        p["capital_invertido"] = 0.0
        p["capital_invertido_fuente"] = "no_disponible_balance_incompleto"

    # Inversión inicial del proyecto ≈ CAPEX propio reciente
    if df_hist is not None and not df_hist.empty and "CAPEX" in df_hist.columns:
        p["inversion_inicial"] = round(abs(float(df_hist["CAPEX"].iloc[-1])), 4)
    elif df_hist is not None and not df_hist.empty and "Ingresos" in df_hist.columns:
        p["inversion_inicial"] = round(abs(float(df_hist["Ingresos"].iloc[-1])) * 0.10, 4)

    # --- Mercado CAPM según país/ticker de ESTA empresa (no el default Colombia de la UI) ---
    currency = info.get("currency") or ""
    merc = _codigo_mercado(country, currency, ticker_yf)
    capm = CAPM_POR_MERCADO.get(merc, CAPM_POR_MERCADO["DEFAULT"])
    p["rf"] = capm["rf"]
    p["erp"] = capm["erp"]
    p["crp"] = capm["crp"]
    p["g_max_macro"] = capm["g_max_macro"]
    p["mercado_capm"] = merc

    # g TERMINAL de largo plazo (Gordon): NO usar el CAGR histórico completo.
    # CAGR reciente alimenta la proyección de horizonte explícito; g perpetuo se ancla a macro del mercado.
    cagr = 0.0
    if df_hist is not None and not df_hist.empty and "Ingresos" in df_hist.columns:
        tail = df_hist["Ingresos"].iloc[-min(5, len(df_hist)):]
        cagr = _cagr_serie(tail.tolist(), floor_g=0.0, cap_g=0.15)
    p["g_cagr_historico"] = round(cagr, 4)
    # Terminal: entre 1% y g_max_macro, sesgado a macro (más estable para DCF)
    g_term = min(capm["g_max_macro"] * 0.7, max(0.01, min(cagr, capm["g_max_macro"])))
    # Si el CAGR es muy alto (tech), no arrastrar 10% a perpetuidad
    if cagr > capm["g_max_macro"]:
        g_term = capm["g_max_macro"] * 0.75
    p["g"] = round(float(g_term), 4)

    # kd: interés propio o rf de su mercado + spread (no el 8% de ISA)
    ir = _safe_float(info.get("interestRate") or info.get("borrowRate"))
    if ir is not None and 0 < ir < 0.4:
        p["kd"] = round(float(ir), 4)
    else:
        ie = _safe_float(info.get("interestExpense"))
        if ie is not None and total_debt and total_debt > 0:
            p["kd"] = round(float(np.clip(abs(ie) / total_debt, 0.01, 0.25)), 4)
        else:
            p["kd"] = round(float(capm["rf"] + capm["kd_spread"]), 4)

    # Beta unlevered de ESTA acción; si Yahoo no trae beta, 1.0 (mercado) con marca
    tax = p["tax"]
    de = p["de_ratio"]
    if beta is not None and beta > 0:
        beta_aj = 0.67 * float(np.clip(beta, 0.2, 2.5)) + 0.33   # ajuste de Blume + winsorización de β bruto
        beta_u = beta_aj / (1 + (1 - tax) * de) if de > 0 else beta_aj
        p["beta_u"] = round(float(np.clip(beta_u, 0.05, 3.0)), 4)
        p["beta_fuente"] = "yahoo (ajuste Blume: 0.67·β + 0.33)"
    else:
        p["beta_u"] = 1.0
        p["beta_fuente"] = "proxy_mercado_1.0"

    if enterprise_to_ebitda is not None and 1 <= enterprise_to_ebitda <= 50:
        p["exit_multiple"] = round(float(enterprise_to_ebitda), 2)
    else:
        # Fallback por mercado: US mega-tech ~22x (no 8–9 del catálogo BVC)
        merc = p.get("mercado_capm") or _codigo_mercado(
            (info or {}).get("country"),
            (info or {}).get("financialCurrency") or (info or {}).get("currency"),
            ticker_yf,
        )
        p["exit_multiple"] = 22.0 if merc == "US" else 10.0
        p["exit_multiple_fuente"] = f"fallback_{merc}"

    p["ticker_yf"] = ticker_yf
    p["currency"] = currency or ""
    return p


def params_empresa(nombre_empresa):
    """
    Parámetros de modelación:
      - Catálogo BVC: params predefinidos de esa ficha
      - Runtime (Yahoo / Excel ya cargado): params derivados desde cero de ESA empresa
      - Nombre libre sin datos: pizarra en blanco (ceros), NUNCA los defaults de ISA
    """
    emp = resolver_empresa(nombre_empresa)
    if emp and emp.get("params"):
        out = emp["params"].copy()
        # Marcar origen si no viene
        if "origen_params" not in out:
            out["origen_params"] = "catalogo" if nombre_empresa in EMPRESAS else "runtime"
        return out
    return params_en_blanco()


import re
import unicodedata


def _norm_col(txt):
    """Normaliza nombres de columna/fila: minúsculas, sin tildes, solo alfanuméricos."""
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


_COL_EXCLUIDAS = re.compile(r"margen|margin|ratio|crecimiento|growth|porcentaje")


def _mapear_columnas(columnas, aliases):
    """Asigna cada campo contable a UNA columna del archivo.

    Reglas (corrigen el uso previo de subcadenas, donde 'ebit' tomaba 'EBITDA' y 'da' tomaba 'Deuda'):
      1) coincidencia exacta del nombre normalizado;
      2) alias como PALABRA COMPLETA (nunca subcadena);
      3) una columna no se reutiliza para dos campos;
      4) se ignoran columnas de márgenes/ratios/crecimientos.
    """
    norm = {c: _norm_col(c) for c in columnas}
    usadas, out = set(), {}
    for fase in ("exacta", "palabra"):
        for target, names in aliases.items():
            if target in out:
                continue
            for alias in names:
                a = _norm_col(alias)
                patron = re.compile(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])")
                for col, n in norm.items():
                    if col in usadas or _COL_EXCLUIDAS.search(n):
                        continue
                    if (fase == "exacta" and n == a) or (fase == "palabra" and patron.search(n)):
                        out[target] = col
                        usadas.add(col)
                        break
                if target in out:
                    break
    return out


def _parse_columna_numerica(serie):
    """Convierte una columna a float soportando 1,234.56 / 1.234,56 / (123) / $ / %.

    El separador decimal se decide por columna (no por valor) para no mezclar formatos.
    """
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")
    s = serie.astype(str).str.strip()
    muestras = s[s.str.contains(r"\d", regex=True)]
    locale_es = bool(
        muestras.str.contains(r"\d,\d{1,2}\)?$").any()
        or muestras.str.contains(r"\d\.\d{3},\d").any()
        or muestras.str.contains(r"^[\(\-\$\s]*\d{1,3}(?:\.\d{3}){2,}").any()
    )

    def conv(x):
        x = str(x).strip()
        if x.lower() in ("", "nan", "none", "n/d", "na", "-", "—"):
            return np.nan
        neg = (x.startswith("(") and x.endswith(")")) or x.startswith("-") or x.endswith("-")
        x = re.sub(r"[^\d.,]", "", x)
        if not x:
            return np.nan
        x = x.replace(".", "").replace(",", ".") if locale_es else x.replace(",", "")
        try:
            v = float(x)
        except ValueError:
            return np.nan
        return -v if neg else v

    return s.map(conv)


def cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=True):
    """Carga financiera con trazabilidad. No mezcla filas ni completa con otra empresa.

    Excel/CSV esperado: Año (opcional), Ingresos, EBITDA, EBIT, CAPEX y NWC.
    Depreciación, Delta_NWC, NOPAT y FCFF se derivan cuando no están presentes.
    Todas las cifras deben estar en la misma moneda y unidad.
    """
    emp_resuelta = resolver_empresa(nombre_empresa)
    emp_catalogo = emp_resuelta is not None
    df_backup = df_historico_empresa(nombre_empresa)
    if archivo is None:
        if usar_datos_publicos and emp_catalogo:
            df_pub, msg_pub, _tipo = obtener_datos_financieros_publicos(nombre_empresa)
            if df_pub is not None and len(df_pub) >= 3:
                df_pub = _historico_sin_ceros_cola(df_pub.copy())
                # Filtrar cualquier año con Ingresos ~0 en medio de la serie
                if "Ingresos" in df_pub.columns:
                    df_pub = df_pub[df_pub["Ingresos"].apply(lambda x: pd.notna(x) and abs(float(x)) > 1e-6)]
                if len(df_pub) >= 3:
                    return df_pub, msg_pub
        if emp_catalogo and not df_backup.empty:
            fuente = (emp_resuelta or {}).get("fuente") or "catálogo"
            df_b = _historico_sin_ceros_cola(df_backup.copy())
            if "Ingresos" in df_b.columns:
                df_b = df_b[df_b["Ingresos"].apply(lambda x: pd.notna(x) and abs(float(x)) > 1e-6)]
            return df_b, f"Histórico disponible ({fuente}) para {nombre_empresa}; verificar antes de usar en decisiones."
        raise ValueError("Empresa personalizada: usa el buscador de ticker Yahoo o carga un Excel/CSV propio. No hay histórico de respaldo para este nombre.")

    path = archivo.name if hasattr(archivo, "name") else str(archivo)
    try:
        if str(path).lower().endswith(".csv"):
            raw = pd.read_csv(path)
        else:
            xls = pd.ExcelFile(path)
            raw = None
            for hoja in xls.sheet_names:
                temp = pd.read_excel(xls, sheet_name=hoja)
                cols_lower = [str(c).strip().lower() for c in temp.columns]
                if any(any(k in c for k in ["ingreso", "revenue", "ventas", "fcff"]) for c in cols_lower):
                    raw = temp
                    break
            if raw is None:
                raw = pd.read_excel(xls, sheet_name=0)
    except Exception as exc:
        raise ValueError(f"No fue posible leer el archivo: {exc}") from exc

    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    aliases = {
        "Año": ["año", "ano", "year", "fecha"],
        "Ingresos": ["ingresos", "revenue", "ventas", "sales", "total revenue"],
        "EBITDA": ["ebitda"],
        "EBIT": ["ebit", "utilidad operativa", "operating income"],
        "Depreciacion": ["depreciacion", "depreciación", "depreciation", "d&a", "da"],
        "CAPEX": ["capex", "inversiones", "capital expenditure"],
        "NWC": ["nwc", "capital de trabajo", "working capital"],
        "Delta_NWC": ["delta_nwc", "variacion capital de trabajo", "cambio en capital de trabajo"],
        "NOPAT": ["nopat"],
        "FCFF": ["fcff", "flujo de caja libre", "free cash flow"],
    }
    avisos = []
    clean = pd.DataFrame(index=raw.index)
    cols_map = _mapear_columnas(list(raw.columns), aliases)
    for target, col in cols_map.items():
        if target == "Año":
            continue
        clean[target] = _parse_columna_numerica(raw[col])
    required = ["Ingresos", "EBITDA", "EBIT", "CAPEX", "NWC"]
    missing = [c for c in required if c not in clean.columns or clean[c].notna().sum() < 3]
    if missing:
        raise ValueError("El archivo no tiene al menos 3 observaciones válidas para: " + ", ".join(missing) + ". No se usará información de otra empresa.")
    year_col = cols_map.get("Año")
    if year_col is not None:
        years = pd.to_numeric(raw[year_col], errors="coerce")
        if years.isna().any():
            # Fechas completas se convierten a año cuando es posible.
            years = pd.to_datetime(raw[year_col], errors="coerce").dt.year
        clean["Año"] = years
        clean = clean.dropna(subset=["Año"]).set_index("Año")
    else:
        ultimo = datetime.now().year - 1
        clean.index = range(ultimo - len(clean) + 1, ultimo + 1)
        clean.index.name = "Año"
        avisos.append(f"sin columna de año: se asumió que el último dato es {ultimo}")
    clean = clean.sort_index()
    clean = clean.replace([np.inf, -np.inf], np.nan)
    clean = clean.dropna(subset=required)
    if clean.index.has_duplicates:
        avisos.append("años duplicados: se conservó la última fila de cada año")
        clean = clean[~clean.index.duplicated(keep="last")]
    sin_ingresos = clean["Ingresos"] <= 0
    if sin_ingresos.any():
        avisos.append(f"se descartaron {int(sin_ingresos.sum())} fila(s) con Ingresos ≤ 0")
        clean = clean[~sin_ingresos]
    if (clean["CAPEX"] < 0).any():
        avisos.append("CAPEX con signo negativo (convención de flujo de caja): se tomó valor absoluto")
        clean["CAPEX"] = clean["CAPEX"].abs()
    if (clean["EBIT"] > clean["EBITDA"] * 1.001).any():
        avisos.append("hay años con EBIT > EBITDA: revisar columnas y unidades")
    if len(clean) < 3:
        raise ValueError("Después de validar los datos quedan menos de 3 años utilizables.")
    try:
        avisos += diagnosticar_atipicos_historico(clean)
    except Exception:
        pass
    if "Depreciacion" not in clean.columns:
        clean["Depreciacion"] = (clean["EBITDA"] - clean["EBIT"]).clip(lower=0)
    if "Delta_NWC" not in clean.columns:
        clean["Delta_NWC"] = clean["NWC"].diff().fillna(0)
    if "NOPAT" not in clean.columns:
        clean["NOPAT"] = np.nan
    if "FCFF" not in clean.columns:
        clean["FCFF"] = np.nan
    # Los valores faltantes se calculan contablemente; no se imputan con datos de otra empresa.
    tax_proxy = float(params_empresa(nombre_empresa).get("tax", 0.30))
    clean["NOPAT"] = clean["NOPAT"].where(clean["NOPAT"].notna(), clean["EBIT"] * (1 - tax_proxy))
    fcff_calc = clean["NOPAT"] + clean["Depreciacion"] - clean["CAPEX"] - clean["Delta_NWC"]
    clean["FCFF"] = clean["FCFF"].where(clean["FCFF"].notna(), fcff_calc)
    clean["EBITDA"] = clean["EBITDA"].astype(float)
    clean = clean.apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(clean[required].to_numpy(dtype=float)).all():
        raise ValueError("Hay valores no numéricos o infinitos en columnas financieras obligatorias.")
    # Empresa no catalogada: registrar histórico y params derivados desde este archivo (sin catálogo)
    if nombre_empresa not in EMPRESAS:
        params_xlsx = derivar_params_desde_cero(clean, info=None, ticker_yf=None)
        params_xlsx["origen_params"] = "excel_desde_cero"
        # Tax: si el usuario no tiene país, conservar 0 y recalcular NOPAT cuando calibre tax en UI
        hist = {"Año": [int(a) for a in clean.index]}
        for col in clean.columns:
            hist[col] = [float(x) if pd.notna(x) else 0.0 for x in clean[col].values]
        EMPRESAS_RUNTIME[nombre_empresa] = {
            "ticker_bvc": None,
            "ticker_yf": None,
            "sector": "No clasificado (Excel propio)",
            "descripcion": f"Estados cargados por el usuario para {nombre_empresa}. Parámetros derivados solo de este archivo.",
            "params": params_xlsx,
            "historico": hist,
            "peers": [],
            "fuente": "Excel/CSV del usuario",
            "moneda": "definir",
            "pais": "",
        }
    msg_avisos = ("Avisos de limpieza: " + " | ".join(avisos) + ". ") if avisos else ""
    return clean, (
        f"Archivo propio validado para {nombre_empresa}: {len(clean)} observaciones. {msg_avisos}"
        f"Campos derivados: depreciación/Delta_NWC/NOPAT/FCFF cuando no venían informados. "
        f"Parámetros de modelación derivados desde cero a partir de este archivo (sin catálogo BVC). "
        f"Verifica unidad, moneda y estados auditados."
    )

# =============================================================================
# NORMALIZACIÓN ROBUSTA DE ATÍPICOS
# -----------------------------------------------------------------------------
# Series contables anuales: n pequeño (3-8), no normales y con ciclos de inversión.
#  - Media/desv. estándar: se contaminan con un solo año atípico  -> NO se usan.
#  - Z-score clásico y Grubbs: asumen normalidad y n grande         -> NO se usan.
#  - IQR (Tukey): inestable con n < 5                               -> solo como respaldo.
#  - MEDIANA + MAD (Hampel / z modificado de Iglewicz-Hoaglin, umbral 3,5): punto de
#    ruptura del 50 %, válido con n >= 4  -> método base.
#  - Winsorización a mediana ± k·σ_MAD en vez de eliminar el dato (no se pierde el año).
#  - Si hay tendencia monótona (|Spearman| >= 0,8) la mediana "revertiría" a niveles abandonados:
#    se usa el último dato (sin extrapolar la tendencia).
#  - Piso de significancia práctica (15 % de la mediana o 1,5 pp): evita marcar desviaciones
#    triviales cuando la serie es muy suave y σ_MAD es diminuto.
#  - Cortes transversales (múltiplos de comparables): winsorización Hampel + z robusto.
# El histórico reportado NUNCA se modifica: solo se normalizan los drivers de proyección.
# =============================================================================
from scipy import stats as _sps

G_CONVERGENCIA = 0.03   # crecimiento hacia el que converge el crecimiento explícito (≈ inflación + PIB real bajo)
RONIC_SPREAD = 0.0      # rentabilidad marginal en perpetuidad = WACC + spread (0 = el crecimiento no crea valor extra)


def _sigma_mad(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else 0.0


def normalizar_atipicos(serie, k=3.5, reemplazo="winsor", piso_rel=0.0, piso_abs=0.0):
    """Detecta atípicos con Hampel (mediana ± k·σ_MAD). Devuelve (serie_normalizada, máscara).

    reemplazo="winsor"  : recorta al límite (series de tiempo: se conserva el año).
    reemplazo="mediana" : sustituye por la mediana (cortes transversales/peers: un dato sospechoso no
                          debe quedar como 'el mejor' o 'el peor' de la muestra)."""
    s = pd.Series(serie, dtype=float)
    vals = s.to_numpy(dtype=float)
    ok = np.isfinite(vals)
    mask = np.zeros(len(s), dtype=bool)
    if ok.sum() < 4:                       # muestra insuficiente: no se detecta nada
        return s, pd.Series(mask, index=s.index)
    med = float(np.median(vals[ok]))
    sig = _sigma_mad(vals[ok])
    if sig > 0:
        lo, hi = med - k * sig, med + k * sig
    else:                                  # MAD = 0 (muchos valores iguales): respaldo IQR de Tukey
        q1, q3 = np.percentile(vals[ok], [25, 75])
        iqr = q3 - q1
        if iqr <= 0:
            # ≥60 % de los datos son idénticos: lo que difiere de la mediana es el atípico
            if (np.isclose(vals[ok], med).mean() >= 0.6) and ok.sum() >= 5:
                lo, hi = med, med
            else:
                return s, pd.Series(mask, index=s.index)
        else:
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    # Piso de significancia práctica: con series muy suaves σ_MAD es diminuto y Hampel marcaría como
    # "atípico" una desviación económicamente irrelevante. Solo se marca si además supera el piso.
    semi_ancho = max((hi - lo) / 2.0, piso_rel * abs(med), piso_abs)
    centro = (hi + lo) / 2.0
    lo, hi = min(lo, centro - semi_ancho), max(hi, centro + semi_ancho)
    mask = ok & ((vals < lo - 1e-12) | (vals > hi + 1e-12))
    if reemplazo == "mediana":
        out = s.copy()
        out[mask] = med
        return out, pd.Series(mask, index=s.index)
    return s.clip(lower=lo, upper=hi), pd.Series(mask, index=s.index)


def driver_robusto(serie, ventana=5, k=3.5):
    """Nivel representativo de una razón histórica: Hampel + mediana (+ último dato si hay tendencia)."""
    s = pd.Series(serie, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().iloc[-ventana:]
    if s.empty:
        return np.nan, {"n": 0, "atipicos": [], "estimador": "sin datos"}
    s_n, mask = normalizar_atipicos(s, k=k, piso_rel=0.15, piso_abs=0.015)
    nivel = float(np.median(s_n))
    estimador = "mediana"
    if len(s_n) >= 4:
        rho = _sps.spearmanr(np.arange(len(s_n)), s_n.to_numpy())[0]
        if np.isfinite(rho) and abs(rho) >= 0.8:
            # tendencia persistente: la mediana "rebotaría" hacia niveles ya abandonados; se mantiene el nivel actual
            nivel = float(s_n.iloc[-1])
            estimador = "último dato (tendencia monótona; no se extrapola ni se revierte)"
    return nivel, {"n": int(len(s_n)), "atipicos": [i for i, m in zip(s.index, mask) if m], "estimador": estimador}


def _margenes_robustos(df_hist):
    """(margen EBITDA, margen EBIT, margen D&A, info). EBIT = EBITDA − D&A: coherencia contable."""
    ing = df_hist["Ingresos"].astype(float).replace(0, np.nan)
    m_ebitda, i1 = driver_robusto(df_hist["EBITDA"] / ing)
    m_da, i2 = driver_robusto((df_hist["EBITDA"] - df_hist["EBIT"]) / ing)
    m_ebitda = float(np.clip(m_ebitda if np.isfinite(m_ebitda) else 0.20, -0.20, 0.90))
    m_da = float(np.clip(m_da if np.isfinite(m_da) else 0.05, 0.0, 0.50))
    return m_ebitda, m_ebitda - m_da, m_da, {"ebitda": i1, "da": i2}


def diagnosticar_atipicos_historico(df):
    """Avisos (sin modificar el histórico) de años atípicos en razones clave y saltos de unidad."""
    avisos = []
    ing = df["Ingresos"].astype(float).replace(0, np.nan)
    razones = {
        "margen EBITDA": df["EBITDA"] / ing, "margen EBIT": df["EBIT"] / ing,
        "CAPEX/ingresos": df["CAPEX"] / ing, "NWC/ingresos": df["NWC"] / ing,
        "crecimiento de ingresos": ing.pct_change(),
    }
    for nombre, serie in razones.items():
        _, mask = normalizar_atipicos(serie.replace([np.inf, -np.inf], np.nan), piso_rel=0.15, piso_abs=0.015)
        anios = [int(i) for i, m in mask.items() if m]
        if anios:
            avisos.append(f"{nombre} atípico en {anios} (se normaliza con Hampel/mediana en la proyección; el histórico se conserva)")
    saltos = ing.pct_change().abs()
    if (saltos > 3.0).any():
        avisos.append(f"salto de ingresos >300% en {[int(i) for i in saltos[saltos > 3.0].index]}: posible error de unidades")
    return avisos


def _tendencia_cagr(serie, horizonte=5, floor_g=0.0, cap_g=0.12):
    """Crecimiento compuesto reciente (CAGR) acotado, útil con series cortas."""
    s = pd.Series(serie).dropna().astype(float)
    if len(s) < 2 or s.iloc[0] <= 0:
        last = float(s.iloc[-1]) if len(s) else 1000.0
        g = 0.04
    else:
        n = len(s) - 1
        g = (float(s.iloc[-1]) / float(s.iloc[0])) ** (1 / max(n, 1)) - 1
        g = float(np.clip(g, floor_g, cap_g))
        last = float(s.iloc[-1])
    forecast = np.array([last * (1 + g) ** i for i in range(1, horizonte + 1)])
    return forecast, g


def ajustar_ets(serie, horizonte=5):
    """Suavizado exponencial (Holt / tendencia aditiva). Mejor que ARIMA con series cortas anuales."""
    try:
        serie = pd.Series(serie).dropna().astype(float)
        if len(serie) < 3:
            forecast, g = _tendencia_cagr(serie, horizonte)
            std = max(abs(forecast[-1]) * 0.08, 1.0)
            return forecast, forecast - 1.96 * std, forecast + 1.96 * std, std, "CAGR"
        # Holt: nivel + tendencia (sin estacionalidad: datos anuales pocos)
        model = ExponentialSmoothing(
            serie, trend="add", seasonal=None, initialization_method="estimated"
        ).fit(optimized=True)
        forecast = np.asarray(model.forecast(horizonte), dtype=float)
        resid = np.asarray(model.resid.dropna(), dtype=float)
        std = float(np.std(resid)) if len(resid) else float(abs(forecast[-1]) * 0.06)
        std = max(std, abs(forecast[-1]) * 0.03)
        return forecast, forecast - 1.96 * std, forecast + 1.96 * std, std, "ETS (Holt)"
    except Exception:
        forecast, g = _tendencia_cagr(serie, horizonte)
        std = max(abs(forecast[-1]) * 0.08, 1.0)
        return forecast, forecast - 1.96 * std, forecast + 1.96 * std, std, "CAGR"


def ajustar_arima(serie, horizonte=5):
    """ARIMA(1,d,1) como benchmark / opción comparable."""
    try:
        serie = pd.Series(serie).dropna().astype(float)
        if len(serie) < 4:
            forecast, g = _tendencia_cagr(serie, horizonte)
            std = max(abs(forecast[-1]) * 0.07, 1.0)
            return forecast, forecast - 1.96 * std, forecast + 1.96 * std, std
        try:
            d = 0 if adfuller(serie)[1] < 0.05 else 1
        except Exception:
            d = 1
        model = ARIMA(serie, order=(1, d, 1)).fit()
        res = model.get_forecast(steps=horizonte)
        mean = res.predicted_mean.values
        conf = res.conf_int(alpha=0.05)
        resid_std = np.std(model.resid.dropna()) if len(model.resid.dropna()) > 0 else mean[-1] * 0.05
        return mean, conf.iloc[:, 0].values, conf.iloc[:, 1].values, resid_std
    except Exception:
        forecast, g = _tendencia_cagr(serie, horizonte)
        std = max(abs(forecast[-1]) * 0.07, 1.0)
        return forecast, forecast - 1.96 * std, forecast + 1.96 * std, std


def proyectar_por_drivers(df_hist, horizonte=5, tax=0.35, g_convergencia=None, convergencia_capex=True):
    """
    Proyección por drivers con estimadores ROBUSTOS (mediana + Hampel) e identidad FCFF:
    - Ingresos: crecimiento = mediana robusta de las variaciones anuales (admite caídas), con
      convergencia lineal hacia G_CONVERGENCIA al final del horizonte.
    - EBITDA y D&A como % de ingresos (EBIT = EBITDA − D&A: coherente; antes D&A salía de CAPEX×ratio).
    - CAPEX % ingresos robusto; converge hacia un nivel de mantenimiento (≤ 1,3×D&A) para que el
      último año del horizonte sea representativo de la perpetuidad.
    - NWC: coeficiente robusto sobre ΔIngresos (admite capital de trabajo negativo).
    - Sin pisos/techos de margen específicos de un sector.
    """
    H = int(horizonte)
    g_conv = G_CONVERGENCIA if g_convergencia is None else float(g_convergencia)
    años_fut = list(range(int(df_hist.index[-1]) + 1, int(df_hist.index[-1]) + 1 + H))
    ing = df_hist["Ingresos"].astype(float)

    g0, info_g = driver_robusto(ing.pct_change())
    g0 = float(np.clip(g0 if np.isfinite(g0) else 0.03, -0.10, 0.12))
    if H > 1:
        g_path = np.array([g0 + (g_conv - g0) * i / (H - 1) for i in range(H)])
    else:
        g_path = np.array([g0])
    ing_proj = float(ing.iloc[-1]) * np.cumprod(1 + g_path)
    ing_prev = np.concatenate([[float(ing.iloc[-1])], ing_proj[:-1]])

    m_ebitda, m_ebit, m_da, info_m = _margenes_robustos(df_hist)
    ebitda_proj = ing_proj * m_ebitda
    ebit_proj = ing_proj * m_ebit
    dep_proj = ebitda_proj - ebit_proj

    capex_r, info_c = driver_robusto(df_hist["CAPEX"].astype(float) / ing.replace(0, np.nan))
    capex_r = float(np.clip(capex_r if np.isfinite(capex_r) else 0.10, 0.0, 0.60))
    if convergencia_capex and H > 1:
        objetivo = max(m_da, min(capex_r, 1.3 * m_da))
        capex_path = np.array([capex_r + (objetivo - capex_r) * i / (H - 1) for i in range(H)])
    else:
        capex_path = np.full(H, capex_r)
    capex_proj = ing_proj * capex_path

    nwc_r, info_n = driver_robusto(df_hist["NWC"].astype(float) / ing.replace(0, np.nan))
    nwc_r = float(np.clip(nwc_r if np.isfinite(nwc_r) else 0.10, -0.30, 0.40))
    delta_nwc = nwc_r * (ing_proj - ing_prev)
    nwc_proj = float(df_hist["NWC"].iloc[-1]) + np.cumsum(delta_nwc)

    nopat_proj = ebit_proj - float(tax) * np.maximum(ebit_proj, 0.0)   # sin escudo fiscal por pérdidas
    fcff_proj = nopat_proj + dep_proj - capex_proj - delta_nwc

    df_proj = pd.DataFrame({
        "Año": años_fut, "Ingresos": ing_proj, "EBITDA": ebitda_proj, "EBIT": ebit_proj,
        "Depreciacion": dep_proj, "CAPEX": capex_proj, "NWC": nwc_proj,
        "Delta_NWC": delta_nwc, "NOPAT": nopat_proj, "FCFF": fcff_proj,
    }).set_index("Año")
    atip = {k: v["atipicos"] for k, v in {"crecimiento": info_g, "margen EBITDA": info_m["ebitda"],
            "margen D&A": info_m["da"], "CAPEX": info_c, "NWC": info_n}.items() if v["atipicos"]}
    meta = {
        "metodo": "Drivers robustos + identidad FCFF",
        "tax": float(tax),
        "g_ingresos": g0,
        "g_convergencia": g_conv,
        "margen_ebitda": m_ebitda,
        "margen_ebit": m_ebit,
        "margen_da": m_da,
        "capex_ratio": capex_r,
        "capex_ratio_final": float(capex_path[-1]),
        "nwc_ratio": nwc_r,
        "dep_ratio": (m_da / capex_r) if capex_r > 0 else 0.0,
        "estimador_ingresos": info_g["estimador"],
        "atipicos_normalizados": atip,
    }
    return df_proj, meta


def proyectar_por_ets(df_hist, horizonte=5, tax=0.35):
    """ETS/Holt sobre ingresos y CAPEX; márgenes e identidad FCFF como en drivers."""
    años_fut = list(range(int(df_hist.index[-1]) + 1, int(df_hist.index[-1]) + 1 + horizonte))
    ing_mean, _, _, std_ing, nombre = ajustar_ets(df_hist["Ingresos"], horizonte)
    margen_ebitda, margen_ebit, _m_da, _ = _margenes_robustos(df_hist)
    ebitda_proj = ing_mean * margen_ebitda
    ebit_proj = ing_mean * margen_ebit
    capex_mean, _, _, _, _ = ajustar_ets(df_hist["CAPEX"], horizonte)
    capex_mean = np.clip(capex_mean, 0.0, ing_mean * 0.60)
    nwc_mean, _, _, _, _ = ajustar_ets(df_hist["NWC"], horizonte)
    delta_nwc = np.diff(np.concatenate([[float(df_hist["NWC"].iloc[-1])], nwc_mean]))
    dep_proj = ebitda_proj - ebit_proj   # D&A coherente con EBITDA − EBIT
    nopat_proj = ebit_proj * (1 - float(tax))
    fcff_proj = nopat_proj + dep_proj - capex_mean - delta_nwc  # conservar FCFF negativos, sin piso artificial
    df_proj = pd.DataFrame({
        "Año": años_fut, "Ingresos": ing_mean, "EBITDA": ebitda_proj, "EBIT": ebit_proj,
        "Depreciacion": dep_proj, "CAPEX": capex_mean, "NWC": nwc_mean,
        "Delta_NWC": delta_nwc, "NOPAT": nopat_proj, "FCFF": fcff_proj,
    }).set_index("Año")
    meta = {"metodo": f"ETS/Holt ({nombre})", "std_ingresos": float(std_ing),
            "margen_ebitda": margen_ebitda, "margen_ebit": margen_ebit, "tax": float(tax)}
    return df_proj, meta


def proyectar_por_arima(df_hist, horizonte=5, tax=0.35):
    """Benchmark ARIMA (método anterior)."""
    años_fut = list(range(int(df_hist.index[-1]) + 1, int(df_hist.index[-1]) + 1 + horizonte))
    ing_mean, _, _, _ = ajustar_arima(df_hist["Ingresos"], horizonte=horizonte)
    margen_ebitda, margen_ebit, _m_da, _ = _margenes_robustos(df_hist)
    ebitda_proj = ing_mean * margen_ebitda
    ebit_proj = ing_mean * margen_ebit
    capex_mean, _, _, _ = ajustar_arima(df_hist["CAPEX"], horizonte=horizonte)
    capex_mean = np.clip(capex_mean, 0.0, ing_mean * 0.60)
    nwc_mean, _, _, _ = ajustar_arima(df_hist["NWC"], horizonte=horizonte)
    delta_nwc = np.diff(np.concatenate([[df_hist["NWC"].iloc[-1]], nwc_mean]))
    dep_proj = ebitda_proj - ebit_proj   # D&A coherente con EBITDA − EBIT
    nopat_proj = ebit_proj * (1 - float(tax))
    fcff_proj = nopat_proj + dep_proj - capex_mean - delta_nwc  # conservar FCFF negativos, sin piso artificial
    df_proj = pd.DataFrame({
        "Año": años_fut, "Ingresos": ing_mean, "EBITDA": ebitda_proj, "EBIT": ebit_proj,
        "Depreciacion": dep_proj, "CAPEX": capex_mean, "NWC": nwc_mean,
        "Delta_NWC": delta_nwc, "NOPAT": nopat_proj, "FCFF": fcff_proj,
    }).set_index("Año")
    return df_proj, {"metodo": "ARIMA (benchmark)", "tax": float(tax)}


def proyectar_variables(df_hist, horizonte=5, metodo="drivers", tax=0.35):
    """
    Despacha el método de proyección.
    metodo: 'drivers' (recomendado) | 'ets' | 'arima'
    """
    metodo = (metodo or "drivers").lower()
    if "ets" in metodo or "holt" in metodo:
        return proyectar_por_ets(df_hist, horizonte, tax=tax)[0]
    if "arima" in metodo:
        return proyectar_por_arima(df_hist, horizonte, tax=tax)[0]
    return proyectar_por_drivers(df_hist, horizonte, tax=tax)[0]


def proyectar_variables_con_meta(df_hist, horizonte=5, metodo="drivers", tax=0.35):
    metodo = (metodo or "drivers").lower()
    if "ets" in metodo or "holt" in metodo:
        return proyectar_por_ets(df_hist, horizonte, tax=tax)
    if "arima" in metodo:
        return proyectar_por_arima(df_hist, horizonte, tax=tax)
    return proyectar_por_drivers(df_hist, horizonte, tax=tax)



def recalcular_fcff(df_proj, tax=0.35, capex_extra=0.0):
    """Recalcula FCFF; rechaza datos faltantes o inválidos en vez de convertirlos en cero."""
    if not isinstance(df_proj, pd.DataFrame) or df_proj.empty:
        raise ValueError("La proyección FCFF debe ser un DataFrame no vacío.")
    try:
        tax = float(tax)
        capex_extra = float(capex_extra)
    except (TypeError, ValueError) as exc:
        raise ValueError("La tasa fiscal y el CAPEX adicional deben ser numéricos.") from exc
    if not np.isfinite(tax) or not 0.0 <= tax <= 1.0:
        raise ValueError("La tasa fiscal debe ser finita y estar entre 0 y 1.")
    if not np.isfinite(capex_extra):
        raise ValueError("El CAPEX adicional debe ser finito.")
    required = ["EBIT", "Depreciacion", "CAPEX", "Delta_NWC"]
    missing = [col for col in required if col not in df_proj.columns]
    if missing:
        raise ValueError(f"Faltan columnas para recalcular FCFF: {', '.join(missing)}.")
    d = df_proj.copy()
    for col in required:
        d[col] = pd.to_numeric(d[col], errors="coerce").astype(float)
        if not np.isfinite(d[col].to_numpy(dtype=float)).all():
            raise ValueError(f"La columna {col} contiene valores ausentes o no finitos; no se reemplazan por cero.")
    ebit = d["EBIT"].to_numpy(dtype=float)
    dep = d["Depreciacion"].to_numpy(dtype=float)
    capex = d["CAPEX"].to_numpy(dtype=float) + capex_extra
    dnwc = d["Delta_NWC"].to_numpy(dtype=float)
    nopat = calcular_nopat(ebit, tax)
    d["CAPEX"] = capex
    d["NOPAT"] = nopat
    d["FCFF"] = nopat + dep - capex - dnwc
    if not np.isfinite(d["FCFF"].to_numpy(dtype=float)).all():
        raise ValueError("El FCFF recalculado contiene valores no finitos.")
    return d

def capital_base_roic(capital_invertido, nopat_prom=None, deuda_neta=0.0, equity_val=None):
    """Devuelve una base contable disponible; nunca fabrica capital a partir del NOPAT.

    Si el capital no está disponible, falla explícitamente para que el caller marque
    ROIC como no calculable en lugar de presentar un proxy como dato contable.
    """
    caps = []
    try:
        c0 = float(capital_invertido)
        if np.isfinite(c0) and c0 > 0:
            caps.append(c0)
    except (TypeError, ValueError):
        pass
    try:
        dn = float(deuda_neta or 0.0)
        ev = float(equity_val)
        if np.isfinite(dn) and np.isfinite(ev) and ev > 0:
            caps.append(ev + max(dn, 0.0))
    except (TypeError, ValueError):
        pass
    if not caps:
        raise ValueError("ROIC no disponible: falta una base de capital invertido válida del balance.")
    return max(caps)



def monte_carlo_fcff(df_proj, df_hist, horizonte=5, n_sim=1000, seed=42, tax=0.35):
    """
    Bandas de incertidumbre por Monte Carlo CENTRADAS en la proyección base:
    los supuestos (márgenes, CAPEX %, NWC) se leen de df_proj, no de promedios distintos;
    la volatilidad de ingresos usa σ_MAD (robusta a años atípicos) en vez de la desviación estándar.
    """
    rng = np.random.default_rng(seed)
    base_ing = df_proj["Ingresos"].values.astype(float)
    pct = df_hist["Ingresos"].astype(float).pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    vol = _sigma_mad(pct.values) if len(pct) >= 3 else (float(pct.std()) if len(pct) else 0.06)
    if not np.isfinite(vol) or vol <= 0:
        vol = float(pct.std()) if len(pct) > 1 else 0.06
    vol = float(np.clip(vol, 0.02, 0.20))
    m_ebit = (df_proj["EBIT"] / df_proj["Ingresos"]).values.astype(float)
    m_da = ((df_proj["EBITDA"] - df_proj["EBIT"]) / df_proj["Ingresos"]).values.astype(float)
    c_ratio = (df_proj["CAPEX"] / df_proj["Ingresos"]).values.astype(float)
    nwc_ratio = float(df_proj["NWC"].iloc[-1] / df_proj["Ingresos"].iloc[-1])
    ing0 = float(df_hist["Ingresos"].iloc[-1])

    sims = np.zeros((n_sim, horizonte))
    for s in range(n_sim):
        shocks = rng.normal(0, vol, size=horizonte)
        ing = base_ing * np.cumprod(1 + shocks)
        ruido_m = rng.normal(0, 0.02)
        ruido_c = rng.normal(0, 0.02)
        ebit = ing * (m_ebit + ruido_m)
        nopat = ebit - float(tax) * np.maximum(ebit, 0.0)
        dep = ing * m_da
        capex = ing * np.clip(c_ratio + ruido_c, 0.0, 0.6)
        dnwc = nwc_ratio * np.diff(np.concatenate([[ing0], ing]))
        sims[s, :] = nopat + dep - capex - dnwc

    return {
        "p50": np.percentile(sims, 50, axis=0), "p10": np.percentile(sims, 10, axis=0),
        "p90": np.percentile(sims, 90, axis=0), "p05": np.percentile(sims, 5, axis=0),
        "p95": np.percentile(sims, 95, axis=0), "std": sims.std(axis=0),
        "vol_ingresos": vol, "n_sim": n_sim,
    }


def generar_fan_chart(df_hist, df_proj, mc_or_std, horizonte=5, nombre_empresa="Empresa", metodo_label="Drivers"):
    """Fan chart con bandas Monte Carlo (dict) o std escalar legado."""
    fig, ax = plt.subplots(figsize=(11, 5.8))
    años_hist = df_hist.index.astype(int)
    años_fut = df_proj.index.astype(int)
    ax.plot(años_hist, df_hist["FCFF"], "o-", color=COLOR_PRIMARY, lw=2.6, ms=8, label="FCFF Histórico", zorder=5)
    ax.plot(años_fut, df_proj["FCFF"], "s--", color=COLOR_ACCENT, lw=2.6, ms=8, label="FCFF Base", zorder=5)

    if isinstance(mc_or_std, dict):
        ax.fill_between(años_fut, mc_or_std["p05"], mc_or_std["p95"], color="#99E6E5", alpha=0.35, label="IC ~90% (MC)")
        ax.fill_between(años_fut, mc_or_std["p10"], mc_or_std["p90"], color="#33C2C0", alpha=0.40, label="IC ~80% (MC)")
        ax.plot(años_fut, mc_or_std["p50"], ":", color="#0F766E", lw=1.8, label="Mediana MC")
    else:
        resid_std_fcff = float(mc_or_std)
        z_vals = {0.50: 0.674, 0.80: 1.282, 0.95: 1.960}
        colors = ["#99E6E5", "#66D4D2", "#33C2C0"]
        for i, (nivel, z) in enumerate(z_vals.items()):
            std = resid_std_fcff * np.sqrt(np.arange(1, horizonte + 1))
            upper = df_proj["FCFF"].values + z * std
            lower = df_proj["FCFF"].values - z * std
            ax.fill_between(años_fut, lower, upper, color=colors[i], alpha=0.45, label=f"IC {int(nivel*100)}%")

    ax.axhline(0, color="#94A3B8", ls=":", lw=1.2)
    ax.set_title(f"Fan Chart · FCFF ({metodo_label})\n{nombre_empresa}",
                 fontsize=13, fontweight="bold", color=COLOR_PRIMARY, pad=12)
    ax.set_xlabel("Año")
    ax.set_ylabel("FCFF (miles de millones, moneda del emisor)")
    ax.legend(loc="upper left", frameon=True, fancybox=True, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    anotar_grafico(ax, "Línea sólida = historia · Punteada = base\nBandas = incertidumbre Monte Carlo\nSi la banda baja cruza 0 → riesgo de caja", loc="lower left")
    return fig



def calcular_wacc(de, kd, ke, t):
    we = 1 / (1 + de)
    wd = de / (1 + de)
    return we * ke + wd * kd * (1 - t), we, wd


def costo_equity_capm(beta_l, rf=0.09, erp=0.06, crp=0.0):
    """
    CAPM con prima país opcional (enfoque institucional emergente).
    Ke = rf + β_L × ERP + CRP
    """
    return float(rf) + float(beta_l) * float(erp) + float(crp or 0.0)



def _normalizar_yield(y):
    """Yahoo: yield como fracción (0.03) o como % (3.0). Devuelve fracción 0-1 o None."""
    if y is None:
        return None
    try:
        v = float(y)
    except Exception:
        return None
    if not np.isfinite(v) or v < 0:
        return None
    if v > 1.0:
        v = v / 100.0
    if v > 0.25:
        return None
    return v



def procedencia_datos(mensaje_carga, ticker_yf=None, mkt=None):
    """Clasifica la calidad/origen de los datos para gobernanza."""
    msg = (mensaje_carga or "").lower()
    if "excel" in msg and "error" not in msg and "insuficientes" not in msg and "respaldo" not in msg:
        nivel, etiqueta = "ALTA", "Estados / Excel del usuario"
    elif "yahoo" in msg or "yfinance" in msg:
        nivel, etiqueta = "MEDIA", "Descarga pública Yahoo Finance (agregada; no es el PDF auditado)"
    elif "curada" in msg or "curado" in msg or "pública curada" in msg or "publica_curada" in msg or "catálogo" in msg or "catalogo" in msg:
        nivel, etiqueta = "MEDIA", "Serie de catálogo/curada (ilustrativa; NWC/FCFF pueden ser estimados — validar vs EEFF)"
    elif "respaldo" in msg or "backup" in msg:
        nivel, etiqueta = "MEDIA-BAJA", "Serie histórica de respaldo (ilustrativa)"
    else:
        nivel, etiqueta = "MEDIA", "Mixto / revisar fuente"
    mercado = "Sin precio BVC en vivo"
    if mkt and mkt.get("ok") and mkt.get("precio"):
        mercado = f"Precio BVC/Yahoo disponible ({mkt.get('precio'):,.0f} {mkt.get('moneda', 'COP')})"
    elif ticker_yf:
        mercado = f"Ticker {ticker_yf} configurado, sin cotización usable en este momento"
    return {
        "nivel_calidad": nivel,
        "fuente_financiera": etiqueta,
        "fuente_mercado": mercado,
        "mensaje": mensaje_carga or "",
    }


def matriz_sensibilidad_wacc_g(fcff_series, deuda_neta, wacc_base, g_base, deuda_neta_val=None, mid_year=True, g_max_macro=0.05, nopat_final=None):
    """Matriz EV y Equity ante cambios de WACC y g (herramienta de comité)."""
    deuda = float(deuda_neta if deuda_neta_val is None else deuda_neta_val)
    waccs = [max(0.04, wacc_base + dw) for dw in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    gs = [max(0.005, g_base + dg) for dg in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    # Evitar g >= wacc
    rows = []
    for w in waccs:
        row = {"WACC %": round(w * 100, 2)}
        for g in gs:
            # valoracion_dcf aplica el mismo techo (min(g_max_macro, WACC−1pp)) que el caso base
            val = valoracion_dcf(fcff_series, w, g, deuda_neta=deuda, mid_year=mid_year, g_max_macro=g_max_macro, nopat_final=nopat_final)
            row[f"g={g*100:.1f}% EV"] = round(val["EV"], 1)
        rows.append(row)
    return pd.DataFrame(rows)


def motor_decision_institucional(
    *,
    wacc, g, roic, de_ratio, vpn, tir, payback, ev_base, equity_base,
    equity_pesimista, delta_ev_capex, riesgo_liq, procedencia, score_heuristico,
    precio_mercado=None, equity_por_accion=None, tv_pct=None, mult_terminal=None,
    moneda_modelo=None, moneda_precio=None,
):
    """
    Marco de decisión estilo comité de inversión.
    No emite orden de compra automática: clasifica con vetos y condiciones.
    moneda_modelo / moneda_precio: si difieren (ej. modelo USD vs precio COP),
    el upside se invalida para no emitir sesgo de compra falso.
    """
    vetos = []
    alertas = []
    soportes = []

    # Consistencia de moneda (evita tomar USD como COP o viceversa)
    mm = (moneda_modelo or "").upper().strip()
    mp = (moneda_precio or "").upper().strip()
    if mm and mp and mm != mp:
        alertas.append(
            f"Moneda del modelo ({mm}) distinta de la del precio de mercado ({mp}). "
            "El upside por acción NO es comparable sin conversión FX; no uses el % "
            "como señal de compra/venta hasta alinear unidades."
        )
        # Anular señal de mercado basada en upside cuando las monedas no coinciden
        precio_mercado = None
        equity_por_accion = None
    elif mm and mm not in ("COP", "USD", "BRL", "MXN", "CLP", "GBP", "EUR"):
        alertas.append(f"Moneda de modelación poco habitual ({mm}): verifica escala y FX.")

    # Vetos de calidad del modelo (controles de consistencia; NO son rating de la acción)
    # g vs WACC: solo veto si g >= WACC (modelo Gordon roto). Si está cerca, es alerta calibrable.
    if wacc is not None and g is not None and float(wacc) > 0:
        if float(g) >= float(wacc):
            vetos.append(
                "g terminal ≥ WACC: el valor terminal de Gordon no está definido. "
                "Baja g (largo plazo) o revisa rf/ERP/β del mercado de la empresa."
            )
        elif float(g) >= float(wacc) - 0.01:
            alertas.append(
                "g terminal muy cerca del WACC (<1 pp). El TV es hipersensible; "
                "usa g de perpetuidad (PIB nominal del país), no el CAGR reciente."
            )
    if equity_base is not None and equity_base <= 0:
        vetos.append(
            "Equity value base ≤ 0 tras el bridge (EV − deuda neta + caja − NCI − otros + asociados). "
            "Revisa: (1) FCFF del horizonte y TV Gordon, (2) deuda neta y NCI en la misma unidad, "
            "(3) que el último año histórico no tenga FCFF atípico negativo contaminando la proyección."
        )
    elif equity_base is not None and ev_base is not None and float(ev_base) > 0 and float(equity_base) < 0.1 * float(ev_base):
        alertas.append(
            "Equity es una fracción muy baja del EV: el bridge (deuda/NCI) consume casi todo el valor de la firma."
        )
    # Métricas de firma: MVA = EV − capital invertido; TIR implícita (con valor terminal) vs WACC
    if vpn is not None and vpn < 0 and tir is not None and not (isinstance(tir, float) and (tir != tir)):
        if tir < wacc:
            alertas.append(
                "El valor de la firma (EV) no supera el capital invertido y su TIR implícita es menor que el WACC: "
                "el modelo no ve creación de valor sobre el capital empleado."
            )
    # Coherencia del valor terminal (control de calidad del modelo)
    if tv_pct is not None and tv_pct > 0.85:
        alertas.append(f"El valor terminal explica {tv_pct*100:.0f}% del EV: la valoración depende casi solo de la perpetuidad.")
    if mult_terminal is not None and (mult_terminal < 3.0 or mult_terminal > 18.0):
        alertas.append(
            f"EV/EBITDA terminal implícito de {mult_terminal:.1f}× fuera del rango habitual (3×–18×): "
            "revisa CAPEX/D&A, WACC y g."
        )
    if procedencia.get("nivel_calidad") == "MEDIA-BAJA":
        alertas.append("Datos financieros de respaldo ilustrativos: no usar como única base de una decisión real.")
    elif procedencia.get("nivel_calidad") != "ALTA":
        alertas.append(
            "ROIC, MVA y TIR implícita son indicativos porque la fuente financiera no está verificada "
            "con estados financieros completos; valida periodo, unidades y capital invertido antes "
            "de interpretar las alertas como una conclusión económica sobre la empresa."
        )
    if de_ratio > 2.0:
        alertas.append("Apalancamiento D/E > 2.0: riesgo financiero elevado.")
    elif de_ratio > 1.5:
        alertas.append("Apalancamiento D/E > 1.5: monitorear covenants y refinanciación.")
    if roic < wacc:
        alertas.append("ROIC < WACC: el capital no cubre su costo en el escenario modelado.")
    else:
        soportes.append(f"ROIC ({roic*100:.1f}%) > WACC ({wacc*100:.1f}%): crea valor económico.")
    if equity_pesimista is not None and equity_pesimista > 0:
        soportes.append("Equity positivo en escenario pesimista (margen de seguridad relativo).")
    elif equity_pesimista is not None and equity_pesimista <= 0:
        alertas.append("Equity ≤ 0 en escenario pesimista: poca holgura ante shocks.")
    if riesgo_liq == "Alto":
        alertas.append("Riesgo de liquidez de flujos (FCFF mínimo negativo).")
    elif riesgo_liq == "Bajo":
        soportes.append("Perfil de caja proyectado sin tensiones severas.")
    if delta_ev_capex is not None and delta_ev_capex < 0:
        alertas.append("El CAPEX extra reduce el EV respecto al caso sin inversión adicional.")
    elif delta_ev_capex is not None and delta_ev_capex > 0:
        soportes.append("El CAPEX extra aporta EV incremental positivo.")
    if payback is not None and payback > 8:
        alertas.append("Payback largo (> 8 años): mayor exposición temporal.")

    # Clasificación
    if vetos:
        # El veto es CONTROL DE CALIDAD DEL MODELO, no un rating de la acción:
        # indica supuestos/datos internamente inconsistentes que hay que recalibrar.
        decision = "RECALIBRAR MODELO · VETO DE CALIDAD"
        color = "#B45309"
        sesgo = (
            "Veto de calidad del modelo activo: los supuestos o datos son internamente inconsistentes "
            "(g vs WACC, equity bridge, FCFF/TV). Esto NO es un rating ni una orden de venta sobre la acción; "
            "no se emite sesgo de inversión hasta recalibrar el modelo y contrastarlo con el mercado."
        )
    elif len(alertas) >= 3 or (len(alertas) >= 2 and len(soportes) == 0):
        decision = "EVITAR / REVISAR"
        color = "#EA580C"
        sesgo = "Demasiadas alertas de riesgo o calidad de datos frente a los soportes."
    elif equity_pesimista is not None and equity_pesimista > 0 and roic > wacc and (vpn is None or vpn >= 0):
        solo_dato = (
            len(alertas) == 1
            and "respaldo" in alertas[0].lower()
        )
        if procedencia.get("nivel_calidad") == "ALTA" and len(alertas) <= 1:
            decision = "FAVORABLE CONDICIONADO"
            color = "#059669"
            sesgo = (
                "Los números del modelo son coherentes (crea valor, holgura en pesimista). "
                "Aun así, un comité exige validar cifras auditadas, liquidez del título y límites del mandato."
            )
        elif solo_dato or procedencia.get("nivel_calidad") in ("MEDIA-BAJA", "MEDIA"):  # series curadas/ilustrativas: falta auditoría
            decision = "PRELIMINAR POSITIVO · PENDIENTE DE DATOS AUDITADOS"
            color = "#CA8A04"
            sesgo = (
                "Los fundamentos modelados se ven bien (ROIC > WACC, equity positivo incluso en pesimista), "
                "pero la serie financiera es de respaldo ilustrativo. "
                "No se puede emitir sesgo de inversión firme hasta cargar estados auditados o un Excel oficial."
            )
        else:
            decision = "NEUTRAL / MONITOREAR"
            color = "#D97706"
            sesgo = "Hay soportes, pero alertas residuales impiden un sesgo de compra firme."
    else:
        decision = "NEUTRAL / MONITOREAR"
        color = "#D97706"
        sesgo = "Señal mixta: no hay convicción institucional suficiente."

    return {
        "decision": decision,
        "color": color,
        "sesgo": sesgo,
        "vetos": vetos,
        "alertas": alertas,
        "soportes": soportes,
        "score_heuristico": score_heuristico,
        "control_calidad_modelo": bool(vetos),  # True = recalibrar modelo; no es rating de la acción
    }


def _metrics_mercado_yahoo(ticker_yf):
    """Snapshot de mercado (best-effort). Reutiliza el proveedor Yahoo enriquecido."""
    out = {"ok": False, "ticker": ticker_yf}
    if not ticker_yf or not HAS_YF:
        return out
    try:
        ticker_yf = asegurar_sufijo_cl_bvc(ticker_yf) or ticker_yf
        m = _proveedor_yahoo(ticker_yf)
        if not m or not m.get("ok"):
            # último intento directo
            t = yf.Ticker(ticker_yf)
            info = _yf_info_dict(t)
            price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose"))
            mcap = _safe_float(info.get("marketCap"))
            pe = _safe_float(info.get("trailingPE") or info.get("forwardPE"))
            beta = _safe_float(info.get("beta"))
            out.update({
                "ok": price is not None or mcap is not None,
                "precio": price,
                "market_cap": mcap,
                "pe": pe,
                "beta": beta,
                "currency": info.get("currency") or "",
                "nombre": info.get("shortName") or info.get("longName") or ticker_yf,
            })
            return out
        out.update({
            "ok": True,
            "precio": m.get("precio"),
            "market_cap": m.get("market_cap"),
            "pe": m.get("pe"),
            "ev_ebitda": m.get("enterprise_to_ebitda"),
            "beta": m.get("beta"),
            "currency": m.get("moneda") or "",
            "nombre": ticker_yf,
            "div_yield": None,
            "target": None,
            "rec_yahoo": "",
        })
    except Exception as e:
        out["error"] = str(e)
    return out


def veredicto_inversion_mercado(nombre_empresa, mkt, upside_modelo_pct=None, motor=None, procedencia=None):
    """
    Lectura del MERCADO de la empresa valorada -> veredicto de inversión.
    Puntúa señales observables (analistas, múltiplos, dividendo, beta y, solo si el
    modelo no tiene veto de calidad, el upside del DCF) y emite:
      'Analizando el mercado se infiere que es una buena/mala decisión invertir en X'.
    Motor de reglas (no es un LLM externo ni asesoría de inversión).
    """
    from html import escape
    mkt = mkt or {}
    motor = motor or {}
    procedencia = procedencia or {}
    nombre = str(nombre_empresa)
    senales = []   # (texto, puntos)

    precio = mkt.get("precio")
    tgt = mkt.get("target")
    if tgt is not None and precio:
        u = (float(tgt) / float(precio) - 1.0) * 100.0
        pts = 2 if u >= 20 else 1 if u >= 8 else -2 if u <= -20 else -1 if u <= -8 else 0
        senales.append((f"Precio objetivo de analistas {float(tgt):,.0f} ({u:+.1f}% vs precio actual)", pts))

    rec = str(mkt.get("rec_yahoo") or "").strip().lower().replace(" ", "_")
    if rec and rec not in ("none", "n/d", "nan"):
        if "strong_buy" in rec:
            pts = 2
        elif "buy" in rec or "outperform" in rec or "overweight" in rec:
            pts = 1
        elif "strong_sell" in rec:
            pts = -2
        elif "sell" in rec:
            pts = -2
        elif "underperform" in rec or "underweight" in rec:
            pts = -1
        else:
            pts = 0
        senales.append((f"Consenso de analistas (Yahoo): {mkt.get('rec_yahoo')}", pts))

    # Upside del DCF solo si el modelo NO tiene veto de calidad (si lo tiene, no es confiable)
    modelo_usable = (
        upside_modelo_pct is not None
        and not (motor.get("vetos") or [])
    )
    if modelo_usable:
        m = float(upside_modelo_pct)
        pts = 2 if m >= 20 else 1 if m >= 8 else -2 if m <= -20 else -1 if m <= -8 else 0
        if procedencia.get("nivel_calidad") == "MEDIA-BAJA":
            pts = max(-1, min(1, pts))  # datos de respaldo: peso reducido
        senales.append((f"Valor por acción del modelo DCF {m:+.1f}% vs precio", pts))

    ev_e = mkt.get("ev_ebitda")
    if ev_e is not None and ev_e > 0:
        pts = 1 if ev_e <= 6 else -1 if ev_e >= 14 else 0
        senales.append((f"EV/EBITDA {float(ev_e):.1f}× ({'barato' if pts > 0 else 'exigente' if pts < 0 else 'en rango medio'})", pts))
    pe = mkt.get("pe")
    if pe is not None and pe > 0:
        pts = 1 if pe <= 10 else -1 if pe >= 30 else 0
        senales.append((f"P/E {float(pe):.1f}× ({'bajo' if pts > 0 else 'alto' if pts < 0 else 'en rango medio'})", pts))
    dy = mkt.get("div_yield")
    if dy is not None and dy >= 0.05:
        senales.append((f"Dividend yield {float(dy)*100:.1f}% (retorno por dividendos atractivo)", 1))
    beta = mkt.get("beta")
    if beta is not None and beta >= 1.5:
        senales.append((f"β de mercado {float(beta):.2f} (alta sensibilidad al mercado)", -1))

    total = sum(p for _, p in senales)
    n = len(senales)

    if n < 2:
        veredicto, etiqueta, color = "NO CONCLUYENTE", "no concluyente", "#64748B"
        frase = (f"No hay datos de mercado suficientes para inferir si es una buena o mala decisión invertir en {nombre}. "
                 "Carga cotización y métricas (ticker válido / conexión a Yahoo) y vuelve a correr.")
    elif total >= 3:
        veredicto, etiqueta, color = "BUENA", "buena decisión", "#059669"
        frase = f"Analizando el mercado se infiere que es una buena decisión invertir en {nombre}."
    elif total <= -3:
        veredicto, etiqueta, color = "MALA", "mala decisión", "#DC2626"
        frase = f"Analizando el mercado se infiere que es una mala decisión invertir en {nombre}."
    else:
        veredicto, etiqueta, color = "NEUTRAL", "decisión neutral", "#D97706"
        frase = (f"Analizando el mercado se infiere que invertir en {nombre} es una decisión neutral: "
                 "las señales son mixtas y no hay una ventaja clara a favor ni en contra.")

    notas = []
    if motor.get("vetos"):
        notas.append("El modelo DCF tiene un veto de calidad activo, así que este veredicto se basa solo en el mercado "
                     "(el valor del modelo no se usó). Recalibra el modelo para contrastarlo.")
    elif modelo_usable and veredicto in ("BUENA", "MALA"):
        m = float(upside_modelo_pct)
        if (veredicto == "BUENA" and m <= -8) or (veredicto == "MALA" and m >= 8):
            notas.append("El valor por acción del modelo DCF apunta en dirección contraria al mercado: "
                         "revisa supuestos antes de actuar.")
    if procedencia.get("nivel_calidad") == "MEDIA-BAJA":
        notas.append("Los datos financieros del modelo son de respaldo ilustrativo; la lectura de mercado es más confiable que el DCF.")

    filas = "".join(
        f"<li style='margin:4px 0'>{escape(t)} "
        f"<b style='color:{'#059669' if p > 0 else '#DC2626' if p < 0 else '#64748B'}'>({p:+d})</b></li>"
        for t, p in senales
    ) or "<li>Sin señales de mercado disponibles.</li>"
    notas_html = "".join(f"<p style='margin:6px 0 0 0;font-size:12px;color:#94A3B8'>{escape(x)}</p>" for x in notas)
    html = f"""
  <div style="background:#151C2C;border:3px solid {color};border-radius:12px;padding:14px 16px;margin:0 0 12px 0">
    <div style="font-size:12px;font-weight:700;color:#94A3B8;letter-spacing:.04em">LECTURA DEL MERCADO · VEREDICTO DE INVERSIÓN</div>
    <div style="font-size:18px;font-weight:800;color:{color};margin:6px 0">{escape(etiqueta.upper())} · puntaje de mercado {total:+d} ({n} señales)</div>
    <p style="margin:0 0 8px 0;font-size:15px;line-height:1.5;color:#E8EEF7"><b>{escape(frase)}</b></p>
    <ul style="margin:0;padding-left:18px;color:#CBD5E1;font-size:13px;line-height:1.45">{filas}</ul>
    {notas_html}
  </div>"""
    texto_senales = "; ".join(f"{t} ({p:+d})" for t, p in senales)
    return {
        "veredicto": veredicto, "etiqueta": etiqueta, "color": color, "puntos": total,
        "n_senales": n, "senales": senales, "frase": frase, "notas": notas, "html": html,
        "texto_plano": frase + (f" Señales: {texto_senales}." if texto_senales else "") + " " + " ".join(notas),
    }


def modulo_ia_contraste_decision(
    *,
    nombre_empresa,
    motor,
    wacc,
    g,
    roic,
    equity_base,
    ev_base,
    de_ratio,
    procedencia,
    ticker_yf=None,
    precio_modelo=None,
    upside_modelo_pct=None,
):
    """
    Módulo de contraste 'modelo vs mercado'.
    No es un LLM externo: motor de reglas experto que:
      1) resume por qué el modelo decidió lo que decidió,
      2) compara con snapshot de mercado (Yahoo),
      3) emite una opción lógica de interpretación (no orden de bolsa).
    """
    from html import escape
    decision = (motor or {}).get("decision") or "N/D"
    vetos = list((motor or {}).get("vetos") or [])
    alertas = list((motor or {}).get("alertas") or [])
    soportes = list((motor or {}).get("soportes") or [])
    color = (motor or {}).get("color") or "#64748B"

    mkt = _metrics_mercado_yahoo(ticker_yf) if ticker_yf else {"ok": False}
    if not mkt.get("ok") and precio_modelo:
        mkt = {"ok": True, "precio": precio_modelo, "ticker": ticker_yf, "currency": (moneda_precio_empresa(nombre_empresa) if nombre_empresa else "USD"), "moneda": (moneda_precio_empresa(nombre_empresa) if nombre_empresa else "USD")}

    # --- Explicación de cada veto en lenguaje de negocio ---
    explicaciones = []
    for v in vetos:
        vl = v.lower()
        if "equity" in vl and "≤ 0" in v or "equity value base" in vl:
            explicaciones.append(
                "<b>Veto equity ≤ 0:</b> el DCF del modelo, tras restar deuda neta y NCI del bridge, "
                "deja valor accionario modelado nulo o negativo. En el mercado la acción cotiza con "
                "capitalización positiva; la discrepancia suele venir de FCFF/TV del catálogo, "
                "NCI/deuda desactualizados o un año de CAPEX atípico, no de insolvencia real."
            )
        elif "g terminal" in vl or "gordon" in vl or "wacc" in vl and "g" in vl:
            explicaciones.append(
                "<b>Veto g ≥ WACC:</b> con esos supuestos el valor terminal de Gordon no es matemáticamente estable. "
                "En la práctica hay que bajar g de perpetuidad (2,5–3,5% típico utilities CO) o revisar rf/β/kd. "
                "No implica por sí solo que el negocio deje de generar caja."
            )
        else:
            explicaciones.append(f"<b>Veto del motor:</b> {escape(v)}")

    if not explicaciones and alertas:
        explicaciones.append(
            "No hay vetos duros; la postura cautelosa del modelo viene de <b>alertas</b> "
            "(calidad de datos, ROIC vs WACC, proyecto VPN/TIR o liquidez de FCFF)."
        )
    if not explicaciones:
        explicaciones.append("El modelo no activó vetos duros; la decisión refleja el balance de soportes y alertas.")

    # --- Lectura de mercado ---
    lineas_mkt = []
    if mkt.get("ok"):
        if mkt.get("precio") is not None:
            cur = mkt.get("currency") or ""
            lineas_mkt.append(f"Precio ~ <b>{mkt['precio']:,.2f} {cur}</b>")
        if mkt.get("market_cap") is not None:
            # escala legible
            mc = mkt["market_cap"]
            if mc > 1e12:
                lineas_mkt.append(f"Capitalización ~ <b>{mc/1e12:.2f} billones</b> (misma moneda Yahoo)")
            elif mc > 1e9:
                lineas_mkt.append(f"Capitalización ~ <b>{mc/1e9:.2f} mil millones</b>")
            else:
                lineas_mkt.append(f"Capitalización ~ <b>{mc:,.0f}</b>")
        # P/E, EV/EBITDA, precio objetivo y consenso ya están como señales del veredicto (no se repiten).
        # β y dividend yield solo se listan aquí cuando NO entraron como señal (umbrales del veredicto).
        if mkt.get("beta") is not None and mkt["beta"] < 1.5:
            lineas_mkt.append(f"β mercado ~ <b>{mkt['beta']:.2f}</b>")
        if mkt.get("div_yield") is not None and mkt["div_yield"] < 0.05:
            lineas_mkt.append(f"Dividend yield ~ <b>{mkt['div_yield']*100:.1f}%</b>")
    else:
        lineas_mkt.append(
            "Sin snapshot Yahoo usable en este momento. El contraste se basa solo en la lógica del modelo "
            "y en los parámetros cargados."
        )

    # --- Veredicto de inversión según el mercado ---
    veredicto_m = veredicto_inversion_mercado(
        nombre_empresa, mkt, upside_modelo_pct=upside_modelo_pct, motor=motor, procedencia=procedencia,
    )

    # --- Opción lógica (síntesis) ---
    hay_veto = len(vetos) > 0
    equity_neg = equity_base is not None and float(equity_base) <= 0
    mkt_vivo = mkt.get("ok") and (mkt.get("market_cap") or mkt.get("precio"))

    if hay_veto and equity_neg and mkt_vivo:
        sintesis = "DIVERGENCIA MODELO–MERCADO"
        sintesis_color = "#B45309"
        opcion = (
            "La opción lógica <b>no es interpretar el veto como orden de venta en bolsa</b>. "
            "El mercado asigna capitalización positiva a la empresa; el modelo está señalando "
            "<b>incoherencia interna del DCF/bridge</b> (datos de catálogo, NCI/deuda, FCFF o TV). "
            "Acción recomendada: recalibrar supuestos con EEFF y cotización actual; usar el veto como "
            "control de calidad del modelo, no como rating de la acción."
        )
        postura = "NEUTRAL / RECALIBRAR MODELO (no equivale a 'vender en mercado')"
    elif hay_veto and not mkt_vivo:
        sintesis = "VETO DE CALIDAD DEL MODELO SIN CONTRASTE DE MERCADO"
        sintesis_color = "#B45309"
        opcion = (
            "Hay veto del motor y no hay precio/capitalización de mercado para contrastar. "
            "El veto es un <b>control de calidad del modelo, no un rating de la acción</b>: "
            "la opción lógica es <b>recalibrar supuestos y cargar datos auditados</b> "
            "antes de sacar cualquier conclusión de inversión."
        )
        postura = "RECALIBRAR MODELO (el veto no es rating de la acción)"
    elif not hay_veto and mkt_vivo:
        # precio vs valor modelo si hay VPS
        sintesis = "MODELO Y MERCADO COMPARABLES"
        sintesis_color = "#059669"
        opcion = (
            "Sin vetos duros: el comité del modelo permite lectura condicionada. "
            "Contrasta múltiplos y precio de mercado con el equity del DCF; "
            "si el mercado cotiza claramente por encima del valor modelado, la opción lógica es "
            "<b>Hold / no perseguir precio</b>; si hay margen, <b>acumular con disciplina</b>."
        )
        postura = "CONDICIONADO A MARGEN DE SEGURIDAD DE MERCADO"
    else:
        sintesis = "LECTURA SOLO DE MODELO"
        sintesis_color = "#D97706"
        opcion = (
            "Decisión basada en reglas internas. Complementa siempre con precio, múltiplos y EEFF oficiales."
        )
        postura = decision

    # ROIC note
    roic_txt = ""
    if roic is not None and wacc is not None:
        if float(roic) < float(wacc):
            roic_txt = (
                f"<p style='margin:8px 0;color:#9A3412'>ROIC modelado ({roic*100:.1f}%) &lt; WACC ({wacc*100:.1f}%): "
                f"el capital del escenario no cubre su costo — alerta de creación de valor en el modelo, "
                f"no prueba de destrucción de valor histórica de la cotizada.</p>"
            )
        else:
            roic_txt = (
                f"<p style='margin:8px 0;color:#065F46'>ROIC modelado ({roic*100:.1f}%) ≥ WACC ({wacc*100:.1f}%): "
                f"soporte de creación de valor en el escenario.</p>"
            )

    calidad = (procedencia or {}).get("nivel_calidad") or "N/D"
    fuente_f = (procedencia or {}).get("fuente_financiera") or "N/D"

    exp_html = "".join(f"<li style='margin:6px 0'>{e}</li>" for e in explicaciones)
    mkt_html = "".join(f"<li>{x}</li>" for x in lineas_mkt)

    html = f"""
<div style="background:linear-gradient(135deg,#111827,#1A2336);border:2px solid #3B82F6;border-radius:14px;padding:18px 20px;margin:16px 0">
  <div style="font-size:12px;font-weight:700;color:#1E40AF;letter-spacing:.04em">
    MÓDULO IA · CONTRASTE MODELO vs MERCADO (reglas expertas · no orden de bolsa)
  </div>
  <h3 style="margin:8px 0 4px 0;color:#E8EEF7">{escape(str(nombre_empresa))}</h3>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 14px 0">
    <span style="background:{sintesis_color};color:#fff;padding:6px 12px;border-radius:8px;font-weight:700;font-size:13px">
      Síntesis: {sintesis}
    </span>
  </div>
{veredicto_m["html"]}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
    <div style="background:#1A2336;border-radius:10px;padding:12px;border:1px solid #243044">
      <div style="font-weight:700;color:#E8EEF7;margin-bottom:6px">Por qué el modelo decide así</div>
      <ul style="margin:0;padding-left:18px;color:#CBD5E1;font-size:13px;line-height:1.45">{exp_html}</ul>
      <p style="margin:8px 0 0 0;font-size:12px;color:#64748B">
        Calidad datos: <b>{escape(str(calidad))}</b> · {escape(str(fuente_f))}
      </p>
      {roic_txt}
    </div>
    <div style="background:#1A2336;border-radius:10px;padding:12px;border:1px solid #243044">
      <div style="font-weight:700;color:#E8EEF7;margin-bottom:6px">Datos de mercado (snapshot)</div>
      <ul style="margin:0;padding-left:18px;color:#CBD5E1;font-size:13px;line-height:1.45">{mkt_html}</ul>
      <p style="margin:8px 0 0 0;font-size:11px;color:#94A3B8">Fuente: Yahoo Finance al momento de la corrida (puede diferir de la BVC en retraso).</p>
    </div>
  </div>

  <div class="caja-oscura" style="background:#0F172A;color:#F8FAFC;border-radius:10px;padding:14px 16px;margin-top:12px">
    <div class="caja-oscura-titulo" style="font-size:12px;color:#93C5FD;font-weight:700">OPCIÓN LÓGICA DE INTERPRETACIÓN</div>
    <div class="caja-oscura-postura" style="font-size:15px;font-weight:700;margin:6px 0;color:#FDE68A">{escape(postura)}</div>
    <p style="margin:0;font-size:13px;line-height:1.5;color:#E2E8F0">{opcion}</p>
  </div>
  <p style="margin:10px 0 0 0;font-size:11px;color:#64748B">
    Este módulo no constituye asesoría de inversión ni sustituye EEFF auditados, research independiente ni límites de mandato.
  </p>
</div>
"""
    return {
        "html": html,
        "sintesis": sintesis,
        "postura": postura,
        "mercado": mkt,
        "veredicto_mercado": veredicto_m,
    }


def beta_apalancado(beta_u, de, t):
    return beta_u * (1 + (1 - t) * de)


def anclar_g_terminal(g, wacc, g_max_macro=0.05, margen_seguridad=0.01):
    """
    Disciplina profesional: g de largo plazo no puede acercarse al WACC
    ni superar un techo macro (p.ej. PIB nominal de largo plazo).
    """
    g = float(g)
    wacc = float(wacc)
    g_cap = min(float(g_max_macro), wacc - float(margen_seguridad))
    g_use = max(0.0, min(g, g_cap))
    return g_use, g_cap



def validar_inputs_valoracion(wacc, g, fcff_series=None, g_max_macro=0.05, acciones=None):
    """Validaciones de robustez antes de DCF / Generar todo.
    Retorna lista de mensajes (vacía = OK). No lanza salvo casos irrecuperables.
    """
    msgs = []
    try:
        w = float(wacc)
        g = float(g)
    except Exception:
        return ["WACC o g no numéricos"]
    if not np.isfinite(w) or w <= 0:
        msgs.append(f"WACC inválido ({w}). Debe ser > 0.")
    if not np.isfinite(g):
        msgs.append("g terminal no finito.")
    g_use, g_cap = anclar_g_terminal(g, w, g_max_macro=g_max_macro)
    if g >= w - 1e-6:
        msgs.append(f"g ({g*100:.2f}%) ≥ WACC ({w*100:.2f}%): Gordon no definido; se anclará a {g_use*100:.2f}%.")
    if g_use + 0.005 >= w:
        msgs.append(f"Margen WACC−g muy estrecho ({(w-g_use)*100:.2f} pp): valor terminal frágil.")
    if fcff_series is not None:
        try:
            arr = [float(x) for x in fcff_series]
            if not arr:
                msgs.append("Serie FCFF vacía.")
            elif not any(x > 0 for x in arr):
                msgs.append("Todos los FCFF ≤ 0: TV Gordon tenderá a 0.")
            elif not all(np.isfinite(x) for x in arr):
                msgs.append("FCFF contiene NaN/inf.")
        except Exception:
            msgs.append("FCFF no convertible a números.")
    if acciones is not None:
        try:
            if float(acciones) <= 0:
                msgs.append("Número de acciones ≤ 0: no se calculará VPS.")
        except Exception:
            msgs.append("Acciones no numéricas.")
    return msgs


def valoracion_dcf(
    fcff_series,
    wacc,
    g,
    deuda_neta=0,
    caja=0.0,
    nci=0.0,
    otros_claims=0.0,
    asociados=0.0,
    acciones=None,
    precio_mercado=None,
    exit_multiple=0.0,
    ebitda_salida=None,
    mid_year=True,
    g_max_macro=0.05,
    nopat_final=None,
    ronic_spread=None,
    deuda_es_bruta=False,
):
    """
    DCF profesional sobre FCFF → Enterprise Value → Equity bridge → por acción.

    Equity atribuible ≈ EV − deuda_neta − NCI − otros claims + asociados.
    Convención: `deuda_neta` = deuda financiera − caja operativa (ya neta).
    No se vuelve a sumar `caja` (evita doble conteo). Si se pasa deuda bruta, usar
    deuda_es_bruta=True para aplicar Equity = EV − D + caja − NCI − otros + asociados.
    Gordon es el caso base. El múltiplo de salida se informa como escenario independiente;
    no se promedian metodologías diferentes sin una ponderación justificada.
    """
    fcff_series = [float(x) for x in list(fcff_series)]
    n = len(fcff_series)
    wacc = float(wacc)
    if not np.isfinite(wacc) or wacc <= -1:
        raise ValueError("WACC inválido: debe ser finito y mayor que -100%.")
    if not np.isfinite(float(g)):
        raise ValueError("La tasa g terminal debe ser finita.")
    if not all(np.isfinite(x) for x in fcff_series):
        raise ValueError("La serie FCFF contiene valores no finitos.")
    g_use, g_cap = anclar_g_terminal(g, wacc, g_max_macro=g_max_macro)

    empty = {
        "EV": 0.0, "EV_Gordon": 0.0, "EV_Exit": None, "Equity_Value": -float(deuda_neta) - float(nci),  # deuda neta: no sumar caja
        "PV_FCFF": 0.0, "PV_TV": 0.0, "TV": 0.0, "TV_Gordon": 0.0, "TV_Exit": None,
        "WACC": wacc, "g_used": g_use, "g_cap": g_cap, "mid_year": mid_year,
        "bridge": {}, "value_per_share": None, "upside_pct": None,
    }
    if n == 0:
        return empty

    # Factores de descuento (fin de año o mitad de año)
    if mid_year:
        dfs = [(1 + wacc) ** -(i + 0.5) for i in range(n)]
        df_tv = (1 + wacc) ** -(n - 0.5)
    else:
        dfs = [(1 + wacc) ** -(i + 1) for i in range(n)]
        df_tv = (1 + wacc) ** -n

    pv_fcff = sum(f * d for f, d in zip(fcff_series, dfs))

    # Terminal Gordon: si el último FCFF ≤ 0, no perpetuar un flujo negativo
    fcff_tv = float(fcff_series[-1])
    nota_tv = None
    if fcff_tv <= 0:
        positivos = [f for f in fcff_series if f > 0]
        if positivos:
            fcff_tv = float(np.mean(positivos))
            nota_tv = (
                f"FCFF final del horizonte ≤ 0 ({fcff_series[-1]:,.1f}); "
                f"TV Gordon usa promedio de FCFF positivos ({fcff_tv:,.1f})."
            )
        else:
            fcff_tv = 0.0
            nota_tv = "Todos los FCFF del horizonte son ≤ 0; TV Gordon = 0."

    if wacc > g_use + 1e-6:
        tv_gordon = fcff_tv * (1 + g_use) / (wacc - g_use) if fcff_tv > 0 else 0.0
    else:
        raise ValueError("No se puede calcular el valor terminal: WACC debe ser mayor que g terminal.")
    tv_fcff_ultimo = tv_gordon   # diagnóstico: Gordon sobre el último FCFF (método anterior)

    # Valor terminal NORMALIZADO (valor-conductor, McKinsey): TV = NOPAT_{N+1}·(1 − g/RONIC)/(WACC − g).
    # Perpetuar el FCFF del último año arrastra el CAPEX de un ciclo de expansión (reinversión > 70 % del
    # NOPAT para crecer g %, es decir un retorno marginal < WACC) y subvalora de forma sistemática.
    tv_metodo = "Gordon sobre FCFF final"
    reinv_term = None
    ronic = None
    if nopat_final is not None:
        spread = RONIC_SPREAD if ronic_spread is None else float(ronic_spread)
        ronic = wacc + spread
        nopat_n1 = float(nopat_final) * (1 + g_use)
        if nopat_n1 > 0 and ronic > 0:
            reinv_term = min(max(g_use / ronic, 0.0), 0.95)
            tv_gordon = nopat_n1 * (1 - reinv_term) / (wacc - g_use)
            nota_tv = (nota_tv + " " if nota_tv else "") + "TV normalizado por valor-conductor."
        else:
            tv_gordon = 0.0
            reinv_term = 0.0
            nota_tv = "NOPAT final ≤ 0: TV = 0 (no se perpetúan pérdidas)."
        tv_metodo = "normalizado (valor-conductor)"
    pv_tv_gordon = tv_gordon * df_tv
    ev_gordon = pv_fcff + pv_tv_gordon

    # Terminal por múltiplo de salida
    tv_exit = None
    pv_tv_exit = None
    ev_exit = None
    if ebitda_salida is not None and float(exit_multiple) > 0:
        tv_exit = float(ebitda_salida) * float(exit_multiple)
        # Misma convención temporal que el TV Gordon (mid-year si aplica)
        pv_tv_exit = tv_exit * df_tv
        ev_exit = pv_fcff + pv_tv_exit

    # Caso base explícito: Gordon. Exit multiple queda separado para comparación.
    ev = ev_gordon
    tv = tv_gordon
    pv_tv = pv_tv_gordon

    deuda_neta = float(deuda_neta or 0)
    caja = float(caja or 0)
    nci = float(nci or 0)
    otros_claims = float(otros_claims or 0)
    asociados = float(asociados or 0)

    # Convención robusta: deuda_neta ya es neta de caja (Yahoo y catálogo).
    # Solo si deuda_es_bruta=True se suma la caja de nuevo.
    if deuda_es_bruta:
        equity = ev - deuda_neta + caja - nci - otros_claims + asociados
    else:
        equity = ev - deuda_neta - nci - otros_claims + asociados
    tv_pct_ev = (pv_tv / ev) if ev and ev > 0 else None
    mult_terminal = (tv / float(ebitda_salida)) if (ebitda_salida and float(ebitda_salida) > 0) else None
    bridge = {
        "Enterprise Value": ev,
        "(-) Deuda neta": -deuda_neta,
        "(-) Interés minoritario (NCI)": -nci,
        "(-) Otros claims": -otros_claims,
        "(+) Asociados / JV": asociados,
        "Equity atribuible": equity,
        "FCFF usado en TV" + (" (normalizado N+1)" if reinv_term is not None else " (último año)"): (
            float(nopat_final) * (1 + g_use) * (1 - reinv_term) if reinv_term is not None else fcff_tv),
        "Reinversión terminal (% NOPAT)": (reinv_term * 100 if reinv_term is not None else 0.0),
        "% del EV en valor terminal": (tv_pct_ev * 100 if tv_pct_ev is not None else 0.0),
        "g_terminal_usada": g_use,
        "WACC": wacc,
        "deuda_es_bruta": bool(deuda_es_bruta),
    }
    # Solo listar caja en el puente si se sumó (deuda bruta). Si deuda ya es neta, anotar.
    if deuda_es_bruta:
        # Insertar caja después de deuda neta en el dict ordenado
        bridge = {
            "Enterprise Value": ev,
            "(-) Deuda bruta": -deuda_neta,
            "(+) Caja y equivalentes": caja,
            "(-) Interés minoritario (NCI)": -nci,
            "(-) Otros claims": -otros_claims,
            "(+) Asociados / JV": asociados,
            "Equity atribuible": equity,
            "FCFF usado en TV" + (" (normalizado N+1)" if reinv_term is not None else " (último año)"): (
                float(nopat_final) * (1 + g_use) * (1 - reinv_term) if reinv_term is not None else fcff_tv),
            "Reinversión terminal (% NOPAT)": (reinv_term * 100 if reinv_term is not None else 0.0),
            "% del EV en valor terminal": (tv_pct_ev * 100 if tv_pct_ev is not None else 0.0),
            "g_terminal_usada": g_use,
            "WACC": wacc,
            "deuda_es_bruta": True,
        }
    else:
        bridge["Nota puente"] = "Deuda ya neta de caja; la caja no se suma otra vez."
    if nota_tv:
        bridge["Nota TV"] = nota_tv

    # VPS / upside (con recalibración de escala de acciones)
    _vu = calcular_vps_y_upside(
        equity,
        acciones,
        precio_mercado=precio_mercado,
        moneda_modelo=None,
        moneda_precio=None,
    )
    vps = _vu.get("value_per_share")
    upside = _vu.get("upside_pct")
    acciones_out = _vu.get("acciones") if _vu.get("acciones") is not None else acciones
    if _vu.get("nota_vps"):
        bridge["Nota VPS"] = _vu["nota_vps"]

    return {
        "EV": ev,
        "EV_Gordon": ev_gordon,
        "EV_Exit": ev_exit,
        "Equity_Value": equity,
        "PV_FCFF": pv_fcff,
        "PV_TV": pv_tv,
        "TV": tv,
        "TV_Gordon": tv_gordon,
        "TV_FCFF_ultimo": tv_fcff_ultimo,
        "tv_metodo": tv_metodo,
        "reinversion_terminal": reinv_term,
        "ronic": ronic,
        "tv_pct_ev": tv_pct_ev,
        "mult_terminal": mult_terminal,
        "TV_Exit": tv_exit,
        "WACC": wacc,
        "g_used": g_use,
        "g_cap": g_cap,
        "mid_year": mid_year,
        "bridge": bridge,
        "value_per_share": vps,
        "upside_pct": upside,
        "acciones": acciones_out,
        "precio_mercado": precio_mercado,
        "nota_vps": _vu.get("nota_vps"),
    }


def formatear_bridge_html(val, moneda_modelo=None, moneda_precio=None, nombre_empresa=None):
    """HTML del puente EV → Equity y valor por acción (moneda del emisor, no COP fijo)."""
    b = val.get("bridge") or {}
    def _celda(v):
        return f"{v:,.1f}" if isinstance(v, (int, float)) else str(v)  # 'Nota TV' es texto

    mon_m = (moneda_modelo or (moneda_empresa(nombre_empresa) if nombre_empresa else None) or "COP").upper()
    mon_p = (moneda_precio or mon_m).upper()
    unidad = etiqueta_unidad(mon_m)

    rows = "".join(
        f"<tr><td style='padding:6px 10px;color:#E8EEF7;border-bottom:1px solid #E2E8F0'>{k}</td>"
        f"<td style='padding:6px 10px;text-align:left;color:#E8EEF7;border-bottom:1px solid #E2E8F0'>{_celda(v)}</td></tr>"
        for k, v in b.items()
    )
    vps = val.get("value_per_share")
    upside = val.get("upside_pct")
    precio = val.get("precio_mercado")
    vps_txt = f"{vps:,.0f} {mon_m}" if vps is not None else "N/D (faltan acciones)"
    if upside is not None and precio is not None:
        if mon_m != mon_p:
            up_txt = (
                f"<span style='color:#D97706;font-weight:700'>N/D comparable</span> "
                f"(modelo en {mon_m}, precio en {mon_p}; sin FX no se calcula upside). "
                f"Precio de mercado: {precio:,.2f} {mon_p}"
            )
        else:
            color = "#059669" if upside >= 0 else "#DC2626"
            up_txt = (
                f"<span style='color:{color};font-weight:700'>{upside:+.1f}%</span> "
                f"vs precio {precio:,.2f} {mon_p}"
            )
    else:
        up_txt = "N/D (sin precio de mercado o sin acciones)"
    tv_line = (
        f"TV ({val.get('tv_metodo', 'Gordon')}) {val.get('TV_Gordon', 0):,.0f}"
        + (f" · TV Exit {val['TV_Exit']:,.0f}" if val.get("TV_Exit") is not None else " · TV Exit N/D")
        + f" · EV ref. {val.get('EV', 0):,.0f} (caso base = DCF con valor terminal normalizado; el múltiplo de salida es solo referencia)"
    )
    mid = "mitad de año" if val.get("mid_year") else "fin de año"
    return f"""
<div class="section-card">
<b>Puente profesional EV → Equity</b>
<p style="color:#CBD5E1;margin:6px 0 10px 0">Unidad del modelo: <b>{unidad}</b> · Convención de descuento: <b>{mid}</b>.
g usado {val.get('g_used', 0)*100:.2f}% (techo {val.get('g_cap', 0)*100:.2f}%). {tv_line}</p>
<table style="width:100%;border-collapse:collapse;font-size:13px">{rows}</table>
<p style="margin:12px 0 0 0;color:#E8EEF7"><b>Valor por acción (modelo):</b> {vps_txt}<br>
<b>Upside / downside vs mercado:</b> {up_txt}</p>
</div>
"""



def params_bridge_desde_ui(deuda_neta, caja, nci, otros_claims, asociados, acciones, exit_multiple, deuda_es_bruta=False):
    """Bridge EV→Equity. Por defecto deuda_neta ya es neta de caja (no sumar caja otra vez)."""
    return {
        "deuda_neta": float(deuda_neta or 0),
        "caja": float(caja or 0),
        "nci": float(nci or 0),
        "otros_claims": float(otros_claims or 0),
        "asociados": float(asociados or 0),
        "acciones": float(acciones) if acciones not in (None, "", 0, "0") else None,
        "exit_multiple": float(exit_multiple) if exit_multiple not in (None, "") else 0.0,
        "deuda_es_bruta": bool(deuda_es_bruta),
    }


def valorar_con_bridge(fcff_series, wacc, g, bridge_params, ebitda_salida=None, precio_mercado=None, mid_year=True, g_max_macro=0.05, nopat_final=None):
    bp = bridge_params or {}
    return valoracion_dcf(
        fcff_series, wacc, g,
        deuda_neta=bp.get("deuda_neta", 0),
        caja=bp.get("caja", 0),
        nci=bp.get("nci", 0),
        otros_claims=bp.get("otros_claims", 0),
        asociados=bp.get("asociados", 0),
        acciones=bp.get("acciones"),
        precio_mercado=precio_mercado,
        exit_multiple=bp.get("exit_multiple", 0.0),
        ebitda_salida=ebitda_salida,
        mid_year=mid_year,
        g_max_macro=g_max_macro,
        nopat_final=nopat_final,
        deuda_es_bruta=bool(bp.get("deuda_es_bruta", False)),
    )


def _escalar_fcff(fcff, fac):
    """Escala escenarios sin perder el sentido: flujos positivos × fac; negativos × (2 − fac).
    (Con fac=0.75 un FCFF de −100 pasa a −125; antes pasaba a −75, es decir, 'mejoraba'.)"""
    f = np.asarray(fcff, dtype=float)
    return np.where(f >= 0, f * fac, f * (2.0 - fac))


def _nopat_final(df, fac=1.0):
    """NOPAT del último año (con el mismo escalamiento sensible al signo de los escenarios)."""
    return float(_escalar_fcff([float(df["NOPAT"].iloc[-1])], fac)[0])


def aplicar_shocks_drivers_proyeccion(df_proj, tax=0.35, shock=None):
    """
    Escenario por drivers (no solo escalado de FCFF).
    shock keys (multiplicadores, 1.0 = base):
      g_ingresos, margen_ebitda, capex_factor, nwc_factor
    Recalcula EBIT, NOPAT, FCFF por identidad contable.
    """
    if df_proj is None or not hasattr(df_proj, "copy"):
        return df_proj
    shock = shock or {}
    d = df_proj.copy()
    g_fac = float(shock.get("g_ingresos", 1.0) or 1.0)
    m_fac = float(shock.get("margen_ebitda", 1.0) or 1.0)
    cx_fac = float(shock.get("capex_factor", 1.0) or 1.0)
    nwc_fac = float(shock.get("nwc_factor", 1.0) or 1.0)

    if "Ingresos" in d.columns and abs(g_fac - 1.0) > 1e-12:
        ing0 = float(d["Ingresos"].iloc[0])
        # Reescala la senda de ingresos: primer año * g_fac sobre el crecimiento implícito
        ings = [float(x) for x in d["Ingresos"].tolist()]
        if len(ings) >= 1 and ings[0] != 0:
            # aplicar factor de nivel al primer año y preservar ratios de crecimiento relativos
            base_ratios = ings[0] / g_fac if g_fac else ings[0]
            # interpretación: g_fac < 1 → ingresos más bajos en todo el horizonte
            ings = [x * g_fac for x in ings]
            d["Ingresos"] = ings

    if "EBITDA" in d.columns and "Ingresos" in d.columns:
        # margen * m_fac, acotado
        for i in range(len(d)):
            ing = float(d["Ingresos"].iloc[i])
            ebitda_old = float(d["EBITDA"].iloc[i]) if "EBITDA" in d.columns else 0.0
            margen = (ebitda_old / ing) if ing else 0.0
            margen = float(np.clip(margen * m_fac, -0.5, 0.85))
            d.iloc[i, d.columns.get_loc("EBITDA")] = ing * margen

    if "CAPEX" in d.columns:
        d["CAPEX"] = pd.to_numeric(d["CAPEX"], errors="coerce").fillna(0.0) * cx_fac

    if "Delta_NWC" in d.columns:
        d["Delta_NWC"] = pd.to_numeric(d["Delta_NWC"], errors="coerce").fillna(0.0) * nwc_fac

    # Reconstruir EBIT / Dep / NOPAT / FCFF
    if "EBITDA" in d.columns and "Depreciacion" in d.columns:
        dep = pd.to_numeric(d["Depreciacion"], errors="coerce").fillna(0.0)
        d["EBIT"] = pd.to_numeric(d["EBITDA"], errors="coerce").fillna(0.0) - dep
    elif "EBITDA" in d.columns:
        d["EBIT"] = pd.to_numeric(d["EBITDA"], errors="coerce").fillna(0.0)

    if "EBIT" in d.columns:
        ebit = pd.to_numeric(d["EBIT"], errors="coerce").fillna(0.0)
        d["NOPAT"] = ebit - float(tax) * np.maximum(ebit, 0.0)

    if all(c in d.columns for c in ("NOPAT", "Depreciacion", "CAPEX", "Delta_NWC")):
        d["FCFF"] = (
            pd.to_numeric(d["NOPAT"], errors="coerce").fillna(0.0)
            + pd.to_numeric(d["Depreciacion"], errors="coerce").fillna(0.0)
            - pd.to_numeric(d["CAPEX"], errors="coerce").fillna(0.0)
            - pd.to_numeric(d["Delta_NWC"], errors="coerce").fillna(0.0)
        )
    return d


def reconciliar_deuda_bridge(deuda_neta=0, caja=0, deuda_bruta=None, deuda_es_bruta=False):
    """
    Tabla de reconciliación del puente EV→Equity.
    Convención preferida: deuda_neta = deuda financiera − caja operativa (no sumar caja otra vez).
    Si deuda_es_bruta=True, el input `deuda_neta` se interpreta como bruta y se resta caja.
    """
    cj = float(caja or 0)
    if deuda_bruta is not None:
        db = float(deuda_bruta)
        dn_puente = db - cj
        modo = "Deuda bruta explícita − caja"
    elif deuda_es_bruta:
        db = float(deuda_neta or 0)
        dn_puente = db - cj
        modo = "Input tratado como deuda bruta − caja"
    else:
        dn_puente = float(deuda_neta or 0)
        db = dn_puente + cj
        modo = "Deuda ya neta (no se suma caja otra vez)"
    filas = [
        {"Concepto": "Deuda financiera bruta", "Valor": round(db, 2)},
        {"Concepto": "(-) Caja / equivalentes", "Valor": round(cj, 2)},
        {"Concepto": "(=) Deuda neta en el puente", "Valor": round(dn_puente, 2)},
        {"Concepto": "Modo", "Valor": modo},
    ]
    import pandas as _pd
    df = _pd.DataFrame(filas)
    return {
        "deuda_bruta": db,
        "caja": cj,
        "deuda_neta_puente": dn_puente,
        "deuda_es_bruta": bool(deuda_es_bruta),
        "df": df,
    }


def self_test_valuation_core():
    """
    Pruebas unitarias mínimas del núcleo (WACC, ancla g, DCF simple).
    Retorna lista de (nombre, ok, detalle).
    """
    results = []
    try:
        w, we, wd = calcular_wacc(1.0, 0.08, 0.12, 0.25)
        # we=0.5, wd=0.5 → 0.5*0.12 + 0.5*0.08*0.75 = 0.06 + 0.03 = 0.09
        ok = abs(w - 0.09) < 1e-9 and abs(we - 0.5) < 1e-12
        results.append(("WACC D/E=1, kd=8%, ke=12%, t=25%", ok, f"wacc={w:.6f} (esp. 0.09)"))
    except Exception as e:
        results.append(("WACC básico", False, str(e)))
    try:
        g_use, g_cap = anclar_g_terminal(0.06, 0.08, g_max_macro=0.04, margen_seguridad=0.01)
        ok = g_use <= 0.04 + 1e-12 and g_use < 0.08 - 0.01 + 1e-9
        results.append(("anclar_g_terminal(0.06, wacc=0.08, techo=0.04)", ok, f"g_use={g_use}, g_cap={g_cap}"))
    except Exception as e:
        results.append(("anclar_g_terminal", False, str(e)))
    try:
        val = valoracion_dcf(
            [100.0, 100.0, 100.0],
            wacc=0.10,
            g=0.03,
            deuda_neta=0,
            mid_year=False,
            g_max_macro=0.05,
            nopat_final=None,
        )
        # TV = 100*1.03/(0.10-0.03) = 1471.428...
        # PV factors end-year: 1/1.1, 1/1.1^2, 1/1.1^3; TV disc at n=3
        tv = 100.0 * 1.03 / 0.07
        pv_fcff = 100/1.1 + 100/1.1**2 + 100/1.1**3
        pv_tv = tv / 1.1**3
        ev_esp = pv_fcff + pv_tv
        ok = abs(val["EV"] - ev_esp) < 0.05 and abs(val["TV_Gordon"] - tv) < 0.05
        results.append(("DCF Gordon 3 años mid_year=False", ok, f"EV={val['EV']:.2f} esp={ev_esp:.2f}"))
    except Exception as e:
        results.append(("DCF Gordon simple", False, str(e)))
    try:
        rec = reconciliar_deuda_bridge(deuda_neta=100, caja=20, deuda_es_bruta=False)
        ok = abs(rec["deuda_neta_puente"] - 100) < 1e-9
        results.append(("Reconciliación deuda neta", ok, str(rec["deuda_neta_puente"])))
    except Exception as e:
        results.append(("Reconciliación deuda", False, str(e)))
    return results


def metricas_valor_firma(fcff_series, capital_invertido, val):
    """Métricas a nivel de FIRMA, consistentes con el DCF:
      MVA = EV − capital invertido ;  TIR implícita = TIR de [−K, FCFF_1..FCFF_N + TV].

    La TIR implícita de firma suele situarse cerca del WACC/ROIC cuando K y TV
    están bien calibrados. Solo se anula si el solver no encuentra raíz finita.
    (Antes se descartaba cualquier TIR > 80%, lo que ocultaba resultados válidos.)
    """
    K = float(capital_invertido or 0)
    if K <= 0:
        return None, None
    f = [float(x) for x in list(fcff_series)]
    if not f:
        return float(val["EV"]) - K, None
    tv = float(val.get("TV") or 0)
    # Último flujo incluye valor terminal (Gordon / exit) del DCF
    cfs = [-K] + list(f[:-1]) + [float(f[-1]) + tv]
    mva = float(val["EV"]) - K
    tir = calcular_irr(cfs)
    if tir is not None and (isinstance(tir, float) and (not np.isfinite(tir))):
        tir = None
    # Guardrail solo para explosiones numéricas (> 500 % anual no es interpretable)
    if tir is not None and abs(float(tir)) > 5.0:
        tir = None
    return mva, tir


def calcular_roic(nopat, capital):
    if capital is None or not np.isfinite(float(capital)) or float(capital) <= 0:
        raise ValueError("No se puede calcular el ROIC: el capital invertido debe ser mayor que 0 (antes se asumía 8%).")
    return nopat / capital


def tasa_reinversion(capex, dep, dnwc, nopat):
    return (capex - dep + dnwc) / nopat if nopat > 0 else 0.40


def calcular_irr(cashflows):
    """TIR (IRR) del vector de flujos. t=0 es el primer elemento (inversión).

    Robusto frente a:
      - ausencia de numpy_financial
      - brackets donde NPV no cambia de signo
      - flujos casi nulos / un solo signo (sin raíz real útil)
    Devuelve float o np.nan (nunca lanza).
    """
    try:
        cfs = [float(x) for x in list(cashflows)]
    except Exception:
        return np.nan
    if len(cfs) < 2:
        return np.nan
    if not any(cf < 0 for cf in cfs) or not any(cf > 0 for cf in cfs):
        # Sin cambio de signo no hay TIR económica convencional
        return np.nan

    # Preferir numpy_financial si está disponible
    if HAS_NPF:
        try:
            r = float(npf.irr(cfs))
            if np.isfinite(r):
                return r
        except Exception:
            pass

    def npv_func(r):
        # Evitar overflow en (1+r)**i con r extremo
        total = 0.0
        for i, cf in enumerate(cfs):
            den = (1.0 + r) ** i
            if den == 0 or not np.isfinite(den):
                return np.inf if cf >= 0 else -np.inf
            total += cf / den
        return total

    # Varios brackets: TIR de proyecto puede ser alta; también cubrir casos negativos
    brackets = [
        (-0.99, 0.0),
        (0.0, 0.5),
        (0.5, 1.5),
        (1.5, 5.0),
        (5.0, 20.0),
        (-0.5, 2.0),
        (-0.99, 10.0),
    ]
    for lo, hi in brackets:
        try:
            vlo, vhi = npv_func(lo), npv_func(hi)
            if not (np.isfinite(vlo) and np.isfinite(vhi)):
                continue
            if vlo == 0:
                return float(lo)
            if vhi == 0:
                return float(hi)
            if vlo * vhi < 0:
                return float(brentq(npv_func, lo, hi, maxiter=200))
        except Exception:
            continue
    return np.nan


def calcular_npv(rate, cashflows):
    """VPN con el primer flujo en t=0 (inversión inicial sin descontar un periodo extra)."""
    try:
        # Implementación explícita (compatible con convención t=0)
        return float(sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows)))
    except Exception:
        return np.nan


def metricas_proyecto_robustas(fcff_series, wacc, inversion_inicial=0.0, capital_invertido=0.0):
    """VPN / TIR / payback de proyecto con guardrails de unidades.

    Problema frecuente: `inversion_inicial` del catálogo es ilustrativa y mucho menor
    que el FCFF anual de toda la firma → TIR artificialmente alta (p. ej. > 80–100 %).

    Reglas:
      1) Si la inversión es pequeña frente al FCFF medio o al capital invertido,
         se eleva a un piso económico (no se inventa un proyecto irreal).
      2) La TIR se reporta siempre que el solver encuentre raíz finita.
      3) Solo se anula si |TIR| > 500 % (explosión numérica) o no hay cambio de signo.
      4) Si la TIR supera 100 %, se adjunta nota de interpretación (no se oculta el número).
    """
    f = [float(x) for x in list(fcff_series if fcff_series is not None else [])]
    n = max(len(f), 1)
    inv_in = abs(float(inversion_inicial or 0))
    mean_abs = float(np.mean([abs(x) for x in f])) if f else 0.0
    sum_abs = float(np.sum([abs(x) for x in f])) if f else 0.0
    cap = abs(float(capital_invertido or 0))

    inv = inv_in
    nota = None

    # Piso de inversión: evita TIR absurda cuando el catálogo pone un desembolso
    # ilustrativo (p. ej. 5.000) frente a FCFF de firma (~3–5 mil M/año) o K enorme.
    # Criterio: inv debe ser al menos ~1 año de |FCFF| medio, o 8 % del capital,
    # o 20 % de la suma de |FCFF| del horizonte (lo que sea mayor y > inv_in).
    if mean_abs > 0 or cap > 0:
        piso_fcff = 1.0 * mean_abs if mean_abs > 0 else 0.0
        piso_cap = 0.08 * cap if cap > 0 else 0.0
        piso_sum = 0.20 * sum_abs if sum_abs > 0 else 0.0
        piso = max(piso_fcff, piso_cap, piso_sum)
        # No aplicar piso si el usuario ya puso una inversión >= 40 % del FCFF medio
        # (proyecto acotado realista) y además >= 3 % del capital.
        usuario_ok = (
            inv_in > 0
            and (mean_abs <= 0 or inv_in >= 0.40 * mean_abs)
            and (cap <= 0 or inv_in >= 0.03 * cap)
        )
        if not usuario_ok and piso > inv_in:
            inv = piso
            nota = (
                f"Inversión inicial del catálogo ({inv_in:,.1f}) es baja frente al FCFF "
                f"medio ({mean_abs:,.1f}) / capital ({cap:,.1f}); se usa piso {inv:,.1f} "
                f"para que VPN/TIR del proyecto sean interpretables (no es CAPEX real auditado)."
            )

    cashflows = [-inv] + f
    vpn = calcular_npv(wacc, cashflows)
    tir = calcular_irr(cashflows)

    # Invalidar solo NaN / no finito / explosión (> 500 % anual)
    if tir is not None and isinstance(tir, float):
        if (not np.isfinite(tir)) or abs(tir) > 5.0:
            tir = None
            if nota is None:
                nota = (
                    "TIR no reportada: no hay raíz económica estable "
                    "(revisa signos de FCFF e inversión inicial)."
                )
            else:
                nota += " TIR omitida por falta de raíz estable o magnitud > 500 %."
        elif abs(tir) > 1.0:
            # TIR > 100 %: se muestra, con advertencia de calibración
            extra = (
                f" TIR elevada ({tir*100:.1f} %): suele indicar inversión aún pequeña "
                f"respecto a los FCFF del horizonte o un perfil muy front-loaded. "
                f"Interpreta junto al VPN y al payback; no es una rentabilidad de mercado."
            )
            nota = (nota or "") + extra

    tir_str = f"{tir*100:.2f}%" if tir is not None else "N/D"
    payback = None
    acum = -inv
    for i_pb, fcff in enumerate(f):
        prev = acum
        acum += fcff
        if acum >= 0 and fcff != 0:
            payback = i_pb + (abs(prev) / fcff if fcff else 0)
            break
    payback_str = f"{payback:.1f} años" if payback is not None else "N/D"

    return {
        "vpn": float(vpn) if vpn == vpn else float("nan"),
        "tir": tir,
        "tir_str": tir_str,
        "payback": payback,
        "payback_str": payback_str,
        "inversion_usada": inv,
        "nota": nota,
        "cashflows": cashflows,
    }





# =============================================================================
# PESTAÑAS
# =============================================================================
def _sanear_historico_tab1(df_hist):
    """Limpieza de integridad para proyección (comité datos).

    1) Índice anual entero ordenado.
    2) Elimina años sin ingresos materiales o ejercicio calendario en curso.
    3) Marca (no borra) outliers de FCFF vía Hampel/MAD para gobernanza.
    4) Exige ≥3 observaciones útiles.
    """
    if df_hist is None or df_hist.empty:
        return df_hist, "Histórico vacío."
    df = df_hist.copy()
    df.index = df.index.map(lambda x: int(float(x)))
    df = df.sort_index()
    if "Ingresos" not in df.columns:
        return df, "Sin columna Ingresos."
    antes = list(df.index.astype(int))
    mask = df["Ingresos"].apply(lambda x: pd.notna(x) and abs(float(x)) > 1e-6)
    df = df.loc[mask]
    anio_actual = datetime.now().year
    df = df.loc[df.index < anio_actual]
    omitidos = [y for y in antes if y not in set(df.index.astype(int))]
    notas = []
    if omitidos:
        notas.append(f"Años omitidos (ingresos ~0 o ejercicio en curso): {omitidos}.")
    # Señales de atípicos en FCFF (informativo; no altera la serie histórica mostrada)
    if "FCFF" in df.columns and len(df) >= 4:
        try:
            s = pd.to_numeric(df["FCFF"], errors="coerce").dropna()
            med = float(s.median())
            mad = float((s - med).abs().median())
            if mad > 1e-12:
                z = (s - med).abs() / (1.4826 * mad)
                outs = [int(i) for i in z.index[z > 3.5]]
                if outs:
                    notas.append(f"Posibles atípicos FCFF (Hampel z>3,5): años {outs} — revisar CAPEX/NWC.")
        except Exception:
            pass
    # Coherencia contable suave: EBIT ≤ EBITDA cuando ambos existen
    if "EBIT" in df.columns and "EBITDA" in df.columns:
        bad = df.index[
            pd.to_numeric(df["EBIT"], errors="coerce") > pd.to_numeric(df["EBITDA"], errors="coerce") + 1e-6
        ].tolist()
        if bad:
            notas.append(f"Inconsistencia EBIT>EBITDA en {bad} — validar EEFF.")
    # Salto de unidades (p. ej. millones vs miles de millones): Δ ingresos > 300%
    if "Ingresos" in df.columns and len(df) >= 2:
        try:
            ing = pd.to_numeric(df["Ingresos"], errors="coerce")
            pct = ing.pct_change().abs()
            jumps = [int(ix) for ix, v in pct.items() if pd.notna(v) and v > 3.0]
            if jumps:
                notas.append(
                    f"Posible salto de unidades en Ingresos (Δ>300%) años {jumps} — "
                    "revisar si se mezclaron escalas (miles vs miles de millones)."
                )
        except Exception:
            pass
    # FCFF identidad suave si hay componentes
    need = {"NOPAT", "Depreciacion", "CAPEX", "Delta_NWC", "FCFF"}
    if need.issubset(set(df.columns)):
        try:
            id_fcff = (
                pd.to_numeric(df["NOPAT"], errors="coerce")
                + pd.to_numeric(df["Depreciacion"], errors="coerce")
                - pd.to_numeric(df["CAPEX"], errors="coerce")
                - pd.to_numeric(df["Delta_NWC"], errors="coerce")
            )
            err = (pd.to_numeric(df["FCFF"], errors="coerce") - id_fcff).abs()
            scale = pd.to_numeric(df["Ingresos"], errors="coerce").abs().replace(0, np.nan)
            rel = err / scale
            bad_id = [int(ix) for ix, v in rel.items() if pd.notna(v) and v > 0.15]
            if bad_id:
                notas.append(
                    f"FCFF no cuadra con NOPAT+D&A−CAPEX−ΔNWC (>15% ingresos) en {bad_id}."
                )
        except Exception:
            pass
    if len(df) < 3:
        raise ValueError(
            f"Tras limpiar años en cero quedan {len(df)} observaciones (mínimo 3). "
            f"Omitidos: {omitidos}. Carga un Excel/CSV o elige otra empresa del catálogo."
        )
    nota = (" " + " ".join(notas)) if notas else ""
    return df, nota



def _series_driver_desde_hist(df_hist, clave):
    """Serie de driver usada en proyección robusta (misma definición que proyectar_por_drivers)."""
    ing = df_hist["Ingresos"].astype(float)
    if clave == "crecimiento":
        return ing.pct_change()
    if clave == "margen EBITDA":
        return df_hist["EBITDA"].astype(float) / ing.replace(0, np.nan)
    if clave in ("margen D&A", "margen DA", "margen da"):
        ebitda = df_hist["EBITDA"].astype(float)
        ebit = df_hist["EBIT"].astype(float)
        return (ebitda - ebit) / ing.replace(0, np.nan)
    if clave == "CAPEX":
        return df_hist["CAPEX"].astype(float) / ing.replace(0, np.nan)
    if clave == "NWC":
        return df_hist["NWC"].astype(float) / ing.replace(0, np.nan)
    return None


def detectar_atipicos_drivers(df_hist, k=3.5):
    """Detecta atípicos en drivers clave sobre cualquier histórico (catálogo, Yahoo o Excel).

    Devuelve dict clave → {serie_orig, serie_norm, mask, anios}.
    """
    if df_hist is None or getattr(df_hist, "empty", True):
        return {}
    df = df_hist.copy()
    if "Ingresos" not in df.columns:
        return {}
    claves_orden = ["crecimiento", "margen EBITDA", "margen D&A", "CAPEX", "NWC"]
    out = {}
    for clave in claves_orden:
        serie = _series_driver_desde_hist(df, clave)
        if serie is None:
            continue
        s = pd.Series(serie, dtype=float).replace([np.inf, -np.inf], np.nan)
        # mínimo 4 puntos finitos para Hampel
        if s.notna().sum() < 4:
            continue
        s_n, mask = normalizar_atipicos(s, k=k, reemplazo="winsor", piso_rel=0.15, piso_abs=0.015)
        anios = [int(ix) for ix, flag in mask.items() if flag]
        if anios:
            out[clave] = {
                "serie_orig": s,
                "serie_norm": s_n,
                "mask": mask,
                "anios": anios,
            }
    return out


def reporte_normalizacion_atipicos(df_hist, meta=None):
    """Nota HTML + figura original vs normalizada para cualquier emisor.

    No depende del catálogo: funciona con Yahoo, Excel y empresas de sesión.
    Si meta trae atipicos_normalizados (método drivers), se unifica con el escaneo directo.
    """
    if df_hist is None or getattr(df_hist, "empty", True):
        return "", None

    detectados = detectar_atipicos_drivers(df_hist)
    # Unir claves solo-meta (por si el driver se calculó con otra ventana)
    meta_atip = (meta or {}).get("atipicos_normalizados") or {}
    for clave, anios_meta in meta_atip.items():
        if not anios_meta:
            continue
        if clave in detectados:
            continue
        serie = _series_driver_desde_hist(df_hist, clave)
        if serie is None:
            continue
        s = pd.Series(serie, dtype=float).replace([np.inf, -np.inf], np.nan)
        s_n, mask = normalizar_atipicos(s, k=3.5, reemplazo="winsor", piso_rel=0.15, piso_abs=0.015)
        anios = [int(ix) for ix, flag in mask.items() if flag] or list(anios_meta)
        if anios:
            detectados[clave] = {
                "serie_orig": s, "serie_norm": s_n, "mask": mask, "anios": anios,
            }

    if not detectados:
        return "", None

    METODO = "Hampel (mediana ± 3,5·σ_MAD) + winsorización"
    MOTIVO = (
        "Un valor extremo en un driver (crecimiento, margen, CAPEX/ingresos, NWC) distorsiona la mediana "
        "y el FCFF proyectado. Se detecta con filtro de Hampel y se recorta al límite (winsor) para conservar "
        "el año sin dejar que el atípico domine el estimador. Aplica a catálogo, tickers Yahoo y Excel propios."
    )

    n = len(detectados)
    fig, axes = plt.subplots(n, 2, figsize=(10.5, max(2.8, 2.6 * n)), squeeze=False)
    detalle_items = []

    for i, (clave, info) in enumerate(detectados.items()):
        s = info["serie_orig"]
        s_n = info["serie_norm"]
        mask = info["mask"]
        anios_at = info["anios"]
        detalle_items.append(
            f"<li><b>{clave}</b>: atípicos en {anios_at} → winsor al límite Hampel</li>"
        )

        x = list(s.index.astype(int)) if hasattr(s.index, "astype") else list(range(len(s)))
        y0 = s.to_numpy(dtype=float)
        y1 = s_n.to_numpy(dtype=float)
        msk = mask.to_numpy() if hasattr(mask, "to_numpy") else np.asarray(mask)

        ax0, ax1 = axes[i, 0], axes[i, 1]
        ax0.plot(x, y0, "o-", color=COLOR_PRIMARY, lw=2, ms=6, label="Original")
        if msk.any():
            ax0.scatter(
                np.array(x)[msk], y0[msk], s=70, facecolors="none",
                edgecolors=COLOR_DANGER, linewidths=2, zorder=5, label="Atípico",
            )
        ax0.set_title(f"{clave} · original", fontsize=10)
        ax0.axhline(0, color="#94A3B8", ls=":", lw=1)
        ax0.legend(loc="best", fontsize=7)
        ax0.spines["top"].set_visible(False)
        ax0.spines["right"].set_visible(False)

        ax1.plot(x, y1, "s-", color=COLOR_ACCENT, lw=2, ms=6, label="Normalizada")
        ax1.plot(x, y0, ":", color="#94A3B8", lw=1.2, alpha=0.7, label="Original (ref.)")
        if msk.any():
            ax1.scatter(np.array(x)[msk], y1[msk], s=55, color=COLOR_SUCCESS, zorder=5, label="Ajustado")
        ax1.set_title(f"{clave} · tras Hampel/winsor", fontsize=10)
        ax1.axhline(0, color="#94A3B8", ls=":", lw=1)
        ax1.legend(loc="best", fontsize=7)
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

    fig.suptitle(
        "Comparación de drivers: original vs normalizado (cualquier emisor)",
        fontsize=12, fontweight="600", y=1.01,
    )
    fig.tight_layout()

    origen = (meta or {}).get("metodo") or "proyección"
    nota = f"""
<div class="result-note" style="border-left-color:#0F766E">
  <b>Normalización de atípicos aplicada</b> · contexto: {origen}<br>
  <b>Motivo:</b> {MOTIVO}<br>
  <b>Método:</b> {METODO}. Si MAD≈0 se usa respaldo Tukey (1,5·IQR).<br>
  <b>Series tratadas:</b>
  <ul style="margin:6px 0 0 1rem;padding:0">{''.join(detalle_items)}</ul>
  El histórico en tablas se conserva; la normalización actúa sobre los <b>drivers</b> que alimentan la proyección FCFF
  (válido para empresas del catálogo, descargadas por ticker y cargadas por Excel).
</div>
"""
    return nota, fig





# --- Glosario didáctico (consultas tipo "¿qué es…?") ---
GLOSARIO_FINANCIERO = {
    "ebitda": (
        "EBITDA",
        "Utilidad antes de intereses, impuestos, depreciación y amortización. "
        "Mide el resultado operativo del negocio sin el efecto de la estructura de capital, "
        "impuestos ni el desgaste contable de activos. Se usa mucho para comparar empresas y en múltiplos (EV/EBITDA)."
    ),
    "ebit": (
        "EBIT",
        "Utilidad operativa (antes de intereses e impuestos). Es el EBITDA menos depreciación y amortización. "
        "Refleja la utilidad del negocio después de reconocer el desgaste de activos."
    ),
    "fcff": (
        "FCFF (Free Cash Flow to Firm)",
        "Flujo de caja libre para la firma: dinero que queda después de operar e invertir, disponible para "
        "deuda y accionistas. Fórmula usual: NOPAT + depreciación − CAPEX − ΔNWC. Es la base del DCF."
    ),
    "nopat": (
        "NOPAT",
        "Utilidad operativa después de impuestos teóricos: EBIT × (1 − tasa impositiva). "
        "Es el beneficio operativo como si no hubiera deuda (sin el escudo fiscal de intereses)."
    ),
    "wacc": (
        "WACC",
        "Costo promedio ponderado de capital. Tasa de descuento que mezcla el costo del equity (Ke) y "
        "el costo de la deuda después de impuestos, según el peso de cada fuente. Se usa para descontar el FCFF."
    ),
    "capm": (
        "CAPM",
        "Modelo de valoración de activos de capital. Estima el costo del equity: Ke = rf + β × ERP (+ CRP país). "
        "rf es la tasa libre de riesgo, β la sensibilidad al mercado y ERP la prima por riesgo accionario."
    ),
    "beta": (
        "Beta (β)",
        "Mide cuánto se mueve la acción respecto al mercado. β>1: más volátil que el mercado; β<1: menos. "
        "β desapalancado (βu) quita el efecto de la deuda; β apalancado (βL) lo incorpora."
    ),
    "dcf": (
        "DCF (Discounted Cash Flow)",
        "Método de valoración que proyecta flujos futuros (p. ej. FCFF) y los trae a valor presente con el WACC. "
        "Incluye un valor terminal (Gordon u otros). El resultado es el enterprise value (EV)."
    ),
    "ev": (
        "Enterprise Value (EV)",
        "Valor total de la operación (para deuda y equity). En un DCF es el valor presente de los FCFF. "
        "Equity value ≈ EV − deuda neta + caja − NCI − otros claims + asociados."
    ),
    "equity": (
        "Equity value",
        "Valor para los accionistas. Se obtiene del EV restando deuda neta y claims de terceros y sumando caja "
        "y partidas equivalentes. Dividido entre acciones diluidas da el valor por acción (VPS)."
    ),
    "vps": (
        "Valor por acción (VPS)",
        "Equity value ÷ número de acciones. Se compara con el precio de mercado para estimar un upside o downside teórico."
    ),
    "upside": (
        "Upside / downside",
        "Diferencia porcentual entre el VPS del modelo y el precio de mercado. "
        "Positivo no implica 'comprar': depende de supuestos (WACC, g, calidad de datos) y no es orden de inversión."
    ),
    "capex": (
        "CAPEX",
        "Inversión en capital (activos fijos u otros activos de largo plazo). Reduce el FCFF del periodo. "
        "Incluye mantenimiento y crecimiento."
    ),
    "nwc": (
        "NWC (Net Working Capital)",
        "Capital de trabajo neto: recursos operativos de corto plazo (p. ej. cartera + inventarios − proveedores). "
        "Un aumento de NWC consume caja (ΔNWC positivo reduce el FCFF)."
    ),
    "roic": (
        "ROIC",
        "Retorno sobre el capital invertido. Comparado con el WACC indica si el negocio crea o destruye valor "
        "(ROIC > WACC suele interpretarse como creación de valor económico)."
    ),
    "g": (
        "g (crecimiento a perpetuidad)",
        "Tasa de crecimiento de largo plazo del FCFF en el valor terminal tipo Gordon. "
        "Debe ser sostenible y menor que el WACC; suele anclarse a un techo macro (p. ej. PIB nominal)."
    ),
    "gordon": (
        "Modelo de Gordon (crecimiento perpetuo)",
        "Valor terminal = FCFF_{t+1} / (WACC − g). Asume crecimiento constante a perpetuidad. "
        "Muy sensible a WACC y g."
    ),
    "deuda neta": (
        "Deuda neta",
        "Deuda financiera bruta menos caja e equivalentes. En el puente a equity se resta al EV "
        "(junto con otros claims) para llegar al valor de los dueños."
    ),
    "nci": (
        "NCI (interés minoritario)",
        "Parte del patrimonio de subsidiarias que no pertenece a la controladora. "
        "En el puente a equity suele restarse porque ese valor no es de los accionistas de la matriz."
    ),
    "tir": (
        "TIR (IRR)",
        "Tasa interna de retorno: tasa que hace el VPN del proyecto igual a cero. "
        "Si la TIR supera el WACC (o la tasa de corte), el proyecto es atractivo en términos de tasa."
    ),
    "vpn": (
        "VPN (NPV)",
        "Valor presente neto: suma de flujos descontados menos la inversión inicial. "
        "VPN > 0 sugiere que el proyecto agrega valor a la tasa de descuento usada."
    ),
    "payback": (
        "Payback",
        "Tiempo necesario para recuperar la inversión inicial con los flujos del proyecto. "
        "El payback descontado usa flujos en valor presente."
    ),
    "hampel": (
        "Filtro de Hampel / atípicos",
        "Método robusto para detectar valores extremos (mediana ± k·MAD). "
        "En esta plataforma se usa con winsorización para que un año raro no distorsione los drivers de proyección."
    ),
    "múltiplo": (
        "Múltiplo de salida (exit multiple)",
        "Forma alternativa de valor terminal: p. ej. EBITDA de salida × EV/EBITDA de mercado. "
        "Se reporta como escenario aparte del Gordon."
    ),
}


def _detectar_termino_glosario(pregunta):
    """Devuelve (clave, titulo, definicion) si la pregunta pide un concepto."""
    q = (pregunta or "").lower()
    # patrones "qué es X", "que significa X", "definir X"
    for clave, (titulo, definicion) in GLOSARIO_FINANCIERO.items():
        aliases = [clave, titulo.lower()]
        if clave == "deuda neta":
            aliases += ["deuda neta", "net debt"]
        if clave == "beta":
            aliases += ["β", "beta apalancado", "beta desapalancado"]
        if any(a in q for a in aliases):
            if any(p in q for p in (
                "qué es", "que es", "qué significa", "que significa", "significado",
                "definir", "definición", "definicion", "explica qué", "explica que",
                "qué quiere decir", "que quiere decir", "cómo se interpreta", "como se interpreta",
                "para qué sirve", "para que sirve",
            )) or q.strip() in aliases or q.strip() == titulo.lower():
                return clave, titulo, definicion
    # pregunta corta solo el término
    q_strip = q.strip(" ¿?¡!.")
    for clave, (titulo, definicion) in GLOSARIO_FINANCIERO.items():
        if q_strip == clave or q_strip == titulo.lower():
            return clave, titulo, definicion
    return None


def _contexto_empresa_modelo(nombre_empresa):
    """Empaqueta datos del modelo (catálogo o runtime) para el asistente."""
    emp = resolver_empresa(nombre_empresa) or {}
    ctx = {
        "nombre": nombre_empresa,
        "en_catalogo": bool(emp) and nombre_empresa in EMPRESAS,
        "ticker_yf": emp.get("ticker_yf"),
        "ticker_bvc": emp.get("ticker_bvc"),
        "sector": emp.get("sector") or (emp.get("params") or {}).get("sector"),
        "fuente": emp.get("fuente") or ("catálogo" if nombre_empresa in EMPRESAS else "sesión/Yahoo"),
        "moneda": emp.get("moneda") or (emp.get("params") or {}).get("moneda") or "COP",
        "params": dict(emp.get("params") or {}),
        "historico": None,
        "avisos": [],
    }
    try:
        df = df_historico_empresa(nombre_empresa)
        if df is not None and not df.empty:
            ctx["historico"] = df
    except Exception as e:
        ctx["avisos"].append(f"Histórico no disponible: {e}")
    return ctx


def _contexto_mercado_web(ticker_yf, nombre_empresa):
    """Mercado vía Yahoo: precio, múltiplos, descripción y noticias."""
    out = {
        "ok": False, "precio": None, "moneda": None, "beta": None, "pe": None,
        "mcap": None, "sector": None, "industry": None, "summary": None,
        "news": [], "errores": [], "debt": None, "cash": None, "short_name": None,
    }
    if not ticker_yf:
        out["errores"].append("La empresa no tiene ticker Yahoo en el modelo.")
        return out
    try:
        import yfinance as yf
    except Exception as e:
        out["errores"].append(f"yfinance no disponible: {e}")
        return out
    try:
        t = yf.Ticker(str(ticker_yf))
        info = {}
        try:
            info = t.info or {}
        except Exception as e:
            out["errores"].append(f"Yahoo info limitado: {e}")
        precio = info.get("currentPrice") or info.get("regularMarketPrice")
        if precio is None:
            try:
                h = t.history(period="10d")
                if h is not None and not h.empty:
                    precio = float(h["Close"].dropna().iloc[-1])
            except Exception as e:
                out["errores"].append(f"Yahoo history: {e}")
        try:
            out["precio"] = float(precio) if precio is not None and np.isfinite(float(precio)) else None
        except Exception:
            out["precio"] = None
        out["moneda"] = info.get("currency") or info.get("financialCurrency")
        out["beta"] = info.get("beta")
        out["pe"] = info.get("trailingPE") or info.get("forwardPE")
        out["mcap"] = info.get("marketCap")
        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
        out["summary"] = (info.get("longBusinessSummary") or "")[:700] or None
        out["debt"] = info.get("totalDebt")
        out["cash"] = info.get("totalCash")
        out["short_name"] = info.get("shortName") or info.get("longName")
        out["ok"] = out["precio"] is not None or bool(out["summary"])
        try:
            news = getattr(t, "news", None) or []
            for n in news[:6]:
                title = n.get("title")
                if not title and isinstance(n.get("content"), dict):
                    title = n["content"].get("title")
                pub = n.get("publisher") or ""
                if title:
                    out["news"].append({"title": str(title), "publisher": str(pub)})
        except Exception:
            pass
    except Exception as e:
        out["errores"].append(str(e))
    return out


def _buscar_web_contexto(query, max_results=5):
    """Búsqueda web (DuckDuckGo) para titulares/contexto."""
    import re as _re
    import urllib.parse
    import urllib.request
    results = []
    try:
        q = urllib.parse.quote(query[:200])
        url = "https://duckduckgo.com/html/?q=" + q
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        for pattern in (r'class="result__a"[^>]*>(.*?)</a>',):
            for m in _re.finditer(pattern, html, _re.I | _re.S):
                title = _re.sub(r"<[^>]+>", "", m.group(1)).strip()
                title = _re.sub(r"\s+", " ", title)
                if title and len(title) > 20 and title not in results:
                    results.append(title)
                if len(results) >= max_results:
                    return results
    except Exception:
        pass
    return results


def _dcf_rapido_desde_ctx(ctx, precio_mkt=None):
    """Calcula WACC/EV/Equity/VPS a partir del contexto del modelo."""
    p = ctx.get("params") or {}
    df = ctx.get("historico")
    if df is None or getattr(df, "empty", True):
        return None
    try:
        tax = float(p.get("tax") if p.get("tax") is not None else 0.35)
        df_s, _ = _sanear_historico_tab1(df)
        if len(df_s) < 3:
            df_s = df.copy()
        df_proj, meta = proyectar_por_drivers(df_s, 5, tax=tax)
        de = float(p.get("de_ratio") if p.get("de_ratio") is not None else 1.0)
        kd = float(p.get("kd") if p.get("kd") is not None else 0.08)
        beta_u = float(p.get("beta_u") if p.get("beta_u") is not None else 0.6)
        g = float(p.get("g") if p.get("g") is not None else 0.03)
        beta_l = beta_apalancado(beta_u, de, tax)
        ke = costo_equity_capm(beta_l, rf=0.09, erp=0.06)
        wacc, _, _ = calcular_wacc(de, kd, ke, tax)
        bp = params_bridge_desde_ui(
            p.get("deuda_neta", 0), p.get("caja", 0), p.get("nci", 0),
            p.get("otros_claims", 0), p.get("asociados", 0),
            p.get("acciones"), p.get("exit_multiple", 0),
        )
        val = valorar_con_bridge(
            df_proj["FCFF"].values, wacc, g, bp,
            ebitda_salida=float(df_proj["EBITDA"].iloc[-1]),
            precio_mercado=precio_mkt, mid_year=True,
            nopat_final=float(df_proj["NOPAT"].iloc[-1]),
        )
        last = df_s.iloc[-1]
        return {
            "wacc": wacc, "ke": ke, "beta_l": beta_l, "g": g,
            "ev": val["EV"], "equity": val["Equity_Value"],
            "vps": val.get("value_per_share"),
            "upside": val.get("upside_pct"),
            "fcff_ultimo": float(last.get("FCFF", float("nan"))),
            "ingresos_ultimo": float(last.get("Ingresos", float("nan"))),
            "ebitda_ultimo": float(last.get("EBITDA", float("nan"))),
            "anio_ultimo": int(df_s.index[-1]),
            "atipicos": meta.get("atipicos_normalizados") or {},
            "fcff_proj_prom": float(df_proj["FCFF"].mean()),
        }
    except Exception as e:
        return {"error": str(e)}


def _llamar_ia_redaccion(sistema, user_content, temperature=0.25, api_key=None, proveedor="auto"):
    """Llama a xAI, OpenAI o Google Gemini si hay API key (argumento o variable de entorno).
    Devuelve texto o None. El último error queda en _llamar_ia_redaccion._last_error.
    """
    import os
    import json as _json
    import urllib.request
    import urllib.error
    import urllib.parse

    key_ui = (api_key or "").strip()
    key_xai = key_ui or (os.environ.get("XAI_API_KEY") or "").strip()
    key_oai = key_ui or (os.environ.get("OPENAI_API_KEY") or "").strip()
    # Nunca incluir claves en el repositorio: UI → variable de entorno / Secrets.
    key_gem = key_ui or (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()

    prov = (proveedor or "auto").lower().strip()

    # Resolver proveedor
    if prov in ("gemini", "google", "google-ai"):
        use = "gemini"
    elif prov == "openai":
        use = "openai"
    elif prov == "xai":
        use = "xai"
    else:
        # auto: prioriza la key del cuadro según pistas; si no, env
        if key_ui:
            if key_ui.startswith("AIza") or "gemini" in (os.environ.get("PREFERRED_LLM") or "").lower():
                use = "gemini"
            elif key_ui.startswith("xai-") or key_ui.startswith("grok_"):
                use = "xai"
            elif key_ui.startswith("sk-"):
                use = "openai"
            else:
                # sin prefijo claro: respetar env o xai por defecto histórico
                if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                    use = "gemini"
                elif os.environ.get("OPENAI_API_KEY") and not os.environ.get("XAI_API_KEY"):
                    use = "openai"
                else:
                    use = "xai"
        elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            use = "gemini"
        elif os.environ.get("XAI_API_KEY"):
            use = "xai"
        elif os.environ.get("OPENAI_API_KEY"):
            use = "openai"
        else:
            _llamar_ia_redaccion._last_error = None
            return None

    def _http_json(url, body_dict, headers, timeout=90):
        body = _json.dumps(body_dict).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read().decode("utf-8"))

    # ---------- Gemini (Google AI Studio — capa gratuita habitual) ----------
    if use == "gemini":
        key = key_gem
        if not key:
            _llamar_ia_redaccion._last_error = (
                "Proveedor gemini sin API key. Crea una gratis en "
                "https://aistudio.google.com/apikey y pégala aquí "
                "(o define GEMINI_API_KEY)."
            )
            return None
        models = []
        env_m = (os.environ.get("GEMINI_MODEL") or "").strip()
        if env_m:
            models.append(env_m)
        # Modelos vigentes en Gemini API (oct 2026). gemini-pro / 1.5 / 2.0-flash ya no sirven.
        # Preferir Flash-Lite y Flash (cuota free tier habitual en AI Studio).
        for m in (
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.6-flash",
            "gemini-2.5-pro",
        ):
            if m not in models:
                models.append(m)
        last_err = None
        for model in models:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                + urllib.parse.quote(model, safe="")
                + ":generateContent?key="
                + urllib.parse.quote(key, safe="")
            )
            body_dict = {
                "system_instruction": {"parts": [{"text": sistema}]},
                "contents": [
                    {"role": "user", "parts": [{"text": user_content[:14000]}]}
                ],
                "generationConfig": {
                    "temperature": float(temperature),
                    "maxOutputTokens": 4096,
                },
            }
            try:
                data = _http_json(
                    url,
                    body_dict,
                    headers={"Content-Type": "application/json"},
                    timeout=90,
                )
                cands = data.get("candidates") or []
                if not cands:
                    # bloqueo de seguridad u otro
                    fb = data.get("promptFeedback") or data
                    last_err = f"Gemini sin candidatos (modelo={model}). Feedback: {str(fb)[:300]}"
                    continue
                parts = (cands[0].get("content") or {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                if text:
                    _llamar_ia_redaccion._last_error = None
                    return text
                last_err = f"Gemini respuesta vacía (modelo={model})."
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    detail = str(e)
                last_err = f"HTTP {e.code} Gemini modelo={model}. Detalle: {detail}"
                if e.code in (401, 403):
                    _llamar_ia_redaccion._last_error = (
                        last_err + " — key inválida o API Gemini no habilitada en el proyecto."
                    )
                    return None
                # 404 modelo inexistente → probar siguiente
                continue
            except Exception as e:
                last_err = f"Error Gemini ({type(e).__name__}): {e}"
                break
        _llamar_ia_redaccion._last_error = last_err or "Gemini no respondió."
        return None

    # ---------- xAI / OpenAI (OpenAI-compatible chat completions) ----------
    if use == "xai":
        key = key_xai if (key_ui or os.environ.get("XAI_API_KEY")) else key_ui
        key = (key or key_ui or "").strip()
        if not key:
            _llamar_ia_redaccion._last_error = (
                "Proveedor xai sin API key. Crea una de pago en https://console.x.ai "
                "(Grok Inference, permisos 2/2) o define XAI_API_KEY."
            )
            return None
        base = (os.environ.get("XAI_API_BASE") or "https://api.x.ai/v1").rstrip("/")
        model0 = (os.environ.get("XAI_MODEL") or "grok-4.3").strip()
        model_list = []
        for m in [model0, "grok-4.3", "grok-4.7", "grok-4.20", "grok-build-0.1"]:
            if m and m not in model_list:
                model_list.append(m)
    else:  # openai
        key = key_oai if (key_ui or os.environ.get("OPENAI_API_KEY")) else key_ui
        key = (key or key_ui or "").strip()
        if not key:
            _llamar_ia_redaccion._last_error = (
                "Proveedor openai sin API key o sin créditos. "
                "https://platform.openai.com/api-keys"
            )
            return None
        base = (os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/")
        model0 = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
        model_list = [model0]

    last_err = None
    for model in model_list:
        payloads = []
        base_msg = {
            "model": model,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": user_content[:14000]},
            ],
        }
        payloads.append({**base_msg, "temperature": temperature})
        if use == "xai":
            payloads.append(base_msg)  # sin temperature (algunos modelos de razonamiento lo rechazan)

        for body_dict in payloads:
            try:
                data = _http_json(
                    base + "/chat/completions",
                    body_dict,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + key,
                    },
                    timeout=90,
                )
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if content:
                    _llamar_ia_redaccion._last_error = None
                    return content
                last_err = f"Respuesta vacía del proveedor (modelo={model})."
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    detail = str(e)
                last_err = f"HTTP {e.code} al llamar {base} modelo={model}. Detalle: {detail}"
                if e.code in (401, 403):
                    _llamar_ia_redaccion._last_error = last_err + " (clave inválida o sin permiso)"
                    return None
                if e.code == 429:
                    _llamar_ia_redaccion._last_error = last_err + " (sin créditos o rate limit)"
                    return None
                if e.code in (400, 404):
                    break  # siguiente modelo
            except Exception as e:
                last_err = f"Error de red/API ({type(e).__name__}): {e}"
                break

    _llamar_ia_redaccion._last_error = last_err or "No se pudo obtener respuesta de la IA."
    return None

_llamar_ia_redaccion._last_error = None


def _texto_a_html(texto):
    """Convierte markdown simple a HTML legible."""
    import html as _html
    import re as _re
    esc = _html.escape(texto or "")
    esc = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
    bloques = []
    for line in esc.split("\n"):
        if line.startswith("- "):
            bloques.append(f"<li>{line[2:]}</li>")
        elif line.startswith("  · ") or line.startswith("  - "):
            bloques.append(f"<li style='margin-left:12px'>{line[4:]}</li>")
        elif line.strip() == "":
            bloques.append("<br>")
        else:
            bloques.append(f"<p style='margin:6px 0'>{line}</p>")
    cuerpo = "\n".join(bloques)
    cuerpo = _re.sub(
        r"(?:<li>.*?</li>\n?)+",
        lambda m: "<ul style='margin:4px 0 8px 1.1rem'>" + m.group(0) + "</ul>",
        cuerpo,
        flags=_re.S,
    )
    return cuerpo


def _respuesta_definicion(titulo, definicion, nombre_empresa=None, ctx=None, dcf=None):
    """Respuesta didáctica para '¿qué es X?', con ejemplo de la empresa si hay datos."""
    partes = [
        f"**{titulo}**",
        "",
        definicion,
        "",
        "**Cómo leerlo en la práctica**",
        "- No es un precio de acción por sí solo: es un concepto para analizar o valorar.",
        "- Contrástalo siempre con la unidad y moneda de tus estados financieros.",
    ]
    if ctx and dcf and not (isinstance(dcf, dict) and dcf.get("error")):
        partes.append("")
        partes.append(f"**Ejemplo con {nombre_empresa or 'la empresa seleccionada'}**")
        if "EBITDA" in titulo.upper() and dcf.get("ebitda_ultimo") is not None:
            partes.append(
                f"- EBITDA del último año en el modelo ({dcf.get('anio_ultimo')}): "
                f"**{dcf['ebitda_ultimo']:,.1f}** (unidad del histórico)."
            )
        if "FCFF" in titulo.upper() and dcf.get("fcff_ultimo") is not None:
            partes.append(
                f"- FCFF del último año ({dcf.get('anio_ultimo')}): **{dcf['fcff_ultimo']:,.1f}**."
            )
        if "WACC" in titulo.upper() and dcf.get("wacc") is not None:
            partes.append(f"- WACC estimado en el modelo: **{dcf['wacc']*100:.2f}%**.")
        if titulo.upper().startswith("BETA") and dcf.get("beta_l") is not None:
            partes.append(f"- β apalancado usado en el CAPM del modelo: **{dcf['beta_l']:.2f}**.")
        if "VALOR POR ACCIÓN" in titulo.upper() or titulo.upper() == "VPS" or "VPS" in titulo.upper():
            if dcf.get("vps") is not None:
                partes.append(f"- VPS del modelo: **{dcf['vps']:,.0f}**.")
    partes.append("")
    partes.append(
        "*Definición pedagógica de la plataforma. No sustituye un manual contable ni asesoría profesional.*"
    )
    return "\n".join(partes)


def _estructurar_respuesta_ia(pregunta, hechos, dcf, mkt, web_hits, modo_definicion=None, api_key=None, proveedor="auto"):
    """Redacción clara: prioriza IA; si no hay API, plantilla explicativa."""
    import json as _json

    sistema = (
        "Eres un analista financiero senior y docente. Responde siempre en español, claro y didáctico. "
        "Usa SOLO los hechos JSON que te entregan (modelo, DCF, mercado, web, glosario, resultados_pestañas). "
        "resultados_pestañas son las corridas reales de la UI (Pronóstico, DCF, Auditoría, Recomendación, VPN/TIR, Sector, Informe). "
        "Priorízalos sobre cualquier recálculo implícito cuando existan y la empresa coincida. "
        "Si estado es sin_corridas o empresa_distinta, dilo y no inventes tablas de pestañas. "
        "Si la pregunta es conceptual (qué es EBITDA, WACC, etc.), explica el término en lenguaje sencillo, "
        "con analogía breve si ayuda, y luego conecta con los números de la empresa o pestañas si existen. "
        "Si es analítica, estructura: 1) respuesta directa 2) evidencia de pestañas/modelo 3) mercado/web 4) matices. "
        "No inventes cifras. No des órdenes de compra. No digas que eres asesor de inversiones."
    )
    payload = {
        "pregunta": pregunta,
        "hechos_modelo": hechos,
        "dcf": dcf,
        "mercado": {k: mkt.get(k) for k in (
            "precio", "moneda", "beta", "pe", "mcap", "sector", "industry",
            "short_name", "summary", "debt", "cash", "news", "errores"
        )},
        "web_titulos": web_hits,
        "definicion_solicitada": modo_definicion,
    }
    user_content = _json.dumps(payload, ensure_ascii=False, default=str)

    ia = _llamar_ia_redaccion(sistema, user_content, api_key=api_key, proveedor=proveedor)
    if ia:
        return ia, "ia"

    # Si hubo intento de IA y falló, dejar rastro en el fallback
    ia_err = getattr(_llamar_ia_redaccion, "_last_error", None)

    # Fallback determinístico explicativo
    if modo_definicion:
        titulo, definicion = modo_definicion[1], modo_definicion[2]
        return _respuesta_definicion(titulo, definicion, hechos.get("nombre"), hechos, dcf), "glosario"

    partes = []
    partes.append("**1. Respuesta directa**")
    ql = (pregunta or "").lower()
    res_tabs = (hechos or {}).get("resultados_pestañas") or {}
    if isinstance(res_tabs, dict) and res_tabs.get("estado") == "ok":
        ejec = ", ".join(res_tabs.get("pestañas_ejecutadas") or [])
        partes.append(
            f"Hay resultados de pestañas ya ejecutadas para **{res_tabs.get('empresa') or hechos.get('nombre')}**: {ejec}. "
            "La interpretación se ancla a esas corridas (no a un recálculo paralelo)."
        )
    elif isinstance(res_tabs, dict) and res_tabs.get("estado") == "sin_corridas":
        if any(k in ql for k in ("auditor", "escenario", "recomend", "vpn", "tir", "ranking", "sector", "informe", "proyecc", "fan")):
            partes.append(
                "Aún **no hay corridas de pestañas** en esta sesión. Ejecute Pronóstico / DCF / Auditoría / etc. "
                "y vuelva a preguntar para interpretar esos resultados."
            )

    if dcf and not dcf.get("error"):
        if any(k in ql for k in ("precio", "upside", "cotiza", "valor", "barat", "car", "vps")):
            if mkt.get("precio") is not None and dcf.get("vps") is not None:
                ups = dcf.get("upside")
                ups_txt = f"{ups:+.1f}%" if ups is not None else "n/d"
                partes.append(
                    f"El modelo estima un **valor por acción (VPS)** de **{dcf['vps']:,.0f}** frente al precio de mercado "
                    f"**{mkt['precio']} {mkt.get('moneda') or ''}** (upside ≈ **{ups_txt}**). "
                    "El upside es una diferencia teórica: no es una recomendación de compra."
                )
            elif dcf.get("vps") is not None:
                partes.append(
                    f"VPS del modelo ≈ **{dcf['vps']:,.0f}**. En esta sesión no hubo precio de mercado confiable para el upside."
                )
            else:
                partes.append("No fue posible calcular VPS (faltan acciones u otros inputs del puente a equity).")
        elif any(k in ql for k in ("fcff", "flujo", "caja libre")):
            partes.append(
                f"**FCFF** es el flujo de caja libre de la firma. En el último año del modelo ({dcf.get('anio_ultimo')}) "
                f"vale **{dcf.get('fcff_ultimo'):,.1f}**; el promedio proyectado a 5 años ≈ **{dcf.get('fcff_proj_prom'):,.1f}**."
            )
        elif any(k in ql for k in ("deuda", "apalanc", "d/e", "caja")):
            partes.append(
                f"Apalancamiento en el modelo: D/E=**{hechos.get('de_ratio')}**, deuda neta=**{hechos.get('deuda_neta')}**, "
                f"caja=**{hechos.get('caja')}**. Esos montos alimentan el puente de EV a equity."
            )
        elif any(k in ql for k in ("wacc", "beta", "capm", "descuento")):
            partes.append(
                f"**WACC** ≈ **{dcf['wacc']*100:.2f}%** (Ke≈{dcf['ke']*100:.2f}%, βL≈{dcf['beta_l']:.2f}, g={dcf['g']*100:.1f}%). "
                "Es la tasa con la que se descuentan los FCFF."
            )
        else:
            partes.append(
                f"Lectura integrada del modelo: EV≈**{dcf['ev']:,.0f}**, equity≈**{dcf['equity']:,.0f}**, "
                f"WACC **{dcf['wacc']*100:.2f}%**"
                + (f", VPS≈**{dcf['vps']:,.0f}**" if dcf.get("vps") is not None else "")
                + (f", upside≈**{dcf['upside']:+.1f}%**" if dcf.get("upside") is not None else "")
                + "."
            )
    else:
        partes.append(
            "No hay suficiente histórico o parámetros para un DCF completo. "
            "Carga un Excel, elige un emisor del catálogo o descarga un ticker. "
            "Si preguntabas por un concepto (p. ej. qué es EBITDA), reformula: «¿Qué es EBITDA?»."
        )

    partes.append("\n**2. Evidencia del modelo**")
    partes.append(
        f"- Empresa: {hechos.get('nombre')} · fuente: {hechos.get('fuente')} · moneda: {hechos.get('moneda')}"
        + (f" · ticker: {hechos.get('ticker')}" if hechos.get("ticker") else "")
    )
    if dcf and not dcf.get("error"):
        partes.append(
            f"- Último año {dcf.get('anio_ultimo')}: ingresos {dcf.get('ingresos_ultimo'):,.1f}, "
            f"EBITDA {dcf.get('ebitda_ultimo'):,.1f}, FCFF {dcf.get('fcff_ultimo'):,.1f}"
        )
        if dcf.get("atipicos"):
            partes.append(f"- Atípicos tratados en drivers: {dcf['atipicos']}")
    elif dcf and dcf.get("error"):
        partes.append(f"- DCF no calculado: {dcf['error']}")

    partes.append("\n**3. Mercado y web**")
    if mkt.get("precio") is not None:
        partes.append(
            f"- Precio {mkt['precio']} {mkt.get('moneda') or ''} · β={mkt.get('beta')} · P/E={mkt.get('pe')} · "
            f"sector {mkt.get('sector') or '—'} / {mkt.get('industry') or '—'}"
        )
    else:
        partes.append("- Sin precio de mercado en esta consulta.")
    if mkt.get("summary"):
        partes.append(f"- Descripción: {mkt['summary'][:400]}…")
    if mkt.get("news"):
        partes.append("- Titulares Yahoo:")
        for n in mkt["news"][:4]:
            partes.append(f"  · {n.get('title')}")
    if web_hits:
        partes.append("- Referencias web (títulos):")
        for t in web_hits[:5]:
            partes.append(f"  · {t}")
    if mkt.get("errores"):
        partes.append(f"- Avisos de datos: {'; '.join(mkt['errores'][:3])}")

    partes.append(
        "\n**4. Limitación** — Texto generado de forma automática con datos del modelo y fuentes públicas. "
        "Para redacción con IA configura XAI_API_KEY u OPENAI_API_KEY. No constituye asesoría de inversión."
    )
    return "\n".join(partes), "plantilla"


def asistente_consulta_financiera(pregunta, nombre_empresa, api_key=None, proveedor="xai"):
    """Asistente didáctico: glosario + modelo + mercado/web + redacción IA si hay API key."""
    import html as _html

    pregunta = (pregunta or "").strip()
    if not pregunta:
        return (
            '<div class="result-note">Escribe una pregunta. Puedes pedir <b>definiciones</b> '
            "(«¿Qué es EBITDA?», «¿Qué es el WACC?») o <b>análisis de la empresa</b> "
            "(precio, upside, deuda, FCFF, resumen para el comité).</div>"
        )

    termino = _detectar_termino_glosario(pregunta)
    ctx = _contexto_empresa_modelo(nombre_empresa) if nombre_empresa else {
        "nombre": None, "params": {}, "historico": None, "ticker_yf": None,
        "fuente": None, "moneda": None,
    }
    mkt = _contexto_mercado_web(ctx.get("ticker_yf"), nombre_empresa) if nombre_empresa else {
        "ok": False, "precio": None, "errores": [], "news": [],
    }
    dcf = _dcf_rapido_desde_ctx(ctx, precio_mkt=mkt.get("precio")) if nombre_empresa else None

    web_hits = []
    if not termino or (termino and nombre_empresa):
        web_query = f"{(ctx.get('ticker_yf') or nombre_empresa or '')} {pregunta}".strip()
        if web_query:
            web_hits = _buscar_web_contexto(web_query, max_results=5)

    # Si es solo definición y no hay empresa, igual respondemos el glosario
    p = ctx.get("params") or {}
    hechos = {
        "nombre": nombre_empresa,
        "fuente": ctx.get("fuente"),
        "moneda": ctx.get("moneda"),
        "ticker": ctx.get("ticker_yf"),
        "de_ratio": p.get("de_ratio"),
        "kd": p.get("kd"),
        "tax": p.get("tax"),
        "g": p.get("g"),
        "beta_u": p.get("beta_u"),
        "deuda_neta": p.get("deuda_neta"),
        "caja": p.get("caja"),
        "acciones": p.get("acciones"),
        "nci": p.get("nci"),
        "resultados_pestañas": texto_resultados_sesion_para_asistente(nombre_empresa),
    }

    modo_def = None
    if termino:
        modo_def = termino  # (clave, titulo, definicion)

    texto, modo = _estructurar_respuesta_ia(
        pregunta, hechos, dcf, mkt, web_hits,
        modo_definicion=modo_def, api_key=api_key, proveedor=proveedor or "xai",
    )
    cuerpo = _texto_a_html(texto)

    if modo == "ia":
        badge = "Redacción con IA · datos del modelo + mercado/web"
    elif modo == "glosario":
        badge = "Definición pedagógica · glosario de la plataforma"
    else:
        err_ia = getattr(_llamar_ia_redaccion, "_last_error", None)
        if err_ia:
            badge = f"Respuesta estructurada (la IA no respondió: {err_ia[:180]})"
        else:
            badge = "Respuesta estructurada · modelo + mercado/web (sin API de IA)"

    empresa_txt = _html.escape(nombre_empresa or "(sin empresa — solo concepto)")
    return f"""
<div class="section-card">
  <b>Consulta:</b> {empresa_txt} — <i>{_html.escape(pregunta)}</i><br>
  <span style="font-size:0.78rem;color:#64748B">{badge}</span>
</div>
<div class="tip-box">
  <div class="tip-body" style="color:#064E3B !important">{cuerpo}</div>
</div>
<div class="help-chip">
  Puede explicar términos (EBITDA, WACC, FCFF, VPN, etc.) y analizar la empresa seleccionada.
  Para redacción con IA: variable de entorno <code>XAI_API_KEY</code> o <code>OPENAI_API_KEY</code>.
  No constituye asesoría de inversión.
</div>
"""



def _metricas_comite_para_ia(nombre_empresa):
    """Recolecta cifras del modelo + mercado para el prompt del comité de inversión."""
    out = {
        "empresa": nombre_empresa or "N/D",
        "precio_mercado": None,
        "vps_modelo": None,
        "upside": None,
        "wacc_calc": None,
        "ke_calc": None,
        "roic_calc": None,
        "de_ratio": None,
        "g": None,
        "val_ev": None,
        "val_equity": None,
        "moneda": None,
        "ticker": None,
    }
    try:
        ctx = _contexto_empresa_modelo(nombre_empresa) if nombre_empresa else {}
        p = (ctx or {}).get("params") or {}
        out["ticker"] = (ctx or {}).get("ticker_yf")
        out["moneda"] = (ctx or {}).get("moneda") or p.get("moneda")
        out["de_ratio"] = float(p["de_ratio"]) if p.get("de_ratio") is not None else None
        out["g"] = float(p["g"]) if p.get("g") is not None else None
        px = resolver_precio_mercado(nombre_empresa)
        out["precio_mercado"] = float(px) if px is not None else None
        dcf = _dcf_rapido_desde_ctx(ctx, precio_mkt=out["precio_mercado"])
        if isinstance(dcf, dict) and not dcf.get("error"):
            out["wacc_calc"] = dcf.get("wacc")
            out["ke_calc"] = dcf.get("ke")
            out["val_ev"] = dcf.get("ev")
            out["val_equity"] = dcf.get("equity")
            out["vps_modelo"] = dcf.get("vps")
            out["upside"] = dcf.get("upside")
            out["g"] = dcf.get("g", out["g"])
        # ROIC desde histórico si hay capital
        df = (ctx or {}).get("historico")
        cap = p.get("capital_invertido")
        if df is not None and hasattr(df, "empty") and (not df.empty) and "NOPAT" in df.columns and cap:
            try:
                out["roic_calc"] = calcular_roic(float(df["NOPAT"].mean()), float(cap))
            except Exception:
                pass
        # Preferir resultados de sesión (tab4/tab7) si existen
        try:
            reg = RESULTADOS_SESION.get(nombre_empresa) or RESULTADOS_SESION.get("global") or {}
            # structure may vary; soft merge
        except Exception:
            pass
        # Refinar con valoración completa si hay params suficientes
        if out.get("wacc_calc") is None and p:
            try:
                tax = float(p.get("tax") or 0.25)
                de = float(p.get("de_ratio") or 0)
                kd = float(p.get("kd") or 0.08)
                beta_u = float(p.get("beta_u") or 1.0)
                g = float(p.get("g") or 0.03)
                rf = float(p.get("rf") or 0.045)
                erp = float(p.get("erp") or 0.05)
                crp = float(p.get("crp") or 0.0)
                beta_l = beta_apalancado(beta_u, de, tax)
                ke = costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
                wacc, _, _ = calcular_wacc(de, kd, ke, tax)
                out["ke_calc"] = ke
                out["wacc_calc"] = wacc
                out["de_ratio"] = de
                out["g"] = g
            except Exception:
                pass
    except Exception as e:
        out["error"] = str(e)
    return out


def generar_recomendacion_comite_ia(nombre_empresa, api_key=None, proveedor="gemini", metricas=None):
    """
    Deliberación tipo comité interdisciplinario (CFO / Mercado / CRO) usando el mismo
    stack de IA que Consulta IA (_llamar_ia_redaccion).
    """
    import html as _html

    m = dict(metricas or {})
    base = _metricas_comite_para_ia(nombre_empresa)
    for k, v in base.items():
        if m.get(k) is None:
            m[k] = v

    def _f(key, default=0.0):
        v = m.get(key)
        try:
            if v is None:
                return float(default)
            return float(v)
        except Exception:
            return float(default)

    empresa = m.get("empresa") or nombre_empresa or "N/D"
    precio_mercado = _f("precio_mercado", 0.0)
    vps_modelo = _f("vps_modelo", 0.0)
    upside = _f("upside", 0.0)
    wacc_calc = _f("wacc_calc", 0.0)
    ke_calc = _f("ke_calc", 0.0)
    roic_calc = _f("roic_calc", 0.0)
    de_ratio = _f("de_ratio", 0.0)
    g = _f("g", 0.0)
    val_ev = _f("val_ev", 0.0)
    val_equity = _f("val_equity", 0.0)
    mon = m.get("moneda") or ""
    ticker = m.get("ticker") or ""

    # Advertencias de datos faltantes
    faltantes = []
    for lab, key in [
        ("precio de mercado", "precio_mercado"),
        ("VPS", "vps_modelo"),
        ("WACC", "wacc_calc"),
        ("EV", "val_ev"),
    ]:
        v = m.get(key)
        if v is None:
            faltantes.append(lab)

    sistema = (
        "Eres el secretario de un Comité Interdisciplinario de Inversión de alto nivel. "
        "Redactas la deliberación entre tres expertos senior: "
        "(1) Director Financiero (CFO / Valuation — DCF/FCFF, WACC, Ke, CAPM, deuda), "
        "(2) Analista de Mercado y Estratega Competitivo (múltiplos, ROIC vs WACC, macro), "
        "(3) Chief Risk Officer (auditoría de supuestos, sensibilidad, escenarios, atípicos). "
        "Respondes siempre en español, con tono profesional de comité, crítico y equilibrado. "
        "No inventes cifras distintas a las del contexto numérico; si faltan datos, dilo explícitamente. "
        "Esto es apoyo a decisión, no una orden de compra/venta ni asesoría personalizada. "
        "Sigue estrictamente el formato de secciones numeradas que pide el usuario."
    )

    user_content = f"""Actúa como un Comité Interdisciplinario de Inversión de alto nivel compuesto por tres expertos senior:

1. **Director Financiero (CFO / Experto en Valuation):** Especialista en valoración intrínseca (DCF/FCFF), costo de capital (WACC, Ke, CAPM), estructura de deuda y sostenibilidad de flujos.
2. **Analista de Mercado y Estratega Competitivo:** Especialista en dinámicas sectoriales, lectura de múltiplos comparables (EV/EBITDA, P/E), posición competitiva (ROIC vs WACC) y contexto macroeconómico.
3. **Chief Risk Officer (CRO / Gestor de Riesgos):** Especialista en auditoría de supuestos (g vs WACC, apalancamiento D/E), análisis de sensibilidad, valoración de escenarios y detección de eventos atípicos.

---

### CONTEXTO DE ENTRADA (Calculado por el Modelo Cuantitativo)
- **Empresa Objetivo / Ticker:** {empresa}{f' ({ticker})' if ticker else ''}
- **Moneda del modelo:** {mon or 'N/D'}
- **Precio Actual de Mercado:** {precio_mercado:,.2f}
- **Valor por Acción Según el Modelo (VPS):** {vps_modelo:,.2f} (Upside calculado: {upside:+.2f}%)
- **WACC Calculado:** {wacc_calc*100:.2f}% | **Ke (CAPM):** {ke_calc*100:.2f}% | **ROIC:** {roic_calc*100:.2f}%
- **Estructura D/E:** {de_ratio:.2f} | **Crecimiento Terminal (g):** {g*100:.2f}%
- **Valor del Negocio (EV Base):** {val_ev:,.2f}
- **Valor del Equity Base:** {val_equity:,.2f}
{('- **Datos incompletos en el modelo:** ' + ', '.join(faltantes)) if faltantes else ''}

---

### INSTRUCCIONES Y FORMATO DE SALIDA
Simula una deliberación crítica entre los tres miembros del comité contrastando estos números con la realidad del mercado.
Entrega el resultado **estrictamente** bajo este formato:

## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO
- **Aportes del CFO (Estructura y DCF):** [...]
- **Aportes del Analista de Mercado (Sector y Competencia):** [...]
- **Aportes del CRO (Riesgos y Sensibilidad):** [...]

## 2. ANÁLISIS DE BRECHA (MODELO VS. MERCADO ACTUAL)
- **Brecha Detectada:** [...]
- **Factores de Mercado no Contemplados:** [...]

## 3. DECISIÓN FINAL DE INVERSIÓN
- **RECOMENDACIÓN FINAL:** [INVERTIR / NO INVERTIR / INVERTIR CONDICIONALMENTE]
- **PUNTAJE DE VIABILIDAD:** [Escala 1 a 10]
- **PRECIO OBJETIVO DE CONSENSO (Rango Ajustado):** [...]
- **TESIS Y JUSTIFICACIÓN ESTRATÉGICA:** [...]

## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO
1. [...]
2. [...]
"""

    texto = _llamar_ia_redaccion(
        sistema, user_content, temperature=0.35, api_key=api_key, proveedor=proveedor or "gemini"
    )
    if not texto:
        err = getattr(_llamar_ia_redaccion, "_last_error", None) or "Sin respuesta del proveedor de IA."
        return (
            f'<div class="result-note" style="border-left:4px solid #DC2626">'
            f"<b>No se pudo generar la deliberación del comité.</b><br>{_html.escape(str(err))}<br>"
            f"Revisa el proveedor y la API key en <b>Consulta IA</b> (mismo conector).</div>"
        )

    cuerpo = _texto_a_html(texto) if "_texto_a_html" in dir() else None
    if cuerpo is None:
        try:
            cuerpo = _texto_a_html(texto)
        except Exception:
            cuerpo = f"<pre style='white-space:pre-wrap;color:#E8EEF7'>{_html.escape(texto)}</pre>"

    return f"""
<div class="section-card" style="border-left:4px solid #14B8A6">
  <div style="font-size:12px;color:#94A3B8;margin-bottom:8px">
    COMITÉ INTERDISCIPLINARIO (IA) · {_html.escape(str(empresa))}
    · proveedor <b>{_html.escape(str(proveedor or 'gemini'))}</b>
    · apoyo a decisión · no es orden de compra/venta
  </div>
  {cuerpo}
</div>
"""



def tab1_carga_y_pronostico(nombre_empresa, archivo, horizonte, metodo="Drivers + identidad FCFF (recomendado)", tax=0.35, usar_datos_publicos=True):
    try:
        horizonte = int(horizonte)
        df_hist, mensaje = cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=bool(usar_datos_publicos))
        df_hist, nota_saneado = _sanear_historico_tab1(df_hist)
        mensaje = f"{mensaje}{nota_saneado}"
        metodo_key = "drivers"
        if metodo and "ETS" in str(metodo).upper():
            metodo_key = "ets"
        elif metodo and "ARIMA" in str(metodo).upper():
            metodo_key = "arima"
        df_proj, meta = proyectar_variables_con_meta(df_hist, horizonte, metodo=metodo_key, tax=float(tax) if tax is not None else 0.35)
        mc = monte_carlo_fcff(df_proj, df_hist, horizonte=horizonte, n_sim=800, tax=tax)
        fig = generar_fan_chart(df_hist, df_proj, mc, horizonte, nombre_empresa, metodo_label=meta.get("metodo", metodo_key))
        nota_norm, fig_norm = reporte_normalizacion_atipicos(df_hist, meta)
        tabla_proforma = df_proj.round(1).reset_index()
        tabla_proforma.columns = ["Año", "Ingresos", "EBITDA", "EBIT", "Depreciación", "CAPEX", "NWC", "ΔNWC", "NOPAT", "FCFF"]
        hist_resumen = df_hist[["Ingresos", "EBITDA", "EBIT", "CAPEX", "FCFF"]].round(1).reset_index()
        extra = ""
        if meta.get("g_ingresos") is not None:
            extra = (f" | <b>g ingresos:</b> {meta['g_ingresos']*100:.1f}%"
                     f" | <b>Margen EBITDA:</b> {meta.get('margen_ebitda',0)*100:.1f}%"
                     f" | <b>CAPEX/Ingresos:</b> {meta.get('capex_ratio',0)*100:.1f}%")
        info = f"""
<div style="background:linear-gradient(135deg,#0A2540 0%,#1B6CA8 100%);padding:18px 22px;border-radius:12px;margin-bottom:12px" class="dark-card">
<h3 style="margin:0 0 8px 0;color:#5EEAD4 !important">Proyección · {meta.get('metodo', metodo_key)} · {nombre_empresa}</h3>
<p style="margin:0;color:#FFFFFF !important">{mensaje}</p>
<p style="margin:8px 0 0 0;color:#FFFFFF !important"><b style="color:#FFFFFF !important">Horizonte:</b> {horizonte} años | <b>Último año:</b> {df_hist.index[-1]} |
<b>FCFF último:</b> {df_hist['FCFF'].iloc[-1]:,.0f} | <b>FCFF promedio proyectado:</b> {df_proj['FCFF'].mean():,.0f}{extra}</p>
<p style="margin:8px 0 0 0;color:#E2E8F0 !important">Incertidumbre: Monte Carlo ({mc['n_sim']} simulaciones) · vol. ingresos hist. ≈ {mc['vol_ingresos']*100:.1f}%</p>
</div>
{tip("El método <b>Drivers + identidad FCFF</b> no inventa el flujo libre a solas: proyecta ingresos y márgenes, y calcula el FCFF como en contabilidad (utilidad + depreciación − inversión − capital de trabajo). Las franjas de color vienen de <b>Monte Carlo</b>: miles de escenarios con shocks aleatorios.")}
{result_note("Cómo leer la tabla de proyección",
    "Cada fila es un año futuro. <b>Ingresos</b> = ventas esperadas. <b>EBITDA</b> = utilidad operativa del día a día. "
    "<b>CAPEX</b> = plata reinvertida en activos. <b>FCFF</b> = lo que realmente queda libre después de operar e invertir. "
    "Todos los valores están en miles de millones de pesos colombianos.")}
{nota_norm}
{result_note("¿Por qué ya no es solo ARIMA?",
    "<b>Drivers</b> (recomendado): más coherente con valoración DCF. <b>ETS/Holt</b>: suaviza tendencia con series cortas. "
    "<b>ARIMA</b>: se mantiene como benchmark estadístico. En series anuales de 5–10 puntos, drivers o ETS suelen ser más estables.")}
"""
        visible_norm = fig_norm is not None
        help_norm = chart_bubble(
            "Cómo leer la comparación de atípicos",
            "Izquierda = serie original (atípicos marcados). Derecha = tras Hampel/winsor. "
            "La nota superior detalla motivo, método y años."
        ) if visible_norm else ""
        try:
            guardar_resultado_tab("1", nombre_empresa, {
                "metodo": meta.get("metodo", metodo_key),
                "horizonte": horizonte,
                "ultimo_anio": int(df_hist.index[-1]) if len(df_hist) else None,
                "fcff_ultimo": float(df_hist["FCFF"].iloc[-1]) if "FCFF" in df_hist.columns and len(df_hist) else None,
                "fcff_promedio_proyectado": float(df_proj["FCFF"].mean()) if "FCFF" in df_proj.columns else None,
                "fcff_proj": [float(x) for x in df_proj["FCFF"].values],
                "g_ingresos": meta.get("g_ingresos"),
                "margen_ebitda": meta.get("margen_ebitda"),
                "capex_ratio": meta.get("capex_ratio"),
                "vol_ingresos_mc": mc.get("vol_ingresos") if isinstance(mc, dict) else None,
                "n_sim_mc": mc.get("n_sim") if isinstance(mc, dict) else None,
                "mensaje": _html_a_texto(mensaje, 800),
                "proyeccion_resumen": _df_a_registros(tabla_proforma, 8),
            })
        except Exception:
            pass
        return (
            info,
            hist_resumen,
            tabla_proforma,
            fig,
            fig_norm,   # figura o None; el wrapper controla visible
            help_norm if visible_norm else "",
        )
    except Exception as e:
        return (
            f"<div style='color:#EF4444'>Error: {e}<br><pre>{traceback.format_exc()}</pre></div>",
            None, None, None,
            None,
            "",
        )


def tab2_simulacion_politicas(nombre_empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u, deuda_neta=0, rf=0.09, erp=0.06, crp=0.0, usar_datos_publicos=True, caja=0, nci=0, otros_claims=0, asociados=0, acciones=None, exit_multiple=0.0, mid_year=True, g_max_macro=0.05):
    try:
        horizonte = int(horizonte)
        df_hist, mensaje_carga = cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=bool(usar_datos_publicos))
        df_proj = proyectar_variables(df_hist, horizonte, tax=tax).copy()
        df_proj = recalcular_fcff(df_proj, tax=tax, capex_extra=capex_extra)
        beta_l = beta_apalancado(beta_u, de_ratio, tax)
        # CAPM pedagógico: rf≈9%, prima de mercado≈6% (Colombia, simplificado)
        ke = costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
        wacc, we, wd = calcular_wacc(de_ratio, kd, ke, tax)
        g_pes = max(0.005, float(g) - 0.01)
        g_opt = min(float(g) + 0.01, wacc - 0.005) if wacc > 0.02 else float(g)
        # Escenarios por shocks de drivers (+ ajuste WACC/g). Fallback: escalado FCFF legacy.
        _SHOCKS = {
            "Pesimista": {"g_ingresos": 0.90, "margen_ebitda": 0.92, "capex_factor": 1.15, "nwc_factor": 1.10},
            "Base":      {"g_ingresos": 1.00, "margen_ebitda": 1.00, "capex_factor": 1.00, "nwc_factor": 1.00},
            "Optimista": {"g_ingresos": 1.08, "margen_ebitda": 1.06, "capex_factor": 0.92, "nwc_factor": 0.95},
        }
        escenarios = {}
        for nombre, fac, g_e, w_adj in [
            ("Pesimista", 0.75, g_pes, wacc + 0.015),
            ("Base", 1.00, float(g), wacc),
            ("Optimista", 1.25, g_opt, max(wacc - 0.01, 0.06)),
        ]:
            acc_res = resolver_acciones_millones(nombre_empresa, acciones)
            bp = params_bridge_desde_ui(deuda_neta, caja, nci, otros_claims, asociados, acc_res, exit_multiple)
            try:
                _emp2 = resolver_empresa(nombre_empresa) or {}
                if (_emp2.get("params") or {}).get("deuda_es_bruta"):
                    bp["deuda_es_bruta"] = True
            except Exception:
                pass
            try:
                df_esc_i = aplicar_shocks_drivers_proyeccion(df_proj, tax=tax, shock=_SHOCKS.get(nombre, {}))
                fcff_i = [float(x) for x in df_esc_i["FCFF"].values]
                nopat_i = float(df_esc_i["NOPAT"].iloc[-1]) if "NOPAT" in df_esc_i.columns else _nopat_final(df_proj, fac)
                ebitda_out = float(df_esc_i["EBITDA"].iloc[-1]) if "EBITDA" in df_esc_i.columns else None
            except Exception:
                df_esc_i = df_proj
                fcff_i = list(_escalar_fcff(df_proj["FCFF"].values, fac))
                nopat_i = _nopat_final(df_proj, fac)
                ebitda_out = float(df_proj["EBITDA"].iloc[-1]) * fac if "EBITDA" in df_proj.columns else None
            precio = resolver_precio_mercado(nombre_empresa)
            val = valorar_con_bridge(
                fcff_i, w_adj, g_e, bp,
                ebitda_salida=ebitda_out, precio_mercado=precio,
                mid_year=bool(mid_year), g_max_macro=float(g_max_macro),
                nopat_final=nopat_i,
            )
            val = forzar_vps_upside(val, nombre_empresa, acciones, precio=precio)
            escenarios[nombre] = val
            escenarios[nombre]["g"] = g_e
            escenarios[nombre]["WACC"] = w_adj
            escenarios[nombre]["shock_drivers"] = _SHOCKS.get(nombre, {})
            escenarios[nombre]["tv_metodo"] = val.get("tv_metodo", "Gordon / valor-conductor")
        df_esc = pd.DataFrame({
            "Escenario": list(escenarios.keys()),
            "WACC (%)": [v["WACC"] * 100 for v in escenarios.values()],
            "g (%)": [v["g"] * 100 for v in escenarios.values()],
            "EV (miles M)": [v["EV"] for v in escenarios.values()],
            "Equity Value": [v["Equity_Value"] for v in escenarios.values()],
            "PV FCFF": [v["PV_FCFF"] for v in escenarios.values()],
            "PV Terminal": [v["PV_TV"] for v in escenarios.values()],
            "TV / EV %": [
                (100.0 * float(v.get("PV_TV") or 0) / float(v["EV"])) if float(v.get("EV") or 0) else 0.0
                for v in escenarios.values()
            ],
            "Método TV": [str(v.get("tv_metodo") or "—") for v in escenarios.values()],
        }).round(1)
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(3)
        width = 0.35
        evs = [v["EV"] for v in escenarios.values()]
        eqs = [v["Equity_Value"] for v in escenarios.values()]
        b1 = ax.bar(x - width / 2, evs, width, label="Valor de la empresa (EV)", color=COLOR_ACCENT, edgecolor="white")
        b2 = ax.bar(x + width / 2, eqs, width, label="Valor para los dueños (Equity)", color=COLOR_PRIMARY, edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(["Pesimista", "Base", "Optimista"])
        ax.set_ylabel("Valor (miles de millones, moneda del emisor)")
        ax.set_title(f"Valoración DCF · {nombre_empresa}", fontweight="bold", color=COLOR_PRIMARY)
        ax.legend()
        ax.bar_label(b1, fmt="%.0f", padding=3, fontsize=9)
        ax.bar_label(b2, fmt="%.0f", padding=3, fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        # --- Lecturas sencillas por escenario (según resultados reales) ---
        p, b, o = escenarios["Pesimista"], escenarios["Base"], escenarios["Optimista"]

        def lectura_escenario(nombre, val, fac_flujos, g_e, w_adj, tono):
            ev, eq = val["EV"], val["Equity_Value"]
            if nombre == "Pesimista":
                if eq > 0 and ev > 0:
                    veredicto = (
                        f"Aunque todo lo que pudiera salir mal saliera mal "
                        f"(flujos 25% más bajos, crecimiento de largo plazo más flojo y dinero más caro), "
                        f"la empresa <b>todavía tendría valor positivo</b>: "
                        f"EV ≈ {ev:,.0f} y para los dueños ≈ {eq:,.0f} miles de millones (moneda del emisor). "
                        f"Eso sugiere un <b>colchón de resiliencia</b>."
                    )
                elif ev > 0 and eq <= 0:
                    veredicto = (
                        f"En el peor caso el negocio aún valdría algo (EV ≈ {ev:,.0f}), "
                        f"pero después de la deuda a los dueños <b>casi no les quedaría nada</b> "
                        f"(Equity ≈ {eq:,.0f}). Habría estrés fuerte para los accionistas."
                    )
                else:
                    veredicto = (
                        f"En el peor caso el valor se deteriora de forma severa "
                        f"(EV ≈ {ev:,.0f}, Equity ≈ {eq:,.0f}). "
                        f"Si todo sale mal, <b>no habría un rendimiento atractivo</b> bajo estos supuestos."
                    )
                supuesto = (
                    "Flujos de caja libres al 75% de lo esperado, crecimiento a largo plazo un punto más bajo "
                    f"y WACC más alto ({w_adj*100:.2f}%). Es el “si todo lo malo ocurre a la vez”."
                )
            elif nombre == "Base":
                if eq > 0:
                    veredicto = (
                        f"Es el futuro <b>más probable</b> con los supuestos actuales. "
                        f"La empresa valdría cerca de {ev:,.0f} en total y unos {eq:,.0f} para los dueños. "
                        f"Sirve como <b>punto de referencia</b> para comparar el pesimista y el optimista."
                    )
                else:
                    veredicto = (
                        f"En el escenario central el valor para los dueños queda débil "
                        f"(Equity ≈ {eq:,.0f}). Conviene revisar deuda, CAPEX o el costo del capital."
                    )
                supuesto = (
                    f"Flujos según la proyección, crecimiento de largo plazo {g_e*100:.2f}% "
                    f"y WACC {w_adj*100:.2f}% (el costo promedio del dinero de la empresa)."
                )
            else:  # Optimista
                veredicto = (
                    f"Si las cosas salen mejor de lo esperado (flujos 25% más altos, un poco más de crecimiento "
                    f"y dinero un poco más barato), el valor sube a EV ≈ {ev:,.0f} y Equity ≈ {eq:,.0f}. "
                    f"Muestra el <b>potencial al alza</b>, no una promesa."
                )
                supuesto = (
                    "Flujos al 125% de lo esperado, crecimiento de largo plazo un punto más alto "
                    f"y WACC más bajo ({w_adj*100:.2f}%)."
                )
            return f"""
<div style="background:#151C2C;border:1px solid #243044;border-left:5px solid {tono};
            border-radius:10px;padding:14px 16px;margin:10px 0;color:#E8EEF7">
  <div style="font-weight:700;font-size:1.05rem;margin-bottom:6px;color:{tono}">{nombre}</div>
  <p style="margin:0 0 8px 0;font-size:0.92rem;color:#CBD5E1"><b>Qué estamos asumiendo:</b> {supuesto}</p>
  <p style="margin:0;font-size:0.95rem;color:#E8EEF7;line-height:1.5">{veredicto}</p>
  <p style="margin:8px 0 0 0;font-size:0.88rem;color:#94A3B8">
    WACC {w_adj*100:.2f}% · g {g_e*100:.2f}% · EV {ev:,.0f} · Equity {eq:,.0f}
    (miles de millones (moneda del emisor))
  </p>
</div>
"""

        bridge_html = formatear_bridge_html(escenarios["Base"], moneda_modelo=moneda_empresa(nombre_empresa), moneda_precio=moneda_precio_empresa(nombre_empresa), nombre_empresa=nombre_empresa)
        bloque_escenarios = (
            lectura_escenario("Pesimista", p, 0.75, g_pes, wacc + 0.015, "#DC2626")
            + lectura_escenario("Base", b, 1.00, float(g), wacc, "#1D4ED8")
            + lectura_escenario("Optimista", o, 1.25, g_opt, max(wacc - 0.01, 0.06), "#059669")
        )

        # Mensaje de margen de seguridad
        if p["Equity_Value"] > 0:
            margen_msg = (
                "Incluso en el escenario pesimista el valor para los dueños sigue siendo positivo: "
                "hay un <b>margen de seguridad</b> relativo frente a sorpresas malas."
            )
        elif b["Equity_Value"] > 0:
            margen_msg = (
                "El caso base es positivo, pero el pesimista presiona el valor de los dueños. "
                "Conviene no planear solo con el escenario bueno."
            )
        else:
            margen_msg = (
                "Ni el caso base deja un Equity sólido. Antes de decidir, revisa deuda, CAPEX extra y supuestos de crecimiento."
            )

        resumen = f"""
<div style="background:#151C2C;border:1px solid #243044;border-radius:12px;padding:18px 22px">
<h3 style="color:{COLOR_PRIMARY};margin-top:0">Parámetros · {nombre_empresa}</h3>
<table style="width:100%;border-collapse:collapse;font-size:14px">
<tr style="background:#0A2540;color:white"><th style="padding:8px;text-align:left">Parámetro</th><th style="padding:8px;text-align:left">Valor</th><th style="padding:8px;text-align:left">¿Qué significa?</th></tr>
<tr><td style="padding:6px;border-bottom:1px solid #E2E8F0">D/E</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0"><b>{de_ratio:.2f}</b></td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Deuda por cada peso de los dueños</td></tr>
<tr style="background:#1A2336"><td style="padding:6px;border-bottom:1px solid #E2E8F0">Kd</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0">{kd*100:.2f}%</td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Interés que paga por sus deudas</td></tr>
<tr><td style="padding:6px;border-bottom:1px solid #E2E8F0">Impuestos</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0">{tax*100:.1f}%</td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Porcentaje que se va en impuestos</td></tr>
<tr style="background:#1A2336"><td style="padding:6px;border-bottom:1px solid #E2E8F0">g perpetuo</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0">{g*100:.2f}%</td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Crecimiento de largo plazo</td></tr>
<tr><td style="padding:6px;border-bottom:1px solid #E2E8F0">CAPEX extra</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0">{capex_extra:,.0f}</td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Inversión adicional en activos</td></tr>
<tr style="background:#1A2336"><td style="padding:6px;border-bottom:1px solid #E2E8F0">β apalancado</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0">{beta_l:.2f}</td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Riesgo del negocio + efecto deuda</td></tr>
<tr><td style="padding:6px;border-bottom:1px solid #E2E8F0">Ke</td><td style="padding:6px;text-align:left;border-bottom:1px solid #E2E8F0">{ke*100:.2f}%</td><td style="padding:6px;border-bottom:1px solid #E2E8F0;font-size:12px;color:#E2E8F0;font-weight:500">Rentabilidad que piden los accionistas</td></tr>
<tr style="background:#00A3A1;color:white"><td style="padding:8px"><b>WACC</b></td><td style="padding:8px;text-align:left"><b>{wacc*100:.2f}%</b></td><td style="padding:8px;font-size:12px">Costo promedio del dinero</td></tr>
</table>
<br>
<p style="margin:0;color:#E8EEF7"><b>EV base:</b> {escenarios['Base']['EV']:,.0f} | <b>Equity base:</b> {escenarios['Base']['Equity_Value']:,.0f}</p>
</div>

<div class="section-card" style="margin-top:14px">
<b>¿Qué es cada escenario?</b>
<p style="margin:8px 0 0 0;color:#E2E8F0;line-height:1.5">
No son predicciones del futuro: son <b>tres historias posibles</b> para ver qué tan sensible es el valor de la empresa
si los flujos, el crecimiento o el costo del dinero cambian.
</p>
</div>

{bloque_escenarios}
{bridge_html}

{tip(margen_msg)}
{result_note("Cómo leer la tabla de escenarios",
    "<b>WACC</b> = costo del dinero usado para descontar. <b>g</b> = crecimiento de largo plazo. "
    "<b>EV</b> = valor de toda la empresa. <b>Equity Value</b> = valor para los accionistas (EV menos deuda neta). "
    "<b>PV FCFF</b> = valor presente de los flujos del horizonte. <b>PV Terminal</b> = valor presente de todo lo que viene después.")}
"""
        try:
            guardar_resultado_tab("2", nombre_empresa, {
                "tabla_escenarios": _df_a_registros(df_esc, 6),
                "texto": _html_a_texto(resumen, 2200),
            })
        except Exception:
            pass
        # Hero global solo en acordeón de sensibilidad (evitar duplicados en la UI)
        resumen = f'<div class="mf-atmosphere-base">{resumen}</div>'
        return resumen, df_esc, fig
    except Exception as e:
        return f"Error: {e}", None, None


def tab3_auditoria_teorica(nombre_empresa, archivo, horizonte, de_ratio, kd, tax, g, beta_u, capital_invertido, rf=0.09, erp=0.06, crp=0.0, usar_datos_publicos=True):
    try:
        horizonte = int(horizonte)
        df_hist, _ = cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=bool(usar_datos_publicos))
        df_proj = recalcular_fcff(proyectar_variables(df_hist, horizonte, tax=tax).copy(), tax=tax, capex_extra=0)
        beta_l = beta_apalancado(beta_u, de_ratio, tax)
        ke = costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
        wacc, we, wd = calcular_wacc(de_ratio, kd, ke, tax)
        nopat_prom = float(df_proj["NOPAT"].mean())
        try:
            roic = float(nopat_prom) / capital_base_roic(capital_invertido, nopat_prom)
        except (TypeError, ValueError, ZeroDivisionError):
            roic = float("nan")
        reinv = tasa_reinversion(df_proj["CAPEX"].mean(), df_proj["Depreciacion"].mean(), df_proj["Delta_NWC"].mean(), nopat_prom)
        g_sost = roic * reinv
        pruebas = []
        if g < wacc:
            pruebas.append(("✅ g < WACC", f"Bien. Crecimiento ({g*100:.2f}%) < costo del dinero ({wacc*100:.2f}%). Modelo estable."))
        else:
            pruebas.append(("❌ g ≥ WACC", f"Problema. Crecimiento ≥ costo del dinero. El valor de largo plazo se infla de forma irreal."))
        if np.isfinite(roic) and roic > wacc:
            pruebas.append(("✅ ROIC > WACC", f"Crea valor: rinde {roic*100:.2f}% y el dinero le cuesta {wacc*100:.2f}%."))
        elif np.isfinite(roic):
            pruebas.append(("⚠️ ROIC ≤ WACC", f"No crea valor: rinde {roic*100:.2f}% vs costo {wacc*100:.2f}%."))
        else:
            pruebas.append(("ℹ️ ROIC no disponible", "Falta una base contable válida de capital invertido."))
        diff = abs(g - g_sost)
        if diff < 0.015:
            pruebas.append(("✅ g coherente", f"Crecimiento sostenible estimado ≈ {g_sost*100:.2f}% (muy parecido a tu g)."))
        else:
            pruebas.append(("⚠️ g poco coherente", f"Tu g={g*100:.2f}% vs sostenible {g_sost*100:.2f}%."))
        if de_ratio <= 1.5:
            pruebas.append(("✅ Deuda moderada", f"D/E={de_ratio:.2f} razonable para infraestructura."))
        else:
            pruebas.append(("⚠️ Deuda elevada", f"D/E={de_ratio:.2f} aumenta el riesgo."))
        # Coyuntura tasas locales (COP): rf demasiado bajo sesga WACC a la baja y EV al alza
        try:
            rf_f = float(rf)
            if rf_f < 0.10:
                pruebas.append((
                    "⚠️ rf bajo vs TES/BanRep",
                    f"rf={rf_f*100:.1f}% está por debajo de la coyuntura local (~11–13% TES 10a / BanRep ~12% en 2026). "
                    "Un rf artificialmente bajo infla el DCF. Calibre a curva local o documente si el modelo es en USD.",
                ))
            elif rf_f >= 0.10:
                pruebas.append((
                    "✅ rf en rango local",
                    f"rf={rf_f*100:.1f}% coherente con un ancla de tasas locales elevadas (no usar CRP extra si rf ya es TES).",
                ))
        except Exception:
            pass
        try:
            if float(crp or 0) > 0.005 and float(rf) >= 0.10:
                pruebas.append((
                    "⚠️ Posible doble conteo CRP",
                    f"CRP={float(crp)*100:.1f}% con rf local alto puede sobredescontar. Si rf≈TES, CRP suele ir en 0.",
                ))
        except Exception:
            pass
        explicacion = f"""
<div style="background:#151C2C;border-left:5px solid {COLOR_ACCENT};padding:18px 22px;border-radius:0 12px 12px 0">
<h3 style="color:{COLOR_PRIMARY};margin-top:0">Auditoría del modelo · {nombre_empresa}</h3>
<p><b>1. ¿El crecimiento es realista?</b><br>
g debe ser menor que WACC. Hoy: g=<b>{g*100:.2f}%</b> | WACC=<b>{wacc*100:.2f}%</b>. {"✅ Cumple." if g < wacc else "❌ No cumple."}</p>
<p><b>2. ¿La empresa crea valor?</b><br>
ROIC ≈ <b>{roic*100:.2f}%</b> vs WACC <b>{wacc*100:.2f}%</b>. {"✅ Crea valor." if roic > wacc else "⚠️ No crea valor."}</p>
<p><b>3. ¿El crecimiento se sostiene?</b><br>
Reinversión ≈ {reinv*100:.1f}% → crecimiento sostenible ≈ <b>{g_sost*100:.2f}%</b>.</p>
<p><b>4. ¿Cuánta deuda?</b><br>
D/E={de_ratio:.2f} → {wd*100:.1f}% deuda y {we*100:.1f}% de los dueños. Costo efectivo de deuda ≈ {kd*(1-tax)*100:.2f}%.</p>
</div>
{tip("Esta pestaña es un <b>examen de coherencia</b>. No dice si la acción está cara o barata; dice si los números tienen lógica entre sí.")}
{result_note("Cómo leer las pruebas",
    "Verde ✅ = el supuesto es coherente. Amarillo ⚠️ = conviene revisarlo. Rojo ❌ = hay un problema serio en el modelo "
    "(por ejemplo, asumir un crecimiento mayor que el costo del dinero hace explotar el valor de largo plazo).")}
"""
        _df_pruebas = pd.DataFrame(pruebas, columns=["Prueba", "Interpretación sencilla"])
        try:
            guardar_resultado_tab("3", nombre_empresa, {
                "pruebas": _df_a_registros(_df_pruebas, 20),
                "texto": _html_a_texto(explicacion, 2200),
            })
        except Exception:
            pass
        return explicacion, _df_pruebas
    except Exception as e:
        return f"Error: {e}", None


def tab4_recomendacion(nombre_empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u, capital_invertido, deuda_neta, rf=0.09, erp=0.06, crp=0.0, usar_datos_publicos=True, caja=0, nci=0, otros_claims=0, asociados=0, acciones=None, exit_multiple=0.0, mid_year=True, g_max_macro=0.05):
    try:
        horizonte = int(horizonte)
        df_hist, mensaje_carga = cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=bool(usar_datos_publicos))
        df_proj = proyectar_variables(df_hist, horizonte, tax=tax).copy()
        df_proj = recalcular_fcff(df_proj, tax=tax, capex_extra=capex_extra)
        beta_l = beta_apalancado(beta_u, de_ratio, tax)
        ke = costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
        wacc, _, _ = calcular_wacc(de_ratio, kd, ke, tax)
        acc_res = resolver_acciones_millones(nombre_empresa, acciones)
        bp = params_bridge_desde_ui(deuda_neta, caja, nci, otros_claims, asociados, acc_res, exit_multiple)
        try:
            _emp4 = resolver_empresa(nombre_empresa) or {}
            if (_emp4.get("params") or {}).get("deuda_es_bruta"):
                bp["deuda_es_bruta"] = True
        except Exception:
            pass
        precio_p = resolver_precio_mercado(nombre_empresa)
        ebitda_out = float(df_proj["EBITDA"].iloc[-1]) if "EBITDA" in df_proj.columns else None
        val_base = valorar_con_bridge(df_proj["FCFF"].values, wacc, g, bp, ebitda_salida=ebitda_out, precio_mercado=precio_p, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_proj))
        val_base = forzar_vps_upside(val_base, nombre_empresa, acciones, precio=precio_p)
        df_ref = df_proj.copy()
        df_ref["CAPEX"] -= capex_extra
        df_ref["FCFF"] = df_ref["NOPAT"] + df_ref["Depreciacion"] - df_ref["CAPEX"] - df_ref["Delta_NWC"]
        val_ref = valorar_con_bridge(df_ref["FCFF"].values, wacc, g, bp, ebitda_salida=float(df_ref["EBITDA"].iloc[-1]) if "EBITDA" in df_ref.columns else None, precio_mercado=precio_p, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_ref))
        delta_ev = val_base["EV"] - val_ref["EV"]
        margen_seg = wacc - g
        riesgo_liq = "Alto" if df_proj["FCFF"].min() < 0 else ("Medio" if df_proj["FCFF"].mean() < 0.03 * df_proj["Ingresos"].mean() else "Bajo")
        roic = calcular_roic(df_proj["NOPAT"].mean(), capital_invertido)
        creacion = roic > wacc
        score, razones = 0, []
        if g < wacc:
            score += 2; razones.append("Crecimiento menor al costo del dinero (modelo estable)")
        else:
            score -= 3; razones.append("Crecimiento ≥ costo del dinero (modelo inestable)")
        if creacion:
            score += 2; razones.append("La empresa rinde más de lo que cuesta financiarse")
        else:
            score -= 2; razones.append("La empresa no supera su costo de capital")
        if de_ratio <= 1.8:
            score += 1; razones.append("Deuda dentro de un rango tolerable")
        else:
            score -= 2; razones.append("Deuda elevada")
        if delta_ev > 1e-9:
            score += 1; razones.append("El CAPEX extra suma valor")
        elif delta_ev < -1e-9:
            score -= 1; razones.append("El CAPEX extra resta valor")
        if riesgo_liq == "Bajo":
            score += 1; razones.append("Caja proyectada estable")
        elif riesgo_liq == "Alto":
            score -= 2; razones.append("Riesgo de caja")
        # Unicidad: sin razones repetidas (orden estable)
        razones = list(dict.fromkeys(razones))

        g_pes = max(0.005, float(g) - 0.01)
        val_pes = valorar_con_bridge(_escalar_fcff(df_proj["FCFF"].values, 0.75), wacc + 0.015, g_pes, bp, ebitda_salida=(ebitda_out * 0.75 if ebitda_out else None), precio_mercado=precio_p, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_proj, 0.75))

        emp = resolver_empresa(nombre_empresa) or {}
        mkt = obtener_datos_mercado_bvc(emp.get("ticker_yf"), ticker_bvc=emp.get("ticker_bvc"))
        prov = procedencia_datos(mensaje_carga, emp.get("ticker_yf"), mkt)

        # Métricas a nivel de FIRMA, consistentes con el DCF: MVA = EV − capital invertido y TIR implícita
        # (incluye valor terminal). Reemplazan al "VPN de proyecto" con inversión inicial arbitraria.
        vpn_p, tir_p = metricas_valor_firma(df_proj["FCFF"].values, capital_invertido, val_base)
        if vpn_p is None:
            vpn_p = float("nan")
        if tir_p is None:
            tir_p = float("nan")
        payback = None

        emp = aplicar_monedas_a_empresa(nombre_empresa, emp)
        mon_modelo, mon_precio = monedas_alineadas_por_ticker(
            ticker=(emp or {}).get("ticker_yf") or (emp or {}).get("ticker_bvc"),
            nombre_empresa=nombre_empresa, emp=emp or {},
        )
        motor = motor_decision_institucional(
            wacc=wacc, g=float(g), roic=roic, de_ratio=float(de_ratio),
            vpn=(vpn_p if vpn_p == vpn_p else None), tir=tir_p if (tir_p == tir_p) else None, payback=payback,
            ev_base=val_base["EV"], equity_base=val_base["Equity_Value"],
            equity_pesimista=val_pes["Equity_Value"], delta_ev_capex=delta_ev,
            riesgo_liq=riesgo_liq, procedencia=prov, score_heuristico=score,
            tv_pct=val_base.get("tv_pct_ev"), mult_terminal=val_base.get("mult_terminal"),
            precio_mercado=precio_p, equity_por_accion=val_base.get("value_per_share"),
            moneda_modelo=mon_modelo, moneda_precio=mon_precio,
        )
        decision, color, just = motor["decision"], motor["color"], motor["sesgo"]

        kpis = pd.DataFrame({
            "Indicador": [
                "Decisión de comité (modelo)", "Score heurístico", "Calidad de datos",
                "Fuente financiera", "Fuente mercado", "Ke (CAPM)", "WACC", "ROIC",
                "ΔEV por CAPEX extra", "Equity base", "Equity pesimista", "MVA firma (EV − capital invertido)", "TIR implícita firma*"
            ],
            "Valor": [
                decision, f"{score}/7", prov["nivel_calidad"], prov["fuente_financiera"], prov["fuente_mercado"],
                f"{ke*100:.2f}%", f"{wacc*100:.2f}%", f"{roic*100:.2f}%",
                f"{delta_ev:,.0f}", f"{val_base['Equity_Value']:,.0f}", f"{val_pes['Equity_Value']:,.0f}",
                f"{vpn_p:,.1f}" if vpn_p == vpn_p else "N/D",
                f"{tir_p*100:.2f}%" if (tir_p == tir_p) else "N/D",
            ],
        })

        vetos_html = "".join(f"<li style='color:#991B1B'>{v}</li>" for v in motor["vetos"]) or "<li style='color:#065F46'>Ningún veto duro activo</li>"
        # Vetos del motor de decisión (sin bloque de contraste modelo vs mercado en esta pestaña).
        vetos_bloque = (
            "<b>Vetos de calidad del modelo (control interno · no son rating de la acción)</b>"
            f"<ul>{vetos_html}</ul>"
        )
        alertas_html = "".join(f"<li style='color:#9A3412'>{a}</li>" for a in motor["alertas"]) or "<li>Sin alertas relevantes</li>"
        soportes_html = "".join(f"<li style='color:#065F46'>{s}</li>" for s in motor["soportes"]) or "<li>Sin soportes destacados</li>"

        try:
            sens = matriz_sensibilidad_wacc_g(df_proj["FCFF"].values, deuda_neta, wacc, float(g), mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_proj))
            sens_html = sens.to_html(index=False, na_rep="—")
            sens_html = sens_html.replace(
                '<table',
                '<table style="width:100%;border-collapse:collapse;font-size:12px;color:#E8EEF7;text-align:left"',
            )
            sens_html = sens_html.replace('<th>', '<th style="text-align:left;padding:8px 10px;background:#0F766E;color:#ECFDF5">')
            sens_html = sens_html.replace('<td>', '<td style="text-align:left;padding:6px 10px;border-bottom:1px solid #243044">')
            sens_html = sens_html.replace('<th>', '<th style="background:#0A2540;color:#fff;padding:6px;text-align:left">')
            sens_html = sens_html.replace('<td>', '<td style="padding:6px;border-bottom:1px solid #E2E8F0;text-align:left;color:#E8EEF7">')
        except Exception as e_sens:
            sens_html = f"<p style='color:#991B1B'>No se pudo calcular la matriz de sensibilidad: {e_sens}</p>"

        decision_html = f"""
<div class="mf-decision-pulse" style="background:#151C2C;border:3px solid {color};border-radius:12px;padding:18px 22px;margin-bottom:14px">
  <div style="font-size:13px;color:#94A3B8;font-weight:600">MARCO DE DECISIÓN INSTITUCIONAL (APOYO · NO ORDEN DE COMPRA)</div>
  <h2 style="margin:6px 0;color:{color};font-size:1.55rem">{decision}</h2>
  <p style="margin:0;color:#E8EEF7;line-height:1.5">{just}</p>
  <p style="margin:10px 0 0 0;color:#CBD5E1;font-size:0.88rem">
    Modelo v2.0-institucional · {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
    CAPM: rf={float(rf)*100:.1f}% · ERP={float(erp)*100:.1f}% · CRP={float(crp)*100:.1f}% · Ke={ke*100:.2f}%
  </p>
</div>
<div class="section-card">
  {vetos_bloque}
  <b>Alertas</b>
  <ul>{alertas_html}</ul>
  <b>Soportes</b>
  <ul>{soportes_html}</ul>
</div>
"""
        resumen = f"""
<div style="background:linear-gradient(135deg,{COLOR_PRIMARY} 0%,#1B6CA8 100%);padding:22px;border-radius:14px;margin-bottom:16px" class="dark-card">
<h2 style="margin:0 0 6px 0;color:#5EEAD4 !important">Comité de inversión · {nombre_empresa}</h2>
<p style="margin:0;color:#FFFFFF !important">Horizonte {horizonte} años · WACC {wacc*100:.2f}% · g {float(g)*100:.2f}% · ROIC {roic*100:.2f}%</p>
<p style="margin:8px 0 0 0;color:#E2E8F0 !important">EV base {val_base['EV']:,.0f} · Equity base {val_base['Equity_Value']:,.0f} · Equity pesimista {val_pes['Equity_Value']:,.0f} (miles M · moneda del emisor)</p>
</div>
<div class="section-card">
<b>Matriz de sensibilidad EV (filas = WACC, columnas = g)</b>
<p style="color:#CBD5E1;margin:6px 0 10px 0">Si el valor se desploma con pequeños cambios de WACC o g, la tesis es frágil para un comité institucional.</p>
{sens_html}
</div>
{tip("Checklist mínimo antes de una decisión real: (1) cifras auditadas, (2) CAPM calibrado al mercado, (3) deuda y CAPEX del guidance oficial, (4) liquidez del título en BVC, (5) límites de riesgo del mandato.")}
"""
        # Salida 1 (decisión): tarjeta + alertas/soportes (sin módulo contraste modelo vs mercado).
        # Salida 3 (memo): resumen numérico + sensibilidad + puente EV→Equity. Sin bloques repetidos.
        resumen = resumen + formatear_bridge_html(val_base, moneda_modelo=mon_modelo, moneda_precio=mon_precio, nombre_empresa=nombre_empresa)
        try:
            guardar_resultado_tab("4", nombre_empresa, {
                "decision": _html_a_texto(decision_html, 1800),
                "kpis": _df_a_registros(kpis, 15) if kpis is not None else None,
                "memo": _html_a_texto(resumen, 2200),
            })
        except Exception:
            pass
        return decision_html, kpis, resumen
    except Exception as e:
        return f"Error: {e}<br><pre>{traceback.format_exc()}</pre>", None, str(e)


def tab5_vpn_tir(nombre_empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u, inversion_inicial, rf=0.09, erp=0.06, crp=0.0, usar_datos_publicos=True):
    try:
        horizonte = int(horizonte)
        df_hist, _ = cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=bool(usar_datos_publicos))
        df_proj = proyectar_variables(df_hist, horizonte, tax=tax).copy()
        df_proj = recalcular_fcff(df_proj, tax=tax, capex_extra=capex_extra)
        beta_l = beta_apalancado(beta_u, de_ratio, tax)
        ke = costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
        wacc, _, _ = calcular_wacc(de_ratio, kd, ke, tax)
        fcff_vals = df_proj["FCFF"].values.tolist()
        emp5 = resolver_empresa(nombre_empresa) or {}
        cap5 = float((emp5.get("params") or {}).get("capital_invertido") or 0)
        mp5 = metricas_proyecto_robustas(
            fcff_vals, wacc,
            inversion_inicial=inversion_inicial,
            capital_invertido=cap5,
        )
        inv_u = float(mp5["inversion_usada"])
        cashflows = mp5["cashflows"]
        vpn = mp5["vpn"]
        tir = mp5["tir"]
        nota_mp5 = mp5.get("nota") or ""
        rows = []
        acumulado_no_desc = -inv_u
        acumulado_desc = -inv_u
        for i, (año, fcff) in enumerate(zip(df_proj.index, fcff_vals)):
            dfactor = 1 / (1 + wacc) ** (i + 1)
            pv = fcff * dfactor
            acumulado_no_desc += fcff
            acumulado_desc += pv
            rows.append({"Año": int(año), "FCFF": round(fcff, 1), "Factor Descuento": round(dfactor, 4),
                         "PV(FCFF)": round(pv, 1), "FCFF Acumulado": round(acumulado_no_desc, 1),
                         "VPN Acumulado": round(acumulado_desc, 1)})
        df_tabla = pd.DataFrame([{"Año": "t=0 (Inversión)", "FCFF": -inv_u, "Factor Descuento": 1.0,
                                  "PV(FCFF)": -inv_u, "FCFF Acumulado": -inv_u,
                                  "VPN Acumulado": -inv_u}] + rows)
        payback = None
        acum = -inv_u
        for i, fcff in enumerate(fcff_vals):
            prev = acum
            acum += fcff
            if acum >= 0:
                payback = i + (abs(prev) / fcff) if fcff != 0 else i + 1.0
                break
        fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
        ax1 = axes[0]
        años_lab = [f"t={i}" for i in range(len(cashflows))]
        colors_bar = [COLOR_DANGER if c < 0 else COLOR_ACCENT for c in cashflows]
        ax1.bar(años_lab, cashflows, color=colors_bar, edgecolor="white", width=0.65)
        ax1.axhline(0, color="#94A3B8", lw=1)
        ax1.set_title("Dinero que entra y sale cada año", fontweight="bold", color=COLOR_PRIMARY)
        ax1.set_ylabel("Miles de millones (moneda del emisor)")
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax2 = axes[1]
        vpn_acum = df_tabla["VPN Acumulado"].values
        ax2.plot(range(len(vpn_acum)), vpn_acum, "o-", color=COLOR_PRIMARY, lw=2.5, ms=8)
        ax2.fill_between(range(len(vpn_acum)), vpn_acum, 0, where=(np.array(vpn_acum) >= 0), color=COLOR_SUCCESS, alpha=0.25, label="Ya recuperó y gana")
        ax2.fill_between(range(len(vpn_acum)), vpn_acum, 0, where=(np.array(vpn_acum) < 0), color=COLOR_DANGER, alpha=0.25, label="Aún no recupera")
        ax2.axhline(0, color="#94A3B8", ls="--", lw=1.2)
        ax2.set_xticks(range(len(vpn_acum)))
        ax2.set_xticklabels(años_lab)
        ax2.set_title("Cómo evoluciona el valor del proyecto", fontweight="bold", color=COLOR_PRIMARY)
        ax2.legend(loc="best")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        plt.tight_layout()
        def _tir_ok(x):
            try:
                return x is not None and isinstance(x, (int, float)) and np.isfinite(float(x))
            except Exception:
                return False
        tir_str = f"{float(tir)*100:.2f}%" if _tir_ok(tir) else "N/D"
        try:
            vpn_f = float(vpn)
            decision_vpn = "CREA VALOR (VPN > 0)" if np.isfinite(vpn_f) and vpn_f > 0 else "NO CREA VALOR (VPN ≤ 0 o N/D)"
        except Exception:
            decision_vpn = "VPN N/D"
        if _tir_ok(tir):
            decision_tir = "TIR > WACC → Tiene sentido" if float(tir) > float(wacc) else "TIR ≤ WACC → Revisar"
        else:
            decision_tir = "TIR N/D (inversión/flujos incoherentes — usar EV/Equity)"
        payback_str = f"{payback:.1f} años" if payback is not None else "N/D"
        resumen = f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:18px">
  <div style="background:linear-gradient(135deg,#0A2540,#1B6CA8);padding:18px;border-radius:12px;text-align:center" class="dark-card">
    <div style="font-size:13px;color:#E2E8F0 !important">VPN (al {wacc*100:.2f}%)</div>
    <div style="font-size:26px;font-weight:700;margin:6px 0;color:#5EEAD4 !important">{vpn:,.1f}</div>
    <div style="font-size:12px;color:#FFFFFF !important">{decision_vpn}</div>
  </div>
  <div style="background:linear-gradient(135deg,#0A2540,#1B6CA8);padding:18px;border-radius:12px;text-align:center" class="dark-card">
    <div style="font-size:13px;color:#E2E8F0 !important">TIR del proyecto</div>
    <div style="font-size:26px;font-weight:700;margin:6px 0;color:#5EEAD4 !important">{tir_str}</div>
    <div style="font-size:12px;color:#FFFFFF !important">{decision_tir}</div>
  </div>
  <div style="background:linear-gradient(135deg,#0A2540,#1B6CA8);padding:18px;border-radius:12px;text-align:center" class="dark-card">
    <div style="font-size:13px;color:#E2E8F0 !important">Payback</div>
    <div style="font-size:26px;font-weight:700;margin:6px 0;color:#5EEAD4 !important">{payback_str}</div>
    <div style="font-size:12px;color:#FFFFFF !important">Años para recuperar</div>
  </div>
</div>
{tip("<b>VPN positivo</b> = después de devolver el costo del capital, el proyecto todavía deja ganancia en pesos de hoy. <b>TIR</b> = rentabilidad anual; si supera el WACC, rinde más que el costo del dinero. <b>Payback</b> = años para recuperar la inversión. Inversión usada en el cálculo: <b>" + f"{inv_u:,.0f}" + "</b> (catálogo: " + f"{float(inversion_inicial or 0):,.0f}" + ") miles de millones (moneda del emisor)." + ((" " + nota_mp5) if nota_mp5 else ""))}
{result_note("Cómo leer la tabla año a año",
    "<b>FCFF</b> = flujo del año. <b>Factor de descuento</b> = cuánto 'vale' ese peso futuro en pesos de hoy. "
    "<b>PV(FCFF)</b> = flujo ya traído a valor presente. <b>VPN acumulado</b> = si ya recuperaste la inversión "
    "(cuando pasa de negativo a positivo). El gráfico de la derecha muestra ese recorrido.")}
"""
        try:
            guardar_resultado_tab("5", nombre_empresa, {
                "texto": _html_a_texto(resumen, 2000),
                "detalle_anual": _df_a_registros(df_tabla, 12),
            })
        except Exception:
            pass
        return resumen, df_tabla, fig
    except Exception as e:
        return f"<div style='color:#EF4444'>Error: {e}<br>{traceback.format_exc()}</div>", None, None



def _safe_float(x, default=None):
    try:
        if x is None:
            return default
        v = float(x)
        if v != v:
            return default
        return v
    except Exception:
        return default


def _safe_div(a, b, default=np.nan):
    """División segura: evita ZeroDivision y propaga default ante NaN/inf."""
    try:
        b = float(b)
        if not np.isfinite(b) or abs(b) < 1e-12:
            return default
        v = float(a) / b
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _fila_sectorial_desde_emp(nombre, emp):
    """Construye una fila de comparación a partir de un bloque tipo EMPRESAS."""
    short = _nombre_corto(nombre)
    # Etiqueta legible: "Nombre completo (TICKER)" si el display trae "—"
    if nombre and "—" in str(nombre):
        label_emp = f"{str(nombre).split('—')[0].strip()} ({short})"
    else:
        label_emp = short
    hist = pd.DataFrame(emp["historico"]).set_index("Año").sort_index()
    params = emp.get("params", {})
    ticker = emp.get("ticker_yf")

    ing = float(hist["Ingresos"].iloc[-1]) if len(hist) else 0.0
    ebitda = float(hist["EBITDA"].iloc[-1]) if len(hist) and "EBITDA" in hist.columns else 0.0
    fcff = float(hist["FCFF"].iloc[-1]) if len(hist) and "FCFF" in hist.columns else 0.0
    margen = 100.0 * ebitda / ing if ing else 0.0
    if len(hist) >= 4:
        ing0 = float(hist["Ingresos"].iloc[-4])
        g3 = ((ing / ing0) ** (1 / 3) - 1) * 100 if ing0 > 0 else 0.0
    else:
        g3 = 0.0
    nopat = float(hist["NOPAT"].iloc[-1]) if "NOPAT" in hist.columns else ebitda * 0.5
    cap_inv = float(params.get("capital_invertido", nopat / 0.1 if nopat else 1))
    roic = 100.0 * nopat / cap_inv if cap_inv else 0.0
    de = float(params.get("de_ratio", 1.0))
    beta_u = float(params.get("beta_u", 0.55))
    tax = float(params.get("tax", 0.35))
    kd = float(params.get("kd", 0.08))
    beta_l = beta_apalancado(beta_u, de, tax)
    _merc = _codigo_mercado(emp.get("pais"), emp.get("moneda"), ticker)
    capm = CAPM_POR_MERCADO["CO"] if (_merc == "DEFAULT" and not emp.get("pais")) else CAPM_POR_MERCADO[_merc]
    ke = costo_equity_capm(beta_l, rf=capm["rf"], erp=capm["erp"], crp=capm["crp"])
    wacc, _, _ = calcular_wacc(de, kd, ke, tax)
    wacc_pct = 100.0 * wacc

    precio = None
    mcap = None
    ev_ebitda = None
    fuente_mult = "Estimado (sin ticker live)"
    live_ok = False
    mkt = obtener_datos_mercado_bvc(ticker, ticker_bvc=emp.get("ticker_bvc")) if ticker else {"ok": False}

    if mkt.get("ok"):
        precio = mkt.get("precio")
        mcap = mkt.get("market_cap")
        live_ok = True
        try:
            ev_ebitda = _safe_float(mkt.get("enterprise_to_ebitda"))
            if ev_ebitda is None and HAS_YF and ticker:
                info = yf.Ticker(ticker).info or {}
                ev_ebitda = _safe_float(info.get("enterpriseToEbitda"))
                if ev_ebitda is None:
                    ev = _safe_float(info.get("enterpriseValue"))
                    ebitda_yf = _safe_float(info.get("ebitda"))
                    if ev and ebitda_yf and ebitda_yf != 0:
                        ev_ebitda = ev / ebitda_yf
                if ev_ebitda is None and mcap and ebitda > 0:
                    deuda = float(params.get("deuda_neta", 0))
                    mcap_mm = mcap / 1e9
                    ev_ebitda = (mcap_mm + deuda) / ebitda
                    fuente_mult = "Aprox. (MarketCap+deuda neta)/EBITDA histórico"
                elif ev_ebitda is not None:
                    fuente_mult = "Yahoo Finance (enterpriseToEbitda o EV/EBITDA)"
        except Exception as e:
            fuente_mult = f"Mercado parcial ({e})"
    else:
        ev_ebitda = float(params.get("exit_multiple") or 8.0)
        fuente_mult = emp.get("fuente") or "Fallback (sin cotización usable)"

    if ev_ebitda is None or ev_ebitda <= 0:
        ev_ebitda = 8.0
        fuente_mult = "Fallback sectorial"

    row = {
        "Empresa": short,
        "Nombre": label_emp,
        "Ingresos (miles M)": round(ing, 1),
        "EBITDA (miles M)": round(ebitda, 1),
        "Margen EBITDA (%)": round(margen, 1),
        "ROIC (%)": round(roic, 1),
        "WACC estimado (%)": round(wacc_pct, 2),
        "D/E": round(de, 2),
        "EV/EBITDA (x)": round(float(ev_ebitda), 2),
        "Crecimiento Ingresos 3a (%)": round(g3, 1),
        "FCFF (miles M)": round(fcff, 1),
        "Precio": round(precio, 0) if precio else None,
        "Fuente múltiplo": fuente_mult,
        "Sector": emp.get("sector", ""),
    }
    return row, short, fuente_mult, live_ok


def construir_tabla_sectorial_live(nombre_empresa_focal=None):
    """
    Comparación por sector de la empresa en análisis (no el catálogo fijo).

    Orden de construcción:
      1. Empresa focal (siempre)
      2. Mismo sector en catálogo + EMPRESAS_RUNTIME
      3. Peers manuales de la ficha
      4. Peers automáticos PEERS_POR_SECTOR según sector/industry Yahoo
    Si el sector es utilities/energía y no hay suficientes peers, se complementa
    con el catálogo BVC energético. En otro caso el catálogo genérico NO se impone.
    Devuelve (DataFrame, notas_por_empresa, resumen_fuentes)
    """
    rows = []
    notas = {}
    n_live = 0
    n_fund = 0
    seen_short = set()

    focal = resolver_empresa(nombre_empresa_focal) if nombre_empresa_focal else None
    sector_focal = (focal or {}).get("sector", "") or ""
    # industry puede venir embebida en sector como "X / Y"
    industry_focal = ""
    if " / " in sector_focal:
        parts = sector_focal.split(" / ", 1)
        sector_focal_main, industry_focal = parts[0], parts[1]
    else:
        sector_focal_main = sector_focal

    exclude_ticker = (focal or {}).get("ticker_yf")

    def _add_emp(nombre, emp, etiqueta_fuente=""):
        nonlocal n_live, n_fund
        short = _nombre_corto(nombre)
        if short in seen_short:
            return False
        try:
            row, short, fuente_mult, live_ok = _fila_sectorial_desde_emp(nombre, emp)
            seen_short.add(short)
            notas[short] = (fuente_mult + (f" · {etiqueta_fuente}" if etiqueta_fuente else "")).strip(" ·")
            rows.append(row)
            n_fund += 1
            if live_ok:
                n_live += 1
            return True
        except Exception as e:
            notas[short] = f"Error: {e}"
            return False

    def _add_ticker(ticker, etiqueta="peer sector"):
        """Descarga peer (completo o ligero) y lo suma al ranking sectorial."""
        if not ticker or not HAS_YF:
            return False
        short_p = str(ticker).split(".")[0].upper()
        if short_p in seen_short:
            return False
        # 1) Si ya está en runtime, reutilizar
        for nom, emp in list(EMPRESAS_RUNTIME.items()):
            ty = str(emp.get("ticker_yf") or "").upper()
            if ty == str(ticker).upper() or ty.split(".")[0] == short_p or _nombre_corto(nom).upper() == short_p:
                return _add_emp(nom, emp, etiqueta)
        # 2) Descarga completa (histórico + params)
        try:
            ok, _html, disp, _ptup = buscar_y_descargar_empresa(str(ticker), "")
            if ok and disp and disp in EMPRESAS_RUNTIME:
                return _add_emp(disp, EMPRESAS_RUNTIME[disp], etiqueta)
        except Exception as e:
            notas[short_p] = f"Peer falló (full): {e}"
        # 3) Fila ligera solo con info Yahoo (múltiplo / margen aprox.) para no dejar el ranking vacío
        try:
            t = yf.Ticker(str(ticker))
            info = t.info or {}
            long_n = info.get("longName") or info.get("shortName") or short_p
            disp = f"{long_n} — {short_p}"
            sec = info.get("sector") or ""
            ind = info.get("industry") or ""
            ebitda = _safe_float(info.get("ebitda")) or 0.0
            rev = _safe_float(info.get("totalRevenue")) or 0.0
            margen = 100.0 * ebitda / rev if rev else 0.0
            ev_eb = _safe_float(info.get("enterpriseToEbitda"))
            if ev_eb is None:
                ev_eb = 10.0
            beta = _safe_float(info.get("beta")) or 1.0
            row = {
                "Empresa": short_p,
                "Nombre": disp,
                "Ingresos (miles M)": round((rev or 0) / 1e9, 2),
                "EBITDA (miles M)": round((ebitda or 0) / 1e9, 2),
                "Margen EBITDA (%)": round(margen, 1),
                "ROIC (%)": 0.0,
                "WACC estimado (%)": 8.0,
                "D/E": round((_safe_float(info.get("debtToEquity")) or 0) / 100.0, 2) if info.get("debtToEquity") else 0.5,
                "EV/EBITDA (x)": round(float(ev_eb), 2),
                "Crecimiento Ingresos 3a (%)": 0.0,
                "FCFF (miles M)": 0.0,
                "Fuente múltiplo": "Yahoo info (peer ligero)",
                "Sector": f"{sec}" + (f" / {ind}" if ind else ""),
            }
            seen_short.add(short_p)
            notas[short_p] = f"Yahoo ligero · {etiqueta}"
            rows.append(row)
            n_fund += 1
            n_live += 1
            # Registrar mínimo en runtime para reutilizar
            EMPRESAS_RUNTIME[disp] = {
                "ticker_yf": str(ticker).upper(),
                "ticker_bvc": short_p,
                "sector": row["Sector"],
                "params": {"de_ratio": row["D/E"], "kd": 0.06, "tax": 0.25, "g": 0.03, "beta_u": beta / max(1.0 + row["D/E"] * 0.65, 0.5),
                           "capital_invertido": max(row["Ingresos (miles M)"], 1) * 2, "deuda_neta": 0, "inversion_inicial": 0,
                           "caja": 0, "nci": 0, "otros_claims": 0, "asociados": 0, "acciones": 0, "exit_multiple": row["EV/EBITDA (x)"],
                           "moneda": info.get("currency") or "USD"},
                "historico": {"Año": [datetime.now().year - 1], "Ingresos": [row["Ingresos (miles M)"]],
                              "EBITDA": [row["EBITDA (miles M)"]], "EBIT": [row["EBITDA (miles M)"] * 0.8],
                              "FCFF": [0.0], "NOPAT": [0.0], "CAPEX": [0.0], "NWC": [0.0]},
                "peers": [],
            }
            return True
        except Exception as e:
            notas[short_p] = f"Peer falló: {e}"
            return False

    # --- 1) Focal siempre ---
    if focal and nombre_empresa_focal:
        _add_emp(nombre_empresa_focal, focal, "focal")

    # --- 2) Mismo sector ya conocido (catálogo + runtime) ---
    mismo_sector = filtrar_empresas_mismo_sector(sector_focal_main or sector_focal, industry_focal)
    for nombre, emp in mismo_sector.items():
        _add_emp(nombre, emp, "mismo sector")

    # --- 3) Peers manuales ---
    peer_tickers = list((focal or {}).get("peers") or [])
    for pt in peer_tickers:
        _add_ticker(pt, "peer manual")

    # --- 4) Peers automáticos del sector (clave para empresas Yahoo fuera del catálogo BVC) ---
    auto_peers, matched_keys = obtener_tickers_peers_sector(
        sector_focal_main or sector_focal,
        industry_focal,
        exclude_ticker=exclude_ticker,
        max_peers=8,
    )
    if not auto_peers and (sector_focal or industry_focal):
        # Reintento con el blob completo sector+industry
        auto_peers, matched_keys = obtener_tickers_peers_sector(
            f"{sector_focal} {industry_focal}",
            "",
            exclude_ticker=exclude_ticker,
            max_peers=8,
        )
    for pt in auto_peers:
        if len(rows) >= 8:
            break
        _add_ticker(pt, "peer auto-sector")

    # --- 5) Complemento solo si el sector es energía/utilities y faltan comparables ---
    sec_norm = _normalizar_texto_sector(sector_focal)
    es_energia = any(
        k in sec_norm
        for k in (
            "energy", "utilit", "oil", "gas", "electric", "petroleo", "energia",
            "transmision", "renovable", "infraestructura", "generacion",
        )
    )
    if es_energia and len(rows) < 4:
        for nombre, emp in EMPRESAS.items():
            if "Bolsa de Valores" in nombre:
                continue
            short = _nombre_corto(nombre)
            if short.upper() == "BVC":
                continue
            _add_emp(nombre, emp, "catálogo energía")
            if len(rows) >= 7:
                break

    # --- 6) Si aún no hay sector ni peers (empresa sin datos), fallback catálogo ---
    if len(rows) < 2:
        for nombre, emp in EMPRESAS.items():
            if "Bolsa de Valores" in nombre:
                continue
            short = _nombre_corto(nombre)
            if short.upper() == "BVC":
                continue
            _add_emp(nombre, emp, "fallback catálogo")
            if len(rows) >= 6:
                break

    if not rows:
        df = pd.DataFrame(DATOS_SECTOR)
        return df, {}, "Fallback a DATOS_SECTOR estático (sin emisores vivos)."

    df = pd.DataFrame(rows)
    # --- Múltiplos: sin 8x inventado. Los comparables sin cotización usan la MEDIANA robusta del sector ---
    if "Fuente múltiplo" in df.columns:
        vivo = df["Fuente múltiplo"].astype(str).str.startswith(("Yahoo", "Aprox"))
        if vivo.sum() >= 2:
            med_mult = float(np.median(normalizar_atipicos(df.loc[vivo, "EV/EBITDA (x)"].astype(float), reemplazo="mediana")[0]))
            df.loc[~vivo, "EV/EBITDA (x)"] = round(med_mult, 2)
            df.loc[~vivo, "Fuente múltiplo"] = f"Mediana sectorial de comparables con cotización (n={int(vivo.sum())})"
        if len(df) >= 4:
            df["EV/EBITDA (x)"] = normalizar_atipicos(df["EV/EBITDA (x)"].astype(float), reemplazo="mediana")[0].round(2)
    keys_txt = ", ".join(matched_keys) if matched_keys else "sin clave PEERS"
    resumen = (
        f"Comparables del sector de la empresa en análisis ({sector_focal or 'N/D'}). "
        f"Emisores en tabla: {n_fund} · cotización live: {n_live}. "
        f"Claves peers: {keys_txt}. "
        "No se impone el catálogo BVC salvo sector energía/utilities o falta de datos."
    )
    return df, notas, resumen



def _nombre_corto(nombre):
    """Etiqueta corta para ranking: preferir ticker tras '—' si existe (AAPL, EC)."""
    if not nombre:
        return ""
    s = str(nombre).strip()
    if "—" in s:
        der = s.split("—")[-1].strip()
        # ticker típico: AAPL, ISA.CL, BRK-B
        if der and len(der) <= 12 and " " not in der:
            return der.split(".")[0]
        izq = s.split("—")[0].strip()
        return izq.split()[0] if izq else der
    return s.split()[0]


def _z_robusto(s):
    x = pd.to_numeric(s, errors="coerce")
    med = x.median()
    sig = _sigma_mad(x.dropna().values)
    if not np.isfinite(sig) or sig == 0:
        sig = float(x.std(ddof=0)) if len(x.dropna()) > 1 else 0.0
    if not sig or not np.isfinite(sig):
        return pd.Series(0.0, index=x.index)
    return ((x - med) / sig).clip(-3, 3)


def calcular_score_sectorial(df_in):
    """Score compuesto + ranking (única fuente de verdad para pestañas 6 y 7).

    Cada componente se convierte a 0–1 de forma ROBUSTA (no por el máximo, que un solo atípico distorsiona):
      n ≥ 4 : winsorización Hampel + z robusto (mediana/MAD) → CDF normal;
      n < 4 : rango percentil (z robusto no es estimable con tan pocos datos).
    Los crecimientos negativos ya no se recortan a cero: una caída de ingresos penaliza.
    """
    df = df_in.copy()
    n = len(df)

    def comp(col, invertir=False):
        x = pd.to_numeric(df[col], errors="coerce").astype(float)
        x = x.fillna(x.median() if x.notna().any() else 0.0)
        if n >= 4:
            xw, _ = normalizar_atipicos(x, reemplazo="mediana")
            z = _z_robusto(xw)
            z = -z if invertir else z
            return pd.Series(_sps.norm.cdf(z.values), index=df.index)
        if n == 1:
            return pd.Series(0.5, index=df.index)
        r = (-x if invertir else x).rank(method="average")
        return (r - 1) / (n - 1)

    df["Score"] = (
        comp("Margen EBITDA (%)") * 0.25
        + comp("ROIC (%)") * 0.30
        + comp("WACC estimado (%)", invertir=True) * 0.15
        + comp("Crecimiento Ingresos 3a (%)") * 0.15
        + comp("EV/EBITDA (x)", invertir=True) * 0.15
    )
    df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    df["Ranking"] = range(1, len(df) + 1)
    return df


def graficar_ranking_sectorial(ax, df_rank, short, titulo):
    """Barras horizontales del Score; resalta la empresa seleccionada y pone #1 arriba."""
    colores = [COLOR_SUCCESS if str(e).upper() == short.upper() else COLOR_PRIMARY for e in df_rank["Empresa"]]
    barras = ax.barh(df_rank["Empresa"], df_rank["Score"], color=colores)
    ax.invert_yaxis()
    xmax = float(df_rank["Score"].max()) if len(df_rank) else 1.0
    for b, val, rk in zip(barras, df_rank["Score"], df_rank["Ranking"]):
        ax.text(val + xmax * 0.01, b.get_y() + b.get_height() / 2, f"#{int(rk)} · {val:.2f}", va="center", fontsize=8)
    ax.set_xlim(0, xmax * 1.18)
    ax.set_xlabel("Score compuesto")
    ax.set_title(titulo or "Ranking por Score compuesto")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    anotar_grafico(ax, "Ordenado por Score (mayor arriba)\nBarra resaltada = empresa en análisis", loc="lower right")


def tab6_comparacion_sectorial(nombre_empresa):
    try:
        df_raw, notas, resumen_fuentes = construir_tabla_sectorial_live(nombre_empresa_focal=nombre_empresa)
        df = calcular_score_sectorial(df_raw)
        short = _nombre_corto(nombre_empresa)

        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
        ax1 = axes[0]
        x = np.arange(len(df))
        width = 0.35
        ax1.bar(x - width / 2, df["Margen EBITDA (%)"], width, label="Margen EBITDA %", color=COLOR_ACCENT)
        ax1.bar(x + width / 2, df["ROIC (%)"], width, label="ROIC %", color=COLOR_PRIMARY)
        ax1.set_xticks(x)
        _labs = df["Nombre"] if "Nombre" in df.columns else df["Empresa"]
        ax1.set_xticklabels([str(x)[:22] for x in _labs], rotation=15, ha="right", fontsize=8)
        ax1.set_ylabel("%")
        ax1.set_title("Margen operativo vs retorno del capital", fontweight="bold", color=COLOR_PRIMARY)
        ax1.legend()
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        ax2 = axes[1]
        _labs2 = df["Nombre"] if "Nombre" in df.columns else df["Empresa"]
        colors = [COLOR_SUCCESS if str(e).upper() == short.upper() else COLOR_PRIMARY for e in df["Empresa"]]
        bars = ax2.barh([str(x)[:28] for x in _labs2], df["EV/EBITDA (x)"], color=colors)
        ax2.set_xlabel("EV/EBITDA (veces)")
        ax2.set_title("Múltiplo EV/EBITDA (live o estimado)", fontweight="bold", color=COLOR_PRIMARY)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        for bar, val in zip(bars, df["EV/EBITDA (x)"]):
            ax2.text(val + 0.15, bar.get_y() + bar.get_height() / 2, f"{val:.1f}x", va="center", fontsize=9)
        plt.tight_layout()

        top = df.iloc[0]
        isa_like = df[df["Empresa"].str.upper() == short.upper()]
        puesto_txt = ""
        if len(isa_like):
            r = isa_like.iloc[0]
            puesto_txt = (
                f"<p style='margin:8px 0 0 0;color:#FFFFFF !important'>Tu selección ocupa el puesto "
                f"<b style='color:#FFFFFF !important'>#{int(r['Ranking'])}</b> (Score {r['Score']:.2f}).</p>"
            )

        # Notas de fuente por empresa
        notas_html = "".join(
            f"<li style='color:#E8EEF7'><b>{e}</b>: {notas.get(e, 'N/D')}</li>"
            for e in df["Empresa"]
        )

        html = f"""
<div class="dark-card" style="background:linear-gradient(135deg,#0A2540 0%,#1B6CA8 100%);padding:18px 22px;border-radius:12px;margin-bottom:14px">
<h3 style="margin:0 0 8px 0;color:#5EEAD4 !important">Ranking de comparables del mismo sector</h3>
<p style="margin:0;color:#FFFFFF !important">La mejor posicionada según margen, retorno, costo de capital, crecimiento y múltiplo es
<b style="color:#FFFFFF !important">{top['Empresa']}</b> (Score {top['Score']:.2f}).</p>
{puesto_txt}
</div>
{tip("<b>Margen EBITDA alto</b> = de cada peso vendido queda más utilidad. <b>ROIC alto</b> = el capital rinde bien. <b>EV/EBITDA bajo</b> = el mercado paga menos por cada unidad de utilidad (puede verse más atractivo). <b>WACC bajo</b> = el dinero le cuesta menos a la empresa.")}
{result_note("Cómo leer el ranking",
    "El <b>Score</b> combina margen, retorno del capital, costo de capital, crecimiento y múltiplo de mercado. "
    "No es una recomendación de inversión: es una foto comparativa para discutir posiciones relativas entre empresas del sector.")}
{result_note("Fuentes de esta pestaña (ya no es solo tabla fija)", resumen_fuentes)}
<div class="section-card">
<b>Origen del múltiplo EV/EBITDA por empresa</b>
<ul>{notas_html}</ul>
</div>
"""
        # Tabla visible sin columna interna de fuente duplicada si se prefiere
        tabla = df.drop(columns=["Fuente múltiplo"], errors="ignore").copy()
        try:
            guardar_resultado_tab("6", nombre_empresa, {
                "texto": _html_a_texto(html, 2000),
                "ranking": _df_a_registros(tabla, 12),
            })
        except Exception:
            pass
        return html, tabla, fig
    except Exception as e:
        return f"<div style='color:#DC2626'>Error en comparación sectorial: {e}<pre>{traceback.format_exc()}</pre></div>", None, None



def generar_pdf_informe(ruta_pdf, nombre_empresa, datos):
    """
    PDF ejecutivo v2 — dashboard para comité (sin narrativa HTML larga).
    Secciones: decisión, KPIs, escenarios, auditoría, sector, (opcional) extracto comité IA.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    import numpy as np

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloMain", parent=styles["Heading1"],
        fontSize=16, textColor=colors.HexColor("#0A2540"),
        spaceAfter=4, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="Subtitulo", parent=styles["Heading2"],
        fontSize=12, textColor=colors.HexColor("#0F766E"),
        spaceBefore=12, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Cuerpo", parent=styles["Normal"],
        fontSize=9.5, textColor=colors.HexColor("#1E293B"),
        leading=13, alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        name="Simple", parent=styles["Normal"],
        fontSize=9.5, textColor=colors.HexColor("#065F46"),
        backColor=colors.HexColor("#ECFDF5"),
        leading=12, spaceBefore=3, spaceAfter=5,
        leftIndent=3, rightIndent=3,
    ))
    styles.add(ParagraphStyle(
        name="Decision", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor(datos.get("decision_color") or "#0A2540"),
        alignment=TA_CENTER, spaceBefore=6, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Pie", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="KPI", parent=styles["Normal"],
        fontSize=8.5, textColor=colors.HexColor("#0F172A"), leading=11,
    ))
    styles.add(ParagraphStyle(
        name="KPIHeader", parent=styles["Normal"],
        fontSize=8.5, textColor=colors.white, leading=11,
    ))
    styles.add(ParagraphStyle(
        name="Badge", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#0F766E"),
        alignment=TA_CENTER, spaceAfter=6,
    ))

    def _esc(s):
        return (
            str(s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _tbl(data, col_widths):
        flow = []
        for ri, row in enumerate(data):
            flow.append([
                Paragraph(_esc(c), styles["KPIHeader"] if ri == 0 else styles["KPI"])
                for c in row
            ])
        t = Table(flow, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ]))
        return t

    story = []
    # —— Portada corta ——
    story.append(Paragraph("Informe Ejecutivo · Dashboard para Comité", styles["TituloMain"]))
    story.append(Paragraph(f"<b>{_esc(nombre_empresa)}</b>", styles["TituloMain"]))
    story.append(Paragraph(
        f"<b>Versión PDF 2.1</b> · {_esc(datos.get('fecha', ''))} · "
        f"Horizonte {datos.get('horizonte', '—')} años · Drivers + identidad FCFF · "
        f"Sin narrativa HTML completa",
        styles["Badge"],
    ))
    story.append(Paragraph(
        "Documento pedagógico de apoyo a decisión. No es asesoría de inversión ni orden de compra/venta.",
        styles["Pie"],
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F766E")))

    # 1. Decisión
    story.append(Paragraph("1. Decisión del modelo (cuantitativa)", styles["Subtitulo"]))
    story.append(Paragraph(_esc(datos.get("decision", "—")), styles["Decision"]))
    if datos.get("decision_just"):
        story.append(Paragraph(_esc(datos["decision_just"]), styles["Cuerpo"]))
    if datos.get("decision_simple"):
        story.append(Paragraph(
            f"<b>En palabras simples:</b> {_esc(datos['decision_simple'])}",
            styles["Simple"],
        ))
    score = datos.get("score", "—")
    razones = datos.get("razones") or []
    story.append(Paragraph(
        f"Puntaje de viabilidad: <b>{_esc(score)}/7</b>"
        + (f". Razones: {_esc('; '.join(razones))}." if razones else "."),
        styles["Cuerpo"],
    ))

    # 2. KPIs
    story.append(Paragraph("2. Números clave", styles["Subtitulo"]))
    vps = datos.get("vps")
    up = datos.get("upside_pct")
    px = datos.get("precio_mercado")
    vps_s = f"{vps:,.2f}" if vps is not None else "N/D"
    try:
        up_s = f"{float(up):+.1f}%" if up is not None and np.isfinite(float(up)) else "N/D"
    except Exception:
        up_s = "N/D"
    px_s = f"{px:,.2f}" if px is not None else "N/D"
    mon = datos.get("moneda") or ""
    kpi_data = [
        ["Indicador", "Valor", "Qué significa"],
        ["WACC", f"{float(datos.get('wacc') or 0)*100:.2f}%", "Costo promedio del capital"],
        ["g terminal", f"{float(datos.get('g') or 0)*100:.2f}%", "Crecimiento de largo plazo"],
        ["ROIC", f"{float(datos.get('roic') or 0)*100:.2f}%", "Retorno del capital invertido"],
        ["D/E", f"{float(datos.get('de_ratio') or 0):.2f}", "Apalancamiento"],
        ["EV base", f"{float(datos.get('ev_base') or 0):,.0f}", f"Valor del negocio (miles M {mon})"],
        ["Equity base", f"{float(datos.get('equity_base') or 0):,.0f}", "Valor para los dueños"],
        ["VPS modelo", vps_s, "Valor por acción del DCF"],
        ["Precio mercado", px_s, "Última cotización (si hay)"],
        ["Upside %", up_s, "VPS vs precio (solo si misma moneda)"],
        ["VPN proyecto", f"{datos.get('vpn', '—')}", "Valor presente del proyecto"],
        ["TIR / Payback", f"{datos.get('tir', '—')} / {datos.get('payback', '—')}", "Rentabilidad y años de recupero"],
    ]
    story.append(_tbl(kpi_data, [1.5 * inch, 1.4 * inch, 3.3 * inch]))
    story.append(Paragraph(
        "<b>Lectura rápida:</b> si ROIC &gt; WACC el negocio crea valor con estos supuestos; "
        "VPN &gt; 0 y TIR &gt; WACC apuntan a que el proyecto aporta valor en pesos de hoy.",
        styles["Simple"],
    ))

    # 3. Calidad de datos (corto)
    story.append(Paragraph("3. Calidad de datos", styles["Subtitulo"]))
    story.append(Paragraph(
        _esc(datos.get("nota_normalizacion_texto") or "Sin nota de normalización en esta corrida."),
        styles["Cuerpo"],
    ))

    # 4. Gráficos (si hay)
    imgs = datos.get("imagenes") or []
    if imgs:
        story.append(Paragraph("4. Gráficos", styles["Subtitulo"]))
        for titulo, ruta, explicacion in imgs:
            if ruta and os.path.exists(ruta):
                story.append(Paragraph(_esc(titulo), styles["Cuerpo"]))
                try:
                    h = 3.6 * inch if "normalizacion" in str(ruta).lower() or "atipic" in str(titulo).lower() else 2.6 * inch
                    story.append(Image(ruta, width=6.2 * inch, height=h))
                except Exception:
                    story.append(Paragraph("(No se pudo insertar la imagen)", styles["Pie"]))
                if explicacion:
                    story.append(Paragraph(f"<b>Cómo leerlo:</b> {_esc(explicacion)}", styles["Simple"]))
                story.append(Spacer(1, 4))

    # 5. Escenarios
    story.append(Paragraph("5. Escenarios de valoración", styles["Subtitulo"]))
    esc_data = [["Escenario", "WACC %", "g %", "EV", "Equity"]]
    for row in datos.get("escenarios") or []:
        esc_data.append([("—" if x is None or str(x).strip() == "" else str(x)) for x in row])
    if len(esc_data) > 1:
        story.append(_tbl(esc_data, [1.3 * inch, 1.0 * inch, 0.9 * inch, 1.5 * inch, 1.5 * inch]))
    story.append(Paragraph(
        "Pesimista = peores flujos / capital más caro; optimista = lo contrario. "
        "Si solo el optimista se ve bien, la tesis es frágil.",
        styles["Simple"],
    ))

    # 6. Auditoría
    story.append(Paragraph("6. Coherencia de supuestos", styles["Subtitulo"]))
    for prueba, interp in (datos.get("pruebas") or []):
        story.append(Paragraph(f"• <b>{_esc(prueba)}</b>: {_esc(interp)}", styles["Cuerpo"]))
    if not datos.get("pruebas"):
        story.append(Paragraph("Sin pruebas de auditoría en esta corrida.", styles["Cuerpo"]))

    # 7. Sector
    story.append(Paragraph("7. Posición sectorial", styles["Subtitulo"]))
    story.append(Paragraph(
        _esc(datos.get("sector_texto") or "Sin comparación sectorial en esta corrida."),
        styles["Cuerpo"],
    ))

    # 8. Cierre corto (sin veredicto de mercado largo tipo contraste)
    story.append(Paragraph("8. Uso del resultado", styles["Subtitulo"]))
    compra_simple = datos.get("compra_simple") or (
        "Apoyo a discusión de comité; no es una orden de compra o venta."
    )
    story.append(Paragraph(_esc(compra_simple), styles["Simple"]))
    # No incluir el bloque largo de veredicto_mercado / contraste en el PDF v2

    # 9. Extracto Comité IA (estructurado)
    comite_struct = datos.get("comite_ia_struct") or {}
    comite_txt = (datos.get("comite_ia_resumen") or "").strip()
    if not comite_struct and comite_txt:
        try:
            comite_struct = extraer_resumen_comite_ia(comite_txt)
        except Exception:
            comite_struct = {}
    _ct_up = (comite_txt or "").upper().replace("Ó", "O")
    _parece_prompt = (
        "ACTUA COMO UN COMITE" in _ct_up
        or "CONTEXTO DE ENTRADA" in _ct_up
        or ("INSTRUCCIONES Y FORMATO DE SALIDA" in _ct_up and "[...]" in (comite_txt or ""))
    )
    if (not _parece_prompt) and (
        comite_struct.get("ok")
        or (comite_txt and (comite_struct.get("recomendacion") or comite_struct.get("puntaje")))
    ):
        story.append(Paragraph("9. Extracto Comité interdisciplinario (IA)", styles["Subtitulo"]))
        story.append(Paragraph(
            "Solo recomendación, puntaje y hasta 3 puntos de monitoreo. "
            "Complemento narrativo; no sustituye el DCF.",
            styles["Cuerpo"],
        ))
        if comite_struct.get("recomendacion"):
            story.append(Paragraph(
                f"<b>Recomendación final:</b> {_esc(comite_struct['recomendacion'])}",
                styles["Simple"],
            ))
        if comite_struct.get("puntaje"):
            story.append(Paragraph(
                f"<b>Puntaje de viabilidad:</b> {_esc(comite_struct['puntaje'])}",
                styles["Simple"],
            ))
        mons = comite_struct.get("monitoreo") or []
        if mons:
            story.append(Paragraph("<b>Puntos de monitoreo:</b>", styles["Cuerpo"]))
            for i, p in enumerate(mons[:3], 1):
                story.append(Paragraph(f"{i}. {_esc(p)}", styles["Cuerpo"]))
    else:
        story.append(Paragraph("9. Extracto Comité interdisciplinario (IA)", styles["Subtitulo"]))
        story.append(Paragraph(
            "No hay deliberación IA en esta sesión. "
            "Ejecuta el comité en la pestaña 4 y vuelve a generar el informe (pestaña 7) para incluir el extracto.",
            styles["Pie"],
        ))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8")))
    story.append(Paragraph(
        "PDF v2.1 · Dashboard ejecutivo · Generado automáticamente · "
        "Escala típica: miles de millones en la moneda del emisor · "
        "No constituye recomendación de inversión.",
        styles["Pie"],
    ))

    doc.build(story)
    return ruta_pdf



def tab7_informe_ejecutivo(nombre_empresa, archivo, horizonte, de_ratio, kd, tax, g,
                           capex_extra, beta_u, capital_invertido, deuda_neta, inversion_inicial,
                           rf=0.09, erp=0.06, crp=0.0, usar_datos_publicos=True,
                           caja=0, nci=0, otros_claims=0, asociados=0, acciones=None, exit_multiple=0.0, mid_year=True, g_max_macro=0.05):
    """
    Consolida resultados de todas las pestañas, genera HTML + gráficos + PDF descargable.
    """
    try:
        horizonte = int(horizonte)
        capex_extra = float(capex_extra or 0)
        df_hist, mensaje_datos = cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=bool(usar_datos_publicos))
        df_proj = proyectar_variables(df_hist, horizonte, tax=tax).copy()
        df_proj = recalcular_fcff(df_proj, tax=tax, capex_extra=capex_extra)

        beta_l = beta_apalancado(beta_u, de_ratio, tax)
        ke = costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
        wacc, we, wd = calcular_wacc(de_ratio, kd, ke, tax)

        # Escenarios
        escenarios = {}
        g_pes = max(0.005, float(g) - 0.01)
        g_opt = min(float(g) + 0.01, wacc - 0.005) if wacc > 0.02 else float(g)
        acc_res = resolver_acciones_millones(nombre_empresa, acciones)
        bp = params_bridge_desde_ui(deuda_neta, caja, nci, otros_claims, asociados, acc_res, exit_multiple)
        emp_sel = resolver_empresa(nombre_empresa) or {}
        try:
            if (emp_sel.get("params") or {}).get("deuda_es_bruta"):
                bp["deuda_es_bruta"] = True
        except Exception:
            pass
        tk = emp_sel.get("ticker_yf") or ticker_yf_empresa(nombre_empresa)
        mkt = obtener_datos_mercado_bvc(tk, ticker_bvc=emp_sel.get("ticker_bvc")) if tk else {"ok": False}
        precio = mkt.get("precio") if mkt.get("ok") else resolver_precio_mercado(nombre_empresa)
        for nombre, fac, g_e, w_adj in [
            ("Pesimista", 0.75, g_pes, wacc + 0.015),
            ("Base", 1.00, float(g), wacc),
            ("Optimista", 1.25, g_opt, max(wacc - 0.01, 0.06)),
        ]:
            ebitda_out = float(df_proj["EBITDA"].iloc[-1]) * fac if "EBITDA" in df_proj.columns else None
            val = valorar_con_bridge(_escalar_fcff(df_proj["FCFF"].values, fac), w_adj, g_e, bp, ebitda_salida=ebitda_out, precio_mercado=precio, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_proj, fac))
            escenarios[nombre] = val
            escenarios[nombre]["g"] = g_e
            escenarios[nombre]["WACC"] = w_adj

        # Asegurar VPS/upside en todos los escenarios (AAPL y cualquier Yahoo)
        for _k in list(escenarios.keys()):
            escenarios[_k] = forzar_vps_upside(
                escenarios[_k], nombre_empresa, acciones, precio=precio
            )
        # Si aún no hay precio, reintentar
        if precio is None:
            precio = resolver_precio_mercado(nombre_empresa)
            for _k in list(escenarios.keys()):
                escenarios[_k] = forzar_vps_upside(
                    escenarios[_k], nombre_empresa, acciones, precio=precio
                )

        # ROIC / auditoría
        nopat_prom = df_proj["NOPAT"].mean()
        try:
            roic = float(nopat_prom) / capital_base_roic(capital_invertido, nopat_prom)
        except (TypeError, ValueError, ZeroDivisionError):
            roic = float("nan")
        reinv = tasa_reinversion(df_proj["CAPEX"].mean(), df_proj["Depreciacion"].mean(),
                                 df_proj["Delta_NWC"].mean(), nopat_prom)
        g_sost = roic * reinv
        pruebas = []
        if g < wacc:
            pruebas.append(("OK: g < WACC", f"Crecimiento {g*100:.2f}% menor al costo del dinero {wacc*100:.2f}%."))
        else:
            pruebas.append(("Problema: g >= WACC", "El crecimiento de largo plazo no debería superar el costo del dinero."))
        if np.isfinite(roic) and roic > wacc:
            pruebas.append(("OK: crea valor", f"ROIC {roic*100:.2f}% > WACC {wacc*100:.2f}%."))
        elif np.isfinite(roic):
            pruebas.append(("Alerta: no crea valor", f"ROIC {roic*100:.2f}% <= WACC {wacc*100:.2f}%."))
        else:
            pruebas.append(("ROIC no disponible", "Faltan partidas fiables de deuda, patrimonio y efectivo para calcular la base de capital."))
        if de_ratio <= 1.5:
            pruebas.append(("OK: deuda moderada", f"D/E = {de_ratio:.2f}."))
        else:
            pruebas.append(("Alerta: deuda alta", f"D/E = {de_ratio:.2f}."))

        # Recomendación score
        val_base = escenarios["Base"]
        df_ref = df_proj.copy()
        df_ref["CAPEX"] = df_ref["CAPEX"] - capex_extra
        df_ref["FCFF"] = df_ref["NOPAT"] + df_ref["Depreciacion"] - df_ref["CAPEX"] - df_ref["Delta_NWC"]
        val_ref = valorar_con_bridge(df_ref["FCFF"].values, wacc, g, bp, ebitda_salida=float(df_ref["EBITDA"].iloc[-1]) if "EBITDA" in df_ref.columns else None, precio_mercado=precio, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_ref))
        delta_ev = val_base["EV"] - val_ref["EV"]
        riesgo_liq = "Alto" if df_proj["FCFF"].min() < 0 else ("Medio" if df_proj["FCFF"].mean() < 0.03 * df_proj["Ingresos"].mean() else "Bajo")
        score, razones = 0, []
        if g < wacc:
            score += 2; razones.append("crecimiento sostenible")
        else:
            score -= 3; razones.append("crecimiento inconsistente")
        if roic > wacc:
            score += 2; razones.append("la empresa crea valor")
        else:
            score -= 2; razones.append("no supera su costo de capital")
        if de_ratio <= 1.8:
            score += 1; razones.append("deuda aceptable")
        else:
            score -= 2; razones.append("deuda elevada")
        if delta_ev > 1e-9:
            score += 1; razones.append("CAPEX extra agrega valor")
        elif delta_ev < -1e-9:
            score -= 1; razones.append("CAPEX extra reduce valor")
        if riesgo_liq == "Bajo":
            score += 1; razones.append("caja saludable")
        elif riesgo_liq == "Alto":
            score -= 2; razones.append("riesgo de caja")

        # VPN / TIR de proyecto con guardrails (evita TIR de decenas de miles de %)
        fcff_vals = df_proj["FCFF"].values.tolist()
        mp = metricas_proyecto_robustas(
            fcff_vals, wacc,
            inversion_inicial=inversion_inicial,
            capital_invertido=capital_invertido,
        )
        vpn = mp["vpn"]
        tir = mp["tir"]
        tir_str = mp["tir_str"]
        payback = mp["payback"]
        payback_str = mp["payback_str"]
        cashflows = mp["cashflows"]
        # Si la TIR de proyecto no es creíble, el KPI ejecutivo usa métricas de FIRMA
        # (MVA / TIR implícita con capital invertido + TV), no el proyecto con inversión ilustrativa.
        _vpn_f, _tir_f = metricas_valor_firma(fcff_vals, capital_invertido, val_base)
        if tir is None and _vpn_f is not None:
            vpn = float(_vpn_f)
            tir = _tir_f
            tir_str = f"{_tir_f*100:.2f}%" if _tir_f is not None else "N/D"
            payback_str = "N/D (usar capital de firma)"

        # Escenario pesimista para el mismo motor de gobernanza que la pestaña 4
        g_pes_m = max(0.005, float(g) - 0.01)
        val_pes = valorar_con_bridge(
            _escalar_fcff(df_proj["FCFF"].values, 0.75),
            wacc + 0.015,
            g_pes_m,
            bp,
            ebitda_salida=(float(df_proj["EBITDA"].iloc[-1]) * 0.75 if "EBITDA" in df_proj.columns else None),
            precio_mercado=precio,
            mid_year=bool(mid_year),
            g_max_macro=float(g_max_macro),
            nopat_final=_nopat_final(df_proj, 0.75),
        )
        prov = procedencia_datos(mensaje_datos, ticker_yf=tk, mkt=mkt)

        # ÚNICA fuente de decisión: motor_decision_institucional (alineado con pestaña 4)
        vpn_firma, tir_firma = metricas_valor_firma(df_proj["FCFF"].values, capital_invertido, val_base)
        mon_modelo, mon_precio = monedas_alineadas_por_ticker(
            ticker=(resolver_empresa(nombre_empresa) or {}).get('ticker_yf') or (resolver_empresa(nombre_empresa) or {}).get('ticker_bvc'),
            nombre_empresa=nombre_empresa,
            emp=resolver_empresa(nombre_empresa) or {},
        )
        motor = motor_decision_institucional(
            wacc=wacc,
            g=float(g),
            roic=roic,
            de_ratio=float(de_ratio),
            vpn=vpn_firma,
            tir=tir_firma,
            payback=None,
            tv_pct=val_base.get("tv_pct_ev"),
            mult_terminal=val_base.get("mult_terminal"),
            ev_base=val_base["EV"],
            equity_base=val_base["Equity_Value"],
            equity_pesimista=val_pes.get("Equity_Value"),
            delta_ev_capex=delta_ev,
            riesgo_liq=riesgo_liq,
            procedencia=prov,
            score_heuristico=score,
            precio_mercado=precio,
            equity_por_accion=val_base.get("value_per_share"),
            moneda_modelo=mon_modelo,
            moneda_precio=mon_precio,
        )
        decision = motor["decision"]
        dcolor = motor["color"]
        decision_just = motor["sesgo"]
        contraste7 = modulo_ia_contraste_decision(
            nombre_empresa=nombre_empresa,
            motor=motor,
            wacc=wacc,
            g=float(g),
            roic=roic,
            equity_base=val_base.get("Equity_Value"),
            ev_base=val_base.get("EV"),
            de_ratio=float(de_ratio),
            procedencia=prov,
            ticker_yf=tk,
            precio_modelo=precio,
            upside_modelo_pct=val_base.get("upside_pct"),
        )
        vm7 = contraste7.get("veredicto_mercado") or {}
        veredicto_mercado_txt = vm7.get("texto_plano") or ""
        # Textos del informe derivados del mismo veredicto
        if "RECALIBRAR" in decision.upper() or "VETO" in decision.upper():
            decision_simple = (
                "El modelo activó un veto de calidad con los supuestos actuales: es un control interno, "
                "no un rating de la acción. Revisa g vs WACC, equity bridge y calidad de datos."
            )
            compra_simple = (
                "Recalibrar el modelo (vetos listados en la pestaña 4) antes de sacar conclusiones de inversión; "
                "el veto no equivale a recomendar vender ni a no invertir."
            )
        elif "EVITAR" in decision.upper() or "REVISAR" in decision.upper():
            decision_simple = "Hay demasiadas alertas frente a los soportes; conviene revisar antes de decidir."
            compra_simple = "No aprobar a ciegas: alinea supuestos y datos auditados."
        elif "FAVORABLE" in decision.upper() or "POSITIVO" in decision.upper():
            decision_simple = "Los números del modelo son coherentes; aun así valida cifras oficiales y mandato."
            compra_simple = "Sesgo favorable condicionado a validación de datos y límites de riesgo."
        else:
            decision_simple = "Resultado neutral/monitoreo: no hay sesgo de compra firme en el modelo."
            compra_simple = "Mantener vigilancia; no interpreta esto como orden de compra en bolsa."
        payback_str = f"{payback:.1f} años" if payback is not None else "N/D"

        # Ranking sectorial (misma tabla viva y mismo score que la pestaña 6)
        short = _nombre_corto(nombre_empresa)
        try:
            df_raw_s, _notas_s, resumen_fuentes_s = construir_tabla_sectorial_live(
                nombre_empresa_focal=nombre_empresa
            )
            fuente_sector = resumen_fuentes_s or "tabla sectorial en vivo (misma lógica que pestaña 6)"
        except Exception as e_sec:
            df_raw_s, resumen_fuentes_s = df_sector.copy(), f"tabla estática de respaldo ({e_sec})"
            fuente_sector = f"tabla estática de respaldo (error en vivo: {e_sec})"
        df_s = calcular_score_sectorial(df_raw_s)
        n_emp = len(df_s)
        lider = df_s.iloc[0]
        # Match por nombre corto, ticker o contención (Apple / AAPL)
        emp_up = df_s["Empresa"].astype(str).str.upper()
        short_up = short.upper()
        match = df_s[emp_up == short_up]
        if match.empty and short_up:
            match = df_s[emp_up.str.contains(short_up, na=False) | emp_up.apply(lambda x: short_up in str(x))]
        if match.empty:
            # intentar ticker de la ficha
            tk_m = (emp_sel.get("ticker_yf") or "").split(".")[0].upper()
            if tk_m:
                match = df_s[emp_up == tk_m]
        if len(match):
            m = match.iloc[0]
            if int(m["Ranking"]) == 1:
                segundo = df_s.iloc[1]["Empresa"] if n_emp > 1 else "—"
                sc2 = df_s.iloc[1]["Score"] if n_emp > 1 else 0
                sector_texto = (
                    f"{m['Empresa']} lidera el ranking de comparables del mismo sector "
                    f"(puesto #1 de {n_emp}, Score {m['Score']:.2f}). "
                    f"Le sigue {segundo} (Score {sc2:.2f})."
                )
            else:
                sector_texto = (
                    f"{m['Empresa']} ocupa el puesto #{int(m['Ranking'])} de {n_emp} entre comparables del sector "
                    f"(Score {m['Score']:.2f}). El líder es {lider['Empresa']} (Score {lider['Score']:.2f})."
                )
        else:
            lista = ", ".join(df_s["Empresa"].astype(str).head(8).tolist())
            sector_texto = (
                f"La empresa en análisis ({short or nombre_empresa}) no apareció etiquetada en el ranking "
                f"({n_emp} comparables: {lista}). "
                f"Líder provisional: {lider['Empresa']} (Score {lider['Score']:.2f}). "
                f"Vuelve a descargar el ticker o indica peers manuales."
            )
        sector_texto += f" Fuente: {fuente_sector}."

        vetos_txt = "; ".join(motor.get("vetos") or []) or "ninguno"
        alertas_txt = "; ".join(motor.get("alertas") or []) or "ninguna"
        compra_texto = (
            f"La decisión de comité del modelo es <b>{decision}</b> "
            f"(misma lógica que la pestaña 4 · score heurístico auxiliar {score}/7). "
            f"Vetos: {vetos_txt}. Alertas: {alertas_txt}. "
            f"VPN del proyecto = {vpn:,.1f}; TIR = {tir_str} frente a WACC {wacc*100:.2f}%. "
            f"ROIC proyectado {roic*100:.1f}% vs WACC {wacc*100:.1f}%. "
            "No constituye orden de compra en bolsa ni asesoría de inversión."
        )
        if vm7.get("frase"):
            compra_texto += f" <b>Lectura del mercado:</b> {vm7['frase']}"

        # ---- Gráficos para el informe ----
        tmpdir = tempfile.mkdtemp(prefix="informe_isa_")
        img_paths = []

        # Fan / proyección FCFF
        fig1, ax = plt.subplots(figsize=(9, 4))
        ax.plot(df_hist.index.astype(int), df_hist["FCFF"], "o-", color=COLOR_PRIMARY, lw=2.2, label="Histórico")
        ax.plot(df_proj.index.astype(int), df_proj["FCFF"], "s--", color=COLOR_ACCENT, lw=2.2, label="Proyectado")
        ax.axhline(0, color="#94A3B8", ls=":")
        ax.set_title("Dinero libre (FCFF): historia y proyección")
        ax.set_ylabel("Miles de millones (moneda del emisor)")
        ax.legend()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        p1 = os.path.join(tmpdir, "fcff.png")
        fig1.tight_layout()
        fig1.savefig(p1, dpi=120, facecolor="white")
        plt.close(fig1)
        img_paths.append((
            "Gráfico A — Flujo de caja libre",
            p1,
            "La línea continua es lo que ya ocurrió; la punteada es lo que el modelo espera. "
            "Si la proyección cae cerca de cero o es negativa, hay más presión de caja."
        ))

        # Escenarios EV/Equity
        fig2, ax = plt.subplots(figsize=(9, 4))
        x = np.arange(3)
        width = 0.35
        evs = [escenarios[k]["EV"] for k in ("Pesimista", "Base", "Optimista")]
        eqs = [escenarios[k]["Equity_Value"] for k in ("Pesimista", "Base", "Optimista")]
        ax.bar(x - width/2, evs, width, label="Valor empresa (EV)", color=COLOR_ACCENT)
        ax.bar(x + width/2, eqs, width, label="Valor dueños (Equity)", color=COLOR_PRIMARY)
        ax.set_xticks(x)
        ax.set_xticklabels(["Pesimista", "Base", "Optimista"])
        ax.set_title("Valoración bajo tres escenarios")
        ax.legend()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        p2 = os.path.join(tmpdir, "escenarios.png")
        fig2.tight_layout()
        fig2.savefig(p2, dpi=120, facecolor="white")
        plt.close(fig2)
        img_paths.append((
            "Gráfico B — Escenarios de valor",
            p2,
            "Compara un futuro malo, normal y bueno. Si incluso el pesimista se ve razonable, hay más margen de seguridad."
        ))

        # VPN path
        fig3, ax = plt.subplots(figsize=(9, 4))
        vpn_acum = []
        running = -abs(inversion_inicial)
        vpn_acum.append(running)
        for i, fcff in enumerate(fcff_vals):
            running += fcff / ((1 + wacc) ** (i + 1))
            vpn_acum.append(running)
        ax.plot(range(len(vpn_acum)), vpn_acum, "o-", color=COLOR_PRIMARY, lw=2.2)
        ax.axhline(0, color="#94A3B8", ls="--")
        ax.fill_between(range(len(vpn_acum)), vpn_acum, 0,
                        where=np.array(vpn_acum) >= 0, color=COLOR_SUCCESS, alpha=0.25)
        ax.fill_between(range(len(vpn_acum)), vpn_acum, 0,
                        where=np.array(vpn_acum) < 0, color=COLOR_DANGER, alpha=0.25)
        ax.set_title("Recuperación del valor del proyecto (VPN acumulado)")
        ax.set_xlabel("Periodo (t=0 es la inversión inicial)")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        p3 = os.path.join(tmpdir, "vpn.png")
        fig3.tight_layout()
        fig3.savefig(p3, dpi=120, facecolor="white")
        plt.close(fig3)
        img_paths.append((
            "Gráfico C — Recuperación del proyecto",
            p3,
            "Empieza negativo (inversión). Cuando cruza cero, el proyecto ya recuperó el valor en pesos de hoy."
        ))

        # Sector bars
        fig4, ax = plt.subplots(figsize=(9, 4))
        graficar_ranking_sectorial(ax, df_s, short, f"Ranking sectorial · {short} resaltada (mayor = mejor)")
        p4 = os.path.join(tmpdir, "sector.png")
        fig4.tight_layout()
        fig4.savefig(p4, dpi=120, facecolor="white")
        plt.close(fig4)
        img_paths.append((
            "Gráfico D — Ranking del sector",
            p4,
            "Combina margen, retorno, costo de capital, crecimiento y múltiplo. La barra verde es la empresa analizada. Es una foto relativa, no una orden de compra."
        ))

        # E — Normalización de atípicos (solo si aplica; cualquier emisor)
        nota_norm, fig_norm = reporte_normalizacion_atipicos(
            df_hist, {"metodo": "Informe ejecutivo · drivers del histórico"}
        )
        if fig_norm is not None:
            p_norm = os.path.join(tmpdir, "normalizacion_atipicos.png")
            fig_norm.savefig(p_norm, dpi=120, facecolor="white", bbox_inches="tight")
            plt.close(fig_norm)
            img_paths.append((
                "Gráfico E — Normalización de atípicos (original vs tratado)",
                p_norm,
                "Izquierda: serie original del driver (atípicos marcados). Derecha: tras Hampel "
                "(mediana ± 3,5·MAD) con winsorización. Se aplica para que un año extremo no sesgue "
                "la proyección FCFF. Válido para catálogo, Yahoo y Excel."
            ))
        else:
            nota_norm = ""

        # PDF
        _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(
            tmpdir, f"Informe_Ejecutivo_v21_{short}_{_ts}.pdf".replace(" ", "_")
        )
        vps = val_base.get("value_per_share")
        upside = val_base.get("upside_pct")
        datos_pdf = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "horizonte": horizonte,
            "decision": decision,
            "decision_color": dcolor,
            "decision_just": decision_just,
            "decision_simple": decision_simple,
            "score": score,
            "razones": list(dict.fromkeys(razones)),
            "wacc": wacc,
            "g": g,
            "roic": roic,
            "de_ratio": de_ratio,
            "ev_base": val_base["EV"],
            "eq_base": val_base["Equity_Value"],
            "eq_pes": escenarios["Pesimista"]["Equity_Value"],
            "eq_opt": escenarios["Optimista"]["Equity_Value"],
            "vps": vps,
            "upside_pct": upside,
            "precio_mercado": precio,
            "moneda": mon_modelo,
            "vpn": vpn,
            "tir_str": tir_str,
            "payback_str": payback_str,
            "fcff_prom": float(df_proj["FCFF"].mean()),
            "escenarios": [
                [k, f"{escenarios[k]['WACC']*100:.2f}", f"{escenarios[k]['g']*100:.2f}",
                 f"{escenarios[k]['EV']:,.0f}", f"{escenarios[k]['Equity_Value']:,.0f}"]
                for k in ("Pesimista", "Base", "Optimista")
            ],
            "pruebas": pruebas,
            "sector_texto": sector_texto,
            "compra_texto": compra_texto.replace("<b>", "").replace("</b>", ""),
            "compra_simple": compra_simple,
            "veredicto_mercado": veredicto_mercado_txt,
            "veredicto_mercado_etiqueta": vm7.get("etiqueta", ""),
            "veredicto_mercado_color": vm7.get("color", "#64748B"),
            "imagenes": img_paths,
            "hubo_normalizacion": bool(nota_norm),
            "nota_normalizacion_texto": (
                "Se detectaron y trataron valores atípicos en drivers del histórico "
                "(Hampel + winsorización). Ver gráfico E y la nota en el informe HTML."
                if nota_norm else
                "No se requirió normalización de atípicos en los drivers del histórico usado."
            ),
            "comite_ia_resumen": (
                ((RESULTADOS_SESION.get("tabs") or {}).get("comite_ia") or {}).get("texto")
                if (RESULTADOS_SESION.get("empresa") in (None, nombre_empresa)
                    or str(RESULTADOS_SESION.get("empresa")) == str(nombre_empresa))
                else None
            ),
            "comite_ia_struct": (
                ((RESULTADOS_SESION.get("tabs") or {}).get("comite_ia") or {}).get("struct")
                if (RESULTADOS_SESION.get("empresa") in (None, nombre_empresa)
                    or str(RESULTADOS_SESION.get("empresa")) == str(nombre_empresa))
                else None
            ),
        }
        try:
            generar_pdf_informe(pdf_path, nombre_empresa, datos_pdf)
            pdf_ok = True
            pdf_msg = "PDF listo para descargar."
        except Exception as e_pdf:
            pdf_ok = False
            pdf_path = None
            pdf_msg = f"No se pudo generar el PDF ({e_pdf}). Revisa que reportlab esté instalado."

        # HTML preview
        html = f"""
<div class="dark-card" style="background:linear-gradient(135deg,#0A2540 0%,#1B6CA8 100%);padding:22px;border-radius:14px;margin-bottom:16px">
  <h2 style="margin:0 0 6px 0;color:#5EEAD4 !important">Informe ejecutivo · {nombre_empresa}</h2>
  <p style="margin:0;color:#FFFFFF !important">Resumen de todas las pestañas · {datos_pdf['fecha']}</p>
</div>
<div style="background:#151C2C;border:3px solid {dcolor};border-radius:12px;padding:16px 20px;margin-bottom:14px">
  <h3 style="margin:0;color:{dcolor};font-size:22px">{decision}</h3>
  <p style="margin:8px 0 0 0;color:#E8EEF7"><b>Puntaje:</b> {score}/7</p>
  <p style="margin:6px 0 0 0;color:#E2E8F0">{decision_just}</p>
</div>
{tip(decision_simple)}
{nota_norm}
{result_note("¿Esto es una orden de compra?",
    compra_simple + " El modelo es pedagógico: usa supuestos y series de respaldo. No reemplaza due diligence ni asesoría profesional.")}
<!-- contraste retirado del informe HTML v2 -->
<div class="section-card">
<b>Números clave</b>
<ul style="color:#E8EEF7;line-height:1.6">
<li><b>WACC:</b> {wacc*100:.2f}% · <b>g:</b> {g*100:.2f}% · <b>ROIC:</b> {roic*100:.2f}%</li>
<li><b>EV base:</b> {val_base['EV']:,.0f} · <b>Equity base:</b> {val_base['Equity_Value']:,.0f} (miles M · moneda del emisor)</li>
<li><b>VPN proyecto:</b> {vpn:,.1f} · <b>TIR:</b> {tir_str} · <b>Payback:</b> {payback_str}</li>
<li><b>FCFF promedio proyectado:</b> {df_proj['FCFF'].mean():,.0f}</li>
<li><b>Método de proyección:</b> Drivers + identidad FCFF (el mismo de las pestañas 2 a 5; el selector de la pestaña 1 solo aplica a esa pestaña)</li>
<li><b>Datos:</b> {mensaje_datos}</li>
</ul>
</div>
{result_note("Cómo leer estos números",
    "Si ROIC > WACC la empresa crea valor. Si VPN > 0 y TIR > WACC el proyecto aporta valor en pesos de hoy. "
    "El payback solo dice cuándo se recupera la plata, no si el proyecto es bueno por sí solo.")}
<div class="section-card">
<b>Auditoría rápida</b>
<ul style="color:#E8EEF7">{''.join(f'<li><b>{p}</b> — {i}</li>' for p,i in pruebas)}</ul>
</div>
<div class="section-card">
<b>Sector</b>
<p style="color:#E8EEF7;margin:0">{sector_texto}</p>
</div>
{tip("Los gráficos de abajo resumen la historia: (A) caja libre proyectada, (B) valor en tres futuros, "
     "(C) cuándo el proyecto recupera valor y (D) ranking sectorial. El PDF incluye el mismo contenido listo para compartir.")}
<p style="color:#E8EEF7;font-weight:600">{pdf_msg}</p>
"""
        # Figura combinada para la UI
        fig_ui, axes = plt.subplots(2, 2, figsize=(12, 8))
        axes = axes.ravel()
        # A
        axes[0].plot(df_hist.index.astype(int), df_hist["FCFF"], "o-", color=COLOR_PRIMARY, label="Histórico")
        axes[0].plot(df_proj.index.astype(int), df_proj["FCFF"], "s--", color=COLOR_ACCENT, label="Proyectado")
        axes[0].set_title("A) FCFF")
        axes[0].legend(fontsize=8)
        axes[0].spines["top"].set_visible(False)
        axes[0].spines["right"].set_visible(False)
        # B
        axes[1].bar(x - width/2, evs, width, label="EV", color=COLOR_ACCENT)
        axes[1].bar(x + width/2, eqs, width, label="Equity", color=COLOR_PRIMARY)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(["Pesim.", "Base", "Optim."])
        axes[1].set_title("B) Escenarios")
        axes[1].legend(fontsize=8)
        axes[1].spines["top"].set_visible(False)
        axes[1].spines["right"].set_visible(False)
        # C
        axes[2].plot(range(len(vpn_acum)), vpn_acum, "o-", color=COLOR_PRIMARY)
        axes[2].axhline(0, color="#94A3B8", ls="--")
        axes[2].set_title("C) VPN acumulado")
        axes[2].spines["top"].set_visible(False)
        axes[2].spines["right"].set_visible(False)
        # D
        graficar_ranking_sectorial(axes[3], df_s, short, "D) Ranking sectorial")
        fig_ui.suptitle(f"Resumen gráfico · {nombre_empresa}", fontweight="bold", color=COLOR_PRIMARY)
        fig_ui.tight_layout()

        vps_txt = f"{vps:,.2f}" if vps is not None and np.isfinite(float(vps)) else "N/D"
        up_txt = f"{float(upside):+.1f}%" if upside is not None and np.isfinite(float(upside)) else "N/D"
        px_txt = f"{precio:,.2f}" if precio is not None else "N/D"
        resumen_tabla = pd.DataFrame({
            "Indicador": [
                "Decisión", "Puntaje", "WACC %", "ROIC %", "D/E",
                "EV base", "Equity base", "Equity pesimista", "Equity optimista",
                "VPS modelo", "Precio mercado", "Upside %",
                "VPN proyecto", "TIR", "Payback", "FCFF prom. proy.",
            ],
            "Valor": [
                decision, f"{score}/7", f"{wacc*100:.2f}", f"{roic*100:.2f}", f"{de_ratio:.2f}",
                f"{val_base['EV']:,.0f}", f"{val_base['Equity_Value']:,.0f}",
                f"{escenarios['Pesimista']['Equity_Value']:,.0f}",
                f"{escenarios['Optimista']['Equity_Value']:,.0f}",
                vps_txt, px_txt, up_txt,
                f"{vpn:,.1f}", tir_str, payback_str, f"{df_proj['FCFF'].mean():,.0f}",
            ],
            "Lectura sencilla": [
                decision_simple,
                "Suma de criterios de viabilidad (máx. 7)",
                "Costo promedio del capital (deuda + equity)",
                "Rendimiento del capital invertido",
                "Deuda por cada unidad de patrimonio",
                "Enterprise Value · escenario base",
                "Valor para accionistas · base",
                "Equity en escenario adverso",
                "Equity en escenario favorable",
                "Valor por acción del modelo",
                "Último precio de mercado (si hay)",
                "VPS vs precio (si monedas alineadas)",
                "VPN del proyecto con inversión inicial",
                "Rentabilidad anual implícita del proyecto",
                "Años para recuperar la inversión",
                "Dinero libre promedio esperado por año",
            ],
        })

        try:
            guardar_resultado_tab("7", nombre_empresa, {
                "texto": _html_a_texto(html, 2200),
                "kpis": _df_a_registros(resumen_tabla, 15),
                "pdf_generado": bool(pdf_ok),
            })
        except Exception:
            pass
        return html, resumen_tabla, fig_ui, pdf_path if pdf_ok else None

    except Exception as e:
        return (
            f"<div style='color:#DC2626;background:#FEF2F2;padding:14px;border-radius:10px'>"
            f"<b>Error al generar el informe:</b> {e}<br><pre style='font-size:11px;color:#7F1D1D'>{traceback.format_exc()}</pre></div>",
            None, None, None
        )




# Rangos de los sliders de la UI (mín, máx). Evita "Value X is less than minimum".
_UI_RANGOS = {
    "de_ratio": (0.0, 5.0),
    "kd": (0.0, 0.25),
    "tax": (0.0, 0.50),
    "g": (0.0, 0.08),
    "beta_u": (0.0, 3.0),
    "capital_invertido": (0.0, 500000.0),
    "deuda_neta": (-50000.0, 300000.0),
    "inversion_inicial": (0.0, 100000.0),
    "caja": (0.0, 200000.0),
    "nci": (0.0, 100000.0),
    "otros_claims": (0.0, 100000.0),
    "asociados": (0.0, 100000.0),
    "exit_multiple": (0.0, 40.0),
}


def _clamp_param(key, value, default=None):
    """Acota un parámetro al rango del control Gradio correspondiente."""
    if value is None:
        return default
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if key in _UI_RANGOS:
        lo, hi = _UI_RANGOS[key]
        if v < lo:
            v = lo
        if v > hi:
            v = hi
    return v


def _params_para_ui(p):
    """Rellena sliders. Si el origen es blanco/derivado, no inyecta defaults del catálogo."""
    origen = (p or {}).get("origen_params", "catalogo")
    # Defaults solo si faltaba la clave; preferir 0 para no arrastrar ISA
    return (
        _clamp_param("de_ratio", p.get("de_ratio"), 0.0),
        _clamp_param("kd", p.get("kd"), 0.0),
        _clamp_param("tax", p.get("tax"), 0.0),
        _clamp_param("g", p.get("g"), 0.0),
        _clamp_param("beta_u", p.get("beta_u"), 0.0),
        _clamp_param("capital_invertido", p.get("capital_invertido"), 0.0),
        _clamp_param("deuda_neta", p.get("deuda_neta"), 0.0),
        _clamp_param("inversion_inicial", p.get("inversion_inicial"), 0.0),
        _clamp_param("caja", p.get("caja", 0), 0.0),
        _clamp_param("nci", p.get("nci", 0), 0.0),
        _clamp_param("otros_claims", p.get("otros_claims", 0), 0.0),
        _clamp_param("asociados", p.get("asociados", 0), 0.0),
        p.get("acciones"),
        _clamp_param("exit_multiple", p.get("exit_multiple"), 0.0),
    )


def _capm_para_ui(p):
    """rf, erp, crp, g_max_macro según el mercado de la empresa.
    Catálogo BVC → anclas CO. Empresas Yahoo/derivadas → usan p['rf']/erp del CAPM_POR_MERCADO.
    Fallback residual: DEFAULT (no Colombia) para no contaminar AAPL/US con rf=12 %.
    """
    p = p or {}
    origen = p.get("origen_params", "catalogo")
    if origen in ("catalogo",) and p.get("rf") is None:
        return (0.12, 0.055, 0.0, 0.04)
    # Preferir valores ya derivados; si faltan, DEFAULT global (no CO)
    _def = CAPM_POR_MERCADO.get("DEFAULT", {"rf": 0.05, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.04})
    return (
        float(p.get("rf") if p.get("rf") is not None else _def["rf"]),
        float(p.get("erp") if p.get("erp") is not None else _def["erp"]),
        float(p.get("crp") if p.get("crp") is not None else _def.get("crp", 0.0)),
        float(p.get("g_max_macro") if p.get("g_max_macro") is not None else _def.get("g_max_macro", 0.04)),
    )


def al_cambiar_empresa(nombre_empresa):
    if nombre_empresa in _EMPRESAS_CATALOGO_INMUTABLE:
        _restaurar_entrada_catalogo(nombre_empresa)
    emp = resolver_empresa(nombre_empresa)
    if emp:
        aplicar_monedas_a_empresa(nombre_empresa, emp)
    p = params_empresa(nombre_empresa)
    tk = ticker_canonico_empresa(nombre_empresa)
    if tk:
        p = dict(p)
        p["ticker_yf"] = tk
        mm, mp = monedas_alineadas_por_ticker(tk, nombre_empresa, emp or {})
        p["moneda"] = mm
        p["precio_moneda"] = mp
        if emp is not None:
            emp["ticker_yf"] = tk
    card = card_empresa_seleccionada(nombre_empresa)
    # Si es catálogo y no trae rf, anotar mercado CO en params para UI
    if p.get("origen_params") == "catalogo" or (nombre_empresa in EMPRESAS and "rf" not in p):
        p = dict(p)
        p.setdefault("rf", 0.12)
        p.setdefault("erp", 0.055)
        p.setdefault("crp", 0.0)
        p.setdefault("g_max_macro", 0.04)
        p.setdefault("mercado_capm", "CO")
    return (card,) + _params_para_ui(p) + _capm_para_ui(p)


def ui_buscar_empresa(ticker_query, peers_query):
    """Handler Gradio: descarga ticker y actualiza ficha, params operativos y CAPM del mercado."""
    ok, html, display_name, params_tuple = buscar_y_descargar_empresa(ticker_query, peers_query or "")
    choices = listar_empresas_disponibles()
    if not ok or not display_name:
        empty_params = [None] * 18  # 14 operativos + 4 CAPM (Streamlit-safe)
        return (html, _upd(choices=choices), _upd()) + tuple(empty_params)
    reset_resultados_sesion(display_name)
    p = params_empresa(display_name)
    card = card_empresa_seleccionada(display_name)
    merc = p.get("mercado_capm", "")
    extra = ""
    if merc:
        extra = (
            f"<div class='section-card'><b>CAPM ajustado al mercado {merc}</b>: "
            f"rf={p.get('rf',0)*100:.1f}%, ERP={p.get('erp',0)*100:.1f}%, "
            f"g terminal={p.get('g',0)*100:.1f}% (no se usa el CAGR histórico como perpetuidad). "
            f"β fuente: {p.get('beta_fuente','N/D')}.</div>"
        )
    # La ficha completa va SOLO a ficha_empresa (evita duplicar el bloque en out_buscar)
    return (
        html + extra,
        _upd(choices=choices, value=display_name),
        card,
    ) + _params_para_ui(p) + _capm_para_ui(p)



def _show_outputs(*values):
    """Tras ejecutar una pestaña, muestra los componentes de resultado (antes ocultos)."""
    out = []
    for v in values:
        if isinstance(v, dict) and "visible" in v:
            out.append(v)
        else:
            out.append(_upd(value=v, visible=True))
    return tuple(out) if len(out) != 1 else out[0]


CUSTOM_CSS = """
/* ============================================================
   TERMINAL FINTECH · Gradio visual system
   Densidad alta · contraste WCAG · jerarquía Bloomberg-like
   ============================================================ */
:root {
  color-scheme: light dark;
  --tf-bg: #0B1220;
  --tf-bg-elev: #111827;
  --tf-surface: #151C2C;
  --tf-surface-2: #1A2336;
  --tf-border: #243044;
  --tf-border-soft: #1E293B;
  --tf-ink: #E8EEF7;
  --tf-ink-2: #CBD5E1;
  --tf-muted: #94A3B8;
  --tf-accent: #14B8A6;
  --tf-accent-2: #0D9488;
  --tf-primary: #3B82F6;
  --tf-risk: #F59E0B;
  --tf-danger: #EF4444;
  --tf-ok: #22C55E;
  --tf-radius: 10px;
  --tf-shadow: 0 1px 0 rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.35);
  --tf-font: "Inter", "Segoe UI", system-ui, sans-serif;
}

/* Fondo general de la app */
.gradio-container {
  font-family: var(--tf-font) !important;
  background: radial-gradient(1200px 600px at 10% -10%, #132033 0%, var(--tf-bg) 55%) !important;
  color: var(--tf-ink) !important;
  max-width: 1280px !important;
  margin: 0 auto !important;
  padding-bottom: 2rem !important;
}

.gradio-container .main,
.gradio-container .contain,
.gradio-container .wrap {
  background: transparent !important;
}

/* Tipografía base */
.gradio-container h1, .gradio-container h2, .gradio-container h3 {
  letter-spacing: -0.02em;
  color: var(--tf-ink) !important;
}
.gradio-container label,
.gradio-container .label-wrap span {
  color: var(--tf-ink-2) !important;
  font-weight: 600 !important;
  font-size: 0.82rem !important;
}

/* Bloques / paneles */
.gradio-container .block {
  background: var(--tf-surface) !important;
  border: 1px solid var(--tf-border-soft) !important;
  border-radius: var(--tf-radius) !important;
  box-shadow: none !important;
  padding: 0.35rem 0.5rem !important;
}
.gradio-container .form,
.gradio-container .panel {
  background: transparent !important;
  border: none !important;
}

/* Inputs */
.gradio-container input,
.gradio-container textarea,
.gradio-container select,
.gradio-container .wrap input {
  background: var(--tf-bg-elev) !important;
  border: 1px solid var(--tf-border) !important;
  color: var(--tf-ink) !important;
  border-radius: 8px !important;
  font-variant-numeric: tabular-nums;
}
.gradio-container input:focus,
.gradio-container textarea:focus {
  border-color: var(--tf-accent) !important;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.15) !important;
  outline: none !important;
}

/* Dropdown */
.gradio-container .dropdown-arrow,
.gradio-container [class*="dropdown"] {
  color: var(--tf-muted) !important;
}

/* Sliders */
.gradio-container input[type="range"] {
  accent-color: var(--tf-accent) !important;
}

/* Botones — jerarquía */
.gradio-container button {
  border-radius: 8px !important;
  font-weight: 700 !important;
  font-size: 0.84rem !important;
  letter-spacing: 0.01em;
  transition: transform 0.12s ease, filter 0.15s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
.gradio-container button:active {
  transform: scale(0.98);
}
.gradio-container button.primary,
.gradio-container .primary {
  background: linear-gradient(180deg, #14B8A6 0%, #0F766E 100%) !important;
  color: #042F2E !important;
  border: 1px solid #2DD4BF !important;
  box-shadow: 0 4px 14px rgba(20, 184, 166, 0.25) !important;
}
.gradio-container button.primary:hover,
.gradio-container .primary:hover {
  filter: brightness(1.08);
}
.gradio-container button.secondary,
.gradio-container .secondary {
  background: var(--tf-surface-2) !important;
  color: var(--tf-ink) !important;
  border: 1px solid var(--tf-border) !important;
}
.gradio-container button.secondary:hover {
  border-color: var(--tf-accent) !important;
  color: var(--tf-accent) !important;
}
.gradio-container button.stop {
  background: rgba(239, 68, 68, 0.12) !important;
  color: #FCA5A5 !important;
  border: 1px solid rgba(239, 68, 68, 0.35) !important;
}

/* Tabs */
.gradio-container .tabs {
  background: transparent !important;
  border: none !important;
}
.gradio-container .tab-nav,
.gradio-container .tabs > .tab-nav {
  background: var(--tf-surface) !important;
  border: 1px solid var(--tf-border-soft) !important;
  border-radius: 10px !important;
  padding: 4px !important;
  gap: 2px !important;
  margin-bottom: 12px !important;
}
.gradio-container .tab-nav button {
  background: transparent !important;
  color: var(--tf-muted) !important;
  border: none !important;
  border-radius: 8px !important;
  padding: 8px 12px !important;
  font-weight: 600 !important;
  font-size: 0.8rem !important;
}
.gradio-container .tab-nav button:hover {
  color: var(--tf-ink) !important;
  background: rgba(255,255,255,0.04) !important;
}
.gradio-container .tab-nav button.selected,
.gradio-container .tab-nav button[aria-selected="true"] {
  background: rgba(20, 184, 166, 0.15) !important;
  color: var(--tf-accent) !important;
  box-shadow: inset 0 -2px 0 var(--tf-accent) !important;
  font-weight: 800 !important;
}

/* Acordeones */
.gradio-container .label-wrap {
  background: var(--tf-surface) !important;
  border: 1px solid var(--tf-border-soft) !important;
  border-radius: 10px !important;
  padding: 10px 12px !important;
}
.gradio-container .label-wrap span {
  font-size: 0.9rem !important;
  font-weight: 700 !important;
  color: var(--tf-ink) !important;
}

/* Dataframes */
.gradio-container .dataframe,
.gradio-container table {
  font-size: 0.78rem !important;
  font-variant-numeric: tabular-nums !important;
  color: var(--tf-ink) !important;
  background: var(--tf-bg-elev) !important;
}
.gradio-container .dataframe th,
.gradio-container table th {
  background: var(--tf-surface-2) !important;
  color: var(--tf-muted) !important;
  font-weight: 700 !important;
  text-transform: uppercase;
  font-size: 0.68rem !important;
  letter-spacing: 0.03em;
  border-bottom: 1px solid var(--tf-border) !important;
}
.gradio-container .dataframe td,
.gradio-container table td {
  border-color: var(--tf-border-soft) !important;
  padding: 6px 8px !important;
}
.gradio-container .dataframe tr:hover td {
  background: rgba(20, 184, 166, 0.06) !important;
}
.gradio-container .table-wrap,
.gradio-container .dataframe wrapper {
  border-radius: 10px !important;
  border: 1px solid var(--tf-border-soft) !important;
  overflow: auto !important;
}

/* Scrollbar */
.gradio-container ::-webkit-scrollbar { width: 8px; height: 8px; }
.gradio-container ::-webkit-scrollbar-track { background: var(--tf-bg); }
.gradio-container ::-webkit-scrollbar-thumb {
  background: #334155; border-radius: 8px;
}
.gradio-container ::-webkit-scrollbar-thumb:hover { background: #475569; }

/* Header de producto */
.main-header {
  background: linear-gradient(125deg, #060D18 0%, #0B1F33 42%, #0F3D4C 100%) !important;
  border: 1px solid var(--tf-border) !important;
  border-radius: 14px !important;
  padding: 18px 22px !important;
  margin-bottom: 14px !important;
  box-shadow: var(--tf-shadow) !important;
  color: #F8FAFC !important;
}
.main-header h1 {
  margin: 0 0 6px 0 !important;
  font-size: 1.35rem !important;
  font-weight: 800 !important;
  color: #F8FAFC !important;
}
.main-header p, .main-header .subtitle, .main-header li {
  color: #CBD5E1 !important;
  font-size: 0.88rem !important;
  line-height: 1.45 !important;
}
.main-header a {
  color: #5EEAD4 !important;
  font-weight: 700 !important;
  text-decoration: none !important;
}
.main-header a:hover { text-decoration: underline !important; }

/* Workflow strip */
.workflow-strip {
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  gap: 8px !important;
  margin: 12px 0 14px 0 !important;
}
.wf-step {
  background: var(--tf-surface) !important;
  border: 1px solid var(--tf-border-soft) !important;
  border-radius: 10px !important;
  padding: 10px 12px !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 2px !important;
}
.wf-num {
  display: inline-flex !important;
  width: 22px; height: 22px;
  align-items: center; justify-content: center;
  border-radius: 999px !important;
  background: rgba(20,184,166,0.2) !important;
  color: var(--tf-accent) !important;
  font-size: 0.72rem !important;
  font-weight: 800 !important;
  margin-bottom: 4px !important;
}
.wf-title {
  font-weight: 800 !important;
  font-size: 0.85rem !important;
  color: var(--tf-ink) !important;
}
.wf-desc {
  font-size: 0.75rem !important;
  color: var(--tf-muted) !important;
}
@media (max-width: 800px) {
  .workflow-strip { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
}

/* Tarjetas de contenido HTML del motor */
.section-card, .tip-box, .result-note, .help-chip, .tab-section-title {
  background: var(--tf-surface) !important;
  border: 1px solid var(--tf-border-soft) !important;
  border-radius: 10px !important;
  padding: 12px 14px !important;
  margin: 8px 0 !important;
  color: var(--tf-ink) !important;
  box-shadow: none !important;
  border-left: none !important;
}
.section-card b, .tab-section-title b {
  color: var(--tf-accent) !important;
  font-weight: 800 !important;
}
.tip-box {
  background: rgba(59, 130, 246, 0.08) !important;
  border-color: rgba(59, 130, 246, 0.25) !important;
}
.result-note {
  background: rgba(20, 184, 166, 0.08) !important;
  border-color: rgba(20, 184, 166, 0.25) !important;
}
.help-chip {
  background: rgba(148, 163, 184, 0.08) !important;
  font-size: 0.84rem !important;
  color: var(--tf-ink-2) !important;
}

/* Glass sutil en paneles destacados */
.tf-glass {
  background: rgba(21, 28, 44, 0.72) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(148, 163, 184, 0.12) !important;
}

/* Hero KPI (inline + class) */
.mf-hero-strip {
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  gap: 10px !important;
  margin: 8px 0 10px 0 !important;
  padding: 12px 14px !important;
  border-radius: 12px !important;
  background: linear-gradient(135deg, #060D18 0%, #0F2744 50%, #0F4C4A 120%) !important;
  border: 1px solid var(--tf-border) !important;
  box-shadow: var(--tf-shadow) !important;
}
.mf-hero-cell {
  padding: 8px 10px !important;
  border-radius: 8px !important;
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.06) !important;
}
.mf-hero-label {
  font-size: 0.65rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
  color: #94A3B8 !important;
  font-weight: 700 !important;
  margin: 0 0 4px 0 !important;
}
.mf-hero-value {
  font-size: 1.1rem !important;
  font-weight: 800 !important;
  color: #F8FAFC !important;
  font-variant-numeric: tabular-nums !important;
  margin: 0 !important;
}
.mf-hero-sub {
  font-size: 0.7rem !important;
  color: #5EEAD4 !important;
  margin: 2px 0 0 0 !important;
}
.mf-scenario-bar { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 10px 0; }
.mf-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 11px; border-radius: 999px;
  font-size: 0.75rem; font-weight: 700;
  border: 1px solid transparent;
}
.mf-chip-pes { background: rgba(245,158,11,0.12); color: #FBBF24 !important; border-color: rgba(245,158,11,0.3); }
.mf-chip-base { background: rgba(20,184,166,0.12); color: #5EEAD4 !important; border-color: rgba(20,184,166,0.3); }
.mf-chip-opt { background: rgba(34,197,94,0.12); color: #86EFAC !important; border-color: rgba(34,197,94,0.3); }

/* Footer */
.footer-note {
  margin-top: 18px !important;
  padding: 12px 14px !important;
  border-radius: 10px !important;
  background: var(--tf-surface) !important;
  border: 1px solid var(--tf-border-soft) !important;
  color: var(--tf-muted) !important;
  font-size: 0.78rem !important;
  text-align: center !important;
}

/* Plots */
.gradio-container .plot,
.gradio-container canvas {
  border-radius: 10px !important;
  background: var(--tf-bg-elev) !important;
}

/* Transiciones suaves */
.gradio-container .block,
.gradio-container .tabitem,
.gradio-container button {
  transition: border-color 0.2s ease, background 0.2s ease, color 0.15s ease !important;
}

@media (prefers-reduced-motion: reduce) {
  .gradio-container * {
    transition: none !important;
    animation: none !important;
  }
}

/* Espaciado de filas densas */
.gradio-container .gap,
.gradio-container .gr-row {
  gap: 10px !important;
}


/* Contraste de texto en HTML embebido (tema oscuro) */
.gradio-container .html-container,
.gradio-container .prose,
.gradio-container .section-card,
.gradio-container .tip-box,
.gradio-container .result-note,
.gradio-container .help-chip,
.gradio-container .tab-section-title {
  color: #E8EEF7 !important;
}
.gradio-container .section-card p,
.gradio-container .section-card li,
.gradio-container .section-card span,
.gradio-container .tip-box p,
.gradio-container .tip-body,
.gradio-container .result-note,
.gradio-container .help-chip {
  color: #E8EEF7 !important;
}
.gradio-container .section-card b,
.gradio-container .tab-section-title b {
  color: #5EEAD4 !important;
}
.gradio-container a { color: #5EEAD4 !important; }



/* ---- Radio / método de proyección: estado seleccionado visible ---- */
.gradio-container .wrap.svelte-1hfxr6a /* fallback */,
.gradio-container fieldset,
.gradio-container [role="radiogroup"],
.gradio-container .form > .wrap {
  /* container only */
}
.gradio-container label:has(input[type="radio"]),
.gradio-container label:has(input[type="checkbox"]) {
  color: #CBD5E1 !important;
  background: #111827 !important;
  border: 1px solid #243044 !important;
  border-radius: 8px !important;
  padding: 8px 12px !important;
  margin: 4px 0 !important;
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  cursor: pointer !important;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease !important;
}
.gradio-container label:has(input[type="radio"]:checked),
.gradio-container label:has(input[type="checkbox"]:checked) {
  background: rgba(20, 184, 166, 0.18) !important;
  border-color: #14B8A6 !important;
  color: #5EEAD4 !important;
  box-shadow: 0 0 0 1px rgba(20, 184, 166, 0.45) !important;
  font-weight: 700 !important;
}
.gradio-container input[type="radio"],
.gradio-container input[type="checkbox"] {
  accent-color: #14B8A6 !important;
  width: 1.05em !important;
  height: 1.05em !important;
  flex-shrink: 0 !important;
}
/* Gradio a veces renderiza radios como botones */
.gradio-container [role="radio"],
.gradio-container .form input[type="radio"] + span,
.gradio-container button[role="radio"] {
  color: #CBD5E1 !important;
}
.gradio-container [role="radio"][aria-checked="true"],
.gradio-container button[role="radio"][aria-checked="true"],
.gradio-container .selected[role="radio"] {
  background: rgba(20, 184, 166, 0.18) !important;
  border: 1px solid #14B8A6 !important;
  color: #5EEAD4 !important;
  font-weight: 700 !important;
  box-shadow: 0 0 0 1px rgba(20, 184, 166, 0.4) !important;
}

/* Tablas dentro de HTML embebido (tab 3/7) legibles en tema oscuro */
.gradio-container .html-container table,
.gradio-container .html-container td,
.gradio-container .html-container th {
  color: #E8EEF7 !important;
  border-color: #243044 !important;
}
.gradio-container .html-container h3,
.gradio-container .html-container h4 {
  color: #5EEAD4 !important;
}
/* Evitar texto casi blanco forzado solo en contenedor; hijos con color propio respetan si tienen !important en inline */
.gradio-container .html-container [style*="color:#0A2540"],
.gradio-container .html-container [style*="color: #0A2540"] {
  color: #E8EEF7 !important;
}



/* Gradio 4: radios a menudo como .wrap labels o botones en fila */
.gradio-container .form .wrap label,
.gradio-container [data-testid="radio"] label,
.gradio-container .block.svelte-radio label,
.gradio-container span:has(> input[type="radio"]) {
  color: #CBD5E1 !important;
}
.gradio-container .form .wrap label:has(input:checked),
.gradio-container [data-testid="radio"] label:has(input:checked),
.gradio-container span:has(> input[type="radio"]:checked) {
  color: #5EEAD4 !important;
  font-weight: 700 !important;
}
/* Contenedor del Radio de método de proyección */
.gradio-container fieldset label,
.gradio-container .radio-row label,
.gradio-container .wrap[role="group"] label {
  border: 1px solid #243044 !important;
  border-radius: 8px !important;
  padding: 10px 14px !important;
  margin: 3px 0 !important;
  background: #111827 !important;
}
.gradio-container fieldset label:has(input:checked),
.gradio-container .radio-row label:has(input:checked),
.gradio-container .wrap[role="group"] label:has(input:checked) {
  background: rgba(20, 184, 166, 0.2) !important;
  border-color: #14B8A6 !important;
  color: #5EEAD4 !important;
  box-shadow: inset 3px 0 0 #14B8A6 !important;
}

/* Evitar bordes dobles feos en HTML embebido legacy */
.section-card[style*="border-left"],
.tip-box[style*="border-left"] {
  border-left-width: 0 !important;
}
"""

APP_THEME = None  # Gradio only


def asegurar_plantilla_excel(ruta=None):
    """Crea (si no existe) la plantilla Excel de EEFF para carga independiente."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    if ruta is None:
        try:
            base = Path(__file__).resolve().parent
        except Exception:
            base = Path.cwd()
        ruta = base / "Plantilla_EEFF_Modelacion_Financiera.xlsx"
    ruta = Path(ruta)
    if ruta.exists() and ruta.stat().st_size > 2000:
        return str(ruta)

    wb = Workbook()
    ws_i = wb.active
    ws_i.title = "Instrucciones"
    ws_i["A1"] = "Plantilla de estados financieros — Modelación Financiera Multisectorial"
    ws_i["A1"].font = Font(bold=True, size=14, color="0B1F33")
    lineas = [
        "",
        "Cómo usar esta plantilla",
        "1. Ve a la hoja «Datos».",
        "2. Reemplaza las filas de ejemplo por los datos de TU empresa (mínimo 3 años; recomendado 5–10).",
        "3. Todas las cifras deben estar en LA MISMA moneda y unidad (p. ej. miles de millones COP o millones USD).",
        "4. No mezcles empresas ni cambies los nombres de columna de la fila de encabezados.",
        "5. Guarda (.xlsx o .csv) y cárgalo en «Estados financieros propios» de la plataforma.",
        "",
        "Columnas obligatorias: Año, Ingresos, EBITDA, EBIT, CAPEX, NWC.",
        "Opcionales (si vacías, el modelo las estima): Depreciacion, Delta_NWC, NOPAT, FCFF.",
        "FCFF = NOPAT + Depreciacion − CAPEX − Delta_NWC.",
        "No uses el año calendario en curso si el ejercicio aún no cierra.",
        "Un salto de ingresos >300% suele indicar error de unidades.",
    ]
    for i, t in enumerate(lineas, start=2):
        ws_i[f"A{i}"] = t
        if t.startswith("Cómo") or t.startswith("Columnas") or t.startswith("Opcionales"):
            ws_i[f"A{i}"].font = Font(bold=True, color="0F766E")
    ws_i.column_dimensions["A"].width = 100

    ws = wb.create_sheet("Datos", 0)
    headers = ["Año", "Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC", "Delta_NWC", "NOPAT", "FCFF"]
    example = [
        [2019, 8500, 3200, 2400, 800, 1500, 900, 0, 1560, 860],
        [2020, 7800, 2900, 2100, 800, 1200, 950, 50, 1365, 915],
        [2021, 9200, 3500, 2700, 800, 1600, 1000, 50, 1755, 905],
        [2022, 10500, 4100, 3200, 900, 1800, 1100, 100, 2080, 1080],
        [2023, 11200, 4500, 3600, 900, 1900, 1150, 50, 2340, 1290],
        [2024, 12000, 4900, 4000, 900, 2000, 1200, 50, 2600, 1450],
    ]
    header_fill = PatternFill("solid", fgColor="0B1F33")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    req_fill = PatternFill("solid", fgColor="0F766E")
    opt_fill = PatternFill("solid", fgColor="64748B")
    example_fill = PatternFill("solid", fgColor="F8FAFC")
    thin = Border(
        left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1"),
    )
    required = {"Año", "Ingresos", "EBITDA", "EBIT", "CAPEX", "NWC"}
    ws.merge_cells("A1:J1")
    ws["A1"] = "PLANTILLA EEFF — reemplaza el ejemplo por los datos de tu empresa (misma moneda y unidad)"
    ws["A1"].font = Font(bold=True, size=12, color="0B1F33")
    ws.merge_cells("A2:F2")
    ws["A2"] = "Obligatorias →"
    ws["A2"].fill = req_fill
    ws["A2"].font = Font(bold=True, color="FFFFFF", size=9)
    ws.merge_cells("G2:J2")
    ws["G2"] = "Opcionales (estimables) →"
    ws["G2"].fill = opt_fill
    ws["G2"].font = Font(bold=True, color="FFFFFF", size=9)
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(3, col, h)
        cell.font = header_font
        cell.fill = header_fill if h in required else PatternFill("solid", fgColor="334155")
        cell.border = thin
        cell.alignment = Alignment(horizontal="center")
    for r, row in enumerate(example, start=4):
        for c, val in enumerate(row, start=1):
            cell = ws.cell(r, c, val)
            cell.border = thin
            cell.fill = example_fill
            if c > 1:
                cell.number_format = "#,##0.0"
    ws.merge_cells("A11:J11")
    ws["A11"] = "NOTA: filas 4–9 son ejemplo ilustrativo. Unidad sugerida CO: miles de millones COP. US: miles de millones USD."
    ws["A11"].font = Font(italic=True, size=9, color="64748B")
    for i, w in enumerate([10, 12, 12, 12, 14, 12, 12, 12, 12, 12], start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    ws_e = wb.create_sheet("Datos_vacios")
    ws_e["A1"] = "Hoja vacía: solo encabezados, sin números de ejemplo."
    for col, h in enumerate(headers, start=1):
        cell = ws_e.cell(2, col, h)
        cell.font = header_font
        cell.fill = header_fill if h in required else PatternFill("solid", fgColor="334155")
        cell.border = thin
    for r in range(3, 13):
        for c in range(1, 11):
            ws_e.cell(r, c).border = thin
    for i, w in enumerate([10, 12, 12, 12, 14, 12, 12, 12, 12, 12], start=1):
        ws_e.column_dimensions[chr(64 + i)].width = w

    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return str(ruta)


# Plantilla Excel disponible para descarga en la UI (Paso 2)
try:
    RUTA_PLANTILLA_EEFF = asegurar_plantilla_excel(
        str(Path.cwd() / "Plantilla_EEFF_Modelacion_Financiera.xlsx")
    )
except Exception:
    try:
        RUTA_PLANTILLA_EEFF = asegurar_plantilla_excel(
            "/home/workdir/artifacts/Plantilla_EEFF_Modelacion_Financiera.xlsx"
        )
    except Exception:
        RUTA_PLANTILLA_EEFF = None


# ---------------------------------------------------------------------------
# UX Gradio: sensibilidad rápida + hero KPI (sin reproyectar FCFF completo)
# ---------------------------------------------------------------------------
def _fcff_desde_sesion_o_hist(nombre_empresa, horizonte=5, tax=0.35):
    """Recupera FCFF proyectado de RESULTADOS_SESION o recalcula drivers una vez."""
    tabs = (RESULTADOS_SESION.get("tabs") or {})
    t1 = tabs.get("1") or {}
    # Si hay proyección en sesión con lista guardada
    if t1.get("fcff_proj"):
        return list(t1["fcff_proj"]), None
    try:
        df_hist, _ = cargar_y_limpiar_excel(None, nombre_empresa, usar_datos_publicos=True)
        df_hist, _ = _sanear_historico_tab1(df_hist)
        df_proj, meta = proyectar_variables_con_meta(df_hist, int(horizonte), metodo="drivers", tax=float(tax))
        fcff = [float(x) for x in df_proj["FCFF"].values]
        return fcff, meta
    except Exception as e:
        return [], str(e)


def sensibilidad_rapida_ui(nombre_empresa, wacc, g, horizonte, tax, deuda_neta, caja, nci, otros_claims, asociados, acciones, mid_year, g_max_macro):
    """Actualiza Hero KPI al mover WACC/g — solo DCF sobre FCFF ya proyectado."""
    try:
        wacc = float(wacc)
        g = float(g)
        fcff, err = _fcff_desde_sesion_o_hist(nombre_empresa, horizonte=horizonte, tax=tax)
        if not fcff:
            msg = err or "Ejecuta la pestaña 1 (Pronóstico) primero."
            return (
                f"<div style='padding:10px 12px;border-radius:10px;background:#FEF3C7;color:#92400E;"
                f"font-size:0.88rem'>Sin FCFF en sesión. {msg}</div>"
            )
        bp = {
            "deuda_neta": float(deuda_neta or 0),
            "caja": float(caja or 0),
            "nci": float(nci or 0),
            "otros_claims": float(otros_claims or 0),
            "asociados": float(asociados or 0),
            "acciones": acciones,
            "exit_multiple": 0.0,
        }
        val = valorar_con_bridge(
            fcff, wacc, g, bp,
            mid_year=bool(mid_year),
            g_max_macro=float(g_max_macro or 0.04),
        )
        ev = val.get("EV")
        eq = val.get("Equity_Value")
        vps = val.get("value_per_share")
        g_used = val.get("g_used", g)
        def _cell(label, value, sub):
            return (
                f"<div style='padding:8px 10px;border-radius:10px;background:rgba(255,255,255,0.06);"
                f"border:1px solid rgba(255,255,255,0.08);min-height:64px'>"
                f"<div style='font-size:0.68rem;letter-spacing:0.04em;text-transform:uppercase;"
                f"color:#94A3B8;font-weight:600;margin-bottom:4px'>{label}</div>"
                f"<div style='font-size:1.15rem;font-weight:800;color:#F8FAFC;font-variant-numeric:tabular-nums'>{value}</div>"
                f"<div style='font-size:0.72rem;color:#99F6E4;margin-top:2px'>{sub}</div></div>"
            )
        vps_txt = f"{vps:,.1f}" if vps is not None else "—"
        html = (
            "<div style='display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;"
            "margin:10px 0 6px 0;padding:12px 14px;border-radius:14px;"
            "background:linear-gradient(135deg,#0B1F33 0%,#163A5F 55%,#0F766E 140%);"
            "box-shadow:0 8px 28px rgba(11,31,51,0.18)'>"
            + _cell("Enterprise value", f"{ev:,.0f}", "miles M · sensibilidad")
            + _cell("Equity value", f"{eq:,.0f}", "tras puente a equity")
            + _cell("WACC · g", f"{wacc*100:.2f}% · {g_used*100:.2f}%", "g anclado si aplica")
            + _cell("VPS", vps_txt, str(nombre_empresa))
            + "</div>"
            "<p style='margin:6px 0 0 0;font-size:0.8rem;color:#5C6B7A'>"
            "Sensibilidad activa · apoyo a decisión · no es orden de compra</p>"
        )
        return html
    except Exception as e:
        return f"<div class='result-note'>Sensibilidad: {e}</div>"



# Tooltips de controles (info=) — textos cortos para la UI

def html_enlace_api_key(proveedor="gemini"):
    """Enlace de ayuda para obtener API key según proveedor de la consulta asistida."""
    p = (proveedor or "gemini").strip().lower()
    if p in ("xai", "x-ai", "grok"):
        url = "https://console.x.ai/"
        nombre = "xAI (Grok)"
        hint = "Crea una API key en la consola de xAI."
    elif p in ("openai", "gpt"):
        url = "https://platform.openai.com/api-keys"
        nombre = "OpenAI"
        hint = "Crea una API key en platform.openai.com."
    else:
        url = "https://aistudio.google.com/apikey"
        nombre = "Google AI Studio (Gemini)"
        hint = "Crea una API key gratuita en Google AI Studio."
        p = "gemini"
    return (
        f"<div class='help-chip' style='margin-top:6px'>"
        f"<b>API key · {nombre}</b> — {hint} "
        f"<a href='{url}' target='_blank' rel='noopener noreferrer'>Abrir sitio para obtener la clave</a>. "
        f"La clave solo se usa en esta sesión; no se guarda en el servidor de la app."
        f"</div>"
    )


INFO = {
    "empresa": "Elige del catálogo, una empresa descargada por Yahoo, o escribe un nombre si cargarás Excel propio.",
    "archivo": "Opcional. Sube EEFF en la plantilla del sistema. Si no cargas archivo, se usan catálogo o Yahoo según la empresa.",
    "horizonte": "Años de proyección explícita antes del valor terminal (típicamente 5).",
    "de_ratio": "Deuda / patrimonio (en valor). Influye en el WACC y en el riesgo financiero.",
    "kd": "Costo de la deuda antes de impuestos (anual, en decimal: 0,08 = 8%).",
    "tax": "Tasa de impuesto efectiva sobre el resultado operativo.",
    "g": "Crecimiento de largo plazo del flujo en la perpetuidad. Debe ser menor que el WACC.",
    "capex_extra": "Inversión adicional en CAPEX (misma unidad que el modelo, p. ej. miles de millones).",
    "beta_u": "Beta del negocio sin deuda. Se reapalanca con D/E e impuestos para el CAPM.",
    "rf": "Tasa libre de riesgo. En COP conviene alinearla a la curva local (p. ej. TES), no a un default bajo.",
    "erp": "Prima de riesgo del mercado accionario sobre rf (CAPM).",
    "crp": "Prima país explícita. Si rf ya es local (TES), suele ir en 0 para no doblar el riesgo.",
    "capital_invertido": "Base para ROIC en la auditoría (misma unidad del modelo).",
    "deuda_neta": "Deuda menos caja operativa usada en el puente de EV a equity.",
    "inversion_inicial": "Desembolso del proyecto en la pestaña VPN/TIR.",
    "caja": "Caja e equivalentes que suman al equity en el puente.",
    "nci": "Interés minoritario / NCI a restar en el puente a equity.",
    "acciones": "Número de acciones para valor por acción (VPS).",
    "g_max_macro": "Techo de g de largo plazo (disciplina macro).",
    "mid_year": "Descontar flujos a mitad de año (más realista que fin de año).",
}

