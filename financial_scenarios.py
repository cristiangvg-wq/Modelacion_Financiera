"""Escenarios financieros y políticas empresariales reproducibles.

Modelo educativo FCFF/DCF. Las cifras deben estar en una única moneda y escala.
La TIR usa inversión inicial explícita más FCFF operativo; no se fuerza una TIR
si no existe raíz económicamente válida. El indicador de riesgo es dispersión
entre escenarios, no volatilidad estadística ni VaR.
"""
from __future__ import annotations

import math
from typing import Mapping

DRIVERS = ("crecimiento_ingresos", "margen_ebit", "capex_pct_ventas",
           "nwc_pct_ventas", "wacc")


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} debe ser finito.")
    return value


def _validate_inputs(base: Mapping, horizon: int) -> dict:
    required = ("ingresos", "crecimiento_ingresos", "margen_ebit", "tasa_impuesto",
                "da_pct_ventas", "capex_pct_ventas", "nwc_pct_ventas", "wacc",
                "g_terminal", "inversion_inicial")
    missing = [k for k in required if k not in base]
    if missing:
        raise ValueError("Faltan supuestos: " + ", ".join(missing))
    b = {k: _finite(k, base[k]) for k in required}
    if b["ingresos"] <= 0 or b["inversion_inicial"] < 0:
        raise ValueError("Ingresos deben ser > 0 e inversión inicial ≥ 0.")
    if not 1 <= int(horizon) <= 15:
        raise ValueError("El horizonte debe estar entre 1 y 15 años.")
    for key in ("tasa_impuesto", "da_pct_ventas", "capex_pct_ventas", "nwc_pct_ventas"):
        if b[key] < 0 or (key == "tasa_impuesto" and b[key] >= 1):
            raise ValueError(f"{key} está fuera de rango.")
    if b["margen_ebit"] < -1 or b["margen_ebit"] > 1:
        raise ValueError("El margen EBIT debe estar entre -100% y 100%.")
    if b["wacc"] <= 0 or b["g_terminal"] < 0 or b["g_terminal"] >= b["wacc"]:
        raise ValueError("Se requiere WACC > 0 y 0 ≤ g terminal < WACC.")
    if b["crecimiento_ingresos"] <= -1:
        raise ValueError("El crecimiento de ingresos debe ser mayor que -100%.")
    return b


def proyectar_fcff(supuestos: Mapping, horizonte: int) -> dict:
    """Proyecta ingresos, NOPAT, D&A, CAPEX, ΔNWC y FCFF, y valora por DCF."""
    b = _validate_inputs(supuestos, horizonte)
    rows = []
    revenue_prev = b["ingresos"]
    nwc_prev = revenue_prev * b["nwc_pct_ventas"]
    fcffs = []
    for year in range(1, int(horizonte) + 1):
        revenue = revenue_prev * (1 + b["crecimiento_ingresos"])
        ebit = revenue * b["margen_ebit"]
        tax = max(0.0, ebit * b["tasa_impuesto"])
        nopat = ebit - tax
        da = revenue * b["da_pct_ventas"]
        capex = revenue * b["capex_pct_ventas"]
        nwc = revenue * b["nwc_pct_ventas"]
        delta_nwc = nwc - nwc_prev
        fcff = nopat + da - capex - delta_nwc
        rows.append({"Año": year, "Ingresos": revenue, "EBIT": ebit, "NOPAT": nopat,
                     "D&A": da, "CAPEX": capex, "NWC": nwc, "Cambio NWC": delta_nwc,
                     "FCFF": fcff})
        fcffs.append(fcff)
        revenue_prev, nwc_prev = revenue, nwc
    terminal_value = fcffs[-1] * (1 + b["g_terminal"]) / (b["wacc"] - b["g_terminal"])
    pv_explicit = sum(cf / ((1 + b["wacc"]) ** (i + 1)) for i, cf in enumerate(fcffs))
    pv_terminal = terminal_value / ((1 + b["wacc"]) ** int(horizonte))
    ev = pv_explicit + pv_terminal
    # TIR sobre inversión inicial explícita: si no hay inversión o raíz, se informa N/D.
    irr = _irr_bisection([-b["inversion_inicial"]] + fcffs) if b["inversion_inicial"] > 0 else None
    return {"proyeccion": rows, "fcff": fcffs, "terminal_value": terminal_value,
            "pv_fcff": pv_explicit, "pv_terminal": pv_terminal, "ev": ev,
            "vpn": ev - b["inversion_inicial"], "tir": irr, "supuestos": b}


def _irr_bisection(cashflows, low=-0.99, high=5.0, iterations=300):
    if not any(x > 0 for x in cashflows) or not any(x < 0 for x in cashflows):
        return None
    def npv(rate):
        return sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cashflows))
    fl, fh = npv(low), npv(high)
    if not math.isfinite(fl) or not math.isfinite(fh) or fl * fh > 0:
        return None
    for _ in range(iterations):
        mid = (low + high) / 2
        fm = npv(mid)
        if abs(fm) < 1e-8:
            return mid
        if fl * fm <= 0:
            high, fh = mid, fm
        else:
            low, fl = mid, fm
    return (low + high) / 2


def construir_escenarios(base: Mapping, horizonte: int) -> dict:
    """Tres escenarios con cinco drivers interrelacionados y supuestos explícitos."""
    b = _validate_inputs(base, horizonte)
    adjustments = {
        "Pesimista": {"crecimiento_ingresos": -0.04, "margen_ebit": -0.03,
                      "capex_pct_ventas": 0.02, "nwc_pct_ventas": 0.02, "wacc": 0.02},
        "Base": {"crecimiento_ingresos": 0.0, "margen_ebit": 0.0,
                 "capex_pct_ventas": 0.0, "nwc_pct_ventas": 0.0, "wacc": 0.0},
        "Optimista": {"crecimiento_ingresos": 0.03, "margen_ebit": 0.02,
                      "capex_pct_ventas": -0.01, "nwc_pct_ventas": -0.01, "wacc": -0.01},
    }
    results = {}
    for name, adj in adjustments.items():
        s = dict(b)
        for driver, delta in adj.items():
            s[driver] += delta
        # No permitir parámetros estructuralmente imposibles.
        s["capex_pct_ventas"] = max(0.0, s["capex_pct_ventas"])
        s["nwc_pct_ventas"] = max(0.0, s["nwc_pct_ventas"])
        s["wacc"] = max(s["g_terminal"] + 0.005, s["wacc"])
        results[name] = {"ajustes": adj, **proyectar_fcff(s, horizonte)}
    return results


def simular_politicas(base: Mapping, horizonte: int, ahorro_capex_pp: float = 0.01,
                      mejora_margen_pp: float = 0.015, costo_implantacion_pct: float = 0.01,
                      minimo_capex_pct: float = 0.03) -> dict:
    """Compara base y dos políticas. Umbrales y efectos son supuestos editables."""
    b = _validate_inputs(base, horizonte)
    for name, val in (("ahorro_capex_pp", ahorro_capex_pp), ("mejora_margen_pp", mejora_margen_pp),
                      ("costo_implantacion_pct", costo_implantacion_pct), ("minimo_capex_pct", minimo_capex_pct)):
        if not math.isfinite(float(val)) or float(val) < 0:
            raise ValueError(f"{name} debe ser finito y no negativo.")
    base_case = proyectar_fcff(b, horizonte)
    capex = dict(b)
    capex["capex_pct_ventas"] = max(float(minimo_capex_pct), b["capex_pct_ventas"] - float(ahorro_capex_pp))
    capex_case = proyectar_fcff(capex, horizonte)
    efficiency = dict(b)
    efficiency["margen_ebit"] = min(1.0, b["margen_ebit"] + float(mejora_margen_pp))
    efficiency_case = proyectar_fcff(efficiency, horizonte)
    # Costo de implementación al año 1: se descuenta tanto del FCFF como del VPN.
    implementation_cost = b["ingresos"] * float(costo_implantacion_pct)
    efficiency_case["fcff"][0] -= implementation_cost
    efficiency_case["proyeccion"][0]["FCFF"] -= implementation_cost
    pv_cost = implementation_cost / (1 + b["wacc"])
    efficiency_case["vpn"] -= pv_cost
    efficiency_case["pv_fcff"] -= pv_cost
    efficiency_case["ev"] -= pv_cost
    efficiency_case["tir"] = _irr_bisection([-b["inversion_inicial"]] + efficiency_case["fcff"]) if b["inversion_inicial"] > 0 else None
    cases = {"Base": base_case, "Optimización CAPEX": capex_case, "Eficiencia operativa": efficiency_case}
    base_vpn = base_case["vpn"]
    base_fcff = sum(base_case["fcff"])
    out = {}
    for name, case in cases.items():
        values = case["fcff"]
        mean = sum(values) / len(values)
        dispersion = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
        out[name] = {
            "vpn": case["vpn"], "delta_vpn": case["vpn"] - base_vpn,
            "ev": case["ev"], "tir": case["tir"], "fcff_total": sum(values),
            "delta_fcff_total": sum(values) - base_fcff,
            "riesgo_dispersion_fcff": dispersion,
            "delta_riesgo_vs_base": dispersion - (sum((x - base_fcff / len(base_case["fcff"])) ** 2 for x in base_case["fcff"]) / len(base_case["fcff"])) ** 0.5,
            "fcff": values, "regla": (
                "Adoptar si ΔVPN > 0 y no se incumplen CAPEX mínimo/operación segura."
                if name == "Optimización CAPEX" else
                "Adoptar si ΔVPN > 0 y el ahorro supera el costo de implantación."
                if name == "Eficiencia operativa" else "Referencia; no es una política."
            ),
        }
    winners = [name for name in ("Optimización CAPEX", "Eficiencia operativa") if out[name]["delta_vpn"] > 0]
    recommendation = ("Evaluar adopción condicionada de: " + ", ".join(winners) +
                      ". Validar supuestos, CAPEX de mantenimiento, ejecución y riesgo.")
    if not winners:
        recommendation = "No adoptar automáticamente ninguna política: ninguna mejora el VPN bajo estos supuestos. Revisar costos, efectos y umbrales."
    return {"resultados": out, "recomendacion_condicionada": recommendation,
            "nota_riesgo": "La dispersión de FCFF entre años es un indicador descriptivo, no una medida probabilística de riesgo."}
