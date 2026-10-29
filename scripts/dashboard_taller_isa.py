"""Dashboard interactivo del Taller ISA 2026 (bonificación): cambia drivers y políticas y ve el resultado al instante.

Ejecutar desde la raíz del repositorio:
    streamlit run scripts/dashboard_taller_isa.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.taller_isa import (  # noqa: E402
    DECISION_THRESHOLDS, POLICIES, SCENARIO_ORDER, cost_of_capital, evaluate, historical_drivers,
    load_isa, monte_carlo, policy_impact, scenario_params,
)

st.set_page_config(page_title="Taller ISA 2026 — Escenarios y políticas", layout="wide")


@st.cache_data
def _isa():
    return load_isa()


isa = _isa()
drivers = historical_drivers(isa)
price = isa["mercado"]["precio_ref"]

st.title("Taller ISA 2026 — pronóstico, escenarios y políticas")
st.caption(
    f"Montos en miles de millones de COP. Datos con corte {isa.get('corte_catalogo')}; precio de referencia "
    f"COP {price:,.0f} ({isa['mercado'].get('fecha_precio_ref')}). Supuestos de escenarios y políticas: hipótesis "
    "académicas editables, no guía oficial de ISA."
)

with st.sidebar:
    st.header("1 · Escenario de partida")
    scenario = st.selectbox("Escenario", SCENARIO_ORDER, index=SCENARIO_ORDER.index("Base"))
    p0 = scenario_params(isa, scenario)
    st.header("2 · Ajuste fino de drivers")
    growth = st.slider("Crecimiento de ingresos (%)", -5.0, 15.0, round(p0["growth"] * 100, 2), 0.25) / 100
    margin = st.slider("Margen EBIT (%)", 25.0, 60.0, round(p0["ebit_margin"] * 100, 2), 0.25) / 100
    intensity = st.slider("Intensidad CAPEX de expansión (COP por COP de nuevo ingreso)", 0.2, 1.5,
                          round(p0["capex_intensity"], 2), 0.01)
    nwc = st.slider("NWC / ingresos (%)", 10.0, 40.0, round(p0["nwc_ratio"] * 100, 2), 0.25) / 100
    wacc_delta = st.slider("Ajuste al WACC CAPM (pp)", -3.0, 4.0, round(p0["wacc_delta"] * 100, 2), 0.25) / 100
    g = st.slider("g terminal (%)", 2.0, 7.0, round(p0["g_terminal"] * 100, 2), 0.25) / 100
    tax = st.slider("Tasa de impuestos (%)", 15.0, 40.0, round(p0["tax"] * 100, 1), 0.5) / 100
    st.header("3 · Política")
    policy = st.radio("Simular", ["Sin política"] + list(POLICIES))

overrides = {"growth": growth, "ebit_margin": margin, "capex_intensity": intensity, "nwc_ratio": nwc,
             "wacc_delta": wacc_delta, "g_terminal": g, "tax": tax}
wacc = cost_of_capital(isa, wacc_delta, tax)["wacc"]
if wacc - g < 0.01:
    st.error(f"Incoherente: WACC {wacc:.2%} debe superar g {g:.2%} en al menos 1 pp. Ajusta los controles.")
    st.stop()

pol = None if policy == "Sin política" else policy
base = evaluate(isa, scenario, overrides=overrides)
res = evaluate(isa, scenario, pol, overrides=overrides) if pol else base
v, vb = res["valuation"], base["valuation"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("WACC", f"{wacc:.2%}")
c2.metric("EV", f"{v['ev']:,.0f}", f"{v['ev'] - vb['ev']:+,.0f}" if pol else None)
c3.metric("Valor por acción (COP)", f"{v['valor_por_accion']:,.0f}", f"{v['valor_por_accion'] / price - 1:+.1%} vs precio")
c4.metric("TIR implícita al precio", f"{res['tir_implicita']:.2%}" if res["tir_implicita"] == res["tir_implicita"] else "N/D")
c5.metric("Máx. deuda neta/EBITDA", f"{res['max_deuda_ebitda']:.2f}x",
          "sobre covenant" if res["max_deuda_ebitda"] > DECISION_THRESHOLDS["covenant_deuda_neta_ebitda"] else "dentro",
          delta_color="inverse")

if pol:
    st.info(f"**Regla:** {POLICIES[pol]['regla']}")

left, right = st.columns([3, 2])
with left:
    st.subheader("FCFF proyectado")
    df = pd.DataFrame({
        "Año": [r["año"] for r in base["rows"] if not r["terminal"]],
        "Sin política": [r["fcff"] for r in base["rows"] if not r["terminal"]],
    })
    if pol:
        df[pol] = [r["fcff"] for r in res["rows"] if not r["terminal"]]
    st.bar_chart(df.set_index("Año"))
    st.subheader("Detalle de la proyección")
    cols = ["año", "ingresos", "margen_ebit", "ebit", "nopat", "depreciacion", "capex", "delta_nwc", "fcff"]
    st.dataframe(pd.DataFrame(res["rows"])[cols].round(3), hide_index=True, use_container_width=True)
with right:
    st.subheader("Puente de valor")
    st.dataframe(pd.DataFrame({
        "Concepto": ["VP FCFF 2026–2030", "VP valor terminal", "EV", "− Deuda neta", "− Minoritarios",
                     "+ Asociadas", "Patrimonio", "Capitalización de mercado", "VPN del inversionista"],
        "Valor": [v["vp_fcff_explicito"], v["vp_valor_terminal"], v["ev"], -isa["puente"]["deuda_neta"],
                  -isa["puente"]["nci"], isa["puente"]["asociados"], v["patrimonio"],
                  v["capitalizacion_mercado"], v["vpn_inversionista"]],
    }).round(0), hide_index=True, use_container_width=True)
    st.subheader("Trayectoria de apalancamiento")
    st.line_chart(pd.DataFrame(res["leverage"]).set_index("año")[["deuda_neta_ebitda"]])

st.subheader("Políticas en los cuatro escenarios predefinidos")
impacts = [policy_impact(isa, s, p) for p in POLICIES for s in SCENARIO_ORDER]
st.dataframe(pd.DataFrame(impacts)[["politica", "escenario", "regla_activa", "delta_vpn", "delta_valor_por_accion",
                                    "lectura_tir", "anios_sobre_covenant_sin", "anios_sobre_covenant_con"]].round(1),
             hide_index=True, use_container_width=True)

with st.expander("Monte Carlo (escenario Base)"):
    n = st.number_input("Simulaciones", 200, 10000, 1000, 200)
    if st.button("Ejecutar Monte Carlo"):
        mc = monte_carlo(isa, n=int(n))
        a, b, c = st.columns(3)
        a.metric("Mediana valor/acción", f"{mc['p50']:,.0f}", f"P5 {mc['p5']:,.0f} · P95 {mc['p95']:,.0f}")
        b.metric("P(valor > precio)", f"{mc['prob_valor_mayor_precio']:.1%}")
        c.metric("P(ΔVPN > 0) P1 / P2", f"{mc['prob_dvpn_p1_pos']:.0%} / {mc['prob_dvpn_p2_pos']:.0%}")
        hist = pd.Series([s["valor_por_accion"] for s in mc["simulaciones"]])
        bins = pd.cut(hist, 30).value_counts().sort_index()
        st.bar_chart(pd.DataFrame({"frecuencia": bins.values}, index=[f"{i.mid:,.0f}" for i in bins.index]))

st.caption(f"Drivers históricos: CAGR ingresos {drivers['growth']:.2%} · margen EBIT 2025 {drivers['ebit_margin']:.2%} "
           f"(promedio 2023–2025 {drivers['ebit_margin_avg']:.2%}) · intensidad CAPEX {drivers['capex_intensity']:.2f} · "
           f"NWC/ingresos {drivers['nwc_ratio']:.2%}.")
