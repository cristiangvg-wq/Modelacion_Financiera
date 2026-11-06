"""ISA Investment Intelligence Room: presentation app independent and driven by the main app snapshot."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from isa_snapshot_store import fetch_latest_snapshot

st.set_page_config(
    page_title="ISA | Investment Intelligence Room",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 12% 0%,#10313a 0%,transparent 32%),radial-gradient(ellipse at 95% 5%,#172747 0%,transparent 30%),#070B14;color:#F3F7FC;font-family:'Manrope',sans-serif}
.block-container{max-width:1450px;padding-top:2rem;padding-bottom:4rem}
h1,h2,h3{font-family:'Manrope',sans-serif;letter-spacing:-.04em;color:#F5F8FC}
h1{font-size:2.45rem!important;font-weight:800!important}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(22,37,55,.9),rgba(12,22,36,.8));border:1px solid #2b4058;border-radius:16px;padding:15px}
[data-testid="stMetricLabel"]{color:#9FB0C5!important;text-transform:uppercase;letter-spacing:.09em;font-size:.68rem!important}
[data-testid="stMetricValue"]{font-family:'DM Mono',monospace;color:#F7FAFF!important}
.hero{padding:32px 36px;border:1px solid #31546a;border-radius:22px;background:linear-gradient(120deg,rgba(10,35,49,.96),rgba(18,37,64,.88) 58%,rgba(10,91,84,.45));box-shadow:0 22px 65px #0007;margin-bottom:20px}
.hero p{max-width:820px;color:#b8d5df;font-size:1.02rem}
.eyebrow{color:#57e3c4;font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;font-weight:800}
.panel{background:linear-gradient(145deg,rgba(18,31,48,.92),rgba(10,19,31,.92));border:1px solid #263b51;border-radius:16px;padding:18px 20px;margin:8px 0}
.panel-title{color:#8da6bc;text-transform:uppercase;letter-spacing:.1em;font-size:.7rem;font-weight:800}
.callout{border-left:3px solid #42e3c1;padding:12px 15px;background:#0e292b;border-radius:0 10px 10px 0;color:#d9fff5}
.caption{color:#8da0b4;font-size:.78rem}
hr{border-color:#23364b}
</style>
""", unsafe_allow_html=True)


def _secret(name: str, env_name: str | None = None) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.environ.get(env_name or name, "")).strip()


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _money(value, decimals=0):
    number = _number(value)
    return "N/D" if number is None else "COP {:,.{d}f}".format(number, d=decimals)


def _percent(value):
    number = _number(value)
    return "N/D" if number is None else "{:.2%}".format(number)


def _render_snapshot():
    url = _secret("SUPABASE_URL")
    anon = _secret("SUPABASE_ANON_KEY")
    token = _secret("ISA_PRESENTATION_TOKEN")
    if not url or not anon or not token:
        st.error("La presentación aún no está conectada. Faltan los secrets de Supabase.")
        st.markdown("Sigue la guía de configuración incluida en el repositorio: docs/CONFIGURAR_PRESENTACION_ISA_SUPABASE.md.")
        st.stop()
    try:
        record = fetch_latest_snapshot(supabase_url=url, anon_key=anon, presentation_token=token)
    except Exception as exc:
        st.error("No fue posible consultar la valoración publicada.")
        st.warning(str(exc))
        st.caption("No se muestran cifras de respaldo ni se ejecuta un cálculo alternativo.")
        st.stop()
    if not record:
        st.warning("Todavía no existe una valoración ISA publicada desde la aplicación principal.")
        st.markdown("Abre Modelación Financiera, ejecuta la pestaña 4 para ISA y vuelve a esta página.")
        st.stop()
    return record


st.markdown('<div class="eyebrow">ISA · INTERCONEXIÓN ELÉCTRICA / INVESTMENT INTELLIGENCE ROOM</div>', unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>ISA: infraestructura crítica,<br>valor bajo escrutinio.</h1><p>Presentación ejecutiva conectada a la última valoración real publicada por Modelación Financiera. Esta sala no recalcula el DCF: conserva la misma corrida, los mismos supuestos y la misma fecha de valoración.</p></div>', unsafe_allow_html=True)

if st.button("↻ Actualizar valoración", type="primary"):
    st.rerun()

record = _render_snapshot()
payload = record.get("payload") or {}
metrics = payload.get("metrics") or {}
published = record.get("published_at") or payload.get("published_at_client") or "N/D"
company = record.get("company_name") or metrics.get("empresa") or "ISA"
ticker = record.get("ticker", "ISA")

st.caption("Fuente: pestaña 4 de Modelación Financiera · {} · publicado: {}".format(company, published))
if metrics.get("fuente_valoracion"):
    st.caption("Motor: " + str(metrics["fuente_valoracion"]))

vps = metrics.get("vps_modelo")
price = metrics.get("precio_mercado_moneda_modelo")
if price is None:
    price = metrics.get("precio_mercado")
upside = metrics.get("upside")
ev = metrics.get("val_ev")
equity = metrics.get("val_equity")
wacc = metrics.get("wacc_calc")
g = metrics.get("g_usada")

tabs = st.tabs(["01 · Tesis y mercado", "02 · Valoración DCF", "03 · Supuestos y riesgos", "04 · Data Room"])

with tabs[0]:
    st.markdown("### La valoración publicada")
    a, b, c, d = st.columns(4)
    a.metric("Valor por acción", _money(vps), _percent(upside) + " vs. mercado" if _number(upside) is not None else None)
    b.metric("Precio de mercado", _money(price))
    c.metric("Enterprise Value", _money(ev) + " mil M" if _number(ev) is not None else "N/D")
    d.metric("WACC / g", _percent(wacc) + " / " + _percent(g))
    st.markdown('<div class="callout">La tesis de inversión debe leerse desde la valoración aprobada en la aplicación principal. El precio de referencia, los supuestos y los resultados que aparecen aquí pertenecen a esa misma ejecución.</div>', unsafe_allow_html=True)
    st.markdown("### Decisión del modelo")
    decision = payload.get("decision_text") or metrics.get("decision_modelo") or "No se registró una decisión textual."
    st.write(decision)
    if metrics.get("fecha_precio"):
        st.caption("Fecha del precio de mercado: " + str(metrics["fecha_precio"]))
    if metrics.get("fuente_precio"):
        st.caption("Fuente del precio: " + str(metrics["fuente_precio"]))

with tabs[1]:
    st.markdown("### Del negocio al valor")
    a, b, c = st.columns(3)
    a.metric("Enterprise Value", _money(ev) + " mil M" if _number(ev) is not None else "N/D")
    b.metric("Equity Value", _money(equity) + " mil M" if _number(equity) is not None else "N/D")
    c.metric("Valor por acción", _money(vps))
    fcff = metrics.get("fcff_proy") or []
    if isinstance(fcff, list) and fcff:
        values = [_number(x) for x in fcff]
        frame = pd.DataFrame({"Periodo": ["t={}".format(i + 1) for i in range(len(values))], "FCFF": values})
        fig = go.Figure(go.Bar(x=frame["Periodo"], y=frame["FCFF"], name="FCFF proyectado"))
        fig.update_layout(template="plotly_dark", title="FCFF de la corrida publicada", height=380,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(11,22,36,.7)",
                          font=dict(color="#dce8f4"), yaxis_title="Miles de millones · moneda del modelo")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("La corrida publicada no contiene una serie FCFF disponible.")
    st.markdown("### Puente EV → patrimonio")
    bridge = metrics.get("bridge")
    if isinstance(bridge, dict):
        st.json(bridge)
    else:
        st.info("No se guardó el detalle del puente en esta instantánea.")
    st.caption("Los importes se muestran con las unidades y moneda registradas por el motor original. No se recalculan ni se convierten aquí.")

with tabs[2]:
    st.markdown("### Supuestos de la valoración")
    assumptions = metrics.get("supuestos") or {}
    rows = [
        ("WACC calculado", _percent(wacc)),
        ("Crecimiento perpetuo utilizado (g)", _percent(g)),
        ("Ke", _percent(metrics.get("ke_calc"))),
        ("Beta industria desapalancada", metrics.get("beta_industria_u")),
        ("ROIC de referencia", _percent(metrics.get("roic_observado"))),
        ("Margen EBITDA proyectado", _percent(metrics.get("margen_ebitda_proy"))),
        ("Horizonte explícito", assumptions.get("horizonte", metrics.get("horizonte"))),
        ("Tasa libre de riesgo", _percent(assumptions.get("rf"))),
        ("Prima de riesgo de mercado", _percent(assumptions.get("erp"))),
        ("Costo de deuda", _percent(assumptions.get("kd"))),
        ("Tasa fiscal", _percent(assumptions.get("tax"))),
        ("Beta desapalancada", assumptions.get("beta_u")),
        ("Deuda / patrimonio", metrics.get("de_ratio")),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Variable", "Valor"]), hide_index=True, use_container_width=True)
    for title, key in [("Alertas del modelo", "alertas_modelo"), ("Vetos de calidad", "vetos_calidad"), ("Soportes del modelo", "soportes_modelo")]:
        items = metrics.get(key) or []
        with st.expander(title):
            if items:
                for item in items:
                    st.write("- " + str(item))
            else:
                st.write("No se registraron elementos en esta categoría.")
    st.caption("Los supuestos son los de la valoración publicada; esta presentación no ofrece controles para modificarlos.")

with tabs[3]:
    st.markdown("### Trazabilidad y calidad")
    st.write("**Empresa:** " + str(company))
    st.write("**Ticker:** " + str(ticker))
    st.write("**Versión del motor:** " + str(record.get("model_version", "N/D")))
    st.write("**Fecha de publicación:** " + str(published))
    st.write("**Nivel de calidad:** " + str(metrics.get("nivel_calidad", "N/D")))
    st.write("**Fuente financiera:** " + str(metrics.get("fuente_financiera", "N/D")))
    st.write("**Fuente de mercado:** " + str(metrics.get("fuente_mercado", "N/D")))
    st.write("**Moneda del modelo:** " + str(metrics.get("moneda", "N/D")))
    st.write("**Unidad:** " + str(metrics.get("unidad_modelo", "N/D")))
    with st.expander("Memo completo de la pestaña 4"):
        st.write(payload.get("memo") or "No se registró memo.")
    with st.expander("Métricas canónicas publicadas (JSON)"):
        st.json(metrics)
    kpis = payload.get("kpis")
    if isinstance(kpis, list) and kpis:
        st.markdown("### KPIs de la corrida")
        st.dataframe(pd.DataFrame(kpis), hide_index=True, use_container_width=True)

st.divider()
st.caption("Herramienta académica y de apoyo a decisiones. No constituye recomendación personalizada de inversión. Los datos son una instantánea de la última valoración ISA publicada; verifica fecha, fuentes y supuestos antes de tomar decisiones.")
