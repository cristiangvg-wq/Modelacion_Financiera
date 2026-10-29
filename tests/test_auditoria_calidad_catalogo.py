"""Auditoría de trazabilidad: los supuestos curados deben viajar con su calidad."""
import unittest

import modelacion_logic as L


class TestAuditoriaCalidadCatalogo(unittest.TestCase):
    def test_todas_las_empresas_curadas_exponen_calidad_de_datos(self):
        self.assertGreater(len(L.EMPRESAS), 0)
        campos = {"historico", "nwc", "impuestos", "asociadas", "mercado", "metodologia"}
        for nombre, empresa in L.EMPRESAS.items():
            with self.subTest(empresa=nombre):
                calidad = empresa.get("calidad_datos") or {}
                self.assertTrue(campos.issubset(calidad.keys()))
                self.assertTrue(all(isinstance(calidad[k], str) and calidad[k].strip() for k in campos))
                params = L.params_empresa(nombre)
                self.assertEqual(params.get("calidad_datos"), calidad)
                self.assertTrue(params.get("tax_estado"))

    def test_isa_no_se_presenta_como_tasa_fiscal_operativa_validada(self):
        nombre = "ISA — Interconexión Eléctrica"
        p = L.params_empresa(nombre)
        self.assertAlmostEqual(float(p["tax"]), 0.22, places=8)
        self.assertEqual(p["tax_estado"], "provisional_no_validado")
        self.assertIn("no valida", p["fuente_tax"].lower())
        self.assertEqual(p["calidad_datos"]["nwc"], "estimado_no_auditado")
        self.assertEqual(p["calidad_datos"]["asociadas"], "valor_contable_no_valorado")
        self.assertEqual(p["calidad_datos"]["mercado"], "snapshot_fechado")

    def test_empresas_sin_serie_no_se_marcan_como_historico_validado(self):
        for nombre in ("EPM — Empresas Públicas de Medellín", "ENEL Colombia"):
            with self.subTest(empresa=nombre):
                p = L.params_empresa(nombre)
                self.assertEqual(p["calidad_datos"]["historico"], "no_disponible")
                self.assertEqual(p["calidad_datos"]["nwc"], "no_disponible")

    def test_el_catalogo_no_certifica_metodo_fcff_para_todos_los_sectores(self):
        for nombre, empresa in L.EMPRESAS.items():
            with self.subTest(empresa=nombre):
                texto = empresa["calidad_datos"]["metodologia"].lower()
                self.assertIn("validar metodología sectorial", texto)


if __name__ == "__main__":
    unittest.main()
