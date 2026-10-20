"""
Modelación Financiera Multisectorial — Streamlit (funcionalidad completa)
Conserva la lógica del notebook/Gradio original: catálogo BVC, Yahoo, Excel,
proyección (drivers/ETS/ARIMA), DCF, auditoría, recomendación, VPN/TIR,
sector, informe PDF, conector de mercado, sensibilidad, consulta IA, glosario.
Herramienta pedagógica · No es asesoría de inversión.
"""
from __future__ import annotations

import io
import os
import traceback
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Lógica de negocio completa (extraída del original)
# ---------------------------------------------------------------------------
import modelacion_logic as L

# Backend matplotlib no interactivo
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    plt = None

st.set_page_config(
    page_title="Modelación Financiera · Multisectorial",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Utilidades UI
# ---------------------------------------------------------------------------
def _html(x, max_chars=120000):
    if x is None:
        return ""
    s = str(x)
    if len(s) > max_chars:
        s = s[:max_chars] + " …[recortado]"
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
    st.pyplot(fig)
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
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state["empresa_sel"] is None:
        cats = _listar_empresas()
        st.session_state["empresa_sel"] = cats[0] if cats else ""


def _cargar_params_empresa(nombre):
    """Al cambiar empresa: params + CAPM como en al_cambiar_empresa."""
    try:
        out = L.al_cambiar_empresa(nombre)
        # out = (ficha_html, de, kd, tax, g, beta, capital, deuda, inv, caja, nci, otros, asoc, acciones, exit_mult, rf, erp, crp, g_max)
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

    # Fallback desde catálogo
    emp = None
    if hasattr(L, "resolver_empresa"):
        emp = L.resolver_empresa(nombre)
    if emp is None:
        emp = getattr(L, "EMPRESAS", {}).get(nombre) or getattr(L, "EMPRESAS_RUNTIME", {}).get(nombre)
    if not emp:
        return
    p = emp.get("params", {})
    st.session_state["params"] = dict(p)
    st.session_state["ficha_html"] = f"<b>{nombre}</b> · {emp.get('sector','')}"
    mon = p.get("moneda") or emp.get("moneda") or "COP"
    st.session_state["rf"] = 0.12 if mon == "COP" else 0.04


def _archivo_para_logic():
    """Devuelve path temporal o None a partir del upload en sesión."""
    data = st.session_state.get("archivo_bytes")
    name = st.session_state.get("archivo_name") or "upload.xlsx"
    if not data:
        return None
    import tempfile
    suffix = ".xlsx"
    if name.lower().endswith(".csv"):
        suffix = ".csv"
    elif name.lower().endswith(".xls"):
        suffix = ".xls"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return tmp.name


def _p(key, default=0.0):
    params = st.session_state.get("params") or {}
    v = params.get(key, default)
    try:
        return float(v) if v is not None else float(default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
def main():
    _init_state()

    st.title("📊 Modelación Financiera y Riesgo")
    st.caption(
        "Proyección · DCF · Auditoría · VPN/TIR · Sector · Informe PDF · Consulta IA · "
        "**Apoyo a decisión · No es asesoría de inversión**"
    )

    # ========== SIDEBAR ==========
    with st.sidebar:
        st.header("1 · Empresa")

        # Buscar Yahoo
        with st.expander("Buscar y descargar (Yahoo Finance)", expanded=False):
            tq = st.text_input("Ticker o nombre", placeholder="AAPL · EC · ISA.CL · MSFT")
            peers = st.text_input("Peers opcionales", placeholder="MSFT,GOOGL,META")
            if st.button("Buscar y descargar", type="primary"):
                with st.spinner("Descargando desde Yahoo..."):
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
                        st.session_state["params"] = {
                            k: params_tuple[i] for i, k in enumerate(keys)
                        }
                    _cargar_params_empresa(display_name)
                    st.session_state["resultados"] = {}
                    st.success("Empresa cargada")
                    _html(html)
                    st.rerun()
                else:
                    st.error("No se pudo descargar")
                    _html(html)

        catalogo = _listar_empresas()
        if st.session_state["empresa_sel"] not in catalogo and catalogo:
            st.session_state["empresa_sel"] = catalogo[0]
        if "select_empresa" not in st.session_state or st.session_state["select_empresa"] not in catalogo:
            st.session_state["select_empresa"] = st.session_state["empresa_sel"]

        empresa = st.selectbox("Empresa a modelar", options=catalogo, key="select_empresa")
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
            with st.expander("Ficha empresa", expanded=False):
                _html(st.session_state["ficha_html"])

        st.header("2 · Estados financieros")
        up = st.file_uploader("Excel/CSV propio (opcional)", type=["xlsx", "xls", "csv"])
        if up is not None:
            st.session_state["archivo_bytes"] = up.read()
            st.session_state["archivo_name"] = up.name
            st.caption(f"Cargado: {up.name}")
        st.session_state["usar_publicos"] = st.checkbox(
            "Si no hay Excel, usar datos públicos (Yahoo / curados)",
            value=st.session_state.get("usar_publicos", True),
        )

        # Plantilla
        try:
            ruta = getattr(L, "RUTA_PLANTILLA_EEFF", None)
            if not ruta:
                ruta = L.asegurar_plantilla_excel()
            if ruta and os.path.isfile(ruta):
                with open(ruta, "rb") as f:
                    st.download_button(
                        "Descargar plantilla Excel EEFF",
                        f,
                        file_name="Plantilla_EEFF_Modelacion_Financiera.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
        except Exception as e:
            st.caption(f"Plantilla no disponible: {e}")

        st.header("3 · Parámetros del modelo")
        ek = str(empresa)[:40]
        p = st.session_state.get("params") or {}

        horizonte = st.slider("Horizonte (años)", 3, 10, 5, key=f"hor_{ek}")
        de_ratio = st.slider("D/E", 0.0, 5.0, float(p.get("de_ratio", 1.2) or 1.2), 0.01, key=f"de_{ek}")
        kd = st.slider("Kd – costo deuda", 0.0, 0.25, float(p.get("kd", 0.08) or 0.08), 0.005, key=f"kd_{ek}")
        tax = st.slider("Tasa impositiva", 0.0, 0.50, float(p.get("tax", 0.35) or 0.35), 0.01, key=f"tax_{ek}")
        g = st.slider("g – crecimiento largo plazo", 0.0, 0.08, float(p.get("g", 0.03) or 0.03), 0.005, key=f"g_{ek}")
        capex_extra = st.slider("CAPEX adicional (miles M)", 0, 8000, 0, 50, key=f"cx_{ek}")
        beta_u = st.slider("β desapalancado", 0.0, 3.0, float(p.get("beta_u", 0.5) or 0.5), 0.05, key=f"bu_{ek}")

        st.subheader("CAPM")
        rf = st.slider("rf", 0.02, 0.16, float(st.session_state.get("rf", 0.12)), 0.005, key=f"rf_{ek}")
        erp = st.slider("ERP", 0.03, 0.10, float(st.session_state.get("erp", 0.055)), 0.005, key=f"erp_{ek}")
        crp = st.slider("CRP país", 0.0, 0.05, float(st.session_state.get("crp", 0.0)), 0.005, key=f"crp_{ek}")

        st.subheader("Balance / puente")
        capital_invertido = st.number_input(
            "Capital invertido (miles M)", value=float(p.get("capital_invertido", 45000) or 0), step=100.0, key=f"ci_{ek}"
        )
        deuda_neta = st.number_input(
            "Deuda neta (miles M)", value=float(p.get("deuda_neta", 0) or 0), step=100.0, key=f"dn_{ek}"
        )
        inversion_inicial = st.number_input(
            "Inversión inicial proyecto", value=float(p.get("inversion_inicial", 0) or 0), step=10.0, key=f"ii_{ek}"
        )
        caja = st.number_input("Caja", value=float(p.get("caja", 0) or 0), step=50.0, key=f"caja_{ek}")
        nci = st.number_input("NCI", value=float(p.get("nci", 0) or 0), step=50.0, key=f"nci_{ek}")
        otros_claims = st.number_input("Otros claims", value=float(p.get("otros_claims", 0) or 0), step=50.0, key=f"oc_{ek}")
        asociados = st.number_input("Asociados / JV", value=float(p.get("asociados", 0) or 0), step=50.0, key=f"as_{ek}")
        acciones = st.number_input(
            "Acciones diluidas (millones)",
            value=float(p.get("acciones") or 0),
            step=1.0,
            key=f"acc_{ek}",
        )
        exit_multiple = st.slider(
            "Múltiplo salida EV/EBITDA",
            0.0, 40.0,
            float(p.get("exit_multiple", 9.0) or 9.0),
            0.5,
            key=f"em_{ek}",
        )
        mid_year = st.checkbox("Convención mid-year", value=True, key=f"my_{ek}")
        g_max_macro = st.slider(
            "Techo macro de g",
            0.02, 0.06,
            float(st.session_state.get("g_max_macro", 0.04)),
            0.005,
            key=f"gmax_{ek}",
        )

        st.header("4 · Conector de mercado")
        with st.expander("Yahoo / API key / manual"):
            prov = st.selectbox("Proveedor", ["yahoo", "api_key", "manual"], index=0)
            api_key = st.text_input("API key vendor", type="password")
            api_url = st.text_input("URL base vendor", placeholder="https://...")
            if st.button("Aplicar config mercado"):
                try:
                    msg = L.aplicar_config_mercado_ui(prov, api_key, api_url)
                    _html(msg)
                except Exception as e:
                    st.error(str(e))

    # ========== BODY ==========
    archivo = _archivo_para_logic()
    usar_publicos = st.session_state.get("usar_publicos", True)

    # Sensibilidad rápida
    with st.expander("⚡ Sensibilidad en vivo (WACC · g) — no reproyecta FCFF", expanded=False):
        sc1, sc2, sc3 = st.columns([1, 1, 1])
        with sc1:
            sens_wacc = st.slider("WACC sens.", 0.06, 0.18, 0.11, 0.0025, key="sens_wacc")
        with sc2:
            sens_g = st.slider("g sens.", 0.005, 0.06, 0.03, 0.0025, key="sens_g")
        with sc3:
            if st.button("Aplicar sensibilidad"):
                try:
                    html = L.sensibilidad_rapida_ui(
                        empresa, sens_wacc, sens_g, horizonte, tax,
                        deuda_neta, caja, nci, otros_claims, asociados, acciones,
                        mid_year, g_max_macro,
                    )
                    st.session_state["hero_html"] = html
                except Exception as e:
                    st.session_state["hero_html"] = f"<div>Error sensibilidad: {e}</div>"
        if st.session_state.get("hero_html"):
            _html(st.session_state["hero_html"])

    # Glosario
    with st.expander("📚 Mini-glosario financiero", expanded=False):
        try:
            _html(L.glosario_html())
        except Exception:
            st.write("Ingresos, EBITDA, EBIT, CAPEX, NWC, FCFF, WACC, ROIC, D/E, EV, Equity, VPN, TIR, Payback, g, Beta.")

    # Consulta IA
    with st.expander("🤖 Consulta asistida (modelo + mercado/web)", expanded=False):
        pregunta = st.text_area("Tu pregunta", placeholder="¿Qué es el WACC? · ¿Precio y upside? · Resumen para el comité")
        cprov = st.selectbox("Proveedor IA", ["gemini", "xai", "openai"], index=0)
        ckey = st.text_input("API key (opcional, solo esta sesión)", type="password")
        if st.button("Consultar"):
            with st.spinner("Consultando..."):
                try:
                    resp = L.asistente_consulta_financiera(
                        pregunta, empresa, api_key=ckey or None, proveedor=cprov
                    )
                    _html(resp)
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

    # ----- 7 PESTAÑAS -----
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "1 · Pronóstico",
        "2 · Escenarios DCF",
        "3 · Auditoría",
        "4 · Recomendación",
        "5 · VPN y TIR",
        "6 · Sector",
        "7 · Informe PDF",
    ])

    # TAB 1
    with tab1:
        st.subheader("Pronóstico FCFF")
        metodo = st.radio(
            "Método de proyección",
            [
                "Drivers + identidad FCFF (recomendado)",
                "ETS / Holt (suavizado exponencial)",
                "ARIMA (benchmark estadístico)",
            ],
            index=0,
        )
        if st.button("Generar proyección y Fan Chart", type="primary", key="btn1"):
            with st.spinner("Proyectando..."):
                try:
                    r = L.tab1_carga_y_pronostico(
                        empresa, archivo, horizonte, metodo, tax, usar_publicos
                    )
                    # r: info, hist, proj, fig, fig_norm?, norm_help?
                    st.session_state["resultados"]["tab1"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())
                    st.session_state["resultados"]["tab1"] = None

        r = st.session_state.get("resultados", {}).get("tab1")
        if r:
            if isinstance(r, (list, tuple)):
                if len(r) > 0:
                    _html(r[0])
                if len(r) > 1:
                    _show_df(r[1], "Historial usado")
                if len(r) > 2:
                    _show_df(r[2], "Proyección año a año")
                if len(r) > 3:
                    _show_fig(r[3], "Fan Chart FCFF")
                if len(r) > 4 and r[4] is not None:
                    _show_fig(r[4], "Atípicos (original vs tratado)")
                if len(r) > 5 and r[5]:
                    _html(r[5])

    # TAB 2
    with tab2:
        st.subheader("Escenarios DCF")
        if st.button("Simular escenarios pesimista · base · optimista", type="primary", key="btn2"):
            with st.spinner("Simulando..."):
                try:
                    r = L.tab2_simulacion_politicas(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        deuda_neta, rf, erp, crp, usar_publicos,
                        caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                    )
                    st.session_state["resultados"]["tab2"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

        r = st.session_state.get("resultados", {}).get("tab2")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Resultados por escenario")
            if len(r) > 2:
                _show_fig(r[2], "EV vs Equity")

    # TAB 3
    with tab3:
        st.subheader("Auditoría de supuestos")
        if st.button("Ejecutar auditoría", type="primary", key="btn3"):
            with st.spinner("Auditando..."):
                try:
                    r = L.tab3_auditoria_teorica(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, beta_u,
                        capital_invertido, rf, erp, crp, usar_publicos,
                    )
                    st.session_state["resultados"]["tab3"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

        r = st.session_state.get("resultados", {}).get("tab3")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Pruebas")

    # TAB 4
    with tab4:
        st.subheader("Recomendación de comité")
        if st.button("Generar recomendación", type="primary", key="btn4"):
            with st.spinner("Generando..."):
                try:
                    r = L.tab4_recomendacion(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        capital_invertido, deuda_neta, rf, erp, crp, usar_publicos,
                        caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                    )
                    st.session_state["resultados"]["tab4"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

        r = st.session_state.get("resultados", {}).get("tab4")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Indicadores de gobernanza")
            if len(r) > 2:
                _html(r[2])

    # TAB 5
    with tab5:
        st.subheader("VPN, TIR y Payback")
        if st.button("Calcular VPN / TIR / Payback", type="primary", key="btn5"):
            with st.spinner("Calculando..."):
                try:
                    r = L.tab5_vpn_tir(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        inversion_inicial, rf, erp, crp, usar_publicos,
                    )
                    st.session_state["resultados"]["tab5"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

        r = st.session_state.get("resultados", {}).get("tab5")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Detalle año a año")
            if len(r) > 2:
                _show_fig(r[2], "Flujos y recuperación")

    # TAB 6
    with tab6:
        st.subheader("Comparación sectorial")
        if st.button("Generar ranking sectorial", type="primary", key="btn6"):
            with st.spinner("Comparando..."):
                try:
                    r = L.tab6_comparacion_sectorial(empresa)
                    st.session_state["resultados"]["tab6"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

        r = st.session_state.get("resultados", {}).get("tab6")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Tabla comparativa")
            if len(r) > 2:
                _show_fig(r[2], "Gráficos del sector")

    # TAB 7
    with tab7:
        st.subheader("Informe ejecutivo y PDF")
        if st.button("Generar informe y PDF", type="primary", key="btn7"):
            with st.spinner("Generando informe..."):
                try:
                    r = L.tab7_informe_ejecutivo(
                        empresa, archivo, horizonte, de_ratio, kd, tax, g, capex_extra, beta_u,
                        capital_invertido, deuda_neta, inversion_inicial, rf, erp, crp, usar_publicos,
                        caja, nci, otros_claims, asociados, acciones, exit_multiple, mid_year, g_max_macro,
                    )
                    st.session_state["resultados"]["tab7"] = r
                except Exception as e:
                    st.error(str(e))
                    st.code(traceback.format_exc())

        r = st.session_state.get("resultados", {}).get("tab7")
        if r and isinstance(r, (list, tuple)):
            if len(r) > 0:
                _html(r[0])
            if len(r) > 1:
                _show_df(r[1], "Resumen de indicadores")
            if len(r) > 2:
                _show_fig(r[2], "Panel gráfico")
            if len(r) > 3 and r[3]:
                pdf_path = r[3]
                if isinstance(pdf_path, str) and os.path.isfile(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "Descargar informe PDF",
                            f,
                            file_name=f"informe_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                        )
                else:
                    st.caption(f"PDF: {pdf_path}")

    st.divider()
    st.caption(
        "Herramienta pedagógica · Lógica del modelo original · "
        "No es feed oficial BVC ni asesoría de inversión."
    )


if __name__ == "__main__":
    main()
