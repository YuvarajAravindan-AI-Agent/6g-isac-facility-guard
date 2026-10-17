"""Dashboard cutaways: drive the live dashboard in headless Chrome, composite panels + KPI callouts into 1920x804 content frames
saved at 12 fps under seg/<id>/. Usage: python dash.py <seg-id> [<seg-id> ...]"""
import io
import json
import os
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from common import *

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://ai-agentic-enterprises.com/6g-isac/"
CAP_FPS = 10
CH = 804
DUR = json.load(open(os.path.join(HERE, "durations.json")))
from script import BYID

KIND = {sid: BYID[sid]["visual"][1] for sid in BYID if BYID[sid]["visual"][0] == "dash"}


def bg():
    return dusk_bg().crop((0, BAR, W, BAR + CH)).convert("RGBA")


def kpi(d, x, y, big, small, color, a=1.0, w=520):
    al = int(255 * a)
    d.rounded_rectangle((x, y, x + w, y + 150), 22, fill=(18, 10, 50, int(225 * a)), outline=color + (al,), width=5)
    d.text((x + w / 2, y + 62), big, font=F(76), fill=color + (al,), anchor="mm")
    d.text((x + w / 2, y + 120), small, font=F(34, False), fill=(245, 242, 255, al), anchor="mm")


def title(d, s, color=CY):
    d.text((80, 24), s, font=F(60), fill=color + (255,))
    d.rectangle((82, 92, 300, 97), fill=AM + (255,))


def place(img, shot, x, y, h=None, w=None):
    if h:
        w = int(shot.width * h / shot.height)
    else:
        h = int(shot.height * w / shot.width)
    s = shot.resize((w, h), Image.BILINEAR)
    img.alpha_composite(s.convert("RGBA"), (x, y))
    return w, h


def reveal(u, t0):
    return ease((u - t0) / 0.06)


def shot_png(loc_or_page, **kw):
    return Image.open(io.BytesIO(loc_or_page.screenshot(**kw))).convert("RGB")


def run(sid, br):
    kind, dur = KIND[sid], DUR[sid]["dur"] + 0.5
    n = int(dur * CAP_FPS)
    out = os.path.join(HERE, "seg", sid)
    os.makedirs(out, exist_ok=True)
    mk = lambda vw, vh, view, dpr: (lambda pg: (pg.goto(URL + f"?view={view}"), pg.wait_for_function("typeof RD!=='undefined' && RD && F", timeout=90000), pg)[2])(br.new_page(viewport={"width": vw, "height": vh}, device_scale_factor=dpr))
    if kind == "rd":
        pg = mk(1200, 1000, "rd", 1.5)
        pg.evaluate("document.querySelector('header').style.display='none'; document.querySelectorAll('.legend,#mnote').forEach(e=>e.style.display='none')")
    elif kind in ("metrics", "rcs", "trk"):
        pg = mk(1200, 900, "metrics", 1.5)
        pg.evaluate("document.querySelector('header').style.display='none'; document.querySelectorAll('.legend,#mnote').forEach(e=>e.style.display='none')")
    elif kind in ("agent", "agent2"):
        pg = mk(1200, 1000, "agent", 1.5)
        pg.evaluate("document.querySelector('#agent').style.maxHeight='620px'")
    elif kind == "audit":
        pg = mk(1200, 900, "audit", 1.5)
    for i in range(n):
        u = i / max(1, n - 1)
        img = bg()
        d = ImageDraw.Draw(img)
        if kind == "rd":
            T = 28.5 * u
            pg.evaluate(f"T={T}; drawAll()")
            shot = shot_png(pg.locator(".card.c-rd"))
            vals = pg.evaluate("[...document.querySelectorAll('#trk > *')].map(e=>e.innerText)")
            title(d, "LIVE SENSING: RANGE–DOPPLER, DETECTION, TRACK")
            place(img, shot, 70, 118, w=1070)
            d.rounded_rectangle((1160, 112, 1850, 470), 22, fill=(18, 10, 50, 232), outline=CY + (255,), width=5)
            d.text((1190, 138), "TRACK", font=F(40), fill=CY + (255,))
            for k in range(0, min(len(vals), 16), 2):
                yy = 190 + (k // 2) * 33
                d.text((1190, yy), vals[k], font=F(27, False), fill=(200, 190, 255, 255))
                d.text((1830, yy), vals[k + 1], font=F(30), fill=(255, 255, 255, 255), anchor="ra")
            for k, (big, small, c_, t0) in enumerate([("321 m", "track confirmed", LM, 0.08), ("27 s", "warning before fence", CY, 0.30), ("0.64 m", "position error RMS", AM, 0.55), ("0.81 m/s", "speed error RMS", MG, 0.75)]):
                a = reveal(u, t0)
                if a > 0:
                    x, y = 1160 + (k % 2) * 350, 490 + (k // 2) * 150
                    d.rounded_rectangle((x, y, x + 335, y + 135), 20, fill=(18, 10, 50, int(232 * a)), outline=c_ + (int(255 * a),), width=5)
                    d.text((x + 168, y + 55), big, font=F(62), fill=c_ + (int(255 * a),), anchor="mm")
                    d.text((x + 168, y + 105), small, font=F(28, False), fill=(245, 242, 255, int(255 * a)), anchor="mm")
        elif kind in ("metrics", "rcs", "trk"):
            tab = {"metrics": "sum" if u < 0.4 else "trk" if u < 0.65 else "pdrcs", "rcs": "pdrcs", "trk": "trk"}[kind]
            pg.evaluate(f"tab='{tab}'; buildMetricTabs()")
            card = pg.locator(".card.c-me")
            shot = shot_png(card)
            title(d, {"sum": "RESULTS OVER 20 SIMULATED FLIGHTS", "trk": "TRACKING ERROR VS RANGE", "pdrcs": "DETECTION VS TARGET SIZE"}[tab])
            w, h = place(img, shot, 80, 108, h=670)
            tiles = {"sum": [("0.64 m", "position error RMS", AM), ("0.81 m/s", "speed error RMS", MG), ("20 / 20", "flights confirmed", LM)],
                     "trk": [("≈ 1 m", "median error at 300 m", AM), ("≈ 3 m", "target 10× smaller", MG), ("< 20 cm", "inside 100 m, both", LM)],
                     "pdrcs": [("6 cm²", "90% detection at 1e-4", AM), ("10 cm²", "90% detection at 1e-6", MG), ("300 m", "range of this test", CY)]}[tab]
            for k, (big, small, c_) in enumerate(tiles):
                kpi(d, 1250, 130 + k * 215, big, small, c_, reveal(u, 0.04 + 0.1 * k) if kind == "metrics" else reveal(u, 0.05 + 0.12 * k), 560)
        elif kind in ("agent", "agent2"):
            T = (20.0 + 11.0 * u) if kind == "agent" else (8.0 + 19.5 * u)
            pg.evaluate(f"T={T}; drawAll(); const a=document.getElementById('agent'); a.scrollTop=a.scrollHeight;")
            shot = shot_png(pg.locator(".card.c-ag"))
            title(d, "THE AGENT PROPOSES, THE HUMAN DECIDES" if kind == "agent" else "THE MODEL IS USEFUL, NOT TRUSTED", MG)
            place(img, shot, 80, 108, h=670)
            tl = [(24.5, "Manager REJECTS police escalation", RD), (29.5, "Approved only over the fence line", LM), (25.5, "Authority alerted, 2 s before fence", AM)] if kind == "agent" else \
                 [(9.5, "Grounding check flags a wrong zone claim", AM), (20.5, "Policy adds the authority alert", CY), (26.5, "Floor raises threat to CRITICAL", RD)]
            for k, (tt, s_, c_) in enumerate(tl):
                a = ease((T - tt + 0.4) / 0.6)
                if a > 0:
                    d.rounded_rectangle((1250, 160 + k * 170, 1850, 290 + k * 170), 22, fill=(18, 10, 50, int(230 * a)), outline=c_ + (int(255 * a),), width=5)
                    ls = wrap(d, s_, F(42), 540)
                    for j, ln in enumerate(ls):
                        d.text((1280, 225 + k * 170 - (len(ls) - 1) * 24 + j * 48), ln, font=F(42), fill=c_ + (int(255 * a),), anchor="lm")
        elif kind == "audit":
            if i == 0:
                pg.evaluate("T=31; drawAll()")
            if u > 0.22 and u <= 0.24:
                pg.evaluate("verify()")
            if u > 0.50 and u <= 0.52:
                pg.evaluate("document.getElementById('tamper').click()")
            if u > 0.80 and u <= 0.82:
                pg.evaluate("document.getElementById('tamper').click()")
            shot = shot_png(pg.locator(".card.c-au"))
            title(d, "EVERY STEP IS HASH-CHAINED AND VERIFIABLE", LM)
            place(img, shot, 80, 108, h=670)
            for k, (s_, c_, t0) in enumerate([("SHA-256 recomputed in your browser", CY, 0.2), ("48 entries: chain intact", LM, 0.26), ("Edit one entry: the chain breaks at that entry", RD, 0.5), ("Restore it: verified again", LM, 0.8)]):
                a = reveal(u, t0)
                if a > 0:
                    d.rounded_rectangle((1000, 160 + k * 150, 1850, 270 + k * 150), 22, fill=(18, 10, 50, int(230 * a)), outline=c_ + (int(255 * a),), width=5)
                    d.text((1030, 215 + k * 150), s_, font=F(40), fill=c_ + (int(255 * a),), anchor="lm")
        img.convert("RGB").save(f"{out}/f{i:05d}.png", compress_level=1)
    pg.close()
    json.dump(dict(n=n, fps=CAP_FPS), open(f"{out}/meta.json", "w"))
    print("dash", sid, kind, n, "frames", flush=True)


if __name__ == "__main__":
    sids = sys.argv[1:] or list(KIND)
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
        for s in sids:
            run(s, br)
        br.close()
