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
    H = L.horizonte_recomendado(nombre)  # 10 años con tres etapas (EE. UU. con consenso); 5 en el resto
    L.reset_resultados_sesion(nombre)
    L.tab2_simulacion_politicas(nombre, None, H, *a, 0.0, p["beta_u"], p["deuda_neta"], rf, erp, crp, True,
                                p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0),
                                p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax)
    L.tab4_recomendacion(nombre, None, H, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"],
                         rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0),
                         p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax)
    L.tab7_informe_ejecutivo(nombre, None, H, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"],
                             p.get("inversion_inicial", 0), rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0),
                             p.get("otros_claims", 0), p.get("asociados", 0), acc,
                             p.get("exit_multiple", 8.0), True, gmax)
    tabs = L.RESULTADOS_SESION["tabs"]
    return {k: (tabs.get(k) or {}).get("metricas") or {} for k in ("2", "4", "7")}


def main(argv):
    L.vincular_estado_sesion({})
    nombres = list(PREDEFINIDAS)
    for n in PREDEFINIDAS:  # igual que la app: datos de Yahoo para el catálogo (respaldo curado si falla)
        try:
            est = L.preparar_empresa(n)
            print(f"[{n}] fuente: {est.get('fuente')}")
        except Exception as e:
            print(f"[{n}] sin descarga ({e}): se usa el catálogo curado")
    for tk in (argv or USUARIO_DEFECTO):
        ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
        if not ok:
            print(f"[{tk}] no descargado: {L._html_a_texto(html, 200)}")
            continue
        print(f"[{tk}] → {nombre} · ticker {L.ticker_canonico_empresa(nombre)}")
        nombres.append(nombre)
    fallos = 0
    print("\nEmpresa | Ticker | Moneda | Precio mercado | VPS modelo | Upside % | WACC | g terminal | Fecha precio | Consistencia 2/4/7")
    for n in nombres:
        m = correr(n)
        m4 = m["4"]
        incons = []
        for k in ("precio_mercado", "val_ev", "val_equity"):
            vals = {t: m[t].get(k) for t in ("2", "4", "7")}
            vs = [v for v in vals.values() if v is not None]
            if vs and max(vs) - min(vs) > 1e-6 * max(1.0, abs(max(vs))):
                incons.append(f"{k}={vals}")
        # Comparar floats con tolerancia relativa: la igualdad exacta puede marcar
        # discrepancias espurias por redondeo aunque ambas pestañas usen los mismos insumos.
        for k in ("vps_modelo", "upside"):
            a, b = m4.get(k), m["7"].get(k)
            if a is None or b is None:
                if a is not b:
                    incons.append(f"{k}: t4={a} t7={b}")
            elif abs(float(a) - float(b)) > 1e-6 * max(1.0, abs(float(a)), abs(float(b))):
                incons.append(f"{k}: t4={a} t7={b}")
        fallos += bool(incons)
        f = lambda v: "N/D" if v is None else f"{v:,.2f}"
        pct = lambda v: "N/D" if v is None else f"{100.0 * float(v):.2f}%"
        print(f"{n[:34]} | {m4.get('ticker')} | {m4.get('moneda')}/{m4.get('moneda_precio')} | "
              f"{f(m4.get('precio_mercado'))} | {f(m4.get('vps_modelo'))} | {f(m4.get('upside'))} | "
              f"WACC {pct(m4.get('wacc_calc'))} | g {pct(m4.get('g_usada', m4.get('g')))} | "
              f"precio-fecha {m4.get('fecha_precio') or 'N/D'} | "
              f"{'OK' if not incons else '; '.join(incons)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
