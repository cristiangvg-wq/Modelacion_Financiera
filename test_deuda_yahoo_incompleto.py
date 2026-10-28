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
        self.assertEqual(L._deuda_y_caja_balance(bs), (30_000e9, 4_000e9))
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
