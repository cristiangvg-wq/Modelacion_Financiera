import json, os, sys, time
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import modelacion_logic as L
import yfinance as yf
out = {}
for tk in ["GEB.CL", "ISA.CL", "ECOPETROL.CL"]:
    f = yf.Ticker(tk).financials
    out[tk] = {r: [float(x)/1e9 if x == x else None for x in f.loc[r].values[:2]] for r in f.index
               if any(k in r for k in ["Interest", "Equity Interest", "Other Non Operating", "Special", "EBIT", "Operating Income", "Pretax"])}
def tiempos(nombre, preparar):
    L.vincular_estado_sesion({})
    t = {}; t0 = time.time()
    if preparar: L.preparar_empresa(nombre)
    t["preparar"] = time.time() - t0
    p = L.params_empresa(nombre); rf, erp, crp, gmax = L._capm_para_ui(p)
    H = L.horizonte_recomendado(nombre); a = (p["de_ratio"], p["kd"], p["tax"], p["g"]); acc = p.get("acciones")
    pasos = [("tab1", lambda: L.tab1_carga_y_pronostico(nombre, None, H, "Drivers + identidad FCFF (recomendado)", p["tax"], True)),
             ("tab2", lambda: L.tab2_simulacion_politicas(nombre, None, H, *a, 0.0, p["beta_u"], p["deuda_neta"], rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax)),
             ("tab3", lambda: L.tab3_auditoria_teorica(nombre, None, H, p["de_ratio"], p["kd"], p["tax"], p["g"], p["beta_u"], p["capital_invertido"], rf, erp, crp, True)),
             ("tab4", lambda: L.tab4_recomendacion(nombre, None, H, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"], rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax)),
             ("tab5", lambda: L.tab5_vpn_tir(nombre, None, H, *a, 0.0, p["beta_u"], p.get("inversion_inicial", 0), rf, erp, crp, True)),
             ("tab6", lambda: L.tab6_comparacion_sectorial(nombre)),
             ("tab7", lambda: L.tab7_informe_ejecutivo(nombre, None, H, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"], p.get("inversion_inicial", 0), rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0), acc, p.get("exit_multiple", 8.0), True, gmax))]
    for k, f in pasos:
        t1 = time.time()
        try: f(); t[k] = round(time.time() - t1, 1)
        except Exception as e: t[k] = f"ERR {str(e)[:150]}"
    return t
out["tiempos_ISA_frio"] = tiempos("ISA — Interconexión Eléctrica", True)
out["tiempos_ISA_caliente"] = tiempos("ISA — Interconexión Eléctrica", True)
L.vincular_estado_sesion({}); t0 = time.time(); ok, html, nombre, _ = L.buscar_y_descargar_empresa("AAPL"); out["descarga_AAPL"] = round(time.time() - t0, 1)
out["tiempos_AAPL"] = tiempos(nombre, False)
print(json.dumps(out, ensure_ascii=False, default=str))
