"""Pestaña 10 — Taller evaluativo 2026: tablero interactivo de los bloques A–E.

Capa de presentación únicamente: todos los cálculos vienen de ``scripts/taller_isa.calcular_modelo`` (el mismo
modelo que genera el PDF del taller), de modo que pantalla, PDF y CSV muestran las mismas cifras.

Estructura (enunciado del taller, sección 4):
  A. Pronóstico (drivers, método, FCFF, VPN y TIR del escenario base)
  B. Escenarios (matriz de ≥ 5 drivers, tabla comparativa, tornado, matriz WACC × g)
  C. Políticas (reglas SI–ENTONCES, impacto por escenario, recomendación condicionada)
  D. Decisión (umbrales explícitos, matriz de decisión)
  E. Ingeniería de prompts y técnicas (prompt maestro, registro, código) + Monte Carlo (bonificación)
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
PROMPTS_MD = ROOT / "docs" / "ingenieria_prompts_taller_isa.md"
CODIGO_TALLER = ROOT / "scripts" / "taller_isa.py"

# Drivers de escenario: (clave, etiqueta, unidad, factor de presentación)
DRIVERS_UI = [
    ("growth_delta", "Crecimiento de ingresos", "pp vs. base", 100.0),
    ("ebit_margin_delta", "Margen EBIT", "pp vs. base", 100.0),
    ("capex_intensity_mult", "Intensidad CAPEX de expansión", "× base", 1.0),
    ("nwc_ratio_mult", "Capital de trabajo / ingresos", "× base", 1.0),
    ("wacc_delta", "WACC", "pp vs. base", 100.0),
    ("g_terminal_delta", "g terminal", "pp vs. base", 100.0),
]
COLORES = {"Estrés": "#DC2626", "Pesimista": "#F59E0B", "Base": "#14B8A6", "Optimista": "#3B82F6"}


def _layout(title="", height=380):
    return dict(
        title=dict(text=title, x=0.0, font=dict(size=14, color="#F8FAFC")),
        paper_bgcolor="#0F172A", plot_bgcolor="#1E293B", height=height,
        font=dict(color="#F1F5F9", size=12), margin=dict(l=56, r=24, t=56, b=56),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", bgcolor="rgba(15,23,42,0.9)"),
        xaxis=dict(gridcolor="#334155"), yaxis=dict(gridcolor="#334155"),
    )


def _pct(x, d=1):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "N/D"
    v = float(x) * 100
    if abs(v) < 0.5 * 10 ** (-d):
        v = 0.0  # evita «−0,00 %»
    return f"{v:,.{d}f} %"


def _n0(x):
    return "N/D" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.0f}"


# ---------------------------------------------------------------------------
# Configuración editable (escenarios, políticas, umbrales)
# ---------------------------------------------------------------------------
def _editor_escenarios(T, key):
    filas = []
    for k, etiqueta, unidad, fac in DRIVERS_UI:
        fila = {"Driver": etiqueta, "Unidad": unidad}
        for esc in T.SCENARIO_ORDER:
            fila[esc] = float(T.SCENARIOS[esc][k]) * fac
        filas.append(fila)
    df = pd.DataFrame(filas)
    st.caption("Matriz de supuestos del escenario: los deltas se suman al driver calibrado con el histórico; los «×» lo "
               "multiplican. El escenario Base debe quedar en 0 / 1,0. Son hipótesis del equipo, no datos.")
    ed = st.data_editor(
        df, hide_index=True, width="stretch", key=f"{key}_esc",
        disabled=["Driver", "Unidad"],
        column_config={esc: st.column_config.NumberColumn(esc, format="%.3f", step=0.1) for esc in T.SCENARIO_ORDER},
    )
    over = {esc: {} for esc in T.SCENARIO_ORDER}
    for (k, _e, _u, fac), (_, row) in zip(DRIVERS_UI, ed.iterrows()):
        for esc in T.SCENARIO_ORDER:
            v = float(row[esc]) / fac
            if not math.isclose(v, float(T.SCENARIOS[esc][k]), rel_tol=0, abs_tol=1e-12):
                over[esc][k] = v
    return {k: v for k, v in over.items() if v}


def _editor_politicas(T, key):
    p1n, p2n, p3n = list(T.POLICIES)
    p1, p2, p3 = (T.POLICIES[x] for x in (p1n, p2n, p3n))
    over = {}
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**{p1n}**")
        a = st.number_input("Diferir (% del CAPEX de expansión 2026–2027)", 0.0, 100.0, p1["defer_share"] * 100, 5.0,
                            key=f"{key}_p1a") / 100
        b = st.number_input("Activar si crecimiento < (%)", 0.0, 20.0, p1["trigger_growth_below"] * 100, 0.5,
                            key=f"{key}_p1b") / 100
        c = st.number_input("o si deuda neta/EBITDA > (x)", 1.0, 10.0, float(p1["trigger_leverage_above"]), 0.25,
                            key=f"{key}_p1c")
        d = st.number_input("Menor crecimiento 2027–2028 (pp)", 0.0, 5.0, p1["growth_penalty"] * 100, 0.1,
                            key=f"{key}_p1d") / 100
        o = {"defer_share": a, "trigger_growth_below": b, "trigger_leverage_above": c, "growth_penalty": d}
        if any(not math.isclose(o[k], float(p1[k]), abs_tol=1e-12) for k in o):
            over[p1n] = o
    with c2:
        st.markdown(f"**{p2n}**")
        a = st.number_input("Costo inicial (% ingresos 2026)", 0.0, 10.0, p2["upfront_cost_pct_revenue"] * 100, 0.1,
                            key=f"{key}_p2a") / 100
        b = st.number_input("Costo recurrente (% ingresos)", 0.0, 5.0, p2["recurring_cost_pct_revenue"] * 100, 0.05,
                            key=f"{key}_p2b") / 100
        c = st.number_input("Mejora de margen EBIT desde 2028 (pp)", 0.0, 10.0, p2["margin_uplift_steady"] * 100, 0.1,
                            key=f"{key}_p2c") / 100
        o = {"upfront_cost_pct_revenue": a, "recurring_cost_pct_revenue": b, "margin_uplift_steady": c}
        if any(not math.isclose(o[k], float(p2[k]), abs_tol=1e-12) for k in o):
            o["margin_uplift_by_year"] = {2026: 0.0, 2027: c / 2.0}
            over[p2n] = o
    with c3:
        st.markdown(f"**{p3n}**")
        a = st.number_input("Payout normal (%)", 0.0, 100.0, p3["payout_normal"] * 100, 5.0, key=f"{key}_p3a") / 100
        b = st.number_input("Payout restringido (%)", 0.0, 100.0, p3["payout_restricted"] * 100, 5.0,
                            key=f"{key}_p3b") / 100
        c = st.number_input("Restringir si deuda neta/EBITDA > (x)", 1.0, 10.0, float(p3["trigger_on"]), 0.25,
                            key=f"{key}_p3c")
        d = st.number_input("Liberar si deuda neta/EBITDA < (x)", 0.5, 10.0, float(p3["trigger_off"]), 0.25,
                            key=f"{key}_p3d")
        o = {"payout_normal": a, "payout_restricted": b, "trigger_on": c, "trigger_off": d}
        if any(not math.isclose(o[k], float(p3[k]), abs_tol=1e-12) for k in o):
            over[p3n] = o
    return over


def _editor_umbrales(T, key):
    th = T.DECISION_THRESHOLDS
    c1, c2, c3, c4 = st.columns(4)
    o = {
        "covenant_deuda_neta_ebitda": c1.number_input("Covenant deuda neta/EBITDA (x)", 1.0, 10.0,
                                                      float(th["covenant_deuda_neta_ebitda"]), 0.25, key=f"{key}_u1"),
        "prob_min_mc_politica": c2.number_input("P(ΔVPN > 0) mínima para adoptar", 0.0, 1.0,
                                                float(th["prob_min_mc_politica"]), 0.05, key=f"{key}_u2"),
        "margen_seguridad_compra": c3.number_input("Margen de seguridad para comprar", 0.0, 1.0,
                                                   float(th["margen_seguridad_compra"]), 0.05, key=f"{key}_u3"),
        "tolerancia_mantener": c4.number_input("Banda para «mantener» (±)", 0.0, 1.0,
                                               float(th["tolerancia_mantener"]), 0.05, key=f"{key}_u4"),
    }
    return {k: v for k, v in o.items() if not math.isclose(v, float(th[k]), abs_tol=1e-12)}


# ---------------------------------------------------------------------------
# Bloques de resultados
# ---------------------------------------------------------------------------
def _bloque_a(r, cur):
    isa, d, c = r["isa"], r["drivers"], r["capital"]
    base = r["evals"]["Base"]
    v = base["valuation"]
    st.markdown("#### Bloque A · Pronóstico base")
    st.markdown(
        "**Método (T1): drivers deterministas.** Ingresos con crecimiento compuesto calibrado con el histórico; costos vía "
        "margen EBIT; reinversión separada en mantenimiento (∝ ingresos) y expansión (∝ aumento de ingresos), de modo que "
        "más ventas exigen más CAPEX y más capital de trabajo. Con 3–5 observaciones anuales, una regresión o un ARIMA "
        "darían falsa precisión; la incertidumbre se trata con escenarios, sensibilidad y Monte Carlo."
    )
    h = pd.DataFrame(isa["history"]).set_index("Año")
    with st.expander("Datos históricos usados (miles de millones)", expanded=False):
        st.dataframe(h.style.format("{:,.0f}"), width="stretch")
        st.caption(f"Fuente: {isa.get('fuente_historico') or 'N/D'}")
    drv = pd.DataFrame([
        ["Crecimiento de ingresos", _pct(d["growth"], 2), d["growth_formula"]],
        ["Margen EBIT (último año)", _pct(d["ebit_margin"], 2), f"EBIT/Ingresos {isa['history'][-1]['Año']}; "
                                                              f"promedio histórico {_pct(d['ebit_margin_avg'], 2)}"],
        ["D&A / ingresos", _pct(d["da_ratio"], 2), "Último año"],
        ["CAPEX de mantenimiento / ingresos", _pct(d["maint_capex_ratio"], 2), "≈ D&A / ingresos (repone el desgaste)"],
        ["Intensidad CAPEX de expansión", f"{d['capex_intensity']:.2f}", "(CAPEX − D&A) / ΔIngresos, años comparables"],
        ["Capital de trabajo / ingresos", _pct(d["nwc_ratio"], 2), "Último año"],
        ["WACC (CAPM)", _pct(c["wacc"], 2), f"Ke {_pct(c['ke'], 2)} · Kd después de impuestos {_pct(c['kd_despues_imp'], 2)} "
                                            f"· pesos E/D {_pct(c['we'], 0)}/{_pct(c['wd'], 0)} · β apalancada {c['beta_l']:.2f}"],
        ["g terminal", _pct(isa["capital"]["g_terminal"], 2), isa["capital"].get("fuente_g_terminal") or "Supuesto"],
        ["Tasa de impuestos", _pct(c["tax"], 1), isa["capital"].get("tax_estado") or ""],
    ], columns=["Driver", "Valor", "Fórmula o fuente"])
    st.dataframe(drv, hide_index=True, width="stretch")
    rows = pd.DataFrame(base["rows"])
    rows["Año"] = [("Terminal " + str(a)) if t else str(a) for a, t in zip(rows["año"], rows["terminal"])]
    show = rows[["Año", "ingresos", "margen_ebit", "ebit", "nopat", "depreciacion", "capex", "delta_nwc", "fcff"]].rename(
        columns={"ingresos": "Ingresos", "margen_ebit": "Margen EBIT", "ebit": "EBIT", "nopat": "NOPAT",
                 "depreciacion": "D&A", "capex": "CAPEX", "delta_nwc": "ΔNWC", "fcff": "FCFF"})
    st.dataframe(show.style.format({c_: "{:,.0f}" for c_ in show.columns if c_ not in ("Año", "Margen EBIT")}
                                   | {"Margen EBIT": "{:.1%}"}), hide_index=True, width="stretch")
    st.caption("FCFF = NOPAT + D&A − CAPEX − ΔNWC · NOPAT = EBIT × (1 − t) · valor terminal = FCFF terminal / (WACC − g).")
    precio = isa["mercado"]["precio_ref"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Valor por acción (Base)", f"{_n0(v['valor_por_accion'])} {cur}",
              f"{(v['valor_por_accion'] / precio - 1) * 100:+.1f} % vs. precio {precio:,.0f}")
    k2.metric(f"VPN del inversionista (miles de millones {cur})", _n0(v["vpn_inversionista"]),
              help="Patrimonio estimado − capitalización de mercado: VPN de comprar toda la empresa al precio actual.")
    k3.metric(f"TIR implícita (WACC {_pct(base['params']['wacc'], 2)})", _pct(base["tir_implicita"], 2),
              help="Tasa que iguala el EV del DCF con el EV que paga el mercado.")
    k4.metric("Valor terminal / EV", _pct(v["peso_valor_terminal"], 0))
    fe = isa.get("fechas") or {}
    if fe.get("nota"):
        st.caption("📅 " + fe["nota"])
    if v["vpn_inversionista"] < 0:
        st.info("Lectura: con los supuestos base, comprar la empresa al precio actual tiene VPN negativo (TIR implícita < WACC): "
                "el mercado paga más de lo que justifican estos flujos al costo de capital del modelo.")
    else:
        st.info("Lectura: con los supuestos base el VPN de comprar al precio actual es positivo (TIR implícita > WACC).")


def _bloque_b(r, cur, T):
    st.markdown("#### Bloque B · Escenarios y sensibilidad")
    esc = r["metadata"]["escenarios"]
    sm = {x["escenario"]: x for x in r["summary"]}
    orden = T.SCENARIO_ORDER
    mat = pd.DataFrame({
        "Driver": ["Crecimiento de ingresos", "Margen EBIT", "Intensidad CAPEX expansión", "NWC / ingresos", "WACC",
                   "g terminal", "Narrativa"],
        **{s: [_pct(sm[s]["crecimiento"], 2), _pct(sm[s]["margen_ebit"], 2), f"{sm[s]['intensidad_capex']:.2f}",
               _pct(sm[s]["nwc_ingresos"], 2), _pct(sm[s]["wacc"], 2), _pct(sm[s]["g_terminal"], 2),
               esc[s].get("descripcion", "")] for s in orden},
    })
    st.markdown("**Matriz de supuestos (6 drivers × 4 escenarios)**")
    st.dataframe(mat, hide_index=True, width="stretch")
    res = pd.DataFrame({
        "Métrica": ["FCFF acumulado 2026–2030", "EV", f"Valor por acción ({cur})", "VPN del inversionista",
                    "TIR implícita", "Valor terminal / EV", "Máx. deuda neta/EBITDA"],
        **{s: [_n0(sm[s]["fcff_acumulado_2026_2030"]), _n0(sm[s]["ev"]), _n0(sm[s]["valor_por_accion"]),
               _n0(sm[s]["vpn_inversionista"]), _pct(sm[s]["tir_implicita"], 2), _pct(sm[s]["peso_valor_terminal"], 0),
               f"{sm[s]['max_deuda_neta_ebitda']:.2f}x"] for s in orden},
    })
    st.markdown("**Resultados comparados**")
    st.dataframe(res, hide_index=True, width="stretch")
    st.caption("Coherencia entre variables: más crecimiento aumenta automáticamente el CAPEX de expansión y la inversión en "
               "capital de trabajo; los escenarios de tasas altas combinan más WACC con menor g terminal.")
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        for s in orden:
            rows = [x for x in r["evals"][s]["rows"] if not x["terminal"]]
            fig.add_trace(go.Scatter(x=[x["año"] for x in rows], y=[x["fcff"] for x in rows], name=s, mode="lines+markers",
                                     line=dict(color=COLORES.get(s), width=2.5)))
        fig.update_layout(**_layout("FCFF proyectado por escenario (miles de millones)"))
        fig.update_xaxes(dtick=1, tickformat="d")
        st.plotly_chart(fig, width="stretch", key="t10_fcff")
        tor = r["tornado"]
        base_v = tor[0]["valor_base"] if tor else 0
        fig2 = go.Figure()
        labels = [x["driver"] for x in tor][::-1]
        fig2.add_trace(go.Bar(y=labels, x=[x["valor_bajo"] - base_v for x in tor][::-1], base=base_v, orientation="h",
                              name="Choque desfavorable", marker_color="#F59E0B"))
        fig2.add_trace(go.Bar(y=labels, x=[x["valor_alto"] - base_v for x in tor][::-1], base=base_v, orientation="h",
                              name="Choque favorable", marker_color="#14B8A6"))
        fig2.update_layout(**_layout(f"Tornado: valor por acción ({cur}) ante cada driver — base {base_v:,.0f}", 420),
                           barmode="overlay")
        st.plotly_chart(fig2, width="stretch", key="t10_tornado")
    except Exception as exc:  # gráfico opcional: los datos siguen en tablas
        st.caption(f"Gráficos no disponibles: {exc}")
    if r["tornado"]:
        top = r["tornado"][0]
        st.caption(f"Driver que más dispersa el valor: **{top['driver']}** (rango {top['rango']:,.0f} {cur} por acción).")
    mtx = r["matrix"]
    gs = [k for k in mtx["filas"][0] if k.startswith("g=")]
    dfm = pd.DataFrame([[_pct(f["wacc"], 2)] + [_n0(f[g]) for g in gs] for f in mtx["filas"]],
                       columns=["WACC \\ g"] + gs)
    st.markdown(f"**Matriz 2D: valor por acción ({cur}) según WACC y g terminal** (N/D si WACC − g < 1 pp)")
    st.dataframe(dfm, hide_index=True, width="stretch")


def _bloque_c(r, cur):
    st.markdown("#### Bloque C · Simulación de políticas")
    st.caption("Cada política es una regla SI–ENTONCES y se mide como contrafactual frente al mismo escenario sin política: "
               "ΔVPN = EV con política − EV sin política (incluye valor terminal).")
    for p, rec in r["recommendations"].items():
        cfg = r["metadata"]["politicas"][p]
        with st.container(border=True):
            st.markdown(f"**{p}** · decisión: **{rec['decision']}**")
            st.markdown(f"*Regla:* {cfg['regla']}")
            rows = [i for i in r["impacts"] if i["politica"] == p]
            if cfg["tipo"] == "financiera":
                df = pd.DataFrame([{
                    "Escenario": i["escenario"], "¿Se activa?": "Sí" if i["regla_activa"] else "No",
                    "ΔEV": round(i["delta_vpn"], 1),
                    "Años sobre covenant (sin → con)": f"{i['anios_sobre_covenant_sin']} → {i['anios_sobre_covenant_con']}",
                    "Deuda neta 2030 (sin → con)": f"{i['deuda_final_sin']:,.0f} → {i['deuda_final_con']:,.0f}",
                    "Dividendos 2026–2030 (sin → con)": f"{i['dividendos_acumulados_sin']:,.0f} → {i['dividendos_acumulados_con']:,.0f}",
                } for i in rows])
            else:
                df = pd.DataFrame([{
                    "Escenario": i["escenario"], "¿Se activa?": "Sí" if i["regla_activa"] else "No",
                    "ΔFCFF 2026–2030": round(i["delta_fcff_acumulado"], 1), "ΔVPN": round(i["delta_vpn"], 1),
                    f"Δ valor/acción ({cur})": round(i["delta_valor_por_accion"], 0),
                    "Riesgo: años sobre covenant (sin → con)": f"{i['anios_sobre_covenant_sin']} → {i['anios_sobre_covenant_con']}",
                    "Lectura TIR incremental": i["lectura_tir"],
                } for i in rows])
            st.dataframe(df, hide_index=True, width="stretch")
            prob = rec.get("prob_mc_dvpn_pos")
            st.caption(f"Razón: {rec['razon']}" + (f" · P(ΔVPN > 0) en Monte Carlo: {prob:.0%}." if prob is not None else ""))


def _bloque_d(r, cur):
    st.markdown("#### Bloque D · Decisión e integración (camino: evaluación empresarial)")
    th = r["metadata"]["umbrales_decision"]
    dec = r["decision"]
    st.dataframe(pd.DataFrame([
        ["Covenant deuda neta/EBITDA", f"{th['covenant_deuda_neta_ebitda']:.2f}x", "Disparador de P1/P3; viabilidad en escenarios adversos"],
        ["Probabilidad mínima (Monte Carlo)", f"{th['prob_min_mc_politica']:.0%}", "Adoptar una política solo si P(ΔVPN > 0) ≥ umbral"],
        ["Margen de seguridad para comprar", f"{th['margen_seguridad_compra']:.0%}", "Valor Base ≥ precio × (1 + margen) y Pesimista ≥ precio"],
        ["Banda para mantener", f"±{th['tolerancia_mantener']:.0%}", "|valor/precio − 1| dentro de la banda"],
    ], columns=["Umbral (fijado por el equipo)", "Valor", "Uso"]), hide_index=True, width="stretch")
    _txt_dec = f"**Decisión sobre la acción:** {dec['decision']}"
    if dec["decision"].lower().startswith("comprar"):
        st.success(_txt_dec)
    elif dec["decision"].lower().startswith("no comprar"):
        st.error(_txt_dec)
    else:
        st.warning(_txt_dec)
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Valor Base vs. precio {dec['precio']:,.0f}", f"{dec['valor_base']:,.0f} {cur}")
    c2.metric("Valor Base / precio", f"{dec['valor_sobre_precio']:.2f}x",
              help=f"Valor del escenario Pesimista: {dec['valor_pesimista']:,.0f} {cur} por acción.")
    c3.metric("Precio máximo de compra", f"{dec['precio_max_compra']:,.0f} {cur}",
              help="Valor Base ÷ (1 + margen de seguridad).")
    st.caption("Regla: " + dec["regla"])
    filas = []
    for p, rec in r["recommendations"].items():
        by = {i["escenario"]: i for i in r["impacts"] if i["politica"] == p}
        fila = {"Política": p}
        for s in ("Estrés", "Pesimista", "Base", "Optimista"):
            i = by.get(s)
            if i is None:
                continue
            fila[s] = ("✔ " if i["delta_vpn"] > 0 else ("— " if abs(i["delta_vpn"]) < 1e-6 else "✖ ")) + f"{i['delta_vpn']:,.0f}"
        fila["Recomendación"] = rec["decision"]
        filas.append(fila)
    st.markdown("**Matriz de decisión: ΔVPN de cada política por escenario**")
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption("✔ crea valor · ✖ destruye valor · — no cambia el EV (política financiera: redistribuye caja). "
               "Resultado académico; no es una recomendación de inversión profesional.")


def _bloque_e(r, cur):
    st.markdown("#### Bloque E · Ingeniería de prompts, técnicas y código")
    tec = pd.DataFrame([
        ["T1 Pronóstico por drivers", "historical_drivers, project", "Bloque A"],
        ["T2 Parametrización de escenarios", "SCENARIOS (editable arriba)", "Bloque B"],
        ["T3 Sensibilidad", "tornado, wacc_g_matrix", "Bloque B"],
        ["T4 Simulación de políticas", "POLICIES, policy_impact, policy_recommendation", "Bloque C"],
        ["T5 Monte Carlo (bonificación)", "monte_carlo (semilla fija)", "Abajo"],
        ["T6 Ingeniería de prompts", "docs/ingenieria_prompts_taller_isa.md", "Abajo"],
    ], columns=["Técnica", "Dónde está en el código (scripts/taller_isa.py)", "Dónde se ve"])
    st.dataframe(tec, hide_index=True, width="stretch")
    mc = r["monte_carlo"]
    precio = r["isa"]["mercado"]["precio_ref"]
    st.markdown(f"**Monte Carlo** · {mc['n']:,} simulaciones · semilla {mc['semilla']} (reproducible)")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(f"P5 ({cur}/acción)", f"{mc['p5']:,.0f}")
    m2.metric("Mediana", f"{mc['p50']:,.0f}")
    m3.metric("P95", f"{mc['p95']:,.0f}")
    m4.metric("P(valor > precio)", f"{mc['prob_valor_mayor_precio']:.0%}")
    m5.metric("P(covenant roto)", f"{mc['prob_covenant_roto']:.0%}")
    try:
        import plotly.graph_objects as go
        vals = [x["valor_por_accion"] for x in mc["simulaciones"]]
        fig = go.Figure(go.Histogram(x=vals, nbinsx=50, marker_color="#14B8A6", name="Simulaciones"))
        fig.add_vline(x=precio, line_dash="dash", line_color="#F8FAFC", annotation_text=f"Precio {precio:,.0f}")
        fig.update_layout(**_layout(f"Distribución del valor por acción ({cur})", 340), showlegend=False)
        st.plotly_chart(fig, width="stretch", key="t10_mc")
    except Exception:
        pass
    st.caption("Distribuciones hipotéticas alrededor del Base: crecimiento y margen normales (σ 1,5 pp), intensidad de CAPEX y "
               "NWC triangulares, WACC normal (σ 0,75 pp), g uniforme; logro de la eficiencia entre 0 % y 150 %.")
    if PROMPTS_MD.exists():
        md = PROMPTS_MD.read_text(encoding="utf-8")
        with st.expander("Prompt maestro y registro de interacciones (anexo del informe)", expanded=False):
            st.markdown(md)
        st.download_button("⬇️ Anexo de prompts (Markdown)", md.encode("utf-8"), "anexo_prompts_taller.md",
                           "text/markdown", key="t10_dl_prompts")
    else:
        st.warning("No se encontró docs/ingenieria_prompts_taller_isa.md: el anexo de prompts es obligatorio.")


def _descargas(r, T):
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Datos y supuestos usados (JSON)",
                       json.dumps(r["inputs"], ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                       f"datos_taller_{r['fingerprint']}.json", "application/json", key="t10_dl_json")
    det = pd.DataFrame(r["detail"])
    c2.download_button("⬇️ Proyecciones por escenario y política (CSV)", det.to_csv(index=False).encode("utf-8-sig"),
                       f"detalle_taller_{r['fingerprint']}.csv", "text/csv", key="t10_dl_csv")
    if CODIGO_TALLER.exists():
        c3.download_button("⬇️ Código del modelo (taller_isa.py)", CODIGO_TALLER.read_bytes(), "taller_isa.py",
                           "text/x-python", key="t10_dl_code")
    st.caption(f"Reproducir: `python scripts/taller_isa.py --data datos_taller_{r['fingerprint']}.json` "
               f"(huella de datos {r['fingerprint']}).")


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def render(T, datos_app_fn, ctx):
    """Dibuja el tablero del taller.

    T: módulo ``scripts.taller_isa``; datos_app_fn: función que arma los datos desde la sesión de la app (puede fallar si
    falta el precio); ctx: contexto de la barra lateral.
    """
    st.markdown("### Taller evaluativo 2026 · pronóstico → escenarios → políticas → decisión")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        fuente = st.radio("Datos", ["Instantánea del taller (ISA, reproducible)", "Modelo de la app (empresa y supuestos actuales)"],
                          horizontal=True, key="t10_fuente",
                          help="La instantánea usa datos_taller_isa_2026.json (corte y fuentes documentados). La opción de la "
                               "app usa el histórico de la pestaña 1 y la barra lateral.")
    with c2:
        camino = st.selectbox("Camino del taller", ["Evaluación empresarial"], key="t10_camino",
                              help="El modelo implementa el camino de evaluación empresarial (Bloque D).")
    with c3:
        mc_n = st.select_slider("Simulaciones Monte Carlo", [1000, 2000, 5000, 10000], value=5000, key="t10_mc_n")
    with st.expander("✏️ Supuestos editables: escenarios, políticas y umbrales de decisión", expanded=False):
        over_esc = _editor_escenarios(T, "t10")
        st.markdown("---")
        over_pol = _editor_politicas(T, "t10")
        st.markdown("---")
        over_th = _editor_umbrales(T, "t10")
        if over_esc or over_pol or over_th:
            st.info("Hay supuestos modificados frente a los valores documentados del taller; quedan registrados en el JSON "
                    "descargable y en el PDF.")
    try:
        if fuente.startswith("Modelo"):
            datos = datos_app_fn(ctx)
        else:
            datos = json.loads(T.DEFAULT_DATA.read_text(encoding="utf-8"))
    except Exception as exc:
        st.warning(f"No se pudieron armar los datos con la app: {exc}. Usa la instantánea del taller o completa el precio y "
                   "pulsa **Generar todo**.")
        return None
    datos = copy.deepcopy(datos)
    cfg = {k: v for k, v in (("escenarios", over_esc), ("politicas", over_pol), ("umbrales", over_th)) if v}
    if cfg:
        datos["config"] = cfg
    clave = json.dumps([datos, int(mc_n)], sort_keys=True, default=str)
    cache = st.session_state.get("t10_resultado")
    if not cache or cache.get("clave") != clave:
        try:
            with st.spinner("Ejecutando el modelo del taller…"):
                r = T.calcular_modelo(datos, int(mc_n))
        except Exception as exc:
            st.error(f"El modelo del taller no se pudo ejecutar con estos datos: {exc}")
            return None
        st.session_state["t10_resultado"] = {"clave": clave, "r": r}
    r = st.session_state["t10_resultado"]["r"]
    cur = r["isa"].get("moneda", "COP")
    st.caption(f"Empresa: **{r['isa']['empresa']}** · camino: **{camino}** · fuente: {r['isa'].get('fuente_datos')} · "
               f"montos en {r['isa'].get('unidad', 'miles de millones')} de {cur} · huella {r['fingerprint']}")
    ta, tb, tc, td, te = st.tabs(["A · Pronóstico", "B · Escenarios", "C · Políticas", "D · Decisión", "E · Prompts y técnicas"])
    with ta:
        _bloque_a(r, cur)
    with tb:
        _bloque_b(r, cur, T)
    with tc:
        _bloque_c(r, cur)
    with td:
        _bloque_d(r, cur)
    with te:
        _bloque_e(r, cur)
    with st.expander("⚠️ Limitaciones y advertencias del modelo", expanded=False):
        for a in r["metadata"]["advertencias"]:
            st.markdown(f"- {a}")
    _descargas(r, T)
    return datos
