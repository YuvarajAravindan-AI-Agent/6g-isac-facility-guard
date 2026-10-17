"""Blender scene for the 6G ISAC movie (Blender 4.5, Cycles). Run inside blender -b --python render.py."""
import json
import math
import os
import bpy
from mathutils import Vector

# ----------------------------------------------------------------- geometry
GNB = Vector((36, 0, 24))
P_START = Vector((300, -200, 60))
P_END = Vector((0, 0, 30))
SPEED = 12.0
VEL = (P_END - P_START).normalized() * SPEED
SIM_END = (P_END - P_START).length / SPEED          # 30.15 s
DRONE_SCALE = 7.0                                    # enlarged for visibility (stated in the video)
OFF_ROOM = Vector((1500, 0, 0))                      # control room lives far from the site
OFF_AUDIT = Vector((0, 1500, 0))                     # hash-chain b-roll
GATE = Vector((33, -9, 0))
CAR_START = Vector((78, -52, 0))
PTZ_POS = Vector((24, -34, 8))
EVENTS = dict(confirm=1.0, cue=4.0, patrol=13.5, fence=27.5, crit=26.5)


def drone_pos(t):
    return P_START + VEL * max(0.0, min(t, SIM_END))


# ----------------------------------------------------------------- materials
def lin(c):
    return (c / 12.92) if c <= 0.04045 else (((c + 0.055) / 1.055) ** 2.4)


def rgba(h, a=1.0):
    h = h.lstrip("#")
    return tuple(lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


def mat(name, color, rough=0.55, metal=0.0, emit=None, es=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = rgba(emit)
        b.inputs["Emission Strength"].default_value = es
    return m


def glow(name, color, strength=8.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba(color)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    val = nt.nodes.new("ShaderNodeValue")
    val.outputs[0].default_value = alpha
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(val.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    m["alpha_node"] = val.name
    m["emit_node"] = em.name
    return m


def glow_img(name, path, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    m["emit_node"] = em.name
    return m


def set_glow(m, alpha=None, strength=None):
    nt = m.node_tree
    if alpha is not None:
        nt.nodes[m["alpha_node"]].outputs[0].default_value = alpha
    if strength is not None:
        nt.nodes[m["emit_node"]].inputs["Strength"].default_value = strength


# ----------------------------------------------------------------- primitives
def _fin(o, name, material, parent=None):
    o.name = name
    if material:
        o.data.materials.append(material)
    if parent:
        o.parent = parent
    return o


def box(name, size, loc, material, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.scale = size
    return _fin(o, name, material, parent)


def cyl(name, r, d, loc, material, parent=None, rot=(0, 0, 0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d, location=loc, rotation=rot, vertices=verts)
    return _fin(bpy.context.active_object, name, material, parent)


def sphere(name, r, loc, material, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=24, ring_count=12)
    return _fin(bpy.context.active_object, name, material, parent)


def ring(name, major, minor, loc, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=loc, rotation=rot,
                                     major_segments=128, minor_segments=8)
    return _fin(bpy.context.active_object, name, material)


def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if parent:
        o.parent = parent
    return o


def light(kind, loc, energy, color, size=1.0, rot=(0, 0, 0)):
    bpy.ops.object.light_add(type=kind, location=loc, rotation=rot)
    L = bpy.context.active_object
    L.data.energy = energy
    L.data.color = rgba(color)[:3]
    if kind == "AREA":
        L.data.size = size
    return L


# ----------------------------------------------------------------- build
W = {}   # handles
SCREENS = os.path.expanduser('~/movie/screens')


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    # world: vivid dusk sky
    wd = bpy.data.worlds.new("sky")
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.12
    mr.inputs["From Max"].default_value = 1.0
    cr = nt.nodes.new("ShaderNodeValToRGB")
    stops = [(0.0, "#ff9a3c"), (0.18, "#ff4f8b"), (0.42, "#9b3df0"), (0.7, "#3a1f9e"), (1.0, "#0e0a3a")]
    cr.color_ramp.elements[0].position = stops[0][0]
    cr.color_ramp.elements[0].color = rgba(stops[0][1])
    cr.color_ramp.elements[1].position = stops[-1][0]
    cr.color_ramp.elements[1].color = rgba(stops[-1][1])
    for p, c in stops[1:-1]:
        e = cr.color_ramp.elements.new(p)
        e.color = rgba(c)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.6
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0]) if False else nt.links.new(tc.outputs["Window"], sep.inputs[0]) if False else None
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], cr.inputs["Fac"])
    nt.links.new(cr.outputs["Color"], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    sc.world = wd
    sun = light("SUN", (0, 0, 50), 4.0, "#ff9a5c")
    sun.rotation_euler = (math.radians(84), 0, math.radians(110))

    ground_m = mat("ground", "#2b1d52", rough=0.9)
    gravel_m = mat("gravel", "#56456f", rough=0.95)
    teal = mat("teal", "#16b8b0", rough=0.5)
    orange = mat("orange", "#ff8a3d", rough=0.5)
    yellow = mat("yellow", "#ffd23f", rough=0.45)
    steel = mat("steel", "#5a7bd8", rough=0.35, metal=0.8)
    white = mat("white", "#f3f1ff", rough=0.4)
    dark = mat("dark", "#141024", rough=0.6)
    neon_c = glow("neon_cyan", "#28e1ff", 14)
    neon_m = glow("neon_mag", "#ff3fb4", 14)
    win_a = glow("win_amber", "#ffb347", 9)
    win_c = glow("win_cyan", "#5eead4", 9)
    red_l = glow("red_l", "#ff3b3b", 18)
    blu_l = glow("blu_l", "#3b6bff", 18)

    box("ground", (3000, 3000, 0.4), (0, 0, -0.2), ground_m)
    box("yard", (74, 64, 0.2), (0, 0, 0.05), gravel_m)
    box("road", (6, 160, 0.1), (46, -50, 0.04), dark)
    # facility
    box("control_building", (20, 10, 6), (-12, 8, 3), teal)
    box("switchgear", (24, 12, 8), (14, -10, 4), orange)
    box("trafo1", (6, 5, 6), (-5, -14, 3), yellow)
    box("trafo2", (6, 5, 6), (5, 14, 3), yellow)
    box("gantry_a", (0.8, 22, 12), (0, -4, 6), steel)
    box("gantry_b", (0.8, 22, 16), (0, 4, 8), steel)
    for i, (cx, cy, sx, sy, h) in enumerate([(-12, 8, 20, 10, 6), (14, -10, 24, 12, 8)]):
        for r in range(2):
            z = 1.8 + r * 2.2
            if z < h - 0.8:
                box(f"win{i}{r}a", (sx * 0.8, 0.12, 0.7), (cx, cy - sy / 2 - 0.05, z), win_a if i == 0 else win_c)
                box(f"win{i}{r}b", (sx * 0.8, 0.12, 0.7), (cx, cy + sy / 2 + 0.05, z), win_a if i == 0 else win_c)
    # neon fence
    for nme, s, l in [("fn", (60, .25, 2.4), (0, 25, 1.2)), ("fs", (60, .25, 2.4), (0, -25, 1.2)),
                      ("fe", (.25, 50, 2.4), (30, 0, 1.2)), ("fw", (.25, 50, 2.4), (-30, 0, 1.2))]:
        box(nme, s, l, neon_c)
    for k in range(-2, 3):
        box(f"post{k}", (0.5, 0.5, 3.0), (30, k * 10, 1.5), neon_m)
    # gnb mast
    box("mast", (0.8, 0.8, 25), (36, 0, 12.5), white)
    W["panel_tx"] = box("panel_tx", (2.4, 0.5, 3.2), (36.4, 0, 25), neon_m)
    W["panel_rx"] = box("panel_rx", (2.4, 0.5, 3.2), (36.4, 0, 21.2), neon_c)
    W["beacon"] = sphere("beacon", 0.5, (36, 0, 26.3), red_l)
    # security hut, ptz
    box("hut", (7, 5, 3.5), (92, -44, 1.75), orange)
    box("hut_roof", (7.6, 5.6, 0.4), (92, -44, 3.7), dark)
    box("ptz_pole", (0.3, 0.3, 8), tuple(PTZ_POS - Vector((0, 0, 4))), white)
    W["ptz"] = box("ptz_head", (1.1, 0.8, 0.7), tuple(PTZ_POS), dark)
    W["ptz_lens"] = box("ptz_lens", (0.3, 0.9, 0.3), (0, 0.55, 0), glow("lens", "#9dff6b", 20), parent=W["ptz"])
    # patrol car
    W["car"] = empty("car", tuple(CAR_START))
    box("car_body", (4.4, 1.9, 1.0), (0, 0, 0.8), white, parent=W["car"])
    box("car_cab", (2.2, 1.7, 0.8), (-0.3, 0, 1.6), dark, parent=W["car"])
    W["bar_r"] = box("bar_r", (0.4, 0.7, 0.25), (-0.3, 0.45, 2.1), red_l, parent=W["car"])
    W["bar_b"] = box("bar_b", (0.4, 0.7, 0.25), (-0.3, -0.45, 2.1), blu_l, parent=W["car"])
    for sx in (-1.4, 1.4):
        for sy in (-0.95, 0.95):
            cyl("wheel", 0.38, 0.3, (sx, sy, 0.38), dark, parent=W["car"], rot=(math.pi / 2, 0, 0))
    W["car_l"] = light("SPOT", (0, 0, 0), 4000, "#fff1c9")
    W["car_l"].data.spot_size = math.radians(60)
    W["car_l"].parent = W["car"]
    W["car_l"].location = (2.4, 0, 1.0)
    W["car_l"].rotation_euler = (0, math.radians(90), 0)
    # drone
    W["drone"] = empty("drone", tuple(P_START))
    W["drone"].scale = (DRONE_SCALE,) * 3
    box("d_body", (0.5, 0.5, 0.16), (0, 0, 0), dark, parent=W["drone"])
    W["d_led"] = sphere("d_led", 0.12, (0, 0, -0.14), glow("d_led", "#ff5a3c", 40), parent=W["drone"])
    W["rotors"] = []
    for i, (x, y) in enumerate([(.45, .45), (-.45, .45), (-.45, -.45), (.45, -.45)]):
        box("arm", (0.65 if i % 2 == 0 else 0.65, 0.07, 0.05), (x / 2, y / 2, 0.02), dark, parent=W["drone"]).rotation_euler = (0, 0, math.atan2(y, x))
        r = cyl("rotor", 0.26, 0.01, (x, y, 0.07), glow("rotor", "#ffd24a", 3.5, 0.55), parent=W["drone"])
        W["rotors"].append(r)
    W["d_halo"] = sphere("d_halo", 0.75, (0, 0, 0), glow("halo", "#ff5a3c", 1.0, 0.05), parent=W["drone"])
    # zone rings (warning / restricted / critical) and pulse rings
    W["zones"] = []
    for nm, r, c in [("warning", 250, "#ffb020"), ("restricted", 120, "#ff6a2b"), ("critical", 45, "#ff2d55")]:
        m = glow("zone_" + nm, c, 7, 0.55)
        o = ring("zone_" + nm, 1.0, 0.0045, (0, 0, 0.25), m)
        o.scale = (r, r, 1)
        W["zones"].append((o, m, r))
    W["pulses"] = []
    for i in range(5):
        m = glow(f"pulse{i}", "#28e1ff", 9, 0.0)
        o = ring(f"pulse{i}", 1.0, 0.004, (36, 0, 0.35), m)
        v = ring(f"pulse_v{i}", 1.0, 0.004, (36, 0, 24), m, rot=(0, math.pi / 2, 0))
        W["pulses"].append((o, v, m))
    W["beam"] = None
    # lights on site
    light("AREA", (0, 0, 22), 9000, "#ffd9a8", size=40)
    light("AREA", (60, -40, 14), 3000, "#9bd1ff", size=20)
    # --- control room (offset)
    ox, oy, oz = OFF_ROOM
    floor = mat("floor", "#2a1a4a", rough=0.3, metal=0.2)
    wall = mat("wall", "#3b2a6b", rough=0.7)
    box("r_floor", (10, 8, 0.2), (ox, oy, -0.1), floor)
    box("r_wall_back", (10, 0.3, 3.4), (ox, oy + 4, 1.7), wall)
    box("r_wall_l", (0.3, 8, 3.4), (ox - 5, oy, 1.7), wall)
    box("r_wall_r", (0.3, 8, 3.4), (ox + 5, oy, 1.7), wall)
    box("r_ceil", (10, 8, 0.2), (ox, oy, 3.5), dark)
    box("r_strip1", (9, 0.12, 0.12), (ox, oy + 3.8, 3.2), neon_m)
    box("r_strip2", (0.12, 7, 0.12), (ox - 4.8, oy, 3.2), neon_c)
    box("r_strip3", (0.12, 7, 0.12), (ox + 4.8, oy, 3.2), neon_c)
    box("desk", (6, 1.6, 0.1), (ox, oy + 1.8, 0.95), dark)
    box("desk_leg1", (0.15, 1.4, 0.95), (ox - 2.8, oy + 1.8, 0.47), dark)
    box("desk_leg2", (0.15, 1.4, 0.95), (ox + 2.8, oy + 1.8, 0.47), dark)
    W["mons"] = []
    for i, c in enumerate(["#28e1ff", "#ff3fb4", "#7dff6b", "#ffb020"]):
        sp = f"{SCREENS}/mon{i}.png"
        m = glow_img(f"mon{i}", sp, 1.1) if os.path.exists(sp) else glow(f"mon{i}", c, 1.6, 1.0)
        box(f"mon{i}", (1.3, 0.06, 0.85), (ox - 2.1 + i * 1.4, oy + 2.35, 1.75), m)
        box(f"monb{i}", (1.38, 0.05, 0.92), (ox - 2.1 + i * 1.4, oy + 2.4, 1.75), dark)
        W["mons"].append(m)
    box("big", (6.4, 0.08, 2.0), (ox, oy + 3.8, 2.1), glow_img("bigscr", f"{SCREENS}/big.png", 1.0) if os.path.exists(f"{SCREENS}/big.png") else glow("bigscr", "#6a5cff", 1.2))
    skin = mat("skin", "#f0c4a0", rough=0.6)
    shirt = mat("shirt", "#ff5e7e", rough=0.6)
    W["op"] = empty("operator", (ox, oy + 0.9, 0))
    cyl("op_body", 0.28, 0.75, (0, 0, 0.95), shirt, parent=W["op"])
    sphere("op_head", 0.2, (0, 0, 1.55), skin, parent=W["op"])
    box("chair", (0.7, 0.7, 0.1), (0, 0, 0.5), dark, parent=W["op"])
    W["op_arm"] = cyl("op_arm", 0.07, 0.6, (0.0, 0.3, 1.15), shirt, parent=W["op"], rot=(math.radians(70), 0, 0))
    W["btn_ok"] = box("btn_ok", (0.3, 0.22, 0.06), (ox - 0.4, oy + 1.5, 1.03), glow("btn_ok", "#4aff7a", 2.0))
    W["btn_no"] = box("btn_no", (0.3, 0.22, 0.06), (ox + 0.4, oy + 1.5, 1.03), glow("btn_no", "#ff3b4a", 2.0))
    light("AREA", (ox, oy, 3.2), 700, "#ffd9f0", size=4)
    # --- audit chain b-roll (offset)
    ax, ay, az = OFF_AUDIT
    box("a_floor", (60, 30, 0.2), (ax + 15, ay, -0.1), mat("afloor", "#1b1140", rough=0.2, metal=0.3))
    W["chain"] = []
    for i in range(10):
        m = glow(f"blk{i}", "#28e1ff" if i % 2 == 0 else "#7a5cff", 5, 1.0)
        b = box(f"blk{i}", (2.0, 2.0, 2.0), (ax + i * 4.0, ay, 1.2), m)
        if i:
            box(f"lnk{i}", (2.0, 0.18, 0.18), (ax + i * 4.0 - 3.0, ay, 1.2), neon_m)
        W["chain"].append((b, m))
    light("AREA", (ax + 18, ay - 6, 9), 3500, "#d9ccff", size=20)

    # illustrative ray paths: mast -> structures (specular bounces) -> back
    W["rays"] = []
    ray_m = glow("ray", "#7dff6b", 10, 1.0)
    ray_m2 = glow("ray2", "#ffd24a", 10, 1.0)
    hits = [(-12, 3.6, 3), (-12, 12.6, 3), (14, -15.7, 4), (14, -4.3, 4), (-5, -16.6, 3), (5, 16.6, 3), (0, -15, 6), (0, 15, 8),
            (30, -15, 1.2), (30, 14, 1.2), (-30, 0, 1.2), (0, 25, 1.2), (0, -25, 1.2), (20, 0, 0.3), (-20, 0, 0.3)]
    for i, h in enumerate(hits):
        a = GNB
        b = Vector(h)
        mid = (a + b) / 2
        L = (b - a).length
        c = cyl(f"ray{i}", 0.09, L, tuple(mid), ray_m if i % 2 == 0 else ray_m2, verts=8)
        c.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
        p = sphere(f"rayp{i}", 0.7, tuple(a), glow(f"rp{i}", "#ffffff", 30))
        W["rays"].append((c, p, a, b))
    # camera + render settings
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.sensor_width = 36
    W["cam"] = cam
    return W


def configure(res_x, res_y, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    sc.cycles.device = "GPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPTIX"
    sc.cycles.max_bounces = 4
    sc.cycles.sample_clamp_indirect = 8
    sc.render.resolution_x, sc.render.resolution_y = res_x, res_y
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 3
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    sc.view_settings.exposure = 0.2
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    gl = nt.nodes.new("CompositorNodeGlare")
    gl.glare_type = "FOG_GLOW"
    gl.quality = "MEDIUM"
    gl.threshold = 0.9
    gl.size = 7
    gl.mix = 0.0
    co = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
    nt.links.new(gl.outputs["Image"], co.inputs["Image"])


# ----------------------------------------------------------------- per-frame state
def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def car_state(sim_t):
    """Patrol car idles at the hut, then races to the east gate after approval (sim 13.5 s)."""
    s = max(0.0, min((sim_t - EVENTS["patrol"]) / 5.0, 1.0))
    p = CAR_START.lerp(GATE, s * s * (3 - 2 * s))
    yaw = math.atan2((GATE - CAR_START).y, (GATE - CAR_START).x) + math.pi
    return p, yaw, s


def set_state(sim_t, movie_t):
    d = drone_pos(sim_t)
    W["drone"].location = d
    spin = movie_t * 60
    for i, r in enumerate(W["rotors"]):
        r.rotation_euler = (0, 0, spin * (1 if i % 2 else -1))
    W["drone"].rotation_euler = (0.08 * math.sin(movie_t * 3), 0.12 * math.sin(movie_t * 2.1), math.atan2(VEL.y, VEL.x))
    # zones light up as the drone enters
    dist = math.hypot(d.x, d.y)
    for o, m, r in W["zones"]:
        on = dist <= r
        set_glow(m, alpha=0.95 if on else 0.4, strength=16 if on else 5)
    # sensing pulses: expanding rings from the mast, period 1.4 s of movie time
    for i, (g, v, m) in enumerate(W["pulses"]):
        ph = ((movie_t / 1.4) + i / len(W["pulses"])) % 1.0
        R = 3 + ph * 360
        g.scale = (R, R, 1)
        v.scale = (R * 0.6, R * 0.6, R * 0.6)
        set_glow(m, alpha=max(0.0, 0.8 * (1 - ph) ** 1.5))
    # camera cue: PTZ points at the drone once approved
    p = W["ptz"]
    tgt = d if sim_t >= EVENTS["cue"] else Vector((200, 0, 12))
    p.rotation_euler = Vector(tgt - p.location).to_track_quat("Y", "Z").to_euler()
    # patrol car
    pos, yaw, s = car_state(sim_t)
    W["car"].location = pos
    W["car"].rotation_euler = (0, 0, yaw)
    flash = int(movie_t * 6) % 2
    set_glow(W["bar_r"].data.materials[0], strength=18 if flash and sim_t >= EVENTS["patrol"] else 1)
    set_glow(W["bar_b"].data.materials[0], strength=18 if not flash and sim_t >= EVENTS["patrol"] else 1)
    W["car_l"].data.energy = 4000 if sim_t >= EVENTS["patrol"] else 0
    # beacon + monitors flicker
    set_glow(W["beacon"].data.materials[0], strength=4 + 16 * (int(movie_t * 2) % 2))
    for i, m in enumerate(W["mons"]):
        set_glow(m, strength=1.0 + 0.15 * math.sin(movie_t * (2 + i) + i))
    # operator reacts: arm moves to approve at cue/patrol moments
    near = min(abs(sim_t - EVENTS["cue"]), abs(sim_t - EVENTS["patrol"]), abs(sim_t - 25.5))
    set_glow(W["btn_ok"].data.materials[0], strength=2 + 14 * max(0, 1 - near / 1.2))
    for k, (b, m) in enumerate(W["chain"]):
        set_glow(m, strength=4 + 3 * math.sin(movie_t * 3 + k))


def rays_visible(on, movie_t=0.0):
    for i, (c, p, a, b) in enumerate(W["rays"]):
        c.hide_render = not on
        p.hide_render = not on
        if on:
            u = (movie_t * 0.45 + i / len(W["rays"])) % 1.0
            p.location = a.lerp(b, u)
