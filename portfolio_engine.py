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


def proyectar_pesos(pesos, peso_maximo: float, tol: float = 1e-12, tol_residuo: float = 1e-5) -> np.ndarray:
    """Lleva un vector casi factible a 0 ≤ w ≤ peso_maximo con Σw = 1 sin violar el tope.

    Solo corrige residuos numéricos del optimizador (hasta `tol_residuo`): el déficit o
    exceso se reparte entre los activos con holgura (nunca se escala un peso ya topado).
    Entradas materialmente incorrectas (vacías, no finitas, negativas, por encima del
    tope o que no suman ~100 %) se rechazan: no se «reparan» en silencio.
    """
    try:
        cap = float(peso_maximo)
    except (TypeError, ValueError) as exc:
        raise ValueError("Peso máximo inválido.") from exc
    if not np.isfinite(cap) or not 0.0 < cap <= 1.0:
        raise ValueError("El peso máximo debe estar entre 0 y 100 %.")
    w = np.asarray(pesos, dtype=float)
    if w.ndim != 1 or len(w) == 0:
        raise ValueError("Vector de pesos vacío o con dimensiones inválidas.")
    if not np.isfinite(w).all():
        raise ValueError("Los pesos contienen valores no finitos.")
    if len(w) * cap < 1.0 - 1e-9:
        raise ValueError("Peso máximo inviable: n × máximo < 100 %.")
    if w.min() < -tol_residuo or w.max() > cap + tol_residuo or abs(float(w.sum()) - 1.0) > tol_residuo:
        raise ValueError("Pesos fuera de las restricciones más allá del residuo numérico: hay que volver a optimizar.")
    w = np.clip(w, 0.0, cap)
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


def _pesos_validados(pesos, columnas, tol: float = 1e-6) -> np.ndarray:
    """Pesos long-only alineados con `columnas`, finitos y que suman 100 % (si no, error explícito)."""
    cols = [str(c) for c in columnas]
    if isinstance(pesos, (pd.Series, dict)):
        ser = pd.Series(pesos, dtype=float)
        ser.index = [str(i) for i in ser.index]
        faltan, sobran = sorted(set(cols) - set(ser.index)), sorted(set(ser.index) - set(cols))
        if faltan or sobran:
            raise ValueError("Los pesos no corresponden a los activos: "
                             + (f"faltan {', '.join(faltan)}" if faltan else "")
                             + ("; " if faltan and sobran else "") + (f"sobran {', '.join(sobran)}" if sobran else ""))
        w = ser.reindex(cols).to_numpy(dtype=float)
    else:
        w = np.asarray(pesos, dtype=float)
        if w.ndim != 1 or len(w) != len(cols):
            raise ValueError("El número de pesos no coincide con el de activos.")
    if not np.isfinite(w).all():
        raise ValueError("Los pesos contienen valores no finitos.")
    if (w < -tol).any():
        raise ValueError("Pesos negativos: estas métricas son para carteras sin ventas en corto.")
    if abs(float(w.sum()) - 1.0) > tol:
        raise ValueError(f"Los pesos suman {float(w.sum()):.2%}, no 100 %: la cartera no está totalmente invertida.")
    return np.clip(w, 0.0, None)


def metricas_riesgo_historicas(rendimientos: pd.DataFrame, pesos, confianza: float = 0.95,
                               periodos_anuales: int = 252) -> dict:
    """Riesgo de pérdidas con los rendimientos diarios observados de la cartera.

    - VaR y CVaR históricos diarios (pérdidas en positivo) al nivel de confianza.
    - Caída máxima desde un pico (drawdown) del capital acumulado, medida desde el
      capital inicial (1,0): una pérdida el primer día también cuenta.
    - Rendimiento compuesto anual (geométrico) frente a la media aritmética anualizada:
      el aritmético es el insumo del optimizador; el compuesto es lo que creció el capital.
    Los pesos deben ser long-only, finitos, uno por activo y sumar 100 %.
    Son descripciones del pasado (pesos fijos en toda la ventana), no garantías futuras.
    """
    try:
        per = float(periodos_anuales)
    except (TypeError, ValueError) as exc:
        raise ValueError("Periodos por año inválidos.") from exc
    if not np.isfinite(per) or per <= 0:
        raise ValueError("Los periodos por año deben ser positivos.")
    if not 0.5 < float(confianza) < 1.0:
        raise ValueError("Nivel de confianza inválido.")
    r = pd.DataFrame(rendimientos).apply(pd.to_numeric, errors="coerce").dropna()
    if len(r) < 2 or r.shape[1] == 0 or not np.isfinite(r.to_numpy()).all():
        raise ValueError("Rendimientos insuficientes o no finitos.")
    w = _pesos_validados(pesos, r.columns)
    rp = r.to_numpy(dtype=float) @ w
    if (rp < -1).any():
        raise ValueError("Un rendimiento simple no puede ser inferior a −100 %.")
    q = float(np.quantile(rp, 1.0 - float(confianza)))
    cola = rp[rp <= q]
    riqueza = np.concatenate([[1.0], np.cumprod(1.0 + rp)])
    dd = riqueza / np.maximum.accumulate(riqueza) - 1.0
    años = len(rp) / per
    geo = float(riqueza[-1] ** (1.0 / años) - 1.0) if riqueza[-1] > 0 else -1.0
    return {
        "var_diario": max(0.0, -q),
        "cvar_diario": max(0.0, -float(cola.mean())) if len(cola) else None,
        "confianza": float(confianza),
        "max_drawdown": float(dd.min()),
        "retorno_compuesto_anual": geo,
        "retorno_aritmetico_anual": float(rp.mean() * per),
        "observaciones": int(len(rp)),
    }


def retornos_esperados_anclados(mu_hist: pd.Series, vol: pd.Series, anios: float, ancla: pd.Series,
                                incertidumbre_ancla: float = 0.03) -> pd.DataFrame:
    """Retorno esperado = mezcla de la media histórica y un ancla, ponderadas por su precisión.

    peso_hist = (1/se²) / (1/se² + 1/τ²), con se = vol/√años (error estándar de la media anual) y
    τ = incertidumbre del ancla. El ancla es el retorno que exige el riesgo (CAPM) o el precio (TIR
    implícita del DCF). Con 5 años y una volatilidad de 30 %, se ≈ 13 pp y el histórico pesa ≈ 5 %:
    una media de 5 años informa poco sobre el futuro (marco de Damodaran).
    """
    try:
        anios = float(anios)
        tau = float(incertidumbre_ancla)
    except (TypeError, ValueError) as exc:
        raise ValueError("Años e incertidumbre del ancla deben ser numéricos.") from exc
    if not np.isfinite(anios) or anios <= 0 or not np.isfinite(tau) or tau <= 0:
        raise ValueError("Años e incertidumbre del ancla deben ser positivos.")
    mu_hist = pd.Series(mu_hist, dtype=float)
    vol = pd.Series(vol, dtype=float).reindex(mu_hist.index)
    ancla = pd.Series(ancla, dtype=float).reindex(mu_hist.index)
    if ancla.isna().any():
        raise ValueError("Falta el ancla de: " + ", ".join(map(str, ancla[ancla.isna()].index)))
    if vol.isna().any() or (vol <= 0).any():
        raise ValueError("Volatilidades inválidas para ponderar la media histórica.")
    se = vol / np.sqrt(anios)
    w = (1.0 / se ** 2) / (1.0 / se ** 2 + 1.0 / tau ** 2)
    return pd.DataFrame({"historico": mu_hist, "ancla": ancla, "error_estandar": se,
                         "peso_historico": w, "esperado": w * mu_hist + (1.0 - w) * ancla})


def retorno_en_moneda(r_local: float, inflacion_local: float, inflacion_base: float) -> float:
    """Lleva un retorno nominal de una moneda a otra por paridad de inflación (Fisher)."""
    return (1.0 + float(r_local)) * (1.0 + float(inflacion_base)) / (1.0 + float(inflacion_local)) - 1.0


def evaluar_fuera_de_muestra(precios: pd.DataFrame, fraccion: float = 0.7, mu_fijo: pd.Series | None = None,
                             **kw) -> dict:
    """Optimiza con la primera parte de la ventana y mide la cartera en la parte que no vio.

    `mu_fijo` (p. ej. retornos anclados) reemplaza la media de la submuestra; la covarianza sale
    siempre de la submuestra. Devuelve pesos y métricas dentro y fuera de muestra.
    """
    if not 0.3 <= float(fraccion) <= 0.9:
        raise ValueError("La fracción de entrenamiento debe estar entre 30 % y 90 %.")
    r = rendimientos_comunes(precios)
    corte = int(len(r) * float(fraccion))
    if corte < 120 or len(r) - corte < 60:
        raise ValueError("Ventana demasiado corta para separar muestra y prueba (≥ 120 y ≥ 60 días).")
    mu, cov = preparar_estadisticas(precios.loc[: r.index[corte - 1]])
    if mu_fijo is not None:
        mu = pd.Series(mu_fijo, dtype=float).reindex(mu.index)
        if mu.isna().any():
            raise ValueError("Falta el retorno esperado de algún activo.")
    res = optimizar_portafolio(mu, cov, **kw)
    return {
        "pesos": res["pesos"],
        "dentro": metricas_riesgo_historicas(r.iloc[:corte], res["pesos"]),
        "fuera": metricas_riesgo_historicas(r.iloc[corte:], res["pesos"]),
        "corte": str(r.index[corte - 1])[:10],
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
    frontier = frontier.sort_values("Volatilidad").reset_index(drop=True)
    # Solo la rama eficiente: un punto con más volatilidad y menos retorno que otro ya listado es
    # ineficiente (o un mínimo local del optimizador) y dibujaba una frontera en zigzag.
    eficiente = frontier["Retorno esperado"] >= frontier["Retorno esperado"].cummax() - 1e-9
    return frontier[eficiente].reset_index(drop=True)


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
