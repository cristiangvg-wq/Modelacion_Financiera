"""Casos límite de valor terminal y del puente EV → patrimonio (auditoría de regresión 2026-10-28)."""
import pytest

import modelacion_logic as L

FCFF = [100.0, 110.0, 120.0, 130.0, 140.0]


def dcf(**k):
    base = dict(wacc=0.12, g=0.03, mid_year=False)
    base.update(k)
    return L.valoracion_dcf(FCFF, **base)


@pytest.mark.parametrize("wacc,g", [(0.05, 0.06), (0.06, 0.06), (0.065, 0.06)])
def test_g_nunca_alcanza_el_wacc(wacc, g):
    v = dcf(wacc=wacc, g=g, g_max_macro=0.08)
    assert v["g_used"] <= wacc - 0.01 + 1e-12
    assert v["EV"] > 0 and v["EV"] < 1e9


def test_wacc_cerca_de_g_advierte_sensibilidad():
    v = dcf(wacc=0.061, g=0.06, g_max_macro=0.07)
    assert "muy sensible" in (v["bridge"].get("Nota TV") or "")
    assert "muy sensible" not in (dcf()["bridge"].get("Nota TV") or "")


def test_flujo_y_nopat_terminal_no_positivos_no_perpetuan_perdidas():
    v = L.valoracion_dcf([100.0, 90.0, 50.0, -10.0, -20.0], 0.12, 0.03, mid_year=False)
    assert v["TV"] == 0
    v = dcf(nopat_final=-50.0)
    assert v["TV"] == 0
    assert "no positivo" in (v["bridge"].get("Nota TV") or "")


def test_reinversion_que_rinde_menos_que_el_wacc_no_crea_valor_con_crecimiento():
    """RONIC < WACC está acotado por el modelo (piso = WACC): crecer más no puede subir el valor."""
    L.vincular_estado_sesion({})
    try:
        L.fijar_ronic_spread(0.0)
        assert dcf(g=0.05, nopat_final=150.0)["EV"] <= dcf(g=0.03, nopat_final=150.0)["EV"] * 1.02
    finally:
        L.fijar_ronic_spread(None)
        L.desvincular_estado_sesion()


def test_caja_neta_suma_al_patrimonio():
    v = dcf(deuda_neta=-200.0, acciones=10.0)
    assert v["Equity_Value"] == pytest.approx(v["EV"] + 200.0)


def test_deuda_bruta_y_caja_no_duplican_la_caja():
    neta = dcf(deuda_neta=300.0)["Equity_Value"]
    assert dcf(deuda_neta=400.0, caja=100.0, deuda_es_bruta=True)["Equity_Value"] == pytest.approx(neta)
    assert dcf(deuda_neta=300.0, caja=100.0)["Equity_Value"] == pytest.approx(neta)  # neta: la caja no se suma otra vez


def test_patrimonio_negativo_no_da_valor_por_accion_negativo():
    v = dcf(deuda_neta=5000.0, acciones=10.0)
    assert v["Equity_Value"] < 0  # el puente conserva el patrimonio negativo
    assert v["value_per_share"] == 0.0
    r = L.calcular_vps_y_upside(v["Equity_Value"], 10.0, precio_mercado=50.0, moneda_modelo="COP", moneda_precio="COP")
    assert r["value_per_share"] == 0.0 and r["upside_pct"] == pytest.approx(-100.0)
    assert "no tiene valor" in r["nota_vps"]


@pytest.mark.parametrize("acciones", [0, -5, float("nan")])
def test_acciones_invalidas_se_rechazan(acciones):
    with pytest.raises(ValueError):
        dcf(deuda_neta=100.0, acciones=acciones)


def test_sin_acciones_no_hay_valor_por_accion():
    v = dcf(deuda_neta=100.0, acciones=None)
    assert v["value_per_share"] is None


def test_partidas_del_puente_faltantes_cuentan_como_cero():
    a = dcf(deuda_neta=100.0, nci=None, otros_claims=None, asociados=None)
    b = dcf(deuda_neta=100.0)
    assert a["Equity_Value"] == pytest.approx(b["Equity_Value"])


def test_sensibilidad_usa_la_misma_reinversion_terminal():
    """La celda central de la tabla WACC × g debe coincidir con la valoración principal."""
    v = dcf(nopat_final=150.0, deuda_neta=100.0)
    m = L.matriz_sensibilidad_wacc_g(FCFF, 100.0, 0.12, 0.03, mid_year=False, g_max_macro=0.05, nopat_final=150.0)
    fila = m[m["WACC %"] == 12.0].iloc[0]
    assert fila["g=3.0% EV"] == pytest.approx(v["EV"], abs=0.06)  # la tabla redondea a un decimal
