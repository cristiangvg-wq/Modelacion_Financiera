#!/usr/bin/env python3
"""Genera el informe PDF del Taller ISA 2026 a partir de las salidas del modelo.

    python scripts/generar_informe_taller_isa.py --equipo "Ana Pérez; Juan Gómez" --fecha "2026-11-05"

Todas las cifras del informe salen de ``scripts/taller_isa.run_model``: si se cambian supuestos,
se regenera el PDF y el texto se actualiza solo.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.taller_isa import (  # noqa: E402
    DECISION_THRESHOLDS, POLICIES, SCENARIO_ORDER, SCENARIOS, run_model,
)

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"


def _register_fonts():
    """DejaVu (incluida en matplotlib) cubre Δ, ≈, ≥, → y el signo menos, que Helvetica no trae."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for name, file in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"),
                       ("DV-BI", "DejaVuSans-BoldOblique.ttf"), ("DVMono", "DejaVuSansMono.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
    addMapping("DV", 0, 0, "DV")
    addMapping("DV", 1, 0, "DV-B")
    addMapping("DV", 0, 1, "DV-I")
    addMapping("DV", 1, 1, "DV-BI")


_register_fonts()

OUT_PDF = ROOT / "docs" / "Informe_Taller_ISA_2026.pdf"
PROMPTS_MD = ROOT / "docs" / "ingenieria_prompts_taller_isa.md"

INK = colors.HexColor("#1f2a37")
ACCENT = colors.HexColor("#1d4e89")
LIGHT = colors.HexColor("#e8eef6")
SC_COLORS = {"Estrés": "#8c2d2d", "Pesimista": "#d08a2e", "Base": "#1d4e89", "Optimista": "#2e7d4f"}


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------
def n0(x):
    return "N/D" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.0f}".replace(",", ".")


def pct(x, d=1):
    return "N/D" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.{d}f} %".replace(".", ",")


def pp(x, d=1):
    return f"{x * 100:+.{d}f} pp".replace(".", ",")


def loc(text: str) -> str:
    """Convierte números con formato inglés de los textos del modelo (28,193 · 26.6% · 4.0x) a formato local."""
    text = re.sub(r"(\d),(\d{3})", r"\1§\2", text)
    text = re.sub(r"(\d)\.(\d)", r"\1,\2", text)
    text = text.replace("§", ".")
    return re.sub(r"(\d)%", r"\1 %", text)


def styles():
    s = getSampleStyleSheet()
    base = ParagraphStyle("B", parent=s["Normal"], fontName="DV", fontSize=8.8, leading=12.2, textColor=INK, spaceAfter=5)
    return {
        "body": base,
        "small": ParagraphStyle("S", parent=base, fontSize=8, leading=10.5),
        "h1": ParagraphStyle("H1", parent=base, fontName="DV-B", fontSize=14, leading=18, textColor=ACCENT, spaceBefore=6, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base, fontName="DV-B", fontSize=11, leading=14, textColor=ACCENT, spaceBefore=6, spaceAfter=4),
        "title": ParagraphStyle("T", parent=base, fontName="DV-B", fontSize=22, leading=28, alignment=TA_CENTER, textColor=ACCENT),
        "center": ParagraphStyle("C", parent=base, alignment=TA_CENTER, fontSize=11, leading=15),
        "quote": ParagraphStyle("Q", parent=base, fontSize=8.5, leading=11.5, leftIndent=10, borderPadding=4,
                                backColor=LIGHT),
        "cell": ParagraphStyle("Cell", parent=base, fontSize=7.2, leading=9, spaceAfter=0),
        "cellb": ParagraphStyle("CellB", parent=base, fontSize=7.2, leading=9, spaceAfter=0, fontName="DV-B", textColor=colors.white),
    }


def table(data, st, widths=None, header=True):
    rows = [[Paragraph(str(c), st["cellb"] if (header and i == 0) else st["cell"]) for c in r] for i, r in enumerate(data)]
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c4d4")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), ACCENT)]
        style += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


def md_inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<font face='DVMono'>\1</font>", text)
    return text


def markdown_to_story(md: str, st: dict) -> list:
    """Conversor mínimo de Markdown (encabezados, párrafos, citas, viñetas, tablas)."""
    story, buf_table = [], []

    def flush_table():
        if buf_table:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in buf_table
                    if not re.match(r"^\s*\|?\s*-{3,}", r)]
            story.append(table([[md_inline(c) for c in r] for r in rows], st))
            story.append(Spacer(1, 4))
            buf_table.clear()

    for line in md.splitlines():
        if line.strip().startswith("|"):
            buf_table.append(line)
            continue
        flush_table()
        if not line.strip():
            continue
        if line.startswith("# "):
            story.append(Paragraph(md_inline(line[2:]), st["h1"]))
        elif line.startswith("## "):
            story.append(Paragraph(md_inline(line[3:]), st["h2"]))
        elif line.startswith("### "):
            story.append(Paragraph(f"<b>{md_inline(line[4:])}</b>", st["body"]))
        elif line.startswith(">"):
            story.append(Paragraph(md_inline(line.lstrip("> ")), st["quote"]))
        elif re.match(r"^\s*[-*] ", line):
            story.append(Paragraph("• " + md_inline(re.sub(r"^\s*[-*] ", "", line)), st["body"]))
        else:
            story.append(Paragraph(md_inline(line), st["body"]))
    flush_table()
    return story


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def _fig(path, w=7.2, h=3.0):
    plt.rcParams.update({"font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False})
    return plt.figure(figsize=(w, h))


def charts(r: dict, tmp: Path) -> dict:
    out = {}
    # FCFF por escenario
    f = _fig(None)
    ax = f.add_subplot(1, 2, 1)
    for s in SCENARIO_ORDER:
        rows = [x for x in r["evals"][s]["rows"] if not x["terminal"]]
        ax.plot([x["año"] for x in rows], [x["fcff"] for x in rows], marker="o", label=s, color=SC_COLORS[s])
    ax.set_title("FCFF proyectado (miles de millones COP)")
    ax.legend(frameon=False, fontsize=7)
    ax2 = f.add_subplot(1, 2, 2)
    vals = [r["evals"][s]["valuation"]["valor_por_accion"] for s in SCENARIO_ORDER]
    ax2.bar(SCENARIO_ORDER, vals, color=[SC_COLORS[s] for s in SCENARIO_ORDER])
    ax2.axhline(r["decision"]["precio"], color="black", ls="--", lw=1)
    ax2.text(-0.4, r["decision"]["precio"] * 1.03, f"Precio {n0(r['decision']['precio'])}", fontsize=7)
    ax2.set_title("Valor por acción (COP)")
    f.tight_layout()
    out["escenarios"] = tmp / "escenarios.png"
    f.savefig(out["escenarios"], dpi=180)
    plt.close(f)

    # Tornado
    f = _fig(None, 7.2, 3.0)
    ax = f.add_subplot(1, 1, 1)
    t = list(reversed(r["tornado"]))
    base = t[0]["valor_base"]
    for i, x in enumerate(t):
        ax.barh(i, x["valor_alto"] - base, left=base, color="#2e7d4f")
        ax.barh(i, x["valor_bajo"] - base, left=base, color="#8c2d2d")
    ax.set_yticks(range(len(t)), [x["driver"] for x in t])
    ax.axvline(base, color="black", lw=0.8)
    ax.set_title(f"Tornado: valor por acción (Base = {n0(base)} COP)")
    f.tight_layout()
    out["tornado"] = tmp / "tornado.png"
    f.savefig(out["tornado"], dpi=180)
    plt.close(f)

    # Políticas + apalancamiento
    f = _fig(None, 7.2, 3.0)
    ax = f.add_subplot(1, 2, 1)
    pols = [p for p in POLICIES if POLICIES[p]["tipo"] != "financiera"]
    width = 0.38
    for j, p in enumerate(pols):
        d = [next(i for i in r["impacts"] if i["politica"] == p and i["escenario"] == s)["delta_vpn"] for s in SCENARIO_ORDER]
        ax.bar([k + (j - 0.5) * width for k in range(len(SCENARIO_ORDER))], d, width, label=p.split(" ", 1)[0] + " " + p.split(" ", 1)[1][:22])
    ax.set_xticks(range(len(SCENARIO_ORDER)), SCENARIO_ORDER)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("ΔVPN de las políticas (miles de millones)")
    ax.legend(frameon=False, fontsize=6.5)
    ax2 = f.add_subplot(1, 2, 2)
    for s in ("Estrés", "Pesimista", "Base"):
        for pol, ls in (("Sin política", "-"), ("P3 Dividendos condicionados al apalancamiento", ":")):
            rows = [x for x in r["leverage"] if x["escenario"] == s and x["politica"] == pol]
            ax2.plot([x["año"] for x in rows], [x["deuda_neta_ebitda"] for x in rows], ls=ls, color=SC_COLORS[s],
                     label=f"{s}{' + P3' if ls == ':' else ''}")
    ax2.axhline(DECISION_THRESHOLDS["covenant_deuda_neta_ebitda"], color="black", ls="--", lw=0.8)
    ax2.set_title("Deuda neta / EBITDA")
    ax2.legend(frameon=False, fontsize=6)
    f.tight_layout()
    out["politicas"] = tmp / "politicas.png"
    f.savefig(out["politicas"], dpi=180)
    plt.close(f)

    # Monte Carlo
    mc = r["monte_carlo"]
    f = _fig(None, 7.2, 2.6)
    ax = f.add_subplot(1, 2, 1)
    ax.hist([x["valor_por_accion"] for x in mc["simulaciones"]], bins=40, color="#1d4e89", alpha=0.85)
    ax.axvline(r["decision"]["precio"], color="black", ls="--", lw=1)
    ax.set_title("Monte Carlo: valor por acción (COP)")
    ax2 = f.add_subplot(1, 2, 2)
    ax2.hist([x["delta_vpn_p2"] for x in mc["simulaciones"]], bins=40, color="#2e7d4f", alpha=0.8, label="P2")
    ax2.hist([x["delta_vpn_p1"] for x in mc["simulaciones"]], bins=40, color="#d08a2e", alpha=0.8, label="P1")
    ax2.axvline(0, color="black", lw=0.8)
    ax2.set_title("Monte Carlo: ΔVPN por política")
    ax2.legend(frameon=False, fontsize=7)
    f.tight_layout()
    out["mc"] = tmp / "mc.png"
    f.savefig(out["mc"], dpi=180)
    plt.close(f)
    return out


def img(path, width=17.5 * cm):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(path)).getSize()
    return Image(str(path), width=width, height=width * ih / iw)


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------
def build(r: dict, equipo: list[str], fecha: str, curso: str, out_pdf: Path) -> Path:
    st = styles()
    isa, d, c, dec, mc = r["isa"], r["drivers"], r["capital"], r["decision"], r["monte_carlo"]
    ev = r["evals"]
    tmp = Path(tempfile.mkdtemp())
    ch = charts(r, tmp)
    S = []

    # Portada
    S += [Spacer(1, 3 * cm), Paragraph("Taller evaluativo 2026", st["center"]),
          Paragraph("Modelación financiera aplicada:<br/>pronóstico, escenarios y simulación de políticas", st["title"]),
          Spacer(1, 1.2 * cm), Paragraph(f"<b>Empresa:</b> {isa['empresa']} (BVC: {isa.get('ticker_bvc', 'ISA')})", st["center"]),
          Paragraph("<b>Camino elegido:</b> Evaluación empresarial", st["center"]),
          Paragraph(f"<b>Curso:</b> {curso}", st["center"]), Spacer(1, 0.8 * cm),
          Paragraph("<b>Equipo</b>", st["center"])]
    S += [Paragraph(m, st["center"]) for m in equipo]
    S += [Spacer(1, 0.8 * cm), Paragraph(f"<b>Fecha de entrega:</b> {fecha}", st["center"]),
          Paragraph(f"Datos con corte {isa.get('corte_catalogo')} · precio de referencia {isa['mercado'].get('fecha_precio_ref')}", st["center"]),
          Spacer(1, 2 * cm),
          Paragraph("Código reproducible: <font face='DVMono'>python scripts/taller_isa.py</font> · pruebas: "
                    "<font face='DVMono'>python -m pytest tests/test_taller_isa.py</font> · dashboard: "
                    "<font face='DVMono'>streamlit run scripts/dashboard_taller_isa.py</font>", st["small"]),
          Paragraph("Montos en miles de millones de COP salvo indicación. Ejercicio académico; no constituye recomendación de inversión profesional.", st["small"]),
          PageBreak()]

    # 1. Resumen ejecutivo
    recs = r["recommendations"]
    S += [Paragraph("1. Resumen ejecutivo", st["h1"]),
          Paragraph(
              f"Se proyectó el FCFF de ISA para 2026–2030 con un modelo de drivers calibrado con los estados financieros "
              f"2023–2025, un WACC por CAPM de {pct(c['wacc'])} y crecimiento terminal de {pct(isa['capital']['g_terminal'])}. "
              f"En el escenario Base el valor del patrimonio es {n0(ev['Base']['valuation']['patrimonio'])} "
              f"({n0(dec['valor_base'])} COP por acción) frente a un precio de {n0(dec['precio'])} COP; la TIR implícita al precio "
              f"de mercado es {pct(dec['tir_implicita'])}, inferior al WACC. <b>Decisión: {dec['decision'].lower()}</b>; el precio "
              f"máximo de compra que respeta el margen de seguridad es {n0(dec['precio_max_compra'])} COP.", st["body"]),
          table([["Política", "Decisión", "Fundamento"]] +
                [[p, rec["decision"], loc(rec["razon"])] for p, rec in recs.items()], st, [4.2 * cm, 3.3 * cm, 10 * cm]),
          Spacer(1, 4),
          Paragraph(
              f"El driver dominante es el WACC (±1 pp mueve el valor por acción entre {n0(r['tornado'][0]['valor_bajo'])} y "
              f"{n0(r['tornado'][0]['valor_alto'])} COP). En {n0(mc['n'])} simulaciones Monte Carlo la probabilidad de que el valor "
              f"supere el precio es {pct(mc['prob_valor_mayor_precio'])} (mediana {n0(mc['p50'])}; P5–P95: {n0(mc['p5'])}–{n0(mc['p95'])}).",
              st["body"])]

    # 2. Datos y drivers
    h = isa["history"]
    S += [Paragraph("2. Datos y drivers de la empresa", st["h1"]),
          Paragraph("ISA transmite energía a alta tensión en Colombia y Latinoamérica bajo esquemas regulados y concesiones; "
                    "sus ingresos dependen de la base de activos remunerada (nuevas convocatorias y expansión), de la indexación "
                    "tarifaria y del costo de capital. Por eso los drivers elegidos son crecimiento de ingresos, margen EBIT, "
                    "reinversión (CAPEX de mantenimiento y de expansión), capital de trabajo y WACC.", st["body"]),
          table([["Año", "Ingresos", "EBITDA", "EBIT", "D&A", "CAPEX", "NWC", "Margen EBIT", "CAPEX/ingresos"]] +
                [[x["Año"], n0(x["Ingresos"]), n0(x["EBITDA"]), n0(x["EBIT"]), n0(x["Depreciacion"]), n0(x["CAPEX"]),
                  n0(x["NWC"]), pct(x["EBIT"] / x["Ingresos"]), pct(x["CAPEX"] / x["Ingresos"])] for x in h], st),
          Paragraph(f"<b>Fuente y calidad:</b> {isa.get('verificacion')}", st["small"]),
          Spacer(1, 4),
          table([["Driver", "Valor base", "Cálculo / fuente", "Tipo"],
                 ["Crecimiento de ingresos", pct(d["growth"], 2), d["growth_formula"], "Observado (calculado)"],
                 ["Margen EBIT", pct(d["ebit_margin"], 2), f"EBIT/ingresos 2025 (promedio 2023–2025: {pct(d['ebit_margin_avg'])}); se usa 2025 por ser el perímetro conciliado", "Observado"],
                 ["CAPEX de mantenimiento / ingresos", pct(d["maint_capex_ratio"], 2), "≈ D&A/ingresos 2025 (reposición de la base de activos)", "Estimado"],
                 ["Intensidad CAPEX de expansión", f"{d['capex_intensity']:.2f}", "(CAPEX − D&A)/ΔIngresos, promedio 2024–2025; 2023 excluido por perímetro no comparable", "Estimado"],
                 ["NWC / ingresos", pct(d["nwc_ratio"], 2), "NWC/ingresos 2025 (NWC preliminar del balance)", "Estimado"],
                 ["Tasa de impuestos", pct(c["tax"]), "Tasa efectiva contable 2025 ≈ 22,13 %; provisional (estrés 35 % en tornado)", "Estimado"],
                 ["WACC", pct(c["wacc"], 2), "CAPM, ver sección 3", "Estimado"],
                 ["g terminal", pct(isa["capital"]["g_terminal"]), "Catálogo; < inflación LP de Colombia (conservador)", "Hipótesis"]],
                st, [4 * cm, 2.2 * cm, 8.8 * cm, 2.6 * cm])]

    # 3. Pronóstico base y método
    base_rows = [x for x in ev["Base"]["rows"]]
    vb = ev["Base"]["valuation"]
    S += [Paragraph("3. Pronóstico base y método", st["h1"]),
          Paragraph("<b>Método.</b> Modelo de drivers determinista: ingresos con crecimiento compuesto calibrado; costos vía margen "
                    "EBIT; reinversión separada en mantenimiento (proporcional a ingresos) y expansión (proporcional al aumento de "
                    "ingresos), lo que garantiza que más ventas exijan más inversión. Con solo tres observaciones anuales, una "
                    "regresión o un ARIMA darían falsa precisión; el modelo de drivers es auditable y la incertidumbre se trata con "
                    "escenarios, sensibilidad y Monte Carlo.", st["body"]),
          Paragraph("Ingresos<sub>t</sub> = Ingresos<sub>t−1</sub>(1+g) · EBIT = Ingresos × margen − costo de política · "
                    "NOPAT = EBIT(1−t) · CAPEX = Ingresos × m<sub>mant</sub> + k × ΔIngresos · ΔNWC = (NWC/Ingresos) × ΔIngresos · "
                    "<b>FCFF = NOPAT + D&amp;A − CAPEX − ΔNWC</b> · VT = FCFF<sub>2031</sub>/(WACC − g) · "
                    "EV = Σ FCFF<sub>t</sub>/(1+WACC)<sup>t</sup> + VT/(1+WACC)<sup>5</sup>", st["quote"]),
          table([["Año", "Ingresos", "Margen EBIT", "NOPAT", "D&A", "CAPEX", "ΔNWC", "FCFF"]] +
                [[("2031 (VT)" if x["terminal"] else x["año"]), n0(x["ingresos"]), pct(x["margen_ebit"]), n0(x["nopat"]),
                  n0(x["depreciacion"]), n0(x["capex"]), n0(x["delta_nwc"]), n0(x["fcff"])] for x in base_rows], st),
          Spacer(1, 4),
          Paragraph(f"<b>Costo de capital.</b> rf = TES 10 años {pct(isa['capital']['tes_10a'], 2)} − spread de default de Colombia "
                    f"{pct(isa['capital']['spread_default_co'], 2)} = {pct(c['rf'], 2)}; β apalancada = {isa['capital']['beta_u']:.2f} × "
                    f"[1 + (1 − {pct(c['tax'], 0)}) × D/E {isa['capital']['de_ratio']:.2f}] = {c['beta_l']:.2f}; ERP Colombia (Damodaran) "
                    f"{pct(isa['capital']['erp_total_co'], 2)} → Ke = {pct(c['ke'], 2)}; Kd = TES + {pct(isa['capital']['kd_spread'], 1)} = "
                    f"{pct(c['kd'], 2)} (después de impuestos {pct(c['kd_despues_imp'], 2)}); pesos E/V {pct(c['we'])}, D/V {pct(c['wd'])} "
                    f"→ <b>WACC {pct(c['wacc'], 2)}</b> nominal en COP.", st["body"]),
          table([["Métrica (escenario Base)", "Valor"],
                 ["VP FCFF 2026–2030", n0(vb["vp_fcff_explicito"])],
                 ["VP valor terminal (peso en EV)", f"{n0(vb['vp_valor_terminal'])} ({pct(vb['peso_valor_terminal'])})"],
                 ["Valor empresarial (EV)", n0(vb["ev"])],
                 ["− Deuda neta − minoritarios + asociadas", f"−{n0(isa['puente']['deuda_neta'])} − {n0(isa['puente']['nci'])} + {n0(isa['puente']['asociados'])}"],
                 ["Valor del patrimonio / por acción", f"{n0(vb['patrimonio'])} / {n0(vb['valor_por_accion'])} COP"],
                 ["Capitalización de mercado", n0(vb["capitalizacion_mercado"])],
                 ["<b>VPN del inversionista</b> (patrimonio − capitalización)", f"<b>{n0(vb['vpn_inversionista'])}</b>"],
                 ["<b>TIR implícita</b> (iguala EV del DCF al EV de mercado)", f"<b>{pct(ev['Base']['tir_implicita'], 2)}</b> vs WACC {pct(c['wacc'], 2)}"]],
                st, [9 * cm, 8.5 * cm]),
          Paragraph("Definiciones: el VPN se interpreta como la decisión de comprar el patrimonio al precio de mercado (inversión inicial = "
                    "capitalización). La TIR es la rentabilidad que obtendría quien compre hoy si se cumplen los flujos proyectados; "
                    "VPN &lt; 0 equivale a TIR &lt; WACC.", st["small"])]

    # 4. Escenarios
    sm = {x["escenario"]: x for x in r["summary"]}
    S += [Paragraph("4. Matriz de escenarios y resultados", st["h1"]),
          Paragraph("Los cuatro escenarios mueven seis drivers a la vez. La coherencia está incorporada en la estructura: "
                    "más crecimiento aumenta automáticamente el CAPEX de expansión y la inversión en capital de trabajo; los "
                    "escenarios de tasas altas combinan mayor WACC con menor g terminal. Todos los choques son hipótesis.", st["body"]),
          table([["Driver"] + SCENARIO_ORDER,
                 ["Crecimiento de ingresos"] + [pct(sm[s]["crecimiento"], 2) for s in SCENARIO_ORDER],
                 ["Margen EBIT"] + [pct(sm[s]["margen_ebit"], 2) for s in SCENARIO_ORDER],
                 ["Intensidad CAPEX de expansión"] + [f"{sm[s]['intensidad_capex']:.2f}" for s in SCENARIO_ORDER],
                 ["NWC / ingresos"] + [pct(sm[s]["nwc_ingresos"], 2) for s in SCENARIO_ORDER],
                 ["WACC"] + [pct(sm[s]["wacc"], 2) for s in SCENARIO_ORDER],
                 ["g terminal"] + [pct(sm[s]["g_terminal"], 2) for s in SCENARIO_ORDER],
                 ["Narrativa"] + [SCENARIOS[s]["descripcion"] for s in SCENARIO_ORDER]], st,
                [3.6 * cm] + [3.5 * cm] * 4),
          Spacer(1, 4),
          table([["Métrica"] + SCENARIO_ORDER,
                 ["FCFF acumulado 2026–2030"] + [n0(sm[s]["fcff_acumulado_2026_2030"]) for s in SCENARIO_ORDER],
                 ["EV"] + [n0(sm[s]["ev"]) for s in SCENARIO_ORDER],
                 ["Valor por acción (COP)"] + [n0(sm[s]["valor_por_accion"]) for s in SCENARIO_ORDER],
                 ["VPN del inversionista"] + [n0(sm[s]["vpn_inversionista"]) for s in SCENARIO_ORDER],
                 ["TIR implícita"] + [pct(sm[s]["tir_implicita"], 2) for s in SCENARIO_ORDER],
                 ["Máx. deuda neta/EBITDA"] + [f"{sm[s]['max_deuda_neta_ebitda']:.2f}x" for s in SCENARIO_ORDER]], st,
                [3.6 * cm] + [3.5 * cm] * 4),
          img(ch["escenarios"]),
          Paragraph("<b>Sensibilidad.</b> El tornado mueve un driver a la vez sobre el Base. El WACC explica la mayor dispersión, "
                    "seguido del crecimiento terminal y del crecimiento de ingresos; los drivers de reinversión (CAPEX, NWC) importan menos. "
                    "Implicación: la decisión depende más del costo de capital que del plan operativo, y el riesgo de tasas es el que "
                    "debe vigilarse.", st["body"]),
          img(ch["tornado"], 15.5 * cm)]
    mtx = r["matrix"]
    gs = [k for k in mtx["filas"][0] if k.startswith("g=")]
    S += [KeepTogether([Paragraph("Matriz 2D: valor por acción (COP) según WACC y g terminal", st["h2"]),
                        table([["WACC \\ g"] + gs] + [[pct(f["wacc"], 2)] + [n0(f[g]) for g in gs] for f in mtx["filas"]],
                              st, [3 * cm] + [3 * cm] * len(gs))])]

    # 5. Políticas
    S += [Paragraph("5. Simulación de políticas", st["h1"]),
          Paragraph("Cada política se implementa como una regla SI–ENTONCES en <font face='DVMono'>POLICIES</font> y se evalúa "
                    "como contrafactual frente al mismo escenario sin política: ΔVPN = EV<sub>con</sub> − EV<sub>sin</sub> (incluye valor "
                    "terminal). Para las políticas que alteran el FCFF se calcula la TIR de los flujos incrementales y se lee según su "
                    "forma (inversión: conviene si TIR &gt; WACC; financiación: conviene si costo &lt; WACC).", st["body"])]
    for p, cfg in POLICIES.items():
        rows = [i for i in r["impacts"] if i["politica"] == p]
        S += [Paragraph(p, st["h2"]), Paragraph(f"<b>Regla:</b> {cfg['regla']}", st["body"])]
        if cfg["tipo"] == "financiera":
            S += [table([["Escenario", "¿Se activa?", "ΔEV", "Años DN/EBITDA > 4,0x (sin → con)", "Deuda neta 2030 (sin → con)",
                          "Dividendos 2026–2030 (sin → con)"]] +
                        [[i["escenario"], "Sí" if i["regla_activa"] else "No", n0(i["delta_vpn"]),
                          f"{i['anios_sobre_covenant_sin']} → {i['anios_sobre_covenant_con']}",
                          f"{n0(i['deuda_final_sin'])} → {n0(i['deuda_final_con'])}",
                          f"{n0(i['dividendos_acumulados_sin'])} → {n0(i['dividendos_acumulados_con'])}"] for i in rows], st)]
        else:
            S += [table([["Escenario", "¿Se activa?", "ΔFCFF 2026–30", "ΔVPN", "Δ valor/acción", "Lectura de la TIR incremental"]] +
                        [[i["escenario"], "Sí" if i["regla_activa"] else "No", n0(i["delta_fcff_acumulado"]), n0(i["delta_vpn"]),
                          n0(i["delta_valor_por_accion"]), loc(i["lectura_tir"])] for i in rows], st,
                        [2 * cm, 1.6 * cm, 2.3 * cm, 1.9 * cm, 2.5 * cm, 7.2 * cm])]
        rec = recs[p]
        prob = f" P(ΔVPN &gt; 0) en Monte Carlo: {pct(rec['prob_mc_dvpn_pos'])}." if rec["prob_mc_dvpn_pos"] is not None else ""
        S += [Paragraph(f"<b>Recomendación: {rec['decision']}.</b> {loc(rec['razon'])}{prob}", st["body"])]
    S += [img(ch["politicas"]),
          Paragraph("<b>Lectura.</b> Diferir CAPEX de expansión libera caja en 2026–2027, pero en un negocio regulado los ingresos "
                    "nacen de la base de activos: el retraso reduce crecimiento y el valor terminal, y el costo implícito de esa "
                    "\"financiación\" supera al WACC. Por eso P1 se descarta aun cuando su regla se activa en el Pesimista: la regla "
                    "debe reformularse (por ejemplo, diferir solo proyectos con TIR propia &lt; WACC). La eficiencia operativa crea valor "
                    "en todos los escenarios porque su costo es pequeño frente a un margen permanente. La política de dividendos no "
                    "crea valor pero reduce el tiempo por encima del covenant en el escenario de Estrés.", st["body"])]

    # 6. Decisión
    th = DECISION_THRESHOLDS
    S += [Paragraph("6. Decisión e integración de resultados (camino: evaluación empresarial)", st["h1"]),
          table([["Umbral (parámetro del equipo)", "Valor", "Uso"],
                 ["Covenant deuda neta/EBITDA", f"{th['covenant_deuda_neta_ebitda']:.1f}x", "Disparador de P1/P3; criterio de viabilidad en escenarios adversos"],
                 ["Probabilidad mínima Monte Carlo", pct(th["prob_min_mc_politica"], 0), "Adoptar una política solo si P(ΔVPN &gt; 0) ≥ umbral"],
                 ["Margen de seguridad de compra", pct(th["margen_seguridad_compra"], 0), "Comprar si valor Base ≥ precio × 1,15 y valor Pesimista ≥ precio"],
                 ["Banda de mantener", f"±{pct(th['tolerancia_mantener'], 0)}", "Mantener si |valor/precio − 1| ≤ 15 %"],
                 ["Regla de política", "ΔVPN &gt; 0", "Adoptar si ΔVPN &gt; 0 en Base y Pesimista; condicionar si solo en uno; descartar si en ninguno"]],
                st, [5 * cm, 2.5 * cm, 10 * cm]),
          Spacer(1, 4),
          Paragraph(f"<b>Decisión sobre la acción: {dec['decision']}.</b> Valor Base {n0(dec['valor_base'])} COP y Pesimista "
                    f"{n0(dec['valor_pesimista'])} COP frente a {n0(dec['precio'])} COP (valor/precio = {dec['valor_sobre_precio']:.2f}). "
                    f"TIR implícita {pct(dec['tir_implicita'], 2)} &lt; WACC {pct(dec['wacc'], 2)}. Solo el escenario Optimista justifica "
                    f"el precio; dicho de otro modo, el mercado descuenta a ISA con una tasa ≈ {pct(dec['tir_implicita'], 1)}, es decir, "
                    f"exige un riesgo menor que el estimado por CAPM o espera crecimiento superior al Base.", st["body"]),
          Paragraph("<b>Recomendación condicionada.</b> (1) No comprar al precio actual; reconsiderar por debajo de "
                    f"{n0(dec['precio_max_compra'])} COP o si el WACC validado baja a ≈ {pct(dec['tir_implicita'], 1)}. (2) Adoptar P2 "
                    "(eficiencia) como política principal. (3) Descartar P1 en su forma actual y reemplazarla por una priorización de "
                    "proyectos con TIR propia &gt; WACC. (4) Mantener P3 como regla contingente que se activa automáticamente si la "
                    "deuda neta/EBITDA supera 4,0x.", st["body"]),
          Paragraph("Árbol de decisión simplificado: ¿TIR implícita &gt; WACC? → No → ¿valor Optimista &gt; precio? → Sí → "
                    "mantener en observación y revisar cuando cambie el WACC (tasas TES) o se adjudiquen nuevas convocatorias; No → vender/no comprar.",
                    st["quote"])]

    # 7. Monte Carlo
    S += [Paragraph("7. Monte Carlo (bonificación)", st["h1"]),
          Paragraph(f"{n0(mc['n'])} simulaciones (semilla {mc['semilla']}) sobre el escenario Base: crecimiento ~ N(base; 1,5 pp), "
                    "margen EBIT ~ N(base; 1,5 pp), intensidad CAPEX × triangular(0,85; 1,00; 1,35), NWC × triangular(0,85; 1,00; 1,20), "
                    "ajuste de WACC ~ N(0; 0,75 pp), g ~ U(3,5 %; 6,0 %) con WACC − g ≥ 2 pp, y logro de la eficiencia ~ U(0 %; 150 %) "
                    "de la meta. Las distribuciones son hipótesis del equipo.", st["body"]),
          table([["Resultado", "Valor"],
                 ["Valor por acción: P5 / mediana / P95", f"{n0(mc['p5'])} / {n0(mc['p50'])} / {n0(mc['p95'])} COP"],
                 ["P(valor &gt; precio)", pct(mc["prob_valor_mayor_precio"])],
                 ["P(ΔVPN &gt; 0) P1 / P2", f"{pct(mc['prob_dvpn_p1_pos'])} / {pct(mc['prob_dvpn_p2_pos'])}"],
                 ["P(deuda neta/EBITDA &gt; 4,0x en algún año)", pct(mc["prob_covenant_roto"])]], st, [9 * cm, 8.5 * cm]),
          img(ch["mc"]),
          Paragraph("El dashboard <font face='DVMono'>scripts/dashboard_taller_isa.py</font> permite mover los seis drivers, la tasa "
                    "de impuestos y la política, y ver al instante FCFF, puente de valor, apalancamiento y Monte Carlo.", st["body"])]

    # 8. Ingeniería de prompts y técnicas
    S += [Paragraph("8. Ingeniería de prompts y técnicas aplicadas", st["h1"]),
          table([["Técnica", "Dónde", "Qué demuestra"],
                 ["T1 Pronóstico por drivers", "historical_drivers, project", "Crecimiento compuesto calibrado; CAPEX enlazado a ΔIngresos"],
                 ["T2 Parametrización de escenarios", "SCENARIOS", "6 drivers × 4 escenarios en un diccionario editable"],
                 ["T3 Sensibilidad", "tornado, wacc_g_matrix", "Tornado de 7 drivers y matriz WACC × g"],
                 ["T4 Simulación de políticas", "POLICIES, policy_impact", "Reglas SI–ENTONCES, contrafactual, ΔVPN y TIR incremental"],
                 ["T5 Monte Carlo", "monte_carlo", "Distribución de valor y probabilidad de éxito de políticas"],
                 ["T6 Ingeniería de prompts", "Anexo A", "Plantilla maestra v2 parametrizable, versionado y 4 interacciones"]],
                st, [4.5 * cm, 4.5 * cm, 8.5 * cm]),
          Paragraph("El prompt maestro define rol, datos con su calidad, módulo de tarea, siete restricciones (no inventar, etiquetar "
                    "observado/estimado/hipótesis, coherencia entre drivers, umbrales explícitos, distinguir VPN/ΔVPN/EV) y un "
                    "formato de salida tabular. Las interacciones del Anexo A muestran cómo la IA detectó cifras desactualizadas y "
                    "vacíos frente a la rúbrica, y cómo cada salida se tradujo en código y en pruebas automatizadas.", st["body"])]

    # 9. Limitaciones
    S += [Paragraph("9. Limitaciones y reproducibilidad", st["h1"])]
    S += [Paragraph("• " + a, st["body"]) for a in r["metadata"]["advertencias"]]
    S += [Paragraph("Reproducción: <font face='DVMono'>python scripts/taller_isa.py</font> genera los CSV y el JSON en "
                    "<font face='DVMono'>salidas_taller_isa/</font>; <font face='DVMono'>python scripts/generar_informe_taller_isa.py</font> "
                    "regenera este informe con las mismas cifras.", st["body"]), PageBreak()]

    # Anexos
    S += [Paragraph("Anexo A. Prompt maestro y registro de interacciones", st["h1"])]
    md = PROMPTS_MD.read_text(encoding="utf-8")
    md = re.sub(r"^# .*\n", "", md, count=1)
    S += markdown_to_story(md, st)
    S += [PageBreak(), Paragraph("Anexo B. Fuentes de datos y archivos de salida", st["h1"])]
    for k, v in r["metadata"]["fuentes"].items():
        if v:
            S.append(Paragraph(f"<b>{k}:</b> {md_inline(str(v))}", st["small"]))
    S += [Spacer(1, 6), table([["Archivo", "Contenido"],
                               ["detalle_escenarios_politicas.csv", "Proyección anual por escenario y política (incluye año terminal)"],
                               ["resumen_escenarios.csv", "Drivers, EV, valor por acción, VPN, TIR y apalancamiento por escenario"],
                               ["impacto_politicas.csv", "Regla activa, ΔFCFF, ΔVPN, TIR incremental y covenant por política"],
                               ["apalancamiento.csv", "Trayectoria de deuda neta, dividendos y DN/EBITDA"],
                               ["tornado.csv · matriz_wacc_g.csv", "Sensibilidades"],
                               ["monte_carlo.csv", "Cada simulación con sus drivers y resultados"],
                               ["metadatos_modelo.json", "Supuestos, umbrales, recomendaciones, fuentes y advertencias"]], st,
                              [6 * cm, 11.5 * cm])]

    def footer(canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setFont("DV", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, "Taller evaluativo 2026 · ISA · Evaluación empresarial")
        canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_pdf), pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title="Taller evaluativo 2026 — ISA", author="; ".join(equipo))
    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    return out_pdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--equipo", default="Luisa Fernanda Cardona Vega; Gustavo Adolfo Castro Grijalba; Cristian Gabriel Vargas Gaviria",
                    help="Integrantes separados por ';'")
    ap.add_argument("--fecha", default="5 de noviembre de 2026")
    ap.add_argument("--curso", default="Modelación financiera aplicada — Prof. Julio César Riascos")
    ap.add_argument("--mc", type=int, default=5000)
    ap.add_argument("--out", type=Path, default=OUT_PDF)
    a = ap.parse_args()
    r = run_model(mc_n=a.mc)
    path = build(r, [m.strip() for m in a.equipo.split(";") if m.strip()], a.fecha, a.curso, a.out)
    print(f"Informe generado: {path}")


if __name__ == "__main__":
    main()
