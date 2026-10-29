"""Guardrails metodológicos por tipo de negocio."""
import unittest
import modelacion_logic as L


class TestSectorMethodology(unittest.TestCase):
    def test_bancos_y_aseguradoras(self):
        for sector in ("Banco comercial", "Seguros de vida", "Insurance"):
            with self.subTest(sector=sector):
                r = L.recomendar_metodologia_sectorial(sector)
                self.assertEqual(r["metodo_principal"], "FCFE/dividendos/exceso de retornos")
                self.assertTrue(r["requiere_revision"])

    def test_reit(self):
        r = L.recomendar_metodologia_sectorial("REIT residencial")
        self.assertEqual(r["metodo_principal"], "FFO/AFFO y NAV")
        self.assertTrue(r["requiere_revision"])

    def test_holding(self):
        r = L.recomendar_metodologia_sectorial("Holding de infraestructura")
        self.assertEqual(r["metodo_principal"], "Suma de partes")
        self.assertTrue(r["requiere_revision"])

    def test_operativa_no_financiera(self):
        r = L.recomendar_metodologia_sectorial("Transmisión de energía")
        self.assertEqual(r["metodo_principal"], "DCF FCFF/WACC")
        self.assertFalse(r["requiere_revision"])

    def test_sector_desconocido(self):
        r = L.recomendar_metodologia_sectorial("")
        self.assertEqual(r["metodo_principal"], "Seleccionar método y validar actividad")
        self.assertTrue(r["requiere_revision"])


if __name__ == "__main__":
    unittest.main()
