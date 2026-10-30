#!/usr/bin/env python3
"""Modelo reproducible del Taller evaluativo 2026 — ISA (camino: Evaluación empresarial).

Flujo: Datos → Pronóstico → Escenarios → Políticas simuladas → Decisión.

* Montos en miles de millones de COP; valor por acción en COP.
* Lee la instantánea ``datos_taller_isa_2026.json`` (independiente del catálogo de la app).
* Todo supuesto que no es un dato observado está en los diccionarios ``SCENARIOS``,
  ``POLICIES`` y ``DECISION_THRESHOLDS`` y se marca como hipótesis.

Técnicas implementadas (nombres usados en el informe):
  T1 Pronóstico por drivers (crecimiento compuesto calibrado + ratios operativos).
  T2 Parametrización de escenarios (diccionario de 6 drivers × 4 escenarios).
  T3 Sensibilidad univariada (tornado) y matriz 2D WACC × g.
  T4 Simulación de políticas con regla si–entonces y contrafactual (ΔVPN, TIR incremental).
  T5 Monte Carlo de drivers (distribución del valor y de ΔVPN de las políticas).
  T6 Ingeniería de prompts (ver docs/ingenieria_prompts_taller_isa.md).
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "datos_taller_isa_2026.json"
CATALOG = ROOT / "datos_curados.json"
DEFAULT_OUT = ROOT / "salidas_taller_isa"
COMPANY = "ISA — Interconexión Eléctrica"

BASE_YEAR = 2025
FORECAST_YEARS = list(range(2026, 2031))

# ---------------------------------------------------------------------------
# Escenarios: 6 drivers movidos de forma conjunta (hipótesis de trabajo editables).
# Coherencia: el CAPEX de expansión depende del crecimiento (intensidad × ΔIngresos) y el
# NWC es un % de ingresos, así que más ventas exigen más inversión y más capital de trabajo.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "Estrés": {
        "growth_delta": -0.060,       # crecimiento ≈ 0 %: aplazamiento de convocatorias y menor demanda
        "ebit_margin_delta": -0.050,  # sobrecostos operativos / ajuste regulatorio de tarifas
        "capex_intensity_mult": 1.25, # sobrecostos de obra: +25 % de CAPEX por peso de nuevo ingreso
        "nwc_ratio_mult": 1.15,       # mayor cartera con distribuidores
        "wacc_delta": 0.025,          # choque de tasas / riesgo país
        "g_terminal_delta": -0.015,
        "descripcion": "Recesión + choque de tasas: escenario de cola para probar viabilidad y covenants.",
    },
    "Pesimista": {
        "growth_delta": -0.030,
        "ebit_margin_delta": -0.020,
        "capex_intensity_mult": 1.15,
        "nwc_ratio_mult": 1.08,
        "wacc_delta": 0.010,
        "g_terminal_delta": -0.010,
        "descripcion": "Menor crecimiento, presión en márgenes, sobrecostos y tasas más altas.",
    },
    "Base": {
        "growth_delta": 0.0,
        "ebit_margin_delta": 0.0,
        "capex_intensity_mult": 1.0,
        "nwc_ratio_mult": 1.0,
        "wacc_delta": 0.0,
        "g_terminal_delta": 0.0,  # sobre la g base de los datos de entrada
        "descripcion": "Drivers calibrados con el histórico 2023–2025 y WACC por CAPM.",
    },
    "Optimista": {
        "growth_delta": 0.020,
        "ebit_margin_delta": 0.020,   # recuperación parcial hacia el margen promedio 2023–2025
        "capex_intensity_mult": 0.90,
        "nwc_ratio_mult": 0.95,
        "wacc_delta": -0.0075,
        "g_terminal_delta": 0.005,
        "descripcion": "Nuevas adjudicaciones, recuperación de margen y compresión de tasas.",
    },
}
SCENARIO_ORDER = ["Estrés", "Pesimista", "Base", "Optimista"]
CORE_SCENARIOS = ["Pesimista", "Base", "Optimista"]

# ---------------------------------------------------------------------------
# Políticas con regla explícita si–entonces (parámetros hipotéticos, editables).
# ---------------------------------------------------------------------------
POLICIES = {
    "P1 Diferir CAPEX de expansión": {
        "tipo": "inversion",
        "regla": ("SI el crecimiento de ingresos del escenario es < 4,0 % O la deuda neta/EBITDA "
                  "máxima proyectada supera 4,0x, ENTONCES diferir 40 % del CAPEX de expansión de "
                  "2026–2027 a 2029–2030 (sin tocar mantenimiento), asumiendo 0,4 pp menos de "
                  "crecimiento en 2027–2028 por entrada tardía de proyectos."),
        "trigger_growth_below": 0.040,
        "trigger_leverage_above": 4.0,
        "defer_share": 0.40,
        "defer_from": [2026, 2027],
        "defer_to": [2029, 2030],
        "growth_penalty": 0.004,
        "growth_penalty_years": [2027, 2028],
    },
    "P2 Programa de eficiencia operativa": {
        "tipo": "margenes",
        "regla": ("SI el margen EBIT proyectado del escenario es inferior al margen promedio "
                  "2023–2025, ENTONCES ejecutar un programa de eficiencia con costo inicial de "
                  "1,0 % de los ingresos de 2026 y costo recurrente de 0,2 % de ingresos, que "
                  "mejora el margen EBIT 0,5 pp en 2027 y 1,0 pp desde 2028."),
        "upfront_cost_pct_revenue": 0.010,
        "recurring_cost_pct_revenue": 0.002,
        "margin_uplift_by_year": {2026: 0.0, 2027: 0.005},
        "margin_uplift_steady": 0.010,
    },
    "P3 Dividendos condicionados al apalancamiento": {
        "tipo": "financiera",
        "regla": ("SI la deuda neta/EBITDA supera 4,0x en un año, ENTONCES el payout baja de 60 % "
                  "a 40 % de la utilidad neta del año siguiente y se mantiene así hasta que la "
                  "razón vuelva a ser < 3,5x."),
        "payout_normal": 0.60,
        "payout_restricted": 0.40,
        "trigger_on": 4.0,
        "trigger_off": 3.5,
    },
}

# ---------------------------------------------------------------------------
# Umbrales de decisión del equipo (Bloque D). Son criterios de diseño, no datos: el equipo
# los fija ex ante y puede ajustarlos; el modelo aplica la regla de forma mecánica.
# ---------------------------------------------------------------------------
DECISION_THRESHOLDS = {
    "covenant_deuda_neta_ebitda": 4.0,       # tope de apalancamiento tolerado (referencia AAA local)
    "prob_min_mc_politica": 0.60,            # P(ΔVPN > 0) mínima en Monte Carlo para adoptar
    "margen_seguridad_compra": 0.15,         # valor intrínseco ≥ precio × (1 + 15 %) para "comprar"
    "tolerancia_mantener": 0.15,             # |valor/precio − 1| ≤ 15 % → "mantener"
}

MC_DEFAULTS = {"n": 5000, "seed": 20261029}


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
HIST_FIELDS = ("Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC")


def load_isa(data: Path | dict = DEFAULT_DATA) -> dict:
    """Carga los datos de entrada: ruta a la instantánea, ruta al catálogo o un diccionario ya armado
    (por ejemplo, el que construye ``inputs_from_app`` con los datos de la sesión de la app)."""
    if isinstance(data, dict):
        raw = copy.deepcopy(data)
    else:
        raw = json.loads(Path(data).read_text(encoding="utf-8"))
    if "empresas" in raw:  # catálogo completo de la app
        raw = snapshot_from_catalog(raw)
    raw.pop("history", None)
    validate_inputs(raw)
    h = raw["historico"]
    rows = []
    for i, year in enumerate(h["Año"]):
        row = {k: float(h[k][i]) for k in HIST_FIELDS}
        row["Año"] = int(year)
        rows.append(row)
    rows.sort(key=lambda r: r["Año"])
    raw.setdefault("fuente_datos", "Instantánea del taller")
    return {**raw, "history": rows}


def validate_inputs(raw: dict) -> None:
    """Rechaza entradas que harían el modelo engañoso (en vez de rellenar con ceros)."""
    h = raw.get("historico") or {}
    missing = [k for k in ("Año",) + HIST_FIELDS if k not in h]
    if missing:
        raise ValueError("El histórico no trae las columnas: " + ", ".join(missing))
    n = len(h["Año"])
    if n < 3:
        raise ValueError(f"Se necesitan al menos 3 años de histórico; hay {n}.")
    for k in HIST_FIELDS:
        vals = h[k]
        if len(vals) != n or any(v is None or not math.isfinite(float(v)) for v in vals):
            raise ValueError(f"La serie '{k}' tiene valores ausentes o no numéricos.")
    if any(float(v) <= 0 for v in h["Ingresos"]):
        raise ValueError("Los ingresos históricos deben ser positivos.")
    b = raw.get("puente") or {}
    for k in ("deuda_neta", "nci", "asociados", "acciones"):
        if b.get(k) is None:
            raise ValueError(f"Falta el dato del puente EV→patrimonio: {k}.")
    if not b.get("acciones") or float(b["acciones"]) <= 0:
        raise ValueError("El número de acciones debe ser positivo.")
    px = (raw.get("mercado") or {}).get("precio_ref")
    if not px or float(px) <= 0:
        raise ValueError("Falta el precio de mercado de referencia (necesario para VPN y TIR implícita).")
    c = raw.get("capital") or {}
    for k in ("beta_u", "de_ratio", "tax", "g_terminal"):
        if c.get(k) is None:
            raise ValueError(f"Falta el parámetro de costo de capital: {k}.")
    if not (("rf" in c and "erp" in c and "kd" in c) or ("tes_10a" in c and "spread_default_co" in c
                                                          and "erp_total_co" in c and "kd_spread" in c)):
        raise ValueError("Faltan rf/ERP/Kd (o TES, spread, ERP y spread de crédito) para el WACC.")


def snapshot_from_catalog(catalog: dict) -> dict:
    """Construye la instantánea a partir de datos_curados.json conservando la parte de mercado vigente."""
    e = catalog["empresas"][COMPANY]
    current = json.loads(DEFAULT_DATA.read_text(encoding="utf-8")) if DEFAULT_DATA.exists() else {}
    snap = copy.deepcopy(current)
    s = e["supuestos"]
    snap.update({
        "empresa": COMPANY,
        "ticker_bvc": e.get("ticker_bvc", "ISA"),
        "moneda": catalog.get("moneda", "COP"),
        "unidad": catalog.get("unidad", "miles de millones"),
        "corte_catalogo": catalog.get("as_of"),
        "historico": e["historico"],
        "fuente_historico": e.get("fuente_historico", ""),
        "verificacion": e.get("verificacion", ""),
        "calidad_historico_por_anio": e.get("calidad_historico_por_anio", {}),
        "puente": e["puente"],
    })
    snap.setdefault("mercado", {}).update({
        "precio_ref": s.get("precio_ref_mercado"),
        "fecha_precio_ref": s.get("fecha_precio_ref"),
        "fuente_precio_ref": s.get("fuente_precio_ref"),
    })
    cap = snap.setdefault("capital", {})
    for key_snap, key_cat in (("beta_u", "beta_u"), ("de_ratio", "de_ratio"), ("tax", "tax"),
                              ("tax_estado", "tax_estado"), ("fuente_tax", "fuente_tax"),
                              ("g_terminal", "g"), ("fuente_de_ratio", "fuente_de_ratio")):
        if key_cat in s:
            cap[key_snap] = s[key_cat]
    return snap


def historical_drivers(isa: dict) -> dict:
    """T1 — Calibra los drivers con el histórico. Devuelve cada driver con su fórmula."""
    h = isa["history"]
    first, prev, last = h[0], h[-2], h[-1]
    n = last["Año"] - first["Año"]
    cagr = (last["Ingresos"] / first["Ingresos"]) ** (1 / n) - 1
    margins = [r["EBIT"] / r["Ingresos"] for r in h]
    # Intensidad de CAPEX de expansión: (CAPEX − D&A) / ΔIngresos. Solo 2024–2025: 2023 no es
    # comparable en CAPEX (perímetro distinto, ver calidad_historico_por_anio).
    years_ok = isa.get("anios_intensidad_capex") or [r["Año"] for r in h[-2:]]
    intensities = []
    for a, b in zip(h[:-1], h[1:]):
        if b["Año"] in years_ok and b["Ingresos"] > a["Ingresos"]:
            intensities.append((b["CAPEX"] - b["Depreciacion"]) / (b["Ingresos"] - a["Ingresos"]))
    if not intensities:  # sin crecimiento reciente: reinversión neta sobre el último año, sin dividir por ~0
        intensities = [max(last["CAPEX"] - last["Depreciacion"], 0.0) / (last["Ingresos"] * 0.05)]
    return {
        "growth": cagr,
        "growth_formula": f"CAGR {first['Año']}–{last['Año']} = ({last['Ingresos']:.0f}/{first['Ingresos']:.0f})^(1/{n}) − 1",
        "growth_last": last["Ingresos"] / prev["Ingresos"] - 1,
        "ebit_margin": margins[-1],
        "ebit_margin_avg": sum(margins) / len(margins),
        "ebit_margins": {r["Año"]: m for r, m in zip(h, margins)},
        "da_ratio": last["Depreciacion"] / last["Ingresos"],
        "maint_capex_ratio": last["Depreciacion"] / last["Ingresos"],
        "capex_intensity": sum(intensities) / len(intensities),
        "capex_intensities": intensities,
        "capex_ratio_last": last["CAPEX"] / last["Ingresos"],
        "capex_ratio_prev": prev["CAPEX"] / prev["Ingresos"],
        "nwc_ratio": last["NWC"] / last["Ingresos"],
        "revenue_base": last["Ingresos"],
        "nwc_base": last["NWC"],
        "ebitda_base": last["EBITDA"],
    }


def cost_of_capital(isa: dict, wacc_delta: float = 0.0, tax: float | None = None) -> dict:
    """WACC nominal COP por CAPM (método de la app: rf = TES − spread de default; ERP = madura + país)."""
    c = isa["capital"]
    t = c["tax"] if tax is None else tax
    if "rf" in c:  # parámetros tomados tal cual de la app (barra lateral)
        rf, erp, crp, kd = float(c["rf"]), float(c["erp"]), float(c.get("crp") or 0.0), float(c["kd"])
    else:          # instantánea: método de la app a partir del TES y las primas de Damodaran
        rf = c["tes_10a"] - c["spread_default_co"]
        erp, crp = c["erp_total_co"], 0.0
        kd = c["tes_10a"] + c["kd_spread"]
    beta_l = c["beta_u"] * (1 + (1 - t) * c["de_ratio"])
    ke = rf + beta_l * erp + crp
    wd = c["de_ratio"] / (1 + c["de_ratio"])
    we = 1 - wd
    wacc = we * ke + wd * kd * (1 - t)
    return {"rf": rf, "beta_l": beta_l, "ke": ke, "kd": kd, "kd_despues_imp": kd * (1 - t),
            "we": we, "wd": wd, "wacc_capm": wacc, "wacc": wacc + wacc_delta, "tax": t}


# ---------------------------------------------------------------------------
# Proyección (T1 + T2)
# ---------------------------------------------------------------------------
def scenario_params(isa: dict, scenario: str | dict, overrides: dict | None = None) -> dict:
    """Combina drivers históricos + shocks del escenario + overrides (tornado / Monte Carlo)."""
    d = historical_drivers(isa)
    s = SCENARIOS[scenario] if isinstance(scenario, str) else scenario
    p = {
        "growth": d["growth"] + s["growth_delta"],
        "ebit_margin": d["ebit_margin"] + s["ebit_margin_delta"],
        "capex_intensity": d["capex_intensity"] * s["capex_intensity_mult"],
        "nwc_ratio": d["nwc_ratio"] * s["nwc_ratio_mult"],
        "da_ratio": d["da_ratio"],
        "maint_capex_ratio": d["maint_capex_ratio"],
        "wacc_delta": s["wacc_delta"],
        "g_terminal": isa["capital"]["g_terminal"] + s.get("g_terminal_delta", 0.0),
        "tax": isa["capital"]["tax"],
    }
    if overrides:
        p.update(overrides)
    p["wacc"] = cost_of_capital(isa, p["wacc_delta"], p["tax"])["wacc"]
    return p


def project(isa: dict, params: dict, policy: str | None = None, policy_params: dict | None = None) -> list[dict]:
    """Proyecta 2026–2030 + año terminal (2031) con la política de inversión/márgenes aplicada."""
    d = historical_drivers(isa)
    pol = (POLICIES[policy] if policy else {}) | (policy_params or {})
    revenue_prev = d["revenue_base"]
    nwc_prev = d["nwc_base"]
    years = FORECAST_YEARS + [FORECAST_YEARS[-1] + 1]
    rows = []
    # Primer paso: ingresos y CAPEX sin diferimiento para conocer el monto diferible.
    deferred_pool = 0.0
    tipo = pol.get("tipo")
    for year in years:
        terminal = year == years[-1]
        growth = params["g_terminal"] if terminal else params["growth"]
        if tipo == "inversion" and year in pol["growth_penalty_years"]:
            growth -= pol["growth_penalty"]
        revenue = revenue_prev * (1 + growth)
        margin = params["ebit_margin"]
        policy_cost = 0.0
        if tipo == "margenes":
            margin += pol["margin_uplift_by_year"].get(year, pol["margin_uplift_steady"])
            policy_cost = revenue * pol["recurring_cost_pct_revenue"]
            if year == FORECAST_YEARS[0]:
                policy_cost += revenue * pol["upfront_cost_pct_revenue"]
        ebit = revenue * margin - policy_cost
        da = revenue * params["da_ratio"]
        capex_maint = revenue * params["maint_capex_ratio"]
        if terminal:
            # Estado estacionario: la expansión acompaña g terminal con la misma intensidad.
            capex_exp = params["capex_intensity"] * max(revenue - revenue_prev, 0.0)
        else:
            capex_exp = params["capex_intensity"] * max(revenue - revenue_prev, 0.0)
        if tipo == "inversion":
            if year in pol["defer_from"]:
                cut = capex_exp * pol["defer_share"]
                capex_exp -= cut
                deferred_pool += cut
            elif year in pol["defer_to"]:
                capex_exp += deferred_pool / len(pol["defer_to"]) if deferred_pool else 0.0
        capex = capex_maint + capex_exp
        nwc = revenue * params["nwc_ratio"]
        delta_nwc = nwc - nwc_prev
        tax_paid = max(ebit, 0.0) * params["tax"]
        nopat = ebit - tax_paid
        fcff = nopat + da - capex - delta_nwc
        rows.append({
            "año": year, "terminal": terminal, "crecimiento": growth, "ingresos": revenue,
            "margen_ebit": ebit / revenue, "costo_politica": policy_cost, "ebit": ebit,
            "ebitda": ebit + da, "impuestos": tax_paid, "nopat": nopat, "depreciacion": da,
            "capex_mantenimiento": capex_maint, "capex_expansion": capex_exp, "capex": capex,
            "nwc": nwc, "delta_nwc": delta_nwc, "fcff": fcff,
        })
        revenue_prev, nwc_prev = revenue, nwc
    return rows


def value(isa: dict, rows: list[dict], wacc: float, g: float) -> dict:
    """DCF: VP de FCFF explícitos + VP del valor terminal (Gordon sobre FCFF del año terminal)."""
    if wacc <= g:
        raise ValueError(f"WACC ({wacc:.2%}) debe superar g ({g:.2%}).")
    explicit = [r for r in rows if not r["terminal"]]
    term = rows[-1]
    shift = 0.5 if isa["capital"].get("mid_year") else 0.0  # misma convención que valoracion_dcf de la app
    pv_explicit = sum(r["fcff"] / (1 + wacc) ** (i + 1 - shift) for i, r in enumerate(explicit))
    tv = term["fcff"] / (wacc - g)
    pv_tv = tv / (1 + wacc) ** (len(explicit) - shift)
    ev = pv_explicit + pv_tv
    b = isa["puente"]
    equity = ev - b["deuda_neta"] - b["nci"] - b.get("otros_claims", 0) + b.get("asociados", 0)
    per_share = equity / b["acciones"] * 1000  # miles de millones / millones de acciones → COP
    mcap = isa["mercado"]["precio_ref"] * b["acciones"] / 1000
    return {
        "vp_fcff_explicito": pv_explicit, "valor_terminal": tv, "vp_valor_terminal": pv_tv,
        "peso_valor_terminal": pv_tv / ev if ev else float("nan"), "ev": ev, "patrimonio": equity,
        "valor_por_accion": per_share, "capitalizacion_mercado": mcap,
        "vpn_inversionista": equity - mcap,
        "fcff_acumulado": sum(r["fcff"] for r in explicit),
    }


def market_ev(isa: dict) -> float:
    b = isa["puente"]
    mcap = isa["mercado"]["precio_ref"] * b["acciones"] / 1000
    return mcap + b["deuda_neta"] + b["nci"] + b.get("otros_claims", 0) - b.get("asociados", 0)


def implied_irr(isa: dict, rows: list[dict], g: float) -> float:
    """TIR implícita: tasa que iguala el EV del DCF al EV pagado a precio de mercado."""
    target = market_ev(isa)
    lo, hi = g + 0.0005, 0.60
    f = lambda r: value(isa, rows, r, g)["ev"] - target
    if f(lo) < 0 or f(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def irr(cashflows: list[float]) -> float:
    """TIR por bisección; NaN si no hay cambio de signo en [-0,99; 5]."""
    npv = lambda r: sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))
    lo, hi = -0.99, 5.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def leverage_path(isa: dict, rows: list[dict], params: dict, dividend_policy: bool = False) -> list[dict]:
    """Deuda neta proyectada: D_t = D_{t-1} − (FCFF − intereses·(1−t) − dividendos).

    Simplificación documentada: no modela distribuciones a minoritarios ni flujos de asociadas.
    """
    cap = cost_of_capital(isa, 0.0, params["tax"])
    p3 = POLICIES["P3 Dividendos condicionados al apalancamiento"]
    debt = isa["puente"]["deuda_neta"]
    restricted = False
    out = []
    prev_ratio = debt / historical_drivers(isa)["ebitda_base"]
    if dividend_policy and prev_ratio > p3["trigger_on"]:
        restricted = True
    for r in (x for x in rows if not x["terminal"]):
        interest = debt * cap["kd"]
        net_income = (r["ebit"] - interest) * (1 - params["tax"])
        payout = p3["payout_restricted"] if (dividend_policy and restricted) else p3["payout_normal"]
        dividends = max(net_income, 0.0) * payout
        debt = debt - (r["fcff"] - interest * (1 - params["tax"]) - dividends)
        ratio = debt / r["ebitda"]
        out.append({"año": r["año"], "intereses": interest, "utilidad_neta": net_income,
                    "payout": payout, "dividendos": dividends, "deuda_neta": debt,
                    "deuda_neta_ebitda": ratio})
        if dividend_policy:
            if ratio > p3["trigger_on"]:
                restricted = True
            elif ratio < p3["trigger_off"]:
                restricted = False
    return out


def evaluate(isa: dict, scenario: str | dict, policy: str | None = None, overrides: dict | None = None,
             policy_params: dict | None = None) -> dict:
    params = scenario_params(isa, scenario, overrides)
    rows = project(isa, params, policy, policy_params)
    val = value(isa, rows, params["wacc"], params["g_terminal"])
    lev = leverage_path(isa, rows, params,
                        dividend_policy=policy == "P3 Dividendos condicionados al apalancamiento")
    return {"params": params, "rows": rows, "valuation": val, "leverage": lev,
            "tir_implicita": implied_irr(isa, rows, params["g_terminal"]),
            "max_deuda_ebitda": max(x["deuda_neta_ebitda"] for x in lev)}


# ---------------------------------------------------------------------------
# Políticas (T4)
# ---------------------------------------------------------------------------
def policy_triggered(isa: dict, scenario: str, policy: str, base_eval: dict | None = None) -> bool:
    ev0 = base_eval or evaluate(isa, scenario)
    pol = POLICIES[policy]
    if pol["tipo"] == "inversion":
        return (ev0["params"]["growth"] < pol["trigger_growth_below"]
                or ev0["max_deuda_ebitda"] > pol["trigger_leverage_above"])
    if pol["tipo"] == "margenes":
        return ev0["params"]["ebit_margin"] < historical_drivers(isa)["ebit_margin_avg"]
    if pol["tipo"] == "financiera":
        return ev0["max_deuda_ebitda"] > pol["trigger_on"]
    raise ValueError(policy)


def policy_impact(isa: dict, scenario: str, policy: str) -> dict:
    base = evaluate(isa, scenario)
    with_p = evaluate(isa, scenario, policy)
    wacc = base["params"]["wacc"]
    inc = [w["fcff"] - b["fcff"] for w, b in zip(with_p["rows"], base["rows"]) if not b["terminal"]]
    # Flujo terminal incremental: diferencia de valores terminales en el último año explícito.
    inc_tv = with_p["valuation"]["valor_terminal"] - base["valuation"]["valor_terminal"]
    flows = [0.0] + inc[:-1] + [inc[-1] + inc_tv]
    tir_inc = irr(flows) if any(abs(x) > 1e-9 for x in flows) else float("nan")
    delta_vpn = with_p["valuation"]["ev"] - base["valuation"]["ev"]
    lev_b = base["leverage"]
    lev_p = with_p["leverage"]
    years_over = lambda lev: sum(1 for x in lev if x["deuda_neta_ebitda"] > DECISION_THRESHOLDS["covenant_deuda_neta_ebitda"])
    return {
        "escenario": scenario, "politica": policy,
        "regla_activa": policy_triggered(isa, scenario, policy, base),
        "delta_fcff_acumulado": sum(inc),
        "delta_vpn": delta_vpn,
        "delta_valor_por_accion": with_p["valuation"]["valor_por_accion"] - base["valuation"]["valor_por_accion"],
        "tir_incremental": tir_inc,
        "flujos_incrementales": flows,
        "wacc": wacc,
        "max_deuda_ebitda_sin": base["max_deuda_ebitda"],
        "max_deuda_ebitda_con": with_p["max_deuda_ebitda"],
        "anios_sobre_covenant_sin": years_over(lev_b),
        "anios_sobre_covenant_con": years_over(lev_p),
        "deuda_final_sin": lev_b[-1]["deuda_neta"],
        "deuda_final_con": lev_p[-1]["deuda_neta"],
        "lectura_tir": _irr_reading(flows, tir_inc, wacc),
        "dividendos_acumulados_sin": sum(x["dividendos"] for x in lev_b),
        "dividendos_acumulados_con": sum(x["dividendos"] for x in lev_p),
    }


def _irr_reading(flows: list[float], tir: float, wacc: float) -> str:
    nz = [f for f in flows if abs(f) > 1e-9]
    if not nz:
        return "Sin efecto en FCFF (política financiera)."
    if math.isnan(tir):
        return "TIR no definida (los flujos incrementales no cambian de signo)."
    if nz[0] > 0:  # primero libera caja y luego la devuelve: es una financiación
        ok = tir < wacc
        return (f"Flujo tipo financiación: costo implícito {tir:.1%} "
                f"{'<' if ok else '>'} WACC {wacc:.1%} → {'conviene' if ok else 'no conviene'}.")
    ok = tir > wacc
    return f"Flujo tipo inversión: TIR {tir:.1%} {'>' if ok else '<'} WACC {wacc:.1%} → {'conviene' if ok else 'no conviene'}."


def policy_recommendation(impacts: list[dict], mc_prob: float | None, tipo: str) -> dict:
    """Aplica los umbrales: adoptar / condicionar / descartar."""
    by = {i["escenario"]: i for i in impacts}
    cov = DECISION_THRESHOLDS["covenant_deuda_neta_ebitda"]
    if tipo == "financiera":
        activa = [s for s in SCENARIO_ORDER if s in by and by[s]["regla_activa"]]
        if not activa:
            return {"decision": "Descartar (no se activa)", "razon": "La regla no se dispara en ningún escenario."}
        mejora = [s for s in activa
                  if by[s]["anios_sobre_covenant_con"] < by[s]["anios_sobre_covenant_sin"]
                  or by[s]["deuda_final_con"] < by[s]["deuda_final_sin"] - 1e-9]
        detalle = "; ".join(
            f"{s}: años con DN/EBITDA > {cov:.1f}x {by[s]['anios_sobre_covenant_sin']} → {by[s]['anios_sobre_covenant_con']}, "
            f"deuda neta 2030 {by[s]['deuda_final_sin']:,.0f} → {by[s]['deuda_final_con']:,.0f}" for s in activa)
        return {"decision": "Adoptar como regla contingente" if mejora else "Condicionar",
                "razon": (f"Solo se dispara en {', '.join(activa)} ({detalle}). No cambia el EV "
                          "(Modigliani–Miller: redistribuye caja entre accionistas y acreedores); su valor es "
                          "proteger la calificación y el acceso a deuda en el escenario adverso.")}
    pos_base = by["Base"]["delta_vpn"] > 0
    pos_pes = by["Pesimista"]["delta_vpn"] > 0
    mc_ok = mc_prob is None or mc_prob >= DECISION_THRESHOLDS["prob_min_mc_politica"]
    if pos_base and pos_pes and mc_ok:
        dec = "Adoptar"
        razon = "ΔVPN > 0 en Base y Pesimista y probabilidad Monte Carlo sobre el umbral."
    elif pos_pes and not pos_base:
        dec = "Condicionar (activar solo con la regla)"
        razon = "Solo crea valor cuando el escenario es adverso; aplicar únicamente si se dispara la condición."
    elif pos_base and not pos_pes:
        dec = "Condicionar"
        razon = "Crea valor en Base pero no protege en Pesimista."
    elif pos_base and pos_pes and not mc_ok:
        dec = "Condicionar (validar ejecución)"
        razon = "ΔVPN > 0 en escenarios deterministas pero la probabilidad de éxito no alcanza el umbral."
    else:
        dec = "Descartar"
        razon = "ΔVPN ≤ 0 en Base y Pesimista."
        rescata = [s for s in by if by[s]["anios_sobre_covenant_con"] < by[s]["anios_sobre_covenant_sin"]]
        if rescata:
            dec = "Condicionar (solo como contingencia de liquidez)"
            razon += f" Reduce años sobre el covenant en {', '.join(rescata)}: reservar como plan de contingencia."
        else:
            razon += " Tampoco reduce los años por encima del covenant: no compensa la pérdida de valor."
    return {"decision": dec, "razon": razon}


# ---------------------------------------------------------------------------
# Sensibilidad (T3)
# ---------------------------------------------------------------------------
TORNADO_DRIVERS = {
    "Crecimiento de ingresos (±2 pp)": ("growth", -0.02, 0.02, "abs"),
    "Margen EBIT (±2 pp)": ("ebit_margin", -0.02, 0.02, "abs"),
    "Intensidad CAPEX expansión (±25 %)": ("capex_intensity", -0.25, 0.25, "rel"),
    "NWC / ingresos (±25 %)": ("nwc_ratio", -0.25, 0.25, "rel"),
    "WACC (±1 pp)": ("wacc_delta", 0.01, -0.01, "abs"),
    "g terminal (±1 pp)": ("g_terminal", -0.01, 0.01, "abs"),
    "Tasa de impuestos (22 % → 35 %)": ("tax", None, 0.35, "set"),
}


def tornado(isa: dict, scenario: str = "Base") -> list[dict]:
    base_params = scenario_params(isa, scenario)
    base_val = evaluate(isa, scenario)["valuation"]["valor_por_accion"]
    out = []
    for label, (key, lo, hi, mode) in TORNADO_DRIVERS.items():
        vals = []
        for shock in (lo, hi):
            if shock is None:
                vals.append(base_val)
                continue
            if mode == "abs":
                ov = {key: base_params[key] + shock}
            elif mode == "rel":
                ov = {key: base_params[key] * (1 + shock)}
            else:
                ov = {key: shock}
            vals.append(evaluate(isa, scenario, overrides=ov)["valuation"]["valor_por_accion"])
        out.append({"driver": label, "valor_bajo": min(vals), "valor_alto": max(vals),
                    "rango": max(vals) - min(vals), "valor_base": base_val})
    out.sort(key=lambda x: x["rango"], reverse=True)
    return out


def wacc_g_matrix(isa: dict, scenario: str = "Base", wacc_steps=(-0.02, -0.01, 0.0, 0.01, 0.02),
                  g_values=(0.03, 0.04, 0.05, 0.06)) -> dict:
    p = scenario_params(isa, scenario)
    rows = []
    for dw in wacc_steps:
        line = {"wacc": p["wacc"] + dw}
        for g in g_values:
            ov = {"wacc_delta": p["wacc_delta"] + dw, "g_terminal": g}
            if p["wacc"] + dw - g < 0.01:
                line[f"g={g:.0%}"] = float("nan")
            else:
                line[f"g={g:.0%}"] = evaluate(isa, scenario, overrides=ov)["valuation"]["valor_por_accion"]
        rows.append(line)
    return {"filas": rows, "g": list(g_values)}


# ---------------------------------------------------------------------------
# Monte Carlo (T5)
# ---------------------------------------------------------------------------
def monte_carlo(isa: dict, n: int = MC_DEFAULTS["n"], seed: int = MC_DEFAULTS["seed"]) -> dict:
    """Muestrea drivers alrededor del Base (distribuciones hipotéticas documentadas)."""
    rng = random.Random(seed)
    base = scenario_params(isa, "Base")
    p2 = POLICIES["P2 Programa de eficiencia operativa"]
    results = []
    for _ in range(n):
        g_term = base["g_terminal"] + rng.uniform(-0.015, 0.010)
        ov = {
            "growth": rng.gauss(base["growth"], 0.015),
            "ebit_margin": rng.gauss(base["ebit_margin"], 0.015),
            "capex_intensity": base["capex_intensity"] * rng.triangular(0.85, 1.35, 1.0),
            "nwc_ratio": base["nwc_ratio"] * rng.triangular(0.85, 1.20, 1.0),
            "wacc_delta": rng.gauss(0.0, 0.0075),
            "g_terminal": g_term,
        }
        wacc = cost_of_capital(isa, ov["wacc_delta"], base["tax"])["wacc"]
        if wacc - g_term < 0.02:  # coherencia: spread mínimo WACC − g de 2 pp
            ov["g_terminal"] = wacc - 0.02
        e0 = evaluate(isa, "Base", overrides=ov)
        e1 = evaluate(isa, "Base", "P1 Diferir CAPEX de expansión", overrides=ov)
        # Incertidumbre de ejecución de la eficiencia: logro entre 0 % y 150 % de la meta.
        achieve = rng.uniform(0.0, 1.5)
        pp = {"margin_uplift_by_year": {k: v * achieve for k, v in p2["margin_uplift_by_year"].items()},
              "margin_uplift_steady": p2["margin_uplift_steady"] * achieve}
        e2 = evaluate(isa, "Base", "P2 Programa de eficiencia operativa", overrides=ov, policy_params=pp)
        results.append({
            "valor_por_accion": e0["valuation"]["valor_por_accion"],
            "vpn_inversionista": e0["valuation"]["vpn_inversionista"],
            "delta_vpn_p1": e1["valuation"]["ev"] - e0["valuation"]["ev"],
            "delta_vpn_p2": e2["valuation"]["ev"] - e0["valuation"]["ev"],
            "max_deuda_ebitda": e0["max_deuda_ebitda"],
            "crecimiento": ov["growth"], "margen": ov["ebit_margin"],
        })
    vals = sorted(r["valor_por_accion"] for r in results)
    pct = lambda q: vals[min(len(vals) - 1, max(0, int(q * len(vals))))]
    price = isa["mercado"]["precio_ref"]
    return {
        "n": n, "semilla": seed, "simulaciones": results,
        "p5": pct(0.05), "p50": pct(0.50), "p95": pct(0.95),
        "media": sum(vals) / n,
        "prob_valor_mayor_precio": sum(v > price for v in vals) / n,
        "prob_dvpn_p1_pos": sum(r["delta_vpn_p1"] > 0 for r in results) / n,
        "prob_dvpn_p2_pos": sum(r["delta_vpn_p2"] > 0 for r in results) / n,
        "prob_covenant_roto": sum(r["max_deuda_ebitda"] > DECISION_THRESHOLDS["covenant_deuda_neta_ebitda"] for r in results) / n,
    }


# ---------------------------------------------------------------------------
# Decisión (Bloque D)
# ---------------------------------------------------------------------------
def investment_decision(isa: dict, evals: dict) -> dict:
    price = isa["mercado"]["precio_ref"]
    th = DECISION_THRESHOLDS
    base = evals["Base"]["valuation"]["valor_por_accion"]
    pes = evals["Pesimista"]["valuation"]["valor_por_accion"]
    ratio = base / price
    if ratio >= 1 + th["margen_seguridad_compra"] and pes >= price:
        dec = "Comprar / sobreponderar"
    elif abs(ratio - 1) <= th["tolerancia_mantener"]:
        dec = "Mantener (valor dentro de la banda de tolerancia)"
    elif ratio < 1 - th["tolerancia_mantener"]:
        dec = "No comprar / subponderar al precio actual"
    else:
        dec = "Mantener con sesgo positivo (no alcanza el margen de seguridad)"
    wacc = evals["Base"]["params"]["wacc"]
    tir = evals["Base"]["tir_implicita"]
    # Precio máximo de compra que respeta el margen de seguridad en Base.
    return {"decision": dec, "valor_base": base, "valor_pesimista": pes, "precio": price,
            "valor_sobre_precio": ratio, "tir_implicita": tir, "wacc": wacc,
            "precio_max_compra": base / (1 + th["margen_seguridad_compra"]),
            "regla": (f"Comprar si valor Base ≥ precio × {1 + th['margen_seguridad_compra']:.2f} y valor "
                      f"Pesimista ≥ precio; mantener si |valor/precio − 1| ≤ {th['tolerancia_mantener']:.0%}; "
                      "si no, no comprar. Contraste: comprar solo si TIR implícita > WACC.")}


# ---------------------------------------------------------------------------
# Ejecución completa y exportación
# ---------------------------------------------------------------------------
def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})


def inputs_fingerprint(isa: dict) -> str:
    """Huella SHA-256 (12 caracteres) de los datos de entrada, para enlazar un informe con su JSON."""
    import hashlib
    clean = {k: v for k, v in isa.items() if k != "history"}
    blob = json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def run_model(data_path: Path | dict = DEFAULT_DATA, output_dir: Path = DEFAULT_OUT, mc_n: int = MC_DEFAULTS["n"]) -> dict:
    isa = load_isa(data_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    drivers = historical_drivers(isa)
    capital = cost_of_capital(isa)

    evals = {s: evaluate(isa, s) for s in SCENARIO_ORDER}
    detail, summary = [], []
    for s in SCENARIO_ORDER:
        for pol in [None] + list(POLICIES):
            e = evals[s] if pol is None else evaluate(isa, s, pol)
            for r in e["rows"]:
                detail.append({"escenario": s, "politica": pol or "Sin política", **r})
        e = evals[s]
        v = e["valuation"]
        summary.append({
            "escenario": s, "crecimiento": e["params"]["growth"], "margen_ebit": e["params"]["ebit_margin"],
            "intensidad_capex": e["params"]["capex_intensity"], "nwc_ingresos": e["params"]["nwc_ratio"],
            "wacc": e["params"]["wacc"], "g_terminal": e["params"]["g_terminal"],
            "fcff_acumulado_2026_2030": v["fcff_acumulado"], "vp_fcff_explicito": v["vp_fcff_explicito"],
            "vp_valor_terminal": v["vp_valor_terminal"], "peso_valor_terminal": v["peso_valor_terminal"],
            "ev": v["ev"], "patrimonio": v["patrimonio"], "valor_por_accion": v["valor_por_accion"],
            "vpn_inversionista": v["vpn_inversionista"], "tir_implicita": e["tir_implicita"],
            "max_deuda_neta_ebitda": e["max_deuda_ebitda"],
        })

    mc = monte_carlo(isa, n=mc_n)
    impacts = [policy_impact(isa, s, p) for p in POLICIES for s in SCENARIO_ORDER]
    recs = {}
    for p, cfg in POLICIES.items():
        prob = {"inversion": mc["prob_dvpn_p1_pos"], "margenes": mc["prob_dvpn_p2_pos"]}.get(cfg["tipo"])
        recs[p] = {**policy_recommendation([i for i in impacts if i["politica"] == p], prob, cfg["tipo"]),
                   "prob_mc_dvpn_pos": prob, "regla": cfg["regla"]}
    torn = tornado(isa)
    matrix = wacc_g_matrix(isa)
    decision = investment_decision(isa, evals)
    leverage_rows = []
    for s in SCENARIO_ORDER:
        for pol in (None, "P3 Dividendos condicionados al apalancamiento"):
            e = evals[s] if pol is None else evaluate(isa, s, pol)
            for x in e["leverage"]:
                leverage_rows.append({"escenario": s, "politica": pol or "Sin política", **x})

    inputs_clean = {k: v for k, v in isa.items() if k != "history"}
    (output_dir / "datos_entrada.json").write_text(json.dumps(inputs_clean, ensure_ascii=False, indent=2, default=str),
                                                    encoding="utf-8")
    _write_csv(output_dir / "detalle_escenarios_politicas.csv", detail)
    _write_csv(output_dir / "resumen_escenarios.csv", summary)
    _write_csv(output_dir / "impacto_politicas.csv", impacts)
    _write_csv(output_dir / "apalancamiento.csv", leverage_rows)
    _write_csv(output_dir / "tornado.csv", torn)
    _write_csv(output_dir / "matriz_wacc_g.csv", matrix["filas"])
    _write_csv(output_dir / "monte_carlo.csv", mc["simulaciones"])

    metadata = {
        "empresa": isa["empresa"], "camino": "Evaluación empresarial",
        "fuente_datos": isa.get("fuente_datos"), "huella_datos": inputs_fingerprint(isa),
        "corte_datos": isa.get("corte_catalogo"), "moneda": isa["moneda"], "unidad": isa["unidad"],
        "historia": [r["Año"] for r in isa["history"]], "horizonte": [FORECAST_YEARS[0], FORECAST_YEARS[-1]],
        "drivers_historicos": {k: v for k, v in drivers.items() if not isinstance(v, (list, dict))},
        "costo_capital": capital,
        "escenarios": SCENARIOS, "politicas": POLICIES, "umbrales_decision": DECISION_THRESHOLDS,
        "recomendacion_politicas": recs, "decision_inversion": decision,
        "monte_carlo": {k: v for k, v in mc.items() if k != "simulaciones"},
        "tecnicas": ["T1 Pronóstico por drivers", "T2 Parametrización de escenarios",
                     "T3 Sensibilidad (tornado y matriz WACC×g)", "T4 Simulación de políticas (regla si–entonces)",
                     "T5 Monte Carlo", "T6 Ingeniería de prompts"],
        "advertencias": [
            "Los shocks de escenarios, los parámetros de las políticas y los umbrales son hipótesis del equipo, no datos observados ni metas de ISA.",
            "El CAPEX histórico es PP&E + intangibles pagados en caja; las inversiones en concesiones registradas como activos financieros/contractuales (CINIIF 12) pueden no estar incluidas, lo que subestimaría la reinversión y sobrestimaría el FCFF.",
            "2023 no es comparable en CAPEX y NWC; la intensidad de CAPEX se calibra solo con 2024–2025.",
            "NWC 2024–2025 es preliminar (derivado del balance, no certificado).",
            "La tasa de impuestos de 22 % es provisional; el tornado muestra el efecto de 35 %.",
            "El puente EV→patrimonio usa asociadas a valor contable y no modela distribuciones a minoritarios en la trayectoria de deuda.",
            "Resultado académico: no es una recomendación de inversión profesional.",
        ],
        "fuentes": {
            "historico": isa.get("fuente_historico"), "verificacion": isa.get("verificacion"),
            "puente": isa["puente"].get("fuente"), "precio": isa["mercado"].get("fuente_precio_ref"),
            "tes": isa["capital"].get("fuente_tes_10a"), "primas": isa["capital"].get("fuente_primas"),
            "beta": isa["capital"].get("fuente_beta_u"), "de_ratio": isa["capital"].get("fuente_de_ratio"),
            "tax": isa["capital"].get("fuente_tax"), "g": isa["capital"].get("fuente_g_terminal"),
        },
    }
    (output_dir / "metadatos_modelo.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x),
        encoding="utf-8")
    return {"isa": isa, "inputs": inputs_clean, "fingerprint": metadata["huella_datos"], "drivers": drivers, "capital": capital, "evals": evals, "summary": summary,
            "detail": detail, "impacts": impacts, "recommendations": recs, "tornado": torn,
            "matrix": matrix, "monte_carlo": mc, "decision": decision, "leverage": leverage_rows,
            "metadata": metadata}


def inputs_from_app(empresa: str, df_hist, *, tax: float, g: float, de_ratio: float, kd: float, beta_u: float,
                    rf: float, erp: float, crp: float, deuda_neta: float, caja: float, nci: float,
                    otros_claims: float, asociados: float, acciones: float, precio: float,
                    mid_year: bool = True, deuda_es_bruta: bool = False, moneda: str = "COP",
                    fuente_precio: str | None = None, fecha_precio: str | None = None,
                    fuente_historico: str | None = None, ticker: str | None = None,
                    descripcion: str | None = None) -> dict:
    """Arma los datos de entrada del taller con lo que la app tiene en la sesión.

    Usa solo argumentos explícitos (histórico de ``cargar_y_limpiar_excel`` y valores de la barra lateral);
    no lee la estructura interna de los resultados de otras pestañas, para que un cambio allá no rompa el taller.
    """
    import pandas as pd  # import local: el script sigue funcionando sin pandas cuando no se usa la app
    df = df_hist.copy()
    if df.index.name == "Año" and "Año" not in df.columns:
        df = df.reset_index()
    missing = [c for c in ("Año",) + HIST_FIELDS if c not in df.columns]
    if missing:
        raise ValueError("El histórico de la app no trae: " + ", ".join(missing))
    df = df.sort_values("Año")
    hist = {"Año": [int(a) for a in df["Año"]]}
    for k in HIST_FIELDS:
        hist[k] = [float(x) for x in pd.to_numeric(df[k], errors="coerce")]
    dn = float(deuda_neta) - float(caja) if deuda_es_bruta else float(deuda_neta)
    nota_dn = (" Deuda ingresada como bruta en la app; deuda neta = deuda − caja." if deuda_es_bruta else "")
    data = {
        "descripcion": "Datos tomados de la sesión de la app (pestañas 1–9 y barra lateral) al generar el informe.",
        "fuente_datos": "Modelo de la app (sesión)",
        "empresa": empresa,
        "ticker_bvc": ticker or empresa.split("—")[0].strip(),
        "moneda": moneda, "unidad": "miles de millones",
        "corte_catalogo": datetime_now_iso(),
        "historico": hist,
        "fuente_historico": fuente_historico or "cargar_y_limpiar_excel de la app (misma fuente que la pestaña 1).",
        "verificacion": "Según la fuente cargada en la app; revisar la pestaña 3 (Auditoría).",
        "puente": {"deuda_neta": dn, "caja": float(caja), "nci": float(nci), "otros_claims": float(otros_claims),
                   "asociados": float(asociados), "acciones": float(acciones),
                   "fuente": "Barra lateral de la app (puente EV→Equity)." + nota_dn},
        "mercado": {"precio_ref": float(precio) if precio else None, "fecha_precio_ref": fecha_precio,
                    "fuente_precio_ref": fuente_precio or "Precio de mercado alineado en la app."},
        "capital": {
            "beta_u": float(beta_u), "de_ratio": float(de_ratio), "tax": float(tax), "g_terminal": float(g),
            "rf": float(rf), "erp": float(erp), "crp": float(crp or 0.0), "kd": float(kd), "mid_year": bool(mid_year),
            "tax_estado": "según barra lateral",
            "fuente_beta_u": "Barra lateral de la app.", "fuente_de_ratio": "Barra lateral de la app.",
            "fuente_tax": "Barra lateral de la app.", "fuente_g_terminal": "Barra lateral de la app.",
            "fuente_primas": f"Barra lateral de la app: rf {float(rf):.2%}, ERP {float(erp):.2%}, CRP {float(crp or 0):.2%}, Kd {float(kd):.2%}.",
            "fuente_tes_10a": "No aplica: rf tomado directamente de la app.",
        },
    }
    if descripcion:
        data["descripcion_negocio"] = descripcion
    validate_inputs(data)
    return data


def datetime_now_iso() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def refresh_snapshot() -> Path:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    snap = snapshot_from_catalog(catalog)
    DEFAULT_DATA.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULT_DATA


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Instantánea JSON (o datos_curados.json)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Directorio de salida")
    parser.add_argument("--mc", type=int, default=MC_DEFAULTS["n"], help="Número de simulaciones Monte Carlo")
    parser.add_argument("--refrescar-instantanea", action="store_true",
                        help="Regenera datos_taller_isa_2026.json desde datos_curados.json y termina")
    args = parser.parse_args()
    if args.refrescar_instantanea:
        print(f"Instantánea actualizada: {refresh_snapshot()}")
        return
    r = run_model(args.data, args.out, args.mc)
    d, c, dec = r["drivers"], r["capital"], r["decision"]
    print(f"Empresa: {r['metadata']['empresa']} | corte {r['metadata']['corte_datos']}")
    print(f"Drivers base: crecimiento {d['growth']:.2%} | margen EBIT {d['ebit_margin']:.2%} | "
          f"intensidad CAPEX {d['capex_intensity']:.2f} | NWC/ingresos {d['nwc_ratio']:.2%} | WACC {c['wacc']:.2%}")
    for s in r["summary"]:
        print(f"  {s['escenario']:<10} EV {s['ev']:>9,.0f}  valor/acción {s['valor_por_accion']:>8,.0f}  "
              f"VPN inv. {s['vpn_inversionista']:>9,.0f}  TIR implícita {s['tir_implicita']:.2%}  "
              f"máx DN/EBITDA {s['max_deuda_neta_ebitda']:.2f}x")
    for p, rec in r["recommendations"].items():
        print(f"  {p}: {rec['decision']}")
    print(f"Decisión de inversión: {dec['decision']} (valor Base {dec['valor_base']:,.0f} vs precio {dec['precio']:,.0f})")
    print(f"Monte Carlo n={r['monte_carlo']['n']}: P(valor > precio) = {r['monte_carlo']['prob_valor_mayor_precio']:.1%}")
    print(f"Archivos generados en: {args.out}")


if __name__ == "__main__":
    main()
