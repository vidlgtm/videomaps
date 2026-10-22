"""Blender (Cycles) matryoshka sequence built on the Hunyuan3D-2 mesh:
mesh normalised -> front image projected as UVs -> lacquer material (wood inside) ->
clean bisect at the painted seam -> 4 nested dolls open one after another and line up.
Transparent background (alpha) for compositing in Remotion.
usage: blender -b -P matryoshka.py -- --model out/model --out frames --start 1 --end 330"""
import bpy, bmesh, sys, json, math, os
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
MD, OUT = arg("--model", "out/model"), arg("--out", "frames")
START, END = int(arg("--start", 1)), int(arg("--end", 330))
FRAMES, LEVELS, SC = 330, 4, 0.79
SEAM_Y_IMG = 905                      # painted seam row in the reference image
meta = json.load(open(f"{MD}/meta.json"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------- import & normalise ----------
path = next(f"{MD}/{f}" for f in ["matryoshka.glb", "matryoshka.obj"] if os.path.exists(f"{MD}/{f}"))
if path.endswith(".glb"): bpy.ops.import_scene.gltf(filepath=path)
else: bpy.ops.wm.obj_import(filepath=path)
meshes = [o for o in sc.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1: bpy.ops.object.join()
doll = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(sc.objects):
    if o != doll: bpy.data.objects.remove(o, do_unlink=True)
me = doll.data


def coords():
    c = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", c); return c.reshape(-1, 3)


def setc(c):
    me.vertices.foreach_set("co", c.astype(np.float32).ravel()); me.update()


c = coords()
ext = c.max(0) - c.min(0); ax = int(np.argmax(ext))
if ax != 2:                                   # make the long axis Z (swap + negate = proper rotation)
    c[:, [ax, 2]] = c[:, [2, ax]]; c[:, 0 if ax == 1 else 1] *= -1
c -= (c.max(0) + c.min(0)) / 2
z = c[:, 2]; hgt = z.max() - z.min()
r = np.hypot(c[:, 0], c[:, 1])
r_lo = r[z < z.min() + 0.03 * hgt].mean(); r_hi = r[z > z.max() - 0.03 * hgt].mean()
if r_hi > r_lo:                               # flat wide base must be at the bottom
    c[:, 2] *= -1; c[:, 1] *= -1
c[:, 2] -= c[:, 2].min()
c *= 2.0 / c[:, 2].max()                      # height = 2 units
setc(c)
print("faces before decimate", len(me.polygons))
if len(me.polygons) > 140000:
    m = doll.modifiers.new("dec", "DECIMATE"); m.ratio = 140000 / len(me.polygons)
    bpy.ops.object.modifier_apply(modifier="dec")
me.shade_smooth() if hasattr(me, "shade_smooth") else None

# ---------- planar front projection UVs (front = -Y) ----------
c = coords(); xmin, xmax = c[:, 0].min(), c[:, 0].max()
bx0, by0, bx1, by1 = meta["bbox"]; IW, IH = meta["img_w"], meta["img_h"]
uvl = me.uv_layers.new(name="front")
li = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", li)
p = c[li]
u = (bx0 + (p[:, 0] - xmin) / (xmax - xmin) * (bx1 - bx0)) / IW
v = 1 - (by0 + (2.0 - p[:, 2]) / 2.0 * (by1 - by0)) / IH
uvl.data.foreach_set("uv", np.stack([u, v], 1).astype(np.float32).ravel())

# ---------- material ----------
mat = bpy.data.materials.new("Lacquer"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; L = nt.links
bsdf = N["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.3
for k, val in (("Coat Weight", 0.7), ("Coat Roughness", 0.04)):
    if k in bsdf.inputs: bsdf.inputs[k].default_value = val
tex = N.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.abspath(f"{MD}/texture.png"))
uvn = N.new("ShaderNodeUVMap"); uvn.uv_map = "front"; L.new(uvn.outputs[0], tex.inputs[0])
tc = N.new("ShaderNodeTexCoord")
dot = N.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"; dot.inputs[1].default_value = (0, -1, 0)
L.new(tc.outputs["Normal"], dot.inputs[0])
fr = N.new("ShaderNodeMapRange"); fr.inputs["From Min"].default_value = 0.10; fr.inputs["From Max"].default_value = 0.45
L.new(dot.outputs["Value"], fr.inputs["Value"])
mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.inputs[6].default_value = (0.42, 0.012, 0.02, 1)
L.new(fr.outputs["Result"], mix.inputs[0]); L.new(tex.outputs["Color"], mix.inputs[7])
geo = N.new("ShaderNodeNewGeometry")
wood = N.new("ShaderNodeMix"); wood.data_type = "RGBA"; wood.inputs[7].default_value = (0.66, 0.47, 0.28, 1)
L.new(geo.outputs["Backfacing"], wood.inputs[0]); L.new(mix.outputs[2], wood.inputs[6])
L.new(wood.outputs[2], bsdf.inputs["Base Color"])
doll.data.materials.clear(); doll.data.materials.append(mat)

# ---------- clean bisect at the painted seam ----------
cut = 2.0 * (by1 - SEAM_Y_IMG) / (by1 - by0)
print("cut height", cut)
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, cut), plane_no=(0, 0, 1))
bm.to_mesh(me); bm.free()


def split(obj, keep_top):
    o = obj.copy(); o.data = obj.data.copy(); sc.collection.objects.link(o)
    b = bmesh.new(); b.from_mesh(o.data)
    kill = [f for f in b.faces if (f.calc_center_median().z > cut) != keep_top]
    bmesh.ops.delete(b, geom=kill, context="FACES"); b.to_mesh(o.data); b.free()
    return o


top0, bot0 = split(doll, True), split(doll, False)
bpy.data.objects.remove(doll, do_unlink=True)
# pivot of each half: base centre (origin at 0,0,0 already)
dolls = []
for k in range(LEVELS):
    s = SC ** k
    t = top0.copy(); b = bot0.copy()
    sc.collection.objects.link(t); sc.collection.objects.link(b)
    for o in (t, b): o.scale = (s, s, s)
    dolls.append({"top": t, "bot": b, "s": s})
bpy.data.objects.remove(top0, do_unlink=True); bpy.data.objects.remove(bot0, do_unlink=True)
width0 = (xmax - xmin)
xs = [0.0]
for k in range(1, LEVELS):
    xs.append(xs[-1] + width0 * (SC ** (k - 1)) / 2 + width0 * (SC ** k) / 2 + 0.22)


def key(o, f, loc=None, rot=None):
    if loc is not None: o.location = loc; o.keyframe_insert("location", frame=f)
    if rot is not None: o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=f)


for d in dolls:
    for o in (d["top"], d["bot"]): key(o, 1, (0, 0, 0), (0, 0, 0))
for k in range(LEVELS - 1):
    # v3 choreography - no interpenetration at any frame:
    # 1) the lid lifts straight up until it clears the head of the seated inner doll,
    # 2) it parks BEHIND its own base (out of the inner doll's column),
    # 3) only then the inner doll rises until its base clears the rim, slides right at that height, and lands,
    # 4) the lid comes back over the now-empty base and closes it.
    F = 34 + k * 78; d = dolls[k]; s_ = d["s"]; hk = 2.0 * s_; X = xs[k]; wk = width0 * s_
    lift = SC * hk - cut * s_ + 0.10 * hk
    back = 1.08 * wk
    rise = cut * s_ + 0.05 * hk
    key(d["top"], F, (X, 0, 0), (0, 0, 0))
    key(d["top"], F + 14, (X, 0, lift), (0, 0, 0))
    key(d["top"], F + 30, (X, back, lift + 0.12 * hk), (math.radians(14), 0, 0))
    key(d["top"], F + 54, (X, back, lift + 0.12 * hk), (math.radians(14), 0, 0))
    key(d["top"], F + 64, (X, 0, lift), (0, 0, 0))
    key(d["top"], F + 74, (X, 0, 0), (0, 0, 0))
    for j in range(k + 1, LEVELS):            # the inner doll carries all smaller dolls nested inside it
        for o in (dolls[j]["top"], dolls[j]["bot"]):
            key(o, F + 26, (X, 0, 0)); key(o, F + 42, (X, 0, rise))
            key(o, F + 54, (xs[k + 1], 0, rise)); key(o, F + 62, (xs[k + 1], 0, 0))
# ---------- camera, lights, shadow catcher ----------
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
tgt = bpy.data.objects.new("Tgt", None); sc.collection.objects.link(tgt)
cn = cam.constraints.new("TRACK_TO"); cn.target = tgt; cn.track_axis = "TRACK_NEGATIVE_Z"; cn.up_axis = "UP_Y"
XC = (xs[0] + xs[-1]) / 2
for f, cp, tp in [(1, (0, -6.8, 1.45), (0, 0, 1.0)), (70, (0.3, -6.4, 1.35), (0.25, 0, 0.95)),
                  (250, (XC, -9.6, 1.5), (XC, 0, 0.8)), (330, (XC, -9.3, 1.45), (XC, 0, 0.8))]:
    key(cam, f, cp); key(tgt, f, tp)
for ob in [cam, tgt] + [d[h] for d in dolls for h in ("top", "bot")]:
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"; kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def area(name, loc, energy, size, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.energy = energy; l.size = size; l.color = color
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    tr = o.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"


area("Key", (-3.5, -4.5, 4.5), 900, 3.5, (1.0, 0.95, 0.88))
area("Fill", (5.0, -3.5, 2.0), 300, 4.0, (0.85, 0.9, 1.0))
area("Rim", (1.0, 4.5, 4.0), 700, 2.5)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
floor = bpy.context.active_object; floor.is_shadow_catcher = True
wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True
wd.node_tree.nodes["Background"].inputs["Color"].default_value = (0.08, 0.08, 0.09, 1)
wd.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.fps = 30; sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.film_transparent = True
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 48; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.03
sc.cycles.use_denoising = True; sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
json.dump({"xs": xs, "levels": LEVELS, "open_frames": [34 + k * 78 for k in range(LEVELS - 1)], "fps": 30, "frames": FRAMES},
          open(os.path.join(os.makedirs(OUT, exist_ok=True) or OUT, "matryoshka_timing.json"), "w"))
for f in range(START, END + 1):
    sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f"f_{f:04d}")
    bpy.ops.render.render(write_still=True); print("rendered", f, flush=True)
