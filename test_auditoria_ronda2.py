"""Regresiones de la segunda ronda de auditoría (datos reales de Yahoo, 27-oct-2026)."""
import types
import unittest
from unittest import mock

import pandas as pd

import modelacion_logic as L

AÑOS = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31"), pd.Timestamp("2022-12-31")]


def _df(filas):
    return pd.DataFrame({k: v for k, v in filas.items()}, index=AÑOS).T


class _TickerGEB:
    """Renglones reales de Yahoo para GEB.CL (miles de millones COP × 1e9)."""
    info = {"currency": "COP", "financialCurrency": "COP", "country": "Colombia", "regularMarketPrice": 3000,
            "sharesOutstanding": 9181177000, "marketCap": 27.54e12, "totalDebt": 20.1e12, "totalCash": 2.95e12,
            "beta": 0.15, "longName": "Grupo Energía Bogotá", "sector": "Utilities"}
    financials = _df({k: [x * 1e9 for x in v] for k, v in {
        "Total Revenue": [8015.65, 7971.566, 7953.723, 6874.591],
        "EBIT": [5118.541, 4425.726, 4758.852, 4563.77],
        "Operating Income": [2550.646, 2677.419, 2575.662, 1967.558],
        "EBITDA": [6153.323, 5394.818, 5737.826, 5399.987],
        "Reconciled Depreciation": [1034.8, 969.1, 979.0, 836.2],
        "Other Non Operating Income Expenses": [147.659, 97.72, 59.184, 62.465],
        "Special Income Charges": [140.219, -93.702, -5.862, 83.364],
        "Tax Provision": [566.753, 479.532, 612.039, 576.102],
        "Pretax Income": [3920.154, 3115.467, 3380.409, 3603.088],
    }.items()})
    cashflow = _df({"Capital Expenditure": [-1973.3e9, -1896.3e9, -1351.5e9, -1906.7e9]})
    balance_sheet = _df({k: [x * 1e9 for x in v] for k, v in {
        "Minority Interest": [576.198, 705.178, 700.0, 690.0],
        "Total Liabilities Net Minority Interest": [26382.147, 26307.959, 25000.0, 24000.0],
        "Total Equity Gross Minority Interest": [20119.892, 19866.851, 19000.0, 18000.0],
        "Long Term Equity Investment": [13688.151, 14477.924, 14000.0, 13000.0],
        "Current Assets": [5000.0, 4800.0, 4700.0, 4600.0],
        "Current Liabilities": [4400.0, 4200.0, 4100.0, 4000.0],
        "Cash Cash Equivalents And Short Term Investments": [2947.9, 1583.5, 1500.0, 1400.0],
    }.items()})

    def __init__(self, *_a, **_k):
        pass


class _TickerAAPL(_TickerGEB):
    info = {"currency": "USD", "financialCurrency": "USD", "country": "United States", "regularMarketPrice": 347.1}
    balance_sheet = _df({k: [x * 1e9 for x in v] for k, v in {
        "Total Liabilities Net Minority Interest": [285.508, 308.03, 290.0, 302.0],
        "Total Equity Gross Minority Interest": [73.733, 56.95, 62.1, 50.7],
        "Stockholders Equity": [73.733, 56.95, 62.1, 50.7],
    }.items()})


class TestEbitOperativo(unittest.TestCase):
    def test_usa_utilidad_operativa_y_estima_participadas(self):
        fake_yf = types.SimpleNamespace(Ticker=_TickerGEB)
        with mock.patch.object(L, "yf", fake_yf), mock.patch.object(L, "HAS_YF", True):
            df, msg = L.descargar_financieros_yfinance("GEB.CL")
        self.assertIsNotNone(df, msg)
        self.assertAlmostEqual(float(df.loc[2025, "EBIT"]), 2550.646, places=2)          # no 5.118
        self.assertAlmostEqual(float(df.loc[2025, "EBITDA"]), 2550.646 + 1034.8, places=2)
        self.assertEqual(df.attrs["ebit_fuente"], "Operating Income (Yahoo)")
        self.assertAlmostEqual(df.attrs["ingreso_participadas"], 5118.541 - 2550.646 - 147.659 - 140.219, places=2)

    def test_asociadas_valoradas_por_su_utilidad_capitalizada(self):
        df = pd.DataFrame({"Ingresos": [7953.7, 7971.6, 8015.6], "EBIT": [2575.7, 2677.4, 2550.6]}, index=[2023, 2024, 2025])
        df.attrs["ingreso_participadas"] = 2280.0
        info = dict(_TickerGEB.info, _balance_sheet=_TickerGEB.balance_sheet)
        p = L.derivar_params_desde_cero(df, info=info, ticker_yf="GEB.CL")
        self.assertGreater(p["asociados"], p["asociados_libros"])  # 2.280 / Ke > 13.688 en libros
        self.assertIn("Ke", p["asociados_fuente"])


class TestInteresMinoritario(unittest.TestCase):
    def test_pasivos_netos_de_minoritarios_no_son_nci(self):
        df = pd.DataFrame({"Ingresos": [383.3, 391.0, 416.2], "EBIT": [114.3, 123.2, 133.0]}, index=[2023, 2024, 2025])
        info = dict(_TickerAAPL.info, _balance_sheet=_TickerAAPL.balance_sheet)
        p = L.derivar_params_desde_cero(df, info=info, ticker_yf="AAPL")
        self.assertLess(p["nci"], 1.0)  # antes: 285,5 (pasivos totales de Apple restados como NCI)


class TestMultiplosSectoriales(unittest.TestCase):
    def test_multiplo_de_yahoo_se_etiqueta_como_tal(self):
        emp = {"historico": {"Año": [2023, 2024, 2025], "Ingresos": [10.0, 11.0, 12.0], "EBITDA": [3.0, 3.3, 3.6],
                             "EBIT": [2.0, 2.2, 2.4], "FCFF": [1.0, 1.1, 1.2]},
               "params": {"tax": 0.25, "de_ratio": 0.5, "beta_u": 0.8, "kd": 0.06, "capital_invertido": 20.0},
               "ticker_yf": "DUK", "moneda": "USD", "pais": "United States"}
        mkt = {"ok": True, "precio": 100.0, "market_cap": 80e9, "enterprise_to_ebitda": 12.5}
        with mock.patch.object(L, "obtener_datos_mercado_bvc", return_value=mkt):
            fila, _corto, _fuente, _live = L._fila_sectorial_desde_emp("Duke — DUK", emp)
        self.assertEqual(fila["EV/EBITDA (x)"], 12.5)
        self.assertTrue(fila["Fuente múltiplo"].startswith("Yahoo"))
        self.assertEqual(fila["Moneda"], "USD")


class TestMateriasPrimasLTM(unittest.TestCase):
    def test_base_ltm_y_margen_del_ultimo_ejercicio(self):
        ing = [0.415, 0.447, 0.539, 0.800]
        df = pd.DataFrame({"Ingresos": ing, "EBITDA": [0.102, 0.113, 0.151, 0.241], "EBIT": [0.1, 0.111, 0.15, 0.24],
                           "Depreciacion": [0.03, 0.03, 0.03, 0.04], "CAPEX": [0.08] * 4, "NWC": [0.02] * 4},
                          index=[2022, 2023, 2024, 2025])
        df.attrs.update({"ciclico": True, "g_convergencia": 0.03})
        proj, meta = L.proyectar_por_drivers(df.copy(), 5, tax=0.37)
        self.assertFalse(meta["base_ltm"])
        self.assertAlmostEqual(meta["margen_ebitda"], 0.241 / 0.800, places=6)  # último ejercicio, no la mediana
        df.attrs["ltm"] = {"Ingresos": 1.0155, "EBITDA": 0.3744}
        proj2, meta2 = L.proyectar_por_drivers(df.copy(), 5, tax=0.37)
        self.assertTrue(meta2["base_ltm"])
        self.assertAlmostEqual(meta2["margen_ebitda"], 0.3744 / 1.0155, places=6)
        self.assertAlmostEqual(float(proj2["Ingresos"].iloc[0]), 1.0155 * 1.03, places=6)
        df.attrs["ltm"] = {"Ingresos": 1015.5, "EBITDA": 374.4}  # unidades cruzadas: se ignora
        _, meta3 = L.proyectar_por_drivers(df.copy(), 5, tax=0.37)
        self.assertFalse(meta3["base_ltm"])


if __name__ == "__main__":
    unittest.main()
