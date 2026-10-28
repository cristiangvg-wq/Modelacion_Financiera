"""Descarga las tablas públicas de Aswath Damodaran (NYU Stern) y genera datos_damodaran.json.

    python scripts/actualizar_damodaran.py            # escribe datos_damodaran.json en la raíz
    python scripts/actualizar_damodaran.py --dir X    # usa archivos ya descargados en X

Fuentes (https://pages.stern.nyu.edu/~adamodar/pc/datasets/):
  - ctrypremJulyAA.xlsx (actualización de mitad de año) o ctryprem.xlsx (enero):
    prima de mercado madura, prima de EE. UU., multiplicador de volatilidad relativa y,
    por país, calificación, spread por calificación, CDS neto y CRP/ERP.
  - vebitda.xls (EE. UU.), vebitdaemerg.xls (emergentes), vebitdaGlobal.xls (global):
    EV/EBITDA y EV/EBIT por industria (firmas con EBITDA positivo).
Damodaran actualiza en enero (todo) y en julio (riesgo país). Requiere xlrd para .xls.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import sys
import urllib.request

import pandas as pd

BASE = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "datos_damodaran.json")
REGIONES_MULT = {"vebitda.xls": "US", "vebitdaemerg.xls": "Emergentes", "vebitdaGlobal.xls": "Global"}


def _bajar(nombre, carpeta=None):
    if carpeta:
        ruta = os.path.join(carpeta, nombre)
        return open(ruta, "rb").read() if os.path.exists(ruta) else None
    try:
        req = urllib.request.Request(BASE + nombre, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=60).read()
    except Exception:
        return None


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def leer_riesgo_pais(raw, archivo):
    df = pd.read_excel(io.BytesIO(raw), sheet_name="ERPs by country", header=None)
    meta = {}
    for i in range(0, 8):
        etiqueta = str(df.iat[i, 0] or "").lower()
        fila_v = [v for v in df.iloc[i, 1:8].tolist() if v is not None and v == v]
        # La fecha está en la columna B; los valores numéricos/«Yes» suelen estar en la E.
        numericos = [v for v in fila_v if _f(v) is not None and not isinstance(v, (pd.Timestamp, dt.datetime))]
        valor = fila_v[0] if "date" in etiqueta and fila_v else (numericos[0] if numericos else None)
        if "date of update" in etiqueta:
            meta["fecha"] = str(pd.Timestamp(valor).date()) if valor is not None else None
        elif "mature equity market" in etiqueta:
            meta["erp_madura"] = _f(valor)
        elif "for the us" in etiqueta:
            meta["erp_us"] = _f(valor)
        elif "multiplier" in etiqueta:
            meta["multiplicador_volatilidad"] = _f(valor)
    fila = df.index[df[0].astype(str).str.strip().eq("Country")][0]
    t = df.iloc[fila + 1:, :9]
    t.columns = ["pais", "region", "rating", "spread_rating", "erp_rating", "crp_rating", "cds_neto", "erp_cds", "crp_cds"]
    paises = {}
    for _, r in t.iterrows():
        nombre = str(r["pais"]).strip() if r["pais"] == r["pais"] and r["pais"] is not None else ""
        if not nombre or nombre.lower() == "nan" or _f(r["crp_rating"]) is None:
            continue
        paises[nombre] = {k: (_f(r[k]) if k not in ("region", "rating") else (str(r[k]) if r[k] == r[k] else None))
                          for k in ["region", "rating", "spread_rating", "erp_rating", "crp_rating", "cds_neto", "erp_cds", "crp_cds"]}
    if not paises or meta.get("erp_madura") is None:
        raise ValueError(f"{archivo}: estructura no reconocida")
    meta["archivo"] = archivo
    return {"meta": meta, "paises": paises}


def leer_multiplos(raw, archivo):
    if archivo.endswith(".csv"):
        hojas = {"Industry Averages": pd.read_csv(io.BytesIO(raw), header=None)}
    else:
        hojas = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None)
    for nombre_hoja, df in hojas.items():
        filas = df.index[df.apply(lambda r: r.astype(str).str.strip().eq("Industry Name").any(), axis=1)]
        if len(filas) == 0:
            continue
        h = filas[0]
        cab = [str(x).strip() for x in df.iloc[h].tolist()]
        try:
            c_ind = cab.index("Industry Name")
            c_n = next(i for i, x in enumerate(cab) if x.lower().startswith("number of firms"))
            c_ebitda = cab.index("EV/EBITDA")          # primera aparición = firmas con EBITDA positivo
            c_ebit = cab.index("EV/EBIT")
        except (ValueError, StopIteration):
            continue
        industrias = {}
        for _, r in df.iloc[h + 1:].iterrows():
            ind = r.iloc[c_ind]
            if not isinstance(ind, str) or not ind.strip():
                continue
            industrias[ind.strip()] = {"n_firmas": _f(r.iloc[c_n]), "ev_ebitda": _f(r.iloc[c_ebitda]), "ev_ebit": _f(r.iloc[c_ebit])}
        if industrias:
            fecha = None
            for i in range(min(h, 6)):
                if "date updated" in str(df.iat[i, 0]).lower():
                    try:
                        fecha = str(pd.Timestamp(df.iat[i, 1]).date())
                    except Exception:
                        fecha = None
            return {"archivo": archivo, "hoja": nombre_hoja, "fecha": fecha, "industrias": industrias}
    raise ValueError(f"{archivo}: no se encontró la tabla de industrias")


def construir(carpeta=None):
    out = {"fuente": "Aswath Damodaran, NYU Stern — https://pages.stern.nyu.edu/~adamodar/",
           "descargado": dt.date.today().isoformat(), "riesgo_pais": None, "multiplos": {}}
    año = dt.date.today().year % 100
    for nombre in (f"ctrypremJuly{año}.xlsx", f"ctrypremJuly{año - 1}.xlsx", "ctryprem.xlsx"):
        raw = _bajar(nombre, carpeta)
        if not raw:
            continue
        try:
            rp = leer_riesgo_pais(raw, nombre)
        except Exception:
            continue
        if out["riesgo_pais"] is None or (rp["meta"].get("fecha") or "") > (out["riesgo_pais"]["meta"].get("fecha") or ""):
            out["riesgo_pais"] = rp
    for nombre, region in REGIONES_MULT.items():
        raw = _bajar(nombre, carpeta)
        archivo = nombre
        if not raw and carpeta:  # copia ya convertida a CSV (sin xlrd)
            archivo = nombre.replace(".xls", ".csv")
            raw = _bajar(archivo, carpeta)
        if raw:
            out["multiplos"][region] = leer_multiplos(raw, archivo)
    if out["riesgo_pais"] is None or not out["multiplos"]:
        raise SystemExit("No se pudieron leer las tablas de Damodaran.")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    ap.add_argument("--salida", default=SALIDA)
    a = ap.parse_args()
    datos = construir(a.dir)
    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, sort_keys=False)
    rp = datos["riesgo_pais"]["meta"]
    print(f"Riesgo país {rp}; múltiplos: " + ", ".join(f"{k} ({len(v['industrias'])} industrias)" for k, v in datos["multiplos"].items()))
