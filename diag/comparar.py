import os, sys, json
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C
CAT = list(L.EMPRESAS)
TK = ["MINEROS.CL", "AAPL", "KO", "MSFT", "PLTR"]
def correr(n, ligada):
    L.REINVERSION_LIGADA_POR_DEFECTO = ligada
    m = C.correr(n)["4"]
    p = L.params_empresa(n)
    df, _ = L.cargar_y_limpiar_excel(None, n, True)
    _dp, meta = L.proyectar_variables_con_meta(df, L.horizonte_recomendado(n), "drivers", p["tax"])
    return {"vps": m.get("vps_modelo"), "up": m.get("upside"), "px": m.get("precio_mercado"), "dec": m.get("decision_modelo"),
            "s2c": meta.get("ventas_capital"), "lig": meta.get("reinversion_ligada"), "roic": m.get("roic_calc"),
            "beta": p.get("beta_u"), "beta_f": p.get("beta_fuente"), "brecha": p.get("beta_brecha_industria"),
            "kd": p.get("kd"), "kd_f": p.get("kd_fuente"), "acc_f": p.get("acciones_fuente"),
            "narr": [(f["nombre"], f["valor"], f["frase"][:80]) for f in meta.get("narrativa") or []]}
out = {}
for n in CAT:
    L.vincular_estado_sesion({}); L.preparar_empresa(n)
    try:
        out[n] = {"ligada": correr(n, True), "mant": correr(n, False)}
    except Exception as e:
        out[n] = {"error": str(e)}
for tk in TK:
    L.vincular_estado_sesion({}); ok, h, n, _ = L.buscar_y_descargar_empresa(tk)
    try:
        out[n] = {"ligada": correr(n, True), "mant": correr(n, False)}
    except Exception as e:
        out[n] = {"error": str(e)}
print(json.dumps(out, ensure_ascii=False, default=str))
