"""Dossier 25-10-4471 — l'appartement de Julien Caron, modélisé et rendu dans Blender.

Construit la salle en 3D aux coordonnées exactes de `godot/scenes/game_room.tscn`
(1 px Godot = 1 cm), puis fait des rendus Cycles vue de dessus, orthographiques :

  background.png          la pièce sans les preuves ni les personnages (1280 × 896, soit 2 px/cm)
  items/<id>.png          chaque pièce à conviction seule, fond transparent, avec son ombre
  characters/<nom>.png    joueur et Lavoie, vus de dessus, regard vers le bas de l'écran

Les rendus sont au double de la résolution du jeu ; Godot les affiche avec `scale = 0.5`.

Lancement, au choix :
  blender -b -P blender/build_room.py -- --out godot/art/room
  python blender/build_room.py --out godot/art/room          (module `bpy` de PyPI)

Options : --samples N (défaut 160), --only background|items|characters,
--save-blend chemin.blend pour retoucher la scène à la main (ou via le MCP Blender + BlenderKit :
remplacer un objet procédural par un asset en gardant son nom, sa position et sa collection).

Tout est procédural : aucun asset externe, les textures sont générées avec numpy.
"""

import argparse
import math
import os
import random
import sys

import bpy  # en premier : le module bpy de PyPI rend bmesh importable
import bmesh
import numpy as np
from mathutils import Euler, Vector

PX = 0.01  # 1 px Godot = 1 cm
ROOM_W, ROOM_H = 640, 448
RES = 2  # pixels de rendu par px Godot
WALL = 16  # épaisseur des murs, en px
CUT = 1.10  # hauteur de coupe des murs vus par la caméra (maquette en coupe)
CEILING = 2.60

# Positions reprises de game_room.tscn
TABLE = (320, 200, 192, 96)
DM_CHAIR = (456, 200)
SHELF = (496, 200, 20, 96)
COUNTER = (96, 96, 64, 128)
BLOOD = (470, 250)
DOOR_Y = 384
WINDOW_X = (240, 400)

# Régions rendues pour chaque preuve : (id, centre x, centre y, largeur, hauteur) en px Godot.
# Le centre peut différer de la position de l'Interactable ; le .tscn compense avec Sprite.position.
ITEM_REGIONS = [
    ("phone_playlist", 260, 236, 32, 32),
    ("treasury_ledger", 300, 164, 40, 40),
    ("dm_notebook", 400, 164, 40, 40),
    ("dm_screen", 404, 228, 48, 64),
    ("character_sheet", 360, 236, 40, 36),
    ("pizza_box", 96, 70, 48, 60),
    ("satchel", 236, 304, 72, 72),
    ("bronze_dragon", 496, 176, 48, 48),
]

CHAR_SIZE = 64  # px Godot, carré centré sur le personnage

rng = random.Random(25104471)


def P(x, y, z=0.0):
    """Coordonnées Godot (px, y vers le bas) → Blender (m, y vers le haut)."""
    return Vector((x * PX, -y * PX, z))


# --------------------------------------------------------------------------------------------
# Textures numpy (origine en haut à gauche, RGBA en sRGB)
# --------------------------------------------------------------------------------------------

def value_noise(h, w, cells, seed):
    r = np.random.default_rng(seed)
    gh, gw = max(2, int(cells * h / max(h, w)) + 2), max(2, int(cells * w / max(h, w)) + 2)
    grid = r.random((gh, gw))
    ys = np.linspace(0, gh - 1.001, h)
    xs = np.linspace(0, gw - 1.001, w)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = grid[y0][:, x0]
    b = grid[y0][:, x0 + 1]
    c = grid[y0 + 1][:, x0]
    d = grid[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(h, w, cells, seed, octaves=4):
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        out += amp * value_noise(h, w, cells * (2 ** o), seed + o * 101)
        total += amp
        amp *= 0.5
    return out / total


def canvas(h, w, color):
    img = np.zeros((h, w, 4))
    img[:, :] = (*color[:3], 1.0) if len(color) == 3 else color
    return img


def rect(img, x0, y0, x1, y1, color, alpha=1.0):
    x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
    sub = img[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    sub[..., :3] = sub[..., :3] * (1 - alpha) + np.array(color[:3]) * alpha
    sub[..., 3] = np.maximum(sub[..., 3], alpha)


def frame(img, x0, y0, x1, y1, t, color):
    rect(img, x0, y0, x1, y0 + t, color)
    rect(img, x0, y1 - t, x1, y1, color)
    rect(img, x0, y0, x0 + t, y1, color)
    rect(img, x1 - t, y0, x1, y1, color)


def line(img, p0, p1, width, color, alpha=1.0):
    h, w = img.shape[:2]
    (ax, ay), (bx, by) = p0, p1
    pad = width + 2
    x0, x1 = int(max(0, min(ax, bx) - pad)), int(min(w, max(ax, bx) + pad))
    y0, y1 = int(max(0, min(ay, by) - pad)), int(min(h, max(ay, by) + pad))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy or 1e-9
    t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / L, 0, 1)
    dist = np.hypot(xx - (ax + t * dx), yy - (ay + t * dy))
    cov = np.clip(width / 2 + 0.5 - dist, 0, 1)[..., None] * alpha
    sub = img[y0:y1, x0:x1]
    sub[..., :3] = sub[..., :3] * (1 - cov) + np.array(color[:3]) * cov
    sub[..., 3:] = np.maximum(sub[..., 3:], cov)


def disk(img, cx, cy, r, color, alpha=1.0):
    h, w = img.shape[:2]
    x0, x1 = int(max(0, cx - r - 2)), int(min(w, cx + r + 2))
    y0, y1 = int(max(0, cy - r - 2)), int(min(h, cy + r + 2))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
    cov = np.clip(r + 0.5 - np.hypot(xx - cx, yy - cy), 0, 1)[..., None] * alpha
    sub = img[y0:y1, x0:x1]
    sub[..., :3] = sub[..., :3] * (1 - cov) + np.array(color[:3]) * cov
    sub[..., 3:] = np.maximum(sub[..., 3:], cov)


def scribble(img, x0, y, x1, height, color, seed, width=1.2):
    """Écriture manuscrite illisible : une sinusoïde bruitée."""
    r = np.random.default_rng(seed)
    pts = []
    x = x0
    while x < x1:
        pts.append((x, y + math.sin(x * 0.9 + r.random()) * height * 0.5 + r.normal(0, height * 0.15)))
        x += 1.6 + r.random() * 1.4
        if r.random() < 0.08:  # espace entre les mots
            if len(pts) > 1:
                for a, b in zip(pts, pts[1:]):
                    line(img, a, b, width, color, 0.85)
            pts = []
            x += 3 + r.random() * 3
    for a, b in zip(pts, pts[1:]):
        line(img, a, b, width, color, 0.85)


def grain(img, amount, cells, seed):
    n = fbm(img.shape[0], img.shape[1], cells, seed) - 0.5
    img[..., :3] = np.clip(img[..., :3] * (1 + n[..., None] * amount), 0, 1)
    return img


def to_image(name, arr, non_color=False):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(np.flipud(np.clip(arr, 0, 1)).astype(np.float32).ravel())
    img.pack()
    return img


# --------------------------------------------------------------------------------------------
# Matériaux
# --------------------------------------------------------------------------------------------

def sock(sockets, identifier):
    for s in sockets:
        if s.identifier == identifier:
            return s
    raise KeyError(identifier)


class Mat:
    """Petit constructeur d'arbre de nœuds autour d'un Principled BSDF."""

    def __init__(self, name, color=(0.5, 0.5, 0.5), rough=0.5, metal=0.0, **extra):
        self.m = bpy.data.materials.new(name)
        try:
            self.m.use_nodes = True
        except AttributeError:
            pass
        self.nt = self.m.node_tree
        self.bsdf = next(n for n in self.nt.nodes if n.type == "BSDF_PRINCIPLED")
        self.out = next(n for n in self.nt.nodes if n.type == "OUTPUT_MATERIAL")
        self.set("Base Color", (*color[:3], 1.0))
        self.set("Roughness", rough)
        self.set("Metallic", metal)
        for k, v in extra.items():
            self.set(k.replace("_", " "), v)

    def set(self, name, value):
        if name in self.bsdf.inputs:
            self.bsdf.inputs[name].default_value = value

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            if k in n.inputs:
                n.inputs[k].default_value = v
            else:
                setattr(n, k, v)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def coords(self, kind="Object", scale=(1, 1, 1), rot=(0, 0, 0), loc=(0, 0, 0)):
        tc = self.node("ShaderNodeTexCoord")
        mp = self.node("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = scale
        mp.inputs["Rotation"].default_value = rot
        mp.inputs["Location"].default_value = loc
        self.link(tc.outputs[kind], mp.inputs["Vector"])
        return mp.outputs["Vector"]

    def mix(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="RGBA")
        for target, src in ((sock(n.inputs, "Factor_Float"), fac), (sock(n.inputs, "A_Color"), a),
                            (sock(n.inputs, "B_Color"), b)):
            if isinstance(src, (tuple, list, float, int)):
                target.default_value = src if not isinstance(src, (tuple, list)) else (*src[:3], 1.0)
            else:
                self.link(src, target)
        return sock(n.outputs, "Result_Color")

    def ramp(self, src, stops):
        r = self.node("ShaderNodeValToRGB")
        els = r.color_ramp.elements
        while len(els) > 1:
            els.remove(els[-1])
        els[0].position, els[0].color = stops[0][0], (*stops[0][1][:3], 1.0)
        for pos, col in stops[1:]:
            e = els.new(pos)
            e.color = (*col[:3], 1.0)
        self.link(src, r.inputs["Fac"])
        return r.outputs["Color"]

    def bump(self, height, strength=0.2, distance=0.002):
        b = self.node("ShaderNodeBump", Strength=strength, Distance=distance)
        self.link(height, b.inputs["Height"])
        self.link(b.outputs["Normal"], self.bsdf.inputs["Normal"])

    def image(self, img, alpha=False, interpolation="Cubic"):
        t = self.node("ShaderNodeTexImage")
        t.image = img
        t.interpolation = interpolation
        self.link(t.outputs["Color"], self.bsdf.inputs["Base Color"])
        if alpha:
            self.link(t.outputs["Alpha"], self.bsdf.inputs["Alpha"])
        return t


def wood_mat(name, light, dark, scale=1.0, rough=0.45, plank=None, seed=0):
    """Bois : veinage étiré le long de X, teinte variable par planche si `plank` = (larg, long)."""
    m = Mat(name, rough=rough)
    v = m.coords("Object", scale=(0.6 * scale, 18 * scale, 18 * scale), loc=(seed * 3.1, seed * 1.7, 0))
    wave = m.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y")
    wave.inputs["Scale"].default_value = 2.0
    wave.inputs["Distortion"].default_value = 1.2
    wave.inputs["Detail"].default_value = 2.0
    m.link(v, wave.inputs["Vector"])
    noise = m.node("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 4.0
    m.link(v, noise.inputs["Vector"])
    fac = m.mix(0.5, wave.outputs["Color"], noise.outputs["Color"])
    col = m.ramp(fac, [(0.15, dark), (0.65, light), (1.0, dark)])
    if plank:
        vb = m.coords("Object", scale=(1, 1, 1))
        brick = m.node("ShaderNodeTexBrick", offset=0.37, offset_frequency=2)
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Mortar Size"].default_value = 0.0015
        brick.inputs["Mortar Smooth"].default_value = 0.3
        brick.inputs["Brick Width"].default_value = plank[1]
        brick.inputs["Row Height"].default_value = plank[0]
        brick.inputs["Bias"].default_value = 0.0
        brick.inputs["Color1"].default_value = (0.78, 0.78, 0.78, 1)
        brick.inputs["Color2"].default_value = (1.08, 1.05, 1.0, 1)
        brick.inputs["Mortar"].default_value = (0.05, 0.04, 0.03, 1)
        m.link(vb, brick.inputs["Vector"])
        mul = m.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
        sock(mul.inputs, "Factor_Float").default_value = 1.0
        m.link(col, sock(mul.inputs, "A_Color"))
        m.link(brick.outputs["Color"], sock(mul.inputs, "B_Color"))
        col = sock(mul.outputs, "Result_Color")
        inv = m.node("ShaderNodeMath", operation="SUBTRACT")
        inv.inputs[0].default_value = 1.0
        m.link(brick.outputs["Fac"], inv.inputs[1])
        m.bump(inv.outputs[0], 0.35, 0.002)
        # usure : zones plus mates et plus pâles
        wear = m.node("ShaderNodeTexNoise")
        wear.inputs["Scale"].default_value = 1.2
        wear.inputs["Detail"].default_value = 4.0
        m.link(m.coords("Object"), wear.inputs["Vector"])
        r = m.node("ShaderNodeMapRange")
        r.inputs["From Min"].default_value = 0.35
        r.inputs["From Max"].default_value = 0.7
        r.inputs["To Min"].default_value = rough - 0.15
        r.inputs["To Max"].default_value = rough + 0.2
        m.link(wear.outputs["Fac"], r.inputs["Value"])
        m.link(r.outputs["Result"], m.bsdf.inputs["Roughness"])
    m.link(col, m.bsdf.inputs["Base Color"])
    return m.m


def noisy_mat(name, a, b, scale=40.0, rough=0.6, metal=0.0, bump=0.1, **extra):
    m = Mat(name, rough=rough, metal=metal, **extra)
    n = m.node("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = 6.0
    m.link(m.coords("Object"), n.inputs["Vector"])
    m.link(m.mix(n.outputs["Fac"], a, b), m.bsdf.inputs["Base Color"])
    if bump:
        m.bump(n.outputs["Fac"], bump, 0.001)
    return m.m


def image_mat(name, img, rough=0.6, alpha=False, bump=0.0, sheen=0.0, metal=0.0):
    m = Mat(name, rough=rough, metal=metal)
    t = m.image(img, alpha=alpha)
    if sheen:
        m.set("Sheen Weight", sheen)
    if bump:
        bw = m.node("ShaderNodeRGBToBW")
        m.link(t.outputs["Color"], bw.inputs["Color"])
        m.bump(bw.outputs["Val"], bump, 0.002)
    return m.m


# --------------------------------------------------------------------------------------------
# Géométrie
# --------------------------------------------------------------------------------------------

COLLS = {}


def coll(name, parent=None):
    if name not in COLLS:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
        COLLS[name] = c
    return COLLS[name]


def finish(name, bm, mat, c, loc, rot=(0, 0, 0), smooth=False, bevel=0.0, subsurf=0):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    if mat:
        me.materials.append(mat)
    if bevel:
        mod = ob.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    if subsurf:
        mod = ob.modifiers.new("Subsurf", "SUBSURF")
        mod.levels = mod.render_levels = subsurf
    return ob


def box(name, c, size, loc, mat, rot=(0, 0, 0), bevel=0.002, origin_bottom=True):
    """Boîte de `size` (m) ; `loc` = centre du dessous si origin_bottom."""
    bm = bmesh.new()
    bm.loops.layers.uv.new()
    bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if origin_bottom:
        bmesh.ops.translate(bm, vec=(0, 0, size[2] / 2), verts=bm.verts)
    return finish(name, bm, mat, c, loc, rot, bevel=bevel)


def box_px(name, c, x0, y0, x1, y1, z0, z1, mat, bevel=0.002):
    w, d = (x1 - x0) * PX, (y1 - y0) * PX
    return box(name, c, (w, d, z1 - z0), P((x0 + x1) / 2, (y0 + y1) / 2, z0), mat, bevel=bevel)


def quad(name, c, w, h, loc, mat, rot=(0, 0, 0), bend=0.0):
    """Plan texturé, UV 0..1, normale +Z. `bend` courbe légèrement le papier."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new()
    n = 8 if bend else 1
    verts = [[bm.verts.new((-w / 2 + w * i / n, -h / 2 + h * j / n,
                            bend * math.sin(math.pi * i / n) * (0.5 + 0.5 * math.sin(j)))) for j in range(n + 1)]
             for i in range(n + 1)]
    for i in range(n):
        for j in range(n):
            f = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
            for loop, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uv].uv = (a / n, b / n)
    return finish(name, bm, mat, c, loc, rot, smooth=True)


def cylinder(name, c, r, h, loc, mat, segs=24, rot=(0, 0, 0), r2=None, bevel=0.0, open_top=False):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r if r2 is None else r2, depth=h)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    if open_top:  # récipient : on retire le couvercle et on donne une épaisseur à la paroi
        top = max(bm.faces, key=lambda f: f.calc_center_median().z)
        bmesh.ops.delete(bm, geom=[top], context="FACES_ONLY")
    ob = finish(name, bm, mat, c, loc, rot, smooth=True, bevel=bevel)
    if open_top:
        sol = ob.modifiers.new("Paroi", "SOLIDIFY")
        sol.thickness = 0.004
    return ob


def sphere(name, c, r, loc, mat, scale=(1, 1, 1), rot=(0, 0, 0), segs=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return finish(name, bm, mat, c, loc, rot, smooth=True)


def ico(name, c, r, loc, mat, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    return finish(name, bm, mat, c, loc, rot, bevel=r * 0.08)


def poly_prism(name, c, pts, h, loc, mat, rot=(0, 0, 0), bevel=0.0, smooth=False):
    """Extrusion verticale d'un polygone 2D (m, repère local)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]
    f = bm.faces.new(vs)
    if f.normal.z < 0:
        f.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, h), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, mat, c, loc, rot, bevel=bevel, smooth=smooth)


def text(name, c, body, size, loc, mat, rot=(0, 0, 0), extrude=0.0002):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = extrude
    ob = bpy.data.objects.new(name, cu)
    c.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    cu.materials.append(mat)
    return ob


# --------------------------------------------------------------------------------------------
# Construction de la pièce
# --------------------------------------------------------------------------------------------

def build_materials():
    M = {}
    M["floor"] = wood_mat("Plancher chêne", (0.30, 0.18, 0.09), (0.13, 0.07, 0.035), scale=1.0,
                          rough=0.42, plank=(0.13, 1.15), seed=1)
    M["walnut"] = wood_mat("Noyer", (0.20, 0.11, 0.06), (0.07, 0.035, 0.02), scale=1.6, rough=0.5, seed=2)
    M["oak"] = wood_mat("Chêne clair", (0.55, 0.38, 0.22), (0.30, 0.19, 0.10), scale=1.4, rough=0.5, seed=3)
    M["pine"] = wood_mat("Pin teint", (0.38, 0.24, 0.13), (0.17, 0.10, 0.05), scale=1.4, rough=0.55, seed=4)
    M["wall_top"] = noisy_mat("Coupe des murs", (0.08, 0.08, 0.085), (0.10, 0.10, 0.105), scale=30, rough=0.9)
    M["plaster"] = noisy_mat("Plâtre peint", (0.55, 0.56, 0.52), (0.60, 0.61, 0.57), scale=12, rough=0.85)
    M["trim"] = Mat("Moulure blanche", (0.58, 0.57, 0.53), rough=0.45).m
    M["glass"] = Mat("Verre", (0.8, 0.9, 1.0), rough=0.02, Transmission_Weight=1.0, IOR=1.5).m
    M["steel"] = noisy_mat("Inox brossé", (0.62, 0.62, 0.63), (0.7, 0.7, 0.71), scale=200, rough=0.28,
                           metal=1.0, bump=0.02)
    M["iron_paint"] = Mat("Fonte peinte", (0.7, 0.69, 0.64), rough=0.45).m
    M["counter_top"] = noisy_mat("Comptoir quartz", (0.05, 0.05, 0.055), (0.11, 0.11, 0.115), scale=90, rough=0.25,
                                 bump=0.01)
    M["cabinet"] = Mat("Armoires", (0.62, 0.63, 0.60), rough=0.4).m
    M["fabric_dark"] = noisy_mat("Tissu gris", (0.07, 0.075, 0.08), (0.11, 0.115, 0.12), scale=300, rough=1.0,
                                 bump=0.2, Sheen_Weight=0.5)
    M["leather"] = noisy_mat("Cuir brun", (0.20, 0.10, 0.05), (0.32, 0.18, 0.09), scale=25, rough=0.5, bump=0.15)
    M["leather_dark"] = noisy_mat("Cuir foncé", (0.10, 0.05, 0.03), (0.15, 0.08, 0.04), scale=25, rough=0.45,
                                  bump=0.1)
    M["brass"] = Mat("Laiton", (0.78, 0.58, 0.28), rough=0.25, metal=1.0).m
    M["bronze"] = noisy_mat("Bronze patiné", (0.42, 0.25, 0.10), (0.62, 0.42, 0.18), scale=35, rough=0.28,
                            metal=1.0, bump=0.25)
    M["black_plastic"] = Mat("Plastique noir", (0.02, 0.02, 0.022), rough=0.3).m
    M["paper"] = Mat("Papier", (0.86, 0.85, 0.80), rough=0.85).m
    M["cardboard"] = noisy_mat("Carton", (0.52, 0.38, 0.22), (0.60, 0.45, 0.28), scale=60, rough=0.9, bump=0.05)
    M["ceramic_white"] = Mat("Céramique", (0.85, 0.84, 0.80), rough=0.12).m
    M["ceramic_blue"] = Mat("Céramique bleue", (0.08, 0.16, 0.30), rough=0.15).m
    M["marker_yellow"] = Mat("Plastique jaune", (0.85, 0.62, 0.02), rough=0.35).m
    M["ink_black"] = Mat("Encre", (0.01, 0.01, 0.01), rough=0.5).m
    M["rubber"] = Mat("Caoutchouc", (0.03, 0.03, 0.03), rough=0.8).m
    M["wax"] = Mat("Cire", (0.82, 0.78, 0.68), rough=0.4, Subsurface_Weight=0.4).m
    return M


def rug_texture():
    h, w = 420, 660  # 2 px/cm, 330 × 210 cm
    img = canvas(h, w, (0.34, 0.06, 0.05))
    navy, cream, gold, dark = (0.07, 0.09, 0.16), (0.78, 0.70, 0.55), (0.66, 0.48, 0.18), (0.18, 0.03, 0.03)
    for (inset, t, col) in ((10, 26, navy), (14, 3, cream), (32, 3, cream), (44, 8, dark)):
        frame(img, inset, inset, w - inset, h - inset, t, col)
    # motif de bordure : losanges
    for x in range(30, w - 30, 22):
        for y in (23, h - 23):
            disk(img, x, y, 5, gold)
            disk(img, x, y, 2.5, dark)
    for y in range(30, h - 30, 22):
        for x in (23, w - 23):
            disk(img, x, y, 5, gold)
            disk(img, x, y, 2.5, dark)
    # médaillon central
    cx, cy = w / 2, h / 2
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    d = np.abs(xx - cx) / 150 + np.abs(yy - cy) / 95
    for lim, col in ((1.0, navy), (0.88, cream), (0.82, (0.42, 0.10, 0.07)), (0.5, gold), (0.42, navy), (0.2, cream)):
        m = d < lim
        img[m, :3] = col
    # treillis de losanges dans le champ, peu contrasté
    lattice = (np.abs(((xx - cx) / 30 + (yy - cy) / 30) % 2 - 1) < 0.08) | (np.abs(((xx - cx) / 30 - (yy - cy) / 30) % 2 - 1) < 0.08)
    field = (xx > 56) & (xx < w - 56) & (yy > 56) & (yy < h - 56) & (d >= 1.0)
    img[lattice & field, :3] = (0.24, 0.05, 0.04)
    for gx in range(86, w - 56, 42):
        for gy in range(86, h - 56, 42):
            if abs(gx - cx) / 150 + abs(gy - cy) / 95 > 1.15:
                disk(img, gx, gy, 3, (0.55, 0.40, 0.18), 0.8)
    # usure, laine, décoloration au soleil côté fenêtre
    grain(img, 0.45, 220, 7)
    grain(img, 0.3, 60, 6)
    grain(img, 0.25, 12, 8)
    fade = np.linspace(1.12, 0.96, h)[:, None, None]
    img[..., :3] = np.clip(img[..., :3] * fade, 0, 1)
    return img


def battlemat_texture():
    h, w = 500, 800  # 4 px/cm, 80 × 50 cm
    img = canvas(h, w, (0.70, 0.67, 0.58))
    step = 2.54 * 4
    for x in np.arange(step / 2, w, step):
        line(img, (x, 0), (x, h), 1.0, (0.55, 0.62, 0.66), 0.7)
    for y in np.arange(step / 2, h, step):
        line(img, (0, y), (w, y), 1.0, (0.55, 0.62, 0.66), 0.7)
    # donjon tracé au feutre effaçable
    wall = (0.12, 0.10, 0.10)
    path = [(120, 80), (420, 80), (420, 180), (560, 180), (560, 80), (700, 80), (700, 360), (520, 360),
            (520, 430), (300, 430), (300, 300), (120, 300), (120, 80)]
    for a, b in zip(path, path[1:]):
        line(img, a, b, 5, wall, 0.9)
    rect(img, 300, 300, 520, 430, (0.35, 0.45, 0.70), 0.18)  # bassin
    for a, b in (((200, 180), (260, 240)), ((610, 230), (650, 300))):
        line(img, a, b, 3, (0.55, 0.12, 0.08), 0.8)
    line(img, (420, 130), (560, 130), 3, (0.15, 0.40, 0.15), 0.7)
    grain(img, 0.12, 40, 9)
    # traces d'effacement
    for _ in range(14):
        x, y = rng.uniform(80, 720), rng.uniform(60, 440)
        disk(img, x, y, rng.uniform(10, 30), (0.70, 0.66, 0.60), 0.15)
    return img


def sheet_texture():
    h, w = 558, 432  # 2 px/mm, lettre 21,6 × 27,9 cm
    img = canvas(h, w, (0.93, 0.92, 0.88))
    ink, pencil = (0.15, 0.15, 0.17), (0.35, 0.35, 0.38)
    rect(img, 20, 18, w - 20, 70, (0.18, 0.16, 0.16))
    rect(img, 30, 26, 200, 62, (0.93, 0.92, 0.88))
    scribble(img, 40, 44, 180, 10, (0.10, 0.12, 0.35), 21, 2.0)  # « Ser Aldric »
    for i in range(6):  # caractéristiques
        y = 90 + i * 62
        frame(img, 22, y, 92, y + 54, 2, ink)
        disk(img, 57, y + 46, 11, (0.93, 0.92, 0.88))
        frame(img, 46, y + 38, 68, y + 54, 1, ink)
        scribble(img, 40, y + 22, 74, 14, pencil, 30 + i, 2.2)
    for c in (110, 270):
        for i in range(14):
            y = 92 + i * 22
            line(img, (c, y + 16), (c + 140, y + 16), 1, (0.55, 0.55, 0.55))
            if rng.random() < 0.8:
                scribble(img, c + 4, y + 9, c + rng.uniform(60, 135), 8, pencil, 50 + i + c, 1.3)
    frame(img, 108, 418, w - 20, h - 20, 2, ink)
    for i in range(5):
        scribble(img, 118, 438 + i * 20, w - 40 - rng.uniform(0, 120), 9, (0.10, 0.12, 0.35), 90 + i, 1.4)
    # rond de café et pliure
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    ring = np.abs(np.hypot(xx - 340, yy - 140) - 40) < 2.5
    img[ring, :3] = img[ring, :3] * np.array((0.82, 0.72, 0.58))
    line(img, (0, h * 0.5), (w, h * 0.5), 1.5, (0.80, 0.79, 0.75), 0.6)
    return grain(img, 0.08, 30, 11)


def notebook_texture():
    h, w = 420, 300
    img = canvas(h, w, (0.55, 0.42, 0.27))  # couverture kraft
    grain(img, 0.25, 50, 12)
    rect(img, 50, 70, 250, 120, (0.88, 0.86, 0.80))
    scribble(img, 62, 95, 225, 14, (0.08, 0.08, 0.10), 13, 2.5)
    for y in range(12, h, 18):  # spirale
        disk(img, 12, y, 5, (0.25, 0.25, 0.27))
        disk(img, 12, y, 2.5, (0.75, 0.75, 0.76))
    # coins usés
    for (cx, cy) in ((w, 0), (w, h)):
        disk(img, cx, cy, 14, (0.70, 0.60, 0.45), 0.6)
    return img


def ledger_texture():
    h, w = 560, 440
    img = canvas(h, w, (0.09, 0.20, 0.13))  # toile verte
    grain(img, 0.35, 120, 14)
    rect(img, 0, 0, 46, h, (0.20, 0.10, 0.06))  # dos en cuir
    rect(img, w - 40, 0, w, 40, (0.20, 0.10, 0.06))
    rect(img, w - 40, h - 40, w, h, (0.20, 0.10, 0.06))
    rect(img, 140, 90, 380, 170, (0.78, 0.70, 0.50))
    frame(img, 146, 96, 374, 164, 3, (0.45, 0.30, 0.10))
    scribble(img, 165, 130, 350, 18, (0.10, 0.08, 0.08), 15, 3.0)
    return img


def phone_texture():
    h, w = 320, 150  # écran 7 × 15 cm
    img = canvas(h, w, (0.03, 0.03, 0.04))
    rect(img, 12, 40, w - 12, 40 + (w - 24), (0.55, 0.18, 0.20))  # pochette d'album
    disk(img, w / 2, 40 + (w - 24) / 2, 40, (0.85, 0.55, 0.20))
    disk(img, w / 2, 40 + (w - 24) / 2, 22, (0.20, 0.08, 0.10))
    rect(img, 12, 200, w - 12, 210, (0.80, 0.80, 0.82))
    rect(img, 12, 180, 110, 186, (0.45, 0.45, 0.48))
    rect(img, 12, 230, w - 12, 232, (0.30, 0.30, 0.32))
    rect(img, 12, 230, 52, 232, (0.90, 0.90, 0.92))
    disk(img, 52, 231, 4, (0.95, 0.95, 0.96))
    disk(img, w / 2, 272, 16, (0.92, 0.92, 0.94))  # bouton lecture (en pause)
    for dx in (-36, 36):
        disk(img, w / 2 + dx, 272, 7, (0.6, 0.6, 0.62))
    return img


def screen_texture(seed):
    h, w = 300, 220
    r = np.random.default_rng(seed)
    img = canvas(h, w, (0.20, 0.05, 0.05))
    n = fbm(h, w, 6, seed)
    sky = np.stack([0.15 + n * 0.5, 0.06 + n * 0.15, 0.05 + n * 0.08], -1)
    img[..., :3] = sky
    for _ in range(5):  # silhouettes de montagnes et d'un dragon
        cx, cy = r.uniform(0, w), r.uniform(h * 0.4, h)
        disk(img, cx, cy, r.uniform(30, 70), (0.05, 0.03, 0.04), 0.85)
    disk(img, w * 0.6, h * 0.3, 24, (0.95, 0.65, 0.25), 0.8)
    frame(img, 0, 0, w, h, 6, (0.55, 0.40, 0.15))
    return grain(img, 0.2, 40, seed)


def blood_texture():
    h, w = 160, 200
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    n = fbm(h, w, 7, 17)
    d = np.hypot((xx - 95) / 62, (yy - 78) / 48) + (n - 0.5) * 0.9
    a = np.clip((1.0 - d) * 6, 0, 1)
    r = np.random.default_rng(4)
    for _ in range(18):  # gouttes satellites
        ang, dist = r.uniform(0, 2 * math.pi), r.uniform(0.9, 1.6)
        cx, cy = 95 + math.cos(ang) * 62 * dist, 78 + math.sin(ang) * 48 * dist
        rr = r.uniform(1.5, 5)
        a = np.maximum(a, np.clip(rr + 0.5 - np.hypot(xx - cx, yy - cy), 0, 1))
    edge = np.clip(1 - np.abs(d - 0.88) * 8, 0, 1)
    col = np.stack([0.30 - edge * 0.12 + n * 0.08, 0.025 + n * 0.01, 0.02 + n * 0.01], -1)
    img = np.concatenate([col, a[..., None]], -1)
    return img


def build_room(M):
    c = coll("Room")
    upper = coll("RoomUpper")  # éclairage seulement : invisible pour la caméra

    # Plancher (déborde sous les murs) et plafond invisible
    box("Plancher", c, (6.6, 4.7, 0.02), P(320, 224, -0.02), M["floor"], bevel=0)
    box("Plafond", upper, (6.6, 4.7, 0.05), P(320, 224, CEILING), M["plaster"], bevel=0)

    # Murs : chaque segment est coupé en deux à CUT (bas visible, haut pour la lumière)
    def wall(name, x0, y0, x1, y1, z0=0.0, z1=CEILING):
        if z0 < CUT:
            box_px(name, c, x0, y0, x1, y1, z0, min(z1, CUT) - 0.001, M["plaster"], bevel=0)
            box_px(name + "_coupe", c, x0, y0, x1, y1, min(z1, CUT) - 0.001, min(z1, CUT), M["wall_top"], bevel=0)
        if z1 > CUT:
            box_px(name + "_haut", upper, x0, y0, x1, y1, max(z0, CUT), z1, M["plaster"], bevel=0)

    wall("MurGauche_a", -40, -40, WALL, DOOR_Y - 40)
    wall("MurGauche_b", -40, DOOR_Y + 40, WALL, ROOM_H + 40)
    wall("Linteau_porte", -40, DOOR_Y - 40, WALL, DOOR_Y + 40, 2.05, CEILING)
    wall("MurDroit", ROOM_W - WALL, -40, ROOM_W + 40, ROOM_H + 40)
    wall("MurBas", -40, ROOM_H - WALL, ROOM_W + 40, ROOM_H + 40)
    wall("MurHaut_a", -40, -40, WINDOW_X[0], WALL)
    wall("MurHaut_b", WINDOW_X[1], -40, ROOM_W + 40, WALL)
    wall("Allège", WINDOW_X[0], -40, WINDOW_X[1], WALL, 0.0, 0.88)
    wall("Linteau_fenêtre", WINDOW_X[0], -40, WINDOW_X[1], WALL, 2.20, CEILING)

    # Fenêtre : tablette, cadre, vitrage à guillotine
    box_px("Tablette", c, WINDOW_X[0] - 6, 2, WINDOW_X[1] + 6, WALL + 4, 0.88, 0.91, M["trim"])
    for x0, x1 in ((WINDOW_X[0], WINDOW_X[0] + 5), (WINDOW_X[1] - 5, WINDOW_X[1]), (318, 322)):
        box_px("Cadre_" + str(x0), c, x0, 4, x1, 10, 0.91, 2.2, M["trim"])
    box_px("Vitre", c, WINDOW_X[0] + 5, 6, WINDOW_X[1] - 5, 7, 0.91, 2.2, M["glass"], bevel=0)

    # Porte (fermée) et chambranle
    box_px("Porte", c, 2, DOOR_Y - 38, 7, DOOR_Y + 38, 0.0, 2.04, M["trim"])
    box_px("Poignée", c, 7, DOOR_Y + 26, 12, DOOR_Y + 30, 0.95, 0.97, M["brass"])
    for y0 in (DOOR_Y - 44, DOOR_Y + 38):
        box_px("Chambranle", c, WALL - 2, y0, WALL + 1, y0 + 6, 0.0, 2.1, M["trim"])

    # Plinthes
    for name, x0, y0, x1, y1 in (("PlintheH_a", WALL, WALL, WINDOW_X[0], WALL + 1.5),
                                 ("PlintheH_b", WINDOW_X[1], WALL, ROOM_W - WALL, WALL + 1.5),
                                 ("PlintheB", WALL, ROOM_H - WALL - 1.5, ROOM_W - WALL, ROOM_H - WALL),
                                 ("PlintheD", ROOM_W - WALL - 1.5, WALL, ROOM_W - WALL, ROOM_H - WALL),
                                 ("PlintheG_a", WALL, WALL, WALL + 1.5, DOOR_Y - 44),
                                 ("PlintheG_b", WALL, DOOR_Y + 44, WALL + 1.5, ROOM_H - WALL)):
        box_px(name, c, x0, y0, x1, y1, 0.0, 0.09, M["trim"], bevel=0.001)

    # Calorifère en fonte sous la fenêtre
    for i in range(22):
        x = 262 + i * 5.6
        box_px("Calorifère_%d" % i, c, x, WALL + 2, x + 4.2, WALL + 11, 0.10, 0.66, M["iron_paint"], bevel=0.008)
    for x in (264, 378):
        cylinder("Pied_calo", c, 0.012, 0.1, P(x, WALL + 6.5), M["iron_paint"])

    # Tapis (sous la table, assez grand pour que la tache de sang tombe dessus)
    rug = to_image("tapis", rug_texture())
    quad("Tapis", c, 3.30, 2.10, P(320, 200, 0.0055), image_mat("Tapis laine", rug, rough=1.0, bump=0.08, sheen=0.6))
    box("Tapis_épaisseur", c, (3.29, 2.09, 0.005), P(320, 200, 0.0), M["fabric_dark"], bevel=0)

    # Tache de sang : sur le tapis, à droite de la chaise du DM
    blood = to_image("sang", blood_texture())
    m = Mat("Sang séché", rough=0.25, Coat_Weight=0.3)
    m.image(blood, alpha=True)
    quad("TacheDeSang", c, 0.60, 0.48, P(BLOOD[0], BLOOD[1], 0.0068), m.m, rot=(0, 0, -8))

    for ob in upper.objects:
        ob.visible_camera = False

    build_table(M, c)
    build_chair(M, c)
    build_shelf(M, c)
    build_counter(M, c)
    build_clutter(M, c)


def build_table(M, c):
    x, y, w, d = TABLE
    top = 0.75
    box_px("Table_plateau", c, x - w / 2, y - d / 2, x + w / 2, y + d / 2, top - 0.04, top, M["walnut"], bevel=0.006)
    box_px("Table_ceinture", c, x - w / 2 + 6, y - d / 2 + 6, x + w / 2 - 6, y + d / 2 - 6, top - 0.12, top - 0.04,
           M["walnut"])
    for lx in (x - w / 2 + 8, x + w / 2 - 8):
        for ly in (y - d / 2 + 8, y + d / 2 - 8):
            box_px("Table_pied", c, lx - 3.5, ly - 3.5, lx + 3.5, ly + 3.5, 0.0, top - 0.04, M["walnut"])

    # Tapis de jeu quadrillé
    mat = to_image("battlemat", battlemat_texture())
    quad("Battlemat", c, 0.80, 0.50, P(315, 200, top + 0.0012), image_mat("Vinyle", mat, rough=0.35), rot=(0, 0, 1.5),
         bend=0.002)

    # Figurines sur le tapis de jeu
    colors = [(0.55, 0.55, 0.58), (0.15, 0.30, 0.55), (0.45, 0.12, 0.10), (0.20, 0.38, 0.18), (0.62, 0.50, 0.25)]
    spots = [(292, 186), (300, 192), (287, 197), (334, 214), (342, 188)]
    for i, ((mx, my), col) in enumerate(zip(spots, colors)):
        mm = Mat("Figurine_%d" % i, col, rough=0.5).m
        cylinder("Mini_socle_%d" % i, c, 0.0125, 0.003, P(mx, my, top + 0.0015), M["black_plastic"], segs=20)
        sphere("Mini_corps_%d" % i, c, 0.007, P(mx, my, top + 0.016), mm, scale=(1, 0.8, 2.2))
        sphere("Mini_tête_%d" % i, c, 0.004, P(mx, my, top + 0.032), mm)
    # Le « monstre » : figurine plus grosse
    cylinder("Mini_boss_socle", c, 0.025, 0.004, P(330, 205, top + 0.0015), M["black_plastic"], segs=24)
    sphere("Mini_boss", c, 0.016, P(330, 205, top + 0.025), Mat("Boss", (0.25, 0.10, 0.30), rough=0.4).m,
           scale=(1.3, 1, 1.4))

    # Dés
    dice_cols = [(0.55, 0.05, 0.08), (0.08, 0.20, 0.55), (0.75, 0.70, 0.60), (0.05, 0.40, 0.25)]
    for i, (dx, dy) in enumerate(((336, 244), (343, 240), (246, 222), (382, 178), (281, 230))):
        dm = Mat("Dé_%d" % i, dice_cols[i % len(dice_cols)], rough=0.15, Coat_Weight=0.6).m
        if i % 2 == 0:
            ico("D20_%d" % i, c, 0.011, P(dx, dy, top + 0.009), dm, rot=(rng.uniform(0, 90), 20, rng.uniform(0, 360)))
        else:
            box("D6_%d" % i, c, (0.016, 0.016, 0.016), P(dx, dy, top), dm, rot=(0, 0, rng.uniform(0, 90)),
                bevel=0.003)

    # Canettes, bol de croustilles, tasse du DM, crayons
    for i, (cx, cy, col) in enumerate(((236, 166, (0.70, 0.08, 0.06)), (232, 248 - 12, (0.10, 0.25, 0.55)),
                                       (372, 160, (0.15, 0.45, 0.15)))):
        can = Mat("Canette_%d" % i, col, rough=0.25, metal=0.6).m
        cylinder("Canette_%d" % i, c, 0.033, 0.122, P(cx, cy, top), can, segs=32)
        cylinder("Canette_dessus_%d" % i, c, 0.028, 0.002, P(cx, cy, top + 0.122), M["steel"], segs=32)
    cylinder("Bol", c, 0.06, 0.06, P(250, 196, top), M["ceramic_white"], r2=0.09, segs=40, open_top=True)
    chips = Mat("Croustilles", (0.80, 0.58, 0.25), rough=0.6).m
    for i in range(16):
        a, r = rng.uniform(0, 6.28), rng.uniform(0, 0.05)
        sphere("Croustille_%d" % i, c, 0.018, P(250 + math.cos(a) * r * 100, 196 + math.sin(a) * r * 100,
                                               top + 0.035 + rng.uniform(0, 0.015)), chips,
               scale=(1, 0.8, 0.12), rot=(rng.uniform(-30, 30), rng.uniform(-30, 30), rng.uniform(0, 360)), segs=12)
    cylinder("Tasse_DM", c, 0.042, 0.095, P(414, 188, top), M["ceramic_blue"], segs=32, open_top=True)
    cylinder("Café", c, 0.037, 0.001, P(414, 188, top + 0.085), Mat("Café", (0.05, 0.025, 0.01), rough=0.05).m)
    for i, (px_, py_, a) in enumerate(((326, 160, 25), (268, 210, -60))):
        cylinder("Crayon_%d" % i, c, 0.0035, 0.17, P(px_, py_, top + 0.0035),
                 Mat("Crayon_%d" % i, (0.85, 0.65, 0.05), rough=0.4).m, segs=6, rot=(0, 90, a))


def build_chair(M, c):
    x, y = DM_CHAIR
    seat = 0.46
    box_px("Chaise_assise", c, x - 21, y - 21, x + 19, y + 21, seat - 0.03, seat, M["oak"], bevel=0.008)
    box_px("Chaise_coussin", c, x - 19, y - 19, x + 15, y + 19, seat, seat + 0.035,
           noisy_mat("Coussin", (0.06, 0.12, 0.08), (0.09, 0.16, 0.11), scale=300, rough=1.0, bump=0.2,
                     Sheen_Weight=0.5), bevel=0.015)
    for lx in (x - 18, x + 16):
        for ly in (y - 18, y + 18):
            box_px("Chaise_pied", c, lx - 2, ly - 2, lx + 2, ly + 2, 0.0, seat - 0.03, M["oak"])
    for ly in (y - 18, y + 18):
        box_px("Chaise_montant", c, x + 15, ly - 2, x + 19, ly + 2, seat, 0.92, M["oak"], bevel=0.004)
    box_px("Chaise_dossier", c, x + 15.5, y - 20, x + 19, y + 20, 0.78, 0.92, M["oak"], bevel=0.006)
    for ly in (y - 8, y, y + 8):
        box_px("Chaise_barreau", c, x + 16, ly - 1, x + 18, ly + 1, seat + 0.03, 0.78, M["oak"])


def build_shelf(M, c):
    x, y, w, d = SHELF
    h = 0.92
    x0, x1, y0, y1 = x - w / 2, x + w / 2, y - d / 2, y + d / 2
    box_px("Étagère_dessus", c, x0 - 1, y0 - 1, x1 + 1, y1 + 1, h - 0.025, h, M["pine"], bevel=0.003)
    for yy in (y0, y1 - 2):
        box_px("Étagère_côté", c, x0, yy, x1, yy + 2, 0.0, h - 0.025, M["pine"])
    box_px("Étagère_fond", c, x1 - 1, y0, x1, y1, 0.0, h, M["pine"])
    for z in (0.02, 0.32, 0.62):
        box_px("Étagère_tablette", c, x0, y0, x1, y1, z, z + 0.02, M["pine"])
    # Livres debout dans les tablettes (visibles par les ombres et les rebords)
    book_cols = [(0.35, 0.08, 0.06), (0.08, 0.15, 0.30), (0.12, 0.25, 0.12), (0.45, 0.35, 0.15), (0.15, 0.12, 0.10)]
    for z in (0.04, 0.34, 0.64):
        yy = y0 + 3
        while yy < y1 - 6:
            t = rng.uniform(2.5, 5)
            hh = rng.uniform(0.18, 0.27)
            box_px("Livre", c, x0 + 2, yy, x1 - 2, yy + t, z, z + hh,
                   Mat("Reliure", rng.choice(book_cols), rough=0.6).m, bevel=0.002)
            yy += t + 0.3
    # Dessus : pile de livres couchés, bougie, bocal à dés. Place du dragon libre (y 164-188).
    top = h
    for i, (bw, bd, col) in enumerate(((24, 17, (0.30, 0.10, 0.08)), (22, 15, (0.10, 0.18, 0.32)),
                                       (19, 13, (0.62, 0.55, 0.40)))):
        box("Livre_couché_%d" % i, c, (bd * PX, bw * PX, 0.035 - i * 0.006), P(x, 226, top + sum(
            0.035 - k * 0.006 for k in range(i))), Mat("Couverture_%d" % i, col, rough=0.55).m,
            rot=(0, 0, rng.uniform(-8, 8)), bevel=0.003)
    cylinder("Bougeoir", c, 0.035, 0.012, P(x, 205, top), M["brass"], segs=32)
    cylinder("Bougie", c, 0.018, 0.07, P(x, 205, top + 0.012), M["wax"], segs=24)
    cylinder("Bocal", c, 0.032, 0.08, P(x - 2, 154 + 4, top), M["glass"], segs=32)


def build_counter(M, c):
    x, y, w, d = COUNTER
    x0, x1, y0, y1 = x - w / 2, x + w / 2, y - d / 2, y + d / 2
    h = 0.92
    box_px("Comptoir_caisson", c, x0 + 2, y0 + 2, x1 - 2, y1 - 2, 0.1, h - 0.03, M["cabinet"], bevel=0.003)
    box_px("Comptoir_socle", c, x0 + 5, y0 + 5, x1 - 5, y1 - 5, 0.0, 0.1, M["black_plastic"], bevel=0)
    # Dessus en quartz avec une cuve d'évier découpée (construite en 4 morceaux autour de la cuve)
    sx0, sx1, sy0, sy1 = x0 + 12, x1 - 12, y0 + 82, y0 + 116
    for (a, b, cc, dd) in ((x0, y0, x1, sy0), (x0, sy1, x1, y1), (x0, sy0, sx0, sy1), (sx1, sy0, x1, sy1)):
        box_px("Comptoir_dessus", c, a, b, cc, dd, h - 0.03, h, M["counter_top"], bevel=0.002)
    box_px("Cuve_fond", c, sx0, sy0, sx1, sy1, h - 0.2, h - 0.19, M["steel"], bevel=0)
    for (a, b, cc, dd) in ((sx0, sy0, sx1, sy0 + 0.6), (sx0, sy1 - 0.6, sx1, sy1), (sx0, sy0, sx0 + 0.6, sy1),
                           (sx1 - 0.6, sy0, sx1, sy1)):
        box_px("Cuve_paroi", c, a, b, cc, dd, h - 0.2, h - 0.005, M["steel"], bevel=0)
    cylinder("Drain", c, 0.02, 0.002, P(x, (sy0 + sy1) / 2, h - 0.19), M["steel"])
    # Robinet à col de cygne
    cylinder("Robinet_base", c, 0.022, 0.05, P(x, sy1 + 6, h), M["steel"], segs=24)
    cylinder("Robinet_col", c, 0.011, 0.26, P(x, sy1 + 6, h + 0.05), M["steel"], segs=16)
    box("Robinet_bec", c, (0.022, 0.13, 0.022), P(x, sy1 + 6 - 6.5, h + 0.29), M["steel"], bevel=0.008)
    # Tasses dans l'évier, bouilloire, planche à découper
    cylinder("Tasse_évier", c, 0.04, 0.09, P(x - 8, sy0 + 12, h - 0.19), M["ceramic_white"], segs=24,
             open_top=True)
    cylinder("Bouilloire", c, 0.085, 0.2, P(x + 14, y1 - 22, h), M["steel"], r2=0.07, segs=32)
    cylinder("Bouilloire_poignée", c, 0.015, 0.03, P(x + 14, y1 - 22, h + 0.2), M["black_plastic"])
    box_px("Planche", c, x0 + 6, y0 + 4, x1 - 34, y0 + 30, h, h + 0.018, M["oak"], bevel=0.003)


def build_clutter(M, c):
    # Paillasson et souliers près de la porte
    mat = noisy_mat("Coco", (0.30, 0.20, 0.10), (0.42, 0.30, 0.16), scale=400, rough=1.0, bump=0.4)
    box_px("Paillasson", c, WALL + 2, DOOR_Y - 30, WALL + 42, DOOR_Y + 30, 0.0, 0.012, mat, bevel=0.002)
    for i, (sx, sy, a) in enumerate(((30, 318, 80), (40, 316, 95))):
        sphere("Soulier_%d" % i, c, 0.05, P(sx, sy, 0.035), M["leather_dark"], scale=(1.4, 0.55, 0.6),
               rot=(0, 0, a))
        box("Semelle_%d" % i, c, (0.14, 0.05, 0.02), P(sx, sy, 0.0), M["rubber"], rot=(0, 0, a), bevel=0.01)
    # Serviette froissée et un dé tombé par terre
    sphere("Serviette", c, 0.05, P(214, 262, 0.012), M["paper"], scale=(1.0, 0.8, 0.35), segs=10)
    box("D6_sol", c, (0.016, 0.016, 0.016), P(428, 272, 0.0), Mat("Dé_sol", (0.08, 0.2, 0.55), rough=0.15).m,
        rot=(0, 0, 31), bevel=0.003)
    # Fil du chargeur qui part de la table vers le mur du bas
    pts = [P(244, 248, 0.73), P(236, 252, 0.3), P(226, 262, 0.012), P(206, 300, 0.012), P(176, 328, 0.012),
           P(150, 431, 0.05)]
    cu = bpy.data.curves.new("Fil", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0025
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new("Fil", cu)
    c.objects.link(ob)
    cu.materials.append(Mat("Fil noir", (0.03, 0.03, 0.03), rough=0.4).m)
    # Marqueurs de scène de crime
    for num, mx, my, a in (("1", 498, 272, -20), ("2", 436, 236, 15)):
        tent = poly_prism("Marqueur_" + num, c, [(-0.04, -0.035), (0.04, -0.035), (0.04, 0.035), (-0.04, 0.035)],
                          0.004, P(mx, my, 0.0), M["marker_yellow"], rot=(0, 0, a))
        tent.scale = (1.4, 1.4, 1.4)
        # en forme de tente : on relève l'arête centrale
        me = tent.data
        for v in me.vertices:
            if v.co.z > 0.001:
                v.co.z = 0.06 - abs(v.co.y) * 1.4
        tent.modifiers.clear()
        text("Num_" + num, c, num, 0.055, P(mx, my, 0.06), M["ink_black"], rot=(0, 0, a))


# --------------------------------------------------------------------------------------------
# Pièces à conviction (une collection chacune)
# --------------------------------------------------------------------------------------------

TABLE_TOP = 0.75


def build_items(M):
    items = {}

    c = items["phone_playlist"] = coll("Item_phone_playlist")
    px_, py_ = 260, 236
    box("Téléphone", c, (0.075, 0.155, 0.008), P(px_, py_, TABLE_TOP), M["black_plastic"], rot=(0, 0, 12),
        bevel=0.004)
    scr = to_image("phone_screen", phone_texture())
    sm = Mat("Écran téléphone", rough=0.05, Coat_Weight=1.0)
    t = sm.image(scr)
    em = sm.node("ShaderNodeEmission", Strength=0.8)
    sm.link(t.outputs["Color"], em.inputs["Color"])
    add = sm.node("ShaderNodeAddShader")
    sm.link(sm.bsdf.outputs["BSDF"], add.inputs[0])
    sm.link(em.outputs["Emission"], add.inputs[1])
    sm.link(add.outputs["Shader"], sm.out.inputs["Surface"])
    quad("Écran", c, 0.07, 0.148, P(px_, py_, TABLE_TOP + 0.0082), sm.m, rot=(0, 0, 12))

    c = items["treasury_ledger"] = coll("Item_treasury_ledger")
    led = image_mat("Registre", to_image("ledger", ledger_texture()), rough=0.7, bump=0.1)
    box("Registre_pages", c, (0.215, 0.275, 0.028), P(300, 164, TABLE_TOP), M["paper"], rot=(0, 0, 84), bevel=0.002)
    box("Registre_couv_bas", c, (0.222, 0.28, 0.003), P(300, 164, TABLE_TOP), M["leather_dark"], rot=(0, 0, 84),
        bevel=0.001)
    quad("Registre_couverture", c, 0.222, 0.28, P(300, 164, TABLE_TOP + 0.0285), led, rot=(0, 0, 84))
    # Ruban signet qui dépasse
    box("Signet", c, (0.008, 0.05, 0.0006), P(300 + 13, 164 + 2, TABLE_TOP), Mat("Ruban", (0.5, 0.05, 0.05)).m,
        rot=(0, 0, 70), bevel=0)

    c = items["dm_notebook"] = coll("Item_dm_notebook")
    nb = image_mat("Bloc-notes", to_image("notebook", notebook_texture()), rough=0.8, bump=0.1)
    box("Bloc_pages", c, (0.15, 0.21, 0.012), P(400, 164, TABLE_TOP), M["paper"], rot=(0, 0, -12), bevel=0.001)
    quad("Bloc_couverture", c, 0.15, 0.21, P(400, 164, TABLE_TOP + 0.0123), nb, rot=(0, 0, -12))
    cylinder("Bloc_crayon", c, 0.0035, 0.17, P(386, 158, TABLE_TOP + 0.016),
             Mat("Crayon bleu", (0.05, 0.12, 0.40), rough=0.3).m, segs=6, rot=(0, 90, 70))

    c = items["dm_screen"] = coll("Item_dm_screen")
    # Écran à trois volets, debout, face aux joueurs (vers la gauche), légèrement incliné
    cx, cy = 404, 228
    panel_w, panel_h = 0.15, 0.22
    for i, (dy, ang) in enumerate(((-15, 30), (0, 0), (15, -30))):
        tex = to_image("screen_%d" % i, screen_texture(40 + i))
        art = image_mat("Volet_%d" % i, tex, rough=0.55)
        ob = box("Volet_%d" % i, c, (0.003, panel_w, panel_h), P(cx + abs(dy) * 0.25, cy + dy, TABLE_TOP),
                 Mat("Carton noir", (0.03, 0.03, 0.03), rough=0.7).m, rot=(0, 22, ang), bevel=0.0008)
        face = quad("Volet_art_%d" % i, c, panel_w * 0.98, panel_h * 0.98, (0, 0, 0), art)
        face.parent = ob
        face.location = (-0.0016, 0, panel_h / 2)
        face.rotation_euler = (math.radians(90), 0, math.radians(-90))

    c = items["character_sheet"] = coll("Item_character_sheet")
    sh = image_mat("Feuille", to_image("sheet", sheet_texture()), rough=0.85)
    quad("Feuille_perso", c, 0.216, 0.279, P(360, 236, TABLE_TOP + 0.0006), sh, rot=(0, 0, 97), bend=0.003)

    c = items["pizza_box"] = coll("Item_pizza_box")
    build_pizza(M, c, 96, 74, 0.92)

    c = items["satchel"] = coll("Item_satchel")
    build_satchel(M, c, 240, 300)

    c = items["bronze_dragon"] = coll("Item_bronze_dragon")
    build_dragon(M, c, 496, 176, 0.92)
    return items


def build_pizza(M, c, x, y, z):
    s = 0.35
    inside = noisy_mat("Carton graisseux", (0.55, 0.42, 0.26), (0.40, 0.26, 0.12), scale=12, rough=0.8, bump=0.03)
    box("Pizza_fond", c, (s, s, 0.004), P(x, y, z), inside, bevel=0.001)
    for name, (sx, sy, ox, oy) in (("g", (0.004, s, -s / 2, 0)), ("d", (0.004, s, s / 2, 0)),
                                   ("b", (s, 0.004, 0, s / 2)), ("h", (s, 0.004, 0, -s / 2))):
        box("Pizza_bord_" + name, c, (sx, sy, 0.04), P(x + ox * 100, y + oy * 100, z), M["cardboard"], bevel=0.001)
    # Couvercle relevé presque à la verticale, charnière à l'arrière (vers le mur du haut)
    # Couvercle ouvert à 110° : il penche vers l'arrière et montre son intérieur taché
    lid_tex = canvas(140, 140, (0.62, 0.47, 0.30))
    grain(lid_tex, 0.3, 30, 31)
    for k in range(6):
        disk(lid_tex, rng.uniform(20, 120), rng.uniform(20, 120), rng.uniform(6, 16), (0.42, 0.28, 0.12), 0.35)
    lid = box("Pizza_couvercle", c, (s, s, 0.003), (0, 0, 0), M["cardboard"], bevel=0.001, origin_bottom=False)
    lid_in = quad("Pizza_couvercle_int", c, s * 0.98, s * 0.98, (0, 0, 0),
                  image_mat("Carton intérieur", to_image("lid", lid_tex), rough=0.85))
    lid_in.parent = lid
    lid_in.location = (0, 0, -0.0016)
    lid_in.rotation_euler = (math.radians(180), 0, 0)
    theta = math.radians(110)
    hinge = P(x, y - s * 50, z + 0.04)
    lid.location = hinge + Vector((0, -s / 2 * math.cos(-theta), -s / 2 * math.sin(-theta)))
    lid.rotation_euler = (-theta, 0, 0)
    # La pointe restante + taches de graisse
    crust = Mat("Croûte", (0.62, 0.38, 0.16), rough=0.7).m
    cheese = noisy_mat("Fromage", (0.85, 0.62, 0.22), (0.70, 0.40, 0.10), scale=60, rough=0.35, bump=0.3)
    ang = math.radians(rng.uniform(0, 40))
    r = 0.16
    pts = [(0, 0)] + [(r * math.cos(ang + math.radians(a)), r * math.sin(ang + math.radians(a)))
                      for a in np.linspace(-22, 22, 8)]
    base = P(x - 6, y + 4, z + 0.004)
    poly_prism("Pointe", c, pts, 0.008, base, cheese)
    for k in range(8):
        a = ang + math.radians(np.linspace(-22, 22, 8)[k])
        sphere("Croûte_%d" % k, c, 0.013, base + Vector((r * math.cos(a), r * math.sin(a), 0.01)), crust,
               scale=(1, 1.8, 0.8), rot=(0, 0, math.degrees(a)), segs=12)
    top_cols = [(0.10, 0.35, 0.10), (0.45, 0.35, 0.28), (0.08, 0.06, 0.06), (0.70, 0.12, 0.08)]
    for k in range(14):
        rr, aa = rng.uniform(0.03, 0.13), ang + math.radians(rng.uniform(-16, 16))
        cylinder("Garniture_%d" % k, c, rng.uniform(0.006, 0.011), 0.004,
                 base + Vector((rr * math.cos(aa), rr * math.sin(aa), 0.012)),
                 Mat("Garniture_%d" % k, rng.choice(top_cols), rough=0.4).m, segs=10)
    grease = Mat("Graisse", (0.40, 0.27, 0.13), rough=0.45).m
    for k in range(3):
        sphere("Graisse_%d" % k, c, rng.uniform(0.02, 0.035), P(x + rng.uniform(6, 14), y + rng.uniform(-12, 12),
                                                                z + 0.0042), grease,
               scale=(1.0, rng.uniform(0.6, 1.0), 0.004), segs=16)


def build_satchel(M, c, x, y):
    rot = 18
    eul = Euler((0, 0, math.radians(rot)))

    def at(dx, dy, dz):
        v = Vector((dx, dy, dz))
        v.rotate(eul)
        return P(x, y, 0) + v

    body = box("Cartable", c, (0.38, 0.28, 0.10), at(0, 0, 0), M["leather"], rot=(0, 0, rot), bevel=0.025)
    body.modifiers["Bevel"].segments = 4
    box("Rabat", c, (0.386, 0.22, 0.012), at(0, 0.035, 0.096), M["leather"], rot=(0, 0, rot), bevel=0.01)
    for dx in (-0.09, 0.09):
        box("Courroie", c, (0.025, 0.17, 0.003), at(dx, -0.01, 0.108), M["leather_dark"], rot=(0, 0, rot),
            bevel=0.001)
        box("Boucle", c, (0.032, 0.022, 0.004), at(dx, -0.07, 0.109), M["brass"], rot=(0, 0, rot), bevel=0.002)
    # Bandoulière qui traîne au sol
    pts = [P(x - 18, y - 2, 0.06), P(x - 30, y + 10, 0.006), P(x - 20, y + 30, 0.006), P(x + 5, y + 26, 0.006),
           P(x + 18, y + 6, 0.06)]
    cu = bpy.data.curves.new("Bandoulière", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.004
    cu.bevel_resolution = 1
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new("Bandoulière", cu)
    c.objects.link(ob)
    cu.materials.append(M["leather_dark"])


def build_dragon(M, c, x, y, z):
    base = P(x, y, z)
    box("Socle", c, (0.09, 0.09, 0.025), base, Mat("Marbre noir", (0.03, 0.03, 0.035), rough=0.15).m, bevel=0.004)
    mb = bpy.data.metaballs.new("Dragon")
    mb.resolution = 0.004
    mb.render_resolution = 0.0025
    ob = bpy.data.objects.new("Dragon", mb)
    c.objects.link(ob)
    ob.location = base + Vector((0, 0, 0.025))
    ob.rotation_euler = (0, 0, math.radians(180))  # tête vers la table (gauche)
    ob.scale = (1.6, 1.6, 1.6)
    mb.materials.append(M["bronze"])

    def ball(co, r, stiff=2.0):
        e = mb.elements.new(type="BALL")
        e.co = co
        e.radius = r
        e.stiffness = stiff

    # Corps assis, cou en S, tête, queue enroulée autour du socle
    for co, r in (((0, 0, 0.03), 0.028), ((0.01, 0, 0.055), 0.026), ((0.025, 0, 0.08), 0.02),
                  ((0.035, 0, 0.10), 0.016), ((0.04, 0, 0.12), 0.014), ((0.055, 0, 0.13), 0.016),
                  ((0.072, 0, 0.128), 0.011)):
        ball(co, r)
    for i in range(10):
        a = math.radians(-90 - i * 26)
        ball((-0.01 + math.cos(a) * 0.03, math.sin(a) * 0.032, 0.012), 0.014 - i * 0.0009, 1.5)
    for sy in (-1, 1):  # pattes
        ball((0.025, sy * 0.016, 0.015), 0.011)
        ball((-0.015, sy * 0.022, 0.012), 0.013)
    # Ailes : membranes fines déployées
    wing = M["bronze"]
    for sy in (-1, 1):
        pts = [(0.01, 0), (-0.015, sy * 0.06), (0.005, sy * 0.105), (-0.03, sy * 0.095), (-0.04, sy * 0.075),
               (-0.06, sy * 0.07), (-0.065, sy * 0.04), (-0.05, 0)]
        w = poly_prism("Aile", c, pts, 0.0025, (0, 0, 0), wing, smooth=True)
        w.parent = ob
        w.location = (0.01, sy * 0.012, 0.075)
        w.rotation_euler = (math.radians(-sy * 35), math.radians(-15), 0)
        sol = w.modifiers.new("Sub", "SUBSURF")
        sol.levels = sol.render_levels = 2


# --------------------------------------------------------------------------------------------
# Personnages
# --------------------------------------------------------------------------------------------

def build_characters(M):
    out = {}
    specs = {
        "player": dict(coat=(0.55, 0.45, 0.30), hair=(0.10, 0.06, 0.04), skin=(0.78, 0.58, 0.45), scarf=(0.35, 0.06, 0.06)),
        "lavoie": dict(coat=(0.07, 0.09, 0.14), hair=(0.55, 0.55, 0.55), skin=(0.70, 0.52, 0.42), scarf=None),
    }
    for name, s in specs.items():
        c = out[name] = coll("Char_" + name)
        coat = noisy_mat("Manteau_" + name, [v * 0.85 for v in s["coat"]], s["coat"], scale=200, rough=0.85, bump=0.1,
                         Sheen_Weight=0.4)
        skin = Mat("Peau_" + name, s["skin"], rough=0.5, Subsurface_Weight=0.2).m
        hair = noisy_mat("Cheveux_" + name, [v * 0.7 for v in s["hair"]], s["hair"], scale=400, rough=0.6, bump=0.3)
        # Vers -Y Blender = bas de l'écran Godot
        sphere("Épaules", c, 0.2, (0, 0, 1.38), coat, scale=(1.0, 0.55, 0.32))
        sphere("Torse", c, 0.18, (0, 0.005, 1.1), coat, scale=(1.0, 0.62, 1.1))
        cylinder("Pans", c, 0.19, 0.6, (0, 0.01, 0.35), coat, r2=0.17, segs=32)
        for sx in (-1, 1):
            sphere("Bras", c, 0.048, (sx * 0.2, -0.015, 1.08), coat, scale=(1, 1.1, 4.6), rot=(8, sx * -4, 0))
            sphere("Main", c, 0.03, (sx * 0.205, -0.05, 0.8), skin, scale=(0.7, 1, 1.3))
            sphere("Soulier", c, 0.05, (sx * 0.09, -0.08, 0.035), M["leather_dark"], scale=(0.8, 1.6, 0.6))
        sphere("Cou", c, 0.055, (0, 0, 1.5), skin, scale=(1, 1, 1.2))
        sphere("Tête", c, 0.095, (0, 0, 1.64), skin, scale=(0.92, 1.0, 1.1))
        sphere("Nez", c, 0.018, (0, -0.095, 1.63), skin, scale=(0.8, 1, 1.2))
        sphere("Cheveux", c, 0.1, (0, 0.012, 1.672), hair, scale=(0.95, 1.0, 0.95))
        for sx in (-1, 1):
            sphere("Oreille", c, 0.02, (sx * 0.088, 0.0, 1.635), skin, scale=(0.5, 1, 1.3))
        if s["scarf"]:
            cylinder("Foulard", c, 0.08, 0.05, (0, 0, 1.47), noisy_mat("Foulard", s["scarf"],
                                                                         [v * 1.3 for v in s["scarf"]], scale=150,
                                                                         rough=0.9), r2=0.07)
        else:  # Lavoie : un calepin dans la main droite
            box("Calepin", c, (0.08, 0.12, 0.012), (0.2, -0.09, 0.9), M["black_plastic"], rot=(70, 0, 0))
    return out


# --------------------------------------------------------------------------------------------
# Lumières, caméra, rendus
# --------------------------------------------------------------------------------------------

def add_light(name, kind, loc, energy, color, c, size=0.1, size_y=None, rot=(0, 0, 0)):
    l = bpy.data.lights.new(name, kind)
    l.energy = energy
    l.color = color
    if kind == "AREA":
        l.shape = "RECTANGLE"
        l.size = size
        l.size_y = size_y or size
    elif kind in ("POINT", "SPOT"):
        l.shadow_soft_size = size
    ob = bpy.data.objects.new(name, l)
    ob.visible_camera = False
    c.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def build_lights():
    c = coll("Lights_room")
    # Jour gris du matin par la fenêtre : grande source froide dehors, inclinée vers la pièce
    add_light("Fenêtre", "AREA", P(320, -60, 1.6), 500, (0.72, 0.82, 1.0), c, size=1.7, size_y=1.4, rot=(-75, 0, 0))
    add_light("Ciel", "AREA", P(320, -200, 3.5), 600, (0.65, 0.75, 1.0), c, size=3.0, size_y=2.0, rot=(-35, 0, 0))
    # Plafonnier resté allumé au-dessus de la table
    add_light("Plafonnier", "POINT", P(320, 200, 2.05), 85, (1.0, 0.76, 0.50), c, size=0.08)
    # Abat-jour opaque (invisible pour la caméra) : la lumière tombe sur la table, pas au plafond
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.24, radius2=0.07, depth=0.26)
    bottom = min(bm.faces, key=lambda f: f.calc_center_median().z)
    bmesh.ops.delete(bm, geom=[bottom], context="FACES_ONLY")
    shade = finish("Abat-jour", bm, Mat("Abat-jour", (0.05, 0.05, 0.05), rough=0.6).m, coll("RoomUpper"),
                   P(320, 200, 2.13), smooth=True)
    shade.modifiers.new("Paroi", "SOLIDIFY").thickness = 0.004
    shade.visible_camera = False
    # Lumière du couloir sous la porte
    add_light("Couloir", "AREA", P(-30, DOOR_Y, 0.02), 6, (1.0, 0.85, 0.65), c, size=0.06, size_y=0.75,
              rot=(0, 90, 0))

    cc = coll("Lights_char")
    add_light("Douce", "AREA", (0.3, 0.4, 5.0), 160, (1.0, 0.95, 0.9), cc, size=1.2, rot=(-4, 3, 0))
    return c, cc


def setup_world():
    w = bpy.data.worlds.new("Monde")
    bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.08


def setup_render(samples):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.02
    s.cycles.max_bounces = 8
    s.cycles.use_denoising = True
    try:
        s.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    s.render.image_settings.color_depth = "8"
    s.view_settings.view_transform = "AgX"
    try:
        s.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    s.view_settings.exposure = 0.0
    s.render.resolution_percentage = 100


def room_camera():
    cam = bpy.data.cameras.new("Caméra")
    cam.type = "ORTHO"
    cam.ortho_scale = ROOM_W * PX
    cam.clip_start = 0.1
    cam.clip_end = 20
    ob = bpy.data.objects.new("Caméra", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = P(ROOM_W / 2, ROOM_H / 2, 8.0)
    return ob


def char_camera():
    cam = bpy.data.cameras.new("Caméra_perso")
    cam.type = "ORTHO"
    cam.ortho_scale = CHAR_SIZE * PX
    ob = bpy.data.objects.new("Caméra_perso", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 0, 8.0)
    return ob


def show(colls_visible):
    for name, c in COLLS.items():
        c.hide_render = name not in colls_visible
    # les collections parentes doivent rester visibles
    for name in colls_visible:
        COLLS[name].hide_render = False


def set_shadow_catcher(collection_names, value):
    for name in collection_names:
        for ob in COLLS[name].all_objects:
            ob.is_shadow_catcher = value


def render(path, fade=None):
    """Rend l'image. `fade` = "edges" ou "radial" : l'alpha s'éteint vers les bords pour qu'une ombre
    portée ne soit jamais coupée net par le cadre du sprite ; le bruit résiduel du shadow catcher est retiré."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if fade:
        img = bpy.data.images.load(path)
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        a = px[..., 3]
        a[a < 0.03] = 0.0
        yy, xx = np.mgrid[0:h, 0:w] + 0.5
        if fade == "radial":
            r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
            m = np.clip((1.0 - r) / 0.25, 0, 1)
        else:
            edge = np.minimum(np.minimum(xx, w - xx), np.minimum(yy, h - yy))
            m = np.clip(edge / 6.0, 0, 1)
        px[..., 3] = a * m
        img.pixels.foreach_set(px.ravel())
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
    print("rendu :", path)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "godot", "art",
                                                  "room"))
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--only", choices=["background", "items", "characters"])
    ap.add_argument("--item", help="ne rendre que cette preuve (id)")
    ap.add_argument("--save-blend")
    args = ap.parse_args(argv)
    out = os.path.abspath(args.out)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    M = build_materials()
    build_room(M)
    items = build_items(M)
    chars = build_characters(M)
    build_lights()
    setup_world()
    setup_render(args.samples)
    cam_room = room_camera()
    cam_char = char_camera()
    room_colls = ["Room", "RoomUpper"]
    item_colls = ["Item_" + k for k in items]

    if args.save_blend:
        show(room_colls + item_colls + ["Lights_room"])
        s.camera = cam_room
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save_blend))

    if args.only in (None, "background"):
        s.camera = cam_room
        s.render.resolution_x, s.render.resolution_y = ROOM_W * RES, ROOM_H * RES
        s.render.use_border = False
        s.render.film_transparent = False
        set_shadow_catcher(room_colls, False)
        show(room_colls + ["Lights_room"])
        render(os.path.join(out, "background.png"))

    if args.only in (None, "items"):
        s.camera = cam_room
        s.render.resolution_x, s.render.resolution_y = ROOM_W * RES, ROOM_H * RES
        s.render.film_transparent = True
        s.render.use_border = True
        s.render.use_crop_to_border = True
        set_shadow_catcher(room_colls, True)
        for item_id, cx, cy, w, h in ITEM_REGIONS:
            if args.item and args.item != item_id:
                continue
            show(room_colls + ["Item_" + item_id, "Lights_room"])
            s.render.border_min_x = (cx - w / 2) / ROOM_W
            s.render.border_max_x = (cx + w / 2) / ROOM_W
            s.render.border_min_y = 1 - (cy + h / 2) / ROOM_H
            s.render.border_max_y = 1 - (cy - h / 2) / ROOM_H
            render(os.path.join(out, "items", item_id + ".png"), fade="edges")
        set_shadow_catcher(room_colls, False)
        s.render.use_border = False

    if args.only in (None, "characters"):
        floor = box("Sol_ombre", coll("CharFloor"), (2, 2, 0.01), (0, 0, -0.01), M["paper"], bevel=0)
        floor.is_shadow_catcher = True
        s.camera = cam_char
        s.render.resolution_x = s.render.resolution_y = CHAR_SIZE * RES
        s.render.film_transparent = True
        for name in chars:
            show(["Char_" + name, "CharFloor", "Lights_char"])
            render(os.path.join(out, "characters", name + ".png"), fade="radial")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)
