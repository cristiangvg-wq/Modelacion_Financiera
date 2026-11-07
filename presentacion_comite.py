"""Presentación de comité descargable (HTML autónomo) para cualquier empresa valorada.

Flujo: métricas canónicas de la pestaña 4 (``metricas_valoracion_sesion``) → snapshot
congelado y conciliado → HTML de diapositivas que solo LEE el snapshot.

Reglas de diseño:
- No hay lógica financiera nueva. Las cifras derivadas (puente, sensibilidad, Ke, WACC,
  NOPAT, VPS) se obtienen llamando a las mismas funciones de ``modelacion_logic`` que usa
  la pestaña 4, con los insumos exactos que esa corrida guardó.
- Cada cifra recalculada se concilia contra la guardada. Si no cuadra, el control queda
  como fallido y la cifra derivada se marca N/D; nunca se muestra un número distinto al
  de la app.
- La plantilla HTML no calcula valores financieros: solo formatea y dibuja.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

import modelacion_logic as L
from isa_snapshot_store import _json_safe

SCHEMA_VERSION = 1
MOTOR = "modelacion_logic.tab4_recomendacion"
TOLERANCIA_REL = 1e-3  # 0,1 % para conciliar recálculos contra la corrida guardada
UMBRAL_TV = 0.75
PLANTILLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plantillas", "presentacion_comite.html")


def _f(x):
    """Float finito o None (nunca convierte faltantes en cero)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _cuadra(a, b, tol=TOLERANCIA_REL):
    a, b = _f(a), _f(b)
    if a is None or b is None:
        return None
    return abs(a - b) <= tol * max(1.0, abs(b))


def _control(lista, cid, nivel, ok, msg):
    """ok: True = superado, False = fallido, None = advertencia o no verificable."""
    lista.append({"id": cid, "nivel": nivel, "ok": ok, "msg": msg})


def _precio_comparable(m):
    """Precio de mercado en la moneda del modelo, o None con el motivo."""
    if m.get("fx_aplicado") and _f(m.get("precio_mercado_moneda_modelo")):
        return _f(m["precio_mercado_moneda_modelo"]), "Precio convertido a {} con FX {} ({})".format(
            m.get("moneda"), m.get("fx_aplicado"), m.get("fuente_fx") or "fuente FX no registrada")
    px = _f(m.get("precio_mercado"))
    mon, mon_px = (m.get("moneda") or "").upper(), (m.get("moneda_precio") or "").upper()
    if px and mon and mon == mon_px:
        return px, None
    if px:
        return None, "Precio en {} y modelo en {} sin conversión FX: upside N/D".format(mon_px or "moneda desconocida", mon or "moneda desconocida")
    return None, "Sin precio de mercado registrado"


def _vps(equity, acciones):
    if _f(equity) is None or not _f(acciones):
        return None
    return _f(L.calcular_vps_y_upside(float(equity), float(acciones)).get("value_per_share"))


class _ContextoRonic:
    """Fija, durante el recálculo, el modo RONIC y el ROIC de referencia que usó ESTA corrida.

    ``valoracion_dcf`` lee el spread RONIC del estado de sesión (última empresa calculada). Sin esto,
    exportar la empresa A después de calcular la B usaría el ROIC de B. Al salir se restaura la sesión.
    """
    _CLAVES = ("_ronic_modo", "_roic_referencia", "_ronic_spread")

    def __init__(self, m):
        self.m = m

    def __enter__(self):
        est = L._almacen_estado()
        self._previo = {k: (k in est, est.get(k)) for k in self._CLAVES}
        modo = self.m.get("ronic_modo") or "roic"
        L.fijar_modo_ronic(modo)
        L.fijar_roic_referencia(self.m.get("empresa"), self.m.get("roic_observado"))
        if modo == "manual" and _f(self.m.get("ronic_terminal")) is not None and _f(self.m.get("wacc_calc")) is not None:
            est["_ronic_spread"] = float(self.m["ronic_terminal"]) - float(self.m["wacc_calc"])
        return self

    def __exit__(self, *exc):
        est = L._almacen_estado()
        for k, (habia, v) in self._previo.items():
            if habia:
                est[k] = v
            else:
                est.pop(k, None)
        return False


def _valorar(m, wacc, g):
    sup = m.get("supuestos") or {}
    return L.valorar_con_bridge(
        m["fcff_proy"], wacc, g, m.get("bridge") or {},
        ebitda_salida=m.get("ebitda_salida"), precio_mercado=None,
        mid_year=bool(sup.get("mid_year", True)), g_max_macro=float(sup.get("g_max_macro", 0.05)),
        nopat_final=m.get("nopat_final"),
    )


def _grilla_sensibilidad(m):
    """Reutiliza la rejilla WACC × g del motor (techo de g incluido) y la expresa por acción."""
    sup = m.get("supuestos") or {}
    bp = m.get("bridge") or {}
    df = L.matriz_sensibilidad_wacc_g(
        m["fcff_proy"], bp.get("deuda_neta", 0), float(m["wacc_calc"]), float(m["g"]),
        mid_year=bool(sup.get("mid_year", True)), g_max_macro=float(sup.get("g_max_macro", 0.05)),
        nopat_final=m.get("nopat_final"), frac_transcurrida=float(bp.get("frac_transcurrida") or 0.0),
        t_valoracion=float(bp.get("t_valoracion") or 0.0),
    )
    # El motor muestra el WACC redondeado a 2 decimales; se recupera el desplazamiento de la rejilla
    # (múltiplos de 1 pp) para valorar con el WACC exacto y que la celda central sea la corrida base.
    w0 = float(m["wacc_calc"])
    waccs = [max(0.04, w0 + round(float(w) / 100.0 - w0, 3)) for w in df["WACC %"].tolist()]
    gs = []
    for col in df.columns:
        mt = re.match(r"g=(-?[\d.]+)% EV", str(col))
        if mt:
            gs.append(float(mt.group(1)) / 100.0)
    vps = [[_vps(_valorar(m, w, g).get("Equity_Value"), m.get("acciones")) for g in gs] for w in waccs]
    return waccs, gs, vps


def construir_snapshot_comite(metrics: dict[str, Any], *, decision_text: str = "",
                              generado: datetime | None = None) -> dict[str, Any]:
    """Snapshot inmutable y conciliado de una corrida de la pestaña 4."""
    if not isinstance(metrics, dict):
        raise ValueError("No hay una valoración de la pestaña 4 para esta empresa. Pulsa Generar todo.")
    faltan = [k for k in ("vps_modelo", "val_ev", "val_equity", "wacc_calc", "fcff_proy", "bridge")
              if metrics.get(k) in (None, [], {})]
    if faltan:
        raise ValueError("La corrida no tiene los datos mínimos para la presentación: " + ", ".join(faltan))
    with _ContextoRonic(metrics):
        return _construir(metrics, decision_text, generado)


def _construir(m, decision_text, generado):
    sup = m.get("supuestos") or {}
    ctr: list[dict[str, Any]] = []
    tax = _f(sup.get("tax"))

    # --- Conciliación de la corrida: recálculo base con las funciones del motor
    base = None
    try:
        base = _valorar(m, float(m["wacc_calc"]), float(m["g"]))
        vps_re = _vps(base.get("Equity_Value"), m.get("acciones"))
        ok = all(_cuadra(x, y) for x, y in ((base.get("EV"), m["val_ev"]), (base.get("Equity_Value"), m["val_equity"]), (vps_re, m["vps_modelo"])))
        _control(ctr, "conciliacion", "CRÍTICO", bool(ok),
                 "Recálculo del snapshot coincide con la corrida (EV, Equity y valor por acción)" if ok else
                 "El recálculo NO coincide con la corrida guardada: puente y sensibilidad marcados N/D")
        if not ok:
            base = None
    except Exception as exc:  # el snapshot nunca rompe la app
        _control(ctr, "conciliacion", "CRÍTICO", False, "No fue posible recalcular la valoración base: " + str(exc)[:200])

    # --- Precio y upside (decimal); la pestaña 4 guarda upside en %
    px, nota_px = _precio_comparable(m)
    vps = _f(m["vps_modelo"])
    upside = (vps / px - 1.0) if (px and vps is not None) else None
    if upside is not None and _f(m.get("upside")) is not None:
        okup = abs(upside - _f(m["upside"]) / 100.0) < 5e-4
        _control(ctr, "upside", "ALTO", okup, "Upside coincide con el de la pestaña 4" if okup else
                 "Upside recalculado ({:.2%}) distinto del guardado ({:.2f} %)".format(upside, _f(m["upside"])))
    if nota_px:
        _control(ctr, "moneda_precio", "ALTO", None if px else False, nota_px)
    else:
        _control(ctr, "moneda_precio", "CRÍTICO", True, "Precio de mercado y modelo en la misma moneda ({})".format(m.get("moneda")))

    # --- Proyección y cascada FCFF
    filas = []
    ident_ok = True
    proy = m.get("proyeccion_sensibilidad") or []
    fcff = list(m.get("fcff_proy") or [])
    for i, r in enumerate(proy):
        ebit, dep, ebitda = _f(r.get("EBIT")), _f(r.get("Depreciacion")), _f(r.get("EBITDA"))
        capex, dnwc = _f(r.get("CAPEX")), _f(r.get("Delta_NWC"))
        nopat = _f(L.calcular_nopat(ebit, tax)) if (ebit is not None and tax is not None) else None
        f_i = _f(fcff[i]) if i < len(fcff) else None
        ok_i = _cuadra(nopat + dep - capex - dnwc, f_i) if None not in (nopat, dep, capex, dnwc, f_i) else None
        ident_ok = ident_ok and bool(ok_i)
        filas.append({
            "anio": r.get("Año"), "ingresos": _f(r.get("Ingresos")), "ebitda": ebitda, "da": dep,
            "margen_ebitda": (ebitda / _f(r.get("Ingresos"))) if (ebitda is not None and _f(r.get("Ingresos"))) else None,
            "conversion_caja": (f_i / ebitda) if (f_i is not None and ebitda) else None,
            "otros_ebitda_ebit": (ebitda - dep - ebit) if None not in (ebitda, dep, ebit) else None,
            "ebit": ebit, "impuestos_op": (ebit - nopat) if None not in (ebit, nopat) else None,
            "nopat": nopat, "capex": capex, "delta_ktno": dnwc, "fcff": f_i,
        })
    _control(ctr, "identidad_fcff", "CRÍTICO", ident_ok if filas else None,
             "FCFF = NOPAT + D&A − CAPEX − ΔKTNO en todos los años" if ident_ok else
             "La identidad del FCFF no se verifica en algún año o faltan partidas")
    otros = [abs(f["otros_ebitda_ebit"]) for f in filas if f["otros_ebitda_ebit"] is not None and f["ebitda"]]
    if otros and max(o / f["ebitda"] for o, f in zip(otros, filas)) > 0.01:
        _control(ctr, "ebitda_ebit", "MEDIO", None,
                 "EBITDA − D&A difiere del EBIT (otras partidas operativas); se muestran como barra separada")

    # --- Costo de capital
    beta_u, rf, erp, crp, kd = (_f(sup.get(k)) for k in ("beta_u", "rf", "erp", "crp", "kd"))
    de = _f(m.get("de_ratio"))
    wacc_blk: dict[str, Any] = {"rf": rf, "erp": erp, "crp": crp, "kd": kd, "tax": tax, "beta_u": beta_u,
                                "de_ratio": de, "ke": _f(m.get("ke_calc")), "wacc": _f(m["wacc_calc"]),
                                "beta_fuente": m.get("beta_fuente"), "capm_as_of": (m.get("macro") or {}).get("capm_as_of")}
    try:
        beta_l = _f(L.beta_apalancado(beta_u, de, tax))
        ke_re = L.costo_equity_capm(beta_l, rf=rf, erp=erp, crp=crp)
        w_re, we, wd = L.calcular_wacc(de, kd, wacc_blk["ke"], tax)
        wacc_blk.update({"beta_l": beta_l, "we": we, "wd": wd, "kd_at": kd * (1 - tax),
                         "beta_erp": beta_l * erp, "pond_ke": we * wacc_blk["ke"], "pond_kd": wd * kd * (1 - tax)})
        ok_ke, ok_w = _cuadra(ke_re, wacc_blk["ke"], 1e-6), _cuadra(w_re, wacc_blk["wacc"], 1e-6)
        _control(ctr, "capm", "ALTO", ok_ke, "Ke = rf + βL × ERP + CRP se verifica con los supuestos guardados" if ok_ke else
                 "Ke guardado no se reproduce con rf, β, ERP y CRP guardados")
        _control(ctr, "wacc", "ALTO", ok_w, "WACC = E/V × Ke + D/V × Kd × (1 − t) se verifica" if ok_w else
                 "WACC guardado no se reproduce con la estructura de capital guardada")
        if not (ok_ke and ok_w):
            for k in ("beta_erp", "pond_ke", "pond_kd"):
                wacc_blk[k] = None
    except Exception as exc:
        _control(ctr, "wacc", "ALTO", False, "No fue posible verificar Ke y WACC: " + str(exc)[:200])

    # --- Valor terminal
    g_in, g_us, wacc = _f(m.get("g")), _f(m.get("g_usada")), _f(m["wacc_calc"])
    tv_pct = _f(m.get("tv_pct_ev"))
    _control(ctr, "g_wacc", "CRÍTICO", (g_us is not None and g_us < wacc),
             "g usada ({:.2%}) menor que WACC ({:.2%})".format(g_us or float("nan"), wacc))
    if g_in is not None and g_us is not None and g_us < g_in - 1e-9:
        _control(ctr, "g_techo", "MEDIO", None, "g ingresada {:.2%} limitada a {:.2%} por el techo macro del motor".format(g_in, g_us))
    if tv_pct is not None:
        _control(ctr, "tv_pct", "ALTO", tv_pct <= UMBRAL_TV, "Valor terminal = {:.1%} del EV (umbral {:.0%})".format(tv_pct, UMBRAL_TV))

    # --- Puente EV → Equity (desde el recálculo conciliado)
    puente = None
    if base:
        b = base.get("bridge") or {}
        puente = {
            "partidas": [{"concepto": k, "valor": _f(v)} for k, v in b.items()
                         if isinstance(v, (int, float)) and not isinstance(v, bool)
                         and (k in ("Enterprise Value", "Equity atribuible") or str(k).startswith("("))],
            "notas": [str(v) for k, v in b.items() if str(k).startswith("Nota")],
            "pv_fcff": _f(base.get("PV_FCFF")), "pv_tv": _f(base.get("PV_TV")), "tv": _f(base.get("TV")),
            "deuda_es_bruta": bool(b.get("deuda_es_bruta")),
        }
        _control(ctr, "caja", "ALTO", True, "Caja sumada una sola vez" if puente["deuda_es_bruta"]
                 else "Deuda ya neta de caja: la caja no se suma otra vez")

    # --- Sensibilidad WACC × g, por acción
    sens = None
    if base:
        try:
            waccs, gs, grid = _grilla_sensibilidad(m)
            sens = {"wacc": waccs, "g": gs, "vps": grid,
                    "upside": [[(v / px - 1.0) if (px and v is not None) else None for v in row] for row in grid]}
            g_base = g_us if g_us is not None else g_in
            i0 = next((i for i, w in enumerate(waccs) if abs(w - wacc) < 1e-9), None)
            j0 = next((j for j, g in enumerate(gs) if g_base is not None and abs(g - g_base) < 1e-6), None)
            if i0 is None or j0 is None:
                sens.update({"i_base": None, "j_base": None})
                _control(ctr, "sens_base", "MEDIO", None,
                         "El caso base (g {:.2%}) queda fuera de la rejilla del motor, que limita g a {:.2%} "
                         "por el WACC más bajo de la matriz".format(g_base or float("nan"), max(gs)))
            else:
                ok_c = _cuadra(grid[i0][j0], vps)
                sens.update({"i_base": i0, "j_base": j0})
                _control(ctr, "sens_base", "ALTO", ok_c, "La celda base de la sensibilidad coincide con el valor por acción de la app"
                         if ok_c else "La celda base de la sensibilidad NO coincide con el valor de la app")
                if not ok_c:
                    sens = None
        except Exception as exc:
            _control(ctr, "sensibilidad", "MEDIO", False, "No fue posible calcular la sensibilidad: " + str(exc)[:200])

    # --- Gobernanza del motor (vetos, alertas, calidad)
    for v in m.get("vetos_calidad") or []:
        _control(ctr, "veto", "CRÍTICO", False, str(v))
    for a in m.get("alertas_modelo") or []:
        _control(ctr, "alerta", "MEDIO", None, str(a))
    if m.get("nivel_calidad"):
        _control(ctr, "calidad", "ALTO", None if "BAJA" in str(m["nivel_calidad"]).upper() else True,
                 "Calidad de datos declarada por el motor: {}".format(m["nivel_calidad"]))

    snap = {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "empresa": m.get("empresa"), "ticker": m.get("ticker"), "moneda": m.get("moneda"),
            "moneda_precio": m.get("moneda_precio"), "unidad_modelo": m.get("unidad_modelo"),
            "fuente_financiera": m.get("fuente_financiera"), "fuente_mercado": m.get("fuente_mercado"),
            "fuente_precio": m.get("fuente_precio"), "fecha_precio": m.get("fecha_precio"),
            "fuente_valoracion": m.get("fuente_valoracion"), "nivel_calidad": m.get("nivel_calidad"),
            "calendario": ((m.get("bridge") or {}).get("calendario") or {}).get("nota"),
            "motor": MOTOR, "horizonte": m.get("horizonte"),
            "generado": (generado or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC"),
        },
        "tesis": {
            "vps": vps, "precio": px, "precio_original": _f(m.get("precio_mercado")), "nota_precio": nota_px,
            "upside": upside, "ev": _f(m["val_ev"]), "equity": _f(m["val_equity"]),
            "equity_pesimista": _f(m.get("equity_pesimista")),
            "vps_pesimista": _vps(m.get("equity_pesimista"), m.get("acciones")),
            "acciones": _f(m.get("acciones")), "decision_modelo": m.get("decision_modelo"),
            "decision_texto": str(decision_text or "")[:1800],
        },
        "proyeccion": filas,
        "wacc": wacc_blk,
        "terminal": {"g": g_in, "g_usada": g_us, "tv_pct_ev": tv_pct, "ev_ebitda_salida": _f(m.get("ev_ebitda_salida_modelo")),
                     "wacc": wacc},
        "puente": puente,
        "sensibilidad": sens,
        "soportes": [str(s) for s in (m.get("soportes_modelo") or [])],
        "controles": ctr,
    }
    snap = _json_safe(snap)
    # Huella determinística: identifica la corrida, no el momento de exportarla.
    cuerpo = {k: v for k, v in snap.items() if k != "meta"}
    cuerpo["meta"] = {k: v for k, v in snap["meta"].items() if k != "generado"}
    snap["meta"]["hash"] = hashlib.sha256(
        json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()[:12]
    return snap


def generar_html_comite(snapshot: dict[str, Any]) -> str:
    """Inserta el snapshot en la plantilla. El JSON se escapa para no cerrar el <script>."""
    with open(PLANTILLA, encoding="utf-8") as fh:
        plantilla = fh.read()
    payload = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return plantilla.replace("__SNAPSHOT__", payload, 1)


def nombre_archivo(snapshot: dict[str, Any]) -> str:
    base = str((snapshot.get("meta") or {}).get("ticker") or (snapshot.get("meta") or {}).get("empresa") or "empresa")
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "empresa"
    return "presentacion_comite_{}_{}.html".format(base, (snapshot.get("meta") or {}).get("hash", "sin_hash"))
