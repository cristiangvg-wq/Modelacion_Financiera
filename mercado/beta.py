"""Beta propia por regresión, con su error estándar, y regla explícita frente a la bottom-up.

Hallazgo de la auditoría: la app toma `info["beta"]` de Yahoo, cuyo índice de referencia, ventana
y frecuencia no se publican en la respuesta y no se pueden auditar. Para un emisor de la BVC, con
negociación poco frecuente, una regresión diaria subestima la beta (sesgo por negociación no
sincrónica). Aquí la beta se estima con rendimientos SEMANALES contra un índice que el analista
declara, y se informa el error estándar para decidir si la regresión es informativa.

Regla (coherente con el criterio que ya usa la app para EE. UU.):
  · regresión si n ≥ 104 semanas, error estándar ≤ 0,25 y β bruta ≥ BETA_REGRESION_MIN;
  · si no, beta bottom-up de Damodaran de la industria (L.damodaran_beta), reapalancada.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Solo índices cuyo símbolo en Yahoo es inequívoco. Para Colombia el analista debe pasar el símbolo
# del índice o ETF de referencia que verifique en Yahoo; sin él se usa la beta bottom-up.
INDICE_POR_MERCADO = {"US": "^GSPC"}

MIN_SEMANAS = 104
MAX_ERROR_ESTANDAR = 0.25


def rendimientos_semanales(precios: pd.Series) -> pd.Series:
    """Cierre del viernes (último dato de la semana) → rendimiento simple semanal."""
    s = pd.to_numeric(pd.Series(precios), errors="coerce").dropna()
    s = s[s > 0]
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    return s.resample("W-FRI").last().dropna().pct_change(fill_method=None).dropna()


def beta_regresion(precios_activo: pd.Series, precios_indice: pd.Series) -> dict:
    """MCO de r_activo = α + β·r_índice + ε con rendimientos semanales en fechas comunes."""
    ra, rm = rendimientos_semanales(precios_activo), rendimientos_semanales(precios_indice)
    df = pd.concat({"a": ra, "m": rm}, axis=1, join="inner").dropna()
    n = len(df)
    if n < 20:
        return {"beta": None, "n": n, "motivo": "menos de 20 semanas comunes"}
    x, y = df["m"].to_numpy(), df["a"].to_numpy()
    vx = float(np.var(x, ddof=1))
    if vx <= 0:
        return {"beta": None, "n": n, "motivo": "índice sin variación"}
    beta = float(np.cov(x, y, ddof=1)[0, 1] / vx)
    alfa = float(y.mean() - beta * x.mean())
    resid = y - (alfa + beta * x)
    se = float(np.sqrt((resid @ resid) / (n - 2) / ((x - x.mean()) @ (x - x.mean()))))
    r2 = float(1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean())))
    return {"beta": beta, "error_estandar": se, "r2": r2, "n": n,
            "desde": str(df.index[0].date()), "hasta": str(df.index[-1].date()),
            "beta_blume": 0.67 * beta + 0.33}


def seleccionar_beta_desapalancada(reg: dict | None, de_mercado: float, tasa_fiscal: float,
                                   beta_bottom_up: dict | None, beta_min: float = 0.30) -> dict:
    """β desapalancada (Hamada) con la regla de arriba. No inventa: si no hay nada, lo dice."""
    de = max(float(de_mercado or 0.0), 0.0)
    t = float(tasa_fiscal)
    if reg and reg.get("beta") is not None:
        informativa = (reg["n"] >= MIN_SEMANAS and reg["error_estandar"] <= MAX_ERROR_ESTANDAR
                       and reg["beta"] >= beta_min)
        if informativa:
            bu = reg["beta_blume"] / (1 + (1 - t) * de)
            return {"beta_u": float(bu), "fuente": (
                f"regresión semanal {reg['desde']}→{reg['hasta']} (n={reg['n']}, β={reg['beta']:.2f}, "
                f"e.e.={reg['error_estandar']:.2f}, R²={reg['r2']:.2f}), Blume, desapalancada con D/E {de:.2f}"),
                "metodo": "regresion"}
        motivo = (f"regresión no informativa (n={reg['n']}, β={reg['beta']:.2f}, "
                  f"e.e.={reg.get('error_estandar', float('nan')):.2f})")
    else:
        motivo = (reg or {}).get("motivo", "sin regresión (índice de referencia no declarado)")
    if beta_bottom_up:
        return {"beta_u": float(beta_bottom_up["beta_u"]), "metodo": "bottom_up",
                "fuente": f"bottom-up {beta_bottom_up.get('fuente')}: {beta_bottom_up.get('industria')} ({motivo})"}
    return {"beta_u": None, "metodo": "N/D", "fuente": f"N/D: {motivo} y sin industria Damodaran"}
