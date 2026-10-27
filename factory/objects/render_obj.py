"""Blender: renders one 3D object as clean transparent pictures from several azimuths (the map-icon look: soft key,
fill and rim lights that turn with the camera so every azimuth is lit the same way, AgX medium-high contrast, no baked
ground shadow - the engine adds a soft contact shadow). The camera distance and lens shift are solved per view so the
object fills the same share of every frame, is centred and never touches the frame edge.
Inputs: a TripoSR mesh (.obj with vertex colours) or a GLB with its own materials and textures.
With --ref (the cut-out picture the object was made from) the colours follow the picture: the vertex colours of a
TripoSR mesh are matched to the picture's colour statistics (mean and spread of L*, a*, b* - TripoSR's colours come out
paler and flatter than the photograph), and the exposure is calibrated on a quick probe render so the object's mean
brightness equals the picture's.
usage: blender -b --python-exit-code 1 -P render_obj.py -- --mesh FILE --out DIR --name N [--res 768] [--samples 256]
       [--views 0,90,180,270] [--elev 32] [--fill 0.78] [--gpu OPTIX] [--ref PICTURE.png]
writes DIR/<name>_a<az>.png and DIR/<name>_render.json (mesh counts, size, colour source, framing per view)"""
import bpy, json, math, os, sys, time
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

a = sys.argv[sys.argv.index("--") + 1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
MESH, OUT, NAME = opt("--mesh"), opt("--out"), opt("--name")
RES, SAMPLES = int(opt("--res", 768)), int(opt("--samples", 256))
VIEWS = [int(v) for v in opt("--views", "0,90,180,270").split(",")]
ELEV, FILL, GPU = math.radians(float(opt("--elev", 32))), float(opt("--fill", 0.78)), opt("--gpu")
REF = opt("--ref")
os.makedirs(OUT, exist_ok=True)
T0 = time.time()


def die(msg):
    print("OBJECT ERROR:", msg, flush=True)
    json.dump({"error": msg}, open(os.path.join(OUT, f"{NAME}_render.json"), "w")); sys.exit(1)


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    if GPU:
        cp = bpy.context.preferences.addons["cycles"].preferences
        for typ in dict.fromkeys([GPU.upper(), "OPTIX", "CUDA"]):
            try:
                cp.compute_device_type = typ; cp.refresh_devices()
                if any(d.type == typ for d in cp.devices): break
            except Exception as e:
                print("gpu backend", typ, "unavailable:", e, flush=True)
        for d in cp.devices: d.use = d.type == cp.compute_device_type
        if any(d.use for d in cp.devices):
            sc.cycles.device = "GPU"
            print("GPU devices:", cp.compute_device_type, [d.name for d in cp.devices if d.use], flush=True)
    sc.cycles.samples = SAMPLES; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.01
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = RES; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "AgX"
    try: sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.85, 0.88, 0.95, 1); bg.inputs[1].default_value = 0.55
    return sc


sc = scene()
ext = os.path.splitext(MESH)[1].lower()
if ext == ".obj":
    bpy.ops.wm.obj_import(filepath=MESH, forward_axis="Y", up_axis="Z")       # TripoSR axes (the v5 icons)
elif ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=MESH)
else:
    die(f"unknown mesh format {ext}")
obs = [o for o in sc.objects if o.type == "MESH"]
if not obs: die("the file holds no mesh")
for o in list(sc.objects):
    if o.type != "MESH": continue
    o.select_set(True)
bpy.context.view_layer.objects.active = obs[0]
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
for o in list(sc.objects):
    if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
for o in obs: o.select_set(True)
bpy.context.view_layer.objects.active = obs[0]
if len(obs) > 1: bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data
if len(me.vertices) < 50: die(f"the mesh has only {len(me.vertices)} vertices")
xs = [v.co for v in me.vertices]
mn = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
mx = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
dims = mx - mn; size = max(dims); ctr = (mn + mx) / 2
for v in me.vertices:
    v.co = (v.co - Vector((ctr.x, ctr.y, mn.z))) * (2.0 / size)
me.update()
colour = "materials"
if ext == ".obj":
    bpy.ops.object.shade_smooth()
    mat = bpy.data.materials.new("M"); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.5
    if me.color_attributes:
        at = nt.nodes.new("ShaderNodeVertexColor"); at.layer_name = me.color_attributes[0].name
        hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = 1.15; hsv.inputs["Value"].default_value = 1.05
        nt.links.new(at.outputs["Color"], hsv.inputs["Color"]); nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
        colour = "vertex"
    else:
        bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1); colour = "none"
    me.materials.clear(); me.materials.append(mat)
elif not any(m for m in me.materials):
    colour = "none"
else:
    imgs = [n for m in me.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
    colour = "texture" if imgs else "materials"
bpy.context.view_layer.update()


def srgb_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_srgb(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0.0), 1 / 2.4) - 0.055)


XYZ = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]); WHITE = np.array([0.95047, 1.0, 1.08883])


def to_lab(srgb):
    xyz = srgb_lin(np.clip(srgb, 0, 1)) @ XYZ.T / WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], -1)


def from_lab(lab):
    fy = (lab[:, 0] + 16) / 116; fx = fy + lab[:, 1] / 500; fz = fy - lab[:, 2] / 200
    f = np.stack([fx, fy, fz], -1); xyz = np.where(f > 0.206893, f ** 3, (f - 16 / 116) / 7.787) * WHITE
    return np.clip(lin_srgb(np.clip(xyz @ np.linalg.inv(XYZ).T, 0, None)), 0, 1)


def image_px(path):
    """RGBA pixels of a PNG as stored (sRGB values, straight alpha)"""
    im = bpy.data.images.load(os.path.abspath(path), check_existing=False)
    try: im.colorspace_settings.name = "Non-Color"
    except Exception: pass
    a_ = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(a_); bpy.data.images.remove(im)
    return a_.reshape(-1, 4)


ref_px = None
if REF and os.path.exists(REF):
    q = image_px(REF); q = q[q[:, 3] > 0.5][:, :3]
    if len(q) > 200000: q = q[np.linspace(0, len(q) - 1, 200000).astype(int)]
    if len(q) >= 64: ref_px = q
colour_match = None
if ref_px is not None and colour == "vertex":                      # TripoSR colours -> the picture's colour statistics
    at = me.color_attributes[0]; nv = len(at.data)
    cs = np.empty(nv * 4, np.float32); at.data.foreach_get("color_srgb", cs); cs = cs.reshape(-1, 4)
    lv, lr = to_lab(cs[:, :3].astype(np.float64)), to_lab(ref_px.astype(np.float64))
    mv, sv, mr, sr = lv.mean(0), lv.std(0) + 1e-6, lr.mean(0), lr.std(0)
    gain = np.clip(sr / sv, [0.6, 0.5, 0.5], [4.0, 2.0, 2.0])
    cs[:, :3] = from_lab((lv - mv) * gain + mr); at.data.foreach_set("color_srgb", cs.ravel())
    me.update()
    colour_match = {"before": [round(float(x), 2) for x in np.r_[mv, sv]], "picture": [round(float(x), 2) for x in np.r_[mr, sr]],
                    "gain": [round(float(x), 3) for x in gain]}
    print("colour match (L a b mean | std): mesh", colour_match["before"], "picture", colour_match["picture"], flush=True)
    for nd in mat.node_tree.nodes:                                   # the picture's own saturation, no extra boost
        if nd.type == "HUE_SAT": nd.inputs["Saturation"].default_value = 1.0; nd.inputs["Value"].default_value = 1.0

# light rig (the v5 icon lights, as seen from azimuth 270) turned with the camera
RIG = [("key", (3.5, -3.0, 5.0), 900, 3.0, (1.0, 0.96, 0.9)), ("fill", (-4.0, -2.0, 2.5), 250, 4.0, (0.85, 0.9, 1.0)),
       ("rim", (-1.0, 4.5, 3.5), 450, 2.0, (1, 1, 1))]
lights = []
for name, loc, power, sz, col in RIG:
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = power; ld.size = sz; ld.color = col
    lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo)
    try: lo.visible_camera = False
    except Exception: pass
    lights.append((lo, Vector(loc)))
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 70; cam.data.sensor_fit = "AUTO"
hgt = max(v.co.z for v in me.vertices)
target = Vector((0, 0, hgt / 2))
# points that bound the projection: the 8 box corners + every k-th vertex (exact enough, fast on big meshes)
step = max(1, len(me.vertices) // 6000)
P = [ob.matrix_world @ me.vertices[i].co for i in range(0, len(me.vertices), step)]


def place(az, dist):
    A = math.radians(az - 90)
    cam.location = target + Vector((dist * math.cos(ELEV) * math.cos(A), dist * math.cos(ELEV) * math.sin(A), dist * math.sin(ELEV)))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


def extent():
    q = [world_to_camera_view(sc, cam, p) for p in P]
    if any(c.z <= 0 for c in q): return None
    x0, x1 = min(c.x for c in q), max(c.x for c in q); y0, y1 = min(c.y for c in q), max(c.y for c in q)
    return x0, y0, x1, y1


info = {"name": NAME, "verts": len(me.vertices), "faces": len(me.polygons), "dims": [round(d / size, 4) for d in dims],
        "colour": colour, "views": {}, "colour_match": colour_match}


def mean_lum(px):
    return float((srgb_lin(np.clip(px[:, :3], 0, 1)) @ np.array([0.2126, 0.7152, 0.0722])).mean())


calibrated = ref_px is None
for az in VIEWS:
    for lo, loc in lights:
        r = math.radians(az - 270)
        lo.location = Vector((loc.x * math.cos(r) - loc.y * math.sin(r), loc.x * math.sin(r) + loc.y * math.cos(r), loc.z))
        lo.rotation_euler = (Vector((0, 0, 0.6)) - lo.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.shift_x = cam.data.shift_y = 0.0
    lo_d, hi_d = 1.5, 60.0
    for _ in range(40):                                   # distance at which the object spans FILL of the frame
        mid = (lo_d + hi_d) / 2; place(az, mid); e = extent()
        if e is None or max(e[2] - e[0], e[3] - e[1]) > FILL: lo_d = mid
        else: hi_d = mid
    place(az, hi_d)
    for _ in range(3):                                    # centre the object with the lens shift (no perspective change)
        e = extent()
        cam.data.shift_x += ((e[0] + e[2]) / 2 - 0.5); cam.data.shift_y += ((e[1] + e[3]) / 2 - 0.5)
        bpy.context.view_layer.update()
    e = extent()
    if not calibrated:                                    # exposure: the object as bright as the picture (probe renders)
        calibrated = True; target_l = mean_lum(ref_px); ev = 0.0
        res0, spp0 = sc.render.resolution_x, sc.cycles.samples
        sc.render.resolution_x = sc.render.resolution_y = 192; sc.cycles.samples = 24
        for _ in range(2):
            sc.render.filepath = os.path.join(OUT, f"{NAME}_probe.png"); bpy.ops.render.render(write_still=True)
            q = image_px(sc.render.filepath); q = q[q[:, 3] > 0.5]
            if len(q) < 64: break
            step = float(np.clip(math.log2(max(target_l, 1e-4) / max(mean_lum(q), 1e-4)), -2.0, 2.0))
            ev = float(np.clip(ev + step, -3.0, 3.0)); sc.view_settings.exposure = ev
            if abs(step) < 0.05: break
        sc.render.resolution_x = sc.render.resolution_y = res0; sc.cycles.samples = spp0
        try: os.remove(os.path.join(OUT, f"{NAME}_probe.png"))
        except OSError: pass
        info["exposure"] = round(ev, 3); print(f"exposure calibrated to the picture: {ev:+.2f} EV", flush=True)
    sc.render.filepath = os.path.join(OUT, f"{NAME}_a{az}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    info["views"][str(az)] = {"dist": round(hi_d, 3), "box": [round(v, 4) for v in e], "render_s": round(time.time() - t, 1)}
    print(f"rendered {NAME} a{az} in {time.time() - t:.1f}s (box {', '.join(f'{v:.3f}' for v in e)})", flush=True)
info["seconds"] = round(time.time() - T0, 1)
json.dump(info, open(os.path.join(OUT, f"{NAME}_render.json"), "w"), indent=1)
