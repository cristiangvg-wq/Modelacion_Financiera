"""Coordinador inicial: flujo explícito y determinista, sin llamadas LLM."""
from __future__ import annotations

from typing import Any

from agents.contracts import AgentContext
from agents.financial_agent import audit_financial_context


def run_financial_audit(context: AgentContext) -> dict[str, Any]:
    """Ejecuta el agente financiero y devuelve un informe serializable.

    El coordinador no modifica el contexto, los parámetros ni el estado de Streamlit.
    """
    result = audit_financial_context(context)
    blocked = result.status == "blocked"
    warning = result.status in {"warning", "error"}
    return {
        "run_id": context.run_id,
        "task": context.task,
        "company": context.company,
        "ticker": context.ticker,
        "snapshot_at": context.snapshot_at,
        "snapshot_hash": context.snapshot_hash,
        "repository_ref": context.repository_ref,
        "status": "BLOQUEADO" if blocked else "ADVERTENCIAS" if warning else "APROBADO PARA REVISIÓN",
        "approval_required": True,
        "changes_applied": False,
        "agent_results": [result.to_dict()],
    }
