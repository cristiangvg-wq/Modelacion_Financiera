"""Propiedades que deben cumplirse siempre (auditoría externa 2026-10-28, sección 4.2).

No comprueban un número concreto sino la dirección y magnitud de los efectos: si alguna
falla, hay un error de signo, unidades o supuestos aunque cada fórmula parezca correcta.
"""
import numpy as np
import pandas as pd
import pytest

import modelacion_logic as L
import portfolio_engine as P

FCFF = [100.0, 110.0, 120.0, 130.0, 140.0]


def dcf(**k):
    base = dict(wacc=0.12, g=0.03, mid_year=False)
    base.update(k)
    return L.valoracion_dcf(FCFF, **base)


@pytest.mark.parametrize("nopat", [None, 150.0])
def test_mayor_wacc_reduce_ev(nopat):
    assert dcf(wacc=0.13, nopat_final=nopat)["EV"] < dcf(wacc=0.12, nopat_final=nopat)["EV"]


def test_mayor_g_aumenta_ev_con_flujo_terminal():
    assert dcf(g=0.04)["EV"] > dcf(g=0.03)["EV"]


def test_g_no_crea_valor_si_la_reinversion_rinde_el_wacc():
    """Con valor terminal por drivers y RONIC = WACC, crecer no crea valor (crecer exige reinvertir)."""
    L.vincular_estado_sesion({})
    try:
        L.fijar_ronic_spread(0.0)
        a = dcf(g=0.03, nopat_final=150.0)["EV"]
        b = dcf(g=0.05, nopat_final=150.0)["EV"]
        assert b == pytest.approx(a, rel=0.02)
    finally:
        L.fijar_ronic_spread(None)
        L.desvincular_estado_sesion()


def test_deuda_neta_reduce_patrimonio_uno_a_uno():
    a, b = dcf(deuda_neta=100.0, acciones=10.0), dcf(deuda_neta=150.0, acciones=10.0)
    assert b["EV"] == pytest.approx(a["EV"])
    assert b["Equity_Value"] == pytest.approx(a["Equity_Value"] - 50.0)


def test_minoritario_y_asociadas_en_el_puente():
    base = dcf(deuda_neta=100.0)["Equity_Value"]
    assert dcf(deuda_neta=100.0, nci=30.0)["Equity_Value"] == pytest.approx(base - 30.0)
    assert dcf(deuda_neta=100.0, asociados=20.0)["Equity_Value"] == pytest.approx(base + 20.0)


def test_mas_acciones_menor_valor_por_accion():
    a = L.calcular_vps_y_upside(1000.0, 10.0)["value_per_share"]
    b = L.calcular_vps_y_upside(1000.0, 20.0)["value_per_share"]
    assert b == pytest.approx(a / 2)


def test_monedas_distintas_sin_tasa_no_dan_upside():
    r = L.calcular_vps_y_upside(1000.0, 10.0, precio_mercado=50.0, moneda_modelo="COP", moneda_precio="EUR")
    assert r["upside_pct"] is None


def test_ida_y_vuelta_de_moneda_recupera_el_valor():
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    fx = pd.Series([4000.0, 4010.0, 3990.0, 4020.0, 4005.0], index=idx)
    px = pd.DataFrame({"A": [10.0, 11.0, 12.0, 11.5, 12.5]}, index=idx)
    usd = P.convertir_a_moneda_comun(px, {"A": "USD"}, fx, moneda_base="COP")
    vuelta = P.convertir_a_moneda_comun(usd, {"A": "COP"}, fx, moneda_base="USD")
    assert np.allclose(vuelta["A"].to_numpy(), px["A"].to_numpy())


def test_mayor_beta_mayor_ke():
    assert L.costo_equity_capm(1.2, rf=0.1, erp=0.06) > L.costo_equity_capm(0.8, rf=0.1, erp=0.06)
