"""Regresiones para el control de calidad de la salida del comité IA."""
import unittest

import modelacion_logic as L


class TestAuditoriaComiteIA(unittest.TestCase):
    def test_detecta_eco_del_prompt(self):
        respuesta = (
            "CONTEXTO DE ENTRADA\nActúa como un Comité Interdisciplinario "
            "INSTRUCCIONES Y FORMATO DE SALIDA"
        )
        audit = L.auditar_respuesta_comite_ia(respuesta, {})
        self.assertFalse(audit["ok"])
        self.assertIn("La IA devolvió/ecoó el prompt", audit["errors"])

    def test_acepta_informe_completo_sin_plantillas(self):
        respuesta = """## 1. DELIBERACIÓN DEL COMITÉ INTERDISCIPLINARIO
- CFO: el resultado depende de los supuestos de flujo y descuento.
- Analista de Mercado: faltan comparables verificados.
- CRO: debe probarse la sensibilidad.

## 2. ANÁLISIS DE BRECHA
La brecha no puede cuantificarse con los datos disponibles.

## 3. DECISIÓN FINAL DE INVERSIÓN
- RECOMENDACIÓN FINAL: INVERTIR CONDICIONALMENTE
- PUNTAJE DE VIABILIDAD: 5/10
- PRECIO OBJETIVO DE CONSENSO: N/D
- TESIS Y JUSTIFICACIÓN ESTRATÉGICA: validar supuestos antes de decidir.

## 4. FACTORES CRÍTICOS Y PUNTOS DE MONITOREO
1. WACC y crecimiento terminal.
2. Calidad y fecha de los datos."""
        audit = L.auditar_respuesta_comite_ia(respuesta, {"roic_calc": None})
        self.assertTrue(audit["ok"], audit["errors"])


if __name__ == "__main__":
    unittest.main()
