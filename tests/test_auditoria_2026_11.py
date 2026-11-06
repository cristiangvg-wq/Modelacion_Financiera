"""Regresión de las correcciones de la auditoría de noviembre de 2026 (capa de datos y portafolio)."""
from unittest import mock

import numpy as np
import pandas as pd
import pytest

import modelacion_logic as L
import portfolio_engine as P
from mercado import tasas as T

from test_mercado_pipeline import FakeTicker, _precios


# --- B1: ΔNWC del primer año con el balance del año anterior ---------------------------------
def test_delta_nwc_primer_anio_usa_balance_anterior():
    t = FakeTicker("FAKE")
    # Balance con un cierre adicional (2021) que no está en el estado de resultados
    bs = t.balance_sheet.copy()
    bs[pd.Timestamp("2021-12-31")] = [280e9, 220e9, 60e9, 20e9, 300e9, 900e9]
    t.balance_sheet = bs
    df, _ = L.descargar_financieros_yfinance("FAKE", ticker_obj=t)
    primero = df.index.min()
    nwc_2021 = (280 - 60) - (220 - 20)
    assert df.loc[primero, "Delta_NWC"] == pytest.approx(df.loc[primero, "NWC"] - nwc_2021)
    assert df.loc[primero, "FCFF"] == pytest.approx(
        df.loc[primero, "NOPAT"] + df.loc[primero, "Depreciacion"] - df.loc[primero, "CAPEX"] - df.loc[primero, "Delta_NWC"])


def test_delta_nwc_sin_balance_anterior_sigue_en_cero():
    df, _ = L.descargar_financieros_yfinance("FAKE", ticker_obj=FakeTicker("FAKE"))
    assert df["Delta_NWC"].iloc[0] == 0.0


# --- M4: beta del portafolio con ajuste de Blume ------------------------------------------------
def test_beta_portafolio_y_valoracion_usan_blume():
    b, fuente = L.beta_para_capm({"beta": 1.5})
    assert b == pytest.approx(0.67 * 1.5 + 0.33) and "Blume" in fuente


# --- A2: reintento ante límite de tasa y mensaje honesto -----------------------------------------
class _YFReintento:
    def __init__(self, fallos):
        self.fallos = fallos

    def Ticker(self, sym):
        return FakeTicker(sym, fallos_info=self.fallos)


def test_busqueda_reintenta_limite_de_tasa():
    with mock.patch.object(L, "yf", _YFReintento(1), create=True), mock.patch.object(L, "HAS_YF", True), \
            mock.patch.object(L._time, "sleep", lambda *_: None):
        ok, html, nombre, _ = L.buscar_y_descargar_empresa("FAKE")
    assert ok, html


def test_busqueda_no_dice_no_encontrado_si_yahoo_limita():
    with mock.patch.object(L, "yf", _YFReintento(99), create=True), mock.patch.object(L, "HAS_YF", True), \
            mock.patch.object(L._time, "sleep", lambda *_: None):
        ok, html, _, _ = L.buscar_y_descargar_empresa("FAKE")
    assert not ok and "no respondió" in html and "No se encontró" not in html


# --- M3: portafolio semanal --------------------------------------------------------------------
def _px_bvc():
    idx, emp = _precios(anios=5)
    px = pd.DataFrame({"A": idx["Close"], "B": emp["Close"]})
    px.iloc[::4, 1] = np.nan  # activo poco líquido: sin cotización uno de cada cuatro días
    return px


def test_cierres_semanales_no_inventan_precios():
    px = _px_bvc()
    w = P.a_cierres_semanales(px)
    assert (w.index.dayofweek == 4).all()
    assert set(w["B"].dropna()).issubset(set(px["B"].dropna()))


def test_fuera_de_muestra_semanal():
    w = P.a_cierres_semanales(_px_bvc())
    out = P.evaluar_fuera_de_muestra(w, 0.7, periodos_anuales=52, objetivo="min_volatility", peso_maximo=1.0)
    assert out["dentro"]["observaciones"] >= 52 and out["fuera"]["observaciones"] >= 26


def test_fuera_de_muestra_diario_sin_cambios():
    out = P.evaluar_fuera_de_muestra(_px_bvc().dropna(), 0.7, objetivo="min_volatility", peso_maximo=1.0)
    assert out["dentro"]["observaciones"] >= 120


def test_minimos_por_frecuencia():
    assert P.minimos_por_frecuencia(252) == (120, 60)
    assert P.minimos_por_frecuencia(52) == (52, 26)


# --- M1: refresco del rf de EE. UU. --------------------------------------------------------------
@pytest.fixture
def capm_aislado():
    us, de, tm = dict(L.CAPM_POR_MERCADO["US"]), dict(L.CAPM_POR_MERCADO["DEFAULT"]), dict(L.TASAS_MERCADO["us_rf"])
    yield
    L.CAPM_POR_MERCADO["US"].clear(); L.CAPM_POR_MERCADO["US"].update(us)
    L.CAPM_POR_MERCADO["DEFAULT"].clear(); L.CAPM_POR_MERCADO["DEFAULT"].update(de)
    L.TASAS_MERCADO["us_rf"] = tm


def test_refresco_rf_aplica_dato_mas_reciente(capm_aislado):
    r = T.refrescar_rf_us_en_proceso({"valor": 0.0483, "fecha": "2099-01-02", "fuente": "Tesoro (prueba)"})
    assert r["cambio"] and L.CAPM_POR_MERCADO["US"]["rf"] == 0.0483
    assert "en vivo" in L.CAPM_POR_MERCADO["US"]["rf_fuente"]


def test_refresco_rf_ignora_dato_viejo_o_fuera_de_rango(capm_aislado):
    antes = L.CAPM_POR_MERCADO["US"]["rf"]
    assert not T.refrescar_rf_us_en_proceso({"valor": 0.03, "fecha": "2000-01-01", "fuente": "x"})["cambio"]
    assert not T.refrescar_rf_us_en_proceso({"valor": 4.83, "fecha": "2099-01-01", "fuente": "x"})["cambio"]
    assert not T.refrescar_rf_us_en_proceso({})["cambio"]
    assert L.CAPM_POR_MERCADO["US"]["rf"] == antes


# --- B3: piso de Kd en el rf bruto (solo en los respaldos, no en la calificación sintética) -------
def test_kd_respaldo_no_queda_bajo_el_rf():
    t = FakeTicker("FAKE")
    df, _ = L.descargar_financieros_yfinance("FAKE", ticker_obj=t)
    info = dict(t.info, interestExpense=3e9)  # 3 / 300 = 1 % < rf; sin _gasto_intereses → no hay sintética
    p = L.derivar_params_desde_cero(df, info=info, ticker_yf="FAKE")
    rf_bruto = L.CAPM_POR_MERCADO["US"].get("rf_bruto", L.CAPM_POR_MERCADO["US"]["rf"])
    assert p["kd"] == pytest.approx(round(rf_bruto, 4)) and p["kd_sin_piso"] == pytest.approx(0.01)
    assert "piso" in p["kd_fuente"]


def test_kd_sintetico_no_se_toca():
    t = FakeTicker("FAKE")
    df, _ = L.descargar_financieros_yfinance("FAKE", ticker_obj=t)
    info = L._completar_info_yahoo(t.info, t, "FAKE")
    p = L.derivar_params_desde_cero(df, info=info, ticker_yf="FAKE")
    assert "calificación sintética" in p["kd_fuente"] and "kd_sin_piso" not in p
