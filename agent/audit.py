"""Append-only, hash-chained audit log (tamper-evident)."""
import hashlib
import json
import datetime


class Audit:
    def __init__(self, path):
        self.path, self.prev, self.seq = path, "0" * 64, 0
        open(path, "w").close()

    def log(self, type_, sim_t, incident, payload):
        e = {"seq": self.seq, "wall": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             "sim_t": round(sim_t, 2), "type": type_, "incident": incident, "payload": payload, "prev": self.prev}
        e["hash"] = hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()
        with open(self.path, "a") as f:
            f.write(json.dumps(e) + "\n")
        self.prev, self.seq = e["hash"], self.seq + 1
        return e


def verify(path):
    prev, n = "0" * 64, 0
    for line in open(path):
        e = json.loads(line)
        h = e.pop("hash")
        if e["prev"] != prev or hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest() != h:
            return False, n, e["seq"]
        prev, n = h, n + 1
    return True, n, None
