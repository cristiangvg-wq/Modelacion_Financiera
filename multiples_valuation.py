"""Independent enterprise valuation using trading comparables multiples.

All monetary inputs must use the same unit. EBITDA must be positive. Peer multiples
must be market-observed or manually verified; the module never invents missing data.
"""
from __future__ import annotations

import math
from statistics import median


def valoracion_por_multiplos(
    ebitda_objetivo: float,
    multiples_comparables,
    deuda_neta: float = 0.0,
    acciones_millones: float | None = None,
) -> dict:
    """Value enterprise and equity from the median EV/EBITDA of valid comparables.

    Monetary units for EBITDA, EV and net debt must match. If monetary values are in
    billions and shares are in millions, equity/share = equity * 1,000 / shares.
    """
    try:
        ebitda = float(ebitda_objetivo)
        deuda = float(deuda_neta)
    except (TypeError, ValueError) as exc:
        raise ValueError("EBITDA y deuda neta deben ser numéricos.") from exc
    if not math.isfinite(ebitda) or ebitda <= 0:
        raise ValueError("El EBITDA objetivo debe ser positivo y finito.")
    if not math.isfinite(deuda):
        raise ValueError("La deuda neta debe ser finita.")

    valid = []
    for value in multiples_comparables or []:
        try:
            m = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(m) and 0 < m <= 80:
            valid.append(m)
    if not valid:
        raise ValueError("Se necesita al menos un múltiplo EV/EBITDA válido y verificado.")

    valid.sort()
    mult_med = float(median(valid))
    ev = ebitda * mult_med
    equity = ev - deuda
    shares = None
    if acciones_millones not in (None, ""):
        try:
            shares = float(acciones_millones)
        except (TypeError, ValueError) as exc:
            raise ValueError("Las acciones en circulación deben ser numéricas.") from exc
        if not math.isfinite(shares) or shares <= 0:
            raise ValueError("Las acciones en circulación deben ser positivas.")
    per_share = equity * 1000.0 / shares if shares is not None else None
    q1 = float(valid[(len(valid) - 1) // 4]) if len(valid) < 4 else _percentile(valid, 0.25)
    q3 = float(valid[(3 * (len(valid) - 1)) // 4]) if len(valid) < 4 else _percentile(valid, 0.75)
    return {
        "multiple_mediano": mult_med,
        "enterprise_value": ev,
        "equity_value": equity,
        "valor_por_accion": per_share,
        "n_comparables": len(valid),
        "multiples_validos": valid,
        "multiple_min": float(valid[0]),
        "multiple_max": float(valid[-1]),
        "q1": q1,
        "q3": q3,
    }


def _percentile(sorted_values, q: float) -> float:
    """Linear-interpolated percentile, independent of numpy/pandas."""
    if not sorted_values:
        raise ValueError("No hay valores para calcular el percentil.")
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    weight = pos - lo
    return float(sorted_values[lo] * (1 - weight) + sorted_values[hi] * weight)
