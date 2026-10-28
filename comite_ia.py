"""Comité de inversión con IA (pestaña 4) — versión 2.

Flujo en dos pasos, separando HECHOS de JUICIO:

  1. Hechos de mercado (``recopilar_hechos``): instantánea Yahoo + anclas macro del
     código + (solo Gemini) una llamada con búsqueda web que devuelve hechos con fuente
     y fecha. Cada hecho web se verifica contra las fuentes que la API realmente
     consultó (groundingMetadata) y se descartan los vencidos o sin respaldo.
  2. Dictamen (``razonar_dictamen``): una llamada SIN búsqueda que solo puede usar el
     modelo, las anclas de precio objetivo calculadas por el código y la hoja de hechos.
     Devuelve JSON con esquema; ``validar_dictamen`` lo audita (vocabulario, vetos,
     divergencia con el motor, precio objetivo dentro del rango de anclas, ids de hechos
     y anclas existentes) y se reintenta una vez con los errores.

El precio objetivo nunca lo inventa la IA: elige o pondera entre anclas que calcula
``calcular_anclas`` (DCF base, escenarios, WACC por paridad, RONIC, múltiplo de pares,
consenso de analistas).

Los resultados se guardan por sesión con una clave de los insumos (caché + historial).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import math
import re
from urllib.parse import urlparse

import modelacion_logic as L

VERSION_COMITE = "comite-ia-v2 (2026-10-27)"
VOCAB = ("COMPRAR", "MANTENER", "VENDER")
HECHOS_TTL_SEG = 6 * 3600          # los hechos web de un emisor se reutilizan 6 h
HECHO_MAX_DIAS = 400               # un hecho más viejo que esto no describe la coyuntura
TOLERANCIA_RANGO_ANCLAS = 0.03     # el objetivo puede salirse ±3 % del rango de anclas
MAX_HISTORIAL = 50

_CACHE_HECHOS = {}                 # (ticker, bloque de 6 h) -> lista de hechos web (datos públicos)

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _num(v):
    try:
        if v is None or isinstance(v, bool):
            return None
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _hoy():
    return _dt.date.today()


def _dominio(url_o_titulo):
    t = str(url_o_titulo or "").strip().lower()
    if not t:
        return ""
    host = urlparse(t).netloc if "://" in t else t.split("/")[0]
    host = host.split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _extraer_json(texto):
    """JSON desde la respuesta: objeto/arreglo completo o el primer bloque balanceado."""
    if not texto:
        return None
    t = str(texto).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I | re.S).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for abre, cierra in (("{", "}"), ("[", "]")):
        i = t.find(abre)
        if i < 0:
            continue
        nivel, en_cadena, esc = 0, False, False
        for j in range(i, len(t)):
            c = t[j]
            if en_cadena:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    en_cadena = False
                continue
            if c == '"':
                en_cadena = True
            elif c == abre:
                nivel += 1
            elif c == cierra:
                nivel -= 1
                if nivel == 0:
                    try:
                        return json.loads(t[i:j + 1])
                    except Exception:
                        break
    return None


def _fmt(v, dec=2, suf=""):
    v = _num(v)
    return "N/D" if v is None else f"{v:,.{dec}f}{suf}"


def _pct(v):
    v = _num(v)
    return "N/D" if v is None else f"{v * 100:.2f} %"


def _motor(m):
    d = str(m.get("decision_modelo") or "").upper()
    veto = bool(m.get("control_calidad_modelo") or m.get("vetos_calidad") or "RECALIBRAR MODELO" in d)
    favorable = ("FAVORABLE" in d or "POSITIVO" in d) and not veto
    prudente = ("EVITAR" in d or "NEUTRAL" in d or "MONITOREAR" in d)
    return veto, favorable, prudente


# ---------------------------------------------------------------------------
# Anclas de precio objetivo (calculadas por el código)
# ---------------------------------------------------------------------------


def _vps_desde_equity(equity, acciones):
    equity, acciones = _num(equity), _num(acciones)
    if equity is None or not acciones or acciones <= 0:
        return None
    return equity * 1000.0 / acciones


def _a_moneda_precio(vps_modelo, m):
    """VPS en moneda del modelo → moneda de cotización (misma tasa que usó la pestaña 4)."""
    vps_modelo = _num(vps_modelo)
    if vps_modelo is None:
        return None
    mm = str(m.get("moneda") or "").upper()
    mp = str(m.get("moneda_precio") or mm).upper()
    if not mm or not mp or mm == mp:
        return vps_modelo
    px, px_mod = _num(m.get("precio_mercado")), _num(m.get("precio_mercado_moneda_modelo"))
    if px and px_mod:
        return vps_modelo * px / px_mod
    conv = L.convertir_precio_a_moneda_modelo(vps_modelo, mm, mp)
    return _num(conv.get("precio")) if conv.get("convertido") else None


def _multiplos_pares(nombre_empresa, moneda=None):
    """Mediana EV/EBITDA de pares OBSERVADOS en mercado (excluye estimados y la empresa focal).

    Si hay al menos 2 pares que reportan en la misma moneda que la empresa, se usan solo esos:
    aplicar a ISA (COP) el múltiplo de utilities de EE. UU. (≈ 13x) ignora el riesgo país.
    """
    filas = None
    try:
        t6 = (L.RESULTADOS_SESION.get("tabs") or {}).get("6") or {}
        if L.RESULTADOS_SESION.get("empresa") == nombre_empresa:
            filas = t6.get("multiplos_pares")
    except Exception:
        filas = None
    if filas is None:
        try:
            df_raw, _notas, _res = L.construir_tabla_sectorial_live(nombre_empresa_focal=nombre_empresa)
            focal = L._nombre_corto(nombre_empresa).upper()
            filas = [{"empresa": str(r.get("Nombre") or r.get("Empresa")),
                      "ev_ebitda": _num(r.get("EV/EBITDA (x)")),
                      "fuente": str(r.get("Fuente múltiplo") or ""),
                      "moneda": str(r.get("Moneda") or ""),
                      "es_focal": str(r.get("Empresa") or "").upper() == focal}
                     for _, r in df_raw.iterrows()]
        except Exception:
            filas = []
    observados = [f for f in filas or []
                  if not f.get("es_focal") and f.get("ev_ebitda") and 1.0 <= f["ev_ebitda"] <= 50.0
                  and (str(f.get("fuente", "")).startswith("Yahoo") or str(f.get("fuente", "")).startswith("Aprox"))]
    mon = str(moneda or "").upper()
    misma = [f for f in observados if mon and str(f.get("moneda") or "").upper() == mon]
    if len(misma) >= 2:
        observados = misma
    vals = sorted(f["ev_ebitda"] for f in observados)
    if len(vals) < 2:
        return None, observados
    n = len(vals)
    mediana = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return mediana, observados


def calcular_anclas(nombre_empresa, m, contexto_mercado=None):
    """Anclas de valor por acción en moneda del modelo y de cotización.

    Devuelve {"anclas": [...], "rango": (min, max) en moneda de cotización, "moneda": …,
              "pares": [...], "escenarios": [...]}. Cada ancla: id, nombre, metodo,
    vps_modelo, vps_precio. Las que no se pueden calcular simplemente no aparecen.
    """
    anclas, escenarios = [], []
    bp = dict(m.get("bridge") or {})
    acc = _num(m.get("acciones")) or _num(bp.get("acciones"))
    fcff = [x for x in (m.get("fcff_proy") or []) if _num(x) is not None]
    nopat = _num(m.get("nopat_final"))
    sup = m.get("supuestos") or {}
    mid = bool(sup.get("mid_year", True))
    gmax = _num(sup.get("g_max_macro")) or 0.06
    g = _num(m.get("g"))
    wacc = _num(m.get("wacc_calc"))

    def agregar(id_, nombre, metodo, vps_mod):
        vps_mod = _num(vps_mod)
        if vps_mod is None or vps_mod <= 0:
            return
        anclas.append({"id": id_, "nombre": nombre, "metodo": metodo,
                       "vps_modelo": vps_mod, "vps_precio": _a_moneda_precio(vps_mod, m)})

    agregar("A1", "DCF base del modelo", "FCFF descontado al WACC del modelo (pestaña 4)", m.get("vps_modelo"))

    # Escenarios de la pestaña 2 (misma empresa)
    try:
        t2 = (L.RESULTADOS_SESION.get("tabs") or {}).get("2") or {}
        if L.RESULTADOS_SESION.get("empresa") == nombre_empresa:
            for r in t2.get("tabla_escenarios") or []:
                esc = str(r.get("Escenario") or "")
                vps = _vps_desde_equity(r.get("Equity Value"), acc)
                escenarios.append({"escenario": esc, "wacc_pct": _num(r.get("WACC (%)")),
                                   "g_pct": _num(r.get("g (%)")), "vps_modelo": vps,
                                   "vps_precio": _a_moneda_precio(vps, m)})
                if esc in ("Pesimista", "Optimista"):
                    agregar("A2" if esc == "Pesimista" else "A3", f"DCF escenario {esc.lower()}",
                            "Escenario de la pestaña 2 (shocks de flujos, WACC y g)", vps)
    except Exception:
        pass

    if fcff and acc and wacc and g is not None:
        # WACC por paridad USD + Fisher (solo modelos en COP)
        w_par = _num(m.get("wacc_paridad_usd"))
        if w_par and w_par > g + 0.005:
            try:
                v = L.valorar_con_bridge(fcff, w_par, g, bp, mid_year=mid, g_max_macro=gmax, nopat_final=nopat)
                agregar("A4", "DCF con WACC por paridad USD", f"Mismos flujos descontados a {w_par * 100:.2f} %",
                        _vps_desde_equity(v.get("Equity_Value"), acc))
            except Exception:
                pass
        # RONIC > WACC: crecimiento que crea valor (la mitad del exceso de ROIC, con techo)
        roic = _num(m.get("roic_calc"))
        if roic is not None and roic > wacc and nopat:
            spread = min(0.5 * (roic - wacc), L.RONIC_SPREAD_MAX)
            try:
                v = L.valoracion_dcf(fcff, wacc, g, deuda_neta=bp.get("deuda_neta", 0), caja=bp.get("caja", 0),
                                     nci=bp.get("nci", 0), otros_claims=bp.get("otros_claims", 0),
                                     asociados=bp.get("asociados", 0), acciones=acc, mid_year=mid,
                                     g_max_macro=gmax, nopat_final=nopat, ronic_spread=spread,
                                     deuda_es_bruta=bool(bp.get("deuda_es_bruta")))
                agregar("A5", "DCF con RONIC > WACC", f"Spread RONIC−WACC {spread * 100:.1f} pp (½ del exceso de ROIC)",
                        _vps_desde_equity(v.get("Equity_Value"), acc))
            except Exception:
                pass

    # Múltiplo EV/EBITDA de pares observados
    mult, pares = _multiplos_pares(nombre_empresa, m.get("moneda"))
    eb = _num(m.get("ebitda_ultimo_hist"))
    if mult and eb and eb > 0 and acc:
        eq = mult * eb - float(bp.get("deuda_neta") or 0) - float(bp.get("nci") or 0) \
            - float(bp.get("otros_claims") or 0) + float(bp.get("asociados") or 0)
        if bp.get("deuda_es_bruta"):
            eq += float(bp.get("caja") or 0)
        agregar("A6", "Múltiplo EV/EBITDA de pares", f"Mediana {mult:.1f}x de {len(pares)} pares × EBITDA último",
                _vps_desde_equity(eq, acc))

    # Múltiplo de la industria según Damodaran (agregado anual, región del emisor)
    dm = m.get("damodaran_multiplo")  # False = desactivado explícitamente
    if dm is None:
        try:
            dm = L.damodaran_empresa(nombre_empresa).get("multiplo")
        except Exception:
            dm = None
    if dm and eb and eb > 0 and acc:
        eq = float(dm["ev_ebitda"]) * eb - float(bp.get("deuda_neta") or 0) - float(bp.get("nci") or 0) \
            - float(bp.get("otros_claims") or 0) + float(bp.get("asociados") or 0)
        if bp.get("deuda_es_bruta"):
            eq += float(bp.get("caja") or 0)
        agregar("A8", "Múltiplo de industria (Damodaran)",
                f"{dm['ev_ebitda']:.1f}x «{dm['industria']}» {dm['region']} ({int(dm.get('n_firmas') or 0)} firmas, {dm.get('fecha')}) × EBITDA último",
                _vps_desde_equity(eq, acc))

    # Consenso de analistas (ya en moneda de cotización)
    cm = contexto_mercado or {}
    obj = _num(cm.get("objetivo_analistas"))
    n_an = _num(cm.get("n_analistas"))
    if obj and obj > 0 and (n_an or 0) >= 1:
        anclas.append({"id": "A7", "nombre": "Consenso de analistas (Yahoo)",
                       "metodo": f"Objetivo medio de {int(n_an)} analistas", "vps_modelo": None, "vps_precio": obj})

    # Anclas internas atípicas (< ½ o > 2× la mediana de las anclas del modelo) se informan pero no
    # amplían el rango permitido: un múltiplo de pares de otro mercado o un pesimista extremo dejaban
    # el control de precio objetivo sin efecto (ISA: 5.100–62.400 COP). El DCF base (A1) y el
    # consenso externo (A7) siempre cuentan.
    internas = [a["vps_precio"] for a in anclas if a["id"] not in ("A1", "A7") and _num(a.get("vps_precio"))]
    base_med = sorted(internas + [a["vps_precio"] for a in anclas if a["id"] == "A1" and _num(a.get("vps_precio"))])
    descartadas = []
    if len(base_med) >= 3:
        n = len(base_med)
        med = base_med[n // 2] if n % 2 else (base_med[n // 2 - 1] + base_med[n // 2]) / 2
        validas = []
        for a in anclas:
            v = _num(a.get("vps_precio"))
            if a["id"] not in ("A1", "A7") and v and not (0.5 * med <= v <= 2.0 * med):
                descartadas.append(dict(a, motivo=f"atípica frente a la mediana de las anclas del modelo ({med:,.2f})"))
            else:
                validas.append(a)
        anclas = validas
    vals = [a["vps_precio"] for a in anclas if _num(a.get("vps_precio"))]
    rango = (min(vals), max(vals)) if vals else None
    return {"anclas": anclas, "descartadas": descartadas, "rango": rango,
            "moneda": m.get("moneda_precio") or m.get("moneda"),
            "pares": pares, "multiplo_pares": mult, "escenarios": escenarios}


# ---------------------------------------------------------------------------
# Paso 1 · hechos de mercado
# ---------------------------------------------------------------------------

_SISTEMA_HECHOS = (
    "Eres un analista de investigación de renta variable. Usa la búsqueda web para reunir HECHOS "
    "recientes y verificables; no opinas ni recomiendas. Respondes SOLO con JSON válido."
)


def _prompt_hechos(empresa, ticker, sector, moneda):
    hoy = _hoy().isoformat()
    return f"""Fecha de hoy: {hoy}. Emisor: {empresa} ({ticker or 's/ticker'}), sector {sector or 'N/D'}, moneda {moneda or 'N/D'}.

Busca en la web y devuelve entre 6 y 12 hechos de los últimos 12 meses que afecten su valoración:
resultados trimestrales y guía de la compañía, eventos corporativos (adquisiciones, ventas de activos, emisiones,
dividendos, cambios de gobierno corporativo), regulación y tarifas, precio de la materia prima si aplica,
política monetaria, tasas y riesgo país de su mercado, y la cotización o rating recientes.

Reglas: cada hecho con una cifra o un evento concreto, la fecha del dato (no la de publicación si difiere) y la
URL exacta de la fuente consultada. Prioriza emisor, regulador, banco central y prensa financiera. Nada de opiniones
ni proyecciones propias.

Formato (solo el JSON, sin texto alrededor):
{{"hechos": [{{"categoria": "resultados|guia|corporativo|regulacion|materia_prima|macro|mercado",
  "hecho": "frase de máximo 30 palabras", "valor": "cifra con unidad o null", "fecha": "AAAA-MM-DD",
  "fuente": "nombre del medio o entidad", "url": "https://..."}}]}}"""


def _hechos_instantanea(cm, m):
    """Hechos verificados por la app (Yahoo + anclas macro del código)."""
    hechos = []
    mon = m.get("moneda_precio") or m.get("moneda") or ""
    fecha_px = str(cm.get("fecha_precio") or "")[:10] or None

    def add(cat, hecho, valor, fecha, fuente):
        hechos.append({"id": f"Y{len(hechos) + 1}", "categoria": cat, "hecho": hecho, "valor": valor,
                       "fecha": fecha, "fuente": fuente, "url": None, "verificado": True, "origen": "app"})

    if _num(cm.get("precio")):
        add("mercado", "Cotización de cierre", f"{_fmt(cm['precio'])} {mon}", fecha_px, cm.get("fuente_precio") or "Yahoo Finance")
    rg = cm.get("rango_52s")
    if rg:
        add("mercado", "Rango de 52 semanas", f"{_fmt(rg[0])} – {_fmt(rg[1])} {mon}", fecha_px, "Yahoo Finance")
    if _num(cm.get("variacion_12m_pct")) is not None:
        add("mercado", "Variación de la acción en 12 meses", _fmt(cm["variacion_12m_pct"], 1, " %"), fecha_px, "Yahoo Finance")
    for k, lab in (("pe", "P/E"), ("pe_forward", "P/E forward"), ("ev_ebitda_yahoo", "EV/EBITDA"), ("beta_yahoo", "Beta")):
        if _num(cm.get(k)):
            add("mercado", f"{lab} de mercado", _fmt(cm[k], 2), fecha_px, "Yahoo Finance")
    if _num(cm.get("ev_ebitda_mercado")):
        add("mercado", "EV/EBITDA de mercado con el puente del modelo", _fmt(cm["ev_ebitda_mercado"], 1, "x"), fecha_px, "Cálculo de la app")
    if _num(cm.get("objetivo_analistas")):
        ob = cm.get("objetivo_rango")
        add("mercado", f"Consenso de analistas ({cm.get('recomendacion_analistas') or 'N/D'}, n={_fmt(cm.get('n_analistas'), 0)})",
            f"{_fmt(cm['objetivo_analistas'])} {mon}" + (f" (rango {_fmt(ob[0])} – {_fmt(ob[1])})" if ob else ""),
            fecha_px, "Yahoo Finance")
    for t in (cm.get("titulares") or [])[:5]:
        add("mercado", f"Titular reciente: {t}", None, fecha_px, "Yahoo Finance (noticias)")
    mac = cm.get("macro") or {}
    asof = str(mac.get("as_of") or L.CAPM_AS_OF)
    if _num(mac.get("ust10")) is not None:
        add("macro", "Rendimiento del Tesoro de EE. UU. a 10 años", _pct(mac["ust10"]), asof, "Constantes del modelo (CAPM_POR_MERCADO)")
    if _num(mac.get("tes10")) is not None:
        add("macro", "Rendimiento TES a 10 años (Colombia)", _pct(mac["tes10"]), asof, "Constantes del modelo (CAPM_POR_MERCADO)")
    dco, dus = mac.get("damodaran_co") or {}, mac.get("damodaran_us") or {}
    if dco.get("crp") is not None:
        add("macro", f"Prima de riesgo país de Colombia (calificación {dco.get('rating')})",
            f"{dco['crp'] * 100:.2f} % (ERP total {dco['erp_total'] * 100:.2f} %)", dco.get("fecha"), "Damodaran, NYU Stern")
    elif _num(mac.get("cds_co")) is not None:
        add("macro", "CDS de Colombia a 5 años", _fmt(mac["cds_co"] * 1e4, 0, " pb"), asof, "Constantes del modelo (RIESGO_PAIS_CDS)")
    if dus.get("erp_us") is not None:
        add("macro", "Prima de riesgo de mercado de EE. UU. (implícita)", f"{dus['erp_us'] * 100:.2f} %", dus.get("fecha"), "Damodaran, NYU Stern")
    dm = cm.get("damodaran_multiplo") or m.get("damodaran_multiplo")
    if dm:
        add("mercado", f"EV/EBITDA de la industria «{dm['industria']}» ({dm['region']}, {int(dm.get('n_firmas') or 0)} firmas)",
            f"{dm['ev_ebitda']:.1f}x", dm.get("fecha"), "Damodaran, NYU Stern")
    if _num(mac.get("inflacion_lp_co")) is not None:
        add("macro", "Inflación implícita de largo plazo en Colombia", _pct(mac["inflacion_lp_co"]), asof, "Constantes del modelo (INFLACION_LP)")
    return hechos


def _depurar_hechos_web(crudos, fuentes_grounding):
    """Conserva hechos con fecha válida y reciente cuya fuente coincide con lo que la API consultó."""
    dominios = {d for f in fuentes_grounding for d in (_dominio(f.get("titulo")), _dominio(f.get("url"))) if d}
    dominios.discard("vertexaisearch.cloud.google.com")
    hoy = _hoy()
    buenos, descartados = [], []
    for h in crudos or []:
        if not isinstance(h, dict) or not str(h.get("hecho") or "").strip():
            continue
        motivo = None
        try:
            f = _dt.date.fromisoformat(str(h.get("fecha") or "")[:10])
            if f > hoy + _dt.timedelta(days=1):
                motivo = "fecha futura"
            elif (hoy - f).days > HECHO_MAX_DIAS:
                motivo = f"más de {HECHO_MAX_DIAS} días"
        except ValueError:
            motivo = "sin fecha válida"
        dom = _dominio(h.get("url")) or _dominio(h.get("fuente"))
        verificado = bool(dom) and any(dom == d or dom.endswith("." + d) or d.endswith("." + dom) for d in dominios)
        if motivo is None and not verificado:
            motivo = "fuente no consultada por la búsqueda"
        item = {"categoria": str(h.get("categoria") or "otro")[:20], "hecho": str(h["hecho"]).strip()[:260],
                "valor": (str(h.get("valor"))[:80] if h.get("valor") not in (None, "", "null") else None),
                "fecha": str(h.get("fecha") or "")[:10], "fuente": str(h.get("fuente") or dom)[:80],
                "url": str(h.get("url") or "")[:400] or None, "verificado": motivo is None, "origen": "web"}
        if motivo:
            item["motivo_descarte"] = motivo
            descartados.append(item)
        else:
            buenos.append(item)
    for i, h in enumerate(buenos, 1):
        h["id"] = f"W{i}"
    return buenos, descartados


def recopilar_hechos(nombre_empresa, m, contexto_mercado, api_key=None, proveedor="gemini", buscar_web=True):
    """Paso 1. Devuelve {"hechos": [...], "descartados": [...], "fuentes": [...], "busqueda": {...}}."""
    hechos = _hechos_instantanea(contexto_mercado or {}, m)
    out = {"hechos": hechos, "descartados": [], "fuentes": [], "busqueda": {"solicitada": bool(buscar_web), "usada": False}}
    es_gemini = str(proveedor or "gemini").lower() in ("gemini", "google", "google-ai")
    if not (buscar_web and es_gemini):
        return out
    ticker = m.get("ticker") or ""
    clave = (str(ticker or nombre_empresa), int(L._time.time() // HECHOS_TTL_SEG))
    if clave in _CACHE_HECHOS:
        web = _CACHE_HECHOS[clave]
        out.update({"hechos": hechos + web["hechos"], "descartados": web["descartados"], "fuentes": web["fuentes"],
                    "busqueda": dict(web["busqueda"], cache=True)})
        return out
    emp = L.resolver_empresa(nombre_empresa) or {}
    texto = L._llamar_ia_redaccion(
        _SISTEMA_HECHOS, _prompt_hechos(nombre_empresa, ticker, emp.get("sector"), m.get("moneda")),
        temperature=0.1, api_key=api_key, proveedor=proveedor, buscar_web=True,
    )
    fuentes = L.fuentes_ultima_ia()
    estado = dict(L._almacen_estado().get("_ia_busqueda_web") or {})
    out["diagnostico"] = [{"paso": "hechos", **x} for x in (L._almacen_estado().get("_ia_diagnostico") or [])]
    crudo = _extraer_json(texto) if texto else None
    lista = (crudo.get("hechos") if isinstance(crudo, dict) else crudo) if crudo else []
    buenos, descartados = _depurar_hechos_web(lista if isinstance(lista, list) else [], fuentes)
    web = {"hechos": buenos, "descartados": descartados, "fuentes": fuentes,
           "busqueda": {"solicitada": True, "usada": bool(fuentes), "consultas": estado.get("consultas", []),
                        "error": None if texto else (L._get_ia_error() or "sin respuesta")}}
    if texto:  # no cachear un fallo
        _CACHE_HECHOS[clave] = web
        if len(_CACHE_HECHOS) > 128:
            _CACHE_HECHOS.pop(next(iter(_CACHE_HECHOS)))
    out.update({"hechos": hechos + buenos, "descartados": descartados, "fuentes": fuentes, "busqueda": web["busqueda"]})
    return out


# ---------------------------------------------------------------------------
# Paso 2 · dictamen estructurado
# ---------------------------------------------------------------------------

ESQUEMA_DICTAMEN = {
    "type": "OBJECT",
    "properties": {
        "analisis_interno": {"type": "OBJECT", "properties": {
            "resumen": {"type": "STRING"},
            "supuestos_fragiles": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "supuesto": {"type": "STRING"}, "impacto": {"type": "STRING"}}, "required": ["supuesto", "impacto"]}},
        }, "required": ["resumen", "supuestos_fragiles"]},
        "contexto_mercado": {"type": "OBJECT", "properties": {
            "resumen": {"type": "STRING"},
            "hechos_usados": {"type": "ARRAY", "items": {"type": "STRING"}},
        }, "required": ["resumen", "hechos_usados"]},
        "recomendacion": {"type": "STRING", "enum": list(VOCAB)},
        "precio_objetivo": {"type": "NUMBER", "nullable": True},
        "anclas_usadas": {"type": "ARRAY", "items": {"type": "STRING"}},
        "metodo_precio_objetivo": {"type": "STRING"},
        "conviccion": {"type": "INTEGER"},
        "tesis": {"type": "ARRAY", "items": {"type": "STRING"}},
        "riesgos": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "riesgo": {"type": "STRING"}, "indicador": {"type": "STRING"}}, "required": ["riesgo", "indicador"]}},
        "catalizadores": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "catalizador": {"type": "STRING"}, "ventana": {"type": "STRING"}}, "required": ["catalizador", "ventana"]}},
        "cambiaria_la_recomendacion": {"type": "ARRAY", "items": {"type": "STRING"}},
        "divergencia_motor": {"type": "OBJECT", "properties": {
            "hay_divergencia": {"type": "BOOLEAN"}, "justificacion": {"type": "STRING"}},
            "required": ["hay_divergencia", "justificacion"]},
        "condicionado_a_recalibrar": {"type": "BOOLEAN"},
    },
    "required": ["analisis_interno", "contexto_mercado", "recomendacion", "precio_objetivo", "anclas_usadas",
                 "metodo_precio_objetivo", "conviccion", "tesis", "riesgos", "catalizadores",
                 "cambiaria_la_recomendacion", "divergencia_motor", "condicionado_a_recalibrar"],
}

_SISTEMA_DICTAMEN = (
    "Eres el comité de inversión institucional de renta variable de una gestora. Decides con rigor de analista "
    "sell-side senior, en español, sin adornos. Solo puedes usar: los resultados del modelo, las anclas de valor "
    "calculadas por el sistema y la hoja de hechos numerados. No tienes acceso a internet en este paso. "
    "Toda afirmación de mercado cita el id del hecho que la respalda. Respondes SOLO con JSON válido."
)


def _texto_anclas(anc):
    if not anc["anclas"]:
        return "- (sin anclas calculables: el precio objetivo debe ser null)"
    mon = anc.get("moneda") or ""
    return "\n".join(
        f"- {a['id']} · {a['nombre']}: {_fmt(a.get('vps_precio'))} {mon} — {a['metodo']}" for a in anc["anclas"]
    ) + (f"\n- Rango permitido para el precio objetivo: {_fmt(anc['rango'][0])} – {_fmt(anc['rango'][1])} {mon}"
         if anc.get("rango") else "")


def _texto_hechos(hechos):
    if not hechos:
        return "- (sin hechos)"
    return "\n".join(
        f"- {h['id']} [{h.get('categoria')}] {h['hecho']}" + (f": {h['valor']}" if h.get("valor") else "")
        + f" ({h.get('fuente') or 'N/D'}, {h.get('fecha') or 's/f'})" for h in hechos
    )


def construir_prompt_dictamen(m, anclas, hechos, contexto_mercado=None):
    mon, mon_px = m.get("moneda") or "", m.get("moneda_precio") or m.get("moneda") or ""
    veto, favorable, prudente = _motor(m)
    esc = anclas.get("escenarios") or []
    pares = anclas.get("pares") or []
    t_esc = "\n".join(
        f"- {e['escenario']}: WACC {_fmt(e.get('wacc_pct'), 2, ' %')}, g {_fmt(e.get('g_pct'), 2, ' %')}, "
        f"VPS {_fmt(e.get('vps_precio'))} {mon_px}" for e in esc) or "- N/D (pestaña 2 no ejecutada)"
    t_par = ", ".join(f"{p['empresa']} {p['ev_ebitda']:.1f}x" for p in pares[:8]) or "N/D"
    cm = contexto_mercado or {}
    return f"""EMISOR: {m.get('empresa')} ({m.get('ticker') or 's/ticker'}) · moneda del modelo {mon or 'N/D'} · cotización en {mon_px or 'N/D'} · fecha {_hoy().isoformat()}

A. RESULTADOS DEL MODELO (pestañas 1–4)
- Precio {_fmt(m.get('precio_mercado'))} {mon_px} · VPS base {_fmt(m.get('vps_modelo'))} {mon} · upside {_fmt(m.get('upside'), 1, ' %')}
- WACC modelo {_pct(m.get('wacc_calc'))} · WACC por paridad USD {_pct(m.get('wacc_paridad_usd'))} · WACC implícito en el precio {_pct(m.get('wacc_implicito_mercado'))} · Ke {_pct(m.get('ke_calc'))}
- g terminal {_pct(m.get('g_usada') if m.get('g_usada') is not None else m.get('g'))} · % del EV en valor terminal {_pct(m.get('tv_pct_ev'))} · ROIC {_pct(m.get('roic_calc'))} · D/E {_fmt(m.get('de_ratio'))}
- Margen EBITDA proyectado {_pct(m.get('margen_ebitda_proy'))} · crecimiento histórico de ingresos {_pct(m.get('g_ingresos_historico'))}
- EV/EBITDA: modelo {_fmt(cm.get('ev_ebitda_modelo'), 1, 'x')} vs mercado {_fmt(cm.get('ev_ebitda_mercado'), 1, 'x')} · pares observados: {t_par}
- Emisor de materias primas: {'sí' if m.get('emisor_ciclico') else 'no'} · crecimiento fuera de dominio del motor: {'sí' if m.get('fuera_de_dominio_crecimiento') else 'no'}
- Motor cuantitativo: {m.get('decision_modelo') or 'N/D'} · veto de calidad: {'SÍ' if veto else 'no'}
- Vetos: {'; '.join(map(str, m.get('vetos_calidad') or [])) or 'ninguno'}
- Alertas: {'; '.join(map(str, m.get('alertas_modelo') or [])) or 'ninguna'}

B. ESCENARIOS DCF (pestaña 2)
{t_esc}

C. ANCLAS DE VALOR POR ACCIÓN (calculadas por el sistema, en {mon_px})
{_texto_anclas(anclas)}

D. HOJA DE HECHOS (solo puedes citar estos ids)
{_texto_hechos(hechos)}

REGLAS
1. No inventes cifras, comparables, consensos ni eventos: lo que no esté en A–D no existe para este dictamen.
2. Si hubiera errores bloqueantes en los datos, no recomiendes: no es el caso de este contexto, que ya pasó la auditoría previa.
3. precio_objetivo: un número JSON en {mon_px}, sin separadores de miles (ej. 24500.5), dentro del rango permitido de la sección C, construido eligiendo o ponderando anclas; lista sus ids en anclas_usadas y explica la ponderación en metodo_precio_objetivo. Sin anclas → null.
4. Con veto de calidad: no puedes recomendar COMPRAR y condicionado_a_recalibrar = true (el veto no es orden de venta).
5. Si recomiendas COMPRAR con el motor prudente o VENDER con el motor favorable: divergencia_motor.hay_divergencia = true y justifícalo con cifras.
6. Si el WACC del modelo difiere > 150 pb del implícito en el precio, explica en analisis_interno qué supuesto produce la brecha (tasa local vs. paridad, crecimiento/RONIC, puente) antes de concluir caro o barato.
7. contexto_mercado.hechos_usados: los ids de D en los que se apoya el resumen (al menos 2 si existen).
8. Al menos 2 riesgos (con el indicador que los mide) y 2 catalizadores (con ventana temporal). conviccion: entero 1–10.

Devuelve SOLO este JSON:
{{"analisis_interno": {{"resumen": "...", "supuestos_fragiles": [{{"supuesto": "...", "impacto": "..."}}]}},
 "contexto_mercado": {{"resumen": "...", "hechos_usados": ["W1", "Y1"]}},
 "recomendacion": "COMPRAR|MANTENER|VENDER", "precio_objetivo": 0.0, "anclas_usadas": ["A1"],
 "metodo_precio_objetivo": "...", "conviccion": 5, "tesis": ["..."],
 "riesgos": [{{"riesgo": "...", "indicador": "..."}}], "catalizadores": [{{"catalizador": "...", "ventana": "..."}}],
 "cambiaria_la_recomendacion": ["..."], "divergencia_motor": {{"hay_divergencia": false, "justificacion": ""}},
 "condicionado_a_recalibrar": false}}"""


def normalizar_dictamen(d, anclas=None):
    """Corrige formas inocuas antes de validar: convicción "7" o 7.0, precio "24.500" o
    "24,500.5", recomendación con texto extra ("Mantener (neutral)"), objetivo escrito
    en miles (29.0 en vez de 29.000 COP cuando el rango de anclas está en miles).
    Devuelve (dictamen, notas). No inventa campos ausentes."""
    notas = []
    if not isinstance(d, dict):
        return d, notas
    d = dict(d)
    rec = str(d.get("recomendacion") or "").upper()
    rec = rec.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    hallado = [v for v in VOCAB if re.search(rf"\b{v}\b", rec)]
    if len(hallado) == 1:
        d["recomendacion"] = hallado[0]
    c = d.get("conviccion")
    if isinstance(c, str) and re.fullmatch(r"\s*\d{1,2}(?:[.,]0+)?\s*(?:/\s*10)?\s*", c):
        d["conviccion"] = int(float(re.match(r"\s*(\d{1,2})", c).group(1)))
    elif isinstance(c, float) and c.is_integer():
        d["conviccion"] = int(c)
    po = d.get("precio_objetivo")
    if isinstance(po, str):
        if po.strip().upper() in ("", "N/D", "ND", "NULL", "NONE"):
            d["precio_objetivo"] = None
        else:
            v = L._numero_texto_es_en(re.sub(r"[^\d.,]", "", po))
            if v is not None:
                d["precio_objetivo"] = v
                notas.append(f"precio_objetivo «{po}» interpretado como {v:,.2f}")
    po = _num(d.get("precio_objetivo"))
    rango = (anclas or {}).get("rango")
    if po and rango and po < rango[0] / 100 and rango[0] / 1000 * 0.97 <= po <= rango[1] / 1000 * 1.03:
        d["precio_objetivo"] = po * 1000
        notas.append(f"precio_objetivo {po} parecía escrito en miles; se usó {po * 1000:,.2f}")
    for k in ("anclas_usadas",):
        if isinstance(d.get(k), str):
            d[k] = re.findall(r"A\d{1,2}", d[k])
    ctx = d.get("contexto_mercado")
    if isinstance(ctx, dict) and isinstance(ctx.get("hechos_usados"), str):
        ctx = dict(ctx)
        ctx["hechos_usados"] = re.findall(r"[WY]\d{1,2}", ctx["hechos_usados"])
        d["contexto_mercado"] = ctx
    return d, notas


def validar_dictamen(d, m, anclas, ids_hechos):
    """Auditoría determinista del dictamen. Devuelve {"ok", "errors", "warnings"}."""
    errors, warnings = [], []
    if not isinstance(d, dict):
        return {"ok": False, "errors": ["La respuesta no es un objeto JSON"], "warnings": []}
    for k in ESQUEMA_DICTAMEN["required"]:
        if k not in d:
            errors.append(f"Falta el campo «{k}»")
    rec = str(d.get("recomendacion") or "").strip().upper()
    if rec not in VOCAB:
        errors.append(f"Recomendación «{d.get('recomendacion')}» fuera de COMPRAR/MANTENER/VENDER")
    conv = d.get("conviccion")
    if not (isinstance(conv, (int, float)) and not isinstance(conv, bool) and float(conv).is_integer() and 1 <= conv <= 10):
        errors.append(f"Convicción inválida ({conv}): debe ser un entero 1–10")

    veto, favorable, prudente = _motor(m)
    if veto:
        if rec == "COMPRAR":
            errors.append("Recomienda COMPRAR con un veto de calidad activo")
        if not d.get("condicionado_a_recalibrar"):
            errors.append("Hay veto de calidad: el dictamen debe quedar condicionado a recalibrar el modelo")
    div = d.get("divergencia_motor") if isinstance(d.get("divergencia_motor"), dict) else {}
    contradice = (rec == "COMPRAR" and prudente) or (rec == "VENDER" and favorable)
    if contradice and not (div.get("hay_divergencia") and len(str(div.get("justificacion") or "").strip()) >= 40):
        errors.append("La recomendación contradice al motor cuantitativo sin declarar y justificar la divergencia")

    ids_anclas = {a["id"] for a in anclas.get("anclas") or []}
    usadas = [str(x) for x in (d.get("anclas_usadas") or [])]
    if any(x not in ids_anclas for x in usadas):
        errors.append(f"Cita anclas inexistentes: {', '.join(x for x in usadas if x not in ids_anclas)}")
    po = _num(d.get("precio_objetivo"))
    rango = anclas.get("rango")
    if d.get("precio_objetivo") is not None and po is None:
        errors.append("precio_objetivo no es numérico")
    if po is not None:
        if not rango:
            errors.append("Hay precio objetivo sin anclas calculables: debe ser null")
        else:
            lo, hi = rango[0] * (1 - TOLERANCIA_RANGO_ANCLAS), rango[1] * (1 + TOLERANCIA_RANGO_ANCLAS)
            if not (lo <= po <= hi):
                errors.append(f"Precio objetivo {po:,.2f} fuera del rango de anclas {rango[0]:,.2f} – {rango[1]:,.2f}")
        if not usadas:
            errors.append("El precio objetivo no indica qué anclas usa")
    elif rango:
        warnings.append("Sin precio objetivo pese a existir anclas")

    ctx = d.get("contexto_mercado") if isinstance(d.get("contexto_mercado"), dict) else {}
    citados = [str(x) for x in (ctx.get("hechos_usados") or [])]
    inventados = [x for x in citados if x not in ids_hechos]
    if inventados:
        errors.append(f"Cita hechos inexistentes: {', '.join(inventados)}")
    if len(ids_hechos) >= 2 and len([x for x in citados if x in ids_hechos]) < 2:
        warnings.append("El contexto de mercado se apoya en menos de 2 hechos de la hoja")
    # ids citados dentro de los textos libres también deben existir
    libres = json.dumps(d, ensure_ascii=False)
    ya = set(inventados) | {x for x in usadas if x not in ids_anclas}
    for x in sorted(set(re.findall(r"\b([WYA]\d{1,2})\b", libres)) - ya):
        if x.startswith("A") and x not in ids_anclas:
            errors.append(f"Menciona el ancla inexistente {x}")
        elif x[0] in "WY" and x not in ids_hechos:
            errors.append(f"Menciona el hecho inexistente {x}")

    if len([r for r in d.get("riesgos") or [] if isinstance(r, dict) and r.get("riesgo")]) < 2:
        errors.append("Se requieren al menos 2 riesgos con su indicador")
    if len([c for c in d.get("catalizadores") or [] if isinstance(c, dict) and c.get("catalizador")]) < 2:
        errors.append("Se requieren al menos 2 catalizadores con su ventana")
    if not [t for t in d.get("tesis") or [] if str(t).strip()]:
        errors.append("Falta la tesis de inversión")
    w_m, w_i = _num(m.get("wacc_calc")), _num(m.get("wacc_implicito_mercado"))
    if w_m and w_i and abs(w_m - w_i) > 0.015:
        txt = str((d.get("analisis_interno") or {}).get("resumen") or "").upper()
        if "WACC" not in txt:
            warnings.append("Brecha WACC modelo vs implícito > 150 pb no explicada en el análisis interno")
    return {"ok": not errors, "errors": list(dict.fromkeys(errors)), "warnings": warnings}


def razonar_dictamen(m, anclas, hechos, api_key=None, proveedor="gemini", contexto_mercado=None, llamar=None):
    """Paso 2 (sin búsqueda). Devuelve {"dictamen", "auditoria", "intentos", "error"}.

    ``llamar`` permite inyectar otro cliente (evaluaciones); por defecto L._llamar_ia_redaccion.
    """
    llamar = llamar or L._llamar_ia_redaccion
    ids = {h["id"] for h in hechos}
    prompt = construir_prompt_dictamen(m, anclas, hechos, contexto_mercado)
    texto = llamar(_SISTEMA_DICTAMEN, prompt, temperature=0.2, api_key=api_key, proveedor=proveedor,
                   esquema_json=ESQUEMA_DICTAMEN)
    if not texto:
        return {"dictamen": None, "auditoria": None, "intentos": 1,
                "diagnostico": [{"paso": "dictamen", **x} for x in (L._almacen_estado().get("_ia_diagnostico") or [])],
                "error": L._get_ia_error() or "Sin respuesta del proveedor de IA."}
    diag = [{"paso": "dictamen", **x} for x in (L._almacen_estado().get("_ia_diagnostico") or [])]
    d, notas = normalizar_dictamen(_extraer_json(texto), anclas)
    aud = validar_dictamen(d, m, anclas, ids)
    aud["warnings"] = notas + aud["warnings"]
    if d is None:
        aud["extracto"] = str(texto)[:600]
    intentos = 1
    if not aud["ok"]:
        intentos = 2
        reintento = (
            "Tu dictamen anterior no pasó la auditoría por estos motivos:\n- " + "\n- ".join(aud["errors"])
            + "\n\nCorrígelo respetando TODAS las reglas. Contexto original a continuación.\n\n" + prompt
            + "\n\nDictamen anterior (para corregir):\n" + (json.dumps(d, ensure_ascii=False) if d else str(texto)[:4000])
        )
        texto2 = llamar(_SISTEMA_DICTAMEN, reintento, temperature=0.1, api_key=api_key, proveedor=proveedor,
                        esquema_json=ESQUEMA_DICTAMEN)
        diag += [{"paso": "dictamen (corrección)", **x} for x in (L._almacen_estado().get("_ia_diagnostico") or [])]
        if texto2:
            d2, notas2 = normalizar_dictamen(_extraer_json(texto2), anclas)
            aud2 = validar_dictamen(d2, m, anclas, ids)
            aud2["warnings"] = notas2 + aud2["warnings"]
            if d2 is None:
                aud2["extracto"] = str(texto2)[:600]
            if aud2["ok"] or (d2 and len(aud2["errors"]) < len(aud["errors"])):
                d, aud = d2, aud2
    if isinstance(d, dict):
        d["recomendacion"] = str(d.get("recomendacion") or "").strip().upper()
    return {"dictamen": d, "auditoria": aud, "intentos": intentos, "diagnostico": diag,
            "error": None if aud["ok"] else "Dictamen rechazado por la auditoría: " + "; ".join(aud["errors"])}


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------


def dictamen_a_markdown(d, anclas, hechos):
    """Texto canónico (secciones estables para el PDF de la pestaña 7 y el extractor)."""
    mon = anclas.get("moneda") or ""
    hx = {h["id"]: h for h in hechos}
    ai, ctx = d.get("analisis_interno") or {}, d.get("contexto_mercado") or {}
    lineas = ["## 1. ANÁLISIS INTERNO DEL MODELO", str(ai.get("resumen") or "")]
    for s in ai.get("supuestos_fragiles") or []:
        lineas.append(f"- {s.get('supuesto')}: {s.get('impacto')}")
    lineas += ["", "## 2. CONTEXTO DE MERCADO REAL", str(ctx.get("resumen") or "")]
    for i in ctx.get("hechos_usados") or []:
        h = hx.get(i)
        if h:
            lineas.append(f"- [{i}] {h['hecho']}" + (f": {h['valor']}" if h.get("valor") else "") + f" ({h.get('fuente')}, {h.get('fecha') or 's/f'})")
    po = _num(d.get("precio_objetivo"))
    lineas += ["", "## 3. RECOMENDACIÓN DE INVERSIÓN",
               f"- RECOMENDACIÓN FINAL: {d.get('recomendacion')}",
               f"- PRECIO OBJETIVO 12 MESES: {_fmt(po) + ' ' + mon if po is not None else 'N/D'} — {d.get('metodo_precio_objetivo') or ''}",
               f"- PUNTAJE DE CONVICCIÓN: {d.get('conviccion')}/10",
               "- TESIS DE INVERSIÓN:"]
    lineas += [f"    - {t}" for t in d.get("tesis") or []]
    div = d.get("divergencia_motor") or {}
    if div.get("hay_divergencia"):
        lineas.append(f"- DIVERGENCIA FRENTE AL MOTOR CUANTITATIVO: {div.get('justificacion')}")
    if d.get("condicionado_a_recalibrar"):
        lineas.append("- VETO DE CALIDAD: dictamen condicionado a recalibrar el modelo.")
    lineas += ["", "## 4. RIESGOS, CATALIZADORES Y PUNTOS DE MONITOREO"]
    lineas += [f"1. Riesgo: {r.get('riesgo')} (indicador: {r.get('indicador')})" for r in d.get("riesgos") or []]
    lineas += [f"- Catalizador: {c.get('catalizador')} ({c.get('ventana')})" for c in d.get("catalizadores") or []]
    lineas += [f"- Cambiaría la recomendación: {x}" for x in d.get("cambiaria_la_recomendacion") or []]
    return "\n".join(lineas)


def _e(x):
    return _html.escape(str(x if x is not None else ""))


def dictamen_a_html(res):
    d, anc, hechos = res["dictamen"], res["anclas"], res["hechos"]
    mon = anc.get("moneda") or ""
    rec = d.get("recomendacion")
    color = {"COMPRAR": "#10B981", "MANTENER": "#F59E0B", "VENDER": "#EF4444"}.get(rec, "#64748B")
    po = _num(d.get("precio_objetivo"))
    px = _num(res["metricas"].get("precio_mercado"))
    pot = f" ({(po / px - 1) * 100:+.1f} % vs precio)" if (po and px) else ""
    usadas = set(d.get("anclas_usadas") or [])
    filas_anc = "".join(
        f"<tr style='{'font-weight:700' if a['id'] in usadas else 'color:#94A3B8'}'><td>{_e(a['id'])}</td><td>{_e(a['nombre'])}</td>"
        f"<td style='text-align:right'>{_fmt(a.get('vps_precio'))}</td><td>{_e(a['metodo'])}</td></tr>"
        for a in anc.get("anclas") or []) + "".join(
        f"<tr style='color:#64748B'><td>{_e(a['id'])}</td><td>{_e(a['nombre'])} <i>(descartada)</i></td>"
        f"<td style='text-align:right'>{_fmt(a.get('vps_precio'))}</td><td>{_e(a.get('motivo'))}</td></tr>"
        for a in anc.get("descartadas") or [])
    hx = {h["id"]: h for h in hechos}
    citados = [hx[i] for i in (d.get("contexto_mercado") or {}).get("hechos_usados") or [] if i in hx]

    def fuente(h):
        f = _e(h.get("fuente") or "")
        return f'<a href="{_e(h["url"])}" target="_blank" rel="noopener">{f}</a>' if h.get("url") else f
    filas_h = "".join(
        f"<tr><td>{_e(h['id'])}</td><td>{_e(h['hecho'])}{(': <b>' + _e(h['valor']) + '</b>') if h.get('valor') else ''}</td>"
        f"<td>{_e(h.get('fecha') or 's/f')}</td><td>{fuente(h)}</td></tr>" for h in citados)
    lista = lambda xs: "".join(f"<li>{_e(x)}</li>" for x in xs)
    riesgos = "".join(f"<li>{_e(r.get('riesgo'))} <span style='color:#94A3B8'>· indicador: {_e(r.get('indicador'))}</span></li>" for r in d.get("riesgos") or [])
    catal = "".join(f"<li>{_e(c.get('catalizador'))} <span style='color:#94A3B8'>· {_e(c.get('ventana'))}</span></li>" for c in d.get("catalizadores") or [])
    frag = "".join(f"<li><b>{_e(s.get('supuesto'))}</b>: {_e(s.get('impacto'))}</li>" for s in (d.get("analisis_interno") or {}).get("supuestos_fragiles") or [])
    div = d.get("divergencia_motor") or {}
    avisos = ""
    if div.get("hay_divergencia"):
        avisos += f"<p style='color:#F59E0B'><b>Divergencia frente al motor cuantitativo:</b> {_e(div.get('justificacion'))}</p>"
    if d.get("condicionado_a_recalibrar"):
        avisos += "<p style='color:#F59E0B'><b>Veto de calidad:</b> dictamen condicionado a recalibrar el modelo.</p>"
    b = res.get("busqueda") or {}
    estado_web = ("con búsqueda web" + (" (hechos en caché)" if b.get("cache") else "")) if b.get("usada") else (
        "búsqueda web sin fuentes: solo hechos de la app" if b.get("solicitada") else "sin búsqueda web")
    desc = res.get("descartados") or []
    bloque_desc = (f"<details><summary>{len(desc)} hechos web descartados</summary><ul>"
                   + "".join(f"<li>{_e(h['hecho'])} — <i>{_e(h.get('motivo_descarte'))}</i></li>" for h in desc[:15])
                   + "</ul></details>") if desc else ""
    fuentes = res.get("fuentes") or []
    bloque_f = (f"<details><summary>Fuentes consultadas por la búsqueda ({len(fuentes)})</summary><ol>"
                + "".join(f'<li><a href="{_e(f["url"])}" target="_blank" rel="noopener">{_e(f["titulo"])}</a></li>' for f in fuentes[:15])
                + "</ol></details>") if fuentes else ""
    tabla = "style='width:100%;border-collapse:collapse;font-size:13px'"
    return f"""
<div class="section-card" style="border-left:4px solid {color}">
  <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:10px">
    <span style="padding:4px 14px;border-radius:999px;background:{color};color:#0B1220;font-weight:800;letter-spacing:.05em">{_e(rec)}</span>
    <span style="font-size:1.05rem"><b>Objetivo 12 m:</b> {_fmt(po) + ' ' + _e(mon) if po is not None else 'N/D'}{_e(pot)}</span>
    <span><b>Convicción:</b> {_e(d.get('conviccion'))}/10</span>
    <span style="color:#94A3B8;font-size:12px">{_e(res['metricas'].get('empresa'))} · {_e(res.get('proveedor'))} · {_e(estado_web)} · {_e(res.get('fecha'))}{' · reutilizado de caché' if res.get('cache') else ''}</span>
  </div>
  {avisos}
  <h4 style="margin:12px 0 4px">1 · Análisis interno del modelo</h4>
  <p>{_e((d.get('analisis_interno') or {}).get('resumen'))}</p>
  {('<ul>' + frag + '</ul>') if frag else ''}
  <h4 style="margin:12px 0 4px">2 · Contexto de mercado</h4>
  <p>{_e((d.get('contexto_mercado') or {}).get('resumen'))}</p>
  {('<div style="overflow-x:auto"><table ' + tabla + '><tr><th>Id</th><th>Hecho</th><th>Fecha</th><th>Fuente</th></tr>' + filas_h + '</table></div>') if filas_h else ''}
  <h4 style="margin:12px 0 4px">3 · Precio objetivo: anclas calculadas por el modelo</h4>
  <p style="color:#CBD5E1">{_e(d.get('metodo_precio_objetivo'))}</p>
  <div style="overflow-x:auto"><table {tabla}><tr><th>Id</th><th>Ancla</th><th style="text-align:right">VPS ({_e(mon)})</th><th>Método</th></tr>{filas_anc}</table></div>
  <h4 style="margin:12px 0 4px">Tesis</h4><ul>{lista(d.get('tesis') or [])}</ul>
  <h4 style="margin:12px 0 4px">4 · Riesgos</h4><ul>{riesgos}</ul>
  <h4 style="margin:12px 0 4px">Catalizadores</h4><ul>{catal}</ul>
  <h4 style="margin:12px 0 4px">Qué cambiaría la recomendación</h4><ul>{lista(d.get('cambiaria_la_recomendacion') or [])}</ul>
  {bloque_f}{bloque_desc}
  <p style="color:#94A3B8;font-size:12px;margin-top:10px">Apoyo a decisión generado con IA a partir del modelo y de hechos con fuente. No es asesoría de inversión personalizada.</p>
</div>"""


def texto_diagnostico(res, extracto=None):
    """Resumen técnico copiable de la última ejecución (sin claves)."""
    lineas = [f"Comité {VERSION_COMITE} · proveedor {res.get('proveedor')} · {res.get('fecha')}",
              f"Error: {res.get('error') or 'ninguno'}",
              f"Búsqueda web: {(res.get('busqueda') or {}).get('usada')} · hechos web aceptados "
              f"{len([h for h in res.get('hechos') or [] if h.get('origen') == 'web'])} · descartados {len(res.get('descartados') or [])}"]
    for x in res.get("diagnostico") or []:
        lineas.append(" · ".join(f"{k}={v}" for k, v in x.items() if v not in (None, "")))
    if extracto:
        lineas.append("Extracto de la respuesta: " + str(extracto)[:600])
    return "\n".join(lineas)


def html_diagnostico(res, extracto=None):
    return ('<details style="margin-top:8px"><summary>Diagnóstico técnico (cópialo si necesitas soporte)</summary>'
            f'<pre style="white-space:pre-wrap;font-size:12px">{_e(texto_diagnostico(res, extracto))}</pre></details>')


def _html_error(titulo, detalle):
    return (f'<div class="result-note" style="border-left:4px solid #DC2626"><b>{_e(titulo)}</b><br>'
            f'{"<br>".join(_e(x) for x in (detalle if isinstance(detalle, list) else [detalle]))}</div>')


# ---------------------------------------------------------------------------
# Orquestación, caché e historial
# ---------------------------------------------------------------------------

_CLAVES_HASH = ("empresa", "ticker", "precio_mercado", "vps_modelo", "wacc_calc", "wacc_paridad_usd",
                "wacc_implicito_mercado", "g", "g_usada", "roic_calc", "de_ratio", "val_ev", "val_equity",
                "decision_modelo", "vetos_calidad", "alertas_modelo", "moneda", "moneda_precio")


def clave_insumos(m, anclas, hechos, proveedor, buscar_web):
    def r(v):
        n = _num(v)
        return round(n, 6) if n is not None else v
    base = {k: r(m.get(k)) for k in _CLAVES_HASH}
    base["anclas"] = [(a["id"], r(a.get("vps_precio"))) for a in anclas.get("anclas") or []]
    base["hechos"] = sorted(f"{h['id']}|{h['hecho']}|{h.get('valor')}" for h in hechos)
    base["proveedor"], base["web"], base["version"] = str(proveedor), bool(buscar_web), VERSION_COMITE
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def historial_comite(nombre_empresa=None):
    h = list(L._almacen_estado().get("comite_historial") or [])
    return [x for x in h if not nombre_empresa or x.get("empresa") == nombre_empresa]


def _registrar_historial(res):
    d, m = res["dictamen"], res["metricas"]
    entrada = {
        "fecha": res["fecha"], "empresa": m.get("empresa"), "ticker": m.get("ticker"),
        "recomendacion": d.get("recomendacion"), "precio_objetivo": _num(d.get("precio_objetivo")),
        "conviccion": d.get("conviccion"), "precio_mercado": _num(m.get("precio_mercado")),
        "vps_modelo": _num(m.get("vps_modelo")), "wacc": _num(m.get("wacc_calc")),
        "wacc_implicito": _num(m.get("wacc_implicito_mercado")), "moneda": res["anclas"].get("moneda"),
        "proveedor": res.get("proveedor"), "hechos_web": len([h for h in res["hechos"] if h.get("origen") == "web"]),
        "anclas_usadas": d.get("anclas_usadas"), "clave": res["clave"], "version": VERSION_COMITE,
    }
    hist = L._almacen_estado().setdefault("comite_historial", [])
    hist.append(entrada)
    del hist[:-MAX_HISTORIAL]


def generar_dictamen(nombre_empresa, api_key=None, proveedor="gemini", metricas=None, buscar_web=True,
                     contexto_mercado=None, forzar=False):
    """Punto de entrada. Devuelve dict con ok, html, markdown, dictamen, anclas, hechos, fuentes, auditoría…"""
    m = dict(metricas or {})
    try:
        base = L._metricas_comite_para_ia(nombre_empresa)
    except Exception:
        base = {}
    for k, v in (base or {}).items():
        if m.get(k) is None:
            m[k] = v
    m.setdefault("empresa", nombre_empresa)
    res = {"ok": False, "html": "", "markdown": "", "dictamen": None, "anclas": {}, "hechos": [], "fuentes": [],
           "descartados": [], "auditoria": None, "metricas": m, "proveedor": proveedor or "gemini",
           "fecha": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "cache": False, "clave": None, "error": None}

    audit_ctx = L.auditar_contexto_comite_ia(m)
    if not audit_ctx["ok"]:
        res["error"] = "Comité IA bloqueado: corrige primero los errores del modelo."
        res["html"] = _html_error(res["error"], audit_ctx["errors"])
        return res

    cm = dict(contexto_mercado or {})
    if not cm:
        try:
            cm = L.contexto_mercado_comite(nombre_empresa, m)
        except Exception:
            cm = {}
    anclas = calcular_anclas(nombre_empresa, m, cm)
    paso1 = recopilar_hechos(nombre_empresa, m, cm, api_key=api_key, proveedor=proveedor, buscar_web=buscar_web)
    res.update({"anclas": anclas, "hechos": paso1["hechos"], "fuentes": paso1["fuentes"],
                "descartados": paso1["descartados"], "busqueda": paso1["busqueda"],
                "diagnostico": list(paso1.get("diagnostico") or [])})

    clave = clave_insumos(m, anclas, paso1["hechos"], proveedor, buscar_web)
    res["clave"] = clave
    cache = L._almacen_estado().setdefault("comite_cache", {})
    if not forzar and clave in cache:
        previo = dict(cache[clave])
        previo["cache"] = True
        previo["html"] = dictamen_a_html(previo)
        return previo

    paso2 = razonar_dictamen(m, anclas, paso1["hechos"], api_key=api_key, proveedor=proveedor, contexto_mercado=cm)
    res["auditoria"] = paso2["auditoria"]
    res["diagnostico"] = res.get("diagnostico", []) + list(paso2.get("diagnostico") or [])
    if paso2["error"] or not isinstance(paso2["dictamen"], dict):
        res["error"] = paso2["error"] or "Dictamen vacío."
        titulo = ("No se pudo generar el dictamen del comité." if paso2["auditoria"] is None
                  else "Dictamen IA rechazado por controles de calidad (se intentó una corrección automática).")
        detalle = (paso2["auditoria"] or {}).get("errors") or [res["error"]]
        res["html"] = _html_error(titulo, detalle) + html_diagnostico(res, (paso2["auditoria"] or {}).get("extracto"))
        return res
    res.update({"ok": True, "dictamen": paso2["dictamen"]})
    res["markdown"] = dictamen_a_markdown(paso2["dictamen"], anclas, paso1["hechos"])
    res["html"] = dictamen_a_html(res)
    guardado = {k: v for k, v in res.items() if k != "html"}
    cache[clave] = guardado
    if len(cache) > 20:
        cache.pop(next(iter(cache)))
    _registrar_historial(res)
    return res
