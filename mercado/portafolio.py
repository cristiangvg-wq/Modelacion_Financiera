"""Precios de varios activos → estadísticas SEMANALES para el optimizador existente.

Hallazgo: la pestaña de portafolios usa rendimientos diarios y descarta los días sin cotización
común. Con acciones de la BVC (negociación poco frecuente, festivos distintos a NYSE) eso produce
correlaciones y volatilidades sesgadas a la baja (efecto Epps / negociación no sincrónica) y
sobrepondera activos colombianos en la cartera de mínima varianza. El cierre semanal mitiga el
problema sin cambiar el motor: se reutiliza portfolio_engine.preparar_estadisticas con 52
periodos por año.
"""
from __future__ import annotations

import pandas as pd

import portfolio_engine as P

from .yahoo_cliente import YahooCliente


def precios_cierre(cliente: YahooCliente, tickers: list[str], periodo: str = "5y") -> tuple[pd.DataFrame, dict]:
    """Cierres ajustados por símbolo (una instantánea por activo) y moneda declarada por Yahoo."""
    series, monedas, huellas = {}, {}, {}
    for tk in dict.fromkeys(t.strip().upper() for t in tickers if t.strip()):
        s = cliente.descargar(tk, periodo_precios=periodo)
        if s.precios.empty or "Close" not in s.precios:
            raise ValueError(f"Sin precios para {tk}: {s.errores.get('precios', 'vacío')}")
        series[tk] = s.precios["Close"]
        monedas[tk] = str(s.info.get("currency") or "").upper() or None
        huellas[tk] = s.huella
    return pd.DataFrame(series).sort_index(), {"monedas": monedas, "huellas": huellas}


def estadisticas_semanales(precios: pd.DataFrame, min_semanas: int = 104, contraccion: bool = True):
    """(mu, cov) anualizados con cierres del viernes. Exige ≥ 2 años de semanas comunes por defecto."""
    semanal = precios.resample("W-FRI").last()
    return P.preparar_estadisticas(semanal, periodos_anuales=52, min_observaciones=min_semanas,
                                   contraccion=contraccion)
