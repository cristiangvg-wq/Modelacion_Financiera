"""Empresas grandes de EE. UU.: tres etapas con consenso, beta bottom-up de Damodaran e inversiones financieras."""
import unittest

import numpy as np
import pandas as pd

import modelacion_logic as L


def _estimado(filas):
    return pd.DataFrame(filas, columns=["index", "avg", "yearAgoRevenue", "numberOfAnalysts"]).set_index("index")


class TestConsenso(unittest.TestCase):
    def test_alinea_el_0y_con_el_ultimo_cierre(self):
        re_ = _estimado([["0y", 477.74e9, 416.161e9, 38], ["+1y", 527.25e9, 477.74e9, 40]])
        c = L.consenso_ingresos_yahoo(re_, 416.161e9)
        self.assertAlmostEqual(c["g"][0], 0.148, places=3)
        self.assertAlmostEqual(c["g"][1], 0.1036, places=3)
        self.assertEqual(c["n_analistas"], [38, 40])

    def test_0y_ya_reportado_usa_solo_el_siguiente(self):
        re_ = _estimado([["0y", 477.74e9, 416.161e9, 38], ["+1y", 527.25e9, 477.74e9, 40]])
        c = L.consenso_ingresos_yahoo(re_, 477.0e9)
        self.assertEqual(len(c["g"]), 1)
        self.assertAlmostEqual(c["g"][0], 0.1036, places=3)

    def test_sin_coincidencia_o_valores_extremos(self):
        re_ = _estimado([["0y", 477.74e9, 416.161e9, 38]])
        self.assertIsNone(L.consenso_ingresos_yahoo(re_, 300e9))
        self.assertIsNone(L.consenso_ingresos_yahoo(_estimado([["0y", 30e9, 10e9, 5]]), 10e9))  # +200 %
        self.assertIsNone(L.consenso_ingresos_yahoo(None, 10e9))


class TestTresEtapas(unittest.TestCase):
    def test_ruta(self):
        r = L.ruta_crecimiento_tres_etapas([0.148, 0.104], 0.03, 10)
        self.assertEqual(len(r), 10)
        self.assertAlmostEqual(r[0], 0.148)
        self.assertAlmostEqual(r[1], 0.104)
        self.assertAlmostEqual(r[-1], 0.03)
        self.assertTrue(np.all(np.diff(r[1:]) < 0))
        self.assertEqual(len(L.ruta_crecimiento_tres_etapas([0.5, 0.4], 0.03, 2)), 2)
        hiper = L.ruta_crecimiento_tres_etapas([0.90, 0.68], 0.03, 10)
        self.assertAlmostEqual(hiper[1], 0.68)            # el consenso se respeta
        self.assertLessEqual(hiper[2], L.CRECIMIENTO_MAX_ETAPA2)  # pero no se extrapola
        self.assertIsNone(L.ruta_crecimiento_tres_etapas([], 0.03, 10))

    def _hist(self):
        df = pd.DataFrame({"Ingresos": [383.3, 391.0, 416.2], "EBITDA": [125.8, 134.7, 144.7], "EBIT": [114.3, 123.2, 133.0],
                           "Depreciacion": [11.5, 11.4, 11.7], "CAPEX": [11.0, 9.4, 12.7], "NWC": [-1.7, -23.4, -17.7]},
                          index=[2023, 2024, 2025])
        df.attrs["g_convergencia"] = 0.03
        return df

    def test_proyeccion_usa_el_consenso(self):
        df = self._hist()
        _, base = L.proyectar_por_drivers(df.copy(), 10, tax=0.16)
        df.attrs["consenso_ingresos"] = {"g": [0.148, 0.104]}
        proj, meta = L.proyectar_por_drivers(df.copy(), 10, tax=0.16)
        self.assertTrue(meta["tres_etapas"])
        self.assertFalse(base["tres_etapas"])
        self.assertAlmostEqual(float(proj["Ingresos"].iloc[0]), 416.2 * 1.148, places=6)
        self.assertAlmostEqual(meta["g_ingresos_ruta"][-1], 0.03)
        self.assertIn("tres etapas", meta["estimador_ingresos"])

    def test_ciclicas_no_usan_consenso(self):
        df = self._hist()
        df.attrs.update({"ciclico": True, "consenso_ingresos": {"g": [0.5]}})
        _, meta = L.proyectar_por_drivers(df, 10, tax=0.16)
        self.assertFalse(meta["tres_etapas"])


@unittest.skipUnless((L.DAMODARAN.get("betas") or {}).get("US"), "sin betas en datos_damodaran.json")
class TestBetaBottomUp(unittest.TestCase):
    INFO = {"country": "United States", "currency": "USD", "financialCurrency": "USD", "beta": 1.069,
            "sector": "Technology", "industry": "Consumer Electronics", "marketCap": 5.0e12, "totalDebt": 84e9,
            "totalCash": 62e9, "sharesOutstanding": 14.6e9, "regularMarketPrice": 347.1}

    def _df(self):
        return pd.DataFrame({"Ingresos": [383.3, 391.0, 416.2], "EBIT": [114.3, 123.2, 133.0]}, index=[2023, 2024, 2025])

    def test_beta_de_industria_como_referencia(self):
        p = L.derivar_params_desde_cero(self._df(), info=dict(self.INFO), ticker_yf="AAPL")
        b = L.damodaran_beta("Technology", "Consumer Electronics", "US")
        self.assertAlmostEqual(p["beta_industria_u"], round(b["beta_u"], 4))
        self.assertIn("bottom-up", p["beta_fuente"])
        self.assertTrue(p["beta_fuente"].startswith("yahoo"))  # la regresión (Blume) sigue siendo la base
        self.assertNotAlmostEqual(p["beta_u"], p["beta_industria_u"], places=2)

    def test_fuera_de_eeuu_no_cambia(self):
        self.assertIsNone(L.damodaran_beta("Technology", "Consumer Electronics", "CO"))
        info = dict(self.INFO, country="Colombia", currency="COP", financialCurrency="COP")
        p = L.derivar_params_desde_cero(self._df(), info=info, ticker_yf="X.CL")
        self.assertTrue(p["beta_fuente"].startswith("yahoo"))


class TestInversionesFinancieras(unittest.TestCase):
    def _bs(self, filas):
        return pd.DataFrame({k: [v] for k, v in filas.items()}, index=[pd.Timestamp("2025-09-30")]).T

    def test_valores_negociables_de_largo_plazo_al_puente(self):
        df = pd.DataFrame({"Ingresos": [383.3, 391.0, 416.2], "EBIT": [114.3, 123.2, 133.0]}, index=[2023, 2024, 2025])
        info = dict(TestBetaBottomUp.INFO, _balance_sheet=self._bs({"Available For Sale Securities": 77.7e9,
                                                                     "Stockholders Equity": 73.7e9,
                                                                     "Total Equity Gross Minority Interest": 73.7e9}))
        p = L.derivar_params_desde_cero(df, info=info, ticker_yf="AAPL")
        self.assertAlmostEqual(p["inversiones_financieras_lp"], 77.7, places=1)
        self.assertAlmostEqual(p["asociados"], 77.7, places=1)


class TestHorizonte(unittest.TestCase):
    def test_catalogo_colombiano_sigue_en_5(self):
        self.assertEqual(L.horizonte_recomendado("ISA — Interconexión Eléctrica"), 5)


if __name__ == "__main__":
    unittest.main()
