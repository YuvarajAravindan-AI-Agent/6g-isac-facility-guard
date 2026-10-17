"""Engineering-proof cards: sequence diagram, workflow, config snapshots, code snapshots, repo/commit log.
All content is read from the real files and the real git history at render time."""
import io
import json
import os
import subprocess
from PIL import Image, ImageDraw
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import JsonLexer, PythonLexer
from common import *
import cards
from cards import CW, CH, alpha_at, base, box, arrow, layer, put, rgba

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def git(*a):
    return subprocess.check_output(["git", "-C", ROOT, *a], text=True).strip()


def panel(d, b, title, a=1.0, color=CY):
    d.rounded_rectangle(b, 18, fill=rgba((10, 6, 30), 0.96 * a), outline=rgba(color, a), width=3)
    d.rectangle((b[0] + 3, b[1] + 3, b[2] - 3, b[1] + 40), fill=rgba((30, 20, 70), a))
    for i, c_ in enumerate([RD, AM, LM]):
        d.ellipse((b[0] + 16 + i * 26, b[1] + 14, b[0] + 30 + i * 26, b[1] + 28), fill=rgba(c_, a))
    d.text((b[0] + 100, b[1] + 22), title, font=FMONO(22, True), fill=rgba((200, 190, 255), a), anchor="lm")


def code_img(src, start, fs=22):
    fmt = ImageFormatter(style="monokai", font_name="DejaVu Sans Mono", font_size=fs, line_numbers=True, line_number_start=start,
                         image_pad=10, line_pad=3, line_number_bg="#1a1236", line_number_fg="#8a7fc2", line_number_separator=True)
    return Image.open(io.BytesIO(highlight(src, PythonLexer(), fmt))).convert("RGB")


def snippet(path, ranges):
    lines = open(os.path.join(ROOT, path)).read().split("\n")
    return [("\n".join(lines[a - 1:b]), a, b) for a, b in ranges]


def commit_of(path):
    return git("log", "-1", "--format=%h", "--", path)


def code_card(title_, path, ranges, notes, p, fs=22):
    rng = ", ".join(f"L{a}–{b}" for a, b in ranges)
    img = base(title_, f"{path}   ·   {rng}   ·   commit {commit_of(path)}")
    L = layer()
    d = ImageDraw.Draw(L)
    chunks = snippet(path, ranges)
    y = 190
    for k, (src, a, b) in enumerate(chunks):
        al = alpha_at(p, k, len(chunks) + len(notes), 0.1)
        if al <= 0:
            continue
        im = code_img(src, a, fs)
        w = min(im.width, 1380)
        im = im.crop((0, 0, w, im.height))
        d.rounded_rectangle((60, y - 6, 60 + w + 12, y + im.height + 6), 14, fill=rgba((10, 6, 30), al), outline=rgba(CY, al), width=3)
        tmp = im.convert("RGBA")
        tmp.putalpha(int(255 * al))
        L.paste(tmp, (66, y), tmp)
        y += im.height + 26
    for k, (s_, c_) in enumerate(notes):
        al = alpha_at(p, len(chunks) + k, len(chunks) + len(notes), 0.1)
        if al > 0:
            x = 1500
            yy = 210 + k * 190
            d.rounded_rectangle((x, yy, 1880, yy + 170), 20, fill=rgba((18, 10, 50), 0.92 * al), outline=rgba(c_, al), width=4)
            for j, ln in enumerate(wrap(d, s_, F(30), 340)):
                d.text((x + 20, yy + 20 + j * 38), ln, font=F(30), fill=rgba(c_ if j == 0 else WH, al))
    return put(img, L).convert("RGB")


def code_gov(p):
    return code_card("THE POLICY ENGINE, IN CODE", "agent/agent.py", [(103, 111), (128, 130)],
                     [("Floor: unregistered drone in the restricted zone is at least HIGH, whatever the model said", AM),
                      ("Block: anything outside the catalog or on the never-executable list", RD)], p, fs=19)


def code_audit(p):
    return code_card("THE AUDIT CHAIN, IN CODE", "agent/audit.py", [(13, 19), (22, 30)],
                     [("Each entry stores the hash of the one before it", CY), ("Verify recomputes every hash; one edit breaks all that follow", LM)], p, fs=17)


def code_cfar(p):
    return code_card("THE DETECTOR, IN CODE", "sim/pipeline.py", [(49, 50), (87, 90)],
                     [("alpha comes from the false-alarm target and the 616 training cells", CY), ("Noise = box average minus the guard region; runs on the GPU over 2M cells per frame", AM)], p, fs=22)


def seqdiag(p):
    img = base("SEQUENCE: FROM ECHO TO AUDITED ACTION", "who talks to whom, in order")
    L = layer()
    d = ImageDraw.Draw(L)
    names = [("Base station", CY), ("Sensing pipeline", MG), ("Tracker", AM), ("Evidence tools", LM), ("Llama 3.1 8B", CY), ("Policy engine", MG), ("Human approver", AM), ("Audit log", LM)]
    xs = [150 + i * 232 for i in range(len(names))]
    for (n_, c_), x in zip(names, xs):
        d.rounded_rectangle((x - 105, 196, x + 105, 252), 14, fill=rgba((18, 10, 50), 0.95), outline=rgba(c_), width=4)
        d.text((x, 224), n_, font=F(27), fill=rgba(c_), anchor="mm")
        for y in range(262, 780, 22):
            d.line((x, y, x, y + 11), fill=rgba(c_, 0.55), width=3)
    msgs = [(0, 1, "echo of the OFDM signal"), (1, 2, "detections: range, speed, angle"), (2, 3, "confirmed track"), (3, 4, "evidence + rules + catalog"),
            (4, 5, "proposal (JSON)"), (5, 6, "approval request"), (6, 5, "approve / reject"), (5, 7, "every step, hash-chained")]
    for k, (a_, b_, s_) in enumerate(msgs):
        al = alpha_at(p, k, len(msgs) + 1, 0.09)
        if al <= 0:
            continue
        y = 318 + k * 55
        x0, x1 = xs[a_], xs[b_]
        col = names[a_][1]
        arrow(d, (x0 + (8 if x1 > x0 else -8), y), (x1 - (8 if x1 > x0 else -8), y), col, al, 5)
        mx = (x0 + x1) / 2
        d.text((mx, y - 16), s_, font=F(25, False), fill=rgba(WH, al), anchor="mm")
    al = alpha_at(p, len(msgs), len(msgs) + 1, 0.09)
    if al > 0:
        d.rounded_rectangle((xs[5] - 120, 764, xs[7] + 100, 794), 8, fill=rgba(LM, al * 0.9))
        d.text(((xs[5] + xs[7]) / 2, 779), "action executed in simulation only, then logged", font=F(22), fill=rgba(INK, al), anchor="mm")
    return put(img, L).convert("RGB")


def workflow(p):
    img = base("WORKFLOW FOR EVERY PROPOSED ACTION", "decided by the policy engine, not by the model")
    L = layer()
    d = ImageDraw.Draw(L)
    def node(k, b, t_, s_, c_):
        al = alpha_at(p, k, 10, 0.09)
        if al > 0:
            box(d, b, t_, s_, c_, al, 34, 24)
        return al
    node(0, (60, 330, 330, 470), "PROPOSED", "from Llama, or added by policy", CY)
    node(1, (420, 330, 760, 470), "POLICY CHECK", "floors · minimums · catalog", MG)
    node(2, (850, 190, 1190, 320), "AUTO", "internal, reversible", LM)
    node(3, (850, 350, 1190, 480), "NEEDS APPROVAL", "touches the real world", AM)
    node(4, (850, 510, 1190, 640), "BLOCKED", "never executable / not in catalog", RD)
    node(5, (1290, 190, 1580, 320), "EXECUTED", "simulated, logged", LM)
    node(6, (1290, 350, 1580, 480), "HUMAN DECIDES", "20 s to answer", AM)
    node(7, (1680, 300, 1880, 400), "APPROVED", "→ executed", LM)
    node(8, (1680, 420, 1880, 520), "REJECTED", "logged", RD)
    node(9, (1680, 540, 1880, 640), "EXPIRED", "logged", (170, 160, 200))
    for k, (a_, b_, c_) in enumerate([((335, 400), (415, 400), WH), ((765, 400), (845, 255), LM), ((765, 400), (845, 415), AM), ((765, 400), (845, 575), RD),
                                       ((1195, 255), (1285, 255), LM), ((1195, 415), (1285, 415), AM), ((1585, 415), (1675, 350), LM), ((1585, 415), (1675, 470), RD), ((1585, 415), (1675, 590), (170, 160, 200))]):
        al = alpha_at(p, k + 1, 10, 0.09)
        if al > 0:
            arrow(d, a_, b_, c_, al, 5)
    return put(img, L).convert("RGB")


def read_lines(path, keys):
    out = []
    for ln in open(os.path.join(ROOT, path)).read().split("\n"):
        if any(ln.startswith(k) for k in keys):
            out.append(ln.split("#")[0].rstrip())
    return out


def config(p):
    img = base("CONFIGURATION SNAPSHOTS", "real files at the moment of recording")
    L = layer()
    d = ImageDraw.Draw(L)
    pol = json.load(open(os.path.join(ROOT, "agent", "policy.json")))
    a1 = alpha_at(p, 0, 3, 0.12)
    if a1 > 0:
        panel(d, (50, 190, 700, 770), f"agent/policy.json  ·  {commit_of('agent/policy.json')}", a1, AM)
        y = 250
        for ln in ['"zones": [warning 250 m, restricted 120 m,', '          critical 45 m],', '"actions": {']:
            d.text((72, y), ln, font=FMONO(21), fill=rgba(WH, a1)); y += 29
        for name, v in pol["actions"].items():
            d.text((90, y), f'"{name}"', font=FMONO(20, True), fill=rgba(LM, a1))
            d.text((470, y), "approval" if v["requires_approval"] else "auto", font=FMONO(20, True), fill=rgba(AM if v["requires_approval"] else CY, a1)); y += 29
        for ln in ['},', '"never_executable": [', '   "jam_or_spoof_drone",', '   "kinetic_countermeasure"]']:
            d.text((72, y), ln, font=FMONO(21), fill=rgba(WH, a1)); y += 29
    a2 = alpha_at(p, 1, 3, 0.12)
    if a2 > 0:
        panel(d, (730, 190, 1330, 770), f"sim/isac_sim.py  ·  {commit_of('sim/isac_sim.py')}", a2, CY)
        keys = ["FC =", "B =", "N =", "DF =", "M =", "PT_DBM", "GAIN_DB", "NF_DB", "RCS =", "FRAME_DT", "SPEED ="]
        y = 250
        for ln in read_lines("sim/isac_sim.py", keys):
            d.text((752, y), ln, font=FMONO(21), fill=rgba(WH, a2)); y += 31
        for ln in ["", "# sim/pipeline.py", "PFA = 1e-6", "KA, KE = 16, 8", "GV, GR, TV, TR = 2, 3, 8, 12"]:
            d.text((752, y), ln, font=FMONO(21), fill=rgba(LM if ln.startswith("#") else WH, a2)); y += 31
    a3 = alpha_at(p, 2, 3, 0.12)
    if a3 > 0:
        panel(d, (1360, 190, 1880, 770), "deployment", a3, MG)
        y = 250
        for ln, c_ in [("AWS us-east-1", CY), ("g6.xlarge · NVIDIA L4", WH), ("Ubuntu 22.04 DLAMI (stopped)", WH), ("", WH), ("Ollama", CY), ("llama3.1:8b · 4.9 GB", WH), ("temperature 0 · seed 42", WH), ("LLM_MODE=replay", LM), ("", WH), ("Contabo VPS · Caddy", CY), ("/6g-isac → static files", WH), ("no backend, no GPU", LM)]:
            d.text((1382, y), ln, font=FMONO(22, True), fill=rgba(c_, a3)); y += 36
    return put(img, L).convert("RGB")


def repo(p):
    img = base("VERSION CONTROL AND CHECKS", "the commits, the layout and the tests")
    L = layer()
    d = ImageDraw.Draw(L)
    log = git("log", "--format=%h  %s", "--reverse").split("\n")
    n_commits = len(log)
    a1 = alpha_at(p, 0, 3, 0.12)
    if a1 > 0:
        panel(d, (50, 190, 1230, 560), "$ git log --oneline", a1, AM)
        y = 250
        for ln in log[-9:]:
            h, s_ = ln.split("  ", 1)
            d.text((74, y), h, font=FMONO(22, True), fill=rgba(AM, a1))
            d.text((190, y), s_[:78], font=FMONO(21), fill=rgba(WH, a1)); y += 33
        d.text((74, 530), f"{n_commits} commits on main · private repository, access on request", font=F(28, False), fill=rgba((200, 190, 255), a1))
    a2 = alpha_at(p, 1, 3, 0.12)
    if a2 > 0:
        panel(d, (1260, 190, 1880, 560), "layout", a2, CY)
        files = git("ls-files").split("\n")
        rows = []
        for top in ["sim", "agent", "site", "movie"]:
            fs = [f for f in files if f.startswith(top + "/")]
            py = sum(len(open(os.path.join(ROOT, f), errors="ignore").read().split("\n")) for f in fs if f.endswith((".py", ".html")))
            rows.append((top + "/", len(fs), py))
        y = 255
        for n_, c_, l_ in rows:
            d.text((1284, y), n_, font=FMONO(24, True), fill=rgba(CY, a2))
            d.text((1440, y), f"{c_:>3} files", font=FMONO(22), fill=rgba(WH, a2))
            d.text((1640, y), f"{l_:>5} lines", font=FMONO(22), fill=rgba(WH, a2)); y += 50
        d.text((1284, y + 14), "Python + HTML only; media is not tracked", font=F(26, False), fill=rgba((200, 190, 255), a2))
    a3 = alpha_at(p, 2, 3, 0.12)
    if a3 > 0:
        panel(d, (50, 590, 1880, 775), "$ python agent/agent.py selftest   ·   LLM_MODE=replay python agent/agent.py", a3, LM)
        res = json.loads(subprocess.check_output(["python3", os.path.join(ROOT, "agent", "agent.py"), "selftest"], text=True, cwd=os.path.join(ROOT, "agent")))
        ok = sum(1 for v in res.values() if v)
        d.text((74, 655), f"selftest: {ok}/{len(res)} checks pass", font=FMONO(30, True), fill=rgba(LM, a3))
        d.text((74, 700), "(forged jam answer blocked · threat floor · unknown action blocked · audit tamper detected)", font=FMONO(20), fill=rgba(WH, a3))
        d.text((74, 735), "replay: 4/4 Llama answers from cache, same event sequence, audit chain valid, no GPU", font=FMONO(22, True), fill=rgba(WH, a3))
    return put(img, L).convert("RGB")


cards.KINDS.update(dict(seqdiag=seqdiag, workflow=workflow, config=config, code_gov=code_gov, code_audit=code_audit, code_cfar=code_cfar, repo=repo))
