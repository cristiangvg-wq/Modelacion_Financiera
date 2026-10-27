import unittest

from multiples_valuation import valoracion_por_multiplos


class MultiplesValuationTests(unittest.TestCase):
    def test_uses_median_and_calculates_equity_and_per_share(self):
        result = valoracion_por_multiplos(
            ebitda_objetivo=100,
            multiples_comparables=[7, 8, 9],
            deuda_neta=150,
            acciones_millones=10,
        )
        self.assertEqual(result["multiple_mediano"], 8)
        self.assertEqual(result["enterprise_value"], 800)
        self.assertEqual(result["equity_value"], 650)
        self.assertEqual(result["valor_por_accion"], 65000)
        self.assertEqual(result["n_comparables"], 3)

    def test_ignores_nonpositive_and_nonfinite_multiples_but_keeps_large_observed_values(self):
        result = valoracion_por_multiplos(100, [7, 8, 9, 10, -1, float("nan"), 100])
        self.assertEqual(result["multiples_validos"], [7, 8, 9, 10, 100])
        self.assertEqual(result["multiple_mediano"], 9)
        self.assertEqual(result["q1"], 8)
        self.assertEqual(result["q3"], 10)

    def test_accepts_numpy_array_of_comparables(self):
        import numpy as np

        result = valoracion_por_multiplos(100, np.array([7.0, 8.0, 9.0]))
        self.assertEqual(result["multiple_mediano"], 8.0)

    def test_rejects_text_instead_of_comparable_collection(self):
        with self.assertRaisesRegex(ValueError, "no como texto"):
            valoracion_por_multiplos(100, "789")

    def test_rejects_overflow_in_enterprise_value(self):
        with self.assertRaisesRegex(ValueError, "resultados no finitos"):
            valoracion_por_multiplos(1e308, [2.0])

    def test_rejects_overflow_in_value_per_share(self):
        with self.assertRaisesRegex(ValueError, "resultados no finitos"):
            valoracion_por_multiplos(1e300, [1.0], acciones_millones=1e-10)

    def test_negative_net_debt_means_net_cash(self):
        result = valoracion_por_multiplos(10, [5], deuda_neta=-20)
        self.assertEqual(result["enterprise_value"], 50)
        self.assertEqual(result["equity_value"], 70)
        self.assertIsNone(result["valor_por_accion"])

    def test_rejects_missing_comparables(self):
        with self.assertRaisesRegex(ValueError, "al menos un múltiplo"):
            valoracion_por_multiplos(100, [])

    def test_rejects_nonpositive_ebitda(self):
        with self.assertRaisesRegex(ValueError, "EBITDA objetivo"):
            valoracion_por_multiplos(0, [8])


if __name__ == "__main__":
    unittest.main()
