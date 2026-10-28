"""Evalúa el comité IA contra el banco de casos (evaluacion_comite/casos.json).

Dos modos:
    python scripts/evaluar_comite_ia.py                 # offline: valida las salidas candidatas del banco
    python scripts/evaluar_comite_ia.py --vivo gemini   # llama al proveedor real con cada caso (requiere API key)

En modo vivo, por cada caso se ejecuta el paso 2 (dictamen JSON) con las métricas, anclas y
hechos del caso y se mide: JSON válido y aprobado por validar_dictamen, recomendación no
prohibida, precio objetivo dentro de las anclas, hechos citados y advertencias. Úsalo antes y
después de cambiar el prompt: un retroceso aparece como una caída del puntaje.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comite_ia as CI  # noqa: E402
import modelacion_logic as L  # noqa: E402

RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evaluacion_comite", "casos.json")


def cargar():
    with open(RUTA, encoding="utf-8") as f:
        return json.load(f)


def _anclas(c):
    a = dict(c["anclas"])
    a["rango"] = tuple(a["rango"]) if a.get("rango") else None
    return a


def evaluar_offline(banco):
    fallos = 0
    for c in banco["casos"]:
        ids = {h["id"] for h in c["hechos"]}
        for s in c["salidas"]:
            d = copy.deepcopy(banco["dictamen_base"])
            d.update(s["parche"])
            a = CI.validar_dictamen(d, c["metricas"], _anclas(c), ids)
            bien = a["ok"] == s["esperado_ok"] and (
                s["esperado_ok"] or any(s.get("error_contiene", "").lower() in e.lower() for e in a["errors"]))
            fallos += not bien
            print(f"{'OK ' if bien else 'FALLA'} {c['id']:24s} {s['etiqueta']:26s} {'; '.join(a['errors'])[:110]}")
    print(f"\n{sum(len(c['salidas']) for c in banco['casos']) - fallos} de {sum(len(c['salidas']) for c in banco['casos'])} veredictos correctos")
    return 1 if fallos else 0


def evaluar_vivo(banco, proveedor, api_key=None):
    L.vincular_estado_sesion({})
    filas, puntos = [], 0
    for c in banco["casos"]:
        t0 = time.monotonic()
        r = CI.razonar_dictamen(c["metricas"], _anclas(c), c["hechos"], api_key=api_key, proveedor=proveedor)
        d, aud = r["dictamen"] or {}, r["auditoria"] or {"ok": False, "errors": [r["error"]], "warnings": []}
        rec = d.get("recomendacion")
        checks = {
            "json_valido": isinstance(r["dictamen"], dict),
            "auditoria_ok": bool(aud.get("ok")),
            "recomendacion_permitida": rec in CI.VOCAB and rec not in c.get("prohibidas", []),
            "sin_reintento": r["intentos"] == 1,
            "cita_hechos": len((d.get("contexto_mercado") or {}).get("hechos_usados") or []) >= min(2, len(c["hechos"])),
        }
        p = sum(checks.values())
        puntos += p
        filas.append((c["id"], rec, d.get("precio_objetivo"), p, len(checks), time.monotonic() - t0, aud.get("errors")))
    print(f"{'caso':24s} {'rec':9s} {'objetivo':>12s} puntaje  seg  errores")
    for cid, rec, po, p, n, seg, errs in filas:
        print(f"{cid:24s} {str(rec):9s} {str(po):>12s} {p}/{n}    {seg:4.1f} {'; '.join(errs or [])[:80]}")
    total = sum(f[4] for f in filas)
    print(f"\nPuntaje total: {puntos}/{total} ({puntos / total * 100:.0f} %) · proveedor {proveedor} · {CI.VERSION_COMITE}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vivo", metavar="PROVEEDOR", help="gemini | openai | xai")
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()
    banco = cargar()
    sys.exit(evaluar_vivo(banco, args.vivo, args.api_key) if args.vivo else evaluar_offline(banco))
