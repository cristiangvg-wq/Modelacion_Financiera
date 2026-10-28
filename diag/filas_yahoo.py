import json, inspect
import yfinance as yf, streamlit as st
out = {"streamlit": st.__version__, "button_params": list(inspect.signature(st.button).parameters),
       "plotly_params": list(inspect.signature(st.plotly_chart).parameters),
       "dataframe_params": list(inspect.signature(st.dataframe).parameters)}
for tk in ["GEB.CL", "ISA.CL", "ECOPETROL.CL", "AAPL", "MINEROS.CL", "CELSIA.CL"]:
    t = yf.Ticker(tk)
    d = {}
    try:
        f = t.financials
        keep = [i for i in f.index if any(k in i.lower() for k in ["ebit", "operating income", "equity interest", "pretax", "tax provision", "tax rate", "total revenue", "special", "unusual", "other non operating"])]
        d["fin"] = {i: [None if v != v else round(float(v) / 1e9, 3) for v in f.loc[i].values[:4]] for i in keep}
        d["fin_cols"] = [str(c)[:10] for c in f.columns[:4]]
        b = t.balance_sheet
        d["bs_minority"] = {i: [None if v != v else round(float(v) / 1e9, 3) for v in b.loc[i].values[:2]] for i in b.index if "minority" in i.lower() or "investment" in i.lower()}
        q = t.quarterly_financials
        d["quarterly_cols"] = [str(c)[:10] for c in q.columns[:6]]
        info = t.info
        d["info"] = {k: info.get(k) for k in ["ebitda", "enterpriseValue", "enterpriseToEbitda", "totalRevenue", "financialCurrency", "currency"]}
    except Exception as e:
        d["error"] = str(e)
    out[tk] = d
print(json.dumps(out, ensure_ascii=False, default=str))
