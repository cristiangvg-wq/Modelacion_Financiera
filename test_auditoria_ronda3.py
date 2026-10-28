"""Regresiones de la tercera auditoría del comité (28-oct-2026)."""
import unittest
from unittest import mock

import pandas as pd

import modelacion_logic as L


def _proj():
    return pd.DataFrame({"Ingresos": [100.0, 105.0, 110.0, 115.0, 120.0], "EBITDA": [40.0, 42.0, 44.0, 46.0, 48.0],
                         "EBIT": [30.0, 31.5, 33.0, 34.5, 36.0], "Depreciacion": [10.0, 10.5, 11.0, 11.5, 12.0],
                         "CAPEX": [12.0, 12.6, 13.2, 13.8, 14.4], "NWC": [5.0, 5.2, 5.4, 5.6, 5.8],
                         "Delta_NWC": [0.2] * 5, "NOPAT": [22.5, 23.6, 24.8, 25.9, 27.0],
                         "FCFF": [20.3, 21.3, 22.4, 23.4, 24.4]}, index=[2026, 2027, 2028, 2029, 2030])


class TestMatrizSensibilidad(unittest.TestCase):
    def test_sin_columnas_repetidas_por_el_techo_de_g(self):
        m = L.matriz_sensibilidad_wacc_g([20.0, 21.0, 22.0, 23.0, 24.0], 50.0, 0.13, 0.06, g_max_macro=0.06, nopat_final=27.0)
        cols = [c for c in m.columns if c.startswith("g=")]
        self.assertEqual(len(cols), 5)
        fila = m.iloc[2]
        self.assertEqual(len({fila[c] for c in cols}), 5)  # antes g=6,0/6,5/7,0 % daban el mismo EV
        self.assertIn("g=6.0% EV", cols)


class TestEscenarioPesimistaUnico(unittest.TestCase):
    def test_pestanas_4_y_7_usan_los_shocks_de_la_2(self):
        df = _proj()
        fc, nop, eb = L.insumos_escenario(df, "Pesimista", tax=0.25)
        esperado = L.aplicar_shocks_drivers_proyeccion(df, tax=0.25, shock=L.SHOCKS_ESCENARIOS["Pesimista"])
        self.assertEqual(fc, [float(x) for x in esperado["FCFF"].values])
        self.assertAlmostEqual(nop, float(esperado["NOPAT"].iloc[-1]))

    def test_respaldo_si_los_shocks_fallan(self):
        with mock.patch.object(L, "aplicar_shocks_drivers_proyeccion", side_effect=ValueError("x")):
            fc, nop, _ = L.insumos_escenario(_proj(), "Pesimista", tax=0.25)
        self.assertAlmostEqual(fc[0], 20.3 * 0.75)


class TestSensibilidadRapida(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})

    def tearDown(self):
        L.desvincular_estado_sesion()

    def test_no_reutiliza_una_proyeccion_ets_y_entrega_nopat(self):
        L.RESULTADOS_SESION.setdefault("tabs", {})["1"] = {"fcff_proj": [1.0] * 5, "metodo_key": "ets", "horizonte": 5,
                                                            "nopat_final": 9.0}
        with mock.patch.object(L, "cargar_y_limpiar_excel", side_effect=RuntimeError("sin datos")):
            fc, err, nop = L._fcff_desde_sesion_o_hist("X", horizonte=5, con_nopat=True)
        self.assertEqual(fc, [])  # recalcula por drivers en vez de usar los flujos ETS
        L.RESULTADOS_SESION["tabs"]["1"].update({"metodo_key": "drivers"})
        fc, err, nop = L._fcff_desde_sesion_o_hist("X", horizonte=5, con_nopat=True)
        self.assertEqual((fc, nop), ([1.0] * 5, 9.0))


class TestCatalogo(unittest.TestCase):
    def test_g_del_catalogo_alineada_con_el_mercado(self):
        g_co = min(L.CAPM_POR_MERCADO["CO"]["g_lp"], L.CAPM_POR_MERCADO["CO"]["g_max_macro"])
        for nombre in ("ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"):
            p = L.EMPRESAS[nombre]["params"]
            self.assertGreaterEqual(p["g"], g_co - 1e-9, nombre)
            self.assertIn("largo plazo", p["g_fuente"])


class TestProcedencia(unittest.TestCase):
    def test_historico_en_sesion_rotula_la_fuente(self):
        y = L.procedencia_datos("Histórico en sesión (ISA.CL) · Yahoo Finance (ISA.CL), 4 años válidos.")
        self.assertEqual(y["nivel_calidad"], "MEDIA")
        self.assertIn("Yahoo", y["fuente_financiera"])
        x = L.procedencia_datos("Histórico en sesión (X) · Excel/CSV del usuario, 4 años válidos.")
        self.assertEqual(x["nivel_calidad"], "ALTA")


if __name__ == "__main__":
    unittest.main()
