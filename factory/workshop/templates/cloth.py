"""Workshop template 'cloth' - a flag on its pole in the wind (Blender Cycles, GPU). Analytic cloth and weather
motion (PC2 caches): every frame renders on its own and identically on any machine.
usage: blender -b -P cloth.py -- --params p.json --data <prep dir> --out <frames dir> --start 1 --end N [--gpu OPTIX]
params: seconds; action wave | lower | raise | half; sky day | dawn | dusk | night | storm; weather none | snow | rain |
        embers | dust; camera pull | push | orbit | low; wind 0..1; background scene | transparent; city true/false;
        finial ball | spear; samples"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

P, arg, _ = C.args()
DATA, OUT, GPU = arg("--data"), arg("--out", "frames"), arg("--gpu")
FPS = 30
T = float(P.get("seconds", 8)); FRAMES = int(round(T * FPS))
START, END = int(arg("--start", 1)), int(arg("--end", FRAMES))
ACTION, SKY, WEATHER, CAMERA = P.get("action", "wave"), P.get("sky", "dusk"), P.get("weather", "none"), P.get("camera", "pull")
WIND = float(P.get("wind", 0.7)); TRANSP = P.get("background", "scene") == "transparent"
WORK = os.path.abspath(os.path.join(OUT, "..", "cache_" + os.path.basename(os.path.abspath(OUT)))); os.makedirs(WORK, exist_ok=True)
fmeta = json.load(open(f"{DATA}/meta.json"))
sc = C.reset(FPS)
sc.frame_start, sc.frame_end = 1, FRAMES
rng = np.random.default_rng(int(P.get("seed", 7)))
tf = lambda f: (f - 1) / FPS
CF = np.arange(1, FRAMES + 3)                 # cache frames (one extra for motion blur)
TT = np.array([tf(f) for f in CF])

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
AW = 0.18 + 0.34 * WIND; SPD = 0.6 + 0.8 * WIND
HANG = math.radians(75 * (1 - WIND) ** 1.5)


def flag_at(t):
    tw = SPD * t
    A = AW * UU ** 0.7 * (0.88 + 0.12 * math.sin(0.8 * tw))
    y = A * (np.sin(2 * np.pi * (1.6 * UU - 1.05 * tw) + 1.4 * VV)
             + 0.45 * np.sin(2 * np.pi * (3.1 * UU - 1.9 * tw) + 2.3 * VV + 1.1)
             + 0.22 * UU * np.sin(2 * np.pi * (6.2 * UU - 3.4 * tw) - 2.6 * VV + 0.3))
    dx0 = L / NU
    dxs = np.sqrt(np.clip(dx0 ** 2 - np.diff(y, axis=1) ** 2, (0.35 * dx0) ** 2, None))
    x = np.concatenate([np.zeros((NV + 1, 1)), np.cumsum(dxs, axis=1)], 1)
    z = -HH * (1 - VV) - 0.16 * UU ** 2 + 0.05 * UU * np.sin(2 * np.pi * (0.9 * UU - 0.7 * tw) + 2.3 * VV)
    xr = 0.075 + x * math.cos(HANG)          # hoist stays on the pole, the fly end droops in weak wind
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
for k, val in (("Sheen Weight", 0.6), ("Sheen Roughness", 0.35)):
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

# ------------------------------------------------------------------ pole, finial, halyard, plinth, roof, city
metal = C.mat("pole", (0.78, 0.78, 0.8), 0.28, 1.0)
gold = C.mat("gold", (1.0, 0.76, 0.33), 0.22, 1.0)
stone = C.mat("stone", (0.42, 0.40, 0.37), 0.8)
roof = C.mat("roof", (0.10, 0.10, 0.11), 0.9)
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=14.3, location=(0, 0, 7.15), vertices=32); C.put(bpy.context.active_object, metal)
if P.get("finial", "ball") == "spear":
    bpy.ops.mesh.primitive_cone_add(radius1=0.09, depth=0.5, location=(0, 0, 14.55), vertices=24); C.put(bpy.context.active_object, gold)
else:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(0, 0, 14.42), segments=32, ring_count=16)
    C.put(bpy.context.active_object, gold); C.smooth_shade(bpy.context.active_object)
bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=14.0, location=(-0.07, 0.0, 7.1), vertices=8)
C.put(bpy.context.active_object, C.mat("rope", (0.85, 0.82, 0.74), 0.7))
if not TRANSP:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6, location=(0, 0, 0.3), vertices=48); C.put(bpy.context.active_object, stone)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); C.put(bpy.context.active_object, roof)
    bpy.ops.mesh.primitive_plane_add(size=6000, location=(0, 0, -30))
    C.put(bpy.context.active_object, C.mat("land", (0.05, 0.06, 0.055), 0.95))
    if P.get("city", SKY in ("dusk", "night", "storm")):
        cols = [C.emitter("c1", (1.0, 0.42, 0.12), 11), C.emitter("c2", (1.0, 0.62, 0.25), 9), C.emitter("c3", (0.95, 0.85, 0.7), 7)]
        bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=1, location=(0, 0, -900)); base = bpy.context.active_object
        for i in range(800):
            m = bpy.data.objects.new(f"city{i}", base.data.copy()); sc.collection.objects.link(m)
            m.location = (rng.uniform(-700, 700), rng.uniform(160, 1100), rng.uniform(-29.5, -27)); r = rng.uniform(0.6, 1.8); m.scale = (r, r, r)
            C.put(m, cols[int(rng.integers(0, 3))])

# ------------------------------------------------------------------ weather (analytic points)
BOX = ((-10, 14), (-16, 12), (-2, 30))
WX = {"snow": (42000, (0.006, 0.019), (0.55, 1.35), (0.95, 0.97, 1.0), 0.5),
      "rain": (70000, (0.0025, 0.005), (8.0, 10.5), (0.8, 0.85, 0.9), 0.25),
      "embers": (3500, (0.008, 0.022), (-1.3, -0.5), (1.0, 0.45, 0.12), 9.0),
      "dust": (7000, (0.003, 0.009), (-0.08, 0.08), (1.0, 0.85, 0.6), 0.6)}
if WEATHER in WX:
    n, rr, sp, col, est = WX[WEATHER]
    P0 = np.stack([rng.uniform(*BOX[0], n), rng.uniform(*BOX[1], n), rng.uniform(*BOX[2], n)], 1)
    S_ = rng.uniform(*sp, n); AMP = rng.uniform(0.04, 0.22, n); PH = rng.uniform(0, 2 * np.pi, (n, 2)); FR = rng.uniform(0.4, 1.1, (n, 2))
    drift = {"snow": 0.45, "rain": 1.6, "embers": 0.5, "dust": 0.15}[WEATHER] * (0.4 + WIND)
    zlo, zh = BOX[2][0], BOX[2][1] - BOX[2][0]

    def wx_at(t):
        tt = t + 2.0
        x = P0[:, 0] + drift * tt + AMP * np.sin(FR[:, 0] * tt + PH[:, 0])
        y = P0[:, 1] + AMP * np.sin(FR[:, 1] * tt + PH[:, 1])
        z = zlo + np.mod(P0[:, 2] - S_ * tt - zlo, zh)
        x = BOX[0][0] + np.mod(x - BOX[0][0], BOX[0][1] - BOX[0][0])
        return np.stack([x, y, z], 1)

    C.write_pc2(f"{WORK}/wx.pc2", np.stack([wx_at(t) for t in TT]))
    C.points_object("weather", wx_at(TT[0]), rng.uniform(*rr, n), C.mat("wx", col, 0.45, emit=col, estr=est), f"{WORK}/wx.pc2")

# ------------------------------------------------------------------ sky, sun, lights
fc0, fc1 = flag_center(0), flag_center(T)
zmid = (fc0.z + fc1.z) / 2
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; wn = w.node_tree; bg = wn.nodes["Background"]
SKYS = {"day": (40, 200, 3.4, (1.0, 0.96, 0.9), 0.75), "dawn": (4, 20, 2.4, (1.0, 0.72, 0.48), 0.9),
        "dusk": (2.5, -25, 2.0, (1.0, 0.6, 0.35), 0.9)}


def sun_lamp(el, rot, energy, color):
    d = Vector((-math.cos(math.radians(el)) * math.sin(math.radians(rot)), math.cos(math.radians(el)) * math.cos(math.radians(rot)), math.sin(math.radians(el))))
    sd = bpy.data.lights.new("sun", "SUN"); sd.energy = energy; sd.color = color; sd.angle = math.radians(1.0)
    so = bpy.data.objects.new("sun", sd); sc.collection.objects.link(so)
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


def spot(name, loc, target, power, size, color, blend=0.6, soft=0.4):
    ld = bpy.data.lights.new(name, "SPOT"); ld.energy = power; ld.spot_size = math.radians(size); ld.spot_blend = blend
    ld.color = color; ld.shadow_soft_size = soft
    o = bpy.data.objects.new(name, ld); o.location = loc; sc.collection.objects.link(o); C.aim(o, target)
    o.visible_camera = False


if SKY in SKYS:
    el, rot, en, col, bs = SKYS[SKY]
    sky = wn.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "NISHITA"; sky.sun_disc = SKY != "day"; sky.sun_elevation = math.radians(el); sky.sun_rotation = math.radians(rot)
        sky.altitude = 40.0; sky.air_density = 1.0; sky.dust_density = 2.2 if SKY != "day" else 1.2; sky.ozone_density = 1.0
    except Exception as e:
        print("sky fallback", e)
    wn.links.new(sky.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = bs
    sun_lamp(el, rot, en, col)
    if SKY != "day":
        ad = bpy.data.lights.new("fill", "AREA"); ad.energy = 900; ad.size = 8; ad.color = (0.75, 0.82, 1.0)
        ao = bpy.data.objects.new("fill", ad); ao.location = (fc0.x - 3, -14, zmid + 2); sc.collection.objects.link(ao); C.aim(ao, (fc0.x, 0, zmid))
        ao.visible_camera = False
else:
    tcw = wn.nodes.new("ShaderNodeTexCoord"); sep = wn.nodes.new("ShaderNodeSeparateXYZ")
    mr = wn.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -0.05; mr.inputs["From Max"].default_value = 0.55
    ramp = wn.nodes.new("ShaderNodeValToRGB")
    if SKY == "storm":
        ramp.color_ramp.elements[0].color = (0.10, 0.11, 0.12, 1); ramp.color_ramp.elements[1].color = (0.035, 0.04, 0.05, 1)
    else:
        ramp.color_ramp.elements[0].color = (0.028, 0.017, 0.012, 1); ramp.color_ramp.elements[1].color = (0.003, 0.006, 0.017, 1)
        ramp.color_ramp.elements.new(0.18).color = (0.05, 0.032, 0.026, 1)
    wn.links.new(tcw.outputs["Generated"], sep.inputs[0]); wn.links.new(sep.outputs["Z"], mr.inputs["Value"])
    wn.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    cl = wn.nodes.new("ShaderNodeTexNoise"); cl.inputs["Scale"].default_value = 2.2; cl.inputs["Detail"].default_value = 7.0
    wn.links.new(tcw.outputs["Generated"], cl.inputs["Vector"])
    cmr = wn.nodes.new("ShaderNodeMapRange"); cmr.inputs["From Min"].default_value = 0.48; cmr.inputs["From Max"].default_value = 0.78
    wn.links.new(cl.outputs["Fac"], cmr.inputs["Value"])
    cadd = wn.nodes.new("ShaderNodeMix"); cadd.data_type = "RGBA"; cadd.blend_type = "ADD"
    cadd.inputs[7].default_value = (0.03, 0.033, 0.04, 1) if SKY == "storm" else (0.010, 0.013, 0.026, 1)
    wn.links.new(cmr.outputs["Result"], cadd.inputs[0]); wn.links.new(ramp.outputs["Color"], cadd.inputs[6])
    wn.links.new(cadd.outputs[2], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 1.0
    sun_lamp(55, 160, 0.12 if SKY == "night" else 0.6, (0.62, 0.72, 1.0))
    cx = fc0.x
    spot("rake", (cx + 6.5, -2.4, zmid + 2.5), (cx, 0, zmid), 5200, 60, (1.0, 0.84, 0.62), 0.5, 0.25)
    spot("key", (cx + 2.0, -9.0, zmid - 2.0), (cx, 0, zmid), 2600, 60, (1.0, 0.86, 0.68))
    spot("fill", (cx - 6.0, -6.5, zmid + 1.0), (cx, 0, zmid), 700, 60, (0.78, 0.85, 1.0))
    spot("rim", (cx - 4.0, 7.0, zmid + 4.0), (cx, 0, zmid), 3000, 60, (0.75, 0.82, 1.0))

# ------------------------------------------------------------------ camera presets (follow the flag)
camd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
look = bpy.data.objects.new("look", None); sc.collection.objects.link(look)
focus = bpy.data.objects.new("focus", None); sc.collection.objects.link(focus)
c = cam.constraints.new("TRACK_TO"); c.target = look; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
camd.sensor_width = 36; camd.dof.use_dof = True; camd.dof.focus_object = focus; camd.clip_start = 0.3; camd.clip_end = 8000


FU, FV = [float(x) for x in P.get("focus_uv", [0.3, 0.65])]     # point of interest on the flag (emblem)


def shot(t):
    k = t / T; f = flag_center(t); q = flag_point(t, FU, FV)
    if CAMERA == "pull":
        a = C.smooth(k / 0.45); b = C.smooth((k - 0.45) / 0.55)
        cp = Vector((q.x - 0.3, -2.9, q.z - 0.1)).lerp(Vector((q.x + 0.2, -2.4, q.z + 0.05)), a).lerp(Vector((f.x + 1.4, -10.5, f.z - 0.5)), b)
        lp = q.lerp(Vector((f.x - 0.3, 0, f.z - 0.3)), b)
        return cp, lp, (q if b < 0.5 else f), 50, 1.8 + 1.2 * b
    if CAMERA == "push":
        cp = Vector((f.x + 2.6, -15.0, f.z - 1.6)).lerp(Vector((f.x + 0.9, -7.6, f.z - 0.5)), C.smooth(k))
        return cp, f, f, 50, 2.8
    if CAMERA == "orbit":
        an = math.radians(-118 + 56 * C.smooth(k)); r = 9.5
        return Vector((f.x + r * math.cos(an), r * math.sin(an), f.z - 0.8 + 1.2 * k)), f, f, 45, 2.8
    cp = Vector((f.x + 3.6, -6.2, 1.7)).lerp(Vector((f.x + 2.1, -5.3, 1.3)), C.smooth(k))   # low, heroic
    return cp, f, f, 26, 4.0


for i in range(int(math.ceil(T)) + 1):
    t = min(T, float(i)); fr = 1 + round(t * FPS)
    cp, lp, fp, lens, fs = shot(t)
    cam.location = cp; look.location = lp; focus.location = fp; camd.lens = lens; camd.dof.aperture_fstop = fs
    for ob in (cam, look, focus): ob.keyframe_insert("location", frame=fr)
    camd.keyframe_insert("lens", frame=fr); camd.dof.keyframe_insert("aperture_fstop", frame=fr)
C.bezier_keys([cam, look, focus])

# ------------------------------------------------------------------ render
C.setup_cycles(sc, GPU, samples=int(P.get("samples", 128)), motion_blur=True, transparent=TRANSP)
if not TRANSP:
    vl = sc.view_layers[0]; vl.use_pass_mist = True
    w.mist_settings.start = 60; w.mist_settings.depth = 900; w.mist_settings.falloff = "QUADRATIC"
    sc.use_nodes = True; ct = sc.node_tree; ct.nodes.clear()
    rl = ct.nodes.new("CompositorNodeRLayers")
    hz = {"day": (0.62, 0.70, 0.80), "dawn": (0.85, 0.62, 0.48), "dusk": (0.55, 0.36, 0.30), "night": (0.03, 0.03, 0.05), "storm": (0.10, 0.11, 0.12)}[SKY]
    mx_ = ct.nodes.new("CompositorNodeMixRGB"); mx_.inputs[2].default_value = (*hz, 1)
    mf = ct.nodes.new("CompositorNodeMath"); mf.operation = "MULTIPLY"; mf.inputs[1].default_value = 0.85
    ct.links.new(rl.outputs["Mist"], mf.inputs[0]); ct.links.new(mf.outputs[0], mx_.inputs[0]); ct.links.new(rl.outputs["Image"], mx_.inputs[1])
    comp = ct.nodes.new("CompositorNodeComposite"); ct.links.new(mx_.outputs[0], comp.inputs[0])
print(f"built: flag {len(verts0)} verts, action {ACTION}, sky {SKY}, weather {WEATHER}, camera {CAMERA}, frames {START}-{END}", flush=True)
C.render_frames(sc, OUT, START, END)
