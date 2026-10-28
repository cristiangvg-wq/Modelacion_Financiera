pip install xlrd
mkdir -p res/dam
B=https://pages.stern.nyu.edu/~adamodar/pc/datasets
for f in ctrypremJuly26.xlsx vebitda.xls vebitdaemerg.xls vebitdaGlobal.xls; do curl -s -A Mozilla/5.0 -o res/dam/$f $B/$f; done
python - <<'PY'
import pandas as pd
for f in ["vebitda.xls", "vebitdaemerg.xls", "vebitdaGlobal.xls"]:
    df = pd.read_excel("res/dam/" + f, sheet_name="Industry Averages", header=None)
    df.to_csv("res/dam/" + f.replace(".xls", ".csv"), index=False, header=False)
PY
rm -f res/dam/*.xls
