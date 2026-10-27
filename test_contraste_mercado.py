"""Regresiones detectadas al contrastar el modelo con datos reales (oct-2026).

Yahoo se simula con estados financieros en el formato de yfinance; las cifras de
NKE son las reportadas (FY2022–FY2026, cierre en mayo). Corre offline.
"""
from __future__ import annotations

import types
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import modelacion_logic as L

M = 1e6


def _frame(rows, cols):
    return pd.DataFrame({pd.Timestamp(c): [rows[k][i] for k in rows] for i, c in enumerate(cols)},
                        index=list(rows.keys()))


NKE_COLS = ["2026-05-31", "2025-05-31", "2024-05-31", "2023-05-31", "2022-05-31"]
MIN_COLS = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"]


def _nke():
    fin = _frame({
        "Total Revenue": [46398, 46309, 51362, 51217, 46710],
        "EBIT": [4182, 3702, 6754, 5915, 6675],
        "EBITDA": [4929, 4477, 7550, 6618, 7515],
        "Reconciled Depreciation": [747, 775, 796, 703, 840],
    }, NKE_COLS) * M
    fin.loc["Tax Rate For Calcs"] = [0.2031, 0.1714, 0.1492, 0.1824, 0.0910]
    cf = _frame({"Capital Expenditure": [-684, -430, -812, -969, -758]}, NKE_COLS) * M
    bs = _frame({
        "Current Assets": [24603, 23362, np.nan, np.nan, np.nan],
        "Current Liabilities": [12547, 10566, np.nan, np.nan, np.nan],
        "Cash Cash Equivalents And Short Term Investments": [9027, 9151, np.nan, np.nan, np.nan],
        "Current Debt And Capital Lease Obligation": [2478, 502, np.nan, np.nan, np.nan],
    }, NKE_COLS) * M
    info = dict(longName="NIKE, Inc.", country="United States", currency="USD", financialCurrency="USD",
                regularMarketPrice=37.77, marketCap=56.10e9, sharesOutstanding=1483.5 * M, beta=1.10,
                totalDebt=7942 * M, totalCash=9027 * M, sector="Consumer Cyclical")
    return dict(info=info, fin=fin, cf=cf, bs=bs, px=37.77)


def _minero_usd():
    """Emisor BVC que reporta en USD y cotiza en COP (patrón MINEROS)."""
    fin = _frame({
        "Total Revenue": [799.7, 538.6, 445.0, 430.0],
        "EBIT": [300.0, 160.0, 110.0, 100.0],
        "EBITDA": [358.4, 209.6, 160.0, 150.0],
        "Reconciled Depreciation": [58.4, 49.6, 50.0, 50.0],
    }, MIN_COLS) * M
    cf = _frame({"Capital Expenditure": [-100.0, -90.0, -85.0, -80.0]}, MIN_COLS) * M
    info = dict(longName="Minera Andina S.A.", country="Colombia", currency="COP", financialCurrency="USD",
                regularMarketPrice=19412.77, sharesOutstanding=295 * M, totalDebt=15.4 * M,
                totalCash=108.0 * M, sector="Basic Materials")
    return dict(info=info, fin=fin, cf=cf, bs=pd.DataFrame(), px=19412.77)


class _FakeYF:
    def __init__(self, data, precios):
        self.data, self.precios = data, precios

    def Ticker(self, sym):
        sym = sym.upper()
        d = self.data.get(sym)
        precios = self.precios

        class T:
            info = dict(d["info"]) if d else {}
            financials = d["fin"] if d else pd.DataFrame()
            cashflow = d["cf"] if d else pd.DataFrame()
            balance_sheet = d["bs"] if d else pd.DataFrame()
            fast_info = {}

            def get_info(self_inner):
                return self_inner.info

            def history(self_inner, **k):
                if sym not in precios:
                    return pd.DataFrame()
                px = precios[sym]
                return pd.DataFrame({"Close": [px, px]}, index=pd.to_datetime(["2026-10-26", "2026-10-27"]))
        return T()


class BaseFake(unittest.TestCase):
    HOY = pd.Timestamp("2026-10-27")

    def setUp(self):
        L.vincular_estado_sesion({})
        L.limpiar_cache_mercado()
        data = {"NKE": _nke(), "MINERA.CL": _minero_usd()}
        precios = {k: v["px"] for k, v in data.items()}
        precios["COP=X"] = 3185.01
        self._p = [mock.patch.object(L, "yf", _FakeYF(data, precios), create=True),
                   mock.patch.object(L, "HAS_YF", True)]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()
        L.limpiar_cache_mercado()
        L.desvincular_estado_sesion()


class TestDescargaYahoo(BaseFake):
    def test_ejercicio_fiscal_cerrado_en_el_anio_en_curso_se_conserva(self):
        df, msg = L.descargar_financieros_yfinance("NKE")
        self.assertIn(2026, list(df.index), "FY2026 (cierre 31-may-2026) es un ejercicio cerrado")
        self.assertEqual(df.attrs["ejercicio_cerrado_hasta"], 2026)
        h, _ = L._sanear_historico_tab1(df)
        self.assertIn(2026, list(h.index))

    def test_tasa_efectiva_desde_estados_y_parametros_coherentes(self):
        df, _ = L.descargar_financieros_yfinance("NKE")
        self.assertAlmostEqual(df.attrs["tax_efectiva"], 0.1714, places=4)  # mediana FY24–FY26
        ok, _, nombre, _ = L.buscar_y_descargar_empresa("NKE")
        self.assertTrue(ok)
        self.assertAlmostEqual(L.params_empresa(nombre)["tax"], 0.1714, places=4)

    def test_nwc_desde_balance(self):
        df, _ = L.descargar_financieros_yfinance("NKE")
        self.assertAlmostEqual(df.loc[2026, "NWC"], 5.507, places=3)
        self.assertAlmostEqual(df.loc[2025, "NWC"], 4.147, places=3)
        self.assertEqual(df.attrs["nwc_fuente"], "balance Yahoo")

    def test_emisor_bvc_con_eeff_usd_se_valora_con_precio_convertido(self):
        ok, html, nombre, _ = L.buscar_y_descargar_empresa("MINERA.CL")
        self.assertTrue(ok, L._html_a_texto(html, 300))
        self.assertEqual(L.monedas_alineadas_por_ticker(nombre_empresa=nombre), ("USD", "COP"))
        p = L.params_empresa(nombre)
        L.tab4_recomendacion(nombre, None, 5, 0.1, 0.08, 0.3, 0.03, 0.0, 1.0, 50.0, -0.09,
                             0.045, 0.05, 0.0, True, 0.108, 0, 0, 0, p.get("acciones"), 6.0, True, 0.04)
        m = L.metricas_valoracion_sesion(nombre)
        self.assertEqual(m["fx_aplicado"], 3185.01)
        self.assertAlmostEqual(m["precio_mercado_moneda_modelo"], 19412.77 / 3185.01, places=6)
        self.assertAlmostEqual(m["upside"], (m["vps_modelo"] / m["precio_mercado_moneda_modelo"] - 1) * 100, places=6)
        self.assertTrue(L.auditar_contexto_comite_ia(m)["ok"])


class TestValoracion(BaseFake):
    def test_sin_capital_invertido_la_pestana_4_no_falla(self):
        ok, _, nombre, _ = L.buscar_y_descargar_empresa("NKE")
        decision_html, kpis, _ = L.tab4_recomendacion(
            nombre, None, 5, 0.14, 0.06, 0.17, 0.01, 0.0, 0.96, 0.0, -1.085, 0.045, 0.05, 0.0, True,
            9.027, 0, 0, 0, 1483.5, 11.0, True, 0.04)
        self.assertIsNotNone(kpis, decision_html[:300])
        roic_val = kpis.set_index("Indicador").loc["ROIC", "Valor"]
        self.assertEqual(roic_val, "N/D")
        self.assertIn("ROIC no disponible", decision_html)

    def test_motor_no_trata_roic_nan_como_creacion_de_valor(self):
        out = L.motor_decision_institucional(
            wacc=0.09, g=0.02, roic=float("nan"), de_ratio=0.5, vpn=None, tir=None, payback=None,
            ev_base=100, equity_base=80, equity_pesimista=50, delta_ev_capex=0, riesgo_liq="Bajo",
            procedencia={"nivel_calidad": "MEDIA"}, score_heuristico=3)
        self.assertFalse(any("crea valor económico" in s for s in out["soportes"]))

    def test_kd_menor_que_rf_genera_alerta(self):
        msgs = L.validar_inputs_valoracion(0.10, 0.03, kd=0.08, rf=0.13)
        self.assertTrue(any("Kd" in x for x in msgs))
        self.assertFalse(any("Kd" in x for x in L.validar_inputs_valoracion(0.10, 0.03, kd=0.15, rf=0.13)))

    def test_conversion_precio_cop_usd(self):
        r = L.convertir_precio_a_moneda_modelo(31850.1, "COP", "USD")
        self.assertAlmostEqual(r["precio"], 10.0, places=6)
        r = L.convertir_precio_a_moneda_modelo(10.0, "USD", "COP")
        self.assertAlmostEqual(r["precio"], 31850.1, places=4)
        self.assertIsNone(L.convertir_precio_a_moneda_modelo(10.0, "EUR", "COP")["precio"])

    def test_isa_deuda_neta_reportada(self):
        p = L._EMPRESAS_CATALOGO_INMUTABLE["ISA — Interconexión Eléctrica"]["params"]
        self.assertEqual(p["deuda_neta"], 30430)
        self.assertEqual(L.CAPM_POR_MERCADO["CO"]["rf"], 0.13)


if __name__ == "__main__":
    unittest.main(verbosity=2)
