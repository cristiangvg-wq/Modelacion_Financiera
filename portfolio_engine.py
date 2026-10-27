"""Motor independiente de optimización de portafolios.

Las rentabilidades históricas son estimaciones, no pronósticos garantizados.
Los precios deben estar ajustados por eventos corporativos y expresados en una
moneda de análisis común antes de llamar a estas funciones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def preparar_estadisticas(
    precios: pd.DataFrame,
    periodos_anuales: int = 252,
    min_observaciones: int = 120,
) -> tuple[pd.Series, pd.DataFrame]:
    """Calcula media aritmética y covarianza anualizadas desde precios."""
    if precios is None or precios.empty:
        raise ValueError("No hay precios para construir el portafolio.")
    if periodos_anuales <= 0 or min_observaciones < 2:
        raise ValueError("Parámetros de anualización/muestra inválidos.")
    p = precios.copy().sort_index()
    p = p.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    p = p.dropna(axis=1, thresh=min_observaciones + 1)
    if p.shape[1] < 2:
        raise ValueError("Se necesitan al menos dos activos con historia suficiente.")
    p = p.dropna(axis=0, how="any")
    if len(p) < min_observaciones + 1:
        raise ValueError("No hay suficientes fechas comunes entre los activos.")
    if (p <= 0).any().any():
        raise ValueError("Los precios deben ser estrictamente positivos.")
    returns = p.pct_change(fill_method=None).dropna()
    if len(returns) < min_observaciones:
        raise ValueError("La muestra de rendimientos es demasiado corta.")
    mu = returns.mean() * float(periodos_anuales)
    cov = returns.cov() * float(periodos_anuales)
    matrix = cov.to_numpy(dtype=float)
    if not np.isfinite(mu.to_numpy(dtype=float)).all() or not np.isfinite(matrix).all():
        raise ValueError("Retornos o covarianza contienen valores no finitos.")
    matrix = (matrix + matrix.T) / 2.0
    if float(np.linalg.eigvalsh(matrix).min()) < -1e-8:
        raise ValueError("La covarianza no es semidefinida positiva; revisar datos.")
    return mu, pd.DataFrame(matrix, index=mu.index, columns=mu.index)


def metricas_portafolio(pesos, mu, cov, tasa_libre_riesgo: float = 0.0) -> dict:
    """Retorno esperado, volatilidad y Sharpe anualizados."""
    w = np.asarray(pesos, dtype=float)
    m = np.asarray(mu, dtype=float)
    c = np.asarray(cov, dtype=float)
    rf = float(tasa_libre_riesgo)
    if w.ndim != 1 or m.ndim != 1 or len(w) == 0 or len(w) != len(m):
        raise ValueError("Dimensiones incompatibles entre pesos y retornos; se requiere al menos un activo.")
    if c.shape != (len(w), len(w)):
        raise ValueError("Dimensión de covarianza incompatible.")
    if not np.isfinite(w).all() or not np.isfinite(m).all() or not np.isfinite(c).all() or not np.isfinite(rf):
        raise ValueError("Pesos, retornos, covarianza y RF deben ser finitos.")
    if not np.allclose(c, c.T, rtol=0.0, atol=1e-8):
        raise ValueError("La covarianza debe ser simétrica.")
    if float(np.linalg.eigvalsh((c + c.T) / 2.0).min()) < -1e-8:
        raise ValueError("La covarianza no es semidefinida positiva.")
    if not np.isclose(float(w.sum()), 1.0, rtol=0.0, atol=1e-6):
        raise ValueError("Los pesos deben sumar 1 (100% del capital invertido).")
    ret = float(w @ m)
    var = float(w @ c @ w)
    if var < -1e-10:
        raise ValueError("Varianza negativa: revisar la matriz de covarianza.")
    vol = float(np.sqrt(max(var, 0.0)))
    sharpe = (ret - rf) / vol if vol > 1e-12 else None
    return {"retorno_esperado": ret, "volatilidad": vol, "sharpe": sharpe}


def optimizar_portafolio(
    mu: pd.Series,
    cov: pd.DataFrame,
    objetivo: str = "max_sharpe",
    tasa_libre_riesgo: float = 0.0,
    peso_maximo: float = 0.35,
    retorno_objetivo: float | None = None,
) -> dict:
    """Optimiza una cartera long-only totalmente invertida."""
    tickers = list(mu.index)
    m = mu.to_numpy(dtype=float)
    c = cov.loc[tickers, tickers].to_numpy(dtype=float)
    n, rf = len(tickers), float(tasa_libre_riesgo)
    if n < 2 or len(set(tickers)) != n:
        raise ValueError("Se requieren al menos dos activos únicos.")
    if not np.isfinite(m).all() or not np.isfinite(c).all() or not np.isfinite(rf):
        raise ValueError("Inputs de optimización no finitos.")
    if not (0 < peso_maximo <= 1):
        raise ValueError("peso_maximo debe estar en (0, 1].")
    if n * peso_maximo < 1 - 1e-12:
        raise ValueError("El peso máximo es incompatible con invertir el 100%.")
    if not np.allclose(c, c.T, atol=1e-8):
        raise ValueError("La covarianza debe ser simétrica.")
    if float(np.linalg.eigvalsh((c + c.T) / 2.0).min()) < -1e-8:
        raise ValueError("La covarianza no es semidefinida positiva.")
    bounds = [(0.0, float(peso_maximo)) for _ in range(n)]
    x0 = np.repeat(1.0 / n, n)
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]

    def volatility(w):
        return float(np.sqrt(max(float(w @ c @ w), 0.0)))

    if objetivo == "min_volatility":
        objective = volatility
    elif objetivo == "max_sharpe":
        def objective(w):
            vol = volatility(w)
            if vol <= 1e-12:
                return 1e6
            return -((float(w @ m) - rf) / vol)
    elif objetivo == "target_return":
        if retorno_objetivo is None or not np.isfinite(float(retorno_objetivo)):
            raise ValueError("Define un retorno objetivo finito.")
        target = float(retorno_objetivo)
        constraints.append({"type": "eq", "fun": lambda w: float(w @ m) - target})
        objective = volatility
    else:
        raise ValueError("Objetivo no reconocido.")

    result = minimize(
        objective, x0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 2000, "ftol": 1e-10},
    )
    if not result.success:
        raise RuntimeError(f"El optimizador no convergió: {result.message}")
    weights = np.asarray(result.x, dtype=float)
    if (
        not np.isfinite(weights).all()
        or weights.min() < -1e-6
        or weights.max() > peso_maximo + 1e-6
        or abs(float(weights.sum()) - 1.0) > 1e-5
    ):
        raise RuntimeError("La solución no cumple las restricciones.")
    weights = np.clip(weights, 0.0, float(peso_maximo))
    weights /= weights.sum()
    metrics = metricas_portafolio(weights, m, c, rf)
    return {
        "pesos": pd.Series(weights, index=tickers, name="Peso"),
        **metrics, "objetivo": objetivo, "solver_success": bool(result.success),
    }


def construir_frontera(
    mu: pd.Series,
    cov: pd.DataFrame,
    tasa_libre_riesgo: float = 0.0,
    peso_maximo: float = 0.35,
    n_puntos: int = 25,
) -> pd.DataFrame:
    """Construye una frontera aproximada, omitiendo objetivos inviables."""
    if n_puntos < 3:
        raise ValueError("Usa al menos tres puntos.")
    targets = np.linspace(float(mu.min()), float(mu.max()), int(n_puntos))
    rows = []
    for target in targets:
        try:
            result = optimizar_portafolio(
                mu, cov, objetivo="target_return",
                tasa_libre_riesgo=tasa_libre_riesgo,
                peso_maximo=peso_maximo, retorno_objetivo=float(target),
            )
            rows.append({
                "Retorno esperado": result["retorno_esperado"],
                "Volatilidad": result["volatilidad"],
                "Sharpe": result["sharpe"],
            })
        except (ValueError, RuntimeError):
            continue
    frontier = pd.DataFrame(rows)
    if frontier.empty:
        raise RuntimeError("No se pudo construir la frontera con estas restricciones.")
    return frontier.sort_values("Volatilidad").reset_index(drop=True)
