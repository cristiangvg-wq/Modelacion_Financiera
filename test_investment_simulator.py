import unittest

from investment_simulator import simular_inversion


class InvestmentSimulatorTests(unittest.TestCase):
    def test_same_currency_and_flat_price(self):
        result = simular_inversion(
            capital=10000, moneda_capital="USD", moneda_activo="USD",
            tasa_cop_usd=4000, precio_actual=100, horizonte=2,
            escenarios={"Base": 0.0}, dividend_yield=0.0,
            costo_compra=0.0, costo_venta=0.0,
        )
        summary = result["resumen"]
        self.assertEqual(summary["acciones"], 100)
        self.assertAlmostEqual(summary["escenarios"]["Base"]["valor_final"], 10000)
        self.assertAlmostEqual(summary["escenarios"]["Base"]["rentabilidad_total"], 0.0)
        self.assertEqual(len(result["trayectoria"]), 3)

    def test_cop_capital_converted_to_usd_asset(self):
        result = simular_inversion(
            capital=4000000, moneda_capital="COP", moneda_activo="USD",
            tasa_cop_usd=4000, precio_actual=100, horizonte=1,
            escenarios={"Base": 0.10},
        )
        self.assertEqual(result["resumen"]["acciones"], 10)
        self.assertAlmostEqual(result["resumen"]["escenarios"]["Base"]["valor_final"], 4400000)

    def test_fees_and_dividends_are_accounted_for(self):
        result = simular_inversion(
            capital=1000, moneda_capital="USD", moneda_activo="USD",
            tasa_cop_usd=4000, precio_actual=100, horizonte=1,
            escenarios={"Base": 0.0}, dividend_yield=0.05,
            costo_compra=0.01, costo_venta=0.01, impuesto_dividendos=0.2,
        )
        self.assertEqual(result["resumen"]["acciones"], 9)
        row = result["resumen"]["escenarios"]["Base"]
        self.assertLess(row["valor_final"], 1000)
        self.assertGreater(row["dividendos_netos"], 0)

    def test_rejects_unsupported_currency(self):
        with self.assertRaisesRegex(ValueError, "Solo se admiten"):
            simular_inversion(
                capital=1000, moneda_capital="USD", moneda_activo="EUR",
                tasa_cop_usd=4000, precio_actual=10, horizonte=1,
                escenarios={"Base": 0.05},
            )

    def test_rejects_invalid_assumptions(self):
        with self.assertRaisesRegex(ValueError, "capital"):
            simular_inversion(
                capital=0, moneda_capital="COP", moneda_activo="COP",
                tasa_cop_usd=4000, precio_actual=10, horizonte=1,
                escenarios={"Base": 0.05},
            )


if __name__ == "__main__":
    unittest.main()
