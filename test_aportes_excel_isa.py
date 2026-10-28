"""Aportes del modelo del curso (ISA_M4_Grupo_06): WACC al estilo Damodaran, EBITDA normalizado,
ajuste por país del múltiplo de Damodaran y retorno explícito de la nueva inversión (RONIC)."""
import unittest
from unittest import mock

import pandas as pd

import comite_ia as CI
import modelacion_logic as L


class _Sesion(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})

    def tearDown(self):
        L.desvincular_estado_sesion()


class TestRonicExplicito(_Sesion):
    ARGS = ([100.0] * 5, 0.09, 0.03)

    def test_modo_roic_converge_a_la_mitad_del_exceso(self):
        L.fijar_roic_referencia("X", 0.25)
        v = L.valoracion_dcf(*self.ARGS, nopat_final=120.0)
        self.assertAlmostEqual(v["ronic"], 0.09 + 0.5 * (0.25 - 0.09), places=9)
        self.assertAlmostEqual(v["reinversion_terminal"], 0.03 / v["ronic"], places=9)

    def test_roic_bajo_el_wacc_no_destruye_valor_en_perpetuidad(self):
        L.fijar_roic_referencia("X", 0.05)
        self.assertAlmostEqual(L.valoracion_dcf(*self.ARGS, nopat_final=120.0)["ronic"], 0.09, places=9)

    def test_modo_wacc_y_manual(self):
        L.fijar_roic_referencia("X", 0.25)
        L.fijar_modo_ronic("wacc")
        self.assertAlmostEqual(L.valoracion_dcf(*self.ARGS, nopat_final=120.0)["ronic"], 0.09, places=9)
        L.fijar_ronic_spread(0.04)
        self.assertEqual(L.modo_ronic_sesion(), "manual")
        self.assertAlmostEqual(L.valoracion_dcf(*self.ARGS, nopat_final=120.0)["ronic"], 0.13, places=9)
        L.fijar_ronic_spread(None)
        self.assertEqual(L.modo_ronic_sesion(), "roic")
        with self.assertRaises(ValueError):
            L.fijar_modo_ronic("otro")

    def test_spread_con_techo(self):
        L.fijar_roic_referencia("X", 3.0 - 1e-9)
        self.assertAlmostEqual(L.ronic_spread_sesion(0.09), L.RONIC_SPREAD_MAX)

    def test_roic_observado(self):
        df = pd.DataFrame({"NOPAT": [10.0, 12.0, 14.0, 13.0]}, index=[2022, 2023, 2024, 2025])
        self.assertAlmostEqual(L.roic_observado(df, 100.0), 0.13)
        self.assertIsNone(L.roic_observado(df, 0))
        self.assertIsNone(L.roic_observado(df.drop(columns="NOPAT"), 100.0))

    def test_el_cargador_fija_el_roic_de_la_empresa(self):
        df, _ = L.cargar_y_limpiar_excel(None, "ISA — Interconexión Eléctrica", True)
        self.assertIsNotNone(df.attrs.get("roic_observado"))
        self.assertAlmostEqual(L.roic_referencia_sesion(), df.attrs["roic_observado"])

    def test_ancla_a5_es_la_alternativa_al_caso_base(self):
        base = {"vps_modelo": 100.0, "acciones": 10.0, "moneda": "USD", "moneda_precio": "USD", "g": 0.03,
                "wacc_calc": 0.09, "fcff_proy": [100.0] * 5, "nopat_final": 120.0, "bridge": {},
                "damodaran_multiplo": False, "roic_observado": 0.25}
        with mock.patch.object(CI, "_multiplos_pares", return_value=(None, [])):
            a = CI.calcular_anclas("X", dict(base, ronic_terminal=0.17), {})
            b = CI.calcular_anclas("X", dict(base, ronic_terminal=0.09), {})
        nombre = lambda anc: next(x["nombre"] for x in anc["anclas"] + anc.get("descartadas", []) if x["id"] == "A5")
        self.assertIn("conservador", nombre(a))
        self.assertIn("RONIC > WACC", nombre(b))


class TestEbitdaNormalizado(unittest.TestCase):
    def test_margen_representativo_por_tamano_actual(self):
        ing = [13356.0, 14134.0, 14935.0, 15918.0]
        df = pd.DataFrame({"Ingresos": ing, "EBITDA": [7767.0, 8129.0, 8897.0, 7922.0],
                           "EBIT": [6761.0, 7070.0, 7870.0, 6842.0], "Depreciacion": [1006.0, 1060.0, 1027.0, 1080.0],
                           "CAPEX": [1833.0, 2051.0, 1578.0, 1706.0], "NWC": [5040.0, 4100.0, 4009.0, 4354.0]},
                          index=[2022, 2023, 2024, 2025])
        _, meta = L.proyectar_por_drivers(df, 5, tax=0.35)
        self.assertAlmostEqual(meta["ebitda_normalizado"], 15918.0 * meta["margen_ebitda"], places=6)
        self.assertGreater(meta["ebitda_normalizado"], 7922.0)  # no el de un año de margen atípico
        self.assertIn("margen EBITDA representativo", meta["ebitda_normalizado_metodo"])

    def test_anclas_de_multiplos_usan_el_normalizado(self):
        m = {"vps_modelo": 100.0, "acciones": 1000.0, "moneda": "COP", "moneda_precio": "COP",
             "ebitda_ultimo_hist": 50.0, "ebitda_normalizado": 80.0, "bridge": {},
             "damodaran_multiplo": {"industria": "Power", "region": "Emergentes", "ev_ebitda": 2.0,
                                    "n_firmas": 1, "fecha": "2026-01-05"}}
        with mock.patch.object(CI, "_multiplos_pares", return_value=(None, [])):
            anc = CI.calcular_anclas("X", m, {})
        a8 = next(a for a in anc["anclas"] + anc.get("descartadas", []) if a["id"] == "A8")
        self.assertAlmostEqual(a8["vps_modelo"], 2.0 * 80.0 * 1000 / 1000.0)


@unittest.skipUnless(L.DAMODARAN.get("ajuste_pais"), "sin ajuste por país en datos_damodaran.json")
class TestAjusteColombia(unittest.TestCase):
    def test_multiplo_emergente_ajustado_a_la_bvc(self):
        aj = L.DAMODARAN["ajuste_pais"]["CO"]
        self.assertAlmostEqual(aj["descuento"], round(1 - aj["mediana_local"] / aj["referencia_emergentes"], 4), places=3)
        dm = L.damodaran_multiplo("Utilities", "Utilities - Regulated Electric", "CO")
        self.assertAlmostEqual(dm["ev_ebitda"], dm["ev_ebitda_industria"] * (1 - aj["descuento"]))
        self.assertEqual(dm["ajuste_pais"]["n"], aj["n"])

    def test_sin_ajuste_fuera_de_colombia(self):
        dm = L.damodaran_multiplo("Technology", "Consumer Electronics", "US")
        self.assertIsNone(dm["ajuste_pais"])
        self.assertEqual(dm["ev_ebitda"], dm["ev_ebitda_industria"])


if __name__ == "__main__":
    unittest.main()
