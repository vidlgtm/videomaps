"""Project-specific Blender clip: four volcanic islands emerge from a Pacific relief table.
Contract: blender -b -P this.py -- --out DIR --start 1 --end N --gpu OPTIX
"""
import argparse, math, os, sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True); ap.add_argument('--start', type=int, default=1); ap.add_argument('--end', type=int, default=240); ap.add_argument('--gpu', default='OPTIX')
a = ap.parse_args(argv)

for ob in list(bpy.data.objects): bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.render.resolution_x = 1920; sc.render.resolution_y = 1080; sc.render.resolution_percentage = 100
sc.render.fps = 30; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 95
sc.render.film_transparent = False
sc.world.color = (0.004, 0.008, 0.014)
sc.view_settings.look = 'AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [x.identifier for x in sc.view_settings.bl_rna.properties['look'].enum_items] else 'None'
sc.cycles.samples = 72; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.025; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 4
try:
    pref = bpy.context.preferences.addons['cycles'].preferences; pref.compute_device_type = a.gpu; pref.refresh_devices()
    for d in pref.devices: d.use = d.type == a.gpu
    if any(d.use for d in pref.devices): sc.cycles.device = 'GPU'
except Exception: pass

def mat(name, color, metallic=0.0, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value = (*color, 1); p.inputs['Metallic'].default_value = metallic; p.inputs['Roughness'].default_value = rough
    return m
wood = mat('charcoal wood', (0.035, 0.022, 0.014), 0.05, 0.32)
water = mat('black blue water', (0.006, 0.045, 0.078), 0.6, 0.18)
rock = mat('volcanic basalt', (0.045, 0.050, 0.052), 0.05, 0.78)
gold = mat('aged brass', (0.43, 0.27, 0.075), 0.82, 0.24)
cream = mat('map inlay', (0.42, 0.34, 0.20), 0.15, 0.5)

def cube(name, loc, scale, material, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc); ob=bpy.context.object; ob.name=name; ob.scale=scale; bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel: mod=ob.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=3
    ob.data.materials.append(material); return ob

def cyl(name, loc, radius, depth, material, vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc); ob=bpy.context.object; ob.name=name; ob.data.materials.append(material); return ob

cube('table', (0,0,-0.42), (6.8,4.4,0.35), wood, 0.16)
cube('inlay', (0,0,-0.04), (6.3,3.9,0.08), cream, 0.10)
bpy.ops.mesh.primitive_plane_add(size=12, location=(0,0,0.14)); sea=bpy.context.object; sea.name='receding Pacific water'; sea.data.materials.append(water)
sea.location.z=0.26; sea.keyframe_insert('location', frame=1); sea.location.z=-0.16; sea.keyframe_insert('location', frame=90); sea.keyframe_insert('location', frame=190); sea.location.z=0.18; sea.keyframe_insert('location', frame=a.end)
for fc in sea.animation_data.action.fcurves:
    for k in fc.keyframe_points: k.interpolation='BEZIER'

# Four basalt island silhouettes, arranged along a gentle northeast arc.
for i,(x,y,s) in enumerate([(-1.8,-0.8,0.42),(-0.7,-0.18,0.54),(0.55,0.40,0.48),(1.75,1.05,0.64)]):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1, location=(x,y,0.02+s*0.20)); ob=bpy.context.object; ob.name=f'basalt island {i+1}'; ob.scale=(s*1.8,s*0.82,s*0.95); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); ob.data.materials.append(rock)
    ob.rotation_euler=(0.15*i,0.08*i,0.2*i)
# Brass compass: the needle rotates, then locks while water has receded.
cx,cy=-3.9,-2.15
cyl('compass rim', (cx,cy,0.16), 0.78, 0.16, gold)
cyl('compass face', (cx,cy,0.25), 0.64, 0.04, cream)
needle=cube('compass needle', (cx,cy,0.31), (0.55,0.075,0.045), gold, 0.03)
hub=cyl('compass hub', (cx,cy,0.37), 0.12, 0.08, gold)
needle.rotation_euler[2]=math.radians(-55); needle.keyframe_insert('rotation_euler', index=2, frame=1)
needle.rotation_euler[2]=math.radians(170); needle.keyframe_insert('rotation_euler', index=2, frame=72)
needle.rotation_euler[2]=math.radians(38); needle.keyframe_insert('rotation_euler', index=2, frame=118)
needle.keyframe_insert('rotation_euler', index=2, frame=a.end)
for fc in needle.animation_data.action.fcurves:
    for k in fc.keyframe_points: k.interpolation='BEZIER'

# Camera, tracked through the relief table.
cam_data=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',cam_data); sc.collection.objects.link(cam); sc.camera=cam; cam.data.lens=48
focus=bpy.data.objects.new('Focus',None); sc.collection.objects.link(focus); focus.location=(0,0,0); con=cam.constraints.new('TRACK_TO'); con.target=focus; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'
for f,loc,tar in [(1,(0,-10.0,8.0),(-0.2,0,0)),(95,(-1.2,-8.2,6.2),(0,0.1,0)),(a.end,(1.8,-9.0,7.0),(0.4,0.3,0))]:
    cam.location=loc; focus.location=tar; cam.keyframe_insert('location',frame=f); focus.keyframe_insert('location',frame=f)
for ob in (cam,focus):
    for fc in ob.animation_data.action.fcurves:
        for k in fc.keyframe_points: k.interpolation='BEZIER'; k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'

# Warm upper-left key and soft blue rim.
def area(name, loc, energy, size, color):
    d=bpy.data.lights.new(name,'AREA'); d.energy=energy; d.shape='DISK'; d.size=size; d.color=color; o=bpy.data.objects.new(name,d); sc.collection.objects.link(o); o.location=loc; o.rotation_euler=(math.radians(24),0,math.radians(25)); return o
area('warm key',(-5,-5,9),1350,5.5,(1.0,0.72,0.42)); area('cool rim',(5,4,7),850,4.0,(0.32,0.55,1.0)); area('fill',(0,-1,5),500,3.0,(0.9,0.88,0.78))
os.makedirs(a.out,exist_ok=True)
for f in range(a.start,a.end+1):
    sc.frame_set(f); sc.render.filepath=os.path.join(a.out,f'f_{f:04d}'); bpy.ops.render.render(write_still=True); print('rendered',f,flush=True)
