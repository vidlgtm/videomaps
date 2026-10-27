"""Shared Blender helpers of the workshop (Blender 4.5, Cycles).
Every scene build runs in one of two modes:
  render  : --start/--end frames at 1920x1080 (GPU), exposure --ev, time budget --budget-min (stops early when the
            projected time is over it, exit code 3)
  preview : --preview, CPU: check grid (rays through 48x27 image points on sampled frames), exposure calibration
            towards the scene's target, 6 key frames at 640x360 + check.json for factory/workshop/preview.py"""
import bpy, gc, json, math, os, shutil, struct, sys, time
import numpy as np
from mathutils import Vector

T_PROC = time.time()
NX, NY = 48, 27


class Opts:
    pass


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    get = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    o = Opts()
    o.params = json.load(open(get("--params")))
    o.data, o.out, o.gpu = get("--data"), os.path.abspath(get("--out", "frames")), get("--gpu")
    o.start = int(get("--start", 1))
    o.end = int(get("--end")) if get("--end") else None
    o.ev = float(get("--ev", 0) or 0)
    o.budget = float(get("--budget-min", 0) or 0)
    o.preview = "--preview" in a
    os.makedirs(o.out, exist_ok=True)
    return o.params, o


def reset(fps=30):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = fps
    return sc


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def key_frames(n, k=6):
    return sorted({1 + round(i * (n - 1) / (k - 1)) for i in range(k)})


# ------------------------------------------------------------------ geometry
def write_pc2(path, frames):
    """(n_frames, n_verts, 3) float32 -> PC2 point cache (analytic motion, any frame renders on its own)"""
    frames = np.ascontiguousarray(frames, np.float32)
    with open(path, "wb") as f:
        f.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, frames.shape[1], 0.0, 1.0, frames.shape[0]))
        f.write(frames.tobytes())


def use_cache(obj, path, frame_start=1):
    mc = obj.modifiers.new("cache", "MESH_CACHE"); mc.cache_format = "PC2"; mc.filepath = path
    mc.time_mode = "FRAME"; mc.play_mode = "SCENE"; mc.frame_start = frame_start; mc.frame_scale = 1.0; mc.interpolation = "LINEAR"
    return mc


def mesh_object(name, co, quads=None, tris=None, face_float=None, link=True):
    """big meshes straight from numpy (vertices already in world space, identity transform)"""
    co = np.ascontiguousarray(co, np.float32).reshape(-1, 3)
    polys = [np.asarray(x, np.int64) for x in (quads, tris) if x is not None and len(x)]
    sizes = np.concatenate([np.full(len(x), x.shape[1], np.int64) for x in polys]) if polys else np.zeros(0, np.int64)
    vidx = np.concatenate([x.ravel() for x in polys]).astype(np.int32) if polys else np.zeros(0, np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co)); me.vertices.foreach_set("co", co.ravel())
    me.loops.add(len(vidx)); me.polygons.add(len(sizes))
    starts = np.zeros(len(sizes), np.int32)
    if len(sizes): starts[1:] = np.cumsum(sizes)[:-1]
    me.polygons.foreach_set("loop_start", starts)
    try: me.polygons.foreach_set("loop_total", sizes.astype(np.int32))
    except Exception: pass
    me.polygons.foreach_set("vertices", vidx)
    me.update(calc_edges=True)
    for k, v in (face_float or {}).items():
        at = me.attributes.new(k, "FLOAT", "FACE"); at.data.foreach_set("value", np.asarray(v, np.float32))
    ob = bpy.data.objects.new(name, me)
    if link: bpy.context.scene.collection.objects.link(ob)
    return ob


def smooth_shade(obj):
    try: obj.data.shade_smooth()
    except Exception: obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))


def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def bezier_keys(objs):
    for ob in objs:
        ad = ob.animation_data
        if not ad or not ad.action: continue
        for fc in ad.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = "BEZIER"; k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"


def no_motion_blur(ob):
    for name in ("use_motion_blur", "use_deform_motion"):
        for owner in (getattr(ob, "cycles", None), ob):
            try:
                if owner is not None and hasattr(owner, name): setattr(owner, name, False)
            except Exception: pass


# ------------------------------------------------------------------ materials
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
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def not_a_light(m):
    """glows to the camera without being sampled as a light source (windows, city lights: fast, no noise)"""
    for owner in (getattr(m, "cycles", None), m):
        try:
            if owner is not None and hasattr(owner, "emission_sampling"): owner.emission_sampling = "NONE"; return True
        except Exception: pass
    return False


def put(obj, m):
    obj.data.materials.clear(); obj.data.materials.append(m)
    return obj


def add_fog(m, sky_group, start, depth, strength=1.0, maxf=1.0):
    """aerial perspective inside the material: camera rays fade toward the colour of the sky behind the point
    (the world itself stays untouched, so the horizon has no seam)"""
    nt = m.node_tree; N, L = nt.nodes, nt.links
    out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
    if not out.inputs["Surface"].links: return
    surf = out.inputs["Surface"].links[0].from_socket
    cd = N.new("ShaderNodeCameraData")
    mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = start; mr.inputs["From Max"].default_value = start + depth
    mr.clamp = True
    L.new(cd.outputs["View Distance"], mr.inputs["Value"])
    pw = N.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.0; L.new(mr.outputs["Result"], pw.inputs[0])
    lp = N.new("ShaderNodeLightPath")
    mu = N.new("ShaderNodeMath"); mu.operation = "MULTIPLY"; L.new(pw.outputs[0], mu.inputs[0]); L.new(lp.outputs["Is Camera Ray"], mu.inputs[1])
    mu2 = N.new("ShaderNodeMath"); mu2.operation = "MULTIPLY"; mu2.inputs[1].default_value = maxf; L.new(mu.outputs[0], mu2.inputs[0])
    geo = N.new("ShaderNodeNewGeometry")
    neg = N.new("ShaderNodeVectorMath"); neg.operation = "SCALE"; neg.inputs["Scale"].default_value = -1.0
    L.new(geo.outputs["Incoming"], neg.inputs[0])
    g = N.new("ShaderNodeGroup"); g.node_tree = sky_group; L.new(neg.outputs[0], g.inputs[0])
    em = N.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = strength; L.new(g.outputs[0], em.inputs["Color"])
    mix = N.new("ShaderNodeMixShader"); L.new(mu2.outputs[0], mix.inputs[0]); L.new(surf, mix.inputs[1]); L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])


def points_object(name, verts, radii, material, cache=None, streak=None):
    """vertex cloud rendered as spheres of per-point radius (snow, embers, dust), or as thin streaks
    streak = (length per unit radius, euler) for rain: the streak already shows the motion, so no motion blur is needed"""
    sc = bpy.context.scene
    me = bpy.data.meshes.new(name); me.vertices.add(len(verts)); me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel()); me.update()
    ra = me.attributes.new("rad", "FLOAT", "POINT"); ra.data.foreach_set("value", np.asarray(radii, np.float32))
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    if cache: use_cache(ob, cache)
    ng = bpy.data.node_groups.new(name + "_pts", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput"); go = ng.nodes.new("NodeGroupOutput")
    m2p = ng.nodes.new("GeometryNodeMeshToPoints"); m2p.mode = "VERTICES"
    na = ng.nodes.new("GeometryNodeInputNamedAttribute"); na.data_type = "FLOAT"; na.inputs["Name"].default_value = "rad"
    ng.links.new(gi.outputs[0], m2p.inputs["Mesh"])
    if streak:
        length, eul = streak
        ng.links.new(na.outputs["Attribute"], m2p.inputs["Radius"])
        cyl = ng.nodes.new("GeometryNodeMeshCylinder"); cyl.inputs["Vertices"].default_value = 6
        cyl.inputs["Radius"].default_value = 1.0; cyl.inputs["Depth"].default_value = 1.0
        smc = ng.nodes.new("GeometryNodeSetMaterial"); smc.inputs["Material"].default_value = material
        ng.links.new(cyl.outputs["Mesh"], smc.inputs["Geometry"])
        iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
        ng.links.new(m2p.outputs["Points"], iop.inputs["Points"]); ng.links.new(smc.outputs["Geometry"], iop.inputs["Instance"])
        ln = ng.nodes.new("ShaderNodeMath"); ln.operation = "MULTIPLY"; ln.inputs[1].default_value = float(length)
        ng.links.new(na.outputs["Attribute"], ln.inputs[0])
        cx = ng.nodes.new("ShaderNodeCombineXYZ"); ng.links.new(ln.outputs[0], cx.inputs[2])
        ng.links.new(na.outputs["Attribute"], cx.inputs[0]); ng.links.new(na.outputs["Attribute"], cx.inputs[1])
        ng.links.new(cx.outputs[0], iop.inputs["Scale"])
        try: iop.inputs["Rotation"].default_value = tuple(eul)
        except Exception as e: print("streak rotation:", e, flush=True)
        ng.links.new(iop.outputs["Instances"], go.inputs[0])
    else:
        sm = ng.nodes.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = material
        ng.links.new(na.outputs["Attribute"], m2p.inputs["Radius"])
        ng.links.new(m2p.outputs["Points"], sm.inputs["Geometry"]); ng.links.new(sm.outputs["Geometry"], go.inputs[0])
    ob.modifiers.new("pts", "NODES").node_group = ng
    no_motion_blur(ob)
    return ob


# ------------------------------------------------------------------ render
def setup_cycles(sc, O, samples=96, motion_blur=False, look="AgX - Medium High Contrast", transparent=False):
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    gpu = None if O.preview else O.gpu
    if gpu:
        cp = bpy.context.preferences.addons["cycles"].preferences
        for typ in dict.fromkeys([gpu.upper(), "OPTIX", "CUDA"]):
            try:
                cp.compute_device_type = typ; cp.refresh_devices()
                if any(d.type == typ for d in cp.devices): break
            except Exception as e:
                print("gpu backend", typ, "unavailable:", e, flush=True)
        for d in cp.devices: d.use = d.type == cp.compute_device_type
        print("GPU devices:", cp.compute_device_type, [d.name for d in cp.devices if d.use], flush=True)
        if any(d.use for d in cp.devices):
            sc.cycles.device = "GPU"
            try: sc.cycles.denoising_use_gpu = True
            except Exception: pass
    sc.render.use_persistent_data = True
    sc.cycles.samples = samples; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 2
    sc.cycles.volume_bounces = 0; sc.cycles.sample_clamp_indirect = 8.0
    try: sc.cycles.transparent_max_bounces = 16
    except Exception: pass
    sc.render.use_motion_blur = bool(motion_blur) and not O.preview; sc.render.motion_blur_shutter = 0.45
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
    sc.render.film_transparent = transparent
    sc.view_settings.view_transform = "AgX"
    try: sc.view_settings.look = look
    except Exception: pass
    sc.view_settings.exposure = O.ev
    if transparent:
        sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    else:
        sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.color_mode = "RGB"; sc.render.image_settings.quality = 95


def ext(sc):
    return ".png" if sc.render.image_settings.file_format == "PNG" else ".jpg"


def render_frames(sc, out, frames, budget_min=0.0, prefix="f_"):
    """renders the frames; with a budget, stops (exit 3) as soon as the projected total is over it"""
    os.makedirs(out, exist_ok=True)
    times, n = [], len(frames)
    for i, f in enumerate(frames):
        t1 = time.time()
        sc.frame_set(f); sc.render.filepath = os.path.join(os.path.abspath(out), f"{prefix}{f:04d}")
        bpy.ops.render.render(write_still=True)
        times.append(time.time() - t1)
        print(f"rendered {f} {times[-1]:.1f}s", flush=True)
        if budget_min and i >= 2:
            per = float(np.median(times[1:])) if i < 8 else float(np.median(times[-6:]))
            proj = (time.time() - T_PROC) + 1.08 * per * (n - i - 1)
            if i == 2 or i % 30 == 0: print(f"budget: projected {proj / 60:.1f} of {budget_min:.0f} min", flush=True)
            if proj > budget_min * 60:
                print(f"BUDGET EXCEEDED: projected {proj / 60:.1f} min > {budget_min:.0f} min after {i + 1} frames "
                      f"({per:.1f} s per frame)", flush=True)
                sys.stdout.flush(); os._exit(3)
    return times


# ------------------------------------------------------------------ preview (checks + exposure)
def cam_rays(sc, cam, nx=NX, ny=NY, box=None):
    """origin + world directions through the centres of an nx x ny grid of image cells (row 0 = top); box = (u0, v0, u1,
    v1) restricts the grid to that part of the frame (u from the left, v from the top, 0..1)"""
    mw = cam.matrix_world
    fr = list(cam.data.view_frame(scene=sc))
    tr = max(fr, key=lambda v: v.x + v.y); bl = min(fr, key=lambda v: v.x + v.y)
    tl = min(fr, key=lambda v: v.x - v.y); br = max(fr, key=lambda v: v.x - v.y)
    o = mw.translation.copy()
    tr, br, bl, tl = (mw @ v for v in (tr, br, bl, tl))
    u0, v0, u1, v1 = box or (0.0, 0.0, 1.0, 1.0)
    rows = []
    for j in range(ny):
        v = v0 + (j + 0.5) / ny * (v1 - v0)
        a, b = tl.lerp(bl, v), tr.lerp(br, v)
        rows.append([(a.lerp(b, u0 + (i + 0.5) / nx * (u1 - u0)) - o).normalized() for i in range(nx)])
    return o, rows


def grid_mask(grid, codes, h, w):
    g = np.array([[c in codes for c in row] for row in grid], bool)
    return g[(np.arange(h) * g.shape[0]) // h][:, (np.arange(w) * g.shape[1]) // w]


def image_luma(path, grid=None, codes=None):
    img = bpy.data.images.load(path, check_existing=False)
    try: img.colorspace_settings.name = "Non-Color"
    except Exception: pass
    w, h = img.size
    px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px); bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]
    y = 0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2]
    if grid is not None:
        m = grid_mask(grid, codes, h, w)
        if m.sum() > 0.02 * m.size: return float(y[m].mean())
    return float(y.mean())


def preview_run(sc, O, n_frames, classify, subject, target, tol, ev_range=(-1.0, 1.5), stats=None, errors=None,
                warnings=None, dark_max=0.15, every=15, after_checks=None, fallback_subject=None, key=None, calibrate=True,
                calm=None):
    key = sorted(key) if key else key_frames(n_frames)
    sampled = sorted(set(key) | set(range(1, n_frames + 1, every)) | {n_frames})
    grids, counts = {}, {}
    t0 = time.time()
    for f in sampled:
        sc.frame_set(f); g = classify(f)
        c = {}
        for row in g:
            for ch in row: c[ch] = c.get(ch, 0) + 1
        counts[str(f)] = c
        if f in key: grids[str(f)] = g
    print(f"check grid: {len(sampled)} frames in {time.time() - t0:.0f}s", flush=True)
    st = stats(grids, counts) if callable(stats) else (stats or {})
    if after_checks: after_checks()
    gc.collect()

    def subj(f):
        g = grids[str(f)]
        n = sum(sum(ch in subject for ch in row) for row in g)
        return subject if n >= 0.08 * NX * NY or not fallback_subject else fallback_subject

    tmp = os.path.join(O.out, "_calib"); os.makedirs(tmp, exist_ok=True)

    def share(f, codes): return sum(sum(ch in codes for ch in row) for row in grids[str(f)]) / (NX * NY)

    good = [f for f in key if share(f, subject) >= 0.08] or [f for f in key if fallback_subject and share(f, fallback_subject) >= 0.08]
    if calm: good = [f for f in good if f in calm] or good           # exposure from the steady scene, not from fire or glow
    cal = [good[round(i * (len(good) - 1) / 2)] for i in range(3)] if len(good) >= 3 else good
    cal = sorted(set(cal))
    if not cal: calibrate = False                                      # nothing on screen depends on the exposure
    base = sc.cycles.samples
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 180, 100
    sc.cycles.samples = 8
    ev, hist = float(O.ev), []
    for it in range(3 if calibrate else 0):
        sc.view_settings.exposure = ev
        ls = []
        for f in cal:
            sc.frame_set(f); sc.render.filepath = os.path.join(tmp, f"c{it}_{f:04d}")
            bpy.ops.render.render(write_still=True)
            ls.append(image_luma(sc.render.filepath + ext(sc), grids[str(f)], subj(f)))
        lum = float(np.mean(ls)); hist.append([round(ev, 3), round(lum, 4)])
        print(f"exposure {it}: ev {ev:+.2f} -> luma {lum:.3f} (target {target:.3f})", flush=True)
        if abs(lum - target) <= 0.5 * tol or it == 2: break
        if len(hist) >= 2 and abs(hist[-1][1] - hist[-2][1]) > 1e-3:
            (e0, l0), (e1, l1) = hist[-2], hist[-1]
            nxt = e1 + (target - l1) * (e1 - e0) / (l1 - l0)
        else:
            nxt = ev + 2.2 * math.log2(max(target, 0.02) / max(lum, 0.02)) * 0.85
        nxt = float(np.clip(nxt, *ev_range))
        if abs(nxt - ev) < 0.02: break
        ev = nxt
    ev = min(hist, key=lambda h: abs(h[1] - target))[0] if hist else ev
    sc.view_settings.exposure = ev
    sc.render.resolution_x, sc.render.resolution_y = 640, 360
    sc.cycles.samples = min(base, 16)
    t1 = time.time()
    for f in key:
        sc.frame_set(f); sc.render.filepath = os.path.join(O.out, f"p_{f:04d}")
        bpy.ops.render.render(write_still=True)
    cpu = (time.time() - t1) / len(key)
    shutil.rmtree(tmp, ignore_errors=True)
    json.dump({"frames": n_frames, "key_frames": key, "ext": ext(sc), "grids": grids, "counts": counts,
               "subject": "".join(subject), "subject_fallback": "".join(fallback_subject or ""),
               "luma_target": target, "luma_tol": tol, "dark_max": dark_max, "ev": ev, "calibration": hist,
               "stats": st, "errors": errors or [], "warnings": warnings or [], "cpu_s_per_frame": round(cpu, 1),
               "calm_frames": sorted(calm) if calm else [],
               "build_s": round(t0 - T_PROC, 1)}, open(os.path.join(O.out, "check.json"), "w"))
    print(f"preview written: ev {ev:+.2f}, {cpu:.1f} s per key frame (CPU)", flush=True)
