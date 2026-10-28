import sys, os
from playwright.sync_api import sync_playwright
URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
log = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 2200})
    errores = []
    pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="networkidle", timeout=120000)
    pg.wait_for_timeout(8000)
    for txt in ("Saltar tour", "Listo, empezar"):
        try:
            pg.get_by_role("button", name=txt).first.click(timeout=3000); pg.wait_for_timeout(2000)
        except Exception:
            pass
    pg.get_by_text("Parámetros del modelo").first.click(timeout=10000)
    log.append('aria: ' + str(pg.locator('[data-testid="stSidebar"] input').evaluate_all('els => els.map(e => e.getAttribute("aria-label")).slice(0,12)')))
    pg.wait_for_timeout(3000)
    sb = pg.locator('[data-testid="stSidebar"]')
    sb.screenshot(path=f"{OUT}/sidebar_antes.png")
    caja = pg.locator('input[aria-label*="Kd"]').last
    log.append("inputs: " + str(pg.locator('[data-testid="stSidebar"] input[type="number"]').count()))
    log.append("Kd caja antes: " + caja.input_value())
    caja.fill("0.1525"); caja.press("Enter"); pg.wait_for_timeout(5000)
    caja = pg.locator('input[aria-label*="Kd"]').last
    log.append("Kd caja después: " + caja.input_value())
    sl = pg.locator('[data-testid="stSidebar"] [data-testid="stSlider"]').nth(2).inner_text()
    log.append("barra Kd: " + sl.replace("\n", " "))
    body = pg.inner_text("body")
    i = body.find("WACC")
    log.append("cabecera: " + body[i:i + 60].replace("\n", " "))
    sb.screenshot(path=f"{OUT}/sidebar_despues.png")
    exc = [t for t in pg.locator('[data-testid="stException"]').all_inner_texts()]
    log.append(f"excepciones: {exc[:3]}")
    log.append(f"consola: {[e for e in errores if 'translate' not in e][:5]}")
    b.close()
open(f"{OUT}/log.txt", "w").write("\n".join(log)); print("\n".join(log))
