import json, yfinance as yf
out = {}
for tk in ["ISA.CL", "GEB.CL", "ECOPETROL.CL", "CELSIA.CL", "AAPL", "MINEROS.CL"]:
    cf = yf.Ticker(tk).cashflow
    keep = [i for i in cf.index if any(k in i.lower() for k in ["capital expenditure", "purchase of", "investing", "intangible", "acquisition", "ppe"])]
    out[tk] = {"cols": [str(c)[:10] for c in cf.columns[:4]],
               "filas": {i: [None if v != v else round(float(v) / 1e9, 1) for v in cf.loc[i].values[:4]] for i in keep}}
print(json.dumps(out, ensure_ascii=False))
