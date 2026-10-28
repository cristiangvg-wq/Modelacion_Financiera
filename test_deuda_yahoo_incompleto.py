"""Yahoo con `info` incompleto (sin totalDebt) no debe dejar la deuda neta en 0."""
import unittest
import pandas as pd
import modelacion_logic as L

ISA = "ISA — Interconexión Eléctrica"


class DeudaYahooIncompleto(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})
        self._orig = L.buscar_y_descargar_empresa
        self._hay_yf = L.HAS_YF

    def tearDown(self):
        L.buscar_y_descargar_empresa = self._orig
        L.HAS_YF = self._hay_yf
        L.vincular_estado_sesion({})

    def test_balance_anual_da_deuda_y_caja(self):
        bs = pd.DataFrame({"2025": [30_000e9, 4_000e9], "2024": [28_000e9, 3_500e9]},
                          index=["Total Debt", "Cash And Cash Equivalents"])
        self.assertEqual(L._deuda_y_caja_balance(bs), (30_000e9, 4_000e9))  # sin renglón con inversiones CP
        bs2 = pd.DataFrame({"2025": [20e9, 5e9]}, index=["Long Term Debt", "Current Debt"])
        self.assertEqual(L._deuda_y_caja_balance(bs2), (25e9, None))
        self.assertEqual(L._deuda_y_caja_balance(None), (None, None))

    def test_preparar_empresa_usa_deuda_del_catalogo(self):
        cat = L.EMPRESAS[ISA]["params"]

        def falso(tk, nombre_display=None, **k):
            L.EMPRESAS_RUNTIME[nombre_display] = {
                "params": {"deuda_neta": 0.0, "caja": 0.0, "nci": 0.0, "asociados": 0.0, "beta_u": 0.3},
                "ticker_yf": tk,
            }
            return True, "", nombre_display, None
        L.buscar_y_descargar_empresa = falso
        L.HAS_YF = True
        est = L.preparar_empresa(ISA, forzar=True)
        p = L.EMPRESAS_RUNTIME[ISA]["params"]
        self.assertEqual(p["deuda_neta"], cat["deuda_neta"])
        self.assertGreater(p["deuda_neta"], 0)
        self.assertIn("deuda_neta", est["detalle"])
        self.assertIn("catálogo", p["deuda_fuente"])

    def test_nota_sin_moneda_no_dice_distinta(self):
        r = L.calcular_vps_y_upside(27_000, 1_108, precio_mercado=27_520)
        self.assertIsNone(r["upside_pct"])
        self.assertNotIn("≠", r.get("nota_vps") or "")


if __name__ == "__main__":
    unittest.main()


class InfoYahooIncompleto(unittest.TestCase):
    """Auditoría 4: cada campo que falta en `info` se completa en lugar de cambiar el valor en silencio."""

    def test_pais_inferido_por_bolsa(self):
        i = L._completar_info_yahoo({"exchange": "NMS", "currency": "USD"}, None, "AAPL")
        self.assertEqual(L._mercado_desde_pais(i["country"]), "US")
        self.assertEqual(L._completar_info_yahoo({}, None, "ISA.CL")["country"], "Colombia")
        self.assertNotIn("country", L._completar_info_yahoo({"currency": "EUR"}, None, "SAP.DE"))

    def test_ltm_desde_trimestres(self):
        q = pd.DataFrame([[10.0, 11.0, 12.0, 13.0, 9.0], [4.0, 4.0, 5.0, 5.0, 3.0]], index=["Total Revenue", "EBITDA"])

        class T:
            quarterly_income_stmt = q
        i = L._completar_info_yahoo({"country": "Colombia"}, T(), "ECOPETROL.CL")
        self.assertEqual(i["totalRevenue"], 46.0)
        self.assertEqual(i["ebitda"], 18.0)
        self.assertIn("EBITDA 12m de los trimestres", i["_completado"])

    def test_sin_totaldebt_ni_caja_usa_balance_y_desapalanca(self):
        bs = pd.DataFrame({"2025": [30_000e9, 4_000e9]}, index=["Total Debt", "Cash And Cash Equivalents"])
        df = pd.DataFrame({"Ingresos": [100.0, 110.0], "EBITDA": [50.0, 55.0], "EBIT": [40.0, 44.0],
                           "Depreciacion": [10.0, 11.0], "CAPEX": [12.0, 13.0], "NWC": [5.0, 5.5],
                           "NOPAT": [30.0, 33.0], "FCFF": [28.0, 30.0], "Delta_NWC": [0.0, 0.5]}, index=[2024, 2025])
        info = {"country": "Colombia", "currency": "COP", "financialCurrency": "COP", "beta": 0.6,
                "sharesOutstanding": 1_107_677_894, "currentPrice": 27_000.0, "_balance_sheet": bs}
        p = L.derivar_params_desde_cero(df, info=info, ticker_yf="ISA.CL")
        self.assertAlmostEqual(p["deuda_neta"], 26_000.0, places=2)
        self.assertAlmostEqual(p["caja"], 4_000.0, places=2)
        self.assertGreater(p["de_ratio"], 0.5)  # sin deuda, D/E era 0 y el β no se desapalancaba
        self.assertIn("balance", p["deuda_fuente"])
