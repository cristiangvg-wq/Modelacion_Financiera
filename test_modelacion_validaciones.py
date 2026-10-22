"""Pruebas de regresión para modelacion_logic.py. Ejecutar: python test_modelacion_validaciones.py"""
import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import modelacion_logic as L


class TestNucleoValoracion(unittest.TestCase):
    def test_self_tests_core(self):
        results = L.self_test_valuation_core()
        self.assertGreaterEqual(len(results), 7)
        self.assertTrue(all(ok for _, ok, _ in results), results)

    def test_rechaza_entradas_wacc_invalidas(self):
        with self.assertRaises(ValueError):
            L.calcular_wacc(-0.1, 0.08, 0.12, 0.25)
        with self.assertRaises(ValueError):
            L.calcular_wacc(1.0, 0.08, 0.12, 1.2)
        with self.assertRaises(ValueError):
            L.valoracion_dcf([100], 0, 0.02)
        with self.assertRaises(ValueError):
            L.valoracion_dcf([], 0.1, 0.02)

    def test_fcff_final_negativo_no_se_reemplaza_por_promedio(self):
        result = L.valoracion_dcf([100, -10], 0.10, 0.02, mid_year=False)
        self.assertEqual(result["TV_Gordon"], 0)
        self.assertIn("TV Gordon = 0", result["bridge"].get("Nota TV", ""))

    def test_catalogo_todas_las_proyecciones_son_finitas_y_fcff_reconcilia(self):
        self.assertEqual(len(L.EMPRESAS), 7)
        for name, company in L.EMPRESAS.items():
            with self.subTest(company=name):
                hist, _ = L.cargar_y_limpiar_excel(None, name, usar_datos_publicos=False)
                projection, _meta = L.proyectar_por_drivers(
                    hist, horizonte=5, tax=company["params"]["tax"]
                )
                projection = L.recalcular_fcff(projection, tax=company["params"]["tax"])
                self.assertEqual(len(projection), 5)
                for col in ("FCFF", "EBITDA", "EBIT", "NOPAT"):
                    self.assertTrue(np.isfinite(projection[col].astype(float)).all(), (name, col))
                residual = (
                    projection["NOPAT"] + projection["Depreciacion"]
                    - projection["CAPEX"] - projection["Delta_NWC"] - projection["FCFF"]
                ).abs().max()
                self.assertLess(residual, 1e-8, name)

    def test_auditoria_historica_no_modifica_datos_y_detecta_diferencias(self):
        hist, _ = L.cargar_y_limpiar_excel(None, "GEB — Grupo Energía Bogotá", usar_datos_publicos=False)
        original = hist.copy(deep=True)
        findings = L.auditar_consistencia_historica(hist)
        self.assertTrue(findings)
        pd.testing.assert_frame_equal(hist, original)
        self.assertTrue(any(x["Estado"] == "REVISAR" for x in findings))

    def test_pestana_auditoria_funciona_para_catalogo(self):
        for name, company in L.EMPRESAS.items():
            with self.subTest(company=name):
                p = company["params"]
                html, checks = L.tab3_auditoria_teorica(
                    name, None, 5, p["de_ratio"], p["kd"], p["tax"], p["g"],
                    p["beta_u"], p["capital_invertido"], usar_datos_publicos=False
                )
                self.assertIsInstance(html, str)
                self.assertIsInstance(checks, pd.DataFrame)
                self.assertGreaterEqual(len(checks), 5)

    def test_empresa_personalizada_csv(self):
        frame = pd.DataFrame({
            "Año": [2021, 2022, 2023, 2024],
            "Ingresos": [1000, 1100, 1200, 1300],
            "EBITDA": [200, 220, 240, 260],
            "EBIT": [150, 165, 180, 195],
            "Depreciacion": [50, 55, 60, 65],
            "CAPEX": [80, 90, 100, 110],
            "NWC": [100, 110, 120, 130],
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8", newline="") as f:
            path = f.name
            frame.to_csv(f, index=False)
        try:
            hist, message = L.cargar_y_limpiar_excel(path, "Empresa de prueba", usar_datos_publicos=False)
            self.assertEqual(len(hist), 4)
            self.assertIn("Archivo propio validado", message)
            projection, _ = L.proyectar_por_drivers(hist, horizonte=3, tax=0.30)
            self.assertEqual(len(projection), 3)
            self.assertTrue(np.isfinite(projection["FCFF"].astype(float)).all())
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
