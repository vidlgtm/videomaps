"""v3 Blender (Cycles, GPU) hero shot: fly-over of the real Caucasus with real colour.
terrain : terrarium DEM z10 (~115 m), x2.6 vertical exaggeration, 5M-vertex mesh
colour  : Sentinel-2 cloudless 2016 (EOX, CC BY 4.0) z11 texture, graded; snow/rock lift on the high ridges
sky     : Nishita physical sky + sun from the SSE (matches the satellite illumination) + aerial-perspective mist
borders : glowing tubes draped on the terrain (international, Chechnya, Abkhazia, South Ossetia)
labels  : per-frame 2D positions with occlusion test (--labels-only) so Remotion pins the names exactly
usage: blender -b -P caucasus3.py -- --data out/cauc3 --out frames --start 1 --end 300 [--labels-only] [--gpu OPTIX]"""
import bpy, sys, json, math, os
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
DATA, OUT = arg("--data", "out/cauc3"), arg("--out", "frames")
GPU = arg("--gpu")
START, END = int(arg("--start", 1)), int(arg("--end", 300))
LABELS_ONLY = "--labels-only" in argv
FRAMES = 300
meta = json.load(open(f"{DATA}/meta.json"))
hm = np.load(f"{DATA}/height.npy")
H, W = hm.shape
U = float(meta.get("u", 100.0))             # grid pixels per Blender unit (v1 world scale kept)
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
STEP = 3
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

mat = bpy.data.materials.new("S2"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; L = nt.links
bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.88
tex = N.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.abspath(f"{DATA}/texture.jpg"))
tex.interpolation = "Cubic"; tex.extension = "EXTEND"
uvn = N.new("ShaderNodeUVMap"); L.new(uvn.outputs[0], tex.inputs[0])
hs = N.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 1.12; hs.inputs["Value"].default_value = 1.06
L.new(tex.outputs["Color"], hs.inputs["Color"])
bc = N.new("ShaderNodeBrightContrast"); bc.inputs["Contrast"].default_value = 0.10
L.new(hs.outputs["Color"], bc.inputs["Color"])
geo = N.new("ShaderNodeNewGeometry"); sep = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Position"], sep.inputs[0])
sepn = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], sepn.inputs[0])
# snow lift above ~3300 m on gentle slopes (the summer satellite mosaic under-represents the snow line)
hz = N.new("ShaderNodeMapRange"); hz.inputs["From Min"].default_value = 3300 * VS; hz.inputs["From Max"].default_value = 4300 * VS
L.new(sep.outputs["Z"], hz.inputs["Value"])
fl = N.new("ShaderNodeMapRange"); fl.inputs["From Min"].default_value = 0.55; fl.inputs["From Max"].default_value = 0.85
L.new(sepn.outputs["Z"], fl.inputs["Value"])
sm = N.new("ShaderNodeMath"); sm.operation = "MULTIPLY"; L.new(hz.outputs["Result"], sm.inputs[0]); L.new(fl.outputs["Result"], sm.inputs[1])
sm2 = N.new("ShaderNodeMath"); sm2.operation = "MULTIPLY"; sm2.inputs[1].default_value = 0.75; L.new(sm.outputs[0], sm2.inputs[0])
snow = N.new("ShaderNodeMix"); snow.data_type = "RGBA"; snow.inputs[7].default_value = (0.92, 0.94, 0.98, 1)
L.new(sm2.outputs[0], snow.inputs[0]); L.new(bc.outputs["Color"], snow.inputs[6])
L.new(snow.outputs[2], bsdf.inputs["Base Color"])
# micro relief from the DEM-scale normals is in the mesh; add a fine bump for crisp ridges
bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.002
bw = N.new("ShaderNodeRGBToBW"); L.new(tex.outputs["Color"], bw.inputs[0]); L.new(bw.outputs[0], bump.inputs["Height"])
L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
terr.data.materials.append(mat)

# ---------- water ----------
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, SEA * VS))
wat = bpy.context.active_object; wat.scale = (W / U * 1.6, H / U * 1.6, 1)
wm = bpy.data.materials.new("Water"); wm.use_nodes = True
wb = wm.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.018, 0.075, 0.105, 1); wb.inputs["Roughness"].default_value = 0.07
wn = wm.node_tree.nodes; wl = wm.node_tree.links
wz = wn.new("ShaderNodeTexNoise"); wz.inputs["Scale"].default_value = 900.0; wz.inputs["Detail"].default_value = 4.0
wbmp = wn.new("ShaderNodeBump"); wbmp.inputs["Strength"].default_value = 0.08; wl.new(wz.outputs["Fac"], wbmp.inputs["Height"])
wl.new(wbmp.outputs["Normal"], wb.inputs["Normal"])
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
sun.data.energy = 4.0; sun.data.angle = math.radians(0.9); sun.data.color = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(55), 0, math.radians(25))     # light from the SSE, 35 deg elevation (as the S2 mosaic)
wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True
sky = wd.node_tree.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "NISHITA"; sky.sun_disc = False; sky.sun_elevation = math.radians(35); sky.sun_rotation = math.radians(155)
    sky.altitude = 2000.0; sky.air_density = 1.0; sky.dust_density = 1.8; sky.ozone_density = 1.0
except Exception as e:
    print("sky fallback", e)
wd.node_tree.links.new(sky.outputs["Color"], wd.node_tree.nodes["Background"].inputs["Color"])
wd.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32

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
if GPU:
    cp = bpy.context.preferences.addons["cycles"].preferences
    for typ in dict.fromkeys([GPU.upper(), "OPTIX", "CUDA"]):
        try:
            cp.compute_device_type = typ; cp.refresh_devices()
            if any(d.type == typ for d in cp.devices): break
        except Exception as e: print("gpu backend", typ, "unavailable:", e, flush=True)
    for d in cp.devices: d.use = d.type == cp.compute_device_type
    print("GPU devices:", cp.compute_device_type, [d.name for d in cp.devices if d.use], flush=True)
    if any(d.use for d in cp.devices):
        sc.cycles.device = "GPU"
        try: sc.cycles.denoising_use_gpu = True
        except Exception: pass
sc.cycles.samples = 72; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True; sc.cycles.max_bounces = 4
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Base Contrast" if "AgX - Base Contrast" in [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items] else "None"
# aerial perspective via mist pass in the compositor
vl = sc.view_layers[0]; vl.use_pass_mist = True
wd.mist_settings.start = 2.0; wd.mist_settings.depth = 22.0; wd.mist_settings.falloff = "QUADRATIC"
sc.use_nodes = True
ct = sc.node_tree; ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers")
mix = ct.nodes.new("CompositorNodeMixRGB"); mix.inputs[2].default_value = (0.66, 0.76, 0.88, 1)
mf = ct.nodes.new("CompositorNodeMath"); mf.operation = "MULTIPLY"; mf.inputs[1].default_value = 0.48
ct.links.new(rl.outputs["Mist"], mf.inputs[0]); ct.links.new(mf.outputs[0], mix.inputs[0])
ct.links.new(rl.outputs["Image"], mix.inputs[1])
comp = ct.nodes.new("CompositorNodeComposite"); ct.links.new(mix.outputs[0], comp.inputs[0])
sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.color_mode = "RGB"; sc.render.image_settings.quality = 95
os.makedirs(OUT, exist_ok=True)
for f in range(START, END + 1):
    sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f"f_{f:04d}")
    bpy.ops.render.render(write_still=True)
    print("rendered", f, flush=True)
