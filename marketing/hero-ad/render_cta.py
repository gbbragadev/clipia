from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    page = b.new_page(viewport={"width": 1080, "height": 1920})
    page.goto((HERE / "cta.html").as_uri())
    page.wait_for_timeout(900)
    page.screenshot(path=str(HERE / "renders" / "cta.png"))
    b.close()
print("cta.png ok")
