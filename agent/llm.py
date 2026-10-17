"""Llama client (Ollama) with a response cache so the public demo replays without a GPU.
LLM_MODE: live | cache-first (default) | replay (cache only; error if missing)."""
import hashlib
import json
import os
import pathlib
import time
import urllib.request

URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("LLM_MODEL", "llama3.1:8b")
MODE = os.environ.get("LLM_MODE", "cache-first")
MAX_LIVE_PER_HOUR = int(os.environ.get("MAX_LIVE_PER_HOUR", "60"))
CACHE = pathlib.Path(__file__).with_name("llm_cache.json")
_live_calls = []


def _load():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def chat(messages, schema):
    key = hashlib.sha256(json.dumps([MODEL, messages, schema], sort_keys=True).encode()).hexdigest()
    cache = _load()
    if MODE != "live" and key in cache:
        return cache[key]["content"], dict(cached=True, model=MODEL, latency_s=cache[key]["latency_s"], key=key[:12])
    if MODE == "replay":
        raise KeyError(f"replay mode: no cached response for {key[:12]}")
    now = time.time()
    _live_calls[:] = [t for t in _live_calls if now - t < 3600]
    if len(_live_calls) >= MAX_LIVE_PER_HOUR:
        raise RuntimeError("live LLM call rate limit reached")
    _live_calls.append(now)
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False, "format": schema,
                       "options": {"temperature": 0, "seed": 42, "num_predict": 500}}).encode()
    req = urllib.request.Request(URL + "/api/chat", body, {"Content-Type": "application/json"})
    t0 = time.time()
    content = json.loads(urllib.request.urlopen(req, timeout=180).read())["message"]["content"]
    lat = round(time.time() - t0, 2)
    cache[key] = dict(content=content, model=MODEL, latency_s=lat)
    CACHE.write_text(json.dumps(cache, indent=1))
    return content, dict(cached=False, model=MODEL, latency_s=lat, key=key[:12])
