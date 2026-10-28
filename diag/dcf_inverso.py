"""DCF inverso de los 6 activos: qué supuestos exige el precio de mercado. Salida JSON por stdout."""
import json, os, sys, time, traceback
import numpy as np
from scipy.optimize import brentq
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L
import contraste_mercado_real as C

CATALOGO = ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"]
TICKERS = ["MINEROS.CL", "AAPL", "PLTR"]


def vps(fcff, w, g, bp, nopat=None, gmax=0.05):
    v = L.valorar_con_bridge(list(fcff), w, g, bp, mid_year=True, g_max_macro=gmax, nopat_final=nopat)
    return float(v["Equity_Value"]) * 1000.0 / float(bp["acciones"])


def resolver(f, lo, hi):
    try:
        a, b = f(lo), f(hi)
        if a * b > 0:
            return None, ("bajo" if a < 0 and b < 0 else "alto")
        return float(brentq(f, lo, hi, xtol=1e-7)), "ok"
    except Exception as e:
        return None, str(e)[:80]


def analizar(nombre):
    m = L.metricas_valoracion_sesion(nombre) or C.correr(nombre)["4"]
    m = L.metricas_valoracion_sesion(nombre) or m
    px = m.get("precio_mercado_moneda_modelo") or (m.get("precio_mercado") if m.get("moneda") == m.get("moneda_precio") else None)
    bp = dict(m["bridge"]); bp["acciones"] = m.get("acciones") or bp.get("acciones")
    fc = [float(x) for x in m["fcff_proy"]]
    w, g, nop = float(m["wacc_calc"]), float(m["g_usada"]), m.get("nopat_final")
    gmax = max(g, 0.05)
    out = {"empresa": nombre, "moneda": m.get("moneda"), "precio": px, "vps_modelo": m["vps_modelo"], "wacc": w, "g": g,
           "ronic": m.get("ronic_terminal"), "roic_obs": m.get("roic_observado"), "fcff": fc, "nopat_final": nop,
           "g_ing_hist": m.get("g_ingresos_historico"), "margen_ebitda": m.get("margen_ebitda_proy"),
           "ev_ebitda_mercado": None, "check_vps": vps(fc, w, g, bp, nop, gmax)}
    try:
        cm = L.contexto_mercado_comite(nombre, m)
        out["ev_ebitda_mercado"] = cm.get("ev_ebitda_mercado"); out["ev_ebitda_modelo"] = cm.get("ev_ebitda_modelo")
        out["objetivo_analistas"] = cm.get("objetivo_analistas")
    except Exception:
        pass
    if not px:
        out["error"] = "sin precio comparable"; return out
    # 1) WACC implícito (todo lo demás igual)
    out["wacc_impl"], out["wacc_impl_motivo"] = resolver(lambda x: vps(fc, x, min(g, x - 0.0105), bp, nop, gmax) - px, g + 0.0106, 0.40)
    # WACC implícito con g fijo pero manteniendo la pendiente correcta
    # 2) Multiplicador de flujos: el mercado espera k veces los flujos del modelo
    out["k_flujos"], out["k_motivo"] = resolver(lambda k: vps([f * k for f in fc], w, g, bp, (nop * k if nop else None), gmax) - px, 0.05, 60.0)
    # 3) Crecimiento implícito del FCFF durante 10 años (desde el FCFF del año 1 del modelo), luego Gordon a g con el WACC del modelo
    base = fc[0] if fc[0] > 0 else (nop or 0) * 0.5
    out["fcff_base_inverso"] = base
    if base > 0:
        def f10(x):
            serie = [base * (1 + x) ** t for t in range(10)]
            return vps(serie, w, g, bp, None, gmax) - px
        out["crec10_impl"], out["crec10_motivo"] = resolver(f10, -0.30, 1.50)
        out["crec10_modelo_equiv"], _ = resolver(lambda x: vps([base * (1 + x) ** t for t in range(10)], w, g, bp, None, gmax) - out["vps_modelo"], -0.30, 1.50)
    # 4) Sensibilidad: VPS con WACC −1/−2 pp
    out["vps_wacc_m1"] = vps(fc, w - 0.01, min(g, w - 0.0205), bp, nop, gmax)
    out["vps_wacc_m2"] = vps(fc, w - 0.02, min(g, w - 0.0305), bp, nop, gmax)
    return out


def main():
    res = []
    for n in CATALOGO:
        L.vincular_estado_sesion({}); L.preparar_empresa(n)
        try:
            C.correr(n); res.append(analizar(n))
        except Exception:
            res.append({"empresa": n, "error": traceback.format_exc()[-1200:]})
    for tk in TICKERS:
        L.vincular_estado_sesion({})
        ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
        try:
            C.correr(nombre); res.append(analizar(nombre))
        except Exception:
            res.append({"empresa": tk, "error": traceback.format_exc()[-1200:]})
    print(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "activos": res}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
