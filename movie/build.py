"""Build clips and assemble cuts.
  python build.py clip s1 s3 ...     # render segment clips (video + narration) to clips/
  python build.py assemble judge     # concat clips, music bed, SRT -> out/
  python build.py assemble long
"""
import json
import math
import os
import subprocess
import sys
import wave
import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw
from common import *
import cards
import docs_cards  # registers the documentation cards
from script import BYID, ORDER_JUDGE, ORDER_LONG

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
DUR = json.load(open(os.path.join(HERE, "durations.json")))
TL = json.load(open(os.path.join(HERE, "..", "site", "data", "timeline.json")))
PAD = 0.5
CUTS = {"s1": ["s1c1", "s1c2", "s1c3"], "s2": ["s2c1", "s2c2", "s2c3"], "s6": ["s6c1", "s6c2", "s6c3"], "s7": ["s7c1", "s7c2", "s7c3"],
        "s9": ["s9c1", "s9c2", "s9c3"], "s10": ["s10c1", "s10c2"], "l3": ["l3c1", "l3c2", "l3c3"]}
NO_HUD = {"s6c1", "s6c2", "s6c3", "l3c1", "l3c2", "l3c3", "s10c2"}
# (entity, text, color, from-fraction, to-fraction) of the cut
LABELS = {
    "s1c1": [("mast", "6G base station", CY, .12, .95), ("fence", "Critical facility", MG, .35, .95)],
    "s1c2": [("mast", "Senses the sky with its own signal", CY, .1, .95)],
    "s1c3": [("drone", "Drone · unregistered", AM, .08, .95)],
    "s2c1": [("mast", "Sensing pulses", CY, .08, .95)],
    "s2c2": [("facility", "Critical facility + 3 policy zones", MG, .1, .5), ("facility", "Warning · Restricted · Critical", AM, .5, .95)],
    "s2c3": [("drone", "12 m/s · ~100 cm² target", AM, .1, .95)],
    "s6c1": [("monitor", "Governed AI agent · Llama 3.1 8B", CY, .1, .95), ("operator", "Human in the loop", LM, .4, .95)],
    "s6c2": [("monitor", "Evidence: zone · distance · time to fence", CY, .1, .95)],
    "s6c3": [("operator", "Duty officer approves", LM, .1, .95)],
    "s7c1": [("car", "Security patrol dispatched", AM, .08, .5), ("gate", "East gate", CY, .55, .95)],
    "s7c2": [("ptz", "PTZ camera cued", CY, .08, .95), ("drone", "Tracked", AM, .08, .95)],
    "s7c3": [("drone", "Unregistered · restricted zone", RD, .06, .95)],
    "s9c1": [("drone", "Entering the critical zone", RD, .08, .95)],
    "s9c2": [("drone", "Over the fence", RD, .08, .95)],
    "s9c3": [("drone", "Police escalation: approved after the fence", AM, .08, .95)],
    "s10c1": [("facility", "Substation Alpha · simulated", MG, .1, .8), ("mast", "6G base station", CY, .4, .95)],
    "l3c1": [("mast", "Illustrative ray paths", LM, .08, .95)],
    "l3c2": [("mast", "Reflections off concrete and steel", LM, .08, .95)],
    "l3c3": [("facility", "15 strong static clutter paths", AM, .08, .95)],
}


# --------------------------------------------------------------------- overlays
def callout(img, pt, s, color, a, placed):
    x, y, z = pt
    if z <= 0 or not (50 < x < W - 50 and 30 < y < 774) or a <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    al = int(255 * a)
    f = F(36)
    tw = d.textlength(s, font=f)
    bw, bh = tw + 40, 58
    right = x < W - bw - 140
    bx = x + 80 if right else x - 80 - bw
    by = y - 100 if y > 150 else y + 60
    for (px0, py0, px1, py1) in placed:
        if bx < px1 + 12 and bx + bw > px0 - 12 and by < py1 + 12 and by + bh > py0 - 12:
            by = py1 + 16 if by + bh + 80 < 770 else py0 - bh - 16
    placed.append((bx, by, bx + bw, by + bh))
    d.line((x, y, bx + (0 if right else bw), by + bh / 2), fill=color + (al,), width=4)
    k = 24
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        d.line((x + sx * k, y + sy * k, x + sx * (k - 12), y + sy * k), fill=color + (al,), width=5)
        d.line((x + sx * k, y + sy * k, x + sx * k, y + sy * (k - 12)), fill=color + (al,), width=5)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), 16, fill=(14, 8, 44, int(225 * a)), outline=color + (al,), width=4)
    d.text((bx + 20, by + bh / 2), s, font=f, fill=(255, 255, 255, al), anchor="lm")


def hud_text(an):
    t, rng, df = an["_sim_t"], an["_range"], an["_dist_fac"]
    zone = "CRITICAL" if df <= 45 else "RESTRICTED" if df <= 120 else "WARNING" if df <= 250 else "OUTSIDE"
    thr = "—"
    for s in TL["steps"]:
        if s["t"] <= t:
            thr = s["decision"]["threat_level"].upper()
    return f"T+{t:04.1f}s   RANGE {rng:3.0f} m   ZONE {zone}   THREAT {thr}"


def end_card(img, a):
    if a <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    al = int(255 * a)
    d.rounded_rectangle((260, 150, 1660, 640), 34, fill=(14, 8, 44, int(215 * a)), outline=MG + (al,), width=6)
    d.text((960, 250), "Yuvaraj Aravindan", font=F(120), fill=(255, 255, 255, al), anchor="mm")
    d.text((960, 350), "Governed AI agents for regulated industries", font=F(54, False), fill=CY + (al,), anchor="mm")
    d.rectangle((760, 400, 1160, 406), fill=AM + (al,))
    d.text((960, 470), "Try it: ai-agentic-enterprises.com/6g-isac", font=FMONO(46, True), fill=LM + (al,), anchor="mm")
    d.text((960, 560), "Simulation only · ISAC is not yet standardized by 3GPP · drone enlarged ×7 for visibility", font=F(34, False), fill=(235, 230, 255, al), anchor="mm")


def title_overlay(img, t):
    if t > 3.4:
        return
    a = ease(t / 0.5) * ease((3.4 - t) / 0.6)
    d = ImageDraw.Draw(img, "RGBA")
    al = int(255 * a)
    d.text((960, 330), "6G ISAC FACILITY GUARD", font=F(150), fill=(0, 0, 0, int(160 * a)), anchor="mm")
    d.text((956, 326), "6G ISAC FACILITY GUARD", font=F(150), fill=(255, 255, 255, al), anchor="mm")
    d.text((960, 440), "a simulation of network sensing, governed by a human", font=F(48, False), fill=AM + (al,), anchor="mm")


# --------------------------------------------------------------------- frame sources
def seg_frames(sid):
    """Yield (content_rgb_1920x804, meta) for every output frame of the segment (narration + PAD)."""
    seg = BYID[sid]
    kind, name = seg["visual"]
    narr = DUR[sid]["dur"]
    total = int(round((narr + PAD) * FPS))
    if kind == "shot":
        cuts = CUTS[sid]
        metas = []
        for c in cuts:
            m = json.load(open(f"{HERE}/frames/{c}/anchors.json"))
            metas.append((c, m["n"], m["anchors"]))
        # scale the cuts to the segment length: nominal frame counts already sum to ~narr*24; hold the last frame for the tail
        order = [(c, i) for c, n, _ in metas for i in range(n)]
        an = {c: a for c, _, a in metas}
        cut_n = {c: n for c, n, _ in metas}
        for f in range(total):
            c, i = order[min(f, len(order) - 1)]
            im = Image.open(f"{HERE}/frames/{c}/f{i:05d}.jpg").convert("RGB")
            yield im, dict(cut=c, i=i, n=cut_n[c], an=an[c][str(i)], hold=f >= len(order))
    elif kind == "card":
        last, cache = -1, None
        for f in range(total):
            idx = f // 2
            if idx != last:
                cache = cards.render(name, min(1.0, (idx * 2 / FPS) / max(1.0, narr)))
                last = idx
            yield cache, dict(card=name)
    else:  # dash
        meta = json.load(open(f"{HERE}/seg/{sid}/meta.json"))
        for f in range(total):
            idx = min(meta["n"] - 1, int(f * meta["fps"] / FPS))
            yield Image.open(f"{HERE}/seg/{sid}/f{idx:05d}.png").convert("RGB"), dict(dash=name)


def compose(content, meta, t, sid, caps):
    img = frame_canvas()
    img.paste(content, (0, BAR))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    right = ""
    if "cut" in meta:
        c, i, n = meta["cut"], meta["i"], meta["n"]
        u = i / max(1, n - 1)
        crop = Image.new("RGBA", (W, 804), (0, 0, 0, 0))
        placed = []
        for ent, s, col, f0, f1 in LABELS.get(c, []):
            a = ease((u - f0) / 0.08) * ease((f1 - u) / 0.08)
            pt = meta["an"].get(ent)
            if sid == "s1" and c == "s1c1" and t < 3.8:
                a = 0   # keep the opening title clear
            if pt:
                callout(crop, pt, s, col, a, placed)
        ov.alpha_composite(crop, (0, BAR))
        if c not in NO_HUD:
            right = hud_text(meta["an"])
        if c == "s10c2":
            ecrop = Image.new("RGBA", (W, 804), (0, 0, 0, 0))
            end_card(ecrop, ease((u - 0.1) / 0.2))
            ov.alpha_composite(ecrop, (0, BAR))
        if sid == "s1" and c == "s1c1":
            tcrop = Image.new("RGBA", (W, 804), (0, 0, 0, 0))
            title_overlay(tcrop, t)
            ov.alpha_composite(tcrop, (0, BAR))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    section = {"arch": "ARCHITECTURE", "numbers": "THE NUMBERS", "cfar": "DETECTION", "tracker": "TRACKING", "evidence": "AGENT INPUT", "hostile": "SECURITY TEST",
               "replay": "REPRODUCIBILITY", "stack": "STACK", "impact": "IMPACT", "next": "NEXT", "isac": "ISAC", "seqdiag": "SEQUENCE DIAGRAM", "workflow": "WORKFLOW", "config": "CONFIGURATION", "code_gov": "CODE · POLICY", "code_audit": "CODE · AUDIT", "code_cfar": "CODE · DETECTOR", "repo": "COMMITS AND TESTS"}.get(meta.get("card", ""), "")
    chrome_bars(img, right=right or section)
    for a, b, s in caps:
        if a <= t < b:
            draw_caption(img, s)
            break
    return img


def make_clip(sid):
    narr = DUR[sid]["dur"]
    caps = captions_for(BYID[sid]["text"], narr)
    out = f"{HERE}/clips/{sid}.mp4"
    os.makedirs(f"{HERE}/clips", exist_ok=True)
    total = narr + PAD
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", DUR[sid]["wav"],
           "-af", f"aresample=48000,apad=pad_dur={PAD}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", "-t", f"{total:.3f}", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for content, meta in seg_frames(sid):
        t = n / FPS
        p.stdin.write(compose(content, meta, t, sid, caps).tobytes())
        n += 1
    p.stdin.close()
    p.wait()
    print("clip", sid, n, "frames", round(total, 1), "s", flush=True)


# --------------------------------------------------------------------- music + assemble
def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def music(dur, path):
    sr = 44100
    n = int(dur * sr)
    t = np.arange(n) / sr
    bpm = 108
    beat = 60 / bpm
    prog = [(55.0, [220.0, 261.63, 329.63]), (43.65, [174.61, 220.0, 261.63]), (65.41, [261.63, 329.63, 392.0]), (49.0, [196.0, 246.94, 293.66])]
    out = np.zeros((n, 2))
    for bar in range(int(dur / (beat * 4)) + 1):
        root, chord = prog[bar % 4]
        for b in range(4):
            t0 = (bar * 4 + b) * beat
            i0 = int(t0 * sr)
            if i0 >= n:
                break
            L = int(beat * sr)
            tt = np.arange(min(L, n - i0)) / sr
            env = np.exp(-tt * 4.0)
            kick = np.sin(2 * np.pi * (root * 1.0) * tt) * env * (0.9 if b % 2 == 0 else 0.55)
            out[i0:i0 + len(tt), :] += kick[:, None] * 0.5
            for e in range(2):  # eighth-note arpeggio
                j0 = i0 + int(e * beat * sr / 2)
                if j0 >= n:
                    break
                ff = chord[(b * 2 + e) % 3] * 2
                tt2 = np.arange(min(int(beat * sr / 2), n - j0)) / sr
                env2 = np.exp(-tt2 * 7.0)
                saw = 2 * ((tt2 * ff) % 1) - 1
                out[j0:j0 + len(tt2), 0] += saw * env2 * 0.10
                out[j0:j0 + len(tt2), 1] += saw * env2 * 0.10 * (0.7 if e else 1.0)
            h0 = i0 + int(beat * sr / 2)
            if h0 < n:
                tt3 = np.arange(min(int(0.05 * sr), n - h0))
                out[h0:h0 + len(tt3), :] += (np.random.default_rng(b).standard_normal(len(tt3)) * np.exp(-tt3 / (0.012 * sr)) * 0.08)[:, None]
    pad = (np.sin(2 * np.pi * 110 * t) + 0.5 * np.sin(2 * np.pi * 164.8 * t)) * 0.05
    out += pad[:, None]
    fade = np.minimum(1, np.minimum(t / 2.0, (dur - t) / 3.0))
    out *= fade[:, None]
    out /= max(1e-6, np.abs(out).max()) / 0.8
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def assemble(which):
    order = ORDER_JUDGE if which == "judge" else ORDER_LONG
    os.makedirs(f"{HERE}/out", exist_ok=True)
    lst = f"{HERE}/out/{which}_list.txt"
    with open(lst, "w") as f:
        for s in order:
            f.write(f"file '{HERE}/clips/{s}.mp4'\n")
    base = f"{HERE}/out/{which}_nomusic.mp4"
    subprocess.check_call([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", base])
    total = sum(DUR[s]["dur"] + PAD for s in order)
    mp = f"{HERE}/out/music_{which}.wav"
    music(total + 1, mp)
    final = f"{HERE}/out/6g-isac-{which}.mp4"
    flt = "[1:a]volume=0.55[m];[m][0:a]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=500[duck];[0:a][duck]amix=inputs=2:weights=1 0.9:duration=first:normalize=0[a]"
    subprocess.check_call([FF, "-y", "-loglevel", "error", "-i", base, "-i", mp, "-filter_complex", flt, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", final])
    # SRT
    t0, n, lines = 0.0, 1, []
    for s in order:
        for a, b, c in captions_for(BYID[s]["text"], DUR[s]["dur"]):
            lines.append(f"{n}\n{srt_time(t0 + a)} --> {srt_time(t0 + b)}\n{c}\n")
            n += 1
        t0 += DUR[s]["dur"] + PAD
    open(f"{HERE}/out/captions-{which}-upload-only-if-no-burned-in.srt", "w").write("\n".join(lines))
    print("assembled", final, round(total, 1), "s")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "clip":
        for s in sys.argv[2:]:
            make_clip(s)
    elif cmd == "assemble":
        assemble(sys.argv[2])
