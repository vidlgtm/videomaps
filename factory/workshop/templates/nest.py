"""Workshop template 'nest' - nesting objects (Blender Cycles): a turned, lacquered wooden object (doll, egg, capsule or
barrel) opens level after level; every level carries its own picture (a flag of its era, a portrait...) in a gold frame.
built-in rules: all levels are turned from one profile, hollow with a fitted lip, the innermost one solid; the size step
between levels is solved so that each level rests inside, comes out through the opening and lets the lid lift off with
clearance (checked again in 3D); the lid twists, lifts clear and leaves before the inner level rises; the base leaves only
once the inner level is above it; the camera keeps the current level at the same size in the frame; pictures keep their
exact colours (camera-only emission at 2^-exposure, Standard view), the exposure is set on the lacquer.
usage: blender -b -P nest.py -- --params p.json --data <prep dir> --out <dir> [--start 1 --end N --gpu OPTIX --ev X
       --budget-min M | --preview]
params: shape doll | egg | capsule | barrel (or profile [[z, r], ...] + seam + panel); levels [{key, image, color}]
        (outermost first, 2..6); ratio (size step, <= the solved fit); background studio | transparent;
        camera {elevation, lens, orbit, fill}; labels [[key, display, style]]; samples"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector, Euler
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import nest_geo as G

P, O = C.args()
DATA = O.data
FPS = 30
T = float(P.get("seconds", 14)); FRAMES = int(round(T * FPS)); END = O.end or FRAMES
meta = json.load(open(os.path.join(DATA, "meta.json")))
LV = P["levels"]; NL = len(LV); NO = NL - 1; KEYS = [lv["key"] for lv in LV]
TRANSP = P.get("background", "studio") == "transparent"
CAMP = P.get("camera", {})
ELEV, LENS = math.radians(float(CAMP.get("elevation", 9))), float(CAMP.get("lens", 70))
ORBIT, FILL = float(CAMP.get("orbit", 6)), float(CAMP.get("fill", 0.58))
PALETTE = ["#7E1A26", "#123E33", "#18305C", "#5A1E4F", "#6B4A12", "#1E1E24"]
GOLD = (0.80, 0.56, 0.22)

sc = C.reset(FPS)
geo = G.profile(P.get("shape", "doll") if "profile" not in P else {"profile": P["profile"], "seam": P["seam"], "panel": P.get("panel")})
KFIT = G.solve_k(geo)
if KFIT is None: raise SystemExit("this profile cannot nest (no size step lets a level pass through the opening)")
if G.min_wall(geo) < 0.5 * G.TW: raise SystemExit(f"the profile is too steep for its wall (thinnest wall {G.min_wall(geo):.3f})")
K = min(KFIT, float(P.get("ratio", 0.8)))
HT = [K ** m for m in range(NL)]                                   # level heights (outermost = 1 m)
TL = G.timeline(T, NL)
TOPEN, SETTLE, PHS, D = TL["t_open"], TL["settle"], G.PH, G.D_OPEN
TAN_V = (36 * 9 / 16 / 2) / LENS                                  # half vertical field of view (sensor 36 mm wide)


def srgb2lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ------------------------------------------------------------------ meshes
MESH = {}
for part in ("base", "lid", "solid"):
    V, Q, Tr, MQ, MT = G.revolve(G.runs(geo, part), 128)
    MESH[part] = (V, Q, Tr, np.concatenate([MQ, MT]))


def make(name, part, mats):
    V, Q, Tr, MI = MESH[part]
    ob = C.mesh_object(name, V, Q, Tr)
    for m in mats: ob.data.materials.append(m)
    ob.data.polygons.foreach_set("material_index", MI.astype(np.int32))
    C.smooth_shade(ob)
    return ob


# ------------------------------------------------------------------ materials
def M(nt, op, a, b=None, c=None):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op
    for i, v in enumerate((a, b, c)):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = float(v)
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def principled(nt, color=None, rough=0.5, metal=0.0, coat=0.0):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    if color is not None: p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough; p.inputs["Metallic"].default_value = metal
    if coat:
        p.inputs["Coat Weight"].default_value = coat; p.inputs["Coat Roughness"].default_value = 0.06
    return p


def mix(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(fac, m.inputs[0])
    nt.links.new(a, m.inputs[1]); nt.links.new(b, m.inputs[2]); return m.outputs[0]


EXACT, PANEL, IMGS = [], {}, {}


def level_material(i, lv):
    key = lv["key"]; lm = meta["levels"][key]
    pn = G.panel(geo, lm["aspect"]); PANEL[key] = pn
    m = bpy.data.materials.new(f"lacquer_{key}"); m.use_nodes = True; nt = m.node_tree; N, L = nt.nodes, nt.links
    N.clear(); out = N.new("ShaderNodeOutputMaterial")
    tc = N.new("ShaderNodeTexCoord"); sx = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sx.inputs[0])
    x, y, z = sx.outputs[0], sx.outputs[1], sx.outputs[2]
    th = M(nt, "ARCTAN2", x, M(nt, "MULTIPLY", y, -1.0))             # angle from the front (-y) towards +x
    u = M(nt, "MULTIPLY_ADD", th, pn["rc"] / pn["w"], 0.5)
    v = M(nt, "MULTIPLY_ADD", z, 1.0 / pn["h"], 0.5 - pn["zc"] / pn["h"])
    cv = N.new("ShaderNodeCombineXYZ"); L.new(u, cv.inputs[0]); L.new(v, cv.inputs[1])
    img = N.new("ShaderNodeTexImage"); im = bpy.data.images.load(os.path.join(DATA, lm["file"]), check_existing=True)
    img.image = im; img.extension = "EXTEND"; img.interpolation = "Cubic"; L.new(cv.outputs[0], img.inputs[0]); IMGS[key] = lm["file"]
    du, dv = M(nt, "ABSOLUTE", M(nt, "SUBTRACT", u, 0.5)), M(nt, "ABSOLUTE", M(nt, "SUBTRACT", v, 0.5))
    inside = M(nt, "MULTIPLY", M(nt, "LESS_THAN", du, 0.5), M(nt, "LESS_THAN", dv, 0.5))
    fw = 0.013
    outer = M(nt, "MULTIPLY", M(nt, "LESS_THAN", du, 0.5 + fw / pn["w"]), M(nt, "LESS_THAN", dv, 0.5 + fw / pn["h"]))
    gold_m = M(nt, "SUBTRACT", outer, inside)
    zs = geo["seam"]
    for a, b in G.BANDS_BASE + [(zs - 0.030, zs - 0.016), (zs + 0.016, zs + 0.030)]:
        gold_m = M(nt, "MAXIMUM", gold_m, M(nt, "MULTIPLY", M(nt, "GREATER_THAN", z, a), M(nt, "LESS_THAN", z, b)))
    col = hexrgb(lv.get("color", PALETTE[i % len(PALETTE)]))
    lac = principled(nt, tuple(srgb2lin(c) for c in col), rough=0.32, coat=0.85)
    gold = principled(nt, GOLD, rough=0.26, metal=1.0)
    # the picture: the camera sees its exact colours (emission x 2^-exposure, a soft fall-off towards the silhouette and
    # a thin clear-coat reflection); every other ray sees a painted surface, so it lights nothing
    ex = N.new("ShaderNodeValue"); ex.outputs[0].default_value = 1.0; EXACT.append(ex)
    lw = N.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
    shade = M(nt, "MULTIPLY_ADD", M(nt, "POWER", lw.outputs["Facing"], 2.0), -0.3, 1.0)
    sc_ = N.new("ShaderNodeVectorMath"); sc_.operation = "SCALE"; L.new(img.outputs["Color"], sc_.inputs[0])
    L.new(M(nt, "MULTIPLY", ex.outputs[0], shade), sc_.inputs["Scale"])
    em = N.new("ShaderNodeEmission"); L.new(sc_.outputs[0], em.inputs["Color"]); em.inputs["Strength"].default_value = 1.0
    gl = N.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.12
    fr = N.new("ShaderNodeFresnel"); fr.inputs["IOR"].default_value = 1.5
    blk = N.new("ShaderNodeEmission"); blk.inputs["Strength"].default_value = 0.0
    coat = mix(nt, M(nt, "MULTIPLY", fr.outputs[0], 0.7), blk.outputs[0], gl.outputs[0])
    add = N.new("ShaderNodeAddShader"); L.new(em.outputs[0], add.inputs[0]); L.new(coat, add.inputs[1])
    paint = principled(nt, rough=0.5); L.new(img.outputs["Color"], paint.inputs["Base Color"])
    lp = N.new("ShaderNodeLightPath")
    pic = mix(nt, lp.outputs["Is Camera Ray"], paint.outputs[0], add.outputs[0])
    s1 = mix(nt, gold_m, lac.outputs[0], gold.outputs[0])
    L.new(mix(nt, inside, s1, pic), out.inputs["Surface"])
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    return m


def wood_material():
    m = bpy.data.materials.new("wood"); m.use_nodes = True; nt = m.node_tree; N, L = nt.nodes, nt.links
    p = N["Principled BSDF"]; p.inputs["Roughness"].default_value = 0.6
    tc = N.new("ShaderNodeTexCoord"); wv = N.new("ShaderNodeTexWave"); wv.wave_type = "RINGS"
    try: wv.rings_direction = "Z"
    except Exception: pass
    wv.inputs["Scale"].default_value = 7.0; wv.inputs["Distortion"].default_value = 3.0; wv.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Object"], wv.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB"); L.new(wv.outputs["Fac"], cr.inputs[0])
    cr.color_ramp.elements[0].color = (0.50, 0.30, 0.14, 1); cr.color_ramp.elements[1].color = (0.66, 0.44, 0.24, 1)
    L.new(cr.outputs[0], p.inputs["Base Color"])
    return m


WOOD = wood_material()
OBJ = {}                                                           # (level, part) -> object
for i, lv in enumerate(LV):
    mt = level_material(i, lv)
    parts = ("solid",) if i == NL - 1 else ("base", "lid")
    for part in parts:
        ob = make(f"{lv['key']}_{part}", part, [mt, WOOD]); ob.scale = (HT[i],) * 3; OBJ[(i, part)] = ob
        if part == "lid": ob.rotation_mode = "ZYX"


def exact_panels(scene, *_):
    v = 2.0 ** (-scene.view_settings.exposure)
    for nd in EXACT: nd.outputs[0].default_value = v


# ------------------------------------------------------------------ studio, floor, lights
if not TRANSP:
    # cyclorama: floor, a soft bend, a back wall
    ys = list(np.linspace(-14, 3, 18)) + [3 + 2.6 * math.sin(a) for a in np.linspace(0.08, math.pi / 2, 14)] + [5.6, 5.6]
    zs_ = [0.0] * 18 + [2.6 - 2.6 * math.cos(a) for a in np.linspace(0.08, math.pi / 2, 14)] + [6.0, 12.0]
    xs = np.linspace(-16, 16, 3)
    co = np.array([[x, y, z] for (y, z) in zip(ys, zs_) for x in xs])
    nq = [[j * 3 + i, j * 3 + i + 1, (j + 1) * 3 + i + 1, (j + 1) * 3 + i] for j in range(len(ys) - 1) for i in range(2)]
    cyc = C.mesh_object("studio", co, np.array(nq)); C.smooth_shade(cyc)
    sm = bpy.data.materials.new("studio"); sm.use_nodes = True; sp = sm.node_tree.nodes["Principled BSDF"]
    sp.inputs["Base Color"].default_value = (0.020, 0.024, 0.032, 1); sp.inputs["Roughness"].default_value = 0.55
    sp.inputs["Specular IOR Level"].default_value = 0.2
    cyc.data.materials.append(sm)
    pool = bpy.data.lights.new("pool", "SPOT"); pool.energy = 500; pool.spot_size = math.radians(55); pool.spot_blend = 1.0
    pool.color = (0.80, 0.86, 1.0); po = bpy.data.objects.new("pool", pool); sc.collection.objects.link(po)
    po.location = (0, -1.5, 5.0); C.aim(po, (0, 5.6, 1.4))
else:
    fl = C.mesh_object("floor", np.array([[-30, -30, 0], [30, -30, 0], [30, 30, 0], [-30, 30, 0]]), np.array([[0, 1, 2, 3]]))
    fl.is_shadow_catcher = True
    fl.data.materials.append(C.mat("floor", (0.5, 0.5, 0.5), 0.6))


def area(name, energy, size, loc, color=(1, 1, 1), size_y=None):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = energy; ld.color = color
    if size_y: ld.shape = "RECTANGLE"; ld.size = size; ld.size_y = size_y
    else: ld.size = size
    ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob); ob.location = loc; C.aim(ob, (0, 0, 0.45)); return ob


kl = area("key", 62, 2.2, (-2.6, -3.4, 3.2), (1.0, 0.97, 0.92), 1.6)
try: kl.data.spread = math.radians(75)
except Exception: pass
fl_ = area("fill", 20, 3.0, (3.0, -2.6, 1.2), (0.92, 0.95, 1.0))
try: fl_.visible_glossy = False
except Exception: pass
area("rim_l", 40, 1.0, (-2.0, 2.0, 1.8), (0.95, 0.97, 1.0))
area("rim_r", 40, 1.0, (2.0, 2.2, 1.6), (1.0, 0.95, 0.88))
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.010, 0.011, 0.014, 1) if not TRANSP else (0.03, 0.03, 0.035, 1)


# ------------------------------------------------------------------ motion
def level_loc(m, t):
    """world position of level m (its base; also the closed lid) at time t"""
    if m > 0 and t < TOPEN[m - 1]:
        lo = level_loc(m - 1, t); return (lo[0], lo[1], lo[2] + G.REST * HT[m - 1])
    if m > 0 and t < TOPEN[m - 1] + D:
        tau = t - TOPEN[m - 1]; Hc = HT[m - 1]
        rest, up = G.REST * Hc, (geo["seam"] + G.LIP + 0.10) * Hc
        return (0.0, 0.0, rest + (up - rest) * G.ph(tau, PHS["rise"]) - up * G.ph(tau, PHS["down"]))
    if m < NO and t >= TOPEN[m]:
        tau = t - TOPEN[m]; a = G.ph(tau, PHS["away"], G.ease_in); side = 1 if m % 2 == 0 else -1
        return (side * 2.6 * HT[m] * a, 1.2 * HT[m] * a, 0.0)
    return (0.0, 0.0, 0.0)


def lid_pose(m, t):
    if t < TOPEN[m]: return level_loc(m, t), (0.0, 0.0, 0.0)
    tau = t - TOPEN[m]; H_ = HT[m]; side = -1 if m % 2 == 0 else 1
    inner_top = (G.REST * H_ + HT[m + 1]) - (geo["seam"] + G.GAP) * H_   # the lid rim must pass the top of the inner level
    clear = max(0.06 * H_, inner_top + 0.10 * H_)
    z = 0.045 * H_ * G.ph(tau, PHS["twist"]) + (clear - 0.045 * H_) * G.ph(tau, PHS["clear"])
    e = G.ph(tau, PHS["exit"], G.ease_in)
    z += 1.1 * H_ * e; x = side * 2.8 * H_ * e
    twist = math.radians(30) * G.ph(tau, PHS["twist"]) + math.radians(40) * e
    rot = (0.0, side * math.radians(-38) * e, twist)
    pv = Vector((0, 0, 0.76 * H_)); comp = pv - Euler(rot, "ZYX").to_matrix() @ pv   # pivot = the lid centre
    return (x + comp.x, comp.y, z + comp.z), rot


def hidden(m, part, t):
    if part == "lid": return t >= TOPEN[m] + PHS["lid_hide"] if m < NO else False
    if part == "base": return t >= TOPEN[m] + PHS["base_hide"] if m < NO else False
    return False


def pose(m, part, t):
    if part == "lid": return lid_pose(m, t)
    return level_loc(m, t), (0.0, 0.0, 0.0)


def current(t):
    """the level the shot is about at time t, and whether it is settled (a hold)"""
    for i in range(NO):
        if TOPEN[i] <= t < TOPEN[i] + D: return i, False
    m = sum(1 for i in range(NO) if t >= TOPEN[i] + D); return m, True


def frame_span(t):
    """height span the camera must hold at time t"""
    for i in range(NO):
        if TOPEN[i] <= t < TOPEN[i] + D:
            tau = t - TOPEN[i]; hs = [HT[i + 1] + level_loc(i + 1, t)[2]]
            if tau < PHS["away"][0]: hs.append((geo["seam"] + G.LIP) * HT[i])
            if tau < PHS["exit"][0]: hs.append(HT[i] + lid_pose(i, t)[0][2])
            return max(hs)
    return HT[current(t)[0]]


ts = np.arange(FRAMES) / FPS
span = np.array([frame_span(t) for t in ts])
sig = 0.32 * FPS; kx = np.arange(-int(3 * sig), int(3 * sig) + 1); kern = np.exp(-0.5 * (kx / sig) ** 2); kern /= kern.sum()
span_s = np.convolve(np.pad(span, len(kx) // 2, mode="edge"), kern, mode="valid")
cam_d = span_s / (2 * FILL * TAN_V); cam_tz = 0.48 * span_s

camd = bpy.data.cameras.new("cam"); camd.lens = LENS; camd.sensor_width = 36; camd.clip_start = 0.01; camd.clip_end = 200
camd.dof.use_dof = True; camd.dof.aperture_fstop = 4.5
cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
ALL = list(OBJ.items())
for fr in range(1, FRAMES + 1):
    t = (fr - 1) / FPS
    for (m, part), ob in ALL:
        loc, rot = pose(m, part, t)
        ob.location = loc; ob.rotation_euler = rot
        ob.keyframe_insert("location", frame=fr); ob.keyframe_insert("rotation_euler", frame=fr)
        hd = hidden(m, part, t); ob.hide_render = hd; ob.keyframe_insert("hide_render", frame=fr)
    az = math.radians(ORBIT * (2 * t / max(T, 1e-6) - 1))
    d_, tz = float(cam_d[fr - 1]), float(cam_tz[fr - 1])
    tgt = Vector((0, 0, tz))
    cam.location = tgt + d_ * Vector((math.sin(az) * math.cos(ELEV), -math.cos(az) * math.cos(ELEV), math.sin(ELEV)))
    C.aim(cam, tgt)
    cam.keyframe_insert("location", frame=fr); cam.keyframe_insert("rotation_euler", frame=fr)
    cm, _ = current(t)
    camd.dof.focus_distance = (cam.location - Vector((0, 0, 0.5 * HT[cm]))).length
    camd.dof.keyframe_insert("focus_distance", frame=fr)
for ob in [o for _, o in ALL] + [cam]:
    ad = ob.animation_data
    for fc in (ad.action.fcurves if ad and ad.action else []):
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
if camd.animation_data and camd.animation_data.action:
    for fc in camd.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

sc.frame_start, sc.frame_end = 1, FRAMES
C.setup_cycles(sc, O, samples=int(P.get("samples", 64)), motion_blur=True, look="None", transparent=TRANSP)
# pictures keep their exact colours: no tone-mapping curve
sc.view_settings.view_transform = "Standard"
try: sc.view_settings.look = "None"
except Exception: pass
bpy.app.handlers.frame_change_pre.append(exact_panels)
exact_panels(sc)
print(f"built: {NL} levels, shape {P.get('shape', 'custom')}, size step {K} (fit {KFIT}), opens at "
      f"{', '.join(f'{x:.1f}' for x in TOPEN)} s, last level settles {SETTLE[-1]:.1f} s, background "
      f"{'transparent' if TRANSP else 'studio'}", flush=True)

# ------------------------------------------------------------------ preview: labels + checks + exposure + key frames
if O.preview:
    errors, warnings = [], []
    stats = {"credits": meta.get("credits", []), "size_step": K, "size_step_fit": KFIT, "heights": [round(h, 3) for h in HT],
             "open_s": [round(x, 2) for x in TOPEN], "panels": {k: {a: round(b, 3) for a, b in v.items()} for k, v in PANEL.items()}}
    LOCAL = {}
    for (m, part), ob in ALL:
        V, Q, Tr, MI = MESH[part]
        LOCAL[(m, part)] = (V, Q.tolist() + Tr.tolist(), MI)
    BVH = {mp: BVHTree.FromPolygons([Vector(v) for v in LOCAL[mp][0]], LOCAL[mp][1]) for mp in OBJ}

    def visible(): return [mp for mp, ob in ALL if not ob.hide_render]

    def mats():
        return {mp: OBJ[mp].matrix_world.copy() for mp in OBJ}

    def hit_code(mp, loc_local, face):
        m, part = mp
        if LOCAL[mp][2][face] == 1: return "w"
        x, y, z = loc_local
        if part != "lid":
            pn = PANEL[KEYS[m]]
            u = 0.5 + math.atan2(x, -y) * pn["rc"] / pn["w"]; v = 0.5 + (z - pn["zc"]) / pn["h"]
            if abs(u - 0.5) < 0.5 and abs(v - 0.5) < 0.5: return "i"
            if abs(u - 0.5) < 0.5 + 0.013 / pn["w"] and abs(v - 0.5) < 0.5 + 0.013 / pn["h"]: return "g"
        zs = geo["seam"]
        for a, b in G.BANDS_BASE + [(zs - 0.030, zs - 0.016), (zs + 0.016, zs + 0.030)]:
            if a < z < b: return "g"
        return "o"

    def inv(Mw, vis): return {mp: (Mw[mp].inverted(), Mw[mp].inverted().to_3x3()) for mp in vis}

    def cast(o, d, Mw, vis, IV):
        best, res = 1e30, None
        for mp in vis:
            mi, m3 = IV[mp]; lo = mi @ o; ld = (m3 @ d).normalized()
            h = BVH[mp].ray_cast(lo, ld)
            if h[0] is None: continue
            dw = ((Mw[mp] @ h[0]) - o).length
            if dw < best: best, res = dw, (mp, h[0], h[2])
        return res, best

    def classify(f):
        Mw = mats(); vis = visible(); IV = inv(Mw, vis); o, rows = C.cam_rays(sc, cam)
        bg = "k" if TRANSP else "b"
        out = []
        for row in rows:
            s = ""
            for d in row:
                r, _ = cast(o, d, Mw, vis, IV)
                s += bg if r is None else hit_code(r[0], r[1], r[2])
            out.append(s)
        return out

    FR_ = list(cam.data.view_frame(scene=sc)); FZ = -FR_[0].z
    VX = (min(v.x for v in FR_) / FZ, max(v.x for v in FR_) / FZ); VY = (min(v.y for v in FR_) / FZ, max(v.y for v in FR_) / FZ)

    def project(pts):
        mi = np.array(cam.matrix_world.inverted())
        pl = pts @ mi[:3, :3].T + mi[:3, 3]
        z = -pl[:, 2]; zs_ = np.where(np.abs(z) < 1e-9, 1e-9, z)
        return np.column_stack([(pl[:, 0] / zs_ - VX[0]) / (VX[1] - VX[0]), (pl[:, 1] / zs_ - VY[0]) / (VY[1] - VY[0]), z])

    def world(mp, Mw, pts=None):
        V = LOCAL[mp][0] if pts is None else pts
        A = np.array(Mw[mp]); return V @ A[:3, :3].T + A[:3, 3]

    SAMPLE = {mp: LOCAL[mp][0][::37].astype(np.float64) for mp in OBJ}
    # labels (under the current level, while it is settled) + framing of every hold + exits out of the frame
    LAB = [e for e in P.get("labels", []) if e[0] in KEYS]
    tracks = {e[0]: [] for e in LAB}
    cut_hold, pop = {}, {}
    for fr in range(1, FRAMES + 1):
        sc.frame_set(fr); t = (fr - 1) / FPS; cm, settled = current(t)
        for e in LAB:
            m = KEYS.index(e[0]); lo = level_loc(m, t)
            pw = Vector((lo[0], lo[1] - float(G.R(geo, 0.0)) * HT[m], lo[2]))
            v = world_to_camera_view(sc, cam, pw)
            on = (t - SETTLE[m] >= 0.15 or m == 0) and (m == NO or t < TOPEN[m] + PHS["twist"][1])
            vis = on and level_loc(m, t)[2] < 1e-6 and 0.02 <= v.x <= 0.98 and 0.06 <= v.y <= 0.98 and v.z > 0
            tracks[e[0]].append([round(v.x * 1920, 1), round((1 - v.y) * 1080 + 34, 1), int(vis)])
        Mw = mats()
        for i in range(NO):
            for part, th in (("lid", PHS["lid_hide"]), ("base", PHS["base_hide"])):
                if abs(t - (TOPEN[i] + th - 1 / FPS)) < 0.5 / FPS:
                    c_ = project(world((i, part), Mw, SAMPLE[(i, part)]))
                    if np.any((c_[:, 0] > 0) & (c_[:, 0] < 1) & (c_[:, 1] > 0) & (c_[:, 1] < 1) & (c_[:, 2] > 0)):
                        pop.setdefault(f"{KEYS[i]} {part}", round(t, 2))
        if fr % 3 and fr != FRAMES: continue
        if settled:
            mp = (cm, "solid") if cm == NO else (cm, "base")
            pts = [mp] + ([] if cm == NO else [(cm, "lid")])
            for q in pts:
                c_ = project(world(q, Mw, SAMPLE[q]))
                if np.any((c_[:, 0] < 0.02) | (c_[:, 0] > 0.98) | (c_[:, 1] < 0.04) | (c_[:, 1] > 0.97) | (c_[:, 2] <= 0)):
                    cut_hold.setdefault(KEYS[cm], []).append(round(t, 1))
    names = [[e[0], e[1] if len(e) > 1 else e[0], e[2] if len(e) > 2 else ""] for e in LAB]
    json.dump({"fps": FPS, "frames": FRAMES, "tracks": tracks, "names": names}, open(f"{O.out}/labels.json", "w"))
    vis_s = {k: round(sum(x[2] for x in v) / FPS, 2) for k, v in tracks.items()}
    stats["labels_visible_s"] = vis_s
    for k, s_ in vis_s.items():
        if s_ < 1.0: warnings.append(f"label {k} visible only {s_:.1f} s")
    for k, ts_ in cut_hold.items(): errors.append(f"level {k} is cut by the frame edge while it is held ({ts_[0]:.1f}-{ts_[-1]:.1f} s)")
    for k, t_ in pop.items(): errors.append(f"{k} is still in the frame when it disappears ({t_:.1f} s) - it would pop out")

    # parts must never pass through each other: closed at rest, and all through every opening
    def wbvh(mp, Mw): return BVHTree.FromPolygons([Vector(v) for v in world(mp, Mw)], LOCAL[mp][1])
    hits = []
    sc.frame_set(1); Mw = mats(); bv = {mp: wbvh(mp, Mw) for mp in OBJ}
    for m in range(NO):
        inner = [(m + 1, "solid")] if m + 1 == NO else [(m + 1, "base"), (m + 1, "lid")]
        for a in inner:
            for b in ((m, "base"), (m, "lid")):
                if bv[a].overlap(bv[b]): hits.append(f"{KEYS[a[0]]} {a[1]} / {KEYS[b[0]]} {b[1]} at rest")
    for i in range(NO):
        f0, f1 = 1 + int(TOPEN[i] * FPS), min(FRAMES, 1 + int((TOPEN[i] + D) * FPS))
        inner = [(i + 1, "solid")] if i + 1 == NO else [(i + 1, "base"), (i + 1, "lid")]
        for fr in range(f0, f1 + 1, 2):
            sc.frame_set(fr); Mw = mats(); t = (fr - 1) / FPS
            act = [mp for mp in [(i, "base"), (i, "lid")] + inner if not hidden(mp[0], mp[1], t)]
            bv = {mp: wbvh(mp, Mw) for mp in act}
            for x_ in range(len(act)):
                for y_ in range(x_ + 1, len(act)):
                    a, b = act[x_], act[y_]
                    if a[0] == b[0]: continue
                    if bv[a].overlap(bv[b]): hits.append(f"{KEYS[a[0]]} {a[1]} / {KEYS[b[0]]} {b[1]} at {t:.2f} s")
            if (i, "lid") in act and (i, "base") in act and t > TOPEN[i] + 0.05 and bv[(i, "lid")].overlap(bv[(i, "base")]):
                hits.append(f"{KEYS[i]} lid / base at {t:.2f} s")
    stats["intersections"] = hits[:12]
    if hits: errors.append(f"parts pass through each other: {'; '.join(hits[:4])}" + (" ..." if len(hits) > 4 else ""))

    # key frames: every level held (picture readable) + moments of the opening
    holds = []
    for m in range(NL):
        a = SETTLE[m] + (0.25 if m else 0.5); b = (TOPEN[m] if m < NO else T) - 0.15
        holds.append(int(round((a + 0.6 * (b - a)) * FPS)) + 1)
    acts = [int(round((TOPEN[j % NO] + x) * FPS)) + 1 for j, x in enumerate((1.3, 0.45, 2.0, 0.9, 1.6, 2.3))]
    KEYF = []
    for f in holds + acts + [int(x) for x in np.linspace(1, FRAMES, 12)]:
        f = int(min(max(f, 1), FRAMES))
        if all(abs(f - g) >= 6 for g in KEYF): KEYF.append(f)
        if len(KEYF) == 6: break
    KEYF = sorted(KEYF)
    C.key_frames = lambda n, k=6: list(KEYF)
    stats["hold_frames"] = holds

    def pixels(path):
        im = bpy.data.images.load(os.path.abspath(path), check_existing=False)
        try: im.colorspace_settings.name = "Non-Color"
        except Exception: pass
        w_, h_ = im.size; a_ = np.empty(w_ * h_ * 4, np.float32); im.pixels.foreach_get(a_); bpy.data.images.remove(im)
        return a_.reshape(h_, w_, 4)[..., :3]

    def picture_fidelity(nx=160, ny=90):
        """held key frames: rendered picture pixels against the picture files, through a grid of camera rays"""
        cp = os.path.join(O.out, "check.json"); ck = json.load(open(cp))
        imgs = {k: pixels(os.path.join(DATA, IMGS[k])) for k in KEYS}
        acc = {k: [] for k in KEYS}
        for f in ck["key_frames"]:
            t = (f - 1) / FPS; cm, settled = current(t)
            if not settled: continue
            rend = pixels(os.path.join(O.out, f"p_{f:04d}{ck.get('ext', '.jpg')}"))[::-1]
            rh_, rw_ = rend.shape[:2]
            sc.frame_set(f); Mw = mats(); vis = visible(); IV = inv(Mw, vis); o, rows = C.cam_rays(sc, cam, nx, ny)
            hk = np.full((ny, nx), -1, np.int32); ex = np.zeros((ny, nx, 3), np.float32)
            key = KEYS[cm]; pn = PANEL[key]; fa = imgs[key]
            for j, row in enumerate(rows):
                for i_, d in enumerate(row):
                    r, _ = cast(o, d, Mw, vis, IV)
                    if r is None or r[0][0] != cm or r[0][1] == "lid" or hit_code(r[0], r[1], r[2]) != "i": continue
                    x, y, z = r[1]
                    u = 0.5 + math.atan2(x, -y) * pn["rc"] / pn["w"]; v = 0.5 + (z - pn["zc"]) / pn["h"]
                    ex[j, i_] = fa[min(max(int(v * fa.shape[0]), 0), fa.shape[0] - 1), min(max(int(u * fa.shape[1]), 0), fa.shape[1] - 1)]
                    hk[j, i_] = cm
            ok = hk >= 0
            pk = np.pad(hk, 2, constant_values=-1); pe = np.pad(ex, ((2, 2), (2, 2), (0, 0)))
            for dj in range(-2, 3):
                for di in range(-2, 3):
                    ok &= pk[2 + dj:2 + dj + ny, 2 + di:2 + di + nx] == hk
                    if abs(dj) <= 1 and abs(di) <= 1:
                        ok &= np.abs(pe[2 + dj:2 + dj + ny, 2 + di:2 + di + nx] - ex).max(-1) < 0.04
            for j, i_ in zip(*np.nonzero(ok)):
                r_ = rend[min(int((j + 0.5) / ny * rh_), rh_ - 1), min(int((i_ + 0.5) / nx * rw_), rw_ - 1)]
                acc[key].append((r_, ex[j, i_]))
        lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        res, errs, warns = {}, [], []
        for k, v in acc.items():
            if len(v) < 12: warns.append(f"picture {k}: too few clear cells to measure its colours ({len(v)})"); continue
            r_ = np.array([a for a, _ in v]); e_ = np.array([b for _, b in v])
            dmed = float(np.median(np.abs(r_ - e_).max(-1)) * 255)
            yl = lambda c: lin(c) @ np.array([0.2126, 0.7152, 0.0722])
            evo = float(np.log2(max(np.median(yl(r_)), 1e-4) / max(np.median(yl(e_)), 1e-4)))
            res[k] = {"median_diff": round(dmed, 1), "ev_offset": round(evo, 3), "cells": len(v)}
            if dmed > 16 or abs(evo) > 0.2: errs.append(f"picture {k} renders off its true colours (median difference {dmed:.0f}/255, {evo:+.2f} EV)")
            elif dmed > 9: warns.append(f"picture {k} colours slightly off (median difference {dmed:.0f}/255)")
        lo_, hi_ = EV_RANGE
        if min(abs(ck["ev"] - lo_), abs(ck["ev"] - hi_)) < 0.02:
            errs.append(f"the exposure stopped at its limit ({ck['ev']:+.2f} EV): the light levels are off for this scene")
        ck["errors"] = ck.get("errors", []) + errs; ck["warnings"] = ck.get("warnings", []) + warns
        ck.setdefault("stats", {})["picture_fidelity"] = res
        json.dump(ck, open(cp, "w"))
        print(f"picture colours: {res}", flush=True)

    # exposure on the lacquer (visible in every frame); the pictures do not depend on it
    lac_l = [0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] for c in (hexrgb(lv.get("color", PALETTE[i % len(PALETTE)])) for i, lv in enumerate(LV))]
    target = round(0.85 * float(np.mean(lac_l)), 3)
    EV_RANGE = (-2.5, 2.0)
    C.preview_run(sc, O, FRAMES, classify, subject=("o",), target=target, tol=max(0.025, round(0.25 * target, 3)),
                  ev_range=EV_RANGE, stats=stats, errors=errors, warnings=warnings, dark_max=1.0 if TRANSP else 0.92)
    picture_fidelity()
    sys.exit(0)

# ------------------------------------------------------------------ render
C.render_frames(sc, O.out, list(range(O.start, END + 1)), O.budget)
