"""Pruebas del motor independiente de portafolios."""
import unittest
import numpy as np
import pandas as pd
from portfolio_engine import preparar_estadisticas, optimizar_portafolio, metricas_portafolio, construir_frontera


class TestPortfolioEngine(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        n = 300
        dates = pd.bdate_range("2024-01-01", periods=n)
        r1 = rng.normal(0.0005, 0.01, n)
        r2 = rng.normal(0.0003, 0.008, n)
        r3 = 0.35 * r1 + rng.normal(0.0002, 0.006, n)
        returns = pd.DataFrame({"AAA": r1, "BBB": r2, "CCC": r3}, index=dates)
        self.prices = 100 * (1 + returns).cumprod()

    def test_preparar_estadisticas(self):
        mu, cov = preparar_estadisticas(self.prices)
        self.assertEqual(len(mu), 3)
        self.assertEqual(cov.shape, (3, 3))
        self.assertTrue(np.isfinite(mu.to_numpy()).all())

    def test_optimizacion_cumple_restricciones(self):
        mu, cov = preparar_estadisticas(self.prices)
        result = optimizar_portafolio(mu, cov, objetivo="min_volatility", peso_maximo=0.6)
        self.assertAlmostEqual(float(result["pesos"].sum()), 1.0, places=6)
        self.assertGreaterEqual(float(result["pesos"].min()), -1e-8)
        self.assertLessEqual(float(result["pesos"].max()), 0.600001)

    def test_limite_inviable_se_rechaza(self):
        mu, cov = preparar_estadisticas(self.prices)
        with self.assertRaises(ValueError):
            optimizar_portafolio(mu, cov, peso_maximo=0.2)

    def test_metricas(self):
        result = metricas_portafolio(
            np.array([0.5, 0.5]), np.array([0.08, 0.06]),
            np.array([[0.04, 0.01], [0.01, 0.02]]), 0.02,
        )
        self.assertAlmostEqual(result["retorno_esperado"], 0.07)
        self.assertGreater(result["volatilidad"], 0)

    def test_metricas_rechaza_pesos_que_no_suman_cien_por_ciento(self):
        with self.assertRaisesRegex(ValueError, "deben sumar 1"):
            metricas_portafolio(
                np.array([0.4, 0.4]), np.array([0.08, 0.06]),
                np.array([[0.04, 0.01], [0.01, 0.02]]), 0.02,
            )

    def test_metricas_rechaza_covarianza_no_simetrica(self):
        with self.assertRaisesRegex(ValueError, "simétrica"):
            metricas_portafolio(
                np.array([0.5, 0.5]), np.array([0.08, 0.06]),
                np.array([[0.04, 0.01], [0.02, 0.02]]), 0.02,
            )

    def test_optimizador_rechaza_covarianza_no_semidefinida_positiva(self):
        mu = pd.Series([0.08, 0.06], index=["AAA", "BBB"])
        cov = pd.DataFrame([[0.01, 0.03], [0.03, 0.01]], index=mu.index, columns=mu.index)
        with self.assertRaisesRegex(ValueError, "semidefinida positiva"):
            optimizar_portafolio(mu, cov, peso_maximo=0.8)

    def test_frontera_devuelve_puntos(self):
        mu, cov = preparar_estadisticas(self.prices)
        frontier = construir_frontera(mu, cov, peso_maximo=0.6, n_puntos=7)
        self.assertFalse(frontier.empty)
        self.assertIn("Volatilidad", frontier.columns)
        self.assertIn("Retorno esperado", frontier.columns)


if __name__ == "__main__":
    unittest.main()
