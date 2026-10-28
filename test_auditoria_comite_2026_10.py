"""Regresiones de la auditoría integral del comité (oct-2026).

Cubre los errores encontrados al validar 3 empresas del catálogo (ISA, GEB,
ECOPETROL) y 3 descargadas (AAPL, KO, EC) contra el mercado. Corre offline.
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

import modelacion_logic as L

TRM = 3157.94


def _bs(rows):
    cols = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]
    return pd.DataFrame({c: [v[i] for v in rows.values()] for i, c in enumerate(cols)}, index=list(rows))


class TestADRMonedasYAcciones(unittest.TestCase):
    """EC: EEFF en COP, precio y marketCap en USD por ADS (1 ADS = 20 acciones)."""

    def setUp(self):
        L.fijar_tasa_cop_usd(TRM)
        self.info = {
            "currency": "USD", "financialCurrency": "COP", "country": "Colombia",
            "regularMarketPrice": 17.29, "marketCap": 35.87e9,
            "sharesOutstanding": 41_116_694_690,          # acciones ordinarias
            "totalDebt": 104_918e9, "totalCash": 11_192e9,  # COP
            "beta": 0.9,
        }

    def tearDown(self):
        L.fijar_tasa_cop_usd(None)

    def test_acciones_en_unidades_cotizadas(self):
        p = L.derivar_params_desde_cero(None, info=self.info, ticker_yf="EC")
        # 35,87 mil M USD / 17,29 USD ≈ 2.075 M de ADS (no 41.117 M de ordinarias)
        self.assertAlmostEqual(p["acciones"], 35.87e9 / 17.29 / 1e6, places=2)
        self.assertIn("marketCap/precio", p["acciones_fuente"])

    def test_de_ratio_con_capitalizacion_en_moneda_de_eeff(self):
        p = L.derivar_params_desde_cero(None, info=self.info, ticker_yf="EC")
        esperado = 104_918e9 / (35.87e9 * TRM)
        self.assertAlmostEqual(p["de_ratio"], esperado, places=3)
        self.assertLess(p["de_ratio"], 2.0)  # antes ~2.900x

    def test_de_ratio_sin_fx_queda_en_cero_y_no_mezcla_monedas(self):
        L.fijar_tasa_cop_usd(None)
        orig = L.tasa_cop_por_usd
        L.tasa_cop_por_usd = lambda: (None, "sin tasa")
        try:
            p = L.derivar_params_desde_cero(None, info=self.info, ticker_yf="EC")
        finally:
            L.tasa_cop_por_usd = orig
        self.assertEqual(p["de_ratio"], 0.0)

    def test_emisor_local_conserva_shares_outstanding(self):
        info = {"currency": "USD", "financialCurrency": "USD", "regularMarketPrice": 343.91,
                "marketCap": 5.07e12, "sharesOutstanding": 14.69e9}
        p = L.derivar_params_desde_cero(None, info=info, ticker_yf="AAPL")
        self.assertAlmostEqual(p["acciones"], 14690.0, places=1)
        self.assertEqual(p["acciones_fuente"], "sharesOutstanding")

    def test_upside_adr_visible_en_puente(self):
        val = L.valoracion_dcf([10_000.0] * 5, 0.14, 0.03, deuda_neta=50_000, acciones=2074.6)
        vu = L.calcular_vps_y_upside(val["Equity_Value"], 2074.6, precio_mercado=17.29,
                                     moneda_modelo="COP", moneda_precio="USD")
        val.update({k: vu[k] for k in ("value_per_share", "upside_pct")})
        val.update(precio_mercado=17.29, fx_aplicado=vu["fx_aplicado"],
                   precio_moneda_modelo=vu["precio_moneda_modelo"], fuente_fx=vu["fuente_fx"])
        html = L.formatear_bridge_html(val, moneda_modelo="COP", moneda_precio="USD")
        self.assertNotIn("N/D comparable", html)
        self.assertIn("FX 3,157.94", html)


class TestInteresMinoritario(unittest.TestCase):
    def test_total_equity_gross_no_se_toma_como_nci(self):
        bs = _bs({
            "Total Equity Gross Minority Interest": [73_733e6, 56_950e6],
            "Stockholders Equity": [73_733e6, 56_950e6],
        })
        p = L.derivar_params_desde_cero(None, info={"_balance_sheet": bs, "currency": "USD"}, ticker_yf="AAPL")
        self.assertEqual(p["nci"], 0.0)

    def test_nci_por_diferencia_gross_menos_controladora(self):
        bs = _bs({
            "Total Equity Gross Minority Interest": [34_275e6, 26_372e6],
            "Stockholders Equity": [32_169e6, 24_856e6],
        })
        p = L.derivar_params_desde_cero(None, info={"_balance_sheet": bs, "currency": "USD"}, ticker_yf="KO")
        self.assertAlmostEqual(p["nci"], 2.106, places=3)

    def test_nci_explicito_tiene_prioridad(self):
        bs = _bs({
            "Total Equity Gross Minority Interest": [110_000e9, 100_000e9],
            "Minority Interest": [38_000e9, 35_000e9],
            "Stockholders Equity": [72_000e9, 65_000e9],
        })
        p = L.derivar_params_desde_cero(None, info={"_balance_sheet": bs, "currency": "COP"}, ticker_yf="X.CL")
        self.assertAlmostEqual(p["nci"], 38_000.0, places=1)


class TestValorTerminalYMercado(unittest.TestCase):
    def test_exit_multiple_se_descuenta_al_cierre_del_anio_n(self):
        v = L.valoracion_dcf([100.0] * 5, 0.10, 0.02, exit_multiple=10.0, ebitda_salida=150.0, mid_year=True)
        self.assertAlmostEqual(v["EV_Exit"] - v["PV_FCFF"], 1500.0 / 1.10 ** 5, places=6)

    def test_wacc_implicito_reproduce_el_precio(self):
        fcff = [1000.0, 1050.0, 1100.0, 1150.0, 1200.0]
        bp = {"deuda_neta": 3000.0, "acciones": 100.0}
        base = L.valorar_con_bridge(fcff, 0.11, 0.03, bp, nopat_final=1500.0, g_max_macro=0.05)
        px = base["Equity_Value"] * 1000.0 / 100.0
        r = L.wacc_implicito_mercado(fcff, 0.03, bp, px, nopat_final=1500.0, g_max_macro=0.05)
        self.assertEqual(r["motivo"], "ok")
        self.assertAlmostEqual(r["wacc"], 0.11, places=4)

    def test_wacc_implicito_informa_precio_inalcanzable(self):
        bp = {"deuda_neta": 0.0, "acciones": 100.0}
        r = L.wacc_implicito_mercado([10.0] * 5, 0.02, bp, 1e9, nopat_final=10.0, g_max_macro=0.04)
        self.assertIsNone(r["wacc"])
        self.assertEqual(r["motivo"], "precio_exige_mas_crecimiento")

    def test_ronic_spread_de_sesion_aplica_en_todas_las_valoraciones(self):
        args = ([100.0] * 5, 0.09, 0.03)
        base = L.valoracion_dcf(*args, nopat_final=120.0)["EV"]
        try:
            L.fijar_ronic_spread(0.06)
            con_spread = L.valoracion_dcf(*args, nopat_final=120.0)
        finally:
            L.fijar_ronic_spread(None)
        self.assertGreater(con_spread["EV"], base)
        self.assertAlmostEqual(con_spread["ronic"], 0.15, places=9)
        self.assertAlmostEqual(L.valoracion_dcf(*args, nopat_final=120.0)["EV"], base, places=9)
        with self.assertRaises(ValueError):
            L.fijar_ronic_spread(0.5)


def _hist():
    años = [2021, 2022, 2023, 2024, 2025]
    ing = np.array([1000.0, 1050.0, 1100.0, 1160.0, 1220.0])
    df = pd.DataFrame({"Ingresos": ing, "EBITDA": ing * 0.30, "EBIT": ing * 0.22,
                       "Depreciacion": ing * 0.08, "CAPEX": ing * 0.09, "NWC": ing * 0.05}, index=años)
    df.index.name = "Año"
    return df


class TestCrecimientoImplicito(unittest.TestCase):
    def test_reproduce_el_crecimiento_que_genera_el_precio(self):
        df, tax, wacc, g = _hist(), 0.25, 0.10, 0.03
        bp = {"deuda_neta": 200.0, "acciones": 50.0}
        dfp, _ = L.proyectar_por_drivers(df, 5, tax=tax, g_ingresos_inicial=0.15)
        dfp = L.recalcular_fcff(dfp, tax=tax)
        v = L.valorar_con_bridge(dfp["FCFF"].values, wacc, g, bp, nopat_final=L._nopat_final(dfp), g_max_macro=0.04)
        px = v["Equity_Value"] * 1000.0 / 50.0
        r = L.crecimiento_implicito_mercado(df, 5, tax, wacc, g, bp, px, g_max_macro=0.04)
        self.assertEqual(r["motivo"], "ok")
        self.assertAlmostEqual(r["g_ingresos"], 0.15, places=3)
        self.assertLess(r["g_base"], 0.10)

    def test_sin_precio_no_inventa_resultado(self):
        r = L.crecimiento_implicito_mercado(_hist(), 5, 0.25, 0.10, 0.03, {"acciones": 50.0}, None)
        self.assertIsNone(r["g_ingresos"])


class TestInversionesNoOperativas(unittest.TestCase):
    def test_investments_and_advances_suma_al_equity(self):
        bs = _bs({"Investments And Advances": [77_723e6, 91_479e6], "Long Term Equity Investment": [1e6, 1e6]})
        p = L.derivar_params_desde_cero(None, info={"_balance_sheet": bs, "currency": "USD"}, ticker_yf="AAPL")
        self.assertAlmostEqual(p["asociados"], 77.723, places=3)

    def test_componentes_se_suman_sin_agregado(self):
        bs = _bs({"Long Term Equity Investment": [20_235e6, 18_087e6],
                  "Investmentin Financial Assets": [1_500e6, 1_400e6]})
        p = L.derivar_params_desde_cero(None, info={"_balance_sheet": bs, "currency": "USD"}, ticker_yf="KO")
        self.assertAlmostEqual(p["asociados"], 21.735, places=3)


class TestMotorDecisionUsaPrecio(unittest.TestCase):
    BASE = dict(wacc=0.09, g=0.03, roic=0.25, de_ratio=0.3, vpn=10.0, tir=0.12, payback=None,
                ev_base=1000.0, equity_base=900.0, equity_pesimista=500.0, delta_ev_capex=0.0,
                riesgo_liq="Bajo", procedencia={"nivel_calidad": "MEDIA"}, score_heuristico=6,
                moneda_modelo="USD", moneda_precio="USD")

    def test_downside_fuerte_bloquea_sesgo_positivo(self):
        m = L.motor_decision_institucional(**self.BASE, precio_mercado=100.0, equity_por_accion=25.0)
        self.assertEqual(m["decision"], "NEUTRAL / MONITOREAR · PRECIO SOBRE VALOR")
        self.assertTrue(any("supera" in a for a in m["alertas"]))

    def test_sin_precio_conserva_lectura_de_fundamentos(self):
        m = L.motor_decision_institucional(**self.BASE)
        self.assertIn("POSITIVO", m["decision"])

    def test_margen_de_seguridad_es_soporte(self):
        m = L.motor_decision_institucional(**self.BASE, precio_mercado=100.0, equity_por_accion=130.0)
        self.assertTrue(any("Margen de seguridad" in x for x in m["soportes"]))


class TestCatalogoYProcedencia(unittest.TestCase):
    def test_techo_g_catalogo_es_el_del_mercado_colombiano(self):
        nombre = next(n for n in L.EMPRESAS if L.EMPRESAS[n].get("historico"))
        out = L.al_cambiar_empresa(nombre)
        self.assertAlmostEqual(out[-1], L.CAPM_POR_MERCADO["CO"]["g_max_macro"])

    def test_serie_del_catalogo_no_se_rotula_como_yahoo(self):
        msg = ("Histórico curado del catálogo para ISA (2022–2025). "
               "Yahoo no sustituye el catálogo en pestaña 1 para evitar años en cero.")
        prov = L.procedencia_datos(msg)
        self.assertIn("curado", prov["fuente_financiera"].lower())
        self.assertNotIn("Descarga pública Yahoo", prov["fuente_financiera"])

    def test_descarga_yahoo_sigue_rotulada_como_yahoo(self):
        prov = L.procedencia_datos("Descargado desde Yahoo Finance (AAPL), 4 años. NWC: balance Yahoo.")
        self.assertIn("Yahoo", prov["fuente_financiera"])

    def test_precio_usd_con_decimales(self):
        prov = L.procedencia_datos("x", mkt={"ok": True, "precio": 17.29, "moneda": "USD"})
        self.assertIn("17.29 USD", prov["fuente_mercado"])


if __name__ == "__main__":
    unittest.main()
