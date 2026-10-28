"""Descarga las tasas de mercado que anclan el CAPM y genera datos_mercado.json.

    python scripts/actualizar_tasas.py                 # escribe datos_mercado.json en la raíz
    python scripts/actualizar_tasas.py --salida X.json

Fuentes públicas, sin clave:
  - Tesoro de EE. UU. (home.treasury.gov): curva nominal diaria → rendimiento a 10 años; curva real
    diaria (TIPS) → inflación implícita a 10 años = nominal − real.
  - OCDE (sdmx.oecd.org, Main Economic Indicators): tasa de largo plazo del gobierno de Colombia
    (bono a 10 años), promedio mensual.
La app usa, para cada tasa, el dato MÁS RECIENTE entre este archivo y la referencia escrita en el código
(que puede venir de una fuente diaria del Banco de la República): un promedio mensual de la OCDE no
reemplaza un dato puntual más nuevo. (FRED bloquea las conexiones desde GitHub Actions.)
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
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
TESORO = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
          "{anio}/all?type={tipo}&field_tdr_date_value={anio}&page&_format=csv")
OCDE = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/COL.M.IRLT.PA.....?"
        "startPeriod={desde}&dimensionAtObservation=AllDimensions&format=csvfilewithlabels")


def _bajar(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig")


def ultimo_tesoro(texto):
    """(fecha ISO, valor en fracción) del plazo de 10 años en un CSV del Tesoro (filas recientes primero)."""
    filas = list(csv.DictReader(io.StringIO(texto)))
    col = next((c for c in (filas[0].keys() if filas else []) if c and c.strip().upper().replace("YR", "YR") in ("10 YR",)), None)
    col = col or next((c for c in (filas[0].keys() if filas else []) if c and c.strip().lower().startswith("10 y")), None)
    if not col:
        raise ValueError("sin columna de 10 años")
    mejores = []
    for f in filas:
        try:
            fecha = dt.datetime.strptime(f["Date"].strip(), "%m/%d/%Y").date()
            mejores.append((fecha, float(f[col])))
        except (KeyError, ValueError, TypeError):
            continue
    if not mejores:
        raise ValueError("sin observaciones")
    fecha, v = max(mejores)
    return fecha.isoformat(), round(v / 100.0, 6)


def ultimo_ocde(texto):
    """(fecha ISO a mitad de mes, valor en fracción) de la observación más reciente del CSV SDMX de la OCDE."""
    mejores = []
    for f in csv.DictReader(io.StringIO(texto)):
        try:
            mejores.append((f["TIME_PERIOD"].strip(), float(f["OBS_VALUE"])))
        except (KeyError, ValueError, TypeError):
            continue
    if not mejores:
        raise ValueError("sin observaciones")
    periodo, v = max(mejores)
    return f"{periodo}-15", round(v / 100.0, 6)


def construir(hoy=None):
    hoy = hoy or dt.date.today()
    out = {"fuente": "Tesoro de EE. UU. (home.treasury.gov) y OCDE (sdmx.oecd.org)", "descargado": hoy.isoformat(), "tasas": {}}

    def tesoro(tipo):
        for anio in (hoy.year, hoy.year - 1):  # en enero el año en curso puede no tener datos
            try:
                return ultimo_tesoro(_bajar(TESORO.format(anio=anio, tipo=tipo)))
            except Exception:
                continue
        raise ValueError(f"Tesoro {tipo}: sin datos")

    try:
        f_n, nominal = tesoro("daily_treasury_yield_curve")
        out["tasas"]["us_rf"] = {"valor": nominal, "fecha": f_n, "fuente": f"Tesoro de EE. UU. a 10 años (Treasury, {f_n})"}
        try:
            f_r, real = tesoro("daily_treasury_real_yield_curve")
            if f_r == f_n:
                out["tasas"]["us_inflacion_lp"] = {"valor": round(nominal - real, 6), "fecha": f_n,
                                                   "fuente": f"Inflación implícita 10a = nominal {nominal:.2%} − real {real:.2%} (Treasury, {f_n})"}
        except Exception as e:
            out["tasas"]["us_inflacion_lp"] = {"error": str(e)[:200]}
    except Exception as e:
        out["tasas"]["us_rf"] = {"error": str(e)[:200]}
    try:
        f_c, co = ultimo_ocde(_bajar(OCDE.format(desde=f"{hoy.year - 1}-01")))
        out["tasas"]["co_rf_bruto"] = {"valor": co, "fecha": f_c,
                                       "fuente": f"Bono del gobierno de Colombia a 10 años, promedio de {f_c[:7]} (OCDE)"}
    except Exception as e:
        out["tasas"]["co_rf_bruto"] = {"error": str(e)[:200]}
    if not any("valor" in v for v in out["tasas"].values()):
        raise SystemExit("No se pudo leer ninguna tasa.")
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
