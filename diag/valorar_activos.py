"""Valoración de los 6 activos con datos reales (Yahoo) para la auditoría. Salida: JSON por stdout."""
import json, os, sys, time, traceback
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L
import contraste_mercado_real as C
import comite_ia as CI

CATALOGO = ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá"]
TICKERS = sys.argv[1:] or ["MINEROS.CL", "AAPL", "PLTR"]
PARAMS = ["g", "g_fuente", "tax", "tax_fuente", "tax_efectiva_observada", "kd", "beta_u", "beta_fuente", "de_ratio",
          "deuda_neta", "caja", "nci", "asociados", "otros_claims", "acciones", "acciones_fuente", "rf", "erp", "crp",
          "g_max_macro", "mercado_capm", "capm_fuente", "exit_multiple", "capital_invertido", "moneda", "moneda_precio"]


def r(v, n=4):
    try:
        return round(float(v), n)
    except Exception:
        return v


def evaluar(nombre, via):
    t0 = time.time()
    out = {"empresa": nombre, "via": via}
    try:
        p = L.params_empresa(nombre)
        out["params"] = {k: r(p.get(k)) for k in PARAMS if p.get(k) is not None}
        df, msg, src = L.obtener_datos_financieros_publicos(nombre)
        out["fuente_hist"] = src
        if df is not None:
            out["hist"] = df[[c for c in ["Ingresos", "EBITDA", "EBIT", "Depreciacion", "CAPEX", "NWC", "FCFF"] if c in df.columns]].round(1).reset_index().values.tolist()
        m = C.correr(nombre)["4"]
        try:
            L.tab6_comparacion_sectorial(nombre)
        except Exception as e:
            out["tab6_error"] = str(e)[:200]
        m = L.metricas_valoracion_sesion(nombre) or m
        keys = ["precio_mercado", "moneda", "moneda_precio", "fx_aplicado", "precio_mercado_moneda_modelo", "vps_modelo", "upside",
                "wacc_calc", "ke_calc", "wacc_implicito_mercado", "wacc_paridad_usd", "g_usada", "tv_pct_ev", "roic_calc",
                "val_ev", "val_equity", "equity_pesimista", "margen_ebitda_proy", "g_ingresos_historico", "emisor_ciclico",
                "fuera_de_dominio_crecimiento", "decision_modelo", "vetos_calidad", "alertas_modelo", "fecha_precio",
                "ebitda_ultimo_hist", "ev_ebitda_salida_modelo", "fcff_proy"]
        out["metricas"] = {k: (r(m.get(k)) if not isinstance(m.get(k), (list, dict, str, bool)) else m.get(k)) for k in keys}
        cm = L.contexto_mercado_comite(nombre, m)
        out["mercado"] = {k: cm.get(k) for k in ["precio", "fecha_precio", "rango_52s", "pe", "pe_forward", "ev_ebitda_yahoo",
                                                  "beta_yahoo", "objetivo_analistas", "objetivo_rango", "recomendacion_analistas",
                                                  "n_analistas", "variacion_12m_pct", "ev_mercado", "ev_ebitda_mercado", "ev_ebitda_modelo", "titulares"]}
        anc = CI.calcular_anclas(nombre, m, cm)
        out["anclas"] = [{"id": a["id"], "nombre": a["nombre"], "vps_precio": r(a.get("vps_precio"), 2), "metodo": a["metodo"]} for a in anc["anclas"]]
        out["pares"] = anc.get("pares")
        out["multiplo_pares"] = anc.get("multiplo_pares")
        out["escenarios"] = anc.get("escenarios")
    except Exception:
        out["error"] = traceback.format_exc()[-1500:]
    out["seg"] = round(time.time() - t0, 1)
    return out


def main():
    res = []
    for n in CATALOGO:
        L.vincular_estado_sesion({})
        est = L.preparar_empresa(n)
        o = evaluar(n, f"catálogo → {est.get('fuente')}: {str(est.get('detalle'))[:200]}")
        res.append(o)
    for tk in TICKERS:
        L.vincular_estado_sesion({})
        ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
        if not ok:
            res.append({"empresa": tk, "error": L._html_a_texto(html, 300)})
            continue
        res.append(evaluar(nombre, f"descarga {tk}"))
    print(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "activos": res}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
