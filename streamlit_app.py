"""
Modelación Financiera Multisectorial — Streamlit
Versión optimizada para Streamlit Community Cloud / local.
Herramienta pedagógica · No es asesoría de inversión.
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Dependencias opcionales
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

try:
    import numpy_financial as npf
    HAS_NPF = True
except ImportError:
    HAS_NPF = False

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Modelación Financiera · Multisectorial",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CATÁLOGO BVC (miles de millones COP) — mismo núcleo del notebook original
# ---------------------------------------------------------------------------
EMPRESAS = {
    "ISA — Interconexión Eléctrica": {
        "ticker_yf": "ISA.CL",
        "sector": "Transmisión de energía / Infraestructura",
        "params": {
            "de_ratio": 1.20, "kd": 0.08, "tax": 0.35, "g": 0.03, "beta_u": 0.42,
            "capital_invertido": 45000, "deuda_neta": 29800, "inversion_inicial": 5000,
            "caja": 4610, "nci": 10400, "otros_claims": 0, "asociados": 4500,
            "acciones": 1108, "exit_multiple": 8.4, "moneda": "COP",
        },
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
        "ticker_yf": "GEB.CL",
        "sector": "Transmisión y distribución de energía / Gas",
        "params": {
            "de_ratio": 0.95, "kd": 0.075, "tax": 0.35, "g": 0.032, "beta_u": 0.40,
            "capital_invertido": 38000, "deuda_neta": 17170, "inversion_inicial": 3500,
            "caja": 2430, "nci": 1500, "otros_claims": 0, "asociados": 800,
            "acciones": 9181, "exit_multiple": 13.6, "moneda": "COP",
        },
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
        "ticker_yf": "CELSIA.CL",
        "sector": "Generación renovable y distribución",
        "params": {
            "de_ratio": 1.10, "kd": 0.085, "tax": 0.35, "g": 0.028, "beta_u": 0.45,
            "capital_invertido": 18000, "deuda_neta": 5030, "inversion_inicial": 2000,
            "caja": 300, "nci": 200, "otros_claims": 0, "asociados": 100,
            "acciones": 1033, "exit_multiple": 7.9, "moneda": "COP",
        },
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
    "ECOPETROL": {
        "ticker_yf": "ECOPETROL.CL",
        "sector": "Petróleo, gas y energía",
        "params": {
            "de_ratio": 1.00, "kd": 0.09, "tax": 0.35, "g": 0.02, "beta_u": 0.75,
            "capital_invertido": 150000, "deuda_neta": 93726, "inversion_inicial": 15000,
            "caja": 11192, "nci": 3000, "otros_claims": 0, "asociados": 2000,
            "acciones": 41117, "exit_multiple": 4.8, "moneda": "COP",
        },
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

EMPRESAS_RUNTIME: dict = {}  # empresas descargadas en sesión vía Yahoo


# ---------------------------------------------------------------------------
# Helpers financieros
# ---------------------------------------------------------------------------
def _safe_div(a, b, default=0.0):
    try:
        if b is None or abs(float(b)) < 1e-12:
            return default
        return float(a) / float(b)
    except Exception:
        return default


def _safe_float(x, default=None):
    try:
        if x is None:
            return default
        v = float(x)
        if v != v or abs(v) == float("inf"):
            return default
        return v
    except Exception:
        return default


def df_historico(nombre: str) -> pd.DataFrame:
    emp = EMPRESAS.get(nombre) or EMPRESAS_RUNTIME.get(nombre)
    if not emp:
        return pd.DataFrame()
    h = emp["historico"]
    df = pd.DataFrame(h)
    if "Año" in df.columns:
        df = df.set_index("Año")
    return df


def calcular_wacc(de_ratio, kd, tax, beta_u, rf=0.12, erp=0.055, crp=0.0):
    """WACC = we*Ke + wd*Kd*(1-t). Ke = rf + βL*ERP + CRP."""
    de = max(float(de_ratio), 0.0)
    we = 1.0 / (1.0 + de)
    wd = de / (1.0 + de)
    beta_l = float(beta_u) * (1.0 + (1.0 - float(tax)) * de)
    ke = float(rf) + beta_l * float(erp) + float(crp)
    kd_after = float(kd) * (1.0 - float(tax))
    wacc = we * ke + wd * kd_after
    return {
        "wacc": wacc,
        "ke": ke,
        "kd_after": kd_after,
        "we": we,
        "wd": wd,
        "beta_l": beta_l,
    }


def proyectar_drivers(df_hist: pd.DataFrame, horizonte: int = 5, tax: float = 0.35) -> pd.DataFrame:
    """Proyecta FCFF con drivers simples (crecimiento de ingresos + márgenes medios)."""
    if df_hist is None or df_hist.empty or "Ingresos" not in df_hist.columns:
        return pd.DataFrame()

    df = df_hist.copy()
    years = list(df.index.astype(int))
    last_year = int(years[-1])

    # Crecimiento medio de ingresos (últimos 3-5 años, winsorizado)
    ing = df["Ingresos"].astype(float).values
    if len(ing) >= 2:
        rets = np.diff(ing) / np.maximum(np.abs(ing[:-1]), 1e-9)
        rets = rets[np.isfinite(rets)]
        g_ing = float(np.clip(np.median(rets[-5:]), -0.05, 0.15)) if len(rets) else 0.04
    else:
        g_ing = 0.04

    ebit_m = _safe_div(df["EBIT"].mean(), df["Ingresos"].mean(), 0.25)
    ebit_m = float(np.clip(ebit_m, 0.05, 0.55))
    dep_m = _safe_div(df["Depreciacion"].mean(), df["Ingresos"].mean(), 0.06) if "Depreciacion" in df.columns else 0.06
    capex_m = _safe_div(df["CAPEX"].mean(), df["Ingresos"].mean(), 0.08) if "CAPEX" in df.columns else 0.08
    nwc_m = _safe_div(df["NWC"].iloc[-1], df["Ingresos"].iloc[-1], 0.05) if "NWC" in df.columns else 0.05

    rows = []
    prev_ing = float(ing[-1])
    prev_nwc = float(df["NWC"].iloc[-1]) if "NWC" in df.columns else prev_ing * nwc_m

    for i in range(1, horizonte + 1):
        y = last_year + i
        ing_t = prev_ing * (1.0 + g_ing)
        ebit = ing_t * ebit_m
        nopat = ebit * (1.0 - tax)
        dep = ing_t * dep_m
        capex = ing_t * capex_m
        nwc = ing_t * nwc_m
        delta_nwc = nwc - prev_nwc
        fcff = nopat + dep - capex - delta_nwc
        rows.append({
            "Año": y,
            "Ingresos": ing_t,
            "EBIT": ebit,
            "NOPAT": nopat,
            "Depreciacion": dep,
            "CAPEX": capex,
            "NWC": nwc,
            "Delta_NWC": delta_nwc,
            "FCFF": fcff,
        })
        prev_ing, prev_nwc = ing_t, nwc

    return pd.DataFrame(rows).set_index("Año")


def valorar_dcf(
    fcff_list,
    wacc: float,
    g: float,
    deuda_neta: float = 0.0,
    caja: float = 0.0,
    nci: float = 0.0,
    otros_claims: float = 0.0,
    asociados: float = 0.0,
    acciones: Optional[float] = None,
    mid_year: bool = True,
    g_max: float = 0.04,
):
    """Gordon growth DCF + puente a equity."""
    fcff = [float(x) for x in fcff_list]
    n = len(fcff)
    if n == 0 or wacc <= 0:
        return {"EV": None, "Equity_Value": None, "value_per_share": None, "g_used": g}

    g_used = min(float(g), float(g_max), float(wacc) - 0.01)
    g_used = max(g_used, -0.02)

    # Valor terminal (Gordon sobre último FCFF)
    tv = fcff[-1] * (1.0 + g_used) / (wacc - g_used)

    # Descuento
    offset = 0.5 if mid_year else 1.0
    ev = 0.0
    for t, f in enumerate(fcff, start=1):
        ev += f / ((1.0 + wacc) ** (t - 1 + offset))
    ev += tv / ((1.0 + wacc) ** (n - 1 + offset))

    equity = ev - float(deuda_neta) + float(caja) - float(nci) - float(otros_claims) + float(asociados)
    vps = None
    if acciones and float(acciones) > 0:
        # acciones en millones; equity en miles de millones → VPS en unidades de moneda
        vps = (equity * 1e9) / (float(acciones) * 1e6)

    return {
        "EV": ev,
        "Equity_Value": equity,
        "value_per_share": vps,
        "TV": tv,
        "g_used": g_used,
        "wacc": wacc,
    }


def descargar_yahoo(ticker: str, tax_default: float = 0.21):
    """Descarga histórico simplificado desde Yahoo Finance (miles de millones)."""
    if not HAS_YF:
        return None, "yfinance no instalado"
    try:
        t = yf.Ticker(ticker)
        fin = t.financials
        cf = t.cashflow
        info = t.info or {}
        if fin is None or fin.empty:
            return None, f"Sin financials para {ticker}"

        def pick(df, names):
            if df is None or df.empty:
                return {}
            idx_map = {str(i).lower(): i for i in df.index}
            for n in names:
                for k, orig in idx_map.items():
                    if n.lower() in k and "normalized" not in k:
                        row = df.loc[orig]
                        out = {}
                        for col, val in row.items():
                            try:
                                y = int(col.year) if hasattr(col, "year") else int(str(col)[:4])
                                v = float(val)
                                if v == v:
                                    out[y] = v / 1e9  # a miles de millones
                            except Exception:
                                pass
                        return out
            return {}

        ingresos = pick(fin, ["Total Revenue", "Operating Revenue", "Revenue"])
        ebit = pick(fin, ["EBIT", "Operating Income"])
        ebitda = pick(fin, ["EBITDA"])
        # CAPEX desde cashflow (suele venir negativo)
        capex_raw = pick(cf, ["Capital Expenditure", "Capital Expenditures"])
        capex = {y: abs(v) for y, v in capex_raw.items()}

        years = sorted(set(ingresos.keys()) & set(ebit.keys()))
        years = [y for y in years if y < datetime.now().year]
        if len(years) < 2:
            return None, "Serie insuficiente"

        # Tax efectiva
        etr = _safe_float(info.get("effectiveTaxRate"))
        if etr and 0 < etr < 0.55:
            tax = etr
        else:
            country = (info.get("country") or "").upper()
            tax = 0.35 if "COLOMBIA" in country else tax_default

        rows = []
        prev_nwc = None
        for y in years:
            ing = ingresos.get(y, 0.0)
            eb = ebit.get(y, 0.0)
            ebd = ebitda.get(y, eb * 1.2)
            dep = max(ebd - eb, 0.0)
            cx = capex.get(y, ing * 0.04)
            nwc = ing * 0.05
            delta = 0.0 if prev_nwc is None else nwc - prev_nwc
            nopat = eb * (1.0 - tax)
            fcff = nopat + dep - cx - delta
            rows.append({
                "Año": y, "Ingresos": ing, "EBITDA": ebd, "EBIT": eb,
                "Depreciacion": dep, "CAPEX": cx, "NWC": nwc,
                "Delta_NWC": delta, "NOPAT": nopat, "FCFF": fcff,
            })
            prev_nwc = nwc

        df = pd.DataFrame(rows).set_index("Año")
        name = info.get("longName") or info.get("shortName") or ticker
        sector = info.get("sector") or "No clasificado"
        params = {
            "de_ratio": _safe_float(info.get("debtToEquity"), 50) / 100.0 if info.get("debtToEquity") else 0.5,
            "kd": 0.06,
            "tax": tax,
            "g": 0.025,
            "beta_u": _safe_float(info.get("beta"), 1.0) or 1.0,
            "capital_invertido": float(df["Ingresos"].iloc[-1]) * 2,
            "deuda_neta": (_safe_float(info.get("totalDebt"), 0) or 0) / 1e9 - (_safe_float(info.get("totalCash"), 0) or 0) / 1e9,
            "inversion_inicial": float(df["Ingresos"].iloc[-1]) * 0.1,
            "caja": (_safe_float(info.get("totalCash"), 0) or 0) / 1e9,
            "nci": 0.0,
            "otros_claims": 0.0,
            "asociados": 0.0,
            "acciones": (_safe_float(info.get("sharesOutstanding"), 0) or 0) / 1e6,
            "exit_multiple": _safe_float(info.get("enterpriseToEbitda"), 10) or 10.0,
            "moneda": info.get("financialCurrency") or info.get("currency") or "USD",
        }
        # Beta unlevered aproximado
        de = params["de_ratio"]
        params["beta_u"] = params["beta_u"] / (1.0 + (1.0 - tax) * max(de, 0))

        display = f"{name} — {ticker}"
        EMPRESAS_RUNTIME[display] = {
            "ticker_yf": ticker,
            "sector": sector,
            "params": params,
            "historico": {c: df[c].tolist() if c != "Año" else list(df.index) for c in ["Año"] + list(df.columns)},
            "moneda": params["moneda"],
        }
        # Fix historico format
        EMPRESAS_RUNTIME[display]["historico"] = {
            "Año": list(df.index.astype(int)),
            **{c: df[c].tolist() for c in df.columns},
        }
        return display, f"OK · {len(df)} años · tax efectiva {tax*100:.1f}%"
    except Exception as e:
        return None, str(e)


def monte_carlo_fcff(fcff_base, n_sim=500, vol=0.20, seed=42):
    """Bandas simples de Monte Carlo alrededor del FCFF proyectado."""
    rng = np.random.default_rng(seed)
    base = np.array(fcff_base, dtype=float)
    sims = []
    for _ in range(n_sim):
        shocks = rng.normal(0, vol, size=len(base))
        path = base * np.cumprod(1.0 + shocks * 0.5)  # shock parcial acumulado
        # también escala nivel
        path = path * (1.0 + rng.normal(0, vol * 0.3))
        sims.append(path)
    arr = np.array(sims)
    return {
        "p10": np.percentile(arr, 10, axis=0),
        "p50": np.percentile(arr, 50, axis=0),
        "p90": np.percentile(arr, 90, axis=0),
        "mean": arr.mean(axis=0),
    }


def vpn_tir(fcff_list, inversion_inicial, wacc):
    """VPN, TIR y payback del proyecto."""
    flows = [-float(inversion_inicial)] + [float(x) for x in fcff_list]
    # VPN
    vpn = sum(f / ((1.0 + wacc) ** t) for t, f in enumerate(flows))
    # TIR
    tir = None
    if HAS_NPF:
        try:
            tir = float(npf.irr(flows))
        except Exception:
            tir = None
    else:
        # fallback Brent
        try:
            from scipy.optimize import brentq
            def npv(r):
                return sum(f / ((1.0 + r) ** t) for t, f in enumerate(flows))
            tir = brentq(npv, -0.99, 5.0)
        except Exception:
            tir = None
    # Payback simple
    acum = 0.0
    payback = None
    for i, f in enumerate(flows):
        acum += f
        if acum >= 0 and i > 0:
            payback = i
            break
    return {"vpn": vpn, "tir": tir, "payback": payback, "flows": flows}


# ---------------------------------------------------------------------------
# UI Streamlit
# ---------------------------------------------------------------------------
def main():
    st.title("📊 Modelación Financiera y Riesgo")
    st.caption("Proyección · DCF · Escenarios · VPN/TIR · Sector · **Herramienta pedagógica · No es asesoría de inversión**")

    # ----- Sidebar: empresa y parámetros -----
    with st.sidebar:
        st.header("1 · Empresa")
        catalogo = list(EMPRESAS.keys()) + list(EMPRESAS_RUNTIME.keys())
        empresa = st.selectbox("Catálogo / descargadas", options=catalogo, index=0)

        with st.expander("Buscar ticker Yahoo Finance"):
            ticker_q = st.text_input("Ticker", placeholder="AAPL, MSFT, EC, ISA.CL")
            if st.button("Descargar", type="primary"):
                with st.spinner("Descargando..."):
                    nombre, msg = descargar_yahoo(ticker_q.strip().upper())
                    if nombre:
                        st.success(f"{nombre}\n{msg}")
                        st.rerun()
                    else:
                        st.error(msg)

        emp = EMPRESAS.get(empresa) or EMPRESAS_RUNTIME.get(empresa)
        if not emp:
            st.error("Empresa no encontrada")
            st.stop()

        p = emp["params"]
        st.header("2 · Parámetros")
        horizonte = st.slider("Horizonte (años)", 3, 10, 5)
        de_ratio = st.slider("D/E", 0.0, 5.0, float(p.get("de_ratio", 1.0)), 0.05)
        kd = st.slider("Kd (costo deuda)", 0.0, 0.25, float(p.get("kd", 0.08)), 0.005)
        tax = st.slider("Tax", 0.0, 0.50, float(p.get("tax", 0.35)), 0.01)
        g = st.slider("g terminal", 0.0, 0.08, float(p.get("g", 0.03)), 0.005)
        beta_u = st.slider("β unlevered", 0.0, 3.0, float(p.get("beta_u", 0.5)), 0.05)
        rf = st.slider("rf", 0.02, 0.16, 0.12 if p.get("moneda") == "COP" else 0.04, 0.005)
        erp = st.slider("ERP", 0.03, 0.10, 0.055, 0.005)
        crp = st.slider("CRP país", 0.0, 0.05, 0.0, 0.005)

        st.subheader("Puente a equity")
        deuda_neta = st.number_input("Deuda neta", value=float(p.get("deuda_neta", 0)), step=100.0)
        caja = st.number_input("Caja", value=float(p.get("caja", 0)), step=50.0)
        nci = st.number_input("NCI", value=float(p.get("nci", 0)), step=50.0)
        otros = st.number_input("Otros claims", value=float(p.get("otros_claims", 0)), step=50.0)
        asociados = st.number_input("Asociados", value=float(p.get("asociados", 0)), step=50.0)
        acciones = st.number_input("Acciones (millones)", value=float(p.get("acciones") or 0), step=1.0)
        inversion = st.number_input("Inversión inicial (proyecto)", value=float(p.get("inversion_inicial", 0)), step=100.0)
        mid_year = st.checkbox("Mid-year convention", value=True)
        g_max = st.slider("Techo macro g", 0.02, 0.06, 0.04, 0.005)

    # WACC
    w = calcular_wacc(de_ratio, kd, tax, beta_u, rf, erp, crp)
    moneda = p.get("moneda", "COP")

    # KPIs superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("WACC", f"{w['wacc']*100:.2f}%")
    c2.metric("Ke (CAPM)", f"{w['ke']*100:.2f}%")
    c3.metric("β apalancado", f"{w['beta_l']:.2f}")
    c4.metric("Sector", emp.get("sector", "—")[:28])

    st.info(f"**{empresa}** · moneda del modelo: **{moneda}** (cifras en miles de millones). Revisa parámetros antes de interpretar.")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1 · Pronóstico",
        "2 · Escenarios DCF",
        "3 · Auditoría",
        "4 · VPN / TIR",
        "5 · Sector",
    ])

    df_hist = df_historico(empresa)

    # ----- TAB 1: Pronóstico -----
    with tab1:
        st.subheader("Proyección de FCFF (drivers)")
        if df_hist.empty:
            st.warning("Sin histórico")
        else:
            st.dataframe(df_hist.style.format("{:.1f}"), use_container_width=True)
            df_proj = proyectar_drivers(df_hist, horizonte=horizonte, tax=tax)
            st.markdown("**Proyección**")
            st.dataframe(df_proj.style.format("{:.1f}"), use_container_width=True)

            # Fan chart Monte Carlo
            mc = monte_carlo_fcff(df_proj["FCFF"].values, n_sim=400, vol=0.18)
            fig, ax = plt.subplots(figsize=(10, 4.5))
            years_p = list(df_proj.index)
            ax.fill_between(years_p, mc["p10"], mc["p90"], alpha=0.25, color="#00A3A1", label="P10–P90")
            ax.plot(years_p, mc["p50"], color="#0A2540", lw=2, label="Mediana")
            ax.plot(years_p, df_proj["FCFF"].values, color="#F59E0B", lw=1.5, ls="--", label="Base drivers")
            if not df_hist.empty and "FCFF" in df_hist.columns:
                ax.plot(df_hist.index, df_hist["FCFF"], color="#64748B", marker="o", label="Histórico")
            ax.set_title("Fan chart FCFF")
            ax.set_ylabel(f"Miles de millones {moneda}")
            ax.legend(loc="best", fontsize=8)
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            plt.close()
            st.session_state["fcff_proj"] = df_proj["FCFF"].tolist()
            st.session_state["df_proj"] = df_proj

    # ----- TAB 2: Escenarios DCF -----
    with tab2:
        st.subheader("Escenarios pesimista · base · optimista")
        fcff = st.session_state.get("fcff_proj")
        if not fcff:
            st.warning("Ejecuta primero la pestaña **Pronóstico**.")
        else:
            escenarios = {
                "Pesimista": {"wacc_mult": 1.15, "g_mult": 0.6, "fcff_mult": 0.85},
                "Base": {"wacc_mult": 1.0, "g_mult": 1.0, "fcff_mult": 1.0},
                "Optimista": {"wacc_mult": 0.90, "g_mult": 1.3, "fcff_mult": 1.15},
            }
            rows = []
            for nombre_e, adj in escenarios.items():
                wacc_e = w["wacc"] * adj["wacc_mult"]
                g_e = g * adj["g_mult"]
                fcff_e = [x * adj["fcff_mult"] for x in fcff]
                val = valorar_dcf(
                    fcff_e, wacc_e, g_e,
                    deuda_neta=deuda_neta, caja=caja, nci=nci,
                    otros_claims=otros, asociados=asociados,
                    acciones=acciones if acciones > 0 else None,
                    mid_year=mid_year, g_max=g_max,
                )
                rows.append({
                    "Escenario": nombre_e,
                    "WACC %": round(wacc_e * 100, 2),
                    "g %": round(val["g_used"] * 100, 2),
                    "EV": round(val["EV"], 1) if val["EV"] is not None else None,
                    "Equity": round(val["Equity_Value"], 1) if val["Equity_Value"] is not None else None,
                    "VPS": round(val["value_per_share"], 1) if val["value_per_share"] is not None else None,
                })
            df_esc = pd.DataFrame(rows)
            st.dataframe(df_esc, use_container_width=True, hide_index=True)

            fig, ax = plt.subplots(figsize=(8, 4))
            x = np.arange(len(df_esc))
            width = 0.35
            ax.bar(x - width/2, df_esc["EV"], width, label="EV", color="#0A2540")
            ax.bar(x + width/2, df_esc["Equity"], width, label="Equity", color="#00A3A1")
            ax.set_xticks(x)
            ax.set_xticklabels(df_esc["Escenario"])
            ax.set_ylabel(f"Miles de millones {moneda}")
            ax.legend()
            ax.set_title("Enterprise Value vs Equity Value")
            st.pyplot(fig)
            plt.close()

            base = rows[1]
            st.success(
                f"**Base** → EV {base['EV']:,.0f} · Equity {base['Equity']:,.0f}"
                + (f" · VPS {base['VPS']:,.1f}" if base["VPS"] else "")
                + f" {moneda}"
            )

    # ----- TAB 3: Auditoría -----
    with tab3:
        st.subheader("Auditoría rápida de supuestos")
        checks = []
        # g < WACC
        ok_g = g < w["wacc"] - 0.005
        checks.append(("g < WACC − 0.5 pp", "OK" if ok_g else "REVISAR", f"g={g*100:.1f}% · WACC={w['wacc']*100:.1f}%"))
        # g techo macro
        ok_macro = g <= g_max + 1e-9
        checks.append(("g ≤ techo macro", "OK" if ok_macro else "REVISAR", f"g={g*100:.1f}% · techo={g_max*100:.1f}%"))
        # D/E razonable
        ok_de = de_ratio <= 3.0
        checks.append(("D/E ≤ 3x", "OK" if ok_de else "ALERTA", f"D/E={de_ratio:.2f}"))
        # Tax
        ok_tax = 0.10 <= tax <= 0.40
        checks.append(("Tax en rango 10–40%", "OK" if ok_tax else "REVISAR", f"tax={tax*100:.0f}%"))
        # Histórico
        ok_hist = len(df_hist) >= 3
        checks.append(("Histórico ≥ 3 años", "OK" if ok_hist else "REVISAR", f"n={len(df_hist)}"))
        # ROIC vs WACC (aprox)
        if not df_hist.empty and "NOPAT" in df_hist.columns:
            nopat_avg = float(df_hist["NOPAT"].tail(3).mean())
            ci = float(p.get("capital_invertido") or 1)
            roic = nopat_avg / ci if ci else 0
            checks.append(("ROIC vs WACC (aprox)", "OK" if roic >= w["wacc"] else "REVISAR", f"ROIC≈{roic*100:.1f}%"))

        df_chk = pd.DataFrame(checks, columns=["Prueba", "Estado", "Detalle"])
        st.dataframe(df_chk, use_container_width=True, hide_index=True)
        n_ok = (df_chk["Estado"] == "OK").sum()
        st.write(f"**{n_ok}/{len(df_chk)}** pruebas en verde.")

    # ----- TAB 4: VPN / TIR -----
    with tab4:
        st.subheader("Proyecto: VPN, TIR y Payback")
        fcff = st.session_state.get("fcff_proj")
        if not fcff:
            st.warning("Ejecuta primero la pestaña **Pronóstico**.")
        else:
            res = vpn_tir(fcff, inversion, w["wacc"])
            k1, k2, k3 = st.columns(3)
            k1.metric("VPN", f"{res['vpn']:,.1f}")
            k2.metric("TIR", f"{res['tir']*100:.1f}%" if res["tir"] is not None else "N/D")
            k3.metric("Payback (años)", f"{res['payback']}" if res["payback"] else "> horizonte")

            # Gráfico flujos
            fig, ax = plt.subplots(figsize=(9, 4))
            labels = ["t0"] + [f"t{i}" for i in range(1, len(res["flows"]))]
            colors = ["#EF4444" if v < 0 else "#10B981" for v in res["flows"]]
            ax.bar(labels, res["flows"], color=colors)
            ax.axhline(0, color="#64748B", lw=0.8)
            ax.set_title("Flujos del proyecto (incluye inversión inicial)")
            ax.set_ylabel(f"Miles de millones {moneda}")
            st.pyplot(fig)
            plt.close()

            if res["vpn"] is not None and res["vpn"] > 0:
                st.success("VPN positivo: el proyecto crea valor a este WACC (bajo los supuestos del modelo).")
            else:
                st.warning("VPN ≤ 0: bajo estos supuestos el proyecto no cubre el costo de capital.")

    # ----- TAB 5: Sector -----
    with tab5:
        st.subheader("Comparación rápida (catálogo BVC)")
        rows = []
        for nom, e in EMPRESAS.items():
            h = pd.DataFrame(e["historico"]).set_index("Año")
            ing = float(h["Ingresos"].iloc[-1])
            ebitda = float(h["EBITDA"].iloc[-1])
            margen = 100 * ebitda / ing if ing else 0
            fcff_last = float(h["FCFF"].iloc[-1])
            pr = e["params"]
            ww = calcular_wacc(pr["de_ratio"], pr["kd"], pr["tax"], pr["beta_u"], rf=0.12, erp=0.055)
            rows.append({
                "Empresa": nom.split("—")[0].strip(),
                "Ingresos": round(ing, 0),
                "Margen EBITDA %": round(margen, 1),
                "FCFF": round(fcff_last, 0),
                "D/E": pr["de_ratio"],
                "WACC %": round(ww["wacc"] * 100, 1),
                "EV/EBITDA ref": pr.get("exit_multiple"),
            })
        df_sec = pd.DataFrame(rows)
        st.dataframe(df_sec, use_container_width=True, hide_index=True)

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh(df_sec["Empresa"], df_sec["Margen EBITDA %"], color="#0A2540")
        ax.set_xlabel("Margen EBITDA %")
        ax.set_title("Margen EBITDA (último año del histórico)")
        st.pyplot(fig)
        plt.close()

    st.divider()
    st.caption(
        "Herramienta pedagógica · Datos de catálogo ilustrativos / Yahoo Finance · "
        "No es feed oficial BVC ni asesoría de inversión."
    )


if __name__ == "__main__":
    main()
