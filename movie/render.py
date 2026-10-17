"""blender -b --python render.py -- OUTDIR RESX RESY SAMPLES [--only s1c1,s2c2] [--still] [--fps 24]
Renders every cut as a PNG sequence + anchors.json (projected screen positions of entities)."""
import json
import math
import os
import sys
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import world as Wd

args = sys.argv[sys.argv.index("--") + 1:]
OUT, RX, RY, SAMPLES = args[0], int(args[1]), int(args[2]), int(args[3])
ONLY = args[args.index("--only") + 1].split(",") if "--only" in args else None
STILL = "--still" in args
FPS = int(args[args.index("--fps") + 1]) if "--fps" in args else 24
DUR = json.load(open(os.path.join(HERE, "durations.json")))


def ease(u):
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def V(*a):
    return Vector(a)


def dir_of():
    return Wd.VEL.normalized()


# rigs: (u, sim_t) -> (cam_location, look_target, focal_length_mm)
def r_fly_low(u, t):
    return V(lerp(95, 45, ease(u)), lerp(-130, -45, ease(u)), lerp(4, 14, u)), V(36, 0, 16), 26


def r_mast_orbit(u, t):
    a = math.radians(-70 + 120 * u)
    return V(36 + 16 * math.cos(a), 16 * math.sin(a), 24 + 3 * u), V(36, 0, 24), 24


def r_tele(u, t):
    return V(lerp(70, 62, u), -30, lerp(3, 5, u)), Wd.drone_pos(t), 100


def r_chase(u, t):
    d = Wd.drone_pos(t)
    dv = dir_of()
    side = V(-dv.y, dv.x, 0).normalized()
    return d - dv * 48 + side * lerp(14, 22, u) + V(0, 0, 9), d + dv * 20, 34


def r_front(u, t):
    return V(27, -6, 3), Wd.drone_pos(t), lerp(40, 60, u)


def r_crane_zones(u, t):
    return V(lerp(-250, -140, ease(u)), lerp(-260, -170, ease(u)), lerp(110, 250, ease(u))), V(0, 0, 0), 28


def r_ptz_view(u, t):
    return Wd.PTZ_POS + V(0, 0, 1.5), Wd.drone_pos(t), 110


def r_patrol(u, t):
    p, _, _ = Wd.car_state(t)
    return p + V(lerp(16, 12, u), lerp(-6, -10, u), 2.4), p + V(0, 0, 1.0), 32


def r_slowfence(u, t):
    return V(40, lerp(-26, -22, u), 2.0), Wd.drone_pos(t), 38


def r_room_dolly(u, t):
    o = Wd.OFF_ROOM
    return o + V(lerp(-1.6, 0.5, ease(u)), lerp(-3.6, -1.0, ease(u)), lerp(1.9, 1.5, u)), o + V(0, 2.6, 1.7), 28


def r_room_close(u, t):
    o = Wd.OFF_ROOM
    return o + V(lerp(1.6, 0.4, u), lerp(0.1, 0.6, u), 1.35), o + V(-0.3, 2.4, 1.5), 38


def r_room_over(u, t):
    o = Wd.OFF_ROOM
    return o + V(lerp(-0.6, 0.4, u), -0.1, 1.95), o + V(0, 3.0, 1.8), 24


def r_pullback(u, t):
    return V(lerp(22, -170, ease(u)), lerp(-18, -230, ease(u)), lerp(16, 170, ease(u))), V(0, 0, 10), 30


def r_crane_rays(u, t):
    return V(lerp(62, -8, ease(u)), lerp(-58, -70, ease(u)), lerp(42, 24, ease(u))), V(10, 0, 8), 30


def r_orbit_site(u, t):
    a = math.radians(-120 + 80 * u)
    return V(190 * math.cos(a), 190 * math.sin(a), lerp(90, 60, u)), V(0, 0, 8), 32


RIGS = dict(fly_low=r_fly_low, mast_orbit=r_mast_orbit, tele=r_tele, chase=r_chase, front=r_front,
            crane_zones=r_crane_zones, ptz_view=r_ptz_view, patrol=r_patrol, slowfence=r_slowfence,
            room_dolly=r_room_dolly, room_close=r_room_close, room_over=r_room_over, pullback=r_pullback,
            orbit_site=r_orbit_site, crane_rays=r_crane_rays)

# (cut id, segment, rig, seconds, sim_a, sim_b)
CUTS = [
    ("s1c1", "s1", "fly_low", 4.5, 0.0, 1.5), ("s1c2", "s1", "mast_orbit", 3.5, 1.5, 2.5), ("s1c3", "s1", "chase", 5.0, 2.0, 6.0),
    ("s2c1", "s2", "mast_orbit", 5.5, 6.0, 7.0), ("s2c2", "s2", "crane_zones", 7.5, 7.0, 11.0), ("s2c3", "s2", "tele", 5.6, 11.0, 13.0),
    ("s6c1", "s6", "room_dolly", 6.5, 3.0, 4.0), ("s6c2", "s6", "room_close", 5.5, 4.0, 4.5), ("s6c3", "s6", "room_over", 5.3, 13.0, 14.0),
    ("s7c1", "s7", "patrol", 7.2, 12.3, 18.5), ("s7c2", "s7", "ptz_view", 5.0, 14.0, 17.0), ("s7c3", "s7", "front", 8.0, 17.0, 22.0),
    ("s9c1", "s9", "front", 4.5, 22.0, 25.0), ("s9c2", "s9", "slowfence", 8.0, 26.0, 28.5), ("s9c3", "s9", "chase", 5.9, 27.5, 29.9),
    ("s10c1", "s10", "pullback", 11.0, 29.5, 30.15), ("s10c2", "s10", "orbit_site", 12.0, 30.15, 30.15),
    ("l3c1", "l3", "crane_rays", 8.0, 0.0, 0.0), ("l3c2", "l3", "mast_orbit", 6.0, 0.0, 0.0), ("l3c3", "l3", "orbit_site", 7.4, 0.0, 0.0),
]
# scale each segment's cuts to the narration length
SEGLEN = {k: v["dur"] for k, v in DUR.items()}
tot = {}
for c in CUTS:
    tot[c[1]] = tot.get(c[1], 0) + c[3]
CUTS = [(i, s, r, d * SEGLEN[s] / tot[s], a, b) for (i, s, r, d, a, b) in CUTS]

Wd.build()
Wd.configure(RX, RY, SAMPLES)
sc = bpy.context.scene
cam = Wd.W["cam"]
ENT = {
    "drone": lambda: Wd.W["drone"].location.copy(),
    "mast": lambda: V(36, 0, 26.5),
    "ptz": lambda: Wd.W["ptz"].location.copy(),
    "car": lambda: Wd.W["car"].location + V(0, 0, 2.6),
    "operator": lambda: Wd.OFF_ROOM + V(0, 0.9, 1.9),
    "monitor": lambda: Wd.OFF_ROOM + V(0, 2.35, 2.3),
    "fence": lambda: V(30, -14, 2.8),
    "facility": lambda: V(0, 0, 9),
    "gate": lambda: Wd.GATE + V(0, 0, 3),
}


def render_cut(cid, seg, rig, secs, a, b):
    n = max(1, int(round(secs * FPS)))
    frames = [n // 2] if STILL else range(n)
    os.makedirs(f"{OUT}/{cid}", exist_ok=True)
    anchors = {}
    movie_off = sum(c[3] for c in CUTS[:[x[0] for x in CUTS].index(cid)])
    for f in frames:
        u = f / max(1, n - 1)
        sim_t = a + (b - a) * u
        mt = movie_off + f / FPS
        Wd.set_state(sim_t, mt)
        Wd.rays_visible(seg == "l3", mt)
        loc, tgt, lens = RIGS[rig](u, sim_t)
        cam.location = loc
        cam.data.lens = lens
        Wd.look_at(cam, tgt)
        bpy.context.view_layer.update()
        an = {}
        for k, fn in ENT.items():
            x, y, z = world_to_camera_view(sc, cam, fn())
            an[k] = [round(x * RX, 1), round((1 - y) * RY, 1), round(z, 1)]
        d = Wd.W["drone"].location
        an["_sim_t"] = round(sim_t, 3)
        an["_range"] = round((d - Wd.GNB).length, 1)
        an["_dist_fac"] = round(math.hypot(d.x, d.y), 1)
        anchors[f] = an
        sc.render.filepath = f"{OUT}/{cid}/f{f:05d}.png"
        bpy.ops.render.render(write_still=True)
    json.dump(dict(fps=FPS, n=n, anchors=anchors), open(f"{OUT}/{cid}/anchors.json", "w"))


import time
t0 = time.time()
for c in CUTS:
    if ONLY and c[0] not in ONLY:
        continue
    t1 = time.time()
    render_cut(*c)
    print("CUT", c[0], round(c[3], 1), "s", "render", round(time.time() - t1, 1), "s", flush=True)
print("TOTAL", round(time.time() - t0, 1), flush=True)
