import json, sys, os, io, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, yfinance as yf
import modelacion_logic as L
out = {}
for tk in ["AAPL", "PLTR", "MSFT", "KO"]:
    t = yf.Ticker(tk); d = {}
    for a in ["revenue_estimate", "earnings_estimate", "growth_estimates"]:
        try:
            v = getattr(t, a); d[a] = v.reset_index().astype(str).values.tolist() if v is not None else None
            d[a + "_cols"] = ["index"] + list(v.columns) if v is not None else None
        except Exception as e:
            d[a] = "ERR " + str(e)[:200]
    try:
        bs = t.balance_sheet
        d["bs_rows"] = {r: float(bs.loc[r].iloc[0]) for r in bs.index if any(k in r for k in ["Invest", "Securit", "Cash", "Debt", "Lease"]) and pd.notna(bs.loc[r].iloc[0])}
    except Exception as e:
        d["bs_rows"] = str(e)
    info = t.info
    d["info"] = {k: info.get(k) for k in ["totalCash", "totalDebt", "beta", "sector", "industry", "sharesOutstanding", "marketCap", "fiscalYearEnd", "lastFiscalYearEnd", "mostRecentQuarter"]}
    d["industria_dam"] = L.industria_damodaran(info.get("sector") or "", info.get("industry") or "")
    try:
        f = t.financials; d["rev_cols"] = [str(c.date()) for c in f.columns]; d["rev"] = [float(x) for x in f.loc["Total Revenue"].values]
    except Exception as e:
        d["rev"] = str(e)
    out[tk] = d
try:
    raw = urllib.request.urlopen(urllib.request.Request("https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    hojas = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None)
    out["betas"] = {h: df.head(12).astype(str).values.tolist() for h, df in hojas.items()}
except Exception as e:
    out["betas"] = "ERR " + str(e)
print(json.dumps(out, default=str, ensure_ascii=False))
