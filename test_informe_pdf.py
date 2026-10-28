"""Informe PDF v3 (pestaña 7): perfil, cifras correctas, escenarios de la pestaña 2 y dictamen del comité."""
import os
import unittest
from unittest import mock

import modelacion_logic as L

try:
    import pypdf
except ImportError:  # pragma: no cover
    pypdf = None

ISA = "ISA — Interconexión Eléctrica"


def _correr(nombre, capturar, antes_del_informe=None):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
    import contraste_mercado_real as C
    C.correr(nombre)
    if antes_del_informe:
        antes_del_informe()
    p = L.params_empresa(nombre)
    rf, erp, crp, gmax = L._capm_para_ui(p)
    with mock.patch.object(L, "generar_pdf_informe", side_effect=capturar) if capturar else mock.patch.object(L, "_fmt_monto", L._fmt_monto):
        return L.tab7_informe_ejecutivo(nombre, None, 5, p["de_ratio"], p["kd"], p["tax"], p["g"], 0.0, p["beta_u"],
                                        p["capital_invertido"], p["deuda_neta"], p.get("inversion_inicial", 0), rf, erp, crp,
                                        True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0),
                                        p.get("acciones"), p.get("exit_multiple", 8.0), True, gmax)


class _Base(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})

    def tearDown(self):
        L.desvincular_estado_sesion()


class TestDatosInforme(_Base):
    def test_contenido_v3(self):
        visto = {}

        def capturar(ruta, nombre, datos):
            visto.update(datos)
            return ruta
        _correr(ISA, capturar)
        self.assertIn("perfil", visto)
        self.assertEqual(visto["perfil"]["pais"], "Colombia")
        self.assertTrue(visto["perfil"]["descripcion"])
        self.assertTrue(any(f[0].startswith("Patrimonio") for f in visto["puente"]))
        self.assertTrue(any("WACC" == f[0] for f in visto["supuestos"]))
        # Escenarios iguales a los de la pestaña 2 (shocks de drivers)
        t2 = {r["Escenario"]: r for r in L.RESULTADOS_SESION["tabs"]["2"]["tabla_escenarios"]}
        pes = [r for r in visto["escenarios_v3"] if r[0] == "Pesimista"][0]
        self.assertEqual(pes[4], L._fmt_monto(t2["Pesimista"]["Equity Value"]))
        self.assertIsNotNone(visto.get("conciliacion"))
        self.assertNotIn("VPN proyecto", str(visto.get("supuestos")))
        self.assertFalse(any("Recuperación del proyecto" in i[0] for i in visto["imagenes"]))

    def test_formato_de_montos(self):
        self.assertEqual(L._fmt_monto(2.374), "2.37")
        self.assertEqual(L._fmt_monto(63168.4), "63,168")
        self.assertEqual(L._fmt_monto(15.26), "15.3")
        self.assertEqual(L._fmt_precio(7.1188), "7.12")
        self.assertEqual(L._fmt_precio(24496.9), "24,497")


@unittest.skipIf(pypdf is None, "pypdf no instalado")
class TestPdf(_Base):
    def test_pdf_completo_con_dictamen(self):
        def dictamen():
            L.guardar_resultado_tab("comite_ia", ISA, {"texto": "x", "struct": {}, "dictamen": {
                "recomendacion": "MANTENER", "precio_objetivo": 26500.0, "conviccion": 6,
                "metodo_precio_objetivo": "50 % DCF base (A1) y 50 % paridad (A4)", "tesis": ["Ingresos regulados"],
                "riesgos": [{"riesgo": "Tasas", "indicador": "TES 10a"}], "catalizadores": [{"catalizador": "Resultados", "ventana": "4T26"}],
                "conciliacion_mercado": {"explicacion": "El precio exige un WACC 270 pb menor.", "es_oportunidad": False}}})
        r = _correr(ISA, None, dictamen)
        self.assertTrue(r[3] and os.path.exists(r[3]))
        texto = "\n".join(pg.extract_text() for pg in pypdf.PdfReader(r[3]).pages)
        for esperado in ("1. La empresa", "Cotiza en", "2. Resumen", "Valor por acción del modelo", "Del valor de la empresa",
                         "4. Rango de valor", "5. Modelo frente al mercado", "7. Datos y fuentes", "9. Dictamen del comité IA",
                         "MANTENER", "26,500", "Ingresos regulados", "TES 10a", "Estado de cada dato", "Deuda neta",
                         "Beta sin deuda"):
            self.assertIn(esperado, texto)
        for prohibido in ("Equity base", "VPN proyecto", "Sin narrativa HTML", "informe HTML"):
            self.assertNotIn(prohibido, texto)


class TestCalidadVariables(_Base):
    """Estado de cada dato crítico (auditoría externa 2026-10-28, sección 2.7)."""

    def test_estados_y_edicion_del_usuario(self):
        p = L.params_empresa(ISA)
        filas = {f[0]: f for f in L.calidad_variables(ISA, {"deuda_neta": p["deuda_neta"], "beta_u": p["beta_u"],
                                                              "rf": 0.11, "erp": 0.07, "crp": 0.0})}
        self.assertIn(filas["Deuda neta"][2], ("OBSERVADO", "CURADO"))
        self.assertTrue(set(f[2] for f in filas.values()) <= set(L.ESTADOS_DATO))
        editado = {f[0]: f for f in L.calidad_variables(ISA, {"deuda_neta": float(p["deuda_neta"]) * 1.2})}
        self.assertEqual(editado["Deuda neta"][2], "USUARIO")
        sin_deuda = {f[0]: f for f in L.calidad_variables(ISA, {"deuda_neta": 0.0, "de_ratio": 1.1})}
        self.assertEqual(sin_deuda["Deuda neta"][2], "FALTANTE")

    def test_crp_en_pesos_avisa_doble_conteo(self):
        filas = {f[0]: f for f in L.calidad_variables(ISA, {"crp": 0.02, "erp": 0.07})}
        self.assertIn("doble conteo", filas["Primas ERP / CRP"][3])

    def test_estado_por_fuente(self):
        self.assertEqual(L._estado_por_fuente("yahoo (ajuste Blume: 0.67·β + 0.33)"), "OBSERVADO")
        self.assertEqual(L._estado_por_fuente("bottom-up Damodaran (sin β)"), "ESTIMADO")
        self.assertEqual(L._estado_por_fuente("catálogo curado (Yahoo sin deuda)"), "CURADO")
        self.assertEqual(L._estado_por_fuente("hoja Parámetros del archivo"), "USUARIO")
        self.assertEqual(L._estado_por_fuente("estatutaria_CO"), "ESTIMADO")


if __name__ == "__main__":
    unittest.main()
