"""Contratos tipados, serializables e inmutables para ejecuciones de agentes."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import uuid4


def _json_safe(value: Any) -> Any:
    """Convierte valores comunes a JSON sin ejecutar ni evaluar contenido."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (ValueError, TypeError):
            pass
    return str(value)


def _snapshot_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_json_safe(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AgentContext:
    """Snapshot de solo lectura lógica; contiene únicamente datos serializables."""
    run_id: str
    task: str
    company: str | None
    ticker: str | None
    snapshot_at: str
    snapshot_hash: str
    currency: str | None = None
    model_inputs: Mapping[str, Any] = field(default_factory=dict)
    model_outputs: Mapping[str, Any] = field(default_factory=dict)
    data_provenance: tuple[Mapping[str, Any], ...] = ()
    quality_flags: tuple[Mapping[str, Any], ...] = ()
    repository_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass(frozen=True)
class AgentFinding:
    agent: str
    status: str
    summary: str
    findings: tuple[Mapping[str, Any], ...] = ()
    evidence: tuple[Mapping[str, Any], ...] = ()
    recommendations: tuple[Mapping[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def build_context(
    *, task: str, model_inputs: Mapping[str, Any] | None = None,
    model_outputs: Mapping[str, Any] | None = None, company: str | None = None,
    ticker: str | None = None, currency: str | None = None,
    data_provenance: list[Mapping[str, Any]] | None = None,
    quality_flags: list[Mapping[str, Any]] | None = None,
    repository_ref: str = "",
) -> AgentContext:
    """Construye un snapshot estable y calcula su hash; no consulta ni muta la app."""
    inputs = _json_safe(model_inputs or {})
    outputs = _json_safe(model_outputs or {})
    provenance = _json_safe(data_provenance or [])
    flags = _json_safe(quality_flags or [])
    payload = {
        "task": task, "company": company, "ticker": ticker, "currency": currency,
        "model_inputs": inputs, "model_outputs": outputs,
        "data_provenance": provenance, "quality_flags": flags,
        "repository_ref": repository_ref,
    }
    return AgentContext(
        run_id=str(uuid4()), task=task, company=company, ticker=ticker,
        snapshot_at=datetime.now(timezone.utc).isoformat(),
        snapshot_hash=_snapshot_hash(payload), currency=currency,
        model_inputs=inputs, model_outputs=outputs,
        data_provenance=tuple(provenance), quality_flags=tuple(flags),
        repository_ref=repository_ref,
    )
