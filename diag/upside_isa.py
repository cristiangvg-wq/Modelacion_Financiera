import sys, os, re
from playwright.sync_api import sync_playwright
URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
log = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 2400})
    pg.goto(URL, wait_until="networkidle", timeout=120000)
    pg.wait_for_timeout(8000)
    for txt in ("Saltar tour", "Listo, empezar"):
        try:
            pg.get_by_role("button", name=txt).first.click(timeout=3000); pg.wait_for_timeout(2000)
        except Exception:
            pass
    sb = pg.locator('[data-testid="stSidebar"]')
    try:
        sel = sb.locator('[data-testid="stSelectbox"]').first
        log.append("emisor inicial: " + sel.inner_text()[:80].replace("\n", " "))
        sel.click(); pg.keyboard.type("ISA"); pg.wait_for_timeout(1500); pg.keyboard.press("Enter")
        pg.wait_for_timeout(20000)
        log.append("emisor: " + sel.inner_text()[:80].replace("\n", " "))
    except Exception as e:
        log.append(f"no seleccionó: {e}")
    try:
        pg.get_by_role("button", name=re.compile("Generar todo")).first.click(timeout=10000)
        pg.wait_for_timeout(90000)
        log.append("generar todo ok")
    except Exception as e:
        log.append(f"generar todo error {e}")
    body = pg.inner_text("body")
    open(f"{OUT}/inicio.txt", "w").write(body)
    for i in range(1, 10):
        try:
            pg.get_by_role("tab").nth(i - 1).click(timeout=5000)
            pg.wait_for_timeout(15000)
            panel = pg.locator('[role="tabpanel"]:visible').first
            t = panel.inner_text()
            open(f"{OUT}/tab{i}.txt", "w").write(t)
            for ln in t.split("\n"):
                if re.search(r"[+\-−]\s?\d+[.,]\d\s?%", ln) or re.search(r"(?i)upside|vs precio|diferencia|valor por acci|VPS|precio", ln):
                    log.append(f"[tab{i}] {ln[:160]}")
            pg.screenshot(path=f"{OUT}/tab{i}.png", full_page=False)
        except Exception as e:
            log.append(f"tab{i} error {e}")
    sb.screenshot(path=f"{OUT}/sidebar.png")
    b.close()
open(f"{OUT}/log.txt", "w").write("\n".join(log)); print("\n".join(log[:300]))
