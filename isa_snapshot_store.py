"""Persistencia compartida de la última valoración ISA para la presentación ejecutiva."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import math
import requests

TIMEOUT_SECONDS = 12


def _json_safe(value):
    """Convierte escalares NumPy/fechas y valores no finitos a JSON válido."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


TABLE_ENDPOINT = "/rest/v1/isa_valuation_snapshots"
RPC_ENDPOINT = "/rest/v1/rpc/get_isa_latest_snapshot"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "apikey": api_key,
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }


def publish_snapshot(
    *, supabase_url: str, service_role_key: str, metrics: dict[str, Any],
    decision_text: str = "", memo: str = "", kpis: Any = None,
) -> tuple[bool, str]:
    """Publica únicamente ISA. La clave service_role solo debe vivir en la app principal."""
    if not isinstance(metrics, dict) or str(metrics.get("ticker", "")).upper() not in {"ISA", "ISA.CL", "ISA.CO"}:
        return False, "La publicación está limitada a la valoración ISA."
    if metrics.get("vps_modelo") is None or metrics.get("val_ev") is None:
        return False, "La valoración no contiene EV y valor por acción; no se publicó."
    base = (supabase_url or "").strip().rstrip("/")
    key = (service_role_key or "").strip()
    if not base or not key:
        return False, "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY."
    payload = {
        "schema_version": 1,
        "published_at_client": datetime.now(timezone.utc).isoformat(),
        "metrics": _json_safe(metrics),
        "decision_text": str(decision_text or ""),
        "memo": str(memo or ""),
        "kpis": _json_safe(kpis) if isinstance(kpis, (list, dict)) else None,
    }
    row = {
        "ticker": "ISA",
        "company_name": str(metrics.get("empresa") or "ISA"),
        "model_version": "modelacion_logic.tab4_recomendacion",
        "payload": payload,
    }
    try:
        response = requests.post(
            base + TABLE_ENDPOINT + "?on_conflict=ticker",
            headers={**_headers(key), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=row,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code not in (200, 201, 204):
            return False, "Supabase respondió HTTP {}: {}".format(response.status_code, response.text[:500])
        return True, "Valoración ISA publicada."
    except requests.RequestException as exc:
        return False, "No fue posible publicar en Supabase: {}".format(exc)


def fetch_latest_snapshot(
    *, supabase_url: str, anon_key: str, presentation_token: str,
) -> dict[str, Any] | None:
    """Lee mediante RPC validada por token; no concede SELECT directo sobre la tabla."""
    base = (supabase_url or "").strip().rstrip("/")
    key = (anon_key or "").strip()
    token = (presentation_token or "").strip()
    if not base or not key or not token:
        raise ValueError("Configura SUPABASE_URL, SUPABASE_ANON_KEY e ISA_PRESENTATION_TOKEN.")
    try:
        response = requests.post(
            base + RPC_ENDPOINT,
            headers=_headers(key),
            json={"p_token": token},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code in (401, 403):
            raise PermissionError("Token de presentación inválido o sin autorización.")
        if response.status_code != 200:
            raise RuntimeError("Supabase respondió HTTP {}: {}".format(response.status_code, response.text[:400]))
        data = response.json()
        if isinstance(data, list):
            data = data[0] if data else None
        if not data:
            return None
        return data if isinstance(data, dict) else None
    except requests.RequestException as exc:
        raise RuntimeError("No fue posible consultar Supabase: {}".format(exc)) from exc
