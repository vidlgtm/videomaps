"""Workshop template 'fly' - fly-over of any real region (Blender Cycles).
terrain : one mesh = the region at full detail + a coarse ring out to the horizon, stitched (no seam, no edge of the
          world); open sea under a water plane; colour = Sentinel-2 cloudless (region + ring), graded, snow on high
          gentle slopes
air     : aerial perspective inside the shaders toward the colour of the sky behind each point (the sky stays clean)
lines   : glowing border tubes draped on the terrain
labels  : per-frame 2D positions with an occlusion test, so the engine pins the names exactly
usage: blender -b -P fly.py -- --params p.json --data <prep dir> --out <dir> [--start 1 --end N --gpu OPTIX --ev X
       --budget-min M | --preview]
params: seconds; path [{t, cam: [lon, lat, alt_km], look: [lon, lat, alt_km]}...]; exaggeration; sea; snow [m0, m1];
        sun {elevation, azimuth}; styles {line key: preset | [r, g, b, strength, width]}; places {name: [lon, lat]};
        labels [[place, display, style]]; lens; samples; haze 0.2..1; saturation; look punchy | base"""
import bpy, os, sys, json, math, gc
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import terrain_mesh as TM

P, O = C.args()
DATA = O.data
FRAMES = int(round(float(P.get("seconds", 10)) * 30))
END = O.end or FRAMES
meta = json.load(open(f"{DATA}/meta.json"))
hz = np.load(f"{DATA}/height.npz")
SCL, OFF = float(hz["scale"]), float(hz["offset"])
hm = hz["main"].astype(np.float32) / SCL + OFF
hf = hz["far"].astype(np.float32) / SCL + OFF
del hz
H, W = hm.shape
FAR = meta["far"]
U = float(meta.get("u", 400.0))
EX = float(P.get("exaggeration", 2.6))
VS = EX / (meta["m_per_px"] * U)
SEA = float(P.get("sea", meta.get("sea", 0.0)))
WU = max(W, H) / U
HAZE = float(P.get("haze", 0.5))
MIST_S, MIST_D = 0.12 * WU, (3.0 - 1.7 * min(max(HAZE, 0.0), 1.0)) * WU
sc = C.reset()


def bil(a, c, r):
    c = np.clip(c, 0, a.shape[1] - 1.001); r = np.clip(r, 0, a.shape[0] - 1.001)
    c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int); fc, fr = c - c0, r - r0
    return (a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr) + a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)


def h_main(c, r): return np.maximum(bil(hm, c, r), SEA - 400)
def h_far(c, r): return np.maximum(bil(hf, (c - FAR["x0"]) / FAR["f"], (r - FAR["y0"]) / FAR["f"]), SEA - 400)


def h_at(c, r):
    c, r = np.asarray(c, np.float64), np.asarray(r, np.float64)
    inside = (c >= 0) & (c <= W - 1) & (r >= 0) & (r <= H - 1)
    return np.where(inside, h_main(c, r), h_far(c, r))


def world(col, row, dz=0.0):
    return Vector(((col - W / 2) / U, (H / 2 - row) / U, float(h_at(col, row)) * VS + dz))


def mist(d):
    return min(max((d - MIST_S) / MIST_D, 0.0), 1.0) ** 2


# ---------- terrain: region + ring, one mesh
STEP = max(2, int(math.ceil(math.sqrt(W * H / 5.5e6))))
SF = max(16, 8 * FAR["f"])
co, quads, tris = TM.assemble(W, H, STEP, FAR, SF, h_main, h_far)
wco = np.stack([(co[:, 0] - W / 2) / U, (H / 2 - co[:, 1]) / U, co[:, 2] * VS], 1)
quads, tris = TM.orient_up(wco, quads), TM.orient_up(wco, tris)
terr = C.mesh_object("Terrain", wco, quads, tris)
C.smooth_shade(terr)
NV = len(wco)
del co, wco, quads, tris
gc.collect()

# ---------- sky (world) + the same sky as a node group for the aerial perspective
SUN = P.get("sun", {})
el, az = float(SUN.get("elevation", 35)), float(SUN.get("azimuth", 155))
WSTR = 0.32


def sky_node(nt):
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "NISHITA"; sky.sun_disc = False; sky.sun_elevation = math.radians(el); sky.sun_rotation = math.radians(az)
        sky.altitude = 2000.0; sky.air_density = 1.0; sky.dust_density = 1.8; sky.ozone_density = 1.0
    except Exception as e:
        print("sky fallback", e)
    return sky


SKYG = bpy.data.node_groups.new("SkyCol", "ShaderNodeTree")
SKYG.interface.new_socket(name="Dir", in_out="INPUT", socket_type="NodeSocketVector")
SKYG.interface.new_socket(name="Color", in_out="OUTPUT", socket_type="NodeSocketColor")
gi, go = SKYG.nodes.new("NodeGroupInput"), SKYG.nodes.new("NodeGroupOutput")
sk = sky_node(SKYG); SKYG.links.new(gi.outputs[0], sk.inputs["Vector"]); SKYG.links.new(sk.outputs["Color"], go.inputs[0])
wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True
wsky = sky_node(wd.node_tree)
wd.node_tree.links.new(wsky.outputs["Color"], wd.node_tree.nodes["Background"].inputs["Color"])
wd.node_tree.nodes["Background"].inputs["Strength"].default_value = WSTR
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 4.0; sun.data.angle = math.radians(0.9); sun.data.color = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(90 - el), 0, math.radians(az - 130))

# ---------- terrain material: region texture inside, ring texture outside (by position), grade, snow, air
snow0, snow1 = [float(v) for v in P.get("snow", [3300, 4300])]
mat = bpy.data.materials.new("S2"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; L = nt.links
bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.88
tco = N.new("ShaderNodeTexCoord")


def mapped(sx, sy, ox, oy):
    m = N.new("ShaderNodeMapping"); m.inputs["Scale"].default_value = (sx, sy, 0.0); m.inputs["Location"].default_value = (ox, oy, 0.0)
    L.new(tco.outputs["Object"], m.inputs["Vector"]); return m


FWp, FHp = FAR["x1"] - FAR["x0"], FAR["y1"] - FAR["y0"]
m_main = mapped(U / W, U / H, 0.5, 0.5)
m_far = mapped(U / FWp, U / FHp, (W / 2 - FAR["x0"]) / FWp, 1 - (H / 2 - FAR["y0"]) / FHp)
t_main = N.new("ShaderNodeTexImage"); t_main.image = bpy.data.images.load(os.path.abspath(f"{DATA}/texture.jpg"))
t_main.interpolation = "Cubic"; t_main.extension = "EXTEND"; L.new(m_main.outputs[0], t_main.inputs[0])
t_far = N.new("ShaderNodeTexImage"); t_far.image = bpy.data.images.load(os.path.abspath(f"{DATA}/far.jpg"))
t_far.interpolation = "Linear"; t_far.extension = "EXTEND"; L.new(m_far.outputs[0], t_far.inputs[0])
sp = N.new("ShaderNodeSeparateXYZ"); L.new(tco.outputs["Object"], sp.inputs[0])


def edge_fac(comp, half):
    ab = N.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; L.new(sp.outputs[comp], ab.inputs[0])
    mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = half * 0.994; mr.inputs["From Max"].default_value = half
    mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0; mr.clamp = True
    L.new(ab.outputs[0], mr.inputs["Value"]); return mr


ex_, ey_ = edge_fac("X", (W - 1) / 2 / U), edge_fac("Y", (H - 1) / 2 / U)
inside = N.new("ShaderNodeMath"); inside.operation = "MULTIPLY"; L.new(ex_.outputs[0], inside.inputs[0]); L.new(ey_.outputs[0], inside.inputs[1])
cmix = N.new("ShaderNodeMix"); cmix.data_type = "RGBA"
L.new(inside.outputs[0], cmix.inputs[0]); L.new(t_far.outputs["Color"], cmix.inputs[6]); L.new(t_main.outputs["Color"], cmix.inputs[7])
hs = N.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = float(P.get("saturation", 1.3)); hs.inputs["Value"].default_value = 1.06
L.new(cmix.outputs[2], hs.inputs["Color"])
bc = N.new("ShaderNodeBrightContrast"); bc.inputs["Contrast"].default_value = 0.10; L.new(hs.outputs["Color"], bc.inputs["Color"])
geo = N.new("ShaderNodeNewGeometry"); sepn = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], sepn.inputs[0])
hzr = N.new("ShaderNodeMapRange"); hzr.inputs["From Min"].default_value = snow0 * VS; hzr.inputs["From Max"].default_value = snow1 * VS
L.new(sp.outputs["Z"], hzr.inputs["Value"])
fl = N.new("ShaderNodeMapRange"); fl.inputs["From Min"].default_value = 0.55; fl.inputs["From Max"].default_value = 0.85
L.new(sepn.outputs["Z"], fl.inputs["Value"])
sm = N.new("ShaderNodeMath"); sm.operation = "MULTIPLY"; L.new(hzr.outputs["Result"], sm.inputs[0]); L.new(fl.outputs["Result"], sm.inputs[1])
sm2 = N.new("ShaderNodeMath"); sm2.operation = "MULTIPLY"; sm2.inputs[1].default_value = 0.75; L.new(sm.outputs[0], sm2.inputs[0])
snow = N.new("ShaderNodeMix"); snow.data_type = "RGBA"; snow.inputs[7].default_value = (0.92, 0.94, 0.98, 1)
L.new(sm2.outputs[0], snow.inputs[0]); L.new(bc.outputs["Color"], snow.inputs[6])
L.new(snow.outputs[2], bsdf.inputs["Base Color"])
bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.002
bw = N.new("ShaderNodeRGBToBW"); L.new(cmix.outputs[2], bw.inputs[0]); L.new(bw.outputs[0], bump.inputs["Height"])
L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
terr.data.materials.append(mat)
C.add_fog(mat, SKYG, MIST_S, MIST_D, WSTR)

# ---------- water plane over the whole ring
ex0, ex1 = (FAR["x0"] - W / 2) / U * 1.05, (FAR["x1"] - W / 2) / U * 1.05
ey0, ey1 = (H / 2 - FAR["y1"]) / U * 1.05, (H / 2 - FAR["y0"]) / U * 1.05
wat = C.mesh_object("Water", np.array([[ex0, ey0, SEA * VS], [ex1, ey0, SEA * VS], [ex1, ey1, SEA * VS], [ex0, ey1, SEA * VS]]), quads=np.array([[0, 1, 2, 3]]))
wm = bpy.data.materials.new("Water"); wm.use_nodes = True
wb = wm.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.018, 0.075, 0.105, 1); wb.inputs["Roughness"].default_value = 0.07
wn = wm.node_tree.nodes; wl = wm.node_tree.links
wz = wn.new("ShaderNodeTexNoise"); wz.inputs["Scale"].default_value = 900.0; wz.inputs["Detail"].default_value = 4.0
wbmp = wn.new("ShaderNodeBump"); wbmp.inputs["Strength"].default_value = 0.08; wl.new(wz.outputs["Fac"], wbmp.inputs["Height"])
wl.new(wbmp.outputs["Normal"], wb.inputs["Normal"])
wat.data.materials.append(wm)
C.add_fog(wm, SKYG, MIST_S, MIST_D, WSTR)

# ---------- glowing lines draped on the terrain
PRESET = {"gold": ((1.0, 0.86, 0.55), 6.0, 0.0065), "red": ((1.0, 0.16, 0.12), 9.0, 0.009),
          "orange": ((1.0, 0.55, 0.15), 7.0, 0.007), "white": ((1.0, 0.97, 0.9), 6.0, 0.006), "blue": ((0.45, 0.75, 1.0), 7.0, 0.007)}
STY = {"intl": "gold"}; STY.update(P.get("styles", {}))
for key, polylines in meta["lines"].items():
    if not polylines: continue
    s = STY.get(key, "white")
    rgb, st, bev = PRESET[s] if isinstance(s, str) else (tuple(s[:3]), float(s[3]), float(s[4]))
    cu = bpy.data.curves.new(f"B_{key}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = bev * ((W / U) / 23.0) ** 0.5; cu.bevel_resolution = 2
    for pl in polylines:
        spl = cu.splines.new("POLY"); spl.points.add(len(pl) - 1)
        for i, (c, r) in enumerate(pl):
            v = world(c, r, 0.01); spl.points[i].co = (v.x, v.y, v.z, 1)
    ob = bpy.data.objects.new(f"B_{key}", cu); sc.collection.objects.link(ob)
    em = C.emitter(f"E_{key}", rgb, st); ob.data.materials.append(em)
    C.add_fog(em, SKYG, MIST_S, MIST_D, WSTR)

# ---------- camera path (lon, lat, altitude in km above the exaggerated sea level)
Nz = 256 * 2 ** meta["zoom"]
mxp = lambda lon: (lon + 180) / 360 * Nz
myp = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * Nz
gx0, gy0 = mxp(meta["lon0"]), myp(meta["lat1"])
px = lambda lon, lat: (mxp(lon) - gx0, myp(lat) - gy0)


def wpt(lon, lat, alt_km):
    c, r = px(lon, lat)
    return Vector(((c - W / 2) / U, (H / 2 - r) / U, float(alt_km) * 1000.0 * VS))


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = float(P.get("lens", 30))
cam.data.clip_end = 2.5 * math.hypot(FWp, FHp) / U
tgt = bpy.data.objects.new("Tgt", None); sc.collection.objects.link(tgt)
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
for k in P["path"]:
    f = 1 + round(float(k["t"]) * 30)
    cam.location = wpt(*k["cam"]); cam.keyframe_insert("location", frame=f)
    tgt.location = wpt(*k["look"]); tgt.keyframe_insert("location", frame=f)
C.bezier_keys([cam, tgt])
sc.frame_start, sc.frame_end = 1, FRAMES
# AgX Base is neutral but flat on satellite imagery; Punchy adds contrast + colour, the exposure is calibrated after it
C.setup_cycles(sc, O, samples=int(P.get("samples", 72)), look={"punchy": "AgX - Punchy", "base": "AgX - Base Contrast"}[P.get("look", "punchy")])
LOOK = {"punchy": "AgX - Punchy", "base": "AgX - Base Contrast"}[P.get("look", "punchy")]
if sc.view_settings.look != LOOK: raise SystemExit(f"colour look {LOOK!r} is not available (got {sc.view_settings.look!r})")
print(f"look {sc.view_settings.view_transform} / {sc.view_settings.look}", flush=True)
print(f"built: terrain {NV} verts (step {STEP}, ring {FAR['w']}x{FAR['h']} px), lines {len(meta['lines'])}", flush=True)

# ---------- preview: labels + checks + exposure calibration + key frames (CPU)
if O.preview:
    dg = bpy.context.evaluated_depsgraph_get()
    t_terr = BVHTree.FromObject(terr, dg)
    t_wat = BVHTree.FromObject(wat, dg)
    errors, warnings, stats = [], [], {}
    # labels (positions every frame, hidden when the terrain is in front)
    LAB = P.get("labels", []); places = P.get("places", {})
    pts = {}
    for e in LAB:
        if e[0] not in places: continue
        cc, rr = px(*places[e[0]])
        pts[e[0]] = world(cc, rr, 0.03)
        if len(e) > 2 and e[2] == "sea": pts[e[0]].z = SEA * VS + 0.02
    tracks, clear_min, clear_at = {}, 1e9, 0
    for f in range(1, FRAMES + 1):
        sc.frame_set(f)
        cpos = cam.matrix_world.translation.copy()
        ccol, crow = cpos.x * U + W / 2, H / 2 - cpos.y * U
        clear = (cpos.z / VS - float(h_at(ccol, crow))) / 1000.0
        if clear < clear_min: clear_min, clear_at = clear, f
        for k, p in pts.items():
            v = world_to_camera_view(sc, cam, p)
            vis = 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0 and v.z > 0
            if vis:
                d = p - cpos
                hit = t_terr.ray_cast(cpos, d.normalized(), d.length - 0.05)
                vis = hit[0] is None
            tracks.setdefault(k, []).append([round(v.x * 1920, 1), round((1 - v.y) * 1080, 1), int(vis)])
    names = [[e[0], e[1] if len(e) > 1 else e[0], e[2] if len(e) > 2 else ""] for e in LAB if e[0] in pts]
    json.dump({"fps": 30, "frames": FRAMES, "tracks": tracks, "names": names}, open(f"{O.out}/labels.json", "w"))
    vis_s = {k: round(sum(t[2] for t in v) / 30, 2) for k, v in tracks.items()}
    stats.update({"clear_km_min": round(clear_min, 2), "clear_frame": clear_at, "labels_visible_s": vis_s, "vertices": NV, "step": STEP})
    if clear_min < 1.0: errors.append(f"camera only {clear_min:.2f} km above the ground at frame {clear_at} (min 1 km)")
    for k, s in vis_s.items():
        if s < 1.0: warnings.append(f"label {k} visible only {s:.1f} s")
    near_lim = (FAR["f"] / U) / (2 * (36.0 / cam.data.lens) / 1920)     # where a ring texel covers 2 screen pixels
    fx0w, fx1w = (FAR["x0"] - W / 2) / U, (FAR["x1"] - W / 2) / U
    fy0w, fy1w = (H / 2 - FAR["y1"]) / U, (H / 2 - FAR["y0"]) / U
    hw, hh = (W - 1) / 2 / U, (H - 1) / 2 / U
    FARD = cam.data.clip_end

    def classify(f):
        o, rows = C.cam_rays(sc, cam)
        out = []
        for row in rows:
            s = []
            for d in row:
                a = t_terr.ray_cast(o, d, FARD); b = t_wat.ray_cast(o, d, FARD)
                da = a[3] if a[0] is not None else 1e30; db = b[3] if b[0] is not None else 1e30
                if da >= 1e30 and db >= 1e30:
                    if d.z >= 0: s.append("s"); continue
                    dp = (o.z - SEA * VS) / -d.z
                    s.append("h" if mist(dp) >= 0.97 else "v"); continue
                loc, dist, water = (a[0], da, False) if da <= db else (b[0], db, True)
                if abs(loc.x) <= hw and abs(loc.y) <= hh: s.append("w" if water else "t"); continue
                if mist(dist) >= 0.97: s.append("h")
                elif not (fx0w <= loc.x <= fx1w and fy0w <= loc.y <= fy1w): s.append("v")
                elif dist >= near_lim: s.append("f")
                else: s.append("x")
            out.append("".join(s))
        return out

    def free():
        global t_terr, t_wat
        t_terr = t_wat = None

    C.preview_run(sc, O, FRAMES, classify, subject=("t",), fallback_subject=("t", "w"), target=0.40, tol=0.07,
                  ev_range=(-0.8, 1.4), stats=stats, errors=errors, warnings=warnings, after_checks=free)
    sys.exit(0)

# ---------- render
C.render_frames(sc, O.out, list(range(O.start, END + 1)), O.budget)
