"""Tasas de mercado automáticas, correcciones del histórico, Excel en formato ancho y suma de partes."""
import datetime as dt
import io
import unittest
from unittest import mock

import pandas as pd

import comite_ia as CI
import modelacion_logic as L

REF = {"co_rf_bruto": {"valor": 0.1318, "fecha": "2026-10-16", "fuente": "BanRep"},
       "us_rf": {"valor": 0.05, "fecha": "2026-10-27", "fuente": "Treasury"}}


class TestTasas(unittest.TestCase):
    def test_gana_el_dato_mas_reciente(self):
        viejo = {"co_rf_bruto": {"valor": 0.1273, "fecha": "2026-09-15"}, "us_rf": {"valor": 0.048, "fecha": "2026-11-02"}}
        t = L.tasas_vigentes(archivo=viejo, referencias=REF)
        self.assertEqual(t["co_rf_bruto"]["valor"], 0.1318)        # el promedio mensual OCDE es más viejo
        self.assertEqual(t["us_rf"]["valor"], 0.048)              # el dato diario de FRED es más nuevo
        self.assertEqual(t["us_rf"]["origen"], "datos_mercado.json")

    def test_valores_absurdos_se_ignoran(self):
        t = L.tasas_vigentes(archivo={"us_rf": {"valor": 4.8, "fecha": "2030-01-01"}}, referencias=REF)
        self.assertEqual(t["us_rf"]["valor"], 0.05)

    def test_aviso_de_vigencia(self):
        av = L.tasas_vigencia(hoy=dt.date(2027, 3, 1), tasas={"us_rf": {"valor": 0.05, "fecha": "2026-10-27"}})
        self.assertTrue(av and "Tesoro" in av[0])
        self.assertEqual(L.tasas_vigencia(hoy=dt.date(2026, 11, 1), tasas={"us_rf": {"valor": 0.05, "fecha": "2026-10-27"}}), [])

    def test_lectores_tesoro_y_ocde(self):
        import scripts.actualizar_tasas as A
        tes = 'Date,"1 Mo","10 Yr","30 Yr"\n10/27/2026,3.9,4.99,5.4\n10/26/2026,3.9,4.97,5.4\n'
        self.assertEqual(A.ultimo_tesoro(tes), ("2026-10-27", 0.0499))
        real = 'Date,"5 YR","10 YR"\n10/27/2026,2.37,2.64\n'
        self.assertEqual(A.ultimo_tesoro(real), ("2026-10-27", 0.0264))
        oc = "TIME_PERIOD,OBS_VALUE\n2026-08,12.18\n2026-09,12.73\n2026-01,12.73\n"
        self.assertEqual(A.ultimo_ocde(oc), ("2026-09-15", 0.1273))

    def test_capm_usa_las_tasas_vigentes(self):
        self.assertEqual(L.CAPM_POR_MERCADO["CO"]["rf_bruto"], round(L.TASAS_MERCADO["co_rf_bruto"]["valor"], 4))
        self.assertEqual(L.INFLACION_LP["US"], round(L.TASAS_MERCADO["us_inflacion_lp"]["valor"], 4))


class _Sesion(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})

    def tearDown(self):
        L.desvincular_estado_sesion()


HIST = pd.DataFrame({"Ingresos": [14134.0, 14935.0, 15918.0], "EBITDA": [8336.0, 9062.0, 7956.0],
                     "EBIT": [7068.0, 8034.0, 6876.0], "Depreciacion": [1268.0, 1027.0, 1080.0],
                     "CAPEX": [4632.0, 1578.0, 1706.0], "NWC": [4388.0, 5566.0, 5840.0]}, index=[2023, 2024, 2025])


class TestHistoricoUsuario(_Sesion):
    def test_correccion_del_capex_cambia_el_fcff_y_se_rotula(self):
        ed = HIST.copy()
        ed.loc[2025, "CAPEX"] = 6300.0
        cambios = L.fijar_historico_usuario("ISA — Interconexión Eléctrica", ed.reset_index().rename(columns={"index": "Año"}),
                                            HIST, fuente_original="Yahoo Finance (ISA.CL)")
        self.assertEqual(cambios, ["CAPEX 2025: 1,706.0 → 6,300.0"])
        df, msg = L.cargar_y_limpiar_excel(None, "ISA — Interconexión Eléctrica", True)
        self.assertEqual(float(df.loc[2025, "CAPEX"]), 6300.0)
        tax = float(L.params_empresa("ISA — Interconexión Eléctrica")["tax"])
        self.assertAlmostEqual(float(df.loc[2025, "FCFF"]), 6876 * (1 - tax) + 1080 - 6300 - (5840 - 5566), places=4)
        self.assertIn("corregido por el usuario", msg)
        pr = L.procedencia_datos(msg)
        self.assertIn("Correcciones del usuario", pr["fuente_financiera"])
        self.assertNotEqual(L.firma_ajustes_usuario("ISA — Interconexión Eléctrica"), L.firma_ajustes_usuario("GEB — Grupo Energía Bogotá"))
        L.borrar_historico_usuario("ISA — Interconexión Eléctrica")
        _, msg2 = L.cargar_y_limpiar_excel(None, "ISA — Interconexión Eléctrica", True)
        self.assertNotIn("corregido por el usuario", msg2)

    def test_validaciones(self):
        malo = HIST.copy()
        malo.loc[2025, "Ingresos"] = -1
        with self.assertRaises(ValueError):
            L.fijar_historico_usuario("X", malo, HIST)
        with self.assertRaises(ValueError):
            L.fijar_historico_usuario("X", HIST.iloc[:2], HIST)


class TestExcelOficial(unittest.TestCase):
    def test_formato_ancho_se_transpone(self):
        raw = pd.DataFrame({"Partida": ["Ingresos", "EBITDA", "EBIT", "CAPEX", "Capital de trabajo"],
                            "2023": [14134, 8336, 7068, 4632, 4388], "2024": [14935, 9062, 8034, 1578, 5566],
                            "2025": [15918, 7956, 6876, 6300, 5840]})
        t, ok = L._normalizar_formato_ancho(raw)
        self.assertTrue(ok)
        self.assertEqual(list(t["Año"]), [2023, 2024, 2025])
        self.assertIn("Ingresos", t.columns)
        self.assertFalse(L._normalizar_formato_ancho(t)[1])

    def test_unidades_en_millones_se_convierten(self):
        clean = HIST * 1000.0
        with mock.patch.object(L, "resolver_empresa", return_value={"historico": {"Año": [2023, 2024, 2025],
                                                                                    "Ingresos": [14134.0, 14935.0, 15918.0]}}):
            fac, txt = L._escala_respecto_referencia(clean, "ISA")
        self.assertEqual(fac, 1e-3)
        self.assertIn("millones", txt)


class TestSumaDePartes(unittest.TestCase):
    def test_metodos(self):
        ke = 0.14
        self.assertAlmostEqual(L.valorar_participada({"metodo": "capitalizada", "utilidad": 3200, "participacion": 42.5}, ke)[0],
                               3200 * 0.425 / 0.14)
        con_g = L.valorar_participada({"metodo": "capitalizada", "utilidad": 100, "participacion": 100, "roe": 20, "g": 6}, ke)[0]
        self.assertAlmostEqual(con_g, 100 * (1 - 0.06 / 0.20) / (0.14 - 0.06))
        self.assertAlmostEqual(L.valorar_participada({"metodo": "pu", "utilidad": 100, "participacion": 50, "pu": 9}, ke)[0], 450)
        self.assertAlmostEqual(L.valorar_participada({"metodo": "dividendos", "dividendo": 80, "g": 6}, ke)[0], 80 * 1.06 / 0.08)
        self.assertAlmostEqual(L.valorar_participada({"metodo": "mercado", "valor": 10000, "participacion": 15.24}, ke)[0], 1524)
        self.assertIsNone(L.valorar_participada({"metodo": "pu", "utilidad": 100}, ke)[0])
        r = L.suma_de_partes([{"participada": "A", "metodo": "libros", "valor": 10}, {"participada": "B", "metodo": "pu"},
                              {"participada": ""}], ke)
        self.assertEqual((r["total"], len(r["errores"])), (10, 1))

    def test_sugeridas_para_geb(self):
        filas = L.participadas_sugeridas("GEB — Grupo Energía Bogotá", {"ingreso_participadas": 2280.0})
        self.assertEqual(filas[0]["participada"], "Enel Colombia")
        self.assertAlmostEqual(filas[1]["utilidad"], 2280 - 3200 * 0.425, places=1)
        self.assertEqual(L.participadas_sugeridas("X", {"asociados": 50.0})[0]["metodo"], "libros")


class TestConciliacionConSumaDePartes(unittest.TestCase):
    def test_participadas_valoradas_no_son_limitacion(self):
        inv = {"precio": 3000, "vps_modelo": 1281, "brecha": -0.57, "wacc": 0.124, "g": 0.06, "wacc_implicito": None,
               "k_flujos": 2.1, "crec10_precio": 0.20, "crec10_modelo": 0.086}
        base = {"moneda": "COP", "moneda_precio": "COP", "val_ev": 30000.0, "bridge": {"asociados": 16000.0},
                "supuestos": {"rf": 0.1143}}
        with mock.patch.object(L, "dcf_inverso", return_value=inv):
            self.assertEqual(L.conciliacion_mercado(base)["causa"], "LIMITACION_PARTICIPADAS")
            c = L.conciliacion_mercado(dict(base, participadas_valoradas=True))
        self.assertNotEqual(c["causa"], "LIMITACION_PARTICIPADAS")
        self.assertTrue(any("suma de partes" in x for x in c["advertencias_datos"]))


if __name__ == "__main__":
    unittest.main()
