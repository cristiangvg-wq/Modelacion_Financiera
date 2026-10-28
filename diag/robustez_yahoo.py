"""Robustez ante respuestas incompletas de Yahoo: quita un campo de `info` y mide el cambio del VPS."""
import json, os, sys, traceback
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C
import yfinance as yf
_Real = yf.Ticker
QUITAR = [None, "totalDebt", "totalCash", "sharesOutstanding", "beta", "marketCap", "currentPrice", "financialCurrency",
          "country", "ebitda", "totalRevenue"]
class Parcial:
    quitar = None
    def __init__(self, *a, **k): self._t = _Real(*a, **k)
    def __getattr__(self, n): return getattr(self._t, n)
    @property
    def info(self):
        i = dict(self._t.info or {})
        if Parcial.quitar:
            i.pop(Parcial.quitar, None)
            if Parcial.quitar == "currentPrice": i.pop("regularMarketPrice", None)
        return i
yf.Ticker = Parcial
L.yf.Ticker = Parcial
res = {}
for objetivo in ["ISA — Interconexión Eléctrica", "AAPL", "ECOPETROL"]:
    res[objetivo] = {}
    for q in QUITAR:
        Parcial.quitar = q
        L.vincular_estado_sesion({})
        try:
            if objetivo in L.EMPRESAS:
                L.preparar_empresa(objetivo, forzar=True); n = objetivo
            else:
                ok, html, n, _ = L.buscar_y_descargar_empresa(objetivo)
            m = C.correr(n)["4"]
            p = L.params_empresa(n)
            res[objetivo][str(q)] = {"vps": round(m.get("vps_modelo") or 0, 2), "upside": round(m.get("upside") or 0, 1) if m.get("upside") is not None else None,
                                     "deuda_neta": p.get("deuda_neta"), "acciones": p.get("acciones"), "beta_u": p.get("beta_u"), "tax": p.get("tax"),
                                     "precio": m.get("precio_mercado"), "moneda": m.get("moneda"), "alertas": (m.get("alertas_modelo") or [])[:3]}
        except Exception:
            res[objetivo][str(q)] = {"error": traceback.format_exc()[-400:]}
print(json.dumps(res, ensure_ascii=False, default=str))
