"""El manual de usuario en PDF existe, es válido y la app lo ofrece desde el inicio."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PDF = RAIZ / "docs" / "Manual_Usuario_Modelacion_Financiera.pdf"
MD = RAIZ / "docs" / "manual_usuario.md"


def test_pdf_del_manual_existe_y_es_pdf():
    assert PDF.is_file(), "Ejecuta: python scripts/generar_manual_pdf.py"
    datos = PDF.read_bytes()
    assert datos.startswith(b"%PDF")
    assert 50_000 < len(datos) < 10_000_000


def test_imagenes_referenciadas_existen():
    claves = re.findall(r"\[\[IMG:([a-z_]+)\|", MD.read_text(encoding="utf-8"))
    assert claves, "El manual debería incluir imágenes de ejemplo"
    for clave in claves:
        assert (RAIZ / "docs" / "img" / f"{clave}.png").is_file(), clave


def test_app_muestra_descarga_del_manual():
    src = (RAIZ / "streamlit_app.py").read_text(encoding="utf-8")
    assert "Manual_Usuario_Modelacion_Financiera.pdf" in src
    # La tarjeta se dibuja justo después del encabezado, antes del tour y de la barra lateral.
    i_hero = src.index('class="tf-hero"')
    i_tarjeta = src.index("_tarjeta_manual_usuario()", i_hero)
    assert i_tarjeta < src.index("_tour_guiado()", i_hero)


def test_ejemplo_del_simulador_coincide_con_el_manual():
    """Las cifras del caso de María en el manual salen del simulador real."""
    from investment_simulator import simular_inversion

    r = simular_inversion(
        capital=3_500_000, moneda_capital="COP", moneda_activo="COP", tasa_cop_usd=4000,
        precio_actual=20000, horizonte=3,
        escenarios={"Pesimista": -0.12, "Base": 0.07, "Optimista": 0.20},
        dividend_yield=0.04, costo_compra=0.005, costo_venta=0.005, impuesto_dividendos=0.10,
    )["resumen"]
    texto = MD.read_text(encoding="utf-8")
    assert r["acciones"] == 174 and "174 acciones" in texto
    for nombre in ("Pesimista", "Base", "Optimista"):
        valor = f"{r['escenarios'][nombre]['valor_final']:,.0f}".replace(",", ".")
        assert valor in texto, (nombre, valor)
