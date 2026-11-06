"""Capa de datos de mercado (extracción → instantánea → motor).

Separa tres responsabilidades que hoy conviven en modelacion_logic.py:
  1. Extracción con reintentos y caché (yahoo_cliente.YahooCliente).
  2. Instantáneas fechadas y reproducibles de lo descargado (yahoo_cliente.Snapshot).
  3. Ensamble de insumos para el motor existente (pipeline), sin duplicar fórmulas:
     WACC, CAPM y DCF siguen en modelacion_logic.

Nada aquí inventa datos: si una fuente falla, el campo queda en None y se registra el motivo.
"""
