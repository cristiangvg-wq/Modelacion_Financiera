"""Motor independiente de optimización de portafolios.

Las rentabilidades históricas son estimaciones, no pronósticos garantizados.
Los precios deben estar ajustados por eventos corporativos y expresados en una
moneda de análisis común antes de llamar a estas funciones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def rendimientos_comunes(precios: pd.DataFrame, min_observaciones: int = 120) -> pd.DataFrame:
    """Rendimientos simples diarios en fechas comunes, sin inventar precios faltantes."""
    if precios is None or precios.empty:
        raise ValueError("No hay precios para construir el portafolio.")
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
    r = p.pct_change(fill_method=None).dropna()
    if len(r) < min_observaciones:
        raise ValueError("La muestra de rendimientos es demasiado corta.")
    return r


def covarianza_ledoit_wolf(rendimientos) -> tuple[np.ndarray, float]:
    """Covarianza con contracción de Ledoit-Wolf (2004) hacia una matriz escalar μ·I.

    Σ_LW = (1 − α)·S + α·μ·I, con α estimado de los datos (misma fórmula que
    sklearn.covariance.LedoitWolf, sin añadir esa dependencia). Reduce el error de
    estimación de las correlaciones; no corrige el error de la media.
    Devuelve (matriz por periodo, α).
    """
    x = np.asarray(rendimientos, dtype=float)
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 1 or not np.isfinite(x).all():
        raise ValueError("Rendimientos inválidos para la covarianza.")
    n, p = x.shape
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / n
    mu = float(np.trace(s)) / p
    delta = float(((s - mu * np.eye(p)) ** 2).sum()) / p
    beta = float(sum(((np.outer(row, row) - s) ** 2).sum() for row in xc)) / (p * n * n)
    beta = min(beta, delta)
    alpha = 0.0 if delta <= 0 else beta / delta
    cov = (1.0 - alpha) * s + alpha * mu * np.eye(p)
    # Corrección a la covarianza muestral insesgada (n − 1) para ser comparable con DataFrame.cov().
    return cov * n / (n - 1), float(alpha)


def preparar_estadisticas(
    precios: pd.DataFrame,
    periodos_anuales: int = 252,
    min_observaciones: int = 120,
    contraccion: bool = True,
) -> tuple[pd.Series, pd.DataFrame]:
    """Calcula media aritmética y covarianza anualizadas desde precios.

    Con `contraccion=True` (por defecto) la covarianza usa Ledoit-Wolf: los pesos
    óptimos dependen menos de correlaciones estimadas con ruido. El α aplicado queda
    en ``cov.attrs["contraccion_alpha"]``.
    """
    if precios is None or precios.empty:
        raise ValueError("No hay precios para construir el portafolio.")
    if periodos_anuales <= 0 or min_observaciones < 2:
        raise ValueError("Parámetros de anualización/muestra inválidos.")
    returns = rendimientos_comunes(precios, min_observaciones)
    mu = returns.mean() * float(periodos_anuales)
    alpha = 0.0
    if contraccion:
        lw, alpha = covarianza_ledoit_wolf(returns.to_numpy(dtype=float))
        cov = pd.DataFrame(lw * float(periodos_anuales), index=returns.columns, columns=returns.columns)
    else:
        cov = returns.cov() * float(periodos_anuales)
    matrix = cov.to_numpy(dtype=float)
    if not np.isfinite(mu.to_numpy(dtype=float)).all() or not np.isfinite(matrix).all():
        raise ValueError("Retornos o covarianza contienen valores no finitos.")
    matrix = (matrix + matrix.T) / 2.0
    if float(np.linalg.eigvalsh(matrix).min()) < -1e-8:
        raise ValueError("La covarianza no es semidefinida positiva; revisar datos.")
    out = pd.DataFrame(matrix, index=mu.index, columns=mu.index)
    out.attrs["contraccion_alpha"] = alpha
    return mu, out


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
    # Antes: recortar al máximo y volver a dividir por la suma. Esa división podía dejar
    # un peso por encima del máximo. Ahora se proyecta sobre {0 ≤ w ≤ máx, Σw = 1}
    # repartiendo el residuo solo entre los activos que aún tienen holgura.
    weights = proyectar_pesos(weights, peso_maximo)
    metrics = metricas_portafolio(weights, m, c, rf)
    return {
        "pesos": pd.Series(weights, index=tickers, name="Peso"),
        **metrics, "objetivo": objetivo, "solver_success": bool(result.success),
    }


def proyectar_pesos(pesos, peso_maximo: float, tol: float = 1e-12) -> np.ndarray:
    """Lleva un vector casi factible a 0 ≤ w ≤ peso_maximo con Σw = 1 sin violar el tope.

    Corrige solo residuos numéricos del optimizador: el déficit o exceso se reparte
    proporcionalmente entre los activos con holgura (nunca se escala un peso ya topado).
    """
    w = np.clip(np.asarray(pesos, dtype=float), 0.0, float(peso_maximo))
    cap = float(peso_maximo)
    if len(w) * cap < 1.0 - 1e-9:
        raise ValueError("Peso máximo inviable: n × máximo < 100 %.")
    for _ in range(len(w) + 2):
        resto = 1.0 - float(w.sum())
        if abs(resto) <= tol:
            break
        if resto > 0:
            libres = w < cap - tol
            base = w[libres] if w[libres].sum() > tol else np.ones(int(libres.sum()))
            w[libres] = np.minimum(cap, w[libres] + resto * base / base.sum())
        else:
            activos = w > tol
            w[activos] = np.maximum(0.0, w[activos] + resto * w[activos] / w[activos].sum())
    if abs(float(w.sum()) - 1.0) > 1e-9 or w.max() > cap + 1e-12 or w.min() < 0:
        raise RuntimeError("No se pudo ajustar los pesos a las restricciones.")
    return w


def metricas_riesgo_historicas(rendimientos: pd.DataFrame, pesos, confianza: float = 0.95,
                               periodos_anuales: int = 252) -> dict:
    """Riesgo de pérdidas con los rendimientos diarios observados de la cartera.

    - VaR y CVaR históricos diarios (pérdidas en positivo) al nivel de confianza.
    - Caída máxima desde un pico (drawdown) del capital acumulado.
    - Rendimiento compuesto anual (geométrico) frente a la media aritmética anualizada:
      el aritmético es el insumo del optimizador; el compuesto es lo que creció el capital.
    Son descripciones del pasado, no garantías sobre pérdidas futuras.
    """
    r = pd.DataFrame(rendimientos).apply(pd.to_numeric, errors="coerce").dropna()
    w = pd.Series(pesos, dtype=float)
    if isinstance(pesos, (pd.Series, dict)):
        w = w.reindex(r.columns).fillna(0.0)
    else:
        w.index = r.columns
    if len(r) < 2 or not np.isfinite(r.to_numpy()).all():
        raise ValueError("Rendimientos insuficientes o no finitos.")
    if not 0.5 < float(confianza) < 1.0:
        raise ValueError("Nivel de confianza inválido.")
    rp = r.to_numpy(dtype=float) @ w.to_numpy(dtype=float)
    if (rp < -1).any():
        raise ValueError("Un rendimiento simple no puede ser inferior a −100 %.")
    q = float(np.quantile(rp, 1.0 - float(confianza)))
    cola = rp[rp <= q]
    riqueza = np.cumprod(1.0 + rp)
    dd = riqueza / np.maximum.accumulate(riqueza) - 1.0
    años = len(rp) / float(periodos_anuales)
    geo = float(riqueza[-1] ** (1.0 / años) - 1.0) if años > 0 and riqueza[-1] > 0 else None
    return {
        "var_diario": max(0.0, -q),
        "cvar_diario": max(0.0, -float(cola.mean())) if len(cola) else None,
        "confianza": float(confianza),
        "max_drawdown": float(dd.min()),
        "retorno_compuesto_anual": geo,
        "retorno_aritmetico_anual": float(rp.mean() * periodos_anuales),
        "observaciones": int(len(rp)),
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


MONEDAS_SOPORTADAS_FX = {"COP", "USD"}


def convertir_a_moneda_comun(
    precios: pd.DataFrame,
    monedas: dict,
    fx_cop_por_usd: pd.Series | None,
    moneda_base: str = "USD",
) -> pd.DataFrame:
    """Expresa todas las series de precios en `moneda_base` (COP o USD).

    `fx_cop_por_usd` es la serie diaria de COP por 1 USD (Yahoo: ``COP=X``).
    La conversión se hace fecha a fecha (no con una tasa fija), de modo que la
    volatilidad cambiaria queda incorporada en los retornos del inversionista en
    `moneda_base`. Fechas sin tasa se rellenan con la última tasa conocida
    (máximo 5 días hábiles); si aun así faltan, se descartan.
    """
    base = str(moneda_base or "").upper()
    if base not in MONEDAS_SOPORTADAS_FX:
        raise ValueError(f"Moneda base no soportada: {moneda_base}. Usa COP o USD.")
    if precios is None or precios.empty:
        raise ValueError("No hay precios para convertir.")
    mon = {str(k): str(v or "").upper() for k, v in (monedas or {}).items()}
    faltan = [c for c in precios.columns if not mon.get(str(c))]
    if faltan:
        raise ValueError("Moneda no confirmada para: " + ", ".join(map(str, faltan)))
    no_soportadas = sorted({m for c, m in mon.items() if c in map(str, precios.columns) and m not in MONEDAS_SOPORTADAS_FX})
    if no_soportadas:
        raise ValueError("Monedas sin conversión disponible: " + ", ".join(no_soportadas))
    requiere_fx = any(mon[str(c)] != base for c in precios.columns)
    out = precios.copy().sort_index()
    if not requiere_fx:
        return out
    if fx_cop_por_usd is None or len(fx_cop_por_usd) == 0:
        raise ValueError("Se requiere la serie COP/USD para convertir a una moneda común.")
    fx = pd.to_numeric(pd.Series(fx_cop_por_usd), errors="coerce").replace([np.inf, -np.inf], np.nan)
    fx.index = pd.to_datetime(fx.index)
    out.index = pd.to_datetime(out.index)
    if getattr(fx.index, "tz", None) is not None:
        fx.index = fx.index.tz_localize(None)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)
    fx = fx.sort_index()
    fx = fx[~fx.index.duplicated(keep="last")]
    fx_al = fx.reindex(out.index.union(fx.index)).ffill(limit=5).reindex(out.index)
    if (fx_al.dropna() <= 0).any():
        raise ValueError("La serie COP/USD contiene valores no positivos.")
    for c in out.columns:
        m = mon[str(c)]
        if m == base:
            continue
        if m == "COP" and base == "USD":
            out[c] = out[c] / fx_al
        elif m == "USD" and base == "COP":
            out[c] = out[c] * fx_al
    return out.dropna(how="any")
