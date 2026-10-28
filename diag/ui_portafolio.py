import sys, os, re
from playwright.sync_api import sync_playwright
URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True); log = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 2600})
    errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="networkidle", timeout=120000); pg.wait_for_timeout(8000)
    for txt in ("Saltar tour", "Listo, empezar"):
        try:
            pg.get_by_role("button", name=txt).first.click(timeout=3000); pg.wait_for_timeout(2000)
        except Exception:
            pass
    pg.get_by_role("tab").nth(7).click(); pg.wait_for_timeout(5000)
    pg.get_by_role("button", name="Optimizar portafolio").first.click(timeout=10000); pg.wait_for_timeout(90000)
    t = pg.locator('[role="tabpanel"]:visible').first.inner_text()
    open(f"{OUT}/tab8.txt", "w").write(t)
    for ln in t.split("\n"):
        if re.search(r"Caída|VaR|CVaR|compuesto|Ledoit|Sharpe|Retorno|Volatilidad|No se pudo", ln):
            log.append(ln[:200])
    pg.screenshot(path=f"{OUT}/tab8.png", full_page=True)
    log.append(f"excepciones: {pg.locator('[data-testid=stException]').all_inner_texts()[:2]}")
    b.close()
open(f"{OUT}/log.txt", "w").write("\n".join(log)); print("\n".join(log))
