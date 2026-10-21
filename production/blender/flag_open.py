"""Opening shot (Blender Cycles): the red flag over the Kremlin Senate dome, night of 25 Dec 1991, falling snow.
Macro slow-motion on the emblem -> crane pull-back revealing the pole, the floodlit dome, the Spasskaya star and the
city lights -> the flag is lowered. Flag and snow motion are analytic (written as PC2 point caches), so every frame
can be rendered independently on any runner and the result is bit-identical across chunks.
usage: blender -b -P flag_open.py -- --tex flag.png --work /tmp/fo --out frames --start 61 --end 367 [--res 100 --samples 160]
Blender frame 61 = film frame 0 (2 s of pre-roll for the motion caches)."""
import bpy, math, os, struct, sys
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = lambda k, d=None: a[a.index(k) + 1] if k in a else d
TEX, WORK, OUT = arg("--tex"), arg("--work", "/tmp/fo"), arg("--out", "frames")
S, E = int(arg("--start", 61)), int(arg("--end", 367))
RES, SPP = int(arg("--res", 100)), int(arg("--samples", 160))
FPS, F0, F1 = 30, 1, 375                      # cache frames
os.makedirs(WORK, exist_ok=True); os.makedirs(OUT, exist_ok=True)
tf = lambda bf: (bf - 61) / FPS               # Blender frame -> film seconds
bf = lambda t: 61 + t * FPS                   # film seconds -> Blender frame

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS; sc.frame_start, sc.frame_end = S, E


def write_pc2(path, frames):                  # frames: (n_frames, n_verts, 3) float32
    frames = np.ascontiguousarray(frames, np.float32)
    with open(path, "wb") as f:
        f.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, frames.shape[1], 0.0, 1.0, frames.shape[0]))
        f.write(frames.tobytes())


def smooth(x): x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emit=None, estr=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1); p.inputs["Emission Strength"].default_value = estr
    return m


def emitter(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (*color, 1); em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"]); return m


def put(obj, m):
    obj.data.materials.clear(); obj.data.materials.append(m); return obj


def smooth_shade(obj):
    try: obj.data.shade_smooth()
    except Exception: obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))


def aim(obj, target):
    d = Vector(target) - obj.location; obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------------ the flag (analytic cloth motion)
NU, NV, L, HH = 72, 36, 4.0, 2.0
u = np.linspace(0, 1, NU + 1); v = np.linspace(0, 1, NV + 1)
U, V = np.meshgrid(u, v)                                      # (NV+1, NU+1)
frames_t = np.array([tf(f) for f in range(F0, F1 + 1)])
speed = np.array([0.55 + 0.45 * smooth((t - 3.8) / 1.6) for t in frames_t])   # slow motion on the macro, then real time
tw = np.cumsum(speed) / FPS


def z_top(t):
    return 13.6 - 5.2 * smooth((t - 6.45) / 2.45) - 0.8 * smooth((t - 8.9) / 1.6)


def flag_at(tw_, t):
    A = 0.30 * U ** 0.85 * (0.9 + 0.1 * math.sin(0.8 * tw_))
    y = A * (np.sin(2 * np.pi * (1.05 * U - 0.85 * tw_) + 0.7 * V)
             + 0.42 * np.sin(2 * np.pi * (2.2 * U - 1.6 * tw_) + 1.8 * V + 1.1)
             + 0.16 * U * np.sin(2 * np.pi * (4.4 * U - 3.0 * tw_) - 2.2 * V + 0.3))
    dx0 = L / NU
    dxs = np.sqrt(np.clip(dx0 ** 2 - np.diff(y, axis=1) ** 2, (0.35 * dx0) ** 2, None))   # keep the cloth length
    x = 0.075 + np.concatenate([np.zeros((NV + 1, 1)), np.cumsum(dxs, axis=1)], 1)
    z = z_top(t) - HH * (1 - V) - 0.16 * U ** 2 + 0.05 * U * np.sin(2 * np.pi * (0.9 * U - 0.7 * tw_) + 2.3 * V)
    return np.stack([x, y, z], -1).reshape(-1, 3)


verts0 = flag_at(tw[0], frames_t[0])
faces = []
for j in range(NV):
    for i in range(NU):
        k = j * (NU + 1) + i; faces.append((k, k + 1, k + NU + 2, k + NU + 1))
me = bpy.data.meshes.new("flag"); me.from_pydata(verts0.tolist(), [], faces); me.update()
uvl = me.uv_layers.new(name="UVMap")
lvi = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lvi)
UVv = np.stack([U.ravel(), V.ravel()], 1)
uvl.data.foreach_set("uv", UVv[lvi].ravel().astype(np.float32))
flag = bpy.data.objects.new("flag", me); sc.collection.objects.link(flag); smooth_shade(flag)
write_pc2(f"{WORK}/flag.pc2", np.stack([flag_at(tw[i], frames_t[i]) for i in range(len(frames_t))]))
mc = flag.modifiers.new("cache", "MESH_CACHE"); mc.cache_format = "PC2"; mc.filepath = f"{WORK}/flag.pc2"
mc.time_mode = "FRAME"; mc.play_mode = "SCENE"; mc.frame_start = F0; mc.frame_scale = 1.0; mc.interpolation = "LINEAR"
flag.modifiers.new("solid", "SOLIDIFY").thickness = 0.004

fm = bpy.data.materials.new("flag"); fm.use_nodes = True; nt = fm.node_tree
p = nt.nodes["Principled BSDF"]; out = nt.nodes["Material Output"]
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(TEX); tex.interpolation = "Cubic"
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
put(flag, fm)

# ------------------------------------------------------------------ pole, finial, the Senate dome, building
metal = mat("pole", (0.78, 0.78, 0.8), 0.28, 1.0)
gold = mat("gold", (1.0, 0.76, 0.33), 0.22, 1.0)
copper = mat("dome", (0.2, 0.42, 0.34), 0.42, 0.35)
ochre = mat("ochre", (0.78, 0.6, 0.32), 0.7)
white = mat("white", (0.85, 0.84, 0.8), 0.6)
brick = mat("brick", (0.33, 0.07, 0.05), 0.8)
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=14.3, location=(0, 0, 7.05), vertices=32); put(bpy.context.active_object, metal)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(0, 0, 14.3), segments=32, ring_count=16)
put(bpy.context.active_object, gold); smooth_shade(bpy.context.active_object)
bpy.ops.mesh.primitive_cylinder_add(radius=0.9, depth=1.6, location=(0, 0, -0.8), vertices=48); put(bpy.context.active_object, white)
bpy.ops.mesh.primitive_cylinder_add(radius=1.05, depth=0.16, location=(0, 0, 0.05), vertices=48); put(bpy.context.active_object, copper)
bpy.ops.mesh.primitive_uv_sphere_add(radius=6.5, location=(0, 0, -6.8), segments=96, ring_count=48)
d = bpy.context.active_object; d.scale = (1, 1, 0.8); put(d, copper); smooth_shade(d)
bpy.ops.mesh.primitive_cylinder_add(radius=6.6, depth=5.2, location=(0, 0, -9.4), vertices=96); put(bpy.context.active_object, ochre)
bpy.ops.mesh.primitive_torus_add(major_radius=6.95, minor_radius=0.24, location=(0, 0, -6.85), major_segments=96, minor_segments=12)
put(bpy.context.active_object, white)
for i in range(28):
    an = 2 * math.pi * i / 28
    bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=4.7, location=(6.95 * math.cos(an), 6.95 * math.sin(an), -9.55), vertices=16)
    put(bpy.context.active_object, white)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -19)); b = bpy.context.active_object; b.scale = (80, 18, 14); put(b, ochre)
win = emitter("window", (1.0, 0.72, 0.42), 6.0)
rng = np.random.default_rng(5)
for row in (-15.5, -21.0):
    for x in np.arange(-38, 38.1, 3.2):
        if rng.random() < 0.55:
            bpy.ops.mesh.primitive_plane_add(size=1, location=(float(x), -9.02, row), rotation=(math.pi / 2, 0, 0))
            w = bpy.context.active_object; w.scale = (1.1, 2.0, 1); put(w, win)

# city lights behind (bokeh)
cols = [emitter("c1", (1.0, 0.42, 0.12), 11), emitter("c2", (1.0, 0.62, 0.25), 9), emitter("c3", (0.95, 0.85, 0.7), 7)]
bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=1, location=(0, 0, -500)); base = bpy.context.active_object
for i in range(700):
    m = bpy.data.objects.new(f"city{i}", base.data.copy()); sc.collection.objects.link(m)
    m.location = (rng.uniform(-520, 520), rng.uniform(250, 900), rng.uniform(-62, -16)); r = rng.uniform(0.6, 1.6); m.scale = (r, r, r)
    put(m, cols[int(rng.integers(0, 3))])

# ------------------------------------------------------------------ snow (analytic, PC2 + points)
pops = [(42000, (-8, 12), (-12, 14), (0, 40))]           # uniform ~2 flakes / m3 around the whole shot
P0, SPD, AMP, PH, FR = [], [], [], [], []
for n, (x0, x1), (y0, y1), (z0, z1) in pops:
    P0.append(np.stack([rng.uniform(x0, x1, n), rng.uniform(y0, y1, n), rng.uniform(z0, z1, n)], 1))
P0 = np.concatenate(P0); N = len(P0)
SPD = rng.uniform(0.55, 1.35, N); AMP = rng.uniform(0.04, 0.22, N); PH = rng.uniform(0, 2 * np.pi, (N, 2)); FR = rng.uniform(0.4, 1.1, (N, 2))
def snow_at(t):
    tt = t + 2.0
    return np.stack([P0[:, 0] + 0.45 * tt + AMP * np.sin(FR[:, 0] * tt + PH[:, 0]),
                     P0[:, 1] + AMP * np.sin(FR[:, 1] * tt + PH[:, 1]),
                     P0[:, 2] - SPD * tt], 1)
sm = bpy.data.meshes.new("snow"); sm.from_pydata(snow_at(frames_t[0]).tolist(), [], []); sm.update()
ra = sm.attributes.new("rad", "FLOAT", "POINT"); ra.data.foreach_set("value", rng.uniform(0.006, 0.019, N).astype(np.float32))
snow = bpy.data.objects.new("snow", sm); sc.collection.objects.link(snow)
write_pc2(f"{WORK}/snow.pc2", np.stack([snow_at(t) for t in frames_t]))
mc = snow.modifiers.new("cache", "MESH_CACHE"); mc.cache_format = "PC2"; mc.filepath = f"{WORK}/snow.pc2"
mc.time_mode = "FRAME"; mc.play_mode = "SCENE"; mc.frame_start = F0; mc.frame_scale = 1.0; mc.interpolation = "LINEAR"
ng = bpy.data.node_groups.new("snowpts", "GeometryNodeTree")
ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
gi = ng.nodes.new("NodeGroupInput"); go = ng.nodes.new("NodeGroupOutput")
m2p = ng.nodes.new("GeometryNodeMeshToPoints"); m2p.mode = "VERTICES"
na = ng.nodes.new("GeometryNodeInputNamedAttribute"); na.data_type = "FLOAT"; na.inputs["Name"].default_value = "rad"
smat = ng.nodes.new("GeometryNodeSetMaterial")
smat.inputs["Material"].default_value = mat("snow", (0.95, 0.97, 1.0), 0.45, emit=(0.9, 0.95, 1.0), estr=0.5)
ng.links.new(gi.outputs[0], m2p.inputs["Mesh"]); ng.links.new(na.outputs["Attribute"], m2p.inputs["Radius"])
ng.links.new(m2p.outputs["Points"], smat.inputs["Geometry"]); ng.links.new(smat.outputs["Geometry"], go.inputs[0])
snow.modifiers.new("pts", "NODES").node_group = ng

# ------------------------------------------------------------------ lights + world
def spot(name, loc, target, power, size, color, blend=0.6, soft=0.4):
    ld = bpy.data.lights.new(name, "SPOT"); ld.energy = power; ld.spot_size = math.radians(size); ld.spot_blend = blend
    ld.color = color; ld.shadow_soft_size = soft
    o = bpy.data.objects.new(name, ld); o.location = loc; sc.collection.objects.link(o); aim(o, target)
    o.visible_camera = False; return o
spot("key", (3.5, -9.0, 5.5), (1.6, 0, 11.5), 6500, 34, (1.0, 0.86, 0.68))
spot("fill", (-4.5, -6.5, 8.0), (1.5, 0, 12.0), 1400, 40, (0.78, 0.85, 1.0))
spot("rim", (2.5, 8.0, 16.5), (1.8, 0, 12.0), 3200, 40, (1.0, 0.8, 0.6))
for i in range(4):
    an = math.radians(45 + 90 * i)
    spot(f"flood{i}", (24 * math.cos(an), 24 * math.sin(an), -18), (0, 0, -4), 22000, 38, (1.0, 0.78, 0.52), 0.5, 1.0)
sd = bpy.data.lights.new("moon", "SUN"); sd.energy = 0.12; sd.color = (0.62, 0.72, 1.0); sd.angle = math.radians(2)
so = bpy.data.objects.new("moon", sd); so.rotation_euler = (math.radians(55), 0, math.radians(160)); sc.collection.objects.link(so)

w = bpy.data.worlds.new("night"); sc.world = w; w.use_nodes = True; wn = w.node_tree
bg = wn.nodes["Background"]; bg.inputs["Strength"].default_value = 1.0
tcw = wn.nodes.new("ShaderNodeTexCoord"); sep = wn.nodes.new("ShaderNodeSeparateXYZ")
mr = wn.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -0.05; mr.inputs["From Max"].default_value = 0.55
ramp = wn.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.028, 0.017, 0.012, 1); ramp.color_ramp.elements[1].color = (0.003, 0.006, 0.017, 1)
ramp.color_ramp.elements.new(0.18).color = (0.05, 0.032, 0.026, 1)
wn.links.new(tcw.outputs["Generated"], sep.inputs[0]); wn.links.new(sep.outputs["Z"], mr.inputs["Value"])
wn.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
cl = wn.nodes.new("ShaderNodeTexNoise"); cl.inputs["Scale"].default_value = 2.2; cl.inputs["Detail"].default_value = 7.0
wn.links.new(tcw.outputs["Generated"], cl.inputs["Vector"])
cmr = wn.nodes.new("ShaderNodeMapRange"); cmr.inputs["From Min"].default_value = 0.48; cmr.inputs["From Max"].default_value = 0.78
wn.links.new(cl.outputs["Fac"], cmr.inputs["Value"])
cadd = wn.nodes.new("ShaderNodeMix"); cadd.data_type = "RGBA"; cadd.blend_type = "ADD"
cadd.inputs[7].default_value = (0.010, 0.013, 0.026, 1)
wn.links.new(cmr.outputs["Result"], cadd.inputs[0]); wn.links.new(ramp.outputs["Color"], cadd.inputs[6])
wn.links.new(cadd.outputs[2], bg.inputs["Color"])

# ------------------------------------------------------------------ camera: macro -> crane pull-back
camd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
look = bpy.data.objects.new("look", None); sc.collection.objects.link(look)
focus = bpy.data.objects.new("focus", None); sc.collection.objects.link(focus)
c = cam.constraints.new("TRACK_TO"); c.target = look; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
camd.sensor_width = 36; camd.dof.use_dof = True; camd.dof.focus_object = focus; camd.clip_start = 0.6; camd.clip_end = 3000
KEYS = [  # t, camera, look-at, focus point, lens, f-stop
    (-2.0, (-0.12, -2.95, 12.72), (0.20, 0, 13.04), (0.78, 0, 13.0), 50, 1.8),
    (0.0, (-0.08, -2.90, 12.75), (0.25, 0, 13.05), (0.80, 0, 13.0), 50, 1.8),
    (4.3, (0.45, -2.50, 13.00), (0.60, 0, 13.00), (0.85, 0, 13.0), 50, 1.8),
    (6.9, (3.20, -9.6, 11.2), (1.75, 0, 11.75), (1.95, 0, 12.6), 50, 2.8),
    (9.0, (3.45, -10.6, 8.7), (1.80, 0, 9.2), (1.95, 0, 9.4), 50, 2.8),
    (10.4, (3.55, -11.0, 7.9), (1.80, 0, 8.3), (1.95, 0, 8.6), 50, 2.8),
]
for t, cl, ll, fl, lens, fs in KEYS:
    f = bf(t); cam.location = cl; look.location = ll; focus.location = fl; camd.lens = lens; camd.dof.aperture_fstop = fs
    cam.keyframe_insert("location", frame=f); look.keyframe_insert("location", frame=f); focus.keyframe_insert("location", frame=f)
    camd.keyframe_insert("lens", frame=f); camd.dof.keyframe_insert("aperture_fstop", frame=f)

# ------------------------------------------------------------------ render
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = SPP; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception: pass
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 2
sc.cycles.volume_bounces = 0; sc.cycles.sample_clamp_indirect = 8.0
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.45
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, RES
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(os.path.abspath(OUT), "f_")
print(f"built: flag {len(verts0)} verts, snow {N} pts, frames {S}-{E} at {RES}% / {SPP} spp", flush=True)
bpy.ops.render.render(animation=True)
print("rendered", S, E, flush=True)
