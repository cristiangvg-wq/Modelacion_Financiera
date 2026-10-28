"""Conciliación modelo vs mercado: DCF inverso, causa de la brecha por reglas y su uso en el comité IA."""
import unittest
from unittest import mock

import comite_ia as CI
import modelacion_logic as L

SUP_US = {"rf": 0.05, "erp": 0.0442, "crp": 0.0, "kd": 0.065, "tax": 0.21, "beta_u": 1.0, "mid_year": True, "g_max_macro": 0.04}
SUP_CO = {"rf": 0.1143, "erp": 0.0692, "crp": 0.0, "kd": 0.1418, "tax": 0.219, "beta_u": 0.29, "mid_year": True, "g_max_macro": 0.06}


def _m(sup=SUP_US, moneda="USD", **kw):
    m = {"moneda": moneda, "moneda_precio": moneda, "supuestos": dict(sup), "de_ratio": 0.05, "val_ev": 1000.0,
         "bridge": {"asociados": 0.0}, "g_ingresos_historico": 0.05}
    m.update(kw)
    return m


def _inv(vps, px, wacc, wi=None, k=None, c_px=None, c_mod=0.03):
    return {"precio": px, "vps_modelo": vps, "brecha": vps / px - 1, "wacc": wacc, "g": 0.03,
            "wacc_implicito": wi, "k_flujos": k, "crec10_precio": c_px, "crec10_modelo": c_mod}


class TestClasificacion(unittest.TestCase):
    def _c(self, inv, **kw):
        with mock.patch.object(L, "dcf_inverso", return_value=inv):
            return L.conciliacion_mercado(_m(**kw))

    def test_alineado(self):
        self.assertEqual(self._c(_inv(95, 100, 0.09, 0.087, 1.05, 0.05))["causa"], "ALINEADO")

    def test_isa_supuesto_de_tasa(self):
        c = self._c(_inv(24364, 28080, 0.1303, 0.1227, 1.07, 0.026, 0.016), sup=dict(SUP_CO), moneda="COP", de_ratio=1.0)
        self.assertEqual(c["causa"], "SUPUESTO_TASA")
        self.assertIn("WACC de 12.27%", c["supuesto_que_iguala"])

    def test_apple_prima_de_calidad(self):
        c = self._c(_inv(173.3, 345.9, 0.0956, 0.0615, 2.0, 0.17, 0.06), sup=dict(SUP_US, beta_u=1.03), de_ratio=0.017)
        self.assertEqual(c["causa"], "PRIMA_CALIDAD")
        self.assertEqual(c["tipo"], "prima_calidad")
        self.assertFalse(c["alguna_razonable"])

    def test_palantir_limitacion_crecimiento(self):
        c = self._c(_inv(26.2, 197.6, 0.112, None, 30.0, 0.57), fuera_de_dominio_crecimiento=True)
        self.assertEqual((c["causa"], c["tipo"]), ("LIMITACION_CRECIMIENTO", "limitacion_modelo"))

    def test_geb_participadas(self):
        c = self._c(_inv(1281, 3000, 0.124, None, 2.13, 0.20, 0.086), sup=dict(SUP_CO), moneda="COP",
                    val_ev=30000.0, bridge={"asociados": 16000.0})
        self.assertEqual(c["causa"], "LIMITACION_PARTICIPADAS")

    def test_materia_prima(self):
        c = self._c(_inv(1817, 2715, 0.150, 0.130, 1.20, 0.062), sup=dict(SUP_CO), moneda="COP", emisor_ciclico=True,
                    de_ratio=0.93)
        self.assertEqual(c["causa"], "MATERIA_PRIMA")
        self.assertIn("SUPUESTO_TASA", c["secundarias"])

    def test_mercado_pesimista(self):
        c = self._c(_inv(150, 100, 0.07, 0.11, 0.6, -0.02, 0.04))
        self.assertEqual(c["causa"], "EXPECTATIVA_PESIMISTA")

    def test_beta_sustituida_se_advierte(self):
        c = self._c(_inv(46.9, 91.4, 0.075, 0.0515, 2.0, 0.09), beta_fuente="bottom-up ... (Yahoo sin beta)")
        self.assertTrue(c["advertencias_datos"])


class TestDcfInverso(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})

    def tearDown(self):
        L.desvincular_estado_sesion()

    def test_reproduce_el_precio(self):
        m = {"fcff_proy": [100.0, 105.0, 110.0, 115.0, 120.0], "bridge": {"deuda_neta": 200.0, "acciones": 100.0},
             "acciones": 100.0, "wacc_calc": 0.09, "g_usada": 0.03, "moneda": "USD", "moneda_precio": "USD",
             "supuestos": {"mid_year": True, "g_max_macro": 0.04}, "nopat_final": 140.0}
        v = L.valorar_con_bridge(m["fcff_proy"], 0.09, 0.03, m["bridge"], nopat_final=140.0, g_max_macro=0.04)
        m["vps_modelo"] = float(v["Equity_Value"]) * 1000 / 100
        m["precio_mercado"] = m["vps_modelo"] * 1.3
        inv = L.dcf_inverso(m)
        self.assertLess(inv["wacc_implicito"], 0.09)
        self.assertAlmostEqual(inv["k_flujos"], 1.3 * 1.0, delta=0.15)
        self.assertGreater(inv["crec10_precio"], inv["crec10_modelo"])
        self.assertIsNone(L.dcf_inverso(dict(m, moneda_precio="COP")))  # precio en otra moneda sin FX


class TestComite(unittest.TestCase):
    CONC = {"causa": "LIMITACION_CRECIMIENTO", "tipo": "limitacion_modelo", "descripcion": "x", "secundarias": [],
            "palancas": [{"palanca": "Flujos (× modelo)", "modelo": 1.0, "exigido": 30.0, "razonable": False}],
            "supuesto_que_iguala": "flujos 30 veces", "advertencias_datos": [], "inverso": {"precio": 197.6, "vps_modelo": 26.2, "brecha": -0.87}}

    def _aud(self, rec, opp, expl="El precio exige flujos 30 veces los del modelo: un crecimiento que el DCF no representa.", conc=None):
        m = {"conciliacion_mercado": conc or self.CONC, "vetos_calidad": []}
        d = {"recomendacion": rec, "conciliacion_mercado": {"explicacion": expl, "es_oportunidad": opp}}
        return CI.validar_dictamen(d, m, {"anclas": [], "rango": None}, set())["errors"]

    def test_limitacion_obliga_a_mantener(self):
        self.assertTrue(any("MANTENER" in e for e in self._aud("VENDER", True)))
        self.assertFalse(any("MANTENER" in e and "Causa" in e for e in self._aud("MANTENER", False)))

    def test_comprar_o_vender_exige_oportunidad(self):
        conc = dict(self.CONC, causa="SUPUESTO_TASA", tipo="supuesto_modelo")
        self.assertTrue(any("oportunidad" in e for e in self._aud("COMPRAR", False, conc=conc)))
        self.assertFalse(any("oportunidad" in e for e in self._aud("COMPRAR", True, conc=conc)))

    def test_explicacion_con_cifra_y_sin_cambiar_la_causa(self):
        self.assertTrue(any("cifra" in e for e in self._aud("MANTENER", False, expl="Crece mucho.")))
        otra = "La causa es PRIMA_CALIDAD: el mercado acepta 5 % de rendimiento por la calidad del negocio."
        self.assertTrue(any("cambia la causa" in e for e in self._aud("MANTENER", False, expl=otra)))
        self.assertTrue(any("Falta conciliacion" in e for e in
                            CI.validar_dictamen({"recomendacion": "MANTENER"}, {"conciliacion_mercado": self.CONC},
                                                {"anclas": [], "rango": None}, set())["errors"]))

    def test_prompt_y_html(self):
        texto = CI._texto_conciliacion(self.CONC, "USD")
        self.assertIn("CAUSA PRINCIPAL", texto)
        self.assertIn("NO razonable", texto)
        html = CI._html_conciliacion(self.CONC, {"explicacion": "abc", "es_oportunidad": False}, "USD")
        self.assertIn("Limitación del modelo", html)


if __name__ == "__main__":
    unittest.main()
