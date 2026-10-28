"""Capturas reales de la app (escritorio y móvil) tras «Generar todo». Uso: python diag/capturas_ui.py URL CARPETA"""
import sys, os, time
from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
TABS = ["1 · Pronóstico", "2 · Escenarios DCF", "3 · Auditoría", "4 · Recomendación", "5 · VPN / TIR",
        "6 · Sector", "7 · Informe PDF", "8 · Portafolios", "9 · Simular inversión"]
log = []


def correr(nombre, ancho, alto, tabs):
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": ancho, "height": alto})
        errores = []
        pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pg.goto(URL, wait_until="networkidle", timeout=120000)
        pg.wait_for_timeout(6000)
        for txt in ("Saltar tour", "Listo, empezar"):
            try:
                pg.get_by_role("button", name=txt).first.click(timeout=3000)
                pg.wait_for_timeout(2500)
            except Exception:
                pass
        pg.screenshot(path=f"{OUT}/{nombre}_00_inicio.png")
        if ancho < 700:  # en móvil el menú lateral tapa la app: cerrarlo como haría el usuario
            for sel in ['[data-testid="stSidebarCollapseButton"] button', 'button[kind="headerNoPadding"]', '[data-testid="stSidebarCollapseButton"]']:
                try:
                    pg.locator(sel).first.click(timeout=3000)
                    pg.wait_for_timeout(1500)
                    break
                except Exception:
                    pass
            pg.screenshot(path=f"{OUT}/{nombre}_00b_sin_menu.png")
        t0 = time.time()
        pg.get_by_role("button", name="▶ Generar todo").first.click(timeout=20000)
        estado = "timeout"
        for _ in range(120):
            pg.wait_for_timeout(3000)
            body = pg.inner_text("body")
            if "Pipeline completo" in body or "Algunas pestañas fallaron" in body:
                estado = "completo" if "Pipeline completo" in body else "con fallos"
                break
            if "Running..." not in body and time.time() - t0 > 60 and "Listo" in body:
                estado = "listo"
                break
        pg.wait_for_timeout(5000)
        log.append(f"{nombre}: Generar todo → {estado} en {time.time() - t0:.0f}s")
        cuerpo = pg.inner_text("body")
        if "fallaron" in cuerpo:
            i = cuerpo.find("Algunas pestañas fallaron")
            log.append(cuerpo[i:i + 800])
        for i, t in enumerate(TABS, 1):
            if i not in tabs:
                continue
            try:
                pg.get_by_role("tab", name=t).first.click(timeout=10000)
                pg.wait_for_timeout(4000)
                pg.screenshot(path=f"{OUT}/{nombre}_{i:02d}.png")
                exc = pg.locator('[data-testid="stException"]').all_inner_texts()
                if exc:
                    log.append(f"{nombre} pestaña {t} EXCEPCIÓN: {exc[0][:400]}")
                panel = pg.locator('[role="tabpanel"]:visible').first.inner_text()
                open(f"{OUT}/{nombre}_{i:02d}.txt", "w").write(panel)
            except Exception as e:
                log.append(f"{nombre} pestaña {t}: {e}"[:300])
        log.append(f"{nombre} errores de consola: {errores[:10]}")
        b.close()


import sys as _s
modo = _s.argv[3] if len(_s.argv) > 3 else "ambos"
try:
    if modo in ("ambos", "escritorio"):
        correr("escritorio", 1440, 3600, {1, 2, 3, 4, 5, 6, 7, 8, 9})
    if modo in ("ambos", "movil"):
        correr("movil", 390, 4200, {1, 2, 4, 6})
except Exception as e:
    log.append(f"ERROR: {e}")
open(f"{OUT}/log.txt", "w", encoding="utf-8").write("\n".join(log))
print("\n".join(log))
