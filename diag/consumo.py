"""Diagnóstico de empresas maduras de consumo de EE. UU."""
import json, os, sys, traceback
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import numpy as np, pandas as pd, yfinance as yf
import modelacion_logic as L
import contraste_mercado_real as C

TK = sys.argv[1:] or ["KO", "PEP", "PG", "CL", "MDLZ", "KMB", "HSY", "MCD", "WMT", "COST", "PM", "GIS"]
PK = ["tax", "tax_fuente", "beta_u", "beta_fuente", "beta_industria_u", "de_ratio", "kd", "g", "deuda_neta", "caja", "nci",
      "asociados", "asociados_fuente", "acciones", "capital_invertido", "consenso_ingresos", "industria_beta"]
MK = ["vps_modelo", "precio_mercado", "upside", "wacc_calc", "ke_calc", "g_usada", "tv_pct_ev", "ronic_terminal",
      "roic_observado", "roic_calc", "wacc_implicito_mercado", "margen_ebitda_proy", "fcff_proy", "horizonte", "decision_modelo"]


def beta_regresion(tk):
    try:
        px = yf.download([tk, "^GSPC"], period="5y", interval="1mo", auto_adjust=True, progress=False)["Close"]
        r = px.pct_change().dropna()
        cov = np.cov(r[tk], r["^GSPC"]); b = cov[0, 1] / cov[1, 1]
        res = r[tk] - b * r["^GSPC"]
        se = float(np.std(res, ddof=2) / (np.std(r["^GSPC"], ddof=1) * np.sqrt(len(r))))
        return round(float(b), 3), round(se, 3), len(r)
    except Exception as e:
        return str(e)[:100]


res = {}
for tk in TK:
    o = {}
    try:
        L.vincular_estado_sesion({})
        ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
        if not ok:
            res[tk] = {"error": L._html_a_texto(html, 300)}; continue
        p = L.params_empresa(nombre)
        o["params"] = {k: p.get(k) for k in PK}
        t = yf.Ticker(tk); info = t.info
        o["info"] = {k: info.get(k) for k in ["beta", "sector", "industry", "trailingPE", "forwardPE", "enterpriseToEbitda",
                                              "targetMeanPrice", "dividendYield", "payoutRatio", "returnOnEquity", "effectiveTaxRate"]}
        o["industria_dam"] = L.industria_damodaran(info.get("sector") or "", info.get("industry") or "")
        o["beta_reg_5a_mensual"] = beta_regresion(tk)
        df, _ = L.cargar_y_limpiar_excel(None, nombre, True)
        o["hist"] = df.round(2).reset_index().values.tolist(); o["hist_cols"] = ["Año"] + list(df.columns)
        m = C.correr(nombre)["4"]; m = L.metricas_valoracion_sesion(nombre) or m
        o["m"] = {k: m.get(k) for k in MK}
        cm = L.contexto_mercado_comite(nombre, m)
        o["mercado"] = {k: cm.get(k) for k in ["ev_ebitda_mercado", "ev_ebitda_modelo", "objetivo_analistas", "ev_mercado"]}
        try:
            cf = t.cashflow
            o["fcf_yahoo"] = {str(c.date()): float(cf.loc["Free Cash Flow", c]) / 1e9 for c in cf.columns if "Free Cash Flow" in cf.index and pd.notna(cf.loc["Free Cash Flow", c])}
            o["sbc"] = {str(c.date()): float(cf.loc["Stock Based Compensation", c]) / 1e9 for c in cf.columns if "Stock Based Compensation" in cf.index and pd.notna(cf.loc["Stock Based Compensation", c])}
        except Exception as e:
            o["fcf_yahoo"] = str(e)[:100]
    except Exception:
        o["error"] = traceback.format_exc()[-1200:]
    res[tk] = o
print(json.dumps(res, ensure_ascii=False, default=str))
