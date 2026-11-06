"""Tasa libre de riesgo y primas con fuente, fecha y vigencia, sin tocar el estado global.

Hoy la app fija rf al IMPORTAR modelacion_logic (TASAS_MERCADO → CAPM_POR_MERCADO): en Streamlit
Cloud el proceso puede vivir semanas y el rf no cambia aunque llegue un dato nuevo, y la tabla
REFERENCIAS_TASAS se edita a mano. Esta capa:
  · consulta en vivo el Tesoro de EE. UU. (misma función del flujo semanal scripts/actualizar_tasas.py);
  · compara con datos_mercado.json y con REFERENCIAS_TASAS y elige el dato MÁS RECIENTE
    (misma regla que L.tasas_vigentes, que se reutiliza);
  · valida rango y antigüedad; devuelve un dict nuevo por llamada (seguro entre sesiones).
El TES colombiano no tiene aquí un descargador: no se inventa un endpoint. Se acepta un
`proveedor_tes` inyectable (p. ej. una función que lea la serie del Banco de la República que el
equipo valide); sin él se usa la referencia fechada del repositorio y se advierte su antigüedad.
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from typing import Callable

import modelacion_logic as L

_RAIZ = Path(__file__).resolve().parents[1]
RANGOS = {"us_rf": (0.0, 0.15), "co_rf_bruto": (0.02, 0.30)}


def _script_tasas():
    spec = importlib.util.spec_from_file_location("actualizar_tasas", _RAIZ / "scripts" / "actualizar_tasas.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bajar_corto(url: str, timeout: float) -> str:
    import urllib.request
    s = _script_tasas()
    req = urllib.request.Request(url, headers=s.UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8-sig")


def ust10_en_vivo(hoy: date | None = None, timeout: float = 8.0) -> dict | None:
    """Último UST 10 años del Tesoro (CSV oficial). None si la red falla: nunca un valor supuesto."""
    try:
        s = _script_tasas()
        hoy = hoy or date.today()
        for anio in (hoy.year, hoy.year - 1):
            try:
                f, v = s.ultimo_tesoro(_bajar_corto(s.TESORO.format(anio=anio, tipo="daily_treasury_yield_curve"),
                                                    timeout))
                return {"valor": v, "fecha": f, "fuente": f"Tesoro de EE. UU. a 10 años (Treasury, {f})",
                        "origen": "en vivo"}
            except Exception:
                continue
    except Exception:
        return None
    return None


def tasas_actuales(en_vivo: bool = True, proveedor_tes: Callable[[], dict | None] | None = None,
                   hoy: date | None = None) -> tuple[dict, list[str]]:
    """(tasas, avisos). Cada tasa: {valor, fecha, fuente, origen}."""
    extra = {}
    if en_vivo:
        u = ust10_en_vivo(hoy)
        if u:
            extra["us_rf"] = u
    if proveedor_tes is not None:
        try:
            c = proveedor_tes()
            if c:
                extra["co_rf_bruto"] = dict(c, origen=c.get("origen", "proveedor_tes"))
        except Exception as e:  # el proveedor externo no debe tumbar la valoración
            extra["_error_tes"] = {"error": str(e)[:200]}
    archivo = dict(L._leer_tasas())
    for k, v in extra.items():  # gana el más reciente (regla de L.tasas_vigentes)
        if "valor" in v and str(v.get("fecha", "")) > str((archivo.get(k) or {}).get("fecha", "")):
            archivo[k] = v
    tasas = L.tasas_vigentes(archivo=archivo)
    for k, v in extra.items():  # conservar el rótulo «en vivo» cuando ese dato fue el elegido
        if k in tasas and tasas[k].get("fecha") == v.get("fecha") and "valor" in v:
            tasas[k]["origen"] = v.get("origen", tasas[k]["origen"])
    avisos = list(L.tasas_vigencia(hoy=hoy, tasas=tasas))
    for k, (lo, hi) in RANGOS.items():
        val = (tasas.get(k) or {}).get("valor")
        if val is not None and not lo <= val <= hi:
            avisos.append(f"{k}={val:.2%} fuera del rango plausible [{lo:.0%}, {hi:.0%}]: revisar unidades.")
    if "_error_tes" in extra:
        avisos.append(f"Proveedor TES falló: {extra['_error_tes']['error']}")
    return tasas, avisos


def capm_mercado(mercado: str, tasas: dict) -> dict:
    """rf, ERP y CRP del mercado con el MISMO método de la app (_aplicar_damodaran_a_capm), sin mutarla."""
    mk = str(mercado or "DEFAULT").upper()
    base = dict(L.CAPM_POR_MERCADO.get(mk, L.CAPM_POR_MERCADO["DEFAULT"]))
    out = {"mercado": mk, "erp": base["erp"], "crp": base.get("crp", 0.0), "erp_fuente": base.get("erp_fuente")}
    if mk == "US":
        t = tasas["us_rf"]
        out.update(rf=t["valor"], rf_bruto=t["valor"], rf_fuente=f"{t['fuente']} · {t['origen']}")
        return out
    clave = f"{mk.lower()}_rf_bruto"
    if clave not in tasas:
        out.update(rf=base["rf"], rf_bruto=base.get("rf_bruto", base["rf"]), rf_fuente=base.get("rf_fuente"))
        return out
    t = tasas[clave]
    rp = L.damodaran_riesgo_pais(mk)
    if rp and rp.get("spread") is not None and rp.get("erp_total") is not None:
        out.update(rf=t["valor"] - float(rp["spread"]), rf_bruto=t["valor"], erp=float(rp["erp_total"]), crp=0.0,
                   rf_fuente=f"{t['fuente']} − spread de default {float(rp['spread']):.2%} ({rp['fuente']})")
    else:
        out.update(rf=t["valor"], rf_bruto=t["valor"], rf_fuente=t["fuente"])
    return out


def refrescar_rf_us_en_proceso(dato: dict | None = None) -> dict:
    """Actualiza en el proceso el rf de EE. UU. si hay un dato del Tesoro MÁS RECIENTE que el cargado.

    Motivo (auditoría nov-2026, M1): TASAS_MERCADO se fija al importar modelacion_logic y un proceso de
    Streamlit Cloud puede vivir semanas con el mismo rf. El rf es un dato de mercado común a todas las
    sesiones, no estado de un usuario, por eso se actualiza en CAPM_POR_MERCADO. Se usa el mismo rango
    de validación que tasas_vigentes (0 < rf < 40 %) y la fuente queda rotulada. Devuelve qué hizo.
    """
    dato = dato if dato is not None else ust10_en_vivo()
    actual = L.TASAS_MERCADO.get("us_rf") or {}
    if not dato or "valor" not in dato:
        return {"cambio": False, "motivo": "Tesoro no disponible; se conserva " + str(actual.get("fecha"))}
    v = float(dato["valor"])
    lo, hi = RANGOS["us_rf"]
    if not lo < v < hi:
        return {"cambio": False, "motivo": f"valor fuera de rango ({v})"}
    if str(dato.get("fecha", "")) <= str(actual.get("fecha", "")):
        return {"cambio": False, "motivo": f"el dato cargado ({actual.get('fecha')}) es igual o más reciente"}
    anterior = L.CAPM_POR_MERCADO["US"]["rf"]
    L.TASAS_MERCADO["us_rf"] = {"valor": v, "fecha": dato["fecha"], "fuente": dato["fuente"], "origen": "en vivo"}
    fuente = f"{dato['fuente']} · {dato['fecha']} (actualizado en vivo)"
    for k in ("US", "DEFAULT"):
        L.CAPM_POR_MERCADO[k]["rf"] = round(v, 4)
        L.CAPM_POR_MERCADO[k]["rf_bruto"] = round(v, 4)
        L.CAPM_POR_MERCADO[k]["rf_fuente"] = fuente
    return {"cambio": True, "anterior": anterior, "nuevo": round(v, 4), "fecha": dato["fecha"]}
