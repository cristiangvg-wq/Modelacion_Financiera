"""Regresiones del formato de salida de Consulta IA."""
import modelacion_logic as logic


def test_normaliza_asteriscos_unicode_y_undefined():
    salida = logic._normalizar_latex_markdown("∗∗Identidad∗∗" + chr(10) + "undefined")
    assert "**Identidad**" in salida
    assert "undefined" not in salida


def test_envuelve_latex_sin_delimitadores():
    slash = chr(92)
    formula = slash + "text{Activo} = " + slash + "text{Pasivo} + " + slash + "text{Patrimonio}"
    salida = logic._normalizar_latex_markdown(formula)
    assert "$$" in salida
    assert slash + "text{Activo}" in salida


def test_no_modifica_bloques_de_codigo():
    fence = chr(96) * 3
    entrada = "Ejemplo:" + chr(10) + fence + "text" + chr(10) + "∗∗literal∗∗" + chr(10) + fence
    salida = logic._normalizar_latex_markdown(entrada)
    assert "∗∗literal∗∗" in salida
