"""Pruebas de las correcciones de la fase 2 (auditoría del 3-nov-2026).

Cada prueba fija un hallazgo de la auditoría con un cálculo independiente:
C-01 trazabilidad, C-03 fecha de valoración, C-04 convergencia de margen, C-05 puente de múltiplos,
M-01 WACC optimista, M-05 escala de acciones y el modelo del taller (pestaña 10) con supuestos editables.
"""
import copy
import json
import math
import unittest
from datetime import date

import numpy as np
import pandas as pd

import modelacion_logic as L
from multiples_valuation import valoracion_por_multiplos
from scripts import taller_isa as T

ISA = "ISA — Interconexión Eléctrica"


class TestFechaValoracion(unittest.TestCase):
    """C-03: los flujos parten del cierre, el puente es posterior y el valor se expresa a la fecha del precio."""

    F = [100.0, 110.0, 120.0, 130.0, 140.0]

    def test_por_defecto_igual_al_metodo_anterior(self):
        v = L.valoracion_dcf(self.F, 0.10, 0.03, mid_year=False)
        pv = sum(x / 1.1 ** (i + 1) for i, x in enumerate(self.F)) + 140 * 1.03 / 0.07 / 1.1 ** 5
        self.assertAlmostEqual(v["EV"], pv, places=6)

    def test_calculo_independiente_mitad_de_anio(self):
        s0, tv, w = 0.5, 0.8, 0.10
        v = L.valoracion_dcf(self.F, w, 0.03, mid_year=True, frac_transcurrida=s0, t_valoracion=tv)
        tiempos = [s0 + (1 - s0) / 2] + [i + 0.5 for i in range(1, 5)]
        flujos = [self.F[0] * (1 - s0)] + self.F[1:]
        pv = sum(f / (1 + w) ** (t - tv) for f, t in zip(flujos, tiempos))
        pv += 140 * 1.03 / (w - 0.03) / (1 + w) ** (4.5 - tv)
        self.assertAlmostEqual(v["EV"], pv, places=6)

    def test_solo_correr_la_fecha_capitaliza_al_wacc(self):
        a = L.valoracion_dcf(self.F, 0.10, 0.03, mid_year=False)
        b = L.valoracion_dcf(self.F, 0.10, 0.03, mid_year=False, t_valoracion=0.5)
        self.assertAlmostEqual(b["EV"] / a["EV"], 1.1 ** 0.5, places=9)

    def test_puente_lleva_las_fechas(self):
        bp = L.params_bridge_desde_ui(100, 0, 0, 0, 0, 10, 0)
        bp.update(frac_transcurrida=0.5, t_valoracion=0.8)
        v1 = L.valorar_con_bridge(self.F, 0.1, 0.03, bp)
        v2 = L.valoracion_dcf(self.F, 0.1, 0.03, deuda_neta=100, acciones=10, frac_transcurrida=0.5, t_valoracion=0.8)
        self.assertAlmostEqual(v1["EV"], v2["EV"], places=9)

    def test_rechaza_fechas_invalidas(self):
        with self.assertRaises(ValueError):
            L.valoracion_dcf(self.F, 0.1, 0.03, frac_transcurrida=1.2)

    def test_calendario_isa(self):
        cal = L.calendario_valoracion(ISA, hoy=date(2026, 10, 29))
        self.assertEqual(cal["fecha_cierre"], "2025-12-31")
        self.assertEqual(cal["fecha_balance"], "2026-06-30")
        self.assertAlmostEqual(cal["frac_transcurrida"], round(181 / 365.25, 4))
        self.assertAlmostEqual(cal["t_valoracion"], round(302 / 365.25, 4))

    def test_calendario_puente_anterior_al_cierre(self):
        cal = L.calendario_valoracion(params={"fecha_cierre_fiscal": "2025-12-31", "fecha_balance": "2025-06-30"},
                                      hoy=date(2026, 3, 1))
        self.assertEqual(cal["frac_transcurrida"], 0.0)
        self.assertIn("anterior al cierre", cal["nota"])


class TestTrazabilidad(unittest.TestCase):
    """C-01: sin fuente no hay «OBSERVADO»; un supuesto del catálogo es ESTIMADO."""

    def test_sin_fuente(self):
        self.assertEqual(L._estado_por_fuente(None), "SIN FUENTE")
        self.assertEqual(L._estado_por_fuente("N/D"), "SIN FUENTE")

    def test_supuesto_y_provisional(self):
        self.assertEqual(L._estado_por_fuente("supuesto del catálogo curado — estado: provisional_no_validado"), "ESTIMADO")
        self.assertEqual(L._estado_por_fuente("catálogo curado: Informe consolidado ISA 2T26"), "CURADO")
        self.assertEqual(L._estado_por_fuente("yahoo: totalDebt − totalCash"), "OBSERVADO")

    def test_catalogo_declara_su_procedencia(self):
        p = L.EMPRESAS[ISA]["params"]
        self.assertTrue(p["deuda_fuente"].startswith("catálogo curado"))
        self.assertIn("provisional", p["tax_fuente"])


class TestMultiplos(unittest.TestCase):
    """C-05: el patrimonio por múltiplos usa el mismo puente que el DCF."""

    def test_puente_completo(self):
        r = valoracion_por_multiplos(1000.0, [7.0, 8.0, 9.0], deuda_neta=3000.0, acciones_millones=100.0,
                                     nci=1000.0, asociados=500.0)
        self.assertAlmostEqual(r["equity_value"], 8000 - 3000 - 1000 + 500)
        self.assertAlmostEqual(r["valor_por_accion"], 4500 * 1000 / 100)

    def test_compatible_sin_nci(self):
        r = valoracion_por_multiplos(1000.0, [8.0], deuda_neta=3000.0)
        self.assertAlmostEqual(r["equity_value"], 5000.0)

    def test_patrimonio_negativo_vale_cero_por_accion(self):
        r = valoracion_por_multiplos(100.0, [5.0], deuda_neta=1000.0, acciones_millones=10.0)
        self.assertEqual(r["valor_por_accion"], 0.0)
        self.assertLess(r["equity_value"], 0)


class TestCorreccionesPuntuales(unittest.TestCase):
    def test_wacc_optimista_nunca_supera_al_base(self):
        for w in (0.05, 0.055, 0.065, 0.09, 0.138):
            self.assertLessEqual(L.wacc_optimista(w, 0.02), w)
        self.assertAlmostEqual(L.wacc_optimista(0.10, 0.03), 0.09)

    def test_acciones_en_unidades(self):
        self.assertAlmostEqual(L.resolver_acciones_millones(None, None, {"sharesOutstanding": 500_000}), 0.5)
        self.assertAlmostEqual(L.resolver_acciones_millones(None, None, {"sharesOutstanding": 1_107_700_000}), 1107.7)

    def test_margen_converge_gradualmente(self):
        df = pd.DataFrame({"Ingresos": [100.0, 105.0, 110.0], "EBITDA": [60.0, 63.0, 50.0], "EBIT": [50.0, 52.0, 40.0],
                           "Depreciacion": [10.0, 11.0, 10.0], "CAPEX": [12.0, 12.0, 13.0], "NWC": [10.0, 11.0, 12.0]},
                          index=pd.Index([2023, 2024, 2025], name="Año"))
        proj, meta = L.proyectar_por_drivers(df, 5, tax=0.3)
        m = (proj["EBITDA"] / proj["Ingresos"]).tolist()
        self.assertEqual(meta["anios_convergencia_margen"], 3)
        self.assertLess(m[0], m[1])
        self.assertLess(m[1], m[2])
        self.assertAlmostEqual(m[2], m[4], places=9)
        self.assertGreater(m[0], 50.0 / 110.0)


class TestTallerPestana10(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(T.DEFAULT_DATA.read_text(encoding="utf-8"))

    def test_fechas_en_la_instantanea(self):
        f = self.data["fechas"]
        self.assertEqual((f["fecha_cierre"], f["fecha_balance"]), ("2025-12-31", "2026-06-30"))

    def test_valor_con_fechas_es_calculo_independiente(self):
        isa = T.load_isa(self.data)
        e = T.evaluate(isa, "Base")
        s0, tv = T.valuation_timing(isa)
        w, g = e["params"]["wacc"], e["params"]["g_terminal"]
        exp = [r for r in e["rows"] if not r["terminal"]]
        if isa["capital"].get("mid_year"):
            pv = exp[0]["fcff"] * (1 - s0) / (1 + w) ** (s0 + (1 - s0) / 2 - tv)
            pv += sum(r["fcff"] / (1 + w) ** (i + 0.5 - tv) for i, r in enumerate(exp) if i > 0)
            pv += e["rows"][-1]["fcff"] / (w - g) / (1 + w) ** (len(exp) - 0.5 - tv)
        else:  # instantánea: flujos a fin de año
            pv = exp[0]["fcff"] * (1 - s0) / (1 + w) ** (1 - tv)
            pv += sum(r["fcff"] / (1 + w) ** (i + 1 - tv) for i, r in enumerate(exp) if i > 0)
            pv += e["rows"][-1]["fcff"] / (w - g) / (1 + w) ** (len(exp) - tv)
        self.assertAlmostEqual(e["valuation"]["ev"], pv, places=6)

    def test_supuestos_editables_cambian_resultado_y_regla(self):
        base = T.calcular_modelo(self.data, 200)
        d2 = copy.deepcopy(self.data)
        d2["config"] = {"escenarios": {"Base": {"ebit_margin_delta": 0.02}},
                        "politicas": {"P1 Diferir CAPEX de expansión": {"defer_share": 0.25}},
                        "umbrales": {"covenant_deuda_neta_ebitda": 4.5}}
        r = T.calcular_modelo(d2, 200)
        vb = base["evals"]["Base"]["valuation"]["valor_por_accion"]
        self.assertGreater(r["evals"]["Base"]["valuation"]["valor_por_accion"], vb)
        self.assertIn("25 %", r["metadata"]["politicas"]["P1 Diferir CAPEX de expansión"]["regla"])
        self.assertEqual(r["metadata"]["umbrales_decision"]["covenant_deuda_neta_ebitda"], 4.5)
        # Los valores por defecto del módulo no cambian (sin estado compartido entre usuarios).
        self.assertEqual(T.POLICIES["P1 Diferir CAPEX de expansión"]["defer_share"], 0.40)
        self.assertEqual(T.DECISION_THRESHOLDS["covenant_deuda_neta_ebitda"], 4.0)

    def test_requisitos_del_taller(self):
        r = T.calcular_modelo(self.data, 200)
        esc = r["metadata"]["escenarios"]
        for s in ("Pesimista", "Base", "Optimista"):
            self.assertIn(s, esc)
        drivers = [k for k in esc["Base"] if k != "descripcion"]
        self.assertGreaterEqual(len(drivers), 5)                         # matriz de ≥ 5 drivers
        self.assertGreaterEqual(len(r["metadata"]["politicas"]), 2)       # ≥ 2 políticas
        for rec in r["recommendations"].values():                         # recomendación condicionada
            self.assertRegex(rec["decision"], "Adoptar|Condicionar|Descartar")
        for s in r["summary"]:                                            # VPN y TIR por escenario
            self.assertIn("vpn_inversionista", s)
            self.assertIn("tir_implicita", s)
        self.assertGreaterEqual(len(r["tornado"]), 5)                     # sensibilidad
        self.assertGreaterEqual(len(r["metadata"]["tecnicas"]), 3)        # técnicas nombradas
        self.assertTrue(T.ROOT.joinpath("docs", "ingenieria_prompts_taller_isa.md").exists())

    def test_valor_por_accion_no_negativo(self):
        r = T.calcular_modelo(self.data, 200)
        for s in r["summary"]:
            self.assertGreaterEqual(s["valor_por_accion"], 0.0)


if __name__ == "__main__":
    unittest.main()
