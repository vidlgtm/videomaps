"""Blender smoke test: procedural relief terrain + water + 3D gold title, Cycles CPU, eased camera dolly."""
import bpy, sys, math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
outp = argv[0] if argv else "/tmp/blender_"

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.engine = 'CYCLES'
scn.cycles.device = 'CPU'
scn.cycles.samples = 24
scn.cycles.use_denoising = True
try:
    scn.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
scn.render.resolution_x, scn.render.resolution_y, scn.render.resolution_percentage = 1920, 1080, 100
scn.frame_start, scn.frame_end = 1, 45
scn.render.fps = 30
scn.render.image_settings.file_format = 'PNG'
scn.render.filepath = outp

# terrain
bpy.ops.mesh.primitive_grid_add(x_subdivisions=280, y_subdivisions=280, size=20)
terrain = bpy.context.active_object
tex = bpy.data.textures.new("hills", type='CLOUDS')
tex.noise_scale = 1.6
tex.noise_depth = 4
mod = terrain.modifiers.new("disp", 'DISPLACE')
mod.texture = tex
mod.strength = 1.6
bpy.ops.object.shade_smooth()
mat = bpy.data.materials.new("terrain"); mat.use_nodes = True
nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = 1.6
ramp = nt.nodes.new("ShaderNodeValToRGB")
nt.links.new(geo.outputs["Position"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
ramp.color_ramp.elements[0].color = (0.20, 0.33, 0.18, 1)
ramp.color_ramp.elements[1].color = (0.93, 0.90, 0.84, 1)
e = ramp.color_ramp.elements.new(0.5); e.color = (0.52, 0.42, 0.28, 1)
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.9
terrain.data.materials.append(mat)

# water
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0.45))
water = bpy.context.active_object
wm = bpy.data.materials.new("water"); wm.use_nodes = True
wb = wm.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.04, 0.16, 0.30, 1)
wb.inputs["Roughness"].default_value = 0.12
water.data.materials.append(wm)

# title
bpy.ops.object.text_add(location=(0, -2.5, 2.9), rotation=(math.radians(78), 0, 0))
txt = bpy.context.active_object
txt.data.body = "VIDEOMAPS"; txt.data.extrude = 0.09; txt.data.align_x = 'CENTER'; txt.data.size = 1.25
tm = bpy.data.materials.new("gold"); tm.use_nodes = True
tb = tm.node_tree.nodes["Principled BSDF"]
tb.inputs["Base Color"].default_value = (0.83, 0.62, 0.22, 1); tb.inputs["Metallic"].default_value = 1.0; tb.inputs["Roughness"].default_value = 0.28
txt.data.materials.append(tm)

# light + sky
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(55), 0, math.radians(35)))
sun = bpy.context.active_object; sun.data.energy = 3.5; sun.data.angle = math.radians(2)
world = bpy.data.worlds.new("w"); scn.world = world; world.use_nodes = True
sky = world.node_tree.nodes.new("ShaderNodeTexSky")
world.node_tree.links.new(sky.outputs["Color"], world.node_tree.nodes["Background"].inputs["Color"])
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

# camera with eased dolly
bpy.ops.object.camera_add(location=(0, -14, 7.5), rotation=(math.radians(64), 0, 0))
cam = bpy.context.active_object; scn.camera = cam
cam.keyframe_insert("location", frame=1)
cam.location = (0, -9, 4.6)
cam.keyframe_insert("location", frame=45)
try:
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
except Exception as ex:
    print("fcurve easing skipped:", ex)

print("BLENDER", bpy.app.version_string, "- rendering", scn.frame_end, "frames")
bpy.ops.render.render(animation=True)
print("BLENDER DONE")
