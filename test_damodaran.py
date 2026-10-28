"""Integración de las tablas de Damodaran (datos_damodaran.json)."""
import json
import os
import unittest
from unittest import mock

import comite_ia as CI
import modelacion_logic as L

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos_damodaran.json")


@unittest.skipUnless(L.DAMODARAN, "sin datos_damodaran.json")
class TestDatosDamodaran(unittest.TestCase):
    def test_archivo_versionado_y_completo(self):
        d = json.load(open(RUTA, encoding="utf-8"))
        meta = d["riesgo_pais"]["meta"]
        self.assertTrue(0.03 < meta["erp_madura"] < 0.08)
        self.assertTrue(1.0 < meta["multiplicador_volatilidad"] < 2.5)
        self.assertEqual(set(d["multiplos"]), {"US", "Emergentes", "Global"})
        # Validado contra la página pública de Damodaran (EE. UU., enero 2026): Power 12,38x; Utility (General) 13,73x
        us = d["multiplos"]["US"]["industrias"]
        self.assertAlmostEqual(us["Power"]["ev_ebitda"], 12.38, places=2)
        self.assertAlmostEqual(us["Utility (General)"]["ev_ebitda"], 13.73, places=2)

    def test_riesgo_pais_colombia_consistente(self):
        co = L.damodaran_riesgo_pais("CO")
        self.assertEqual(co["pais"], "Colombia")
        self.assertAlmostEqual(co["erp_total"], co["erp_madura"] + co["crp"], places=6)
        self.assertAlmostEqual(co["crp"], co["spread"] * co["multiplicador"], places=6)
        self.assertIsNone(L.damodaran_riesgo_pais("XX"))

    def test_erp_de_eeuu_desde_damodaran(self):
        self.assertAlmostEqual(L.CAPM_POR_MERCADO["US"]["erp"], round(L.damodaran_riesgo_pais("US")["erp_us"], 4))

    def test_colombia_metodo_damodaran_en_pesos(self):
        co, dam = L.CAPM_POR_MERCADO["CO"], L.damodaran_riesgo_pais("CO")
        self.assertAlmostEqual(co["rf"], round(co["rf_bruto"] - dam["spread"], 4))   # TES − spread de default
        self.assertAlmostEqual(co["erp"], round(dam["erp_total"], 4))                # madura + riesgo país
        self.assertEqual(co["crp"], 0.0)                                              # sin doble conteo
        isa = L.EMPRESAS["ISA — Interconexión Eléctrica"]["params"]
        self.assertAlmostEqual(isa["kd"], round(co["rf_bruto"] + 0.01, 4))            # Kd sobre el TES completo

    def test_wacc_paridad_usa_primas_de_damodaran(self):
        wp = L.wacc_paridad_usd(0.42, 1.09, 0.22)
        co = L.damodaran_riesgo_pais("CO")
        bl = L.beta_apalancado(0.42, 1.09, 0.22)
        self.assertAlmostEqual(wp["ke_usd"], L.CAPM_POR_MERCADO["US"]["rf"] + bl * co["erp_madura"] + co["crp"], places=9)
        self.assertIn("Damodaran", wp["fuente"])

    def test_mapeo_de_industrias(self):
        casos = {("Utilities", "Utilities - Regulated Electric"): "Power",
                 ("Basic Materials", "Gold"): "Precious Metals",
                 ("Energy", "Oil & Gas Integrated"): "Oil/Gas (Integrated)",
                 ("Technology", "Consumer Electronics"): "Computers/Peripherals",
                 ("Technology", "Software - Infrastructure"): "Software (System & Application)",
                 ("Financial Services", "Banks - Regional"): None,
                 ("Servicios financieros", "Bolsa de valores"): None}
        for (sec, ind), esperado in casos.items():
            self.assertEqual(L.industria_damodaran(sec, ind), esperado, (sec, ind))
        self.assertEqual(L.industria_damodaran("x", "y", explicita="Power"), "Power")

    def test_region_por_pais_del_emisor(self):
        self.assertEqual(L.damodaran_multiplo("Utilities", "Utilities - Regulated Electric", "CO")["region"], "Emergentes")
        self.assertEqual(L.damodaran_multiplo("Technology", "Consumer Electronics", "US")["region"], "US")
        self.assertEqual(L.damodaran_multiplo("Utilities", "Utilities - Regulated Electric", "DE")["region"], "Global")
        self.assertIsNone(L.damodaran_multiplo("Financial Services", "Banks - Regional", "US"))

    def test_catalogo_isa_usa_power_emergentes(self):
        dm = L.damodaran_empresa("ISA — Interconexión Eléctrica")["multiplo"]
        self.assertEqual((dm["industria"], dm["region"]), ("Power", "Emergentes"))

    def test_vigencia(self):
        self.assertFalse(L.damodaran_vigencia(L.datetime(2026, 11, 1))["vencido"])
        v = L.damodaran_vigencia(L.datetime(2027, 4, 1))
        self.assertTrue(v["vencido"])
        self.assertIn("actualizar_damodaran", v["aviso"])

    def test_ancla_a8_en_el_comite(self):
        m = {"vps_modelo": 13423.0, "acciones": 1108.0, "moneda": "COP", "moneda_precio": "COP",
             "ebitda_ultimo_hist": 8186.0, "bridge": {"deuda_neta": 30430.0, "nci": 10539.0, "asociados": 4332.0},
             "damodaran_multiplo": {"industria": "Power", "region": "Emergentes", "ev_ebitda": 7.0, "n_firmas": 328, "fecha": "2026-01-05"}}
        with mock.patch.object(CI, "_multiplos_pares", return_value=(None, [])):
            anc = CI.calcular_anclas("ISA — Interconexión Eléctrica", m, {})
        a8 = next(a for a in anc["anclas"] + anc.get("descartadas", []) if a["id"] == "A8")
        self.assertAlmostEqual(a8["vps_modelo"], (7.0 * 8186.0 - 30430.0 - 10539.0 + 4332.0) * 1000 / 1108.0)
        self.assertIn("Damodaran", a8["nombre"])

    def test_actualizador_lee_los_archivos(self):
        import importlib.util
        ruta = os.path.join(os.path.dirname(RUTA), "scripts", "actualizar_damodaran.py")
        spec = importlib.util.spec_from_file_location("act_dam", ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.construir))


if __name__ == "__main__":
    unittest.main()
