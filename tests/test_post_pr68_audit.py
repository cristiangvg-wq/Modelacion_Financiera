"""Regresiones posteriores a PR #68: snapshot de mercado, FX y unidades."""
import json
from pathlib import Path
import unittest

import modelacion_logic as L


ROOT = Path(__file__).resolve().parents[1]


class TestPostPR68Audit(unittest.TestCase):
    def test_explicit_incomplete_fx_map_does_not_fall_back_to_untracked_spot(self):
        result = L.convertir_precio_a_moneda_modelo(
            27500.0, "COP", "USD", tasas_cop_por_moneda={"EUR": 4400.0}
        )
        self.assertIsNone(result["precio"])
        self.assertFalse(result["convertido"])
        self.assertIn("mapa FX explícito incompleto", result["fuente_fx"])

    def test_explicit_cop_usd_rates_convert_price_in_correct_direction(self):
        result = L.convertir_precio_a_moneda_modelo(
            40000.0, "COP", "USD", tasas_cop_por_moneda={"USD": 4000.0}
        )
        self.assertTrue(result["convertido"])
        self.assertAlmostEqual(result["precio"], 10.0, places=10)
        self.assertAlmostEqual(result["fx"], 4000.0, places=10)

    def test_isa_snapshot_reconciles_price_shares_gross_debt_and_de_ratio(self):
        data = json.loads((ROOT / "datos_curados.json").read_text(encoding="utf-8"))
        isa = data["empresas"]["ISA — Interconexión Eléctrica"]
        sup, bridge = isa["supuestos"], isa["puente"]

        # El catálogo se actualizó después de la instantánea BVC fechada.
        self.assertGreaterEqual(data["as_of"], sup["fecha_precio_ref"][:10])
        self.assertEqual(sup["fuente_precio_ref"].strip(), sup["fuente_precio_ref"])
        self.assertTrue(sup["fuente_precio_ref"])
        self.assertEqual(bridge["acciones"], 1107.7)
        deuda_bruta = bridge["deuda_neta"] + bridge["caja"]
        self.assertAlmostEqual(deuda_bruta, 34155.0, places=8)

        # Precio COP/acción × acciones en millones / 1.000 = COP miles de millones.
        capitalizacion = sup["precio_ref_mercado"] * bridge["acciones"] / 1000.0
        self.assertAlmostEqual(capitalizacion, 30461.75, places=6)
        self.assertAlmostEqual(deuda_bruta / capitalizacion, sup["de_ratio"], places=4)
        self.assertAlmostEqual(bridge["deuda_neta"], deuda_bruta - bridge["caja"], places=8)


if __name__ == "__main__":
    unittest.main()
