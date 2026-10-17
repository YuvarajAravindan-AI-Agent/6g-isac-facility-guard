import base64, hashlib, json, os, time, wave, requests
from script import SEGS, EXTRA, tts_text
HERE = os.path.dirname(os.path.abspath(__file__))
VOICE, MODEL = "Gacrux", "gemini-3.8-flash-tts"
CACHE = os.path.join(HERE, "tts_cache"); os.makedirs(CACHE, exist_ok=True)
GW = dict(l.strip().split("=", 1) for l in open(os.path.expanduser("~/Videos/agent-factory/gw.env")) if "=" in l)
def tts(text):
    p = os.path.join(CACHE, hashlib.sha1(f"{VOICE}|{MODEL}|{text}".encode()).hexdigest() + ".wav")
    if os.path.exists(p): return p
    body = {"contents": [{"parts": [{"text": text}]}], "generationConfig": {"responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    for a in range(12):
        r = requests.post(f"{GW['GEMINI_BASE']}/{MODEL}:generateContent", json=body, timeout=180, headers={"x-goog-api-key": GW["GEMINI_API_KEY"]})
        if r.status_code == 200:
            try:
                b = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]); assert b[:4] == b"RIFF"
                open(p, "wb").write(b); return p
            except Exception as e: err = f"bad payload {e}"
        else: err = f"HTTP {r.status_code} {r.text[:120]}"
        print("  retry", a, err, flush=True); time.sleep(min(60, 8 * (a + 1)))
    raise RuntimeError(err)
out = {}
for s in SEGS + EXTRA:
    p = tts(tts_text(s["text"]))
    with wave.open(p) as w: d = w.getnframes() / w.getframerate()
    out[s["id"]] = dict(wav=p, dur=round(d, 2)); print(s["id"], round(d, 1), "s", flush=True)
json.dump(out, open(os.path.join(HERE, "durations.json"), "w"), indent=1)
print("total", round(sum(v["dur"] for v in out.values()), 1), "s")
