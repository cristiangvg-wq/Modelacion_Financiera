"""Guarded DCF helpers and market quote reconciliation for audit workflows."""
from __future__ import annotations
from datetime import datetime, timezone
import math
import pandas as pd

PREDEFINED_TICKERS = ("ISA.CL", "EC", "GEB.CL")
DYNAMIC_TICKERS = ("AAPL", "MSFT", "AMZN")
STRESS_TICKERS = PREDEFINED_TICKERS + DYNAMIC_TICKERS

def _finite(value, name):
    try: result = float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"{name} debe ser numérico.") from exc
    if not math.isfinite(result): raise ValueError(f"{name} debe ser finito.")
    return result

def auditar_supuestos(fcff, wacc, g, enterprise_value, pv_terminal):
    warnings = []
    if g >= wacc: warnings.append("CRÍTICO: g debe ser estrictamente menor que WACC.")
    if any(cf < 0 for cf in fcff): warnings.append("REVISAR: FCFF negativo; valida CAPEX, capital de trabajo y etapa de crecimiento.")
    if fcff[-1] <= 0: warnings.append("CRÍTICO: FCFF terminal no positivo; revisa el valor terminal.")
    if enterprise_value and pv_terminal / enterprise_value > .75: warnings.append("ALTO: más del 75% del EV procede del valor terminal; alta sensibilidad a WACC y g.")
    if wacc <= 0: warnings.append("CRÍTICO: WACC no positivo; revisa coste de capital y coherencia nominal/real.")
    return warnings

def valorar_dcf(fcff, wacc, g, deuda_neta=0.0, acciones_diluidas=None, precio_mercado=None, horizonte_tir=5):
    """Annual FCFF Gordon DCF. All monetary inputs must share units/currency."""
    flows = [_finite(x, "FCFF") for x in fcff]
    if not flows: raise ValueError("Se requiere al menos un FCFF proyectado.")
    wacc, g, debt = _finite(wacc, "WACC"), _finite(g, "g"), _finite(deuda_neta, "deuda neta")
    if wacc <= -1: raise ValueError("WACC debe ser mayor que -100%.")
    if g < -1: raise ValueError("g debe ser mayor que -100%.")
    if g >= wacc: raise ValueError("El crecimiento perpetuo g debe ser menor que WACC (WACC - g > 0).")
    if not isinstance(horizonte_tir, int) or horizonte_tir < 1: raise ValueError("El horizonte de TIR debe ser un entero positivo.")
    pv_fcff = sum(cf / (1 + wacc) ** year for year, cf in enumerate(flows, 1))
    tv = flows[-1] * (1 + g) / (wacc - g)
    pv_tv = tv / (1 + wacc) ** len(flows)
    ev, equity = pv_fcff + pv_tv, pv_fcff + pv_tv - debt
    if not all(math.isfinite(x) for x in (pv_fcff, tv, pv_tv, ev, equity)): raise ValueError("Valoración no finita; revisa unidades y supuestos.")
    per_share = None
    if acciones_diluidas not in (None, ""):
        shares = _finite(acciones_diluidas, "acciones diluidas")
        if shares <= 0: raise ValueError("Las acciones diluidas deben ser positivas.")
        per_share = equity / shares
    upside = irr = None
    if precio_mercado not in (None, ""):
        price = _finite(precio_mercado, "precio de mercado")
        if price <= 0: raise ValueError("El precio de mercado debe ser positivo.")
        if per_share is not None:
            upside = per_share / price - 1
            if per_share > 0: irr = (per_share / price) ** (1 / horizonte_tir) - 1
    return {"pv_fcff": pv_fcff, "valor_terminal": tv, "pv_valor_terminal": pv_tv,
            "enterprise_value": ev, "equity_value": equity, "valor_intrinseco_accion": per_share,
            "precio_mercado": None if precio_mercado in (None, "") else float(precio_mercado),
            "upside_downside": upside, "tir_implicita_anual": irr, "wacc": wacc, "g": g,
            "peso_terminal_ev": pv_tv / ev if ev else None,
            "alertas": auditar_supuestos(flows, wacc, g, ev, pv_tv)}

def descargar_precios(tickers=STRESS_TICKERS):
    """Fetch recent Yahoo Finance closes; unavailable symbols are explicitly flagged."""
    try: import yfinance as yf
    except ImportError as exc: raise RuntimeError("Instala yfinance desde requirements.txt.") from exc
    rows = []
    for ticker in tickers:
        row = {"ticker": ticker, "precio": None, "moneda": None, "fecha": None, "estado": "SIN DATOS"}
        try:
            instrument = yf.Ticker(ticker)
            hist = instrument.history(period="5d", auto_adjust=False)
            if hist is not None and not hist.empty:
                close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
                if not close.empty and float(close.iloc[-1]) > 0:
                    row.update(precio=float(close.iloc[-1]), fecha=str(close.index[-1].date()), estado="OK")
            try: row["moneda"] = instrument.fast_info.get("currency")
            except Exception: pass
        except Exception as exc: row["estado"] = f"ERROR: {type(exc).__name__}"
        rows.append(row)
    result = pd.DataFrame(rows)
    result["consultado_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result

def reconciliar_valuaciones(precios, resultados_modelo):
    out = precios.copy()
    out["valor_intrinseco_accion"] = out["ticker"].map(lambda t: (resultados_modelo.get(t) or {}).get("valor_intrinseco_accion"))
    out["upside_downside"] = out.apply(lambda r: r["valor_intrinseco_accion"] / r["precio"] - 1
        if pd.notna(r.get("valor_intrinseco_accion")) and pd.notna(r.get("precio")) and r["precio"] > 0 else None, axis=1)
    out["validacion_modelo"] = out["valor_intrinseco_accion"].map(lambda x: "MODELO DISPONIBLE" if pd.notna(x) else "PENDIENTE: ejecutar valoración")
    return out
