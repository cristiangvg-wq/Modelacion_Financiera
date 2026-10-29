"""Pruebas de contrato multisectorial: las identidades financieras no dependen de ISA."""
import unittest

import numpy as np
import pandas as pd

import modelacion_logic as L


class TestContratoMultisectorial(unittest.TestCase):
    """Casos sintéticos de sectores y escalas diferentes; no calibran una empresa real."""

    def test_fcff_identity_is_sector_neutral(self):
        cases = [
            # ingresos, EBIT, D&A, CAPEX, delta NWC, tasa fiscal
            (1000.0, 180.0, 40.0, 70.0, 10.0, 0.25),   # servicios
            (5000.0, 600.0, 250.0, 420.0, -30.0, 0.30), # industria
            (300.0, 45.0, 15.0, 8.0, 5.0, 0.20),       # software/activos ligeros
        ]
        for ingresos, ebit, da, capex, dnwc, tax in cases:
            with self.subTest(ingresos=ingresos):
                df = pd.DataFrame({
                    "Ingresos": [ingresos], "EBIT": [ebit],
                    "Depreciacion": [da], "CAPEX": [capex],
                    "Delta_NWC": [dnwc],
                })
                out = L.recalcular_fcff(df, tax=tax)
                expected = ebit * (1 - tax) + da - capex - dnwc
                self.assertAlmostEqual(float(out["NOPAT"].iloc[0]), ebit * (1-tax), places=8)
                self.assertAlmostEqual(float(out["FCFF"].iloc[0]), expected, places=8)

    def test_operating_losses_do_not_create_automatic_tax_shield(self):
        result = L.calcular_nopat(np.array([-100.0, 100.0]), 0.25)
        np.testing.assert_allclose(result, [-100.0, 75.0])

    def test_wacc_weights_sum_to_one_for_multiple_capital_structures(self):
        for de in (0.0, 0.25, 1.0, 3.0):
            with self.subTest(de=de):
                wacc, we, wd = L.calcular_wacc(de, 0.07, 0.12, 0.25)
                self.assertAlmostEqual(we + wd, 1.0, places=12)
                self.assertGreater(wacc, 0.0)
                self.assertLessEqual(wacc, 0.12)

    def test_enterprise_to_equity_bridge_does_not_double_count_net_cash(self):
        # Las magnitudes están en una unidad monetaria común y en una escala consistente.
        flows = [100.0, 110.0, 120.0, 130.0, 140.0]
        bp = L.params_bridge_desde_ui(
            deuda_neta=80.0, caja=0.0, nci=10.0,
            otros_claims=5.0, asociados=15.0, acciones=20.0,
            exit_multiple=0.0, deuda_es_bruta=False,
        )
        val = L.valorar_con_bridge(flows, 0.10, 0.025, bp, mid_year=False)
        self.assertGreater(val["EV"], 0.0)
        self.assertAlmostEqual(val["Equity_Value"], val["EV"] - 80.0 - 10.0 - 5.0 + 15.0, places=6)

    def test_invalid_tax_and_missing_fcff_inputs_fail_loudly(self):
        with self.assertRaises(ValueError):
            L.calcular_nopat(100.0, 1.2)
        incomplete = pd.DataFrame({
            "EBIT": [100.0], "Depreciacion": [10.0],
            "CAPEX": [20.0],
        })
        with self.assertRaises(ValueError):
            L.recalcular_fcff(incomplete, tax=0.25)


    def test_currency_conversion_requires_explicit_rates_for_non_cop_usd_pairs(self):
        # Tasas expresadas como COP por una unidad de cada divisa; números sintéticos.
        rates = {"USD": 4000.0, "EUR": 4400.0, "GBP": 5000.0}
        eur_to_usd = L.convertir_precio_a_moneda_modelo(10.0, "EUR", "USD", rates)
        self.assertTrue(eur_to_usd["convertido"])
        self.assertAlmostEqual(eur_to_usd["precio"], 11.0, places=8)
        self.assertAlmostEqual(eur_to_usd["fx"], 1.1, places=8)

        missing = L.convertir_precio_a_moneda_modelo(10.0, "JPY", "USD")
        self.assertIsNone(missing["precio"])
        self.assertFalse(missing["convertido"])

    def test_currency_conversion_rejects_non_finite_prices_and_invalid_rates(self):
        bad_price = L.convertir_precio_a_moneda_modelo(float("nan"), "EUR", "USD",
                                                        {"EUR": 4400.0, "USD": 4000.0})
        self.assertIsNone(bad_price["precio"])
        bad_rate = L.convertir_precio_a_moneda_modelo(10.0, "EUR", "USD",
                                                       {"EUR": -1.0, "USD": 4000.0})
        self.assertIsNone(bad_rate["precio"])

    def test_upside_accepts_explicit_cross_currency_rates(self):
        # La función de alto nivel debe propagar las tasas al conversor; importes sintéticos.
        rates = {"EUR": 4400.0, "USD": 4000.0}
        result = L.calcular_vps_y_upside(
            equity=0.01, acciones_millones=1.0, precio_mercado=10.0,
            moneda_modelo="USD", moneda_precio="EUR",
            tasas_cop_por_moneda=rates,
        )
        self.assertAlmostEqual(result["precio_moneda_modelo"], 11.0, places=8)
        self.assertAlmostEqual(result["fx_aplicado"], 1.1, places=8)
        self.assertAlmostEqual(result["upside_pct"], (10.0 / 11.0 - 1.0) * 100.0, places=8)
        self.assertIn("EUR a USD", result["nota_vps"])

    def test_upside_cross_currency_without_rates_remains_blocked(self):
        result = L.calcular_vps_y_upside(
            equity=0.01, acciones_millones=1.0, precio_mercado=10.0,
            moneda_modelo="USD", moneda_precio="EUR",
        )
        self.assertIsNone(result["upside_pct"])
        self.assertIn("sin FX", result["nota_vps"])

    def test_dcf_rejects_terminal_growth_at_or_above_discount_rate_after_anchoring(self):
        # La función debe producir una valoración finita y no dejar Gordon singular.
        val = L.valoracion_dcf([100.0, 110.0, 120.0], 0.10, 0.10, mid_year=False)
        self.assertTrue(np.isfinite(val["EV"]))
        self.assertLess(val["g_used"], val["WACC"])


if __name__ == "__main__":
    unittest.main()
