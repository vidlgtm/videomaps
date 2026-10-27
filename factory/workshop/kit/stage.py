"""Builds one described 3D scene in Blender (4.5, Cycles) from the general tools of the kit.
plan.py solves the layout, the motion of the cast and the camera path; this file makes the place, the light of the mood,
the geometry and materials of every cast member, the keys, and (preview) measures what every image cell shows, the label
tracks, overlaps, members cut by the frame or showing as a sliver, and the true colours of every picture."""
import math, os
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
import common as C
import mats as M
import plan as P
import props as PR
import outdoor as OD

KIT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.normpath(os.path.join(KIT, "..", "..", "..", "fonts"))
SURFACE = {"desk": "walnut", "museum": "marble", "floor": "stone", "void": None}
MATERIAL = {"sheet": "paper", "print": "paper", "canvas": "gold", "frame": "gold", "disc": "wax", "block": "marble", "text": "gold",
            "pole": "walnut", "plinth": "marble", "table": "walnut", "candle": "wax", "book": "leather", "box": "walnut",
            "globe": "walnut", "cutout": "paper", "cloth": "cloth", "wall": "plaster", "tile": "slate", "terrain": "stone",
            "model": "painted"}
# LIGHT. A document or picture is shown in its exact colours, so the scene is lit for paper: the key light gives the cast an
# irradiance that is a share of E_PAPER (under E_PAPER white paper is exactly white at 0 EV). Seals, hands and props on the
# documents are then lit as the documents appear. The key is one soft pool over the whole cast (full strength over the cast,
# a smooth fall-off beyond it), so the room around falls into the mood's darkness; its direction, height, softness and colour,
# the fill, the rim and the room make the mood. The room's own light follows its surface, so a black slate floor or white
# marble still reads as a room, not as a void or a glare.
E_PAPER = math.pi / 0.8
PAPER_LIGHT = E_PAPER * 4 * math.pi                                # spot power for E_PAPER = PAPER_LIGHT x distance^2
# key: azimuth and elevation from the centre of the cast (deg; the camera stands at -90), distance and size (x L0), colour,
# irradiance (share of E_PAPER); fill and rim: colour, share of the key; world: ambient colour; dark: share of near-black allowed
LIGHT = {
    "lamp": {"key": (-125, 58, 1.7, 0.6, (1.0, 0.86, 0.68), 0.6), "fill": ((0.85, 0.88, 1.0), 0.08), "rim": ((1.0, 0.9, 0.75), 0.3),
             "world": (0.0040, 0.0036, 0.0032), "dark": 0.92},
    "museum": {"key": (-100, 72, 2.0, 0.45, (1.0, 0.95, 0.88), 0.6), "fill": ((0.9, 0.93, 1.0), 0.04), "rim": ((0.92, 0.95, 1.0), 0.3),
               "world": (0.0012, 0.0012, 0.0014), "dark": 0.97},
    "candle": {"key": (90, 30, 1.1, 0.22, (1.0, 0.64, 0.34), 0.7), "fill": ((0.55, 0.6, 0.8), 0.04), "rim": None,
               "world": (0.0025, 0.0018, 0.0012), "dark": 0.95},
    "studio": {"key": (-130, 50, 1.8, 1.4, (1.0, 0.97, 0.92), 0.65), "fill": ((0.92, 0.95, 1.0), 0.25), "rim": ((1.0, 0.98, 0.95), 0.4),
               "world": (0.010, 0.010, 0.011), "dark": 0.5},
    "dawn": {"key": (-165, 22, 2.4, 2.0, (1.0, 0.80, 0.62), 0.75), "fill": ((0.75, 0.82, 1.0), 0.12), "rim": None,
             "world": (0.010, 0.009, 0.010), "dark": 0.6},
    "noon": {"key": (-120, 62, 2.2, 1.6, (1.0, 0.97, 0.92), 0.65), "fill": ((0.85, 0.9, 1.0), 0.18), "rim": None,
             "world": (0.018, 0.018, 0.020), "dark": 0.5},
    "dusk": {"key": (-165, 20, 2.4, 2.0, (1.0, 0.60, 0.34), 0.7), "fill": ((0.6, 0.72, 1.0), 0.10), "rim": None,
             "world": (0.008, 0.006, 0.006), "dark": 0.65},
    "overcast": {"key": (-110, 55, 2.2, 3.0, (0.86, 0.90, 1.0), 0.55), "fill": ((0.86, 0.9, 1.0), 0.3), "rim": None,
                 "world": (0.025, 0.027, 0.030), "dark": 0.5},
    "night": {"key": (-150, 35, 2.2, 1.6, (0.62, 0.72, 1.0), 0.35), "fill": ((0.5, 0.55, 0.8), 0.05), "rim": ((0.62, 0.72, 1.0), 0.25),
              "world": (0.0012, 0.0016, 0.0032), "dark": 0.95},
}
DIM = 0.25                    # a scene whose pictures get their light on cue keeps its room at a quarter of the key
A_ROOM = 0.06                 # the room light is set for a surface of this albedo and scaled to the real one (1/8 .. 4)
# size of the key's pool (x L0, radius of its cone over the cast is 0.86 of it) and the softness of its edge, per mood:
# a candle or a museum spot is a tight pool that falls into darkness, a studio or a window lights the whole stage
POOL = {"candle": (0.95, 0.9), "museum": (1.15, 0.55), "lamp": (1.3, 0.7), "night": (1.2, 0.8), "studio": (2.6, 0.3),
        "dawn": (2.2, 0.5), "noon": (2.4, 0.4), "dusk": (2.2, 0.5), "overcast": (3.0, 0.3)}
# linear albedo of the place's surfaces (the exposure target on the lit surface follows from it)
ALBEDO = {"walnut": 0.06, "wood": 0.06, "oak": 0.28, "marble": 0.58, "stone": 0.25, "slate": 0.012, "sand": 0.3,
          "plaster": 0.52, "velvet": 0.011}


def srgb(x): return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


GLOW = {"warm": (1.0, 0.72, 0.40), "gold": (1.0, 0.78, 0.35), "red": (1.0, 0.25, 0.15), "blue": (0.45, 0.65, 1.0), "white": (1.0, 0.97, 0.92)}


def lin(c): return M.lin3(c)


# ------------------------------------------------------------------ keys
def keys(owner, path, values, index=-1, frames=None):
    """keys only where a value changes (the first and last frame of every steady run), linear in between"""
    v = np.asarray(values, float)
    if v.ndim == 1: v = v[:, None]
    n = len(v)
    if np.ptp(v, axis=0).max() < 1e-7:
        val = v[0] if v.shape[1] > 1 else float(v[0, 0])
        if index >= 0: getattr(owner, path)[index] = float(v[0, 0])
        else: setattr(owner, path, tuple(val) if v.shape[1] > 1 else val)
        return 0
    ch = np.abs(np.diff(v, axis=0)).max(1) > 1e-7
    keep = sorted({0, n - 1} | set(np.nonzero(ch)[0].tolist()) | set((np.nonzero(ch)[0] + 1).tolist()))
    for i in keep:
        val = v[i] if v.shape[1] > 1 else float(v[i, 0])
        if index >= 0: getattr(owner, path)[index] = float(v[i, 0])
        else: setattr(owner, path, tuple(val) if v.shape[1] > 1 else val)
        owner.keyframe_insert(path, index=index, frame=i + 1)
    return len(keep)


def key_socket(node, values):
    if node is None: return
    keys(node.outputs[0], "default_value", values)


# ------------------------------------------------------------------ geometry
def link(ob, parent=None):
    if ob.name not in bpy.context.scene.collection.objects: bpy.context.scene.collection.objects.link(ob)
    if parent is not None: ob.parent = parent
    return ob


def bm_object(name, bm, parent, mats):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); link(ob, parent)
    for m in mats: me.materials.append(m)
    return ob


def box(name, w, d, h, parent, mat, z0=0.0, x=0.0, y=0.0, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((x + v.co.x * w, y + v.co.y * d, z0 + (v.co.z + 0.5) * h))
    ob = bm_object(name, bm, parent, [mat])
    ob.data.polygons.foreach_set("use_smooth", [False] * len(ob.data.polygons))
    if bevel > 0:
        b = ob.modifiers.new("bevel", "BEVEL"); b.width = bevel; b.segments = 3; b.limit_method = "ANGLE"
    return ob


def cylinder(name, r, h, parent, mat, z0=0.0, seg=48, x=0.0, y=0.0, bevel=0.0, wobble=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=h)
    ph = [P.jitter(name, k, math.pi) for k in range(3)]
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        f = 1 + wobble * (0.6 * math.sin(3 * a + ph[0]) + 0.3 * math.sin(5 * a + ph[1]) + 0.2 * math.sin(8 * a + ph[2]))
        v.co = Vector((x + v.co.x * f, y + v.co.y * f, z0 + v.co.z + h / 2))
    ob = bm_object(name, bm, parent, [mat])
    sm = [abs(p.normal.z) < 0.5 for p in ob.data.polygons]; ob.data.polygons.foreach_set("use_smooth", sm)
    if bevel > 0:
        b = ob.modifiers.new("bevel", "BEVEL"); b.width = bevel; b.segments = 4; b.limit_method = "ANGLE"
        try: b.harden_normals = True
        except Exception: pass
    return ob


def quad(name, w, d, z, parent, mat, cx=0.0, cy=0.0):
    bm = bmesh.new()
    vs = [bm.verts.new((cx + sx * w / 2, cy + sy * d / 2, z)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm.faces.new(vs)
    return bm_object(name, bm, parent, [mat])


def sphere(name, r, parent, mat, at=(0, 0, 0), scale=(1, 1, 1)):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
    for v in bm.verts: v.co = Vector((at[0] + v.co.x * scale[0], at[1] + v.co.y * scale[1], at[2] + v.co.z * scale[2]))
    ob = bm_object(name, bm, parent, [mat]); ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
    return ob


def curl(m, x, y):
    """height of a sheet above its support: the edges lift a little, the corners most"""
    L = max(m["w"], m["d"]); doc = m["noun"] == "sheet"
    a, b = np.abs(2 * x / m["w"]), np.abs(2 * y / m["d"])
    return L * ((0.016 if doc else 0.010) * (0.7 * a ** 3 + 0.3 * b ** 3) + (0.012 if doc else 0.006) * (a * b) ** 4)


def sheet_mesh(name, m, parent, mats):
    nx, ny = 64, max(8, int(64 * m["d"] / m["w"]))
    xs, ys = np.linspace(-m["w"] / 2, m["w"] / 2, nx + 1), np.linspace(-m["d"] / 2, m["d"] / 2, ny + 1)
    X, Y = np.meshgrid(xs, ys)
    Z = m["h"] + curl(m, X, Y)
    co = np.stack([X, Y, Z], -1).reshape(-1, 3)
    idx = np.arange((nx + 1) * (ny + 1)).reshape(ny + 1, nx + 1)
    quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    ob = C.mesh_object(name, co, quads); ob.parent = parent
    for mt in mats: ob.data.materials.append(mt)
    so = ob.modifiers.new("thick", "SOLIDIFY"); so.thickness = m["h"]; so.offset = -1.0
    so.material_offset = 1; so.material_offset_rim = 1
    return ob


def text_object(name, words, size, parent, mat, extrude):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = words
    font = "Cinzel.ttf" if words.upper() == words else "CormorantGaramond.ttf"
    try: cu.font = bpy.data.fonts.load(os.path.join(FONTS, font), check_existing=True)
    except Exception as e: print("font:", e, flush=True)
    cu.size = size; cu.extrude = extrude; cu.bevel_depth = 0.12 * extrude; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu); link(ob, parent); cu.materials.append(mat)
    ob.location.z = extrude + 0.12 * extrude
    return ob


def local_size(objs):
    """footprint and height of objects parented to an empty at the origin (evaluated, with modifiers)"""
    bpy.context.view_layer.update()
    pts = []
    for ob in objs:
        for c in ob.bound_box: pts.append(ob.matrix_parent_inverse @ ob.matrix_basis @ Vector(c))
    a = np.array([[p.x, p.y, p.z] for p in pts])
    return a.min(0), a.max(0)


# ------------------------------------------------------------------ the stage
class Stage:
    def __init__(self, scene, data, meta, O):
        self.S, self.data, self.meta, self.O = scene, data, meta, O
        self.T = float(scene["seconds"]); self.n = int(round(self.T * P.FPS))
        self.place = scene["place"]["kind"]; self.mood = scene["light"]["mood"]
        self.cast = scene["cast"]; self.beats = scene.get("beats", []); self.cams = scene["camera"]
        self.errors, self.warnings = [], []
        self.sc = sc = C.reset(P.FPS)
        sc.frame_start, sc.frame_end = 1, self.n
        try: bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
        except Exception as e: print("interpolation preference:", e, flush=True)
        self.pics, self.objs, self.root, self.mats, self.nodes, self.lights, self.cones = [], {}, {}, {}, {}, [], []
        self.items = meta.get("items", {})
        self.unit, self.fixed, self.ground_fn, self.span, self.ground_obj, self.sky = 1.0, {}, None, None, None, None
        self.globes, self.models, self.model_parts, self.terrain_z, self.route_objs, self.rigs = {}, {}, {}, {}, [], []
        self.split_members = {b["who"] for b in self.beats if b["do"] in ("split", "assemble")}
        self.extra_split = {}
        for b in self.beats:
            if b["do"] in ("split", "assemble") and b.get("gap") is not None:
                self.extra_split.setdefault(b["who"], {})["gap"] = float(np.clip(b["gap"], 0.05, 1.5))
        self.fold_members = {b["who"] for b in self.beats if b["do"] in ("fold", "unfold")}
        geo = PR.data_json(self, "geo.json")
        self.tile_meta = geo.get("tiles") or {}; self.tiles = self.tile_meta.get("members", {})
        self.pieces = geo.get("pieces") or {}; self.terrains = geo.get("terrains") or {}; self.geo_routes = geo.get("routes") or {}
        self.geo_fly = geo.get("fly") or {}
        if self.place in ("terrain", "sea"): OD.load_place(self)
        self.make_cast()
        self.make_place()
        self.make_lights()
        self.animate()
        self.make_camera()
        OD.weather(self)
        for ob in self.sc.objects:                                      # lamps light the scene but are never seen as dots
            if ob.type == "LIGHT":
                try: ob.visible_camera = False
                except Exception as e: print("light visibility:", e, flush=True)

    # ---------------------------------------------------------- cast
    def src(self, name):
        s = str(self.cast[name].get("from", "none")); k, _, v = s.partition(":")
        return k, v

    def aspect(self, name):
        k, v = self.src(name)
        if k == "store" and self.cast[name]["is"] == "cutout" and ("cut:" + v) in self.items: return float(self.items["cut:" + v]["aspect"])
        if k == "store" and v in self.items and self.items[v].get("aspect"): return float(self.items[v]["aspect"])
        if self.cast[name]["is"] == "terrain" and name in self.terrains: return float(self.terrains[name]["aspect"])
        return None

    def make_cast(self):
        aspects = {n: self.aspect(n) for n in self.cast if self.aspect(n)}
        over = {}
        for n, c in self.cast.items():                                  # text: its real size decides the layout
            if c["is"] == "text":
                k, words = self.src(n)
                d = P.dims(c, None, self.unit); mt = M.solid(n, c.get("material", "gold"))
                e = self.empty(n)
                ob = text_object(f"{n}_text", words, d["L"], e, mt, 0.06 * d["L"])
                lo, hi = local_size([ob])
                over[n] = {"w": float(hi[0] - lo[0]), "d": float(hi[1] - lo[1]), "h": float(hi[2])}
                self.objs[n] = [(ob, "o")]; self.mats[n] = [mt]
        tl = [n for n, c in self.cast.items() if c["is"] == "tile"]
        self.tile_scale = max([P.dims(self.cast[n], None, self.unit)["L"] for n in tl] or [1.0])
        groups = {}
        for n in tl:                                                    # the tiles of one map keep their places
            D = self.tiles.get(n)
            if not D: continue
            S = self.tile_scale
            over[n] = {"w": D["w"] * S, "d": D["d"] * S, "h": 0.03 * S, "L": max(D["w"], D["d"]) * S}
            groups[n] = (D["cx"] * S, D["cy"] * S)
        for n, c in self.cast.items():                                  # an imported model: its real proportions
            if c["is"] == "model":
                holder, size = PR.model_import(self, n, P.dims(c, None, self.unit)["L"])
                if holder is not None:
                    self.models[n] = holder; over[n] = {"w": float(size[0]), "d": float(size[1]), "h": float(size[2])}
        self.L, errs = P.layout(self.cast, aspects, over, place=self.place, unit=self.unit, fixed=self.fixed, groups=groups)
        self.errors += errs
        if self.ground_fn is not None:                                  # on a region: members stand on its ground
            dz = {}
            for n, c in self.cast.items():
                wh = c.get("where")
                if wh and wh[1] != "place": continue
                fp = P.footprint(self.L[n]); z = float(np.max(self.ground_fn(fp[:, 0], fp[:, 1])))
                dz[n] = z - self.L[n]["z"]; self.L[n]["z"] = z
            for _ in range(len(self.cast)):                             # and what stands on them follows
                for n, c in self.cast.items():
                    wh = c.get("where")
                    if n not in dz and wh and wh[1] in dz: dz[n] = dz[wh[1]]; self.L[n]["z"] += dz[n]
        for n, c in self.cast.items():
            if c["is"] != "text": self.make_member(n, c, self.L[n])
        for n in self.cast:
            m = self.L[n]; e = self.root[n]
            e.location = (m["x"] + m["ox"], m["y"], m["z"] + m["oz"]); e.rotation_euler = (math.radians(m["rx0"]), 0, math.radians(m["rot"]))

    def empty(self, n):
        e = bpy.data.objects.new(f"{n}_root", None); link(e); self.root[n] = e
        return e

    def burn_from(self, n):
        for b in self.beats:
            if b["who"] == n and b["do"] == "burn": return b.get("from", "left")
        return "left"

    def builder(self, n, c):
        noun = c["is"]
        if noun in ("sheet", "print") and n in self.split_members: return PR.torn
        if noun in ("sheet", "print") and n in self.fold_members: return PR.sheet_folding
        return {"book": PR.book, "box": PR.chest, "globe": PR.globe, "cutout": PR.cutout, "model": PR.model, "cloth": PR.cloth,
                "wall": PR.wall, "tile": PR.tiles, "terrain": PR.terrain_block}.get(noun)

    def make_member(self, n, c, m):
        noun = c["is"]; e = self.root.get(n) or self.empty(n)
        fn = self.builder(n, c)
        if fn is not None:
            self.objs.setdefault(n, []); self.mats.setdefault(n, [])
            self.rigs += [(n, r) for r in (fn(self, n, c, m, e) or [])]
            return
        if m.get("upright"): m = dict(m, d=m["d0"], h=m["h0"])           # hung on a wall: built lying, the root stands it up
        kind, val = self.src(n); mat = c.get("material", MATERIAL.get(noun, "painted"))
        objs, mats = [], []
        if noun in ("sheet", "print"):
            pk = "parchment" if mat == "parchment" else "paper"
            if kind == "store":
                path = os.path.join(self.data, self.items[val]["file"])
                pm, nd = M.picture(n, path, m["w"], m["d"], m["iw"], m["ih"], kind=pk if noun == "sheet" else "print",
                                   sheen=noun == "print", burn_from=self.burn_from(n))
                back, bnd = M.paper(f"{n}_back", pk, m["w"], m["d"], self.burn_from(n))
                ob = sheet_mesh(n, m, e, [pm, back]); objs.append((ob, "i")); mats += [pm, back]
                self.pics.append({"member": n, "obj": ob, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0})
                self.nodes.setdefault(n, []).extend([nd, bnd])
            else:
                pm, nd = M.paper(n, pk, m["w"], m["d"], self.burn_from(n))
                ob = sheet_mesh(n, m, e, [pm, pm]); objs.append((ob, "o")); mats.append(pm)
                self.nodes.setdefault(n, []).append(nd)
        elif noun in ("canvas", "frame"):
            fm = M.solid(f"{n}_frame", mat if mat in M.METALS or mat in ("walnut", "oak", "wood") else "gold"); mats.append(fm)
            b = 0.07 * m["L"]; hh = m["h"]
            for i, (x, y, w, d) in enumerate(((0, -(m["d"] - b) / 2, m["w"], b), (0, (m["d"] - b) / 2, m["w"], b),
                                              (-(m["w"] - b) / 2, 0, b, m["d"] - 2 * b), ((m["w"] - b) / 2, 0, b, m["d"] - 2 * b))):
                objs.append((box(f"{n}_bar{i}", w, d, hh, e, fm, x=x, y=y, bevel=0.18 * b), "o"))
            if noun == "canvas" and kind == "store":
                path = os.path.join(self.data, self.items[val]["file"])
                pm, nd = M.picture(n, path, m["iw"], m["ih"], m["iw"], m["ih"], kind="paper", burn_from=self.burn_from(n))
                ob = quad(f"{n}_canvas", m["iw"], m["ih"], 0.55 * hh, e, pm); objs.append((ob, "i")); mats.append(pm)
                self.pics.append({"member": n, "obj": ob, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0})
                self.nodes.setdefault(n, []).append(nd)
        elif noun == "disc":
            wm = M.solid(n, mat, color=(0.50, 0.04, 0.04) if mat == "wax" else None); mats.append(wm)
            wax = mat == "wax"                                          # a poured seal: a spill of wax under a pressed disc
            if wax:
                objs.append((cylinder(f"{n}_spill", 0.5 * m["w"], 0.3 * m["h"], e, wm, seg=64, bevel=0.12 * m["h"], wobble=0.07), "o"))
                ob = cylinder(n, 0.4 * m["w"], m["h"], e, wm, seg=64, bevel=0.3 * m["h"], wobble=0.02)
            else: ob = cylinder(n, m["w"] / 2, m["h"], e, wm, seg=64, bevel=0.2 * m["h"])
            objs.append((ob, "o"))
            stamp = next((b for b in self.beats if b["who"] == n and b["do"] == "stamp"), None)
            if stamp:
                k2, v2 = str(stamp["with"]).partition(":")[::2]
                if k2 == "text" and v2:
                    rr = 0.4 * m["w"] if wax else 0.5 * m["w"]
                    mk = M.solid(f"{n}_mark", mat, color=(0.80, 0.13, 0.09) if wax else None); mats.append(mk)
                    to = text_object(f"{n}_mark", v2, 1.25 * rr / max(1.0, 0.62 * len(v2)), e, mk, 0.12 * m["h"])
                    to.location.z = m["h"] + 0.04 * m["h"]; objs.append((to, "o"))
                else:
                    self.errors.append(f'cast {n}: a stamp "with" a picture mark is not built yet in the workshop (use "text:...")')
        elif noun == "block":
            bm_ = M.solid(n, mat); mats.append(bm_)
            objs.append((box(n, m["w"], m["d"], m["h"], e, bm_, bevel=0.03 * m["L"]), "o"))
            if kind == "store":
                path = os.path.join(self.data, self.items[val]["file"])
                pm, nd = M.picture(n, path, m["iw"], m["ih"], m["iw"], m["ih"], kind="print", burn_from=self.burn_from(n))
                ob = quad(f"{n}_face", m["iw"], m["ih"], m["h"] + 0.0006, e, pm); objs.append((ob, "i")); mats.append(pm)
                self.pics.append({"member": n, "obj": ob, "iw": m["iw"], "ih": m["ih"], "path": path, "ox": 0.0, "oy": 0.0})
                self.nodes.setdefault(n, []).append(nd)
            elif kind == "text":
                light = mat in ("marble", "stone", "plaster", "sand", "paper", "parchment", "silver", "glass")
                gm = M.solid(f"{n}_letters", "painted", color=(0.045, 0.045, 0.05)) if light else M.solid(f"{n}_letters", "gold")
                mats.append(gm); dep = (0.0012 if light else 0.008) * m["L"]
                to = text_object(f"{n}_text", val, 0.24 * m["L"], e, gm, dep)
                lo, hi = local_size([to])
                s = min(1.0, 0.9 * m["w"] / max(hi[0] - lo[0], 1e-6), 0.62 * m["d"] / max(hi[1] - lo[1], 1e-6))
                to.scale = (s, s, 1.0); to.location.z = m["h"] + 1.12 * dep; objs.append((to, "o"))
        elif noun == "pole":                                            # proportions of a 1.8 m flagpole at any size
            pm = M.solid(n, mat); mats.append(pm); k = m["L"] / 1.8
            objs.append((cylinder(n, 0.016 * k, m["h"], e, pm, seg=24), "o"))
            objs.append((cylinder(f"{n}_foot", 0.09 * k, 0.025 * k, e, pm, seg=32, bevel=0.006 * k), "o"))
            gm = M.solid(f"{n}_finial", "brass"); mats.append(gm)
            objs.append((sphere(f"{n}_finial", 0.028 * k, e, gm, at=(0, 0, m["h"] + 0.02 * k)), "o"))
        elif noun == "plinth":
            pm = M.solid(n, mat); mats.append(pm); w = m["w"]
            objs.append((box(f"{n}_base", 1.12 * w, 1.12 * w, 0.06 * m["h"], e, pm, bevel=0.01), "o"))
            objs.append((box(n, w, w, 0.88 * m["h"], e, pm, z0=0.06 * m["h"], bevel=0.006), "o"))
            objs.append((box(f"{n}_cap", 1.08 * w, 1.08 * w, 0.06 * m["h"], e, pm, z0=0.94 * m["h"], bevel=0.01), "o"))
        elif noun == "table":
            tm = M.solid(n, mat); mats.append(tm); k = m["L"] / 1.4
            objs.append((box(f"{n}_top", m["w"], m["d"], 0.04 * k, e, tm, z0=m["h"] - 0.04 * k, bevel=0.008 * k), "o"))
            for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
                objs.append((box(f"{n}_leg{i}", 0.05 * k, 0.05 * k, m["h"] - 0.04 * k, e, tm, x=sx * (m["w"] / 2 - 0.07 * k),
                                 y=sy * (m["d"] / 2 - 0.07 * k)), "o"))
        elif noun == "candle":
            cm = M.solid(n, "wax", color=(0.92, 0.88, 0.78)); mats.append(cm); k = m["L"] / 0.16
            body = cylinder(n, 0.022 * k, m["h"], e, cm, seg=32, bevel=0.002 * k); objs.append((body, "o"))
            try: body.visible_shadow = False                           # wax lets its own flame through: no black ring at its foot
            except Exception: pass
            km = M.solid(f"{n}_wick", "painted", color=(0.03, 0.03, 0.03)); mats.append(km)
            objs.append((cylinder(f"{n}_wick", 0.0012 * k, 0.012 * k, e, km, z0=m["h"], seg=8), "o"))
            fl = M.flame(f"{n}_flame"); mats.append(fl)
            fo = sphere(f"{n}_flame", 0.006 * k, e, fl, at=(0, 0, m["h"] + 0.022 * k), scale=(1, 1, 2.6)); objs.append((fo, "o"))
            for vis in ("visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission"):
                try: setattr(fo, vis, False)
                except Exception: pass
            ld = bpy.data.lights.new(f"{n}_light", "POINT"); ld.color = (1.0, 0.62, 0.30); ld.shadow_soft_size = 0.008 * k
            lo_ = bpy.data.objects.new(f"{n}_light", ld); link(lo_, e); lo_.location = (0, 0, m["h"] + 0.045 * k)
            self.lights.append(("candle", n, lo_))
        else:
            self.errors.append(f'cast {n}: the workshop has no "{noun}" tool built yet')
        self.objs[n] = objs; self.mats[n] = mats

    # ---------------------------------------------------------- place
    def make_place(self):
        names = list(self.L)
        if names: pts = np.concatenate([P.box_points(self.L[k]) for k in names])
        else: pts = self.region_pts()
        lo, hi = pts.min(0), pts.max(0); self.lo, self.hi = lo, hi
        self.center = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0.0))
        self.L0 = max(0.35, float(math.hypot(hi[0] - lo[0], hi[1] - lo[1])), float(hi[2] - lo[2]))
        self.Lz = float(hi[2] - lo[2])
        self.R = max(8.0, 14.0 * self.L0)
        wd = bpy.data.worlds.new("world"); self.sc.world = wd; wd.use_nodes = True
        bg = wd.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (*LIGHT[self.mood]["world"], 1)
        bg.inputs["Strength"].default_value = 1.0
        self.surface = None; self.backdrop = None; self.albedo = None
        if self.S.get("output") == "over_map": OD.catcher(self)
        if self.place in ("terrain", "sea", "sky", "wall"): OD.place(self); return
        if self.place == "void": return
        sname = self.S["place"].get("surface") or SURFACE[self.place]
        self.albedo = ALBEDO.get(sname, 0.2)
        sm = M.surface(sname)
        self.surface = quad("surface", 2 * self.R, 2 * self.R, 0.0, None, sm, self.center.x, self.center.y)
        wm = M.Graph("room"); p = wm.node("ShaderNodeBsdfPrincipled", Roughness=0.9)
        p.inputs["Base Color"].default_value = (*lin((0.06, 0.058, 0.055) if self.place != "museum" else (0.07, 0.075, 0.085)), 1)
        wm = wm.finish(p.outputs[0], presence=False)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=96, radius1=0.95 * self.R, radius2=0.95 * self.R, depth=2 * self.R)
        for v in bm.verts: v.co = Vector((self.center.x + v.co.x, self.center.y + v.co.y, v.co.z + self.R))
        self.backdrop = bm_object("room", bm, None, [wm])

    def region_pts(self):
        """what to frame on a terrain or sea place without a cast: the region at its ground"""
        D = self.place_d; H, W = self.hm.shape; px = D["px_km"]; x1, y1 = (W - 1) / 2 * px, (H - 1) / 2 * px
        g = float(np.percentile(self.hm, 60)) / 1000.0 * D["ve"]
        return np.array([[sx * x1 * 0.8, sy * y1 * 0.8, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, max(g, 0.0))])

    # ---------------------------------------------------------- light
    def lit_by_beat(self, n): return any(b["who"] == n and b["do"] == "light" for b in self.beats)

    def spot(self, name, at, target, color, power, cover, blend):
        ld = bpy.data.lights.new(name, "SPOT"); ld.color = color; ld.energy = power; ld.shadow_soft_size = 0.06 * cover
        d = (Vector(target) - Vector(at)).length
        ld.spot_size = min(2.6, 2 * math.atan(0.75 * cover * 1.15 / max(d, 1e-3))); ld.spot_blend = blend
        ob = bpy.data.objects.new(name, ld); link(ob); ob.location = at; C.aim(ob, target)
        return ob

    def area(self, name, az, el, dist, size, color, E, target):
        """a large soft light at (az, el) from the target, giving irradiance E there (disk, lambertian)"""
        d = dist * self.L0; at = Vector(target) + d * Vector(P.cam_dir(el, az))
        ld = bpy.data.lights.new(name, "AREA"); ld.shape = "DISK"; ld.size = size * self.L0; ld.color = color
        ld.energy = E * math.pi * d * d * (1 + (ld.size / (2 * d)) ** 2)
        ob = bpy.data.objects.new(name, ld); link(ob); ob.location = at; C.aim(ob, target)
        return ob

    def make_lights(self):
        if self.place in P.OUTDOOR: OD.outdoor_lights(self); return
        Lt = LIGHT[self.mood]; self.dark_max = Lt["dark"]
        az, el, dist, size, col, share = Lt["key"]
        wall = self.place == "wall"
        if wall: az, el = float(np.clip(az, -140, -40)), min(el, 42.0)        # the key lights the face of the wall
        candle = next((n for kind, n, _ in self.lights if kind == "candle" and n), None)
        if candle:                                                      # the candle on the stage motivates the key
            m = self.L[candle]; v = Vector((m["x"], m["y"], 0)) - self.center
            if v.length > 1e-3: az = math.degrees(math.atan2(v.y, v.x))
        if any(b["do"] == "light" for b in self.beats): share *= DIM
        room = float(np.clip(A_ROOM / self.albedo, 1 / 8, 4)) if self.albedo else 1.0
        if self.albedo is not None and self.albedo < 0.03: self.dark_max = max(self.dark_max, 0.95)
        self.sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = room
        tgt = self.center + Vector((0, 0, 0.25 * self.Lz if not wall else 0.5 * (self.lo[2] + self.hi[2])))
        d = dist * self.L0; at = tgt + d * Vector(P.cam_dir(el, az))
        cover, blend = POOL[self.mood]
        self.key = self.spot("key", at, tgt, col, PAPER_LIGHT * share * d * d, cover * self.L0, blend)
        self.key.data.shadow_soft_size = 0.5 * size * self.L0; self.key.visible_glossy = False
        fcol, fsh = Lt["fill"]
        self.area("fill", az + 180, 30, 2.0, 1.5, fcol, share * fsh * E_PAPER * room, tgt).visible_glossy = False
        if Lt["rim"]:
            rcol, rsh = Lt["rim"]; d2 = 2.0 * self.L0; at2 = tgt + d2 * Vector(P.cam_dir(35, 70))
            ob = self.spot("rim", at2, tgt, rcol, PAPER_LIGHT * share * rsh * d2 * d2, self.L0, 0.6)
            ob.visible_glossy = False
        # exposure target: the lit surface near the cast as this light shows it (linear -> sRGB luma)
        if self.albedo is not None:
            inc = math.cos(math.radians(el)) * max(0.2, -math.sin(math.radians(az))) if wall else math.sin(math.radians(el))
            lin = self.albedo * (share * inc + share * fsh * 0.5 * room) * E_PAPER / math.pi
            lin += self.albedo * float(np.mean(Lt["world"])) * room
            self.target = round(srgb(lin), 3)
        else: self.target = 0.18
        self.share = share
        t = np.arange(self.n) / P.FPS
        for kind, n, ob in self.lights:
            if kind == "candle":                                        # a living flame: slow sway + quick flicker
                fl = 1 + 0.07 * np.sin(2 * np.pi * 1.3 * t) + 0.05 * np.sin(2 * np.pi * 3.7 * t + 1.1) + 0.03 * np.sin(2 * np.pi * 9.1 * t + 2.3)
                keys(ob.data, "energy", 0.05 * PAPER_LIGHT * 0.15 ** 2 * fl)
                if self.mood == "candle":
                    keys(self.key.data, "energy", self.key.data.energy * (1 + 0.5 * (fl - 1)))

    # ---------------------------------------------------------- motion
    def animate(self):
        self.ch, self.spots, self.labels, errs, self.extra = P.channels(self.L, self.beats, self.T)
        self.errors += errs
        for n, sp in self.extra["splits"].items(): self.L[n]["gap"] = sp["gap"]
        for i, wr in enumerate(self.extra["writes"]): PR.write(self, wr, i)
        for n, rig in self.rigs: rig(self.ch[n], self.extra)
        self.make_routes()
        for n, e in self.root.items():
            ch, m = self.ch[n], self.L[n]
            spin = 0.0 if n in self.globes else 1.0                    # a globe turns its Earth, not its stand
            keys(e, "location", np.stack([m["x"] + m["ox"] + ch["dx"], m["y"] + ch["dy"], m["z"] + m["oz"] + ch["dz"]], -1))
            keys(e, "rotation_euler", np.stack([math.radians(m["rx0"]) + ch["rx"], ch["ry"], math.radians(m["rot"]) + spin * ch["rz"]], -1))
            keys(e, "scale", np.stack([ch["sx"], ch["sy"], ch["sz"]], -1))
            if np.ptp(ch["dissolve"]) > 0:
                for mt in self.mats.get(n, []):
                    key_socket(M.add_dissolve(mt, 6.0 / max(m["L"], 0.05)), ch["dissolve"])
            for mt in self.mats.get(n, []): key_socket(M.presence_node(mt), ch["presence"])
            for nd in self.nodes.get(n, []):
                key_socket(nd["reveal"], ch["reveal"]); key_socket(nd["burn"], ch["burn"]); key_socket(nd["glow"], ch["glow"])
            if np.ptp(ch["glow"]) > 0:
                col = next((GLOW.get(b.get("color", "warm"), GLOW["warm"]) for b in self.beats if b["who"] == n and b["do"] == "glow"), GLOW["warm"])
                for mt in self.mats.get(n, []):
                    if mt.name.startswith(("pic_", "paper_")): continue
                    v = M.add_glow(mt, col); key_socket(v, 2.5 * ch["glow"])
                Lm = max(0.25, max(m["w"], m["d"]))
                ld = bpy.data.lights.new(f"{n}_glow", "POINT"); ld.color = col; ld.shadow_soft_size = 0.3 * Lm
                ob = bpy.data.objects.new(f"{n}_glow", ld); link(ob, e); ob.location = (0, 0, m["h"] + 0.5 * Lm)
                keys(ld, "energy", 0.12 * PAPER_LIGHT * (0.5 * Lm) ** 2 * ch["glow"])
            if np.ptp(ch["burn"]) > 0:                                 # the fire lights the room while it eats the sheet
                Lm = max(0.25, max(m["w"], m["d"]))
                ld = bpy.data.lights.new(f"{n}_fire", "POINT"); ld.color = (1.0, 0.45, 0.12); ld.shadow_soft_size = 0.05
                ob = bpy.data.objects.new(f"{n}_fire", ld); link(ob, e); ob.location = (0, 0, m["h"] + 0.35 * Lm)
                t = np.arange(self.n) / P.FPS; b = ch["burn"]
                on = ((b > 0.002) & (b < 0.995)).astype(float)
                fl = 1 + 0.25 * np.sin(2 * np.pi * 7.3 * t) + 0.15 * np.sin(2 * np.pi * 13.1 * t + 0.7)
                keys(ld, "energy", 0.15 * PAPER_LIGHT * (0.35 * Lm) ** 2 * on * fl * np.sin(np.pi * np.clip(b, 0, 1)) ** 0.5)
        for n, sp in self.spots.items():
            m = self.L[n]; Lm = max(0.25, max(m["w"], m["d"], m["h"] if m.get("upright") else 0.0))
            if m.get("upright"):                                       # a picture on the wall: lit from the front, a little above
                c = Vector((m["x"], m["y"] - m["d"] / 2, m["z"] + m["h"] / 2)); at = c + Vector((-0.3, -2.2, 0.8)) * Lm
            else:
                c = Vector((m["x"], m["y"], m["z"] + m["h"])); at = c + Vector((-0.35, -0.8, 2.2)) * Lm
            P0 = PAPER_LIGHT * (at - c).length_squared
            ob = self.spot(f"{n}_spot", at, c, (1.0, 0.9, 0.76), P0, Lm, 0.5)
            ob.data.shadow_soft_size = 0.15 * Lm; ob.visible_glossy = False
            keys(ob.data, "energy", P0 * sp["level"])
            self.cones.append((n, ob, at, (c - at).normalized(), ob.data.spot_size / 2))

    def make_routes(self):
        """lines drawn over a map tile, a terrain block, a globe or the ground of a terrain or sea place (points prepared
        with the scene data: projected to the piece they are drawn on)"""
        for r in self.extra["routes"]:
            pts = self.geo_routes.get(str(r["i"]))
            who = r["who"]
            if not pts: self.errors.append(f"route {r['i'] + 1} on {who}: its points are missing from the scene data"); continue
            P_ = np.asarray(pts, float)
            if who == "place":
                if self.ground_fn is None: self.errors.append("a route on the place needs a terrain or sea place"); continue
                z = self.ground_fn(P_[:, 0], P_[:, 1]) + 0.004 * self.span
                PR.route(self, r, np.c_[P_[:, :2], z], None, 0.0022 * self.span); continue
            m = self.L.get(who); noun = m["noun"] if m else None
            if noun == "tile":
                S = self.tile_scale; D = self.tiles[who]
                xy = P_[:, :2] * S - np.array([D["cx"] * S, D["cy"] * S])
                PR.route(self, r, np.c_[xy, np.full(len(xy), m["h"] + 0.004 * S)], self.root[who], 0.003 * S)
            elif noun == "terrain" and who in self.terrain_z:
                xs, ys, zs = self.terrain_z[who]; xy = P_[:, :2] * [m["w"], m["d"]]
                col = np.interp(xy[:, 0], xs, np.arange(len(xs))); row = np.interp(-xy[:, 1], -ys, np.arange(len(ys)))
                z = OD.bilinear(zs, row, col) + 0.006 * m["w"]
                PR.route(self, r, np.c_[xy, z], self.root[who], 0.003 * m["w"])
            elif noun == "globe" and who in self.globes:
                g = self.globes[who]; lon, lat = np.radians(P_[:, 0]), np.radians(P_[:, 1]); rr = 1.012 * g["r"]
                xyz = np.stack([rr * np.cos(lat) * np.cos(lon), rr * np.cos(lat) * np.sin(lon), rr * np.sin(lat)], -1)
                PR.route(self, r, xyz, g["sphere"], 0.008 * g["r"])
            else:
                self.errors.append(f'route {r["i"] + 1}: "who" must be a map tile, a terrain, a globe or "place" (a terrain or sea place)')

    # ---------------------------------------------------------- camera
    def make_camera(self):
        cd = bpy.data.cameras.new("cam"); cd.lens = P.LENS; cd.sensor_width = P.SENSOR; cd.sensor_fit = "HORIZONTAL"
        cd.clip_start = 0.01; cd.clip_end = max(4 * self.R, 10 * self.span if self.span else 0.0)   # outdoors: to the horizon
        cam = bpy.data.objects.new("cam", cd); link(cam); self.sc.camera = cam; self.cam = cam
        cam.rotation_mode = "QUATERNION"
        fly = {}
        for i, e in enumerate(sorted(self.cams, key=lambda x: x["t"])):
            if e["move"] == "fly":
                pts = self.geo_fly.get(str(i))
                if pts and self.ground_fn is not None: fly[i] = P.fly_path(pts, self.ground_fn, self.span)
                else: self.errors.append(f"camera {i + 1}: fly needs its path in the scene data and a terrain place")
        plan = P.camera(self.cams, self.L, self.ch, self.T, self.place, labels={x["who"] for x in self.labels}, fly=fly,
                        extra_pts=self.region_pts() if self.place in ("terrain", "sea") else [[0, 0, 0], [1, 1, 0.5]])
        self.plan = plan
        loc, rot, fd = [], [], []
        prev = None
        for fi in range(self.n):
            p = P.cam_pos(plan, fi); tg = plan["target"][fi]
            q = (Vector(tg) - Vector(p)).to_track_quat("-Z", "Y")
            if prev is not None and prev.dot(q) < 0: q.negate()
            prev = q; loc.append(p); rot.append((q.w, q.x, q.y, q.z))
            a, b, x = plan["focus"][fi]
            fa = self.member_center(a, fi) if a else None; fb = self.member_center(b, fi) if b else Vector(tg)
            f = (Vector(p) - fb).length if fa is None else (1 - x) * (Vector(p) - fa).length + x * (Vector(p) - fb).length
            fd.append(f)
        keys(cam, "location", np.array(loc)); keys(cam, "rotation_quaternion", np.array(rot))
        PR.route_widths(self)                                           # lines on a region: steady width on screen
        cd.dof.use_dof = True
        keys(cd.dof, "focus_distance", np.array(fd)); keys(cd.dof, "aperture_fstop", plan["fstop"])

    def member_center(self, n, fi):
        m, ch = self.L[n], self.ch[n]
        return Vector((m["x"] + ch["dx"][fi], m["y"] + ch["dy"][fi], m["z"] + ch["dz"][fi] + 0.5 * m["h"]))

    # ---------------------------------------------------------- measuring (preview)
    def bvh(self):
        """local BVH of every visible object of the cast (modifiers applied; transforms come from the frame)"""
        dg = bpy.context.evaluated_depsgraph_get(); self.sc.frame_set(1)
        self.B = []
        for n, objs in self.objs.items():
            for ob, code in objs:
                ev = ob.evaluated_get(dg)
                try: me = ev.to_mesh()
                except Exception as e: self.warnings.append(f"cast {n}: no mesh to measure ({e})"); continue
                me.calc_loop_triangles()
                vs = [v.co.copy() for v in me.vertices]; tris = [tuple(t.vertices) for t in me.loop_triangles]
                ev.to_mesh_clear()
                if not tris: continue
                pic = next((p for p in self.pics if p["obj"].name == ob.name), None)
                self.B.append({"member": n, "obj": ob, "code": code, "tree": BVHTree.FromPolygons(vs, tris), "pic": pic,
                               "V": np.array([[v.x, v.y, v.z, 1.0] for v in vs]), "tri": tris})
        if getattr(self, "ground_mesh", None) is not None:             # the ground of a terrain or sea place
            wc, fc = self.ground_mesh
            self.ground_tree = BVHTree.FromPolygons([Vector(v) for v in wc], [tuple(int(i) for i in f) for f in fc])

    def frame_mats(self, fi):
        for b in self.B:
            mw = b["obj"].matrix_world.copy(); b["mw"] = mw; b["iv"] = mw.inverted(); b["i3"] = b["iv"].to_3x3()

    def visible(self, n, fi): return self.ch[n]["presence"][fi] >= 0.5 and min(self.ch[n]["sx"][fi], self.ch[n]["sz"][fi]) > 0.05

    def cast_ray(self, o, d, fi):
        best, res = 1e30, None
        for b in self.B:
            if not self.visible(b["member"], fi): continue
            h = b["tree"].ray_cast(b["iv"] @ o, (b["i3"] @ d).normalized())
            if h[0] is None: continue
            dw = ((b["mw"] @ h[0]) - o).length
            if dw < best: best, res = dw, (b, h[0], dw)
        return res

    def lit_level(self, n, fi):
        sp = self.spots.get(n)
        return 1.0 if sp is None else float(sp["level"][fi])

    def classify(self, f):
        fi = f - 1; o, rows = C.cam_rays(self.sc, self.cam); self.frame_mats(fi)
        lit = [n for n in self.L if self.visible(n, fi) and self.lit_level(n, fi) >= 0.9]
        out = []
        for row in rows:
            s = ""
            for d in row:
                r = self.cast_ray(o, d, fi)
                if r is not None:
                    b, hp, _ = r; pic = b["pic"]; n = b["member"]
                    clean = self.ch[n]["burn"][fi] < 0.01 and self.ch[n]["reveal"][fi] >= 0.99
                    s += "i" if pic and clean and abs(hp.x + pic.get("ox", 0.0)) < pic["iw"] / 2 and abs(hp.y + pic.get("oy", 0.0)) < pic["ih"] / 2 else "o"; continue
                if self.place == "void": s += "b"; continue
                bc = OD.bg_code(self, o, d)
                if bc: s += bc; continue
                if self.place == "wall" and d.y > 1e-9:                # the wall: lit near the hung pieces
                    tw = -o.y / d.y; tf = (-o.z / d.z) if d.z < -1e-9 else 1e30
                    if tw < tf:
                        q = o + d * tw
                        near = any(abs(q.x - self.L[n]["x"]) < 0.5 * self.L[n]["w"] + 0.12 * self.L0 and
                                   abs(q.z - self.L[n]["z"] - 0.5 * self.L[n]["h"]) < 0.5 * self.L[n]["h"] + 0.12 * self.L0 for n in lit)
                        s += "r" if near else "d"; continue
                if d.z >= -1e-6:
                    s += "k" if self.backdrop else "v"; continue
                q = o + d * (-o.z / d.z)
                if (Vector((q.x, q.y, 0)) - self.center).length > 0.93 * self.R: s += "k"; continue
                if any(self.lit_level(n, fi) > 0.05 and (q - at).normalized().dot(ax) > math.cos(half) for n, _, at, ax, half in self.cones):
                    s += "p"; continue
                near = any((q.x - self.L[n]["x"]) ** 2 + (q.y - self.L[n]["y"]) ** 2 <
                           (0.5 * max(self.L[n]["w"], self.L[n]["d"]) + 0.12 * self.L0) ** 2 for n in lit)
                s += "r" if near else "d"
            out.append(s)
        return out

    def corners(self, n, fi, top=True):
        m = self.L[n]; e = self.root[n]; mw = e.matrix_world
        if m["rx0"] or m["ox"] or m["oz"]:                              # hung pieces and flags: their box in the world
            q = P.box_points(m, self.ch[n], fi)
            return [Vector(tuple(v)) for v in (q if top else q[::2])]
        pts = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            for z in ((0.0, m["h"]) if top else (0.0,)):
                pts.append(mw @ Vector((sx * m["w"] / 2, sy * m["d"] / 2, z)))
        return pts

    def moving(self, n, fi):
        ch = self.ch[n]; a, b = max(0, fi - 3), min(self.n - 1, fi + 3)
        return any(abs(ch[k][b] - ch[k][a]) > 1e-4 for k in ("dx", "dy", "dz", "rx", "ry", "rz", "sx", "sy", "sz", "presence"))

    def checks(self):
        """labels (tracks for the overlay), cast members cut by the frame or showing as a thin sliver while they are held,
        members passing through each other, pictures seen almost edge-on, a cast lost in a big empty frame"""
        sc, cam = self.sc, self.cam
        LAB = self.labels; tracks = {f"{x['who']}#{i}": [] for i, x in enumerate(LAB)}
        CHW = 0.5 * 45
        cut, sliver, lout, lover, overl, edgeon, cover = {}, {}, {}, {}, {}, {}, []
        support = {(n, c["where"][1]) for n, c in self.cast.items() if c.get("where") and c["where"][0] in ("on", "in")}
        support |= {(b["who"], b.get("on")) for b in self.beats if b["do"] == "stack"}
        for fr in range(1, self.n + 1):
            sc.frame_set(fr); fi = fr - 1; t = fi / P.FPS
            for i, lb in enumerate(LAB):
                n = lb["who"]; m = self.L[n]; e = self.root[n]
                pw = e.matrix_world @ Vector((-0.44 * m["w"], -m["d"] / 2 - 0.012, 0.0))
                v = world_to_camera_view(sc, cam, pw); px, py = v.x * 1920, (1 - v.y) * 1080 + 34
                on = lb["t0"] <= t < lb["t1"] and self.visible(n, fi)
                vis = on and 0.02 <= v.x <= 0.98 and 0.06 <= v.y <= 0.98 and v.z > 0
                key = f"{n}#{i}"; LW = 18 + CHW * len(lb["text"])
                if vis:
                    if px + LW > 0.97 * 1920 or py + 20 > 0.97 * 1080: lout.setdefault(key, []).append(round(t, 1))
                    for k2 in self.L:
                        if k2 != n and (k2, n) not in support and (n, k2) not in support and self.visible(k2, fi) and \
                                self.crosses(k2, fi, px, px + LW, py - 27, py + 20):
                            lover.setdefault(key, set()).add(k2)
                tracks[key].append([round(px, 1), round(py, 1), int(vis)])
            if fr % 3 and fr != self.n: continue
            # while the camera holds: the subject of the shot whole in the frame, and nothing small half in it
            # (during a camera move things cross the frame edge naturally; a big support such as a plinth may be cut)
            if not self.plan["steady"][fi]: continue
            subj = self.plan["subject"][fi]
            for p in self.pics:                                        # a picture turned almost edge-on shows as a line
                n = p["member"]
                if p.get("obj") is None or p.get("deforms") or p.get("pieces") or not self.visible(n, fi) or self.moving(n, fi): continue
                if self.ch[n]["open"][fi] not in (0.0, 1.0) or (self.L[n]["noun"] == "box" and self.ch[n]["open"][fi] > 0): continue
                mw = p["obj"].matrix_world; nrm = (mw.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
                vd = (mw.translation - cam.matrix_world.translation).normalized()
                if abs(nrm.dot(vd)) < 0.3: edgeon.setdefault(n, []).append(round(t, 1))
            if self.place not in P.OUTDOOR:                            # how much of the frame the cast fills
                bx = []
                for n in self.L:
                    if not self.visible(n, fi): continue
                    vs = [world_to_camera_view(sc, cam, p) for p in self.corners(n, fi)]
                    if any(p.z <= 0 for p in vs): continue
                    bx.append((min(p.x for p in vs), min(p.y for p in vs), max(p.x for p in vs), max(p.y for p in vs)))
                if bx:
                    x0 = max(0.0, min(b[0] for b in bx)); y0 = max(0.0, min(b[1] for b in bx))
                    x1 = min(1.0, max(b[2] for b in bx)); y1 = min(1.0, max(b[3] for b in bx))
                    cover.append((max(0.0, x1 - x0) * max(0.0, y1 - y0), round(t, 1)))
            for n in self.L:
                if not self.visible(n, fi) or self.moving(n, fi): continue
                vs = [world_to_camera_view(sc, cam, p) for p in self.corners(n, fi)]
                if any(p.z <= 0 for p in vs):
                    if subj in (None, n): cut.setdefault(n, []).append(round(t, 1))
                    continue
                x0, x1 = min(p.x for p in vs), max(p.x for p in vs); y0, y1 = min(p.y for p in vs), max(p.y for p in vs)
                small = (x1 - x0) < 0.5 and (y1 - y0) < 0.5
                if not (subj in (None, n) or small): continue
                if x0 < P.SAFE[0] or x1 > P.SAFE[1] or y0 < P.SAFE[2] or y1 > P.SAFE[3]:
                    fx = (min(x1, 1) - max(x0, 0)) / max(x1 - x0, 1e-6); fy = (min(y1, 1) - max(y0, 0)) / max(y1 - y0, 1e-6)
                    if 0 < min(fx, fy) < 0.35: sliver.setdefault(n, []).append(round(t, 1))
                    elif min(fx, fy) > 0: cut.setdefault(n, []).append(round(t, 1))
            if fr % 6 and fr != self.n: continue
            self.frame_mats(fi)
            vis = [b for b in self.B if self.visible(b["member"], fi)]
            W_, trees = {}, {}
            for b in vis:
                W = b["V"] @ np.array(b["mw"]).T; W_[id(b)] = W[:, :3]
                b["box"] = (W[:, :3].min(0) - 1e-4, W[:, :3].max(0) + 1e-4)

            def tree(b):
                if id(b) not in trees: trees[id(b)] = BVHTree.FromPolygons([Vector(v) for v in W_[id(b)]], b["tri"])
                return trees[id(b)]
            for i, a in enumerate(vis):
                for b in vis[i + 1:]:
                    na, nb = a["member"], b["member"]
                    if na == nb or (na, nb) in support or (nb, na) in support: continue
                    if (a["box"][0] > b["box"][1]).any() or (b["box"][0] > a["box"][1]).any(): continue
                    if tree(a).overlap(tree(b)): overl.setdefault(tuple(sorted((na, nb))), []).append(round(t, 1))
        names = [[f"{x['who']}#{i}", x["text"], ""] for i, x in enumerate(LAB)]
        self.label_json = {"fps": P.FPS, "frames": self.n, "tracks": tracks, "names": names}
        E, W = self.errors, self.warnings
        for k, v in tracks.items():
            s_ = sum(x[2] for x in v) / P.FPS
            if LAB and s_ < 1.0: W.append(f"label {k} visible only {s_:.1f} s")
        for k, ts in lout.items(): E.append(f"label {k} runs out of the frame ({ts[0]:.1f}-{ts[-1]:.1f} s): shorten it")
        for k, ks in lover.items(): E.append(f"label {k} crosses {', '.join(sorted(ks))}")
        for k, ts in sliver.items(): E.append(f"only a thin sliver of {k} shows at the frame edge ({ts[0]:.1f}-{ts[-1]:.1f} s)")
        for k, ts in cut.items(): E.append(f"{k} is cut by the frame edge while it is held ({ts[0]:.1f}-{ts[-1]:.1f} s)")
        for k, ts in overl.items(): E.append(f"{k[0]} and {k[1]} pass through each other ({ts[0]:.1f}-{ts[-1]:.1f} s)")
        for k, ts in edgeon.items(): E.append(f"the picture of {k} is seen almost edge-on while it is held ({ts[0]:.1f}-{ts[-1]:.1f} s)")
        if cover:
            a_, t_ = min(cover)
            if a_ < 0.12: W.append(f"the cast fills only {a_:.0%} of the frame at {t_:.1f} s (frame it closer)")
        return {"cut": cut, "sliver": sliver, "overlap": {f"{a}+{b}": v for (a, b), v in overl.items()}}

    def crosses(self, k, fi, x0, x1, y0, y1):
        q = [(p.x * 1920, (1 - p.y) * 1080, p.z) for p in (world_to_camera_view(self.sc, self.cam, c) for c in self.corners(k, fi, top=False))]
        if any(p[2] <= 0 for p in q): return False
        n = len(q); area = sum(q[j][0] * q[(j + 1) % n][1] - q[(j + 1) % n][0] * q[j][1] for j in range(n))
        for gx in np.linspace(x0, x1, 16):
            for gy in np.linspace(y0, y1, 4):
                if all(((q[(j + 1) % n][0] - q[j][0]) * (gy - q[j][1]) - (q[(j + 1) % n][1] - q[j][1]) * (gx - q[j][0])) * area >= 0
                       for j in range(n)): return True
        return False

    def fidelity(self, out, key_frames, ext):
        """rendered picture pixels against the picture files at the key frames where a picture is held lit and whole"""
        def pixels(path, alpha=False):
            im = bpy.data.images.load(os.path.abspath(path), check_existing=False)
            try: im.colorspace_settings.name = "Non-Color"
            except Exception: pass
            w_, h_ = im.size; a_ = np.empty(w_ * h_ * 4, np.float32); im.pixels.foreach_get(a_); bpy.data.images.remove(im)
            a_ = a_.reshape(h_, w_, 4)
            return a_ if alpha else a_[..., :3]
        lin_ = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0.0), 1 / 2.4) - 0.055)
        yl = lambda c: lin_(c) @ np.array([0.2126, 0.7152, 0.0722])
        imgs, seen = {}, {}
        acc = {p["member"]: [] for p in self.pics}; acc_all = {p["member"]: [] for p in self.pics}
        nx, ny = 160, 90
        for f in key_frames:
            fi = f - 1
            held = [p for p in self.pics if p.get("obj") is not None and not p.get("deforms") and not p.get("pieces")
                    and self.visible(p["member"], fi) and not self.moving(p["member"], fi)
                    and self.ch[p["member"]]["open"][fi] in (0.0, 1.0) and self.ch[p["member"]]["dissolve"][fi] < 1e-3
                    and self.ch[p["member"]]["reveal"][fi] >= 0.999 and self.ch[p["member"]]["burn"][fi] < 1e-3
                    and self.ch[p["member"]]["glow"][fi] < 1e-3 and abs(self.ch[p["member"]]["rx"][fi]) < 1e-3
                    and abs(self.ch[p["member"]]["ry"][fi]) < 1e-3]
            if not held: continue
            rend = pixels(os.path.join(out, f"p_{f:04d}{ext}"))[::-1]; rh, rw = rend.shape[:2]
            self.sc.frame_set(f); self.frame_mats(fi)
            for p in held:
                k = p["member"]
                if k not in imgs: imgs[k] = pixels(p["path"], alpha=bool(p.get("alpha")))     # a cut-out: only its opaque part counts
                fa = imgs[k]; mw = p["obj"].matrix_world
                cv = [world_to_camera_view(self.sc, self.cam, mw @ Vector((sx * p["iw"] / 2 - p.get("ox", 0.0), sy * p["ih"] / 2 - p.get("oy", 0.0), 0.0)))
                      for sx in (-1, 1) for sy in (-1, 1)]
                wpx = (max(q.x for q in cv) - min(q.x for q in cv)) * rw; hpx = (max(q.y for q in cv) - min(q.y for q in cv)) * rh
                by, bx = max(1, int(round(fa.shape[0] / max(hpx, 1.0)))), max(1, int(round(fa.shape[1] / max(wpx, 1.0))))
                if (k, by, bx) not in seen:
                    a = fa
                    if by > 1 or bx > 1:
                        h2, w2 = a.shape[0] // by * by, a.shape[1] // bx * bx
                        rgb_ = srgb(lin_(a[:h2, :w2, :3]).reshape(h2 // by, by, w2 // bx, bx, 3).mean(axis=(1, 3)))
                        if a.shape[2] == 4: rgb_ = np.concatenate([rgb_, a[:h2, :w2, 3:].reshape(h2 // by, by, w2 // bx, bx, 1).min(axis=(1, 3))], -1)
                        a = rgb_
                    seen[(k, by, bx)] = a
                fa = seen[(k, by, bx)]
                # rays only over the picture (a fine grid, so a small picture is measured as well as a big one)
                bu0, bu1 = max(0.0, min(q.x for q in cv)), min(1.0, max(q.x for q in cv))
                bv0, bv1 = max(0.0, 1 - max(q.y for q in cv)), min(1.0, 1 - min(q.y for q in cv))
                if bu1 - bu0 < 1e-3 or bv1 - bv0 < 1e-3: continue
                nx = 48; ny = int(np.clip(round(nx * (bv1 - bv0) * rh / max((bu1 - bu0) * rw, 1.0)), 8, 96))
                o, rows = C.cam_rays(self.sc, self.cam, nx, ny, box=(bu0, bv0, bu1, bv1))
                hk = np.zeros((ny, nx), bool); ex = np.zeros((ny, nx, 3), np.float32)
                for j, row in enumerate(rows):
                    for i_, d in enumerate(row):
                        r = self.cast_ray(o, d, fi)
                        if r is None or r[0]["obj"].name != p["obj"].name: continue
                        x, y = r[1].x + p.get("ox", 0.0), r[1].y + p.get("oy", 0.0)
                        if not (abs(x) < p["iw"] / 2 and abs(y) < p["ih"] / 2): continue
                        u, v = x / p["iw"] + 0.5, y / p["ih"] + 0.5
                        px_ = fa[min(max(int(v * fa.shape[0]), 0), fa.shape[0] - 1), min(max(int(u * fa.shape[1]), 0), fa.shape[1] - 1)]
                        if fa.shape[2] == 4 and px_[3] < 0.98: continue          # transparent part of a cut-out: what is behind shows
                        ex[j, i_] = px_[:3]
                        hk[j, i_] = True
                ok = hk.copy(); pk = np.pad(hk, 2, constant_values=False); pe = np.pad(ex, ((2, 2), (2, 2), (0, 0)))
                for dj in range(-2, 3):
                    for di in range(-2, 3): ok &= pk[2 + dj:2 + dj + ny, 2 + di:2 + di + nx]
                inner = ok.copy()
                for dj in range(-1, 2):
                    for di in range(-1, 2): ok &= np.abs(pe[2 + dj:2 + dj + ny, 2 + di:2 + di + nx] - ex).max(-1) < 0.04
                for j, i_ in zip(*np.nonzero(inner)):
                    r_ = rend[min(int((bv0 + (j + 0.5) / ny * (bv1 - bv0)) * rh), rh - 1), min(int((bu0 + (i_ + 0.5) / nx * (bu1 - bu0)) * rw), rw - 1)]
                    acc_all[k].append((r_, ex[j, i_]))
                    if ok[j, i_]: acc[k].append((r_, ex[j, i_]))
        res = {}

        def gain(r_, e_):
            br = yl(e_) >= 0.02
            if br.sum() < 12: return None, int(br.sum())
            return float(np.log2(max(yl(r_)[br].mean(), 1e-5) / max(yl(e_)[br].mean(), 1e-5))), int(br.sum())

        for k in acc:
            v, w_ = acc[k], acc_all[k]
            if len(w_) < 40 and len(v) < 12:
                self.warnings.append(f"picture {k}: not held lit and whole at a key frame, colours not measured"); continue
            if len(v) < 12:
                r_ = np.array([a for a, _ in w_]); e_ = np.array([b for _, b in w_]); evo, nb = gain(r_, e_)
                if evo is None: self.warnings.append(f"picture {k}: too dark to measure"); continue
                res[k] = {"ev_offset": round(evo, 3), "cells": len(w_), "mode": "all"}
                if abs(evo) > 0.25: self.errors.append(f"picture {k} renders off its true brightness ({evo:+.2f} EV)")
                continue
            r_ = np.array([a for a, _ in v]); e_ = np.array([b for _, b in v])
            dmed = float(np.median(np.abs(r_ - e_).max(-1)) * 255); evo, nb = gain(r_, e_)
            res[k] = {"median_diff": round(dmed, 1), "ev_offset": None if evo is None else round(evo, 3), "cells": len(v)}
            if dmed > 16 or (evo is not None and abs(evo) > 0.2):
                self.errors.append(f"picture {k} renders off its true colours (median difference {dmed:.0f}/255, {0.0 if evo is None else evo:+.2f} EV)")
            elif dmed > 9: self.warnings.append(f"picture {k} colours slightly off (median difference {dmed:.0f}/255)")
        return res
