"""Cambios de la auditoría con el marco de Damodaran (28-oct-2026): narrativa, reinversión, riesgo país,
acciones diluidas, Kd sintético, beta de emergentes y retornos esperados del portafolio."""
import numpy as np
import pandas as pd
import pytest

import modelacion_logic as L
import portfolio_engine as P

HIST = pd.DataFrame({
    "Ingresos": [12000.0, 13000.0, 14500.0, 15800.0, 16000.0],
    "EBITDA": [7000.0, 7600.0, 8500.0, 9200.0, 8200.0],
    "EBIT": [5900.0, 6450.0, 7300.0, 7900.0, 6800.0],
    "Depreciacion": [900.0, 950.0, 1000.0, 1070.0, 1080.0],
    "CAPEX": [3000.0, 3500.0, 4200.0, 4800.0, 6300.0],
    "NWC": [500.0, 550.0, 600.0, 650.0, 700.0],
}, index=[2021, 2022, 2023, 2024, 2025])


def _hist(**attrs):
    h = L.completar_historico(HIST.copy(), 0.22)
    h.attrs.update({"capital_invertido": 40000.0, "g_convergencia": 0.06, **attrs})
    return h


@pytest.fixture(autouse=True)
def _sesion():
    L.vincular_estado_sesion({})
    yield
    L.desvincular_estado_sesion()


class TestReinversion:
    def test_ventas_capital_media_o_marginal(self):
        v, fuente = L.ventas_capital_historica(_hist(), 40000.0)
        assert 0.1 <= v <= 1.0 and fuente
        assert L.ventas_capital_historica(HIST.drop(columns=["CAPEX"]))[0] is None

    def test_reinversion_ligada_sin_valle_antes_de_la_perpetuidad(self):
        dp, meta = L.proyectar_por_drivers(_hist(), 5, tax=0.22)
        assert meta["reinversion_ligada"]
        s2c, g = meta["ventas_capital"], 0.06
        reinv = dp["CAPEX"] - dp["Depreciacion"] + dp["Delta_NWC"]
        esperado_ultimo = dp["Ingresos"].iloc[-1] * g / s2c
        assert reinv.iloc[-1] == pytest.approx(esperado_ultimo, rel=1e-6)
        # el último flujo ya no supera holgadamente al de la perpetuidad (antes: valle de reinversión)
        fcff_perp = dp["NOPAT"].iloc[-1] * (1 + g) - esperado_ultimo * (1 + g)
        assert abs(dp["FCFF"].iloc[-1] / fcff_perp - 1) < 0.15

    def test_modo_mantenimiento_conserva_el_metodo_anterior(self):
        L.fijar_narrativa("X", {"reinversion": "mantenimiento"})
        dp, meta = L.proyectar_por_drivers(_hist(narrativa=L.narrativa_sesion("X")), 5, tax=0.22)
        assert not meta["reinversion_ligada"]
        assert meta["capex_ratio_final"] <= 1.3 * meta["margen_da"] + 1e-9

    def test_materias_primas_no_ligan_reinversion(self):
        dp, meta = L.proyectar_por_drivers(_hist(ciclico=True), 5, tax=0.22)
        assert not meta["reinversion_ligada"]


class TestNarrativa:
    def test_propuesta_del_modelo_explica_el_margen(self):
        _dp, meta = L.proyectar_por_drivers(_hist(), 5, tax=0.22)
        filas = {f["palanca"]: f for f in meta["narrativa"]}
        assert set(filas) == set(L.PALANCAS_NARRATIVA)
        assert all(f["fuente"] == "modelo" for f in filas.values())
        assert "último año" in filas["margen_ebitda"]["frase"]

    def test_palancas_del_usuario_mueven_la_proyeccion(self):
        L.fijar_narrativa("X", {"margen_ebitda": 0.51, "anios_convergencia": 3, "g_ingresos": 0.03},
                          {"margen_ebitda": "el cargo de 2025 se repite"})
        dp, meta = L.proyectar_por_drivers(_hist(narrativa=L.narrativa_sesion("X")), 5, tax=0.22)
        m = dp["EBITDA"] / dp["Ingresos"]
        assert m.iloc[-1] == pytest.approx(0.51)
        assert dp["Ingresos"].iloc[0] == pytest.approx(16000.0 * 1.03)
        filas = {f["palanca"]: f for f in meta["narrativa"]}
        assert filas["margen_ebitda"]["fuente"] == "usuario"
        assert filas["margen_ebitda"]["frase"] == "el cargo de 2025 se repite"

    @pytest.mark.parametrize("palancas", [{"margen_ebitda": 1.5}, {"g_ingresos": 0.9}, {"anios_convergencia": 20},
                                          {"ventas_capital": 0.0}, {"g_ingresos": float("nan")}])
    def test_palancas_invalidas(self, palancas):
        with pytest.raises(ValueError):
            L.fijar_narrativa("X", palancas)

    def test_narrativa_invalida_resultados(self):
        antes = L.firma_ajustes_usuario("X")
        L.fijar_narrativa("X", {"margen_ebitda": 0.5})
        assert L.firma_ajustes_usuario("X") != antes


class TestRiesgoPais:
    def test_pesos_por_pais(self):
        assert L.leer_pesos_paises("Brasil 40, Colombia 30; Chile: 15 %, Perú 15") == {
            "Brazil": 40.0, "Colombia": 30.0, "Chile": 15.0, "Peru": 15.0}
        with pytest.raises(ValueError):
            L.leer_pesos_paises("Brasil cuarenta")

    def test_erp_ponderada(self):
        paises = {"Colombia": {"erp_rating": 0.0692, "crp_rating": 0.0272}, "Chile": {"erp_rating": 0.0525, "crp_rating": 0.0105}}
        r = L.erp_por_operaciones({"Colombia": 50, "Chile": 50}, paises)
        assert r["erp"] == pytest.approx((0.0692 + 0.0525) / 2)
        with pytest.raises(ValueError):
            L.erp_por_operaciones({"Atlantis": 1}, paises)


class TestDeudaYAcciones:
    @pytest.mark.parametrize("cobertura,calif", [(0.1, "D2/D"), (2.5, "Baa2/BBB"), (3.0, "A3/A-"), (50, "Aaa/AAA")])
    def test_calificacion_sintetica_sin_huecos(self, cobertura, calif):
        assert L.calificacion_sintetica(cobertura, 1.0)["calificacion"] == calif

    def test_kd_sintetico_y_acciones_diluidas(self):
        df = pd.DataFrame({"Ingresos": [100.0, 110.0], "EBITDA": [40.0, 44.0], "EBIT": [30.0, 33.0],
                           "Depreciacion": [10.0, 11.0], "CAPEX": [12.0, 13.0], "NWC": [5.0, 5.5],
                           "NOPAT": [22.0, 24.0], "FCFF": [20.0, 21.0], "Delta_NWC": [0.0, 0.5]}, index=[2024, 2025])
        info = {"country": "United States", "currency": "USD", "financialCurrency": "USD", "beta": 1.1,
                "sharesOutstanding": 2.0e9, "impliedSharesOutstanding": 2.1e9, "currentPrice": 50.0,
                "marketCap": 1.0e11, "totalDebt": 20e9, "totalCash": 5e9, "_gasto_intereses": 3.3e9}
        p = L.derivar_params_desde_cero(df, info=info, ticker_yf="X")
        assert p["acciones"] == pytest.approx(2100.0)
        assert "diluidas" in p["acciones_fuente"]
        assert p["calificacion_sintetica"] == "Aaa/AAA"  # cobertura 33 / 3,3 = 10 > 8,5 (empresas grandes)
        assert "calificación sintética" in p["kd_fuente"]


class TestPortafolio:
    def test_retornos_anclados_ponderan_por_precision(self):
        t = P.retornos_esperados_anclados(pd.Series({"A": 0.25, "B": 0.05}), pd.Series({"A": 0.30, "B": 0.25}), 5,
                                          pd.Series({"A": 0.12, "B": 0.10}))
        assert t.loc["A", "peso_historico"] == pytest.approx(0.0476, abs=1e-3)
        assert t.loc["A", "esperado"] == pytest.approx(0.126, abs=1e-3)
        with pytest.raises(ValueError):
            P.retornos_esperados_anclados(pd.Series({"A": 0.1}), pd.Series({"A": 0.2}), 5, pd.Series({"B": 0.1}))

    def test_fisher(self):
        assert P.retorno_en_moneda(0.10, 0.06, 0.02) == pytest.approx(1.10 * 1.02 / 1.06 - 1)

    def test_fuera_de_muestra(self):
        rng = np.random.default_rng(1)
        r = rng.normal(0.0004, 0.012, (800, 3))
        px = pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=pd.bdate_range("2023-01-02", periods=800), columns=list("ABC"))
        o = P.evaluar_fuera_de_muestra(px, 0.7, objetivo="min_volatility", peso_maximo=0.6)
        assert set(o) >= {"pesos", "dentro", "fuera", "corte"}
        assert o["pesos"].sum() == pytest.approx(1.0)
        o2 = P.evaluar_fuera_de_muestra(px, 0.7, mu_fijo=pd.Series({"A": 0.1, "B": 0.08, "C": 0.06}),
                                        objetivo="max_sharpe", peso_maximo=0.6)
        assert o2["pesos"]["A"] >= o2["pesos"]["C"] - 1e-9
        with pytest.raises(ValueError):
            P.evaluar_fuera_de_muestra(px.iloc[:100], 0.7)


def test_motor_sin_division_por_cero_con_valor_cero():
    """Valor por acción 0 (patrimonio ≤ 0) daba ZeroDivisionError en la alerta de precio sobre valor."""
    m = L.motor_decision_institucional(wacc=0.12, g=0.04, roic=0.06, de_ratio=1.0, vpn=-10.0, tir=0.05, payback=None,
                                       ev_base=900.0, equity_base=-100.0, equity_pesimista=-500.0, delta_ev_capex=0.0,
                                       riesgo_liq=None, procedencia={}, score_heuristico=40, precio_mercado=5000.0,
                                       equity_por_accion=0.0, moneda_modelo="COP", moneda_precio="COP")
    assert any("no asigna valor" in a for a in m.get("alertas") or [])
