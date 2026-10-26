"""Shared Blender helpers of the workshop templates (Blender 4.5, Cycles)."""
import bpy, json, math, os, struct, sys
import numpy as np
from mathutils import Vector


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    get = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    P = json.load(open(get("--params")))
    return P, get, ("--labels-only" in a)


def reset(fps=30):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = fps
    return sc


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


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


def put(obj, m):
    obj.data.materials.clear(); obj.data.materials.append(m)
    return obj


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


def points_object(name, verts, radii, material, cache=None):
    """vertex cloud rendered as spheres of per-point radius (snow, rain, embers, dust)"""
    sc = bpy.context.scene
    me = bpy.data.meshes.new(name); me.from_pydata(np.asarray(verts).tolist(), [], []); me.update()
    ra = me.attributes.new("rad", "FLOAT", "POINT"); ra.data.foreach_set("value", np.asarray(radii, np.float32))
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    if cache: use_cache(ob, cache)
    ng = bpy.data.node_groups.new(name + "_pts", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput"); go = ng.nodes.new("NodeGroupOutput")
    m2p = ng.nodes.new("GeometryNodeMeshToPoints"); m2p.mode = "VERTICES"
    na = ng.nodes.new("GeometryNodeInputNamedAttribute"); na.data_type = "FLOAT"; na.inputs["Name"].default_value = "rad"
    sm = ng.nodes.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = material
    ng.links.new(gi.outputs[0], m2p.inputs["Mesh"]); ng.links.new(na.outputs["Attribute"], m2p.inputs["Radius"])
    ng.links.new(m2p.outputs["Points"], sm.inputs["Geometry"]); ng.links.new(sm.outputs["Geometry"], go.inputs[0])
    ob.modifiers.new("pts", "NODES").node_group = ng
    return ob


def setup_cycles(sc, gpu, samples=96, motion_blur=False, look="AgX - Medium High Contrast", transparent=False):
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
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
    sc.render.use_motion_blur = motion_blur; sc.render.motion_blur_shutter = 0.45
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
    sc.render.film_transparent = transparent
    sc.view_settings.view_transform = "AgX"
    try: sc.view_settings.look = look
    except Exception: pass
    if transparent:
        sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    else:
        sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.color_mode = "RGB"; sc.render.image_settings.quality = 95


def render_frames(sc, out, start, end):
    os.makedirs(out, exist_ok=True)
    for f in range(start, end + 1):
        sc.frame_set(f); sc.render.filepath = os.path.join(os.path.abspath(out), f"f_{f:04d}")
        bpy.ops.render.render(write_still=True)
        print("rendered", f, flush=True)
