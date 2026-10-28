"""Efecto de cada ajuste para empresas de EE. UU.: base (5 años, regresión) → tres etapas → beta bottom-up."""
import json, os, sys, time, traceback
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L
import contraste_mercado_real as C

KEYS = ["vps_modelo", "precio_mercado", "upside", "wacc_calc", "ke_calc", "g_usada", "tv_pct_ev", "ronic_terminal",
        "wacc_implicito_mercado", "decision_modelo"]
orig_beta = L.damodaran_beta
orig_cons = L.consenso_ingresos_yahoo
res = {}
for tk in sys.argv[1:] or ["AAPL", "MSFT", "PLTR", "KO", "NVDA", "MINEROS.CL"]:
    out = {}
    try:
        for var in ["base", "nuevo"]:
            L.vincular_estado_sesion({})
            pass
            L.consenso_ingresos_yahoo = (lambda *a, **k: None) if var == "base" else orig_cons
            ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
            if not ok:
                out = {"error": L._html_a_texto(html, 300)}; break
            p = L.params_empresa(nombre)
            m = C.correr(nombre)["4"]
            m = L.metricas_valoracion_sesion(nombre) or m
            out[var] = {k: m.get(k) for k in KEYS}
            out[var].update({"beta_u": p.get("beta_u"), "beta_fuente": p.get("beta_fuente"), "beta_reg": p.get("beta_regresion_u"),
                             "consenso": p.get("consenso_ingresos"), "H": L.horizonte_recomendado(nombre),
                             "asociados": p.get("asociados"), "asociados_fuente": p.get("asociados_fuente"),
                             "inv_fin": p.get("inversiones_financieras_lp"), "beta_ind": p.get("beta_industria_u"), "deuda_neta": p.get("deuda_neta"),
                             "caja": p.get("caja"), "acciones": p.get("acciones")})
            meta = (L.RESULTADOS_SESION.get("tabs", {}).get("4") or {}).get("metricas") or {}
            out[var]["fcff_proy"] = m.get("fcff_proy")
    except Exception:
        out["error"] = traceback.format_exc()[-1500:]
    res[tk] = out
print(json.dumps(res, ensure_ascii=False, default=str))
