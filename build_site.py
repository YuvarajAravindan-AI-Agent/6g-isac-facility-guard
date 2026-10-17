"""Build site/data/* for the static dashboard from sim/ and agent/ outputs (no GPU needed)."""
import json, pathlib, shutil, sys
R = pathlib.Path(__file__).parent
SRC = R / "sim" / ("new" if (R / "sim" / "new" / "rd_frames.bin").exists() else ".")
OUT = R / "site" / "data"
OUT.mkdir(parents=True, exist_ok=True)

tr = json.load(open(SRC / "tracks.json"))
frames = []
for f in tr["frames"]:
    t = f["truth"]
    k = f["track"]
    frames.append(dict(
        t=f["t"], truth=[*t["pos"], t["R"], t["rv"]],
        track=None if not k else dict(p=k["pos"], v=k["vel"], s=k["sigma_pos"], c=k["confirmed"]),
        det=[[d["R"], d["vr"], d["u"], d["v"], d["snr_db"], int(d["is_truth"])] for d in f["detections"]],
        err=f["err_pos"]))
json.dump(dict(meta=tr["meta"], frames=frames), open(OUT / "frames.json", "w"), separators=(",", ":"))

lines = [json.loads(l) for l in open(R / "agent" / "audit.jsonl")]
audit = []
for e in lines:
    e2 = dict(e); h = e2.pop("hash")
    audit.append(dict(seq=e["seq"], sim_t=e["sim_t"], type=e["type"], incident=e["incident"], payload=e["payload"],
                      prev=e["prev"], hash=h, canon=json.dumps(e2, sort_keys=True)))
json.dump(audit, open(OUT / "audit.json", "w"), separators=(",", ":"))
decisions = [a for a in audit if a["type"] == "approval_decision"]

tl = json.load(open(R / "agent" / "out" / "incident_timeline.json"))
for s in tl["steps"]:
    for ev in s["events"]:
        if ev["outcome"] in ("executed_approved", "rejected"):
            m = [d for d in decisions if d["payload"]["action"] == ev["action"] and abs(d["sim_t"] - ev["t"]) < 0.06]
            if m:
                ev["reason"] = m[0]["payload"]["reason"]; ev["approver"] = m[0]["payload"]["approver"]
    s["evidence"] = {k: v for k, v in s["evidence"].items() if k != "registered_flights_untrusted_notes"}
pol = json.load(open(R / "agent" / "policy.json"))
json.dump(dict(fence_cross_t=tl["fence_cross_t"], steps=tl["steps"], rules=pol["rules"], actions=pol["actions"],
               model=json.load(open(R / "agent" / "out" / "agent_metrics.json"))["model"]),
          open(OUT / "timeline.json", "w"), separators=(",", ":"))

shutil.copy(SRC / "metrics.json", OUT / "metrics.json")
if (SRC / "rd_frames.bin").exists():
    shutil.copy(SRC / "rd_frames.bin", OUT / "rd_frames.bin"); shutil.copy(SRC / "rd_meta.json", OUT / "rd_meta.json")
print("built from", SRC, [p.name for p in sorted(OUT.iterdir())])
