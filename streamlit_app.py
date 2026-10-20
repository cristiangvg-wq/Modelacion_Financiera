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
  --text: #E8EEF7;
  --text-muted: #94A3B8;
  --text-dim: #64748B;
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
section[data-testid="stSidebar"] label {
  color: var(--text-muted) !important;
  font-size: 0.82rem !important;
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

/* Expanders */
.streamlit-expanderHeader {
  background: var(--bg-card) !important;
  border-radius: 10px !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  font-weight: 500 !important;
}
.streamlit-expanderContent {
  background: var(--bg-panel) !important;
  border: 1px solid var(--border-soft) !important;
  border-top: none !important;
  border-radius: 0 0 10px 10px !important;
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
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748B !important;
  font-weight: 700;
  margin: 1rem 0 0.4rem 0;
}

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
  background: transparent !important;
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


def _show_df(df, label=None):
    if df is None:
        return
    if isinstance(df, pd.DataFrame) and not df.empty:
        if label:
            st.caption(label)
        st.dataframe(df, use_container_width=True)


def _show_fig(fig, caption=None):
    if fig is None:
        return
    if not HAS_MPL:
        st.warning("matplotlib no instalado")
        return
    if caption:
        st.caption(caption)
    # Dark axes for FinTech look
    try:
        for ax in fig.get_axes():
            ax.set_facecolor("#151C2C")
            fig.patch.set_facecolor("#111827")
            ax.tick_params(colors="#94A3B8")
            ax.xaxis.label.set_color("#94A3B8")
            ax.yaxis.label.set_color("#94A3B8")
            ax.title.set_color("#E8EEF7")
            for spine in ax.spines.values():
                spine.set_color("#243044")
            legend = ax.get_legend()
            if legend:
                legend.get_frame().set_facecolor("#1A2336")
                legend.get_frame().set_edgecolor("#243044")
                for t in legend.get_texts():
                    t.set_color("#E8EEF7")
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


def _kpi_card(label: str, value: str, sub: str = "", accent: bool = False) -> str:
    cls = "tf-kpi accent" if accent else "tf-kpi"
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="{cls}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}</div>"
    )


def _kpi_row(items: list[tuple]) -> None:
    """items: list of (label, value, sub, accent?)"""
    cards = []
    for it in items:
        label, value = it[0], it[1]
        sub = it[2] if len(it) > 2 else ""
        accent = it[3] if len(it) > 3 else False
        cards.append(_kpi_card(label, value, sub, accent))
    st.markdown(f'<div class="tf-kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _section_start(title: str) -> None:
    st.markdown(
        f'<div class="tf-section"><div class="tf-section-title">{title}</div>',
        unsafe_allow_html=True,
    )


def _section_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


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

        if st.session_state.get("ficha_html"):
            with st.expander("Ficha", expanded=False):
                _html(st.session_state["ficha_html"])

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

        st.markdown('<p class="tf-sidebar-label">Parámetros</p>', unsafe_allow_html=True)
        ek = str(empresa)[:48]
        p = st.session_state.get("params") or {}

        horizonte = st.slider("Horizonte (años)", 3, 10, 5, key=f"hor_{ek}")
        de_ratio = st.slider("D/E", 0.0, 5.0, float(p.get("de_ratio", 1.2) or 1.2), 0.01, key=f"de_{ek}")
        kd = st.slider("Kd", 0.0, 0.25, float(p.get("kd", 0.08) or 0.08), 0.005, key=f"kd_{ek}")
        tax = st.slider("Tax", 0.0, 0.50, float(p.get("tax", 0.35) or 0.35), 0.01, key=f"tax_{ek}")
        g = st.slider("g terminal", 0.0, 0.08, float(p.get("g", 0.03) or 0.03), 0.005, key=f"g_{ek}")
        capex_extra = st.slider("CAPEX extra", 0, 8000, 0, 50, key=f"cx_{ek}")
        beta_u = st.slider("β unlevered", 0.0, 3.0, float(p.get("beta_u", 0.5) or 0.5), 0.05, key=f"bu_{ek}")

        with st.expander("CAPM", expanded=True):
            rf = st.slider("rf", 0.02, 0.16, float(st.session_state.get("rf", 0.12)), 0.005, key=f"rf_{ek}")
            erp = st.slider("ERP", 0.03, 0.10, float(st.session_state.get("erp", 0.055)), 0.005, key=f"erp_{ek}")
            crp = st.slider("CRP", 0.0, 0.05, float(st.session_state.get("crp", 0.0)), 0.005, key=f"crp_{ek}")

        with st.expander("Puente a equity", expanded=False):
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

    # ----- KPI strip -----
    _kpi_row(
        [
            ("WACC", f"{w['wacc']*100:.2f}%", "costo capital", True),
            ("Ke (CAPM)", f"{w['ke']*100:.2f}%", f"βL {w['beta_l']:.2f}"),
            ("Horizonte", f"{horizonte} a", f"g {g*100:.1f}%"),
            ("Emisor", empresa.split("—")[0].strip()[:18], str(sector)[:22]),
        ]
    )

    st.markdown(
        f'<div class="tf-info"><b>{empresa}</b> · modelo en <b>{moneda}</b> '
        f"(miles de millones). Calibra supuestos antes de interpretar.</div>",
        unsafe_allow_html=True,
    )

    # ----- Tools strip -----
    t1, t2, t3 = st.columns(3)
    with t1:
        with st.expander("⚡ Sensibilidad WACC · g", expanded=False):
            sw = st.slider("WACC", 0.06, 0.18, float(w["wacc"]), 0.0025, key="sens_wacc")
            sg = st.slider("g", 0.005, 0.06, float(g), 0.0025, key="sens_g")
            if st.button("Aplicar", key="btn_sens", use_container_width=True):
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
    with t2:
        with st.expander("📚 Glosario", expanded=False):
            try:
                _html(L.glosario_html())
            except Exception:
                st.caption("FCFF · WACC · ROIC · EV · Equity · VPN · TIR · g · Beta")
    with t3:
        with st.expander("🤖 Consulta IA", expanded=False):
            pregunta = st.text_area("Pregunta", height=70, placeholder="¿WACC? · upside · resumen comité")
            cprov = st.selectbox("Proveedor", ["gemini", "xai", "openai"], key="iaprov")
            ckey = st.text_input("API key", type="password", key="iakey")
            if st.button("Consultar", key="btn_ia", use_container_width=True):
                with st.spinner("…"):
                    try:
                        _html(L.asistente_consulta_financiera(pregunta, empresa, api_key=ckey or None, proveedor=cprov))
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
            if len(r) > 3:
                _show_fig(r[3], "Fan chart FCFF")
            if len(r) > 4 and r[4] is not None:
                _show_fig(r[4], "Atípicos")
            if len(r) > 5 and r[5]:
                _html(r[5])

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
            if len(r) > 2:
                _show_fig(r[2], "EV vs Equity")

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
            if len(r) > 2:
                _show_fig(r[2], "Recuperación")

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
            if len(r) > 2:
                _show_fig(r[2], "Sector")

    with tab7:
        st.markdown("##### Informe ejecutivo")
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
                _show_df(r[1], "KPIs")
            if len(r) > 2:
                _show_fig(r[2], "Panel")
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
