"""Comité IA v2: hechos con fuente → dictamen JSON validado con anclas de precio objetivo."""
import copy
import datetime as dt
import io
import json
import os
import unittest
from unittest import mock

import comite_ia as CI
import modelacion_logic as L

HOY = dt.date.today()
RECIENTE = (HOY - dt.timedelta(days=20)).isoformat()
VIEJO = (HOY - dt.timedelta(days=900)).isoformat()


def _metricas(**extra):
    m = {
        "empresa": "ISA — Interconexión Eléctrica", "ticker": "ISA.CL", "moneda": "COP", "moneda_precio": "COP",
        "monedas_alineadas": True, "precio_mercado": 29000.0, "vps_modelo": 13423.0, "upside": -53.7,
        "wacc_calc": 0.1396, "ke_calc": 0.1727, "roic_calc": 0.1668, "de_ratio": 1.09, "g": 0.05, "g_usada": 0.05,
        "val_ev": 51510.0, "val_equity": 14873.0, "wacc_implicito_mercado": 0.1088, "wacc_paridad_usd": 0.1252,
        "decision_modelo": "EVITAR / REVISAR", "vetos_calidad": [], "control_calidad_modelo": False,
        "unidad_modelo": "miles de millones de COP", "unidad_precio": "por acción", "fuente_precio": "test",
        "fecha_precio": RECIENTE, "fuente_valoracion": "DCF test", "acciones": 1108.0,
        "fcff_proy": [2108.0, 3311.0, 4604.0, 5963.0, 7359.0], "nopat_final": 7841.0, "ebitda_ultimo_hist": 8186.0,
        "bridge": {"deuda_neta": 30430.0, "caja": 3725.0, "nci": 10539.0, "otros_claims": 0.0, "asociados": 4332.0,
                   "acciones": 1108.0, "exit_multiple": 8.4, "deuda_es_bruta": False},
        "supuestos": {"mid_year": True, "g_max_macro": 0.06},
    }
    m.update(extra)
    return m


def _dictamen_valido(anclas, ids_hechos, **parche):
    lo, hi = anclas["rango"]
    usados = [i for i in ids_hechos][:2]
    d = {
        "analisis_interno": {"resumen": "El WACC del modelo supera en 308 pb al implícito.",
                             "supuestos_fragiles": [{"supuesto": "WACC local", "impacto": "alto"}]},
        "contexto_mercado": {"resumen": "Coyuntura estable.", "hechos_usados": usados},
        "recomendacion": "MANTENER", "precio_objetivo": round((lo + hi) / 2, 2),
        "anclas_usadas": [anclas["anclas"][0]["id"]], "metodo_precio_objetivo": "Ponderación de anclas",
        "conviccion": 6, "tesis": ["Flujos regulados"],
        "riesgos": [{"riesgo": "Tasas", "indicador": "TES"}, {"riesgo": "Regulación", "indicador": "CREG"}],
        "catalizadores": [{"catalizador": "Resultados", "ventana": "3T26"}, {"catalizador": "OPA", "ventana": "2027"}],
        "cambiaria_la_recomendacion": ["WACC < 11 %"],
        "divergencia_motor": {"hay_divergencia": False, "justificacion": ""}, "condicionado_a_recalibrar": False,
    }
    d.update(parche)
    return d


class _Base(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})
        CI._CACHE_HECHOS.clear()

    def tearDown(self):
        L.desvincular_estado_sesion()


class TestUtilidades(_Base):
    def test_extraer_json_tolera_bloques_y_texto(self):
        self.assertEqual(CI._extraer_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(CI._extraer_json('Aquí va: {"a": {"b": "x}"}} fin'), {"a": {"b": "x}"}})
        self.assertEqual(CI._extraer_json('[{"x": 1}]'), [{"x": 1}])
        self.assertIsNone(CI._extraer_json("sin json"))

    def test_depurar_hechos_web(self):
        crudos = [
            {"hecho": "ISA reporta EBITDA 3T26", "fecha": RECIENTE, "fuente": "ISA", "url": "https://www.isa.co/r"},
            {"hecho": "Dato viejo", "fecha": VIEJO, "fuente": "ISA", "url": "https://isa.co/v"},
            {"hecho": "Fuente no consultada", "fecha": RECIENTE, "fuente": "blog", "url": "https://blog.example/x"},
            {"hecho": "Sin fecha", "fecha": "", "url": "https://isa.co/s"},
            {"hecho": "Futuro", "fecha": (HOY + dt.timedelta(days=30)).isoformat(), "url": "https://isa.co/f"},
        ]
        buenos, malos = CI._depurar_hechos_web(crudos, [{"titulo": "isa.co", "url": "https://vertexaisearch.cloud.google.com/x"}])
        self.assertEqual([h["hecho"] for h in buenos], ["ISA reporta EBITDA 3T26"])
        self.assertEqual(buenos[0]["id"], "W1")
        self.assertEqual({h["motivo_descarte"] for h in malos},
                         {f"más de {CI.HECHO_MAX_DIAS} días", "fuente no consultada por la búsqueda", "sin fecha válida", "fecha futura"})


class TestAnclas(_Base):
    def test_anclas_calculadas_por_el_codigo(self):
        L.RESULTADOS_SESION["empresa"] = "ISA — Interconexión Eléctrica"
        L.RESULTADOS_SESION["tabs"] = {
            "2": {"tabla_escenarios": [
                {"Escenario": "Pesimista", "Equity Value": 2000.0}, {"Escenario": "Base", "Equity Value": 14873.0},
                {"Escenario": "Optimista", "Equity Value": 32000.0}]},
            "6": {"multiplos_pares": [
                {"empresa": "ISA", "ev_ebitda": 8.4, "fuente": "Yahoo Finance", "es_focal": True},
                {"empresa": "GEB", "ev_ebitda": 9.0, "fuente": "Yahoo Finance (enterpriseToEbitda o EV/EBITDA)", "es_focal": False},
                {"empresa": "Celsia", "ev_ebitda": 7.0, "fuente": "Aprox. (MarketCap+deuda neta)/EBITDA histórico", "es_focal": False},
                {"empresa": "EPM", "ev_ebitda": 8.0, "fuente": "Fallback sectorial", "es_focal": False}]},
        }
        anc = CI.calcular_anclas("ISA — Interconexión Eléctrica", _metricas(),
                                 {"objetivo_analistas": 31000.0, "n_analistas": 5})
        ids = {a["id"]: a for a in anc["anclas"]}
        # El pesimista (equity 2.000 → 1.805 COP/acción) es < ½ de la mediana: se informa, no amplía el rango.
        self.assertEqual(set(ids), {"A1", "A3", "A4", "A5", "A6", "A7"})
        self.assertEqual([a["id"] for a in anc["descartadas"]], ["A2"])
        self.assertAlmostEqual(ids["A1"]["vps_precio"], 13423.0)
        self.assertAlmostEqual(ids["A3"]["vps_modelo"], 32000.0 * 1000 / 1108.0)
        self.assertEqual(anc["multiplo_pares"], 8.0)  # mediana de 9,0 y 7,0: excluye focal y estimados
        eq_par = 8.0 * 8186.0 - 30430.0 - 10539.0 + 4332.0
        self.assertAlmostEqual(ids["A6"]["vps_modelo"], eq_par * 1000 / 1108.0)
        m = _metricas()
        base = L.valorar_con_bridge(m["fcff_proy"], m["wacc_calc"], m["g"], m["bridge"], g_max_macro=0.06,
                                    nopat_final=m["nopat_final"])["Equity_Value"] * 1000 / 1108.0
        self.assertGreater(ids["A4"]["vps_modelo"], base)  # WACC paridad < WACC local → más valor
        self.assertGreater(ids["A5"]["vps_modelo"], base)  # RONIC > WACC: el crecimiento crea valor
        self.assertEqual(anc["rango"], (min(a["vps_precio"] for a in anc["anclas"]), max(a["vps_precio"] for a in anc["anclas"])))

    def test_pares_de_la_misma_moneda_y_ancla_atipica(self):
        L.RESULTADOS_SESION["empresa"] = "ISA — Interconexión Eléctrica"
        L.RESULTADOS_SESION["tabs"] = {"6": {"multiplos_pares": [
            {"empresa": "GEB", "ev_ebitda": 8.0, "fuente": "Yahoo Finance (enterpriseToEbitda)", "moneda": "COP", "es_focal": False},
            {"empresa": "Celsia", "ev_ebitda": 7.0, "fuente": "Yahoo Finance (enterpriseToEbitda)", "moneda": "COP", "es_focal": False},
            {"empresa": "Duke", "ev_ebitda": 14.0, "fuente": "Yahoo Finance (enterpriseToEbitda)", "moneda": "USD", "es_focal": False},
            {"empresa": "NextEra", "ev_ebitda": 16.0, "fuente": "Yahoo Finance (enterpriseToEbitda)", "moneda": "USD", "es_focal": False}]}}
        mult, pares = CI._multiplos_pares("ISA — Interconexión Eléctrica", "COP")
        self.assertEqual(mult, 7.5)
        self.assertEqual({p["empresa"] for p in pares}, {"GEB", "Celsia"})
        mult_usd, _ = CI._multiplos_pares("ISA — Interconexión Eléctrica", "EUR")  # sin pares en EUR: todos
        self.assertEqual(mult_usd, 11.0)

    def test_anclas_convertidas_a_moneda_de_cotizacion(self):
        m = _metricas(moneda="USD", moneda_precio="COP", vps_modelo=4.0, precio_mercado=19400.0,
                      precio_mercado_moneda_modelo=6.0, fx_aplicado=3233.33, fcff_proy=[], wacc_paridad_usd=None)
        with mock.patch.object(CI, "_multiplos_pares", return_value=(None, [])):
            anc = CI.calcular_anclas("Mineros", m, {})
        self.assertAlmostEqual(anc["anclas"][0]["vps_precio"], 4.0 * 19400.0 / 6.0)


class TestValidacion(_Base):
    def setUp(self):
        super().setUp()
        self.anc = {"anclas": [{"id": "A1", "nombre": "DCF", "metodo": "x", "vps_modelo": 13423.0, "vps_precio": 13423.0},
                               {"id": "A3", "nombre": "Optimista", "metodo": "x", "vps_modelo": 29000.0, "vps_precio": 29000.0}],
                    "rango": (13423.0, 29000.0), "moneda": "COP"}
        self.ids = {"Y1", "Y2", "W1"}

    def test_valido(self):
        a = CI.validar_dictamen(_dictamen_valido(self.anc, self.ids), _metricas(), self.anc, self.ids)
        self.assertTrue(a["ok"], a["errors"])

    def test_errores_detectados(self):
        casos = {
            "fuera del rango": {"precio_objetivo": 50000},
            "anclas inexistentes": {"anclas_usadas": ["A9"]},
            "hechos inexistentes": {"contexto_mercado": {"resumen": "x", "hechos_usados": ["W7"]}},
            "Convicción": {"conviccion": 11},
            "fuera de COMPRAR": {"recomendacion": "COMPRA FUERTE"},
            "2 catalizadores": {"catalizadores": []},
            "contradice": {"recomendacion": "COMPRAR"},
        }
        for esperado, parche in casos.items():
            a = CI.validar_dictamen(_dictamen_valido(self.anc, self.ids, **parche), _metricas(), self.anc, self.ids)
            self.assertFalse(a["ok"], esperado)
            self.assertTrue(any(esperado.lower() in e.lower() for e in a["errors"]), (esperado, a["errors"]))

    def test_veto(self):
        m = _metricas(control_calidad_modelo=True, vetos_calidad=["Equity <= 0"])
        a = CI.validar_dictamen(_dictamen_valido(self.anc, self.ids), m, self.anc, self.ids)
        self.assertFalse(a["ok"])
        a2 = CI.validar_dictamen(_dictamen_valido(self.anc, self.ids, condicionado_a_recalibrar=True), m, self.anc, self.ids)
        self.assertTrue(a2["ok"], a2["errors"])


class TestBancoDeEvaluacion(unittest.TestCase):
    def test_todos_los_veredictos_del_banco(self):
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluacion_comite", "casos.json")
        banco = json.load(open(ruta, encoding="utf-8"))
        self.assertGreaterEqual(len(banco["casos"]), 10)
        for c in banco["casos"]:
            anc = dict(c["anclas"])
            anc["rango"] = tuple(anc["rango"]) if anc["rango"] else None
            ids = {h["id"] for h in c["hechos"]}
            for s in c["salidas"]:
                d = copy.deepcopy(banco["dictamen_base"])
                d.update(s["parche"])
                a = CI.validar_dictamen(d, c["metricas"], anc, ids)
                with self.subTest(caso=c["id"], salida=s["etiqueta"]):
                    self.assertEqual(a["ok"], s["esperado_ok"], a["errors"])
                    if not s["esperado_ok"]:
                        self.assertTrue(any(s["error_contiene"].lower() in e.lower() for e in a["errors"]), a["errors"])


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestEsquemaJSONEnProveedor(_Base):
    def test_gemini_envia_esquema_y_reintenta_sin_el_si_400(self):
        import urllib.error
        cuerpos = []

        def fake_urlopen(req, timeout=None):
            b = json.loads(req.data.decode("utf-8"))
            cuerpos.append(b)
            if "responseSchema" in b["generationConfig"]:
                raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b"schema not supported"))
            return _Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}).encode())

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            out = L._llamar_ia_redaccion("s", "u", api_key="AIza-t", proveedor="gemini", esquema_json=CI.ESQUEMA_DICTAMEN)
        self.assertEqual(out, "{}")
        self.assertEqual(cuerpos[0]["generationConfig"]["responseMimeType"], "application/json")
        self.assertNotIn("responseSchema", cuerpos[1]["generationConfig"])

    def test_openai_pide_json_object(self):
        cuerpos = []

        def fake_urlopen(req, timeout=None):
            cuerpos.append(json.loads(req.data.decode("utf-8")))
            return _Resp(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            L._llamar_ia_redaccion("s", "u", api_key="sk-t", proveedor="openai", esquema_json={"type": "OBJECT"})
        self.assertEqual(cuerpos[0]["response_format"], {"type": "json_object"})


class TestFlujoDosPasos(_Base):
    def _ejecutar(self, llamadas, dictamenes, forzar=False, buscar_web=True):
        hechos_web = json.dumps({"hechos": [
            {"categoria": "resultados", "hecho": "ISA reportó utilidad del 3T26", "valor": "COP 700.000 M",
             "fecha": RECIENTE, "fuente": "ISA", "url": "https://www.isa.co/3t26"},
            {"categoria": "macro", "hecho": "Dato sin respaldo", "fecha": RECIENTE, "fuente": "foro", "url": "https://foro.example/x"},
        ]})

        def fake(sistema, user, **kw):
            llamadas.append(kw)
            if kw.get("buscar_web"):
                L._almacen_estado()["_ia_ultimas_fuentes"] = [{"titulo": "isa.co", "url": "https://vertexaisearch.cloud.google.com/r"}]
                L._almacen_estado()["_ia_busqueda_web"] = {"solicitada": True, "usada": True, "consultas": ["ISA 3T26"]}
                return hechos_web
            return dictamenes.pop(0)

        with mock.patch.object(L, "_llamar_ia_redaccion", fake), \
                mock.patch.object(L, "_metricas_comite_para_ia", lambda _n: {}), \
                mock.patch.object(CI, "_multiplos_pares", return_value=(None, [])):
            return CI.generar_dictamen("ISA — Interconexión Eléctrica", api_key="AIza-t", proveedor="gemini",
                                       metricas=_metricas(), buscar_web=buscar_web, forzar=forzar,
                                       contexto_mercado={"precio": 29000.0, "fecha_precio": RECIENTE, "macro": {"as_of": "2026-10"}})

    def _dictamen_para(self, res_previa=None):
        anc = {"anclas": [{"id": "A1"}], "rango": (13423.0, 13423.0 * 1.6)}
        return json.dumps(_dictamen_valido(anc, ["Y1", "W1"], precio_objetivo=15000.0))

    def test_hechos_con_busqueda_y_dictamen_sin_busqueda_con_esquema(self):
        llamadas = []
        res = self._ejecutar(llamadas, [self._dictamen_para()])
        self.assertTrue(res["ok"], res["error"])
        self.assertTrue(llamadas[0].get("buscar_web"))
        self.assertIsNone(llamadas[0].get("esquema_json"))
        self.assertFalse(llamadas[1].get("buscar_web"))
        self.assertIs(llamadas[1].get("esquema_json"), CI.ESQUEMA_DICTAMEN)
        web = [h for h in res["hechos"] if h["origen"] == "web"]
        self.assertEqual([h["hecho"] for h in web], ["ISA reportó utilidad del 3T26"])
        self.assertEqual(res["descartados"][0]["motivo_descarte"], "fuente no consultada por la búsqueda")
        self.assertIn("https://www.isa.co/3t26", res["html"])
        self.assertIn("MANTENER", res["html"])
        r = L.extraer_resumen_comite_ia(res["markdown"])
        self.assertEqual(r["recomendacion"], "MANTENER")

    def test_cache_historial_y_regenerar(self):
        llamadas = []
        self._ejecutar(llamadas, [self._dictamen_para()])
        n = len(llamadas)
        res2 = self._ejecutar(llamadas, [])
        self.assertTrue(res2["cache"])
        self.assertEqual(len(llamadas), n)  # ni hechos (caché 6 h) ni dictamen (misma clave)
        res3 = self._ejecutar(llamadas, [self._dictamen_para()], forzar=True)
        self.assertFalse(res3["cache"])
        self.assertEqual(len(llamadas), n + 1)  # solo el dictamen
        self.assertEqual(len(CI.historial_comite("ISA — Interconexión Eléctrica")), 2)

    def test_reintento_con_errores_y_rechazo_final(self):
        llamadas = []
        malo = json.dumps(_dictamen_valido({"anclas": [{"id": "A1"}], "rango": (1, 2)}, ["Y1"], precio_objetivo=99999.0))
        res = self._ejecutar(llamadas, [malo, malo])
        self.assertFalse(res["ok"])
        self.assertIn("fuera del rango", " ".join(res["auditoria"]["errors"]))
        self.assertIn("no pasó la auditoría", L._html_a_texto(res["html"]) + "no pasó la auditoría")
        self.assertEqual(len([k for k in llamadas if k.get("esquema_json")]), 2)

    def test_sin_busqueda_solo_hechos_de_la_app(self):
        llamadas = []
        res = self._ejecutar(llamadas, [self._dictamen_para().replace('"W1"', '"Y1"')], buscar_web=False)
        self.assertTrue(res["ok"], res["error"])
        self.assertEqual(len(llamadas), 1)
        self.assertTrue(all(h["origen"] == "app" for h in res["hechos"]))


if __name__ == "__main__":
    unittest.main()


class TestRobustezProduccion(_Base):
    """Fallas vistas con la API real: JSON truncado, timeouts, claves AQ., formatos laxos."""

    def test_normalizar_formas_inocuas(self):
        anc = {"rango": (13423.0, 29000.0)}
        d, notas = CI.normalizar_dictamen({"recomendacion": "Mantener (neutral)", "conviccion": "7/10",
                                           "precio_objetivo": "24.500", "anclas_usadas": "A1, A3",
                                           "contexto_mercado": {"resumen": "x", "hechos_usados": "Y1 y W1"}}, anc)
        self.assertEqual(d["recomendacion"], "MANTENER")
        self.assertEqual(d["conviccion"], 7)
        self.assertEqual(d["precio_objetivo"], 24500.0)
        self.assertEqual(d["anclas_usadas"], ["A1", "A3"])
        self.assertEqual(d["contexto_mercado"]["hechos_usados"], ["Y1", "W1"])
        d2, notas2 = CI.normalizar_dictamen({"precio_objetivo": 24.5}, anc)  # escrito en miles
        self.assertEqual(d2["precio_objetivo"], 24500.0)
        self.assertTrue(notas2)
        d3, _ = CI.normalizar_dictamen({"precio_objetivo": 343.9}, {"rango": (80.0, 400.0)})
        self.assertEqual(d3["precio_objetivo"], 343.9)  # USD: no se toca

    def _gemini(self, respuestas):
        """respuestas: lista de callables(req) -> bytes | excepción, una por intento."""
        enviados = []

        def fake_urlopen(req, timeout=None):
            enviados.append((json.loads(req.data.decode("utf-8")), timeout))
            r = respuestas.pop(0)(req)
            if isinstance(r, Exception):
                raise r
            return _Resp(r)
        return enviados, fake_urlopen

    @staticmethod
    def _ok(texto, finish="STOP"):
        return lambda req: json.dumps({"candidates": [{"content": {"parts": [{"text": texto}]}, "finishReason": finish}]}).encode()

    def test_json_truncado_pasa_al_siguiente_modelo(self):
        enviados, fake = self._gemini([self._ok('{"a": ', "MAX_TOKENS"), self._ok('{"a": 1}')])
        with mock.patch("urllib.request.urlopen", fake):
            out = L._llamar_ia_redaccion("s", "u", api_key="AQ.t", proveedor="gemini", esquema_json={"type": "OBJECT"})
        self.assertEqual(out, '{"a": 1}')
        self.assertEqual(enviados[0][0]["generationConfig"]["maxOutputTokens"], 32768)
        self.assertEqual(enviados[0][1], L.GEMINI_TIMEOUT_LARGO_SEG)
        self.assertEqual(L._almacen_estado()["_ia_diagnostico"][0]["finish"], "MAX_TOKENS")

    def test_timeout_no_detiene_la_cascada(self):
        enviados, fake = self._gemini([lambda r: TimeoutError("timed out"), self._ok("ok")])
        with mock.patch("urllib.request.urlopen", fake):
            out = L._llamar_ia_redaccion("s", "u", api_key="AQ.t", proveedor="gemini")
        self.assertEqual(out, "ok")

    def test_401_en_un_modelo_prueba_los_demas(self):
        import urllib.error
        e401 = lambda req: urllib.error.HTTPError(req.full_url, 401, "u", {}, io.BytesIO(b'{"error":{"status":"UNAUTHENTICATED","details":[{"reason":"ACCESS_TOKEN_TYPE_UNSUPPORTED"}]}}'))
        enviados, fake = self._gemini([e401, self._ok("ok")])
        with mock.patch("urllib.request.urlopen", fake):
            out = L._llamar_ia_redaccion("s", "u", api_key="AQ.t", proveedor="gemini")
        self.assertEqual(out, "ok")

    def test_401_en_todos_los_modelos_explica_la_clave_aq(self):
        import urllib.error
        n = len(L.GEMINI_MODELOS_PREFERIDOS) + 2
        e401 = lambda req: urllib.error.HTTPError(req.full_url, 401, "u", {}, io.BytesIO(b"ACCESS_TOKEN_TYPE_UNSUPPORTED"))
        enviados, fake = self._gemini([e401] * n)
        with mock.patch("urllib.request.urlopen", fake), mock.patch.dict(os.environ, {"GEMINI_MODEL": ""}):
            out = L._llamar_ia_redaccion("s", "u", api_key="AQ.t", proveedor="gemini")
        self.assertIsNone(out)
        self.assertIn("AQ.", L._get_ia_error())

    def test_clave_invalida_se_informa_de_inmediato(self):
        import urllib.error
        e400 = lambda req: urllib.error.HTTPError(req.full_url, 400, "b", {}, io.BytesIO(b"API_KEY_INVALID"))
        enviados, fake = self._gemini([e400])
        with mock.patch("urllib.request.urlopen", fake):
            self.assertIsNone(L._llamar_ia_redaccion("s", "u", api_key="AQ.t", proveedor="gemini"))
        self.assertEqual(len(enviados), 1)
        self.assertIn("no es válida", L._get_ia_error())

    def test_fallo_del_dictamen_muestra_diagnostico(self):
        with mock.patch.object(L, "_llamar_ia_redaccion", lambda *a, **k: None), \
                mock.patch.object(L, "_metricas_comite_para_ia", lambda _n: {}), \
                mock.patch.object(CI, "_multiplos_pares", return_value=(None, [])):
            res = CI.generar_dictamen("ISA — Interconexión Eléctrica", api_key="AQ.t", proveedor="gemini",
                                      metricas=_metricas(), buscar_web=False, contexto_mercado={"precio": 29000.0})
        self.assertFalse(res["ok"])
        self.assertIn("Diagnóstico técnico", res["html"])
