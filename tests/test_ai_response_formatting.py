"""Regresiones del formato de salida de Consulta IA."""
import modelacion_logic as logic


def test_normaliza_asteriscos_unicode_y_undefined():
    salida = logic._normalizar_latex_markdown("∗∗Identidad∗∗\\nundefined")
    assert "**Identidad**" in salida
    assert "undefined" not in salida


def test_envuelve_latex_sin_delimitadores():
    salida = logic._normalizar_latex_markdown(r"\\text{Activo} = \\text{Pasivo} + \\text{Patrimonio}")
    assert "$$" in salida
    assert r"\\text{Activo}" in salida


def test_no_modifica_bloques_de_codigo():
    entrada = "Ejemplo:\\n```text\\n∗∗literal∗∗\\n```"
    salida = logic._normalizar_latex_markdown(entrada)
    assert "∗∗literal∗∗" in salida
