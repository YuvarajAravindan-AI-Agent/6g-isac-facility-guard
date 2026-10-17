"""Procedural power-substation scene for Sionna RT (Mitsuba XML of cuboids).

Coordinates: metres, z up, facility centred at the origin.
"""
import pathlib

MATS = {
    "concrete": ("concrete", 0.30),
    "metal": ("metal", 0.01),
    "ground": ("concrete", 0.50),
}

# (name, material, centre xyz, full size xyz)
BOXES = [
    ("terrain", "ground", (0, 0, -0.25), (600, 600, 0.5)),
    ("control_building", "concrete", (-12, 8, 3), (20, 10, 6)),
    ("switchgear_hall", "concrete", (14, -10, 4), (24, 12, 8)),
    ("transformer_1", "metal", (-5, -14, 3), (6, 5, 6)),
    ("transformer_2", "metal", (5, 14, 3), (6, 5, 6)),
    ("gantry_a", "metal", (0, -4, 6), (0.6, 22, 12)),
    ("gantry_b", "metal", (0, 4, 8), (0.6, 22, 16)),
    # perimeter fence, 60 x 50 m, 2.4 m high, thin metal plates
    ("fence_n", "metal", (0, 25, 1.2), (60, 0.05, 2.4)),
    ("fence_s", "metal", (0, -25, 1.2), (60, 0.05, 2.4)),
    ("fence_e", "metal", (30, 0, 1.2), (0.05, 50, 2.4)),
    ("fence_w", "metal", (-30, 0, 1.2), (0.05, 50, 2.4)),
    # 6G base-station mast just outside the east fence
    ("gnb_mast", "metal", (36, 0, 12.5), (0.5, 0.5, 25)),
]

GNB_TX = (36.0, 0.0, 25.0)   # transmit panel on top of the mast
GNB_RX = (36.0, 0.0, 23.0)   # receive panel 2 m below (quasi-monostatic ISAC)


def write_scene(path="scene/substation.xml"):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = ['<scene version="2.1.0">']
    for mid, (typ, thick) in MATS.items():
        out.append(f'  <bsdf type="itu-radio-material" id="mat-{mid}">'
                   f'<string name="type" value="{typ}"/>'
                   f'<float name="thickness" value="{thick}"/></bsdf>')
    for name, mat, c, s in BOXES:
        out.append(
            f'  <shape type="cube" id="{name}"><transform name="to_world">'
            f'<scale x="{s[0]/2}" y="{s[1]/2}" z="{s[2]/2}"/>'
            f'<translate x="{c[0]}" y="{c[1]}" z="{c[2]}"/></transform>'
            f'<ref id="mat-{mat}" name="bsdf"/></shape>')
    out.append('</scene>')
    p.write_text("\n".join(out))
    return str(p)


if __name__ == "__main__":
    print(write_scene())
