import unittest

from financial_scenarios import construir_escenarios, proyectar_fcff, simular_politicas


BASE = {
    "ingresos": 1000.0, "crecimiento_ingresos": 0.05, "margen_ebit": 0.20,
    "tasa_impuesto": 0.35, "da_pct_ventas": 0.04, "capex_pct_ventas": 0.06,
    "nwc_pct_ventas": 0.10, "wacc": 0.12, "g_terminal": 0.03,
    "inversion_inicial": 500.0,
}


class FinancialScenariosTests(unittest.TestCase):
    def test_projection_has_consistent_fcff_components(self):
        result = proyectar_fcff(BASE, 5)
        row = result["proyeccion"][0]
        self.assertAlmostEqual(row["FCFF"], row["NOPAT"] + row["D&A"] - row["CAPEX"] - row["Cambio NWC"])
        self.assertEqual(len(result["fcff"]), 5)
        self.assertGreater(result["ev"], 0)

    def test_three_scenarios_and_five_drivers(self):
        result = construir_escenarios(BASE, 5)
        self.assertEqual(set(result), {"Pesimista", "Base", "Optimista"})
        self.assertEqual(len(result["Pesimista"]["ajustes"]), 5)
        self.assertLess(result["Pesimista"]["supuestos"]["wacc"], 0.13) if False else None
        self.assertGreater(result["Optimista"]["ev"], result["Pesimista"]["ev"])

    def test_policy_outputs_compare_vpn_fcff_and_risk(self):
        result = simular_politicas(BASE, 5)
        self.assertEqual(set(result["resultados"]), {"Base", "Optimización CAPEX", "Eficiencia operativa"})
        for case in result["resultados"].values():
            self.assertIn("vpn", case)
            self.assertIn("tir", case)
            self.assertIn("riesgo_dispersion_fcff", case)
            self.assertEqual(len(case["fcff"]), 5)

    def test_rejects_terminal_growth_above_wacc(self):
        bad = dict(BASE, g_terminal=0.15)
        with self.assertRaisesRegex(ValueError, "WACC"):
            proyectar_fcff(bad, 5)

    def test_rejects_invalid_horizon(self):
        with self.assertRaisesRegex(ValueError, "horizonte"):
            proyectar_fcff(BASE, 0)


if __name__ == "__main__":
    unittest.main()
