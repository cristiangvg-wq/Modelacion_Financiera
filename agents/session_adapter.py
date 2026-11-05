"""Adaptador de solo lectura entre la sesión Streamlit y los contratos de agentes."""
from __future__ import annotations

from typing import Any, Mapping


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _row_value(row: Any, *names: str) -> float | None:
    for name in names:
        try:
            value = row[name]
        except (KeyError, TypeError, IndexError):
            continue
        number = _finite(value)
        if number is not None:
            return number
    return None


def build_session_snapshot(
    session_state: Mapping[str, Any],
    logic: Any,
    *,
    repository_ref: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    """Construye un snapshot únicamente desde resultados vigentes de esta sesión.

    Devuelve (payload, None) o (None, motivo). No ejecuta cálculos del modelo,
    no descarga datos y no modifica session_state ni el estado de la lógica.
    """
    company = session_state.get("empresa_sel")
    if not company:
        return None, "Selecciona una empresa en la página principal."

    if bool(session_state.get("modelo_dirty")):
        return None, "Los supuestos cambiaron. Pulsa «Generar todo» en la página principal antes de auditar."

    try:
        metrics = logic.metricas_valoracion_sesion(company)
    except Exception:
        metrics = None
    if not isinstance(metrics, dict):
        return None, "No hay una valoración vigente de la pestaña 4 para esta empresa. Ejecuta «Generar todo»."

    results = session_state.get("resultados")
    if not isinstance(results, Mapping):
        return None, "No se encontraron resultados de la sesión. Ejecuta «Generar todo»."

    tab1 = results.get("tab1")
    if not isinstance(tab1, (tuple, list)) or len(tab1) <= 6:
        return None, "No se encontró la proyección de la pestaña 1. Ejecuta «Generar todo»."

    projection = tab1[6]
    if projection is None or getattr(projection, "empty", True):
        return None, "La proyección FCFF está vacía; revisa la pestaña 1."

    try:
        last_row = projection.iloc[-1]
    except (AttributeError, IndexError, KeyError, TypeError):
        return None, "No se pudo leer el último año de la proyección FCFF."

    params = session_state.get("params")
    params = params if isinstance(params, Mapping) else {}
    key_suffix = str(company)[:48]

    def current(widget_prefix: str, param_name: str, default: Any = None) -> float | None:
        raw = session_state.get(f"{widget_prefix}_{key_suffix}")
        if raw is None:
            raw = params.get(param_name, default)
        return _finite(raw)

    de_ratio = current("de", "de_ratio")
    kd = current("kd", "kd")
    tax = current("tax", "tax")
    g = current("g", "g")
    beta_u = current("bu", "beta_u")
    rf = current("rf", "rf", session_state.get("rf"))
    erp = current("erp", "erp", session_state.get("erp"))
    crp = current("crp", "crp", session_state.get("crp"))
    capex_extra = current("cx", "capex_extra", 0.0)
    # Se conservan el método y los insumos exactos del TV de la pestaña 4.
    # fcff_terminal_n1 representa el FCFF normalizado que el motor usó en Gordon.
    fcff_next = _finite(metrics.get("fcff_terminal_n1"))
    terminal_value = _finite(metrics.get("tv_gordon"))
    terminal_method = metrics.get("tv_metodo")

    model_inputs: dict[str, Any] = {}
    if de_ratio is not None and de_ratio >= 0:
        model_inputs["debt_weight"] = de_ratio / (1.0 + de_ratio)
        model_inputs["equity_weight"] = 1.0 / (1.0 + de_ratio)
    for key, value in (
        ("kd", kd), ("tax_rate", tax), ("wacc", _finite(metrics.get("wacc_calc"))),
        ("terminal_growth", _finite(metrics.get("g_usada", metrics.get("g")))),
        ("ke", _finite(metrics.get("ke_calc"))), ("de_ratio", de_ratio),
        ("beta_unlevered", beta_u), ("rf", rf), ("erp", erp), ("crp", crp),
        ("capex_extra", capex_extra), ("fcff_next", fcff_next),
    ):
        if value is not None:
            model_inputs[key] = value
    if terminal_method is not None:
        model_inputs["terminal_method"] = str(terminal_method)

    # Las cifras se extraen de la misma proyección calculada por la pestaña 1.
    nopat = _row_value(last_row, "NOPAT")
    depreciation = _row_value(last_row, "Depreciacion", "Depreciación", "D&A")
    capex = _row_value(last_row, "CAPEX")
    change_nwc = _row_value(last_row, "Delta_NWC", "ΔNWC", "Variacion_NWC")
    fcff = _row_value(last_row, "FCFF")
    for key, value in (
        ("nopat", nopat), ("depreciation", depreciation),
        ("capex", capex), ("change_nwc", change_nwc),
    ):
        if value is not None:
            model_inputs[key] = value

    model_outputs: dict[str, Any] = {}
    reported_wacc = _finite(metrics.get("wacc_calc"))
    if reported_wacc is not None:
        model_outputs["wacc"] = reported_wacc
    if fcff is not None:
        model_outputs["fcff"] = fcff
    if terminal_value is not None:
        model_outputs["terminal_value"] = terminal_value

    company_name = str(company)
    provenance = [{
        "field": "financial_projection",
        "source": "resultado de la pestaña 1 de esta sesión",
        "period": str(getattr(projection, "index", [""])[-1]),
        "currency": metrics.get("moneda"),
    }, {
        "field": "valuation_metrics",
        "source": "métricas guardadas por la pestaña 4 de esta sesión",
    }]
    for field, metric_key in (
        ("financial_source", "fuente_financiera"),
        ("market_source", "fuente_mercado"),
        ("data_quality", "nivel_calidad"),
    ):
        if metrics.get(metric_key):
            provenance.append({"field": field, "source": str(metrics[metric_key])})

    quality_flags = []
    for index, item in enumerate(metrics.get("vetos_calidad") or []):
        quality_flags.append({
            "code": f"MODEL_VETO_{index + 1}",
            "severity": "high",
            "title": "Veto de calidad del modelo",
            "description": str(item),
            "suggested_action": "Resolver el veto en la página principal y volver a ejecutar la valoración.",
        })
    for index, item in enumerate(metrics.get("alertas_modelo") or []):
        quality_flags.append({
            "code": f"MODEL_ALERT_{index + 1}",
            "severity": "medium",
            "title": "Alerta del modelo",
            "description": str(item),
            "suggested_action": "Revisar la alerta y validar su fuente antes de interpretar la valoración.",
        })

    payload = {
        "task": f"Auditoría financiera de la valoración vigente de {company_name}",
        "company": company_name,
        "ticker": metrics.get("ticker"),
        "currency": metrics.get("moneda"),
        "model_inputs": model_inputs,
        "model_outputs": model_outputs,
        "data_provenance": provenance,
        "quality_flags": quality_flags,
        "repository_ref": repository_ref,
    }
    return payload, None
