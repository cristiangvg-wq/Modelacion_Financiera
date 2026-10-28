import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L
L.vincular_estado_sesion({})
n = "ISA — Interconexión Eléctrica"
L.preparar_empresa(n)
p = L.params_empresa(n); rf, erp, crp, gmax = L._capm_para_ui(p); H = L.horizonte_recomendado(n)
base = dict(H=H, de=p["de_ratio"], kd=p["kd"], tax=p["tax"], g=p["g"], cx=0.0, bu=p["beta_u"], rf=rf, erp=erp, crp=crp,
            ex=p.get("exit_multiple", 8.0), gmax=gmax, mid=True)
print("BASE", base)
def run(**k):
    a = dict(base); a.update(k)
    L.reset_resultados_sesion(n)
    L.tab4_recomendacion(n, None, a["H"], a["de"], a["kd"], a["tax"], a["g"], a["cx"], a["bu"], p["capital_invertido"], p["deuda_neta"],
                         a["rf"], a["erp"], a["crp"], True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0),
                         p.get("asociados", 0), p.get("acciones"), a["ex"], a["mid"], a["gmax"])
    m = (L.RESULTADOS_SESION["tabs"].get("4") or {}).get("metricas") or {}
    return m.get("vps_modelo"), m.get("upside")
casos = [("base", {}), ("g=0.08", dict(g=0.08)), ("g=0.07", dict(g=0.07)), ("gmax=0.08,g=0.08", dict(g=0.08, gmax=0.08)),
         ("H=10", dict(H=10)), ("H=3", dict(H=3)), ("de=0", dict(de=0.0)), ("de=2", dict(de=2.0)), ("de=5", dict(de=5.0)),
         ("kd=0.08", dict(kd=0.08)), ("tax=0.35", dict(tax=0.35)), ("tax=0", dict(tax=0.0)), ("bu=0", dict(bu=0.0)),
         ("rf=0.0943", dict(rf=0.0943)), ("rf=0.02", dict(rf=0.02)), ("erp=0.03", dict(erp=0.03)), ("crp=0.03", dict(crp=0.03)),
         ("ex=0", dict(ex=0.0)), ("ex=12", dict(ex=12.0)), ("mid=False", dict(mid=False)), ("cx=500", dict(cx=500.0))]
for nom, k in casos:
    try:
        v, u = run(**k); print(f"{nom:20s} vps={v} upside={u}")
    except Exception as e:
        print(nom, "ERR", e)
