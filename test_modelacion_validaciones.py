"""Pruebas de regresión para modelacion_logic.py. Ejecutar: python test_modelacion_validaciones.py"""
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import modelacion_logic as L


class TestNucleoValoracion(unittest.TestCase):
    def test_self_tests_core(self):
        results = L.self_test_valuation_core()
        self.assertGreaterEqual(len(results), 7)
        self.assertTrue(all(ok for _, ok, _ in results), results)

    def test_vps_isa_no_recalibra_acciones_para_forzar_precio(self):
        result = L.calcular_vps_y_upside(
            33066.40, 1108, precio_mercado=28.5,
            moneda_modelo="COP", moneda_precio="COP",
        )
        self.assertAlmostEqual(result["value_per_share"], 29843.32, places=2)
        self.assertIsNone(result["upside_pct"])
        self.assertEqual(result["acciones"], 1108)
        self.assertIn("upside bloqueado", result["nota_vps"].lower())

    def test_vps_comite_usa_factor_miles_millones_a_millones(self):
        result = L.calcular_vps_y_upside(33066.40, 1108, moneda_modelo="COP", moneda_precio="COP")
        self.assertAlmostEqual(result["value_per_share"], 29843.32, places=2)

    def test_calcular_nopat_no_reconoce_escudo_fiscal_sin_utilidad(self):
        ebit = pd.Series([-100.0, 0.0, 100.0])
        nopat = L.calcular_nopat(ebit, 0.30)
        np.testing.assert_allclose(nopat.to_numpy(), [-100.0, 0.0, 70.0])
        with self.assertRaises(ValueError):
            L.calcular_nopat(ebit, 1.2)

    def test_anclaje_g_informa_cuando_cambia_supuestos(self):
        msgs = L.validar_inputs_valoracion(0.10, 0.08, g_max_macro=0.05)
        self.assertTrue(any("ingresado" in m and "utilizado" in m for m in msgs))

    def test_resolver_precio_isa_normaliza_yahoo_miles_de_cop(self):
        empresa = {
            "ticker_yf": "ISA.CL",
            "ticker_bvc": "ISA",
            "params": {"moneda": "COP"},
        }
        with patch.object(L, "resolver_empresa", return_value=empresa), \
             patch.object(L, "obtener_datos_mercado_bvc", return_value={
                 "ok": True, "precio": 28.5, "fuente": "yahoo:ISA.CL",
                 "proveedor": "yahoo",
             }):
            self.assertAlmostEqual(
                L.resolver_precio_mercado("ISA — Interconexión Eléctrica"),
                28500.0,
                places=2,
            )

    def test_resolver_precio_no_escala_otras_empresas_ni_fuentes(self):
        empresa = {
            "ticker_yf": "OTRA.CL",
            "ticker_bvc": "OTRA",
            "params": {"moneda": "COP"},
        }
        with patch.object(L, "resolver_empresa", return_value=empresa), \
             patch.object(L, "obtener_datos_mercado_bvc", return_value={
                 "ok": True, "precio": 28.5, "fuente": "yahoo:OTRA.CL",
                 "proveedor": "yahoo",
             }):
            self.assertAlmostEqual(L.resolver_precio_mercado("Otra"), 28.5)

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


    def test_auditoria_contexto_comite_detecta_g_wacc_y_unidades(self):
        ctx = {
            "precio_mercado": 100.0, "vps_modelo": 120.0, "upside": 20.0,
            "wacc_calc": 0.08, "ke_calc": 0.12, "roic_calc": 0.10,
            "de_ratio": 0.5, "g": 0.09, "val_ev": 1000.0, "val_equity": 800.0,
            "moneda": "COP", "moneda_precio": "COP",
        }
        audit = L.auditar_contexto_comite_ia(ctx)
        self.assertFalse(audit["ok"])
        self.assertTrue(any("g terminal debe ser menor que WACC" in e for e in audit["errors"]))
        self.assertAlmostEqual(audit["upside_recalculado"], 20.0)
        self.assertTrue(any("unidad" in w.lower() for w in audit["warnings"]))

    def test_auditoria_contexto_detecta_upside_inconsistente(self):
        ctx = {
            "precio_mercado": 100.0, "vps_modelo": 125.0, "upside": 10.0,
            "wacc_calc": 0.10, "ke_calc": 0.12, "roic_calc": 0.11,
            "de_ratio": 0.4, "g": 0.03, "val_ev": 1000.0, "val_equity": 800.0,
            "moneda": "COP", "moneda_precio": "COP", "unidad_modelo": "COP miles de millones",
            "fuente_precio": "test", "fecha_precio": "2026-10-22", "fuente_valoracion": "DCF test",
        }
        audit = L.auditar_contexto_comite_ia(ctx)
        self.assertTrue(audit["ok"])
        self.assertAlmostEqual(audit["upside_recalculado"], 25.0)
        self.assertTrue(any("Upside informado" in w for w in audit["warnings"]))

    def test_comite_prompt_exige_no_inventar_comparables_y_bloquear_errores(self):
        original_base = L._metricas_comite_para_ia
        original_call = L._llamar_ia_redaccion
        captured = {}
        try:
            L._metricas_comite_para_ia = lambda _name: {}
            def fake_call(system, user, **kwargs):
                captured["prompt"] = user
                return "## 1. Deliberación\n## 2. Brecha\n## 3. Decisión\n## 4. Monitoreo"
            L._llamar_ia_redaccion = fake_call
            metrics = {
                "empresa": "Test", "moneda": "COP", "moneda_precio": "COP",
                "precio_mercado": 100, "vps_modelo": 110, "upside": 10,
                "wacc_calc": 0.10, "ke_calc": 0.12, "roic_calc": 0.11,
                "de_ratio": 0.5, "g": 0.03, "val_ev": 1000, "val_equity": 800,
                "unidad_modelo": "COP miles de millones", "unidad_precio": "por acción",
                "fuente_precio": "test", "fecha_precio": "2026-10-22", "fuente_valoracion": "DCF test",
            }
            L.generar_recomendacion_comite_ia("Test", metricas=metrics)
            self.assertIn("no inventes comparables", captured["prompt"].lower())
            self.assertIn("errores bloqueantes", captured["prompt"].lower())
        finally:
            L._metricas_comite_para_ia = original_base
            L._llamar_ia_redaccion = original_call

    def test_comite_reintenta_una_vez_si_la_ia_repite_el_prompt(self):
        original_base = L._metricas_comite_para_ia
        original_call = L._llamar_ia_redaccion
        calls = []
        valid = (
            "## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO\\n"
            "## 2. ANÁLISIS DE BRECHA\\n"
            "## 3. DECISIÓN FINAL DE INVERSIÓN\\n"
            "RECOMENDACIÓN FINAL: INVERTIR CONDICIONALMENTE\\n"
            "PUNTAJE DE VIABILIDAD: 6/10\\n"
            "## 4. FACTORES CRÍTICOS"
        )
        try:
            L._metricas_comite_para_ia = lambda _name: {}
            def fake_call(system, user, **kwargs):
                calls.append(user)
                return "CONTEXTO DE ENTRADA" if len(calls) == 1 else valid
            L._llamar_ia_redaccion = fake_call
            metrics = {
                "empresa": "Test", "moneda": "COP", "moneda_precio": "COP",
                "precio_mercado": 100, "vps_modelo": 110, "upside": 10,
                "wacc_calc": 0.10, "ke_calc": 0.12, "roic_calc": 0.11,
                "de_ratio": 0.5, "g": 0.03, "val_ev": 1000, "val_equity": 800,
                "unidad_modelo": "COP miles de millones", "unidad_precio": "por acción",
                "fuente_precio": "test", "fecha_precio": "2026-10-22", "fuente_valoracion": "DCF test",
            }
            result = L.generar_recomendacion_comite_ia("Test", metricas=metrics)
            self.assertEqual(len(calls), 2)
            self.assertIn("COMITÉ INTERDISCIPLINARIO", result)
        finally:
            L._metricas_comite_para_ia = original_base
            L._llamar_ia_redaccion = original_call

    def test_auditoria_respuesta_comite_detecta_prompt_y_plantillas(self):
        result = L.auditar_respuesta_comite_ia("CONTEXTO DE ENTRADA\nRECOMENDACIÓN FINAL: [ ... ]")
        self.assertFalse(result["ok"])
        self.assertTrue(any("prompt" in e.lower() for e in result["errors"]))
        self.assertTrue(any("plantilla" in e.lower() for e in result["errors"]))

    def test_auditoria_respuesta_comite_detecta_puntaje_fuera_de_rango(self):
        result = L.auditar_respuesta_comite_ia(
            "## DELIBERACIÓN\n## ANÁLISIS DE BRECHA\n## DECISIÓN FINAL\n"
            "RECOMENDACIÓN FINAL: INVERTIR\nPUNTAJE DE VIABILIDAD: 12/10\n"
            "## FACTORES CRÍTICOS"
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("fuera de escala" in e.lower() for e in result["errors"]))

    def test_auditoria_contexto_bloquea_metricas_esenciales_ausentes(self):
        audit = L.auditar_contexto_comite_ia({
            "precio_mercado": 100.0,
            "vps_modelo": 110.0,
            "wacc_calc": 0.10,
        })
        self.assertFalse(audit["ok"])
        self.assertTrue(any("métricas financieras esenciales" in e.lower() for e in audit["errors"]))

    def test_auditoria_contexto_bloquea_discrepancia_extrema_vps_precio(self):
        audit = L.auditar_contexto_comite_ia({
            "precio_mercado": 28500.0,
            "vps_modelo": 29.84,
            "upside": -99.9,
            "wacc_calc": 0.1089,
            "ke_calc": 0.1647,
            "roic_calc": None,
            "de_ratio": 1.20,
            "g": 0.03,
            "val_ev": 1000.0,
            "val_equity": 800.0,
            "moneda": "COP",
            "moneda_precio": "COP",
            "unidad_modelo": "COP miles de millones",
            "unidad_precio": "por acción",
            "fuente_precio": "test",
            "fecha_precio": "2026-10-22",
            "fuente_valoracion": "DCF test",
        })
        self.assertFalse(audit["ok"])
        self.assertTrue(any("comparabilidad bloqueada" in e.lower() for e in audit["errors"]))
        self.assertAlmostEqual(audit["upside_recalculado"], 100 * (29.84 / 28500 - 1), places=4)

    def test_auditoria_respuesta_detecta_roic_cero_sin_respaldo(self):
        text = "ROIC: 0.00%\\n## 1. DELIBERACIÓN"
        audit = L.auditar_respuesta_comite_ia(text, {"roic_calc": None})
        self.assertFalse(audit["ok"])
        self.assertTrue(any("roic 0%" in e.lower() for e in audit["errors"]))

    def test_auditoria_respuesta_normaliza_encabezados_escapados(self):
        audit = L.auditar_respuesta_comite_ia("\\\\## 1. DELIBERACIÓN")
        self.assertTrue(audit["texto"].startswith("##"))

    def test_roic_sectorial_no_se_imputa_si_faltan_nopat_y_ebit(self):
        emp = {
            "historico": {
                "Año": [2023, 2024],
                "Ingresos": [100.0, 110.0],
                "EBITDA": [20.0, 22.0],
                "FCFF": [5.0, 6.0],
            },
            "params": {"de_ratio": 0.5, "kd": 0.08, "tax": 0.3, "beta_u": 0.5},
            "ticker_yf": None,
            "pais": None,
            "moneda": "COP",
        }
        row, _, _, _ = L._fila_sectorial_desde_emp("Empresa sin NOPAT", emp)
        self.assertIsNone(row["ROIC (%)"])

    def test_roic_sectorial_deriva_nopat_desde_ebit_sin_inventar_capital(self):
        emp = {
            "historico": {
                "Año": [2023, 2024],
                "Ingresos": [100.0, 110.0],
                "EBITDA": [20.0, 22.0],
                "EBIT": [10.0, 12.0],
                "FCFF": [5.0, 6.0],
            },
            "params": {"de_ratio": 0.5, "kd": 0.08, "tax": 0.25, "beta_u": 0.5},
            "ticker_yf": None,
            "pais": None,
            "moneda": "COP",
        }
        row, _, _, _ = L._fila_sectorial_desde_emp("Empresa sin capital invertido", emp)
        self.assertIsNone(row["ROIC (%)"])

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
