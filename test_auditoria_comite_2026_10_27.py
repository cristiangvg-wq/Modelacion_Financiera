"""Regresiones de la auditoría del comité (27-oct-2026).

Cubre: CAPM coherente con la moneda de los flujos, g terminal de largo plazo,
tasa fiscal de perpetuidad, proyección a ciclo medio de emisores de materias
primas, puente verificado de Ecopetrol, comité IA con contexto de mercado
(COMPRAR/MANTENER/VENDER) y búsqueda web de Gemini.
"""
import io
import json
import unittest
from unittest import mock

import pandas as pd

import modelacion_logic as L


def _df_hist(ingresos, margen_ebitda=0.40, margen_ebit=0.30, capex=0.10, nwc=0.05, inicio=2022):
    años = list(range(inicio, inicio + len(ingresos)))
    ing = pd.Series(ingresos, index=años, dtype=float)
    df = pd.DataFrame({
        "Ingresos": ing,
        "EBITDA": ing * margen_ebitda,
        "EBIT": ing * margen_ebit,
        "Depreciacion": ing * (margen_ebitda - margen_ebit),
        "CAPEX": ing * capex,
        "NWC": ing * nwc,
    })
    df.index.name = "Año"
    return df


class TestCapmMonedaFlujos(unittest.TestCase):
    def test_emisor_colombiano_con_flujos_usd_usa_ust_mas_riesgo_pais(self):
        c = L.capm_coherente_con_moneda("Colombia", "USD", "MINEROS.CL")
        self.assertEqual(c["mercado"], "US")
        self.assertAlmostEqual(c["rf"], L.CAPM_POR_MERCADO["US"]["rf"])
        self.assertAlmostEqual(c["crp_deuda"], L.RIESGO_PAIS_CDS["CO"])
        self.assertAlmostEqual(c["crp"], round(L.MULT_CRP_EQUITY * L.RIESGO_PAIS_CDS["CO"], 4))
        self.assertTrue(c["cruce_moneda"])

    def test_flujos_en_moneda_local_no_duplican_riesgo_pais(self):
        c = L.capm_coherente_con_moneda("Colombia", "COP", "ISA.CL")
        self.assertEqual(c["mercado"], "CO")
        self.assertEqual(c["crp"], 0.0)
        self.assertFalse(c["cruce_moneda"])

    def test_derivar_params_mineros_no_descuenta_usd_con_tes(self):
        info = {"country": "Colombia", "currency": "COP", "financialCurrency": "USD",
                "regularMarketPrice": 19400, "marketCap": 5.7424e12, "sharesOutstanding": 296e6,
                "totalDebt": 55.6e6, "totalCash": 41.1e6, "beta": 0.75}
        p = L.derivar_params_desde_cero(_df_hist([0.44, 0.45, 0.54, 0.80]), info=info, ticker_yf="MINEROS.CL")
        self.assertEqual(p["mercado_capm"], "US")
        self.assertLess(p["rf"], 0.08)
        self.assertGreater(p["crp"], 0.0)
        self.assertLess(p["kd"], L.CAPM_POR_MERCADO["CO"]["rf"])
        self.assertLessEqual(p["g"], L.CAPM_POR_MERCADO["US"]["g_max_macro"])


class TestCrecimientoYTasaPerpetuidad(unittest.TestCase):
    def test_g_terminal_es_el_nominal_de_largo_plazo_no_el_cagr(self):
        info = {"country": "United States", "currency": "USD", "financialCurrency": "USD",
                "regularMarketPrice": 100.0, "marketCap": 1e12, "sharesOutstanding": 1e10,
                "totalDebt": 1e10, "totalCash": 5e9, "beta": 1.1, "effectiveTaxRate": 0.16}
        p = L.derivar_params_desde_cero(_df_hist([394, 383, 391, 416]), info=info, ticker_yf="AAPL")
        self.assertAlmostEqual(p["g"], L.CAPM_POR_MERCADO["US"]["g_lp"])
        self.assertLess(p["g_cagr_historico"], p["g"])

    def test_tasa_efectiva_transitoria_no_se_perpetua(self):
        info = {"country": "United States", "currency": "USD", "financialCurrency": "USD",
                "regularMarketPrice": 200.0, "marketCap": 4.8e11, "sharesOutstanding": 2.4e9,
                "totalDebt": 2.4e8, "totalCash": 7.2e9, "beta": 2.6, "effectiveTaxRate": 0.044}
        p = L.derivar_params_desde_cero(_df_hist([1.9, 2.2, 2.9, 4.5]), info=info, ticker_yf="PLTR")
        self.assertAlmostEqual(p["tax"], 0.21)
        self.assertAlmostEqual(p["tax_efectiva_observada"], 0.044)

    def test_tasa_efectiva_normal_se_respeta(self):
        info = {"country": "United States", "currency": "USD", "financialCurrency": "USD",
                "regularMarketPrice": 100.0, "marketCap": 1e12, "sharesOutstanding": 1e10,
                "totalDebt": 1e10, "totalCash": 5e9, "beta": 1.1, "effectiveTaxRate": 0.16}
        p = L.derivar_params_desde_cero(_df_hist([394, 383, 391, 416]), info=info, ticker_yf="AAPL")
        self.assertAlmostEqual(p["tax"], 0.16)


class TestCicloMedioMateriasPrimas(unittest.TestCase):
    def test_sector_ciclico_detectado_sin_falsos_positivos(self):
        self.assertTrue(L.es_sector_ciclico("Petróleo, gas y energía"))
        self.assertTrue(L.es_sector_ciclico("Basic Materials", "Gold"))
        self.assertTrue(L.es_sector_ciclico("Energy", "Oil & Gas Integrated"))
        self.assertFalse(L.es_sector_ciclico("Transmisión y distribución de energía / Gas"))
        self.assertFalse(L.es_sector_ciclico("Transmisión de energía / Infraestructura"))
        self.assertFalse(L.es_sector_ciclico("Technology", "Consumer Electronics"))

    def test_caida_de_precios_no_se_extrapola_en_emisor_ciclico(self):
        df = _df_hist([159.6, 143.2, 133.3, 119.7])
        df.attrs["g_convergencia"] = 0.06
        _, meta_normal = L.proyectar_por_drivers(df.copy(), 5, tax=0.35)
        self.assertLess(meta_normal["g_ingresos"], 0)
        df.attrs["ciclico"] = True
        proj, meta = L.proyectar_por_drivers(df, 5, tax=0.35)
        self.assertTrue(meta["ciclico"])
        self.assertAlmostEqual(meta["g_ingresos"], 0.06)
        self.assertGreater(float(proj["Ingresos"].iloc[0]), 119.7)

    def test_hipercrecimiento_se_marca_fuera_de_dominio(self):
        _, meta = L.proyectar_por_drivers(_df_hist([1.9, 2.2, 2.9, 4.5]), 5, tax=0.21)
        self.assertTrue(meta["fuera_de_dominio_crecimiento"])
        _, meta2 = L.proyectar_por_drivers(_df_hist([394, 383, 391, 416]), 5, tax=0.16)
        self.assertFalse(meta2["fuera_de_dominio_crecimiento"])

    def test_ecopetrol_es_ciclico_e_isa_no(self):
        self.assertTrue(L.empresa_es_ciclica("ECOPETROL"))
        self.assertFalse(L.empresa_es_ciclica("ISA — Interconexión Eléctrica"))


class TestPuenteEcopetrolVerificado(unittest.TestCase):
    def test_nci_y_asociadas_no_son_valores_de_relleno(self):
        p = L.EMPRESAS["ECOPETROL"]["params"]
        # EEFF consolidados 30-jun-2025: NCI 26.356; asociadas 8.913; deuda neta 110.141 (miles de millones COP)
        self.assertGreater(p["nci"], 20000)
        self.assertGreater(p["asociados"], 5000)
        self.assertGreater(p["deuda_neta"], 100000)


class TestParidadUSD(unittest.TestCase):
    def test_wacc_paridad_menor_que_wacc_local_con_tes_alto(self):
        wp = L.wacc_paridad_usd(0.42, 1.09, 0.22)
        bl = L.beta_apalancado(0.42, 1.09, 0.22)
        ke_local = L.costo_equity_capm(bl, rf=L.CAPM_POR_MERCADO["CO"]["rf"], erp=L.CAPM_POR_MERCADO["CO"]["erp"])
        w_local, _, _ = L.calcular_wacc(1.09, L.CAPM_POR_MERCADO["CO"]["rf"] + 0.01, ke_local, 0.22)
        self.assertIsNotNone(wp)
        self.assertLess(wp["wacc_local_fisher"], w_local)
        self.assertGreater(wp["wacc_local_fisher"], wp["wacc_usd"])


SALIDA_NUEVA = """## 1. ANÁLISIS INTERNO DEL MODELO
El WACC del modelo supera en 300 pb al implícito en el precio.
## 2. CONTEXTO DE MERCADO REAL
Instantánea verificada sin eventos adicionales.
## 3. RECOMENDACIÓN DE INVERSIÓN
- RECOMENDACIÓN FINAL: MANTENER
- PRECIO OBJETIVO 12 MESES: 30.500 COP (DCF con WACC por paridad)
- PUNTAJE DE CONVICCIÓN: 6/10
- TESIS DE INVERSIÓN: flujo regulado indexado.
## 4. RIESGOS, CATALIZADORES Y PUNTOS DE MONITOREO
1. Riesgo: TES 10 años por encima de 13 %.
2. Catalizador: resultados 3T26.
"""


class TestAuditorComiteNuevoFormato(unittest.TestCase):
    def test_acepta_formato_nuevo_con_vocabulario_comprar_mantener_vender(self):
        a = L.auditar_respuesta_comite_ia(SALIDA_NUEVA, {"precio_mercado": 29000, "decision_modelo": "NEUTRAL / MONITOREAR"})
        self.assertTrue(a["ok"], a["errors"])
        self.assertFalse(any("Falta sección" in w for w in a["warnings"]), a["warnings"])
        self.assertFalse(any("Precio objetivo" in w for w in a["warnings"]), a["warnings"])

    def test_comprar_con_veto_se_rechaza(self):
        salida = SALIDA_NUEVA.replace("MANTENER", "COMPRAR")
        a = L.auditar_respuesta_comite_ia(salida, {"control_calidad_modelo": True, "vetos_calidad": ["Equity <= 0"]})
        self.assertFalse(a["ok"])

    def test_comprar_contra_motor_prudente_exige_divergencia(self):
        salida = SALIDA_NUEVA.replace("MANTENER", "COMPRAR")
        a = L.auditar_respuesta_comite_ia(salida, {"decision_modelo": "EVITAR / REVISAR"})
        self.assertFalse(a["ok"])
        a2 = L.auditar_respuesta_comite_ia(
            salida + "\nDIVERGENCIA FRENTE AL MOTOR CUANTITATIVO: WACC local sobreestimado.",
            {"decision_modelo": "EVITAR / REVISAR"})
        self.assertTrue(a2["ok"], a2["errors"])

    def test_precio_objetivo_fuera_de_escala_genera_advertencia(self):
        salida = SALIDA_NUEVA.replace("30.500 COP", "305 COP")
        a = L.auditar_respuesta_comite_ia(salida, {"precio_mercado": 29000})
        self.assertTrue(any("Precio objetivo" in w for w in a["warnings"]))

    def test_resumen_extrae_recomendacion_y_conviccion(self):
        r = L.extraer_resumen_comite_ia(SALIDA_NUEVA)
        self.assertEqual(r["recomendacion"], "MANTENER")
        self.assertTrue(str(r["puntaje"]).startswith("6"))

    def test_numero_es_en(self):
        self.assertEqual(L._numero_texto_es_en("30.500"), 30500.0)
        self.assertEqual(L._numero_texto_es_en("29,000.5"), 29000.5)
        self.assertEqual(L._numero_texto_es_en("29.000,5"), 29000.5)
        self.assertEqual(L._numero_texto_es_en("343.91"), 343.91)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestGeminiBusquedaWeb(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})

    def tearDown(self):
        L.desvincular_estado_sesion()

    def test_busqueda_web_envia_herramienta_y_extrae_fuentes(self):
        enviados = []
        respuesta = {"candidates": [{
            "content": {"parts": [{"text": "Informe"}]},
            "groundingMetadata": {
                "webSearchQueries": ["ISA resultados 3T26"],
                "groundingChunks": [{"web": {"uri": "https://isa.co/x", "title": "ISA 3T26"}},
                                    {"web": {"uri": "https://isa.co/x", "title": "duplicado"}}],
            },
        }]}

        def fake_urlopen(req, timeout=None):
            enviados.append(json.loads(req.data.decode("utf-8")))
            return _Resp(json.dumps(respuesta).encode("utf-8"))

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            txt = L._llamar_ia_redaccion("s", "u", api_key="AIza-test", proveedor="gemini", buscar_web=True)
        self.assertEqual(txt, "Informe")
        self.assertEqual(enviados[0].get("tools"), [{"google_search": {}}])
        self.assertEqual(L.fuentes_ultima_ia(), [{"titulo": "ISA 3T26", "url": "https://isa.co/x"}])

    def test_modelo_sin_soporte_de_busqueda_reintenta_sin_herramienta(self):
        import urllib.error
        llamadas = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            llamadas.append("tools" in body)
            if "tools" in body:
                raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b"Tool not supported"))
            return _Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode("utf-8"))

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            txt = L._llamar_ia_redaccion("s", "u", api_key="AIza-test", proveedor="gemini", buscar_web=True)
        self.assertEqual(txt, "OK")
        self.assertEqual(llamadas[:2], [True, False])

    def test_sin_busqueda_no_envia_herramienta(self):
        enviados = []

        def fake_urlopen(req, timeout=None):
            enviados.append(json.loads(req.data.decode("utf-8")))
            return _Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode("utf-8"))

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            L._llamar_ia_redaccion("s", "u", api_key="AIza-test", proveedor="gemini")
        self.assertNotIn("tools", enviados[0])


# El comité completo (dos pasos, JSON, anclas) se prueba en test_comite_ia_v2.py.


if __name__ == "__main__":
    unittest.main()
