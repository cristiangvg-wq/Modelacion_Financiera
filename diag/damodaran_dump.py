import io, json, sys, urllib.request
import pandas as pd
BASE = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/"
out = {}
for f in ["ctryprem.xlsx", "vebitda.xls", "vebitdaemerg.xls", "vebitdaGlobal.xls"]:
    try:
        req = urllib.request.Request(BASE + f, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=60).read()
        open(f"res/{f}", "wb").write(raw)
        xl = pd.ExcelFile(io.BytesIO(raw))
        out[f] = {}
        for sh in xl.sheet_names:
            df = xl.parse(sh, header=None, nrows=25)
            out[f][sh] = [[None if (isinstance(v, float) and v != v) else str(v)[:40] for v in row] for row in df.values.tolist()[:25]]
    except Exception as e:
        out[f] = {"error": repr(e)}
print(json.dumps(out, ensure_ascii=False))
