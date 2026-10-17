"""Shared look: neon-dusk cinema. Fonts: Liberation Sans Narrow (display), DejaVu Sans Mono (data)."""
import math
import os
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 24
BAR = (H - 804) // 2            # letterbox bar height for the 2.39:1 picture
FL = "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono"

CY, MG, AM, LM, RD, WH = (40, 225, 255), (255, 63, 180), (255, 176, 32), (125, 255, 107), (255, 59, 74), (245, 242, 255)
INK, VIO, DEEP = (14, 10, 40), (58, 31, 158), (26, 12, 70)


def F(size, bold=True):
    return ImageFont.truetype(FL + ("Bold" if bold else "Regular") + ".ttf", size)


def FMONO(size, bold=False):
    return ImageFont.truetype(FM + ("-Bold" if bold else "") + ".ttf", size)


_bg = {}


def dusk_bg():
    """Vertical dusk gradient with a horizon glow and a perspective grid (synthwave-ish), cached."""
    if "bg" in _bg:
        return _bg["bg"].copy()
    img = Image.new("RGB", (W, H))
    px = img.load()
    stops = [(0.0, (14, 8, 44)), (0.45, (58, 31, 158)), (0.72, (255, 79, 139)), (0.86, (255, 154, 60)), (1.0, (40, 14, 70))]
    for y in range(H):
        t = y / (H - 1)
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                a, b = stops[i], stops[i + 1]
                f = (t - a[0]) / (b[0] - a[0])
                c = tuple(int(a[1][k] + (b[1][k] - a[1][k]) * f) for k in range(3))
                break
        for x in range(0, W, 8):
            for k in range(8):
                px[x + k, y] = c
    d = ImageDraw.Draw(img, "RGBA")
    hz = int(H * 0.78)
    for i in range(-20, 21):
        d.line((W / 2 + i * 40, hz, W / 2 + i * 340, H), fill=(40, 225, 255, 70), width=2)
    for j in range(1, 9):
        y = hz + (H - hz) * (j / 8) ** 1.8
        d.line((0, y, W, y), fill=(255, 63, 180, 60), width=2)
    _bg["bg"] = img
    return img.copy()


def text(d, xy, s, font, fill=WH, anchor="la", shadow=True):
    if shadow:
        d.text((xy[0] + 2, xy[1] + 3), s, font=font, fill=(0, 0, 0, 160), anchor=anchor)
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


def wrap(d, s, font, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def tile(img, box, fill=(20, 12, 54, 215), outline=CY, width=3, r=22):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle(box, r, fill=fill, outline=outline + (255,), width=width)
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def chip(d, xy, s, color=CY, font=None, pad=14):
    font = font or F(26)
    w = d.textlength(s, font=font)
    d.rounded_rectangle((xy[0], xy[1], xy[0] + w + 2 * pad, xy[1] + 44), 14, fill=(14, 8, 44), outline=color, width=3)
    d.text((xy[0] + pad, xy[1] + 22), s, font=font, fill=color, anchor="lm")
    return xy[0] + w + 2 * pad


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def frame_canvas():
    return Image.new("RGB", (W, H), (0, 0, 0))


def captions_for(text_, dur, lead=0.2):
    """Split narration into caption chunks (<= ~11 words, at punctuation) timed by character count."""
    import re
    sents = re.split(r"(?<=[.!?:;])\s+", text_.strip())
    chunks = []
    for s in sents:
        words = s.split()
        if len(words) <= 12:
            chunks.append(s)
        else:
            step = math.ceil(len(words) / math.ceil(len(words) / 10))
            chunks += [" ".join(words[i:i + step]) for i in range(0, len(words), step)]
    total = sum(len(c) + 4 for c in chunks)
    t, out = lead, []
    span = max(0.1, dur - lead - 0.1)
    for c in chunks:
        d = span * (len(c) + 4) / total
        out.append((t, t + d, c))
        t += d
    return out


def draw_caption(img, s):
    d = ImageDraw.Draw(img, "RGBA")
    f = F(44)
    lines = wrap(d, s, f, 1560)
    y = H - BAR // 2 - len(lines) * 26 + 4
    for i, ln in enumerate(lines):
        text(d, (W / 2, y + i * 52), ln, f, WH, anchor="ma")


def chrome_bars(img, left="6G ISAC · SIMULATION", right=""):
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, 0, W, BAR), fill=(0, 0, 0))
    d.rectangle((0, H - BAR, W, H), fill=(0, 0, 0))
    chip(d, (40, 47), left, MG, F(28))
    if right:
        d.text((W - 40, BAR // 2), right, font=FMONO(26, True), fill=CY, anchor="rm")
