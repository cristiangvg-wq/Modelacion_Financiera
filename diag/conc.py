import json, os, sys, traceback
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C, comite_ia as CI
CAT = ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"]
TK = ["MINEROS.CL", "AAPL", "MSFT", "NVDA", "PLTR", "KO", "WMT", "PG", "GIS", "HSY"]
IA = set(sys.argv[1:])
res = {}
def correr(nombre):
    m = C.correr(nombre)["4"]; m = L.metricas_valoracion_sesion(nombre) or m
    c = m.get("conciliacion_mercado") or {}
    o = {"vps": m.get("vps_modelo"), "precio": m.get("precio_mercado"), "upside": m.get("upside"),
         "conc": {k: v for k, v in c.items() if k != "inverso"}, "inv": c.get("inverso")}
    if nombre.split(" ")[0] in IA or any(t in nombre for t in IA):
        try:
            r = CI.generar_dictamen(nombre, api_key=os.environ.get("GEMINI_API_KEY"), proveedor="gemini", metricas=m, buscar_web=True)
            o["ia"] = {"ok": r["ok"], "error": r.get("error"), "rec": (r.get("dictamen") or {}).get("recomendacion"),
                       "conc": (r.get("dictamen") or {}).get("conciliacion_mercado"),
                       "warnings": (r.get("auditoria") or {}).get("warnings"), "errors": (r.get("auditoria") or {}).get("errors")}
        except Exception:
            o["ia"] = traceback.format_exc()[-800:]
    return o
for n in CAT:
    L.vincular_estado_sesion({}); L.preparar_empresa(n)
    try: res[n] = correr(n)
    except Exception: res[n] = {"error": traceback.format_exc()[-800:]}
for tk in TK:
    L.vincular_estado_sesion({})
    try:
        ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk); res[tk] = correr(nombre)
    except Exception: res[tk] = {"error": traceback.format_exc()[-800:]}
print(json.dumps(res, ensure_ascii=False, default=str))
