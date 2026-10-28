"""Empresas maduras de consumo de EE. UU.: industria de Damodaran y beta cuando la regresión no informa."""
import unittest

import pandas as pd

import modelacion_logic as L

BASE = {"country": "United States", "currency": "USD", "financialCurrency": "USD", "marketCap": 390e9,
        "totalDebt": 41.6e9, "totalCash": 16.6e9, "sharesOutstanding": 4.3e9, "regularMarketPrice": 91.0}
DF = pd.DataFrame({"Ingresos": [45.75, 47.06, 47.94], "EBIT": [13.1, 14.02, 14.91]}, index=[2023, 2024, 2025])
TIENE_BETAS = bool((L.DAMODARAN.get("betas") or {}).get("US"))


class TestIndustrias(unittest.TestCase):
    def test_consumo_mapeado(self):
        casos = {("Consumer Defensive", "Beverages - Non-Alcoholic"): "Beverage (Soft)",
                 ("Consumer Defensive", "Household & Personal Products"): "Household Products",
                 ("Consumer Defensive", "Confectioners"): "Food Processing",
                 ("Consumer Defensive", "Discount Stores"): "Retail (General)",
                 ("Consumer Defensive", "Tobacco"): "Tobacco",
                 ("Consumer Cyclical", "Restaurants"): "Restaurant/Dining",
                 ("Consumer Defensive", "Packaged Foods"): "Food Processing"}
        for (sec, ind), esperado in casos.items():
            self.assertEqual(L.industria_damodaran(sec, ind), esperado, ind)

    def test_catalogo_colombiano_sin_cambio(self):
        self.assertEqual(L.industria_damodaran("Transmisión de energía", "Infraestructura"), "Power")
        self.assertEqual(L.industria_damodaran("Petróleo, gas y energía", ""), "Oil/Gas (Integrated)")


@unittest.skipUnless(TIENE_BETAS, "sin betas en datos_damodaran.json")
class TestBetaNoInformativa(unittest.TestCase):
    def _p(self, **kw):
        info = dict(BASE, sector="Consumer Defensive", industry="Beverages - Non-Alcoholic", **kw)
        return L.derivar_params_desde_cero(DF, info=info, ticker_yf="KO")

    def test_sin_beta_en_yahoo_usa_la_industria(self):
        p = self._p()
        self.assertAlmostEqual(p["beta_u"], p["beta_industria_u"])
        self.assertIn("Yahoo sin beta", p["beta_fuente"])

    def test_beta_casi_cero_usa_la_industria(self):
        p = self._p(beta=0.02)
        self.assertAlmostEqual(p["beta_u"], p["beta_industria_u"])
        self.assertIn("no informativa", p["beta_fuente"])
        self.assertIsNotNone(p["beta_regresion_u"])

    def test_beta_informativa_se_conserva(self):
        p = self._p(beta=0.45)
        self.assertTrue(p["beta_fuente"].startswith("yahoo"))
        self.assertNotAlmostEqual(p["beta_u"], p["beta_industria_u"], places=3)

    def test_fuera_de_eeuu_sigue_el_proxy(self):
        info = dict(BASE, country="Colombia", currency="COP", financialCurrency="COP",
                    sector="Consumer Defensive", industry="Beverages - Non-Alcoholic")
        p = L.derivar_params_desde_cero(DF, info=info, ticker_yf="X.CL")
        self.assertEqual(p["beta_fuente"], "proxy_mercado_1.0")


if __name__ == "__main__":
    unittest.main()
