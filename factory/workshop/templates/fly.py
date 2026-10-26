"""Workshop template 'fly' - fly-over of any real region (Blender Cycles, GPU).
terrain: DEM mesh with vertical exaggeration; colour: Sentinel-2 cloudless, graded, snow lift on high gentle slopes;
sky: Nishita + sun; aerial perspective (mist); borders: glowing tubes draped on the terrain; labels: per-frame 2D
positions with an occlusion test (--labels-only) so the engine pins the names exactly.
usage: blender -b -P fly.py -- --params p.json --data <prep dir> --out <frames dir> --start 1 --end N [--gpu OPTIX] [--labels-only]
params: seconds; path [{t, cam: [lon, lat, alt_km], look: [lon, lat, alt_km]}, ...]; exaggeration; sea (m); snow [m0, m1];
        sun {elevation, azimuth}; styles {line key: preset | [r, g, b, strength, width]}; labels [[place, display, style]];
        lens; samples"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

P, arg, LABELS_ONLY = C.args()
DATA, OUT, GPU = arg("--data"), arg("--out", "frames"), arg("--gpu")
FRAMES = int(round(float(P.get("seconds", 10)) * 30))
START, END = int(arg("--start", 1)), int(arg("--end", FRAMES))
meta = json.load(open(f"{DATA}/meta.json"))
hm = np.load(f"{DATA}/height.npy")
H, W = hm.shape
U = float(meta.get("u", 400.0))
EX = float(P.get("exaggeration", 2.6))
VS = EX / (meta["m_per_px"] * U)
SEA = float(P.get("sea", 0.0))
WU = W / U
sc = C.reset()


def h_at(col, row):
    c = np.clip(col, 0, W - 1.001); r = np.clip(row, 0, H - 1.001)
    c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int); fc, fr = c - c0, r - r0
    v = (hm[r0, c0] * (1 - fc) * (1 - fr) + hm[r0, c0 + 1] * fc * (1 - fr) + hm[r0 + 1, c0] * (1 - fc) * fr + hm[r0 + 1, c0 + 1] * fc * fr)
    return np.maximum(v, SEA - 400)


def world(col, row, dz=0.0):
    return Vector(((col - W / 2) / U, (H / 2 - row) / U, float(h_at(col, row)) * VS + dz))


# ---------- terrain (about 5-8 M vertices)
STEP = max(2, int(round(math.sqrt(W * H / 7.0e6))))
nx, ny = W // STEP, H // STEP
bpy.ops.mesh.primitive_grid_add(x_subdivisions=nx, y_subdivisions=ny, size=1.0)
terr = bpy.context.active_object; terr.name = "Terrain"
terr.scale = (W / U, H / U, 1); bpy.ops.object.transform_apply(scale=True)
me = terr.data
co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
cols = co[:, 0] * U + W / 2; rows = H / 2 - co[:, 1] * U
co[:, 2] = h_at(cols, rows) * VS
me.vertices.foreach_set("co", co.ravel()); me.update()
C.smooth_shade(terr)

snow0, snow1 = [float(v) for v in P.get("snow", [3300, 4300])]
mat = bpy.data.materials.new("S2"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; L = nt.links
bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.88
tex = N.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.abspath(f"{DATA}/texture.jpg"))
tex.interpolation = "Cubic"; tex.extension = "EXTEND"
uvn = N.new("ShaderNodeUVMap"); L.new(uvn.outputs[0], tex.inputs[0])
hs = N.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = float(P.get("saturation", 1.12)); hs.inputs["Value"].default_value = 1.06
L.new(tex.outputs["Color"], hs.inputs["Color"])
bc = N.new("ShaderNodeBrightContrast"); bc.inputs["Contrast"].default_value = 0.10
L.new(hs.outputs["Color"], bc.inputs["Color"])
geo = N.new("ShaderNodeNewGeometry"); sep = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Position"], sep.inputs[0])
sepn = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], sepn.inputs[0])
hz = N.new("ShaderNodeMapRange"); hz.inputs["From Min"].default_value = snow0 * VS; hz.inputs["From Max"].default_value = snow1 * VS
L.new(sep.outputs["Z"], hz.inputs["Value"])
fl = N.new("ShaderNodeMapRange"); fl.inputs["From Min"].default_value = 0.55; fl.inputs["From Max"].default_value = 0.85
L.new(sepn.outputs["Z"], fl.inputs["Value"])
sm = N.new("ShaderNodeMath"); sm.operation = "MULTIPLY"; L.new(hz.outputs["Result"], sm.inputs[0]); L.new(fl.outputs["Result"], sm.inputs[1])
sm2 = N.new("ShaderNodeMath"); sm2.operation = "MULTIPLY"; sm2.inputs[1].default_value = 0.75; L.new(sm.outputs[0], sm2.inputs[0])
snow = N.new("ShaderNodeMix"); snow.data_type = "RGBA"; snow.inputs[7].default_value = (0.92, 0.94, 0.98, 1)
L.new(sm2.outputs[0], snow.inputs[0]); L.new(bc.outputs["Color"], snow.inputs[6])
L.new(snow.outputs[2], bsdf.inputs["Base Color"])
bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.002
bw = N.new("ShaderNodeRGBToBW"); L.new(tex.outputs["Color"], bw.inputs[0]); L.new(bw.outputs[0], bump.inputs["Height"])
L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
terr.data.materials.append(mat)

# ---------- water
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

# ---------- glowing lines draped on the terrain
PRESET = {"gold": ((1.0, 0.86, 0.55), 6.0, 0.0065), "red": ((1.0, 0.16, 0.12), 9.0, 0.009),
          "orange": ((1.0, 0.55, 0.15), 7.0, 0.007), "white": ((1.0, 0.97, 0.9), 6.0, 0.006), "blue": ((0.45, 0.75, 1.0), 7.0, 0.007)}
STY = {"intl": "gold"}; STY.update(P.get("styles", {}))
for key, polylines in meta["lines"].items():
    if not polylines: continue
    s = STY.get(key, "white")
    rgb, st, bev = PRESET[s] if isinstance(s, str) else (tuple(s[:3]), float(s[3]), float(s[4]))
    cu = bpy.data.curves.new(f"B_{key}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = bev * (WU / 23.0) ** 0.5; cu.bevel_resolution = 2
    for pl in polylines:
        sp = cu.splines.new("POLY"); sp.points.add(len(pl) - 1)
        for i, (c, r) in enumerate(pl):
            v = world(c, r, 0.01); sp.points[i].co = (v.x, v.y, v.z, 1)
    ob = bpy.data.objects.new(f"B_{key}", cu); sc.collection.objects.link(ob)
    ob.data.materials.append(C.emitter(f"E_{key}", rgb, st))

# ---------- light & world
SUN = P.get("sun", {})
el, az = float(SUN.get("elevation", 35)), float(SUN.get("azimuth", 155))
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 4.0; sun.data.angle = math.radians(0.9); sun.data.color = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(90 - el), 0, math.radians(az - 130))
wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True
sky = wd.node_tree.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "NISHITA"; sky.sun_disc = False; sky.sun_elevation = math.radians(el); sky.sun_rotation = math.radians(az)
    sky.altitude = 2000.0; sky.air_density = 1.0; sky.dust_density = 1.8; sky.ozone_density = 1.0
except Exception as e:
    print("sky fallback", e)
wd.node_tree.links.new(sky.outputs["Color"], wd.node_tree.nodes["Background"].inputs["Color"])
wd.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32

# ---------- camera path (lon, lat, altitude in km above the exaggerated sea level)
Nz = 256 * 2 ** meta["zoom"]
mxp = lambda lon: (lon + 180) / 360 * Nz
myp = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * Nz
gx0, gy0 = mxp(meta["lon0"]), myp(meta["lat1"])


def wpt(lon, lat, alt_km):
    c, r = mxp(lon) - gx0, myp(lat) - gy0
    return Vector(((c - W / 2) / U, (H / 2 - r) / U, float(alt_km) * 1000.0 * VS))


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = float(P.get("lens", 30)); cam.data.clip_end = 400
tgt = bpy.data.objects.new("Tgt", None); sc.collection.objects.link(tgt)
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
for k in P["path"]:
    f = 1 + round(float(k["t"]) * 30)
    cam.location = wpt(*k["cam"]); cam.keyframe_insert("location", frame=f)
    tgt.location = wpt(*k["look"]); tgt.keyframe_insert("location", frame=f)
C.bezier_keys([cam, tgt])
sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080

# ---------- per-frame label positions (with occlusion)
if LABELS_ONLY:
    LAB = P.get("labels", [])
    tracks = {}
    pts = {}
    for e in LAB:
        k = e[0]
        if k not in meta["places"]: print("WARNING: label place not in places:", k, flush=True); continue
        cc, rr = meta["places"][k]
        pts[k] = world(cc, rr, 0.03)
        if len(e) > 2 and e[2] == "sea": pts[k].z = SEA * VS + 0.02
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
    names = [[e[0], e[1] if len(e) > 1 else e[0], e[2] if len(e) > 2 else ""] for e in LAB if e[0] in pts]
    json.dump({"fps": 30, "frames": FRAMES, "tracks": tracks, "names": names}, open(f"{OUT}/labels.json", "w"))
    print("labels written", len(names), flush=True); sys.exit(0)

# ---------- render
C.setup_cycles(sc, GPU, samples=int(P.get("samples", 72)), look="AgX - Base Contrast")
vl = sc.view_layers[0]; vl.use_pass_mist = True
wd.mist_settings.start = 0.087 * WU; wd.mist_settings.depth = 0.96 * WU; wd.mist_settings.falloff = "QUADRATIC"
sc.use_nodes = True
ct = sc.node_tree; ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers")
mix = ct.nodes.new("CompositorNodeMixRGB"); mix.inputs[2].default_value = (0.66, 0.76, 0.88, 1)
mf = ct.nodes.new("CompositorNodeMath"); mf.operation = "MULTIPLY"; mf.inputs[1].default_value = float(P.get("haze", 0.48))
ct.links.new(rl.outputs["Mist"], mf.inputs[0]); ct.links.new(mf.outputs[0], mix.inputs[0])
ct.links.new(rl.outputs["Image"], mix.inputs[1])
comp = ct.nodes.new("CompositorNodeComposite"); ct.links.new(mix.outputs[0], comp.inputs[0])
print(f"built: terrain {len(me.vertices)} verts (step {STEP}), lines {len(meta['lines'])}, frames {START}-{END}", flush=True)
C.render_frames(sc, OUT, START, END)
