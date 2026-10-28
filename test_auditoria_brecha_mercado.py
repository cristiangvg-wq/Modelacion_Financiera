"""Pruebas offline para alertas de calidad del contraste de valoración."""
from scripts.contraste_mercado_real import evaluar_calidad_valoracion


def _metricas(**overrides):
    base = {
        "moneda": "COP",
        "moneda_precio": "COP",
        "precio_mercado": 100.0,
        "vps_modelo": 90.0,
        "acciones": 100.0,
        "wacc_calc": 0.12,
        "g_usada": 0.04,
    }
    base.update(overrides)
    return base


def test_valoracion_coherente_y_con_historia_suficiente_no_genera_alertas():
    assert evaluar_calidad_valoracion(_metricas(), anios_historicos=5) == []


def test_brecha_extrema_y_solo_dos_anios_bloquean_nutresa():
    # Reproduce la escala observada en la ejecución del 28-oct-2026.
    m = _metricas(precio_mercado=322140.0, vps_modelo=3768.45, acciones=460.0,
                  wacc_calc=0.1805, g_usada=0.06)
    alertas = evaluar_calidad_valoracion(m, anios_historicos=2)
    mensajes = " | ".join(texto for _, texto in alertas)
    niveles = {nivel for nivel, _ in alertas}
    assert "BLOQUEO" in niveles
    assert "histórico insuficiente" in mensajes
    assert "brecha extrema" in mensajes


def test_moneda_no_alineada_sin_fx_bloquea():
    alertas = evaluar_calidad_valoracion(
        _metricas(moneda="USD", moneda_precio="COP", fx_aplicado=None),
        anios_historicos=5,
    )
    assert any(nivel == "BLOQUEO" and "monedas no alineadas" in msg for nivel, msg in alertas)


def test_crecimiento_terminal_mayor_o_igual_a_wacc_bloquea():
    alertas = evaluar_calidad_valoracion(_metricas(wacc_calc=0.06, g_usada=0.06), anios_historicos=5)
    assert any(nivel == "BLOQUEO" and "no es menor que WACC" in msg for nivel, msg in alertas)


def test_sin_acciones_no_se_considera_vps_validado():
    alertas = evaluar_calidad_valoracion(_metricas(acciones=None), anios_historicos=5)
    assert any(nivel == "BLOQUEO" and "acciones en circulación" in msg for nivel, msg in alertas)
