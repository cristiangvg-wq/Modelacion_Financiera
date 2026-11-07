"""API privada de escenarios ISA: reutiliza el DCF oficial de modelacion_logic."""
from __future__ import annotations

import hmac
import math
import os
from typing import Any

import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import modelacion_logic as ml

app = FastAPI(
    title="ISA Scenario Engine",
    version="1.0.0",
    description="Servicio privado de escenarios que reutiliza el motor financiero Python.",
)


class Parameters(BaseModel):
    wacc: float = Field(gt=0.0, le=0.50)
    g: float = Field(ge=-0.05, le=0.15)
    ebitda_margin: float = Field(ge=0.20, le=0.85)


class ScenarioRequest(BaseModel):
    metrics: dict[str, Any]
    parameters: Parameters


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} debe ser numérico.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} debe ser finito.")
    return number


def _snapshot_inputs(metrics: dict[str, Any]) -> tuple[list[dict], dict, dict]:
    if str(metrics.get("ticker") or "").upper() not in {"ISA", "ISA.CL", "ISA.CO"}:
        raise ValueError("El motor de escenarios está limitado a snapshots ISA.")
    rows = metrics.get("proyeccion_sensibilidad")
    bridge = metrics.get("bridge")
    assumptions = metrics.get("supuestos") or {}
    if not isinstance(rows, list) or not rows:
        raise ValueError(
            "La publicación ISA no contiene proyeccion_sensibilidad. "
            "Actualiza el motor Python y vuelve a publicar la valoración."
        )
    if not isinstance(bridge, dict) or not isinstance(assumptions, dict):
        raise ValueError("El snapshot no contiene el puente EV→Equity y los supuestos oficiales.")
    required = {"Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "Delta_NWC"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not required.issubset(row):
            raise ValueError(f"La proyección del año {index + 1} está incompleta.")
        for key in required:
            _finite(row[key], f"{key} año {index + 1}")
    if not bridge.get("acciones") or _finite(bridge["acciones"], "acciones") <= 0:
        raise ValueError("El snapshot no contiene un número de acciones válido.")
    return rows, bridge, assumptions


def _projection_for_margin(rows: list[dict], assumptions: dict, target_margin: float):
    frame = pd.DataFrame(rows)
    revenues = frame["Ingresos"].astype(float)
    baseline = float((frame["EBITDA"].astype(float) / revenues).mean())
    delta_margin = target_margin - baseline
    # El margen EBITDA cambia el EBIT en la misma variación: D&A y demás drivers
    # permanecen constantes, respetando la identidad FCFF del modelo central.
    frame["EBIT"] = frame["EBIT"].astype(float) + revenues * delta_margin
    frame["EBITDA"] = revenues * target_margin
    tax = _finite(assumptions.get("tax"), "tax")
    frame = ml.recalcular_fcff(frame, tax=tax, capex_extra=0.0)
    fcff = [float(x) for x in frame["FCFF"].tolist()]
    nopat_final = float(frame["NOPAT"].iloc[-1])
    ebitda_final = float(frame["EBITDA"].iloc[-1])
    return fcff, nopat_final, ebitda_final, baseline


def _dcf(metrics: dict, bridge: dict, assumptions: dict, parameters: dict):
    rows, _, _ = _snapshot_inputs(metrics)
    fcff, nopat_final, ebitda_final, baseline_margin = _projection_for_margin(
        rows, assumptions, parameters["ebitda_margin"]
    )
    wacc = _finite(parameters["wacc"], "WACC")
    growth = _finite(parameters["g"], "g")
    if wacc <= growth:
        raise ValueError("WACC debe ser estrictamente mayor que g.")
    g_max = _finite(assumptions.get("g_max_macro", 0.05), "g_max_macro")
    ronic_terminal = metrics.get("ronic_terminal")
    ronic_spread = None
    if ronic_terminal is not None:
        ronic_spread = _finite(ronic_terminal, "ronic_terminal") - wacc
    market_price = metrics.get("precio_mercado_moneda_modelo")
    if market_price is None:
        market_price = metrics.get("precio_mercado")
    result = ml.valoracion_dcf(
        fcff,
        wacc,
        growth,
        deuda_neta=bridge.get("deuda_neta", 0.0),
        caja=bridge.get("caja", 0.0),
        nci=bridge.get("nci", 0.0),
        otros_claims=bridge.get("otros_claims", 0.0),
        asociados=bridge.get("asociados", 0.0),
        acciones=bridge.get("acciones"),
        precio_mercado=market_price,
        exit_multiple=bridge.get("exit_multiple", 0.0),
        ebitda_salida=ebitda_final,
        mid_year=bool(assumptions.get("mid_year", True)),
        g_max_macro=g_max,
        nopat_final=nopat_final,
        ronic_spread=ronic_spread,
        deuda_es_bruta=bool(bridge.get("deuda_es_bruta", False)),
        frac_transcurrida=float(bridge.get("frac_transcurrida") or 0.0),
        t_valoracion=float(bridge.get("t_valoracion") or 0.0),
    )
    return result, fcff, baseline_margin


def _compact(result: dict) -> dict:
    keys = (
        "EV", "Equity_Value", "value_per_share", "upside_pct", "WACC",
        "g_used", "PV_FCFF", "PV_TV", "TV", "tv_pct_ev", "mult_terminal",
    )
    output = {}
    for key in keys:
        value = result.get(key)
        if value is None:
            output[key] = None
        else:
            number = float(value)
            output[key] = number if math.isfinite(number) else None
    return output


def calculate_scenario(metrics: dict, parameters: dict) -> dict:
    rows, bridge, assumptions = _snapshot_inputs(metrics)
    current = {
        "wacc": _finite(parameters["wacc"], "WACC"),
        "g": _finite(parameters["g"], "g"),
        "ebitda_margin": _finite(parameters["ebitda_margin"], "margen EBITDA"),
    }
    base_result, _, baseline_margin = _dcf(metrics, bridge, assumptions, current)

    def case(wacc: float, growth: float, margin: float) -> dict:
        p = {"wacc": max(0.04, wacc), "g": growth, "ebitda_margin": min(0.85, max(0.20, margin))}
        p["g"] = min(p["g"], p["wacc"] - 0.01)
        result, _, _ = _dcf(metrics, bridge, assumptions, p)
        return {"parameters": p, **_compact(result)}

    scenarios = {
        "Bear": case(current["wacc"] + 0.015, current["g"] - 0.005, current["ebitda_margin"] - 0.02),
        "Base": {"parameters": current, **_compact(base_result)},
        "Bull": case(current["wacc"] - 0.01, current["g"] + 0.005, current["ebitda_margin"] + 0.02),
    }

    wacc_grid = [max(0.04, current["wacc"] + step) for step in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    growth_grid = [max(0.005, current["g"] + step) for step in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    sensitivity = []
    for w in sorted(set(round(x, 6) for x in wacc_grid)):
        cells = []
        for g in sorted(set(round(x, 6) for x in growth_grid)):
            if g >= w:
                cells.append({"g": g, "EV": None, "Equity_Value": None, "value_per_share": None, "valid": False})
                continue
            result, _, _ = _dcf(metrics, bridge, assumptions, {**current, "wacc": w, "g": g})
            cell = _compact(result)
            cells.append({"g": g, "EV": cell["EV"], "Equity_Value": cell["Equity_Value"],
                          "value_per_share": cell["value_per_share"], "valid": True})
        sensitivity.append({"wacc": w, "cells": cells})

    base_equity = _compact(base_result)["Equity_Value"]
    tornado = []
    shocks = (
        ("WACC", {"wacc": -0.01}, {"wacc": 0.01}),
        ("Crecimiento perpetuo", {"g": -0.005}, {"g": 0.005}),
        ("Margen EBITDA", {"ebitda_margin": -0.01}, {"ebitda_margin": 0.01}),
    )
    for name, low_change, high_change in shocks:
        impacts = []
        for change in (low_change, high_change):
            p = dict(current)
            for key, delta in change.items():
                p[key] += delta
            p["wacc"] = max(0.04, p["wacc"])
            p["g"] = min(p["g"], p["wacc"] - 0.01)
            p["ebitda_margin"] = min(0.85, max(0.20, p["ebitda_margin"]))
            result, _, _ = _dcf(metrics, bridge, assumptions, p)
            equity = _compact(result)["Equity_Value"]
            impacts.append(equity - base_equity if equity is not None and base_equity is not None else None)
        tornado.append({"driver": name, "delta_low": impacts[0], "delta_high": impacts[1]})

    official_ev = metrics.get("val_ev")
    return {
        "source_engine": "modelacion_logic.valoracion_dcf",
        "currency": metrics.get("moneda", "COP"),
        "unit": metrics.get("unidad_modelo", "Unidad del snapshot oficial"),
        "parameters": current,
        "base": _compact(base_result),
        "scenarios": scenarios,
        "sensitivity": sensitivity,
        "tornado": tornado,
        "diagnostics": {
            "official_ev": official_ev,
            "scenario_ev_delta_vs_official": (
                _compact(base_result)["EV"] - float(official_ev)
                if official_ev is not None else None
            ),
            "baseline_margin_from_projection": baseline_margin,
            "margin_adjustment_applied": current["ebitda_margin"] - baseline_margin,
            "official_publication_is_unchanged": True,
            "calculation_is_persisted": False,
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "engine": "modelacion_logic.valoracion_dcf"}


@app.post("/v1/scenario")
def run_scenario(payload: ScenarioRequest, authorization: str | None = Header(default=None)):
    expected = os.environ.get("SCENARIO_API_TOKEN", "")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="No autorizado.")
    try:
        return calculate_scenario(payload.metrics, payload.parameters.model_dump())
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # No exponer trazas, credenciales ni detalles internos al consumidor HTTP.
        raise HTTPException(status_code=500, detail="No fue posible calcular el escenario con el motor financiero.") from exc
