"""Prueba de humo del comité IA contra la API REAL de Gemini (requiere GEMINI_API_KEY y red).

    GEMINI_API_KEY=... python scripts/smoke_gemini_comite.py [EMPRESA]

Corre las pestañas 2, 4 y 6 de la empresa (por defecto ISA), luego el comité en dos pasos
con búsqueda web, e imprime: modelo de Gemini usado, si la búsqueda devolvió fuentes, hechos
aceptados y descartados (con motivo), anclas y rango, y el veredicto de la auditoría del
dictamen. Termina con código 1 si algo crítico falla.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comite_ia as CI  # noqa: E402
import contraste_mercado_real as C  # noqa: E402
import modelacion_logic as L  # noqa: E402


def main(empresa):
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("Falta GEMINI_API_KEY.")
        return 1
    L.vincular_estado_sesion({})
    C.correr(empresa)
    L.tab6_comparacion_sectorial(empresa)
    m = L.metricas_valoracion_sesion(empresa)
    res = CI.generar_dictamen(empresa, proveedor="gemini", metricas=m, buscar_web=True, forzar=True)
    alm = L._almacen_estado()
    print(f"Modelo Gemini usado: {alm.get('_ia_ultimo_modelo')}")
    print(f"Modelos sin búsqueda: {list((alm.get('_ia_busqueda_no_soportada') or {}).keys())}")
    print(f"Modelos sin esquema JSON: {list((alm.get('_ia_esquema_no_soportado') or {}).keys())}")
    b = res.get("busqueda") or {}
    print(f"Búsqueda web: usada={b.get('usada')} consultas={b.get('consultas')} error={b.get('error')}")
    print(f"Fuentes consultadas: {len(res['fuentes'])}")
    web = [h for h in res["hechos"] if h.get("origen") == "web"]
    print(f"Hechos web aceptados: {len(web)} · descartados: {len(res['descartados'])}")
    for h in web:
        print(f"  {h['id']} {h['fecha']} {h['fuente']}: {h['hecho'][:90]}")
    for h in res["descartados"]:
        print(f"  ✗ {h.get('motivo_descarte')}: {h['hecho'][:80]}")
    print(f"Anclas: {[(a['id'], round(a['vps_precio'] or 0, 2)) for a in res['anclas'].get('anclas', [])]} rango={res['anclas'].get('rango')}")
    aud = res.get("auditoria") or {}
    print(f"Dictamen ok={res['ok']} errores={aud.get('errors')} advertencias={aud.get('warnings')}")
    if res["ok"]:
        d = res["dictamen"]
        print(f"→ {d['recomendacion']} · objetivo {d.get('precio_objetivo')} · convicción {d.get('conviccion')}")
    criticos = [not res["ok"], b.get("solicitada") and not b.get("usada")]
    return 1 if any(criticos) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "ISA — Interconexión Eléctrica"))
