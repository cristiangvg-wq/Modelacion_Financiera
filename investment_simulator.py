"""Simulación transparente de una inversión en una acción bajo escenarios editables.
No es un pronóstico: los resultados dependen de supuestos introducidos por el usuario.
"""
from __future__ import annotations

import math
from typing import Mapping

SUPPORTED_CURRENCIES = {"COP", "USD"}


def simular_inversion(
    *,
    capital: float,
    moneda_capital: str,
    moneda_activo: str,
    tasa_cop_usd: float,
    precio_actual: float,
    horizonte: int,
    escenarios: Mapping[str, float],
    dividend_yield: float = 0.0,
    costo_compra: float = 0.0,
    costo_venta: float = 0.0,
    impuesto_dividendos: float = 0.0,
) -> dict:
    """Calcula acciones enteras, efectivo residual y escenarios de valor final.

    tasa_cop_usd expresa COP por 1 USD. Si las monedas difieren, se mantiene
    constante durante el horizonte. Los dividendos no se reinvierten.
    """
    capital = float(capital)
    precio_actual = float(precio_actual)
    fx = float(tasa_cop_usd)
    horizonte = int(horizonte)
    moneda_capital = str(moneda_capital).upper()
    moneda_activo = str(moneda_activo).upper()

    for name, value in (
        ("capital", capital), ("precio_actual", precio_actual), ("tasa_cop_usd", fx),
        ("dividend_yield", float(dividend_yield)), ("costo_compra", float(costo_compra)),
        ("costo_venta", float(costo_venta)), ("impuesto_dividendos", float(impuesto_dividendos)),
    ):
        if not math.isfinite(value):
            raise ValueError(f"{name} debe ser un número finito.")
    if capital <= 0:
        raise ValueError("El capital debe ser mayor que cero.")
    if precio_actual <= 0:
        raise ValueError("El precio de la acción debe ser mayor que cero.")
    if horizonte < 1 or horizonte > 50:
        raise ValueError("El horizonte debe estar entre 1 y 50 años.")
    if moneda_capital not in SUPPORTED_CURRENCIES or moneda_activo not in SUPPORTED_CURRENCIES:
        raise ValueError("Solo se admiten inversiones en COP o USD. La moneda del activo debe confirmarse.")
    if fx <= 0:
        raise ValueError("La tasa COP/USD debe ser mayor que cero.")
    if not 0 <= dividend_yield <= 1:
        raise ValueError("El rendimiento por dividendos debe estar entre 0 y 100%.")
    if not 0 <= costo_compra < 1 or not 0 <= costo_venta < 1:
        raise ValueError("Los costos de compra y venta deben estar entre 0% y menos de 100%.")
    if not 0 <= impuesto_dividendos <= 1:
        raise ValueError("El impuesto sobre dividendos debe estar entre 0 y 100%.")
    if not escenarios:
        raise ValueError("Define al menos un escenario.")
    for name, growth in escenarios.items():
        if not str(name).strip():
            raise ValueError("Los escenarios deben tener nombre.")
        if not math.isfinite(float(growth)) or not -0.90 <= float(growth) <= 1.0:
            raise ValueError("Cada valorización anual debe estar entre -90% y 100%.")

    if moneda_capital == moneda_activo:
        capital_activo = capital
    elif moneda_capital == "COP" and moneda_activo == "USD":
        capital_activo = capital / fx
    else:
        capital_activo = capital * fx

    acciones = int(math.floor(capital_activo / (precio_actual * (1.0 + costo_compra))))
    efectivo_residual = capital_activo - acciones * precio_actual * (1.0 + costo_compra)
    if acciones < 0 or efectivo_residual < -1e-8:
        raise ValueError("No fue posible calcular la compra con estos datos.")
    efectivo_residual = max(0.0, efectivo_residual)

    resultados = {}
    trayectoria = []
    for nombre, growth_raw in escenarios.items():
        growth = float(growth_raw)
        annual_dividend_net = acciones * precio_actual * dividend_yield * (1.0 - impuesto_dividendos)
        values = []
        for year in range(horizonte + 1):
            market_value = acciones * precio_actual * ((1.0 + growth) ** year)
            dividends = annual_dividend_net * year
            liquidation = market_value * (1.0 - costo_venta) + dividends + efectivo_residual
            if moneda_capital == moneda_activo:
                value_in_capital = liquidation
            elif moneda_capital == "COP" and moneda_activo == "USD":
                value_in_capital = liquidation * fx
            else:
                value_in_capital = liquidation / fx
            values.append(float(value_in_capital))
            trayectoria.append({"Año": year, nombre: float(value_in_capital)})
        final_value = values[-1]
        gain = final_value - capital
        annualized = (final_value / capital) ** (1.0 / horizonte) - 1.0 if final_value > 0 else -1.0
        resultados[nombre] = {
            "valor_final": final_value,
            "ganancia_neta": gain,
            "rentabilidad_total": gain / capital,
            "rentabilidad_anualizada": annualized,
            "dividendos_netos": annual_dividend_net * horizonte,
            "valorizacion_anual": growth,
        }

    trajectory_by_year = {year: {"Año": year} for year in range(horizonte + 1)}
    for row in trayectoria:
        year = row["Año"]
        for key, value in row.items():
            if key != "Año":
                trajectory_by_year[year][key] = value
    return {
        "resumen": {
            "acciones": acciones,
            "efectivo_residual": efectivo_residual,
            "capital_convertido": capital_activo,
            "moneda_activo": moneda_activo,
            "moneda_capital": moneda_capital,
            "escenarios": resultados,
        },
        "trayectoria": [trajectory_by_year[year] for year in range(horizonte + 1)],
    }
