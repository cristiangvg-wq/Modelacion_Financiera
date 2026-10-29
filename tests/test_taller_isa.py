import json
import tempfile
import unittest
from pathlib import Path

from scripts.taller_isa import (
    DEFAULT_DATA, POLICIES, SCENARIOS, build_projection, load_isa, run_model
)


class TestTallerISA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isa = load_isa(DEFAULT_DATA)

    def test_three_scenarios_and_five_drivers(self):
        self.assertEqual(set(SCENARIOS), {"Pesimista", "Base", "Optimista"})
        self.assertGreaterEqual(len(self.isa["history"]), 3)
        self.assertEqual(len([
            "crecimiento de ingresos", "margen EBIT", "ratio CAPEX/ingresos",
            "ratio NWC/ingresos", "depreciación/ingresos"
        ]), 5)

    def test_two_distinct_policies_have_explicit_rules(self):
        self.assertGreaterEqual(len(POLICIES) - 1, 2)
        self.assertGreater(POLICIES["Priorizar CAPEX"]["capex_saving"], 0)
        self.assertGreater(POLICIES["Eficiencia operativa"]["ebit_margin_uplift"], 0)

    def test_projection_has_five_years_and_reconciles_fcff(self):
        rows = build_projection("Base", "Sin política", self.isa)
        self.assertEqual([r["año"] for r in rows], [2026, 2027, 2028, 2029, 2030])
        for r in rows:
            expected = r["nopat"] + r["depreciacion"] - r["capex"] - r["delta_nwc"]
            self.assertAlmostEqual(r["fcff"], expected, places=7)

    def test_policy_changes_results(self):
        base = build_projection("Base", "Sin política", self.isa)
        capex = build_projection("Base", "Priorizar CAPEX", self.isa)
        efficiency = build_projection("Base", "Eficiencia operativa", self.isa)
        self.assertGreater(capex[0]["fcff"], base[0]["fcff"])
        self.assertGreater(efficiency[0]["fcff"], base[0]["fcff"])

    def test_export_creates_auditable_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_model(DEFAULT_DATA, Path(tmp))
            self.assertEqual(len(result["summary"]), 9)
            self.assertEqual(len(result["detail"]), 45)
            for filename in ("detalle_escenarios_politicas.csv", "resumen_escenarios_politicas.csv", "metadatos_modelo.json"):
                self.assertTrue((Path(tmp) / filename).exists())
            metadata = json.loads((Path(tmp) / "metadatos_modelo.json").read_text(encoding="utf-8"))
            self.assertIn("CAPEX", " ".join(metadata["drivers"]))


if __name__ == "__main__":
    unittest.main()
