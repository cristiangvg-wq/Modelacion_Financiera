"""Pruebas sin red de la capa mercado/ (cliente, instantáneas, beta, pipeline, portafolio)."""
import numpy as np
import pandas as pd
import pytest

import modelacion_logic as L
from mercado import beta as B
from mercado import pipeline as PL
from mercado.portafolio import estadisticas_semanales
from mercado.yahoo_cliente import DatosNoDisponibles, Snapshot, TickerReplay, YahooCliente

CIERRES = pd.to_datetime(["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"])


def _precios(seed=7, beta=1.2, anios=5):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-10-30", periods=252 * anios)
    rm = rng.normal(0.0004, 0.010, len(idx))
    ra = 0.0002 + beta * rm + rng.normal(0, 0.008, len(idx))
    return (pd.DataFrame({"Close": 100 * np.cumprod(1 + rm)}, index=idx),
            pd.DataFrame({"Close": 50 * np.cumprod(1 + ra)}, index=idx))


def _tabla(filas):
    return pd.DataFrame(filas, index=CIERRES).T


class FakeTicker:
    def __init__(self, sym, fallos_info=0, error=ConnectionError("429 Too Many Requests")):
        self.sym, self._fallos, self._error, self.llamadas = sym, fallos_info, error, 0
        idx_px, emp_px = _precios()
        self._px = idx_px if sym.startswith("^") else emp_px
        rev = [1000.0, 900.0, 820.0, 760.0]
        self.financials = _tabla({
            "Total Revenue": [v * 1e9 for v in rev],
            "Operating Income": [v * 0.25e9 for v in rev],
            "Reconciled Depreciation": [v * 0.05e9 for v in rev],
            "EBITDA": [v * 0.30e9 for v in rev],
            "Tax Rate For Calcs": [0.21] * 4,
            "Interest Expense": [12e9] * 4,
        })
        self.cashflow = _tabla({"Capital Expenditure": [-v * 0.06e9 for v in rev]})
        self.balance_sheet = _tabla({
            "Current Assets": [400e9, 360e9, 330e9, 300e9], "Current Liabilities": [300e9, 280e9, 250e9, 230e9],
            "Cash And Cash Equivalents": [100e9, 90e9, 80e9, 70e9], "Current Debt": [20e9] * 4,
            "Total Debt": [300e9] * 4, "Stockholders Equity": [900e9] * 4,
        })
        self.quarterly_income_stmt = pd.DataFrame()

    @property
    def info(self):
        self.llamadas += 1
        if self.llamadas <= self._fallos:
            raise self._error
        if self.sym.startswith("^"):
            return {"symbol": self.sym, "currency": "USD", "shortName": "Índice"}
        return {"symbol": self.sym, "country": "United States", "currency": "USD", "financialCurrency": "USD",
                "marketCap": 3000e9, "totalDebt": 300e9, "totalCash": 100e9, "sharesOutstanding": 10e9,
                "regularMarketPrice": 300.0, "beta": 1.1, "sector": "Technology",
                "industry": "Software—Infrastructure", "exchange": "NMS"}

    def history(self, period="5y", interval="1d", auto_adjust=True):
        return self._px.copy()


def _cliente(**kw):
    dormidas = []
    c = YahooCliente(fabrica_ticker=lambda s: FakeTicker(s, **kw), dormir=dormidas.append)
    return c, dormidas


def test_reintenta_solo_errores_transitorios():
    c, dormidas = _cliente(fallos_info=2)
    snap = c.descargar("FAKE")
    assert snap.info["marketCap"] == 3000e9 and len(dormidas) == 2 and "info" not in snap.errores
    c2, d2 = _cliente(fallos_info=1, error=KeyError("no existe"))
    snap2 = c2.descargar("FAKE")
    assert d2 == [] and "info" in snap2.errores  # no se reintenta un error permanente; se registra


def test_falla_explicita_si_no_hay_nada():
    class Vacio:
        info, financials, cashflow, balance_sheet, quarterly_income_stmt = {}, None, None, None, None
        def history(self, **_): return pd.DataFrame()
    c = YahooCliente(fabrica_ticker=lambda s: Vacio(), dormir=lambda _: None, reintentos=0)
    with pytest.raises(DatosNoDisponibles):
        c.descargar("NADA")


def test_cache_evita_segunda_descarga():
    creados = []
    c = YahooCliente(fabrica_ticker=lambda s: creados.append(s) or FakeTicker(s), dormir=lambda _: None)
    assert c.descargar("FAKE") is c.descargar("fake")
    assert creados == ["FAKE"]


def test_instantanea_reproducible_y_a_prueba_de_alteraciones(tmp_path):
    c, _ = _cliente()
    s = c.descargar("FAKE")
    ruta = s.guardar(tmp_path)
    s2 = Snapshot.cargar(ruta)
    assert s2.huella == s.huella
    df1, _ = L.descargar_financieros_yfinance("FAKE", ticker_obj=TickerReplay(s))
    df2, _ = L.descargar_financieros_yfinance("FAKE", ticker_obj=TickerReplay(s2))
    pd.testing.assert_frame_equal(df1, df2)
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("3000000000000.0", "3100000000000.0"), encoding="utf-8")
    with pytest.raises(ValueError, match="huella"):
        Snapshot.cargar(ruta)


def test_beta_semanal_recupera_beta_conocida():
    idx, emp = _precios(beta=1.2)
    r = B.beta_regresion(emp["Close"], idx["Close"])
    assert r["n"] > 250 and abs(r["beta"] - 1.2) < 3 * r["error_estandar"] + 0.05
    sel = B.seleccionar_beta_desapalancada(r, de_mercado=0.5, tasa_fiscal=0.25, beta_bottom_up=None)
    assert sel["metodo"] == "regresion"
    assert sel["beta_u"] == pytest.approx(r["beta_blume"] / (1 + 0.75 * 0.5))


def test_beta_no_informativa_cae_a_bottom_up():
    r = {"beta": 0.9, "error_estandar": 0.40, "r2": 0.05, "n": 60, "beta_blume": 0.93}
    sel = B.seleccionar_beta_desapalancada(r, 0.2, 0.3, {"beta_u": 0.85, "fuente": "Damodaran", "industria": "X"})
    assert sel["metodo"] == "bottom_up" and sel["beta_u"] == 0.85


def test_pipeline_conecta_extraccion_con_motor():
    c, _ = _cliente()
    inp, df_hist = PL.construir_inputs("FAKE", c, en_vivo=False)
    assert inp.mercado_capm == "US" and inp.moneda_flujos == "USD"
    assert inp.de_mercado == pytest.approx(300 / 3000)            # D/E a valor de MERCADO
    assert inp.deuda_neta == pytest.approx(200.0)                  # (300 − 100) en miles de millones
    assert inp.fuentes["beta"].startswith("regresión semanal")      # índice ^GSPC declarado para US
    # WACC recalculado a mano con los insumos publicados = WACC del motor
    ke = inp.rf + inp.beta_l * inp.erp + inp.crp
    we, wd = 1 / (1 + inp.de_mercado), inp.de_mercado / (1 + inp.de_mercado)
    assert inp.ke == pytest.approx(ke) and inp.wacc == pytest.approx(we * ke + wd * inp.kd * (1 - inp.tax))
    val = PL.valorar(inp, df_hist)
    assert val["EV"] > 0 and val["trazabilidad"]["snapshot_sha256"] == inp.snapshot_huella
    # Reproducible: misma instantánea → mismo valor
    inp2, df2 = PL.construir_inputs("FAKE", snapshot=c.descargar("FAKE"),
                                    snapshot_indice=c.descargar("^GSPC"), en_vivo=False)
    assert PL.valorar(inp2, df2)["EV"] == pytest.approx(val["EV"])


def test_portafolio_semanal_anualiza_con_52():
    idx, emp = _precios()
    px = pd.DataFrame({"A": idx["Close"], "B": emp["Close"]})
    px.iloc[::7, 1] = np.nan  # días sin negociación en un activo: el cierre semanal los absorbe
    mu, cov = estadisticas_semanales(px)
    r = px.resample("W-FRI").last().pct_change(fill_method=None).dropna()
    assert mu["A"] == pytest.approx(r["A"].mean() * 52)
    assert cov.shape == (2, 2) and np.all(np.linalg.eigvalsh(cov.to_numpy()) > 0)
