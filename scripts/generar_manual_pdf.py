"""Genera el Manual de Usuario en PDF a partir de docs/manual_usuario.md.

Uso (desde la raíz del repositorio):

    python scripts/generar_manual_pdf.py

Produce:
  - docs/img/*.png  → gráficos de ejemplo con los datos ficticios del caso de María.
  - docs/Manual_Usuario_Modelacion_Financiera.pdf → el archivo que descarga la app.

El texto se edita en docs/manual_usuario.md. Las líneas [[IMG:clave|Pie de foto]]
insertan el gráfico `clave` (ver GRAFICOS abajo). Volver a ejecutar el script tras
cualquier cambio de texto para regenerar el PDF.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

DOCS = RAIZ / "docs"
IMG = DOCS / "img"
FUENTE_MD = DOCS / "manual_usuario.md"
SALIDA_PDF = DOCS / "Manual_Usuario_Modelacion_Financiera.pdf"

# Paleta alineada con la app
NAVY = "#0F172A"
AZUL = "#2563EB"
TEAL = "#0D9488"
VERDE = "#059669"
AMBAR = "#D97706"
ROJO = "#DC2626"
GRIS = "#64748B"
GRIS_CLARO = "#E2E8F0"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#94A3B8",
    "axes.labelcolor": NAVY,
    "xtick.color": "#334155",
    "ytick.color": "#334155",
    "axes.titleweight": "bold",
    "axes.titlesize": 11,
    "axes.titlecolor": NAVY,
})


def _miles(x: float) -> str:
    """Formato colombiano: 25.000 / 1,8."""
    return f"{x:,.0f}".replace(",", ".")


def _guardar(fig, nombre: str) -> Path:
    IMG.mkdir(parents=True, exist_ok=True)
    ruta = IMG / f"{nombre}.png"
    fig.savefig(ruta, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return ruta


# ---------------------------------------------------------------------------
# Datos ficticios del caso de María (coherentes con la sección 3 del manual)
# Cifras del modelo en miles de millones de COP; acciones en millones.
# ---------------------------------------------------------------------------
ANIOS_HIST = [2020, 2021, 2022, 2023, 2024, 2025]
FCFF_HIST = [1520, 1610, 1180, 1650, 1720, 1800]  # 2022: año atípico
ANIOS_PROY = [2026, 2027, 2028, 2029, 2030]
FCFF_PROY = [1950, 2120, 2290, 2450, 2600]
WACC, G = 0.115, 0.04
ACCIONES = 1000.0
PRECIO = 20000.0
VPS_OBJETIVO = 25000.0


def _ev(wacc: float, g: float, fcff=FCFF_PROY) -> tuple[float, float]:
    pv = sum(f / (1 + wacc) ** (i + 1) for i, f in enumerate(fcff))
    tv = fcff[-1] * (1 + g) / (wacc - g)
    pv_tv = tv / (1 + wacc) ** len(fcff)
    return pv + pv_tv, pv_tv


EV_BASE, PV_TV_BASE = _ev(WACC, G)
# Deuda neta calibrada para que el caso base dé VPS = 25.000 COP
DEUDA_NETA = EV_BASE - VPS_OBJETIVO * ACCIONES / 1000.0


def _vps(wacc: float, g: float, fcff=FCFF_PROY) -> float:
    ev, _ = _ev(wacc, g, fcff)
    return (ev - DEUDA_NETA) / ACCIONES * 1000.0


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def g_flujo():
    pasos = [
        ("1", "Elegir la\nempresa", "Barra lateral"),
        ("2", "Revisar\nparámetros", "Barra lateral"),
        ("3", "▶ Generar\ntodo", "Botón principal"),
        ("4", "Leer la\nvaloración", "Pestañas 1 a 7"),
        ("5", "Canasta y\nsimulación", "Pestañas 8 y 9"),
    ]
    fig, ax = plt.subplots(figsize=(9, 2.1))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.2)
    ax.axis("off")
    for i, (num, titulo, donde) in enumerate(pasos):
        x = 0.15 + i * 2.0
        color = TEAL if i == 2 else NAVY
        ax.add_patch(FancyBboxPatch((x, 0.55), 1.6, 1.35, boxstyle="round,pad=0.02,rounding_size=0.15",
                                    fc=color, ec="none"))
        ax.text(x + 0.8, 1.55, num, ha="center", va="center", color="white", fontsize=9, alpha=0.7)
        ax.text(x + 0.8, 1.12, titulo, ha="center", va="center", color="white", fontsize=10.5, weight="bold")
        ax.text(x + 0.8, 0.28, donde, ha="center", va="center", color=GRIS, fontsize=8.5)
        if i < len(pasos) - 1:
            ax.annotate("", xy=(x + 2.0, 1.22), xytext=(x + 1.65, 1.22),
                        arrowprops=dict(arrowstyle="-|>", color=GRIS, lw=1.6))
    return _guardar(fig, "flujo")


def g_semaforo():
    tarjetas = [
        (VERDE, "Crecimiento (g)", "g (4 %) menor que el\nWACC (11,5 %): coherente."),
        (AMBAR, "Apalancamiento", "D/E = 2,40: elevado;\nel equity es más sensible."),
        (ROJO, "Historia", "Solo 2 años de datos:\nsube tu Excel."),
        (VERDE, "Impuestos", "Tasa 35 % en rango\nhabitual."),
    ]
    fig, ax = plt.subplots(figsize=(9, 1.7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1.7)
    ax.axis("off")
    for i, (color, titulo, texto) in enumerate(tarjetas):
        x = 0.05 + i * 2.5
        ax.add_patch(FancyBboxPatch((x, 0.1), 2.35, 1.5, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc="#F8FAFC", ec=color, lw=2))
        ax.add_patch(plt.Circle((x + 0.25, 1.28), 0.09, color=color))
        ax.text(x + 0.45, 1.28, titulo, va="center", fontsize=10, weight="bold", color=NAVY)
        ax.text(x + 0.15, 0.62, texto, va="center", fontsize=8, color="#334155")
    return _guardar(fig, "semaforo")


def g_sensibilidad():
    waccs = np.linspace(0.095, 0.14, 40)
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    for g, color, estilo in ((0.03, AZUL, "--"), (0.04, TEAL, "-"), (0.05, AMBAR, ":")):
        ax.plot(waccs * 100, [_vps(w, g) for w in waccs], color=color, ls=estilo, lw=2.2,
                label=f"g = {g*100:.0f} %")
    ax.axhline(PRECIO, color=GRIS, lw=1)
    ax.text(9.55, PRECIO - 1500, "Precio de bolsa 20.000", ha="left", fontsize=8.5, color=GRIS)
    ax.scatter([WACC * 100], [_vps(WACC, G)], color=NAVY, zorder=5, s=40)
    ax.annotate("Caso base\n25.000", (WACC * 100, _vps(WACC, G)), xytext=(12.4, 35000),
                fontsize=8.5, color=NAVY, arrowprops=dict(arrowstyle="-", color=NAVY, lw=0.8))
    ax.set_xlabel("WACC de prueba (%)")
    ax.set_ylabel("Valor por acción (COP)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _miles(v)))
    ax.set_title("Sensibilidad: un WACC más alto baja el valor")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", color=GRIS_CLARO, lw=0.8)
    return _guardar(fig, "sensibilidad")


def g_fan():
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    x_h, y_h = ANIOS_HIST, [v / 1000 for v in FCFF_HIST]
    x_p = [ANIOS_HIST[-1]] + ANIOS_PROY
    y_p = [FCFF_HIST[-1] / 1000] + [v / 1000 for v in FCFF_PROY]
    ancho = np.array([0] + [0.06 * (i + 1) for i in range(len(ANIOS_PROY))])
    ax.fill_between(x_p, np.array(y_p) - ancho * 2, np.array(y_p) + ancho * 2, color=TEAL, alpha=0.12,
                    label="Rango probable")
    ax.fill_between(x_p, np.array(y_p) - ancho, np.array(y_p) + ancho, color=TEAL, alpha=0.22)
    ax.plot(x_h, y_h, color=AZUL, lw=2.4, marker="o", ms=4, label="Historia (lo que ya pasó)")
    ax.plot(x_p, y_p, color=TEAL, lw=2.4, marker="o", ms=4, label="Proyección (lo esperado)")
    ax.scatter([2022], [FCFF_HIST[2] / 1000], marker="x", s=90, color=ROJO, zorder=6, lw=2.2,
               label="Año atípico")
    ax.axvline(2025.5, color=GRIS_CLARO, lw=1)
    ax.text(2025.6, 0.95, "hoy", color=GRIS, fontsize=8.5)
    ax.set_ylim(0.9, 3.4)
    ax.set_ylabel("Plata libre FCFF\n(billones de COP)")
    ax.set_title("Fan chart · FCFF (historia → proyección)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.grid(axis="y", color=GRIS_CLARO, lw=0.8)
    ax.set_xticks(ANIOS_HIST + ANIOS_PROY)
    return _guardar(fig, "fan")


def escenarios_datos():
    casos = {
        "Pesimista": _ev(WACC + 0.01, G - 0.005, [f * 0.92 for f in FCFF_PROY])[0],
        "Base": EV_BASE,
        "Optimista": _ev(WACC - 0.01, G + 0.003, [f * 1.06 for f in FCFF_PROY])[0],
    }
    return {k: (ev, ev - DEUDA_NETA) for k, ev in casos.items()}


def g_escenarios():
    datos = escenarios_datos()
    nombres = list(datos)
    ev = [datos[n][0] / 1000 for n in nombres]
    eq = [datos[n][1] / 1000 for n in nombres]
    x = np.arange(len(nombres))
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    b1 = ax.bar(x - 0.2, ev, 0.38, color=NAVY, label="EV · valor de todo el negocio")
    b2 = ax.bar(x + 0.2, eq, 0.38, color=TEAL, label="Equity · valor para los dueños")
    for barras in (b1, b2):
        for b in barras:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.4, f"{b.get_height():.1f}".replace(".", ","),
                    ha="center", fontsize=8.5, color=NAVY)
    ax.set_xticks(x, nombres)
    ax.set_ylabel("Billones de COP")
    ax.set_title("Escenarios pesimista · base · optimista")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_ylim(0, max(ev) * 1.25)
    ax.grid(axis="y", color=GRIS_CLARO, lw=0.8)
    return _guardar(fig, "escenarios")


def g_vpn():
    inversion = 500.0
    flujos = [130, 150, 165, 175, 185, 190]
    acumulada = [-inversion]
    for i, f in enumerate(flujos):
        acumulada.append(acumulada[-1] + f / (1 + WACC) ** (i + 1))
    anios = list(range(len(acumulada)))
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    ax.axhspan(min(acumulada) * 1.15, 0, color=ROJO, alpha=0.07)
    ax.axhspan(0, max(acumulada) * 1.4, color=VERDE, alpha=0.07)
    ax.plot(anios, acumulada, color=NAVY, lw=2.4, marker="o", ms=4)
    ax.axhline(0, color=GRIS, lw=1)
    cruce = next(i for i, v in enumerate(acumulada) if v >= 0)
    ax.annotate(f"Recuperas la inversión\n(en pesos de hoy) en el año {cruce}", (cruce, acumulada[cruce]),
                xytext=(1.2, 60), fontsize=8.5, color=NAVY,
                arrowprops=dict(arrowstyle="-", color=NAVY, lw=0.8))
    ax.text(5.9, -420, "Zona roja: aún no recuperas", ha="right", fontsize=8.5, color=ROJO)
    ax.text(4.75, 150, f"VPN final: +{acumulada[-1]:.0f} mil millones",
            ha="right", fontsize=8.5, color=VERDE, weight="bold")
    ax.set_xlabel("Año")
    ax.set_ylabel("VPN acumulada\n(miles de millones COP)")
    ax.set_title("VPN acumulada de un proyecto de 500 mil millones")
    ax.set_ylim(min(acumulada) * 1.15, max(acumulada) * 1.4)
    return _guardar(fig, "vpn")


def g_upside():
    fig, ax = plt.subplots(figsize=(7.5, 2.0))
    ax.barh([1], [PRECIO], color=GRIS, height=0.5)
    ax.barh([0], [VPS_OBJETIVO], color=TEAL, height=0.5)
    ax.set_yticks([0, 1], ["VPS modelo", "Precio de bolsa"])
    for y, v in ((1, PRECIO), (0, VPS_OBJETIVO)):
        ax.text(v + 300, y, f"{_miles(v)} COP", va="center", fontsize=9.5, color=NAVY, weight="bold")
    ax.annotate("", xy=(VPS_OBJETIVO, 0.5), xytext=(PRECIO, 0.5),
                arrowprops=dict(arrowstyle="<->", color=VERDE, lw=1.6))
    ax.text((PRECIO + VPS_OBJETIVO) / 2, 0.62, "Upside +25 %", ha="center", fontsize=9.5, color=VERDE,
            weight="bold")
    ax.set_xlim(0, 30000)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: _miles(v)))
    ax.set_title("Valor por acción del modelo vs. precio de bolsa")
    return _guardar(fig, "upside")


def g_portafolio():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.4), gridspec_kw={"width_ratios": [1, 1.4]})
    nombres, pesos = ["ACCB", "EMPX", "ACCC"], [40, 35, 25]
    colores = [AZUL, TEAL, AMBAR]
    barras = a1.barh(nombres[::-1], pesos[::-1], color=colores[::-1], height=0.55)
    for b in barras:
        a1.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, f"{b.get_width():.0f} %", va="center",
                fontsize=9.5, weight="bold", color=NAVY)
    a1.set_xlim(0, 60)
    a1.axvline(60, color=ROJO, ls=":", lw=1)
    a1.text(59, 2.45, "tope 60 %", ha="right", fontsize=8, color=ROJO)
    a1.set_title("Pesos sugeridos")
    a1.set_xlabel("% de tu dinero")

    mu = np.linspace(14.0, 21.5, 80)
    sigma = np.sqrt(169 + 3 * (mu - 14) ** 2)
    a2.plot(sigma, mu, color=NAVY, lw=2.2, label="Frontera eficiente")
    activos = {"EMPX": (22, 19, TEAL), "ACCB": (17, 15, AZUL), "ACCC": (25, 20, AMBAR)}
    for n, (s, m, c) in activos.items():
        a2.scatter([s], [m], color=c, s=55, zorder=5)
        a2.text(s + 0.35, m - 0.15, f"{n} sola", fontsize=8.5, color=c)
    a2.scatter([14], [17], marker="*", s=260, color=VERDE, zorder=6, label="Canasta de María")
    a2.annotate("17 % retorno\n14 % volatilidad", (14, 17), xytext=(17.5, 16.2), fontsize=8.5, color=VERDE,
                arrowprops=dict(arrowstyle="-", color=VERDE, lw=0.8))
    a2.set_xlabel("Volatilidad anual (%) · riesgo")
    a2.set_ylabel("Retorno esperado anual (%)")
    a2.set_title("Frontera eficiente aproximada")
    a2.set_xlim(12, 27)
    a2.legend(frameon=False, fontsize=8.5, loc="lower right")
    a2.grid(color=GRIS_CLARO, lw=0.8)
    fig.tight_layout()
    return _guardar(fig, "portafolio")


def simulacion_maria():
    from investment_simulator import simular_inversion

    return simular_inversion(
        capital=3_500_000, moneda_capital="COP", moneda_activo="COP", tasa_cop_usd=4000,
        precio_actual=PRECIO, horizonte=3,
        escenarios={"Pesimista": -0.12, "Base": 0.07, "Optimista": 0.20},
        dividend_yield=0.04, costo_compra=0.005, costo_venta=0.005, impuesto_dividendos=0.10,
    )


def g_simulador():
    res = simulacion_maria()
    tray = res["trayectoria"]
    anios = [r["Año"] for r in tray]
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    for nombre, color in (("Optimista", VERDE), ("Base", TEAL), ("Pesimista", ROJO)):
        vals = [r[nombre] / 1e6 for r in tray]
        ax.plot(anios, vals, color=color, lw=2.4, marker="o", ms=4, label=nombre)
        ax.text(anios[-1] + 0.06, vals[-1], f"{vals[-1]:.2f} M".replace(".", ","), va="center", fontsize=8.5,
                color=color, weight="bold")
    ax.axhline(3.5, color=GRIS, ls="--", lw=1)
    ax.text(0.05, 3.58, "Lo invertido: 3,5 M", fontsize=8.5, color=GRIS)
    ax.set_xticks(anios, [f"Año {a}" for a in anios])
    ax.set_xlim(-0.1, anios[-1] + 0.55)
    ax.set_ylabel("Millones de COP")
    ax.set_title("Evolución estimada del capital de María")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.grid(axis="y", color=GRIS_CLARO, lw=0.8)
    return _guardar(fig, "simulador")


GRAFICOS = {
    "flujo": g_flujo,
    "semaforo": g_semaforo,
    "sensibilidad": g_sensibilidad,
    "fan": g_fan,
    "escenarios": g_escenarios,
    "vpn": g_vpn,
    "upside": g_upside,
    "portafolio": g_portafolio,
    "simulador": g_simulador,
}


# ---------------------------------------------------------------------------
# Markdown → PDF (subconjunto: títulos, párrafos, listas, tablas, citas, imágenes)
# ---------------------------------------------------------------------------
_EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿️❓]")


def _sin_emoji(t: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI.sub("", t)).strip()


def _inline(t: str) -> str:
    t = _sin_emoji(t) if _EMOJI.search(t) else t
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t


def _fuentes():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", str(base / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(base / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(base / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", str(base / "DejaVuSans-BoldOblique.ttf")))
    from reportlab.lib.fonts import addMapping

    addMapping("DejaVu", 0, 0, "DejaVu")
    addMapping("DejaVu", 1, 0, "DejaVu-Bold")
    addMapping("DejaVu", 0, 1, "DejaVu-Oblique")
    addMapping("DejaVu", 1, 1, "DejaVu-BoldOblique")


def construir_pdf(md_path: Path = FUENTE_MD, salida: Path = SALIDA_PDF) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (CondPageBreak, Image, KeepTogether, ListFlowable, ListItem, PageBreak,
                                    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    _fuentes()
    c_navy, c_teal, c_gris = colors.HexColor(NAVY), colors.HexColor(TEAL), colors.HexColor(GRIS)
    est = {
        "body": ParagraphStyle("body", fontName="DejaVu", fontSize=10, leading=14.5, spaceAfter=6,
                               textColor=colors.HexColor("#1E293B")),
        "h1": ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=26, leading=32, textColor=c_navy,
                             alignment=TA_CENTER, spaceAfter=10),
        "sub": ParagraphStyle("sub", fontName="DejaVu", fontSize=12, leading=17, textColor=c_gris,
                              alignment=TA_CENTER),
        "h2": ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=16, leading=21, textColor=colors.white,
                             backColor=c_navy, borderPadding=(7, 8, 7, 8), spaceBefore=6, spaceAfter=14),
        "h3": ParagraphStyle("h3", fontName="DejaVu-Bold", fontSize=12.5, leading=16, textColor=c_teal,
                             spaceBefore=12, spaceAfter=6),
        "quote": ParagraphStyle("quote", fontName="DejaVu-Oblique", fontSize=9.5, leading=13.5,
                                textColor=colors.HexColor("#334155"), backColor=colors.HexColor("#F1F5F9"),
                                borderColor=c_teal, borderWidth=0, borderPadding=8, leftIndent=8,
                                spaceBefore=4, spaceAfter=10),
        "cell": ParagraphStyle("cell", fontName="DejaVu", fontSize=8.8, leading=11.5),
        "cellh": ParagraphStyle("cellh", fontName="DejaVu-Bold", fontSize=8.8, leading=11.5,
                                textColor=colors.white),
        "cap": ParagraphStyle("cap", fontName="DejaVu-Oblique", fontSize=8.5, leading=11.5, textColor=c_gris,
                              alignment=TA_CENTER, spaceAfter=10),
        "toc": ParagraphStyle("toc", fontName="DejaVu", fontSize=11, leading=20, textColor=c_navy),
    }
    ancho_util = A4[0] - 4 * cm

    lineas = md_path.read_text(encoding="utf-8").splitlines()
    story = []
    titulo = _sin_emoji(lineas[0].lstrip("# ").strip())
    subtitulo = lineas[2].strip() if len(lineas) > 2 else ""
    secciones = [_sin_emoji(l[3:]) for l in lineas if l.startswith("## ")]

    # Portada
    story += [Spacer(1, 4.2 * cm), Paragraph(titulo, est["h1"]), Spacer(1, 4), Paragraph(_inline(subtitulo), est["sub"]),
              Spacer(1, 1.2 * cm)]
    portada = IMG / "flujo.png"
    if portada.exists():
        story.append(Image(str(portada), width=ancho_util, height=ancho_util * 2.1 / 9))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("<b>Contenido</b>", est["toc"]))
    for s in secciones:
        story.append(Paragraph(_inline(s), est["toc"]))
    story.append(PageBreak())

    i = 3
    primera_h2 = True
    parrafo: list[str] = []

    def vaciar():
        if parrafo:
            story.append(Paragraph(_inline(" ".join(parrafo)), est["body"]))
            parrafo.clear()

    while i < len(lineas):
        l = lineas[i].rstrip()
        if not l.strip():
            vaciar(); i += 1; continue
        if l.startswith("## "):
            vaciar()
            if not primera_h2:
                story.append(PageBreak())
            primera_h2 = False
            story.append(Paragraph(_inline(l[3:]), est["h2"]))
        elif l.startswith("### "):
            vaciar()
            story.append(CondPageBreak(3.5 * cm))
            story.append(Paragraph(_inline(l[4:]), est["h3"]))
        elif l.strip() == "---":
            vaciar(); story.append(Spacer(1, 6))
        elif l.startswith("> "):
            vaciar(); story.append(Paragraph(_inline(l[2:]), est["quote"]))
        elif l.startswith("[[IMG:"):
            vaciar()
            clave, _, pie = l.strip()[6:-2].partition("|")
            ruta = IMG / f"{clave}.png"
            from PIL import Image as PILImage

            with PILImage.open(ruta) as im:
                w, h = im.size
            ancho = ancho_util if w / h > 2.2 else ancho_util * 0.88
            story.append(KeepTogether([Spacer(1, 4), Image(str(ruta), width=ancho, height=ancho * h / w),
                                       Spacer(1, 3), Paragraph(_inline(pie), est["cap"])]))
        elif l.startswith("|"):
            vaciar()
            filas = []
            while i < len(lineas) and lineas[i].startswith("|"):
                celdas = [c.strip() for c in lineas[i].strip().strip("|").split("|")]
                if not all(set(c) <= {"-", ":"} for c in celdas):
                    filas.append(celdas)
                i += 1
            ncol = len(filas[0])
            datos = [[Paragraph(_inline(c), est["cellh" if r == 0 else "cell"]) for c in fila] for r, fila in enumerate(filas)]
            if ncol == 2:
                anchos = [ancho_util * 0.34, ancho_util * 0.66]
            else:
                anchos = [ancho_util / ncol] * ncol
            t = Table(datos, colWidths=anchos, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), c_teal),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story += [t, Spacer(1, 10)]
            continue
        elif re.match(r"^(\d+)\. |^- ", l):
            vaciar()
            ordenada = bool(re.match(r"^\d+\. ", l))
            items = []
            while i < len(lineas) and re.match(r"^(\d+)\. |^- ", lineas[i]):
                txt = re.sub(r"^(\d+)\. |^- ", "", lineas[i])
                items.append(ListItem(Paragraph(_inline(txt), est["body"]), leftIndent=14))
                i += 1
            story.append(ListFlowable(items, bulletType="1" if ordenada else "bullet", start="1" if ordenada else None,
                                      bulletFontName="DejaVu-Bold" if ordenada else "DejaVu", bulletFontSize=9.5,
                                      bulletColor=c_teal, leftIndent=16))
            continue
        else:
            parrafo.append(l.strip())
        i += 1
    vaciar()

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 8)
        canvas.setFillColor(c_gris)
        canvas.drawString(2 * cm, 1.2 * cm, "Modelación Financiera · Manual de Usuario · Herramienta pedagógica, no es asesoría de inversión")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.setStrokeColor(c_teal)
        canvas.setLineWidth(2)
        canvas.line(2 * cm, A4[1] - 1.3 * cm, A4[0] - 2 * cm, A4[1] - 1.3 * cm)
        canvas.restoreState()

    salida.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(salida), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.9 * cm,
                            bottomMargin=1.9 * cm, title=titulo, author="Modelación Financiera",
                            subject="Manual de usuario de la aplicación")
    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    return salida


def main():
    for nombre, fn in GRAFICOS.items():
        fn()
    datos = escenarios_datos()
    print(f"EV base {EV_BASE:,.0f} · deuda neta calibrada {DEUDA_NETA:,.0f} · TV/EV {PV_TV_BASE / EV_BASE:.0%}")
    for k, (ev, eq) in datos.items():
        print(f"  {k}: EV {ev:,.0f} · equity {eq:,.0f} · VPS {eq / ACCIONES * 1000:,.0f}")
    ruta = construir_pdf()
    print(f"PDF generado: {ruta.relative_to(RAIZ)} ({os.path.getsize(ruta) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
