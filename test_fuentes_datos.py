"""Orden de fuentes de datos: archivo del usuario → Yahoo → respaldo curado (datos_curados.json)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

import modelacion_logic as L
from test_contraste_mercado import _FakeYF, _frame

M = 1e6
ISA = "ISA — Interconexión Eléctrica"
EPM = "EPM — Empresas Públicas de Medellín"
COLS = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"]


def _isa_yahoo():
    fin = _frame({
        "Total Revenue": [16000, 15000, 14200, 13400],
        "EBIT": [7400, 8400, 7600, 6900],
        "EBITDA": [8700, 9750, 9100, 7800],
        "Reconciled Depreciation": [1300, 1350, 1500, 900],
    }, COLS) * 1e9
    cf = _frame({"Capital Expenditure": [-6300, -4800, -4600, -950]}, COLS) * 1e9
    info = dict(longName="Interconexión Eléctrica S.A. E.S.P.", country="Colombia", currency="COP",
                financialCurrency="COP", regularMarketPrice=29000.0, marketCap=32.1e12,
                sharesOutstanding=1107.7 * M, beta=0.32, totalDebt=34.2e12, totalCash=3.7e12,
                sector="Utilities")
    return dict(info=info, fin=fin, cf=cf, bs=pd.DataFrame(), px=29000.0)


class BaseFuentes(unittest.TestCase):
    def setUp(self):
        L.vincular_estado_sesion({})
        L.limpiar_cache_mercado()

    def tearDown(self):
        L.limpiar_cache_mercado()
        L.desvincular_estado_sesion()

    def _con_yahoo(self, data):
        precios = {k: v["px"] for k, v in data.items()}
        return [mock.patch.object(L, "yf", _FakeYF(data, precios), create=True),
                mock.patch.object(L, "HAS_YF", True)]


class TestCatalogoCurado(BaseFuentes):
    def test_json_sin_anos_de_relleno(self):
        datos = json.loads(Path(L.__file__).with_name("datos_curados.json").read_text(encoding="utf-8"))
        self.assertEqual(len(datos["empresas"]), 7)
        for nombre, emp in datos["empresas"].items():
            h = emp.get("historico")
            if h:
                self.assertGreaterEqual(min(h["Año"]), 2021, nombre)
                self.assertTrue(emp.get("fuente_historico"), nombre)
                self.assertTrue(emp.get("verificacion"), nombre)
        self.assertIsNone(datos["empresas"][EPM]["historico"])
        self.assertIsNone(datos["empresas"]["ENEL Colombia"]["historico"])
        # ISA 2025 usa CAPEX de caja identificable (PP&E + intangibles), no inversión ejecutada de gestión.
        self.assertAlmostEqual(datos["empresas"][ISA]["historico"]["CAPEX"][-1], 1706.308, places=3)
        self.assertIn("no reconciliados", datos["empresas"][ISA]["calidad_historico_por_anio"]["2023"])

    def test_historico_curado_cumple_identidades(self):
        h = pd.DataFrame(L.EMPRESAS[ISA]["historico"]).set_index("Año")
        tax = L.EMPRESAS[ISA]["params"]["tax"]
        np.testing.assert_allclose(h["NOPAT"], h["EBIT"] * (1 - tax), atol=1e-3)
        np.testing.assert_allclose(h["FCFF"], h["NOPAT"] + h["Depreciacion"] - h["CAPEX"] - h["Delta_NWC"], atol=1e-3)

    def test_kd_por_regla(self):
        rf = L.CAPM_POR_MERCADO["CO"].get("rf_bruto", L.CAPM_POR_MERCADO["CO"]["rf"])  # Kd sobre el TES completo
        self.assertAlmostEqual(L.EMPRESAS[ISA]["params"]["kd"], rf + 0.01)
        self.assertAlmostEqual(L.EMPRESAS["ECOPETROL"]["params"]["kd"], rf + 0.02)
        self.assertIn("spread", L.EMPRESAS[ISA]["params"]["kd_fuente"])


class TestOrdenDeFuentes(BaseFuentes):
    def test_yahoo_primero_para_precargadas(self):
        parches = self._con_yahoo({"ISA.CL": _isa_yahoo()})
        for p in parches:
            p.start()
        try:
            est = L.preparar_empresa(ISA)
            self.assertEqual(est["fuente"], "yahoo", est)
            self.assertIn(ISA, L.EMPRESAS_RUNTIME)
            self.assertIs(L.resolver_empresa(ISA), L.EMPRESAS_RUNTIME[ISA])
            p = L.params_empresa(ISA)
            self.assertAlmostEqual(p["deuda_neta"], 30500.0, places=3)  # (34,2 − 3,7) billones = 30.500 miles de millones, desde Yahoo
            self.assertEqual(p["nci"], L.EMPRESAS[ISA]["params"]["nci"])  # completado con el catálogo
            df, msg = L.cargar_y_limpiar_excel(None, ISA, True)
            self.assertIn("sesión", msg)
            self.assertAlmostEqual(float(df.loc[2025, "Ingresos"]), 16000.0)  # dato de Yahoo, no del catálogo
            self.assertEqual(L.estado_fuente_empresa(ISA)["fuente"], "yahoo")
        finally:
            for p in parches:
                p.stop()

    def test_respaldo_curado_si_yahoo_falla(self):
        parches = self._con_yahoo({})
        for p in parches:
            p.start()
        try:
            est = L.preparar_empresa(ISA)
            self.assertEqual(est["fuente"], "curado")
            self.assertIn("Respaldo curado", est["detalle"])
            df, _ = L.cargar_y_limpiar_excel(None, ISA, True)
            self.assertEqual(list(df.index), [2023, 2024, 2025])
        finally:
            for p in parches:
                p.stop()

    def test_sin_cotizacion_ni_serie_exige_eeff(self):
        est = L.preparar_empresa(EPM)
        self.assertEqual(est["fuente"], "sin_datos")
        with self.assertRaises(ValueError) as ctx:
            L.cargar_y_limpiar_excel(None, EPM, True)
        self.assertIn("Carga sus estados financieros", str(ctx.exception))

    def test_archivo_del_usuario_tiene_prioridad(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        pd.DataFrame({
            "Año": [2023, 2024, 2025], "Ingresos": [100.0, 110.0, 120.0], "EBITDA": [40.0, 44.0, 48.0],
            "EBIT": [30.0, 33.0, 36.0], "CAPEX": [10.0, 11.0, 12.0], "NWC": [5.0, 5.5, 6.0],
        }).to_csv(tmp.name, index=False)
        tmp.close()
        try:
            df, msg = L.cargar_y_limpiar_excel(tmp.name, EPM, True)
            self.assertEqual(float(df.loc[2025, "Ingresos"]), 120.0)
        finally:
            os.unlink(tmp.name)

    def test_estado_de_fuente_por_sesion(self):
        L.preparar_empresa(EPM)
        self.assertIsNotNone(L.estado_fuente_empresa(EPM))
        L.vincular_estado_sesion({})
        self.assertIsNone(L.estado_fuente_empresa(EPM))


if __name__ == "__main__":
    unittest.main(verbosity=2)
