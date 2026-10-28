import json, os, sys, re
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C
out = {}
for n in ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"]:
    L.vincular_estado_sesion({}); L.preparar_empresa(n)
    p = L.params_empresa(n); rf, erp, crp, gmax = L._capm_para_ui(p)
    L.tab1_carga_y_pronostico(n, None, 5, "Drivers + identidad FCFF (recomendado)", p["tax"], True)
    m = C.correr(n)
    t2 = L.RESULTADOS_SESION["tabs"]["2"]["tabla_escenarios"]
    m4 = L.metricas_valoracion_sesion(n) or m["4"]
    w = m4["wacc_calc"]
    html = L.sensibilidad_rapida_ui(n, w, p["g"], 5, p["tax"], p["deuda_neta"], p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0), p.get("acciones"), True, gmax)
    vps_sens = re.findall(r"VPS</div><div[^>]*>([\d,\.]+)", html)
    t4 = {r["Indicador"]: r["Valor"] for r in L.RESULTADOS_SESION["tabs"]["4"]["kpis"]}
    out[n] = {"vps_tab4": m4["vps_modelo"], "vps_sensibilidad": vps_sens, "eq_pes_tab2": t2[0]["Equity Value"],
              "eq_pes_tab4": m4.get("equity_pesimista"), "eq_pes_tab7": (m["7"] or {}).get("equity_pesimista"),
              "fuente_financiera": t4.get("Fuente financiera"), "decision": m4.get("decision_modelo"), "g": p["g"]}
print(json.dumps(out, ensure_ascii=False, default=str))
