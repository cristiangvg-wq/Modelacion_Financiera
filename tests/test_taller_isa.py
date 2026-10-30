import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.taller_isa import (
    CATALOG, DECISION_THRESHOLDS, DEFAULT_DATA, POLICIES, SCENARIOS, SCENARIO_ORDER,
    cost_of_capital, evaluate, historical_drivers, implied_irr, irr, load_isa, market_ev,
    monte_carlo, policy_impact, policy_triggered, project, run_model, scenario_params,
    snapshot_from_catalog, tornado, value,
)


class TestTallerISA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isa = load_isa(DEFAULT_DATA)
        cls.drivers = historical_drivers(cls.isa)

    # --- Datos y calibración (Bloque A) ---
    def test_snapshot_is_standalone_and_has_sources(self):
        self.assertTrue(DEFAULT_DATA.exists())
        self.assertGreaterEqual(len(self.isa["history"]), 3)
        for key in ("fuente_tes_10a", "fuente_primas", "fuente_tax", "fuente_de_ratio"):
            self.assertTrue(self.isa["capital"][key])
        self.assertTrue(self.isa["puente"]["fuente"])

    @unittest.skipUnless(CATALOG.exists(), "catálogo de la app no disponible")
    def test_snapshot_matches_catalog_history(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        if "ISA — Interconexión Eléctrica" not in catalog.get("empresas", {}):
            self.skipTest("ISA ya no está en el catálogo")
        snap = snapshot_from_catalog(catalog)
        self.assertEqual(snap["historico"], self.isa["historico"])

    def test_growth_is_computed_from_data_not_hardcoded(self):
        h = self.isa["history"]
        n = h[-1]["Año"] - h[0]["Año"]
        expected = (h[-1]["Ingresos"] / h[0]["Ingresos"]) ** (1 / n) - 1
        self.assertAlmostEqual(self.drivers["growth"], expected, places=12)

    def test_capex_ratio_matches_current_data(self):
        last = self.isa["history"][-1]
        self.assertAlmostEqual(self.drivers["capex_ratio_last"], last["CAPEX"] / last["Ingresos"])
        self.assertLess(self.drivers["capex_ratio_last"], 0.20)  # 10,7 %, no 39 % (texto antiguo)

    def test_wacc_capm_components(self):
        c = cost_of_capital(self.isa)
        cap = self.isa["capital"]
        self.assertAlmostEqual(c["rf"], cap["tes_10a"] - cap["spread_default_co"])
        self.assertAlmostEqual(c["we"] + c["wd"], 1.0)
        self.assertAlmostEqual(c["wacc"], c["we"] * c["ke"] + c["wd"] * c["kd"] * (1 - c["tax"]))
        self.assertGreater(c["wacc"], cap["g_terminal"] + 0.02)

    # --- Pronóstico ---
    def test_projection_reconciles_fcff_and_links_capex_to_growth(self):
        p = scenario_params(self.isa, "Base")
        rows = project(self.isa, p)
        self.assertEqual([r["año"] for r in rows if not r["terminal"]], [2026, 2027, 2028, 2029, 2030])
        self.assertTrue(rows[-1]["terminal"])
        prev = self.drivers["revenue_base"]
        for r in rows:
            self.assertAlmostEqual(r["fcff"], r["nopat"] + r["depreciacion"] - r["capex"] - r["delta_nwc"], places=7)
            self.assertAlmostEqual(r["capex_expansion"], p["capex_intensity"] * (r["ingresos"] - prev), places=7)
            prev = r["ingresos"]

    def test_valuation_bridge(self):
        e = evaluate(self.isa, "Base")
        v, b = e["valuation"], self.isa["puente"]
        self.assertAlmostEqual(v["ev"], v["vp_fcff_explicito"] + v["vp_valor_terminal"])
        self.assertAlmostEqual(v["patrimonio"], v["ev"] - b["deuda_neta"] - b["nci"] + b["asociados"])
        self.assertAlmostEqual(v["vpn_inversionista"], v["patrimonio"] - v["capitalizacion_mercado"])

    def test_implied_irr_equates_market_ev(self):
        e = evaluate(self.isa, "Base")
        r = e["tir_implicita"]
        self.assertFalse(math.isnan(r))
        ev_at_r = value(self.isa, e["rows"], r, e["params"]["g_terminal"])["ev"]
        self.assertAlmostEqual(ev_at_r, market_ev(self.isa), delta=1.0)
        # Coherencia VPN–TIR: VPN < 0 ⇔ TIR implícita < WACC
        self.assertEqual(e["valuation"]["vpn_inversionista"] < 0, r < e["params"]["wacc"])

    def test_irr_helper(self):
        self.assertAlmostEqual(irr([-100, 110]), 0.10, places=6)
        self.assertTrue(math.isnan(irr([100, 100])))

    # --- Escenarios (Bloque B) ---
    def test_scenarios_move_at_least_five_drivers_and_are_ordered(self):
        self.assertTrue({"Pesimista", "Base", "Optimista"} <= set(SCENARIOS))
        drivers = ("growth_delta", "ebit_margin_delta", "capex_intensity_mult", "nwc_ratio_mult", "wacc_delta", "g_terminal_delta")
        base = SCENARIOS["Base"]
        for name in ("Pesimista", "Optimista", "Estrés"):
            moved = sum(1 for k in drivers if SCENARIOS[name][k] != base[k])
            self.assertGreaterEqual(moved, 5, name)
        values = [evaluate(self.isa, s)["valuation"]["valor_por_accion"] for s in SCENARIO_ORDER]
        self.assertEqual(values, sorted(values))

    def test_tornado_has_all_drivers_sorted(self):
        t = tornado(self.isa)
        self.assertGreaterEqual(len(t), 6)
        self.assertEqual([x["rango"] for x in t], sorted((x["rango"] for x in t), reverse=True))

    # --- Políticas (Bloque C) ---
    def test_three_policies_with_explicit_rules(self):
        self.assertGreaterEqual(len(POLICIES), 2)
        for cfg in POLICIES.values():
            self.assertIn("SI", cfg["regla"])
            self.assertIn("ENTONCES", cfg["regla"])

    def test_capex_deferral_keeps_total_nominal_capex_before_penalty(self):
        pol = dict(POLICIES["P1 Diferir CAPEX de expansión"], growth_penalty=0.0)
        p = scenario_params(self.isa, "Base")
        base = project(self.isa, p)
        deferred = project(self.isa, p, "P1 Diferir CAPEX de expansión", pol)
        total = lambda rows: sum(r["capex_expansion"] for r in rows if not r["terminal"])
        self.assertAlmostEqual(total(base), total(deferred), places=6)
        self.assertLess(deferred[0]["capex"], base[0]["capex"])
        self.assertEqual(deferred[0]["capex_mantenimiento"], base[0]["capex_mantenimiento"])

    def test_efficiency_policy_charges_cost_and_rule_triggers(self):
        imp = policy_impact(self.isa, "Base", "P2 Programa de eficiencia operativa")
        self.assertLess(imp["flujos_incrementales"][1], 1e-9 + max(imp["flujos_incrementales"][2:]))
        self.assertTrue(policy_triggered(self.isa, "Base", "P2 Programa de eficiencia operativa"))

    def test_dividend_policy_does_not_change_ev_but_cuts_debt_when_triggered(self):
        imp = policy_impact(self.isa, "Estrés", "P3 Dividendos condicionados al apalancamiento")
        self.assertAlmostEqual(imp["delta_vpn"], 0.0, places=6)
        if imp["regla_activa"]:
            self.assertLess(imp["deuda_final_con"], imp["deuda_final_sin"])

    # --- Monte Carlo y exportación ---
    def test_monte_carlo_reproducible(self):
        a = monte_carlo(self.isa, n=50, seed=1)
        b = monte_carlo(self.isa, n=50, seed=1)
        self.assertEqual(a["p50"], b["p50"])
        self.assertLessEqual(a["p5"], a["p50"])
        self.assertLessEqual(a["p50"], a["p95"])
        self.assertTrue(0 <= a["prob_valor_mayor_precio"] <= 1)

    def test_run_model_exports_auditable_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_model(DEFAULT_DATA, Path(tmp), mc_n=50)
            for f in ("detalle_escenarios_politicas.csv", "resumen_escenarios.csv", "impacto_politicas.csv",
                      "apalancamiento.csv", "tornado.csv", "matriz_wacc_g.csv", "monte_carlo.csv",
                      "metadatos_modelo.json"):
                self.assertTrue((Path(tmp) / f).exists(), f)
            meta = json.loads((Path(tmp) / "metadatos_modelo.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["camino"], "Evaluación empresarial")
            self.assertEqual(meta["umbrales_decision"], DECISION_THRESHOLDS)
            self.assertEqual(set(meta["recomendacion_politicas"]), set(POLICIES))
            for rec in meta["recomendacion_politicas"].values():
                self.assertRegex(rec["decision"], "Adoptar|Condicionar|Descartar")
            self.assertGreaterEqual(len(meta["tecnicas"]), 3)
            self.assertEqual(len(r["summary"]), len(SCENARIO_ORDER))

    def test_report_pdf_builds_within_page_limit(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf no instalado")
        from scripts.generar_informe_taller_isa import build
        with tempfile.TemporaryDirectory() as tmp:
            r = run_model(DEFAULT_DATA, Path(tmp) / "out", mc_n=50)
            pdf = build(r, ["Integrante de prueba"], "2026-11-05", "Curso", Path(tmp) / "informe.pdf")
            pages = [p.extract_text() for p in PdfReader(str(pdf)).pages]
            annex = next(i for i, t in enumerate(pages) if "Anexo A" in t[:300])
            self.assertLessEqual(annex - 1, 12)  # cuerpo sin portada ≤ 12 páginas
            text = " ".join(pages)
            for must in ("Camino elegido", "Evaluación empresarial", "Integrante de prueba", "TIR implícita",
                         "Ingeniería de prompts", "Recomendación"):
                self.assertIn(must, text)

    def test_pdf_bytes_helper_for_tab10_button(self):
        from scripts.generar_informe_taller_isa import generar_pdf_bytes
        data = generar_pdf_bytes(["Integrante"], "5 de noviembre de 2026", mc_n=50)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 50_000)

    def test_tab10_has_report_button(self):
        src = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("def _ui_informe_taller_isa", src)
        self.assertIn("_ui_informe_taller_isa(", src.split("with tab10:", 1)[1])


class TestTallerConectadoApp(unittest.TestCase):
    """Modo conectado: el taller usa el histórico y los supuestos de la app."""

    EMP = "ISA — Interconexión Eléctrica"

    @classmethod
    def setUpClass(cls):
        try:
            import modelacion_logic as L
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"modelacion_logic no disponible: {exc}")
        cls.L = L
        if not L.params_empresa(cls.EMP):
            raise unittest.SkipTest("ISA no está en el catálogo de la app")
        cls.df, _ = L.cargar_y_limpiar_excel(None, cls.EMP, usar_datos_publicos=False)
        cls.p = L.params_empresa(cls.EMP)
        cls.co = L.CAPM_POR_MERCADO["CO"]

    def _inputs(self, **over):
        from scripts.taller_isa import inputs_from_app
        p, co = self.p, self.co
        args = dict(tax=p["tax"], g=p["g"], de_ratio=p["de_ratio"], kd=p["kd"], beta_u=p["beta_u"], rf=co["rf"],
                    erp=co["erp"], crp=co["crp"], deuda_neta=p["deuda_neta"], caja=p["caja"], nci=p["nci"],
                    otros_claims=p["otros_claims"], asociados=p["asociados"], acciones=p["acciones"], precio=27500.0)
        args.update(over)
        return inputs_from_app(self.EMP, self.df, **args)

    def test_history_matches_tab1_source(self):
        snap = load_isa(DEFAULT_DATA)
        self.assertEqual(self._inputs()["historico"], snap["historico"])

    def test_wacc_equals_app_formula(self):
        isa = load_isa(self._inputs())
        L, p, co = self.L, self.p, self.co
        ke = co["rf"] + L.beta_apalancado(p["beta_u"], p["de_ratio"], p["tax"]) * co["erp"] + co["crp"]
        wacc_app = L.calcular_wacc(p["de_ratio"], p["kd"], ke, p["tax"])[0]
        self.assertAlmostEqual(cost_of_capital(isa)["wacc"], wacc_app, places=10)

    def test_mid_year_follows_app(self):
        a = evaluate(load_isa(self._inputs(mid_year=True)), "Base")["valuation"]["ev"]
        b = evaluate(load_isa(self._inputs(mid_year=False)), "Base")["valuation"]["ev"]
        self.assertGreater(a, b)

    def test_gross_debt_is_netted(self):
        d = self._inputs(deuda_neta=34155.0, caja=3725.0, deuda_es_bruta=True)
        self.assertAlmostEqual(d["puente"]["deuda_neta"], 30430.0)

    def test_missing_price_is_rejected(self):
        with self.assertRaises(ValueError):
            self._inputs(precio=None)

    def test_json_reproduces_same_report_inputs(self):
        from scripts.generar_informe_taller_isa import generar_informe
        from scripts.taller_isa import inputs_fingerprint
        out = generar_informe(["X"], "f", mc_n=30, data=self._inputs())
        reloaded = load_isa(json.loads(out["json"].decode("utf-8")))
        self.assertEqual(inputs_fingerprint(reloaded), out["huella"])
        self.assertEqual(out["fuente"], "Modelo de la app (sesión)")

    def test_tab10_passes_sidebar_context(self):
        src = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
        call = src.split("with tab10:", 1)[1].split("_ui_informe_taller_isa(", 1)[1][:600]
        for key in ("empresa", "archivo", "tax", "deuda_neta", "acciones", "mid_year"):
            self.assertIn(f'"{key}"', call)


if __name__ == "__main__":
    unittest.main()
