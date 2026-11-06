"""Fachada pública para crear snapshots y ejecutar auditorías de solo lectura."""
from __future__ import annotations

from typing import Any, Mapping

from agents.contracts import build_context
from agents.coordinator import run_financial_audit


def audit_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Valida un payload básico y ejecuta la auditoría sin modificarlo."""
    if not isinstance(payload, Mapping):
        raise TypeError("El snapshot debe ser un objeto/diccionario.")
    task = payload.get("task", "Auditoría financiera")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("El campo 'task' debe ser un texto no vacío.")
    for key in ("model_inputs", "model_outputs"):
        if key in payload and not isinstance(payload[key], Mapping):
            raise TypeError(f"El campo '{key}' debe ser un objeto/diccionario.")
    context = build_context(
        task=task,
        company=payload.get("company"), ticker=payload.get("ticker"),
        currency=payload.get("currency"),
        model_inputs=payload.get("model_inputs", {}),
        model_outputs=payload.get("model_outputs", {}),
        data_provenance=payload.get("data_provenance", []),
        quality_flags=payload.get("quality_flags", []),
        repository_ref=payload.get("repository_ref", ""),
    )
    return run_financial_audit(context)
