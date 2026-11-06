"""Presentación ejecutiva ISA — narrativa editorial alimentada por el snapshot oficial."""
from __future__ import annotations

import math
import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from isa_snapshot_store import fetch_latest_snapshot

st.set_page_config(
    page_title="ISA | Investor Presentation",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Playfair+Display:wght@500;600;700&display=swap');
:root{--ink:#07121d;--ink2:#0b1d29;--paper:#f0eee7;--muted:#9eafb4;--teal:#72e0c0;--line:rgba(210,231,224,.17);--gold:#d5bd8a}
html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--ink)!important;color:var(--paper)!important;font-family:'Manrope',sans-serif}
[data-testid="stHeader"]{background:transparent}
[data-testid="stToolbar"]{right:1rem}
.block-container{max-width:1320px;padding:1.25rem 3.2rem 5rem}
h1,h2,h3{color:var(--paper)!important;font-family:'Manrope',sans-serif;letter-spacing:-.045em}
h1{font-size:clamp(3.2rem,7vw,6.6rem)!important;line-height:.98!important;font-weight:700!important}
h2{font-size:clamp(2rem,4vw,3.6rem)!important;line-height:1.05!important;font-weight:700!important}
h3{font-size:1.25rem!important;font-weight:650!important}
p,li{color:#c3d0cc;line-height:1.75}
a{color:var(--teal)!important}
hr{border-color:var(--line)!important;margin:3rem 0}
[data-testid="stMetric"]{background:transparent;border:0;border-top:1px solid var(--line);padding:1rem .2rem .5rem}
[data-testid="stMetricLabel"]{color:#91a9a8!important;text-transform:uppercase;letter-spacing:.13em;font-size:.66rem!important}
[data-testid="stMetricValue"]{font-family:'DM Mono',monospace;color:var(--paper)!important;font-size:clamp(1.4rem,2.6vw,2.3rem)!important}
[data-testid="stMetricDelta"]{font-family:'DM Mono',monospace}
.stButton>button{border:1px solid rgba(114,224,192,.5);background:rgba(114,224,192,.1);color:var(--teal);border-radius:2px;padding:.55rem 1.1rem;letter-spacing:.04em}
.stButton>button:hover{border-color:var(--teal);background:rgba(114,224,192,.18);color:white}
[data-testid="stDataFrame"]{border:1px solid var(--line)}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:4px;background:rgba(255,255,255,.025)}
.eyebrow{font-family:'DM Mono',monospace;color:var(--teal);font-size:.72rem;letter-spacing:.2em;text-transform:uppercase}
.cover{position:relative;overflow:hidden;min-height:490px;padding:clamp(2rem,6vw,5.5rem);border:1px solid rgba(114,224,192,.24);background:radial-gradient(ellipse at 82% 42%,rgba(26,113,102,.4),transparent 35%),linear-gradient(120deg,#0b1b27 0%,#102a35 58%,#0b252b 100%);margin:1rem 0 2rem}
.cover:after{content:"";position:absolute;width:410px;height:410px;right:-80px;top:45px;border:1px solid rgba(114,224,192,.18);border-radius:50%;box-shadow:0 0 0 38px rgba(114,224,192,.035),0 0 0 82px rgba(114,224,192,.025),0 0 0 128px rgba(114,224,192,.018)}
.cover-inner{position:relative;z-index:1;max-width:850px}
.cover-kicker{font-family:'DM Mono',monospace;color:var(--teal);letter-spacing:.2em;font-size:.76rem;text-transform:uppercase;margin-bottom:2rem}
.cover-title{font-family:'Playfair Display',serif;font-size:clamp(3.3rem,7vw,6.8rem);line-height:.96;letter-spacing:-.04em;color:#f3f0e8;margin:0 0 1.5rem}
.cover-sub{font-size:1.05rem;color:#b9cfca;max-width:650px;line-height:1.8}
.cover-foot{display:flex;gap:2rem;flex-wrap:wrap;margin-top:3.2rem;font-family:'DM Mono',monospace;color:#91aaa6;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase}
.chapter{padding-top:1rem;margin-top:3rem}
.chapter-no{font-family:'DM Mono',monospace;color:var(--teal);font-size:.72rem;letter-spacing:.2em;margin-bottom:.8rem}
.chapter-lead{font-size:1.1rem;color:#b7c8c2;max-width:820px;line-height:1.8}
.pullquote{border-left:2px solid var(--teal);padding:1rem 1.4rem;margin:1.5rem 0;background:linear-gradient(90deg,rgba(114,224,192,.08),transparent);font-family:'Playfair Display',serif;font-size:1.35rem;color:#e7eee8}
.kpi-label{font-family:'DM Mono',monospace;font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:#8da8a3}
.kpi-value{font-family:'DM Mono',monospace;font-size:1.6rem;color:#f1f0e9;margin-top:.35rem}
.kpi-note{font-size:.78rem;color:#92a6a2;margin-top:.3rem}
.kpi-box{border-top:1px solid var(--line);padding:1rem .2rem;min-height:105px}
.source-note{font-family:'DM Mono',monospace;color:#7f9692;font-size:.68rem;line-height:1.7}
.section-rule{height:1px;background:linear-gradient(90deg,var(--teal),rgba(114,224,192,0));margin:1.4rem 0 2rem}
[data-testid="stCaptionContainer"]{color:#819994}
nav{display:none}
@media(max-width:760px){.block-container{padding:1rem 1.1rem 3rem}.cover{min-height:420px}.cover:after{right:-240px;opacity:.6}.cover-foot{gap:.8rem}}
</style>
""", unsafe_allow_html=True)


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.environ.get(name, "")).strip()


def _num(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _money(value, decimals=0):
    n = _num(value)
    if n is None:
        return "N/D"
    return "COP {:,.{d}f}".format(n, d=decimals)


def _pct(value):
    n = _num(value)
    return "N/D" if n is None else "{:.2%}".format(n)


def _text(value, fallback="No disponible"):
    return fallback if value is None or value == "" else str(value)


def _section(number, kicker, title, lead=None):
    st.markdown(
        f'<div class="chapter"><div class="chapter-no">{number} / {kicker}</div><h2>{title}</h2>'
        + (f'<div class="chapter-lead">{lead}</div>' if lead else "")
        + '<div class="section-rule"></div></div>',
        unsafe_allow_html=True,
    )


def _metric_row(items):
    cols = st.columns(len(items))
    for col, (label, value, note) in zip(cols, items):
        with col:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>',
                unsafe_allow_html=True,
            )


def _load_snapshot():
    url, anon, token = (_secret("SUPABASE_URL"), _secret("SUPABASE_ANON_KEY"), _secret("ISA_PRESENTATION_TOKEN"))
    if not all((url, anon, token)):
        st.error("Conexión pendiente: configura SUPABASE_URL, SUPABASE_ANON_KEY e ISA_PRESENTATION_TOKEN en los secrets de esta app.")
        st.stop()
    try:
        record = fetch_latest_snapshot(supabase_url=url, anon_key=anon, presentation_token=token)
    except Exception as exc:
        st.error("No fue posible recuperar la última valoración publicada.")
        st.caption(str(exc))
        st.stop()
    if not record:
        st.warning("Aún no hay una valoración ISA publicada. Ejecuta la valoración en la aplicación principal y publícala desde la pestaña correspondiente.")
        st.stop()
    return record


record = _load_snapshot()
payload = record.get("payload") or {}
m = payload.get("metrics") or {}
assumptions = m.get("supuestos") or {}
published = _text(record.get("published_at") or payload.get("published_at_client"))
company = _text(record.get("company_name") or m.get("empresa"), "ISA")
ticker = _text(record.get("ticker"), "ISA")
currency = _text(m.get("moneda"), "COP")
unit = _text(m.get("unidad_modelo"), "unidad registrada por el modelo")
vps = m.get("vps_modelo")
price = m.get("precio_mercado_moneda_modelo")
if price is None:
    price = m.get("precio_mercado")
upside = m.get("upside")
ev = m.get("val_ev")
equity = m.get("val_equity")
wacc = m.get("wacc_calc")
g = m.get("g_usada")
decision = _text(payload.get("decision_text") or m.get("decision_modelo"), "La corrida no incluye una conclusión textual.")
memo = payload.get("memo") or ""

# Cover: editorial, presentation-first; no dashboard navigation or tabs.
st.markdown(
    f'<div class="cover"><div class="cover-inner">'
    f'<div class="cover-kicker">INVESTMENT CASE · {ticker} · {currency}</div>'
    f'<div class="cover-title">{company}<br>valor, riesgo<br>y perspectiva.</div>'
    f'<div class="cover-sub">Una lectura ejecutiva de la valoración fundamental de la compañía. '
    f'Los resultados y supuestos de esta presentación provienen de la última corrida publicada en Modelación Financiera.</div>'
    f'<div class="cover-foot"><span>Investor presentation</span><span>Snapshot: {published}</span><span>Confidencial · Uso académico</span></div>'
    f'</div></div>',
    unsafe_allow_html=True,
)
top1, top2 = st.columns([5, 1])
with top1:
    st.markdown('<div class="source-note">DOCUMENTO VIVO · LOS DATOS SE ACTUALIZAN DESDE LA VALORACIÓN CENTRAL · NO EXISTE RECÁLCULO EN ESTA VISTA</div>', unsafe_allow_html=True)
with top2:
    if st.button("↻ Sincronizar"):
        st.rerun()

# 01 — thesis and decision framing
_section("01", "INVESTMENT THESIS", "La decisión en una mirada",
         "El punto de partida es comparar el valor fundamental estimado por el modelo con la referencia de mercado, sin separar el resultado de sus supuestos.")
_metric_row([
    ("Valor estimado / acción", _money(vps), "Resultado de la corrida publicada"),
    ("Precio de mercado", _money(price), _text(m.get("fecha_precio"), "Fecha no registrada")),
    ("Potencial vs. mercado", _pct(upside), "Upside / downside calculado por el motor"),
    ("WACC · g", f"{_pct(wacc)} · {_pct(g)}", "Costo de capital · crecimiento perpetuo"),
])
st.markdown(f'<div class="pullquote">{decision}</div>', unsafe_allow_html=True)
if m.get("fuente_precio") or m.get("fuente_mercado"):
    st.markdown('<div class="source-note">REFERENCIA DE MERCADO · ' + _text(m.get("fuente_precio") or m.get("fuente_mercado")) + '</div>', unsafe_allow_html=True)

# 02 — valuation story
_section("02", "VALUATION", "Del flujo de caja al valor",
         "El DCF traduce los flujos de caja libre proyectados y su valor terminal a valor presente. Esta sección expone los resultados que guardó el motor, no una estimación paralela.")
_metric_row([
    ("Enterprise value", _money(ev), "Valor de las operaciones"),
    ("Equity value", _money(equity), "Valor atribuible al patrimonio"),
    ("Valor por acción", _money(vps), "Resultado por título"),
])
fcff = m.get("fcff_proy") or []
if isinstance(fcff, list) and fcff:
    values = [_num(x) for x in fcff]
    if any(x is not None for x in values):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[f"Año {i+1}" for i in range(len(values))], y=values,
            marker=dict(color=values, colorscale=[[0, "#356d70"], [1, "#79dfbf"]], showscale=False),
            hovertemplate="%{x}<br>FCFF: %{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            template="plotly_dark", height=390, title="Flujo de caja libre proyectado",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.015)",
            font=dict(family="Manrope", color="#d6e2dc"),
            margin=dict(l=12,r=12,t=55,b=12),
            xaxis=dict(title="", showgrid=False), yaxis=dict(title=f"{currency} · {unit}", gridcolor="rgba(255,255,255,.08)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("La instantánea no contiene una serie FCFF utilizable; no se construye una proyección sustituta.")

bridge = m.get("bridge")
if isinstance(bridge, dict) and bridge:
    st.markdown("#### Puente de valor empresarial a patrimonio")
    bridge_rows = [{"Concepto": str(k).replace("_", " ").capitalize(), "Valor": v} for k, v in bridge.items()]
    st.dataframe(pd.DataFrame(bridge_rows), hide_index=True, use_container_width=True)
else:
    st.caption("El detalle del puente EV → patrimonio no fue incluido en la instantánea publicada.")

# 03 — assumptions, interpretation and risk
_section("03", "MODEL DRIVERS", "Qué sostiene el resultado",
         "El valor no es un número aislado: depende del costo de capital, del crecimiento de largo plazo y de la capacidad operativa proyectada.")
assumption_items = [
    ("WACC", _pct(wacc)), ("Crecimiento perpetuo", _pct(g)),
    ("Ke", _pct(m.get("ke_calc"))), ("Beta sectorial βu", _text(m.get("beta_industria_u"))),
    ("Margen EBITDA proyectado", _pct(m.get("margen_ebitda_proy"))), ("ROIC observado", _pct(m.get("roic_observado"))),
    ("Tasa libre de riesgo", _pct(assumptions.get("rf"))), ("Prima de riesgo", _pct(assumptions.get("erp"))),
    ("Costo de deuda", _pct(assumptions.get("kd"))), ("Tasa fiscal", _pct(assumptions.get("tax"))),
    ("Beta desapalancada", _text(assumptions.get("beta_u"))), ("Deuda / patrimonio", _text(m.get("de_ratio"))),
    ("Horizonte explícito", _text(assumptions.get("horizonte", m.get("horizonte")))),
]
left, right = st.columns([1.15, .85], gap="large")
with left:
    st.markdown("#### Parámetros de la corrida")
    st.dataframe(pd.DataFrame(assumption_items, columns=["Variable", "Valor"]), hide_index=True, use_container_width=True)
with right:
    st.markdown("#### Lectura de riesgo y calidad")
    st.markdown(f'<div class="kpi-box"><div class="kpi-label">Nivel de calidad</div><div class="kpi-value">{_text(m.get("nivel_calidad"))}</div><div class="kpi-note">Clasificación registrada por el motor</div></div>', unsafe_allow_html=True)
    for label, key in [("Alertas del modelo", "alertas_modelo"), ("Vetos de calidad", "vetos_calidad"), ("Soportes", "soportes_modelo")]:
        items = m.get(key) or []
        with st.expander(f"{label} · {len(items) if isinstance(items, list) else 0}"):
            if isinstance(items, list) and items:
                for item in items:
                    st.markdown(f"- {item}")
            else:
                st.caption("No hay elementos registrados en esta categoría.")

# 04 — decision panel
_section("04", "CONCLUSION", "Valor frente a mercado",
         "La lectura final debe considerar tanto la diferencia entre valor estimado y precio como la sensibilidad del resultado a los supuestos.")
left, right = st.columns([1, 1], gap="large")
with left:
    st.markdown("#### Referencia de precio")
    if _num(vps) is not None and _num(price) is not None:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[_num(vps), _num(price)], y=["Valor estimado", "Precio de mercado"],
            orientation="h", marker_color=["#72e0c0", "#607a88"],
            text=[_money(vps), _money(price)], textposition="outside",
            hovertemplate="%{y}: %{x:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            template="plotly_dark", height=230, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.015)",
            font=dict(family="Manrope", color="#d6e2dc"), margin=dict(l=10,r=95,t=15,b=15),
            xaxis=dict(visible=False), yaxis=dict(title="", showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No hay datos suficientes para comparar valor estimado y precio de mercado.")
with right:
    st.markdown("#### Conclusión registrada")
    st.markdown(f'<div class="pullquote">{decision}</div>', unsafe_allow_html=True)
    st.caption("No se genera recomendación automática cuando faltan datos o soportes en la corrida.")

# 05 — data room / audit trail
_section("05", "DATA ROOM", "Fuentes, fecha y trazabilidad",
         "Esta sala conserva la procedencia de la información. Para auditar el resultado, contrasta la instantánea con la corrida de la aplicación principal.")
meta = [
    ("Compañía", company), ("Ticker", ticker), ("Publicación", published),
    ("Versión del modelo", _text(record.get("model_version"))),
    ("Moneda", currency), ("Unidad", unit),
    ("Fuente financiera", _text(m.get("fuente_financiera"))),
    ("Fuente de mercado", _text(m.get("fuente_mercado"))),
    ("Fecha del precio", _text(m.get("fecha_precio"))),
    ("Fuente del precio", _text(m.get("fuente_precio"))),
]
meta_cols = st.columns(2)
for i, (label, value) in enumerate(meta):
    with meta_cols[i % 2]:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">{label}</div><div style="color:#e7eee8;margin-top:.4rem">{value}</div></div>', unsafe_allow_html=True)
with st.expander("Memo de la valoración original"):
    st.write(memo or "La corrida no contiene un memo.")
with st.expander("Datos completos publicados (JSON)"):
    st.json(m)

st.markdown("---")
st.markdown(
    '<div class="source-note">ISA · INVESTMENT PRESENTATION<br>'
    'Fuente primaria: última instantánea publicada por Modelación Financiera vía Supabase. '
    'Esta página es una capa de presentación: no modifica supuestos, no recalcula el DCF y no sustituye la verificación de fuentes.<br>'
    'Material académico y de apoyo al análisis; no constituye recomendación personalizada de inversión.</div>',
    unsafe_allow_html=True,
)
