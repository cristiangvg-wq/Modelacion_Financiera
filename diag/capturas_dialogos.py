import sys, os
from playwright.sync_api import sync_playwright
URL, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
log = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1300})
    pg.goto(URL, wait_until="networkidle", timeout=120000)
    pg.wait_for_timeout(8000)
    for txt in ("Saltar tour", "Listo, empezar"):
        try:
            pg.get_by_role("button", name=txt).first.click(timeout=3000); pg.wait_for_timeout(2000)
        except Exception:
            pass
    try:
        pg.get_by_role("button", name="Corregir histórico (cifras oficiales)").first.click(timeout=15000)
        pg.wait_for_timeout(5000)
        pg.screenshot(path=f"{OUT}/dialogo_historico.png")
        # editar el CAPEX 2025 a 6300 y aplicar
        log.append("dialogo historico abierto")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(2000)
    except Exception as e:
        log.append(f"historico: {e}"[:300])
    try:
        pg.get_by_text("Parámetros del modelo").first.click(timeout=10000); pg.wait_for_timeout(2500)
        pg.get_by_role("button", name="Valorar participadas por separado").first.scroll_into_view_if_needed()
        pg.get_by_role("button", name="Valorar participadas por separado").first.click(timeout=15000)
        pg.wait_for_timeout(6000)
        pg.screenshot(path=f"{OUT}/dialogo_suma_partes.png")
        log.append("dialogo suma de partes abierto")
        pg.get_by_role("button", name="Usar en el puente a equity").first.click(timeout=10000)
        pg.wait_for_timeout(6000)
        pg.screenshot(path=f"{OUT}/tras_suma_partes.png", full_page=False)
        try:
            exp = pg.get_by_text("Parámetros del modelo").first
            if "Asociados por suma de partes" not in pg.inner_text("body"):
                exp.click(timeout=5000); pg.wait_for_timeout(2500)
        except Exception:
            pass
        loc = pg.get_by_text("Asociados por suma de partes").first
        try:
            loc.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        pg.screenshot(path=f"{OUT}/tras_suma_partes.png", full_page=False)
        body = pg.inner_text("body")
        i = body.find("Asociados por suma de partes")
        log.append(body[i:i + 200] if i >= 0 else "sin caption de suma de partes")
    except Exception as e:
        log.append(f"suma partes: {e}"[:300])
    b.close()
open(f"{OUT}/log.txt", "w").write("\n".join(log)); print("\n".join(log))
