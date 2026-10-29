import io, urllib.request, pandas as pd
BASE = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/"
for n in ["ratings.xls", "betaemerg.xls", "betaGlobal.xls"]:
    try:
        raw = urllib.request.urlopen(urllib.request.Request(BASE + n, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        x = pd.ExcelFile(io.BytesIO(raw))
        print("=====", n, x.sheet_names)
        for sh in x.sheet_names[:4]:
            df = pd.read_excel(x, sheet_name=sh, header=None)
            print("--- hoja", sh, df.shape)
            with pd.option_context("display.max_columns", 20, "display.width", 250, "display.max_colwidth", 30):
                print(df.head(45 if n == "ratings.xls" else 12).to_string())
    except Exception as e:
        print(n, "ERROR", e)
