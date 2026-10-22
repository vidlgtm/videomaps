"""Render TripoSR meshes as map icons (clean transparent PNG, object only), 4 azimuths each.
usage: blender -b -P icons.py -- <triposr_out_dir> <names_csv> <out_dir>"""
import bpy, sys, os, math
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
IN, NAMES, OUT = a[0], a[1].split(","), a[2]
os.makedirs(OUT, exist_ok=True)


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 128
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 768
    sc.view_settings.view_transform = "AgX"
    try: sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.85, 0.88, 0.95, 1); bg.inputs[1].default_value = 0.55
    return sc


def light(name, loc, power, size, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.energy = power; l.size = size; l.color = color
    o = bpy.data.objects.new(name, l); bpy.context.scene.collection.objects.link(o); o.location = loc
    d = Vector((0, 0, 0.6)) - o.location; o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


for i, name in enumerate(NAMES):
    path = os.path.join(IN, str(i), "mesh.obj")
    if not os.path.exists(path):
        print("missing", path); continue
    sc = setup_scene()
    bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
    obs = [o for o in sc.objects if o.type == "MESH"]
    bpy.context.view_layer.objects.active = obs[0]
    for o in obs: o.select_set(True)
    if len(obs) > 1: bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = ob.data
    xs = [v.co for v in me.vertices]
    mn = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    mx = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    size = max(mx - mn); ctr = (mn + mx) / 2
    for v in me.vertices:
        v.co = (v.co - Vector((ctr.x, ctr.y, mn.z))) * (2.0 / size)
    bpy.ops.object.shade_smooth()
    mat = bpy.data.materials.new("M"); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.5
    if me.color_attributes:
        at = nt.nodes.new("ShaderNodeVertexColor"); at.layer_name = me.color_attributes[0].name
        hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = 1.15; hsv.inputs["Value"].default_value = 1.05
        nt.links.new(at.outputs["Color"], hsv.inputs["Color"]); nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
    me.materials.clear(); me.materials.append(mat)
    # v3: no baked ground shadow (it was clipped by the frame -> rectangular shadow); Remotion adds a soft contact shadow
    light("key", (3.5, -3.0, 5.0), 900, 3.0, (1.0, 0.96, 0.9))
    light("fill", (-4.0, -2.0, 2.5), 250, 4.0, (0.85, 0.9, 1.0))
    light("rim", (-1.0, 4.5, 3.5), 450, 2.0)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 70
    hgt = max(v.co.z for v in me.vertices)
    for az in (0, 90, 180, 270):
        el, dist = math.radians(32), 7.2
        A = math.radians(az - 90)
        cam.location = (dist * math.cos(el) * math.cos(A), dist * math.cos(el) * math.sin(A), dist * math.sin(el) + hgt * 0.35)
        d = Vector((0, 0, hgt * 0.45)) - cam.location; cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, f"{name}_a{az}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", name, az, flush=True)
