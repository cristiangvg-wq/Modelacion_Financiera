"""Descarga las tasas de mercado que anclan el CAPM y genera datos_mercado.json.

    python scripts/actualizar_tasas.py                 # escribe datos_mercado.json en la raíz
    python scripts/actualizar_tasas.py --salida X.json

Fuente: FRED (Federal Reserve Bank of St. Louis), CSV público sin clave:
  - DGS10: rendimiento del Tesoro de EE. UU. a 10 años (diario).
  - T10YIE: inflación implícita (breakeven) a 10 años en EE. UU. (diario).
  - COLIRLTLT01STM: bono del gobierno de Colombia a 10 años, promedio mensual (OCDE).
La app usa, para cada tasa, el dato MÁS RECIENTE entre este archivo y la referencia escrita en el
código (que puede venir de una fuente diaria del Banco de la República): un promedio mensual de
la OCDE no reemplaza un dato puntual más nuevo.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "datos_mercado.json")
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
SERIES = {
    "us_rf": ("DGS10", "Tesoro de EE. UU. a 10 años (FRED DGS10)"),
    "us_inflacion_lp": ("T10YIE", "Inflación implícita a 10 años de EE. UU. (FRED T10YIE)"),
    "co_rf_bruto": ("COLIRLTLT01STM", "Bono del gobierno de Colombia a 10 años, promedio mensual (OCDE vía FRED COLIRLTLT01STM)"),
}


def ultimo_dato(serie, raw=None):
    """(fecha ISO, valor en fracción) de la última observación numérica de una serie FRED."""
    if raw is None:
        req = urllib.request.Request(FRED + serie, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    filas = list(csv.reader(io.StringIO(raw)))
    for fecha, valor in reversed(filas[1:]):
        try:
            v = float(valor)
        except ValueError:
            continue  # FRED marca los días sin dato con «.»
        if serie.endswith("STM"):  # mensual: fecha = primer día del mes; se usa la mitad del mes
            fecha = (dt.date.fromisoformat(fecha) + dt.timedelta(days=14)).isoformat()
        return fecha, round(v / 100.0, 6)
    raise ValueError(f"{serie}: sin observaciones numéricas")


def construir():
    out = {"fuente": "FRED — https://fred.stlouisfed.org", "descargado": dt.date.today().isoformat(), "tasas": {}}
    for clave, (serie, desc) in SERIES.items():
        try:
            fecha, valor = ultimo_dato(serie)
            out["tasas"][clave] = {"valor": valor, "fecha": fecha, "serie": serie, "fuente": desc}
        except Exception as e:  # una serie caída no bloquea las demás
            out["tasas"][clave] = {"error": str(e)[:200], "serie": serie}
    if not any("valor" in v for v in out["tasas"].values()):
        raise SystemExit("No se pudo leer ninguna serie de FRED.")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=SALIDA)
    a = ap.parse_args()
    datos = construir()
    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    for k, v in datos["tasas"].items():
        print(k, v.get("valor"), v.get("fecha"), v.get("error", ""))
