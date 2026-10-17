import time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=1.5)
    msgs=[]; pg.on("console", lambda m: msgs.append(m.text)); pg.on("pageerror", lambda e: msgs.append("ERR "+str(e)))
    pg.goto("https://ai-agentic-enterprises.com/6g-isac/?view=all")
    pg.wait_for_function("typeof RD!=='undefined' && RD && F", timeout=60000)
    t0=time.time()
    for T in (3, 14, 26.6):
        pg.evaluate(f"T={T}; drawAll()")
        pg.locator(".card.c-rd").screenshot(path=f"cap/rd_{T}.png")
    print("3 shots in", round(time.time()-t0,2), "s", msgs[:3])
    pg.screenshot(path="cap/full.png", full_page=True)
    b.close()
