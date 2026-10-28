"""Pruebas de la auditoría integral (protocolo de validación post-cambios).

Corren 100 % offline: el conector de mercado y la API de Gemini se simulan, de
modo que validan la LÓGICA (sufijo .CL, normalización monetaria, consistencia
entre pestañas y purga de estado), no cotizaciones reales. Para el contraste con
el mercado real usar `scripts/contraste_mercado_real.py` con acceso a Yahoo.
"""
from __future__ import annotations

import copy
import json
import sys
import threading
import types
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import modelacion_logic as L
import portfolio_engine as PE


# ---------------------------------------------------------------------------
# Mercado simulado: precio + moneda declarada por "Yahoo" para cada ticker
# ---------------------------------------------------------------------------
PRECIOS_SIM = {
    "ISA.CL": (25_000.0, "COP"),
    "ECOPETROL.CL": (2_400.0, "COP"),
    "GEB.CL": (3_000.0, "COP"),
    "NUTRESA.CL": (80_000.0, "COP"),
    "AAPL": (260.0, "USD"),
    "PLTR": (180.0, "USD"),
}
LLAMADAS_MERCADO = []


def _mercado_simulado(ticker_yf, ticker_bvc=None, proveedor=None):
    tk = L.asegurar_sufijo_cl_bvc(ticker_yf or ticker_bvc)
    LLAMADAS_MERCADO.append(tk)
    if tk not in PRECIOS_SIM:
        return L._respuesta_mercado_vacia(f"sin dato {tk}", proveedor="yahoo")
    px, cur = PRECIOS_SIM[tk]
    return {
        "ok": True, "precio": px, "moneda": cur, "cambio_pct": 0.4, "market_cap": None,
        "beta": None, "pe": None, "enterprise_to_ebitda": None, "proveedor": "yahoo",
        "fuente": f"yahoo:{tk}", "fecha_precio": "2026-10-26", "ticker": tk,
    }


def _registrar_runtime(nombre, ticker_yf, moneda, base_catalogo, acciones):
    """Simula una empresa ingresada por el usuario (misma forma que buscar_y_descargar_empresa)."""
    emp = copy.deepcopy(L._EMPRESAS_CATALOGO_INMUTABLE[base_catalogo])
    p = emp["params"]
    p.update({"moneda": moneda, "moneda_precio": moneda, "precio_moneda": moneda,
              "currency": moneda, "acciones": acciones})
    L.EMPRESAS_RUNTIME[nombre] = {
        "ticker_bvc": ticker_yf[:-3] if ticker_yf.endswith(".CL") else None,
        "ticker_yf": ticker_yf, "sector": emp["sector"], "descripcion": "simulada",
        "params": p, "historico": emp["historico"], "peers": [],
        "fuente": f"Yahoo Finance ({ticker_yf})", "moneda": moneda, "moneda_precio": moneda,
        "pais": "Colombia" if ticker_yf.endswith(".CL") else "United States",
    }


PREDEFINIDAS = ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"]
USUARIO = [
    ("Grupo Nutresa — NUTRESA", "NUTRESA.CL", "COP", "CELSIA — Celsia S.A. E.S.P.", 457.0),
    ("Apple Inc. — AAPL", "AAPL", "USD", "BVC — Bolsa de Valores de Colombia", 14_800.0),
    ("Palantir Technologies — PLTR", "PLTR", "USD", "BVC — Bolsa de Valores de Colombia", 2_360.0),
]


def _args_empresa(nombre):
    p = L.params_empresa(nombre)
    return dict(
        horizonte=5, de_ratio=p["de_ratio"], kd=p["kd"], tax=p["tax"], g=p["g"],
        capex_extra=0.0, beta_u=p["beta_u"], capital_invertido=p["capital_invertido"],
        deuda_neta=p["deuda_neta"], caja=p.get("caja", 0), nci=p.get("nci", 0),
        otros_claims=p.get("otros_claims", 0), asociados=p.get("asociados", 0),
        acciones=p.get("acciones"), exit_multiple=p.get("exit_multiple", 8.0),
        inversion_inicial=p.get("inversion_inicial", 0),
    )


def _correr_pestanas(nombre):
    a = _args_empresa(nombre)
    rf, erp = (0.12, 0.055) if L.moneda_empresa(nombre) == "COP" else (0.045, 0.05)
    L.tab2_simulacion_politicas(
        nombre, None, a["horizonte"], a["de_ratio"], a["kd"], a["tax"], a["g"], a["capex_extra"],
        a["beta_u"], a["deuda_neta"], rf, erp, 0.0, True, a["caja"], a["nci"], a["otros_claims"],
        a["asociados"], a["acciones"], a["exit_multiple"], True, 0.05,
    )
    L.tab4_recomendacion(
        nombre, None, a["horizonte"], a["de_ratio"], a["kd"], a["tax"], a["g"], a["capex_extra"],
        a["beta_u"], a["capital_invertido"], a["deuda_neta"], rf, erp, 0.0, True, a["caja"], a["nci"],
        a["otros_claims"], a["asociados"], a["acciones"], a["exit_multiple"], True, 0.05,
    )
    L.tab7_informe_ejecutivo(
        nombre, None, a["horizonte"], a["de_ratio"], a["kd"], a["tax"], a["g"], a["capex_extra"],
        a["beta_u"], a["capital_invertido"], a["deuda_neta"], a["inversion_inicial"], rf, erp, 0.0,
        True, a["caja"], a["nci"], a["otros_claims"], a["asociados"], a["acciones"],
        a["exit_multiple"], True, 0.05,
    )
    tabs = L.RESULTADOS_SESION["tabs"]
    return {k: (tabs.get(k) or {}).get("metricas") for k in ("2", "4", "7")}


class BaseOffline(unittest.TestCase):
    def setUp(self):
        self.almacen = {}
        L.vincular_estado_sesion(self.almacen)
        L.limpiar_cache_mercado()
        LLAMADAS_MERCADO.clear()
        self._p = mock.patch.object(L, "_obtener_datos_mercado_sin_cache", side_effect=_mercado_simulado)
        self._p.start()
        self._yf = mock.patch.object(L, "HAS_YF", False)
        self._yf.start()

    def tearDown(self):
        self._p.stop()
        self._yf.stop()
        L.limpiar_cache_mercado()
        L.desvincular_estado_sesion()


# ---------------------------------------------------------------------------
# 1. Sufijo .CL estrictamente condicional a la BVC
# ---------------------------------------------------------------------------
class TestSufijoCL(BaseOffline):
    def test_catalogo_bvc_recibe_cl(self):
        for t in ("ECOPETROL", "PFAVAL", "BCOLOMBIA", "NUTRESA", "isa", " geb ", "PFCIBEST"):
            self.assertEqual(L.asegurar_sufijo_cl_bvc(t), t.strip().upper() + ".CL", t)

    def test_internacionales_intactos(self):
        for t in ("AAPL", "MSFT", "TSLA", "PLTR", "EC", "CIB", "AVAL", "BRK-B", "SAN.MC", "VOD.L"):
            self.assertEqual(L.asegurar_sufijo_cl_bvc(t), t, t)
        self.assertEqual(L.asegurar_sufijo_cl_bvc("AAPL.CL"), "AAPL")

    def test_descarga_runtime_no_contamina_tickers_internacionales(self):
        """Regresión: tras descargar ZETA (USD) la normalización la convertía en ZETA.CL."""
        L.EMPRESAS_RUNTIME["Zeta Global — ZETA"] = {"ticker_yf": "ZETA", "ticker_bvc": None, "params": {}}
        self.assertNotIn("ZETA", L._tickers_bvc_conocidos())
        self.assertEqual(L.asegurar_sufijo_cl_bvc("ZETA"), "ZETA")
        L.EMPRESAS_RUNTIME["Mineros — MINEROSX"] = {"ticker_yf": "MINEROSX.CL", "ticker_bvc": "MINEROSX", "params": {}}
        self.assertEqual(L.asegurar_sufijo_cl_bvc("MINEROSX"), "MINEROSX.CL")

    def test_candidatos_y_validacion_cop(self):
        self.assertEqual(L.candidatos_ticker_yf("nutresa"), ["NUTRESA.CL"])
        self.assertEqual(L.candidatos_ticker_yf("aapl"), ["AAPL"])
        self.assertEqual(L.candidatos_ticker_yf("XYZW"), ["XYZW", "XYZW.CL"])
        self.assertFalse(L._es_candidato_bvc_valido("XYZW.CL", {"currency": "USD"}))
        self.assertTrue(L._es_candidato_bvc_valido("XYZW.CL", {"currency": "COP"}))
        self.assertTrue(L._es_candidato_bvc_valido("AAPL", {}))

    def test_catalogo_inmutable_tras_sesion_usd(self):
        _registrar_runtime(*USUARIO[1])
        L.aplicar_monedas_a_empresa(USUARIO[1][0])
        self.assertEqual(L.ticker_canonico_empresa("ISA — Interconexión Eléctrica"), "ISA.CL")
        self.assertEqual(L.monedas_alineadas_por_ticker(nombre_empresa="ISA — Interconexión Eléctrica"), ("COP", "COP"))


# ---------------------------------------------------------------------------
# 2. Normalización monetaria
# ---------------------------------------------------------------------------
class TestMonedas(BaseOffline):
    def test_monedas_por_emisor(self):
        for nombre in PREDEFINIDAS:
            self.assertEqual(L.monedas_alineadas_por_ticker(nombre_empresa=nombre), ("COP", "COP"))
        for nombre, tk, mon, base, acc in USUARIO:
            _registrar_runtime(nombre, tk, mon, base, acc)
            self.assertEqual(L.monedas_alineadas_por_ticker(nombre_empresa=nombre), (mon, mon), nombre)

    def test_upside_bloqueado_con_monedas_distintas_o_desconocidas(self):
        r = L.calcular_vps_y_upside(100.0, 10.0, precio_mercado=9_000.0, moneda_modelo="COP", moneda_precio="USD")
        self.assertIsNone(r["upside_pct"])
        val = {"Equity_Value": 100.0, "value_per_share": 10_000.0, "upside_pct": None, "acciones": 10.0}
        with mock.patch.object(L, "moneda_empresa", return_value=None), \
                mock.patch.object(L, "moneda_precio_empresa", return_value=None):
            out = L.forzar_vps_upside(dict(val), "X", precio=9_000.0)
        self.assertIsNone(out.get("upside_pct"), "monedas desconocidas no deben producir upside")

    def test_upside_ratio_extremo_bloqueado_en_ultimo_recurso(self):
        val = {"Equity_Value": None, "value_per_share": 10.0, "upside_pct": None}
        with mock.patch.object(L, "moneda_empresa", return_value="COP"), \
                mock.patch.object(L, "moneda_precio_empresa", return_value="COP"):
            out = L.forzar_vps_upside(dict(val), "X", precio=25_000.0)
        self.assertIsNone(out.get("upside_pct"))

    def test_portafolio_convierte_cop_a_usd_fecha_a_fecha(self):
        idx = pd.date_range("2026-01-01", periods=4, freq="B")
        precios = pd.DataFrame({"ISA.CL": [20_000, 20_400, 20_400, 20_800], "AAPL": [250, 250, 255, 255]}, index=idx)
        fx = pd.Series([4_000, 4_080, 4_000, 4_160], index=idx)
        out = PE.convertir_a_moneda_comun(precios, {"ISA.CL": "COP", "AAPL": "USD"}, fx, "USD")
        np.testing.assert_allclose(out["ISA.CL"].to_numpy(), [5.0, 5.0, 5.1, 5.0])
        np.testing.assert_allclose(out["AAPL"].to_numpy(), [250, 250, 255, 255])
        out_cop = PE.convertir_a_moneda_comun(precios, {"ISA.CL": "COP", "AAPL": "USD"}, fx, "COP")
        self.assertAlmostEqual(out_cop["AAPL"].iloc[0], 1_000_000.0)
        with self.assertRaises(ValueError):
            PE.convertir_a_moneda_comun(precios, {"ISA.CL": "COP", "AAPL": "EUR"}, fx, "USD")
        with self.assertRaises(ValueError):
            PE.convertir_a_moneda_comun(precios, {"ISA.CL": "COP", "AAPL": "USD"}, None, "USD")

    def test_proveedor_yahoo_unidades(self):
        class FakeTicker:
            def __init__(self, s):
                self.info = {"currency": "USD", "regularMarketChangePercent": 0.5, "pegRatio": 2.1,
                             "enterpriseValue": 9e12, "currentPrice": 100.0}
                self.fast_info = {}

            def history(self, **k):
                return pd.DataFrame()

        fake_yf = types.SimpleNamespace(Ticker=FakeTicker)
        with mock.patch.object(L, "yf", fake_yf, create=True), mock.patch.object(L, "HAS_YF", True):
            r = L._proveedor_yahoo("AAPL")
        self.assertEqual(r["cambio_pct"], 0.5, "0,5 % no debe convertirse en 50 %")
        self.assertIsNone(r["pe"], "PEG no es P/E")
        self.assertIsNone(r["market_cap"], "EV no es capitalización bursátil")
        self.assertEqual(r["moneda"], "USD")


# ---------------------------------------------------------------------------
# 3. Activos múltiples + consistencia cross-tab
# ---------------------------------------------------------------------------
class TestActivosMultiplesCrossTab(BaseOffline):
    def test_seis_empresas_consistencia_entre_pestanas(self):
        for nombre, tk, mon, base, acc in USUARIO:
            _registrar_runtime(nombre, tk, mon, base, acc)
        reporte = []
        for nombre in PREDEFINIDAS + [u[0] for u in USUARIO]:
            L.reset_resultados_sesion(nombre)
            m = _correr_pestanas(nombre)
            m2, m4, m7 = m["2"], m["4"], m["7"]
            self.assertIsNotNone(m4, f"{nombre}: tab4 sin métricas")
            snap = L.instantanea_precio_mercado(nombre)
            tk_esperado = dict((u[0], u[1]) for u in USUARIO).get(nombre) or \
                L._EMPRESAS_CATALOGO_INMUTABLE[nombre]["ticker_yf"]
            self.assertEqual(m4["ticker"], tk_esperado, nombre)
            # Precio idéntico en cabecera, tab2, tab4 y tab7 (misma instantánea)
            for mx in (m2, m4, m7):
                self.assertEqual(mx["precio_mercado"], snap["precio"], nombre)
            # EV / Equity / VPS / upside idénticos entre tab4 y tab7 (mismos supuestos)
            for k in ("val_ev", "val_equity", "vps_modelo", "upside"):
                if m4[k] is None:
                    self.assertIsNone(m7[k], f"{nombre}:{k}")
                else:
                    self.assertAlmostEqual(m4[k], m7[k], places=6, msg=f"{nombre}:{k}")
            # tab2 escenario base = tab4 base
            self.assertAlmostEqual(m2["val_ev"], m4["val_ev"], places=6, msg=nombre)
            # Comité / simulador / portafolio leen exactamente las métricas de tab4
            mc = L._metricas_comite_para_ia(nombre)
            self.assertEqual(mc.get("origen_metricas"), "pestaña 4 (sesión)")
            for k in ("precio_mercado", "vps_modelo", "upside", "val_ev", "wacc_calc"):
                self.assertEqual(mc[k], m4[k], f"{nombre}:{k}")
            self.assertEqual(m4["moneda"], m4["moneda_precio"])
            self.assertEqual(m4["moneda"], "USD" if nombre.endswith(("AAPL", "PLTR")) else "COP")
            reporte.append((nombre, m4["ticker"], m4["moneda"], m4["precio_mercado"], m4["vps_modelo"], m4["upside"]))
        self.assertEqual(len(reporte), 6)

    def test_cache_unica_instantanea_por_ticker(self):
        for _ in range(5):
            L.resolver_precio_mercado("ISA — Interconexión Eléctrica")
        self.assertEqual(LLAMADAS_MERCADO.count("ISA.CL"), 1, "5 lecturas → 1 consulta al proveedor")


# ---------------------------------------------------------------------------
# 4. Estrés de estado: cambios rápidos de empresa y aislamiento entre sesiones
# ---------------------------------------------------------------------------
class TestEstresEstado(BaseOffline):
    def test_cambios_rapidos_no_arrastran_metricas(self):
        for nombre, tk, mon, base, acc in USUARIO:
            _registrar_runtime(nombre, tk, mon, base, acc)
        secuencia = (PREDEFINIDAS + [u[0] for u in USUARIO]) * 3
        anterior = None
        for nombre in secuencia:
            L.reset_resultados_sesion(nombre)  # lo que hace _purgar_estado_empresa
            self.assertEqual(L.RESULTADOS_SESION["tabs"], {})
            if anterior and anterior != nombre:
                self.assertIsNone(L.metricas_valoracion_sesion(anterior))
            m = _correr_pestanas(nombre)
            import matplotlib.pyplot as _plt
            _plt.close("all")  # la interfaz cierra cada figura al mostrarla; aquí nadie la muestra
            self.assertEqual(m["4"]["empresa"], nombre)
            # guardar con otra empresa purga lo previo (defensa en profundidad)
            L.guardar_resultado_tab("4", "OTRA", {"metricas": {"empresa": "OTRA"}})
            self.assertIsNone(L.metricas_valoracion_sesion(nombre))
            anterior = nombre

    def test_aislamiento_entre_sesiones_concurrentes(self):
        res = {}

        def sesion(nombre_sesion, empresa, api_key):
            alm = {}
            L.vincular_estado_sesion(alm)
            L.EMPRESAS_RUNTIME[empresa] = {"ticker_yf": "AAPL", "params": {}}
            L.configurar_mercado("api_key", api_key, "")
            L.reset_resultados_sesion(empresa)
            res[nombre_sesion] = (sorted(L.EMPRESAS_RUNTIME.keys()), L.MERCADO_CONFIG["api_key"],
                                  L.RESULTADOS_SESION["empresa"])
            L.desvincular_estado_sesion()

        hilos = [threading.Thread(target=sesion, args=("A", "EmpA", "key-A")),
                 threading.Thread(target=sesion, args=("B", "EmpB", "key-B"))]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(res["A"], (["EmpA"], "key-A", "EmpA"))
        self.assertEqual(res["B"], (["EmpB"], "key-B", "EmpB"))
        self.assertNotIn("EmpA", L.EMPRESAS_RUNTIME)  # la sesión de la prueba no ve a otras

    def test_purga_streamlit(self):
        """_purgar_estado_empresa elimina todo el estado de la empresa previa."""
        st_fake = types.ModuleType("streamlit")
        st_fake.session_state = {}
        st_fake.set_page_config = lambda *a, **k: None
        st_fake.markdown = lambda *a, **k: None
        st_fake.cache_data = lambda *a, **k: (lambda f: f)
        with mock.patch.dict(sys.modules, {"streamlit": st_fake}):
            sys.modules.pop("streamlit_app", None)
            import streamlit_app as app
            ss = st_fake.session_state
            ss.update({
                "params": {"ticker_yf": "AAPL"}, "resultados": {"tab4": "x"}, "hero_html": "<b>AAPL</b>",
                "precio_mercado_alineado": 260.0, "tab4_comite_ia_html": "AAPL", "archivo_bytes": b"x",
                "portfolio_result": {}, "investment_sim_result": {}, "investment_sim_ticker_apple": "AAPL",
                "multiples_ebitda": 120.0, "contraste_mercado_actual": {}, "_model_fingerprint": ("x",),
                "tour_done": True, "iakey": "k", "_uploader_nonce": 3,
            })
            app._purgar_estado_empresa("ISA — Interconexión Eléctrica")
            for k in ("hero_html", "precio_mercado_alineado", "tab4_comite_ia_html", "archivo_bytes",
                      "portfolio_result", "investment_sim_result", "investment_sim_ticker_apple",
                      "multiples_ebitda", "contraste_mercado_actual", "_model_fingerprint"):
                self.assertNotIn(k, ss, k)
            self.assertEqual(ss["resultados"], {})
            self.assertIsNone(ss["params"])
            self.assertEqual(ss["_uploader_nonce"], 4)
            self.assertTrue(ss["tour_done"])  # preferencias del usuario se conservan
            self.assertEqual(ss["iakey"], "k")
            self.assertEqual(ss["_empresa_estado"], "ISA — Interconexión Eléctrica")
        sys.modules.pop("streamlit_app", None)


class TestRecargaEnRedespliegue(unittest.TestCase):
    """Streamlit Cloud reejecuta el script sin reiniciar el proceso: si la lógica en
    memoria es la versión anterior, la app debe recargarla en vez de fallar."""

    def test_logica_obsoleta_se_recarga(self):
        st_fake = types.ModuleType("streamlit")
        st_fake.session_state = {}
        st_fake.set_page_config = lambda *a, **k: None
        st_fake.markdown = lambda *a, **k: None
        st_fake.cache_data = lambda *a, **k: (lambda f: f)
        import modelacion_logic as logic
        original = logic.vincular_estado_sesion
        del logic.vincular_estado_sesion  # simula el módulo viejo en caché
        try:
            with mock.patch.dict(sys.modules, {"streamlit": st_fake}):
                sys.modules.pop("streamlit_app", None)
                import streamlit_app as app
                self.assertTrue(hasattr(app.L, "vincular_estado_sesion"))
        finally:
            if not hasattr(logic, "vincular_estado_sesion"):
                logic.vincular_estado_sesion = original
            sys.modules.pop("streamlit_app", None)


# ---------------------------------------------------------------------------
# 5. Gemini: clave en cabecera, fallback de modelos, métricas del modelo en el prompt
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestGemini(BaseOffline):
    def test_clave_en_cabecera_y_fallback_404(self):
        import urllib.error
        import urllib.request
        vistos = []

        def fake_urlopen(req, timeout=None):
            vistos.append((req.full_url, dict(req.header_items())))
            if len(vistos) == 1:
                raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, None)
            return _FakeResp({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

        with mock.patch.object(urllib.request, "urlopen", fake_urlopen), \
                mock.patch.dict("os.environ", {"GEMINI_MODEL": ""}):
            out = L._llamar_ia_redaccion("sys", "user", api_key="AIza-SECRETA", proveedor="gemini")
        self.assertEqual(out, "ok")
        self.assertEqual(len(vistos), 2)
        for url, headers in vistos:
            self.assertNotIn("AIza-SECRETA", url)
            self.assertEqual({k.lower(): v for k, v in headers.items()}["x-goog-api-key"], "AIza-SECRETA")
        self.assertIsNone(L._get_ia_error())

    def test_comite_recibe_metricas_de_tab4(self):
        _correr_pestanas("ISA — Interconexión Eléctrica")
        m4 = L.metricas_valoracion_sesion("ISA — Interconexión Eléctrica")
        capturado = {}
        respuesta = json.dumps({
            "analisis_interno": {"resumen": "El WACC del modelo explica la brecha.", "supuestos_fragiles": []},
            "contexto_mercado": {"resumen": "Instantánea de mercado.", "hechos_usados": []},
            "recomendacion": "MANTENER", "precio_objetivo": None, "anclas_usadas": [],
            "metodo_precio_objetivo": "N/D", "conviccion": 6, "tesis": ["Flujos regulados."],
            "riesgos": [{"riesgo": "Tasa", "indicador": "TES"}, {"riesgo": "Regulación", "indicador": "CREG"}],
            "catalizadores": [{"catalizador": "Resultados", "ventana": "3T26"}, {"catalizador": "OPA GEB", "ventana": "2027"}],
            "cambiaria_la_recomendacion": ["WACC < 11 %"],
            "divergencia_motor": {"hay_divergencia": False, "justificacion": ""}, "condicionado_a_recalibrar": False,
            "conciliacion_mercado": {"explicacion": "El precio exige un WACC 308 pb menor que el del modelo; la brecha se explica por la tasa local.", "es_oportunidad": False},
        })

        def fake_llm(sistema, user, **k):
            capturado["user"] = user
            return respuesta

        with mock.patch.object(L, "_llamar_ia_redaccion", side_effect=fake_llm):
            html = L.generar_recomendacion_comite_ia("ISA — Interconexión Eléctrica", api_key="k", metricas=m4,
                                                     buscar_web=False)
        if m4["vps_modelo"] is not None and L.auditar_contexto_comite_ia(m4)["ok"]:
            self.assertIn(f"{m4['precio_mercado']:,.2f}", capturado["user"])
            self.assertIn(f"{m4['vps_modelo']:,.2f}", capturado["user"])
            self.assertIn("MANTENER", html)
            self.assertIn("A1", capturado["user"])  # el DCF base viaja como ancla del precio objetivo
        else:
            self.assertIn("bloqueado", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
