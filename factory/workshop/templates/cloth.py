"""Workshop template 'cloth' - a flag on its pole in the wind, in a real setting (Blender Cycles). Analytic cloth and
weather motion (PC2 caches): every frame renders on its own and identically on any machine.
built-in rules: rain and snow always fall from an overcast sky (no sun); no particle comes closer than 2 m to the lens
during the shot; the background is a real setting (city or hills) or transparent for compositing; cheap settings (rain
as streaks without motion blur, windows and street lights glow without being light sources)
usage: blender -b -P cloth.py -- --params p.json --data <prep dir> --out <dir> [--start 1 --end N --gpu OPTIX --ev X
       --budget-min M | --preview]
params: seconds; action wave | lower | raise | half; sky day | dawn | dusk | night | storm | overcast;
        weather none | snow | rain | embers | dust; camera pull | push | orbit | low; wind 0..1;
        background city | hills | transparent; finial ball | spear; focus_uv [u, v]; seed; samples"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import terrain_mesh as TM

P, O = C.args()
DATA = O.data
FPS = 30
T = float(P.get("seconds", 8)); FRAMES = int(round(T * FPS)); END = O.end or FRAMES
ACTION, SKY, WEATHER, CAMERA = P.get("action", "wave"), P.get("sky", "dusk"), P.get("weather", "none"), P.get("camera", "pull")
WIND = float(P.get("wind", 0.7))
BG = P.get("background", "city"); TRANSP = BG == "transparent"
OVERCAST = WEATHER in ("rain", "snow") or SKY in ("storm", "overcast")
TOD = "day" if SKY == "overcast" else SKY
WET = WEATHER == "rain"
WORK = os.path.join(O.out, "_cache"); os.makedirs(WORK, exist_ok=True)
fmeta = json.load(open(f"{DATA}/meta.json"))
sc = C.reset(FPS)
sc.frame_start, sc.frame_end = 1, FRAMES
rng = np.random.default_rng(int(P.get("seed", 7)))
tf = lambda f: (f - 1) / FPS
CF = np.arange(1, FRAMES + 3)                 # cache frames (one extra for motion blur)
TT = np.array([tf(f) for f in CF])
POLE, ENV, GROUND = [], [], []

# ------------------------------------------------------------------ the flag
L = 4.0; HH = L / max(1.2, min(2.6, float(fmeta.get("aspect", 1.5))))
NU, NV = 72, max(20, int(round(72 / (L / HH))))
TOP, BOTTOM = 13.6, HH + 0.9
HALF = (TOP + BOTTOM) / 2


def z_top(t):
    if ACTION == "lower": return TOP - (TOP - BOTTOM) * C.smooth((t - 0.2 * T) / (0.65 * T))
    if ACTION == "raise": return BOTTOM + (TOP - BOTTOM) * C.smooth((t - 0.15 * T) / (0.65 * T))
    if ACTION == "half": return TOP - (TOP - HALF) * C.smooth((t - 0.25 * T) / (0.45 * T))
    return TOP


u = np.linspace(0, 1, NU + 1); v = np.linspace(0, 1, NV + 1)
UU, VV = np.meshgrid(u, v)
AW = (0.12 + 0.26 * WIND) * (0.75 if WET else 1.0); SPD = 0.6 + 0.8 * WIND      # a wet flag is heavier: smaller waves
HANG = math.radians(75 * (1 - WIND) ** 1.5 + (6.0 if WET else 0.0))


def flag_at(t):
    tw = SPD * t
    A = AW * UU ** 0.7 * (0.88 + 0.12 * math.sin(0.8 * tw))
    y = A * (np.sin(2 * np.pi * (1.6 * UU - 1.05 * tw) + 1.4 * VV)
             + 0.32 * np.sin(2 * np.pi * (3.1 * UU - 1.9 * tw) + 2.3 * VV + 1.1)
             + 0.12 * UU * np.sin(2 * np.pi * (6.2 * UU - 3.4 * tw) - 2.6 * VV + 0.3))
    dx0 = L / NU
    dxs = np.sqrt(np.clip(dx0 ** 2 - np.diff(y, axis=1) ** 2, (0.35 * dx0) ** 2, None))
    x = np.concatenate([np.zeros((NV + 1, 1)), np.cumsum(dxs, axis=1)], 1)
    z = -HH * (1 - VV) - 0.16 * UU ** 2 + 0.05 * UU * np.sin(2 * np.pi * (0.9 * UU - 0.7 * tw) + 2.3 * VV)
    xr = 0.075 + x * math.cos(HANG)
    zr = z - x * math.sin(HANG)
    return np.stack([xr, y, z_top(t) + zr], -1).reshape(-1, 3)


def flag_point(t, fu, fv):
    return Vector((0.075 + fu * L * math.cos(HANG), 0.0, z_top(t) - HH * (1 - fv) - fu * L * math.sin(HANG)))


def flag_center(t):
    return flag_point(t, 0.5, 0.5)


verts0 = flag_at(TT[0])
faces = [(j * (NU + 1) + i, j * (NU + 1) + i + 1, (j + 1) * (NU + 1) + i + 1, (j + 1) * (NU + 1) + i) for j in range(NV) for i in range(NU)]
me = bpy.data.meshes.new("flag"); me.from_pydata(verts0.tolist(), [], faces); me.update()
uvl = me.uv_layers.new(name="UVMap")
lvi = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lvi)
UVv = np.stack([UU.ravel(), VV.ravel()], 1)
uvl.data.foreach_set("uv", UVv[lvi].ravel().astype(np.float32))
flag = bpy.data.objects.new("flag", me); sc.collection.objects.link(flag); C.smooth_shade(flag)
C.write_pc2(f"{WORK}/flag.pc2", np.stack([flag_at(t) for t in TT]))
C.use_cache(flag, f"{WORK}/flag.pc2", 1)
flag.modifiers.new("solid", "SOLIDIFY").thickness = 0.004

fm = bpy.data.materials.new("flag"); fm.use_nodes = True; nt = fm.node_tree
p = nt.nodes["Principled BSDF"]; out = nt.nodes["Material Output"]
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(os.path.abspath(f"{DATA}/flag.png")); tex.interpolation = "Cubic"
nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
p.inputs["Roughness"].default_value = 0.58
for k, val in (("Sheen Weight", 0.22), ("Sheen Roughness", 0.6)):     # strong sheen draws bright bands along the folds
    if k in p.inputs: p.inputs[k].default_value = val
tc = nt.nodes.new("ShaderNodeTexCoord")
weave = nt.nodes.new("ShaderNodeTexWave"); weave.inputs["Scale"].default_value = 900; weave.wave_type = "BANDS"
weave2 = nt.nodes.new("ShaderNodeTexWave"); weave2.inputs["Scale"].default_value = 900; weave2.bands_direction = "Y"
crease = nt.nodes.new("ShaderNodeTexNoise"); crease.inputs["Scale"].default_value = 7.0; crease.inputs["Detail"].default_value = 3.0
for n in (weave, weave2, crease): nt.links.new(tc.outputs["UV"], n.inputs["Vector"])
mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
nt.links.new(weave.outputs["Fac"], mul.inputs[0]); nt.links.new(weave2.outputs["Fac"], mul.inputs[1])
b1 = nt.nodes.new("ShaderNodeBump"); b1.inputs["Strength"].default_value = 0.06; b1.inputs["Distance"].default_value = 0.002
nt.links.new(mul.outputs[0], b1.inputs["Height"])
b2 = nt.nodes.new("ShaderNodeBump"); b2.inputs["Strength"].default_value = 0.12; b2.inputs["Distance"].default_value = 0.01
nt.links.new(crease.outputs["Fac"], b2.inputs["Height"]); nt.links.new(b1.outputs["Normal"], b2.inputs["Normal"])
nt.links.new(b2.outputs["Normal"], p.inputs["Normal"])
tr = nt.nodes.new("ShaderNodeBsdfTranslucent"); nt.links.new(tex.outputs["Color"], tr.inputs["Color"])
mix = nt.nodes.new("ShaderNodeMixShader"); mix.inputs[0].default_value = 0.14
nt.links.new(p.outputs[0], mix.inputs[1]); nt.links.new(tr.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs["Surface"])
C.put(flag, fm)

# ------------------------------------------------------------------ pole, finial, halyard, plinth
metal = C.mat("pole", (0.78, 0.78, 0.8), 0.28, 1.0)
gold = C.mat("gold", (1.0, 0.76, 0.33), 0.22, 1.0)
stone = C.mat("stone", (0.42, 0.40, 0.37), 0.8 if not WET else 0.35)
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=14.3, location=(0, 0, 7.15), vertices=32); POLE.append(C.put(bpy.context.active_object, metal))
if P.get("finial", "ball") == "spear":
    bpy.ops.mesh.primitive_cone_add(radius1=0.09, depth=0.5, location=(0, 0, 14.55), vertices=24); POLE.append(C.put(bpy.context.active_object, gold))
else:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(0, 0, 14.42), segments=32, ring_count=16)
    POLE.append(C.put(bpy.context.active_object, gold)); C.smooth_shade(bpy.context.active_object)
bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=14.0, location=(-0.07, 0.0, 7.1), vertices=8)
POLE.append(C.put(bpy.context.active_object, C.mat("rope", (0.85, 0.82, 0.74), 0.7)))
if not TRANSP:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6, location=(0, 0, 0.3), vertices=48); POLE.append(C.put(bpy.context.active_object, stone))

# ------------------------------------------------------------------ sky (world + the same sky as a node group)
SKYS = {"day": (40, 200, 3.4, (1.0, 0.96, 0.9), 0.75), "dawn": (4, 20, 2.4, (1.0, 0.72, 0.48), 0.9),
        "dusk": (2.5, -25, 2.0, (1.0, 0.6, 0.35), 0.9)}
OVC = {"day": ((0.62, 0.64, 0.67), (0.34, 0.36, 0.40), 1.6), "dawn": ((0.60, 0.46, 0.38), (0.20, 0.20, 0.25), 0.8),
       "dusk": ((0.40, 0.25, 0.19), (0.07, 0.07, 0.10), 0.35), "night": ((0.05, 0.04, 0.035), (0.006, 0.008, 0.016), 0.06),
       "storm": ((0.10, 0.11, 0.12), (0.035, 0.04, 0.05), 0.5)}
CLEAR_NIGHT = ((0.028, 0.017, 0.012), (0.003, 0.006, 0.017))
NISHITA = not OVERCAST and TOD in SKYS
GLOW_ROT = {"dawn": 20, "dusk": -25}.get(TOD)


def sky_group():
    g = bpy.data.node_groups.new("SkyCol", "ShaderNodeTree")
    g.interface.new_socket(name="Dir", in_out="INPUT", socket_type="NodeSocketVector")
    g.interface.new_socket(name="Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, Lk = g.nodes, g.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    if NISHITA:
        el, rot, en, col, bs = SKYS[TOD]
        sky = N.new("ShaderNodeTexSky")
        try:
            sky.sky_type = "NISHITA"; sky.sun_disc = TOD != "day"; sky.sun_elevation = math.radians(el); sky.sun_rotation = math.radians(rot)
            sky.altitude = 40.0; sky.air_density = 1.0; sky.dust_density = 2.2 if TOD != "day" else 1.2; sky.ozone_density = 1.0
        except Exception as e:
            print("sky fallback", e)
        Lk.new(gi.outputs[0], sky.inputs["Vector"])
        mm = N.new("ShaderNodeVectorMath"); mm.operation = "SCALE"; mm.inputs["Scale"].default_value = bs
        Lk.new(sky.outputs["Color"], mm.inputs[0]); Lk.new(mm.outputs[0], go.inputs[0])
        return g
    hor, zen = OVC[TOD][:2] if OVERCAST else CLEAR_NIGHT
    sp = N.new("ShaderNodeSeparateXYZ"); Lk.new(gi.outputs[0], sp.inputs[0])
    mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -0.05; mr.inputs["From Max"].default_value = 0.55
    Lk.new(sp.outputs["Z"], mr.inputs["Value"])
    ramp = N.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*hor, 1); ramp.color_ramp.elements[1].color = (*zen, 1)
    Lk.new(mr.outputs["Result"], ramp.inputs["Fac"])
    cl = N.new("ShaderNodeTexNoise"); cl.inputs["Scale"].default_value = 2.2; cl.inputs["Detail"].default_value = 7.0
    Lk.new(gi.outputs[0], cl.inputs["Vector"])
    cm = N.new("ShaderNodeMapRange"); cm.inputs["From Min"].default_value = 0.46; cm.inputs["From Max"].default_value = 0.80
    Lk.new(cl.outputs["Fac"], cm.inputs["Value"])
    cadd = N.new("ShaderNodeMix"); cadd.data_type = "RGBA"; cadd.blend_type = "ADD"
    cadd.inputs[7].default_value = tuple(min(1.0, 0.18 * c + 0.012) for c in hor) + (1,)
    Lk.new(cm.outputs["Result"], cadd.inputs[0]); Lk.new(ramp.outputs["Color"], cadd.inputs[6])
    res = cadd.outputs[2]
    if OVERCAST and GLOW_ROT is not None:      # warm glow low in the sky where the hidden sun is
        sd = Vector((-math.sin(math.radians(GLOW_ROT)), math.cos(math.radians(GLOW_ROT)), 0.0))
        dp = N.new("ShaderNodeVectorMath"); dp.operation = "DOT_PRODUCT"; dp.inputs[1].default_value = tuple(sd)
        Lk.new(gi.outputs[0], dp.inputs[0])
        mx_ = N.new("ShaderNodeMath"); mx_.operation = "MAXIMUM"; mx_.inputs[1].default_value = 0.0; Lk.new(dp.outputs["Value"], mx_.inputs[0])
        pw = N.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 6.0; Lk.new(mx_.outputs[0], pw.inputs[0])
        low = N.new("ShaderNodeMapRange"); low.inputs["From Min"].default_value = 0.0; low.inputs["From Max"].default_value = 0.35
        low.inputs["To Min"].default_value = 1.0; low.inputs["To Max"].default_value = 0.0; Lk.new(sp.outputs["Z"], low.inputs["Value"])
        gm = N.new("ShaderNodeMath"); gm.operation = "MULTIPLY"; Lk.new(pw.outputs[0], gm.inputs[0]); Lk.new(low.outputs["Result"], gm.inputs[1])
        gadd = N.new("ShaderNodeMix"); gadd.data_type = "RGBA"; gadd.blend_type = "ADD"
        gadd.inputs[7].default_value = (0.42, 0.20, 0.08, 1) if TOD == "dusk" else (0.45, 0.30, 0.18, 1)
        Lk.new(gm.outputs[0], gadd.inputs[0]); Lk.new(res, gadd.inputs[6]); res = gadd.outputs[2]
    Lk.new(res, go.inputs[0])
    return g


SKYG = sky_group()
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; wn = w.node_tree; bg = wn.nodes["Background"]
tcw = wn.nodes.new("ShaderNodeTexCoord"); gw = wn.nodes.new("ShaderNodeGroup"); gw.node_tree = SKYG
wn.links.new(tcw.outputs["Generated"], gw.inputs[0]); wn.links.new(gw.outputs[0], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 1.0
fc0, fc1 = flag_center(0), flag_center(T)
zmid = (fc0.z + fc1.z) / 2


def sun_lamp(el, rot, energy, color, angle=1.0):
    d = Vector((-math.cos(math.radians(el)) * math.sin(math.radians(rot)), math.cos(math.radians(el)) * math.cos(math.radians(rot)), math.sin(math.radians(el))))
    sd = bpy.data.lights.new("sun", "SUN"); sd.energy = energy; sd.color = color; sd.angle = math.radians(angle)
    so = bpy.data.objects.new("sun", sd); sc.collection.objects.link(so)
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


HERO = bpy.data.collections.new("hero")
for ob_ in [flag] + POLE: HERO.objects.link(ob_)


def spot(name, loc, target, power, size, color, blend=0.6, soft=0.4):
    ld = bpy.data.lights.new(name, "SPOT"); ld.energy = power; ld.spot_size = math.radians(size); ld.spot_blend = blend
    ld.color = color; ld.shadow_soft_size = soft
    o = bpy.data.objects.new(name, ld); o.location = loc; sc.collection.objects.link(o); C.aim(o, target)
    o.visible_camera = False
    try: o.light_linking.receiver_collection = HERO
    except Exception as e: print("light linking unavailable:", e, flush=True)


if NISHITA:
    el, rot, en, col, bs = SKYS[TOD]
    sun_lamp(el, rot, en, col)
    if TOD != "day":
        ad = bpy.data.lights.new("fill", "AREA"); ad.energy = 900; ad.size = 8; ad.color = (0.75, 0.82, 1.0)
        ao = bpy.data.objects.new("fill", ad); ao.location = (fc0.x - 3, -14, zmid + 2); sc.collection.objects.link(ao); C.aim(ao, (fc0.x, 0, zmid))
        ao.visible_camera = False
elif OVERCAST:
    sun_lamp(55, 160, OVC[TOD][2], (0.86, 0.89, 0.95), angle=30)
else:
    sun_lamp(55, 160, 0.12, (0.62, 0.72, 1.0))
if TOD in ("dusk", "night", "storm") and not NISHITA:
    cx = fc0.x
    k = 0.75 if OVERCAST and TOD == "dusk" else 1.0
    spot("rake", (cx + 6.5, -2.4, zmid + 2.5), (cx, 0, zmid), 5200 * k, 60, (1.0, 0.84, 0.62), 0.5, 0.25)
    spot("key", (cx + 2.0, -9.0, zmid - 2.0), (cx, 0, zmid), 2600 * k, 60, (1.0, 0.86, 0.68))
    spot("fill", (cx - 6.0, -6.5, zmid + 1.0), (cx, 0, zmid), 700 * k, 60, (0.78, 0.85, 1.0))
    spot("rim", (cx - 4.0, 7.0, zmid + 4.0), (cx, 0, zmid), 3000 * k, 60, (0.75, 0.82, 1.0))

# ------------------------------------------------------------------ the setting
LIT = {"night": (0.40, 6.0), "dusk": (0.26, 4.0), "storm": (0.24, 3.0), "dawn": (0.10, 2.0), "day": (0.0, 0.0)}[TOD]
FACADE = (0.36, 0.33, 0.30) if TOD in ("day", "dawn") else (0.15, 0.142, 0.135)
FOG = (60.0, 1600.0)


def ico(centers, r):
    t = (1 + 5 ** 0.5) / 2
    V = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                  (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], float)
    V = V / np.linalg.norm(V, axis=1, keepdims=True)
    Fc = np.array([(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
                   (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)])
    centers = np.asarray(centers, float)
    co = (V[None] * r + centers[:, None]).reshape(-1, 3)
    return co, (Fc[None] + 12 * np.arange(len(centers))[:, None, None]).reshape(-1, 3)


def lights(name, centers, r, color, strength):
    if not len(centers): return None
    co, f = ico(centers, r)
    ob = C.mesh_object(name, co, tris=f)
    m = C.emitter(name, color, strength); C.not_a_light(m); C.put(ob, m); C.no_motion_blur(ob)
    ENV.append(ob)
    return m


def wet_ground(name, base, rough_dry, brick=False):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; N, Lk = nt.nodes, nt.links
    pb = N["Principled BSDF"]
    tcn = N.new("ShaderNodeTexCoord")
    col = (*base, 1)
    if brick:
        br = N.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1.6
        br.inputs["Color1"].default_value = (base[0] * 1.15, base[1] * 1.12, base[2] * 1.08, 1); br.inputs["Color2"].default_value = (*base, 1)
        br.inputs["Mortar"].default_value = (base[0] * 0.5, base[1] * 0.5, base[2] * 0.5, 1); br.inputs["Mortar Size"].default_value = 0.015
        Lk.new(tcn.outputs["Object"], br.inputs["Vector"]); Lk.new(br.outputs["Color"], pb.inputs["Base Color"])
    else:
        nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.35; Lk.new(tcn.outputs["Object"], nz.inputs["Vector"])
        cr = N.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (base[0] * 0.8, base[1] * 0.8, base[2] * 0.8, 1)
        cr.color_ramp.elements[1].color = (base[0] * 1.25, base[1] * 1.25, base[2] * 1.25, 1)
        Lk.new(nz.outputs["Fac"], cr.inputs["Fac"]); Lk.new(cr.outputs["Color"], pb.inputs["Base Color"])
    if WET:
        pud = N.new("ShaderNodeTexNoise"); pud.inputs["Scale"].default_value = 0.08; pud.inputs["Detail"].default_value = 3.0
        Lk.new(tcn.outputs["Object"], pud.inputs["Vector"])
        rr = N.new("ShaderNodeMapRange"); rr.inputs["From Min"].default_value = 0.45; rr.inputs["From Max"].default_value = 0.62
        rr.inputs["To Min"].default_value = 0.32; rr.inputs["To Max"].default_value = 0.04
        Lk.new(pud.outputs["Fac"], rr.inputs["Value"]); Lk.new(rr.outputs["Result"], pb.inputs["Roughness"])
    else:
        pb.inputs["Roughness"].default_value = rough_dry
    return m


def facade_material():
    m = bpy.data.materials.new("facades"); m.use_nodes = True; nt = m.node_tree; N, Lk = nt.nodes, nt.links
    pb = N["Principled BSDF"]
    geo = N.new("ShaderNodeNewGeometry"); sp = N.new("ShaderNodeSeparateXYZ"); sn = N.new("ShaderNodeSeparateXYZ")
    Lk.new(geo.outputs["Position"], sp.inputs[0]); Lk.new(geo.outputs["Normal"], sn.inputs[0])

    def op(o, a, b=None, val=None):
        n = N.new("ShaderNodeMath"); n.operation = o
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = float(x)
            else: Lk.new(x, n.inputs[i])
        return n.outputs[0]

    ax, ay = op("ABSOLUTE", sn.outputs["X"]), op("ABSOLUTE", sn.outputs["Y"])
    sel = op("GREATER_THAN", ax, ay)
    hco = op("ADD", sp.outputs["X"], op("MULTIPLY", sel, op("SUBTRACT", sp.outputs["Y"], sp.outputs["X"])))
    uu, vv = op("FRACT", op("DIVIDE", hco, 3.4)), op("FRACT", op("DIVIDE", sp.outputs["Z"], 3.1))
    win = op("MULTIPLY", op("MULTIPLY", op("GREATER_THAN", uu, 0.18), op("LESS_THAN", uu, 0.82)),
             op("MULTIPLY", op("GREATER_THAN", vv, 0.28), op("LESS_THAN", vv, 0.78)))
    win = op("MULTIPLY", win, op("MULTIPLY", op("LESS_THAN", op("ABSOLUTE", sn.outputs["Z"]), 0.5), op("GREATER_THAN", sp.outputs["Z"], 3.5)))
    at = N.new("ShaderNodeAttribute"); at.attribute_name = "bid"
    cell = op("ADD", op("ADD", op("FLOOR", op("DIVIDE", hco, 3.4)), op("MULTIPLY", op("FLOOR", op("DIVIDE", sp.outputs["Z"], 3.1)), 57.31)),
              op("MULTIPLY", at.outputs["Fac"], 1000.0))
    wnz = N.new("ShaderNodeTexWhiteNoise"); wnz.noise_dimensions = "1D"; Lk.new(cell, wnz.inputs["W"])
    lit = op("GREATER_THAN", wnz.outputs["Value"], 1.0 - LIT[0])
    wn2 = N.new("ShaderNodeTexWhiteNoise"); wn2.noise_dimensions = "1D"; Lk.new(op("ADD", cell, 0.5), wn2.inputs["W"])
    var = op("ADD", 0.35, op("MULTIPLY", wn2.outputs["Value"], 1.1))
    Lk.new(op("MULTIPLY", op("MULTIPLY", op("MULTIPLY", win, lit), var), LIT[1]), pb.inputs["Emission Strength"])
    pb.inputs["Emission Color"].default_value = (1.0, 0.72, 0.42, 1)
    shade = op("ADD", 0.7, op("MULTIPLY", at.outputs["Fac"], 0.6))
    fac_rgb = N.new("ShaderNodeCombineXYZ")
    for i, c in enumerate(FACADE): Lk.new(op("MULTIPLY", shade, c), fac_rgb.inputs[i])
    cm = N.new("ShaderNodeMix"); cm.data_type = "RGBA"; cm.inputs[7].default_value = (0.03, 0.035, 0.045, 1)
    Lk.new(win, cm.inputs[0]); Lk.new(fac_rgb.outputs[0], cm.inputs[6]); Lk.new(cm.outputs[2], pb.inputs["Base Color"])
    rm = N.new("ShaderNodeMapRange"); rm.inputs["To Min"].default_value = 0.85; rm.inputs["To Max"].default_value = 0.12
    Lk.new(win, rm.inputs["Value"]); Lk.new(rm.outputs["Result"], pb.inputs["Roughness"])
    C.not_a_light(m)
    return m


def build_city():
    co, quads, bid = [], [], []
    for i in range(760):
        r = 70 + 1500 * rng.random() ** 1.5
        a = math.radians(rng.uniform(-30, 210))
        cx, cy = r * math.cos(a), r * math.sin(a)
        if cy < 32: continue
        wdt, dep = rng.uniform(12, 38), rng.uniform(12, 30)
        hgt = rng.uniform(8, 26) * (1 + r / 700) * (2.3 if rng.random() < 0.06 else 1.0)
        x0, x1, y0, y1 = cx - wdt / 2, cx + wdt / 2, cy - dep / 2, cy + dep / 2
        b = len(co)
        co += [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, hgt), (x1, y0, hgt), (x1, y1, hgt), (x0, y1, hgt)]
        quads += [(b, b + 1, b + 5, b + 4), (b + 1, b + 2, b + 6, b + 5), (b + 2, b + 3, b + 7, b + 6), (b + 3, b, b + 4, b + 7), (b + 4, b + 5, b + 6, b + 7)]
        bid += [float(rng.random())] * 5
    ob = C.mesh_object("city", np.array(co), np.array(quads), face_float={"bid": np.array(bid)})
    C.put(ob, facade_material()); ENV.append(ob)
    if LIT[1] > 0:
        st = [(x, y, 7.0) for y in (60, 95, 140, 210, 300, 420) for x in np.arange(-500, 501, 28) + rng.uniform(-6, 6)]
        lights("streetlights", st, 0.45, (1.0, 0.62, 0.3), 24.0)
    g = C.mesh_object("ground", np.array([(-3500, -3500, 0), (3500, -3500, 0), (3500, 3500, 0), (-3500, 3500, 0)], float), quads=np.array([[0, 1, 2, 3]]))
    C.put(g, wet_ground("asphalt", (0.045, 0.045, 0.05), 0.55)); GROUND.append(g)
    n = 64
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pco = np.r_[[(0, 0, 0.004)], np.c_[30 * np.cos(ang), 30 * np.sin(ang), np.full(n, 0.004)]]
    ptr = np.array([(0, 1 + i, 1 + (i + 1) % n) for i in range(n)])
    pl = C.mesh_object("plaza", pco, tris=ptr)
    C.put(pl, wet_ground("stones", (0.30, 0.285, 0.26), 0.7, brick=True)); GROUND.append(pl)


def vnoise(x, y, seed):
    r = np.random.default_rng(seed); g = r.random((66, 66))
    x = np.mod(x, 64.0); y = np.mod(y, 64.0)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int); fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    return (g[y0, x0] * (1 - fx) * (1 - fy) + g[y0, x0 + 1] * fx * (1 - fy) + g[y0 + 1, x0] * (1 - fx) * fy + g[y0 + 1, x0 + 1] * fx * fy)


def hills_h(x, y):
    r = np.hypot(x, y)
    ramp = np.clip((r - 60) / 590, 0, 1); ramp = ramp * ramp * (3 - 2 * ramp)
    side = np.where(y > 0, 1.0, 0.45)
    f = sum(vnoise(x / (900 / 2 ** k) + 11 * k, y / (900 / 2 ** k) + 7 * k, 40 + k) * 0.5 ** k for k in range(4))
    return ramp * side * (f * 190 + 18)


def build_hills():
    n = 241
    g = np.linspace(-3200, 3200, n); X, Y = np.meshgrid(g, g)
    Zh = hills_h(X, Y)
    co = np.stack([X.ravel(), Y.ravel(), Zh.ravel()], 1)
    idx = np.arange(n * n).reshape(n, n)
    q = np.stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()], 1)
    hob = C.mesh_object("hills", co, quads=TM.orient_up(co, q)); C.smooth_shade(hob)
    m = bpy.data.materials.new("grass"); m.use_nodes = True; nt = m.node_tree; N, Lk = nt.nodes, nt.links
    pb = N["Principled BSDF"]; pb.inputs["Roughness"].default_value = 0.9 if not WET else 0.45
    tcn = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.02; nz.inputs["Detail"].default_value = 6
    Lk.new(tcn.outputs["Object"], nz.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.05, 0.085, 0.03, 1); cr.color_ramp.elements[1].color = (0.13, 0.14, 0.055, 1)
    Lk.new(nz.outputs["Fac"], cr.inputs["Fac"])
    geo = N.new("ShaderNodeNewGeometry"); sn = N.new("ShaderNodeSeparateXYZ"); Lk.new(geo.outputs["Normal"], sn.inputs[0])
    sl = N.new("ShaderNodeMapRange"); sl.inputs["From Min"].default_value = 0.78; sl.inputs["From Max"].default_value = 0.92
    sl.inputs["To Min"].default_value = 1.0; sl.inputs["To Max"].default_value = 0.0; Lk.new(sn.outputs["Z"], sl.inputs["Value"])
    rk = N.new("ShaderNodeMix"); rk.data_type = "RGBA"; rk.inputs[7].default_value = (0.2, 0.19, 0.17, 1)
    Lk.new(sl.outputs["Result"], rk.inputs[0]); Lk.new(cr.outputs["Color"], rk.inputs[6]); Lk.new(rk.outputs[2], pb.inputs["Base Color"])
    C.put(hob, m); ENV.append(hob)
    k = 2600
    r = 90 + 2100 * rng.random(k) ** 0.8; a = np.radians(rng.uniform(-20, 200, k))
    tx, ty = r * np.cos(a), r * np.sin(a); keep = ty > 25; tx, ty = tx[keep], ty[keep]
    tz = hills_h(tx, ty); th = rng.uniform(7, 15, len(tx)); trd = rng.uniform(2.0, 3.8, len(tx))
    ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    tco, ttr = [], []
    for i in range(len(tx)):
        b = len(tco)
        tco += [(tx[i] + trd[i] * math.cos(q_), ty[i] + trd[i] * math.sin(q_), tz[i] + 1.0) for q_ in ang] + [(tx[i], ty[i], tz[i] + th[i])]
        ttr += [(b + j, b + (j + 1) % 8, b + 8) for j in range(8)]
    tob = C.mesh_object("trees", np.array(tco), tris=np.array(ttr)); C.put(tob, C.mat("trees", (0.03, 0.055, 0.025), 0.85)); ENV.append(tob)
    if LIT[1] > 0:
        kk = 170; r2 = 300 + 1700 * rng.random(kk); a2 = np.radians(rng.uniform(10, 170, kk))
        vx, vy = r2 * np.cos(a2), r2 * np.sin(a2)
        lights("villages", np.c_[vx, vy, hills_h(vx, vy) + 4], 0.9, (1.0, 0.66, 0.34), 18.0)


if BG == "city": build_city()
elif BG == "hills": build_hills()
for ob in ENV + GROUND:
    if ob.type == "MESH" and ob.data.materials:
        for m in ob.data.materials:
            if not m.get("fog"): C.add_fog(m, SKYG, *FOG, strength=1.0, maxf=0.92); m["fog"] = 1

# ------------------------------------------------------------------ camera presets (follow the flag)
camd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
look = bpy.data.objects.new("look", None); sc.collection.objects.link(look)
focus = bpy.data.objects.new("focus", None); sc.collection.objects.link(focus)
c = cam.constraints.new("TRACK_TO"); c.target = look; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
camd.sensor_width = 36; camd.dof.use_dof = True; camd.dof.focus_object = focus; camd.clip_start = 0.3; camd.clip_end = 9000

FU, FV = [float(x) for x in P.get("focus_uv", [0.3, 0.65])]
FVI = int(round(FV * NV)) * (NU + 1) + int(round(FU * NU))      # cloth vertex at the point of interest


def shot(t):
    k = t / T; f = flag_center(t); q = Vector(flag_at(t)[FVI])
    if CAMERA == "pull":
        a = C.smooth(k / 0.45); b = C.smooth((k - 0.45) / 0.55)
        cp = Vector((q.x - 0.3, -2.9, q.z - 0.1)).lerp(Vector((q.x + 0.2, -2.4, q.z + 0.05)), a).lerp(Vector((f.x + 1.4, -10.5, f.z - 0.5)), b)
        lp = q.lerp(Vector((f.x - 0.3, 0, f.z - 0.3)), b)
        return cp, lp, (q if b < 0.5 else f), 50, 2.8 - 0.8 * b
    if CAMERA == "push":
        cp = Vector((f.x + 2.6, -15.0, f.z - 1.6)).lerp(Vector((f.x + 0.9, -7.6, f.z - 0.5)), C.smooth(k))
        return cp, f, f, 50, 2.8
    if CAMERA == "orbit":
        an = math.radians(-118 + 56 * C.smooth(k)); r = 9.5
        return Vector((f.x + r * math.cos(an), r * math.sin(an), f.z - 0.8 + 1.2 * k)), f, f, 45, 2.8
    cp = Vector((f.x + 3.6, -6.2, 1.7)).lerp(Vector((f.x + 2.1, -5.3, 1.3)), C.smooth(k))
    return cp, f, f, 26, 4.0


for i in range(int(math.ceil(T * 2)) + 1):
    t = min(T, i / 2.0); fr = 1 + round(t * FPS)
    cp, lp, fp, lens, fs = shot(t)
    cam.location = cp; look.location = lp; focus.location = fp; camd.lens = lens; camd.dof.aperture_fstop = fs
    for ob in (cam, look, focus): ob.keyframe_insert("location", frame=fr)
    camd.keyframe_insert("lens", frame=fr); camd.dof.keyframe_insert("aperture_fstop", frame=fr)
C.bezier_keys([cam, look, focus])
cams = []
for f in CF:
    sc.frame_set(int(f)); cams.append(tuple(cam.matrix_world.translation))
cams = np.array(cams)

# ------------------------------------------------------------------ weather (analytic points, never near the lens)
WX = {"snow": (1.6, 30000, (0.006, 0.019), (0.55, 1.35), (0.95, 0.97, 1.0), 0.5, 1.6),
      "rain": (2.4, 40000, (0.0022, 0.0040), (8.0, 10.5), (0.78, 0.82, 0.88), 0.5, 2.0),
      "embers": (0.15, 3000, (0.008, 0.022), (-1.3, -0.5), (1.0, 0.45, 0.12), 9.0, 2.0),
      "dust": (0.35, 7000, (0.003, 0.009), (-0.08, 0.08), (1.0, 0.85, 0.6), 0.6, 2.0)}
NEAR = 0
if WEATHER in WX:
    dens, cap, rr, spd, col, est, dmin = WX[WEATHER]
    bx = (min(cams[:, 0].min(), 0.0) - 6.0, max(cams[:, 0].max(), L) + 14.0)
    by = (cams[:, 1].min() - 1.0, 16.0)
    bz = (-0.5, max(cams[:, 2].max(), TOP) + 8.0)
    n = int(min(cap, dens * (bx[1] - bx[0]) * (by[1] - by[0]) * (bz[1] - bz[0])))
    P0 = np.stack([rng.uniform(*bx, n), rng.uniform(*by, n), rng.uniform(*bz, n)], 1)
    S_ = rng.uniform(*spd, n); AMP = rng.uniform(0.04, 0.22, n); PH = rng.uniform(0, 2 * np.pi, (n, 2)); FR = rng.uniform(0.4, 1.1, (n, 2))
    drift = {"snow": 0.45, "rain": 1.6, "embers": 0.5, "dust": 0.15}[WEATHER] * (0.4 + WIND)
    zlo, zh = bz[0], bz[1] - bz[0]

    def wx_at(t, sel=slice(None)):
        tt = t + 2.0
        x = P0[sel, 0] + drift * tt + AMP[sel] * np.sin(FR[sel, 0] * tt + PH[sel, 0])
        y = P0[sel, 1] + AMP[sel] * np.sin(FR[sel, 1] * tt + PH[sel, 1])
        z = zlo + np.mod(P0[sel, 2] - S_[sel] * tt - zlo, zh)
        x = bx[0] + np.mod(x - bx[0], bx[1] - bx[0])
        return np.stack([x, y, z], 1)

    dmin_all = np.full(n, 1e9)
    for i, t in enumerate(TT):
        d = np.linalg.norm(wx_at(t) - cams[i], axis=1); np.minimum(dmin_all, d, out=dmin_all)
    keep = np.nonzero(dmin_all >= dmin)[0]
    print(f"weather {WEATHER}: {n} particles, {n - len(keep)} removed (closer than {dmin} m to the lens)", flush=True)
    P0, S_, AMP, PH, FR = P0[keep], S_[keep], AMP[keep], PH[keep], FR[keep]
    n = len(keep)
    NEAR = int(sum((np.linalg.norm(wx_at(t) - cams[i], axis=1) < dmin).sum() for i, t in enumerate(TT)))
    C.write_pc2(f"{WORK}/wx.pc2", np.stack([wx_at(t) for t in TT]))
    radii = rng.uniform(*rr, n)
    if WEATHER == "rain":
        rm = bpy.data.materials.new("rain"); rm.use_nodes = True; rnt = rm.node_tree
        for x in list(rnt.nodes): rnt.nodes.remove(x)
        tr_ = rnt.nodes.new("ShaderNodeBsdfTransparent"); em = rnt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*col, 1); em.inputs["Strength"].default_value = est
        mx2 = rnt.nodes.new("ShaderNodeMixShader"); mx2.inputs[0].default_value = 0.28
        o2 = rnt.nodes.new("ShaderNodeOutputMaterial")
        rnt.links.new(tr_.outputs[0], mx2.inputs[1]); rnt.links.new(em.outputs[0], mx2.inputs[2]); rnt.links.new(mx2.outputs[0], o2.inputs["Surface"])
        C.not_a_light(rm)
        vel = Vector((drift, 0.0, -float(np.mean(spd)))).normalized()
        eul = Vector((0, 0, 1)).rotation_difference(vel).to_euler()
        C.points_object("weather", wx_at(TT[0]), radii, rm, f"{WORK}/wx.pc2", streak=(float(np.mean(spd)) * 0.45 / FPS / float(np.mean(rr)), eul))
    else:
        wm_ = C.mat("wx", col, 0.45, emit=col, estr=est); C.not_a_light(wm_)
        C.points_object("weather", wx_at(TT[0]), radii, wm_, f"{WORK}/wx.pc2")

# ------------------------------------------------------------------ render settings
C.setup_cycles(sc, O, samples=int(P.get("samples", 64)), motion_blur=True, transparent=TRANSP)
for ob in ENV + GROUND + POLE: C.no_motion_blur(ob)
print(f"built: flag {len(verts0)} verts, action {ACTION}, sky {SKY}{' (overcast)' if OVERCAST else ''}, weather {WEATHER}, "
      f"background {BG}, camera {CAMERA}", flush=True)

if O.preview:
    dg = bpy.context.evaluated_depsgraph_get()
    tree = lambda objs: [(BVHTree.FromObject(ob, dg), ob.matrix_world.inverted()) for ob in objs if ob.type == "MESH"]
    T_P, T_E, T_G = tree(POLE), tree(ENV), tree(GROUND)
    errors, warnings = [], []
    flag_out = 0
    for f in range(1, FRAMES + 1):
        sc.frame_set(f)
        vv = world_to_camera_view(sc, cam, flag_center(tf(f)))
        if not (0.03 <= vv.x <= 0.97 and 0.03 <= vv.y <= 0.97 and vv.z > 0): flag_out += 1
    if flag_out: errors.append(f"flag centre out of frame in {flag_out} frames")
    if NEAR: errors.append(f"{NEAR} particle positions closer than the lens limit")

    def classify(f):
        dgf = bpy.context.evaluated_depsgraph_get()
        tfl = BVHTree.FromObject(flag, dgf)
        o, rows = C.cam_rays(sc, cam)
        res = []
        for row in rows:
            s = []
            for d in row:
                best, code = 1e30, None
                for cd, trees in (("F", [(tfl, None)]), ("p", T_P), ("e", T_E), ("g", T_G)):
                    for tr_, inv in trees:
                        if inv is None: hit = tr_.ray_cast(o, d, 9000.0)
                        else: hit = tr_.ray_cast(inv @ o, (inv.to_3x3() @ d).normalized(), 9000.0)
                        if hit[0] is not None and hit[3] < best: best, code = hit[3], cd
                if code is None: code = "s" if (d.z > -0.02 or TRANSP) else "v"
                s.append(code)
            res.append("".join(s))
        return res

    def stats(grids, counts):
        env = {}
        for k, g in grids.items():
            cells = "".join(g); fl = cells.count("F") / len(cells)
            rest = len(cells) - cells.count("F") - cells.count("p")
            env[k] = [round(fl, 3), round(cells.count("e") / max(1, rest), 3)]
        if not TRANSP:
            wide = [k for k, (fl, e) in env.items() if fl < 0.45]
            if wide and min(env[k][1] for k in wide) < 0.06:
                errors.append("empty background: the setting fills less than 6 % of the background in a wide frame")
        return {"flag_and_setting": env, "flag_out_frames": flag_out, "near_particles": NEAR, "overcast": OVERCAST}

    K = {"day": 0.95, "dawn": 0.82, "dusk": 0.78, "night": 0.62, "storm": 0.62}
    target = float(fmeta.get("luma", 0.5)) * (K[TOD] * (0.88 if OVERCAST else 1.0))
    C.preview_run(sc, O, FRAMES, classify, subject=("F",), target=round(target, 3), tol=0.08, ev_range=(-1.0, 1.5),
                  stats=stats, errors=errors, warnings=warnings, dark_max=0.15 if TOD in ("day", "dawn") else 0.45)
    sys.exit(0)

C.render_frames(sc, O.out, list(range(O.start, END + 1)), O.budget)
