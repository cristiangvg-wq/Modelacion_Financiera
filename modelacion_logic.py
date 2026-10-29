"""
Lógica completa — Modelación Financiera Multisectorial
Extraída del notebook/Gradio original (todas las funciones de negocio).
No contiene la UI de Gradio; pensado para Streamlit u otro frontend.
"""
from pathlib import Path
import json
# =============================================================================
# PLATAFORMA MULTISECTORIAL DE MODELACIÓN FINANCIERA Y RIESGO
# Empresas cotizadas o privadas: Excel/CSV propio, datos públicos cuando estén disponibles
# Los emisores BVC son ejemplos de referencia, no el límite de la plataforma
# =============================================================================

import warnings
import math
# No ocultar advertencias globalmente: son relevantes para la calidad del modelo.
# Si alguna librería genera ruido, filtrar solo esa advertencia de forma específica.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
# statsmodels (ARIMA/ETS) se importa de forma diferida dentro de ajustar_ets/ajustar_arima:
# solo lo usan los métodos alternativos de la pestaña 1 y su importación en frío añade
# ~1–2 s y ~100 MB a CADA arranque del contenedor de Streamlit Cloud.
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
import hashlib
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

import threading as _threading
import time as _time
from collections.abc import MutableMapping as _MutableMapping

# =============================================================================
# ESTADO POR SESIÓN
# Streamlit importa este módulo una sola vez por proceso: cualquier dict global
# queda compartido entre TODOS los usuarios conectados. Los registros mutables
# (empresas descargadas, resultados de pestañas, credenciales del conector de
# mercado y último error de IA) se resuelven contra un almacén ligado al hilo
# de ejecución de la sesión mediante vincular_estado_sesion(). Sin vínculo
# (pruebas, scripts, notebooks) se usa un almacén por defecto del proceso.
# =============================================================================
_ESTADO_LOCAL = _threading.local()
_ESTADO_POR_DEFECTO = {}


def vincular_estado_sesion(almacen):
    """Asocia el hilo actual a `almacen` (p. ej. un dict dentro de st.session_state)."""
    _ESTADO_LOCAL.almacen = almacen if isinstance(almacen, dict) else None
    return almacen


def desvincular_estado_sesion():
    _ESTADO_LOCAL.almacen = None


def _almacen_estado():
    alm = getattr(_ESTADO_LOCAL, "almacen", None)
    return alm if alm is not None else _ESTADO_POR_DEFECTO


class _DictSesion(_MutableMapping):
    """Dict cuyo contenido vive en el almacén de la sesión activa."""

    def __init__(self, nombre, fabrica):
        self._nombre = nombre
        self._fabrica = fabrica

    def _d(self):
        alm = _almacen_estado()
        if self._nombre not in alm or not isinstance(alm[self._nombre], dict):
            alm[self._nombre] = self._fabrica()
        return alm[self._nombre]

    def __getitem__(self, k):
        return self._d()[k]

    def __setitem__(self, k, v):
        self._d()[k] = v

    def __delitem__(self, k):
        del self._d()[k]

    def __iter__(self):
        return iter(list(self._d().keys()))

    def __len__(self):
        return len(self._d())

    def copy(self):
        return dict(self._d())

    def __repr__(self):
        return f"_DictSesion({self._nombre}={self._d()!r})"


def _set_ia_error(msg):
    _almacen_estado()["_ia_last_error"] = msg


def _get_ia_error():
    return _almacen_estado().get("_ia_last_error")

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
# CATÁLOGO DE EMPRESAS PRECARGADAS (respaldo curado, no fuente principal)
# Orden de fuentes de una empresa: (1) estados financieros cargados por el usuario,
# (2) descarga de Yahoo Finance, (3) esta serie curada, con aviso visible de fuente.
# Los datos viven en datos_curados.json con fuente y estado de verificación por
# empresa. Los años 2016-2021 del catálogo anterior (valores redondos y crecimientos
# constantes) se eliminaron; EPM y Enel Colombia quedan sin serie: requieren EEFF.
# Montos en miles de millones de COP.
# =============================================================================
_RUTA_DATOS_CURADOS = Path(__file__).with_name("datos_curados.json")


def _leer_datos_curados(ruta=None):
    try:
        return json.loads(Path(ruta or _RUTA_DATOS_CURADOS).read_text(encoding="utf-8"))
    except Exception as exc:  # el app debe arrancar aunque falte el archivo
        warnings.warn(f"No se pudo leer datos_curados.json: {exc}")
        return {"empresas": {}, "series": {}, "reglas": {}}


_DATOS_CURADOS = _leer_datos_curados()
_COLS_HIST = ("Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC")


def _historico_desde_curado(h, tax):
    """Serie curada → histórico completo (ΔNWC, NOPAT y FCFF con la tasa de la empresa)."""
    años = [int(a) for a in h["Año"]]
    out = {"Año": años}
    for c in _COLS_HIST:
        out[c] = [float(v) for v in h[c]]
    dnwc, nopat, fcff = [], [], []
    for i in range(len(años)):
        d = 0.0 if i == 0 else out["NWC"][i] - out["NWC"][i - 1]
        n = out["EBIT"][i] * (1.0 - float(tax))
        dnwc.append(round(d, 4))
        nopat.append(round(n, 4))
        fcff.append(round(n + out["Depreciacion"][i] - out["CAPEX"][i] - d, 4))
    out.update({"Delta_NWC": dnwc, "NOPAT": nopat, "FCFF": fcff})
    return out


def _construir_catalogo(datos):
    emps = {}
    for nombre, c in (datos.get("empresas") or {}).items():
        sup, pu = c.get("supuestos") or {}, c.get("puente") or {}
        params = {
            "de_ratio": sup.get("de_ratio"), "kd": None,  # Kd por regla: _aplicar_reglas_catalogo()
            "tax": sup.get("tax"), "g": sup.get("g"), "beta_u": sup.get("beta_u"),
            "capital_invertido": sup.get("capital_invertido"), "inversion_inicial": sup.get("inversion_inicial"),
            "exit_multiple": sup.get("exit_multiple"),
            "deuda_neta": pu.get("deuda_neta"), "caja": pu.get("caja"), "nci": pu.get("nci"),
            "otros_claims": pu.get("otros_claims"), "asociados": pu.get("asociados"),
            "acciones": pu.get("acciones"), "moneda": datos.get("moneda", "COP"),
            "ciclico": c.get("ciclico"),
            "industria_damodaran": c.get("industria_damodaran"),
        }
        emp = {
            "ticker_bvc": c.get("ticker_bvc"), "ticker_yf": c.get("ticker_yf"),
            "sector": c.get("sector"), "descripcion": c.get("descripcion"),
            "calificacion": c.get("calificacion"), "verificacion": c.get("verificacion"),
            "fuente_curada": c.get("fuente_historico"), "fuente_puente": pu.get("fuente"),
            "params": params,
        }
        if c.get("historico"):
            emp["historico"] = _historico_desde_curado(c["historico"], sup.get("tax") or 0.35)
        emps[nombre] = emp
    return emps


EMPRESAS = _construir_catalogo(_DATOS_CURADOS)

# ---------------------------------------------------------------------------
# Registro en tiempo de ejecución: empresas descargadas vía Yahoo Finance
# (tickers arbitrarios fuera del catálogo BVC)
# ---------------------------------------------------------------------------
EMPRESAS_RUNTIME = _DictSesion("empresas_runtime", dict)  # nombre_display -> mismo shape que EMPRESAS[k] (por sesión)

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
# Catálogo de nemotécnicos de la Bolsa de Valores de Colombia (BVC/BVC-Nu).
# ÚNICA fuente que autoriza a añadir el sufijo Yahoo ".CL". Un ticker fuera de
# esta lista solo recibe ".CL" si el usuario lo escribe explícitamente o si
# Yahoo confirma cotización en COP (ver buscar_y_descargar_empresa).
_TICKERS_BVC = {
    # Energía, utilities e infraestructura
    "ISA", "GEB", "CELSIA", "EPM", "ENELAM", "ECOPETROL", "PROMIGAS", "TERPEL",
    "CNEC", "CONCONCRET", "ETB", "MINEROS",
    # Financiero
    "BVC", "BCOLOMBIA", "PFBCOLOM", "CIBEST", "PFCIBEST", "BANCOLOMBIA", "PFBANCOLOMBIA",
    "GRUPOAVAL", "PFAVAL", "BOGOTA", "OCCIDENTE", "POPULAR", "BBVACOL",
    "PFDAVVNDA", "CORFICOLCF", "PFCORFICOL", "GRUBOLIVAR", "GRUPOSURA", "PFGRUPSURA",
    # Holdings, industria y consumo
    "GRUPOARGOS", "PFGRUPOARG", "PFGRUPOARGOS", "CEMARGOS", "PFCEMARGOS", "CLH",
    "NUTRESA", "EXITO", "VALOREM", "ENKA", "FABRICATO", "TABLEMAC", "ELCONDOR",
    "PREVER", "HCOLSEL", "ICOLCAP",
}
_TICKERS_NUNCA_CL = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "NFLX",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "BRK-B", "BRK.B",
    "XOM", "CVX", "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "NEE", "DUK",
    "SO", "D", "AEP", "EXC", "ORCL", "CRM", "ADBE", "INTC", "AMD", "TSM",
    "AVGO", "QCOM", "KO", "PEP", "WMT", "COST", "HD", "MCD", "NKE", "DIS",
    "T", "VZ", "IBM", "CSCO", "BA", "CAT", "GE", "HON", "SPY", "QQQ",
    "PLTR", "UBER", "SHOP", "PYPL", "SBUX", "BABA", "PBR", "VALE", "AMX",
    # ADRs colombianos en NYSE: cotizan en USD, NUNCA llevan .CL
    "EC", "CIB", "AVAL", "TGLS",
}


def _tickers_bvc_conocidos():
    """Nemotécnicos BVC: lista curada + catálogo estático + descargas runtime .CL.

    Las descargas runtime solo aportan su base si quedaron registradas con sufijo
    .CL (cotización COP confirmada). Antes cualquier ticker descargado (p. ej.
    PLTR) entraba en este conjunto y la siguiente normalización lo convertía en
    PLTR.CL, contaminando tickers internacionales.
    """
    s = set(_TICKERS_BVC)
    for emp in _EMPRESAS_CATALOGO_INMUTABLE.values():
        for key in ("ticker_bvc", "ticker_yf"):
            raw = emp.get(key)
            if raw:
                u = str(raw).upper().strip()
                base = u[:-3] if u.endswith(".CL") else u.split(".")[0]
                if base and base not in _TICKERS_NUNCA_CL:
                    s.add(base)
    for emp in list(EMPRESAS_RUNTIME.values()):
        u = str(emp.get("ticker_yf") or "").upper().strip()
        if u.endswith(".CL"):
            base = u[:-3]
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
    """Candidatos Yahoo en orden de prioridad.

    - BVC conocido  → [BASE.CL]       (nunca se prueba la versión sin sufijo: en
                                       Yahoo podría ser otro emisor extranjero)
    - Internacional → [BASE]
    - Desconocido   → [BASE, BASE.CL] (el .CL solo se acepta si Yahoo confirma
                                       cotización en COP; ver _es_candidato_bvc_valido)
    """
    q = (query or "").strip().upper().replace(" ", "")
    if not q:
        return []
    if "." in q:
        return [asegurar_sufijo_cl_bvc(q)]
    base = q.split(".")[0]
    if base in _TICKERS_NUNCA_CL:
        return [base]
    if base in _tickers_bvc_conocidos():
        return [f"{base}.CL"]
    if base.isalpha() and len(base) >= 3:
        return [base, f"{base}.CL"]
    return [base]


def _es_candidato_bvc_valido(cand, info):
    """Un .CL fuera del catálogo solo es válido si Yahoo lo cotiza en COP."""
    c = str(cand or "").upper()
    if not c.endswith(".CL"):
        return True
    if c[:-3] in _tickers_bvc_conocidos():
        return True
    return str((info or {}).get("currency") or "").upper() == "COP"


def monedas_alineadas_por_ticker(ticker=None, nombre_empresa=None, emp=None):
    """
    Devuelve (moneda_modelo, moneda_precio) sin confundir moneda contable y cotización.
    BVC/.CL cotiza en COP; los estados pueden estar en COP o USD si Yahoo lo confirma.
    """
    tk = ticker
    if emp is None and nombre_empresa:
        emp = resolver_empresa(nombre_empresa) if "resolver_empresa" in globals() else None
    emp = emp or {}
    if not tk:
        tk = emp.get("ticker_yf") or emp.get("ticker_bvc")
    if tk:
        tk = asegurar_sufijo_cl_bvc(tk)

    fuente_emp = str(emp.get("fuente") or "")
    params_emp = emp.get("params") or {}

    def _norm_currency(value):
        value = str(value or "").strip().upper()
        value = value.replace("US$", "USD").replace("U$S", "USD")
        if value in ("COL", "COL$", "COP$"):
            return "COP"
        if value in ("US", "USA", "US DOLLAR"):
            return "USD"
        return value

    # financialCurrency describe los estados; currency normalmente describe la
    # cotización. Priorizar el campo explícito de Yahoo sobre la moneda heredada
    # del catálogo, que puede ser solo un valor por defecto.
    mm_runtime = _norm_currency(
        params_emp.get("financialCurrency") or emp.get("financialCurrency") or
        params_emp.get("moneda") or emp.get("moneda")
    )
    mp_runtime = _norm_currency(
        params_emp.get("currency") or params_emp.get("moneda_precio") or
        params_emp.get("precio_moneda") or emp.get("currency") or emp.get("moneda_precio")
    )
    es_bvc = bool(
        str(tk or "").upper().endswith(".CL") or emp.get("ticker_bvc") or
        (tk and es_ticker_bvc(tk))
    )

    # No dejar que la rama del catálogo tape metadatos Yahoo explícitos.
    if fuente_emp.lower().startswith("yahoo") and (mm_runtime or mp_runtime):
        if es_bvc:
            # La acción local BVC se cotiza en COP aunque los EEFF consolidados
            # del emisor estén en USD. El precio se convierte al comparar VPS.
            return mm_runtime or "COP", "COP"
        if mm_runtime and mp_runtime:
            return mm_runtime, mp_runtime
        if mm_runtime:
            return mm_runtime, mp_runtime or mm_runtime

    if nombre_empresa and (
        nombre_empresa in _EMPRESAS_CATALOGO_INMUTABLE or nombre_empresa in EMPRESAS
    ):
        return "COP", "COP"

    if es_bvc:
        # Si no hay moneda contable explícita, el respaldo curado BVC está en COP.
        return "COP", "COP"

    if tk:
        base = str(tk).upper().split(".")[0]
        if base in _TICKERS_NUNCA_CL:
            return "USD", "USD"
        if base.isalpha() and 1 <= len(base) <= 5 and "." not in str(tk):
            if not es_ticker_bvc(base):
                if fuente_emp.lower().startswith("yahoo"):
                    return mm_runtime or "USD", mp_runtime or mm_runtime or "USD"

    pais = str(emp.get("pais") or "").upper()
    if "COLOMBIA" in pais or pais in ("CO", "COL"):
        return "COP", "COP"
    mon = _norm_currency(emp.get("moneda") or params_emp.get("moneda"))
    if mon == "COP":
        return "COP", "COP"
    if mon == "USD":
        return "USD", "USD"
    if emp.get("ticker_bvc"):
        return "COP", "COP"
    if fuente_emp.lower().startswith("yahoo"):
        return mm_runtime or "USD", mp_runtime or mm_runtime or "USD"
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
RESULTADOS_SESION = _DictSesion(
    "resultados_sesion",
    lambda: {"empresa": None, "tabs": {}},  # "1".."7" -> dict serializable
)


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


def metricas_valoracion_sesion(nombre_empresa):
    """Métricas numéricas de la última corrida de la pestaña 4 para ESTA empresa.

    Devuelve None si no hay corrida o si pertenece a otra empresa (nunca mezcla).
    """
    if RESULTADOS_SESION.get("empresa") != nombre_empresa:
        return None
    t4 = (RESULTADOS_SESION.get("tabs") or {}).get("4") or {}
    m = t4.get("metricas")
    if isinstance(m, dict) and m.get("empresa") == nombre_empresa:
        return dict(m)
    return None


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
        r"\b(COMPRAR|MANTENER|VENDER|INVERTIR\s+CONDICIONALMENTE|NO\s+INVERTIR|INVERTIR)\b",
    ):
        mm = re.search(pat, raw, flags=re.I)
        if mm:
            recomendacion = _limpia(mm.group(1) if mm.lastindex else mm.group(0))
            break

    # PUNTAJE
    for pat in (
        r"PUNTAJE\s+DE\s+(?:VIABILIDAD|CONVICCI[ÓO]N)\s*[:：]\s*([^\n]+)",
        r"Puntaje\s+de\s+(?:viabilidad|convicci[oó]n)\s*[:：]\s*([^\n]+)",
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
    # Finanzas / bolsas
    "financial": ["JPM", "BAC", "WFC", "GS", "MS", "C"],
    "banks": ["JPM", "BAC", "WFC", "C", "USB", "PNC"],
    "bancos": ["JPM", "BAC", "WFC", "C", "USB", "PNC"],
    "insurance": ["BRK-B", "MET", "PRU", "AIG", "ALL"],
    "capital markets": ["GS", "MS", "SCHW", "BLK", "SPGI", "ICE", "CME", "NDAQ"],
    "exchange": ["ICE", "CME", "NDAQ", "CBOE", "SPGI"],
    "bolsa": ["ICE", "CME", "NDAQ", "CBOE"],
    "valores": ["ICE", "CME", "NDAQ", "SPGI"],
    "servicios financieros": ["JPM", "BAC", "GS", "MS", "SCHW", "ICE"],
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


def _familia_sector(sector_texto, industry_texto=""):
    """Familia comparable (energy, financial, …) para no mezclar sectores."""
    blob = _normalizar_texto_sector(f"{sector_texto or ''} {industry_texto or ''}")
    if not blob.strip():
        return "other"
    familias = [
        ("financial", ("financial", "bank", "banco", "insurance", "capital market", "bolsa", "valores", "fintech", "exchange", "servicios financieros", "broker", "securities")),
        ("energy", ("energy", "utilit", "oil", "gas", "electric", "petroleo", "energia", "transmision", "renovable", "generacion", "midstream", "power", "pipeline")),
        ("technology", ("technology", "software", "semiconductor", "information technology", "hardware")),
        ("healthcare", ("healthcare", "pharma", "biotech", "drug", "medical")),
        ("consumer", ("consumer", "retail", "automotive", "food", "beverage")),
        ("industrials", ("industrial", "aerospace", "defense", "machinery", "transport")),
        ("materials", ("basic materials", "mining", "steel", "chemical")),
        ("telecom", ("telecom", "communication services", "media")),
        ("real_estate", ("real estate", "reit", "inmobili")),
    ]
    for fam, keys in familias:
        if any(k in blob for k in keys):
            return fam
    if "infraestructura" in blob and any(k in blob for k in ("energia", "electric", "transmision", "gas")):
        return "energy"
    return "other"


def filtrar_empresas_mismo_sector(sector_focal, industry_focal=""):
    """Catálogo + runtime de la misma familia de sector que la focal."""
    matches = {}
    fam_f = _familia_sector(sector_focal, industry_focal)
    for nombre, emp in list(EMPRESAS.items()) + list(EMPRESAS_RUNTIME.items()):
        sec = emp.get("sector", "") or ""
        if fam_f != "other" and _familia_sector(sec) == fam_f:
            matches[nombre] = emp
        elif fam_f == "other":
            ta = set(_normalizar_texto_sector(f"{sector_focal} {industry_focal}").split())
            tb = set(_normalizar_texto_sector(sec).split())
            stop = {"de", "y", "the", "and", "or", "a", "la", "el", "del"}
            ta = {t for t in ta if len(t) >= 4 and t not in stop}
            tb = {t for t in tb if len(t) >= 4 and t not in stop}
            if ta & tb:
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


def buscar_y_descargar_empresa(query, peers_tickers="", nombre_display=None):
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
            if not _es_candidato_bvc_valido(cand, info):
                continue
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
    # El downloader ya entrega solo ejercicios cerrados (por fecha de cierre).
    cerrado_hasta = df_fin.attrs.get("ejercicio_cerrado_hasta")
    df_mm.attrs.update(dict(df_fin.attrs))

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
        info = _completar_info_yahoo(info, t_obj, used_ticker)
        # Consenso de analistas de ingresos (año en curso y siguiente): base de la etapa 1 del
        # modelo de tres etapas para empresas de EE. UU.
        if _mercado_desde_pais(info.get("country")) == "US":
            try:
                re_ = getattr(t_obj, "revenue_estimate", None)
                if re_ is not None and not getattr(re_, "empty", True):
                    info = dict(info)
                    info["_revenue_estimate"] = re_
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
    if nombre_display:
        # Empresa precargada: los datos descargados se registran bajo su nombre de catálogo.
        display_name = nombre_display

    # financialCurrency = moneda de los EEFF (modelo); currency = moneda del precio de cotización.
    # En ADRs (ej. EC) pueden diferir: EEFF en COP, precio en USD → upside no comparable sin FX.
    fin_cur = (info.get("financialCurrency") or info.get("currency") or "")
    px_cur = (info.get("currency") or fin_cur or "")
    if isinstance(fin_cur, str) and fin_cur.upper() in ("US$", "U$S"):
        fin_cur = "USD"
    if isinstance(px_cur, str) and px_cur.upper() in ("US$", "U$S"):
        px_cur = "USD"
    # Propagar por separado la moneda contable y la moneda de cotización.
    # No sobrescribir una moneda declarada por Yahoo sin convertir los importes.
    used_ticker = asegurar_sufijo_cl_bvc(used_ticker) or used_ticker
    ticker_local_bvc = str(used_ticker).upper().endswith(".CL")
    fin_cur = str(info.get("financialCurrency") or fin_cur or "").upper().replace("US$", "USD").replace("COL", "COP")
    px_cur = str(info.get("currency") or px_cur or "").upper().replace("US$", "USD").replace("COL", "COP")
    if ticker_local_bvc:
        # El downloader ya bloquea EEFF explícitamente no-COP. Si Yahoo no informa
        # moneda contable/cotización, COP se usa como inferencia por el mercado local.
        fin_cur = fin_cur or "COP"
        px_cur = px_cur or "COP"
    else:
        # Para acciones US inferir USD solo cuando Yahoo no trae moneda; no reetiquetar
        # EEFF que declaren otra divisa (p. ej. ADRs con EEFF COP y precio USD).
        es_ticker_us = str(used_ticker).split(".")[0].upper() in _TICKERS_NUNCA_CL
        fin_cur = fin_cur or ("USD" if es_ticker_us else "USD")
        px_cur = px_cur or ("USD" if es_ticker_us else fin_cur)
    # No se permite que la regla BVC reetiquete EEFF en USD como COP sin FX.
    # El downloader ya bloquea ese caso para .CL; para tickers ADR se preservan
    # monedas distintas y el upside queda no comparable hasta convertir con FX.
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
        "ejercicio_cerrado_hasta": cerrado_hasta,
        # Perfil para el informe (pestaña 7)
        "industria": industry,
        "ciudad": info.get("city") or "",
        "web": info.get("website") or "",
        "empleados": info.get("fullTimeEmployees"),
        "bolsa": info.get("fullExchangeName") or info.get("exchange") or "",
        "descripcion_completa": (info.get("longBusinessSummary") or "").strip(),
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
    """Datos descargados en la sesión primero (también para empresas precargadas que
    se descargaron de Yahoo con preparar_empresa); el catálogo curado es respaldo."""
    if nombre_empresa in EMPRESAS_RUNTIME:
        return EMPRESAS_RUNTIME[nombre_empresa]
    if nombre_empresa in _EMPRESAS_CATALOGO_INMUTABLE:
        _restaurar_entrada_catalogo(nombre_empresa)
    if nombre_empresa in EMPRESAS:
        return EMPRESAS[nombre_empresa]
    # match parcial runtime
    if nombre_empresa and len(str(nombre_empresa).strip()) >= 4:
        q = str(nombre_empresa).strip().lower()
        hits = [v for k, v in EMPRESAS_RUNTIME.items() if q in k.lower() or k.lower() in q]
        if len(hits) == 1:  # solo si es inequívoco: evita mezclar datos de otra empresa
            return hits[0]
    return None


_PARAMS_PUENTE_CURADO = ("nci", "asociados", "otros_claims")


def _deuda_y_caja_balance(bs):
    """(deuda total, caja) del renglón más reciente del balance Yahoo, en unidades de la moneda (o None)."""
    if bs is None or not hasattr(bs, "index") or getattr(bs, "empty", True):
        return None, None
    idx = {str(i).strip().lower(): i for i in bs.index}

    def _primero(nombres):
        for n in nombres:
            k = idx.get(n.lower())
            if k is None:
                continue
            for v in bs.loc[k].values:
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv == fv:
                    return fv
        return None
    deuda = _primero(["Total Debt"])
    if deuda is None:
        partes = [_primero([n]) for n in ("Long Term Debt", "Current Debt", "Short Term Debt")]
        partes = [x for x in partes if x is not None]
        deuda = sum(partes) if partes else None
    # Mismo alcance que totalCash de Yahoo (incluye inversiones de corto plazo).
    caja = _primero(["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
    return deuda, caja


def preparar_empresa(nombre_empresa, forzar=False):
    """Obtiene los datos de una empresa precargada: Yahoo primero, curado como respaldo.

    Devuelve {"fuente": "yahoo"|"curado"|"sin_datos"|"no_catalogo", "detalle": str}.
    El resultado se guarda por sesión (estado_fuente_empresa) para mostrarlo en la UI.
    Si Yahoo trae la serie, también se usan sus parámetros (deuda, caja, acciones, β,
    tasa efectiva); el catálogo solo completa partidas que Yahoo no reporta (NCI,
    asociadas) o un β que Yahoo no trae.
    """
    estados = _almacen_estado().setdefault("fuente_empresa", {})
    if nombre_empresa not in EMPRESAS:
        return {"fuente": "no_catalogo", "detalle": ""}
    if not forzar and nombre_empresa in estados:
        return estados[nombre_empresa]
    cat = EMPRESAS[nombre_empresa]
    tk = cat.get("ticker_yf")
    estado = None
    if tk and HAS_YF:
        try:
            ok, html, _disp, _pt = buscar_y_descargar_empresa(tk, nombre_display=nombre_empresa)
        except Exception as exc:
            ok, html = False, str(exc)
        if ok and nombre_empresa in EMPRESAS_RUNTIME:
            rt = EMPRESAS_RUNTIME[nombre_empresa]
            p, pc = rt.setdefault("params", {}), cat.get("params") or {}
            completados = []
            for k in _PARAMS_PUENTE_CURADO:
                if not float(p.get(k) or 0) and float(pc.get(k) or 0):
                    p[k] = pc[k]
                    completados.append(k)
            # Sin deuda reportada por Yahoo (ni en info ni en el balance) no se puede suponer
            # deuda 0: se usa la del catálogo curado, con su caja, para que el puente cuadre.
            if p.get("deuda_bruta") is None and pc.get("deuda_neta") is not None:
                p["deuda_neta"] = pc["deuda_neta"]
                p["deuda_es_bruta"] = False
                p["deuda_fuente"] = "catálogo curado (Yahoo sin deuda)"
                completados.append("deuda_neta")
                if pc.get("caja") is not None:
                    p["caja"] = pc["caja"]
            # Industria de Damodaran del catálogo (curada) sobre la que infiere Yahoo: Celsia es «Power», no
            # «Green & Renewable Energy» (0,46 frente a 0,59 desapalancada en emergentes).
            if pc.get("industria_damodaran"):
                _mk = _mercado_desde_pais(rt.get("pais")) or "CO"
                _bd = damodaran_beta(explicita=pc["industria_damodaran"], mercado=_mk)
                if _bd:
                    _ref = (f"{_bd['fuente']}: {_bd['industria']} {_bd.get('region')} {float(_bd['beta_u']):.2f} "
                            f"({int(_bd['n_firmas'] or 0)} empresas, corregida por caja)")
                    if str(p.get("beta_fuente", "")).startswith("bottom-up"):
                        p["beta_u"] = round(float(_bd["beta_u"]), 4)
                        p["beta_fuente"] = f"bottom-up {_ref} (industria del catálogo; regresión no informativa)"
                    p["beta_industria_u"] = round(float(_bd["beta_u"]), 4)
                    p.pop("beta_brecha_industria", None)
                    if not str(p.get("beta_fuente", "")).startswith("bottom-up") and abs(float(p.get("beta_u") or 0) - float(_bd["beta_u"])) >= 0.15:
                        p["beta_brecha_industria"] = round(float(_bd["beta_u"]) - float(p.get("beta_u") or 0), 4)
            if str(p.get("beta_fuente", "")).startswith("proxy") and pc.get("beta_u"):
                p["beta_u"] = pc["beta_u"]
                p["beta_fuente"] = "catálogo (Yahoo sin β)"
                completados.append("beta_u")
            # Costo de la deuda: la calificación REAL del emisor (catálogo) manda sobre la sintética de Yahoo
            # (Damodaran: la sintética es para quien no tiene calificación).
            if cat.get("calificacion") and pc.get("kd"):
                p["kd"], p["kd_fuente"] = pc["kd"], pc.get("kd_fuente") or f"calificación {cat['calificacion']}"
                p.pop("calificacion_sintetica", None)
            rt["sector"] = cat.get("sector") or rt.get("sector")
            rt["descripcion"] = cat.get("descripcion") or rt.get("descripcion")
            rt["calificacion"] = cat.get("calificacion")
            detalle = "Estados financieros y mercado descargados de Yahoo Finance."
            if completados:
                detalle += f" Completado con catálogo curado: {', '.join(completados)}."
            estado = {"fuente": "yahoo", "detalle": detalle}
        else:
            motivo = _html_a_texto(html, 200) if html else "sin respuesta"
            estado = {"fuente": "curado", "detalle": f"Yahoo no disponible ({motivo})."}
    if estado is None or estado["fuente"] != "yahoo":
        base = (estado or {}).get("detalle", "Sin ticker en Yahoo.")
        if cat.get("historico"):
            estado = {"fuente": "curado", "detalle": (
                f"{base} Respaldo curado ({_DATOS_CURADOS.get('as_of', 's/f')}): "
                f"{cat.get('fuente_curada') or 'serie curada'} Verificación: {cat.get('verificacion') or 'N/D'}."
            )}
        else:
            estado = {"fuente": "sin_datos", "detalle": (
                f"{base} Sin serie curada verificada: carga los estados financieros de la empresa."
            )}
    estados[nombre_empresa] = estado
    return estado


def estado_fuente_empresa(nombre_empresa):
    """Fuente de datos vigente de la empresa en esta sesión (para mostrar en la UI)."""
    return (_almacen_estado().get("fuente_empresa") or {}).get(nombre_empresa)


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
MERCADO_CONFIG = _DictSesion(
    "mercado_config",
    lambda: {
        "proveedor": "yahoo",          # yahoo | api_key | manual
        "api_key": "",                 # credencial del usuario: NUNCA compartida entre sesiones
        "api_base_url": "",            # opcional: endpoint propio del vendor
        "api_timeout": 12,
    },
)


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
            hist = t.history(period="15d", auto_adjust=False)
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
            # Yahoo entrega regularMarketChangePercent YA en puntos porcentuales
            # (-0.31 = -0,31 %). Multiplicar por 100 cuando |x|<1 inflaba 100x
            # cualquier variación diaria pequeña.
            ch = _finite_or_none(info.get("regularMarketChangePercent"))
            if ch is None:
                ch = _yf_fast_get(fi, "regular_market_change_percent", "change_percent")
            if ch is not None:
                cambio_pct = ch

        # --- Capitalización ---
        # Capitalización bursátil = precio × acciones. El EV (incluye deuda neta) NO
        # es un sustituto válido: inflaría P/VL y múltiplos de equity.
        mcap = _finite_or_none(info.get("marketCap"))
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
        # P/E trailing → forward. El PEG (P/E ÷ crecimiento) es otra métrica y no
        # puede usarse como respaldo del P/E.
        pe = (
            _finite_or_none(info.get("trailingPE"))
            or _finite_or_none(info.get("forwardPE"))
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
            # Moneda de cotización declarada por Yahoo; solo se infiere por mercado
            # cuando el proveedor no la informa.
            "moneda": (
                str(info.get("currency") or "").upper()
                or ("COP" if str(ticker_yf or "").upper().endswith(".CL") else "USD")
            ),
            "cambio_pct": cambio_pct,
            "market_cap": mcap,
            "beta": beta,
            "pe": pe,
            "enterprise_to_ebitda": ev_ebitda,
            "proveedor": "yahoo",
            "fuente": f"yahoo:{ticker_yf}",
            "fecha_precio": str(hist.index[-1].date()) if hist is not None and len(hist) > 0 else None,
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


# Caché de cotizaciones (TTL). Dos objetivos:
#  1) rendimiento: cada pestaña pedía la misma cotización a Yahoo (2-3 HTTP c/u);
#  2) consistencia cruzada: todas las pestañas de una corrida leen la MISMA
#     instantánea de precio, nunca ticks distintos tomados segundos aparte.
MERCADO_CACHE_TTL_SEG = 300
_CACHE_MERCADO = {}
_CACHE_MERCADO_LOCK = _threading.Lock()


def limpiar_cache_mercado(ticker=None):
    with _CACHE_MERCADO_LOCK:
        if ticker is None:
            _CACHE_MERCADO.clear()
        else:
            t = str(ticker).upper()
            for k in [k for k in _CACHE_MERCADO if k[1] == t]:
                _CACHE_MERCADO.pop(k, None)


def obtener_datos_mercado_bvc(ticker_yf, ticker_bvc=None, proveedor=None):
    """Fachada cacheada (TTL) del conector de mercado; ver _obtener_datos_mercado_sin_cache."""
    tk = asegurar_sufijo_cl_bvc(ticker_yf) if ticker_yf else asegurar_sufijo_cl_bvc(ticker_bvc)
    prov = (proveedor or MERCADO_CONFIG.get("proveedor") or "yahoo").strip().lower()
    # La URL del vendor forma parte de la llave; la API key NO se guarda en ella.
    clave = (prov, str(tk or "").upper(), str(ticker_bvc or "").upper(),
             MERCADO_CONFIG.get("api_base_url") or "")
    ahora = _time.monotonic()
    with _CACHE_MERCADO_LOCK:
        hit = _CACHE_MERCADO.get(clave)
        if hit and ahora - hit[0] < MERCADO_CACHE_TTL_SEG:
            return dict(hit[1])
    res = _obtener_datos_mercado_sin_cache(ticker_yf, ticker_bvc=ticker_bvc, proveedor=proveedor)
    if isinstance(res, dict) and res.get("ok"):
        res.setdefault("consultado_utc", _time.strftime("%Y-%m-%d %H:%M UTC", _time.gmtime()))
        with _CACHE_MERCADO_LOCK:
            _CACHE_MERCADO[clave] = (ahora, dict(res))
    return res


def _obtener_datos_mercado_sin_cache(ticker_yf, ticker_bvc=None, proveedor=None):
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

# Series curadas (miles de millones de la moneda del emisor), leídas de datos_curados.json.
# Solo respaldo: se usan si no hay archivo del usuario ni descarga de Yahoo.
def _series_curadas(datos):
    out = {}
    for nombre, c in (datos.get("empresas") or {}).items():
        h = c.get("historico")
        if h:
            out[nombre] = {"fuente": c.get("fuente_historico") or "serie curada", "años": list(h["Año"]),
                           **{k: list(h[k]) for k in _COLS_HIST}}
    for nombre, blk in (datos.get("series") or {}).items():
        out[nombre] = dict(blk)
    return out


DATOS_PUBLICOS_CURADOS = _series_curadas(_DATOS_CURADOS)


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

        # Moneda contable real de los EEFF, separada de la moneda de cotización.
        # En un ticker BVC (.CL) se espera COP: si Yahoo declara otra divisa,
        # no etiquetar cifras como COP ni convertirlas con FX spot; detener y pedir
        # una fuente local/EEFF consolidados. Para ADRs no BVC sí se permite COP/USD
        # distinto y el comparador de upside debe bloquearse si no hay conversión.
        fin_currency_raw = info.get("financialCurrency") or info.get("currency")
        fin_currency = str(fin_currency_raw or "").upper().replace("US$", "USD").replace("COL", "COP")
        es_bvc_local = str(ticker_yf).upper().endswith(".CL")
        # Emisores BVC que reportan en USD (p. ej. MINEROS): antes se bloqueaban por
        # completo. Ahora el modelo se construye en la moneda de reporte (sin
        # convertir históricos con FX spot) y solo el PRECIO se convierte a esa
        # moneda con la tasa spot al calcular el upside (calcular_vps_y_upside).

        # Tasa efectiva desde los propios estados (Yahoo "Tax Rate For Calcs" o
        # impuesto/utilidad antes de impuestos). Antes un emisor US sin
        # effectiveTaxRate en `info` (campo casi nunca presente) caía al 21 %
        # estatutario aunque pagara ~30 % (XOM), sobrestimando NOPAT y FCFF.
        if tax_efectiva is None:
            try:
                tasas = []
                r_rate = _yf_pick_row(fin, ["Tax Rate For Calcs"])
                if r_rate is not None:
                    tasas = [float(v) for v in r_rate.values if v is not None and np.isfinite(float(v))]
                if not tasas:
                    r_tax = _yf_pick_row(fin, ["Tax Provision", "Income Tax Expense"])
                    r_pre = _yf_pick_row(fin, ["Pretax Income", "Income Before Tax"])
                    if r_tax is not None and r_pre is not None:
                        for c in r_tax.index:
                            tv, pv = r_tax.get(c), r_pre.get(c)
                            if tv is not None and pv is not None and np.isfinite(float(tv)) and float(pv) > 0:
                                tasas.append(float(tv) / float(pv))
                tasas = [t for t in tasas[:3] if 0.0 < t < 0.55]
                if tasas:
                    tax_efectiva = float(np.median(tasas))
            except Exception:
                pass

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
        # EBIT OPERATIVO. El renglón «EBIT» de Yahoo es utilidad antes de impuestos + intereses:
        # incluye el método de participación y otros no operativos. Como el puente EV→Equity
        # ya suma las inversiones en asociadas, usarlo las contaba dos veces (GEB: EBIT Yahoo
        # 5.118 vs utilidad operativa 2.551 miles de millones COP en 2025; ISA 7.415 vs 6.875).
        ebit_yf = _series_from_yf_row(_yf_pick_row(fin, ["EBIT"]), fac)
        ebit = _series_from_yf_row(_yf_pick_row(fin, ["Operating Income", "Ingresos operativos"]), fac) or ebit_yf
        dep = _series_from_yf_row(_yf_pick_row(fin, ["Reconciled Depreciation", "Depreciation", "Depreciación"]), fac)
        ebitda_yf = _series_from_yf_row(_yf_pick_row(fin, ["EBITDA"]), fac)
        # EBITDA coherente con el EBIT operativo (utilidad operativa + D&A).
        ebitda = {y: ebit[y] + dep[y] for y in ebit if y in dep} if ebit is not ebit_yf else {}
        for y, v in ebitda_yf.items():
            ebitda.setdefault(y, v)
        # Ingreso por participadas (para valorar las asociadas en el puente, no en los flujos).
        eq_row = _series_from_yf_row(_yf_pick_row(fin, ["Earnings From Equity Interest"]), fac)
        otros_no_op = _series_from_yf_row(_yf_pick_row(fin, ["Other Non Operating Income Expenses"]), fac)
        especiales = _series_from_yf_row(_yf_pick_row(fin, ["Special Income Charges"]), fac)
        # EE. UU.: el residuo EBIT − utilidad operativa incluye los intereses que rinde la caja (MSFT ≈ 9 mil
        # millones USD). La caja ya se suma en el puente; capitalizar también sus intereses la contaría dos veces.
        intereses_caja = (_series_from_yf_row(_yf_pick_row(fin, ["Interest Income Non Operating", "Interest Income"]), fac)
                          if _mercado_desde_pais(info.get("country")) == "US" else {})
        ingreso_participadas = {}
        for y in ebit:
            if y in eq_row:
                ingreso_participadas[y] = eq_row[y]
            elif y in ebit_yf and ebit is not ebit_yf:
                ingreso_participadas[y] = (ebit_yf[y] - ebit[y] - otros_no_op.get(y, 0.0) - especiales.get(y, 0.0)
                                           - intereses_caja.get(y, 0.0))

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

        # Solo ejercicios CERRADOS: se decide por la fecha de cierre de cada columna,
        # no por el año calendario. Antes se descartaba todo ejercicio rotulado con el
        # año en curso, de modo que NKE (cierre 31-may-2026) perdía su último año fiscal.
        hoy = pd.Timestamp(datetime.now().date())
        cerrados = set()
        for col in fin.columns:
            try:
                ts = pd.Timestamp(col)
                if ts.tz is not None:
                    ts = ts.tz_localize(None)
                if ts <= hoy:
                    cerrados.add(int(ts.year))
            except Exception:
                try:
                    y = int(str(col)[:4])
                    if y < hoy.year:
                        cerrados.add(y)
                except Exception:
                    pass
        years = [y for y in years if y in cerrados]

        # NWC operativo desde el balance (activo corriente − caja e inversiones CP −
        # (pasivo corriente − deuda CP)). Si falta, se usa la razón NWC/ingresos del
        # año real más cercano; el 5 % genérico queda solo como último recurso.
        nwc_real = {}
        bs = getattr(t, "balance_sheet", None)
        if bs is not None and not getattr(bs, "empty", True):
            try:
                ca = _series_from_yf_row(_yf_pick_row(bs, ["Current Assets", "Total Current Assets"]), fac)
                cl = _series_from_yf_row(_yf_pick_row(bs, ["Current Liabilities", "Total Current Liabilities"]), fac)
                cash_s = _series_from_yf_row(_yf_pick_row(bs, [
                    "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents",
                ]), fac)
                std = _series_from_yf_row(_yf_pick_row(bs, [
                    "Current Debt And Capital Lease Obligation", "Current Debt",
                ]), fac)
                for y in set(ca) & set(cl):
                    nwc_real[y] = (ca[y] - cash_s.get(y, 0.0)) - (cl[y] - std.get(y, 0.0))
            except Exception:
                nwc_real = {}

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
            if y in nwc_real:
                nwc = float(nwc_real[y])
            elif nwc_real:
                y_ref = min(nwc_real, key=lambda k: abs(k - y))
                ing_ref = rev.get(y_ref)
                nwc = abs(ing) * (nwc_real[y_ref] / ing_ref) if ing_ref else abs(ing) * 0.05
            else:
                nwc = abs(ing) * 0.05
            delta = 0.0 if prev_nwc is None else nwc - prev_nwc
            # Unificar la política fiscal con el motor de proyección: sin escudo fiscal automático por pérdidas.
            nopat = float(calcular_nopat(eb, tax_efectiva))
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
        # Metadata no cambia magnitudes: importes en miles de millones de la
        # moneda de los EEFF. Mantenerla permite auditar COP vs USD aguas abajo.
        df.attrs["moneda"] = fin_currency or ("COP" if es_bvc_local else "USD")
        df.attrs["moneda_fuente"] = "Yahoo financialCurrency" if fin_currency else "inferida_por_ticker"
        df.attrs["unidad"] = "miles de millones"
        df.attrs["ticker_yf"] = ticker_yf
        df.attrs["ejercicio_cerrado_hasta"] = int(max(df.index))
        df.attrs["nwc_fuente"] = "balance Yahoo" if nwc_real else "proxy 5 % de ingresos"
        df.attrs["tax_efectiva"] = tax_efectiva
        df.attrs["ebit_fuente"] = "Operating Income (Yahoo)" if ebit is not ebit_yf else "EBIT (Yahoo)"
        _ult = int(max(df.index))
        if _ult in ingreso_participadas and np.isfinite(ingreso_participadas[_ult]):
            df.attrs["ingreso_participadas"] = float(ingreso_participadas[_ult])
        while len(df) > 3 and abs(float(df["Ingresos"].iloc[-1])) < 1e-9:
            df = df.iloc[:-1]
        extra = f" Omitidos {omitidos}." if omitidos else ""
        return df, (
            f"Descargado desde Yahoo Finance ({ticker_yf}), {len(df)} años "
            f"({int(df.index.min())}–{int(df.index.max())}). "
            f"Tax efectiva usada={tax_efectiva:.1%}. "
            f"NWC: {df.attrs['nwc_fuente']}; CAPEX real cuando disponible.{extra}"
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
        # No sustituir una serie financiera no curada por datos ficticios. Nutresa requiere
        # reconciliar los estados consolidados 2025/2024 y el cambio extraordinario de deuda
        # asociado a activos financieros; hasta incorporar la serie completa, explicitar el límite.
        nombre_norm = str(nombre_empresa or "").upper()
        if "NUTRESA" in nombre_norm:
            return None, (
                "NUTRESA: no hay serie histórica consolidada curada en el repositorio. "
                "No se debe interpretar una valoración basada en Yahoo con CAPEX/NWC proxy "
                "como resultado validado. Cargar/reconciliar EEFF consolidados oficiales "
                "2025 y 2024, deuda, caja, NCI, asociadas y flujos antes de concluir Equity."
            )
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
    # Nutresa solo tiene dos ejercicios consolidados incorporados (2024-2025).
    # Marcar explícitamente la excepción; no rebajar el mínimo para Excel/Yahoo u otras empresas.
    if "NUTRESA" in str(nombre_empresa or "").upper():
        df.attrs["serie_curada_corta"] = "NUTRESA_2024_2025"
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
    nombre_norm = str(nombre_empresa or "").upper()
    # Nutresa usa siempre la serie consolidada explícita de 2024-2025. No permitir que
    # Yahoo o un histórico genérico del catálogo la suplanten; solo hay dos años reconciliados.
    if "NUTRESA" in nombre_norm:
        df_n, msg_n = descargar_financieros_curados("NUTRESA — Grupo Nutresa S.A.")
        if df_n is not None and len(df_n) == 2:
            return df_n, msg_n + " Serie corta: solo 2024-2025; D&A redondeada y NWC derivado.", "PUBLICA_CURADA_NUTRESA"

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
                if emp.get("ejercicio_cerrado_hasta"):
                    df.attrs["ejercicio_cerrado_hasta"] = int(emp["ejercicio_cerrado_hasta"])
                # La fuente en el mensaje permite a procedencia_datos rotularla (antes «Mixto / revisar fuente»
                # para todas las empresas descargadas de Yahoo, incluidas ISA, GEB y Ecopetrol).
                _fte = emp.get("fuente") or "fuente no indicada"
                return df, (f"Histórico en sesión ({emp.get('ticker_yf') or nombre_empresa}) · {_fte}, {len(df)} años "
                            f"válidos{detalle}."), "PUBLICA_RUNTIME"

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
# g_lp = crecimiento NOMINAL de largo plazo en la moneda del mercado (inflación esperada
# + crecimiento real bajo). Es el punto al que converge el crecimiento explícito de los
# ingresos. Antes era un 3 % fijo para todas las monedas: en COP, con inflación implícita
# de ~6 %, eso equivalía a suponer una contracción real perpetua del 3 % anual.
CAPM_POR_MERCADO = {
    # US: Treasury 10 años 4,99 % al 27-oct-2026 (Forbes Advisor / Treasury). Antes 4,5 %.
    "US": {"rf": 0.05, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.015, "g_lp": 0.03},
    # CO: TES 10 años en COP por encima de 13 % (La República, 21-oct-2026). Antes 12 %.
    # Inflación implícita (breakeven TES COP vs UVR) a 10 años: 6,15 % (BanRep, 21-ago-2026).
    # rf_bruto = TES 10 años 13,18 % (BanRep, curva cero cupón, 16-oct-2026). Con datos de Damodaran,
    # _aplicar_damodaran_a_capm() fija rf = TES − spread de default y ERP = madura + riesgo país.
    "CO": {"rf": 0.13,  "erp": 0.055, "crp": 0.0, "g_max_macro": 0.06, "kd_spread": 0.01, "g_lp": 0.06, "rf_bruto": 0.1318},
    "BR": {"rf": 0.12,  "erp": 0.055, "crp": 0.0, "g_max_macro": 0.05, "kd_spread": 0.025, "g_lp": 0.05},
    "MX": {"rf": 0.09,  "erp": 0.055, "crp": 0.0, "g_max_macro": 0.045, "kd_spread": 0.02, "g_lp": 0.045},
    "CL": {"rf": 0.055, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.035, "kd_spread": 0.015, "g_lp": 0.035},
    "GB": {"rf": 0.04,  "erp": 0.05, "crp": 0.0, "g_max_macro": 0.035, "kd_spread": 0.015, "g_lp": 0.03},
    "DEFAULT": {"rf": 0.05, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.04, "kd_spread": 0.02, "g_lp": 0.03},
}
CAPM_AS_OF = "2026-10"  # US rf~5.0% (UST10 4,99 % 27-oct-2026) / ERP~5%; CO rf~13% (TES 10a >13% al 21-oct-2026). Revisar en cada ciclo de FOMC/BanRep.

# Riesgo país: CDS soberano a 5 años (Bloomberg vía La República, corte 20-oct-2026).
# Solo se suma cuando los flujos están en una moneda DURA distinta a la local del emisor
# (p. ej. MINEROS: EEFF en USD, emisor colombiano). Si los flujos están en COP, el TES ya
# incorpora el riesgo soberano y sumarlo otra vez sería doble conteo.
RIESGO_PAIS_CDS = {"CO": 0.0160, "BR": 0.0117, "MX": 0.0095, "PE": 0.0067, "CL": 0.0054}
MULT_CRP_EQUITY = 1.5   # σ(acciones)/σ(bonos) típico en emergentes: CRP equity ≈ 1,5 × CDS
# Las dos constantes anteriores son RESPALDO: si existe datos_damodaran.json (tablas de
# Aswath Damodaran, NYU Stern, versionadas en el repositorio) se usan sus primas.

# ---------------------------------------------------------------------------
# Damodaran: prima de mercado, riesgo país y múltiplos por industria
# ---------------------------------------------------------------------------
_RUTA_DAMODARAN = Path(__file__).with_name("datos_damodaran.json")
NOMBRE_PAIS_DAMODARAN = {"CO": "Colombia", "US": "United States", "BR": "Brazil", "MX": "Mexico",
                         "CL": "Chile", "PE": "Peru", "GB": "United Kingdom"}
REGION_MULTIPLOS = {"US": "US", "CO": "Emergentes", "BR": "Emergentes", "MX": "Emergentes",
                    "CL": "Emergentes", "PE": "Emergentes"}
DAMODARAN_VIGENCIA_MESES = 13


def _leer_damodaran(ruta=None):
    try:
        with open(ruta or _RUTA_DAMODARAN, encoding="utf-8") as f:
            d = json.load(f)
        return d if (d.get("riesgo_pais") and d.get("multiplos")) else {}
    except Exception:
        return {}


DAMODARAN = _leer_damodaran()


def _meses_desde(fecha_iso, hoy=None):
    try:
        f = datetime.strptime(str(fecha_iso)[:10], "%Y-%m-%d")
        hoy = hoy or datetime.now()
        return (hoy.year - f.year) * 12 + (hoy.month - f.month)
    except Exception:
        return None


def damodaran_vigencia(hoy=None):
    """{"riesgo_pais": fecha, "multiplos": fecha, "vencido": bool, "aviso": str|None}."""
    if not DAMODARAN:
        return {"riesgo_pais": None, "multiplos": None, "vencido": True,
                "aviso": "Sin datos de Damodaran: se usan las constantes de respaldo del código."}
    f_rp = (DAMODARAN["riesgo_pais"].get("meta") or {}).get("fecha")
    f_mu = next((m.get("fecha") for m in DAMODARAN["multiplos"].values() if m.get("fecha")), None)
    edades = [x for x in (_meses_desde(f_rp, hoy), _meses_desde(f_mu, hoy)) if x is not None]
    vencido = bool(edades) and max(edades) > DAMODARAN_VIGENCIA_MESES
    aviso = (f"Tablas de Damodaran con más de {DAMODARAN_VIGENCIA_MESES} meses (riesgo país {f_rp}, múltiplos {f_mu}): "
             "ejecuta scripts/actualizar_damodaran.py o el flujo «Actualizar datos de Damodaran».") if vencido else None
    return {"riesgo_pais": f_rp, "multiplos": f_mu, "vencido": vencido, "aviso": aviso}


def damodaran_riesgo_pais(mercado):
    """Primas de Damodaran para un código de mercado (CO, US, …) o None.

    erp_madura: prima de un mercado maduro sin riesgo soberano; crp: prima de riesgo país
    para el patrimonio (spread por calificación × volatilidad relativa acciones/bonos);
    spread: spread de default por calificación (para el costo de la deuda en moneda dura);
    erp_total = erp_madura + crp; crp_cds: alternativa con el CDS soberano.
    """
    if not DAMODARAN:
        return None
    rp = DAMODARAN["riesgo_pais"]
    meta = rp.get("meta") or {}
    datos = (rp.get("paises") or {}).get(NOMBRE_PAIS_DAMODARAN.get(str(mercado or "").upper(), ""))
    if not datos:
        return None
    return {"pais": NOMBRE_PAIS_DAMODARAN.get(str(mercado).upper()), "rating": datos.get("rating"),
            "erp_madura": meta.get("erp_madura"), "erp_us": meta.get("erp_us"),
            "multiplicador": meta.get("multiplicador_volatilidad"),
            "crp": datos.get("crp_rating"), "spread": datos.get("spread_rating"), "erp_total": datos.get("erp_rating"),
            "crp_cds": datos.get("crp_cds"), "cds_neto": datos.get("cds_neto"), "fecha": meta.get("fecha"),
            "fuente": f"Damodaran ({meta.get('archivo')}, {meta.get('fecha')})"}


# Industria de Damodaran por palabras clave del sector/industria (Yahoo o catálogo).
# El orden importa: lo más específico primero. Sin coincidencia → sin ancla (no se usa el total del mercado).
INDUSTRIA_DAMODARAN_REGLAS = (
    (("gold", "oro", "precious", "silver", "plata"), "Precious Metals"),
    (("oil & gas integrated", "petróleo, gas", "petroleo, gas", "integrated oil"), "Oil/Gas (Integrated)"),
    (("oil & gas e&p", "exploration & production", "exploración y producción"), "Oil/Gas (Production and Exploration)"),
    (("oil & gas midstream", "gas distribution", "distribución de gas", "gas natural"), "Oil/Gas Distribution"),
    (("copper", "cobre", "industrial metals", "metals & mining", "minería", "mineria", "coal", "carbón"), "Metals & Mining"),
    (("renewable", "renovable"), "Green & Renewable Energy"),
    (("water", "acueducto", "agua"), "Utility (Water)"),
    (("utilities - regulated electric", "utilities - diversified", "transmisión", "transmision",
      "distribución eléctrica", "distribucion electrica", "energía", "energia", "electric", "power"), "Power"),
    (("software - infrastructure", "software - application", "software"), "Software (System & Application)"),
    (("consumer electronics", "computer hardware"), "Computers/Peripherals"),
    (("semiconductor",), "Semiconductor"),
    (("banks - regional", "banks - diversified", "banco"), None),   # EV/EBITDA no aplica a bancos
    # Consumo (EE. UU.): beta de industria y múltiplo de referencia para empresas maduras.
    (("beverages - non-alcoholic", "soft drinks"), "Beverage (Soft)"),
    (("beverages - brewers", "beverages - wineries", "distilleries", "cerveza"), "Beverage (Alcoholic)"),
    (("household & personal products", "household products", "personal products"), "Household Products"),
    (("confectioners",), "Food Processing"),
    (("restaurants",), "Restaurant/Dining"),
    (("discount stores", "department stores"), "Retail (General)"),
    (("grocery stores", "supermercados"), "Retail (Grocery and Food)"),
    (("tobacco", "tabaco"), "Tobacco"),
    (("drug manufacturers",), "Drugs (Pharmaceutical)"),
    (("biotechnology",), "Drugs (Biotechnology)"),
    (("apparel", "footwear"), "Apparel"),
    (("lodging", "resorts & casinos"), "Hotel/Gaming"),
    (("food", "alimentos", "packaged foods"), "Food Processing"),
    (("telecom",), "Telecom. Services"),
    (("cement", "cemento", "building materials"), "Building Materials"),
    (("exchange", "bolsa de valores", "capital markets", "servicios financieros"), None),  # sin equivalente claro
)


def calificacion_sintetica(ebit, gasto_intereses, grande=True, tabla=None):
    """Calificación y spread de default por cobertura de intereses (EBIT ÷ gasto financiero), tabla de Damodaran.

    Damodaran usa dos tablas: empresas grandes (> 5.000 millones de USD) y pequeñas/riesgosas.
    Devuelve None si no hay tabla o los datos no permiten calcular la cobertura.
    """
    cal = tabla or ((DAMODARAN or {}).get("calificaciones") or {}).get("grandes" if grande else "pequenas")
    try:
        ebit, gasto = float(ebit), abs(float(gasto_intereses))
    except (TypeError, ValueError):
        return None
    if not cal or not np.isfinite(ebit) or not np.isfinite(gasto):
        return None
    cobertura = 1e5 if gasto <= 0 else ebit / gasto
    # Tramos «> desde y ≤ hasta» con límites como 2,499999: se toma el último tramo cuyo «desde» no
    # supera la cobertura, para no dejar huecos en los bordes (2,5 cae en Baa2/BBB, no en ninguno).
    filas = sorted(cal, key=lambda x: float(x[0]))
    elegido = filas[0]
    for fila in filas:
        if cobertura >= float(fila[0]):
            elegido = fila
    return {"calificacion": elegido[2], "spread": float(elegido[3]), "cobertura": cobertura,
            "tabla": "empresas grandes" if grande else "empresas pequeñas"}


def beta_para_capm(info):
    """Beta con deuda para el CAPM de un activo del portafolio, con la misma regla que la valoración:
    regresión de Yahoo si informa (≥ BETA_REGRESION_MIN); si no, bottom-up de Damodaran de su industria y
    región, reapalancada con su D/E de mercado; si tampoco hay, 1,0 (mercado). Devuelve (beta, fuente)."""
    info = info or {}
    b = _safe_float(info.get("beta"))
    explicita = None
    tk = str(info.get("symbol") or "").upper()
    for emp in EMPRESAS.values():  # emisor del catálogo: su industria curada
        if tk and str(emp.get("ticker_yf") or "").upper() == tk:
            explicita = (emp.get("params") or {}).get("industria_damodaran")
    if b is not None and BETA_REGRESION_MIN <= b <= 3.0:
        return float(b), f"β {b:.2f} (Yahoo)"
    pais = _mercado_desde_pais(info.get("country")) or ("CO" if str(info.get("symbol") or "").upper().endswith(".CL") else "US")
    bd = damodaran_beta(info.get("sector") or "", info.get("industry") or "", pais, explicita=explicita)
    if bd:
        deuda, mcap = _safe_float(info.get("totalDebt")), _safe_float(info.get("marketCap"))
        de = (deuda / mcap) if deuda and mcap and mcap > 0 else 0.0
        t = TASA_ESTATUTARIA.get(pais, 0.25)
        bl = float(bd["beta_u"]) * (1 + (1 - t) * min(de, 3.0))
        motivo = "Yahoo sin beta" if b is None else f"regresión {b:.2f} no informativa"
        return bl, f"β {bl:.2f} bottom-up {bd['industria']} {bd.get('region')} ({motivo})"
    return 1.0, "β 1,00 de mercado (sin beta ni industria)"


def industria_damodaran(sector="", industry="", explicita=None):
    if explicita:
        return explicita
    texto = f" {sector or ''} {industry or ''} ".lower()
    for claves, industria in INDUSTRIA_DAMODARAN_REGLAS:
        if any(k in texto for k in claves):
            return industria
    return None


def damodaran_multiplo(sector="", industry="", mercado=None, explicita=None):
    """EV/EBITDA agregado de la industria en la región del emisor (EE. UU., emergentes o global)."""
    if not DAMODARAN:
        return None
    ind = industria_damodaran(sector, industry, explicita)
    if not ind:
        return None
    region = REGION_MULTIPLOS.get(str(mercado or "").upper(), "Global")
    bloque = DAMODARAN["multiplos"].get(region) or DAMODARAN["multiplos"].get("Global") or {}
    fila = (bloque.get("industrias") or {}).get(ind)
    if not fila or not fila.get("ev_ebitda") or not (1.0 <= float(fila["ev_ebitda"]) <= 50.0):
        return None
    out = {"industria": ind, "region": region, "ev_ebitda": float(fila["ev_ebitda"]),
           "ev_ebitda_industria": float(fila["ev_ebitda"]), "ajuste_pais": None,
           "ev_ebit": fila.get("ev_ebit"), "n_firmas": fila.get("n_firmas"), "fecha": bloque.get("fecha"),
           "fuente": f"Damodaran {bloque.get('archivo')} ({bloque.get('fecha')})"}
    # Ajuste por país (modelo del curso): la bolsa local paga menos por cada peso de EBITDA que el
    # promedio emergente → múltiplo de la industria × (1 − descuento del mercado local).
    aj = ((DAMODARAN.get("ajuste_pais") or {}).get(str(mercado or "").upper()) or {}) if region == "Emergentes" else {}
    desc = aj.get("descuento")
    if desc is not None and -0.5 < float(desc) < 0.8:
        out["ev_ebitda"] = float(fila["ev_ebitda"]) * (1 - float(desc))
        out["ajuste_pais"] = {"descuento": float(desc), "mediana_local": aj.get("mediana_local"), "n": aj.get("n"),
                              "referencia_emergentes": aj.get("referencia_emergentes"), "fecha": aj.get("fecha")}
    return out


def damodaran_beta(sector="", industry="", mercado="US", explicita=None):
    """Beta «bottom-up» de Damodaran: beta desapalancada de la industria corregida por caja.

    Es la beta del NEGOCIO (sin el efecto de la caja, cuya beta es ≈ 0), que es lo coherente con
    un DCF que suma la caja aparte en el puente. Promedia decenas de empresas, por lo que tiene
    mucho menos error estándar que la regresión de una sola acción. Solo hay tabla de EE. UU.
    """
    if not DAMODARAN:
        return None
    mk = str(mercado or "").upper()
    region = "US" if mk == "US" else (REGION_MULTIPLOS.get(mk) or ("Emergentes" if mk in ("CO", "BR", "MX", "CL", "PE") else "Global"))
    if mk in ("EMERGENTES", "GLOBAL"):
        region = mk.title()
    bloque = (DAMODARAN.get("betas") or {}).get(region) or {}
    if not bloque:
        return None
    ind = industria_damodaran(sector, industry, explicita)
    fila = (bloque.get("industrias") or {}).get(ind) if ind else None
    if not fila:
        return None
    b = fila.get("beta_u_caja") or fila.get("beta_u")
    try:
        b = float(b)
    except (TypeError, ValueError):
        return None
    if not (0.2 <= b <= 3.0):
        return None
    return {"industria": ind, "beta_u": b, "beta_u_sin_corregir": fila.get("beta_u"), "n_firmas": fila.get("n_firmas"),
            "region": region, "fecha": bloque.get("fecha"), "fuente": f"Damodaran {bloque.get('archivo')} ({bloque.get('fecha')})"}


def _aplicar_damodaran_a_capm():
    """Primas de Damodaran sobre las anclas CAPM.

    · EE. UU.: ERP implícita de Damodaran (antes 5 % fijo).
    · Colombia (método de Damodaran para tasas en moneda local, como en el modelo del curso):
        rf = TES 10 años − spread de default de Colombia (el TES incluye el riesgo de impago);
        ERP = ERP madura + prima de riesgo país (ya incluye el riesgo país, CRP = 0 aparte);
        Kd = TES (bruto) + spread de la empresa.
      Antes: rf = TES completo y ERP 5,5 % sin riesgo país explícito.
    """
    for k, v in CAPM_POR_MERCADO.items():
        v.setdefault("rf_bruto", v["rf"])
    rp_us = damodaran_riesgo_pais("US")
    if rp_us and rp_us.get("erp_us"):
        for k in ("US", "DEFAULT"):
            CAPM_POR_MERCADO[k]["erp"] = round(float(rp_us["erp_us"]), 4)
            CAPM_POR_MERCADO[k]["erp_fuente"] = rp_us["fuente"]
    rp_co = damodaran_riesgo_pais("CO")
    if rp_co and rp_co.get("spread") is not None and rp_co.get("erp_total") is not None:
        co = CAPM_POR_MERCADO["CO"]
        co["rf"] = round(float(co["rf_bruto"]) - float(rp_co["spread"]), 4)
        co["erp"] = round(float(rp_co["erp_total"]), 4)
        co["crp"] = 0.0
        co["erp_fuente"] = (f"{rp_co['fuente']}: ERP madura {rp_co['erp_madura']:.2%} + riesgo país "
                            f"{rp_co['crp']:.2%} (Colombia {rp_co['rating']})")
        co["rf_fuente"] = f"TES 10a {co['rf_bruto']:.2%} − spread de default {rp_co['spread']:.2%} (Damodaran)"


# ---------------------------------------------------------------------------
# Tasas de mercado: referencia fechada del código vs datos_mercado.json (Tesoro de EE. UU. y OCDE, flujo semanal)
# ---------------------------------------------------------------------------
_RUTA_TASAS = Path(__file__).with_name("datos_mercado.json")
# Referencias puntuales (fuente y fecha). Gana el dato MÁS RECIENTE entre esta tabla y el archivo:
# un promedio mensual de la OCDE no reemplaza un TES diario del Banco de la República más nuevo.
REFERENCIAS_TASAS = {
    "us_rf": {"valor": 0.05, "fecha": "2026-10-27", "fuente": "Tesoro de EE. UU. a 10 años 4,99 % (Treasury, 27-oct-2026)"},
    "us_inflacion_lp": {"valor": 0.0235, "fecha": "2026-10-09", "fuente": "UST10 5,22 % − tasa real 10a 2,87 % (9-oct-2026)"},
    "co_rf_bruto": {"valor": 0.1318, "fecha": "2026-10-16", "fuente": "TES 10 años, curva cero cupón (Banco de la República, 16-oct-2026)"},
    "co_inflacion_lp": {"valor": 0.0615, "fecha": "2026-08-21", "fuente": "Inflación implícita TES COP vs UVR a 10 años (Banco de la República, 21-ago-2026)"},
}
VIGENCIA_TASAS_DIAS = {"us_rf": 45, "co_rf_bruto": 75, "us_inflacion_lp": 120, "co_inflacion_lp": 200}
NOMBRE_TASA = {"us_rf": "Tesoro de EE. UU. a 10 años", "co_rf_bruto": "TES a 10 años",
               "us_inflacion_lp": "inflación de largo plazo de EE. UU.", "co_inflacion_lp": "inflación de largo plazo de Colombia"}


def _leer_tasas(ruta=None):
    try:
        with open(ruta or _RUTA_TASAS, encoding="utf-8") as f:
            return (json.load(f) or {}).get("tasas") or {}
    except Exception:
        return {}


def tasas_vigentes(archivo=None, referencias=None):
    """{clave: {"valor", "fecha", "fuente", "origen"}} con el dato más reciente de cada tasa."""
    archivo = _leer_tasas() if archivo is None else archivo
    out = {}
    for k, ref in (referencias or REFERENCIAS_TASAS).items():
        elegido = dict(ref, origen="referencia del código")
        a = archivo.get(k) or {}
        try:
            v = float(a["valor"])
            if 0.0 < v < 0.40 and str(a.get("fecha") or "") > str(ref.get("fecha") or ""):
                elegido = {"valor": v, "fecha": a["fecha"], "fuente": a.get("fuente") or a.get("serie"), "origen": "datos_mercado.json"}
        except (KeyError, TypeError, ValueError):
            pass
        out[k] = elegido
    return out


def tasas_vigencia(hoy=None, tasas=None):
    """Avisos para las tasas más viejas que su vigencia (días)."""
    hoy = hoy or datetime.now().date()
    tasas = tasas or TASAS_MERCADO
    avisos = []
    for k, t in tasas.items():
        try:
            dias = (hoy - datetime.fromisoformat(str(t["fecha"])).date()).days
        except Exception:
            continue
        if dias > VIGENCIA_TASAS_DIAS.get(k, 90):
            avisos.append(f"{NOMBRE_TASA.get(k, k)} con {dias} días ({t['fecha']}): ejecuta el flujo «Actualizar tasas de "
                          "mercado» o actualiza REFERENCIAS_TASAS.")
    return avisos


TASAS_MERCADO = tasas_vigentes()
CAPM_POR_MERCADO["US"]["rf"] = round(TASAS_MERCADO["us_rf"]["valor"], 4)
CAPM_POR_MERCADO["US"]["rf_fuente"] = f"{TASAS_MERCADO['us_rf']['fuente']} · {TASAS_MERCADO['us_rf']['fecha']}"
CAPM_POR_MERCADO["CO"]["rf_bruto"] = round(TASAS_MERCADO["co_rf_bruto"]["valor"], 4)
CAPM_POR_MERCADO["CO"]["rf_bruto_fuente"] = f"{TASAS_MERCADO['co_rf_bruto']['fuente']} · {TASAS_MERCADO['co_rf_bruto']['fecha']}"
CAPM_POR_MERCADO["CO"]["rf"] = CAPM_POR_MERCADO["CO"]["rf_bruto"]  # sin Damodaran: rf = TES completo

_aplicar_damodaran_a_capm()
# Inflación de largo plazo implícita en el mercado (para Fisher / paridad):
#   CO: breakeven TES COP vs UVR 10 años 6,15 % (BanRep, 21-ago-2026)
#   US: UST10 5,22 % − tasa real 10 años 2,87 % = 2,35 % (9-oct-2026)
INFLACION_LP = {"CO": round(TASAS_MERCADO["co_inflacion_lp"]["valor"], 4),
                "US": round(TASAS_MERCADO["us_inflacion_lp"]["valor"], 4)}
MERCADO_POR_MONEDA = {"COP": "CO", "USD": "US", "BRL": "BR", "MXN": "MX", "CLP": "CL", "GBP": "GB"}
TASA_ESTATUTARIA = {"CO": 0.35, "US": 0.21, "BR": 0.34, "MX": 0.30, "CL": 0.27, "GB": 0.25}


_BOLSAS_US = {"NMS", "NGM", "NCM", "NYQ", "NYS", "ASE", "PCX", "BTS", "NASDAQ", "NYSE", "NASDAQGS", "NASDAQGM", "NASDAQCM", "NYSEARCA", "AMEX"}


def _completar_info_yahoo(info, t_obj=None, ticker=None):
    """Rellena huecos de `info` que cambian la valoración (auditoría 4).

    - País: sin él, una empresa de EE. UU. perdía el CAPM en dólares y el modelo de tres
      etapas (AAPL −34 %). Se infiere de la bolsa (o del sufijo .CL → Colombia).
    - Ingresos y EBITDA de los últimos 12 meses: sin ellos un emisor cíclico se normalizaba
      con el año fiscal (Ecopetrol −37 %). Se suman los cuatro últimos trimestres.
    Los datos añadidos se marcan en `_completado` para rotular la fuente.
    """
    info = dict(info or {})
    hechos = []
    if not info.get("country"):
        bolsa = str(info.get("exchange") or info.get("fullExchangeName") or "").upper().replace(" ", "")
        tk = str(ticker or info.get("symbol") or "").upper()
        if tk.endswith(".CL"):
            info["country"] = "Colombia"
        elif bolsa in _BOLSAS_US or (("." not in tk) and str(info.get("currency") or "").upper() == "USD"
                                      and str(info.get("financialCurrency") or "USD").upper() == "USD"):
            info["country"] = "United States"
        if info.get("country"):
            hechos.append("país inferido de la bolsa")
    if t_obj is not None and (info.get("totalRevenue") is None or info.get("ebitda") is None):
        try:
            q = getattr(t_obj, "quarterly_income_stmt", None)
            if q is None or getattr(q, "empty", True):
                q = getattr(t_obj, "quarterly_financials", None)
            if q is not None and not getattr(q, "empty", True) and q.shape[1] >= 4:
                idx = {str(i).strip().lower(): i for i in q.index}

                def _ltm(nombres):
                    for n in nombres:
                        k = idx.get(n)
                        if k is not None:
                            v = pd.to_numeric(q.loc[k].iloc[:4], errors="coerce")
                            if v.notna().all():
                                return float(v.sum())
                    return None
                if info.get("totalRevenue") is None:
                    v = _ltm(["total revenue", "operating revenue"])
                    if v is not None:
                        info["totalRevenue"] = v
                        hechos.append("ingresos 12m de los trimestres")
                if info.get("ebitda") is None:
                    v = _ltm(["ebitda", "normalized ebitda"])
                    if v is None:  # EBITDA trimestral incompleto: utilidad operativa + depreciación
                        ebit = _ltm(["operating income", "ebit"])
                        da = _ltm(["reconciled depreciation", "depreciation and amortization in income statement",
                                   "depreciation amortization depletion income statement"])
                        v = ebit + da if ebit is not None and da is not None else None
                    if v is not None:
                        info["ebitda"] = v
                        hechos.append("EBITDA 12m de los trimestres")
        except Exception:
            pass
    # Gasto financiero del último ejercicio (para la calificación sintética del costo de la deuda).
    if t_obj is not None and info.get("_gasto_intereses") is None:
        try:
            f = getattr(t_obj, "financials", None)
            if f is not None and not getattr(f, "empty", True):
                idx = {str(i).strip().lower(): i for i in f.index}
                for n in ("interest expense", "interest expense non operating"):
                    if n in idx:
                        v = pd.to_numeric(f.loc[idx[n]], errors="coerce").dropna()
                        if len(v) and float(v.iloc[0]) != 0:
                            info["_gasto_intereses"] = abs(float(v.iloc[0]))
                            break
        except Exception:
            pass
    if hechos:
        info["_completado"] = hechos
    return info


def _mercado_desde_pais(country):
    c = str(country or "").strip().upper()
    return {
        "COLOMBIA": "CO", "COL": "CO", "CO": "CO", "UNITED STATES": "US", "USA": "US", "US": "US",
        "BRAZIL": "BR", "BRA": "BR", "BR": "BR", "MEXICO": "MX", "MEX": "MX", "MX": "MX",
        "CHILE": "CL", "CHL": "CL", "UNITED KINGDOM": "GB", "GBR": "GB", "GB": "GB", "UK": "GB",
        "PERU": "PE", "PER": "PE", "PE": "PE",
    }.get(c)


def capm_coherente_con_moneda(country=None, moneda_flujos=None, ticker_yf=None):
    """Anclas CAPM en la MONEDA DE LOS FLUJOS (regla de consistencia del DCF).

    Antes el mercado CAPM se elegía por país/sufijo del ticker: un emisor .CL que reporta
    en USD (MINEROS) se descontaba con el TES en COP (13 %) y Kd = 14 %, mezclando la
    inflación colombiana en una tasa aplicada a flujos en dólares (WACC 17,3 % vs 14,5 %
    implícito en el precio). Ahora:
      · rf, ERP, g de largo plazo y techo macro → mercado de la moneda de los flujos;
      · si esa moneda es dura y el emisor es de un país emergente → + riesgo país
        (Ke: 1,5×CDS; Kd: + CDS).
    Devuelve dict con rf, erp, crp, crp_deuda, g_max_macro, g_lp, kd_spread y códigos.
    """
    merc_pais = _mercado_desde_pais(country) or _codigo_mercado(country, None, ticker_yf)
    merc_moneda = MERCADO_POR_MONEDA.get(str(moneda_flujos or "").upper().replace("US$", "USD"))
    merc = merc_moneda or merc_pais or "DEFAULT"
    if merc not in CAPM_POR_MERCADO:
        merc = "DEFAULT"
    base = dict(CAPM_POR_MERCADO[merc])
    crp_eq, crp_deuda, fuente = 0.0, 0.0, None
    if merc_moneda and merc_pais and merc_pais != merc_moneda:
        dam = damodaran_riesgo_pais(merc_pais) if merc_moneda == "US" else None
        if dam and dam.get("crp") is not None:
            # Damodaran: ERP del país = ERP madura + CRP; deuda en USD = rf + spread por calificación.
            base["erp"] = float(dam["erp_madura"])
            crp_eq, crp_deuda = float(dam["crp"]), float(dam["spread"] or 0.0)
            fuente = f"{dam['fuente']} · {dam['pais']} {dam['rating']}"
        else:
            cds = float(RIESGO_PAIS_CDS.get(merc_pais, 0.0))
            crp_eq, crp_deuda = MULT_CRP_EQUITY * cds, cds
            fuente = "constantes del código (CDS × 1,5)" if cds else None
    base.update({
        "crp": round(float(base.get("crp", 0.0)) + crp_eq, 4),
        "crp_deuda": round(crp_deuda, 4),
        "mercado": merc,
        "mercado_pais": merc_pais,
        "cruce_moneda": bool(crp_eq or crp_deuda),
        "riesgo_pais_fuente": fuente,
    })
    return base


def tasa_estatutaria(country=None, mercado=None):
    """Tasa estatutaria de renta por país (fallback 25 %)."""
    m = mercado or _mercado_desde_pais(country)
    return float(TASA_ESTATUTARIA.get(m, 0.25))


def wacc_paridad_usd(beta_u, de_ratio, tax, kd_spread=0.01, pais="CO"):
    """WACC alternativo construido en USD y llevado a COP por paridad de inflación (Fisher).

    Práctica habitual de banca de inversión para emisores colombianos con negocio
    regional: Ke_USD = rf_US + β_L·ERP + 1,5·CDS; Kd_USD = rf_US + spread + CDS; luego
    (1+x_USD)·(1+π_CO)/(1+π_US) − 1. La diferencia frente al WACC local (TES) mide la
    prima de plazo/liquidez del mercado local que el modelo está cobrando. Es un
    diagnóstico: no reemplaza el caso base.
    """
    try:
        us = CAPM_POR_MERCADO["US"]
        dam = damodaran_riesgo_pais(pais)
        if dam and dam.get("crp") is not None:
            erp, crp, spread = float(dam["erp_madura"]), float(dam["crp"]), float(dam["spread"] or 0.0)
            fuente_rp = f"{dam['fuente']} ({dam['pais']} {dam['rating']}: CRP {crp:.2%}, spread {spread:.2%})"
        else:
            cds = float(RIESGO_PAIS_CDS.get(pais, 0.0))
            erp, crp, spread = us["erp"], MULT_CRP_EQUITY * cds, cds
            fuente_rp = f"CDS {pais} {cds:.2%} × {MULT_CRP_EQUITY}"
        bl = beta_apalancado(float(beta_u), float(de_ratio), float(tax))
        ke_usd = us["rf"] + bl * erp + crp
        kd_usd = us["rf"] + float(kd_spread) + spread
        wacc_usd, _, _ = calcular_wacc(float(de_ratio), kd_usd, ke_usd, float(tax))
        fisher = (1 + INFLACION_LP.get(pais, INFLACION_LP["US"])) / (1 + INFLACION_LP["US"])
        return {
            "ke_usd": ke_usd, "kd_usd": kd_usd, "wacc_usd": wacc_usd,
            "wacc_local_fisher": (1 + wacc_usd) * fisher - 1,
            "ke_local_fisher": (1 + ke_usd) * fisher - 1,
            "fuente": f"UST10 {us['rf']:.2%} + ERP {erp:.2%} + riesgo país: {fuente_rp} · π {pais} {INFLACION_LP.get(pais, 0):.2%} vs π US {INFLACION_LP['US']:.2%}",
        }
    except Exception:
        return None


# Sectores cuyos ingresos dependen del precio de una materia prima: la tendencia
# histórica de ingresos/márgenes refleja el ciclo de precios, no capacidad.
_PALABRAS_SECTOR_CICLICO = (
    "petróleo", "petroleo", "oil", "crude", "exploration & production", "gold", "oro ",
    "minería", "mineria", "mining", "metals", "metal", "copper", "cobre", "coal", "carbón",
    "silver", "plata", "steel", "acero",
)


def es_sector_ciclico(sector="", industry=""):
    texto = f" {sector or ''} {industry or ''} ".lower()
    if texto.strip() in ("energy",) or " energy " in texto.replace("/", " "):
        return True
    return any(k in texto for k in _PALABRAS_SECTOR_CICLICO)


def _aplicar_reglas_catalogo():
    """Kd del catálogo = rf del mercado CO + spread según calificación (datos_curados.json).

    g terminal = g de largo plazo del mercado CO (la misma que usa la ruta Yahoo). El catálogo traía
    3–5 % nominal en COP, por debajo de la inflación de largo plazo (6,15 %): contracción real perpetua,
    y un valor muy distinto al de la ruta Yahoo para la misma empresa (ISA 14.000 vs 24.400 COP).
    """
    g_co = min(float(CAPM_POR_MERCADO["CO"]["g_lp"]), float(CAPM_POR_MERCADO["CO"]["g_max_macro"]))
    for catalogo in (EMPRESAS, _EMPRESAS_CATALOGO_INMUTABLE):
        for emp in catalogo.values():
            g_cat = emp["params"].get("g")
            if g_cat is None or float(g_cat) < g_co:
                emp["params"]["g_catalogo"] = g_cat
                emp["params"]["g"] = round(g_co, 4)
                emp["params"]["g_fuente"] = f"g de largo plazo del mercado CO ({g_co:.1%} nominal en COP); catálogo {g_cat}"
    rf = CAPM_POR_MERCADO["CO"].get("rf_bruto", CAPM_POR_MERCADO["CO"]["rf"])  # Kd sobre el TES completo
    spreads = ((_DATOS_CURADOS.get("reglas") or {}).get("spread_kd_por_calificacion") or {})
    for catalogo in (EMPRESAS, _EMPRESAS_CATALOGO_INMUTABLE):
        for emp in catalogo.values():
            sp = float(spreads.get(emp.get("calificacion"), CAPM_POR_MERCADO["CO"]["kd_spread"]))
            emp["params"]["kd"] = round(rf + sp, 4)
            emp["params"]["kd_fuente"] = f"TES 10a {rf:.2%} + spread {sp:.1%} ({emp.get('calificacion') or 'sin calificación'})"


_aplicar_reglas_catalogo()



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


def instantanea_precio_mercado(nombre_empresa):
    """Precio + metadatos (fuente, fecha, moneda) de la instantánea cacheada.

    Es la ÚNICA fuente de precio para cabecera, pestañas, comité IA, simulador y
    portafolio: todos leen la misma cotización dentro del TTL de la caché.
    """
    out = {"precio": None, "moneda": None, "fuente": None, "fecha": None, "ticker": None}
    emp = resolver_empresa(nombre_empresa) if nombre_empresa else None
    emp = emp or {}
    tk = ticker_yf_empresa(nombre_empresa) if nombre_empresa else None
    tk = tk or emp.get("ticker_yf")
    if not tk:
        return out
    out["ticker"] = tk
    precio = resolver_precio_mercado(nombre_empresa)
    out["precio"] = precio
    try:
        mkt = obtener_datos_mercado_bvc(tk, ticker_bvc=emp.get("ticker_bvc"))
        if mkt and mkt.get("ok"):
            out["moneda"] = mkt.get("moneda")
            out["fuente"] = mkt.get("fuente") or mkt.get("proveedor")
            out["fecha"] = mkt.get("fecha_precio") or mkt.get("consultado_utc")
    except Exception:
        pass
    return out


def resolver_precio_mercado(nombre_empresa=None, precio_ui=None):
    """Precio de mercado en moneda de cotización. UI → conector Yahoo/runtime."""
    try:
        if precio_ui is not None and float(precio_ui) > 0:
            return float(precio_ui)
    except Exception:
        pass
    emp = resolver_empresa(nombre_empresa) if nombre_empresa else None
    emp = emp or {}
    # Ticker canónico primero (a prueba de contaminación de sesión), igual que en
    # instantanea_precio_mercado: misma llave de caché → mismo precio en todo el app.
    tk = (ticker_yf_empresa(nombre_empresa) if nombre_empresa else None) or emp.get("ticker_yf")
    if not tk:
        # Empresa cargada desde Excel con precio en la hoja Parámetros (no cotiza o no tiene ticker).
        pr = (emp.get("params") or {}).get("precio_referencia")
        return float(pr) if pr else None
    try:
        mkt = obtener_datos_mercado_bvc(tk, ticker_bvc=emp.get("ticker_bvc"))
        if mkt and mkt.get("ok") and mkt.get("precio") is not None:
            precio = float(mkt["precio"])
            # Yahoo para ISA.CL puede entregar la cotización en miles de COP
            # (p. ej. 28.5) mientras el mercado BVC y el modelo usan COP/acción
            # (28,500). Normalizar solo ese ticker y solo en el rango conocido;
            # no inferir ni alterar el número de acciones para forzar una coincidencia.
            ticker_bvc = str(emp.get("ticker_bvc") or "").upper().strip()
            fuente = str(mkt.get("fuente") or mkt.get("proveedor") or "").lower()
            if ticker_bvc == "ISA" and "yahoo" in fuente and 10.0 <= precio < 100.0:
                precio *= 1000.0
            return precio
    except Exception:
        pass
    return None


def fijar_tasa_cop_usd(valor=None):
    """Fija (o borra con None) una tasa COP por USD manual para la sesión."""
    alm = _almacen_estado()
    if valor is None:
        alm.pop("_tasa_cop_usd_manual", None)
        return None
    v = float(valor)
    if not (1000.0 < v < 20000.0):
        raise ValueError("La tasa COP/USD debe estar entre 1.000 y 20.000.")
    alm["_tasa_cop_usd_manual"] = v
    return v


def tasa_cop_por_usd():
    """COP por 1 USD: tasa manual de la sesión o spot Yahoo (COP=X, caché TTL).

    Devuelve (tasa, fuente) o (None, motivo). Solo se usa para convertir el PRECIO
    de mercado a la moneda del modelo; nunca para reexpresar estados históricos.
    """
    manual = _almacen_estado().get("_tasa_cop_usd_manual")
    if manual:
        return float(manual), "manual"
    try:
        mkt = obtener_datos_mercado_bvc("COP=X")
        px = _finite_or_none((mkt or {}).get("precio")) if (mkt or {}).get("ok") else None
        if px is not None and 1000.0 < px < 20000.0:
            return float(px), f"spot {mkt.get('fuente') or 'yahoo:COP=X'} {mkt.get('fecha_precio') or ''}".strip()
    except Exception:
        pass
    return None, "sin tasa COP/USD disponible"


def convertir_precio_a_moneda_modelo(precio, moneda_precio, moneda_modelo, tasas_cop_por_moneda=None):
    """Convierte precio por acción a moneda del modelo sin inventar tipos de cambio.

    `tasas_cop_por_moneda` es un mapa explícito {ISO4217: COP por una unidad de esa moneda},
    con fecha/fuente que el caller debe conservar por separado. Permite cruces como EUR→USD
    solo cuando se proporcionan ambas tasas. Sin mapa, se mantiene el proveedor spot COP/USD
    existente. No convierte estados financieros históricos.
    """
    out = {"precio": precio, "fx": None, "fuente_fx": None, "convertido": False}
    mp = str(moneda_precio or "").strip().upper()
    mm = str(moneda_modelo or "").strip().upper()
    if precio is None or not mp or not mm:
        out["precio"] = None
        out["fuente_fx"] = "precio o moneda ausente"
        return out
    try:
        px0 = float(precio)
    except (TypeError, ValueError):
        out["precio"] = None
        out["fuente_fx"] = "precio no numérico"
        return out
    if not np.isfinite(px0):
        out["precio"] = None
        out["fuente_fx"] = "precio no finito"
        return out
    if mp == mm:
        out["precio"] = px0
        return out

    mapa_fx_explicito = tasas_cop_por_moneda is not None
    tasas = dict(tasas_cop_por_moneda or {})
    tasas = {str(k).strip().upper(): _safe_float(v) for k, v in tasas.items()}
    # COP es el numerario de referencia; no requiere una tasa externa.
    tasas.setdefault("COP", 1.0)

    # Para COP/USD, fx conserva la cotización COP por USD; rate es el multiplicador
    # aplicado al precio. Al convertir un precio COP a USD se multiplica por 1/fx.
    if {mp, mm} == {"COP", "USD"}:
        if mp in tasas and mm in tasas:
            cop_por_usd = tasas.get("USD")
            cop_por_cop = tasas.get("COP")
            if (cop_por_usd is None or cop_por_cop is None or
                    not np.isfinite(float(cop_por_usd)) or not np.isfinite(float(cop_por_cop)) or
                    float(cop_por_usd) <= 0 or float(cop_por_cop) <= 0):
                out["precio"] = None
                out["fuente_fx"] = "tasas FX deben ser positivas y finitas"
                return out
            fx = float(cop_por_usd) / float(cop_por_cop)
            fuente = "tasas explícitas COP/COP y COP/USD"
        elif mapa_fx_explicito:
            # Si el caller entrega un mapa FX, no mezclarlo silenciosamente con
            # un spot de otra fuente/fecha cuando falta una de las tasas requeridas.
            out["precio"] = None
            out["fuente_fx"] = "mapa FX explícito incompleto para COP/USD"
            return out
        else:
            fx, fuente = tasa_cop_por_usd()
        if fx is not None and np.isfinite(float(fx)) and float(fx) > 0:
            fx = float(fx)
            rate = 1.0 / fx if mp == "COP" else fx
            out.update({"precio": px0 * rate, "fx": fx, "fuente_fx": fuente, "convertido": True})
            return out
        out["precio"] = None
        out["fuente_fx"] = fuente
        return out

    if mp in tasas and mm in tasas:
        origen, destino = tasas[mp], tasas[mm]
        if origen is None or destino is None or origen <= 0 or destino <= 0:
            out["precio"] = None
            out["fuente_fx"] = "tasas FX deben ser positivas y finitas"
            return out
        rate = float(origen) / float(destino)
        out.update({"precio": px0 * rate, "fx": rate,
                    "fuente_fx": f"tasas explícitas COP/{mp} y COP/{mm}", "convertido": True})
        return out

    out["precio"] = None
    out["fuente_fx"] = f"sin tasas FX verificables para {mp}→{mm}"
    return out


def calcular_vps_y_upside(equity, acciones_millones, precio_mercado=None, moneda_modelo=None, moneda_precio=None, tasas_cop_por_moneda=None):
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
        if eq <= 0:
            # Responsabilidad limitada: el accionista no pierde más que su aporte. Un valor por acción
            # negativo no tiene sentido económico (antes salía, p. ej., −366.641 por acción).
            vps = 0.0
            nota = ("Patrimonio ≤ 0 tras restar deuda y otros derechos: con estos supuestos la acción no "
                    "tiene valor (se muestra 0; el patrimonio negativo se conserva en el puente).")

        mm = (moneda_modelo or "").upper().strip()
        mp = (moneda_precio or "").upper().strip()
        # Sin moneda confirmada en ambos lados, no calcular upside: ausencia de dato no equivale a igualdad.
        monedas_ok = bool(mm and mp and mm == mp)
        fx_info = None
        if precio_mercado is not None and mm and mp and mm != mp:
            # Modelo y cotización en monedas distintas (MINEROS: EEFF USD / precio COP;
            # ADR: EEFF COP / precio USD). Se convierte el precio con la tasa spot.
            fx_info = convertir_precio_a_moneda_modelo(precio_mercado, mp, mm, tasas_cop_por_moneda=tasas_cop_por_moneda)
            if fx_info.get("convertido"):
                precio_mercado = fx_info["precio"]
                monedas_ok = True
                nota = (
                    f"Precio convertido de {mp} a {mm}; factor FX aplicado: "
                    f"{fx_info['fx']:,.6g} ({fx_info['fuente_fx']})."
                )

        if precio_mercado is not None and float(precio_mercado) > 0:
            px = float(precio_mercado)
            # Nunca cambiar el número de acciones para acercar artificialmente
            # el VPS al precio. Si hay una diferencia extrema, conservar el VPS
            # calculado y bloquear el upside hasta verificar las unidades.
            ratio = (vps / px) if (vps is not None and px > 0) else None
            if ratio is not None and vps > 0 and (ratio < 0.01 or ratio > 100.0):
                nota = (
                    f"VPS ({vps:,.2f}) y precio de mercado ({px:,.2f}) difieren "
                    "más de 100x; upside bloqueado hasta verificar unidades y fuente."
                )
                upside = None
            elif monedas_ok and vps is not None and px > 0:
                upside = (vps / px - 1.0) * 100.0
                if not np.isfinite(upside):
                    upside = None
                elif abs(upside) > 1000.0:
                    nota = (nota or "") + (
                        f" Upside extremo ({upside:+.0f} pp): revisa WACC, g, bridge o escala de EEFF."
                    )
            elif not monedas_ok:
                if mm and mp:
                    nota = (nota or "") + f" Moneda modelo ({mm}) ≠ cotización ({mp}): upside no comparable sin FX."
                elif mm or mp:
                    nota = (nota or "") + (
                        f" Moneda sin confirmar (modelo: {mm or 'N/D'}, cotización: {mp or 'N/D'}): upside no calculado."
                    )
                upside = None  # sin moneda en ambos lados: sin upside y sin nota (lo compara quien llama)
    except Exception as e:
        nota = f"VPS no calculable: {e}"
        vps, upside = None, None
        fx_info = None

    return {
        "value_per_share": float(vps) if vps is not None and np.isfinite(vps) else None,
        "upside_pct": float(upside) if upside is not None and np.isfinite(upside) else None,
        "acciones": acciones_used,
        "nota_vps": nota,
        "fx_aplicado": (fx_info or {}).get("fx") if (fx_info or {}).get("convertido") else None,
        "fuente_fx": (fx_info or {}).get("fuente_fx") if fx_info else None,
        "precio_moneda_modelo": (fx_info or {}).get("precio") if (fx_info or {}).get("convertido") else None,
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
        if vu.get("fx_aplicado"):
            val["fx_aplicado"] = vu["fx_aplicado"]
            val["fuente_fx"] = vu.get("fuente_fx")
            val["precio_moneda_modelo"] = vu.get("precio_moneda_modelo")
        if vu.get("nota_vps"):
            val["nota_vps"] = vu["nota_vps"]
            br = val.get("bridge") or {}
            br["Nota VPS"] = vu["nota_vps"]
            val["bridge"] = br

    # Último recurso: upside solo si ya hay VPS y precio, con las MISMAS guardas que
    # calcular_vps_y_upside (monedas confirmadas e iguales y ratio VPS/precio en
    # [1/100, 100]). Antes este atajo aceptaba monedas desconocidas y saltaba el
    # control de escala, produciendo upsides distintos entre pestañas.
    if (val.get("upside_pct") is None) and vps is not None and px is not None:
        try:
            px = float(px)
            vps = float(vps)
            mm_u, mp_u = str(mm or "").upper(), str(mp or "").upper()
            if px > 0 and np.isfinite(vps) and mm_u and mp_u and mm_u == mp_u:
                ratio = vps / px
                if 0.01 <= ratio <= 100.0:
                    val["upside_pct"] = (ratio - 1.0) * 100.0
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


BETA_REGRESION_MIN = 0.30          # beta bruta de Yahoo por debajo de esto se considera ruido (EE. UU.)
CONSENSO_G_LIMITES = (-0.30, 1.00)   # crecimiento anual de ingresos aceptado del consenso
HORIZONTE_TRES_ETAPAS = 10


def consenso_ingresos_yahoo(revenue_estimate, ingresos_ultimo_cierre):
    """Crecimiento de ingresos esperado por los analistas para los próximos ejercicios.

    `revenue_estimate` es la tabla de Yahoo (filas 0y = ejercicio en curso, +1y = siguiente; columnas
    avg, yearAgoRevenue, numberOfAnalysts). Se alinea con el último ejercicio CERRADO del histórico
    (`ingresos_ultimo_cierre`, en unidades): si el «año anterior» del 0y coincide con ese cierre, el 0y
    es el año 1 de la proyección; si ya coincide el del +1y (el 0y ya se reportó), el año 1 es el +1y.
    Devuelve {"g": [g1, g2?], "n_analistas": [...], "fuente": ...} o None.
    """
    try:
        df = revenue_estimate
        if df is None or getattr(df, "empty", True) or not ingresos_ultimo_cierre:
            return None
        ult = float(ingresos_ultimo_cierre)

        def fila(k):
            if k not in df.index:
                return None
            r = df.loc[k]
            avg, prev = _safe_float(r.get("avg")), _safe_float(r.get("yearAgoRevenue"))
            n = _safe_float(r.get("numberOfAnalysts"))
            return (avg, prev, n) if (avg and prev and avg > 0 and prev > 0) else None

        f0, f1 = fila("0y"), fila("+1y")
        cerca = lambda a, b: abs(a / b - 1.0) < 0.03
        if f0 and cerca(f0[1], ult):
            filas = [f0] + ([f1] if f1 and cerca(f1[1], f0[0]) else [])
        elif f1 and cerca(f1[1], ult):
            filas = [f1]
        else:
            return None
        g = [f[0] / f[1] - 1.0 for f in filas]
        if not all(CONSENSO_G_LIMITES[0] <= x <= CONSENSO_G_LIMITES[1] for x in g):
            return None
        return {"g": [round(x, 4) for x in g], "n_analistas": [int(f[2] or 0) for f in filas],
                "fuente": "Yahoo Finance — consenso de analistas (revenue_estimate)",
                "fecha": datetime.now().date().isoformat()}
    except Exception:
        return None


CRECIMIENTO_MAX_ETAPA2 = 0.20


def ruta_crecimiento_tres_etapas(g_consenso, g_terminal, horizonte):
    """Etapa 1: consenso de analistas; etapa 2: convergencia lineal hasta g terminal en el último año
    del horizonte; etapa 3 (perpetuidad): g terminal en el valor terminal.

    La etapa 2 arranca como máximo en CRECIMIENTO_MAX_ETAPA2 (20 %): el consenso de 1–2 años de una
    empresa en hipercrecimiento (NVDA +68 %) no se puede extrapolar 8 años más; las tasas base de
    crecimiento muestran que muy pocas empresas grandes sostienen más de 20 % anual por una década.
    """
    H = int(horizonte)
    g1 = [float(x) for x in (g_consenso or [])][:max(H - 1, 1)]
    k = len(g1)
    if k == 0:
        return None
    resto = H - k
    if resto <= 0:
        return np.array(g1[:H])
    ultimo = min(g1[-1], CRECIMIENTO_MAX_ETAPA2)
    fase2 = [ultimo + (float(g_terminal) - ultimo) * i / resto for i in range(1, resto + 1)]
    return np.array(g1 + fase2)


def horizonte_recomendado(nombre_empresa):
    """10 años cuando la empresa usa el modelo de tres etapas (consenso de EE. UU.); 5 en el resto."""
    try:
        p = params_empresa(nombre_empresa) or {}
        return HORIZONTE_TRES_ETAPAS if (p.get("consenso_ingresos") and not empresa_es_ciclica(nombre_empresa)) else 5
    except Exception:
        return 5


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
    if (info or {}).get("_completado"):
        p["datos_completados"] = list(info["_completado"])

    # --- Tax: preferir effectiveTaxRate de Yahoo; si no, estatutaria por país ---
    # (AAPL ~15–16 % efectivo; hardcode 35 % o 21 % sin ETR sesgaba NOPAT/FCFF)
    country = (info.get("country") or info.get("countryCode") or "").upper()
    etr = _safe_float(info.get("effectiveTaxRate"))
    etr_hist = _safe_float(getattr(df_hist, "attrs", {}).get("tax_efectiva")) if df_hist is not None else None
    if etr is not None and 0.0 < etr < 0.55:
        p["tax"] = round(float(etr), 4)
        p["tax_fuente"] = "yahoo_effectiveTaxRate"
    elif etr_hist is not None and 0.0 < etr_hist < 0.55:
        # Misma tasa con la que el downloader calculó NOPAT histórico: antes la
        # pestaña usaba 21 % estatutario y el histórico otra tasa (NKE 17 %, XOM 30 %).
        p["tax"] = round(float(etr_hist), 4)
        p["tax_fuente"] = "estados_financieros (Tax Rate For Calcs / impuesto ÷ UAI)"
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

    # Yahoo a veces devuelve `info` incompleto. Cada hueco cambiaba el valor en silencio
    # (auditoría 4, quitando un campo a la vez): sin totalDebt la deuda neta quedaba en 0
    # (ISA +76 % frente al precio) o, con D/E = 0, el β no se desapalancaba (ISA −40 %);
    # sin totalCash se restaba la deuda bruta. Se completan con el balance anual y con
    # precio × acciones, y se rotula la fuente.
    db_bs, caja_bs = _deuda_y_caja_balance(info.get("_balance_sheet"))
    if total_debt is None and db_bs is not None:
        total_debt = db_bs
        p["deuda_fuente"] = "balance anual Yahoo (resumen sin deuda)"
    if cash is None and caja_bs is not None:
        cash = caja_bs
        p["caja_fuente"] = "balance anual Yahoo (resumen sin caja)"
    _px_info = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose"))
    if mcap is None and shares and _px_info:
        mcap = float(shares) * _px_info
        p["mcap_fuente"] = "precio × acciones (resumen sin capitalización)"

    if cash is not None:
        p["caja"] = round(cash / 1e9, 4)
    if total_debt is not None:
        # deuda_neta = deuda − caja (ya neta). El puente NO debe sumar caja otra vez.
        p["deuda_neta"] = round((total_debt - (cash or 0)) / 1e9, 4)
        p["deuda_es_bruta"] = False
        p["deuda_bruta"] = round(total_debt / 1e9, 4)
    # Moneda de los EEFF (deuda, caja, flujos) vs moneda de cotización (precio,
    # marketCap). En ADRs difieren (EC: EEFF COP, precio USD por ADS de 20 acciones).
    fin_cur_p = str(info.get("financialCurrency") or info.get("currency") or "").upper()
    px_cur_p = str(info.get("currency") or fin_cur_p or "").upper()
    px_chk = _safe_float(info.get("regularMarketPrice") or info.get("currentPrice"))
    if shares is not None and shares > 0:
        # Yahoo sharesOutstanding viene en unidades; el modelo usa millones.
        sh = float(shares)
        p["acciones_fuente"] = "sharesOutstanding"
        # Acciones diluidas (Damodaran: las opciones y acciones restringidas en circulación son derechos sobre
        # el patrimonio). Yahoo las da como impliedSharesOutstanding; se usan si exceden a las básicas en ≤ 25 %
        # (más que eso suele ser otra clase de acción o un error de unidades).
        _impl = _safe_float(info.get("impliedSharesOutstanding"))
        if _impl and 1.0 < _impl / sh <= 1.25:
            p["acciones_basicas"] = round(sh / 1e6, 4) if sh >= 1e6 else round(sh, 4)
            sh = _impl
            p["acciones_fuente"] = f"impliedSharesOutstanding (diluidas; básicas {p['acciones_basicas']:,.1f} M)"
        p["acciones"] = round(sh / 1e6, 4) if sh >= 1e6 else round(sh, 4)
    # marketCap / precio da el número de unidades COTIZADAS (ADS en un ADR, o todas
    # las clases en emisores multiclase). El VPS se compara con el precio de esa
    # unidad, así que esta es la base correcta cuando difiere de sharesOutstanding.
    # Antes solo se corregía con una desviación >20x: el ADR de Ecopetrol (ratio
    # exacto 20x) quedaba con acciones ordinarias y el upside salía ~-95 %.
    if mcap is not None and mcap > 0 and px_chk and px_chk > 0:
        implied = (mcap / px_chk) / 1e6
        acc_actual = p.get("acciones")
        if implied > 0 and (not acc_actual or not (0.8 <= acc_actual / implied <= 1.25)):
            p["acciones"] = round(implied, 4)
            p["acciones_fuente"] = "marketCap/precio (unidades cotizadas)"

    if p.get("acciones") and p["acciones"] > 500_000:  # >500 mil millones de acciones: escala errónea
        p["acciones"] = round(p["acciones"] / 1000.0, 4)

    # marketCap en la moneda de los EEFF para que D/E compare magnitudes homogéneas
    # (antes: deuda COP / capitalización USD → D/E ~3.000x mayor en ADRs).
    mcap_fin = mcap
    if mcap is not None and fin_cur_p and px_cur_p and fin_cur_p != px_cur_p:
        conv = convertir_precio_a_moneda_modelo(mcap, px_cur_p, fin_cur_p)
        mcap_fin = conv["precio"] if conv.get("convertido") else None
        p["mcap_fx"] = conv.get("fx")

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
            idx_map = {str(i).strip().lower(): i for i in bs.index}

            def _bs_first(candidates, excluir=()):
                """Primer valor del renglón: coincidencia EXACTA antes que parcial.

                Antes bastaba una coincidencia parcial: «Minority Interest» casaba con
                «Total Equity Gross Minority Interest» (renglón presente en TODO balance
                Yahoo), de modo que el patrimonio total se restaba como NCI (AAPL:
                −73.700 M USD de Equity; KO: −34.300 M en vez de −2.100 M).
                """
                def _valor(original):
                    for v in bs.loc[original].values:
                        fv = _safe_float(v)
                        if fv is not None:
                            return fv
                    return None
                for cand in candidates:
                    original = idx_map.get(cand.lower())
                    if original is not None:
                        val = _valor(original)
                        if val is not None:
                            return val
                for cand in candidates:
                    c = cand.lower()
                    for k, original in idx_map.items():
                        if c in k and not any(x in k for x in excluir):
                            val = _valor(original)
                            if val is not None:
                                return val
                return None
            # Minority interest explícito
            mi = _bs_first([
                "Minority Interest",
                "Noncontrolling Interest",
                "Non Controlling Interest",
                "Minority Interests",
            ], excluir=("gross", "total equity", "net income", "dividends", "liabilit"))
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
            # Inversiones financieras de largo plazo (valores negociables no corrientes: AAPL ≈ 78 mil
            # millones USD). No son operativas ni están en totalCash: se suman en el puente como activo
            # no operativo. Yahoo suele incluirlas en «Investments And Advances»; si no, se suman aquí.
            inv_fin = _bs_first([
                "Investmentin Financial Assets",
                "Available For Sale Securities",
                "Held To Maturity Securities",
            ])
            if inv_fin is not None and inv_fin > 0:
                p["inversiones_financieras_lp"] = round(float(inv_fin) / 1e9, 4)
            if (inv is not None and _bs_first(["Investments And Advances"]) is None and inv_fin
                    and _mercado_desde_pais(country) == "US"):
                inv = float(inv) + float(inv_fin)
            elif inv is None and inv_fin and _mercado_desde_pais(country) == "US":
                inv = float(inv_fin)
            if inv is not None and asociados_val is None:
                asociados_val = inv
                if p.get("inversiones_financieras_lp"):
                    p["asociados_fuente"] = (f"balance Yahoo: participadas + inversiones financieras de largo plazo "
                                             f"({p['inversiones_financieras_lp']:,.1f} en valores negociables no corrientes)")
        except Exception:
            pass
    if nci_val is not None:
        p["nci"] = round(abs(float(nci_val)) / 1e9, 4)
    if asociados_val is not None:
        p["asociados"] = round(abs(float(asociados_val)) / 1e9, 4)

    # D/E solo con cifras de esta empresa
    if total_debt is not None and mcap_fin is not None and mcap_fin > 0:
        p["de_ratio"] = round(max(0.0, total_debt / mcap_fin), 4)
    elif (total_debt is not None and book is not None and shares and book * shares > 0
          and (not fin_cur_p or fin_cur_p == px_cur_p)):
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

    # --- Mercado CAPM en la MONEDA DE LOS FLUJOS (no por sufijo del ticker) ---
    # MINEROS.CL reporta en USD: sus flujos se descuentan con UST + riesgo país CO,
    # no con el TES en COP (que incorpora ~6 % de inflación colombiana).
    currency = info.get("currency") or ""
    capm = capm_coherente_con_moneda(country, fin_cur_p or currency, ticker_yf)
    merc = capm["mercado"]
    p["rf"] = capm["rf"]
    p["erp"] = capm["erp"]
    p["crp"] = capm["crp"]
    p["g_max_macro"] = capm["g_max_macro"]
    p["mercado_capm"] = merc
    p["mercado_pais"] = capm.get("mercado_pais")
    if capm.get("erp_fuente"):
        p["erp_fuente"] = capm["erp_fuente"]
    if capm.get("cruce_moneda"):
        p["capm_fuente"] = (
            f"flujos en {fin_cur_p} → rf {merc} {capm['rf']:.2%} + ERP {capm['erp']:.2%} + riesgo país "
            f"{capm['mercado_pais']} (spread deuda {capm['crp_deuda']:.2%}; CRP patrimonio {capm['crp']:.2%}; "
            f"{capm.get('riesgo_pais_fuente') or 's/f'})"
        )

    # Tasa de impuestos de PERPETUIDAD: una tasa efectiva muy inferior a la estatutaria
    # suele reflejar pérdidas fiscales acumuladas (NOL) o créditos temporales (PLTR ≈ 4 %).
    # Perpetuarla infla NOPAT y valor terminal; se usa la estatutaria y se informa.
    _stat = tasa_estatutaria(country, capm.get("mercado_pais"))
    if p.get("tax") is not None and float(p["tax"]) < 0.5 * _stat:
        p["tax_efectiva_observada"] = float(p["tax"])
        p["tax"] = round(_stat, 4)
        p["tax_fuente"] = (
            f"estatutaria {_stat:.0%} (la efectiva observada {p['tax_efectiva_observada']:.1%} es < 50 % de la "
            "estatutaria: beneficio fiscal transitorio que no se perpetúa)"
        )

    # g TERMINAL de largo plazo (Gordon): crecimiento nominal de largo plazo de la moneda
    # de los flujos (g_lp ≈ inflación esperada + crecimiento real bajo), acotado por el techo
    # macro. Antes se usaba el CAGR histórico de ingresos: AAPL (CAGR 1,8 %) quedaba con
    # g < inflación de EE. UU., es decir, contracción real perpetua.
    cagr = 0.0
    if df_hist is not None and not df_hist.empty and "Ingresos" in df_hist.columns:
        tail = df_hist["Ingresos"].iloc[-min(5, len(df_hist)):]
        cagr = _cagr_serie(tail.tolist(), floor_g=0.0, cap_g=0.15)
    p["g_cagr_historico"] = round(cagr, 4)
    g_term = min(float(capm.get("g_lp", G_CONVERGENCIA)), float(capm["g_max_macro"]))
    p["g"] = round(float(g_term), 4)
    p["g_fuente"] = f"g de largo plazo del mercado {merc} (nominal en {fin_cur_p or currency or 'moneda del emisor'})"

    # kd: interés propio o rf de su mercado + spread (+ CDS si la deuda está en moneda dura de un emisor emergente)
    ir = _safe_float(info.get("interestRate") or info.get("borrowRate"))
    _sint = None
    try:
        _ebit_u = float(df_hist["EBIT"].iloc[-1]) * 1e9 if df_hist is not None and "EBIT" in df_hist.columns else None
        _int_u = _safe_float(info.get("_gasto_intereses"))
        _mcap_usd = mcap if str(px_cur_p or "").upper() == "USD" else (
            mcap / float(convertir_precio_a_moneda_modelo(1.0, "USD", px_cur_p).get("fx") or 0) if mcap and px_cur_p == "COP" else None)
        if _ebit_u is not None and _int_u is not None:
            _sint = calificacion_sintetica(_ebit_u, _int_u, grande=bool(_mcap_usd and _mcap_usd > 5e9))
    except Exception:
        _sint = None
    if _sint:
        _rf_kd = float(capm.get("rf_bruto", capm["rf"]))
        p["kd"] = round(_rf_kd + _sint["spread"] + float(capm.get("crp_deuda", 0.0)), 4)
        p["kd_fuente"] = (f"calificación sintética {_sint['calificacion']} (cobertura de intereses {_sint['cobertura']:.1f}×, "
                          f"Damodaran): rf {_rf_kd:.2%} + spread {_sint['spread']:.2%}"
                          + (f" + riesgo país {capm.get('crp_deuda', 0):.2%}" if capm.get("crp_deuda") else ""))
        p["calificacion_sintetica"] = _sint["calificacion"]
    elif ir is not None and 0 < ir < 0.4:
        p["kd"] = round(float(ir), 4)
    else:
        ie = _safe_float(info.get("interestExpense"))
        if ie is not None and total_debt and total_debt > 0:
            p["kd"] = round(float(np.clip(abs(ie) / total_debt, 0.01, 0.25)), 4)
        else:
            p["kd"] = round(float(capm.get("rf_bruto", capm["rf"]) + capm["kd_spread"] + capm.get("crp_deuda", 0.0)), 4)

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
    # Empresas de EE. UU.: beta «bottom-up» de la industria (Damodaran, corregida por caja).
    # Por defecto es REFERENCIA: el promedio simple de la industria lo dominan empresas pequeñas y volátiles
    # (Computers/Peripherals 1,32 frente a 1,03 de Apple), mientras que la regresión de una empresa grande y
    # líquida es precisa y Blume ya la encoge hacia 1.
    # Pasa a ser la BASE cuando la regresión no informa: Yahoo no trae beta (KO: antes 1,0 de mercado) o la
    # beta bruta es < BETA_REGRESION_MIN (GIS 0,02, HSY 0,09: con un error estándar de ≈ 0,2, son ruido y
    # llevaban el WACC a 6 %).
    _merc_beta = "US" if (merc == "US" and _mercado_desde_pais(country) == "US") else (_mercado_desde_pais(country) or merc)
    if _merc_beta:
        _bd = damodaran_beta(info.get("sector") or "", info.get("industry") or "", _merc_beta)
        if _bd:
            p["beta_industria_u"] = round(float(_bd["beta_u"]), 4)
            p["industria_beta"] = _bd["industria"]
            _ref = (f"{_bd['fuente']}: {_bd['industria']} {_bd.get('region', 'US')} {p['beta_industria_u']:.2f} "
                    f"({int(_bd['n_firmas'] or 0)} empresas, corregida por caja)")
            # Diferencia material entre la regresión y la industria: se deja constancia (en mercados poco
            # líquidos la regresión contra el índice local suele subestimar el riesgo; Damodaran prefiere la
            # bottom-up). La base sigue la misma regla en todos los mercados: regresión si informa.
            if beta is not None and beta > 0 and abs(float(p["beta_u"]) - float(_bd["beta_u"])) >= 0.15:
                p["beta_brecha_industria"] = round(float(_bd["beta_u"]) - float(p["beta_u"]), 4)
            if beta is None or beta <= 0 or float(beta) < BETA_REGRESION_MIN:
                p["beta_regresion_u"] = p["beta_u"] if beta is not None and beta > 0 else None
                p["beta_u"] = p["beta_industria_u"]
                _motivo = ("Yahoo sin beta" if beta is None or beta <= 0
                           else f"beta de regresión {float(beta):.2f} < {BETA_REGRESION_MIN:.2f}: no informativa")
                p["beta_fuente"] = f"bottom-up {_ref} ({_motivo})"
            else:
                p["beta_fuente"] = f"{p['beta_fuente']}; referencia bottom-up {_ref}"

    # Asociadas / negocios conjuntos: el valor contable puede quedarse muy corto frente a lo que
    # rinden (GEB recibe ≈ 2,3 billones COP/año de participadas). Como sus resultados ya no entran
    # en el EBIT operativo, se valoran en el puente al mayor entre libros y su utilidad
    # capitalizada al Ke (sin crecimiento: misma convención RONIC = costo de capital del DCF).
    ing_part = _safe_float(getattr(df_hist, "attrs", {}).get("ingreso_participadas")) if df_hist is not None else None
    if ing_part is not None and ing_part > 0:
        try:
            ke_aso = costo_equity_capm(beta_apalancado(p["beta_u"], p["de_ratio"], p["tax"]),
                                       rf=p["rf"], erp=p["erp"], crp=p["crp"])
            cap = ing_part / ke_aso if ke_aso and ke_aso > 0.02 else None
            p["ingreso_participadas"] = round(ing_part, 4)
            if cap is not None and cap > float(p.get("asociados") or 0):
                p["asociados_libros"] = p.get("asociados")
                p["asociados"] = round(cap, 4)
                p["asociados_fuente"] = (f"utilidad de participadas {ing_part:,.1f} / Ke {ke_aso:.1%} "
                                         f"(> valor en libros {float(p.get('asociados_libros') or 0):,.1f})")
            else:
                p["asociados_fuente"] = "valor en libros (≥ utilidad de participadas capitalizada al Ke)"
        except Exception:
            pass

    # Últimos doce meses (Yahoo info, moneda de los EEFF): base de proyección para emisores de
    # materias primas, cuyo último ejercicio cerrado puede reflejar otro nivel de precios.
    ltm_ing, ltm_ebitda = _safe_float(info.get("totalRevenue")), _safe_float(info.get("ebitda"))
    if ltm_ing and ltm_ebitda and ltm_ing > 0:
        p["ltm_ingresos"] = round(ltm_ing / 1e9, 4)
        p["ltm_ebitda"] = round(ltm_ebitda / 1e9, 4)

    if _mercado_desde_pais(country) == "US" and df_hist is not None and "Ingresos" in getattr(df_hist, "columns", []):
        _cons = consenso_ingresos_yahoo(info.get("_revenue_estimate"), float(df_hist["Ingresos"].iloc[-1]) * 1e9)
        if _cons:
            p["consenso_ingresos"] = _cons

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


def mercado_empresa(nombre_empresa):
    """Código de mercado CAPM (CO/US/…) de la empresa, coherente con su moneda de modelo."""
    try:
        p = params_empresa(nombre_empresa) or {}
        merc = p.get("mercado_capm")
        if merc in CAPM_POR_MERCADO:
            return merc
    except Exception:
        pass
    mon = str(moneda_empresa(nombre_empresa) or "").upper()
    return {"COP": "CO", "USD": "US", "BRL": "BR", "MXN": "MX", "CLP": "CL", "GBP": "GB"}.get(mon, "DEFAULT")


def g_convergencia_empresa(nombre_empresa):
    """Crecimiento nominal de largo plazo hacia el que converge la proyección explícita."""
    m = CAPM_POR_MERCADO.get(mercado_empresa(nombre_empresa), CAPM_POR_MERCADO["DEFAULT"])
    return float(m.get("g_lp", G_CONVERGENCIA))


def mercado_pais_empresa(nombre_empresa):
    """País del emisor (no la moneda de los flujos): CO para .CL y catálogo, US para AAPL, etc."""
    try:
        emp = resolver_empresa(nombre_empresa) or {}
        p = emp.get("params") or {}
        if p.get("mercado_pais"):
            return p["mercado_pais"]
        tk = str(emp.get("ticker_yf") or "")
        if nombre_empresa in EMPRESAS or tk.upper().endswith(".CL"):
            return "CO"
        return _mercado_desde_pais(emp.get("pais")) or mercado_empresa(nombre_empresa)
    except Exception:
        return None


def damodaran_empresa(nombre_empresa):
    """Múltiplo de industria y riesgo país de Damodaran aplicables a la empresa."""
    emp = resolver_empresa(nombre_empresa) or {}
    p = emp.get("params") or {}
    sector = str(emp.get("sector") or "")
    sec, _, ind = sector.partition(" / ")
    pais = mercado_pais_empresa(nombre_empresa)
    return {"multiplo": damodaran_multiplo(sec, ind or emp.get("industry") or "", pais, p.get("industria_damodaran")),
            "riesgo_pais": damodaran_riesgo_pais(pais) if pais else None,
            "mercado_pais": pais, "vigencia": damodaran_vigencia()}


def empresa_es_ciclica(nombre_empresa):
    """True si la empresa vende una materia prima (petróleo, oro, metales, carbón).

    En esos emisores la tendencia de ingresos y márgenes refleja el ciclo de precios:
    Ecopetrol 2022→2025 (Brent normalizándose) daba −10 %/año de ingresos perpetuados en
    la proyección justo cuando el 2T26 creció +35 %. Se proyecta a precio de ciclo medio.
    """
    try:
        emp = resolver_empresa(nombre_empresa) or {}
        p = emp.get("params") or {}
        if p.get("ciclico") is not None:
            return bool(p.get("ciclico"))
        return es_sector_ciclico(emp.get("sector") or "", emp.get("industry") or "")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Correcciones del usuario sobre el histórico (cifras oficiales) y suma de partes de participadas
# ---------------------------------------------------------------------------
HISTORICO_EDITABLE = ["Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC"]


def _ajustes_usuario():
    a = _almacen_estado().setdefault("ajustes_usuario", {"historico": {}, "suma_partes": {}})
    a.setdefault("narrativa", {})
    a.setdefault("paises_operacion", {})
    return a


# Narrativa explícita (marco de Damodaran): cada valoración es una historia traducida a cuatro
# palancas. El modelo propone valores por estadística; el usuario puede fijarlos con una frase.
PALANCAS_NARRATIVA = {
    "g_ingresos": "Crecimiento de ingresos (año 1)",
    "margen_ebitda": "Margen EBITDA objetivo",
    "anios_convergencia": "Años para llegar al margen objetivo",
    "ventas_capital": "Ventas por unidad de capital reinvertido",
}


def fijar_narrativa(nombre_empresa, palancas, justificacion=None):
    """Guarda las palancas que el usuario fija (las que no estén, las decide el modelo)."""
    limpio = {}
    for k, v in (palancas or {}).items():
        if k == "reinversion" and v in ("ligada", "mantenimiento"):
            limpio[k] = v
            continue
        if k not in PALANCAS_NARRATIVA or v is None:
            continue
        v = float(v)
        if not np.isfinite(v):
            raise ValueError(f"{PALANCAS_NARRATIVA[k]} no es un número válido.")
        if k == "g_ingresos" and not -0.30 <= v <= 0.60:
            raise ValueError("El crecimiento del año 1 debe estar entre −30 % y 60 %.")
        if k == "margen_ebitda" and not -0.5 <= v <= 0.95:
            raise ValueError("El margen EBITDA debe estar entre −50 % y 95 %.")
        if k == "anios_convergencia" and not 1 <= v <= 10:
            raise ValueError("La convergencia del margen debe tomar entre 1 y 10 años.")
        if k == "ventas_capital" and not 0.05 <= v <= 10:
            raise ValueError("Ventas/capital debe estar entre 0,05 y 10.")
        limpio[k] = int(round(v)) if k == "anios_convergencia" else v
    if limpio:
        _ajustes_usuario()["narrativa"][nombre_empresa] = {"palancas": limpio, "justificacion": dict(justificacion or {})}
    else:
        _ajustes_usuario()["narrativa"].pop(nombre_empresa, None)


def narrativa_sesion(nombre_empresa):
    return (_ajustes_usuario()["narrativa"] or {}).get(nombre_empresa)


# Nombres en español → nombre de la tabla de Damodaran (ctryprem).
_PAISES_DAMODARAN = {
    "colombia": "Colombia", "brasil": "Brazil", "brazil": "Brazil", "chile": "Chile", "peru": "Peru", "perú": "Peru",
    "mexico": "Mexico", "méxico": "Mexico", "estados unidos": "United States", "eeuu": "United States",
    "ee. uu.": "United States", "ee.uu.": "United States", "usa": "United States", "united states": "United States",
    "panama": "Panama", "panamá": "Panama", "guatemala": "Guatemala", "el salvador": "El Salvador",
    "honduras": "Honduras", "costa rica": "Costa Rica", "ecuador": "Ecuador", "argentina": "Argentina",
    "bolivia": "Bolivia", "uruguay": "Uruguay", "paraguay": "Paraguay", "canada": "Canada", "canadá": "Canada",
    "españa": "Spain", "espana": "Spain", "spain": "Spain", "reino unido": "United Kingdom",
    "alemania": "Germany", "francia": "France", "china": "China", "japon": "Japan", "japón": "Japan",
}


def leer_pesos_paises(texto):
    """«Brasil 40, Colombia 30, Chile 15» → {'Brazil': 40.0, 'Colombia': 30.0, 'Chile': 15.0}."""
    import re as _re
    pesos = {}
    for parte in _re.split(r"[;,\n]+", str(texto or "")):
        m = _re.match(r"\s*(.+?)\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)\s*%?\s*$", parte)
        if not m:
            if parte.strip():
                raise ValueError(f"No entendí «{parte.strip()}»: usa «País peso», p. ej. «Brasil 40».")
            continue
        nombre = m.group(1).strip()
        pais = _PAISES_DAMODARAN.get(nombre.lower(), nombre.strip().title())
        peso = float(m.group(2).replace(",", "."))
        if peso < 0:
            raise ValueError(f"Peso negativo para {nombre}.")
        pesos[pais] = pesos.get(pais, 0.0) + peso
    return pesos


def erp_por_operaciones(pesos_ingresos, paises=None):
    """Prima de riesgo ponderada por dónde la empresa genera sus ingresos (Damodaran: el riesgo país
    viene de las operaciones, no de la sede). Devuelve ERP total y CRP ponderados con su detalle."""
    paises = paises if paises is not None else ((DAMODARAN or {}).get("riesgo_pais") or {}).get("paises") or {}
    total = float(sum(pesos_ingresos.values()))
    if total <= 0:
        raise ValueError("Los pesos de ingresos deben sumar más que cero.")
    faltan = [p for p in pesos_ingresos if p not in paises]
    if faltan:
        raise ValueError("Sin prima de Damodaran para: " + ", ".join(faltan))
    w = {p: float(v) / total for p, v in pesos_ingresos.items()}
    return {"erp": sum(w[p] * float(paises[p]["erp_rating"]) for p in w),
            "crp": sum(w[p] * float(paises[p]["crp_rating"]) for p in w), "pesos": w}


def fijar_paises_operacion(nombre_empresa, pesos):
    if pesos:
        _ajustes_usuario()["paises_operacion"][nombre_empresa] = dict(pesos)
    else:
        _ajustes_usuario()["paises_operacion"].pop(nombre_empresa, None)


def paises_operacion_sesion(nombre_empresa):
    return (_ajustes_usuario()["paises_operacion"] or {}).get(nombre_empresa)


def completar_historico(df, tax):
    """Recalcula ΔNWC, NOPAT y FCFF desde las partidas editables (misma identidad que la carga de Excel)."""
    df = df[[c for c in HISTORICO_EDITABLE if c in df.columns]].astype(float).sort_index().copy()
    df["CAPEX"] = df["CAPEX"].abs()
    df["Delta_NWC"] = df["NWC"].diff().fillna(0.0)
    df["NOPAT"] = calcular_nopat(df["EBIT"], float(tax))
    df["FCFF"] = df["NOPAT"] + df["Depreciacion"] - df["CAPEX"] - df["Delta_NWC"]
    return df


def fijar_historico_usuario(nombre_empresa, df_editado, df_original=None, fuente_original=None, attrs=None):
    """Guarda en la sesión el histórico corregido por el usuario (p. ej. el CAPEX oficial de ISA).

    Solo se guardan las partidas editables; las derivadas se recalculan al usarlo. Devuelve la lista de
    celdas cambiadas («CAPEX 2025: 1.706 → 6.300»).
    """
    df = df_editado.copy()
    if "Año" in df.columns:
        df = df.set_index("Año")
    df.index = [int(x) for x in df.index]
    df = df[[c for c in HISTORICO_EDITABLE if c in df.columns]].apply(pd.to_numeric, errors="coerce")
    faltan = [c for c in HISTORICO_EDITABLE if c not in df.columns]
    if faltan or df.isna().any().any() or len(df) < 3:
        raise ValueError("El histórico corregido necesita al menos 3 años completos de: " + ", ".join(HISTORICO_EDITABLE))
    if (df["Ingresos"] <= 0).any():
        raise ValueError("Los ingresos deben ser positivos en todos los años.")
    cambios = []
    if df_original is not None:
        o = df_original
        for y in df.index:
            for c in HISTORICO_EDITABLE:
                try:
                    a, b = float(o.loc[y, c]), float(df.loc[y, c])
                except (KeyError, TypeError, ValueError):
                    cambios.append(f"{c} {y}: nuevo")
                    continue
                if abs(a - b) > 1e-6 * max(1.0, abs(a)):
                    cambios.append(f"{c} {y}: {a:,.1f} → {b:,.1f}")
    _ajustes_usuario()["historico"][nombre_empresa] = {
        "datos": {c: {int(y): float(df.loc[y, c]) for y in df.index} for c in HISTORICO_EDITABLE},
        "cambios": cambios, "fuente_original": fuente_original or "fuente original",
        "attrs": {k: v for k, v in (attrs or {}).items() if isinstance(v, (str, int, float, bool, type(None)))},
    }
    return cambios


def historico_usuario(nombre_empresa):
    return (_ajustes_usuario()["historico"] or {}).get(nombre_empresa)


def borrar_historico_usuario(nombre_empresa):
    _ajustes_usuario()["historico"].pop(nombre_empresa, None)


METODOS_PARTICIPADA = {
    "capitalizada": "Utilidad capitalizada al Ke (con ROE y g)",
    "pu": "Múltiplo P/U",
    "dividendos": "Dividendos recibidos (Gordon)",
    "mercado": "Valor de mercado × participación",
    "libros": "Valor en libros de la inversión",
}


def valorar_participada(fila, ke):
    """Valor de UNA participada para el accionista de la matriz (moneda y unidad del modelo).

    · capitalizada: U × p × (1 − g/ROE) / (Ke − g)  — con ROE = Ke y g = 0 es U × p / Ke (convención previa);
    · pu: U × p × P/U;  · dividendos: D × (1 + g) / (Ke − g), D = dividendo que recibe la matriz;
    · mercado: valor 100 % × p;  · libros: valor de la inversión en el balance de la matriz.
    Devuelve (valor, texto) o (None, motivo).
    """
    def num(k, defecto=None):
        try:
            v = fila.get(k)
            return defecto if v is None or (isinstance(v, float) and not np.isfinite(v)) or v == "" else float(v)
        except (TypeError, ValueError):
            return defecto
    p = num("participacion", 100.0) / 100.0
    met = str(fila.get("metodo") or "capitalizada")
    ke = float(ke)
    g = num("g", 0.0) / 100.0
    if met == "capitalizada":
        u, roe = num("utilidad"), num("roe", ke * 100) / 100.0
        if u is None:
            return None, "falta la utilidad"
        if roe <= 0 or ke <= g + 0.005:
            return None, "Ke debe superar a g y el ROE ser positivo"
        v = u * p * (1 - g / roe) / (ke - g)
        return v, f"{u:,.1f} × {p:.1%} × (1 − {g:.1%}/{roe:.1%}) / ({ke:.1%} − {g:.1%})"
    if met == "pu":
        u, m = num("utilidad"), num("pu")
        if u is None or not m:
            return None, "faltan la utilidad o el P/U"
        return u * p * m, f"{u:,.1f} × {p:.1%} × {m:.1f}x"
    if met == "dividendos":
        d = num("dividendo")
        if d is None:
            return None, "falta el dividendo recibido"
        if ke <= g + 0.005:
            return None, "Ke debe superar a g"
        return d * (1 + g) / (ke - g), f"{d:,.1f} × (1 + {g:.1%}) / ({ke:.1%} − {g:.1%})"
    if met == "mercado":
        v100 = num("valor")
        if v100 is None:
            return None, "falta el valor de mercado (100 %)"
        return v100 * p, f"{v100:,.1f} × {p:.1%}"
    if met == "libros":
        v = num("valor")
        return (v, "valor en libros") if v is not None else (None, "falta el valor en libros")
    return None, f"método desconocido «{met}»"


def suma_de_partes(filas, ke):
    """Valora cada participada y suma. Devuelve {"total", "detalle": [...], "errores": [...]}."""
    detalle, errores, total = [], [], 0.0
    for f in filas or []:
        nombre = str(f.get("participada") or "").strip()
        if not nombre:
            continue
        v, txt = valorar_participada(f, ke)
        if v is None:
            errores.append(f"{nombre}: {txt}")
            continue
        total += v
        detalle.append({"participada": nombre, "metodo": METODOS_PARTICIPADA.get(f.get("metodo"), f.get("metodo")),
                        "valor": v, "calculo": txt})
    return {"total": total, "detalle": detalle, "errores": errores}


# Estructura conocida de participadas (fuentes públicas). Solo la parte verificable; el resto queda agregado.
PARTICIPADAS_CURADAS = {
    "GEB — Grupo Energía Bogotá": [
        {"participada": "Enel Colombia", "participacion": 42.5, "metodo": "capitalizada", "utilidad": 3200.0,
         "fuente": "Utilidad neta 2025 de 3,2 billones COP (Portafolio, feb-2026); participación 42,5 % (Portafolio, 2021)"},
    ],
}


def participadas_sugeridas(nombre_empresa, params=None):
    """Filas iniciales del editor de suma de partes: estructura curada + el resto agregado de Yahoo."""
    p = params if params is not None else (params_empresa(nombre_empresa) or {})
    filas = [dict(f) for f in PARTICIPADAS_CURADAS.get(nombre_empresa, [])]
    ing = p.get("ingreso_participadas")
    if ing and not filas and p.get("asociados") and p.get("asociados_libros") is None:
        # La matriz ya usa el valor en libros porque supera a la utilidad capitalizada (ISA): se propone ese.
        filas.append({"participada": "Inversiones en asociadas (libros)", "participacion": 100.0, "metodo": "libros",
                      "valor": float(p["asociados"]),
                      "fuente": f"Balance; la utilidad de participadas ({float(ing):,.1f}) capitalizada al Ke vale menos"})
        filas.append({"participada": "Alternativa: utilidad de participadas", "participacion": 0.0,
                      "metodo": "capitalizada", "utilidad": round(float(ing), 1),
                      "fuente": "Pon la participación en 100 % y la de libros en 0 para usar este método"})
        return filas
    if ing:
        resto = float(ing) - sum(float(f.get("utilidad") or 0) * float(f.get("participacion") or 0) / 100.0
                                 for f in filas if f.get("metodo") in ("capitalizada", "pu"))
        if resto > 0:
            filas.append({"participada": "Resto de participadas (agregado)", "participacion": 100.0,
                          "metodo": "capitalizada", "utilidad": round(resto, 1),
                          "fuente": "Ingreso por participadas estimado de Yahoo menos las filas anteriores"})
    elif p.get("asociados"):
        filas.append({"participada": "Inversiones en asociadas (libros)", "participacion": 100.0,
                      "metodo": "libros", "valor": float(p["asociados"]), "fuente": "Balance (Yahoo o catálogo)"})
    return filas


def fijar_suma_partes(nombre_empresa, filas, resultado, ke):
    _ajustes_usuario()["suma_partes"][nombre_empresa] = {"filas": filas, "total": float(resultado["total"]),
                                                          "detalle": resultado["detalle"], "ke": float(ke)}


def suma_partes_sesion(nombre_empresa):
    return (_ajustes_usuario()["suma_partes"] or {}).get(nombre_empresa)


def borrar_suma_partes(nombre_empresa):
    _ajustes_usuario()["suma_partes"].pop(nombre_empresa, None)


def firma_ajustes_usuario(nombre_empresa):
    """Huella de las correcciones del usuario (invalida resultados cuando cambian)."""
    a = _ajustes_usuario()
    return json.dumps({"h": (a["historico"].get(nombre_empresa) or {}).get("datos"),
                       "s": (a["suma_partes"].get(nombre_empresa) or {}).get("total"),
                       "n": a["narrativa"].get(nombre_empresa),
                       "o": a["paises_operacion"].get(nombre_empresa)}, sort_keys=True, default=str)


def cargar_y_limpiar_excel(archivo, nombre_empresa, usar_datos_publicos=True):
    """Carga el histórico (Excel/CSV o datos públicos) y anota la moneda/mercado.

    Envoltorio de _cargar_y_limpiar_excel_impl: adjunta en df.attrs el crecimiento
    nominal de convergencia del mercado de la empresa, que leen todas las proyecciones
    (pestañas 1–7), de modo que la moneda del modelo y su inflación sean coherentes.
    """
    _hu = historico_usuario(nombre_empresa) if archivo is None else None
    if _hu:
        _tax = float((params_empresa(nombre_empresa) or {}).get("tax") or 0.30)
        df = completar_historico(pd.DataFrame(_hu["datos"]), _tax)
        df.index.name = "Año"
        df.attrs.update(_hu.get("attrs") or {})
        _n = len(_hu.get("cambios") or [])
        msg = (f"Histórico corregido por el usuario sobre {_hu.get('fuente_original')} ({_n} celda(s) cambiada(s)"
               + (": " + "; ".join(_hu["cambios"][:6]) if _n else "") + ").")
    else:
        df, msg = _cargar_y_limpiar_excel_impl(archivo, nombre_empresa, usar_datos_publicos=usar_datos_publicos)
    if df is not None and hasattr(df, "attrs"):
        try:
            df.attrs["g_convergencia"] = g_convergencia_empresa(nombre_empresa)
        except Exception:
            pass
        try:
            if "NOPAT" not in df.columns and "EBIT" in df.columns:
                _t = float((params_empresa(nombre_empresa) or {}).get("tax") or 0.35)
                _nop = df["EBIT"].astype(float) * (1 - _t)
            else:
                _nop = None
            _dfr = df if _nop is None else df.assign(NOPAT=_nop)
            _roic = roic_observado(_dfr, (params_empresa(nombre_empresa) or {}).get("capital_invertido"))
            df.attrs["roic_observado"] = _roic
            fijar_roic_referencia(nombre_empresa, _roic)
        except Exception:
            pass
        try:
            _pp = params_empresa(nombre_empresa) or {}
            _ci = _pp.get("capital_invertido")
            if _ci and float(_ci) > 0:
                # Capital OPERATIVO: sin las participaciones en asociadas, cuyos resultados no están en el
                # EBIT (Damodaran: las participaciones cruzadas se valoran aparte). GEB: 38.000 → 24.312.
                _as = float(_pp.get("asociados") or 0.0)
                df.attrs["capital_invertido"] = float(_ci) - _as if 0 <= _as < 0.8 * float(_ci) else float(_ci)
            _nar = narrativa_sesion(nombre_empresa)
            if _nar:
                df.attrs["narrativa"] = dict(_nar)
        except Exception:
            pass
        try:
            df.attrs["ciclico"] = empresa_es_ciclica(nombre_empresa)
            if df.attrs["ciclico"]:
                _p = params_empresa(nombre_empresa) or {}
                if _p.get("ltm_ingresos") and _p.get("ltm_ebitda"):
                    df.attrs["ltm"] = {"Ingresos": float(_p["ltm_ingresos"]), "EBITDA": float(_p["ltm_ebitda"])}
            else:
                _cons = (params_empresa(nombre_empresa) or {}).get("consenso_ingresos")
                if _cons and _cons.get("g"):
                    df.attrs["consenso_ingresos"] = dict(_cons)
        except Exception:
            pass
    return df, msg


_PALABRAS_INGRESOS = ("ingreso", "revenue", "ventas", "sales")
_CAMPOS_ENCABEZADO = ("ano", "year", "ingresos", "revenue", "ventas", "ebitda", "ebit", "capex", "nwc",
                      "capital de trabajo", "depreciacion", "fcff", "nopat", "utilidad operativa")
_HOJAS_NO_DATOS = ("instrucciones", "ejemplo", "parametros", "leeme", "readme")

# Ejemplo de la plantilla (para avisar si se carga sin reemplazarlo)
_EJEMPLO_PLANTILLA = {"Ingresos": [8500, 7800, 9200, 10500, 11200, 12000], "EBITDA": [3200, 2900, 3500, 4100, 4500, 4900]}
_EJEMPLO_PLANTILLA_V2 = {"Ingresos": [9200, 10500, 11200, 12000, 12900], "EBITDA": [3500, 4100, 4500, 4900, 5300]}


def _es_ejemplo_plantilla(clean):
    try:
        ing = [round(float(x)) for x in clean["Ingresos"].values]
        eb = [round(float(x)) for x in clean["EBITDA"].values]
        return any(ing == e["Ingresos"] and eb == e["EBITDA"] for e in (_EJEMPLO_PLANTILLA, _EJEMPLO_PLANTILLA_V2))
    except Exception:
        return False


def _tabla_desde_hoja(df0):
    """Convierte una hoja leída SIN encabezado en tabla con columnas = partidas.

    Busca en las primeras 25 filas: (a) una fila con ≥ 3 nombres de partidas (formato largo: años en filas),
    o (b) una fila con ≥ 2 años y partidas en la primera columna debajo (formato ancho de los estados
    oficiales). Así funcionan los archivos con título, notas o filas en blanco arriba. Devuelve
    (DataFrame, transpuesto) o (DataFrame vacío, False).
    """
    df0 = df0.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if df0.empty:
        return df0, False
    for i in range(min(25, len(df0))):
        celdas = [_norm_col(x) for x in df0.iloc[i].tolist() if pd.notna(x)]
        n = sum(1 for c in celdas if c in _CAMPOS_ENCABEZADO or any(c.startswith(k + " ") for k in ("ingresos", "capex", "ebitda")))
        if n >= 3:
            t = df0.iloc[i + 1:].copy()
            t.columns = [str(x).strip() if pd.notna(x) else f"col{j}" for j, x in enumerate(df0.iloc[i].tolist())]
            return t.reset_index(drop=True), False
    for i in range(min(25, len(df0))):
        fila = df0.iloc[i].tolist()
        anios = pd.to_numeric(pd.Series([str(x)[:4] for x in fila[1:]]), errors="coerce")
        if anios.between(1990, 2100).sum() >= 2:
            debajo = df0.iloc[i + 1:, 0].astype(str).map(_norm_col)
            if debajo.apply(lambda x: any(k in x for k in _PALABRAS_INGRESOS)).any():
                t = df0.iloc[i + 1:].copy()
                t.columns = ["Partida"] + [str(x)[:4] if pd.notna(x) else f"col{j}" for j, x in enumerate(fila[1:], 1)]
                t = t[t["Partida"].notna()]
                larga, _ = _normalizar_formato_ancho(t)
                return larga, True
    return pd.DataFrame(), False


def _elegir_hoja_datos(xls):
    """Hoja con más años utilizables (se ignoran Instrucciones, Ejemplo y Parámetros)."""
    mejor = (None, False, None, -1)
    for hoja in xls.sheet_names:
        if _norm_col(hoja).split(" ")[0] in _HOJAS_NO_DATOS:
            continue
        t, transp = _tabla_desde_hoja(pd.read_excel(xls, sheet_name=hoja, header=None))
        if t.empty:
            continue
        cols = {_norm_col(c) for c in t.columns}
        col_ing = next((c for c in t.columns if any(k in _norm_col(c) for k in _PALABRAS_INGRESOS)), None)
        filas = int(pd.to_numeric(t[col_ing], errors="coerce").notna().sum()) if col_ing is not None else 0
        if filas > mejor[3] and cols:
            mejor = (t, transp, hoja, filas)
    if mejor[0] is None or mejor[3] <= 0:
        raise ValueError("No se encontró una hoja con la tabla de estados financieros (encabezados Año, Ingresos, "
                         "EBITDA, EBIT, CAPEX, NWC). Usa la hoja «Datos» de la plantilla.")
    return mejor[0], mejor[1], mejor[2]


_UNIDADES_ARCHIVO = {"miles de millones": 1.0, "millones": 1e-3, "miles": 1e-6, "unidades": 1e-9}
_CLAVES_PARAMETROS = {
    "moneda": "moneda", "unidad": "unidad", "pais": "pais", "tasa de impuestos": "tax", "impuestos": "tax",
    "deuda financiera": "deuda", "deuda": "deuda", "caja": "caja", "efectivo": "caja",
    "interes minoritario": "nci", "minoritarios": "nci", "inversiones en asociadas": "asociados", "asociadas": "asociados",
    "acciones en circulacion": "acciones", "acciones": "acciones", "precio por accion": "precio", "precio": "precio",
    "beta": "beta",
}


def _leer_hoja_parametros(xls):
    """Hoja opcional «Parámetros» (columna A = concepto, B = valor). Devuelve dict normalizado o {}."""
    hoja = next((h for h in xls.sheet_names if _norm_col(h).startswith("parametros")), None)
    if hoja is None:
        return {}
    df = pd.read_excel(xls, sheet_name=hoja, header=None)
    out = {}
    for _, r in df.iterrows():
        if len(r) < 2 or pd.isna(r.iloc[0]) or pd.isna(r.iloc[1]):
            continue
        etiqueta = _norm_col(str(r.iloc[0]).split("(")[0])
        clave = next((v for k, v in _CLAVES_PARAMETROS.items() if etiqueta == k or etiqueta.startswith(k + " ")), None)
        if clave is None or clave in out:
            continue
        val = r.iloc[1]
        if clave in ("moneda", "unidad", "pais"):
            out[clave] = str(val).strip()
        else:
            v = _numero_texto_es_en(str(val)) if isinstance(val, str) else float(val)
            if v is None:
                continue
            if clave == "tax" and v > 1:  # 35 → 0,35
                v = v / 100.0
            out[clave] = float(v)
    if out.get("unidad"):
        u = _norm_col(out["unidad"])
        out["factor_unidad"] = next((f for k, f in _UNIDADES_ARCHIVO.items() if u == _norm_col(k)), None)
    if out.get("moneda"):
        out["moneda"] = out["moneda"].upper()[:3]
    return out


def _info_desde_parametros(meta, fac=1.0):
    """Datos de la hoja Parámetros con la forma de `info` de Yahoo (montos en unidades), para reutilizar
    derivar_params_desde_cero: tasa, deuda neta, D/E de mercado, acciones y beta."""
    if not meta:
        return None
    mm = 1e9 * float(fac)  # montos del archivo → miles de millones → unidades
    info = {"country": meta.get("pais") or "", "currency": meta.get("moneda"), "financialCurrency": meta.get("moneda")}
    if meta.get("tax") is not None:
        info["effectiveTaxRate"] = float(meta["tax"])
    if meta.get("deuda") is not None:
        info["totalDebt"] = float(meta["deuda"]) * mm
    if meta.get("caja") is not None:
        info["totalCash"] = float(meta["caja"]) * mm
    if meta.get("acciones"):
        info["sharesOutstanding"] = float(meta["acciones"]) * 1e6
        if meta.get("precio"):
            info["regularMarketPrice"] = float(meta["precio"])
            info["marketCap"] = float(meta["precio"]) * float(meta["acciones"]) * 1e6
    if meta.get("beta"):
        info["beta"] = float(meta["beta"])
    return info


def _normalizar_formato_ancho(raw):
    """Estados financieros oficiales suelen venir con las partidas en filas y los años en columnas.

    Si ninguna columna parece «Ingresos» pero la primera columna contiene esa partida y el resto de
    encabezados son años, se transpone. Devuelve (DataFrame, transpuesto: bool).
    """
    try:
        cols = [str(c).strip().lower() for c in raw.columns]
        if any(any(k in c for k in _PALABRAS_INGRESOS) for c in cols):
            return raw, False
        primera = raw.iloc[:, 0].astype(str).str.strip().str.lower()
        if not primera.apply(lambda x: any(k in x for k in _PALABRAS_INGRESOS)).any():
            return raw, False
        anios = pd.to_numeric(pd.Series([str(c)[:4] for c in raw.columns[1:]]), errors="coerce")
        if anios.notna().sum() < 2 or not anios.dropna().between(1990, 2100).all():
            return raw, False
        t = raw.set_index(raw.columns[0]).T
        t.index = [int(str(c)[:4]) if str(c)[:4].isdigit() else c for c in t.index]
        t = t.reset_index().rename(columns={"index": "Año"})
        t.columns = [str(c).strip() for c in t.columns]
        return t, True
    except Exception:
        return raw, False


def _escala_respecto_referencia(clean, nombre_empresa):
    """Detecta unidades distintas a las del modelo (miles de millones) comparando los ingresos del archivo con
    los de la fuente pública de la misma empresa. Devuelve (factor, aviso)."""
    try:
        ref = None
        emp = resolver_empresa(nombre_empresa) or {}
        h = emp.get("historico") or {}
        if h.get("Ingresos") and h.get("Año"):
            serie = {int(a): v for a, v in zip(h["Año"], h["Ingresos"]) if v}
            comunes = [a for a in clean.index if int(a) in serie]
            if comunes:
                a = comunes[-1]
                ref = (float(serie[int(a)]), float(clean.loc[a, "Ingresos"]))
        if ref is None:
            return 1.0, None
        r = ref[1] / ref[0]
        for fac, unidad in ((1e-3, "millones"), (1e-6, "miles"), (1e-9, "unidades"), (1e3, "billones")):
            if 0.7 <= r * fac <= 1.4:
                return fac, (f"el archivo parece estar en {unidad} (ingresos {ref[1]:,.0f} vs {ref[0]:,.1f} de la fuente "
                             f"pública): se convirtió a miles de millones")
        return 1.0, None
    except Exception:
        return 1.0, None


def _cargar_y_limpiar_excel_impl(archivo, nombre_empresa, usar_datos_publicos=True):
    """Carga financiera con trazabilidad. No mezcla filas ni completa con otra empresa.

    Excel/CSV esperado: Año (opcional), Ingresos, EBITDA, EBIT, CAPEX y NWC.
    Depreciación, Delta_NWC, NOPAT y FCFF se derivan cuando no están presentes.
    Todas las cifras deben estar en la misma moneda y unidad.
    """
    emp_resuelta = resolver_empresa(nombre_empresa)
    emp_catalogo = emp_resuelta is not None
    df_backup = df_historico_empresa(nombre_empresa)
    if archivo is None:
        nombre_norm = str(nombre_empresa or "").upper()
        if "NUTRESA" in nombre_norm and usar_datos_publicos:
            df_pub, msg_pub, tipo_pub = obtener_datos_financieros_publicos(
                nombre_empresa, preferir_yahoo=False
            )
            if df_pub is not None and len(df_pub) == 2 and tipo_pub == "PUBLICA_CURADA_NUTRESA":
                return df_pub, (
                    msg_pub + " Advertencia: histórico 2024-2025 solamente; "
                    "D&A redondeada y NWC derivado, por lo que el FCFF es preliminar."
                )
            raise ValueError(
                "NUTRESA: no se pudo cargar la serie consolidada 2024-2025. "
                "No se recurrirá a Yahoo ni a proxies genéricos."
            )
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
        _emp_sd = resolver_empresa(nombre_empresa) or {}
        if nombre_empresa in EMPRESAS and not _emp_sd.get("historico"):
            raise ValueError(
                f"{nombre_empresa}: no hay estados financieros verificados ni descarga disponible "
                "(no cotiza en Yahoo). Carga sus estados financieros con el módulo de carga (Excel/CSV)."
            )
        raise ValueError("Empresa personalizada: usa el buscador de ticker Yahoo o carga un Excel/CSV propio. No hay histórico de respaldo para este nombre.")

    path = archivo.name if hasattr(archivo, "name") else str(archivo)
    meta_xlsx = {}
    try:
        if str(path).lower().endswith(".csv"):
            raw, _transpuesto = _tabla_desde_hoja(pd.read_csv(path, header=None))
        else:
            xls = pd.ExcelFile(path)
            raw, _transpuesto, hoja_usada = _elegir_hoja_datos(xls)
            meta_xlsx = _leer_hoja_parametros(xls)
    except ValueError:
        raise
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
    avisos = ["formato ancho (partidas en filas, años en columnas): se transpuso"] if _transpuesto else []
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
            # Fechas completas («31/12/2024») se convierten a año, SOLO en las celdas no numéricas: antes una fila
            # de notas convertía toda la columna con to_datetime y 2021 pasaba a 1970 (nanosegundos desde 1970).
            faltan = years.isna()
            fechas = pd.to_datetime(raw.loc[faltan, year_col].astype(str), errors="coerce", dayfirst=True)
            years = years.where(~faltan, fechas.dt.year)
        years = years.where(years.between(1900, 2100))
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
    if _es_ejemplo_plantilla(clean):
        raise ValueError("La hoja todavía tiene los números de ejemplo de la plantilla: reemplázalos por los de tu empresa.")
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
    if meta_xlsx.get("factor_unidad") is not None:
        _fac = float(meta_xlsx["factor_unidad"])
        _txt_fac = (f"cifras en {meta_xlsx['unidad']} (hoja Parámetros): se convirtieron a miles de millones"
                    if _fac != 1.0 else None)
    else:
        _fac, _txt_fac = _escala_respecto_referencia(clean, nombre_empresa)
    if _fac != 1.0:
        for _c in [c for c in clean.columns if c in ("Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC", "Delta_NWC", "NOPAT", "FCFF")]:
            clean[_c] = clean[_c] * _fac
        avisos.append(_txt_fac)
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
    # Tasa para el NOPAT histórico: la de la hoja Parámetros, la de la empresa o 25 % (antes 0 % para una empresa
    # nueva: NOPAT = EBIT y un FCFF histórico inflado frente a la proyección, que usaba 25 %).
    tax_proxy = meta_xlsx.get("tax")
    if tax_proxy is None:
        tax_proxy = float(params_empresa(nombre_empresa).get("tax") or 0.0) or 0.25
    clean["NOPAT"] = clean["NOPAT"].where(clean["NOPAT"].notna(), clean["EBIT"] * (1 - tax_proxy))
    fcff_calc = clean["NOPAT"] + clean["Depreciacion"] - clean["CAPEX"] - clean["Delta_NWC"]
    clean["FCFF"] = clean["FCFF"].where(clean["FCFF"].notna(), fcff_calc)
    clean["EBITDA"] = clean["EBITDA"].astype(float)
    clean = clean.apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(clean[required].to_numpy(dtype=float)).all():
        raise ValueError("Hay valores no numéricos o infinitos en columnas financieras obligatorias.")
    # Empresa no catalogada: registrar histórico y params derivados desde este archivo (sin catálogo)
    if nombre_empresa not in EMPRESAS:
        params_xlsx = derivar_params_desde_cero(clean, info=_info_desde_parametros(meta_xlsx, _fac), ticker_yf=None)
        params_xlsx["origen_params"] = "excel_desde_cero"
        for _k_m, _k_p in (("nci", "nci"), ("asociados", "asociados")):
            if meta_xlsx.get(_k_m) is not None:
                params_xlsx[_k_p] = round(float(meta_xlsx[_k_m]) * _fac, 4)
        if meta_xlsx.get("precio"):
            params_xlsx["precio_referencia"] = float(meta_xlsx["precio"])
        if meta_xlsx.get("tax") is not None:
            params_xlsx["tax"] = round(float(meta_xlsx["tax"]), 4)
            params_xlsx["tax_fuente"] = "hoja Parámetros del archivo"
        # Tax: si el usuario no tiene país, conservar 0 y recalcular NOPAT cuando calibre tax en UI
        hist = {"Año": [int(a) for a in clean.index]}
        for col in clean.columns:
            hist[col] = [float(x) if pd.notna(x) else 0.0 for x in clean[col].values]
        _prev = EMPRESAS_RUNTIME.get(nombre_empresa) or {}
        EMPRESAS_RUNTIME[nombre_empresa] = {
            # Si la empresa venía de Yahoo, se conserva su ticker: el precio de mercado sigue disponible.
            "ticker_bvc": _prev.get("ticker_bvc"),
            "ticker_yf": _prev.get("ticker_yf"),
            "sector": _prev.get("sector") or "No clasificado (Excel propio)",
            "descripcion": f"Estados cargados por el usuario para {nombre_empresa}. Parámetros derivados solo de este archivo.",
            "params": params_xlsx,
            "historico": hist,
            "peers": [],
            "fuente": "Excel/CSV del usuario",
            "moneda": meta_xlsx.get("moneda") or _prev.get("moneda") or "definir",
            "moneda_precio": meta_xlsx.get("moneda") or _prev.get("moneda_precio") or None,
            "pais": meta_xlsx.get("pais") or _prev.get("pais") or "",
        }
    _puente_archivo = {}
    if meta_xlsx:
        _f = float(_fac or 1.0)
        if meta_xlsx.get("deuda") is not None:
            _puente_archivo["deuda_neta"] = round((float(meta_xlsx["deuda"]) - float(meta_xlsx.get("caja") or 0)) * _f, 4)
        for _k in ("caja", "nci", "asociados"):
            if meta_xlsx.get(_k) is not None:
                _puente_archivo[_k] = round(float(meta_xlsx[_k]) * _f, 4)
        if meta_xlsx.get("acciones"):
            _puente_archivo["acciones"] = float(meta_xlsx["acciones"])
        if meta_xlsx.get("tax") is not None:
            _puente_archivo["tax"] = round(float(meta_xlsx["tax"]), 4)
    _almacen_estado().setdefault("parametros_archivo", {})[nombre_empresa] = _puente_archivo
    if meta_xlsx:
        avisos.append("hoja Parámetros leída (" + ", ".join(k for k in ("moneda", "unidad", "pais", "tax", "deuda", "caja",
                                                                         "nci", "asociados", "acciones", "precio")
                                                                if meta_xlsx.get(k) is not None) + ")")
    msg_avisos = ("Avisos de limpieza: " + " | ".join(avisos) + ". ") if avisos else ""
    return clean, (
        f"Archivo propio validado para {nombre_empresa}: {len(clean)} observaciones. {msg_avisos}"
        f"Campos derivados: depreciación/Delta_NWC/NOPAT/FCFF cuando no venían informados. "
        + ("Parámetros de modelación derivados desde cero a partir de este archivo (sin catálogo BVC). "
           if nombre_empresa not in EMPRESAS else
           ("Supuestos de la empresa del catálogo; la hoja Parámetros reemplaza " + ", ".join(sorted(_puente_archivo)) + ". "
            if _puente_archivo else "Supuestos (deuda, acciones, impuesto) de la empresa del catálogo. "))
        + "Verifica unidad, moneda y estados auditados."
    )


def parametros_archivo(nombre_empresa):
    """Partidas del puente y tasa leídas de la hoja Parámetros del Excel cargado (miles de millones)."""
    return dict((_almacen_estado().get("parametros_archivo") or {}).get(nombre_empresa) or {})

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
RONIC_SPREAD_MAX = 0.20


RONIC_CONVERGENCIA = 0.5   # el retorno de la nueva inversión recorre la mitad del camino ROIC → WACC
MODOS_RONIC = ("roic", "wacc", "manual")


def fijar_ronic_spread(valor=None):
    """Spread RONIC − WACC MANUAL en perpetuidad para la sesión (None = vuelve al modo por defecto).

    Con spread 0 (supuesto conservador de McKinsey) el crecimiento terminal no crea
    valor: TV = NOPAT/WACC. Es razonable para negocios regulados o commodities, pero
    subvalora franquicias con ventajas competitivas duraderas (marcas, ecosistemas),
    cuyo precio de mercado incorpora retornos sobre nuevo capital > WACC. El valor se
    guarda por sesión para que TODAS las pestañas usen el mismo supuesto.
    """
    alm = _almacen_estado()
    if valor is None:
        alm.pop("_ronic_spread", None)
        alm.pop("_ronic_modo", None)
        return RONIC_SPREAD
    v = float(valor)
    if not (0.0 <= v <= RONIC_SPREAD_MAX):
        raise ValueError(f"El spread RONIC − WACC debe estar entre 0 y {RONIC_SPREAD_MAX:.0%}.")
    alm["_ronic_spread"] = v
    alm["_ronic_modo"] = "manual"
    return v


def fijar_modo_ronic(modo):
    """Retorno de la nueva inversión en el valor terminal (por sesión):
      «roic»   → RONIC = WACC + ½·(ROIC observado − WACC), sin bajar del WACC (por defecto);
      «wacc»   → RONIC = WACC: el crecimiento no crea valor (conservador);
      «manual» → WACC + el spread fijado con fijar_ronic_spread().
    """
    if modo not in MODOS_RONIC:
        raise ValueError(f"Modo RONIC desconocido: {modo}")
    _almacen_estado()["_ronic_modo"] = modo
    return modo


def modo_ronic_sesion():
    return _almacen_estado().get("_ronic_modo") or "roic"


def fijar_roic_referencia(nombre_empresa, roic):
    """ROIC observado (histórico) de la empresa en análisis; lo usa el modo «roic»."""
    r = _finite_or_none(roic)
    _almacen_estado()["_roic_referencia"] = {"empresa": nombre_empresa, "roic": r}
    return r


def roic_referencia_sesion():
    return (_almacen_estado().get("_roic_referencia") or {}).get("roic")


def roic_observado(df_hist, capital_invertido, ventana=3):
    """Mediana del NOPAT de los últimos años ÷ capital invertido (None si falta algo)."""
    try:
        cap = float(capital_invertido or 0)
        if cap <= 0 or df_hist is None or "NOPAT" not in df_hist.columns:
            return None
        nop = pd.to_numeric(df_hist["NOPAT"], errors="coerce").dropna().iloc[-ventana:]
        if nop.empty:
            return None
        r = float(np.median(nop)) / cap
        return r if np.isfinite(r) and -1.0 < r < 3.0 else None
    except Exception:
        return None


def ronic_spread_sesion(wacc=None):
    """Spread RONIC − WACC que usa el valor terminal según el modo de la sesión."""
    modo = modo_ronic_sesion()
    try:
        if modo == "manual":
            return float(_almacen_estado().get("_ronic_spread", RONIC_SPREAD))
        if modo == "wacc":
            return 0.0
        roic = roic_referencia_sesion()
        if roic is None or wacc is None:
            return RONIC_SPREAD
        return float(np.clip(RONIC_CONVERGENCIA * (float(roic) - float(wacc)), 0.0, RONIC_SPREAD_MAX))
    except (TypeError, ValueError):
        return RONIC_SPREAD


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


def driver_robusto(serie, ventana=5, k=3.5, ciclo_medio=False):
    """Nivel representativo de una razón histórica: Hampel + mediana (+ último dato si hay tendencia).

    ciclo_medio=True (emisores de materias primas): siempre la mediana del ciclo; una
    tendencia de precios no es una tendencia de capacidad y no debe fijarse en el último dato.
    """
    s = pd.Series(serie, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().iloc[-ventana:]
    if s.empty:
        return np.nan, {"n": 0, "atipicos": [], "estimador": "sin datos"}
    s_n, mask = normalizar_atipicos(s, k=k, piso_rel=0.15, piso_abs=0.015)
    nivel = float(np.median(s_n))
    estimador = "mediana"
    if ciclo_medio:
        # Materias primas: margen del ÚLTIMO ejercicio, coherente con el nivel de precios de los
        # ingresos base. La mediana del ciclo aplicada a ingresos del último año mezclaba precios
        # de 2022 con volúmenes valorados a precios de 2025 (Mineros: margen 27 % vs 30 % real).
        return float(s.iloc[-1]), {"n": int(len(s_n)), "atipicos": [],
                                   "estimador": "último ejercicio (coherente con el precio de los ingresos base)"}
    if len(s_n) >= 4 and float(np.ptp(s_n.to_numpy())) > 0:  # serie constante: sin tendencia (y sin aviso de SciPy)
        rho = _sps.spearmanr(np.arange(len(s_n)), s_n.to_numpy())[0]
        if np.isfinite(rho) and abs(rho) >= 0.8:
            # tendencia persistente: la mediana "rebotaría" hacia niveles ya abandonados; se mantiene el nivel actual
            nivel = float(s_n.iloc[-1])
            estimador = "último dato (tendencia monótona; no se extrapola ni se revierte)"
    return nivel, {"n": int(len(s_n)), "atipicos": [i for i, m in zip(s.index, mask) if m], "estimador": estimador}


def _margenes_robustos(df_hist, ciclo_medio=False):
    """Márgenes independientes de EBITDA, EBIT y D&A sobre ingresos.

    No fuerza EBIT = EBITDA − D&A: algunos emisores incluyen impuestos operativos
    y resultados de participadas en su EBITDA publicado. En esos casos la identidad
    aritmética no representa D&A ni EBIT operativo comparable.
    """
    ing = df_hist["Ingresos"].astype(float).replace(0, np.nan)
    m_ebitda, i1 = driver_robusto(df_hist["EBITDA"].astype(float) / ing, ciclo_medio=ciclo_medio)
    if "Depreciacion" in df_hist.columns:
        da_hist = pd.to_numeric(df_hist["Depreciacion"], errors="coerce").astype(float)
        m_da, i2 = driver_robusto(da_hist / ing, ciclo_medio=ciclo_medio)
    else:
        m_da, i2 = driver_robusto(
            (df_hist["EBITDA"].astype(float) - df_hist["EBIT"].astype(float)) / ing
        )
    m_ebit, i3 = driver_robusto(df_hist["EBIT"].astype(float) / ing, ciclo_medio=ciclo_medio)
    m_ebitda = float(np.clip(m_ebitda if np.isfinite(m_ebitda) else 0.20, -0.20, 0.90))
    m_ebit = float(np.clip(m_ebit if np.isfinite(m_ebit) else m_ebitda - m_da, -0.20, 0.90))
    m_da = float(np.clip(m_da if np.isfinite(m_da) else 0.05, 0.0, 0.50))
    return m_ebitda, m_ebit, m_da, {"ebitda": i1, "da": i2, "ebit": i3}


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
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
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
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.tsa.stattools import adfuller
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


def calcular_nopat(ebit, tax):
    """NOPAT coherente: EBIT - tasa fiscal × max(EBIT, 0), sin escudo fiscal automático por pérdidas."""
    try:
        tasa = float(tax)
    except (TypeError, ValueError) as exc:
        raise ValueError("La tasa fiscal debe ser numérica entre 0 y 1.") from exc
    if not np.isfinite(tasa) or not 0.0 <= tasa <= 1.0:
        raise ValueError("La tasa fiscal debe ser finita y estar entre 0 y 1.")
    es_serie = isinstance(ebit, pd.Series)
    try:
        valores = pd.to_numeric(ebit, errors="raise")
        arr = np.asarray(valores, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("EBIT contiene valores no numéricos.") from exc
    if not np.isfinite(arr).all():
        raise ValueError("EBIT contiene valores no finitos.")
    resultado = arr - tasa * np.maximum(arr, 0.0)
    if es_serie:
        return pd.Series(resultado, index=ebit.index, name="NOPAT")
    if np.isscalar(ebit):
        return float(resultado)
    return resultado


VENTAS_CAPITAL_RANGO = (0.10, 10.0)
# Reinversión ligada al crecimiento: opción de la narrativa (pestaña «Narrativa»), no el valor por defecto.
# Con datos reales (28-oct-2026) baja ISA 17 %, BVC 34 % y lleva Celsia a ≈ 0: en utilities con tarifas
# indexadas, parte del crecimiento nominal no exige capital nuevo y la razón ventas/capital histórica lo
# sobrestima. Queda a decisión del usuario, con el impacto visible.
REINVERSION_LIGADA_POR_DEFECTO = False


def ventas_capital_historica(df_hist, capital_invertido=None, anios=3):
    """Ingresos adicionales por unidad de capital reinvertido (Damodaran: sales-to-capital).

    Marginal = Δingresos ÷ reinversión neta de los últimos años; si es inestable (fuera de 0,5–2 ×
    la media) o no se puede calcular, se usa la media = ingresos ÷ capital invertido.
    Devuelve (valor, fuente) o (None, motivo).
    """
    try:
        ing = df_hist["Ingresos"].astype(float)
        dnwc = df_hist["Delta_NWC"].astype(float) if "Delta_NWC" in df_hist.columns else df_hist["NWC"].astype(float).diff().fillna(0.0)
        reinv = (df_hist["CAPEX"].astype(float) - df_hist["Depreciacion"].astype(float) + dnwc).tail(anios)
        d_ing = ing.diff().tail(anios)
    except (KeyError, TypeError, ValueError):
        return None, "histórico sin CAPEX, depreciación o ingresos"
    media = None
    if capital_invertido and float(capital_invertido) > 0:
        media = float(ing.iloc[-1]) / float(capital_invertido)
    marginal = float(d_ing.sum() / reinv.sum()) if float(reinv.sum()) > 0 else None
    lo, hi = VENTAS_CAPITAL_RANGO
    if media is not None and marginal is not None and 0.5 * media <= marginal <= 2.0 * media and lo <= marginal <= hi:
        return marginal, f"marginal de los últimos {anios} años (Δingresos ÷ reinversión neta)"
    if media is not None and lo <= media <= hi:
        return media, "media: ingresos ÷ capital invertido"
    if marginal is not None and lo <= marginal <= hi:
        return marginal, f"marginal de los últimos {anios} años (sin capital invertido para contrastar)"
    return None, "no calculable de forma estable"


def proyectar_por_drivers(df_hist, horizonte=5, tax=0.35, g_convergencia=None, convergencia_capex=True):
    """
    Proyección por drivers con estimadores ROBUSTOS (mediana + Hampel) e identidad FCFF:
    - Ingresos: crecimiento = mediana robusta de las variaciones anuales (admite caídas), con
      convergencia lineal hacia G_CONVERGENCIA al final del horizonte.
    - EBITDA, EBIT y D&A proyectados como drivers independientes; evita asumir EBIT = EBITDA − D&A
      cuando el EBITDA reportado incluye impuestos operativos o resultados de participadas.
    - CAPEX % ingresos robusto; converge hacia un nivel de mantenimiento (≤ 1,3×D&A) para que el
      último año del horizonte sea representativo de la perpetuidad.
    - NWC: coeficiente robusto sobre ΔIngresos (admite capital de trabajo negativo).
    - Sin pisos/techos de margen específicos de un sector.
    """
    H = int(horizonte)
    if g_convergencia is None:
        g_convergencia = getattr(df_hist, "attrs", {}).get("g_convergencia")
    g_conv = G_CONVERGENCIA if g_convergencia is None else float(g_convergencia)
    años_fut = list(range(int(df_hist.index[-1]) + 1, int(df_hist.index[-1]) + 1 + H))
    ing = df_hist["Ingresos"].astype(float)

    ciclico = bool(getattr(df_hist, "attrs", {}).get("ciclico"))
    g0, info_g = driver_robusto(ing.pct_change())
    g_hist = float(g0) if np.isfinite(g0) else None
    g0 = float(np.clip(g0 if np.isfinite(g0) else 0.03, -0.10, 0.12))
    if ciclico:
        # Materias primas: precio de ciclo medio → ingresos crecen al nominal de largo plazo.
        g0 = float(g_conv)
        info_g = dict(info_g, estimador="ciclo medio (no se extrapola la tendencia de precios)")
    consenso = getattr(df_hist, "attrs", {}).get("consenso_ingresos") if not ciclico else None
    g_path = ruta_crecimiento_tres_etapas(consenso.get("g"), g_conv, H) if consenso else None
    if g_path is not None:
        # Tres etapas (empresas de EE. UU. con consenso): analistas → convergencia → perpetuidad.
        g0 = float(g_path[0])
        info_g = dict(info_g, estimador=(f"tres etapas: consenso de analistas {', '.join(f'{x:.1%}' for x in consenso['g'])} "
                                         f"→ convergencia lineal a {g_conv:.1%} en el año {H}"))
    narr = (getattr(df_hist, "attrs", {}).get("narrativa") or {})
    pal = dict(narr.get("palancas") or {})
    fuentes_pal = {}
    if pal.get("g_ingresos") is not None:
        g0 = float(pal["g_ingresos"])
        g_path = None  # la ruta del usuario reemplaza la de consenso o estadística
        info_g = dict(info_g, estimador=f"narrativa del usuario: {g0:.1%} el año 1 → {g_conv:.1%} al final")
        fuentes_pal["g_ingresos"] = "usuario"
    if g_path is not None:
        pass
    elif H > 1:
        g_path = np.array([g0 + (g_conv - g0) * i / (H - 1) for i in range(H)])
    else:
        g_path = np.array([g0])
    ing_base = float(ing.iloc[-1])
    m_ebitda, m_ebit, m_da, info_m = _margenes_robustos(df_hist, ciclo_medio=ciclico)
    base_ltm = False
    ltm = getattr(df_hist, "attrs", {}).get("ltm") if ciclico else None
    if ltm:
        try:
            li, le = float(ltm["Ingresos"]), float(ltm["EBITDA"])
            # Solo si es plausible frente al último cierre (descarta unidades o monedas cruzadas).
            if li > 0 and 0.4 <= li / ing_base <= 2.5 and -0.2 < le / li < 0.9:
                ing_base, m_ebitda = li, le / li
                m_ebit = m_ebitda - m_da
                base_ltm = True
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            pass
    ing_proj = ing_base * np.cumprod(1 + g_path)
    ing_prev = np.concatenate([[ing_base], ing_proj[:-1]])

    # Margen: el modelo lo fija en el representativo desde el año 1 (eso ya es una historia: «el último
    # año fue atípico»). La narrativa puede fijar otro objetivo y cuántos años toma llegar a él.
    try:
        m_ultimo = float(df_hist["EBITDA"].iloc[-1]) / float(ing.iloc[-1])
    except (ZeroDivisionError, TypeError, ValueError):
        m_ultimo = m_ebitda
    m_obj = float(pal["margen_ebitda"]) if pal.get("margen_ebitda") is not None else m_ebitda
    n_conv = int(pal.get("anios_convergencia") or 1)
    if pal.get("margen_ebitda") is not None:
        fuentes_pal["margen_ebitda"] = "usuario"
    if pal.get("anios_convergencia") is not None:
        fuentes_pal["anios_convergencia"] = "usuario"
    m_inicio = m_ultimo if (n_conv > 1 and not base_ltm) else m_obj
    m_path = np.array([m_inicio + (m_obj - m_inicio) * min((i + 1) / n_conv, 1.0) for i in range(H)])
    ebitda_proj = ing_proj * m_path
    ebit_proj = ing_proj * (m_ebit + (m_path - m_ebitda))  # la D&A no cambia con la historia de margen
    dep_proj = ing_proj * m_da

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

    # Reinversión atada al crecimiento (g = tasa de reinversión × ROIC): la reinversión neta de cada año
    # financia los ingresos adicionales del año siguiente a la eficiencia histórica (ventas/capital), y el
    # último año financia el primero de la perpetuidad. Antes el CAPEX convergía al mantenimiento por su
    # cuenta mientras los ingresos seguían creciendo: un «valle» de reinversión antes del valor terminal
    # (ISA: FCFF 2030 un 52 % mayor que el primer flujo de la perpetuidad). No aplica a materias primas,
    # cuyos ingresos se mueven por precio y no por capacidad instalada.
    s2c, s2c_fuente = (None, None)
    reinversion_ligada = False
    if pal.get("ventas_capital") is not None:
        s2c, s2c_fuente = float(pal["ventas_capital"]), "usuario"
        fuentes_pal["ventas_capital"] = "usuario"
    elif not ciclico:
        s2c, s2c_fuente = ventas_capital_historica(df_hist, getattr(df_hist, "attrs", {}).get("capital_invertido"))
    modo_reinv = pal.get("reinversion") or ("ligada" if REINVERSION_LIGADA_POR_DEFECTO else "mantenimiento")
    if s2c and not ciclico and convergencia_capex and modo_reinv == "ligada":
        ing_sig = np.concatenate([ing_proj[1:], [ing_proj[-1] * (1.0 + g_conv)]])
        reinv_neta = np.maximum((ing_sig - ing_proj) / s2c, 0.0)  # sin liberar capital si los ingresos caen
        capex_proj = np.maximum(dep_proj + reinv_neta - delta_nwc, 0.0)
        capex_path = capex_proj / ing_proj
        reinversion_ligada = True

    nopat_proj = calcular_nopat(ebit_proj, tax)
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
        "ciclico": ciclico,
        "base_ltm": base_ltm,
        # EBITDA «normal» para múltiplos (criterio de ciclo medio del modelo del curso: margen
        # representativo × tamaño actual), no el de un año raro. Mismo margen que la proyección.
        "ebitda_normalizado": float(ing_base * m_ebitda),
        "ebitda_normalizado_metodo": (
            "EBITDA de los últimos doce meses (materia prima)" if base_ltm else
            f"margen EBITDA representativo {m_ebitda:.1%} ({info_m['ebitda'].get('estimador')}) × ingresos "
            f"{'del último periodo' if not ciclico else 'del último ejercicio'}"),
        "g_ingresos_historico": g_hist,
        "tres_etapas": bool(consenso),
        "consenso_ingresos": dict(consenso) if consenso else None,
        "g_ingresos_ruta": [float(x) for x in g_path],
        # Fuera de dominio: crecimiento observado muy por encima del techo del motor (12 %).
        # Un DCF de 5 años con convergencia rápida subestima sistemáticamente a estos emisores.
        "fuera_de_dominio_crecimiento": bool(g_hist is not None and not ciclico and g_hist > 0.25),
        "reinversion_ligada": reinversion_ligada,
        "modo_reinversion": modo_reinv if not ciclico else "materia prima: CAPEX converge al mantenimiento",
        "ventas_capital": s2c,
        "ventas_capital_fuente": s2c_fuente,
        "margen_ebitda_ultimo": m_ultimo,
        "margen_ebitda_objetivo": m_obj,
        "anios_convergencia_margen": n_conv,
        "narrativa": narrativa_modelo(g0, m_obj, n_conv, s2c, m_ultimo, info_g, info_m, s2c_fuente,
                                      fuentes_pal, narr.get("justificacion") or {}, ciclico, base_ltm),
    }
    return df_proj, meta


def narrativa_modelo(g0, m_obj, n_conv, s2c, m_ultimo, info_g, info_m, s2c_fuente, fuentes_pal, justif, ciclico, base_ltm):
    """Las cuatro palancas de la historia con su valor, quién la decidió y la frase que la sostiene."""
    def frase(k, por_defecto):
        return justif.get(k) or por_defecto
    est_m = (info_m.get("ebitda") or {}).get("estimador") or "estimador robusto"
    dif = m_obj - m_ultimo
    if base_ltm:
        txt_m = "margen de los últimos doce meses (materia prima a precio de ciclo medio)"
    elif abs(dif) > 0.02:
        txt_m = (f"{est_m}: supone que el margen del último año ({m_ultimo:.1%}) "
                 + ("fue anormalmente bajo y se recupera" if dif > 0 else "fue anormalmente alto y se normaliza"))
    else:
        txt_m = f"{est_m}: cercano al último año ({m_ultimo:.1%})"
    filas = [
        {"palanca": "g_ingresos", "nombre": PALANCAS_NARRATIVA["g_ingresos"], "valor": g0,
         "fuente": fuentes_pal.get("g_ingresos", "modelo"), "frase": frase("g_ingresos", info_g.get("estimador") or "")},
        {"palanca": "margen_ebitda", "nombre": PALANCAS_NARRATIVA["margen_ebitda"], "valor": m_obj,
         "fuente": fuentes_pal.get("margen_ebitda", "modelo"), "frase": frase("margen_ebitda", txt_m)},
        {"palanca": "anios_convergencia", "nombre": PALANCAS_NARRATIVA["anios_convergencia"], "valor": n_conv,
         "fuente": fuentes_pal.get("anios_convergencia", "modelo"),
         "frase": frase("anios_convergencia", "inmediata (año 1)" if n_conv <= 1 else f"lineal en {n_conv} años")},
        {"palanca": "ventas_capital", "nombre": PALANCAS_NARRATIVA["ventas_capital"], "valor": s2c,
         "fuente": fuentes_pal.get("ventas_capital", "modelo"),
         "frase": frase("ventas_capital", "no aplica: materia prima (ingresos por precio, no por capacidad)" if ciclico
                        else (s2c_fuente or "no calculable: CAPEX converge al mantenimiento"))},
    ]
    return filas


def proyectar_por_ets(df_hist, horizonte=5, tax=0.35):
    """ETS/Holt sobre ingresos y CAPEX; márgenes e identidad FCFF como en drivers."""
    años_fut = list(range(int(df_hist.index[-1]) + 1, int(df_hist.index[-1]) + 1 + horizonte))
    ing_mean, _, _, std_ing, nombre = ajustar_ets(df_hist["Ingresos"], horizonte)
    margen_ebitda, margen_ebit, m_da, _ = _margenes_robustos(df_hist)
    ebitda_proj = ing_mean * margen_ebitda
    ebit_proj = ing_mean * margen_ebit
    capex_mean, _, _, _, _ = ajustar_ets(df_hist["CAPEX"], horizonte)
    capex_mean = np.clip(capex_mean, 0.0, ing_mean * 0.60)
    nwc_mean, _, _, _, _ = ajustar_ets(df_hist["NWC"], horizonte)
    delta_nwc = np.diff(np.concatenate([[float(df_hist["NWC"].iloc[-1])], nwc_mean]))
    dep_proj = ing_mean * m_da   # usa D&A histórica; no infiere depreciación de EBITDA − EBIT
    nopat_proj = calcular_nopat(ebit_proj, tax)
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
    margen_ebitda, margen_ebit, m_da, _ = _margenes_robustos(df_hist)
    ebitda_proj = ing_mean * margen_ebitda
    ebit_proj = ing_mean * margen_ebit
    capex_mean, _, _, _ = ajustar_arima(df_hist["CAPEX"], horizonte=horizonte)
    capex_mean = np.clip(capex_mean, 0.0, ing_mean * 0.60)
    nwc_mean, _, _, _ = ajustar_arima(df_hist["NWC"], horizonte=horizonte)
    delta_nwc = np.diff(np.concatenate([[df_hist["NWC"].iloc[-1]], nwc_mean]))
    dep_proj = ing_mean * m_da   # usa D&A histórica; no infiere depreciación de EBITDA − EBIT
    nopat_proj = calcular_nopat(ebit_proj, tax)
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
    """WACC con D/E y costos expresados como fracciones (no porcentajes enteros).

    Valida dominios para evitar resultados aparentemente válidos producidos por
    tasas mal digitadas (p. ej. 12 en vez de 0.12) o estructura de capital imposible.
    """
    de, kd, ke, t = map(float, (de, kd, ke, t))
    if not all(np.isfinite(x) for x in (de, kd, ke, t)):
        raise ValueError("D/E, Kd, Ke y tasa fiscal deben ser valores finitos.")
    if de < 0:
        raise ValueError("D/E no puede ser negativo.")
    if kd < 0 or ke < 0:
        raise ValueError("Kd y Ke deben ser tasas no negativas en formato decimal.")
    if not 0 <= t <= 1:
        raise ValueError("La tasa fiscal debe estar entre 0 y 1 (p. ej. 0.35).")
    we = 1.0 / (1.0 + de)
    wd = de / (1.0 + de)
    wacc = we * ke + wd * kd * (1.0 - t)
    if not np.isfinite(wacc) or wacc <= 0:
        raise ValueError("WACC resultante debe ser finito y mayor que cero.")
    return wacc, we, wd


def costo_equity_capm(beta_l, rf=0.09, erp=0.06, crp=0.0):
    """
    CAPM con prima país opcional.
    Ke = rf + beta apalancada × ERP + CRP.
    Tasas en decimales; las fuentes y fechas deben registrarse en los parámetros del modelo.
    """
    try:
        beta_l = float(beta_l)
        rf = float(rf)
        erp = float(erp)
        crp = 0.0 if crp is None else float(crp)
    except (TypeError, ValueError) as exc:
        raise ValueError("Beta, RF, ERP y CRP deben ser numéricos.") from exc
    if not all(np.isfinite(x) for x in (beta_l, rf, erp, crp)):
        raise ValueError("Beta, RF, ERP y CRP deben ser finitos.")
    if beta_l < 0:
        raise ValueError("Beta negativa requiere una justificación explícita.")
    if min(rf, erp, crp) < 0:
        raise ValueError("RF, ERP y CRP no pueden ser negativos en esta configuración.")
    ke = rf + beta_l * erp + crp
    if not np.isfinite(ke) or ke <= 0:
        raise ValueError("Ke resultante debe ser finito y positivo.")
    return float(ke)



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
    es_curado = any(k in msg for k in ("curada", "curado", "pública curada", "publica_curada", "catálogo", "catalogo"))
    if "corregido por el usuario" in msg:
        nivel, etiqueta = "MEDIA", ("Correcciones del usuario sobre la fuente pública: verifica que sean cifras "
                                   "oficiales (" + (re.search(r"\((\d+) celda", msg).group(1) if re.search(r"\((\d+) celda", msg) else "?")
                                   + " celdas)")
    elif "excel" in msg and "error" not in msg and "insuficientes" not in msg and "respaldo" not in msg:
        nivel, etiqueta = "ALTA", "Estados / Excel del usuario"
    elif es_curado and not msg.startswith("descargado desde yahoo"):
        # El mensaje del catálogo dice «Yahoo no sustituye el catálogo»: antes caía
        # en la rama Yahoo y la ficha rotulaba la fuente como descarga Yahoo.
        nivel, etiqueta = "MEDIA-BAJA", "Respaldo curado del catálogo (solo años verificables; NWC puede ser estimado — preferir Yahoo o EEFF del usuario)"
    elif "yahoo" in msg or "yfinance" in msg:
        # La serie Yahoo puede combinar partidas reportadas con CAPEX/NWC aproximados.
        # No debe etiquetarse como calidad MEDIA si la propia carga declara proxies.
        if "proxy" in msg or "estimad" in msg or "aproximad" in msg:
            nivel, etiqueta = (
                "MEDIA-BAJA",
                "Yahoo Finance con partidas proxy/estimadas; FCFF, ROIC, MVA y TIR son indicativos",
            )
        else:
            nivel, etiqueta = "MEDIA", "Descarga pública Yahoo Finance (agregada; no es el PDF auditado)"
    elif "respaldo" in msg or "backup" in msg:
        nivel, etiqueta = "MEDIA-BAJA", "Serie histórica de respaldo (ilustrativa)"
    else:
        nivel, etiqueta = "MEDIA", "Mixto / revisar fuente"
    mercado = "Sin precio BVC en vivo"
    if mkt and mkt.get("ok") and mkt.get("precio"):
        _mon_px = str(mkt.get("moneda") or "COP").upper()
        _px_fmt = f"{mkt.get('precio'):,.0f}" if _mon_px == "COP" else f"{mkt.get('precio'):,.2f}"
        mercado = f"Precio de mercado disponible ({_px_fmt} {_mon_px})"
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
    # g no puede superar el techo (min(g_max_macro, WACC−1 pp) en la fila más baja): si la rejilla lo cruzaba,
    # las columnas por encima del techo repetían el mismo EV (ISA: g = 6,0/6,5/7,0 % idénticas). Se desplaza
    # la rejilla para que termine en el techo.
    techo = min(float(g_max_macro), min(waccs) - 0.01)
    g_top = min(g_base + 0.01, techo)
    gs = [max(0.005, g_top + dg) for dg in (-0.02, -0.015, -0.01, -0.005, 0.0)]
    gs = sorted(dict.fromkeys(round(x, 6) for x in gs))
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


UMBRAL_SOBREVALORACION = 0.30   # downside ≥ 30 % bloquea sesgos positivos
UMBRAL_MARGEN_SEGURIDAD = 0.20  # upside ≥ 20 % cuenta como soporte


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
            "Equity value base ≤ 0 tras el bridge. Con deuda neta: Equity = EV − deuda neta − NCI − otros claims + asociados; "
            "con deuda bruta: Equity = EV − deuda bruta + caja − NCI − otros claims + asociados. "
            "Compara en el detalle del puente el EV mínimo para Equity = 0 y verifica que EV, deuda, caja, NCI y asociados "
            "estén en la misma moneda/unidad; revisa también FCFF proyectado y valor terminal."
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
    try:
        roic_fin = roic is not None and np.isfinite(float(roic))
    except (TypeError, ValueError):
        roic_fin = False
    if not roic_fin:
        # NaN no es "ROIC > WACC": antes la comparación fallida caía en la rama de soporte.
        alertas.append("ROIC no disponible (sin capital invertido en balance): no se evalúa creación de valor.")
    elif roic < wacc:
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

    # Contraste valor del modelo vs precio (antes se recibían pero NO se usaban: una
    # empresa con −75 % de downside podía salir «PRELIMINAR POSITIVO»).
    margen_mercado = None
    try:
        if precio_mercado is not None and equity_por_accion is not None and float(precio_mercado) > 0:
            margen_mercado = float(equity_por_accion) / float(precio_mercado) - 1.0
            if not np.isfinite(margen_mercado):
                margen_mercado = None
    except (TypeError, ValueError):
        margen_mercado = None
    precio_sobre_valor = margen_mercado is not None and margen_mercado <= -UMBRAL_SOBREVALORACION
    if precio_sobre_valor and margen_mercado <= -0.999:
        # Valor por acción 0 (patrimonio ≤ 0): «el precio supera el valor en x %» sería una división por cero.
        alertas.append(
            "Con estos supuestos el modelo no asigna valor a la acción (patrimonio ≤ 0 tras restar deuda y otros "
            "derechos), mientras el mercado le da precio: revisa crecimiento, reinversión, márgenes y deuda."
        )
    elif precio_sobre_valor:
        alertas.append(
            f"El precio de mercado supera en {(-margen_mercado / (1 + margen_mercado)) * 100:.0f}% el valor por acción "
            f"del modelo (downside {margen_mercado * 100:.0f}%): no hay margen de seguridad en el caso base. "
            "Revisa el WACC implícito del precio para ver qué crecimiento o riesgo descuenta el mercado."
        )
    elif margen_mercado is not None and margen_mercado >= UMBRAL_MARGEN_SEGURIDAD:
        soportes.append(f"Margen de seguridad: valor del modelo {margen_mercado * 100:.0f}% por encima del precio.")

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
    elif precio_sobre_valor:
        decision = "NEUTRAL / MONITOREAR · PRECIO SOBRE VALOR"
        color = "#D97706"
        sesgo = (
            "El precio de mercado está muy por encima del valor del caso base: aunque los fundamentos "
            "puedan ser sólidos, no hay margen de seguridad para un sesgo de compra."
        )
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
                + ("pero la serie financiera es una descarga pública agregada (Yahoo), no estados auditados. "
                   if procedencia.get("nivel_calidad") == "MEDIA" and not solo_dato else
                   "pero la serie financiera es de respaldo ilustrativo. ")
                + "No se puede emitir sesgo de inversión firme hasta cargar estados auditados o un Excel oficial."
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
    Limita el crecimiento terminal superior sin alterar silenciosamente una
    hipótesis de contracción perpetua (g < 0). El usuario conserva el supuesto
    económico ingresado; solo se aplica un techo por prudencia.
    """
    g = float(g)
    wacc = float(wacc)
    g_max_macro = float(g_max_macro)
    margen_seguridad = float(margen_seguridad)
    if not all(np.isfinite(x) for x in (g, wacc, g_max_macro, margen_seguridad)):
        raise ValueError("g, WACC, techo macro y margen deben ser finitos.")
    if wacc <= 0:
        raise ValueError("WACC debe ser positivo.")
    if g_max_macro < 0 or margen_seguridad < 0:
        raise ValueError("El techo macro y el margen no pueden ser negativos.")
    g_cap = min(g_max_macro, wacc - margen_seguridad)
    if g_cap < 0:
        raise ValueError("No hay margen viable entre WACC y el crecimiento terminal.")
    g_use = min(g, g_cap)
    return g_use, g_cap



def validar_inputs_valoracion(wacc, g, fcff_series=None, g_max_macro=0.05, acciones=None, kd=None, rf=None):
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
        msgs.append(f"WACC inválido ({w}). Debe ser finito y > 0.")
        return msgs
    if not np.isfinite(g):
        msgs.append("g terminal no finito.")
        return msgs
    if not np.isfinite(float(g_max_macro)) or float(g_max_macro) < 0:
        msgs.append("El techo macro de g debe ser finito y no negativo.")
        return msgs
    if g < 0:
        msgs.append("g terminal negativo: representa contracción perpetua; revisar si se desea modelar así. La función de anclaje conserva g negativo y solo aplica un techo superior.")
    g_use, g_cap = anclar_g_terminal(g, w, g_max_macro=g_max_macro)
    if not np.isclose(g_use, g, rtol=0.0, atol=1e-9):
        msgs.append(f"g terminal ajustado por disciplina del modelo: ingresado {g*100:.2f}%, utilizado {g_use*100:.2f}% (techo aplicado {g_cap*100:.2f}%).")
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
    if kd is not None and rf is not None:
        try:
            if float(kd) < float(rf):
                msgs.append(
                    f"Kd ({float(kd)*100:.2f}%) < tasa libre de riesgo ({float(rf)*100:.2f}%) en la misma moneda: "
                    "el costo de la deuda no puede ser menor que el del Estado. El WACC queda subestimado y el "
                    "valor sobrestimado; usar Kd ≥ rf + spread de crédito o modelar la deuda en su moneda original."
                )
        except (TypeError, ValueError):
            pass
    return msgs


BRECHA_WACC_G_SENSIBLE = 0.02  # diferencia WACC − g por debajo de la cual se advierte sensibilidad alta


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
    try:
        fcff_series = [float(x) for x in list(fcff_series)]
        wacc = float(wacc)
        g = float(g)
        g_max_macro = float(g_max_macro)
    except (TypeError, ValueError) as exc:
        raise ValueError("FCFF, WACC, g y techo macro deben ser numéricos.") from exc
    n = len(fcff_series)
    if not np.isfinite(wacc) or wacc <= 0:
        raise ValueError("WACC inválido: debe ser finito y estrictamente mayor que cero.")
    if not np.isfinite(g):
        raise ValueError("La tasa g terminal debe ser finita.")
    if not np.isfinite(g_max_macro) or g_max_macro < 0:
        raise ValueError("El techo macro de g debe ser finito y no negativo.")
    if not all(np.isfinite(x) for x in fcff_series):
        raise ValueError("La serie FCFF contiene valores no finitos.")
    if not fcff_series:
        raise ValueError("La serie FCFF está vacía; no se puede calcular un DCF.")
    # Validar todos los componentes del puente antes de valorar; NaN no debe
    # propagarse silenciosamente hasta el Equity Value.
    # Partidas del puente no informadas (None) cuentan como 0, igual que en la barra lateral.
    deuda_neta, caja, nci, otros_claims, asociados = (0.0 if x is None else x
                                                      for x in (deuda_neta, caja, nci, otros_claims, asociados))
    bridge_inputs = (deuda_neta, caja, nci, otros_claims, asociados)
    if not all(np.isfinite(float(x or 0)) for x in bridge_inputs):
        raise ValueError("Deuda, caja, NCI, otros claims y asociados deben ser finitos.")
    if acciones is not None and (not np.isfinite(float(acciones)) or float(acciones) <= 0):
        raise ValueError("El número de acciones debe ser finito y mayor que cero.")
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

    # Terminal Gordon: no sustituir un FCFF final negativo por un promedio histórico
    # positivo. Esa heurística puede inflar materialmente el valor terminal y ocultar
    # deterioro. Si no se aporta NOPAT normalizado, el TV se fija en cero y se informa.
    fcff_tv = float(fcff_series[-1])
    nota_tv = None
    if fcff_tv <= 0:
        fcff_tv = 0.0
        nota_tv = (
            f"FCFF final del horizonte es no positivo ({fcff_series[-1]:,.1f}); "
            "TV Gordon = 0 porque no se proporcionó un NOPAT terminal normalizado. "
            "Revise el horizonte, la recuperación operativa y la reinversión antes de usar el resultado."
        )

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
        spread = ronic_spread_sesion(wacc) if ronic_spread is None else float(ronic_spread)
        ronic = wacc + spread
        nopat_n1 = float(nopat_final) * (1 + g_use)
        if nopat_n1 > 0 and ronic > 0:
            reinv_term = min(max(g_use / ronic, 0.0), 0.95)
            tv_gordon = nopat_n1 * (1 - reinv_term) / (wacc - g_use)
            # Si el último FCFF era negativo pero hay NOPAT terminal normalizado positivo,
            # el DCF sí calcula TV; no conservar la advertencia antigua que decía TV = 0.
            nota_tv = "TV normalizado por valor-conductor (NOPAT terminal y reinversión coherentes con g/RONIC)."
        else:
            tv_gordon = 0.0
            reinv_term = 0.0
            nota_tv = "NOPAT terminal no positivo o no válido: TV = 0 (no se perpetúan pérdidas)."
        tv_metodo = "normalizado (valor-conductor)"
    pv_tv_gordon = tv_gordon * df_tv
    ev_gordon = pv_fcff + pv_tv_gordon

    # Terminal por múltiplo de salida
    tv_exit = None
    pv_tv_exit = None
    ev_exit = None
    if ebitda_salida is not None and float(exit_multiple) > 0:
        tv_exit = float(ebitda_salida) * float(exit_multiple)
        # El múltiplo EV/EBITDA es un precio de mercado observado al CIERRE del año N:
        # se descuenta N años completos aunque los flujos usen mitad de año
        # (descontarlo N−0,5 sobrevaloraba el escenario de salida ≈ ½·WACC).
        pv_tv_exit = tv_exit * (1 + wacc) ** -n
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
    # WACC muy cerca de g: el valor terminal 1/(WACC − g) se vuelve muy sensible (±0,5 pp mueven el TV >25 %).
    _brecha = float(wacc) - float(g_use)
    if tv and _brecha < BRECHA_WACC_G_SENSIBLE:
        nota_tv = ((nota_tv + " ") if nota_tv else "") + (
            f"WACC − g = {_brecha * 100:.1f} pp: el valor terminal es muy sensible a ambos supuestos; revisa la tabla WACC × g.")
    mult_terminal = (tv / float(ebitda_salida)) if (ebitda_salida and float(ebitda_salida) > 0) else None
    bridge = {
        "Enterprise Value": ev,
        "(-) Deuda neta": -deuda_neta,
        "(-) Interés minoritario (NCI)": -nci,
        "(-) Otros claims": -otros_claims,
        "(+) Asociados / JV": asociados,
        "Equity atribuible": equity,
        # Diagnósticos del bridge para detectar desajustes de escala y deuda.
        # Se expresan en la misma unidad monetaria que FCFF/EV (normalmente miles de millones).
        "Claims netos descontados del EV": deuda_neta + nci + otros_claims - asociados,
        "EV mínimo para Equity = 0": deuda_neta + nci + otros_claims - asociados,
        "Equity / EV (%)": (equity / ev * 100 if ev else None),
        "Deuda neta / EV (%)": (deuda_neta / ev * 100 if ev else None),
        "FCFF usado en TV" + (" (normalizado N+1)" if reinv_term is not None else " (último año)"): (
            float(nopat_final) * (1 + g_use) * (1 - reinv_term) if reinv_term is not None else fcff_tv),
        "Reinversión terminal (% NOPAT)": (reinv_term * 100 if reinv_term is not None else 0.0),
        "RONIC terminal (%)": (ronic * 100 if ronic is not None else None),
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
    # Claves técnicas que ya se muestran en el encabezado (WACC, g) o son banderas internas.
    _OCULTAS = {"WACC", "g_terminal_usada", "deuda_es_bruta"}

    def _celda(k, v):
        if isinstance(v, bool):
            return "Sí" if v else "No"
        if v is None:
            return "—"
        if isinstance(v, (int, float)):
            return f"{v:,.1f} %" if "%" in str(k) else f"{v:,.1f}"
        return str(v)  # 'Nota TV' es texto

    mon_m = (moneda_modelo or (moneda_empresa(nombre_empresa) if nombre_empresa else None) or "COP").upper()
    mon_p = (moneda_precio or mon_m).upper()
    unidad = etiqueta_unidad(mon_m)

    def _fmt_px(x, mon):
        return f"{x:,.0f} {mon}" if mon == "COP" else f"{x:,.2f} {mon}"

    rows = "".join(
        f"<tr><td style='padding:6px 10px;color:#E8EEF7;border-bottom:1px solid #243044;text-align:left'>{k}</td>"
        + (f"<td style='padding:6px 10px;text-align:left;color:#CBD5E1;border-bottom:1px solid #243044'>{_celda(k, v)}</td></tr>"
           if isinstance(v, str) else
           f"<td style='padding:6px 10px;text-align:right;font-variant-numeric:tabular-nums;color:#E8EEF7;"
           f"border-bottom:1px solid #243044;white-space:nowrap'>{_celda(k, v)}</td></tr>")
        for k, v in b.items() if k not in _OCULTAS
    )
    vps = val.get("value_per_share")
    upside = val.get("upside_pct")
    precio = val.get("precio_mercado")
    vps_txt = _fmt_px(vps, mon_m) if vps is not None else "N/D (faltan acciones)"
    if upside is not None and precio is not None and mon_m != mon_p and val.get("fx_aplicado"):
        # ADR / emisor con EEFF en otra moneda: el upside SÍ es comparable porque el
        # precio se convirtió con la tasa spot (antes se mostraba «N/D» aunque existía).
        color = "#059669" if upside >= 0 else "#DC2626"
        px_mod = val.get("precio_moneda_modelo")
        up_txt = (
            f"<span style='color:{color};font-weight:700'>{upside:+.1f}%</span> "
            f"vs precio {_fmt_px(precio, mon_p)} ≈ {_fmt_px(px_mod, mon_m) if px_mod else 'N/D'} "
            f"(FX {val['fx_aplicado']:,.2f} COP/USD · {val.get('fuente_fx') or 'spot'})"
        )
    elif upside is not None and precio is not None:
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
                f"vs precio {_fmt_px(precio, mon_p)}"
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


def wacc_implicito_mercado(fcff_series, g, bridge_params, precio_objetivo, mid_year=True,
                           g_max_macro=0.05, nopat_final=None, lo=None, hi=0.40):
    """WACC que iguala el VPS del DCF al precio de mercado (DCF inverso).

    Mantiene FCFF, g, puente y número de acciones del caso base; solo resuelve la
    tasa. `precio_objetivo` debe estar YA en la moneda del modelo (tras FX). Sirve
    para contrastar el modelo con el mercado sin forzar el resultado: si el WACC
    implícito es muy inferior al WACC CAPM, el precio descuenta más crecimiento o
    menos riesgo que el caso base.

    Devuelve {"wacc": float | None, "motivo": str}. Sin solución en [lo, hi]:
    «precio_exige_mas_crecimiento» si aun con WACC = g + ~1 pp el VPS queda por
    debajo del precio, o «precio_bajo_aun_con_wacc_max» en el caso opuesto.
    """
    sin = {"wacc": None, "motivo": "sin_datos"}
    try:
        px = float(precio_objetivo)
        acc = float((bridge_params or {}).get("acciones") or 0)
        g = float(g)
    except (TypeError, ValueError):
        return sin
    if not (np.isfinite(px) and px > 0 and acc > 0 and np.isfinite(g)):
        return sin
    lo = max(g + 0.0105, 0.005) if lo is None else lo

    def _gap(w):
        v = valorar_con_bridge(fcff_series, w, g, bridge_params, mid_year=mid_year,
                               g_max_macro=g_max_macro, nopat_final=nopat_final)
        return float(v["Equity_Value"]) * 1000.0 / acc - px

    try:
        f_lo, f_hi = _gap(lo), _gap(hi)
        if not (np.isfinite(f_lo) and np.isfinite(f_hi)):
            return sin
        if f_lo < 0:
            return {"wacc": None, "motivo": "precio_exige_mas_crecimiento"}
        if f_hi > 0:
            return {"wacc": None, "motivo": "precio_bajo_aun_con_wacc_max"}
        return {"wacc": float(brentq(_gap, lo, hi, xtol=1e-6)), "motivo": "ok"}
    except (ValueError, RuntimeError, ZeroDivisionError):
        return sin


# ---------------------------------------------------------------------------
# Conciliación modelo vs mercado (DCF inverso + causa de la brecha, reglas deterministas)
# ---------------------------------------------------------------------------
CAUSAS_BRECHA = {
    "ALINEADO": ("alineado", "El valor del modelo y el precio difieren 10 % o menos"),
    "SUPUESTO_TASA": ("supuesto_modelo", "Una diferencia razonable en la tasa de descuento explica la brecha"),
    "MATERIA_PRIMA": ("expectativa_mercado", "El precio descuenta un precio de la materia prima distinto al del modelo"),
    "PRIMA_CALIDAD": ("prima_calidad", "El mercado acepta un rendimiento cercano a la tasa libre de riesgo por la calidad y estabilidad del negocio"),
    "LIMITACION_CRECIMIENTO": ("limitacion_modelo", "El precio exige un crecimiento que un DCF de este tipo no puede representar"),
    "LIMITACION_PARTICIPADAS": ("limitacion_modelo", "Buena parte del valor está en participadas que el modelo valora de forma simplificada"),
    "EXPECTATIVA_PESIMISTA": ("expectativa_mercado", "El mercado espera menos crecimiento o rentabilidad (o más riesgo) que el modelo"),
    "EXPECTATIVA_OPTIMISTA": ("expectativa_mercado", "El mercado espera más crecimiento o rentabilidad que el modelo"),
}
BRECHA_ALINEADO = 0.10          # |valor/precio − 1| ≤ 10 %
DELTA_WACC_RAZONABLE = 0.03     # ±300 pb de tasa se consideran discutibles, no un error
PRIMA_CALIDAD_ERP_RELATIVA = 0.40  # prima de mercado implícita < 40 % de la del modelo → prima por calidad
PARTICIPADAS_PESO_MIN = 0.25    # participadas ≥ 25 % del valor de la firma


def dcf_inverso(m):
    """Qué exige el precio de mercado, moviendo UNA palanca a la vez sobre la corrida de la pestaña 4.

    · WACC implícito (todo lo demás igual);
    · múltiplo de los flujos (k × FCFF y NOPAT terminal del modelo);
    · crecimiento anual de los flujos durante 10 años desde el FCFF del año 1, con Gordon al g terminal,
      comparado con el crecimiento que, con el mismo esquema, reproduce el valor del modelo.
    Devuelve None si faltan insumos o el precio no está en la moneda del modelo.
    """
    try:
        fc = [float(x) for x in (m.get("fcff_proy") or [])]
        bp = dict(m.get("bridge") or {})
        bp["acciones"] = m.get("acciones") or bp.get("acciones")
        w, g = float(m["wacc_calc"]), float(m.get("g_usada") if m.get("g_usada") is not None else m.get("g"))
        vps_m = float(m["vps_modelo"])
    except (KeyError, TypeError, ValueError):
        return None
    px = m.get("precio_mercado_moneda_modelo")
    if px is None and m.get("moneda") and m.get("moneda") == (m.get("moneda_precio") or m.get("moneda")):
        px = m.get("precio_mercado")
    try:
        px = float(px)
    except (TypeError, ValueError):
        return None
    if not fc or not bp.get("acciones") or px <= 0 or vps_m <= 0:
        return None
    sup = m.get("supuestos") or {}
    mid = bool(sup.get("mid_year", True))
    gmax = max(float(sup.get("g_max_macro") or 0.05), g)
    nop = m.get("nopat_final")

    def vps(serie, wacc, gg, nopat):
        v = valorar_con_bridge(list(serie), wacc, gg, bp, mid_year=mid, g_max_macro=gmax, nopat_final=nopat)
        return float(v["Equity_Value"]) * 1000.0 / float(bp["acciones"])

    def resolver(f, lo, hi):
        try:
            a, b = f(lo), f(hi)
            if not (np.isfinite(a) and np.isfinite(b)) or a * b > 0:
                return None
            return float(brentq(f, lo, hi, xtol=1e-6))
        except (ValueError, RuntimeError, ZeroDivisionError):
            return None

    out = {"precio": px, "vps_modelo": vps_m, "brecha": vps_m / px - 1.0, "wacc": w, "g": g}
    out["wacc_implicito"] = m.get("wacc_implicito_mercado")
    if out["wacc_implicito"] is None:
        out["wacc_implicito"] = resolver(lambda x: vps(fc, x, min(g, x - 0.0105), nop) - px, g + 0.0106, 0.40)
    out["k_flujos"] = resolver(lambda k: vps([f * k for f in fc], w, g, (float(nop) * k if nop else None)) - px, 0.05, 60.0)
    base = fc[0] if fc[0] > 0 else (float(nop) * 0.5 if nop and nop > 0 else 0.0)
    out["crec10_precio"] = out["crec10_modelo"] = None
    if base > 0:
        serie = lambda x: [base * (1 + x) ** t for t in range(10)]
        out["crec10_precio"] = resolver(lambda x: vps(serie(x), w, g, None) - px, -0.30, 1.50)
        out["crec10_modelo"] = resolver(lambda x: vps(serie(x), w, g, None) - vps_m, -0.30, 1.50)
    return out


def conciliacion_mercado(m):
    """Clasifica la brecha valor del modelo vs precio con reglas deterministas (lista cerrada CAUSAS_BRECHA).

    Devuelve {"causa", "tipo", "descripcion", "secundarias", "palancas", "supuesto_que_iguala", "inverso"}.
    El comité IA solo INTERPRETA este resultado: no elige la causa.
    """
    inv = dcf_inverso(m)
    if not inv:
        return None
    mon = str(m.get("moneda") or "").upper()
    merc = MERCADO_POR_MONEDA.get(mon, "DEFAULT")
    rf = float((m.get("supuestos") or {}).get("rf") or CAPM_POR_MERCADO.get(merc, CAPM_POR_MERCADO["DEFAULT"])["rf"])
    w, wi, k = inv["wacc"], inv.get("wacc_implicito"), inv.get("k_flujos")
    c_px, c_mod = inv.get("crec10_precio"), inv.get("crec10_modelo")
    g_hist = m.get("g_ingresos_historico")
    brecha = inv["brecha"]
    bajo_precio = brecha < 0          # el modelo vale menos que el precio

    # Prima de mercado IMPLÍCITA: del WACC implícito se despeja el Ke (con la deuda del modelo) y luego
    # ERP = (Ke − rf − CRP) / β apalancada. Compararla con la ERP del modelo evita juzgar contra rf, que
    # en pesos queda por encima de muchos WACC por el escudo fiscal de la deuda.
    sup = m.get("supuestos") or {}
    erp_impl = erp_mod = None
    try:
        de, t = float(m.get("de_ratio") or 0.0), float(sup["tax"])
        bl = float(sup["beta_u"]) * (1 + (1 - t) * de)
        erp_mod, crp = float(sup["erp"]), float(sup.get("crp") or 0.0)
        if wi is not None and bl > 0.05:
            ke_impl = (wi * (1 + de) - de * float(sup["kd"]) * (1 - t))
            erp_impl = (ke_impl - rf - crp) / bl
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        erp_impl = None
    if erp_impl is not None and erp_mod:
        tasa_ok = erp_impl >= PRIMA_CALIDAD_ERP_RELATIVA * erp_mod
        prima_calidad = erp_impl < PRIMA_CALIDAD_ERP_RELATIVA * erp_mod
    else:  # sin supuestos de CAPM: criterio simple contra la tasa libre de riesgo
        tasa_ok = wi is not None and wi >= rf + 0.02
        prima_calidad = wi is not None and wi < rf + 0.015

    # Palancas y su razonabilidad (umbrales explícitos, no juicio del LLM)
    pal = []
    if wi is not None:
        pal.append({"palanca": "WACC", "modelo": w, "exigido": wi,
                    "razonable": bool(tasa_ok and abs(wi - w) <= DELTA_WACC_RAZONABLE)})
    if k is not None:
        pal.append({"palanca": "Flujos (× modelo)", "modelo": 1.0, "exigido": k, "razonable": bool(0.75 <= k <= 1.35)})
    if c_px is not None and c_mod is not None:
        tope = max(c_mod + 0.04, (float(g_hist) if g_hist is not None else 0.0) + 0.03)
        pal.append({"palanca": "Crecimiento anual de flujos 10 años", "modelo": c_mod, "exigido": c_px,
                    "razonable": bool(c_px <= min(tope, 0.25))})

    # Peso de las participadas en el valor de la firma
    aso = float((m.get("bridge") or {}).get("asociados") or 0.0)
    ev = m.get("val_ev")
    peso_aso = aso / (float(ev) + aso) if (ev and float(ev) + aso > 0) else 0.0

    sec = []
    if m.get("emisor_ciclico"):
        sec.append("MATERIA_PRIMA")
    if peso_aso >= PARTICIPADAS_PESO_MIN and not m.get("participadas_valoradas"):
        sec.append("LIMITACION_PARTICIPADAS")
    if wi is not None and abs(wi - w) <= DELTA_WACC_RAZONABLE and tasa_ok:
        sec.append("SUPUESTO_TASA")

    if abs(brecha) <= BRECHA_ALINEADO:
        causa = "ALINEADO"
    elif bajo_precio and (m.get("fuera_de_dominio_crecimiento") or (k is not None and k > 4.0)
                          or (c_px is not None and c_px > 0.30)):
        causa = "LIMITACION_CRECIMIENTO"
    elif m.get("emisor_ciclico"):
        causa = "MATERIA_PRIMA"
    elif bajo_precio and peso_aso >= PARTICIPADAS_PESO_MIN and not m.get("participadas_valoradas"):
        causa = "LIMITACION_PARTICIPADAS"
    elif wi is not None and abs(wi - w) <= DELTA_WACC_RAZONABLE and tasa_ok:
        causa = "SUPUESTO_TASA"
    elif bajo_precio and wi is not None and prima_calidad:
        causa = "PRIMA_CALIDAD"
    else:
        causa = "EXPECTATIVA_OPTIMISTA" if bajo_precio else "EXPECTATIVA_PESIMISTA"
    sec = [x for x in dict.fromkeys(sec) if x != causa]
    bf = str(m.get("beta_fuente") or "")
    datos = []
    if "no informativa" in bf or "Yahoo sin beta" in bf or bf.startswith("proxy"):
        datos.append("beta sustituida o de mercado (la regresión de la acción no era utilizable)")
    if m.get("vetos_calidad"):
        datos.append("veto de calidad del modelo activo")
    if m.get("participadas_valoradas"):
        datos.append("participadas valoradas por suma de partes con supuestos del usuario")

    razonables = [p for p in pal if p["razonable"]]

    def _txt(p):
        if p["palanca"] == "WACC":
            return f"WACC de {p['exigido']:.2%} (modelo {p['modelo']:.2%}, {(p['exigido'] - p['modelo']) * 1e4:+,.0f} pb)"
        if p["palanca"].startswith("Flujos"):
            return f"flujos {p['exigido']:.2f} veces los del modelo"
        return f"crecimiento de los flujos de {p['exigido']:.1%} anual por 10 años (el modelo implica {p['modelo']:.1%})"

    iguala = (_txt(razonables[0]) + " — supuesto razonable") if razonables else (
        ("; ".join(_txt(p) for p in pal) + " — ninguno razonable por sí solo") if pal else "N/D")
    tipo, desc = CAUSAS_BRECHA[causa]
    return {"causa": causa, "tipo": tipo, "descripcion": desc, "secundarias": sec, "palancas": pal,
            "supuesto_que_iguala": iguala, "alguna_razonable": bool(razonables), "advertencias_datos": datos,
            "peso_participadas": round(peso_aso, 4), "rf": rf, "erp_implicita": erp_impl, "erp_modelo": erp_mod,
            "inverso": inv}


def _escalar_fcff(fcff, fac):
    """Escala escenarios sin perder el sentido: flujos positivos × fac; negativos × (2 − fac).
    (Con fac=0.75 un FCFF de −100 pasa a −125; antes pasaba a −75, es decir, 'mejoraba'.)"""
    f = np.asarray(fcff, dtype=float)
    return np.where(f >= 0, f * fac, f * (2.0 - fac))


def _nopat_final(df, fac=1.0):
    """NOPAT del último año (con el mismo escalamiento sensible al signo de los escenarios)."""
    return float(_escalar_fcff([float(df["NOPAT"].iloc[-1])], fac)[0])


# Escenarios por shocks de drivers: UNA sola definición para las pestañas 2, 4 y 7.
# g_ingresos es multiplicador de NIVEL de ingresos, no variación de crecimiento anual.
# CAPEX y Delta_NWC reciben shocks independientes; D&A conserva su senda base.
# Los factores son hipótesis ilustrativas y no deben presentarse como pronóstico oficial.
SHOCKS_ESCENARIOS = {
    "Pesimista": {"g_ingresos": 0.90, "margen_ebitda": 0.92, "capex_factor": 1.15, "nwc_factor": 1.10},
    "Base": {"g_ingresos": 1.00, "margen_ebitda": 1.00, "capex_factor": 1.00, "nwc_factor": 1.00},
    "Optimista": {"g_ingresos": 1.08, "margen_ebitda": 1.06, "capex_factor": 0.92, "nwc_factor": 0.95},
}
FACTOR_RESPALDO_ESCENARIO = {"Pesimista": 0.75, "Base": 1.0, "Optimista": 1.25}


def insumos_escenario(df_proj, nombre, tax=0.35):
    """(FCFF, NOPAT terminal, EBITDA de salida) del escenario por shocks de drivers; respaldo: escalar FCFF."""
    try:
        df_e = aplicar_shocks_drivers_proyeccion(df_proj, tax=tax, shock=SHOCKS_ESCENARIOS.get(nombre, {}))
        fc = [float(x) for x in df_e["FCFF"].values]
        nop = float(df_e["NOPAT"].iloc[-1]) if "NOPAT" in df_e.columns else None
        eb = float(df_e["EBITDA"].iloc[-1]) if "EBITDA" in df_e.columns else None
        if fc and all(np.isfinite(fc)):
            return fc, nop, eb
    except Exception:
        pass
    fac = FACTOR_RESPALDO_ESCENARIO.get(nombre, 1.0)
    eb = float(df_proj["EBITDA"].iloc[-1]) * fac if "EBITDA" in df_proj.columns else None
    return [float(x) for x in _escalar_fcff(df_proj["FCFF"].values, fac)], _nopat_final(df_proj, fac), eb


def aplicar_shocks_drivers_proyeccion(df_proj, tax=0.35, shock=None):
    """
    Escenario por drivers (no solo escalado de FCFF).
    Todos los shocks son multiplicadores de NIVEL/ratio, no cambios en tasas anuales:
      g_ingresos: multiplica el nivel de ingresos proyectado en todos los años;
      margen_ebitda: multiplica el margen EBITDA implícito;
      capex_factor: multiplica CAPEX;
      nwc_factor: multiplica Delta_NWC.
    Recalcula EBIT, NOPAT y FCFF. No interpreta g_ingresos como crecimiento anual
    ni recalcula automáticamente D&A/CAPEX/NWC a partir de ratios nuevos.
    """
    if df_proj is None or not hasattr(df_proj, "copy"):
        return df_proj
    shock = shock or {}
    d = df_proj.copy()
    ingresos_originales = (
        pd.to_numeric(d["Ingresos"], errors="coerce").astype(float).copy()
        if "Ingresos" in d.columns else None
    )
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

    ebitda_delta = pd.Series(0.0, index=d.index, dtype=float)
    if "EBITDA" in d.columns and "Ingresos" in d.columns:
        # Ajustar el margen EBITDA sin imponer EBIT = EBITDA - D&A.
        # Para shock base, EBITDA y EBIT quedan exactamente iguales al caso base;
        # para otros escenarios, el cambio de EBITDA se traslada incrementalmente al EBIT.
        ebitda_old = pd.to_numeric(d["EBITDA"], errors="coerce").fillna(0.0).astype(float)
        ing_base = pd.to_numeric(ingresos_originales, errors="coerce").replace(0, np.nan).astype(float)
        margen = (ebitda_old / ing_base).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        margen_nuevo = (margen * m_fac).clip(-0.5, 0.85)
        ebitda_nuevo = pd.to_numeric(d["Ingresos"], errors="coerce").fillna(0.0).astype(float) * margen_nuevo
        ebitda_delta = ebitda_nuevo - ebitda_old
        d["EBITDA"] = ebitda_nuevo

    if "CAPEX" in d.columns:
        d["CAPEX"] = pd.to_numeric(d["CAPEX"], errors="coerce").fillna(0.0) * cx_fac

    if "Delta_NWC" in d.columns:
        d["Delta_NWC"] = pd.to_numeric(d["Delta_NWC"], errors="coerce").fillna(0.0) * nwc_fac

    # Preservar el EBIT independiente de D&A y trasladar solo el shock incremental.
    # No reconstruir EBIT como EBITDA - D&A: la diferencia puede incluir impuestos
    # operativos y resultados de participadas según la definición reportada del emisor.
    if "EBIT" in d.columns:
        d["EBIT"] = pd.to_numeric(d["EBIT"], errors="coerce").fillna(0.0) + ebitda_delta

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


def auditar_consistencia_historica(df, tolerancia_abs=1.0):
    """Audita identidades contables básicas sin modificar datos de entrada.

    La tolerancia está en las unidades de la serie (p. ej. COP miles de millones).
    Retorna hallazgos por año para que el usuario concilie con EEFF y definiciones.
    No asume que diferencias pequeñas sean errores: puede haber reclasificaciones.
    """
    hallazgos = []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return [{"Prueba": "Serie histórica", "Estado": "ERROR", "Detalle": "No hay datos históricos para auditar."}]
    def _col(name):
        return name if name in df.columns else None
    # Solo evalúa identidades cuando todas las columnas necesarias existen.
    checks = [
        ("FCFF = NOPAT + Depreciación - CAPEX - ΔNWC", ["NOPAT", "Depreciacion", "CAPEX", "Delta_NWC", "FCFF"],
         lambda r: float(r["NOPAT"]) + float(r["Depreciacion"]) - float(r["CAPEX"]) - float(r["Delta_NWC"]) - float(r["FCFF"])),
        ("EBITDA ≈ EBIT + Depreciación", ["EBITDA", "EBIT", "Depreciacion"],
         lambda r: float(r["EBIT"]) + float(r["Depreciacion"]) - float(r["EBITDA"])),
    ]
    for label, cols, residual_fn in checks:
        if not all(_col(c) for c in cols):
            hallazgos.append({"Prueba": label, "Estado": "NO EVALUABLE", "Detalle": "Faltan columnas requeridas; no se infiere consistencia."})
            continue
        for idx, row in df.iterrows():
            try:
                vals = [float(row[c]) for c in cols]
                if not all(np.isfinite(v) for v in vals):
                    hallazgos.append({"Prueba": label, "Estado": "ERROR", "Detalle": f"Fila {idx}: contiene NaN/inf."})
                    continue
                residual = residual_fn(row)
                if abs(residual) > float(tolerancia_abs):
                    year = row.get("Año", row.get("Year", idx))
                    hallazgos.append({"Prueba": label, "Estado": "REVISAR", "Detalle": f"Año/fila {year}: residuo {residual:,.3f}; conciliar con estados financieros y definición de partidas."})
            except (TypeError, ValueError, KeyError):
                hallazgos.append({"Prueba": label, "Estado": "ERROR", "Detalle": f"Fila {idx}: no se pudo calcular la identidad."})
    if not hallazgos:
        hallazgos.append({"Prueba": "Identidades contables", "Estado": "OK", "Detalle": f"Identidades revisadas dentro de tolerancia absoluta {tolerancia_abs}."})
    return hallazgos


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
    try:
        try:
            valoracion_dcf([100.0], wacc=0.0, g=0.02)
            ok = False
            detail = "No rechazó WACC cero"
        except ValueError:
            ok = True
            detail = "WACC cero rechazado correctamente"
        results.append(("DCF rechaza WACC cero", ok, detail))
    except Exception as e:
        results.append(("DCF rechaza WACC cero", False, str(e)))
    try:
        val = valoracion_dcf([100.0, -10.0], wacc=0.10, g=0.02, mid_year=False)
        ok = abs(val["TV_Gordon"]) < 1e-12 and "TV Gordon = 0" in str(val.get("bridge", {}).get("Nota TV", ""))
        results.append(("DCF no extrapola FCFF positivo si el último es negativo", ok, f"TV={val['TV_Gordon']:.4f}"))
    except Exception as e:
        results.append(("DCF no extrapola FCFF positivo si el último es negativo", False, str(e)))
    try:
        calcular_wacc(-0.2, 0.08, 0.12, 0.25)
        ok = False
        detail = "No rechazó D/E negativo"
    except ValueError:
        ok = True
        detail = "D/E negativo rechazado correctamente"
    results.append(("WACC rechaza D/E negativo", ok, detail))
    try:
        moneda = monedas_alineadas_por_ticker(
            ticker="ISA.CL",
            nombre_empresa="ISA — Interconexión Eléctrica",
            emp={
                "ticker_yf": "ISA.CL", "ticker_bvc": "ISA",
                "fuente": "Yahoo Finance",
                "params": {"financialCurrency": "USD", "currency": "COP"},
            },
        )
        ok = moneda == ("USD", "COP")
        results.append(("Moneda contable USD y cotización BVC COP", ok, f"monedas={moneda}"))
    except Exception as e:
        results.append(("Moneda contable USD y cotización BVC COP", False, str(e)))
    try:
        val = valoracion_dcf(
            [100.0, -10.0], wacc=0.10, g=0.02, mid_year=False,
            nopat_final=100.0,
        )
        nota = str((val.get("bridge") or {}).get("Nota TV", ""))
        ok = val["TV_Gordon"] > 0 and "normalizado" in nota.lower() and "TV Gordon = 0" not in nota
        results.append(("TV normalizado no conserva advertencia FCFF negativa", ok, f"TV={val['TV_Gordon']:.2f}; nota={nota}"))
    except Exception as e:
        results.append(("TV normalizado no conserva advertencia FCFF negativa", False, str(e)))
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
    # La excepción de dos años aplica únicamente a la serie curada de Nutresa;
    # no modifica el control de integridad para archivos propios ni otras fuentes.
    serie_curada_corta = getattr(df_hist, "attrs", {}).get("serie_curada_corta") == "NUTRESA_2024_2025"
    minimo_observaciones = 2 if serie_curada_corta else 3
    df = df_hist.copy()
    df.index = df.index.map(lambda x: int(float(x)))
    df = df.sort_index()
    if "Ingresos" not in df.columns:
        return df, "Sin columna Ingresos."
    antes = list(df.index.astype(int))
    mask = df["Ingresos"].apply(lambda x: pd.notna(x) and abs(float(x)) > 1e-6)
    df = df.loc[mask]
    anio_actual = datetime.now().year
    # Un ejercicio fiscal ya cerrado (p. ej. NKE FY2026, cierre en mayo) puede llevar
    # el año en curso; solo se descarta lo que no esté marcado como cerrado.
    cerrado = getattr(df_hist, "attrs", {}).get("ejercicio_cerrado_hasta")
    limite = max(anio_actual, int(cerrado) + 1) if cerrado else anio_actual
    df = df.loc[df.index < limite]
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
    if len(df) < minimo_observaciones:
        raise ValueError(
            f"Tras limpiar años en cero quedan {len(df)} observaciones (mínimo {minimo_observaciones}). "
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
        for _ax in (ax0, ax1):  # años enteros en el eje (antes 2022.5)
            _ax.set_xticks(x)
            _ax.set_xticklabels([str(v) for v in x], fontsize=8)
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


GEMINI_MODELOS_PREFERIDOS = (
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
)  # gemini-2.5-flash se retiró para claves nuevas (HTTP 404, oct-2026)
GEMINI_TIMEOUT_SEG = 45
GEMINI_TIMEOUT_LARGO_SEG = 120    # búsqueda web o salida JSON larga (modelos con razonamiento tardan más)
GEMINI_PRESUPUESTO_SEG = 240


def fuentes_ultima_ia():
    """Fuentes web (título, URL) que Gemini citó en la última llamada con búsqueda (por sesión)."""
    return list(_almacen_estado().get("_ia_ultimas_fuentes") or [])


def _extraer_fuentes_grounding(cand):
    """groundingMetadata.groundingChunks[].web → [{'titulo','url'}] sin duplicados."""
    out, vistos = [], set()
    try:
        gm = cand.get("groundingMetadata") or {}
        for ch in gm.get("groundingChunks") or []:
            web = ch.get("web") or {}
            uri = str(web.get("uri") or "").strip()
            if uri and uri not in vistos:
                vistos.add(uri)
                out.append({"titulo": str(web.get("title") or uri)[:160], "url": uri})
        consultas = [str(q) for q in (gm.get("webSearchQueries") or [])][:6]
    except Exception:
        consultas = []
    return out, consultas


IA_MAX_PROMPT_CHARS = 30000   # antes 14.000: el dictamen v2 envía hechos + anclas + escenarios + pares


def _llamar_ia_redaccion(sistema, user_content, temperature=0.25, api_key=None, proveedor="auto",
                         buscar_web=False, esquema_json=None):
    """Llama a xAI, OpenAI o Google Gemini si hay API key (argumento o variable de entorno).
    Devuelve texto o None. El último error queda en _get_ia_error() (por sesión).

    buscar_web=True (solo Gemini): activa la herramienta google_search de la Gemini API
    para que el comité contraste la coyuntura con fuentes actuales. Las URLs citadas
    quedan en fuentes_ultima_ia(). Si el modelo no admite la herramienta (HTTP 400),
    se reintenta sin búsqueda y se informa en _almacen_estado()['_ia_busqueda_web'].

    esquema_json (dict, formato OpenAPI de Gemini): pide salida JSON validada por el
    proveedor (Gemini responseSchema; xAI/OpenAI response_format json_object). No se
    combina con la búsqueda web; si el modelo rechaza el esquema (HTTP 400) se reintenta
    sin él y la validación queda a cargo del código.
    """
    _almacen_estado()["_ia_ultimas_fuentes"] = []
    _almacen_estado()["_ia_busqueda_web"] = {"solicitada": bool(buscar_web), "usada": False, "consultas": []}
    _almacen_estado()["_ia_diagnostico"] = []   # un registro por intento (modelo, HTTP, finishReason, segundos)

    def _diag(**kw):
        try:
            _almacen_estado().setdefault("_ia_diagnostico", []).append(kw)
        except Exception:
            pass
    import os
    import json as _json
    import urllib.request
    import urllib.error
    import urllib.parse

    key_ui = (api_key or "").strip()
    key_xai = key_ui or (os.environ.get("XAI_API_KEY") or "").strip()
    key_oai = key_ui or (os.environ.get("OPENAI_API_KEY") or "").strip()
    # No usar claves embebidas: UI → variables de entorno.
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
            _set_ia_error(None)
            return None

    def _http_json(url, body_dict, headers, timeout=90):
        body = _json.dumps(body_dict).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read().decode("utf-8"))

    # ---------- Gemini (Google AI Studio) ----------
    if use == "gemini":
        key = key_gem
        if not key:
            _set_ia_error(
                "Proveedor gemini sin API key. Crea una gratis en "
                "https://aistudio.google.com/apikey y pégala en la app "
                "(o define GEMINI_API_KEY en st.secrets / variables de entorno)."
            )
            return None
        models = []
        env_m = (os.environ.get("GEMINI_MODEL") or "").strip()
        if env_m:
            models.append(env_m)
        # Familias vigentes en la Gemini API (oct-2026). Se prueban en orden: un 404
        # (modelo retirado/inexistente) o 429 (cuota por modelo) pasa al siguiente.
        # GEMINI_MODEL permite fijar uno concreto sin tocar el código.
        for m in GEMINI_MODELOS_PREFERIDOS:
            if m not in models:
                models.append(m)
        last_err = None
        errores_auth = []
        codigos_http = []
        t0 = _time.monotonic()
        for model in models:
            if _time.monotonic() - t0 > GEMINI_PRESUPUESTO_SEG:
                last_err = (last_err or "") + " · presupuesto de tiempo agotado."
                break
            # La clave viaja en cabecera (x-goog-api-key), nunca en la URL: las URLs
            # quedan en logs de proxies y trazas de excepciones.
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                + urllib.parse.quote(model, safe="")
                + ":generateContent"
            )
            body_dict = {
                "system_instruction": {"parts": [{"text": sistema}]},
                "contents": [
                    {"role": "user", "parts": [{"text": user_content[:IA_MAX_PROMPT_CHARS]}]}
                ],
                "generationConfig": {
                    "temperature": float(temperature),
                    # Con modelos de razonamiento los tokens de "pensamiento" cuentan en este tope:
                    # 8.192 truncaba el JSON del dictamen (finishReason MAX_TOKENS).
                    "maxOutputTokens": 32768 if (esquema_json or buscar_web) else 8192,
                },
            }
            usar_esquema = bool(esquema_json) and not buscar_web and \
                not _almacen_estado().get("_ia_esquema_no_soportado", {}).get(model)
            if usar_esquema:
                body_dict["generationConfig"]["responseMimeType"] = "application/json"
                body_dict["generationConfig"]["responseSchema"] = esquema_json
            usar_busqueda = bool(buscar_web) and not _almacen_estado().get("_ia_busqueda_no_soportada", {}).get(model)
            if usar_busqueda:
                body_dict["tools"] = [{"google_search": {}}]
            _t_ini = _time.monotonic()
            try:
                data = _http_json(
                    url,
                    body_dict,
                    headers={"Content-Type": "application/json", "x-goog-api-key": key},
                    timeout=GEMINI_TIMEOUT_LARGO_SEG if (esquema_json or buscar_web) else GEMINI_TIMEOUT_SEG,
                )
                cands = data.get("candidates") or []
                if not cands:
                    fb = data.get("promptFeedback") or data
                    last_err = f"Gemini sin candidatos (modelo={model}). Feedback: {str(fb)[:300]}"
                    _diag(modelo=model, http=200, finish=None, seg=round(_time.monotonic() - _t_ini, 1), error=last_err)
                    continue
                parts = (cands[0].get("content") or {}).get("parts") or []
                # Las partes de "pensamiento" (thought=True) no son la respuesta.
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")).strip()
                finish = cands[0].get("finishReason")
                _diag(modelo=model, http=200, finish=finish, seg=round(_time.monotonic() - _t_ini, 1),
                      busqueda=usar_busqueda, esquema=usar_esquema, chars=len(text))
                if text and finish == "MAX_TOKENS" and esquema_json:
                    # JSON truncado: no sirve; probar el siguiente modelo.
                    last_err = f"Gemini cortó la respuesta por límite de tokens (modelo={model})."
                    continue
                if text:
                    _set_ia_error(None)
                    _almacen_estado()["_ia_ultimo_modelo"] = model
                    if usar_busqueda:
                        fuentes, consultas = _extraer_fuentes_grounding(cands[0])
                        _almacen_estado()["_ia_ultimas_fuentes"] = fuentes
                        _almacen_estado()["_ia_busqueda_web"] = {
                            "solicitada": True, "usada": bool(fuentes or consultas), "consultas": consultas,
                        }
                    return text
                last_err = f"Gemini respuesta vacía (modelo={model}, finishReason={cands[0].get('finishReason')})."
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    detail = str(e)
                detail = detail.replace(key, "***") if key else detail
                last_err = f"HTTP {e.code} Gemini modelo={model}. Detalle: {detail}"
                codigos_http.append(e.code)
                _diag(modelo=model, http=e.code, finish=None, seg=round(_time.monotonic() - _t_ini, 1), error=detail[:300])
                if e.code == 400 and usar_esquema and "API_KEY" not in detail.upper():
                    _almacen_estado().setdefault("_ia_esquema_no_soportado", {})[model] = True
                    models.insert(models.index(model) + 1, model)
                    continue
                if e.code == 400 and usar_busqueda and "API_KEY" not in detail.upper():
                    # Modelo sin soporte de google_search: recordar y reintentar el MISMO modelo sin herramienta.
                    _almacen_estado().setdefault("_ia_busqueda_no_soportada", {})[model] = True
                    models.insert(models.index(model) + 1, model)
                    continue
                if "API_KEY_INVALID" in detail.upper() or (e.code == 400 and "API_KEY" in detail.upper()):
                    _set_ia_error(last_err + " — la API key no es válida.")
                    return None
                if e.code in (401, 403):
                    # Claves AQ. de AI Studio: Google indica que ACCESS_TOKEN_TYPE_UNSUPPORTED suele
                    # deberse a un modelo retirado; se prueban los demás antes de culpar a la clave.
                    errores_auth.append(model)
                    continue
                continue  # 404 modelo inexistente / 429 cuota / 5xx → siguiente modelo
            except Exception as e:  # noqa: PERF203
                last_err = f"Error Gemini ({type(e).__name__}): {e}"
                _diag(modelo=model, http=None, finish=None, seg=round(_time.monotonic() - _t_ini, 1), error=last_err[:300])
                # Un timeout en un modelo lento no debe impedir probar uno más rápido.
                if isinstance(e, (TimeoutError, OSError)) or "timed out" in str(e).lower():
                    continue
                break
        if codigos_http and all(c in (404, 429) for c in codigos_http) and 429 in codigos_http:
            # Cuota agotada (no un error del código ni de la clave): decirlo en claro. Con búsqueda web,
            # la herramienta google_search tiene su propia cuota, limitada en el plan gratuito.
            last_err = ("Cuota de Gemini agotada (HTTP 429) en todos los modelos"
                        + (" para la búsqueda web (google_search, con cuota propia y limitada en el plan gratuito). "
                           "El dictamen puede seguir sin hechos web." if buscar_web else
                           ". Espera a que se renueve o revisa el plan en https://ai.dev/rate-limit."))
        if errores_auth and len(errores_auth) == len({m for m in models}):
            last_err = (last_err or "") + (
                " — Gemini rechazó la autenticación en todos los modelos. Si tu clave empieza por «AQ.», "
                "crea una nueva en AI Studio (https://aistudio.google.com/apikey) y verifica que la Generative "
                "Language API esté habilitada en su proyecto.")
        _set_ia_error(last_err or "Gemini no respondió.")
        return None

    # ---------- xAI / OpenAI (OpenAI-compatible chat completions) ----------
    if use == "xai":
        key = key_xai if (key_ui or os.environ.get("XAI_API_KEY")) else key_ui
        key = (key or key_ui or "").strip()
        if not key:
            _set_ia_error(
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
            _set_ia_error(
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
                {"role": "user", "content": user_content[:IA_MAX_PROMPT_CHARS]},
            ],
        }
        if esquema_json:
            payloads.append({**base_msg, "temperature": temperature, "response_format": {"type": "json_object"}})
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
                    _set_ia_error(None)
                    return content
                last_err = f"Respuesta vacía del proveedor (modelo={model})."
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    detail = str(e)
                last_err = f"HTTP {e.code} al llamar {base} modelo={model}. Detalle: {detail}"
                if e.code in (401, 403):
                    _set_ia_error(last_err + " (clave inválida o sin permiso)")
                    return None
                if e.code == 429:
                    _set_ia_error(last_err + " (sin créditos o rate limit)")
                    return None
                if e.code == 400 and "response_format" in body_dict:
                    continue  # mismo modelo sin modo JSON
                if e.code in (400, 404):
                    break  # siguiente modelo
            except Exception as e:
                last_err = f"Error de red/API ({type(e).__name__}): {e}"
                break

    _set_ia_error(last_err or "No se pudo obtener respuesta de la IA.")
    return None

_set_ia_error(None)


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
    ia_err = _get_ia_error()

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
        err_ia = _get_ia_error()
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
        # Preferir la corrida de la pestaña 4 de ESTA empresa (supuestos del usuario).
        # El DCF rápido con parámetros de catálogo solo rellena lo que falte; así el
        # simulador, el portafolio y el comité muestran el mismo VPS/upside que tab 4.
        try:
            m4 = metricas_valoracion_sesion(nombre_empresa)
            if m4:
                for k, v in m4.items():
                    if v is not None:
                        out[k] = v
                out["origen_metricas"] = "pestaña 4 (sesión)"
                return out
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


def auditar_contexto_comite_ia(metricas):
    """Valida plausibilidad y consistencia del contexto antes de enviarlo al comité IA.

    No reemplaza auditoría contable ni verifica datos de mercado externamente.
    Devuelve errores bloqueantes, advertencias y estado de comparabilidad.
    """
    m = dict(metricas or {})
    errors, warnings = [], []

    def num(k):
        try:
            v = m.get(k)
            if v is None or isinstance(v, bool):
                return None
            v = float(v)
            return v if math.isfinite(v) else None
        except (TypeError, ValueError):
            return None

    required = ("precio_mercado", "vps_modelo", "wacc_calc", "val_ev", "val_equity")
    missing = [k for k in required if num(k) is None]
    if missing:
        errors.append("Faltan métricas financieras esenciales: " + ", ".join(missing))
    for k in ("precio_mercado", "vps_modelo"):
        v = num(k)
        if v is not None and v <= 0:
            warnings.append(f"{k} <= 0: no se interpreta como dato válido de mercado/valoración")
    for k in ("wacc_calc", "ke_calc"):
        v = num(k)
        if v is not None and not (0 < v < 1):
            errors.append(f"{k} debe expresarse como decimal entre 0 y 1; recibido {v}")
    de = num("de_ratio")
    if de is not None and de < 0:
        errors.append("de_ratio (D/E) no puede ser negativo")
    g = num("g")
    wacc = num("wacc_calc")
    if g is not None and not (-0.5 < g < 0.5):
        warnings.append("g fuera del rango de plausibilidad [-50%, 50%]")
    if g is not None and wacc is not None and g >= wacc:
        errors.append("g terminal debe ser menor que WACC")
    roic, ke = num("roic_calc"), num("ke_calc")
    if roic is not None and ke is not None and roic > 1:
        warnings.append("ROIC > 100%: confirmar escala/unidad")
    if roic is not None and wacc is not None and abs(roic-wacc) > 0.75:
        warnings.append("ROIC-WACC supera 75 pp: confirmar escala y periodo")
    currency = str(m.get("moneda") or "").strip().upper().replace("$", "").replace(" ", "")
    price_currency = str(m.get("moneda_precio") or currency).strip().upper().replace("$", "").replace(" ", "")
    unit_model = str(m.get("unidad_modelo") or "").strip().lower()
    unit_price = str(m.get("unidad_precio") or "por acción").strip().lower()
    if not currency or not price_currency:
        warnings.append("Moneda del modelo/cotización no identificada")
    elif currency != price_currency and not m.get("fx_aplicado"):
        warnings.append("Moneda del modelo y cotización distintas sin FX aplicado")
    if not unit_model:
        warnings.append("Escala/unidad monetaria del EV y Equity no documentada")
    if unit_price not in ("por acción", "por accion", "acción", "accion", "share"):
        warnings.append("Unidad del precio por acción no reconocida")
    price, vps = num("precio_mercado"), num("vps_modelo")
    if m.get("fx_aplicado") and num("precio_mercado_moneda_modelo") is not None:
        price = num("precio_mercado_moneda_modelo")  # mismo numerario que el VPS
    upside_calc = None
    monedas_comparables = bool(currency and price_currency and currency == price_currency) or bool(m.get("fx_aplicado"))
    if price is not None and vps is not None and price > 0 and vps > 0 and monedas_comparables:
        ratio = vps / price
        if ratio < 0.01 or ratio > 100:
            errors.append(
                "Comparabilidad bloqueada: la relación VPS/precio de mercado está fuera del rango "
                "1/100–100x. Verifica unidades, moneda, número de acciones y puente EV-Equity "
                "antes de emitir una recomendación de inversión."
            )
        upside_calc = 100.0 * (vps-price)/price
        given = num("upside")
        if given is not None and abs(given-upside_calc) > 0.5:
            warnings.append(f"Upside informado ({given:.2f}%) no coincide con recálculo ({upside_calc:.2f}%)")
    else:
        warnings.append("Upside no calculable: precio mercado/VPS faltante o no positivo")
    if not m.get("fuente_precio") or not m.get("fecha_precio"):
        warnings.append("Precio de mercado sin fuente y/o fecha de corte explícitas")
    if not m.get("fuente_valoracion"):
        warnings.append("No se identifica fuente/version del cálculo de valoración")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "upside_recalculado": upside_calc, "missing": missing}


def auditar_respuesta_comite_ia(respuesta, metricas=None):
    """Audita estructura, eco del prompt y contradicciones financieras detectables."""
    import re
    raw = _html_a_texto(respuesta, max_len=20000) if respuesta else ""
    # Algunos proveedores escapan los encabezados Markdown; normalizar antes de validar/renderizar.
    raw = re.sub(r"(?m)^\\+(?=#{1,6}\s)", "", raw)
    upper = raw.upper()
    errors, warnings = [], []
    m = dict(metricas or {})
    if not raw:
        errors.append("Respuesta vacía")
    if ("CONTEXTO DE ENTRADA" in upper or "INSTRUCCIONES Y FORMATO DE SALIDA" in upper
            or "FORMATO DE SALIDA (MARKDOWN" in upper or "NO LA CONTRADIGAS SIN CITAR" in upper
            or "REGLAS DE CALIDAD (LIBRO VERSIONADO)" in upper):
        errors.append("La IA devolvió/ecoó el prompt")
    if re.search(r"\[\s*\.\.\.\s*\]", raw):
        errors.append("La respuesta contiene marcadores de plantilla [ ... ] sin completar")
    # Si no hay ROIC verificable, no aceptar que el modelo lo presente como 0%.
    roic = m.get("roic_calc")
    roic_source = m.get("roic_fuente") or m.get("fuente_roic")
    roic_supported = bool(roic_source) or (
        m.get("nopat") is not None and m.get("capital_invertido") not in (None, 0)
    )
    if (roic is None or (isinstance(roic, (int, float)) and abs(float(roic)) < 1e-12 and not roic_supported)):
        if re.search(r"\bROIC\b.{0,80}\b0(?:[.,]0+)?\s*%", upper):
            errors.append("La respuesta presenta ROIC 0% sin respaldo verificable; debe indicar N/D")
    price, vps = m.get("precio_mercado"), m.get("vps_modelo")
    try:
        price, vps = float(price), float(vps)
        extreme_gap = price > 0 and vps > 0 and (vps / price < 0.01 or vps / price > 100)
    except (TypeError, ValueError):
        extreme_gap = False
    if extreme_gap and re.search(r"(CLARO\s+ERROR\s+DE\s+ESCALA|ERROR\s+DE\s+ESCALA|BRECHA\s+NOMINAL\s+ABSURDA|SE\s+DEBE\s+A\s+UN\s+ERROR\s+DE\s+ESCALA)", upper):
        errors.append("La respuesta atribuye la discrepancia a un error de escala sin evidencia; solo puede indicarla como hipótesis por verificar")
    # Formato vigente (análisis interno / contexto / recomendación / riesgos y catalizadores);
    # se acepta el formato anterior (deliberación / brecha / decisión / factores) por compatibilidad.
    formato_nuevo = "ANÁLISIS INTERNO" in upper or "CONTEXTO DE MERCADO" in upper
    secciones = (("ANÁLISIS INTERNO", "CONTEXTO DE MERCADO", "RECOMENDACIÓN DE INVERSIÓN", "RIESGOS")
                 if formato_nuevo else ("DELIBERACIÓN", "ANÁLISIS DE BRECHA", "DECISIÓN FINAL", "FACTORES CRÍTICOS"))
    for section in secciones:
        if section not in upper:
            warnings.append(f"Falta sección: {section}")
    if formato_nuevo and "CATALIZADOR" not in upper:
        warnings.append("No se identificaron catalizadores")
    rec = re.search(
        r"RECOMENDACI[ÓO]N\s+FINAL\s*[:：\-]*\s*\**\s*(COMPRAR|MANTENER|VENDER|INVERTIR\s+CONDICIONALMENTE|NO\s+INVERTIR|INVERTIR)\b",
        upper,
    )
    if not rec:
        warnings.append("No se identificó recomendación final dentro del vocabulario permitido")
    # Equivalencias para las reglas de coherencia con el motor.
    _equiv = {"COMPRAR": "INVERTIR", "VENDER": "NO INVERTIR", "MANTENER": "INVERTIR CONDICIONALMENTE"}
    # La respuesta debe respetar el estado de calidad y explicar divergencias materiales.
    vetos = m.get("vetos_calidad") or []
    veto_activo = bool(m.get("control_calidad_modelo") or vetos)
    decision_motor = str(m.get("decision_modelo") or "").upper()
    rec_raw = re.sub(r"\s+", " ", rec.group(1)).strip() if rec else None
    rec_norm = _equiv.get(rec_raw, rec_raw) if rec else None
    if veto_activo:
        # Con veto: MANTENER/VENDER se admiten (no implican compra); COMPRAR/INVERTIR/condicional no.
        if rec_raw in ("COMPRAR", "INVERTIR", "INVERTIR CONDICIONALMENTE"):
            errors.append("La IA recomienda invertir pese a un veto de calidad activo; debe pausarse la recomendación hasta recalibrar el modelo")
        if "VETO DE CALIDAD" not in upper and "RECALIBRAR" not in upper:
            errors.append("La respuesta omite el veto de calidad del modelo y la necesidad de recalibración")
    elif rec:
        recomendacion = rec_norm
        favorable_motor = ("FAVORABLE" in decision_motor or "POSITIVO" in decision_motor)
        prudente_motor = ("EVITAR" in decision_motor or "NEUTRAL" in decision_motor or "MONITOREAR" in decision_motor)
        # La recomendación condicional puede ser una cautela compatible con el motor prudente.
        # Solo exigir divergencia cuando la recomendación contradice directamente la señal.
        diverge = (recomendacion == "INVERTIR" and prudente_motor) or (recomendacion == "NO INVERTIR" and favorable_motor)
        if diverge and "DIVERGENCIA FRENTE AL MOTOR CUANTITATIVO" not in upper:
            errors.append("La recomendación difiere del motor cuantitativo sin declarar y justificar la divergencia")
    score = re.search(r"PUNTAJE(?:\s+DE\s+(?:VIABILIDAD|CONVICCI[ÓO]N))?\s*[:：-]*\s*\**\s*(\d+(?:[.,]\d+)?)\s*(?:/\s*10)?", upper)
    if score:
        try:
            val = float(score.group(1).replace(",", "."))
            if not 1 <= val <= 10:
                errors.append(f"Puntaje fuera de escala 1–10: {val}")
        except Exception:
            warnings.append("Puntaje no interpretable")
    else:
        warnings.append("No se identificó puntaje de viabilidad")
    po = re.search(r"PRECIO\s+OBJETIVO[^:\n]*[:：]\s*\**\s*\$?\s*([0-9][0-9.,]*)", upper)
    try:
        px_ref = float(m.get("precio_mercado")) if m.get("precio_mercado") is not None else None
    except (TypeError, ValueError):
        px_ref = None
    if po and px_ref and px_ref > 0:
        po_val = _numero_texto_es_en(po.group(1))
        if po_val is not None and not (px_ref / 5.0 <= po_val <= px_ref * 5.0):
            warnings.append(f"Precio objetivo {po_val:,.2f} fuera de 0,2×–5× del precio de mercado: verificar moneda/escala")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "texto": raw}


def _numero_texto_es_en(txt):
    """'29.000' / '29,000.5' / '29.000,5' / '343.91' → float (None si no es interpretable)."""
    t = str(txt or "").strip().rstrip(".,")
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "." in t:
        partes = t.split(".")
        if len(partes) > 2 or (len(partes) == 2 and len(partes[1]) == 3):
            t = t.replace(".", "")  # separador de miles es-CO
    elif "," in t:
        partes = t.split(",")
        t = t.replace(",", "") if (len(partes) > 2 or len(partes[1]) == 3) else t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


_CACHE_SNAPSHOT_IA = {}


def contexto_mercado_comite(nombre_empresa, metricas=None, ttl_seg=900):
    """Instantánea VERIFICADA de mercado y macro para el comité IA (sin texto libre de la IA).

    Combina: (1) cotización/fecha de la instantánea única de la app; (2) datos Yahoo del
    emisor (rango 52 semanas, P/E, EV/EBITDA, β, consenso de analistas, titulares);
    (3) anclas macro versionadas en el código (UST10, TES 10a, CDS, inflación implícita);
    (4) múltiplos implícitos del propio modelo frente al precio (EV de mercado con el
    mismo puente que usa el DCF). Todo lo que falta queda en None → «N/D» en el prompt.
    """
    m = dict(metricas or {})
    tk = m.get("ticker") or (ticker_yf_empresa(nombre_empresa) if nombre_empresa else None)
    clave = (str(tk), int(_time.time() // max(int(ttl_seg), 60)))
    if clave in _CACHE_SNAPSHOT_IA:
        base = dict(_CACHE_SNAPSHOT_IA[clave])
    else:
        base = {"ticker": tk, "rango_52s": None, "pe": None, "pe_forward": None, "ev_ebitda_yahoo": None,
                "beta_yahoo": None, "objetivo_analistas": None, "objetivo_rango": None,
                "recomendacion_analistas": None, "n_analistas": None, "rentabilidad_dividendo": None,
                "variacion_12m_pct": None, "titulares": [], "moneda_cotizacion": None}
        if tk and HAS_YF:
            try:
                t = yf.Ticker(str(tk))
                info = _yf_info_dict(t)
                base["moneda_cotizacion"] = info.get("currency")
                lo, hi = _finite_or_none(info.get("fiftyTwoWeekLow")), _finite_or_none(info.get("fiftyTwoWeekHigh"))
                try:
                    h = t.history(period="1y", auto_adjust=False)
                    if h is not None and len(h) > 5 and "Close" in h.columns:
                        cl = h["Close"].dropna()
                        lo = lo or float(cl.min())
                        hi = hi or float(cl.max())
                        if float(cl.iloc[0]) > 0:
                            base["variacion_12m_pct"] = (float(cl.iloc[-1]) / float(cl.iloc[0]) - 1) * 100
                except Exception:
                    pass
                base["rango_52s"] = (lo, hi) if (lo and hi) else None
                base["pe"] = _finite_or_none(info.get("trailingPE"))
                base["pe_forward"] = _finite_or_none(info.get("forwardPE"))
                base["ev_ebitda_yahoo"] = _finite_or_none(info.get("enterpriseToEbitda"))
                base["beta_yahoo"] = _finite_or_none(info.get("beta"))
                base["objetivo_analistas"] = _finite_or_none(info.get("targetMeanPrice"))
                tlo, thi = _finite_or_none(info.get("targetLowPrice")), _finite_or_none(info.get("targetHighPrice"))
                base["objetivo_rango"] = (tlo, thi) if (tlo and thi) else None
                base["recomendacion_analistas"] = info.get("recommendationKey")
                base["n_analistas"] = _finite_or_none(info.get("numberOfAnalystOpinions"))
                dy = _finite_or_none(info.get("dividendYield"))
                base["rentabilidad_dividendo"] = (dy * 100 if dy is not None and dy < 1 else dy)
                for n in (getattr(t, "news", None) or [])[:5]:
                    title = n.get("title") or ((n.get("content") or {}).get("title") if isinstance(n.get("content"), dict) else None)
                    if title:
                        base["titulares"].append(str(title)[:180])
            except Exception:
                pass
        _CACHE_SNAPSHOT_IA[clave] = dict(base)
        if len(_CACHE_SNAPSHOT_IA) > 256:
            _CACHE_SNAPSHOT_IA.pop(next(iter(_CACHE_SNAPSHOT_IA)))

    snap = instantanea_precio_mercado(nombre_empresa) if nombre_empresa else {}
    base.update({
        "precio": m.get("precio_mercado") if m.get("precio_mercado") is not None else snap.get("precio"),
        "fecha_precio": m.get("fecha_precio") or snap.get("fecha"),
        "fuente_precio": m.get("fuente_precio") or snap.get("fuente"),
    })
    # EV de mercado con el MISMO puente del DCF (moneda del modelo) y múltiplo implícito.
    try:
        acc = _finite_or_none(m.get("acciones"))
        px_mod = _finite_or_none(m.get("precio_mercado_moneda_modelo")) if m.get("fx_aplicado") else (
            _finite_or_none(m.get("precio_mercado")) if m.get("monedas_alineadas") else None)
        p = m.get("bridge") or (params_empresa(nombre_empresa) if nombre_empresa else {})
        if acc and px_mod:
            mcap = acc * px_mod / 1000.0  # millones de acciones × precio → miles de millones
            ev_mkt = mcap + float(p.get("deuda_neta") or 0) + float(p.get("nci") or 0) \
                + float(p.get("otros_claims") or 0) - float(p.get("asociados") or 0)
            base["capitalizacion_modelo"] = mcap
            base["ev_mercado"] = ev_mkt
            eb = _finite_or_none(m.get("ebitda_normalizado")) or _finite_or_none(m.get("ebitda_ultimo_hist"))
            if eb is None:
                df_h, _msg = cargar_y_limpiar_excel(None, nombre_empresa, True)
                if df_h is not None and "EBITDA" in df_h.columns:
                    eb = float(df_h["EBITDA"].iloc[-1])
            if eb and eb > 0:
                base["ebitda_ultimo"] = eb
                base["ev_ebitda_mercado"] = ev_mkt / eb
                if m.get("val_ev"):
                    base["ev_ebitda_modelo"] = float(m["val_ev"]) / eb
    except Exception:
        pass
    mac = m.get("macro") or {}
    base["macro"] = {
        "as_of": mac.get("capm_as_of") or CAPM_AS_OF,
        "ust10": mac.get("rf_us", CAPM_POR_MERCADO["US"]["rf"]),
        "tes10": mac.get("rf_co", CAPM_POR_MERCADO["CO"].get("rf_bruto", CAPM_POR_MERCADO["CO"]["rf"])),
        "cds_co": mac.get("cds_co", RIESGO_PAIS_CDS.get("CO")),
        "inflacion_lp_co": mac.get("inflacion_lp_co", INFLACION_LP.get("CO")),
        "inflacion_lp_us": mac.get("inflacion_lp_us", INFLACION_LP.get("US")),
        "damodaran_co": mac.get("damodaran_co") or damodaran_riesgo_pais("CO"),
        "damodaran_us": mac.get("damodaran_us") or damodaran_riesgo_pais("US"),
    }
    base["damodaran_multiplo"] = m.get("damodaran_multiplo")
    return base


def _texto_contexto_mercado(cm, mon_px=""):
    """Bloque de texto para el prompt (todo N/D si falta)."""
    def n(v, d=2, suf=""):
        try:
            return "N/D" if v is None else f"{float(v):,.{d}f}{suf}"
        except (TypeError, ValueError):
            return "N/D"
    mac = cm.get("macro") or {}
    rg = cm.get("rango_52s")
    ob = cm.get("objetivo_rango")
    lineas = [
        f"- Cotización: {n(cm.get('precio'))} {mon_px} · fecha {cm.get('fecha_precio') or 'N/D'} · fuente {cm.get('fuente_precio') or 'N/D'}",
        f"- Rango 52 semanas: {n(rg[0]) + ' – ' + n(rg[1]) if rg else 'N/D'} · variación 12 meses: {n(cm.get('variacion_12m_pct'), 1, ' %')}",
        f"- Múltiplos de mercado (Yahoo): P/E {n(cm.get('pe'), 1)} · P/E forward {n(cm.get('pe_forward'), 1)} · EV/EBITDA {n(cm.get('ev_ebitda_yahoo'), 1)} · β {n(cm.get('beta_yahoo'))} · dividendo {n(cm.get('rentabilidad_dividendo'), 2, ' %')}",
        f"- EV/EBITDA normalizado con el puente del modelo: mercado {n(cm.get('ev_ebitda_mercado'), 1, 'x')} vs modelo {n(cm.get('ev_ebitda_modelo'), 1, 'x')} (EBITDA normalizado {n(cm.get('ebitda_ultimo'), 1)})",
        f"- Consenso de analistas (Yahoo): objetivo medio {n(cm.get('objetivo_analistas'))} {mon_px} · rango {n(ob[0]) + ' – ' + n(ob[1]) if ob else 'N/D'} · recomendación {cm.get('recomendacion_analistas') or 'N/D'} · n={n(cm.get('n_analistas'), 0)}",
        f"- Macro ({mac.get('as_of', 'N/D')}): UST10 {n((mac.get('ust10') or 0) * 100 if mac.get('ust10') is not None else None, 2, ' %')} · TES 10a {n((mac.get('tes10') or 0) * 100 if mac.get('tes10') is not None else None, 2, ' %')} · CDS Colombia 5a {n((mac.get('cds_co') or 0) * 1e4 if mac.get('cds_co') is not None else None, 0, ' pb')} · inflación implícita LP CO {n((mac.get('inflacion_lp_co') or 0) * 100 if mac.get('inflacion_lp_co') is not None else None, 2, ' %')} / US {n((mac.get('inflacion_lp_us') or 0) * 100 if mac.get('inflacion_lp_us') is not None else None, 2, ' %')}",
    ]
    dco, dus, dm = mac.get("damodaran_co") or {}, mac.get("damodaran_us") or {}, cm.get("damodaran_multiplo") or {}
    if dco or dus:
        lineas.append(
            f"- Damodaran ({dco.get('fecha') or dus.get('fecha') or 'N/D'}): ERP EE. UU. {n((dus.get('erp_us') or 0) * 100 if dus.get('erp_us') else None, 2, ' %')}"
            f" · ERP madura {n((dco.get('erp_madura') or 0) * 100 if dco.get('erp_madura') else None, 2, ' %')}"
            f" · Colombia {dco.get('rating') or 'N/D'}: prima de riesgo país {n((dco.get('crp') or 0) * 100 if dco.get('crp') is not None else None, 2, ' %')}"
            f", ERP total {n((dco.get('erp_total') or 0) * 100 if dco.get('erp_total') is not None else None, 2, ' %')}")
    if dm:
        lineas.append(f"- EV/EBITDA de la industria (Damodaran, {dm.get('industria')}, {dm.get('region')}, {dm.get('fecha')}, "
                      f"{n(dm.get('n_firmas'), 0)} firmas): {n(dm.get('ev_ebitda_industria', dm.get('ev_ebitda')), 1, 'x')}"
                      + (f"; ajustado a Colombia (descuento BVC {dm['ajuste_pais']['descuento']:.0%}): {n(dm.get('ev_ebitda'), 1, 'x')}"
                         if dm.get("ajuste_pais") else ""))
    tit = cm.get("titulares") or []
    lineas.append("- Titulares recientes (Yahoo): " + (" | ".join(tit[:5]) if tit else "N/D"))
    return "\n".join(lineas)


VOCAB_RECOMENDACION = ("COMPRAR", "MANTENER", "VENDER")


def _reglas_calidad_ia_para_prompt():
    """Carga el libro de reglas versionado junto al código; usa un respaldo seguro si falta."""
    fallback = [
        "Los datos ausentes o inválidos son N/D, nunca cero por defecto.",
        "No inventar cotizaciones, comparables ni datos macroeconómicos.",
        "Si hay errores bloqueantes, no emitir recomendación ni puntaje.",
        "Distinguir datos observados, supuestos y estimaciones."
    ]
    try:
        ruta = Path(__file__).with_name("reglas_calidad_ia.json")
        data = json.loads(ruta.read_text(encoding="utf-8"))
        reglas = [
            str(item.get("regla")).strip()
            for item in data.get("reglas", [])
            if isinstance(item, dict) and item.get("regla")
        ]
        return "\n".join(f"- {regla}" for regla in reglas) if reglas else "\n".join(f"- {regla}" for regla in fallback)
    except Exception:
        return "\n".join(f"- {regla}" for regla in fallback)


def generar_recomendacion_comite_ia(nombre_empresa, api_key=None, proveedor="gemini", metricas=None,
                                    buscar_web=True, contexto_mercado=None, forzar=False):
    """Dictamen del comité de inversión con IA (pestaña 4). Devuelve HTML.

    Implementación en comite_ia.generar_dictamen (v2): hechos con fuente → dictamen JSON
    validado con anclas de precio objetivo calculadas por el modelo. El resultado
    estructurado completo queda en _almacen_estado()["comite_ia_ultimo"].
    """
    import comite_ia as _cia
    res = _cia.generar_dictamen(
        nombre_empresa, api_key=api_key, proveedor=proveedor, metricas=metricas,
        buscar_web=buscar_web, contexto_mercado=contexto_mercado, forzar=forzar,
    )
    _almacen_estado()["comite_ia_ultimo"] = res
    return res["html"]


def comite_historial(nombre_empresa=None):
    """Historial de dictámenes del comité IA en esta sesión (más reciente al final)."""
    import comite_ia as _cia
    return _cia.historial_comite(nombre_empresa)


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
                "metodo_key": metodo_key,
                "nopat_final": float(df_proj["NOPAT"].iloc[-1]) if "NOPAT" in df_proj.columns else None,
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
            df_proj.copy(),  # proyección cruda, sin redondeo, para cálculos conectados (pestaña 10)
        )
    except Exception as e:
        return (
            f"<div style='color:#EF4444'>Error: {e}<br><pre>{traceback.format_exc()}</pre></div>",
            None, None, None,
            None,
            "",
            None,
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
        _SHOCKS = SHOCKS_ESCENARIOS
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
            # g efectivamente usada (con el techo macro aplicado): el optimista mostraba 7 % aunque
            # el valor se calculaba con 6 %.
            escenarios[nombre]["g"] = float(val.get("g_used", g_e))
            escenarios[nombre]["g_solicitada"] = g_e
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
            lectura_escenario("Pesimista", p, 0.75, p["g"], wacc + 0.015, "#DC2626")
            + lectura_escenario("Base", b, 1.00, b["g"], wacc, "#1D4ED8")
            + lectura_escenario("Optimista", o, 1.25, o["g"], max(wacc - 0.01, 0.06), "#059669")
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
            _b2 = escenarios.get("Base") or {}
            guardar_resultado_tab("2", nombre_empresa, {
                "tabla_escenarios": _df_a_registros(df_esc, 6),
                "texto": _html_a_texto(resumen, 2200),
                "metricas": {
                    "val_ev": _finite_or_none(_b2.get("EV")),
                    "val_equity": _finite_or_none(_b2.get("Equity_Value")),
                    "vps_modelo": _finite_or_none(_b2.get("value_per_share")),
                    "upside": _finite_or_none(_b2.get("upside_pct")),
                    "precio_mercado": _finite_or_none(_b2.get("precio_mercado")),
                },
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
        if de_ratio < 0:
            pruebas.append(("❌ D/E inválido", f"D/E={de_ratio:.2f} no puede ser negativo."))
        elif de_ratio <= 1.5:
            pruebas.append(("ℹ️ D/E dentro de umbral orientativo", f"D/E={de_ratio:.2f}. El riesgo debe compararse con empresas del mismo sector, país y modelo de negocio; 1.5 no es un límite universal."))
        else:
            pruebas.append(("⚠️ D/E elevado frente al umbral orientativo", f"D/E={de_ratio:.2f}. Evaluar cobertura de intereses, vencimientos, volatilidad de caja y comparables sectoriales; no es una conclusión automática."))
        # La tasa libre de riesgo depende de moneda, plazo y fecha de valoración.
        # Evitar reglas fijas con cifras de mercado que envejecen y no aplican a USD.
        try:
            rf_f, erp_f, crp_f = float(rf), float(erp), float(crp or 0)
            if not all(np.isfinite(x) for x in (rf_f, erp_f, crp_f)) or min(rf_f, erp_f, crp_f) < 0:
                pruebas.append(("❌ Parámetros CAPM inválidos", "rf, ERP y CRP deben ser finitos y no negativos."))
            else:
                pruebas.append(("ℹ️ CAPM: validar fuente y fecha", f"rf={rf_f*100:.2f}%, ERP={erp_f*100:.2f}%, CRP={crp_f*100:.2f}%. Documentar moneda, plazo, fecha de corte y fuente; comprobar que CRP no esté duplicada en rf/ERP."))
        except Exception:
            pruebas.append(("❌ Parámetros CAPM inválidos", "No fue posible convertir rf, ERP y CRP a tasas numéricas."))
        # Auditoría de identidades contables de la serie histórica: no corrige los
        # datos; deja hallazgos explícitos para conciliación con los estados financieros.
        hallazgos_hist = auditar_consistencia_historica(df_hist)
        hallazgos_revisar = [h for h in hallazgos_hist if h.get("Estado") in ("REVISAR", "ERROR")]
        if hallazgos_revisar:
            pruebas.append(("⚠️ Conciliación histórica requerida",
                            f"Se detectaron {len(hallazgos_revisar)} diferencia(s) en identidades contables. "
                            + " | ".join(h["Detalle"] for h in hallazgos_revisar[:3])))
        else:
            pruebas.append(("ℹ️ Identidades históricas", "; ".join(h.get("Detalle", h.get("Estado", "")) for h in hallazgos_hist[:2])))

        explicacion = f"""
<div style="background:#151C2C;border-left:5px solid {COLOR_ACCENT};padding:18px 22px;border-radius:0 12px 12px 0">
<h3 style="color:{COLOR_PRIMARY};margin-top:0">Auditoría del modelo · {nombre_empresa}</h3>
<p><b>1. ¿El crecimiento es realista?</b><br>
g debe ser menor que WACC. Hoy: g=<b>{g*100:.2f}%</b> | WACC=<b>{wacc*100:.2f}%</b>. {"✅ Cumple." if g < wacc else "❌ No cumple."}</p>
<p><b>2. ¿La empresa crea valor?</b><br>
ROIC ≈ <b>{(f"{roic*100:.2f}%" if np.isfinite(roic) else "N/D")}</b> vs WACC <b>{wacc*100:.2f}%</b>. {("✅ Crea valor." if roic > wacc else "⚠️ No crea valor.") if np.isfinite(roic) else "ℹ️ Sin capital invertido en balance: no se concluye."}</p>
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
        df_proj, meta_proj = proyectar_variables_con_meta(df_hist, horizonte, tax=tax)
        df_proj = recalcular_fcff(df_proj.copy(), tax=tax, capex_extra=capex_extra)
        meta_proj = meta_proj or {}
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
        # Misma base de ROIC que las pestañas 3 y 7. Sin capital invertido en el
        # balance (frecuente en descargas Yahoo) el ROIC es N/D: antes calcular_roic
        # lanzaba una excepción y la pestaña 4 completa fallaba (caso XOM).
        try:
            roic = float(df_proj["NOPAT"].mean()) / capital_base_roic(capital_invertido, df_proj["NOPAT"].mean())
        except (TypeError, ValueError, ZeroDivisionError):
            roic = float("nan")
        roic_ok = bool(np.isfinite(roic))
        creacion = roic_ok and roic > wacc
        score, razones = 0, []
        if g < wacc:
            score += 2; razones.append("Crecimiento menor al costo del dinero (modelo estable)")
        else:
            score -= 3; razones.append("Crecimiento ≥ costo del dinero (modelo inestable)")
        if not roic_ok:
            razones.append("ROIC no disponible: falta capital invertido en el balance")
        elif creacion:
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
        _fc_p, _nop_p, _eb_p = insumos_escenario(df_proj, "Pesimista", tax=tax)  # mismo pesimista que la pestaña 2
        val_pes = valorar_con_bridge(_fc_p, wacc + 0.015, g_pes, bp, ebitda_salida=_eb_p, precio_mercado=precio_p, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nop_p)

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
            precio_mercado=(val_base.get("precio_moneda_modelo") if val_base.get("fx_aplicado") else precio_p),
            equity_por_accion=val_base.get("value_per_share"),
            moneda_modelo=mon_modelo, moneda_precio=(mon_modelo if val_base.get("fx_aplicado") else mon_precio),
        )
        decision, color, just = motor["decision"], motor["color"], motor["sesgo"]
        # Alertas de dominio del modelo (no cambian la decisión; informan al comité).
        _g_hist = meta_proj.get("g_ingresos_historico")
        if meta_proj.get("fuera_de_dominio_crecimiento"):
            _techo_txt = (f"tres etapas: consenso de analistas y convergencia desde máx. {CRECIMIENTO_MAX_ETAPA2:.0%} "
                          f"en {int(horizonte)} años" if meta_proj.get("tres_etapas")
                          else f"12 % con convergencia en {int(horizonte)} años")
            motor.setdefault("alertas", []).append(
                f"Crecimiento histórico de ingresos ≈ {_g_hist*100:.0f} %/año, muy por encima de lo que el motor "
                f"puede sostener ({_techo_txt}): el DCF base subestima por construcción a un emisor de "
                "hipercrecimiento. Úsalo como piso conservador y contrasta con un escenario explícito de crecimiento."
            )
        if meta_proj.get("ciclico"):
            motor.setdefault("alertas", []).append(
                "Emisor de materias primas: no se extrapola la tendencia de precios; ingresos y margen base del "
                + ("último año móvil (LTM)" if meta_proj.get("base_ltm") else "último ejercicio cerrado")
                + ", creciendo al nominal de largo plazo. El valor es muy sensible al precio de la materia prima."
            )
        try:
            _inf_lp = INFLACION_LP.get(mercado_empresa(nombre_empresa))
            # Tolerancia de 0,5 pp: g = 6,0 % frente a 6,15 % de inflación es crecimiento real ≈ 0, no contracción.
            if _inf_lp is not None and float(val_base.get("g_used", g)) < _inf_lp - 0.005:
                motor.setdefault("alertas", []).append(
                    f"g terminal nominal {float(val_base.get('g_used', g))*100:.2f}% < inflación de largo plazo de la moneda "
                    f"({_inf_lp*100:.2f}%): el valor terminal asume contracción REAL perpetua."
                )
        except Exception:
            pass
        _wp = wacc_paridad_usd(beta_u, de_ratio, tax, pais="CO") if str(mon_modelo or "").upper() == "COP" else None
        try:
            _dam = damodaran_empresa(nombre_empresa)
        except Exception:
            _dam = {"multiplo": None, "riesgo_pais": None, "vigencia": damodaran_vigencia()}
        if (_dam.get("vigencia") or {}).get("aviso"):
            motor.setdefault("alertas", []).append(_dam["vigencia"]["aviso"])
        for _av in tasas_vigencia():
            motor.setdefault("alertas", []).append("Tasa de mercado desactualizada: " + _av)

        _px_modelo = val_base.get("precio_moneda_modelo") if val_base.get("fx_aplicado") else (
            precio_p if (mon_modelo and mon_modelo == mon_precio) else None)
        _wi = wacc_implicito_mercado(
            df_proj["FCFF"].values, g, bp, _px_modelo, mid_year=bool(mid_year),
            g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_proj),
        ) if _px_modelo else {"wacc": None, "motivo": "sin_precio_comparable"}
        wacc_impl = _wi.get("wacc")
        _wi_txt = {
            "precio_exige_mas_crecimiento": "N/D: el precio exige más crecimiento que el caso base (aun con WACC ≈ g + 1 pp)",
            "precio_bajo_aun_con_wacc_max": "N/D: el precio queda por debajo del valor aun con WACC de 40 %",
            "sin_precio_comparable": "N/D: sin precio en la moneda del modelo",
        }.get(_wi.get("motivo"), "N/D")

        # Conciliación modelo vs mercado (DCF inverso + causa de la brecha por reglas): la lee el comité IA.
        _conc = None
        try:
            _conc = conciliacion_mercado({
                "fcff_proy": [float(x) for x in df_proj["FCFF"].values], "bridge": dict(bp),
                "acciones": val_base.get("acciones"), "wacc_calc": wacc, "g_usada": val_base.get("g_used", g), "g": g,
                "vps_modelo": val_base.get("value_per_share"), "precio_mercado": precio_p,
                "precio_mercado_moneda_modelo": val_base.get("precio_moneda_modelo"),
                "moneda": mon_modelo, "moneda_precio": mon_precio, "nopat_final": _nopat_final(df_proj),
                "supuestos": {"mid_year": bool(mid_year), "g_max_macro": float(g_max_macro), "rf": float(rf),
                              "erp": float(erp), "crp": float(crp), "kd": float(kd), "tax": float(tax),
                              "beta_u": float(beta_u)},
                "de_ratio": de_ratio,
                "wacc_implicito_mercado": wacc_impl, "g_ingresos_historico": meta_proj.get("g_ingresos_historico"),
                "emisor_ciclico": bool(meta_proj.get("ciclico")),
                "fuera_de_dominio_crecimiento": bool(meta_proj.get("fuera_de_dominio_crecimiento")),
                "val_ev": val_base.get("EV"), "beta_fuente": (params_empresa(nombre_empresa) or {}).get("beta_fuente"),
                "vetos_calidad": list(motor.get("vetos") or []),
                "participadas_valoradas": suma_partes_sesion(nombre_empresa) is not None,
            })
        except Exception:
            _conc = None
        _pal = {x["palanca"]: x for x in ((_conc or {}).get("palancas") or [])}
        _k = _pal.get("Flujos (× modelo)")
        _c10 = _pal.get("Crecimiento anual de flujos 10 años")

        kpis = pd.DataFrame({
            "Indicador": [
                "Decisión de comité (modelo)", "Score heurístico", "Calidad de datos",
                "Fuente financiera", "Fuente mercado", "Ke (CAPM)", "WACC", "ROIC",
                "ΔEV por CAPEX extra", "Equity base", "Equity pesimista", "MVA firma (EV − capital invertido)", "TIR implícita firma*",
                "WACC implícito en el precio (DCF inverso)",
                "Flujos que exige el precio (DCF inverso)",
                "Crecimiento de flujos a 10 años que exige el precio",
                "Causa principal de la brecha modelo vs mercado",
                "EBITDA normalizado (base de múltiplos)",
            ],
            "Valor": [
                decision, f"{score}/7", prov["nivel_calidad"], prov["fuente_financiera"], prov["fuente_mercado"],
                f"{ke*100:.2f}%", f"{wacc*100:.2f}%", (f"{roic*100:.2f}%" if roic_ok else "N/D"),
                f"{delta_ev:,.0f}", f"{val_base['Equity_Value']:,.0f}", f"{val_pes['Equity_Value']:,.0f}",
                f"{vpn_p:,.1f}" if vpn_p == vpn_p else "N/D",
                f"{tir_p*100:.2f}%" if (tir_p == tir_p) else "N/D",
                (f"{wacc_impl*100:.2f}% ({(wacc_impl - wacc)*1e4:+,.0f} pb vs WACC)" if wacc_impl is not None else _wi_txt),
                (f"{_k['exigido']:.2f} × los del modelo ({'razonable' if _k['razonable'] else 'exigente'})" if _k else "N/D"),
                (f"{_c10['exigido']:.1%} anual (el modelo implica {_c10['modelo']:.1%}; "
                 f"{'razonable' if _c10['razonable'] else 'exigente'})" if _c10 else "N/D"),
                (f"{_conc['descripcion']} ({_conc['causa']})" if _conc else "N/D"),
                (f"{meta_proj['ebitda_normalizado']:,.1f} · {meta_proj.get('ebitda_normalizado_metodo')}"
                 if meta_proj.get("ebitda_normalizado") else "N/D"),
            ],
        })

        # Tonos claros: la app es oscura y #991B1B/#065F46/#9A3412 eran casi ilegibles sobre #0B1220.
        vetos_html = "".join(f"<li style='color:#F87171'>{v}</li>" for v in motor["vetos"]) or "<li style='color:#34D399'>Ningún veto duro activo</li>"
        # Vetos del motor de decisión (sin bloque de contraste modelo vs mercado en esta pestaña).
        vetos_bloque = (
            "<b>Vetos de calidad del modelo (control interno · no son rating de la acción)</b>"
            f"<ul>{vetos_html}</ul>"
        )
        alertas_html = "".join(f"<li style='color:#FDBA74'>{a}</li>" for a in motor["alertas"]) or "<li>Sin alertas relevantes</li>"
        soportes_html = "".join(f"<li style='color:#6EE7B7'>{s}</li>" for s in motor["soportes"]) or "<li>Sin soportes destacados</li>"

        try:
            sens = matriz_sensibilidad_wacc_g(df_proj["FCFF"].values, deuda_neta, wacc, float(g), mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=_nopat_final(df_proj))
            sens_html = sens.to_html(index=False, na_rep="—")
            sens_html = sens_html.replace(
                '<table',
                '<table style="width:100%;border-collapse:collapse;font-size:12px;color:#E8EEF7;text-align:left"',
            )
            # Cifras alineadas a la derecha; la primera columna (WACC) es la etiqueta de fila.
            sens_html = sens_html.replace('<th>', '<th style="text-align:right;padding:8px 10px;background:#0F766E;color:#ECFDF5">')
            sens_html = sens_html.replace('<td>', '<td class="num" style="text-align:right;padding:6px 10px;border-bottom:1px solid #243044;font-variant-numeric:tabular-nums">')
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
<p style="margin:0;color:#FFFFFF !important">Horizonte {horizonte} años · WACC {wacc*100:.2f}% · g {float(val_base.get("g_used", g))*100:.2f}%{(f" (ingresado {float(g)*100:.2f}%, techo macro)" if abs(float(val_base.get("g_used", g)) - float(g)) > 1e-9 else "")} · ROIC {(f"{roic*100:.2f}%" if roic_ok else "N/D")}</p>
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
            _snap = instantanea_precio_mercado(nombre_empresa)
            guardar_resultado_tab("4", nombre_empresa, {
                "decision": _html_a_texto(decision_html, 1800),
                "kpis": _df_a_registros(kpis, 15) if kpis is not None else None,
                "memo": _html_a_texto(resumen, 2200),
                # Métricas numéricas canónicas (fuente única para comité IA,
                # simulador y portafolio; evita re-parsear tablas formateadas).
                "metricas": {
                    "empresa": nombre_empresa,
                    "ticker": ticker_canonico_empresa(nombre_empresa),
                    "moneda": mon_modelo,
                    "moneda_precio": mon_precio,
                    "monedas_alineadas": bool(mon_modelo and mon_precio and (mon_modelo == mon_precio or val_base.get("fx_aplicado"))),
                    "precio_mercado": _finite_or_none(precio_p),
                    "fx_aplicado": _finite_or_none(val_base.get("fx_aplicado")),
                    "fuente_fx": val_base.get("fuente_fx"),
                    "precio_mercado_moneda_modelo": _finite_or_none(val_base.get("precio_moneda_modelo")),
                    "vps_modelo": _finite_or_none(val_base.get("value_per_share")),
                    "upside": _finite_or_none(val_base.get("upside_pct")),
                    "acciones": _finite_or_none(val_base.get("acciones")),
                    "wacc_calc": _finite_or_none(wacc),
                    "wacc_implicito_mercado": _finite_or_none(wacc_impl),
                    "wacc_paridad_usd": _finite_or_none((_wp or {}).get("wacc_local_fisher")),
                    "wacc_paridad_fuente": (_wp or {}).get("fuente"),
                    "g_usada": _finite_or_none(val_base.get("g_used")),
                    "ronic_terminal": _finite_or_none(val_base.get("ronic")),
                    "ronic_modo": modo_ronic_sesion(),
                    "roic_observado": _finite_or_none(roic_referencia_sesion()),
                    "tv_pct_ev": _finite_or_none(val_base.get("tv_pct_ev")),
                    "ev_ebitda_salida_modelo": _finite_or_none(val_base.get("mult_terminal")),
                    "margen_ebitda_proy": _finite_or_none(meta_proj.get("margen_ebitda")),
                    "g_ingresos_historico": _finite_or_none(meta_proj.get("g_ingresos_historico")),
                    "g_ingresos_proy_inicial": _finite_or_none(meta_proj.get("g_ingresos")),
                    "emisor_ciclico": bool(meta_proj.get("ciclico")),
                    "fuera_de_dominio_crecimiento": bool(meta_proj.get("fuera_de_dominio_crecimiento")),
                    "macro": {
                        "capm_as_of": CAPM_AS_OF,
                        "rf_us": CAPM_POR_MERCADO["US"]["rf"], "rf_co": CAPM_POR_MERCADO["CO"].get("rf_bruto", CAPM_POR_MERCADO["CO"]["rf"]),
                        "erp": float(erp), "cds_co": RIESGO_PAIS_CDS.get("CO"),
                        "inflacion_lp_co": INFLACION_LP.get("CO"), "inflacion_lp_us": INFLACION_LP.get("US"),
                        "damodaran_co": damodaran_riesgo_pais("CO"),
                        "damodaran_us": damodaran_riesgo_pais("US"),
                    },
                    "damodaran_multiplo": _dam.get("multiplo"),
                    "damodaran_riesgo_pais": _dam.get("riesgo_pais"),
                    "ke_calc": _finite_or_none(ke),
                    "roic_calc": _finite_or_none(roic),
                    "roic_fuente": "NOPAT medio proyectado / capital invertido (pestaña 4)",
                    "de_ratio": _finite_or_none(de_ratio),
                    "g": _finite_or_none(g),
                    "val_ev": _finite_or_none(val_base.get("EV")),
                    "val_equity": _finite_or_none(val_base.get("Equity_Value")),
                    "equity_pesimista": _finite_or_none(val_pes.get("Equity_Value")),
                    "decision_modelo": decision,
                    "vetos_calidad": list(motor.get("vetos") or []),
                    "alertas_modelo": list(motor.get("alertas") or []),
                    "soportes_modelo": list(motor.get("soportes") or []),
                    "control_calidad_modelo": bool(motor.get("control_calidad_modelo")),
                    "nivel_calidad": prov.get("nivel_calidad"),
                    "fuente_financiera": prov.get("fuente_financiera"),
                    "fuente_mercado": prov.get("fuente_mercado"),
                    "unidad_modelo": f"miles de millones de {mon_modelo}",
                    "unidad_precio": "por acción",
                    "fuente_precio": _snap.get("fuente"),
                    "fecha_precio": _snap.get("fecha"),
                    "fuente_valoracion": "DCF FCFF · modelacion_logic.tab4_recomendacion · escenario base",
                    "supuestos": {
                        "horizonte": horizonte, "rf": float(rf), "erp": float(erp), "crp": float(crp),
                        "kd": float(kd), "tax": float(tax), "beta_u": float(beta_u),
                        "capex_extra": float(capex_extra), "mid_year": bool(mid_year),
                        "g_max_macro": float(g_max_macro),
                    },
                    # Insumos exactos de ESTA corrida (incluido un archivo propio del usuario) para
                    # que el comité calcule anclas de precio objetivo sin re-proyectar con otra fuente.
                    "fcff_proy": [float(x) for x in df_proj["FCFF"].values],
                    "nopat_final": _finite_or_none(_nopat_final(df_proj)),
                    "ebitda_salida": _finite_or_none(ebitda_out),
                    "ebitda_ultimo_hist": _finite_or_none(float(df_hist["EBITDA"].iloc[-1])) if (df_hist is not None and "EBITDA" in df_hist.columns and len(df_hist)) else None,
                    "ebitda_normalizado": _finite_or_none(meta_proj.get("ebitda_normalizado")),
                    "ebitda_normalizado_metodo": meta_proj.get("ebitda_normalizado_metodo"),
                    "tres_etapas": bool(meta_proj.get("tres_etapas")),
                    "consenso_ingresos": meta_proj.get("consenso_ingresos"),
                    "horizonte": int(horizonte),
                    "beta_industria_u": _finite_or_none((params_empresa(nombre_empresa) or {}).get("beta_industria_u")),
                    "beta_fuente": (params_empresa(nombre_empresa) or {}).get("beta_fuente"),
                    "conciliacion_mercado": _conc,
                    "participadas_valoradas": suma_partes_sesion(nombre_empresa) is not None,
                    "historico_corregido": historico_usuario(nombre_empresa) is not None,
                    "bridge": dict(bp),
                },
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
    # No inventar NOPAT ni capital invertido: si faltan datos, ROIC queda no disponible.
    tax = _safe_float(params.get("tax"))
    if len(hist) and "NOPAT" in hist.columns:
        nopat = _safe_float(hist["NOPAT"].iloc[-1])
    elif len(hist) and "EBIT" in hist.columns and tax is not None and 0 <= tax <= 1:
        ebit_last = _safe_float(hist["EBIT"].iloc[-1])
        nopat = ebit_last * (1.0 - tax) if ebit_last is not None else None
    else:
        nopat = None
    cap_inv = _safe_float(params.get("capital_invertido"))
    roic = (
        100.0 * nopat / cap_inv
        if nopat is not None and cap_inv is not None and cap_inv > 0
        else None
    )
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
            if ev_ebitda is not None:
                # Antes la etiqueta quedaba en «Estimado (sin ticker live)» aunque el múltiplo
                # viniera de Yahoo: la pestaña 6 y el comité lo trataban como estimado.
                fuente_mult = "Yahoo Finance (enterpriseToEbitda)"
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
        "ROIC (%)": round(roic, 1) if roic is not None else None,
        "WACC estimado (%)": round(wacc_pct, 2),
        "D/E": round(de, 2),
        "EV/EBITDA (x)": round(float(ev_ebitda), 2),
        "Crecimiento Ingresos 3a (%)": round(g3, 1),
        "FCFF (miles M)": round(fcff, 1),
        "Precio": round(precio, 0) if precio else None,
        "Fuente múltiplo": fuente_mult,
        "Sector": emp.get("sector", ""),
        # Moneda de las cifras: la tabla mezcla emisores en COP y USD (miles de millones de cada una).
        "Moneda": str(emp.get("moneda") or (emp.get("params") or {}).get("moneda") or ""),
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
        nonlocal n_live, n_fund
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
            ebitda_obs = _safe_float(info.get("ebitda"))
            rev_obs = _safe_float(info.get("totalRevenue"))
            ebitda = ebitda_obs if ebitda_obs is not None else 0.0
            rev = rev_obs if rev_obs is not None else 0.0
            margen = 100.0 * ebitda / rev if rev_obs not in (None, 0) and ebitda_obs is not None else None
            # No imputar un múltiplo sectorial ficticio cuando Yahoo no lo informa.
            ev_eb = _safe_float(info.get("enterpriseToEbitda"))
            if ev_eb is not None and (not np.isfinite(ev_eb) or ev_eb <= 0):
                ev_eb = None
            beta_obs = _safe_float(info.get("beta"))
            beta = beta_obs if beta_obs is not None else 1.0
            de_obs = _safe_float(info.get("debtToEquity"))
            de_ratio_obs = round(de_obs / 100.0, 2) if de_obs is not None and de_obs >= 0 else None
            de_ratio_model = de_ratio_obs if de_ratio_obs is not None else 0.5
            row = {
                "Empresa": short_p,
                "Nombre": disp,
                "Ingresos (miles M)": round(rev / 1e9, 2) if rev_obs is not None else None,
                "EBITDA (miles M)": round(ebitda / 1e9, 2) if ebitda_obs is not None else None,
                "Margen EBITDA (%)": round(margen, 1) if margen is not None else None,
                # Campos no observados permanecen N/D.
                "ROIC (%)": None,
                "WACC estimado (%)": None,
                "D/E": de_ratio_obs,
                "EV/EBITDA (x)": round(float(ev_eb), 2) if ev_eb is not None else None,
                "Crecimiento Ingresos 3a (%)": None,
                "FCFF (miles M)": None,
                "Fuente múltiplo": "Yahoo info (peer ligero)" if ev_eb is not None else "Yahoo info (múltiplo N/D)",
                "Sector": f"{sec}" + (f" / {ind}" if ind else ""),
            }
            seen_short.add(short_p)
            _fallbacks = []
            if de_ratio_obs is None:
                _fallbacks.append("D/E supuesto 0.5 solo para inicializar el modelo")
            if beta_obs is None:
                _fallbacks.append("beta supuesta 1.0 solo para inicializar el modelo")
            if ev_eb is None:
                _fallbacks.append("EV/EBITDA observado no disponible")
            notas[short_p] = f"Yahoo ligero · {etiqueta}" + (("; " + "; ".join(_fallbacks)) if _fallbacks else "")
            rows.append(row)
            n_fund += 1
            n_live += 1
            # Registrar mínimo en runtime para reutilizar
            EMPRESAS_RUNTIME[disp] = {
                "ticker_yf": str(ticker).upper(),
                "ticker_bvc": short_p,
                "sector": row["Sector"],
                "params": {"de_ratio": de_ratio_model, "kd": 0.06, "tax": 0.25, "g": 0.03, "beta_u": beta / max(1.0 + de_ratio_model * 0.65, 0.5),
                           "capital_invertido": max((row["Ingresos (miles M)"] or 0), 1) * 2, "deuda_neta": 0, "inversion_inicial": 0,
                           "caja": 0, "nci": 0, "otros_claims": 0, "asociados": 0, "acciones": 0, "exit_multiple": row["EV/EBITDA (x)"],
                           "moneda": info.get("currency") or "USD"},
                "historico": {"Año": [datetime.now().year - 1], "Ingresos": [row["Ingresos (miles M)"] or 0.0],
                              "EBITDA": [row["EBITDA (miles M)"] or 0.0], "EBIT": [(row["EBITDA (miles M)"] or 0.0) * 0.8],
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

    # --- 5) Solo mismo sector/familia ---
    fam_focal = _familia_sector(sector_focal_main or sector_focal, industry_focal)
    if len(rows) < 5:
        for nombre, emp in list(EMPRESAS.items()) + list(EMPRESAS_RUNTIME.items()):
            if nombre == nombre_empresa_focal:
                continue
            sec_e = emp.get("sector", "") or ""
            if fam_focal != "other" and _familia_sector(sec_e) != fam_focal:
                continue
            if fam_focal == "other":
                continue
            _add_emp(nombre, emp, f"mismo sector ({fam_focal})")
            if len(rows) >= 8:
                break

    # --- 6) Refuerzo peers auto del sector (sin otro oficio) ---
    if len(rows) < 3:
        for pt in (auto_peers or []):
            if len(rows) >= 6:
                break
            _add_ticker(pt, "peer auto-sector")

    if not rows:
        return (
            pd.DataFrame([]), {},
            f"Sin comparables del sector «{sector_focal or 'N/D'}» (familia {fam_focal}).",
        )

    df = pd.DataFrame(rows)
    # Los múltiplos faltantes se conservan como N/D: no se imputan como si fueran observados.
    if "EV/EBITDA (x)" in df.columns:
        df["EV/EBITDA (x)"] = pd.to_numeric(df["EV/EBITDA (x)"], errors="coerce")
        df.loc[
            ~np.isfinite(df["EV/EBITDA (x)"]) | (df["EV/EBITDA (x)"] <= 0),
            "EV/EBITDA (x)",
        ] = np.nan
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
        # Si todo el componente falta, usar score neutral (0.5), no cero ficticio.
        if not x.notna().any():
            return pd.Series(0.5, index=df.index)
        x = x.fillna(x.median())
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


def _html_referencia_damodaran(nombre_empresa, df=None):
    """Bloque de referencia: EV/EBITDA de la industria según Damodaran frente al del emisor y sus pares."""
    try:
        dm = damodaran_empresa(nombre_empresa).get("multiplo")
    except Exception:
        dm = None
    if not dm:
        return ""
    propio = mediana = None
    try:
        if df is not None and "EV/EBITDA (x)" in df.columns:
            focal = _nombre_corto(nombre_empresa).upper()
            fila = df[df["Empresa"].astype(str).str.upper() == focal]
            propio = float(fila["EV/EBITDA (x)"].iloc[0]) if len(fila) else None
            otros = df[df["Empresa"].astype(str).str.upper() != focal]["EV/EBITDA (x)"].astype(float)
            mediana = float(otros.median()) if len(otros) else None
    except Exception:
        pass
    aj = dm.get("ajuste_pais") or {}
    partes = [f"<b>{dm['ev_ebitda_industria']:.1f}x</b> para «{dm['industria']}» ({dm['region']}, {int(dm['n_firmas'] or 0)} firmas, "
              f"datos de {dm['fecha']})"]
    if aj:
        partes.append(f"ajustado a Colombia <b>{dm['ev_ebitda']:.1f}x</b> (la BVC paga {aj['mediana_local']:.1f}x frente a "
                      f"{aj['referencia_emergentes']:.1f}x del total emergente: descuento {aj['descuento']:.0%}, {aj['n']} emisores)")
    if propio:
        partes.append(f"el emisor cotiza a {propio:.1f}x")
    if mediana:
        partes.append(f"la mediana de la tabla es {mediana:.1f}x")
    return result_note(
        "Referencia de industria (Damodaran)",
        "EV/EBITDA agregado de la industria: " + "; ".join(partes) + ". Es una referencia anual de contraste, "
        "no un par directo: agrega muchos países y se actualiza en enero.",
    )


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
{_html_referencia_damodaran(nombre_empresa, df)}
{result_note("Fuentes de esta pestaña (ya no es solo tabla fija)", resumen_fuentes)}
<div class="section-card">
<b>Origen del múltiplo EV/EBITDA por empresa</b>
<ul>{notas_html}</ul>
</div>
"""
        # Tabla visible sin columna interna de fuente duplicada si se prefiere
        tabla = df.drop(columns=["Fuente múltiplo"], errors="ignore").copy()
        try:
            _focal = _nombre_corto(nombre_empresa).upper()
            try:
                _dm6 = damodaran_empresa(nombre_empresa).get("multiplo")
            except Exception:
                _dm6 = None
            guardar_resultado_tab("6", nombre_empresa, {
                "damodaran_multiplo": _dm6,
                "texto": _html_a_texto(html, 2000),
                "ranking": _df_a_registros(tabla, 12),
                # Múltiplos de pares con su procedencia: el comité solo usa los observados en mercado.
                "multiplos_pares": [
                    {"empresa": str(r.get("Nombre") or r.get("Empresa")),
                     "ev_ebitda": _finite_or_none(r.get("EV/EBITDA (x)")),
                     "fuente": str(r.get("Fuente múltiplo") or ""),
                     "moneda": str(r.get("Moneda") or ""),
                     "es_focal": str(r.get("Empresa") or "").upper() == _focal}
                    for _, r in df.iterrows()
                ],
            })
        except Exception:
            pass
        return html, tabla, fig
    except Exception as e:
        return f"<div style='color:#DC2626'>Error en comparación sectorial: {e}<pre>{traceback.format_exc()}</pre></div>", None, None



def _fmt_monto(v, dec=None):
    """Monto en miles de millones: sin decimales desde 1.000, uno desde 10, dos por debajo (USD pequeños)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "N/D"
    if not np.isfinite(x):
        return "N/D"
    if dec is None:
        dec = 0 if abs(x) >= 1000 else (1 if abs(x) >= 10 else 2)
    return f"{x:,.{dec}f}"


def _fmt_precio(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "N/D"
    return "N/D" if not np.isfinite(x) else (f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.2f}")


def _pct_txt(v, dec=2):
    try:
        x = float(v)
        return f"{x * 100:.{dec}f} %" if np.isfinite(x) else "N/D"
    except (TypeError, ValueError):
        return "N/D"


ESTADOS_DATO = {
    "OBSERVADO": "dato de una fuente identificable (validar fecha y definición)",
    "CURADO": "revisado o conciliado a mano (catálogo)",
    "ESTIMADO": "sustituto o regla del modelo: leer con su sensibilidad",
    "USUARIO": "escrito o cargado por el usuario",
    "FALTANTE": "no disponible: no se reemplaza por cero en silencio",
}


def _estado_por_fuente(fuente, por_defecto="OBSERVADO"):
    f = str(fuente or "").lower()
    if not f:
        return por_defecto
    if any(k in f for k in ("hoja parámetros", "usuario", "archivo", "excel")):
        return "USUARIO"
    if f.startswith("yahoo") or f.startswith("estados_financieros") or f == "sharesoutstanding":
        return "OBSERVADO"  # dato de Yahoo, aunque la fuente cite una referencia adicional
    if any(k in f for k in ("catálogo", "catalogo", "curad")):
        return "CURADO"
    if any(k in f for k in ("proxy", "bottom-up", "industria", "estatutaria", "default", "balance anual",
                            "regla", "spread", "inferid", "trimestres", "precio ×", "supuest")):
        return "ESTIMADO"
    return "OBSERVADO"


def calidad_variables(nombre_empresa, usados=None):
    """Estado de cada variable crítica de la valoración: OBSERVADO, CURADO, ESTIMADO, USUARIO o FALTANTE.

    `usados` son los valores que el modelo realmente aplicó (barra lateral): si difieren del dato de la
    fuente, la variable queda como USUARIO. Devuelve filas [variable, valor, estado, fuente].
    """
    u = dict(usados or {})
    p = params_empresa(nombre_empresa) or {}
    pa = parametros_archivo(nombre_empresa)
    est_f = estado_fuente_empresa(nombre_empresa) or {}
    filas = []

    def distinto(k, ref, tol=0.005):
        v = u.get(k)
        if v is None or ref is None:
            return False
        try:
            v, ref = float(v), float(ref)
        except (TypeError, ValueError):
            return False
        return abs(v - ref) > tol * max(abs(ref), 1e-9) + 1e-9

    def fila(nombre, k, valor_txt, fuente, por_defecto="OBSERVADO", faltante=False):
        if faltante:
            estado = "FALTANTE"
        elif k in pa:
            estado, fuente = "USUARIO", "hoja Parámetros del Excel"
        elif distinto(k, p.get(k)):
            estado, fuente = "USUARIO", f"escrito en la barra lateral (fuente: {fuente or 'N/D'})"
        else:
            estado = _estado_por_fuente(fuente, por_defecto)
        filas.append([nombre, valor_txt, estado, str(fuente or "N/D")])

    # Estados financieros
    origen = str(p.get("origen_params") or "")
    if historico_usuario(nombre_empresa):
        filas.append(["Estados financieros", "", "USUARIO", "histórico corregido con cifras oficiales"])
    elif origen == "excel_desde_cero" or pa:
        filas.append(["Estados financieros", "", "USUARIO", "Excel/CSV cargado"])
    elif est_f.get("fuente") == "yahoo":
        filas.append(["Estados financieros", "", "OBSERVADO", "Yahoo Finance (agregado, no auditado)"])
    elif est_f.get("fuente") == "curado":
        filas.append(["Estados financieros", "", "CURADO", "serie curada del catálogo"])
    elif est_f.get("fuente") == "sin_datos":
        filas.append(["Estados financieros", "", "FALTANTE", "sin serie: cargar estados financieros"])
    else:
        filas.append(["Estados financieros", "", "OBSERVADO", p.get("fuente") or "Yahoo Finance"])

    dn = u.get("deuda_neta", p.get("deuda_neta"))
    de = u.get("de_ratio", p.get("de_ratio"))
    fila("Deuda neta", "deuda_neta", _fmt_monto(dn), p.get("deuda_fuente") or "Yahoo Finance (totalDebt − totalCash)",
         faltante=(dn is not None and abs(float(dn)) < 1e-9 and float(de or 0) > 0.2))
    fila("Caja", "caja", _fmt_monto(u.get("caja", p.get("caja"))), p.get("caja_fuente") or "Yahoo Finance (totalCash)")
    acc = u.get("acciones", p.get("acciones"))
    fila("Acciones (millones)", "acciones", _fmt_monto(acc), p.get("acciones_fuente") or "N/D", faltante=not acc)
    _det = str(est_f.get("detalle") or "")
    _de_cat = "completado con catálogo" in _det.lower()

    def _fuente_puente(k):
        if p.get(f"{k}_fuente"):
            return p[f"{k}_fuente"]
        if _de_cat and k in _det:
            return "catálogo curado (Yahoo no lo reporta)"
        return "catálogo curado" if est_f.get("fuente") == "curado" else "Yahoo Finance (balance)"
    fila("Interés minoritario", "nci", _fmt_monto(u.get("nci", p.get("nci"))), _fuente_puente("nci"))
    sdp = suma_partes_sesion(nombre_empresa)
    if sdp:
        filas.append(["Asociadas", _fmt_monto(sdp.get("total")), "USUARIO", "suma de partes de las participadas"])
    else:
        fila("Asociadas", "asociados", _fmt_monto(u.get("asociados", p.get("asociados"))), _fuente_puente("asociados"))
    _bf = p.get("beta_fuente")
    if p.get("beta_brecha_industria") is not None:
        _bf = f"{_bf}; la industria difiere en {float(p['beta_brecha_industria']):+.2f}"
    fila("Beta sin deuda", "beta_u", f"{float(u.get('beta_u', p.get('beta_u')) or 0):.2f}", _bf)
    fila("Tasa de impuestos", "tax", _pct_txt(u.get("tax", p.get("tax")), 1), p.get("tax_fuente"))
    fila("Costo de la deuda (Kd)", "kd", _pct_txt(u.get("kd", p.get("kd"))), p.get("kd_fuente") or "regla: rf + spread")
    mon = str(p.get("moneda") or "").upper()
    tm = TASAS_MERCADO.get("co_rf_bruto" if mon == "COP" else "us_rf") or {}
    venc = [a for a in tasas_vigencia() if ("TES" in a if mon == "COP" else "Tesoro" in a)]
    filas.append(["Tasa libre de riesgo", _pct_txt(u.get("rf")), "USUARIO" if u.get("rf_editada") else "OBSERVADO",
                  f"{tm.get('fuente', 'N/D')} · {tm.get('fecha', '')}" + (" · desactualizada" if venc else "")])
    crp = float(u.get("crp") or 0)
    filas.append(["Primas ERP / CRP", f"{_pct_txt(u.get('erp'))} / {_pct_txt(crp)}",
                  "USUARIO" if u.get("erp_editada") else "OBSERVADO",
                  "Damodaran (NYU Stern)"
                  + (" · ponderada por ingresos: " + ", ".join(f"{k} {v:.0f}" for k, v in paises_operacion_sesion(nombre_empresa).items())
                     if paises_operacion_sesion(nombre_empresa) else " · país de la sede")
                  + (" · CRP con flujos en pesos: posible doble conteo" if mon == "COP" and crp > 0 else "")])
    px_ref = p.get("precio_referencia")
    snap = instantanea_precio_mercado(nombre_empresa) or {}
    if px_ref and not snap.get("precio"):
        filas.append(["Precio de la acción", _fmt_precio(px_ref), "USUARIO", "precio de la hoja Parámetros"])
    else:
        filas.append(["Precio de la acción", _fmt_precio(snap.get("precio")), "OBSERVADO" if snap.get("precio") else "FALTANTE",
                      f"{snap.get('fuente') or 'Yahoo Finance'} · {str(snap.get('fecha') or '')[:10]}"])
    for h in p.get("datos_completados") or []:
        filas.append(["Dato completado", "", "ESTIMADO", str(h)])
    return filas


def _datos_informe_v3(nombre_empresa, *, df_hist, df_proj, meta_proj, val_base, escenarios, wacc, ke, beta_l, rf, erp,
                      crp, kd, tax, de_ratio, we, wd, beta_u, g, horizonte, precio, bp, mon_modelo, mon_precio,
                      capital_invertido, prov, mensaje_datos, motor, mid_year, g_max_macro, vpn_firma, tir_firma,
                      nota_norm=False):
    """Contenido del informe v3: perfil, valor vs precio en ambas monedas, supuestos, puente, rango de valor,
    conciliación con el mercado, comité IA estructurado y fuentes. Todo de la misma corrida que la pestaña 4."""
    out = {"perfil": perfil_empresa(nombre_empresa)}
    mon = mon_modelo or ""
    mon_px = mon_precio or mon
    snap = instantanea_precio_mercado(nombre_empresa)
    vps = val_base.get("value_per_share")
    fx = val_base.get("fx_aplicado")
    out["valor"] = {
        "vps": vps, "mon_vps": mon, "precio": precio, "mon_precio": mon_px, "fx": fx,
        "precio_en_modelo": val_base.get("precio_moneda_modelo") if fx else None,
        "vps_en_precio": (float(vps) * float(fx) if (fx and vps is not None and mon_px == "COP" and mon == "USD") else
                          (float(vps) / float(fx) if (fx and vps is not None and mon_px == "USD" and mon == "COP") else None)),
        "upside": val_base.get("upside_pct"), "fecha_precio": snap.get("fecha"), "fuente_precio": snap.get("fuente"),
    }
    # Supuestos (construcción del WACC y del valor terminal)
    ronic = val_base.get("ronic")
    out["supuestos"] = [
        ["Tasa libre de riesgo (rf)", _pct_txt(rf), CAPM_POR_MERCADO.get(MERCADO_POR_MONEDA.get(mon, "DEFAULT"), {}).get("rf_fuente")
         or CAPM_POR_MERCADO.get(MERCADO_POR_MONEDA.get(mon, "DEFAULT"), {}).get("rf_bruto_fuente") or "Parámetros del modelo"],
        ["Prima de mercado (ERP)", _pct_txt(erp), (
            "ponderada por ingresos: " + ", ".join(f"{k} {v / sum(paises_operacion_sesion(nombre_empresa).values()):.0%}"
                                                 for k, v in paises_operacion_sesion(nombre_empresa).items()) + " (Damodaran)")
         if paises_operacion_sesion(nombre_empresa) else
         (CAPM_POR_MERCADO.get(MERCADO_POR_MONEDA.get(mon, "DEFAULT"), {}).get("erp_fuente") or "Parámetros del modelo")],
        ["Prima de riesgo país (CRP)", _pct_txt(crp), "Solo si los flujos están en moneda dura de un emisor emergente"],
        ["Beta sin deuda / con deuda", f"{float(beta_u):.2f} / {float(beta_l):.2f}", (params_empresa(nombre_empresa) or {}).get("beta_fuente") or "Parámetros del modelo"],
        ["Costo del patrimonio (Ke)", _pct_txt(ke), "rf + beta con deuda × ERP + CRP"],
        ["Costo de la deuda (Kd) antes / después de impuestos", f"{_pct_txt(kd)} / {_pct_txt(float(kd) * (1 - float(tax)))}",
         (params_empresa(nombre_empresa) or {}).get("kd_fuente") or "Parámetros del modelo"],
        ["Tasa de impuestos", _pct_txt(tax, 1), (params_empresa(nombre_empresa) or {}).get("tax_fuente") or "Parámetros del modelo"],
        ["Deuda / patrimonio (pesos)", f"{float(de_ratio):.2f} ({_pct_txt(we, 0)} patrimonio · {_pct_txt(wd, 0)} deuda)", "Valor de mercado"],
        ["WACC", _pct_txt(wacc), "Ke × peso del patrimonio + Kd × (1 − t) × peso de la deuda"],
        ["Crecimiento perpetuo (g)", _pct_txt(val_base.get("g_used", g)), f"Nominal en {mon}; techo {_pct_txt(g_max_macro, 1)} y WACC − 1 pp"],
        ["Rentabilidad de la reinversión futura (RONIC)", _pct_txt(ronic) if ronic is not None else "N/D",
         {"roic": "Converge al ROIC observado (piso: WACC)", "wacc": "Igual al WACC", "manual": "Manual"}.get(modo_ronic_sesion(), "")],
        ["Horizonte explícito", f"{int(horizonte)} años", "Descuento a mitad de año" if mid_year else "Descuento a fin de año"],
    ]
    est = (meta_proj or {}).get("estimador_ingresos") or ""

    def _fmt_palanca(f):
        v = f.get("valor")
        if v is None:
            return "no aplica"
        if f["palanca"] in ("g_ingresos", "margen_ebitda"):
            return _pct_txt(v, 1)
        if f["palanca"] == "anios_convergencia":
            return f"{int(v)} año(s)"
        return f"{float(v):.2f} ×"
    out["narrativa"] = [[f["nombre"], _fmt_palanca(f), "Usuario" if f.get("fuente") == "usuario" else "Modelo", f.get("frase") or ""]
                        for f in (meta_proj or {}).get("narrativa") or []]
    out["proyeccion"] = (
        f"Ingresos: {est or 'mediana robusta del histórico'}; crecimiento año 1 {_pct_txt((meta_proj or {}).get('g_ingresos'), 1)}. "
        f"Margen EBITDA objetivo {_pct_txt((meta_proj or {}).get('margen_ebitda_objetivo', (meta_proj or {}).get('margen_ebitda')), 1)}; "
        + (f"reinversión ligada al crecimiento (ventas/capital {float((meta_proj or {}).get('ventas_capital')):.2f}): cada año "
           "reinvierte lo que exige el crecimiento del siguiente. " if (meta_proj or {}).get("reinversion_ligada")
           else "CAPEX converge hacia el nivel de mantenimiento. ")
        + f"Valor terminal: {_pct_txt(val_base.get('tv_pct_ev'), 0)} del valor de la empresa."
        + (" Emisor de materias primas: precio de ciclo medio (base últimos doce meses)." if (meta_proj or {}).get("ciclico") else "")
    )
    b = val_base.get("bridge") or {}
    filas = []
    for k in ("Enterprise Value", "(-) Deuda neta", "(-) Deuda bruta", "(+) Caja y equivalentes",
              "(-) Interés minoritario (NCI)", "(-) Otros claims", "(+) Asociados / JV", "Equity atribuible"):
        if k in b and (k in ("Enterprise Value", "Equity atribuible") or abs(float(b[k] or 0)) > 1e-9):
            etiqueta = {"Enterprise Value": "Valor de la empresa (EV)", "(-) Deuda neta": "(−) Deuda neta",
                        "(-) Deuda bruta": "(−) Deuda bruta", "(+) Caja y equivalentes": "(+) Caja",
                        "(-) Interés minoritario (NCI)": "(−) Interés minoritario", "(-) Otros claims": "(−) Otros pasivos",
                        "(+) Asociados / JV": "(+) Asociadas y negocios conjuntos",
                        "Equity atribuible": "Patrimonio de los accionistas"}[k]
            filas.append([etiqueta, _fmt_monto(b[k])])
    acc = val_base.get("acciones") or bp.get("acciones")
    if acc:
        filas.append(["÷ Acciones (millones)", _fmt_monto(acc)])
    filas.append([f"Valor por acción ({mon})", _fmt_precio(vps)])
    out["puente"] = filas
    out["firma"] = {"mva": vpn_firma, "tir": tir_firma}
    out["escenarios_v3"] = [
        [k, _pct_txt(escenarios[k]["WACC"]), _pct_txt(escenarios[k]["g"]), _fmt_monto(escenarios[k]["EV"]),
         _fmt_monto(escenarios[k]["Equity_Value"]), _fmt_precio(escenarios[k].get("value_per_share"))]
        for k in ("Pesimista", "Base", "Optimista")]
    # Métricas de la pestaña 4 (misma corrida): conciliación y anclas
    m4 = metricas_valoracion_sesion(nombre_empresa) or {}
    out["conciliacion"] = m4.get("conciliacion_mercado")
    out["anclas"] = None
    if m4.get("vps_modelo") is not None:
        try:
            import comite_ia as _CI
            cm = contexto_mercado_comite(nombre_empresa, m4)
            anc = _CI.calcular_anclas(nombre_empresa, m4, cm)
            out["anclas"] = {"moneda": anc.get("moneda"), "rango": anc.get("rango"),
                             "filas": [[a["id"], a["nombre"], _fmt_precio(a.get("vps_precio")), a.get("metodo")] for a in anc.get("anclas") or []],
                             "descartadas": [[a["id"], a["nombre"], _fmt_precio(a.get("vps_precio")), a.get("motivo")] for a in anc.get("descartadas") or []],
                             "valores": {a["id"]: a.get("vps_precio") for a in anc.get("anclas") or []}}
        except Exception as e:
            out["anclas"] = {"error": str(e)[:200]}
    # Comité IA (dictamen estructurado v3) de esta empresa
    ci = (RESULTADOS_SESION.get("tabs") or {}).get("comite_ia") or {}
    if RESULTADOS_SESION.get("empresa") in (None, nombre_empresa) and isinstance(ci.get("dictamen"), dict):
        out["comite"] = ci["dictamen"]
    # Datos, fuentes y correcciones del usuario
    dv = damodaran_vigencia()
    tm = TASAS_MERCADO
    out["calidad"] = {"nivel": prov.get("nivel_calidad"), "fuente": prov.get("fuente_financiera"), "mercado": prov.get("fuente_mercado")}
    hu, sdp = historico_usuario(nombre_empresa), suma_partes_sesion(nombre_empresa)
    out["ajustes"] = []
    if hu:
        out["ajustes"].append("Histórico corregido por el usuario: " + ("; ".join(hu.get("cambios") or []) or "sin celdas distintas"))
    if sdp:
        out["ajustes"].append(f"Participadas por suma de partes: {_fmt_monto(sdp['total'])} ({len(sdp.get('detalle') or [])} participadas, Ke {_pct_txt(sdp.get('ke'))})")
    anios = [int(x) for x in df_hist.index] if df_hist is not None and len(df_hist) else []
    out["fuentes"] = [
        ["Estados financieros", (out["perfil"].get("fuente") or "") + (f" · {anios[0]}–{anios[-1]}" if anios else ""), "Último ejercicio cerrado"],
        ["Precio de la acción", ("Yahoo Finance (" + str(out["valor"]["fuente_precio"]).split(":", 1)[-1] + ")")
         if str(out["valor"].get("fuente_precio") or "").lower().startswith("yahoo") else str(out["valor"].get("fuente_precio") or "Yahoo Finance"),
         str(out["valor"].get("fecha_precio") or "")[:10]],
        ["Tasa libre de riesgo", (tm.get("co_rf_bruto") if mon == "COP" else tm.get("us_rf"), )[0]["fuente"] if tm else "", (tm.get("co_rf_bruto") if mon == "COP" else tm.get("us_rf"))["fecha"] if tm else ""],
        ["Primas de mercado y riesgo país", "Aswath Damodaran (NYU Stern)", str(dv.get("riesgo_pais") or "")],
        ["Múltiplos y betas por industria", "Aswath Damodaran (NYU Stern)", str(dv.get("multiplos") or "")],
        ["Pares del sector y consenso", "Yahoo Finance", datetime.now().strftime("%Y-%m-%d")],
    ]
    try:
        _p0 = params_empresa(nombre_empresa) or {}
        _rf0, _erp0, _crp0, _ = _capm_para_ui(_p0)
        out["calidad_variables"] = calidad_variables(nombre_empresa, {
            "deuda_neta": bp.get("deuda_neta"), "caja": bp.get("caja"), "nci": bp.get("nci"),
            "asociados": bp.get("asociados"), "acciones": val_base.get("acciones") or bp.get("acciones"),
            "beta_u": beta_u, "tax": tax, "kd": kd, "de_ratio": de_ratio, "rf": rf, "erp": erp, "crp": crp,
            "rf_editada": abs(float(rf) - float(_rf0)) > 1e-4,
            "erp_editada": abs(float(erp) - float(_erp0)) > 1e-4 or abs(float(crp) - float(_crp0)) > 1e-4,
        })
    except Exception as _e_cal:
        out["calidad_variables"] = [["Estado de los datos", "", "FALTANTE", f"no se pudo evaluar: {_e_cal}"[:120]]]
    out["nota_normalizacion"] = bool(nota_norm)
    out["alertas"] = list(motor.get("alertas") or [])[:6]
    out["vetos"] = list(motor.get("vetos") or [])
    return out


def generar_pdf_informe(ruta_pdf, nombre_empresa, datos):
    """Informe de valoración v3 (pestaña 7): perfil, resumen, cálculo, rango de valor, modelo vs mercado,
    datos y fuentes, gráficos y dictamen del comité IA."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, KeepTogether
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    AZUL, VERDE, GRIS, TEXTO = "#0A2540", "#0F766E", "#64748B", "#1E293B"
    doc = SimpleDocTemplate(ruta_pdf, pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.55 * inch, bottomMargin=0.6 * inch,
                            title=f"Informe de valoración · {nombre_empresa}", author="Modelación Financiera")
    st_ = getSampleStyleSheet()
    def estilo(nombre, padre="Normal", **kw):
        st_.add(ParagraphStyle(name=nombre, parent=st_[padre], **kw))
    estilo("T1", "Heading1", fontSize=17, textColor=colors.HexColor(AZUL), alignment=TA_CENTER, spaceAfter=2)
    estilo("T2", "Heading2", fontSize=12.5, textColor=colors.HexColor(VERDE), spaceBefore=11, spaceAfter=5)
    estilo("Cuerpo", fontSize=9.3, textColor=colors.HexColor(TEXTO), leading=12.5, alignment=TA_JUSTIFY)
    estilo("Nota", fontSize=8, textColor=colors.HexColor(GRIS), leading=10)
    estilo("Centro", fontSize=8.5, textColor=colors.HexColor(GRIS), alignment=TA_CENTER)
    estilo("Simple", fontSize=9.2, textColor=colors.HexColor("#065F46"), backColor=colors.HexColor("#ECFDF5"),
           leading=12, spaceBefore=3, spaceAfter=5, leftIndent=3, rightIndent=3)
    estilo("Decision", "Heading2", fontSize=13, alignment=TA_CENTER, spaceBefore=4, spaceAfter=4,
           textColor=colors.HexColor(datos.get("decision_color") or AZUL))
    estilo("Celda", fontSize=8.4, textColor=colors.HexColor("#0F172A"), leading=10.5)
    estilo("CeldaDer", fontSize=8.4, textColor=colors.HexColor("#0F172A"), leading=10.5, alignment=2)
    estilo("Cab", fontSize=8.4, textColor=colors.white, leading=10.5, fontName="Helvetica-Bold")
    estilo("CabDer", fontSize=8.4, textColor=colors.white, leading=10.5, fontName="Helvetica-Bold", alignment=2)

    def e(x):
        return str("" if x is None else x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def tabla(filas, anchos, der=(), cabecera=True, negrita_ultima=False):
        flow = []
        for ri, fila in enumerate(filas):
            cab = cabecera and ri == 0
            flow.append([Paragraph(e(c), st_[("CabDer" if ci in der else "Cab") if cab else ("CeldaDer" if ci in der else "Celda")])
                         for ci, c in enumerate(fila)])
        t = Table(flow, colWidths=anchos, repeatRows=1 if cabecera else 0)
        estilo_t = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("ROWBACKGROUNDS", (0, 1 if cabecera else 0), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")])]
        if cabecera:
            estilo_t.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(VERDE)))
        if negrita_ultima:
            estilo_t += [("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor(VERDE)),
                         ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ECFDF5"))]
        t.setStyle(TableStyle(estilo_t))
        return t

    W = 7.1 * inch
    story = []
    perfil = datos.get("perfil") or {}
    val = datos.get("valor") or {}
    mon, mon_px = val.get("mon_vps") or datos.get("moneda") or "", val.get("mon_precio") or ""

    # —— Portada ——
    story.append(Paragraph("Informe de valoración", st_["T1"]))
    story.append(Paragraph(f"<b>{e(nombre_empresa)}</b>", st_["T1"]))
    story.append(Paragraph(f"{e(datos.get('fecha', ''))} · flujo de caja descontado a {e(datos.get('horizonte', '—'))} años · "
                           "apoyo a la decisión, no es asesoría de inversión ni una orden de compra o venta", st_["Centro"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(VERDE)))

    # 1. Perfil
    story.append(Paragraph("1. La empresa", st_["T2"]))
    hechos = []
    if perfil.get("ticker"):
        hechos.append(["Cotiza en", f"{perfil.get('bolsa') or 'Bolsa'} · {perfil['ticker']}"])
    hechos.append(["Sector", perfil.get("sector") + (f" · {perfil['industria']}" if perfil.get("industria") else "")])
    origen = ", ".join(x for x in (perfil.get("ciudad"), perfil.get("pais")) if x)
    if origen:
        hechos.append(["Sede", origen])
    if perfil.get("empleados"):
        hechos.append(["Empleados", f"{int(perfil['empleados']):,}"])
    if perfil.get("web"):
        hechos.append(["Sitio web", perfil["web"]])
    mon_eeff = perfil.get("moneda_eeff") or mon
    hechos.append(["Moneda", f"Estados financieros en {mon_eeff}" + (f" · cotiza en {perfil.get('moneda_precio')}" if perfil.get("moneda_precio") and perfil.get("moneda_precio") != mon_eeff else "")])
    story.append(tabla(hechos, [1.4 * inch, W - 1.4 * inch], cabecera=False))
    story.append(Spacer(1, 4))
    story.append(Paragraph(e(perfil.get("descripcion") or "Sin descripción disponible."), st_["Cuerpo"]))
    if perfil.get("nota"):
        story.append(Paragraph(e(perfil["nota"]), st_["Nota"]))

    # 2. Resumen
    story.append(Paragraph("2. Resumen", st_["T2"]))
    story.append(Paragraph(e(datos.get("decision", "—")), st_["Decision"]))
    vps_t = f"{_fmt_precio(val.get('vps'))} {mon}"
    if val.get("vps_en_precio"):
        vps_t += f" (≈ {_fmt_precio(val['vps_en_precio'])} {mon_px})"
    px_t = f"{_fmt_precio(val.get('precio'))} {mon_px}" if val.get("precio") is not None else "N/D"
    if val.get("precio_en_modelo"):
        px_t += f" (≈ {_fmt_precio(val['precio_en_modelo'])} {mon})"
    if val.get("fecha_precio"):
        px_t += f" · {str(val['fecha_precio'])[:10]}"
    up = val.get("upside")
    try:
        up_t = f"{float(up):+.1f} %" if up is not None and np.isfinite(float(up)) else "N/D"
    except Exception:
        up_t = "N/D"
    resumen = [["Valor por acción del modelo", vps_t], ["Precio de mercado", px_t],
               ["Diferencia (valor vs precio)", up_t]]
    conc = datos.get("conciliacion") or {}
    if conc:
        resumen.append(["Causa de la diferencia", conc.get("descripcion") or conc.get("causa")])
    com = datos.get("comite") or {}
    if com.get("recomendacion"):
        po = com.get("precio_objetivo")
        resumen.append(["Comité IA", f"{com['recomendacion']} · precio objetivo 12 meses {_fmt_precio(po)} {mon_px} · convicción {com.get('conviccion')}/10"
                        if po is not None else f"{com['recomendacion']} · convicción {com.get('conviccion')}/10"])
    story.append(tabla(resumen, [2.1 * inch, W - 2.1 * inch], cabecera=False))
    story.append(Spacer(1, 4))
    if datos.get("decision_just"):
        story.append(Paragraph(e(datos["decision_just"]), st_["Cuerpo"]))
    if datos.get("decision_simple"):
        story.append(Paragraph(f"<b>En palabras simples:</b> {e(datos['decision_simple'])}", st_["Simple"]))
    if datos.get("vetos"):
        story.append(Paragraph("<b>Vetos de calidad:</b> " + e("; ".join(datos["vetos"])), st_["Cuerpo"]))

    # 3. Cómo se llegó al valor
    story.append(Paragraph("3. Cómo se llegó al valor", st_["T2"]))
    if datos.get("supuestos"):
        story.append(tabla([["Supuesto", "Valor", "Fuente o regla"]] + datos["supuestos"],
                           [2.35 * inch, 1.35 * inch, W - 3.7 * inch], der=(1,)))
    if datos.get("narrativa"):
        story.append(Spacer(1, 5))
        story.append(Paragraph("<b>La historia en cuatro palancas</b> (quién decidió cada una y qué la sostiene)", st_["Cuerpo"]))
        story.append(Spacer(1, 2))
        story.append(tabla([["Palanca", "Valor", "Decide", "Historia que la sostiene"]] + datos["narrativa"],
                           [1.9 * inch, 0.8 * inch, 0.7 * inch, W - 3.4 * inch], der=(1,)))
    if datos.get("proyeccion"):
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>Proyección:</b> " + e(datos["proyeccion"]), st_["Cuerpo"]))
    if datos.get("puente"):
        story.append(Spacer(1, 5))
        story.append(Paragraph(f"<b>Del valor de la empresa al valor por acción</b> (miles de millones de {e(mon)})", st_["Cuerpo"]))
        story.append(Spacer(1, 2))
        story.append(tabla(datos["puente"], [3.4 * inch, 1.6 * inch], der=(1,), cabecera=False, negrita_ultima=True))

    # 4. Rango de valor
    story.append(Paragraph("4. Rango de valor", st_["T2"]))
    anc = datos.get("anclas") or {}
    if anc.get("filas"):
        px_val = val.get("precio")
        filas = [["Id", "Método", f"Valor ({e(anc.get('moneda') or mon_px)})", "vs precio", "Cálculo"]]
        for aid, nombre, v_txt, metodo in anc["filas"]:
            v = (anc.get("valores") or {}).get(aid)
            dif = f"{(float(v) / float(px_val) - 1) * 100:+.0f} %" if (v and px_val) else "—"
            filas.append([aid, nombre, v_txt, dif, metodo])
        for aid, nombre, v_txt, motivo in anc.get("descartadas") or []:
            filas.append([aid, f"{nombre} (descartada)", v_txt, "—", motivo])
        story.append(tabla(filas, [0.4 * inch, 1.9 * inch, 0.95 * inch, 0.7 * inch, W - 3.95 * inch], der=(2, 3)))
        if anc.get("rango"):
            story.append(Paragraph(f"Rango de las anclas utilizables: {_fmt_precio(anc['rango'][0])} – {_fmt_precio(anc['rango'][1])} "
                                   f"{e(anc.get('moneda') or mon_px)}.", st_["Nota"]))
    else:
        story.append(Paragraph("Rango por método no disponible: ejecuta la pestaña 4 antes de generar el informe.", st_["Nota"]))
    if datos.get("escenarios_v3"):
        story.append(Spacer(1, 5))
        story.append(Paragraph("<b>Escenarios</b> (los mismos de la pestaña 2)", st_["Cuerpo"]))
        story.append(Spacer(1, 2))
        story.append(tabla([["Escenario", "WACC", "g", f"EV ({e(mon)})", "Patrimonio", f"Valor por acción ({e(mon)})"]] + datos["escenarios_v3"],
                           [1.1 * inch, 0.9 * inch, 0.8 * inch, 1.3 * inch, 1.3 * inch, W - 5.4 * inch], der=(1, 2, 3, 4, 5)))
        story.append(Paragraph("Pesimista: menos crecimiento y margen, más CAPEX y capital de trabajo, WACC +1,5 pp y g −1 pp. "
                               "Optimista: lo contrario. Si solo el optimista se ve bien, la tesis es frágil.", st_["Nota"]))

    # 5. Modelo vs mercado
    if conc:
        story.append(Paragraph("5. Modelo frente al mercado", st_["T2"]))
        story.append(Paragraph(f"<b>{e(conc.get('descripcion'))}</b> ({e(conc.get('causa'))}).", st_["Cuerpo"]))
        pal = conc.get("palancas") or []
        if pal:
            def _v(p_):
                if p_["palanca"] == "WACC":
                    return _pct_txt(p_["modelo"]), _pct_txt(p_["exigido"])
                if p_["palanca"].startswith("Flujos"):
                    return "1,00×", f"{p_['exigido']:.2f}×"
                return _pct_txt(p_["modelo"], 1), _pct_txt(p_["exigido"], 1)
            story.append(Spacer(1, 3))
            story.append(tabla([["Qué exige el precio", "Modelo", "Precio", "Juicio"]]
                               + [[p_["palanca"], *_v(p_), "razonable" if p_["razonable"] else "exigente"] for p_ in pal],
                               [3.0 * inch, 1.2 * inch, 1.2 * inch, W - 5.4 * inch], der=(1, 2)))
        story.append(Paragraph("Supuesto que iguala modelo y precio: " + e(conc.get("supuesto_que_iguala")), st_["Nota"]))
        if conc.get("advertencias_datos"):
            story.append(Paragraph("Advertencias: " + e("; ".join(conc["advertencias_datos"])), st_["Nota"]))
        cm_ = (com.get("conciliacion_mercado") or {}) if com else {}
        if cm_.get("explicacion"):
            story.append(Paragraph("<b>Lectura del comité IA:</b> " + e(cm_["explicacion"]), st_["Simple"]))

    # 6. Creación de valor y coherencia
    story.append(Paragraph("6. Creación de valor y coherencia", st_["T2"]))
    firma = datos.get("firma") or {}
    roic = datos.get("roic")
    filas = [["Indicador", "Valor", "Lectura"],
             ["ROIC vs WACC", f"{_pct_txt(roic)} vs {_pct_txt(datos.get('wacc'))}", "Si el ROIC supera al WACC, el negocio crea valor"],
             ["Valor creado sobre el capital (EV − capital invertido)", f"{_fmt_monto(firma.get('mva'))} {e(mon)}", "Positivo: el mercado del modelo paga más que lo invertido"],
             ["Rentabilidad implícita de la empresa", _pct_txt(firma.get("tir")), "Tasa que iguala el capital invertido con flujos y valor terminal"],
             ["Puntaje auxiliar del modelo", f"{e(datos.get('score'))}/7", "; ".join(datos.get("razones") or [])]]
    story.append(tabla(filas, [2.6 * inch, 1.5 * inch, W - 4.1 * inch]))
    for prueba, interp in (datos.get("pruebas") or []):
        story.append(Paragraph(f"• <b>{e(prueba)}</b>: {e(interp)}", st_["Cuerpo"]))
    if datos.get("sector_texto"):
        story.append(Paragraph("<b>Posición en el sector:</b> " + e(str(datos["sector_texto"]).replace("..", ".")), st_["Cuerpo"]))

    # 7. Datos y fuentes
    story.append(Paragraph("7. Datos y fuentes", st_["T2"]))
    cal = datos.get("calidad") or {}
    if cal:
        story.append(Paragraph(f"<b>Calidad de datos: {e(cal.get('nivel'))}</b> — {e(cal.get('fuente'))}. {e(cal.get('mercado'))}.", st_["Cuerpo"]))
    for a in datos.get("ajustes") or []:
        story.append(Paragraph("• " + e(a), st_["Cuerpo"]))
    story.append(Paragraph(e(datos.get("nota_normalizacion_texto") or ""), st_["Nota"]))
    if datos.get("calidad_variables"):
        story.append(Spacer(1, 3))
        story.append(Paragraph("<b>Estado de cada dato</b> (OBSERVADO: fuente identificable · CURADO: revisado a mano · "
                               "ESTIMADO: sustituto o regla, leer con su sensibilidad · USUARIO: escrito o cargado por ti · "
                               "FALTANTE: no disponible)", st_["Nota"]))
        story.append(tabla([["Variable", "Valor", "Estado", "Fuente"]] + [[str(c) for c in f] for f in datos["calidad_variables"]],
                           [1.6 * inch, 1.0 * inch, 0.95 * inch, W - 3.55 * inch]))
    if datos.get("fuentes"):
        story.append(Spacer(1, 3))
        story.append(tabla([["Dato", "Fuente", "Fecha"]] + datos["fuentes"], [1.9 * inch, W - 3.1 * inch, 1.2 * inch]))
    if datos.get("alertas"):
        story.append(Spacer(1, 3))
        story.append(Paragraph("<b>Alertas del modelo:</b> " + e(" · ".join(datos["alertas"])), st_["Nota"]))

    # 8. Gráficos
    imgs = [x for x in (datos.get("imagenes") or []) if x[1] and os.path.exists(x[1])]
    if imgs:
        story.append(Paragraph("8. Gráficos", st_["T2"]))
        for titulo, ruta, explicacion in imgs:
            alto = 3.6 * inch if "normalizacion" in str(ruta).lower() else 2.6 * inch
            bloque = [Paragraph(f"<b>{e(titulo)}</b>", st_["Cuerpo"]), Image(ruta, width=6.6 * inch, height=alto)]
            if explicacion:
                bloque.append(Paragraph(f"<b>Cómo leerlo:</b> {e(explicacion)}", st_["Simple"]))
            story.append(KeepTogether(bloque))
            story.append(Spacer(1, 4))

    # 9. Comité IA
    story.append(Paragraph("9. Dictamen del comité IA", st_["T2"]))
    if com.get("recomendacion"):
        po = com.get("precio_objetivo")
        story.append(Paragraph(f"<b>{e(com['recomendacion'])}</b>" + (f" · precio objetivo 12 meses {_fmt_precio(po)} {e(mon_px)}" if po is not None else "")
                               + f" · convicción {e(com.get('conviccion'))}/10", st_["Simple"]))
        if com.get("metodo_precio_objetivo"):
            story.append(Paragraph("<b>Precio objetivo:</b> " + e(com["metodo_precio_objetivo"]), st_["Cuerpo"]))
        for t_ in (com.get("tesis") or [])[:4]:
            story.append(Paragraph("• " + e(t_), st_["Cuerpo"]))
        riesgos = [r for r in com.get("riesgos") or [] if isinstance(r, dict)][:4]
        if riesgos:
            story.append(Paragraph("<b>Riesgos y cómo vigilarlos:</b>", st_["Cuerpo"]))
            for r in riesgos:
                story.append(Paragraph(f"• {e(r.get('riesgo'))} — indicador: {e(r.get('indicador'))}", st_["Cuerpo"]))
        cats = [c for c in com.get("catalizadores") or [] if isinstance(c, dict)][:3]
        if cats:
            story.append(Paragraph("<b>Catalizadores:</b> " + e("; ".join(f"{c.get('catalizador')} ({c.get('ventana')})" for c in cats)), st_["Cuerpo"]))
        cambia = (com.get("cambiaria_la_recomendacion") or [])[:3]
        if cambia:
            story.append(Paragraph("<b>Cambiaría la recomendación:</b> " + e("; ".join(map(str, cambia))), st_["Cuerpo"]))
        story.append(Paragraph("Dictamen generado con IA a partir del modelo y de hechos con fuente; complementa, no sustituye, el análisis.", st_["Nota"]))
    else:
        story.append(Paragraph("No hay dictamen del comité IA en esta sesión. Genéralo en la pestaña 4 y vuelve a crear el informe para incluirlo.", st_["Nota"]))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8")))
    story.append(Paragraph(f"Montos en miles de millones de {e(mon) or 'la moneda del emisor'} salvo valores por acción. "
                           "Documento generado automáticamente. No constituye recomendación de inversión.", st_["Centro"]))

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor(GRIS))
        canvas.drawString(0.7 * inch, 0.35 * inch, f"Informe de valoración · {nombre_empresa}"[:90])
        canvas.drawRightString(letter[0] - 0.7 * inch, 0.35 * inch, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    return ruta_pdf


_PAISES_ES = {"United States": "Estados Unidos", "Colombia": "Colombia", "Brazil": "Brasil", "Mexico": "México",
              "Chile": "Chile", "Peru": "Perú", "United Kingdom": "Reino Unido", "Canada": "Canadá", "Spain": "España",
              "Germany": "Alemania", "France": "Francia", "Netherlands": "Países Bajos", "Switzerland": "Suiza",
              "Ireland": "Irlanda", "Japan": "Japón", "China": "China", "Taiwan": "Taiwán"}


def _traducir_descripcion(texto, api_key=None):
    """Traduce al español la descripción de Yahoo (inglés) con el proveedor de IA configurado; None si no hay."""
    if not texto:
        return None
    try:
        cache = _almacen_estado().setdefault("_traducciones", {})
        k = hashlib.sha1(texto.encode("utf-8")).hexdigest()
        if k in cache:
            return cache[k]
        clave = api_key or _almacen_estado().get("clave_ia")
        if not clave and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            return None
        out = _llamar_ia_redaccion(
            "Eres traductor financiero. Traduce al español neutro, fiel y conciso; no agregues información.",
            "Traduce esta descripción de una empresa (máximo 120 palabras; resume si es más larga):\n\n" + texto[:2500],
            temperature=0.1, api_key=clave, proveedor="gemini" if clave or os.environ.get("GEMINI_API_KEY") else "auto")
        out = (out or "").strip() or None
        if out:
            cache[k] = out
        return out
    except Exception:
        return None


def perfil_empresa(nombre_empresa, traducir=True):
    """Descripción de la empresa para el inicio del informe: a qué se dedica, sector, de dónde es, dónde cotiza."""
    emp = resolver_empresa(nombre_empresa) or {}
    p = emp.get("params") or {}
    sector = str(emp.get("sector") or "No clasificado")
    sec, _, ind = sector.partition(" / ")
    tk = emp.get("ticker_yf") or (ticker_yf_empresa(nombre_empresa) if nombre_empresa else None) or emp.get("ticker_bvc")
    pais_en = emp.get("pais") or ""
    if not pais_en and (str(tk or "").upper().endswith(".CL") or nombre_empresa in EMPRESAS):
        pais_en = "Colombia"
    pais = _PAISES_ES.get(pais_en, pais_en)
    desc = (emp.get("descripcion_completa") or emp.get("descripcion") or "").strip()
    # El catálogo trae una descripción curada en español: preferirla si existe.
    cat = (EMPRESAS.get(nombre_empresa) or {}).get("descripcion") if nombre_empresa in EMPRESAS else None
    idioma, nota = "es", None
    if cat and not _texto_parece_ingles(cat):
        desc_es = cat
        if desc and _texto_parece_ingles(desc) and len(desc) > len(cat) * 1.5 and traducir:
            desc_es = _traducir_descripcion(desc) or cat
    elif desc and _texto_parece_ingles(desc):
        desc_es = _traducir_descripcion(desc) if traducir else None
        if desc_es:
            nota = "Descripción de Yahoo Finance traducida automáticamente."
        else:
            desc_es, idioma = desc[:900] + ("…" if len(desc) > 900 else ""), "en"
            nota = "Descripción original de Yahoo Finance (en inglés)."
    else:
        desc_es = desc or "Sin descripción disponible."
    bolsa = emp.get("bolsa") or ("Bolsa de Valores de Colombia (BVC)" if str(tk or "").upper().endswith(".CL") else "")
    return {
        "nombre": nombre_empresa, "ticker": tk, "bolsa": bolsa, "sector": (sec or sector).strip(),
        "industria": (emp.get("industria") or ind or "").strip(), "pais": pais, "ciudad": emp.get("ciudad") or "",
        "web": emp.get("web") or "", "empleados": emp.get("empleados"),
        "moneda_eeff": emp.get("moneda") or p.get("moneda") or "", "moneda_precio": emp.get("moneda_precio") or "",
        "descripcion": desc_es, "idioma": idioma, "nota": nota, "fuente": emp.get("fuente") or "catálogo",
    }


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
        df_proj, meta_proj7 = proyectar_variables_con_meta(df_hist, horizonte, tax=tax)
        df_proj = recalcular_fcff(df_proj.copy(), tax=tax, capex_extra=capex_extra)

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
            # Mismos escenarios que la pestaña 2 (shocks de drivers); el base es la proyección de la pestaña 4.
            if nombre == "Base":
                fc_e, nop_e = df_proj["FCFF"].values, _nopat_final(df_proj)
                ebitda_out = float(df_proj["EBITDA"].iloc[-1]) if "EBITDA" in df_proj.columns else None
            else:
                fc_e, nop_e, ebitda_out = insumos_escenario(df_proj, nombre, tax=tax)
            val = valorar_con_bridge(fc_e, w_adj, g_e, bp, ebitda_salida=ebitda_out, precio_mercado=precio, mid_year=bool(mid_year), g_max_macro=float(g_max_macro), nopat_final=nop_e)
            escenarios[nombre] = val
            escenarios[nombre]["g"] = float(val.get("g_used", g_e))
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
        if not np.isfinite(roic):
            razones.append("ROIC no disponible")  # mismo criterio que la pestaña 4
        elif roic > wacc:
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
        _fc_p, _nop_p, _eb_p = insumos_escenario(df_proj, "Pesimista", tax=tax)  # mismo pesimista que la pestaña 2
        val_pes = valorar_con_bridge(
            _fc_p,
            wacc + 0.015,
            g_pes_m,
            bp,
            ebitda_salida=_eb_p,
            precio_mercado=precio,
            mid_year=bool(mid_year),
            g_max_macro=float(g_max_macro),
            nopat_final=_nop_p,
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
            precio_mercado=(val_base.get("precio_moneda_modelo") if val_base.get("fx_aplicado") else precio),
            equity_por_accion=val_base.get("value_per_share"),
            moneda_modelo=mon_modelo,
            moneda_precio=(mon_modelo if val_base.get("fx_aplicado") else mon_precio),
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
            + (f"ROIC proyectado {roic*100:.1f}% vs WACC {wacc*100:.1f}%. " if np.isfinite(roic)
               else f"ROIC no disponible (sin capital invertido) · WACC {wacc*100:.1f}%. ")
            + "No constituye orden de compra en bolsa ni asesoría de inversión."
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
        # El gráfico C (VPN acumulado de un «proyecto» con inversión ilustrativa) ya no va al PDF: al valorar una
        # empresa completa confundía; se reemplaza por el valor creado sobre el capital invertido (MVA).

        # Sector bars
        fig4, ax = plt.subplots(figsize=(9, 4))
        graficar_ranking_sectorial(ax, df_s, short, f"Ranking sectorial · {short} resaltada (mayor = mejor)")
        p4 = os.path.join(tmpdir, "sector.png")
        fig4.tight_layout()
        fig4.savefig(p4, dpi=120, facecolor="white")
        plt.close(fig4)
        img_paths.append((
            "Gráfico C — Ranking del sector",
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
                "Gráfico D — Normalización de atípicos (original vs tratado)",
                p_norm,
                "Izquierda: serie original del driver (atípicos marcados). Derecha: tras Hampel "
                "(mediana ± 3,5·MAD) con winsorización. Se aplica para que un año extremo no sesgue "
                "la proyección FCFF. Válido para catálogo, Yahoo y Excel."
            ))
        else:
            nota_norm = ""

        # ---- Contenido nuevo del informe (v3) ----
        extras_pdf = {}
        try:
            extras_pdf = _datos_informe_v3(
                nombre_empresa, df_hist=df_hist, df_proj=df_proj, meta_proj=meta_proj7, val_base=val_base,
                escenarios=escenarios, wacc=wacc, ke=ke, beta_l=beta_l, rf=rf, erp=erp, crp=crp, kd=kd, tax=tax,
                de_ratio=de_ratio, we=we, wd=wd, beta_u=beta_u, g=g, horizonte=horizonte, precio=precio, bp=bp,
                mon_modelo=mon_modelo, mon_precio=mon_precio, capital_invertido=capital_invertido, prov=prov,
                mensaje_datos=mensaje_datos, motor=motor, mid_year=mid_year, g_max_macro=g_max_macro,
                vpn_firma=vpn_firma, tir_firma=tir_firma, nota_norm=bool(nota_norm),
            )
        except Exception as _e_v3:
            extras_pdf = {"error_v3": str(_e_v3)}

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
                "Se detectaron y trataron valores atípicos en los drivers del histórico "
                "(Hampel + winsorización) para que un año extremo no sesgue la proyección. Ver gráfico D."
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
        datos_pdf.update(extras_pdf)
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
<li><b>WACC:</b> {wacc*100:.2f}% · <b>g:</b> {g*100:.2f}% · <b>ROIC:</b> {(f"{roic*100:.2f}%" if np.isfinite(roic) else "N/D")}</li>
<li><b>EV base:</b> {val_base['EV']:,.0f} · <b>Equity base:</b> {val_base['Equity_Value']:,.0f} (miles M · moneda del emisor)</li>
<li><b>Valor creado sobre el capital invertido (EV − capital):</b> {_fmt_monto(vpn_firma)} · <b>Rentabilidad implícita de la empresa:</b> {_pct_txt(tir_firma)}</li>
<li><b>FCFF promedio proyectado:</b> {df_proj['FCFF'].mean():,.0f}</li>
<li><b>Método de proyección:</b> Drivers + identidad FCFF (el mismo de las pestañas 2 a 5; el selector de la pestaña 1 solo aplica a esa pestaña)</li>
<li><b>Datos:</b> {mensaje_datos}</li>
</ul>
</div>
{result_note("Cómo leer estos números",
    "Si ROIC > WACC la empresa crea valor. Si el valor de la empresa supera el capital invertido y su rentabilidad "
    "implícita supera el WACC, el modelo ve creación de valor con estos supuestos.")}
<div class="section-card">
<b>Auditoría rápida</b>
<ul style="color:#E8EEF7">{''.join(f'<li><b>{p}</b> — {i}</li>' for p,i in pruebas)}</ul>
</div>
<div class="section-card">
<b>Sector</b>
<p style="color:#E8EEF7;margin:0">{sector_texto}</p>
</div>
{tip("Los gráficos de abajo resumen la historia: (A) caja libre proyectada, (B) valor en tres futuros, "
     "(C) valor por acción de cada escenario frente al precio y (D) ranking sectorial. El PDF agrega el perfil de la empresa, "
     "los supuestos, el rango de valor por método, la comparación con el mercado, las fuentes y el dictamen del comité IA.")}
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
        # C: valor por acción de cada escenario frente al precio
        _vps_esc = [escenarios[k].get("value_per_share") or 0.0 for k in ("Pesimista", "Base", "Optimista")]
        axes[2].bar(["Pesim.", "Base", "Optim."], _vps_esc, color=[COLOR_DANGER, COLOR_PRIMARY, COLOR_SUCCESS])
        _px_ref = val_base.get("precio_moneda_modelo") if val_base.get("fx_aplicado") else precio
        if _px_ref:
            axes[2].axhline(float(_px_ref), color="#F59E0B", ls="--", label="Precio")
            axes[2].legend(fontsize=8)
        axes[2].set_title("C) Valor por acción vs precio")
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
                decision, f"{score}/7", f"{wacc*100:.2f}", (f"{roic*100:.2f}" if np.isfinite(roic) else "N/D"), f"{de_ratio:.2f}",
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
                "metricas": {
                    "val_ev": _finite_or_none(val_base.get("EV")),
                    "val_equity": _finite_or_none(val_base.get("Equity_Value")),
                    "vps_modelo": _finite_or_none(vps),
                    "upside": _finite_or_none(upside),
                    "precio_mercado": _finite_or_none(precio),
                },
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
        co = CAPM_POR_MERCADO["CO"]  # una sola fuente para las anclas de Colombia
        return (co["rf"], co["erp"], co["crp"], co["g_max_macro"])
    # Preferir valores ya derivados; si faltan, DEFAULT global (no CO)
    _def = CAPM_POR_MERCADO.get("DEFAULT", {"rf": 0.05, "erp": 0.05, "crp": 0.0, "g_max_macro": 0.04})
    return (
        float(p.get("rf") if p.get("rf") is not None else _def["rf"]),
        float(p.get("erp") if p.get("erp") is not None else _def["erp"]),
        float(p.get("crp") if p.get("crp") is not None else _def.get("crp", 0.0)),
        float(p.get("g_max_macro") if p.get("g_max_macro") is not None else _def.get("g_max_macro", 0.04)),
    )


def al_cambiar_empresa(nombre_empresa):
    if nombre_empresa in EMPRESAS:
        preparar_empresa(nombre_empresa)  # Yahoo primero; catálogo curado como respaldo
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
        p.setdefault("rf", CAPM_POR_MERCADO["CO"]["rf"])
        p.setdefault("erp", CAPM_POR_MERCADO["CO"]["erp"])
        p.setdefault("crp", 0.0)
        # Techo nominal en COP: inflación implícita ~6 % (BanRep). Antes 4 % fijo
        # (techo pensado para USD) → crecimiento real negativo a perpetuidad y
        # valor terminal subestimado en todas las empresas colombianas.
        p.setdefault("g_max_macro", CAPM_POR_MERCADO["CO"]["g_max_macro"])
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


VERSION_PLANTILLA_EEFF = "2"


def asegurar_plantilla_excel(ruta=None, forzar=False):
    """Crea (o actualiza si es de una versión anterior) la plantilla Excel de EEFF para carga independiente.

    Versión 2: hoja «Datos» vacía para llenar (el ejemplo pasa a la hoja «Ejemplo», que el cargador ignora),
    hoja «Parámetros» con moneda, unidad, tasa de impuestos y datos del puente a patrimonio (con listas
    desplegables), e instrucciones sobre formatos aceptados.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    if ruta is None:
        try:
            base = Path(__file__).resolve().parent
        except Exception:
            base = Path.cwd()
        ruta = base / "Plantilla_EEFF_Modelacion_Financiera.xlsx"
    ruta = Path(ruta)
    if ruta.exists() and ruta.stat().st_size > 2000 and not forzar:
        try:
            wb0 = load_workbook(ruta, read_only=True)
            ver = str(wb0["Instrucciones"]["A30"].value or "") if "Instrucciones" in wb0.sheetnames else ""
            wb0.close()
            if ver.endswith(f"versión {VERSION_PLANTILLA_EEFF}"):
                return str(ruta)
        except Exception:
            pass

    headers = ["Año", "Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC", "Delta_NWC", "NOPAT", "FCFF"]
    required = {"Año", "Ingresos", "EBITDA", "EBIT", "CAPEX", "NWC"}
    oscuro, verde, gris = "0B1F33", "0F766E", "334155"
    thin = Border(left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"),
                  top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1"))
    anchos = [10, 13, 13, 13, 15, 13, 13, 13, 13, 13]

    def encabezados(ws, fila):
        for col, h in enumerate(headers, start=1):
            c = ws.cell(fila, col, h)
            c.font = Font(bold=True, color="FFFFFF", size=11)
            c.fill = PatternFill("solid", fgColor=oscuro if h in required else gris)
            c.border = thin
            c.alignment = Alignment(horizontal="center")
        for k, w in enumerate(anchos, start=1):
            ws.column_dimensions[chr(64 + k)].width = w

    wb = Workbook()
    # --- Datos (para llenar) ---
    ws = wb.active
    ws.title = "Datos"
    ws.merge_cells("A1:J1")
    ws["A1"] = "ESTADOS FINANCIEROS — un año por fila, del más antiguo al más reciente (mínimo 3 años; ideal 5–10)"
    ws["A1"].font = Font(bold=True, size=12, color=oscuro)
    ws.merge_cells("A2:F2")
    ws["A2"] = "Obligatorias (azul oscuro)"
    ws["A2"].fill = PatternFill("solid", fgColor=verde)
    ws["A2"].font = Font(bold=True, color="FFFFFF", size=9)
    ws.merge_cells("G2:J2")
    ws["G2"] = "Opcionales: si quedan vacías se calculan"
    ws["G2"].fill = PatternFill("solid", fgColor="64748B")
    ws["G2"].font = Font(bold=True, color="FFFFFF", size=9)
    encabezados(ws, 3)
    for r in range(4, 19):
        for c in range(1, 11):
            cell = ws.cell(r, c)
            cell.border = thin
            cell.number_format = "0" if c == 1 else "#,##0.0"
    ws["A20"] = ("Unidad y moneda: indícalas en la hoja «Parámetros». CAPEX en positivo. NWC = activo corriente − "
                 "pasivo corriente (sin caja ni deuda financiera). No incluyas el año en curso si no ha cerrado.")
    ws["A20"].font = Font(italic=True, size=9, color="64748B")
    ws.freeze_panes = "B4"

    # --- Parámetros ---
    wp = wb.create_sheet("Parametros")
    wp["A1"] = "PARÁMETROS — completa lo que tengas; lo vacío lo estima el modelo o lo tomas de la fuente pública"
    wp["A1"].font = Font(bold=True, size=12, color=oscuro)
    filas = [
        ("Moneda", "COP", "COP, USD u otra (código de 3 letras)"),
        ("Unidad de las cifras", "miles de millones", "miles de millones · millones · miles · unidades (se convierte a miles de millones)"),
        ("País", "Colombia", "Define la tasa libre de riesgo y la prima de mercado (Colombia, United States, …)"),
        ("Tasa de impuestos (%)", None, "Tasa efectiva o legal, p. ej. 35"),
        ("Deuda financiera", None, "Último cierre, en la misma unidad de las cifras"),
        ("Caja y equivalentes", None, "Último cierre"),
        ("Interés minoritario", None, "Patrimonio de minoritarios en el balance consolidado"),
        ("Inversiones en asociadas", None, "Valor en libros de asociadas y negocios conjuntos"),
        ("Acciones en circulación (millones)", None, "Para el valor por acción"),
        ("Precio por acción", None, "Opcional: para comparar el valor con el mercado si la empresa no cotiza en Yahoo"),
        ("Beta", None, "Opcional: beta apalancada observada; si falta, se usa 1,0"),
    ]
    for k, (etq, val, nota) in enumerate(filas, start=3):
        wp.cell(k, 1, etq).font = Font(bold=True, color=oscuro)
        c = wp.cell(k, 2, val)
        c.border = thin
        c.fill = PatternFill("solid", fgColor="ECFDF5")
        wp.cell(k, 3, nota).font = Font(size=9, color="64748B")
    wp.column_dimensions["A"].width = 36
    wp.column_dimensions["B"].width = 22
    wp.column_dimensions["C"].width = 90
    dv_mon = DataValidation(type="list", formula1='"COP,USD,EUR,BRL,MXN,CLP,PEN"', allow_blank=True)
    dv_uni = DataValidation(type="list", formula1='"miles de millones,millones,miles,unidades"', allow_blank=False)
    wp.add_data_validation(dv_mon)
    wp.add_data_validation(dv_uni)
    dv_mon.add("B3")
    dv_uni.add("B4")
    wp["A16"] = ("Si la empresa ya está en el catálogo o se descargó de Yahoo, el modelo usa sus datos de mercado y de esta "
                 "hoja solo toma la unidad y la tasa de impuestos.")
    wp["A16"].font = Font(italic=True, size=9, color="64748B")

    # --- Ejemplo (el cargador lo ignora) ---
    we = wb.create_sheet("Ejemplo")
    we["A1"] = "EJEMPLO ILUSTRATIVO (miles de millones COP) — esta hoja no se carga"
    we["A1"].font = Font(bold=True, size=12, color=oscuro)
    encabezados(we, 2)
    ejemplo = [
        [2021, 9200, 3500, 2700, 800, 1600, 1000, None, None, None],
        [2022, 10500, 4100, 3200, 900, 1800, 1100, None, None, None],
        [2023, 11200, 4500, 3600, 900, 1900, 1150, None, None, None],
        [2024, 12000, 4900, 4000, 900, 2000, 1200, None, None, None],
        [2025, 12900, 5300, 4350, 950, 2100, 1260, None, None, None],
    ]
    for r, fila in enumerate(ejemplo, start=3):
        for c, v in enumerate(fila, start=1):
            cell = we.cell(r, c, v)
            cell.border = thin
            cell.number_format = "0" if c == 1 else "#,##0.0"

    # --- Instrucciones ---
    wi = wb.create_sheet("Instrucciones")
    wi["A1"] = "Plantilla de estados financieros — Modelación Financiera"
    wi["A1"].font = Font(bold=True, size=14, color=oscuro)
    lineas = [
        "", "Cómo usar esta plantilla",
        "1. Llena la hoja «Datos»: un año por fila (mínimo 3, ideal 5–10), del más antiguo al más reciente.",
        "2. Completa la hoja «Parámetros»: moneda, unidad de las cifras y tasa de impuestos como mínimo.",
        "3. Guarda como .xlsx (o .csv solo con la tabla) y cárgalo en «Estados financieros» de la barra lateral.",
        "", "Columnas",
        "Obligatorias: Año, Ingresos, EBITDA, EBIT (utilidad operativa), CAPEX (inversiones, en positivo), NWC (capital de trabajo).",
        "Opcionales: Depreciacion (si falta = EBITDA − EBIT), Delta_NWC, NOPAT (= EBIT × (1 − impuestos)) y "
        "FCFF (= NOPAT + Depreciacion − CAPEX − Delta_NWC).",
        "", "Formatos aceptados",
        "· La tabla puede tener títulos o filas en blanco arriba: el cargador busca la fila de encabezados.",
        "· También se acepta el formato de los estados oficiales: partidas en filas y años en columnas.",
        "· Los nombres pueden ir en español o inglés (Ingresos/Revenue, CAPEX/Inversiones, Capital de trabajo/NWC…).",
        "· Si tus cifras están en millones o en pesos, indícalo en «Unidad de las cifras»: se convierten solas.",
        "", "Buenas prácticas",
        "· Usa estados consolidados auditados y la misma moneda y unidad en todas las celdas.",
        "· No incluyas el año en curso si el ejercicio no ha cerrado.",
        "· EBIT sin el método de participación: el valor de las asociadas se suma aparte en el puente a patrimonio.",
        "· Un salto de ingresos de más de 300 % entre años suele indicar un error de unidades.",
        "· Para corregir solo una partida de la fuente pública (p. ej. el CAPEX) usa el botón "
        "«Corregir histórico (cifras oficiales)» de la app, sin cargar archivo.",
    ]
    for k, t in enumerate(lineas, start=2):
        wi[f"A{k}"] = t
        if t in ("Cómo usar esta plantilla", "Columnas", "Formatos aceptados", "Buenas prácticas"):
            wi[f"A{k}"].font = Font(bold=True, color=verde)
    wi["A30"] = f"Plantilla EEFF · versión {VERSION_PLANTILLA_EEFF}"
    wi["A30"].font = Font(size=8, color="94A3B8")
    wi.column_dimensions["A"].width = 120

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
def _fcff_desde_sesion_o_hist(nombre_empresa, horizonte=5, tax=0.35, con_nopat=False):
    """FCFF proyectado por DRIVERS (el mismo motor de la pestaña 4) y, si se pide, el NOPAT terminal.

    Reutiliza la pestaña 1 solo si se proyectó por drivers con el mismo horizonte: con ETS/ARIMA los
    flujos difieren de los de la pestaña 4 y la sensibilidad mostraba otro valor por acción.
    """
    tabs = (RESULTADOS_SESION.get("tabs") or {})
    t1 = tabs.get("1") or {}
    if (t1.get("fcff_proj") and t1.get("metodo_key", "drivers") == "drivers"
            and int(t1.get("horizonte") or 0) == int(horizonte) and (t1.get("nopat_final") is not None or not con_nopat)):
        fc = list(t1["fcff_proj"])
        return (fc, None, t1.get("nopat_final")) if con_nopat else (fc, None)
    try:
        df_hist, _ = cargar_y_limpiar_excel(None, nombre_empresa, usar_datos_publicos=True)
        df_hist, _ = _sanear_historico_tab1(df_hist)
        df_proj, meta = proyectar_variables_con_meta(df_hist, int(horizonte), metodo="drivers", tax=float(tax))
        fcff = [float(x) for x in df_proj["FCFF"].values]
        return (fcff, meta, _nopat_final(df_proj)) if con_nopat else (fcff, meta)
    except Exception as e:
        return ([], str(e), None) if con_nopat else ([], str(e))


def sensibilidad_rapida_ui(nombre_empresa, wacc, g, horizonte, tax, deuda_neta, caja, nci, otros_claims, asociados, acciones, mid_year, g_max_macro):
    """Actualiza Hero KPI al mover WACC/g — solo DCF sobre FCFF ya proyectado."""
    try:
        wacc = float(wacc)
        g = float(g)
        fcff, err, nopat_fin = _fcff_desde_sesion_o_hist(nombre_empresa, horizonte=horizonte, tax=tax, con_nopat=True)
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
        # Mismo valor terminal que la pestaña 4 (NOPAT terminal y RONIC): antes Gordon sobre el último FCFF.
        val = valorar_con_bridge(
            fcff, wacc, g, bp,
            mid_year=bool(mid_year),
            g_max_macro=float(g_max_macro or 0.04),
            nopat_final=nopat_fin,
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

