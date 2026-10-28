"""Optimizador: pesos dentro de los límites después del ajuste final; contracción y métricas de riesgo."""
import numpy as np
import pandas as pd
import pytest

import portfolio_engine as P


def _precios(n=400, k=4, semilla=7):
    rng = np.random.default_rng(semilla)
    r = rng.normal(0.0005, 0.012, (n, k)) + rng.normal(0, 0.006, (n, 1))
    idx = pd.bdate_range("2024-01-01", periods=n + 1)
    return pd.DataFrame(100 * np.cumprod(np.vstack([np.ones(k), 1 + r]), axis=0), index=idx,
                        columns=[f"A{i}" for i in range(k)])


def test_proyeccion_no_supera_el_maximo():
    """Caso de la auditoría: recortar y volver a dividir dejaba pesos sobre el 35 %."""
    w = P.proyectar_pesos([0.3500002, 0.3500002, 0.2999996], 0.35)
    assert w.max() <= 0.35 + 1e-12
    assert w.sum() == pytest.approx(1.0, abs=1e-12)
    w = P.proyectar_pesos([0.350004, 0.350004, 0.25, 0.049992], 0.35)
    assert w.max() <= 0.35 + 1e-12 and w.min() >= 0 and w.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("pesos,maximo", [
    ([], 0.5),                          # vacío
    ([np.nan, 0.5, 0.5], 0.5),          # no finito
    ([np.inf, 0.0, 0.0], 0.5),
    ([0.5, 0.5], 0.0),                  # tope nulo
    ([0.5, 0.5], -0.2),                 # tope negativo
    ([0.5, 0.5], 1.5),                  # tope > 100 %
    ([-0.2, 0.6, 0.6], 0.6),            # negativo material
    ([0.36, 0.36, 0.25, 0.03], 0.35),   # 1 pp sobre el tope: no es residuo numérico
    ([0.2, 0.2, 0.2], 0.5),             # suma 60 %
    ([[0.5, 0.5]], 0.5),                # dimensiones
])
def test_proyeccion_rechaza_entradas_invalidas(pesos, maximo):
    with pytest.raises(ValueError):
        P.proyectar_pesos(pesos, maximo)


def test_proyeccion_en_el_limite_de_factibilidad():
    w = P.proyectar_pesos([0.25, 0.25, 0.25, 0.25], 0.25)  # n × máximo = 100 % exacto
    assert np.allclose(w, 0.25)
    w = P.proyectar_pesos([0.2500004, 0.2499998, 0.2499998, 0.25], 0.25)
    assert w.max() <= 0.25 + 1e-12 and w.sum() == pytest.approx(1.0, abs=1e-12)


def test_proyeccion_inviable():
    with pytest.raises(ValueError):
        P.proyectar_pesos([0.5, 0.5], 0.4)


@pytest.mark.parametrize("objetivo", ["max_sharpe", "min_volatility"])
@pytest.mark.parametrize("maximo", [0.3, 0.35, 0.5])
def test_optimizador_respeta_limites(objetivo, maximo):
    mu, cov = P.preparar_estadisticas(_precios())
    res = P.optimizar_portafolio(mu, cov, objetivo=objetivo, peso_maximo=maximo)
    w = res["pesos"].to_numpy()
    assert w.max() <= maximo + 1e-12 and w.min() >= 0 and w.sum() == pytest.approx(1.0, abs=1e-12)


def test_ledoit_wolf_igual_a_la_formula_de_referencia():
    x = np.random.default_rng(3).normal(0, 0.01, (250, 6))
    cov, alpha = P.covarianza_ledoit_wolf(x)
    assert 0.0 <= alpha <= 1.0
    assert np.allclose(cov, cov.T)
    assert np.linalg.eigvalsh(cov).min() > 0
    try:
        from sklearn.covariance import LedoitWolf
    except ImportError:
        return
    lw = LedoitWolf().fit(x)
    assert np.allclose(cov, lw.covariance_ * 250 / 249)
    assert alpha == pytest.approx(lw.shrinkage_)


def test_contraccion_es_opcional_y_registrada():
    p = _precios()
    _, c1 = P.preparar_estadisticas(p)
    _, c0 = P.preparar_estadisticas(p, contraccion=False)
    assert c1.attrs["contraccion_alpha"] > 0
    assert c0.attrs["contraccion_alpha"] == 0
    r = P.rendimientos_comunes(p)
    assert np.allclose(c0.to_numpy(), r.cov().to_numpy() * 252)


@pytest.mark.parametrize("serie,esperado", [
    ([-0.2, 0.05, 0.05, 0.0], -0.2),          # pérdida el primer día: antes salía 0 %
    ([0.1, -0.2, 0.05], -0.2),                # ganancia y luego caída
    ([-0.1, 0.2, -0.05], -0.1),               # recuperación completa y nueva caída menor
    ([-0.5, 0.5], -0.5),                      # recuperación parcial (0,5 → 0,75)
    ([0.01, 0.02, 0.0, 0.03], 0.0),           # sin pérdidas
])
def test_caida_maxima_desde_el_capital_inicial(serie, esperado):
    r = pd.DataFrame({"A": serie, "B": [0.0] * len(serie)})
    assert P.metricas_riesgo_historicas(r, {"A": 1.0, "B": 0.0})["max_drawdown"] == pytest.approx(esperado)


@pytest.mark.parametrize("pesos", [
    {"A": 0.6},                       # falta B y suma 60 %
    {"A": 0.6, "B": 0.0},             # suma 60 %: cartera parcialmente invertida
    {"A": 1.0, "B": 0.0, "C": 0.0},   # activo que no existe
    {"A": 1.2, "B": -0.2},            # venta en corto
    {"A": np.nan, "B": 1.0},
    [1.0],                            # dimensión
])
def test_metricas_rechazan_pesos_inconsistentes(pesos):
    r = pd.DataFrame({"A": [0.01, -0.02, 0.03], "B": [0.0, 0.01, -0.01]})
    with pytest.raises(ValueError):
        P.metricas_riesgo_historicas(r, pesos)


@pytest.mark.parametrize("periodos", [0, -252, float("nan")])
def test_metricas_rechazan_periodos_invalidos(periodos):
    r = pd.DataFrame({"A": [0.01, -0.02, 0.03], "B": [0.0, 0.01, -0.01]})
    with pytest.raises(ValueError):
        P.metricas_riesgo_historicas(r, [0.5, 0.5], periodos_anuales=periodos)


def test_metricas_de_riesgo():
    r = pd.DataFrame({"A": [0.2, -0.2] * 126, "B": [0.0] * 252})
    m = P.metricas_riesgo_historicas(r, {"A": 1.0, "B": 0.0})
    assert m["retorno_aritmetico_anual"] == pytest.approx(0.0)
    assert m["retorno_compuesto_anual"] < -0.9  # (1,2 × 0,8)^126 − 1: el compuesto no es la media
    assert m["max_drawdown"] < -0.9
    assert m["var_diario"] == pytest.approx(0.2) and m["cvar_diario"] == pytest.approx(0.2)
    with pytest.raises(ValueError):
        P.metricas_riesgo_historicas(r, {"A": 1.0, "B": 0.0}, confianza=1.2)
