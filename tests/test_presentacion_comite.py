"""Pruebas de la presentación de comité (snapshot conciliado + HTML autónomo).

Corren offline con el mercado simulado de ``test_auditoria_integral``: validan que el snapshot
reproduce exactamente la corrida de la pestaña 4 y que los controles fallan cuando no cuadra.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from unittest import mock

import pytest

import modelacion_logic as L
import presentacion_comite as PC
import test_auditoria_integral as T

ISA = "ISA — Interconexión Eléctrica"
AAPL = "Apple Inc. — AAPL"


@pytest.fixture(scope="module")
def corridas():
    almacen = {}
    L.vincular_estado_sesion(almacen)
    L.limpiar_cache_mercado()
    out = {}
    with mock.patch.object(L, "_obtener_datos_mercado_sin_cache", side_effect=T._mercado_simulado), \
            mock.patch.object(L, "HAS_YF", False):
        T._registrar_runtime(*T.USUARIO[1])
        for nombre in (ISA, AAPL):
            T._correr_pestanas(nombre)
            out[nombre] = copy.deepcopy(L.metricas_valoracion_sesion(nombre))
    L.EMPRESAS_RUNTIME.pop(AAPL, None)
    L.limpiar_cache_mercado()
    L.desvincular_estado_sesion()
    return out


def _ctr(snap, cid):
    return [c for c in snap["controles"] if c["id"] == cid]


@pytest.mark.parametrize("nombre", [ISA, AAPL])
def test_snapshot_reproduce_la_corrida(corridas, nombre):
    m = corridas[nombre]
    s = PC.construir_snapshot_comite(m)
    assert _ctr(s, "conciliacion")[0]["ok"] is True
    assert _ctr(s, "identidad_fcff")[0]["ok"] is True
    assert _ctr(s, "capm")[0]["ok"] is True and _ctr(s, "wacc")[0]["ok"] is True
    assert s["tesis"]["vps"] == pytest.approx(m["vps_modelo"])
    assert s["tesis"]["ev"] == pytest.approx(m["val_ev"])
    assert s["tesis"]["equity"] == pytest.approx(m["val_equity"])
    # La pestaña 4 guarda upside en %; el snapshot lo expresa en decimal y lo verifica.
    assert s["tesis"]["upside"] == pytest.approx(m["upside"] / 100.0, abs=5e-4)
    assert s["tesis"]["upside"] == pytest.approx(m["vps_modelo"] / s["tesis"]["precio"] - 1.0)
    # La celda base de la sensibilidad es exactamente el valor por acción de la app.
    se = s["sensibilidad"]
    assert se is not None
    if se["i_base"] is not None:
        assert se["vps"][se["i_base"]][se["j_base"]] == pytest.approx(m["vps_modelo"], rel=1e-6)
        assert _ctr(s, "sens_base")[0]["ok"] is True
    else:  # caso base fuera de la rejilla del motor: advertencia explícita, nunca una celda inventada
        assert _ctr(s, "sens_base")[0]["ok"] is None
    # El puente cierra: EV + partidas = Equity.
    partidas = s["puente"]["partidas"]
    ev = next(p["valor"] for p in partidas if p["concepto"] == "Enterprise Value")
    eq = next(p["valor"] for p in partidas if p["concepto"] == "Equity atribuible")
    ajustes = sum(p["valor"] for p in partidas if p["concepto"].startswith("("))
    assert ev + ajustes == pytest.approx(eq)
    # FCFF de la cascada = FCFF guardado por el motor.
    assert [f["fcff"] for f in s["proyeccion"]] == pytest.approx(m["fcff_proy"])


def test_isa_tiene_celda_base_y_apple_no(corridas):
    assert PC.construir_snapshot_comite(corridas[ISA])["sensibilidad"]["i_base"] is not None
    assert PC.construir_snapshot_comite(corridas[AAPL])["sensibilidad"]["i_base"] is None


def test_snapshot_no_depende_de_la_ultima_empresa_calculada(corridas):
    """valoracion_dcf lee el RONIC de la sesión; el snapshot debe usar el de su propia corrida y restaurar la sesión."""
    est = {"_ronic_modo": "wacc", "_roic_referencia": {"empresa": "otra", "roic": 0.9}}
    L.vincular_estado_sesion(est)
    try:
        s = PC.construir_snapshot_comite(corridas[ISA])
        assert _ctr(s, "conciliacion")[0]["ok"] is True
        assert est["_ronic_modo"] == "wacc" and est["_roic_referencia"]["roic"] == 0.9
    finally:
        L.desvincular_estado_sesion()


def test_hash_identifica_la_corrida_no_el_momento(corridas):
    m = corridas[ISA]
    a = PC.construir_snapshot_comite(m, generado=datetime(2026, 1, 1, tzinfo=timezone.utc))
    b = PC.construir_snapshot_comite(m, generado=datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert a["meta"]["hash"] == b["meta"]["hash"]
    m2 = copy.deepcopy(m)
    m2["supuestos"]["tax"] = m2["supuestos"]["tax"] + 0.01
    assert PC.construir_snapshot_comite(m2)["meta"]["hash"] != a["meta"]["hash"]


def test_corrida_alterada_no_se_presenta_como_valida(corridas):
    m = copy.deepcopy(corridas[ISA])
    m["val_ev"] = m["val_ev"] * 1.10  # EV guardado inconsistente con sus insumos
    s = PC.construir_snapshot_comite(m)
    assert _ctr(s, "conciliacion")[0]["ok"] is False
    assert s["puente"] is None and s["sensibilidad"] is None


def test_wacc_inconsistente_se_marca(corridas):
    m = copy.deepcopy(corridas[ISA])
    m["ke_calc"] = m["ke_calc"] + 0.02
    s = PC.construir_snapshot_comite(m)
    assert _ctr(s, "capm")[0]["ok"] is False
    assert s["wacc"]["pond_ke"] is None


def test_monedas_distintas_sin_fx_bloquean_upside(corridas):
    m = copy.deepcopy(corridas[ISA])
    m.update({"moneda_precio": "USD", "fx_aplicado": None, "precio_mercado_moneda_modelo": None})
    s = PC.construir_snapshot_comite(m)
    assert s["tesis"]["upside"] is None and s["tesis"]["precio"] is None
    assert _ctr(s, "moneda_precio")[0]["ok"] is False
    assert all(u is None for fila in s["sensibilidad"]["upside"] for u in fila)


def test_faltan_datos_minimos():
    with pytest.raises(ValueError):
        PC.construir_snapshot_comite(None)
    with pytest.raises(ValueError, match="fcff_proy"):
        PC.construir_snapshot_comite({"vps_modelo": 1, "val_ev": 1, "val_equity": 1, "wacc_calc": 0.1, "bridge": {"a": 1}})


def test_html_autonomo_y_sin_inyeccion(corridas):
    m = copy.deepcopy(corridas[ISA])
    m["empresa"] = "Empresa </script><script>alert(1)</script>"
    m["alertas_modelo"] = ["<img src=x onerror=alert(2)>"]
    s = PC.construir_snapshot_comite(m)
    html = PC.generar_html_comite(s)
    assert "__SNAPSHOT__" not in html
    bloque = re.search(r'<script id="snapshot" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert "<" not in bloque and ">" not in bloque  # el JSON no puede cerrar la etiqueta
    assert json.loads(bloque)["meta"]["hash"] == s["meta"]["hash"]
    assert "onerror=alert" not in html.split('<script id="snapshot"')[0]
    # Sin dependencias de red obligatorias: solo la hoja de fuentes (opcional, con respaldo del sistema).
    externos = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert all(u.startswith("https://fonts.googleapis.com/") for u in externos)
    assert PC.nombre_archivo(s).endswith(s["meta"]["hash"] + ".html")
