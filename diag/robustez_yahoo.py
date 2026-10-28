import json, os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C
import yfinance as yf
t = yf.Ticker("ECOPETROL.CL"); info = t.info
out = {"info_ebitda": info.get("ebitda"), "info_rev": info.get("totalRevenue")}
i2 = dict(info); i2.pop("ebitda")
c = L._completar_info_yahoo(i2, t, "ECOPETROL.CL")
out["fallback_ebitda"] = c.get("ebitda"); out["completado"] = c.get("_completado")
n = "ECOPETROL"
for quitar in (None, "ebitda"):
    _R = yf.Ticker
    class P:
        def __init__(s, *a, **k): s._t = _R(*a, **k)
        def __getattr__(s, x): return getattr(s._t, x)
        @property
        def info(s):
            d = dict(s._t.info or {}); d.pop(quitar, None) if quitar else None; return d
    L.yf.Ticker = P
    L.vincular_estado_sesion({}); L.preparar_empresa(n, forzar=True)
    p = L.params_empresa(n)
    df, msg, src = L.obtener_datos_financieros_publicos(n)
    m = C.correr(n)["4"]
    out[str(quitar)] = {"ltm": [p.get("ltm_ingresos"), p.get("ltm_ebitda")], "attrs_ltm": df.attrs.get("ltm"), "vps": m.get("vps_modelo"),
                        "datos_completados": p.get("datos_completados"), "ebitda_norm": m.get("ebitda_normalizado")}
    L.yf.Ticker = _R
print(json.dumps(out, default=str, indent=1))
