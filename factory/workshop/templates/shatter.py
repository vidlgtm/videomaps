"""Workshop template 'shatter' - map pieces as 3D slabs over a base map (Blender Cycles).
break : the union flag spans all pieces as one slab with a gold rim; the shared borders crack with light, the pieces
        split apart and lift one after another, and each top wipes from the union flag to its own flag
rise  : pieces lift out of the map - their tops first show the land, then wipe to their flags - leaving dark sockets
drop  : pieces fall into place one after another, fading in, and land with a light ring in their own outline
look  : flag tops with a gold rim, dark slab sides, soft sun shadows on the base, vignette toward the edges of the view
labels: per-frame 2D positions of each labelled piece (a point inside its shape, moving with it; hidden when another
        piece covers it), so the engine pins the names exactly
usage: blender -b -P shatter.py -- --params p.json --data <prep dir> --out <dir> [--start 1 --end N --gpu OPTIX --ev X
       --budget-min M | --preview]
params: seconds; action; camera {target [lon, lat], span [km, km], heading [deg, deg], tilt [deg, deg]}; pieces
        [{key, ..., fit, focus}]; union {fit, focus}; order; thickness / lift / spread (fractions of the start span);
        rim (frame px); base_dim; sun {elevation, azimuth (relative to the frame)}; lens; samples; timing; labels"""
import bpy, os, sys, json, math, zlib
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import shatter_time as ST

P, O = C.args()
DATA = O.data
SEC = float(P.get("seconds", 10)); FPS = 30
FRAMES = int(round(SEC * FPS)); END = O.end or FRAMES
meta = json.load(open(f"{DATA}/meta.json"))
NPZ = np.load(f"{DATA}/pieces.npz")
W, H, NM, X0, Y0 = meta["w"], meta["h"], meta["N"], meta["x0"], meta["y0"]
SB = 100.0 / max(W, H)
ACT = P["action"]
PIECES = P["pieces"]; PK = [pc["key"] for pc in PIECES]; PM = {i["key"]: i for i in meta["pieces"]}
n = len(PIECES)
SCH = ST.schedule(ACT, SEC, n, P.get("timing"))
CAM = P["camera"]
LT, LA = CAM["target"]
mx = lambda lon: (lon + 180) / 360 * NM - X0
my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * NM - Y0
MPP = 40075016.686 * math.cos(math.radians(LA)) / NM
km = lambda v: v * 1000.0 / MPP * SB
wx = lambda x: (x - W / 2) * SB
wy = lambda y: (H / 2 - y) * SB
TGT = Vector((wx(mx(LT)), wy(my(LA)), 0.0))
SPAN0 = km(float(CAM["span"][0]))
THICK = float(P.get("thickness", 0.014)) * SPAN0
LIFT = float(P.get("lift", 0.05 if ACT == "break" else 0.08)) * SPAN0
SPREAD = float(P.get("spread", 0.07)) * SPAN0
PX_FRAME = SPAN0 / SB / 1920.0                       # base px per frame px at the target, start of the clip
RIM = float(P.get("rim", 3.5)) * PX_FRAME
AA = 0.7 * PX_FRAME
CW = 1.25 * RIM + 0.5 * AA
SAT = meta["base"] == "satellite"
DIM = float(P.get("base_dim", 0.72 if SAT else 1.0))
VIG = 0.45 if SAT else 0.4
LENS = float(P.get("lens", 45))
rnd = lambda key, salt: (zlib.crc32(f"{key}/{salt}".encode()) % 10007) / 10007.0

sc = C.reset(FPS)


def nodes_of(m):
    nt = m.node_tree
    for x in list(nt.nodes): nt.nodes.remove(x)
    return nt.nodes, nt.links, nt.nodes.new("ShaderNodeOutputMaterial")


def math_node(N, L, op, a, b=None):
    m = N.new("ShaderNodeMath"); m.operation = op
    for i, v in enumerate((a, b)):
        if v is None: continue
        if isinstance(v, (int, float)): m.inputs[i].default_value = float(v)
        else: L.new(v, m.inputs[i])
    return m.outputs[0]


def smoothstep(N, L, x, lo, hi):
    """smoothstep of socket x between lo and hi (numbers or sockets)"""
    mr = N.new("ShaderNodeMapRange"); mr.interpolation_type = "SMOOTHSTEP"; mr.clamp = True
    L.new(x, mr.inputs["Value"])
    for name, v in (("From Min", lo), ("From Max", hi)):
        if isinstance(v, (int, float)): mr.inputs[name].default_value = float(v)
        else: L.new(v, mr.inputs[name])
    return mr.outputs["Result"]


def uvmap(N, name):
    u = N.new("ShaderNodeUVMap"); u.uv_map = name
    return u.outputs["UV"]


def image(N, L, img, uv, interp="Linear"):
    t = N.new("ShaderNodeTexImage"); t.image = img; t.interpolation = interp; t.extension = "EXTEND"
    L.new(uv, t.inputs["Vector"])
    return t


def value(N, v=0.0):
    x = N.new("ShaderNodeValue"); x.outputs[0].default_value = v
    return x


def mixc(N, L, fac, a, b):
    m = N.new("ShaderNodeMix"); m.data_type = "RGBA"
    for i, v in ((0, fac), (6, a), (7, b)):
        if isinstance(v, (int, float)): m.inputs[i].default_value = float(v)
        elif isinstance(v, tuple): m.inputs[i].default_value = v
        else: L.new(v, m.inputs[i])
    return m.outputs[2]


def vignette(N, L):
    geo = N.new("ShaderNodeNewGeometry"); sp = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Position"], sp.inputs[0])
    dx = math_node(N, L, "SUBTRACT", sp.outputs[0], TGT.x); dy = math_node(N, L, "SUBTRACT", sp.outputs[1], TGT.y)
    d = math_node(N, L, "SQRT", math_node(N, L, "ADD", math_node(N, L, "MULTIPLY", dx, dx), math_node(N, L, "MULTIPLY", dy, dy)))
    s = smoothstep(N, L, d, 0.55 * SPAN0, 1.6 * SPAN0)
    return math_node(N, L, "SUBTRACT", 1.0, math_node(N, L, "MULTIPLY", s, VIG))


def scale_color(N, L, col, f):
    m = N.new("ShaderNodeMix"); m.data_type = "RGBA"; m.blend_type = "MULTIPLY"; m.inputs[0].default_value = 1.0
    L.new(col, m.inputs[6])
    if isinstance(f, (int, float)): m.inputs[7].default_value = (f, f, f, 1)
    else:
        cc = N.new("ShaderNodeCombineColor"); [L.new(f, cc.inputs[i]) for i in range(3)]; L.new(cc.outputs[0], m.inputs[7])
    return m.outputs[2]


def base_color(N, L, col):
    """base map colour: dark water lifted a little (gamma), dimmed, vignette toward the edges of the view"""
    g = N.new("ShaderNodeGamma"); g.inputs["Gamma"].default_value = 0.85; L.new(col, g.inputs["Color"])
    c = scale_color(N, L, scale_color(N, L, g.outputs["Color"], DIM), vignette(N, L))
    m = N.new("ShaderNodeMix"); m.data_type = "RGBA"; m.blend_type = "ADD"; m.inputs[0].default_value = 1.0
    L.new(c, m.inputs[6]); m.inputs[7].default_value = (0.004, 0.0045, 0.006, 1)
    return m.outputs[2]


def keyval(node, v, f):
    node.outputs[0].default_value = v; node.outputs[0].keyframe_insert("default_value", frame=f)


# ------------------------------------------------------------------ images
def load(path, color=True):
    img = bpy.data.images.load(os.path.abspath(path), check_existing=True)
    if not color:
        try: img.colorspace_settings.name = "Non-Color"
        except Exception: pass
    return img


def float_image(name, arr):
    """float data -> OpenEXR file -> image (an image only made in memory renders black)"""
    h, w = arr.shape[:2]
    tmp = bpy.data.images.new(name + "_tmp", w, h, alpha=True, float_buffer=True)
    try: tmp.colorspace_settings.name = "Non-Color"     # data: no colour conversion when the file is written
    except Exception: pass
    rgba = np.ones((h, w, 4), np.float32); rgba[..., :3] = arr[::-1]
    tmp.pixels.foreach_set(rgba.ravel())
    path = os.path.abspath(os.path.join(DATA, f"{name}.exr"))
    tmp.filepath_raw = path; tmp.file_format = "OPEN_EXR"; tmp.save()
    bpy.data.images.remove(tmp)
    img = bpy.data.images.load(path, check_existing=False)
    try: img.colorspace_settings.name = "Non-Color"
    except Exception: pass
    px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    SDF_MAX[name] = [round(float(px.reshape(-1, 4)[:, 0].max()), 2), round(float(arr[..., 0].max()), 2)]
    return img


SDF_MAX = {}


BASE_IMG = load(f"{DATA}/base.jpg")
UNION_IMG = load(f"{DATA}/{meta['union']['flag']['file']}") if meta.get("union") else None

# ------------------------------------------------------------------ base map
bv = np.array([[wx(0), wy(H), 0], [wx(W), wy(H), 0], [wx(W), wy(0), 0], [wx(0), wy(0), 0]], np.float32)
base = C.mesh_object("Base", bv, quads=np.array([[0, 1, 2, 3]]))
uvl = base.data.uv_layers.new(name="UVMap"); uvl.data.foreach_set("uv", np.array([0, 0, 1, 0, 1, 1, 0, 1], np.float32))
bm = bpy.data.materials.new("base"); bm.use_nodes = True
N_, L_, out = nodes_of(bm)
bt = image(N_, L_, BASE_IMG, uvmap(N_, "UVMap"), "Cubic")
bcol = base_color(N_, L_, bt.outputs["Color"])
dif = N_.new("ShaderNodeBsdfDiffuse"); L_.new(bcol, dif.inputs["Color"]); dif.inputs["Roughness"].default_value = 0.8
L_.new(dif.outputs[0], out.inputs["Surface"])
C.put(base, bm)

# ------------------------------------------------------------------ pieces
def place(bounds, aspect, fit, focus):
    bx0, by0, bx1, by1 = bounds; bw, bh = bx1 - bx0, by1 - by0
    cover = fit != "contain"
    if (bw / bh > aspect) == cover: rw, rh = bw, bw / aspect
    else: rw, rh = bh * aspect, bh
    fu, fv = focus
    rx0, ry0 = bx0 + bw / 2 - fu * rw, by0 + bh / 2 - fv * rh
    lo_x, hi_x = (bx1 - rw, bx0) if cover else (bx0, bx1 - rw)
    lo_y, hi_y = (by1 - rh, by0) if cover else (by0, by1 - rh)
    rx0 = min(max(rx0, min(lo_x, hi_x)), max(lo_x, hi_x)); ry0 = min(max(ry0, min(lo_y, hi_y)), max(lo_y, hi_y))
    return rx0, ry0, rw, rh


UNION = P.get("union") or {}
if meta.get("union"):
    U_RECT = place(meta["union"]["bounds"], meta["union"]["flag"]["aspect"], UNION.get("fit", "cover"), UNION.get("focus", [0.5, 0.5]))
OBJ, HND, LOCAL, NTOP, CEN, SOCK, RING = {}, {}, {}, {}, {}, {}, {}
tri_total = 0


def top_material(k, pc, pm, own_img, sdf_img):
    m = bpy.data.materials.new(f"top_{k}"); m.use_nodes = True
    N_, L_, out = nodes_of(m)
    own = image(N_, L_, own_img, uvmap(N_, "UVown"), "Cubic")
    sdf = image(N_, L_, sdf_img, uvmap(N_, "UVsdf"))
    sep = N_.new("ShaderNodeSeparateColor"); L_.new(sdf.outputs["Color"], sep.inputs[0])
    R, G = sep.outputs[0], sep.outputs[1]
    box = N_.new("ShaderNodeSeparateXYZ"); L_.new(uvmap(N_, "UVbox"), box.inputs[0])
    s = math_node(N_, L_, "ADD", math_node(N_, L_, "MULTIPLY", box.outputs[0], 0.8),
                  math_node(N_, L_, "MULTIPLY", math_node(N_, L_, "SUBTRACT", 1.0, box.outputs[1]), 0.2))
    wipe = value(N_, 2.0)
    soft = 0.07
    fac = math_node(N_, L_, "SUBTRACT", 1.0, smoothstep(N_, L_, s, math_node(N_, L_, "SUBTRACT", wipe.outputs[0], soft),
                                                       math_node(N_, L_, "ADD", wipe.outputs[0], soft)))
    dd = math_node(N_, L_, "DIVIDE", math_node(N_, L_, "SUBTRACT", s, wipe.outputs[0]), soft)
    glow = math_node(N_, L_, "EXPONENT", math_node(N_, L_, "MULTIPLY", math_node(N_, L_, "MULTIPLY", dd, dd), -1.0))
    pnew = N_.new("ShaderNodeBsdfPrincipled"); L_.new(own.outputs["Color"], pnew.inputs["Base Color"])
    pnew.inputs["Roughness"].default_value = 0.42
    try: pnew.inputs["Coat Weight"].default_value = 0.18
    except Exception: pass
    if ACT == "break":
        un = image(N_, L_, UNION_IMG, uvmap(N_, "UVunion"), "Cubic")
        pold = N_.new("ShaderNodeBsdfPrincipled"); L_.new(un.outputs["Color"], pold.inputs["Base Color"])
        pold.inputs["Roughness"].default_value = 0.42
        try: pold.inputs["Coat Weight"].default_value = 0.18
        except Exception: pass
    elif ACT == "rise":
        land = image(N_, L_, BASE_IMG, uvmap(N_, "UVbase"), "Cubic")
        pold = N_.new("ShaderNodeBsdfDiffuse"); pold.inputs["Roughness"].default_value = 0.8
        L_.new(base_color(N_, L_, land.outputs["Color"]), pold.inputs["Color"])
    else:
        pold = pnew
    flagmix = N_.new("ShaderNodeMixShader"); L_.new(fac, flagmix.inputs[0]); L_.new(pold.outputs[0], flagmix.inputs[1]); L_.new(pnew.outputs[0], flagmix.inputs[2])
    # gold rim; its parts along the shared borders only show from the crack on (one seamless slab before)
    rim = math_node(N_, L_, "SUBTRACT", 1.0, smoothstep(N_, L_, R, RIM - AA, RIM + AA))
    inner = math_node(N_, L_, "SUBTRACT", 1.0, smoothstep(N_, L_, G, CW - AA, CW + AA))
    show = value(N_, 1.0)
    hide = math_node(N_, L_, "MULTIPLY", inner, math_node(N_, L_, "SUBTRACT", 1.0, show.outputs[0]))
    rimv = math_node(N_, L_, "MULTIPLY", rim, math_node(N_, L_, "SUBTRACT", 1.0, hide)) if RIM > 0 else 0.0
    gold = N_.new("ShaderNodeBsdfPrincipled"); gold.inputs["Base Color"].default_value = (0.86, 0.63, 0.26, 1)
    gold.inputs["Metallic"].default_value = 1.0; gold.inputs["Roughness"].default_value = 0.3
    rmix = N_.new("ShaderNodeMixShader")
    if isinstance(rimv, float): rmix.inputs[0].default_value = 0.0
    else: L_.new(rimv, rmix.inputs[0])
    L_.new(flagmix.outputs[0], rmix.inputs[1]); L_.new(gold.outputs[0], rmix.inputs[2])
    crack = value(N_, 0.0)
    estr = math_node(N_, L_, "ADD", math_node(N_, L_, "MULTIPLY", math_node(N_, L_, "MULTIPLY", inner, crack.outputs[0]), 9.0),
                     math_node(N_, L_, "MULTIPLY", glow, 1.6))
    em = N_.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.86, 0.62, 1); L_.new(estr, em.inputs["Strength"])
    add = N_.new("ShaderNodeAddShader"); L_.new(rmix.outputs[0], add.inputs[0]); L_.new(em.outputs[0], add.inputs[1])
    alpha = value(N_, 1.0)
    tr = N_.new("ShaderNodeBsdfTransparent")
    am = N_.new("ShaderNodeMixShader"); L_.new(alpha.outputs[0], am.inputs[0]); L_.new(tr.outputs[0], am.inputs[1]); L_.new(add.outputs[0], am.inputs[2])
    L_.new(am.outputs[0], out.inputs["Surface"])
    return m, {"wipe": wipe, "show": show, "crack": crack, "alpha": alpha}


def side_material(k):
    m = bpy.data.materials.new(f"side_{k}"); m.use_nodes = True
    N_, L_, out = nodes_of(m)
    tc = N_.new("ShaderNodeTexCoord"); sp = N_.new("ShaderNodeSeparateXYZ"); L_.new(tc.outputs["Object"], sp.inputs[0])
    z = math_node(N_, L_, "DIVIDE", sp.outputs[2], max(THICK, 1e-6))
    col = mixc(N_, L_, smoothstep(N_, L_, z, 0.0, 1.0), (0.022, 0.025, 0.031, 1), (0.105, 0.11, 0.125, 1))
    pb = N_.new("ShaderNodeBsdfPrincipled"); L_.new(col, pb.inputs["Base Color"]); pb.inputs["Roughness"].default_value = 0.45
    alpha = value(N_, 1.0)
    tr = N_.new("ShaderNodeBsdfTransparent")
    am = N_.new("ShaderNodeMixShader"); L_.new(alpha.outputs[0], am.inputs[0]); L_.new(tr.outputs[0], am.inputs[1]); L_.new(pb.outputs[0], am.inputs[2])
    L_.new(am.outputs[0], out.inputs["Surface"])
    return m, alpha


for pc in PIECES:
    k = pc["key"]; pm = PM[k]
    V = NPZ[f"{k}_v"].astype(np.float64); T = NPZ[f"{k}_t"].astype(np.int64)
    RL = NPZ[f"{k}_rl"]; RT = NPZ[f"{k}_rt"]
    Xw, Yw = wx(V[:, 0]), wy(V[:, 1])
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    cz = (Xw[b] - Xw[a]) * (Yw[c] - Yw[a]) - (Xw[c] - Xw[a]) * (Yw[b] - Yw[a])
    T[cz < 0] = T[cz < 0][:, [0, 2, 1]]
    area = np.abs(cz) / 2
    cx = float((area * (Xw[a] + Xw[b] + Xw[c]) / 3).sum() / area.sum()); cy = float((area * (Yw[a] + Yw[b] + Yw[c]) / 3).sum() / area.sum())
    nv = len(V)
    co = np.zeros((2 * nv, 3)); co[:nv, 0] = co[nv:, 0] = Xw - cx; co[:nv, 1] = co[nv:, 1] = Yw - cy; co[:nv, 2] = THICK
    quads, s0 = [], 0
    for L, ext in zip(RL, RT):
        idx = np.arange(s0, s0 + L); nxt = np.roll(idx, -1)
        ccw = float(np.sum(Xw[idx] * Yw[nxt] - Xw[nxt] * Yw[idx])) > 0
        q = np.stack([idx + nv, nxt + nv, nxt, idx], 1) if ccw == bool(ext) else np.stack([idx, nxt, nxt + nv, idx + nv], 1)
        quads.append(q); s0 += L
    quads = np.concatenate(quads)
    ob = C.mesh_object(f"piece_{k}", co, quads=quads, tris=T)
    me = ob.data
    try: me.shade_flat()
    except Exception:
        at = me.attributes.get("sharp_face") or me.attributes.new("sharp_face", "BOOLEAN", "FACE")
        at.data.foreach_set("value", np.ones(len(me.polygons), bool))
    nt_ = len(T)
    mi = np.zeros(len(me.polygons), np.int32)
    sizes = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", sizes)
    mi[sizes == 4] = 1                                   # sides (quads), tops (triangles) keep 0
    me.polygons.foreach_set("material_index", mi)
    ob.location = (cx, cy, 0.0)
    # uv maps of the top: own flag, union flag, base map, distance field, bounding box
    lvi = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lvi)
    px, py = np.concatenate([V[:, 0], V[:, 0]]), np.concatenate([V[:, 1], V[:, 1]])
    fl = pm["flag"]
    rx0, ry0, rw, rh = place(pm["bounds"], fl["aspect"], pc.get("fit", "cover"), pc.get("focus", [0.5, 0.5]))
    bx0, by0, rr, wr, hr = pm["sdf"]
    mnx, mny, mxx, mxy = pm["bounds"]
    uvs = {"UVown": ((px - rx0) / rw, 1 - (py - ry0) / rh), "UVbase": (px / W, 1 - py / H),
           "UVsdf": ((px - bx0) * rr / wr, 1 - (py - by0) * rr / hr), "UVbox": ((px - mnx) / max(mxx - mnx, 1e-6), 1 - (py - mny) / max(mxy - mny, 1e-6))}
    if meta.get("union"):
        ux0, uy0, uw, uh = U_RECT
        uvs["UVunion"] = ((px - ux0) / uw, 1 - (py - uy0) / uh)
    for name, (u, v) in uvs.items():
        lay = me.uv_layers.new(name=name)
        lay.data.foreach_set("uv", np.stack([u[lvi], v[lvi]], 1).astype(np.float32).ravel())
    sdf_img = float_image(f"sdf_{k}", NPZ[f"{k}_sdf"].astype(np.float32) / 64.0)
    tm, hnd = top_material(k, pc, pm, load(f"{DATA}/{fl['file']}"), sdf_img)
    sm, salpha = side_material(k)
    hnd["salpha"] = salpha
    me.materials.append(tm); me.materials.append(sm)
    C.no_motion_blur(ob)
    OBJ[k], HND[k], NTOP[k], CEN[k] = ob, hnd, nt_, (cx, cy)
    LOCAL[k] = (co.astype(np.float32), [tuple(t) for t in T.tolist()] + [tuple(q) for q in quads.tolist()])
    tri_total += nt_
    if ACT == "rise":   # dark socket left in the map
        so = C.mesh_object(f"socket_{k}", np.column_stack([Xw, Yw, np.full(nv, 0.0006 * SPAN0)]), tris=T)
        m2 = bpy.data.materials.new(f"sock_{k}"); m2.use_nodes = True
        N_, L_, out = nodes_of(m2)
        d2 = N_.new("ShaderNodeBsdfDiffuse"); d2.inputs["Color"].default_value = (0.012, 0.014, 0.018, 1)
        al = value(N_, 0.0); tr = N_.new("ShaderNodeBsdfTransparent")
        am = N_.new("ShaderNodeMixShader"); L_.new(al.outputs[0], am.inputs[0]); L_.new(tr.outputs[0], am.inputs[1]); L_.new(d2.outputs[0], am.inputs[2])
        L_.new(am.outputs[0], out.inputs["Surface"]); C.put(so, m2); SOCK[k] = al
    if ACT == "drop":   # landing ring in the piece's own outline
        qx = [bx0, bx0 + wr / rr, bx0 + wr / rr, bx0]; qy = [by0 + hr / rr, by0 + hr / rr, by0, by0]
        ro = C.mesh_object(f"ring_{k}", np.array([[wx(x), wy(y), 0.0009 * SPAN0] for x, y in zip(qx, qy)]), quads=np.array([[0, 1, 2, 3]]))
        ul = ro.data.uv_layers.new(name="UVMap"); ul.data.foreach_set("uv", np.array([0, 0, 1, 0, 1, 1, 0, 1], np.float32))
        m3 = bpy.data.materials.new(f"ring_{k}"); m3.use_nodes = True
        N_, L_, out = nodes_of(m3)
        st = image(N_, L_, sdf_img, uvmap(N_, "UVMap")); sp3 = N_.new("ShaderNodeSeparateColor"); L_.new(st.outputs["Color"], sp3.inputs[0])
        B = sp3.outputs[2]
        rad, ra = value(N_, 0.0), value(N_, 0.0)
        rw_ = 1.6 * RIM + 2 * AA
        q = math_node(N_, L_, "DIVIDE", math_node(N_, L_, "SUBTRACT", B, rad.outputs[0]), rw_)
        ring = math_node(N_, L_, "EXPONENT", math_node(N_, L_, "MULTIPLY", math_node(N_, L_, "MULTIPLY", q, q), -1.0))
        ring = math_node(N_, L_, "MULTIPLY", ring, smoothstep(N_, L_, B, 0.2 * PX_FRAME, 1.2 * PX_FRAME))
        fa = math_node(N_, L_, "MULTIPLY", ring, ra.outputs[0])
        em = N_.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.85, 0.58, 1); em.inputs["Strength"].default_value = 2.8
        tr = N_.new("ShaderNodeBsdfTransparent")
        am = N_.new("ShaderNodeMixShader"); L_.new(fa, am.inputs[0]); L_.new(tr.outputs[0], am.inputs[1]); L_.new(em.outputs[0], am.inputs[2])
        L_.new(am.outputs[0], out.inputs["Surface"]); C.put(ro, m3); RING[k] = (rad, ra, 0.85 * (mnx - bx0))
        C.no_motion_blur(ro)

# ------------------------------------------------------------------ light
SUN = P.get("sun", {})
el = math.radians(float(SUN.get("elevation", 42)))
az = math.radians(float(CAM.get("heading", [0, 0])[0]) + float(SUN.get("azimuth", 300)))
sdir = Vector((math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)))
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.data.angle = math.radians(5.0)
sun.rotation_euler = sdir.to_track_quat("Z", "Y").to_euler()
wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True
bg = wd.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.10, 0.112, 0.135, 1); bg.inputs["Strength"].default_value = 0.9

# ------------------------------------------------------------------ camera
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = LENS
THX = 18.0 / LENS


def cam_pose(t):
    e = ST.smooth(t / SEC)
    lerp = lambda v: float(v[0]) + (float(v[1]) - float(v[0])) * e
    span = km(lerp(CAM["span"])); hd = math.radians(lerp(CAM.get("heading", [0, 0]))); tl = math.radians(lerp(CAM.get("tilt", [35, 40])))
    d = span / (2 * THX)
    f = Vector((math.sin(tl) * math.sin(hd), math.sin(tl) * math.cos(hd), -math.cos(tl)))
    r = f.cross(Vector((math.sin(hd), math.cos(hd), 0.0))).normalized(); u = r.cross(f)
    rot = Matrix((r, u, -f)).transposed()
    return TGT - d * f, rot.to_euler(), d


d_max = 0.0
for fr in range(1, FRAMES + 1):
    loc, rot, d = cam_pose((fr - 1) / FPS)
    cam.location = loc; cam.rotation_euler = rot; d_max = max(d_max, d)
    cam.keyframe_insert("location", frame=fr); cam.keyframe_insert("rotation_euler", frame=fr)
cam.data.clip_start = 0.002 * d_max; cam.data.clip_end = 6.0 * d_max

# ------------------------------------------------------------------ animation
CU = (sum(CEN[k][0] * PM[k]["area"] for k in PK) / sum(PM[k]["area"] for k in PK),
      sum(CEN[k][1] * PM[k]["area"] for k in PK) / sum(PM[k]["area"] for k in PK))
order = P.get("order") or sorted(PK, key=lambda k: -math.hypot(CEN[k][0] - CU[0], CEN[k][1] - CU[1]))
RANK = {k: i for i, k in enumerate(order)}
dist = {k: math.hypot(CEN[k][0] - CU[0], CEN[k][1] - CU[1]) for k in PK}
dmax = max(dist.values()) or 1.0
FLOAT = 0.0045 * SPAN0
# pieces rising side by side keep one height (their shared walls stay hidden); split pieces vary
LIFTK = {k: LIFT * ((0.8 + 0.4 * rnd(k, "lift")) if ACT == "break" else 1.0) for k in PK}
OFF = {k: ((CEN[k][0] - CU[0]) / dmax * SPREAD, (CEN[k][1] - CU[1]) / dmax * SPREAD) if ACT == "break" else (0.0, 0.0) for k in PK}
RAISED = {}
if ACT == "break":
    def end_bvh(k):
        v = LOCAL[k][0].astype(np.float64) + np.array([CEN[k][0] + OFF[k][0], CEN[k][1] + OFF[k][1], LIFTK[k]])
        return BVHTree.FromPolygons([Vector(x) for x in v], LOCAL[k][1])
    for _ in range(12):
        bvs = {k: end_bvh(k) for k in PK}; moved = False
        for i_, a_ in enumerate(PK):
            for b_ in PK[i_ + 1:]:
                if not bvs[a_].overlap(bvs[b_]): continue
                lo, hi = (a_, b_) if LIFTK[a_] <= LIFTK[b_] else (b_, a_)
                need = LIFTK[lo] + 1.3 * THICK + 2 * FLOAT
                if LIFTK[hi] < need - 1e-9:
                    LIFTK[hi] = need; moved = True; RAISED[hi] = round(LIFTK[hi] / LIFT, 2)
        if not moved: break
    if RAISED: print("separation: raised", RAISED, flush=True)


def state(k, t):
    """(dx, dy, z, quaternion, wipe, show, crack, alpha, socket, ring radius, ring alpha) of piece k at time t"""
    i = RANK[k]; s = SCH
    dx = dy = 0.0; z = 0.0; q = Quaternion(); wipe, show, crack, alpha, sock, rr, ra = 2.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0
    lift = LIFTK[k]
    ph = 2 * math.pi * rnd(k, "phase")
    if ACT in ("break", "rise"):
        t0 = (s["split"] if ACT == "break" else s["rise"]) + s["stagger"] * i
        p = (t - t0) / s["move"]
        if ACT == "break":
            vx, vy = OFF[k]; L = math.hypot(vx, vy)
            ux, uy = (vx / L, vy / L) if L > 1e-9 else (0.0, 0.0)
            e = ST.ease_out_back(p, 1.2)
            dx, dy = vx * e, vy * e
            z = lift * ST.ease_out_back(p, 0.9)
            if 0 < p < 1 and L > 1e-9:
                q = Quaternion((-uy, ux, 0.0), math.radians(7.0) * math.sin(math.pi * p) * (1 - ST.smooth(p)))
            env = ST.smooth((t - s["crack"]) / 0.35) * (1 - ST.smooth((t - s["split"]) / (0.45 * s["move"])))
            crack = env
            show = ST.smooth((t - s["crack"]) / 0.25)
            if s["crack"] <= t < s["split"] + 0.2:
                z += 0.07 * THICK * math.sin(2 * math.pi * 13 * (t - s["crack"])) * env
        else:
            z0 = -THICK + 0.0012 * SPAN0
            z = z0 + (lift - z0) * ST.ease_out_back(p, 0.8)
            sock = 0.78 * ST.smooth(p * 1.6)
        if p > 1: z += FLOAT * math.sin(2 * math.pi * (t - t0 - s["move"]) / 3.4 + ph) * ST.smooth((t - t0 - s["move"]) / 0.8)
        tw = s["flags"] + s["wstagger"] * i
        wipe = -0.3 + 1.6 * ST.smooth((t - tw) / s["wipe"])
    else:
        t0 = s["drop"] + s["stagger"] * i
        p = (t - t0) / s["move"]
        z0 = 0.32 * SPAN0 * (0.85 + 0.3 * rnd(k, "drop"))
        axis = Vector((math.cos(ph), math.sin(ph), 0.0))
        if p < 0: z, alpha = z0, 0.0; q = Quaternion(axis, math.radians(9.0))
        elif p < 1:
            z = z0 * (1 - p * p); alpha = ST.smooth(p / 0.3); q = Quaternion(axis, math.radians(9.0) * (1 - p) ** 2)
        else:
            qb = (t - t0 - s["move"]) / s["bounce"]
            if qb < 1: z = 0.35 * THICK * math.sin(math.pi * qb) * (1 - qb)
            qr = (t - t0 - s["move"]) / s["ring"]
            if qr < 1: rr, ra = RING[k][2] * (1 - (1 - qr) ** 3), (1 - qr) ** 1.5
    return dx, dy, z, q, wipe, show, crack, alpha, sock, rr, ra


for fr in range(1, FRAMES + 1):
    t = (fr - 1) / FPS
    for k in PK:
        dx, dy, z, q, wipe, show, crack, alpha, sock, rr, ra = state(k, t)
        ob = OBJ[k]
        ob.location = (CEN[k][0] + dx, CEN[k][1] + dy, z); ob.rotation_euler = q.to_euler()
        ob.keyframe_insert("location", frame=fr); ob.keyframe_insert("rotation_euler", frame=fr)
        h = HND[k]
        keyval(h["wipe"], wipe, fr); keyval(h["show"], show, fr); keyval(h["crack"], crack, fr)
        if ACT == "drop": keyval(h["alpha"], alpha, fr); keyval(h["salpha"], alpha, fr); keyval(RING[k][0], rr, fr); keyval(RING[k][1], ra, fr)
        if ACT == "rise": keyval(SOCK[k], sock, fr)
sc.frame_start, sc.frame_end = 1, FRAMES
C.setup_cycles(sc, O, samples=int(P.get("samples", 64)), look="None")
# flags keep their exact colours: no tone-mapping curve (AgX desaturates and shifts saturated colours)
sc.view_settings.view_transform = "Standard"
try: sc.view_settings.look = "None"
except Exception: pass
print(f"built: distance fields max {SDF_MAX}", flush=True)
print(f"built: {n} pieces, {tri_total} top triangles, action {ACT}, end of animation {SCH['end']:.1f} s, base {W}x{H} px "
      f"({meta['base']}), rim {RIM:.1f} base px", flush=True)

# ------------------------------------------------------------------ preview: labels + checks + exposure + key frames
if O.preview:
    BVH = {k: BVHTree.FromPolygons([Vector(v) for v in LOCAL[k][0]], LOCAL[k][1]) for k in PK}
    bx_lo, bx_hi, by_lo, by_hi = wx(0), wx(W), wy(H), wy(0)
    errors, warnings, stats = [], [], {"credits": meta.get("credits", []), "pieces": n, "triangles": tri_total,
                                       "sdf_max": SDF_MAX, "raised": RAISED}
    for k_, (got, want) in SDF_MAX.items():
        if abs(got - want) > 0.03 * want + 0.05:
            errors.append(f"distance field {k_} reads {got} instead of {want} - rims and cracks would have the wrong width")

    def mats():
        M = {k: OBJ[k].matrix_world.copy() for k in PK}
        return M, {k: (m.inverted(), m.inverted().to_3x3()) for k, m in M.items()}

    def cast(o, d, Mi):
        best, code = 1e30, "v"
        if d.z < -1e-9:
            s = -o.z / d.z; hp = o + d * s
            if bx_lo <= hp.x <= bx_hi and by_lo <= hp.y <= by_hi: best, code = s, "b"
        for k in PK:
            mi, m3 = Mi[k]
            hit = BVH[k].ray_cast(mi @ o, (m3 @ d).normalized(), best)
            if hit[0] is not None and hit[3] < best:
                best, code = hit[3], ("p" if hit[2] < NTOP[k] else "s")
        return code, best

    FR_ = list(cam.data.view_frame(scene=sc)); FZ = -FR_[0].z
    VX = (min(v.x for v in FR_) / FZ, max(v.x for v in FR_) / FZ); VY = (min(v.y for v in FR_) / FZ, max(v.y for v in FR_) / FZ)

    def project(pts):
        mi = np.array(cam.matrix_world.inverted())
        pl = pts @ mi[:3, :3].T + mi[:3, 3]
        z = -pl[:, 2]; zs = np.where(np.abs(z) < 1e-9, 1e-9, z)
        return np.column_stack([(pl[:, 0] / zs - VX[0]) / (VX[1] - VX[0]), (pl[:, 1] / zs - VY[0]) / (VY[1] - VY[0]), z])

    def world_pts(k, M, pts):
        R3 = np.array(M[k].to_3x3()); return pts @ R3.T + np.array(M[k].translation)

    # label tracks + in-frame checks over the whole clip
    LAB = [e for e in P.get("labels", []) if e[0] in OBJ]
    tracks = {e[0]: [] for e in LAB}
    end_t = SCH["end"]
    cut_end, cut_move = {}, {}
    sample = {}
    for k in PK:
        tv = LOCAL[k][0][: len(LOCAL[k][0]) // 2]
        sample[k] = tv[::max(1, len(tv) // 400)].astype(np.float64)
    for fr in range(1, FRAMES + 1):
        sc.frame_set(fr); t = (fr - 1) / FPS
        M, Mi = mats(); co_ = cam.matrix_world.translation.copy()
        for e in LAB:
            k = e[0]; pm = PM[k]
            pl = Vector((wx(pm["label"][0]) - CEN[k][0], wy(pm["label"][1]) - CEN[k][1], THICK + 0.002 * SPAN0))
            pw = M[k] @ pl
            v = world_to_camera_view(sc, cam, pw)
            vis = 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0 and v.z > 0 and state(k, t)[7] >= 0.5
            if vis:
                dvec = pw - co_; code, dd = cast(co_, dvec.normalized(), Mi)
                vis = dd >= dvec.length - 0.004 * SPAN0
            tracks[k].append([round(v.x * 1920, 1), round((1 - v.y) * 1080, 1), int(vis)])
        if fr % 3 and fr != FRAMES: continue
        for k in PK:
            c_ = project(world_pts(k, M, sample[k]))
            if np.any((c_[:, 0] < 0.004) | (c_[:, 0] > 0.996) | (c_[:, 1] < 0.004) | (c_[:, 1] > 0.996) | (c_[:, 2] <= 0)):
                (cut_end if t >= end_t else cut_move).setdefault(k, []).append(round(t, 1))
    names = [[e[0], e[1] if len(e) > 1 else e[0], e[2] if len(e) > 2 else ""] for e in LAB]
    json.dump({"fps": FPS, "frames": FRAMES, "tracks": tracks, "names": names}, open(f"{O.out}/labels.json", "w"))
    vis_s = {k: round(sum(x[2] for x in v) / FPS, 2) for k, v in tracks.items()}
    stats["labels_visible_s"] = vis_s
    for k, ts in cut_end.items(): errors.append(f"piece {k} is cut by the frame edge during the hold (at {ts[0]:.1f}-{ts[-1]:.1f} s)")
    for k, ts in cut_move.items(): warnings.append(f"piece {k} touches the frame edge while moving ({ts[0]:.1f}-{ts[-1]:.1f} s)")
    for k, s_ in vis_s.items():
        if s_ < 1.5: warnings.append(f"label {k} visible only {s_:.1f} s")

    # pieces must not pass through each other once they have split
    def world_bvh(k, M):
        return BVHTree.FromPolygons([Vector(v) for v in world_pts(k, M, LOCAL[k][0].astype(np.float64))], LOCAL[k][1])

    if ACT == "break":
        chk = {"end": FRAMES, "settled": min(FRAMES, 1 + int(round((SCH["motion_end"] + 0.1) * FPS))),
               "moving": 1 + int(round((SCH["split"] + SCH["stagger"] * (n - 1) + 0.45 * SCH["move"]) * FPS))}
        hits = {}
        for tag, fr in chk.items():
            sc.frame_set(fr); M, _ = mats(); bv_ = {k: world_bvh(k, M) for k in PK}
            for i_, a_ in enumerate(PK):
                for b_ in PK[i_ + 1:]:
                    if bv_[a_].overlap(bv_[b_]): hits.setdefault(tag, []).append(f"{a_}/{b_}")
        for tag, prs in hits.items():
            (errors if tag != "moving" else warnings).append(f"pieces intersect ({tag}, {(chk[tag] - 1) / FPS:.1f} s): {', '.join(prs)} - raise spread or change the order")
        stats["intersections"] = hits
    # how big each piece is on screen at the end
    sc.frame_set(FRAMES); M, _ = mats(); small = {}
    for k in PK:
        tv = LOCAL[k][0][: len(LOCAL[k][0]) // 2].astype(np.float64)
        c_ = project(world_pts(k, M, tv)); xy = np.column_stack([c_[:, 0] * 1920, (1 - c_[:, 1]) * 1080])
        tri = np.array([t_ for t_ in LOCAL[k][1] if len(t_) == 3])
        a2 = np.abs((xy[tri[:, 1], 0] - xy[tri[:, 0], 0]) * (xy[tri[:, 2], 1] - xy[tri[:, 0], 1]) -
                    (xy[tri[:, 2], 0] - xy[tri[:, 0], 0]) * (xy[tri[:, 1], 1] - xy[tri[:, 0], 1])).sum() / 2
        small[k] = int(a2)
        if a2 < 2500: warnings.append(f"piece {k} is small on screen at the end ({int(a2)} px2) - its flag will be hard to read")
    stats["screen_area_px2"] = small

    def classify(f):
        _, Mi = mats(); o, rows = C.cam_rays(sc, cam)
        return ["".join(cast(o, d, Mi)[0] for d in row) for row in rows]

    fl = [PM[k]["flag"]["luma"] for k in PK]
    lum = float(np.mean(fl))
    if ACT == "break": lum = 0.35 * meta["union"]["flag"]["luma"] + 0.65 * lum
    target = float(np.clip(0.95 * lum, 0.25, 0.7))
    C.preview_run(sc, O, FRAMES, classify, subject=("p",), fallback_subject=("p", "s"), target=target, tol=0.09,
                  ev_range=(-1.2, 1.5), stats=stats, errors=errors, warnings=warnings, dark_max=0.35 if SAT else 0.85)
    sys.exit(0)

# ------------------------------------------------------------------ render
C.render_frames(sc, O.out, list(range(O.start, END + 1)), O.budget)
