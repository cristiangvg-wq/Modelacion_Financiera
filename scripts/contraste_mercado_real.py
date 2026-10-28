"""Contraste contra el mercado real (requiere red: Yahoo Finance).

Uso:
    python scripts/contraste_mercado_real.py                 # 3 predefinidas + NUTRESA, AAPL, PLTR
    python scripts/contraste_mercado_real.py PFAVAL MSFT EC  # tickers de usuario propios

Para cada empresa: descarga (si es de usuario), corre pestañas 2, 4 y 7 con los
parámetros por defecto y verifica que precio, EV, Equity, VPS y upside coincidan
entre pestañas. Imprime una tabla y termina con código 1 si hay discrepancias.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import modelacion_logic as L  # noqa: E402

PREDEFINIDAS = ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"]
USUARIO_DEFECTO = ["NUTRESA", "AAPL", "PLTR"]


def correr(nombre):
    p = L.params_empresa(nombre)
    # Mismas anclas CAPM que usa la app (catálogo → CO; Yahoo → mercado del emisor)
    rf, erp, crp, gmax = L._capm_para_ui(p)  # mismo techo macro que usa la app (antes 0,05 fijo)
    a = (p["de_ratio"], p["kd"], p["tax"], p["g"])
    acc = p.get("acciones")
    L.reset_resultados_sesion(nombre)
    L.tab2_simulacion_politicas(nombre, None, 5, *a, 0.0, p["beta_u"], p["deuda_neta"], rf, erp, crp, True,
                                p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0),
                                p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax)
    L.tab4_recomendacion(nombre, None, 5, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"],
                         rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0),
                         p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax)
    L.tab7_informe_ejecutivo(nombre, None, 5, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"],
                             p.get("inversion_inicial", 0), rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0),
                             p.get("otros_claims", 0), p.get("asociados", 0), acc,
                             p.get("exit_multiple", 8.0), True, gmax)
    tabs = L.RESULTADOS_SESION["tabs"]
    return {k: (tabs.get(k) or {}).get("metricas") or {} for k in ("2", "4", "7")}


def main(argv):
    L.vincular_estado_sesion({})
    nombres = list(PREDEFINIDAS)
    for tk in (argv or USUARIO_DEFECTO):
        ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
        if not ok:
            print(f"[{tk}] no descargado: {L._html_a_texto(html, 200)}")
            continue
        print(f"[{tk}] → {nombre} · ticker {L.ticker_canonico_empresa(nombre)}")
        nombres.append(nombre)
    fallos = 0
    print("\nEmpresa | Ticker | Moneda | Precio | VPS | Upside % | Consistencia 2/4/7")
    for n in nombres:
        m = correr(n)
        m4 = m["4"]
        incons = []
        for k in ("precio_mercado", "val_ev", "val_equity"):
            vals = {t: m[t].get(k) for t in ("2", "4", "7")}
            vs = [v for v in vals.values() if v is not None]
            if vs and max(vs) - min(vs) > 1e-6 * max(1.0, abs(max(vs))):
                incons.append(f"{k}={vals}")
        for k in ("vps_modelo", "upside"):
            if m4.get(k) != m["7"].get(k):
                incons.append(f"{k}: t4={m4.get(k)} t7={m['7'].get(k)}")
        fallos += bool(incons)
        f = lambda v: "N/D" if v is None else f"{v:,.2f}"
        print(f"{n[:34]} | {m4.get('ticker')} | {m4.get('moneda')}/{m4.get('moneda_precio')} | "
              f"{f(m4.get('precio_mercado'))} | {f(m4.get('vps_modelo'))} | {f(m4.get('upside'))} | "
              f"{'OK' if not incons else '; '.join(incons)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
