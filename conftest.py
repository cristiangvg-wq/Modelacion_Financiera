"""Configuración común de pytest."""
import pytest


@pytest.fixture(autouse=True)
def _cerrar_figuras():
    """Las pestañas devuelven figuras de Matplotlib para la interfaz (que las cierra al mostrarlas).
    En las pruebas nadie las muestra: se cierran al terminar cada prueba para no acumular memoria."""
    yield
    try:
        import matplotlib.pyplot as plt
        plt.close("all")
    except Exception:
        pass
