"""Agente financiero de primera fase: auditoría determinista, sin LLM ni mutaciones."""
from __future__ import annotations

import math
from typing import Any, Mapping

from agents.contracts import AgentContext, AgentFinding


def _number(mapping: Mapping[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finding(code: str, severity: str, title: str, description: str,
             evidence: dict[str, Any], action: str) -> dict[str, Any]:
    return {
        "id": code, "severity": severity, "title": title,
        "description": description, "evidence_ref": evidence,
        "impact": "Puede afectar la consistencia o interpretación de la valoración.",
        "suggested_action": action, "confidence": "high" if evidence else "limited",
    }


def audit_financial_context(context: AgentContext, tolerance: float = 1e-6) -> AgentFinding:
    """Comprueba identidades solo cuando los campos requeridos están presentes.

    Claves admitidas en model_inputs/model_outputs:
      WACC: debt_weight, equity_weight, kd, ke, tax_rate; output: wacc
      FCFF: ebit, nopat, depreciation, capex, change_nwc; output: fcff
      TV: fcff_next, terminal_growth, wacc; output: terminal_value
    Las tasas se expresan como decimales (p. ej. 0.10 = 10%).
    """
    inputs, outputs = context.model_inputs, context.model_outputs
    findings: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    limitations: list[str] = []
    recommendations: list[dict[str, Any]] = []
    checks_run = 0

    # WACC: los pesos deben sumar 100%; si además hay componentes, comprobar la fórmula.
    dw, ew = _number(inputs, "debt_weight"), _number(inputs, "equity_weight")
    if dw is not None and ew is not None:
        checks_run += 1
        total = dw + ew
        evidence.append({"check": "wacc_weights", "debt_weight": dw, "equity_weight": ew, "sum": total})
        if abs(total - 1.0) > tolerance:
            findings.append(_finding(
                "FIN-WACC-001", "high", "Los pesos de capital no suman 100%",
                f"La suma de los pesos de deuda y patrimonio es {total:.6g}; se esperaba 1.0.",
                {"fields": ["model_inputs.debt_weight", "model_inputs.equity_weight"]},
                "Verificar denominador y base de capitalización; no ajustar los pesos automáticamente.",
            ))
    else:
        limitations.append("No se verificó la suma de pesos WACC: faltan debt_weight o equity_weight.")

    kd, ke, tax, reported_wacc = (
        _number(inputs, "kd"), _number(inputs, "ke"), _number(inputs, "tax_rate"),
        _number(outputs, "wacc"),
    )
    if None not in (dw, ew, kd, ke, tax, reported_wacc):
        checks_run += 1
        expected = dw * kd * (1.0 - tax) + ew * ke
        evidence.append({"check": "wacc_formula", "expected": expected, "reported": reported_wacc})
        if abs(expected - reported_wacc) > max(tolerance, abs(expected) * 1e-4):
            findings.append(_finding(
                "FIN-WACC-002", "high", "El WACC reportado no coincide con sus componentes",
                f"WACC calculado {expected:.6%}; WACC reportado {reported_wacc:.6%}.",
                {"fields": ["debt_weight", "equity_weight", "kd", "ke", "tax_rate", "model_outputs.wacc"]},
                "Revisar pesos, costo de deuda después de impuestos, costo de equity y unidades de tasa.",
            ))
    elif reported_wacc is not None:
        limitations.append("No se recalculó WACC: faltan uno o más componentes (pesos, kd, ke o tax_rate).")

    # FCFF = NOPAT + D&A - CAPEX - variación de NWC.
    ebit, nopat = _number(inputs, "ebit"), _number(inputs, "nopat")
    da, capex, nwc, reported_fcff = (
        _number(inputs, "depreciation"), _number(inputs, "capex"),
        _number(inputs, "change_nwc"), _number(outputs, "fcff"),
    )
    if None not in (nopat, da, capex, nwc, reported_fcff):
        checks_run += 1
        expected = nopat + da - capex - nwc
        evidence.append({"check": "fcff_identity", "expected": expected, "reported": reported_fcff})
        if abs(expected - reported_fcff) > max(tolerance, abs(expected) * 1e-4):
            findings.append(_finding(
                "FIN-FCFF-001", "high", "El FCFF no coincide con la identidad operativa",
                f"FCFF reconstruido {expected:.6g}; FCFF reportado {reported_fcff:.6g}.",
                {"fields": ["nopat", "depreciation", "capex", "change_nwc", "model_outputs.fcff"]},
                "Revisar signos, periodos y unidades de NOPAT, D&A, CAPEX y variación de capital de trabajo.",
            ))
    else:
        limitations.append("No se verificó FCFF: se requieren nopat, depreciation, capex, change_nwc y fcff.")

    # Advertir sobre inputs no finitos o tasa terminal no válida.
    g, wacc = _number(inputs, "terminal_growth"), _number(inputs, "wacc")
    tv = _number(outputs, "terminal_value")
    fcff_next = _number(inputs, "fcff_next")
    if g is not None and wacc is not None:
        checks_run += 1
        evidence.append({"check": "terminal_spread", "wacc": wacc, "terminal_growth": g})
        if wacc <= g:
            findings.append(_finding(
                "FIN-TV-001", "critical", "WACC no supera el crecimiento perpetuo",
                f"WACC ({wacc:.6%}) debe ser mayor que g ({g:.6%}) para aplicar Gordon-Shapiro.",
                {"fields": ["model_inputs.wacc", "model_inputs.terminal_growth"]},
                "Revisar coherencia de moneda, nominalidad, riesgo y crecimiento; no forzar un valor terminal.",
            ))
        elif fcff_next is not None and tv is not None:
            checks_run += 1
            expected_tv = fcff_next / (wacc - g)
            evidence.append({"check": "terminal_value", "expected": expected_tv, "reported": tv})
            if abs(expected_tv - tv) > max(tolerance, abs(expected_tv) * 1e-4):
                findings.append(_finding(
                    "FIN-TV-002", "high", "El valor terminal no coincide con Gordon-Shapiro",
                    f"Valor terminal calculado {expected_tv:.6g}; reportado {tv:.6g}.",
                    {"fields": ["fcff_next", "wacc", "terminal_growth", "model_outputs.terminal_value"]},
                    "Verificar FCFF del periodo siguiente, unidades y consistencia de tasas.",
                ))
    elif tv is not None:
        limitations.append("No se verificó el valor terminal: faltan WACC y/o crecimiento perpetuo.")

    # Señalar calidad del contexto sin inferir ni completar datos.
    for flag in context.quality_flags:
        if isinstance(flag, Mapping):
            severity = str(flag.get("severity", "info")).lower()
            if severity in {"critical", "high", "medium", "low", "info"}:
                findings.append(_finding(
                    f"DATA-{str(flag.get('code', 'FLAG'))[:40]}", severity,
                    str(flag.get("title", "Indicador de calidad de datos")),
                    str(flag.get("description", "Se recibió una alerta de calidad de datos.")),
                    {"source": "context.quality_flags"},
                    str(flag.get("suggested_action", "Revisar la alerta y su fuente.")),
                ))

    critical = any(f["severity"] == "critical" for f in findings)
    high = any(f["severity"] == "high" for f in findings)
    status = "blocked" if critical else "warning" if high or findings or limitations else "ok"
    summary = (
        f"Se ejecutaron {checks_run} comprobaciones financieras; "
        f"se encontraron {len(findings)} hallazgos y {len(limitations)} limitaciones."
    )
    if findings:
        recommendations = [{"priority": f["severity"], "action": f["suggested_action"], "finding_id": f["id"]} for f in findings]
    return AgentFinding(
        agent="financial_agent", status=status, summary=summary,
        findings=tuple(findings), evidence=tuple(evidence),
        recommendations=tuple(recommendations), limitations=tuple(limitations),
    )
