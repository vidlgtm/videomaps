"""Workshop template 'reveal' - archival pictures and documents revealed as physical objects (Blender Cycles): photo
prints and paper sheets lying on a walnut desk or on museum velvet, each one revealed in turn by its own light (a spot that
fades up, or a beam that sweeps across it), the camera travelling from one to the next and pushing in slowly; once the
camera moves on, the item it leaves sinks back to a low light.
built-in rules: once lit, every picture keeps its exact colours (camera-only emission at 2^-exposure, Standard view);
the light that reveals it is a real light, so the desk, the paper edges and the shadows answer it; items never overlap;
every item is held whole in the frame with its label; the exposure is set on the lit desk around the items.
usage: blender -b -P reveal.py -- --params p.json --data <prep dir> --out <dir> [--start 1 --end N --gpu OPTIX --ev X
       --budget-min M | --preview]
params: items [{key, image, kind print | document, size}] (1..4, left to right); setting desk | museum;
        reveal spot | sweep; camera {elevation, lens, fill}; labels [[key, display, style]]; samples"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import reveal_geo as G

P, O = C.args()
DATA = O.data
FPS = 30
T = float(P.get("seconds", 10)); FRAMES = int(round(T * FPS)); END = O.end or FRAMES
meta = json.load(open(os.path.join(DATA, "meta.json")))
IT = P["items"]; NI = len(IT); KEYS = [e["key"] for e in IT]
SETTING = P.get("setting", "desk"); MODE = P.get("reveal", "spot")
CAMP = P.get("camera", {})
EL, LENS, FILL = float(CAMP.get("elevation", 58)), float(CAMP.get("lens", 50)), float(CAMP.get("fill", 0.66))
TL = G.timeline(T, NI)
DARK = 0.008                        # what is left of a picture before its light comes on (linear)
SOFT = 0.35                         # width of the edge of a sweeping reveal (share of the item width)
E_SPOT = 60.0 if SETTING == "desk" else 39.0
BLEND = 0.45
DIM = 0.35                          # what is left of an item's light (and picture) once the camera has moved on


def srgb2lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


sc = C.reset(FPS)

# ------------------------------------------------------------------ items: sizes, layout, meshes
DIMS = []
for e in IT:
    d = G.dims(meta["items"][e["key"]]["aspect"], e.get("kind", "print"), float(e.get("size", 1.0)))
    d.update(key=e["key"], kind=e.get("kind", "print")); DIMS.append(d)
ITEMS, MIN_GAP, GAP_USED, SLIVERS = G.plan(DIMS, T, EL, LENS, FILL, FPS)    # the gap that leaves no sliver at the frame edge


def sheet(it):
    L_ = max(it["w"], it["h"]); nx = max(8, int(round(56 * it["w"] / L_))); ny = max(8, int(round(56 * it["h"] / L_)))
    xs, ys = np.linspace(-it["w"] / 2, it["w"] / 2, nx + 1), np.linspace(-it["h"] / 2, it["h"] / 2, ny + 1)
    X, Y = np.meshgrid(xs, ys); Z = G.curl(it, X, Y)
    V = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    idx = lambda i, j: j * (nx + 1) + i
    Q = np.array([[idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)] for j in range(ny) for i in range(nx)])
    return V, Q


# ------------------------------------------------------------------ materials
def M(nt, op, a, b=None, c=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = float(v)
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def mix(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(fac, m.inputs[0])
    nt.links.new(a, m.inputs[1]); nt.links.new(b, m.inputs[2]); return m.outputs[0]


EXACT, REVN, REVD, IMGS = [], {}, {}, {}
PAPER = (0.93, 0.91, 0.86)                                           # photo paper (sRGB)


def item_material(it):
    key = it["key"]; im_meta = meta["items"][key]
    m = bpy.data.materials.new(f"item_{key}"); m.use_nodes = True; nt = m.node_tree; N, L = nt.nodes, nt.links
    N.clear(); out = N.new("ShaderNodeOutputMaterial")
    tc = N.new("ShaderNodeTexCoord"); sx = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sx.inputs[0])
    x, y = sx.outputs[0], sx.outputs[1]
    u = M(nt, "MULTIPLY_ADD", x, 1.0 / it["iw"], 0.5); v = M(nt, "MULTIPLY_ADD", y, 1.0 / it["ih"], 0.5)
    cv = N.new("ShaderNodeCombineXYZ"); L.new(u, cv.inputs[0]); L.new(v, cv.inputs[1])
    img = N.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(os.path.join(DATA, im_meta["file"]), check_existing=True)
    img.extension = "EXTEND"; img.interpolation = "Cubic"; L.new(cv.outputs[0], img.inputs[0]); IMGS[key] = im_meta["file"]
    du, dv = M(nt, "ABSOLUTE", M(nt, "SUBTRACT", u, 0.5)), M(nt, "ABSOLUTE", M(nt, "SUBTRACT", v, 0.5))
    inside = M(nt, "MULTIPLY", M(nt, "LESS_THAN", du, 0.5), M(nt, "LESS_THAN", dv, 0.5))
    # the paper margin: its exact colour with a faint grain
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 220.0; nz.inputs["Detail"].default_value = 4.0
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    grain = M(nt, "MULTIPLY_ADD", nz.outputs["Fac"], 0.05, 0.975)
    pap = N.new("ShaderNodeCombineXYZ")
    for i, c in enumerate(PAPER): pap.inputs[i].default_value = srgb2lin(c)
    pg = N.new("ShaderNodeVectorMath"); pg.operation = "SCALE"; L.new(pap.outputs[0], pg.inputs[0]); L.new(grain, pg.inputs["Scale"])
    mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; L.new(inside, mx.inputs[0])
    L.new(pg.outputs[0], mx.inputs[6]); L.new(img.outputs["Color"], mx.inputs[7]); col = mx.outputs[2]
    # the reveal: a fade (spot) or an edge that crosses the item from left to right (sweep)
    rv = N.new("ShaderNodeValue"); rv.outputs[0].default_value = 0.0; REVN[key] = rv
    if MODE == "sweep":
        uu = M(nt, "MULTIPLY_ADD", x, 1.0 / it["w"], 0.5)
        r = M(nt, "DIVIDE", M(nt, "SUBTRACT", rv.outputs[0], uu), SOFT, clamp=True)
        r = M(nt, "POWER", r, 2.2)
    else:
        r = rv.outputs[0]
    fac = M(nt, "MULTIPLY_ADD", r, 1.0 - DARK, DARK)
    dm = N.new("ShaderNodeValue"); dm.outputs[0].default_value = 1.0; REVD[key] = dm
    fac = M(nt, "MULTIPLY", fac, dm.outputs[0])
    ex = N.new("ShaderNodeValue"); ex.outputs[0].default_value = 1.0; EXACT.append(ex)
    lw = N.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
    shade = M(nt, "MULTIPLY_ADD", M(nt, "POWER", lw.outputs["Facing"], 2.0), -0.3, 1.0)
    sc_ = N.new("ShaderNodeVectorMath"); sc_.operation = "SCALE"; L.new(col, sc_.inputs[0])
    L.new(M(nt, "MULTIPLY", M(nt, "MULTIPLY", ex.outputs[0], fac), shade), sc_.inputs["Scale"])
    em = N.new("ShaderNodeEmission"); L.new(sc_.outputs[0], em.inputs["Color"]); em.inputs["Strength"].default_value = 1.0
    top = em.outputs[0]
    if it["kind"] == "print":                                       # satin photo paper: a faint sheen
        gl = N.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.22
        fr = N.new("ShaderNodeFresnel"); fr.inputs["IOR"].default_value = 1.5
        blk = N.new("ShaderNodeEmission"); blk.inputs["Strength"].default_value = 0.0
        coat = mix(nt, M(nt, "MULTIPLY", fr.outputs[0], 0.5), blk.outputs[0], gl.outputs[0])
        add = N.new("ShaderNodeAddShader"); L.new(top, add.inputs[0]); L.new(coat, add.inputs[1]); top = add.outputs[0]
    paint = N.new("ShaderNodeBsdfPrincipled"); paint.inputs["Roughness"].default_value = 0.6; L.new(col, paint.inputs["Base Color"])
    lp = N.new("ShaderNodeLightPath")
    L.new(mix(nt, lp.outputs["Is Camera Ray"], paint.outputs[0], top), out.inputs["Surface"])
    try: m.cycles.emission_sampling = "NONE"
    except Exception: pass
    return m


MESH, OBJ, LIFT = {}, {}, {}
for it in ITEMS:
    V, Q = sheet(it); MESH[it["key"]] = (V, Q)
    ob = C.mesh_object(f"item_{it['key']}", V, Q); C.smooth_shade(ob)
    th = G.thickness(it)
    so = ob.modifiers.new("thick", "SOLIDIFY"); so.thickness = th; so.offset = -1.0; so.use_even_offset = True
    ob.data.materials.append(item_material(it))
    ob.location = (it["x"], it["y"], th + 0.0008); ob.rotation_euler = (0.0, 0.0, math.radians(it["rot"]))
    OBJ[it["key"]] = ob; LIFT[it["key"]] = G.lift(it)


def exact_pictures(scene, *_):
    v = 2.0 ** (-scene.view_settings.exposure)
    for nd in EXACT: nd.outputs[0].default_value = v


# ------------------------------------------------------------------ the surface, the room light
def desk_material():
    m = bpy.data.materials.new("desk"); m.use_nodes = True; nt = m.node_tree; N, L = nt.nodes, nt.links
    p = N["Principled BSDF"]; p.inputs["Roughness"].default_value = 0.42
    p.inputs["Coat Weight"].default_value = 0.5; p.inputs["Coat Roughness"].default_value = 0.14
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.35, 3.2, 1.0); L.new(tc.outputs["Object"], mp.inputs["Vector"])
    wn = N.new("ShaderNodeTexNoise"); wn.inputs["Scale"].default_value = 0.9; wn.inputs["Detail"].default_value = 2.0
    L.new(tc.outputs["Object"], wn.inputs["Vector"])                 # the grain wanders gently (domain warp)
    wc = N.new("ShaderNodeVectorMath"); wc.operation = "SUBTRACT"; L.new(wn.outputs["Color"], wc.inputs[0]); wc.inputs[1].default_value = (0.5, 0.5, 0.5)
    ws = N.new("ShaderNodeVectorMath"); ws.operation = "SCALE"; L.new(wc.outputs[0], ws.inputs[0]); ws.inputs["Scale"].default_value = 0.45
    wa = N.new("ShaderNodeVectorMath"); wa.operation = "ADD"; L.new(mp.outputs[0], wa.inputs[0]); L.new(ws.outputs[0], wa.inputs[1])
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.6; nz.inputs["Detail"].default_value = 6.0
    L.new(wa.outputs[0], nz.inputs["Vector"])
    wv = N.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"
    try: wv.bands_direction = "Y"
    except Exception: pass
    wv.inputs["Scale"].default_value = 2.2; wv.inputs["Distortion"].default_value = 7.0; wv.inputs["Detail"].default_value = 3.0
    L.new(wa.outputs[0], wv.inputs["Vector"])
    f = M(nt, "MULTIPLY_ADD", wv.outputs["Fac"], 0.65, M(nt, "MULTIPLY", nz.outputs["Fac"], 0.35))
    cr = N.new("ShaderNodeValToRGB"); L.new(f, cr.inputs[0])
    cr.color_ramp.elements[0].color = (0.040, 0.018, 0.007, 1); cr.color_ramp.elements[1].color = (0.125, 0.058, 0.024, 1)
    ln = N.new("ShaderNodeTexNoise"); ln.inputs["Scale"].default_value = 0.22; ln.inputs["Detail"].default_value = 1.0
    L.new(tc.outputs["Object"], ln.inputs["Vector"])                 # slow changes of tone across the desk
    tone = M(nt, "MULTIPLY_ADD", ln.outputs["Fac"], 0.5, 0.75)
    tn = N.new("ShaderNodeVectorMath"); tn.operation = "SCALE"; L.new(cr.outputs[0], tn.inputs[0]); L.new(tone, tn.inputs["Scale"])
    L.new(tn.outputs[0], p.inputs["Base Color"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.05; bp.inputs["Distance"].default_value = 0.002
    L.new(f, bp.inputs["Height"]); L.new(bp.outputs[0], p.inputs["Normal"])
    return m


def velvet_material():
    m = bpy.data.materials.new("velvet"); m.use_nodes = True; p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.011, 0.011, 0.013, 1); p.inputs["Roughness"].default_value = 1.0
    p.inputs["Specular IOR Level"].default_value = 0.1
    try: p.inputs["Sheen Weight"].default_value = 0.8; p.inputs["Sheen Roughness"].default_value = 0.4
    except Exception: pass
    return m


fl = C.mesh_object("surface", np.array([[-30, -30, 0], [30, -30, 0], [30, 30, 0], [-30, 30, 0]]), np.array([[0, 1, 2, 3]]))
fl.data.materials.append(desk_material() if SETTING == "desk" else velvet_material())
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.0046, 0.0041, 0.0037, 1) if SETTING == "desk" else (0.0014, 0.0014, 0.0016, 1)
if SETTING == "desk":                                               # a far warm lamp: a soft gradient across the desk
    ld = bpy.data.lights.new("lamp", "AREA"); ld.energy = 9.2; ld.size = 2.5; ld.color = (1.0, 0.80, 0.58)
    lo = bpy.data.objects.new("lamp", ld); sc.collection.objects.link(lo); lo.location = (-3.0, 2.5, 3.5); C.aim(lo, (0, 0, 0))
    lo.visible_camera = False; lo.visible_glossy = False                # no grey blob on the varnish

# ------------------------------------------------------------------ one light per item
SPOT, RCOV = {}, {}
LCOL = (1.0, 0.86, 0.68) if SETTING == "desk" else (1.0, 0.94, 0.86)
for it in ITEMS:
    L_ = max(it["w"], it["h"]); off = np.array([-0.45, -1.0, 2.0]) * L_
    dist = float(np.linalg.norm(off)); rc = 0.62 * math.hypot(it["w"], it["h"]); RCOV[it["key"]] = rc
    ld = bpy.data.lights.new(f"spot_{it['key']}", "SPOT"); ld.energy = 0.0; ld.color = LCOL
    ld.spot_size = min(math.radians(150), 2 * math.atan(rc / dist) / math.sqrt(1 - BLEND)); ld.spot_blend = BLEND
    ld.shadow_soft_size = 0.08 * L_
    ob = bpy.data.objects.new(f"spot_{it['key']}", ld); sc.collection.objects.link(ob); ob.visible_camera = False
    ob.location = (it["x"] + off[0], it["y"] + off[1], off[2]); C.aim(ob, (it["x"], it["y"], 0.0))
    SPOT[it["key"]] = ob


def ease(x): return C.smooth(x)


def light_on(i, t):
    """share of item i's light that is on at time t (linear power; the eye sees it come up evenly)"""
    if MODE == "sweep": return ease((t - TL["t_rev"][i]) / (0.35 * G.REV)) ** 2.2
    return ease((t - TL["t_rev"][i]) / (0.85 * G.REV)) ** 2.2


def dim(i, t):
    """1 while item i is the subject; DIM once the camera has moved on to the next item"""
    if i == NI - 1: return 1.0
    return 1.0 - (1.0 - DIM) * ease((t - TL["end"][i]) / G.ARR)


def level(i, t): return light_on(i, t) * dim(i, t)


def reveal_value(i, t):
    """value driving the picture: the fade (spot) or the position of the sweeping edge"""
    if MODE == "sweep":
        x = min(max((t - TL["t_rev"][i]) / G.REV, 0.0), 1.0)
        return -0.05 + (1.0 + SOFT + 0.05) * (1 - (1 - x) ** 2)
    return light_on(i, t)


def beam_target(i, t):
    it = ITEMS[i]
    if MODE != "sweep": return (it["x"], it["y"], 0.0)
    x = min(max((t - TL["t_rev"][i]) / G.REV, 0.0), 1.0); s = 1 - (1 - x) ** 2
    return (it["x"] - (1 - s) * 1.0 * it["w"], it["y"], 0.0)


# ------------------------------------------------------------------ camera
TG, DD, AZ, VIEW = G.camera_path(ITEMS, TL, T, EL, LENS, FILL, FPS)


camd = bpy.data.cameras.new("cam"); camd.lens = LENS; camd.sensor_width = 36; camd.clip_start = 0.01; camd.clip_end = 200
camd.dof.use_dof = True; camd.dof.aperture_fstop = 5.6
cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
for fr in range(1, FRAMES + 1):
    t = (fr - 1) / FPS
    tg = Vector(TG[fr - 1]); cam.location = tg + float(DD[fr - 1]) * Vector(G.cam_dir(EL, float(AZ[fr - 1]))); C.aim(cam, tg)
    cam.keyframe_insert("location", frame=fr); cam.keyframe_insert("rotation_euler", frame=fr)
    camd.dof.focus_distance = float(DD[fr - 1]); camd.dof.keyframe_insert("focus_distance", frame=fr)
    for i, it in enumerate(ITEMS):
        k = it["key"]; sp = SPOT[k]
        sp.data.energy = E_SPOT * max(it["w"], it["h"]) ** 2 * level(i, t); sp.data.keyframe_insert("energy", frame=fr)
        if MODE == "sweep":
            C.aim(sp, beam_target(i, t)); sp.keyframe_insert("rotation_euler", frame=fr)
        nd = REVN[k].outputs[0]; nd.default_value = reveal_value(i, t); nd.keyframe_insert("default_value", frame=fr)
        nd = REVD[k].outputs[0]; nd.default_value = dim(i, t); nd.keyframe_insert("default_value", frame=fr)


def linear(idb):
    ad = getattr(idb, "animation_data", None)
    for fc in (ad.action.fcurves if ad and ad.action else []):
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"


for idb in [cam, camd] + [SPOT[k] for k in KEYS] + [SPOT[k].data for k in KEYS] + [OBJ[k].active_material.node_tree for k in KEYS]:
    linear(idb)

sc.frame_start, sc.frame_end = 1, FRAMES
C.setup_cycles(sc, O, samples=int(P.get("samples", 48)), motion_blur=True, look="None")
sc.view_settings.view_transform = "Standard"                       # pictures keep their exact colours
try: sc.view_settings.look = "None"
except Exception: pass
bpy.app.handlers.frame_change_pre.append(exact_pictures)
exact_pictures(sc)
print(f"built: {NI} items on the {SETTING}, reveal {MODE}, reveals at {', '.join(f'{x:.1f}' for x in TL['t_rev'])} s, "
      f"hold {TL['hold']:.1f} s, camera distances {', '.join(f'{v[1]:.2f}' for v in VIEW)}", flush=True)

# ------------------------------------------------------------------ preview: labels + checks + exposure + key frames
if O.preview:
    errors, warnings = [], []
    stats = {"credits": meta.get("credits", []), "timeline": {k: (v if not isinstance(v, list) else [None if x is None else round(x, 2) for x in v])
             for k, v in TL.items()}, "layout": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in it.items()} for it in ITEMS],
             "camera_distance": [round(v[1], 3) for v in VIEW], "min_gap": None if MIN_GAP is None else round(MIN_GAP, 3),
             "gap_used": GAP_USED, "slivers_planned": SLIVERS}
    if MIN_GAP is not None and MIN_GAP < 0.1: errors.append(f"items too close or overlapping on the desk (gap {MIN_GAP:.2f})")
    sc.frame_set(1)                                                   # evaluates matrix_world of every object
    BVH = {k: BVHTree.FromPolygons([Vector(v) for v in MESH[k][0]], MESH[k][1].tolist()) for k in KEYS}
    MW = {k: OBJ[k].matrix_world.copy() for k in KEYS}
    IV = {k: (MW[k].inverted(), MW[k].inverted().to_3x3()) for k in KEYS}
    DI = {it["key"]: it for it in ITEMS}

    def cast(o, d):
        best, res = 1e30, None
        for k in KEYS:
            mi, m3 = IV[k]; lo = mi @ o; ld_ = (m3 @ d).normalized()
            h = BVH[k].ray_cast(lo, ld_)
            if h[0] is None: continue
            dw = ((MW[k] @ h[0]) - o).length
            if dw < best: best, res = dw, (k, h[0])
        return res

    def classify(f):
        t = (f - 1) / FPS; o, rows = C.cam_rays(sc, cam)
        lit = [i for i in range(NI) if level(i, t) >= 0.9]
        out = []
        for row in rows:
            s = ""
            for d in row:
                r = cast(o, d)
                if r is not None:
                    it = DI[r[0]]; x, y = r[1].x, r[1].y
                    s += "i" if abs(x) < it["iw"] / 2 and abs(y) < it["ih"] / 2 else "p"; continue
                if d.z >= -1e-6: s += "k"; continue
                q = o + d * (-o.z / d.z)
                s += "r" if any((q.x - ITEMS[i]["x"]) ** 2 + (q.y - ITEMS[i]["y"]) ** 2 < (0.8 * RCOV[KEYS[i]]) ** 2 for i in lit) else "d"
            out.append(s)
        return out

    def corners3(k):
        it = DI[k]; c = G.corners(it); return [Vector((x, y, LIFT[k])) for x, y in c] + [Vector((x, y, 0.0)) for x, y in c]

    # labels: a dot under the bottom edge near its left end, the text running to the right (as the overlay draws it),
    # from the end of the reveal until the camera leaves; the text stays inside the frame and off the other items
    LAB = [e for e in P.get("labels", []) if e[0] in KEYS]
    tracks = {e[0]: [] for e in LAB}
    CHW = 0.5 * 45                                                    # px per character of the label font at 1920 x 1080
    LW = {e[0]: 18 + CHW * len(e[1] if len(e) > 1 else e[0]) for e in LAB}
    cut, small, lout, lover, sliver = {}, {}, {}, {}, {}

    def box(k):
        vs = [world_to_camera_view(sc, cam, p) for p in corners3(k)[:4]]
        return min(p.x for p in vs), max(p.x for p in vs), min(p.y for p in vs), max(p.y for p in vs), min(p.z for p in vs)

    def crosses(k, x0, x1, y0, y1):
        """does the text box [x0, x1] x [y0, y1] (px, y down) touch the item k as the camera sees it?"""
        q = [(p.x * 1920, (1 - p.y) * 1080, p.z) for p in (world_to_camera_view(sc, cam, c) for c in corners3(k)[:4])]
        if any(p[2] <= 0 for p in q): return False
        n = len(q); area = sum(q[j][0] * q[(j + 1) % n][1] - q[(j + 1) % n][0] * q[j][1] for j in range(n))
        for gx in np.linspace(x0, x1, 16):
            for gy in np.linspace(y0, y1, 4):
                if all(((q[(j + 1) % n][0] - q[j][0]) * (gy - q[j][1]) - (q[(j + 1) % n][1] - q[j][1]) * (gx - q[j][0])) * area >= 0
                       for j in range(n)): return True
        return False

    for fr in range(1, FRAMES + 1):
        sc.frame_set(fr); t = (fr - 1) / FPS
        for e in LAB:
            i = KEYS.index(e[0]); it = ITEMS[i]; a = math.radians(it["rot"])
            xx, yy = -0.44 * it["w"], -it["h"] / 2 - 0.012
            pw = Vector((it["x"] + math.cos(a) * xx - math.sin(a) * yy, it["y"] + math.sin(a) * xx + math.cos(a) * yy, 0.0))
            v = world_to_camera_view(sc, cam, pw); px, py = v.x * 1920, (1 - v.y) * 1080 + 34
            on = TL["t_rev"][i] + G.REV + 0.15 <= t < TL["end"][i] or (i == NI - 1 and t >= TL["t_rev"][i] + G.REV + 0.15)
            vis = on and 0.02 <= v.x <= 0.98 and 0.06 <= v.y <= 0.98 and v.z > 0
            if vis:
                if px + LW[e[0]] > 0.97 * 1920 or py + 20 > 0.97 * 1080: lout.setdefault(e[0], []).append(round(t, 1))
                for k2 in KEYS:
                    if k2 != e[0] and crosses(k2, px, px + LW[e[0]], py - 27, py + 20): lover.setdefault(e[0], set()).add(k2)
            tracks[e[0]].append([round(px, 1), round(py, 1), int(vis)])
        if fr % 3 and fr != FRAMES: continue
        for i, k in enumerate(KEYS):
            if not (TL["t_rev"][i] + G.REV <= t < TL["end"][i] or (i == NI - 1 and t >= TL["t_rev"][i] + G.REV)): continue
            vs = [world_to_camera_view(sc, cam, p) for p in corners3(k)]
            if any(p.x < 0.03 or p.x > 0.97 or p.y < 0.05 or p.y > 0.96 or p.z <= 0 for p in vs):
                cut.setdefault(k, []).append(round(t, 1))
            span = max(max(p.x for p in vs) - min(p.x for p in vs), (max(p.y for p in vs) - min(p.y for p in vs)))
            if span < 0.45: small.setdefault(k, []).append(round(span, 2))
        if any(TL["t_arr"][j] is not None and TL["t_arr"][j] <= t < TL["t_rev"][j] for j in range(NI)): continue
        for i, k in enumerate(KEYS):                                  # a revealed item barely inside the frame looks like a mistake
            if t < TL["t_rev"][i] + 0.5 * G.REV: continue
            x0, x1, y0, y1, z0 = box(k)
            if z0 <= 0: continue
            fx = (min(x1, 1) - max(x0, 0)) / max(x1 - x0, 1e-6); fy = (min(y1, 1) - max(y0, 0)) / max(y1 - y0, 1e-6)
            if (0 < fx < G.SLIVER and fy > 0) or (0 < fy < G.SLIVER and fx > 0): sliver.setdefault(k, []).append(round(t, 1))
    names = [[e[0], e[1] if len(e) > 1 else e[0], e[2] if len(e) > 2 else ""] for e in LAB]
    json.dump({"fps": FPS, "frames": FRAMES, "tracks": tracks, "names": names}, open(f"{O.out}/labels.json", "w"))
    vis_s = {k: round(sum(x[2] for x in v) / FPS, 2) for k, v in tracks.items()}
    stats["labels_visible_s"] = vis_s
    for k, s_ in vis_s.items():
        if s_ < 1.0: warnings.append(f"label {k} visible only {s_:.1f} s")
    for k, ts_ in lout.items(): errors.append(f"label {k} runs out of the frame ({ts_[0]:.1f}-{ts_[-1]:.1f} s): shorten it")
    for k, ks in lover.items(): errors.append(f"label {k} crosses item(s) {', '.join(sorted(ks))}")
    for k, ts_ in sliver.items(): errors.append(f"only a thin sliver of item {k} shows at the frame edge ({ts_[0]:.1f}-{ts_[-1]:.1f} s)")
    for k, ts_ in cut.items(): errors.append(f"item {k} is cut by the frame edge while it is held ({ts_[0]:.1f}-{ts_[-1]:.1f} s)")
    for k, sp_ in small.items(): warnings.append(f"item {k} is small in the frame while held ({min(sp_):.0%} of the frame)")

    # key frames: every item held (picture readable), then its reveal under way (the sweeping edge shows)
    holds, revs = [], []
    for i in range(NI):
        a = TL["t_rev"][i] + G.REV + 0.2; b = TL["end"][i] - 0.15
        holds.append([int(round((a + q * (b - a)) * FPS)) + 1 for q in (0.6, 0.15, 0.95)])
        revs.append(int(round((TL["t_rev"][i] + 0.60 * G.REV) * FPS)) + 1)
    order = [h[0] for h in holds] + revs + [h[1] for h in holds] + [h[2] for h in holds]
    KEYF = []
    for f in order:
        f = int(min(max(f, 1), FRAMES))
        if all(abs(f - g) >= 6 for g in KEYF): KEYF.append(f)
        if len(KEYF) == 6: break
    KEYF = sorted(KEYF)
    C.key_frames = lambda n, k=6: list(KEYF)
    stats["hold_frames"] = [h[0] for h in holds]

    def held(t):
        for i in range(NI):
            if TL["t_rev"][i] + G.REV <= t < TL["end"][i] or (i == NI - 1 and t >= TL["t_rev"][i] + G.REV): return i
        return None

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
        acc = {k: [] for k in KEYS}; acc_all = {k: [] for k in KEYS}
        lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0.0), 1 / 2.4) - 0.055)
        yl = lambda c: lin(c) @ np.array([0.2126, 0.7152, 0.0722])
        seen = {}

        def seen_as(k, by, bx):
            """the picture as the camera sees it at that size: means in linear light over by x bx source pixels"""
            if (k, by, bx) not in seen:
                a = imgs[k]
                if by > 1 or bx > 1:
                    h2, w2 = a.shape[0] // by * by, a.shape[1] // bx * bx
                    a = srgb(lin(a[:h2, :w2]).reshape(h2 // by, by, w2 // bx, bx, 3).mean(axis=(1, 3)))
                seen[(k, by, bx)] = a
            return seen[(k, by, bx)]

        for f in ck["key_frames"]:
            t = (f - 1) / FPS; i = held(t)
            if i is None: continue
            key = KEYS[i]; it = DI[key]; fa = imgs[key]
            rend = pixels(os.path.join(O.out, f"p_{f:04d}{ck.get('ext', '.jpg')}"))[::-1]
            rh_, rw_ = rend.shape[:2]
            sc.frame_set(f); o, rows = C.cam_rays(sc, cam, nx, ny)
            cv = [world_to_camera_view(sc, cam, MW[key] @ Vector((sx * it["iw"] / 2, sy * it["ih"] / 2, 0.0))) for sx in (-1, 1) for sy in (-1, 1)]
            wpx = (max(p.x for p in cv) - min(p.x for p in cv)) * rw_; hpx = (max(p.y for p in cv) - min(p.y for p in cv)) * rh_
            fa = seen_as(key, max(1, int(round(fa.shape[0] / max(hpx, 1.0)))), max(1, int(round(fa.shape[1] / max(wpx, 1.0)))))
            hk = np.zeros((ny, nx), bool); ex = np.zeros((ny, nx, 3), np.float32)
            for j, row in enumerate(rows):
                for i_, d in enumerate(row):
                    r = cast(o, d)
                    if r is None or r[0] != key: continue
                    x, y = r[1].x, r[1].y
                    if not (abs(x) < it["iw"] / 2 and abs(y) < it["ih"] / 2): continue
                    u, v = x / it["iw"] + 0.5, y / it["ih"] + 0.5
                    ex[j, i_] = fa[min(max(int(v * fa.shape[0]), 0), fa.shape[0] - 1), min(max(int(u * fa.shape[1]), 0), fa.shape[1] - 1)]
                    hk[j, i_] = True
            ok = hk.copy()
            pk = np.pad(hk, 2, constant_values=False); pe = np.pad(ex, ((2, 2), (2, 2), (0, 0)))
            for dj in range(-2, 3):
                for di in range(-2, 3):
                    ok &= pk[2 + dj:2 + dj + ny, 2 + di:2 + di + nx]
            inner = ok.copy()
            for dj in range(-1, 2):
                for di in range(-1, 2):
                    ok &= np.abs(pe[2 + dj:2 + dj + ny, 2 + di:2 + di + nx] - ex).max(-1) < 0.04
            for j, i_ in zip(*np.nonzero(inner)):
                r_ = rend[min(int((j + 0.5) / ny * rh_), rh_ - 1), min(int((i_ + 0.5) / nx * rw_), rw_ - 1)]
                acc_all[key].append((r_, ex[j, i_]))
                if ok[j, i_]: acc[key].append((r_, ex[j, i_]))
        res, errs, warns = {}, [], []

        def gain(r_, e_):
            """brightness offset (EV) from the means in linear light over the cells that are not near black"""
            br = yl(e_) >= 0.02
            if br.sum() < 12: return None, int(br.sum())
            return float(np.log2(max(yl(r_)[br].mean(), 1e-5) / max(yl(e_)[br].mean(), 1e-5))), int(br.sum())

        for k, v in acc.items():
            if len(v) < 12:                                           # a textured picture: brightness over all its inner cells
                w_ = acc_all[k]
                if len(w_) < 40: warns.append(f"picture {k}: too few cells to measure its colours ({len(w_)})"); continue
                r_ = np.array([a for a, _ in w_]); e_ = np.array([b for _, b in w_])
                evo, nb = gain(r_, e_)
                if evo is None: warns.append(f"picture {k}: too dark to measure its brightness"); continue
                res[k] = {"ev_offset": round(evo, 3), "cells": len(w_), "bright_cells": nb, "mode": "all"}
                if abs(evo) > 0.25: errs.append(f"picture {k} renders off its true brightness ({evo:+.2f} EV)")
                continue
            r_ = np.array([a for a, _ in v]); e_ = np.array([b for _, b in v])
            dmed = float(np.median(np.abs(r_ - e_).max(-1)) * 255)
            evo, nb = gain(r_, e_)
            if evo is None:                                           # flat dark cells: the brightness comes from all inner cells
                w_ = acc_all[k]; evo, nb = gain(np.array([a for a, _ in w_]), np.array([b for _, b in w_])) if len(w_) >= 40 else (None, 0)
            res[k] = {"median_diff": round(dmed, 1), "ev_offset": None if evo is None else round(evo, 3), "cells": len(v), "bright_cells": nb}
            if dmed > 16 or (evo is not None and abs(evo) > 0.2):
                errs.append(f"picture {k} renders off its true colours (median difference {dmed:.0f}/255, {0.0 if evo is None else evo:+.2f} EV)")
            elif dmed > 9: warns.append(f"picture {k} colours slightly off (median difference {dmed:.0f}/255)")
        lo_, hi_ = EV_RANGE
        if min(abs(ck["ev"] - lo_), abs(ck["ev"] - hi_)) < 0.02:
            errs.append(f"the exposure stopped at its limit ({ck['ev']:+.2f} EV): the light levels are off for this scene")
        ck["errors"] = ck.get("errors", []) + errs; ck["warnings"] = ck.get("warnings", []) + warns
        ck.setdefault("stats", {})["picture_fidelity"] = res
        json.dump(ck, open(cp, "w"))
        print(f"picture colours: {res}", flush=True)

    # exposure on the lit surface around the items (the pictures do not depend on it)
    target = 0.12 if SETTING == "desk" else 0.09                       # a dark desk with a warm pool of light
    EV_RANGE = (-3.0, 3.0)
    C.preview_run(sc, O, FRAMES, classify, subject=("r",), target=target, tol=round(0.25 * target, 3),
                  ev_range=EV_RANGE, stats=stats, errors=errors, warnings=warnings, dark_max=0.92 if SETTING == "desk" else 0.97)
    picture_fidelity()
    sys.exit(0)

# ------------------------------------------------------------------ render
C.render_frames(sc, O.out, list(range(O.start, END + 1)), O.budget)
