import sys, os, re
from playwright.sync_api import sync_playwright
URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True); log = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 2600})
    pg.goto(URL, wait_until="networkidle", timeout=120000); pg.wait_for_timeout(8000)
    for txt in ("Saltar tour", "Listo, empezar"):
        try:
            pg.get_by_role("button", name=txt).first.click(timeout=3000); pg.wait_for_timeout(2000)
        except Exception:
            pass
    pg.get_by_role("button", name=re.compile("Generar todo")).first.click(timeout=10000); pg.wait_for_timeout(90000)
    # narrativa
    try:
        pg.get_by_role("button", name="Narrativa (palancas de la historia)").first.click(timeout=10000); pg.wait_for_timeout(8000)
        d = pg.locator('[role="dialog"]').first
        log.append("DIALOGO: " + d.inner_text()[:1500].replace("\n", " | "))
        d.screenshot(path=f"{OUT}/narrativa.png")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(2000)
    except Exception as e:
        log.append(f"narrativa error {e}")
    # portafolio
    pg.get_by_role("tab").nth(7).click(); pg.wait_for_timeout(5000)
    f = pg.get_by_label("Otros tickers del universo, separados por coma").first
    f.fill("ECOPETROL.CL,GEB.CL,AAPL"); f.press("Enter"); pg.wait_for_timeout(4000)
    pg.get_by_role("button", name="Optimizar portafolio").first.click(timeout=10000); pg.wait_for_timeout(100000)
    t = pg.locator('[role="tabpanel"]:visible').first.inner_text()
    open(f"{OUT}/tab8.txt", "w").write(t)
    pg.locator('[role="tabpanel"]:visible').first.screenshot(path=f"{OUT}/tab8.png")
    log.append(f"excepciones: {[x[:300] for x in pg.locator('[data-testid=stException]').all_inner_texts()]}")
    # parametros: ingresos por pais
    try:
        pg.get_by_text("Parámetros del modelo").first.click(timeout=10000); pg.wait_for_timeout(2000)
        f = pg.get_by_role("textbox", name="Ingresos por país (opcional)").first
        f.fill("Brasil 40, Colombia 30, Chile 15, Perú 15"); f.press("Enter"); pg.wait_for_timeout(6000)
        sb = pg.locator('[data-testid="stSidebar"]').inner_text()
        i = sb.find("Prima ponderada"); log.append("OPS: " + sb[i:i + 200].replace("\n", " "))
        log.append("ERP caja: " + pg.get_by_role("spinbutton", name="ERP (valor exacto)").first.input_value())
    except Exception as e:
        log.append(f"ops error {e}")
    b.close()
open(f"{OUT}/log.txt", "w").write("\n".join(log)); print("\n".join(log))
