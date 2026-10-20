"""Photoreal Caucasus fly-over v2 (Cycles): real 55 m terrain, Blue Marble colour + procedural rock/snow detail,
Nishita sky + low sun, aerial haze (mist pass), drifting cloud shadows, glowing borders.
usage: blender -b -P caucasus2.py -- --data out/cauc2 --out frames --start 1 --end 300 [--labels-only] [--probe]"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
DATA, OUT = arg("--data", "out/cauc2"), arg("--out", "frames")
S, E = int(arg("--start", 1)), int(arg("--end", 300))
LABELS_ONLY, PROBE = "--labels-only" in argv, "--probe" in argv
FRAMES, VE, SEA = 300, 1.5, -0.027
meta = json.load(open(f"{DATA}/meta.json"))
hm = np.load(f"{DATA}/height_mesh.npy")
Hm, Wm = hm.shape
WKM, HKM = meta["W"] * meta["mpp"] / 1000, meta["H"] * meta["mpp"] / 1000
N = 256 * 2 ** meta["zoom"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def bilinear(A, r, c):
    r = np.clip(r, 0, A.shape[0] - 1.001); c = np.clip(c, 0, A.shape[1] - 1.001)
    r0, c0 = np.floor(r).astype(np.int64), np.floor(c).astype(np.int64); fr, fc = r - r0, c - c0
    return A[r0, c0] * (1 - fr) * (1 - fc) + A[r0, c0 + 1] * (1 - fr) * fc + A[r0 + 1, c0] * fr * (1 - fc) + A[r0 + 1, c0 + 1] * fr * fc


def uv_of(lon, lat):
    mx = (lon + 180) / 360 * N
    my = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N
    return (mx - meta["x0"]) / (meta["x1"] - meta["x0"]), 1 - (my - meta["y0"]) / (meta["y1"] - meta["y0"])


def h_at_uv(u, v, spread=0.0):
    r, c = (1 - v) * (Hm - 1), u * (Wm - 1)
    if not spread: return float(bilinear(hm, np.array([r]), np.array([c]))[0])
    o = np.array([-spread, 0, spread])
    rr, cc = np.meshgrid(r + o, c + o)
    return float(bilinear(hm, rr.ravel(), cc.ravel()).max())


def P(lon, lat, alt_km=None, above=0.0, spread=0.0):
    u, v = uv_of(lon, lat)
    z = (h_at_uv(u, v, spread) / 1000 * VE + above) if alt_km is None else alt_km
    return Vector(((u - 0.5) * WKM, (v - 0.5) * HKM, z))


# ---------------- terrain ----------------
bpy.ops.mesh.primitive_grid_add(x_subdivisions=Wm - 1, y_subdivisions=Hm - 1, size=1, calc_uvs=True)
terr = bpy.context.active_object; terr.name = "Terrain"; me = terr.data
nv = len(me.vertices)
co = np.empty(nv * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
u, v = co[:, 0] + 0.5, co[:, 1] + 0.5
z = bilinear(hm, (1 - v) * (Hm - 1), u * (Wm - 1)) / 1000 * VE
co[:, 0], co[:, 1], co[:, 2] = (u - 0.5) * WKM, (v - 0.5) * HKM, z
me.vertices.foreach_set("co", co.ravel()); me.update()
if hasattr(me, "shade_smooth"): me.shade_smooth()
print("terrain verts", nv, "size km", round(WKM), round(HKM), flush=True)

mat = bpy.data.materials.new("Ground"); mat.use_nodes = True; nt = mat.node_tree; nd, lk = nt.nodes, nt.links
bsdf = nd["Principled BSDF"]
uvn = nd.new("ShaderNodeUVMap")
col = nd.new("ShaderNodeTexImage"); col.image = bpy.data.images.load(os.path.abspath(f"{DATA}/color.png")); col.interpolation = "Cubic"
lk.new(uvn.outputs["UV"], col.inputs["Vector"])
hsv = nd.new("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = 0.92; hsv.inputs["Value"].default_value = 1.12
lk.new(col.outputs["Color"], hsv.inputs["Color"])
geo = nd.new("ShaderNodeNewGeometry")
sep = nd.new("ShaderNodeSeparateXYZ"); lk.new(geo.outputs["Position"], sep.inputs["Vector"])
sepn = nd.new("ShaderNodeSeparateXYZ"); lk.new(geo.outputs["Normal"], sepn.inputs["Vector"])
elev = nd.new("ShaderNodeMath"); elev.operation = "MULTIPLY"; elev.inputs[1].default_value = 1000 / VE
lk.new(sep.outputs["Z"], elev.inputs[0])
noi = nd.new("ShaderNodeTexNoise"); noi.inputs["Scale"].default_value = 0.35; noi.inputs["Detail"].default_value = 8
lk.new(geo.outputs["Position"], noi.inputs["Vector"])
fine = nd.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 4.0; fine.inputs["Detail"].default_value = 6
lk.new(geo.outputs["Position"], fine.inputs["Vector"])
# elevation jitter for natural snow line
jit = nd.new("ShaderNodeMath"); jit.operation = "MULTIPLY_ADD"; jit.inputs[1].default_value = 700; jit.inputs[2].default_value = -350
lk.new(noi.outputs["Fac"], jit.inputs[0])
ej = nd.new("ShaderNodeMath"); ej.operation = "ADD"; lk.new(elev.outputs[0], ej.inputs[0]); lk.new(jit.outputs[0], ej.inputs[1])


def mr(src, a, b, smooth=True):
    m = nd.new("ShaderNodeMapRange"); m.interpolation_type = "SMOOTHSTEP" if smooth else "LINEAR"
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = a, b
    lk.new(src, m.inputs["Value"]); return m.outputs["Result"]


def mul(a, b):
    m = nd.new("ShaderNodeMath"); m.operation = "MULTIPLY"; lk.new(a, m.inputs[0]); lk.new(b, m.inputs[1]); return m.outputs[0]


def inv01(a):
    m = nd.new("ShaderNodeMath"); m.operation = "SUBTRACT"; m.inputs[0].default_value = 1.0; lk.new(a, m.inputs[1]); return m.outputs[0]


def mixc(fac, a, b):
    m = nd.new("ShaderNodeMix"); m.data_type = "RGBA"; lk.new(fac, m.inputs[0])
    (lk.new(a, m.inputs[6]) if not isinstance(a, tuple) else m.inputs[6].__setattr__("default_value", a))
    (lk.new(b, m.inputs[7]) if not isinstance(b, tuple) else m.inputs[7].__setattr__("default_value", b))
    return m.outputs[2]


snow = mul(mr(ej.outputs[0], 3050, 3500), mr(sepn.outputs["Z"], 0.50, 0.72))
rock = mul(inv01(mr(sepn.outputs["Z"], 0.60, 0.84)), mr(elev.outputs[0], 700, 1400))
# detail modulation of the satellite colour
det = nd.new("ShaderNodeMath"); det.operation = "MULTIPLY_ADD"; det.inputs[1].default_value = 0.35; det.inputs[2].default_value = 0.82
lk.new(fine.outputs["Fac"], det.inputs[0])
base = nd.new("ShaderNodeMix"); base.data_type = "RGBA"; base.blend_type = "MULTIPLY"; base.inputs[0].default_value = 1.0
lk.new(hsv.outputs["Color"], base.inputs[6])
cvt = nd.new("ShaderNodeCombineColor"); [lk.new(det.outputs[0], cvt.inputs[i]) for i in range(3)]
lk.new(cvt.outputs["Color"], base.inputs[7])
rockc = mixc(fine.outputs["Fac"], (0.30, 0.27, 0.24, 1), (0.46, 0.42, 0.37, 1))
c1 = mixc(rock, base.outputs[2], rockc)
c2 = mixc(snow, c1, (0.93, 0.95, 0.98, 1))
lk.new(c2, bsdf.inputs["Base Color"])
rough = nd.new("ShaderNodeMath"); rough.operation = "MULTIPLY_ADD"; rough.inputs[1].default_value = -0.4; rough.inputs[2].default_value = 0.92
lk.new(snow, rough.inputs[0]); lk.new(rough.outputs[0], bsdf.inputs["Roughness"])
hf = nd.new("ShaderNodeTexImage"); hf.image = bpy.data.images.load(os.path.abspath(f"{DATA}/height_full.png"))
hf.image.colorspace_settings.name = "Non-Color"; hf.interpolation = "Cubic"; lk.new(uvn.outputs["UV"], hf.inputs["Vector"])
bump = nd.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.55; bump.inputs["Distance"].default_value = 6.0 * VE
lk.new(hf.outputs["Color"], bump.inputs["Height"]); lk.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
me.materials.append(mat)

# ---------------- Caspian water ----------------
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, SEA * VE)); wat = bpy.context.active_object
wat.scale = (WKM, HKM, 1)
wm = bpy.data.materials.new("Water"); wm.use_nodes = True; wb = wm.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.03, 0.12, 0.16, 1); wb.inputs["Roughness"].default_value = 0.12
wat.data.materials.append(wm)

# ---------------- sky, sun, clouds ----------------
w = bpy.data.worlds.new("Sky"); sc.world = w; w.use_nodes = True
sky = w.node_tree.nodes.new("ShaderNodeTexSky"); sky.sky_type = "NISHITA"; sky.sun_disc = False
SUN_EL, SUN_AZ = math.radians(17), math.radians(248)      # azimuth clockwise from north
sky.sun_elevation = SUN_EL; sky.sun_rotation = math.pi / 2 - SUN_AZ + math.pi
sky.altitude = 1500; sky.air_density = 1.0; sky.dust_density = 2.2; sky.ozone_density = 1.0
bgn = w.node_tree.nodes["Background"]; bgn.inputs["Strength"].default_value = 0.22
w.node_tree.links.new(sky.outputs["Color"], bgn.inputs["Color"])
sl = bpy.data.lights.new("Sun", "SUN"); sl.energy = 3.6; sl.angle = math.radians(1.2); sl.color = (1.0, 0.9, 0.78)
so = bpy.data.objects.new("Sun", sl); sc.collection.objects.link(so)
dirv = Vector((math.sin(SUN_AZ) * math.cos(SUN_EL), math.cos(SUN_AZ) * math.cos(SUN_EL), math.sin(SUN_EL)))  # toward the sun
so.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 7.5)); cl = bpy.context.active_object; cl.scale = (WKM * 1.6, HKM * 1.6, 1)
cm = bpy.data.materials.new("Clouds"); cm.use_nodes = True; cn = cm.node_tree.nodes; cl_l = cm.node_tree.links
for n_ in list(cn):
    if n_.type != "OUTPUT_MATERIAL": cn.remove(n_)
tr, df, mx_ = cn.new("ShaderNodeBsdfTransparent"), cn.new("ShaderNodeBsdfDiffuse"), cn.new("ShaderNodeMixShader")
cg = cn.new("ShaderNodeTexCoord"); cno = cn.new("ShaderNodeTexNoise"); cno.inputs["Scale"].default_value = 12.0; cno.inputs["Detail"].default_value = 6
cl_l.new(cg.outputs["Object"], cno.inputs["Vector"])
crm = cn.new("ShaderNodeMapRange"); crm.inputs["From Min"].default_value, crm.inputs["From Max"].default_value = 0.56, 0.66
cl_l.new(cno.outputs["Fac"], crm.inputs["Value"]); cl_l.new(crm.outputs["Result"], mx_.inputs[0])
cl_l.new(tr.outputs[0], mx_.inputs[1]); cl_l.new(df.outputs[0], mx_.inputs[2])
cl_l.new(mx_.outputs[0], cn["Material Output"].inputs["Surface"])
cl.data.materials.append(cm)
for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter"):
    setattr(cl, attr, False)
cl.visible_shadow = True

# ---------------- borders ----------------
B = json.load(open(f"{DATA}/borders.json"))


def emis(name, rgb, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; n_ = m.node_tree.nodes
    for x in list(n_):
        if x.type != "OUTPUT_MATERIAL": n_.remove(x)
    e = n_.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*rgb, 1); e.inputs["Strength"].default_value = strength
    m.node_tree.links.new(e.outputs[0], n_["Material Output"].inputs["Surface"]); return m


def polyline(name, pts, bev, mat_):
    dense = []
    for (a0, b0), (a1, b1) in zip(pts[:-1], pts[1:]):
        steps = max(1, int(math.hypot((a1 - a0) * 81, (b1 - b0) * 111) / 0.35))
        dense += [(a0 + (a1 - a0) * t / steps, b0 + (b1 - b0) * t / steps) for t in range(steps)]
    dense.append(tuple(pts[-1]))
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = bev; cu.bevel_resolution = 2
    sp = cu.splines.new("POLY"); sp.points.add(len(dense) - 1)
    for i, (lo, la) in enumerate(dense):
        p = P(lo, la, above=0.10, spread=1.5); sp.points[i].co = (p.x, p.y, p.z, 1)
    ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob); cu.materials.append(mat_)
    ob.visible_shadow = False


m_int, m_che = emis("BorderIntl", (1.0, 0.93, 0.82), 4.0), emis("BorderChe", (1.0, 0.42, 0.36), 6.5)
for i, ln in enumerate(B["intl"]): polyline(f"intl{i}", ln, 0.09, m_int)
for i, ring in enumerate(B["chechnya"]): polyline(f"che{i}", ring + [ring[0]], 0.12, m_che)

# ---------------- camera ----------------
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 28; cam.data.clip_start = 0.05; cam.data.clip_end = 1500
KEYS = [(1, (45.50, 44.32, 12.5), (45.68, 42.62, 2.4)),
        (150, (45.60, 43.98, 9.2), (45.78, 42.56, 2.7)),
        (300, (45.72, 43.58, 6.6), (45.86, 42.50, 3.0))]


def catmull(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def cam_at(f):
    ks = [(k[0], P(*k[1][:2], alt_km=k[1][2]), P(*k[2][:2], alt_km=k[2][2])) for k in KEYS]
    ks = [(ks[0][0] - 150, ks[0][1] * 2 - ks[1][1], ks[0][2] * 2 - ks[1][2])] + ks + [(ks[-1][0] + 150, ks[-1][1] * 2 - ks[-2][1], ks[-1][2] * 2 - ks[-2][2])]
    for i in range(1, len(ks) - 2):
        if ks[i][0] <= f <= ks[i + 1][0]:
            t = (f - ks[i][0]) / (ks[i + 1][0] - ks[i][0]); t = t * t * (3 - 2 * t) * 0.35 + t * 0.65
            return (catmull(ks[i - 1][1], ks[i][1], ks[i + 1][1], ks[i + 2][1], t), catmull(ks[i - 1][2], ks[i][2], ks[i + 1][2], ks[i + 2][2], t))
    return ks[-2][1], ks[-2][2]


for f in range(1, FRAMES + 1):
    pc, pt = cam_at(f)
    cam.location = pc; cam.rotation_euler = (pt - pc).to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    cl.location.x = -5 + 10 * f / FRAMES; cl.keyframe_insert("location", frame=f)      # drifting cloud shadows
sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.fps = 30
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080

# ---------------- labels (per-frame screen positions with terrain occlusion) ----------------
if LABELS_ONLY:
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(terr, dg)
    pts = {k: (P(lo, la, alt_km=SEA * VE + 0.03) if "SEA" in k else P(lo, la, above=0.05)) for k, (lo, la) in meta["places"].items()}
    tracks = {}
    for f in range(1, FRAMES + 1):
        sc.frame_set(f); cpos = cam.matrix_world.translation.copy()
        for k, p in pts.items():
            vv = world_to_camera_view(sc, cam, p)
            vis = 0.0 <= vv.x <= 1.0 and 0.0 <= vv.y <= 1.0 and vv.z > 0
            if vis:
                d = p - cpos; hit = bvh.ray_cast(cpos, d.normalized(), d.length - 0.08)
                vis = hit[0] is None
            tracks.setdefault(k, []).append([round(vv.x * 1920, 1), round((1 - vv.y) * 1080, 1), int(vis)])
    os.makedirs(OUT, exist_ok=True)
    json.dump({"fps": 30, "frames": FRAMES, "tracks": tracks}, open(f"{OUT}/caucasus2_labels.json", "w"))
    print("labels written"); sys.exit(0)

# ---------------- render settings + haze compositing ----------------
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 64; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 3; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 1; sc.cycles.transmission_bounces = 0
sc.cycles.volume_bounces = 0; sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass
sc.world.mist_settings.start, sc.world.mist_settings.depth, sc.world.mist_settings.falloff = 12.0, 190.0, "QUADRATIC"
bpy.context.view_layer.use_pass_mist = True
sc.use_nodes = True; tree = sc.node_tree
for n_ in list(tree.nodes): tree.nodes.remove(n_)
rl = tree.nodes.new("CompositorNodeRLayers"); comp = tree.nodes.new("CompositorNodeComposite")
mix = tree.nodes.new("CompositorNodeMixRGB"); mix.blend_type = "MIX"; mix.inputs[2].default_value = (0.70, 0.78, 0.88, 1)
fac = tree.nodes.new("CompositorNodeMath"); fac.operation = "MULTIPLY"; fac.inputs[1].default_value = 0.62
tree.links.new(rl.outputs["Mist"], fac.inputs[0]); tree.links.new(fac.outputs[0], mix.inputs[0])
tree.links.new(rl.outputs["Image"], mix.inputs[1])
last = mix.outputs[0]
try:
    gl = tree.nodes.new("CompositorNodeGlare"); gl.glare_type = "FOG_GLOW"
    for k_, v_ in (("threshold", 1.0), ("size", 7), ("quality", "HIGH")):
        try:
            setattr(gl, k_, v_); continue
        except Exception: pass
        try: gl.inputs[k_.capitalize()].default_value = v_
        except Exception: pass
    tree.links.new(last, gl.inputs[0]); last = gl.outputs[0]
except Exception as e:
    print("glare skipped", e)
tree.links.new(last, comp.inputs[0])
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"

EXPF = f"{DATA}/exposure.txt"
if PROBE:   # find the exposure that puts the mean display value at ~0.47 (deterministic, run once)
    sc.render.resolution_percentage = 25; sc.cycles.samples = 16; sc.cycles.use_denoising = False
    sc.frame_set(150); e = 0.0
    for it in range(4):
        sc.view_settings.exposure = e; sc.render.filepath = "/tmp/probe.png"; bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load("/tmp/probe.png", check_existing=False); px_ = np.array(im.pixels[:]).reshape(-1, 4)
        m = float((px_[:, :3] @ np.array([0.2126, 0.7152, 0.0722])).mean()); bpy.data.images.remove(im)
        print(f"probe it{it} exposure {e:+.2f} mean {m:.3f}", flush=True)
        e = max(-6, min(6, e + 2.0 * math.log2(0.47 / max(m, 1e-3))))
    open(EXPF, "w").write(f"{e:.3f}\n"); sys.exit(0)

sc.view_settings.exposure = float(open(EXPF).read()) if os.path.exists(EXPF) else 0.0
print("exposure", sc.view_settings.exposure, flush=True)
os.makedirs(OUT, exist_ok=True)
for f in range(S, E + 1):
    sc.frame_set(f); sc.render.filepath = f"{OUT}/f_{f:04d}.png"
    bpy.ops.render.render(write_still=True); print("rendered", f, flush=True)
