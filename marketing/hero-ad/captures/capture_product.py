"""Grava o produto real (dashboard Em alta + editor com legendas word-level).

Viewport 720x1560 (layout mobile, 9:16-ish) gravado em resolucao nativa.
Screenshots de QA em cada etapa para revisao visual.
"""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3003"
TOKEN = sys.argv[1]
JOB_ID = "8f4686a3-07ed-4c32-a4a0-dc9ec29e60fb"
OUT = Path(__file__).parent
VIEW = {"width": 720, "height": 1560}


def smooth_scroll(page, to_y, steps=30, dt=0.03):
    cur = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)  # smoothstep easing
        page.evaluate(
            f"window.scrollTo(0, {cur + (to_y - cur)})"
            if i == steps
            else f"window.scrollTo(0, {cur + (to_y - cur) * e})"
        )
        time.sleep(dt)


def record(pw, name, actions):
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport=VIEW,
        record_video_dir=str(OUT / "raw"),
        record_video_size=VIEW,
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


def dashboard(page):
    page.goto(f"{BASE}/dashboard", wait_until="networkidle", timeout=45000)
    time.sleep(2.5)
    page.screenshot(path=str(OUT / "qa-dash-top.png"))
    # digita um tema no campo de topico, devagar (visivel no video)
    for sel in ["textarea", "input[placeholder*='tema' i]", "input[type='text']"]:
        el = page.locator(sel).first
        if el.count() and el.is_visible():
            el.click()
            time.sleep(0.4)
            el.type("5 sinais de que a IA vai mudar seu trabalho", delay=55)
            break
    time.sleep(1.0)
    page.screenshot(path=str(OUT / "qa-dash-typed.png"))
    # procura o painel Em alta e rola ate ele
    trend = page.get_by_text("Em alta", exact=False).first
    if trend.count():
        trend.scroll_into_view_if_needed()
        time.sleep(1.8)
    page.screenshot(path=str(OUT / "qa-dash-trends.png"))
    smooth_scroll(page, 900, steps=40)
    time.sleep(1.5)
    page.screenshot(path=str(OUT / "qa-dash-bottom.png"))


def editor(page):
    page.goto(f"{BASE}/editor/{JOB_ID}", wait_until="networkidle", timeout=60000)
    time.sleep(6)  # player Remotion carrega via dynamic import
    page.screenshot(path=str(OUT / "qa-editor-loaded.png"))
    # tenta dar play no player (botao central ou controle)
    for sel in ["[aria-label*='play' i]", "button:has(svg)", "video"]:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible():
                el.click(timeout=3000)
                break
        except Exception:
            continue
    time.sleep(1)
    page.screenshot(path=str(OUT / "qa-editor-playing.png"))
    time.sleep(9)  # deixa as legendas word-level animarem
    page.screenshot(path=str(OUT / "qa-editor-late.png"))


def landing(page):
    page.goto(BASE, wait_until="networkidle", timeout=45000)
    time.sleep(2.5)
    page.screenshot(path=str(OUT / "qa-landing-top.png"))
    smooth_scroll(page, 1400, steps=60, dt=0.04)
    time.sleep(1.2)
    smooth_scroll(page, 3200, steps=60, dt=0.04)
    time.sleep(1.5)
    page.screenshot(path=str(OUT / "qa-landing-mid.png"))


with sync_playwright() as pw:
    (OUT / "raw").mkdir(exist_ok=True)
    record(pw, "cap-dashboard", dashboard)
    record(pw, "cap-editor", editor)
    record(pw, "cap-landing", landing)
print("capturas concluidas")
