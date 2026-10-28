import json, os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C
out = {"tasas": L.TASAS_MERCADO, "avisos": L.tasas_vigencia(), "capm_us_rf": L.CAPM_POR_MERCADO["US"]["rf"],
       "capm_co": {k: L.CAPM_POR_MERCADO["CO"].get(k) for k in ("rf", "rf_bruto", "erp")}}
# GEB: suma de partes sugerida y efecto
n = "GEB — Grupo Energía Bogotá"
L.vincular_estado_sesion({}); L.preparar_empresa(n)
p = L.params_empresa(n); m0 = C.correr(n)["4"]; m0 = L.metricas_valoracion_sesion(n) or m0
filas = L.participadas_sugeridas(n, p)
ke = m0["ke_calc"]
r = L.suma_de_partes(filas, ke)
out["geb"] = {"ingreso_participadas": p.get("ingreso_participadas"), "asociados_actual": p.get("asociados"), "ke": ke,
              "filas": filas, "sdp": r, "vps_base": m0["vps_modelo"], "causa_base": (m0.get("conciliacion_mercado") or {}).get("causa")}
# variante con g = 6 % y ROE de Enel Colombia ~ supuesto ilustrativo
# ISA: corrección del CAPEX 2025 a 6.300 (oficial) y efecto
n = "ISA — Interconexión Eléctrica"
L.vincular_estado_sesion({}); L.preparar_empresa(n)
base, msg = L._cargar_y_limpiar_excel_impl(None, n, True)
m1 = C.correr(n)["4"]; m1 = L.metricas_valoracion_sesion(n) or m1
ed = base[L.HISTORICO_EDITABLE].copy(); ed.loc[max(ed.index), "CAPEX"] = 6300.0
L.fijar_historico_usuario(n, ed, base, fuente_original=msg.split(".")[0], attrs=dict(base.attrs))
L.reset_resultados_sesion(n)
m2 = C.correr(n)["4"]; m2 = L.metricas_valoracion_sesion(n) or m2
out["isa_capex"] = {"vps_antes": m1["vps_modelo"], "vps_despues": m2["vps_modelo"], "fcff_antes": m1["fcff_proy"], "fcff_despues": m2["fcff_proy"],
                    "capex_hist": [float(x) for x in base["CAPEX"].values]}
print(json.dumps(out, ensure_ascii=False, default=str))
