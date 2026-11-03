"""Pestaña 10 con el motor de las pestañas 2–7.

El escenario Base del taller debe ser idéntico a la valoración de la pestaña 4 con los mismos insumos, y los
escenarios deben usar los mismos choques de WACC y g que la pestaña 2.
"""
import copy
import json
import unittest

import modelacion_logic as L
from scripts import taller_isa as T

ISA = "ISA — Interconexión Eléctrica"


class TestMotorUnificado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(T.DEFAULT_DATA.read_text(encoding="utf-8"))
        cls.isa = T.load_isa(cls.data)
        cls.r = T.calcular_modelo(cls.data, 200)

    def test_instantanea_en_modo_modelo(self):
        self.assertTrue(T.modo_app(self.isa))
        self.assertEqual(self.data["valoracion"]["motor"], "modelo_app")
        self.assertIn("proyeccion_base", self.data)

    def test_base_reproduce_la_proyeccion_de_la_app(self):
        pb = self.data["proyeccion_base"]
        rows = [x for x in self.r["evals"]["Base"]["rows"] if not x["terminal"]]
        for k_app, k_t in (("Ingresos", "ingresos"), ("EBIT", "ebit"), ("CAPEX", "capex"),
                           ("Delta_NWC", "delta_nwc"), ("FCFF", "fcff")):
            for a, b in zip(pb[k_app], [x[k_t] for x in rows]):
                self.assertAlmostEqual(a, b, places=6, msg=k_app)

    def test_base_igual_a_la_valoracion_de_la_pestana_4(self):
        """Mismo cálculo que tab4_recomendacion: valorar_con_bridge con la proyección, puente y fechas."""
        d, c = self.data, self.r["capital"]
        pb = d["proyeccion_base"]
        bp = L.params_bridge_desde_ui(d["puente"]["deuda_neta"], 0.0, d["puente"]["nci"], d["puente"]["otros_claims"],
                                      d["puente"]["asociados"], d["puente"]["acciones"], 0.0)
        bp.update(frac_transcurrida=d["fechas"]["frac_transcurrida"], t_valoracion=d["fechas"]["t_valoracion"])
        spread = T.ronic_spread(self.isa, c["wacc"])
        v = L.valoracion_dcf(pb["FCFF"], c["wacc"], d["capital"]["g_terminal"], deuda_neta=bp["deuda_neta"],
                             nci=bp["nci"], asociados=bp["asociados"], acciones=bp["acciones"], mid_year=True,
                             g_max_macro=d["valoracion"]["g_max_macro"], nopat_final=pb["NOPAT"][-1],
                             ronic_spread=spread, frac_transcurrida=bp["frac_transcurrida"],
                             t_valoracion=bp["t_valoracion"])
        self.assertAlmostEqual(self.r["evals"]["Base"]["valuation"]["valor_por_accion"], v["value_per_share"], places=6)

    def test_wacc_de_escenarios_como_la_pestana_2(self):
        w = {x["escenario"]: x["wacc"] for x in self.r["summary"]}
        self.assertAlmostEqual(w["Pesimista"] - w["Base"], 0.015, places=9)
        self.assertAlmostEqual(w["Base"] - w["Optimista"], 0.010, places=9)

    def test_coherencia_mas_crecimiento_mas_capex_y_nwc(self):
        base = T.evaluate(self.isa, "Base")["rows"]
        mas = T.evaluate(self.isa, "Base", overrides={"growth": T.historical_drivers(self.isa)["growth"] + 0.02})["rows"]
        self.assertGreater(mas[0]["capex_expansion"], base[0]["capex_expansion"])
        self.assertGreater(mas[0]["delta_nwc"], base[0]["delta_nwc"])

    def test_politicas_sobre_la_base_de_la_app(self):
        rows = T.project(self.isa, T.scenario_params(self.isa, "Base"), "P1 Diferir CAPEX de expansión")
        base = T.project(self.isa, T.scenario_params(self.isa, "Base"))
        tot = lambda rr: sum(x["capex_expansion"] for x in rr if not x["terminal"])
        self.assertLess(rows[0]["capex"], base[0]["capex"])
        self.assertEqual(rows[0]["capex_mantenimiento"], base[0]["capex_mantenimiento"])
        self.assertGreater(tot(base), 0)
        for p in T.POLICIES:
            self.assertIn(p, self.r["recommendations"])

    def test_tir_implicita_iguala_ev_de_mercado(self):
        e = self.r["evals"]["Base"]
        ev_r = T.value(self.isa, e["rows"], e["tir_implicita"], e["params"]["g_terminal"])["ev"]
        self.assertAlmostEqual(ev_r, T.market_ev(self.isa), delta=1.0)

    def test_huella_no_depende_de_campos_derivados(self):
        self.assertNotIn("_base_app", self.r["inputs"])
        self.assertEqual(T.inputs_fingerprint(self.isa), T.inputs_fingerprint(T.load_isa(copy.deepcopy(self.data))))

    def test_builder_de_la_app_coincide_con_la_instantanea(self):
        if L.resolver_precio_mercado(ISA) is not None:
            self.skipTest("Con datos de Yahoo en vivo la app usa otra serie; la instantánea congela los datos del catálogo")
        p = dict(L.params_empresa(ISA))
        rf, erp, crp, gmax = L._capm_para_ui(p)
        d = L.datos_taller_modelo(ISA, tax=p["tax"], g=p["g"], de_ratio=p["de_ratio"], kd=p["kd"], beta_u=p["beta_u"],
                                  rf=rf, erp=erp, crp=crp, deuda_neta=p["deuda_neta"], caja=p.get("caja") or 0.0,
                                  nci=p.get("nci") or 0.0, asociados=p.get("asociados") or 0.0,
                                  acciones=p.get("acciones"), g_max_macro=gmax)
        for a, b in zip(d["proyeccion_base"]["FCFF"], self.data["proyeccion_base"]["FCFF"]):
            self.assertAlmostEqual(a, b, places=6)


if __name__ == "__main__":
    unittest.main()
