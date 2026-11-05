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


def _fallo_transitorio_o_cuota(error):
    """Identifica bloqueos del proveedor que impiden evaluar el caso."""
    texto = str(error or "").lower()
    return any(token in texto for token in (
        "http 429", "resource_exhausted", "quota exceeded", "quota de gemini",
        "http 500", "http 502", "http 503", "http 504",
        "service unavailable", "high demand",
    ))


def evaluar_vivo(banco, proveedor, api_key=None):
    L.vincular_estado_sesion({})
    filas, puntos, total, inconclusos = [], 0, 0, 0
    for c in banco["casos"]:
        t0 = time.monotonic()
        r = CI.razonar_dictamen(c["metricas"], _anclas(c), c["hechos"], api_key=api_key, proveedor=proveedor)
        d = r.get("dictamen") or {}
        aud = r.get("auditoria") or {"ok": False, "errors": [r.get("error")], "warnings": []}
        errores = aud.get("errors") or []
        detalle_error = " | ".join([str(r.get("error") or ""), *(str(x) for x in errores)])
        seg = time.monotonic() - t0
        if _fallo_transitorio_o_cuota(detalle_error):
            inconclusos += 1
            filas.append((c["id"], None, None, 0, 0, seg, errores or [r.get("error")], "INCONCLUSO"))
            continue

        rec = d.get("recomendacion")
        checks = {
            "json_valido": isinstance(r.get("dictamen"), dict),
            "auditoria_ok": bool(aud.get("ok")),
            "recomendacion_permitida": rec in CI.VOCAB and rec not in c.get("prohibidas", []),
            "sin_reintento": r.get("intentos") == 1,
            "cita_hechos": len((d.get("contexto_mercado") or {}).get("hechos_usados") or []) >= min(2, len(c["hechos"])),
        }
        p = sum(checks.values())
        puntos += p
        total += len(checks)
        filas.append((c["id"], rec, d.get("precio_objetivo"), p, len(checks), seg, errores, "EVALUADO"))

    print(f"{'caso':24s} {'estado':12s} {'rec':9s} {'objetivo':>12s} puntaje  seg  errores")
    for cid, rec, po, p, n, seg, errs, estado in filas:
        puntaje = f"{p}/{n}" if n else "N/A"
        print(f"{cid:24s} {estado:12s} {str(rec):9s} {str(po):>12s} {puntaje:>7s} {seg:4.1f} {'; '.join(errs or [])[:80]}")

    if total:
        print(f"\nPuntaje de casos evaluados: {puntos}/{total} ({puntos / total * 100:.0f} %) · proveedor {proveedor} · {CI.VERSION_COMITE}")
    else:
        print(f"\nNo hubo casos evaluables · proveedor {proveedor} · {CI.VERSION_COMITE}")
    if inconclusos:
        print(f"INCONCLUSO: {inconclusos}/{len(filas)} casos bloqueados por cuota o indisponibilidad del proveedor. No se contabilizan como aprobados.")
        return 2
    if puntos != total:
        print("FALLA: el proveedor respondió, pero uno o más criterios de evaluación no se cumplieron.")
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vivo", metavar="PROVEEDOR", help="gemini | openai | xai")
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()
    banco = cargar()
    sys.exit(evaluar_vivo(banco, args.vivo, args.api_key) if args.vivo else evaluar_offline(banco))
