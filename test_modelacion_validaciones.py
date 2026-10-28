"""Pruebas de regresión para modelacion_logic.py. Ejecutar: python test_modelacion_validaciones.py"""
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import modelacion_logic as L


class TestNucleoValoracion(unittest.TestCase):
    def test_score_sectorial_no_inventa_multiplo_cuando_todos_faltan(self):
        df = pd.DataFrame({
            "Empresa": ["AAA", "BBB"],
            "Margen EBITDA (%)": [20.0, 15.0],
            "ROIC (%)": [None, None],
            "WACC estimado (%)": [None, None],
            "Crecimiento Ingresos 3a (%)": [None, None],
            "EV/EBITDA (x)": [None, None],
        })
        scored = L.calcular_score_sectorial(df)
        self.assertTrue(scored["EV/EBITDA (x)"].isna().all())
        self.assertTrue(np.isfinite(scored["Score"]).all())

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

    def test_anclaje_g_terminal_preserva_crecimiento_negativo(self):
        g_use, g_cap = L.anclar_g_terminal(-0.02, 0.08, g_max_macro=0.04)
        self.assertAlmostEqual(g_use, -0.02)
        self.assertAlmostEqual(g_cap, 0.04)

    def test_anclaje_g_terminal_rechaza_wacc_invalido(self):
        with self.assertRaises(ValueError):
            L.anclar_g_terminal(0.02, 0.0)

    def test_vps_bloquea_upside_si_falta_moneda_confirmada(self):
        result = L.calcular_vps_y_upside(
            0.08, 10.0, precio_mercado=8.0,
            moneda_modelo="COP", moneda_precio=None,
        )
        self.assertIsNotNone(result["value_per_share"])
        self.assertIsNone(result["upside_pct"])
        self.assertIn("moneda", (result["nota_vps"] or "").lower())

    def test_vps_rechaza_unidades_invalidas_sin_generar_upside(self):
        result = L.calcular_vps_y_upside(
            100.0, 0, precio_mercado=10.0,
            moneda_modelo="COP", moneda_precio="COP",
        )
        self.assertIsNone(result["value_per_share"])
        self.assertIsNone(result["upside_pct"])

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

    def test_capm_valida_entradas_y_calcula_ke(self):
        self.assertAlmostEqual(L.costo_equity_capm(1.2, 0.04, 0.05, 0.01), 0.11)
        with self.assertRaises(ValueError):
            L.costo_equity_capm(1.0, float("nan"), 0.05, 0.0)
        with self.assertRaises(ValueError):
            L.costo_equity_capm(-0.5, 0.04, 0.05, 0.0)

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

    def test_proyeccion_separa_depreciacion_de_diferencia_ebitda_ebit(self):
        # ISA publica EBITDA que incluye impuestos operativos y resultados de participadas;
        # D&A debe provenir de la partida contable, no de EBITDA - EBIT.
        hist = pd.DataFrame({
            "Ingresos": [1000.0, 1000.0, 1000.0],
            "EBITDA": [200.0, 200.0, 200.0],
            "EBIT": [150.0, 150.0, 150.0],
            "Depreciacion": [30.0, 30.0, 30.0],
            "CAPEX": [100.0, 100.0, 100.0],
            "NWC": [50.0, 50.0, 50.0],
        }, index=[2022, 2023, 2024])
        proj, _ = L.proyectar_por_drivers(
            hist, horizonte=1, tax=0.22, convergencia_capex=False
        )
        self.assertAlmostEqual(float(proj["EBIT"].iloc[0]), 150.0, places=6)
        self.assertAlmostEqual(float(proj["Depreciacion"].iloc[0]), 30.0, places=6)
        self.assertAlmostEqual(
            float(proj["FCFF"].iloc[0]), 150.0 * (1 - 0.22) + 30.0 - 100.0, places=6
        )

    def test_shocks_base_preservan_ebit_y_shock_ingresos_escala_ebitda(self):
        base = pd.DataFrame({
            "Ingresos": [1000.0, 1100.0],
            "EBITDA": [200.0, 220.0],
            "EBIT": [150.0, 165.0],
            "Depreciacion": [30.0, 33.0],
            "CAPEX": [100.0, 110.0],
            "Delta_NWC": [5.0, 5.0],
            "NOPAT": [117.0, 128.7],
            "FCFF": [42.0, 46.7],
        }, index=[2026, 2027])
        base_shock = L.aplicar_shocks_drivers_proyeccion(
            base, tax=0.22,
            shock={"g_ingresos": 1.0, "margen_ebitda": 1.0, "capex_factor": 1.0, "nwc_factor": 1.0},
        )
        np.testing.assert_allclose(base_shock["EBIT"].to_numpy(), base["EBIT"].to_numpy())
        np.testing.assert_allclose(base_shock["EBITDA"].to_numpy(), base["EBITDA"].to_numpy())
        revenue_shock = L.aplicar_shocks_drivers_proyeccion(
            base, tax=0.22,
            shock={"g_ingresos": 0.9, "margen_ebitda": 1.0, "capex_factor": 1.0, "nwc_factor": 1.0},
        )
        np.testing.assert_allclose(revenue_shock["Ingresos"].to_numpy(), base["Ingresos"].to_numpy() * 0.9)
        np.testing.assert_allclose(revenue_shock["EBITDA"].to_numpy(), base["EBITDA"].to_numpy() * 0.9)
        np.testing.assert_allclose(
            revenue_shock["EBIT"].to_numpy(),
            base["EBIT"].to_numpy() + base["EBITDA"].to_numpy() * (0.9 - 1.0),
        )

    def test_catalogo_todas_las_proyecciones_son_finitas_y_fcff_reconcilia(self):
        self.assertEqual(len(L.EMPRESAS), 7)
        for name, company in L.EMPRESAS.items():
            with self.subTest(company=name):
                if not company.get("historico"):
                    # Sin serie curada verificada (EPM, Enel): exige EEFF del usuario.
                    with self.assertRaises(ValueError):
                        L.cargar_y_limpiar_excel(None, name, usar_datos_publicos=False)
                    continue
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
        # La serie curada ya cumple las identidades; se introduce una diferencia
        # deliberada para comprobar que la auditoría la detecta sin corregirla.
        hist.loc[hist.index[-1], "FCFF"] = float(hist["FCFF"].iloc[-1]) + 500.0
        original = hist.copy(deep=True)
        findings = L.auditar_consistencia_historica(hist)
        self.assertTrue(findings)
        pd.testing.assert_frame_equal(hist, original)
        self.assertTrue(any(x["Estado"] == "REVISAR" for x in findings))

    def test_pestana_auditoria_funciona_para_catalogo(self):
        for name, company in L.EMPRESAS.items():
            if not company.get("historico"):
                continue  # sin serie curada: requiere EEFF del usuario
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

    def test_auditoria_contexto_no_calcula_upside_si_moneda_distinta(self):
        audit = L.auditar_contexto_comite_ia({
            "precio_mercado": 100.0, "vps_modelo": 110.0,
            "wacc_calc": 0.10, "ke_calc": 0.12, "roic_calc": None,
            "de_ratio": 0.5, "g": 0.03, "val_ev": 1000.0, "val_equity": 800.0,
            "moneda": "COP", "moneda_precio": "USD",
            "unidad_modelo": "COP miles de millones", "unidad_precio": "por acción",
            "fuente_precio": "test", "fecha_precio": "2026-10-23",
            "fuente_valoracion": "DCF test",
        })
        self.assertIsNone(audit["upside_recalculado"])
        self.assertTrue(any("distintas" in warning.lower() for warning in audit["warnings"]))
        self.assertTrue(any("upside no calculable" in warning.lower() for warning in audit["warnings"]))

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

    def test_historico_sin_ceros_cola_conserva_ingreso_faltante(self):
        historico = pd.DataFrame(
            {"Ingresos": [100.0, None], "EBITDA": [20.0, None]},
            index=[2023, 2024],
        )
        limpio = L._historico_sin_ceros_cola(historico)
        self.assertEqual(len(limpio), 2)
        self.assertTrue(pd.isna(limpio.loc[2024, "Ingresos"]))

    def test_historico_proyectable_excluye_anios_con_componentes_incompletos(self):
        historico = pd.DataFrame({
            "Ingresos": [100.0, 110.0, 120.0],
            "EBITDA": [20.0, None, 24.0],
            "EBIT": [10.0, 11.0, 12.0],
            "CAPEX": [5.0, 5.5, 6.0],
            "NWC": [10.0, 11.0, 12.0],
        }, index=[2022, 2023, 2024])
        limpio = L._filtrar_historico_proyectable(historico)
        self.assertEqual(list(limpio.index), [2022, 2024])
        self.assertTrue(np.isfinite(limpio[["Ingresos", "EBITDA", "EBIT", "CAPEX", "NWC"]].to_numpy()).all())

    def test_obtener_datos_publicos_filtra_historial_runtime_incompleto_sin_fallar(self):
        nombre = "Runtime con año incompleto"
        empresa = {
            "historico": {
                "Año": [2022, 2023, 2024],
                "Ingresos": [100.0, 110.0, 120.0],
                "EBITDA": [20.0, None, 24.0],
                "EBIT": [10.0, 11.0, 12.0],
                "Depreciacion": [10.0, 10.0, 12.0],
                "CAPEX": [5.0, 5.5, 6.0],
                "NWC": [10.0, 11.0, 12.0],
                "Delta_NWC": [1.0, 1.0, 1.0],
                "NOPAT": [None, None, None],
                "FCFF": [None, None, None],
            },
            "ticker_yf": "TEST",
            "fuente": "Yahoo Finance (TEST)",
        }
        with patch.dict(L.EMPRESAS_RUNTIME, {nombre: empresa}):
            with patch.object(L, "resolver_empresa", return_value=empresa):
                historico, mensaje, fuente = L.obtener_datos_financieros_publicos(
                    nombre, preferir_yahoo=False
                )
            self.assertEqual(fuente, "PUBLICA_RUNTIME")
            self.assertEqual(list(historico.index), [2022, 2024])
            self.assertIn("1 año(s) con componentes financieros incompletos omitidos", mensaje)
            self.assertIsNone(L.EMPRESAS_RUNTIME[nombre]["historico"]["FCFF"][0])
        L.EMPRESAS_RUNTIME.pop(nombre, None)

    def test_historico_proyectable_rechaza_columnas_esenciales_ausentes(self):
        historico = pd.DataFrame({"Ingresos": [100.0, 110.0]}, index=[2023, 2024])
        self.assertTrue(L._filtrar_historico_proyectable(historico).empty)

    def test_recalcular_fcff_rechaza_datos_faltantes(self):
        proyeccion = pd.DataFrame({
            "EBIT": [100.0, np.nan],
            "Depreciacion": [10.0, 10.0],
            "CAPEX": [5.0, 5.0],
            "Delta_NWC": [1.0, 1.0],
        })
        with self.assertRaisesRegex(ValueError, "ausentes o no finitos"):
            L.recalcular_fcff(proyeccion, tax=0.30)

    def test_recalcular_fcff_rechaza_tasa_fiscal_invalida(self):
        proyeccion = pd.DataFrame({
            "EBIT": [100.0], "Depreciacion": [10.0],
            "CAPEX": [5.0], "Delta_NWC": [1.0],
        })
        with self.assertRaisesRegex(ValueError, "tasa fiscal"):
            L.recalcular_fcff(proyeccion, tax=1.2)

    def test_normalizador_sectorial_maneja_acentos_y_guiones_unicode(self):
        self.assertEqual(
            L._normalizar_texto_sector("  UTILITÉS—RÉGULÉES   ÉLECTRIQUES "),
            "utilites-regulees electriques",
        )

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


    def test_capital_invertido_yahoo_usa_deuda_patrimonio_menos_efectivo(self):
        balance = pd.DataFrame(
            [[10_000_000_000], [50_000_000_000], [5_000_000_000]],
            index=["Total Debt", "Stockholders Equity", "Cash And Cash Equivalents"],
            columns=["2025-09-27"],
        )
        capital = L.capital_invertido_operativo_yahoo({
            "totalDebt": 10_000_000_000,
            "totalStockholderEquity": 50_000_000_000,
            "totalCash": 5_000_000_000,
            "_balance_sheet": balance,
        })
        self.assertEqual(capital, 55.0)

    def test_capital_invertido_yahoo_no_usa_activos_o_market_cap_como_proxy(self):
        capital = L.capital_invertido_operativo_yahoo({
            "totalAssets": 100_000_000_000,
            "marketCap": 200_000_000_000,
        })
        self.assertIsNone(capital)

    def test_capital_base_roic_falla_si_no_hay_base_valida(self):
        with self.assertRaisesRegex(ValueError, "falta una base de capital"):
            L.capital_base_roic(0.0, 100.0)

    def test_capital_base_roic_no_usa_piso_artificial_de_nopat(self):
        self.assertEqual(L.capital_base_roic(55.0, 100.0), 55.0)



    def test_filtrar_historico_proyectable_acepta_columnas_int64(self):
        historico = pd.DataFrame({
            "Año": [2016, 2017, 2018],
            "Ingresos": pd.Series([7200, 7800, 8400], dtype="int64"),
            "EBITDA": pd.Series([1200, 1300, 1400], dtype="int64"),
            "EBIT": pd.Series([800, 900, 1000], dtype="int64"),
            "CAPEX": pd.Series([300, 320, 340], dtype="int64"),
            "NWC": pd.Series([100, 110, 120], dtype="int64"),
        })
        filtrado = L._filtrar_historico_proyectable(historico)
        self.assertEqual(len(filtrado), 3)
        for columna in ["Ingresos", "EBITDA", "EBIT", "CAPEX", "NWC"]:
            self.assertTrue(pd.api.types.is_float_dtype(filtrado[columna].dtype))
        self.assertEqual(filtrado["Ingresos"].tolist(), [7200.0, 7800.0, 8400.0])



if __name__ == "__main__":
    unittest.main(verbosity=2)
