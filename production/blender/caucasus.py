"""Blender (Cycles) hero shot: fly-over of the real Caucasus terrain with glowing borders
(international borders, Chechnya, Abkhazia, South Ossetia). Also exports per-frame 2D
screen positions of places (with occlusion test) so Remotion can pin labels exactly.
usage: blender -b -P caucasus.py -- --data out/cauc --out frames --start 1 --end 300 [--labels-only]"""
import bpy, sys, json, math, os
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
DATA, OUT = arg("--data", "out/cauc"), arg("--out", "frames")
START, END = int(arg("--start", 1)), int(arg("--end", 300))
LABELS_ONLY = "--labels-only" in argv
FRAMES = 300
meta = json.load(open(f"{DATA}/meta.json"))
hm = np.load(f"{DATA}/height.npy")
H, W = hm.shape
U = 100.0                                   # pixels per Blender unit
VS = 2.6 / (meta["m_per_px"] * U)           # vertical exaggeration x2.6, metres -> units
SEA = -27.0                                 # Caspian surface; Black Sea bathymetry lies far below

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def h_at(col, row):
    c = np.clip(col, 0, W - 1.001); r = np.clip(row, 0, H - 1.001)
    c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int); fc, fr = c - c0, r - r0
    v = (hm[r0, c0] * (1 - fc) * (1 - fr) + hm[r0, c0 + 1] * fc * (1 - fr) + hm[r0 + 1, c0] * (1 - fc) * fr + hm[r0 + 1, c0 + 1] * fc * fr)
    return np.maximum(v, SEA - 400)


def world(col, row, dz=0.0):
    return Vector(((col - W / 2) / U, (H / 2 - row) / U, float(h_at(col, row)) * VS + dz))


# ---------- terrain ----------
STEP = 2
nx, ny = W // STEP, H // STEP
bpy.ops.mesh.primitive_grid_add(x_subdivisions=nx, y_subdivisions=ny, size=1.0)
terr = bpy.context.active_object; terr.name = "Terrain"
terr.scale = (W / U, H / U, 1); bpy.ops.object.transform_apply(scale=True)
me = terr.data
co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
cols = co[:, 0] * U + W / 2; rows = H / 2 - co[:, 1] * U
co[:, 2] = h_at(cols, rows) * VS
me.vertices.foreach_set("co", co.ravel()); me.update()
me.shade_smooth() if hasattr(me, "shade_smooth") else [setattr(p, "use_smooth", True) for p in me.polygons]

mat = bpy.data.materials.new("Hypso"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; L = nt.links
bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.92
geo = N.new("ShaderNodeNewGeometry"); sep = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Position"], sep.inputs[0])
mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = 5200 * VS
L.new(sep.outputs["Z"], mr.inputs["Value"])
ramp = N.new("ShaderNodeValToRGB"); L.new(mr.outputs["Result"], ramp.inputs["Fac"])
cr = ramp.color_ramp; cr.interpolation = "EASE"
stops = [(0.0, (0.30, 0.40, 0.20)), (0.05, (0.36, 0.45, 0.22)), (0.17, (0.46, 0.47, 0.27)), (0.33, (0.47, 0.39, 0.27)),
         (0.50, (0.42, 0.38, 0.35)), (0.57, (0.58, 0.56, 0.55)), (0.62, (0.93, 0.94, 0.96)), (1.0, (0.98, 0.98, 1.0))]
cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1)
cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
for pos, col in stops[1:-1]:
    e = cr.elements.new(pos); e.color = (*col, 1)
# steep slopes -> bare rock
sepn = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], sepn.inputs[0])
slope = N.new("ShaderNodeMapRange"); slope.inputs["From Min"].default_value = 0.80; slope.inputs["From Max"].default_value = 0.55
L.new(sepn.outputs["Z"], slope.inputs["Value"])
rock = N.new("ShaderNodeMix"); rock.data_type = "RGBA"; rock.inputs[7].default_value = (0.33, 0.31, 0.29, 1)
L.new(slope.outputs["Result"], rock.inputs[0]); L.new(ramp.outputs["Color"], rock.inputs[6])
noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 60; noise.inputs["Detail"].default_value = 8
L.new(geo.outputs["Position"], noise.inputs["Vector"])
mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs[0].default_value = 0.25
L.new(rock.outputs[2], mul.inputs[6]); L.new(noise.outputs["Color"], mul.inputs[7])
L.new(mul.outputs[2], bsdf.inputs["Base Color"])
terr.data.materials.append(mat)

# ---------- water ----------
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, SEA * VS))
wat = bpy.context.active_object; wat.scale = (W / U * 1.6, H / U * 1.6, 1)
wm = bpy.data.materials.new("Water"); wm.use_nodes = True
wb = wm.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.035, 0.12, 0.17, 1); wb.inputs["Roughness"].default_value = 0.18
wat.data.materials.append(wm)


# ---------- glowing borders draped on terrain ----------
def emis(name, rgb, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; n.remove(n["Principled BSDF"])
    e = n.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*rgb, 1); e.inputs["Strength"].default_value = strength
    m.node_tree.links.new(e.outputs[0], n["Material Output"].inputs[0]); return m


STY = {"intl": ((1.0, 0.86, 0.55), 6.0, 0.0065), "chechnya": ((1.0, 0.16, 0.12), 9.0, 0.009),
       "abkhaz": ((1.0, 0.55, 0.15), 7.0, 0.007), "south": ((1.0, 0.55, 0.15), 7.0, 0.007)}
for key, polylines in meta["lines"].items():
    rgb, st, bev = STY.get(key, ((1, 1, 1), 5.0, 0.006))
    cu = bpy.data.curves.new(f"B_{key}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = bev; cu.bevel_resolution = 2
    for pl in polylines:
        sp = cu.splines.new("POLY"); sp.points.add(len(pl) - 1)
        for i, (c, r) in enumerate(pl):
            v = world(c, r, 0.01); sp.points[i].co = (v.x, v.y, v.z, 1)
    ob = bpy.data.objects.new(f"B_{key}", cu); sc.collection.objects.link(ob)
    ob.data.materials.append(emis(f"E_{key}", rgb, st))

# ---------- light & world ----------
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 4.2; sun.data.angle = math.radians(2.0); sun.data.color = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(58), 0, math.radians(-110))   # light from WNW, 32 deg elevation
wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True
wd.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.68, 0.82, 1)
wd.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55

# ---------- camera path (grid px coords + height above sea in units) ----------
def P(lon, lat):
    N_ = 256 * 2 ** meta["zoom"]
    x = (lon + 180) / 360 * N_
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N_
    x0 = (meta["lon0"] + 180) / 360 * N_
    y0 = (1 - math.log(math.tan(math.radians(meta["lat1"])) + 1 / math.cos(math.radians(meta["lat1"]))) / math.pi) / 2 * N_
    return x - x0, y - y0


def wpt(lon, lat, z):
    c, r = P(lon, lat); return Vector(((c - W / 2) / U, (H / 2 - r) / U, z))


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 30; cam.data.clip_end = 400
tgt = bpy.data.objects.new("Tgt", None); sc.collection.objects.link(tgt)
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [  # frame, camera(lon,lat,z), target(lon,lat,z)
    (1, (38.7, 42.3, 1.15), (41.6, 43.4, 0.10)),
    (110, (40.9, 42.0, 0.95), (43.3, 43.2, 0.15)),
    (210, (43.2, 41.6, 1.00), (45.6, 43.1, 0.06)),
    (300, (45.0, 41.2, 1.30), (47.0, 43.0, 0.00)),
]
for f, cp, tp in KEYS:
    cam.location = wpt(*cp); cam.keyframe_insert("location", frame=f)
    tgt.location = wpt(*tp); tgt.keyframe_insert("location", frame=f)
for ob in (cam, tgt):
    for fc in ob.animation_data.action.fcurves:
        for k in fc.keyframe_points: k.interpolation = "BEZIER"; k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"

sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.fps = 30
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080

# ---------- per-frame label positions (with occlusion) ----------
if LABELS_ONLY:
    dg = bpy.context.evaluated_depsgraph_get()
    tracks = {}
    pts = {k: world(c, r, 0.03) for k, (c, r) in meta["places"].items()}
    for k in ("BLACK SEA", "CASPIAN SEA"):
        if k in pts: pts[k].z = SEA * VS + 0.02
    for f in range(1, FRAMES + 1):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        cpos = cam.matrix_world.translation
        for k, p in pts.items():
            v = world_to_camera_view(sc, cam, p)
            vis = 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0 and v.z > 0
            if vis:
                d = (p - cpos); dist = d.length
                hit, loc, *_ = sc.ray_cast(dg, cpos, d.normalized(), distance=dist - 0.05)
                vis = not hit
            tracks.setdefault(k, []).append([round(v.x * 1920, 1), round((1 - v.y) * 1080, 1), int(vis)])
    os.makedirs(OUT, exist_ok=True)
    json.dump({"fps": 30, "frames": FRAMES, "tracks": tracks}, open(f"{OUT}/caucasus_labels.json", "w"))
    print("labels written"); sys.exit(0)

# ---------- render ----------
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 40; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.03
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 4
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Base Contrast" if "AgX - Base Contrast" in [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items] else "None"
# aerial perspective via mist pass in the compositor
vl = sc.view_layers[0]; vl.use_pass_mist = True
wd.mist_settings.start = 2.0; wd.mist_settings.depth = 22.0; wd.mist_settings.falloff = "QUADRATIC"
sc.use_nodes = True
ct = sc.node_tree; ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers")
mix = ct.nodes.new("CompositorNodeMixRGB"); mix.inputs[2].default_value = (0.70, 0.79, 0.88, 1)
mf = ct.nodes.new("CompositorNodeMath"); mf.operation = "MULTIPLY"; mf.inputs[1].default_value = 0.55
ct.links.new(rl.outputs["Mist"], mf.inputs[0]); ct.links.new(mf.outputs[0], mix.inputs[0])
ct.links.new(rl.outputs["Image"], mix.inputs[1])
comp = ct.nodes.new("CompositorNodeComposite"); ct.links.new(mix.outputs[0], comp.inputs[0])
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.color_mode = "RGB"; sc.render.image_settings.quality = 95
os.makedirs(OUT, exist_ok=True)
for f in range(START, END + 1):
    sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f"f_{f:04d}")
    bpy.ops.render.render(write_still=True)
    print("rendered", f, flush=True)
