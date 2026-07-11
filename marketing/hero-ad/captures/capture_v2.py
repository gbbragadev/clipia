"""Captura v2: editor em desktop (player Remotion tocando) + dashboard Em alta.

NAO clica em Resetar/Gerar/Confirmar (mutam estado / custam credito).
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3003"
TOKEN = sys.argv[1]
JOB_ID = "8f4686a3-07ed-4c32-a4a0-dc9ec29e60fb"
OUT = Path(__file__).parent


def record(pw, name, viewport, actions):
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport=viewport,
        record_video_dir=str(OUT / "raw"),
        record_video_size=viewport,
        locale="pt-BR",
        color_scheme="dark",
    )
    ctx.add_init_script(f"localStorage.setItem('clipia_token', '{TOKEN}')")
    page = ctx.new_page()
    try:
        actions(page)
    except Exception as e:
        print(f"  ! {name}: {e}")
        page.screenshot(path=str(OUT / f"err-{name}.png"))
    video = page.video
    ctx.close()
    src = Path(video.path())
    dst = OUT / f"{name}.webm"
    if dst.exists():
        dst.unlink()
    src.rename(dst)
    browser.close()
    print(f"  OK {name}.webm")


def editor_desktop(page):
    page.goto(f"{BASE}/editor/{JOB_ID}", wait_until="networkidle", timeout=60000)
    time.sleep(7)  # player Remotion via dynamic import
    page.screenshot(path=str(OUT / "qa2-editor-desktop.png"))
    # play: botao do Remotion Player usa aria-label; fallback: clique no centro do player
    played = False
    for sel in ["[aria-label='Play']", "[aria-label='play']", "[aria-label*='Play' i]"]:
        try:
            el = page.locator(sel).first
            if el.count():
                el.click(timeout=2500)
                played = True
                break
        except Exception:
            continue
    if not played:
        # clica no centro-esquerda da area do player (evita header/direita onde ha botoes de acao)
        page.mouse.click(360, 450)
    time.sleep(1.5)
    page.screenshot(path=str(OUT / "qa2-editor-play1.png"))
    time.sleep(6)
    page.screenshot(path=str(OUT / "qa2-editor-play2.png"))
    time.sleep(5)
    page.screenshot(path=str(OUT / "qa2-editor-play3.png"))


def trends(page):
    page.goto(f"{BASE}/dashboard", wait_until="networkidle", timeout=45000)
    time.sleep(3)
    page.screenshot(path=str(OUT / "qa2-trends-top.png"))
    # clica num chip de categoria (nao gera nada)
    try:
        chip = page.get_by_text("Curiosidades", exact=False).first
        if chip.count():
            chip.click(timeout=2500)
    except Exception:
        pass
    time.sleep(2)
    # scroll suave pelos cards de tendencia
    for y in (250, 480, 700, 950):
        page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'smooth'}})")
        time.sleep(1.1)
    page.screenshot(path=str(OUT / "qa2-trends-scrolled.png"))
    time.sleep(1)


with sync_playwright() as pw:
    (OUT / "raw").mkdir(exist_ok=True)
    record(pw, "cap-editor-desktop", {"width": 1440, "height": 900}, editor_desktop)
    record(pw, "cap-trends", {"width": 720, "height": 1560}, trends)
print("v2 concluida")
