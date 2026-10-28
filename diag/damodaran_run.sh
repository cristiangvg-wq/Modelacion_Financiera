set -x
pip install xlrd
mkdir -p res/dam
python scripts/actualizar_damodaran.py --salida res/dam/datos_damodaran.json > res/dam/log.txt 2>&1
for f in ctrypremJuly26.xlsx ctrypremJuly25.xlsx ctryprem.xlsx; do curl -s -o /dev/null -w "$f %{http_code} %{size_download}\n" -A Mozilla/5.0 https://pages.stern.nyu.edu/~adamodar/pc/datasets/$f >> res/dam/log.txt; done
python - <<'PY' >> res/dam/log.txt 2>&1
import pandas as pd
for f in ["vebitda.xls"]:
    import urllib.request, io
    raw = urllib.request.urlopen(urllib.request.Request("https://pages.stern.nyu.edu/~adamodar/pc/datasets/"+f, headers={"User-Agent":"Mozilla/5.0"})).read()
    for sh, df in pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None).items():
        print("==", sh); print(df.head(12).to_string()[:4000])
PY
