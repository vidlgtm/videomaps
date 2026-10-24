"""Project-specific Blender clip: an evenly balanced brass scale carrying four basalt island markers."""
import argparse, math, os, sys
import bpy

argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); ap.add_argument('--start',type=int,default=1); ap.add_argument('--end',type=int,default=270); ap.add_argument('--gpu',default='OPTIX'); a=ap.parse_args(argv)
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob,do_unlink=True)
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.render.resolution_x=1920; sc.render.resolution_y=1080; sc.render.resolution_percentage=100; sc.render.fps=30; sc.render.image_settings.file_format='JPEG'; sc.render.image_settings.quality=95
sc.world.color=(0.003,0.006,0.012); sc.cycles.samples=72; sc.cycles.use_adaptive_sampling=True; sc.cycles.adaptive_threshold=0.025; sc.cycles.use_denoising=True; sc.cycles.max_bounces=4
try:
 p=bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type=a.gpu; p.refresh_devices(); [setattr(d,'use',d.type==a.gpu) for d in p.devices]; sc.cycles.device='GPU' if any(d.use for d in p.devices) else 'CPU'
except Exception: pass

def mat(name,c,metal=0,rough=.5):
 m=bpy.data.materials.new(name); m.use_nodes=True; q=m.node_tree.nodes.get('Principled BSDF'); q.inputs['Base Color'].default_value=(*c,1); q.inputs['Metallic'].default_value=metal; q.inputs['Roughness'].default_value=rough; return m
brass=mat('brass',(0.43,.26,.06),.86,.22); basalt=mat('basalt',(.04,.045,.05),.05,.78); paper=mat('parchment',(.52,.40,.22),.05,.55); floor=mat('ink stone',(.008,.013,.020),.25,.28)
def cube(n,loc,scale,m,bevel=0):
 bpy.ops.mesh.primitive_cube_add(location=loc); o=bpy.context.object; o.name=n; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(m)
 if bevel: z=o.modifiers.new('edges','BEVEL'); z.width=bevel; z.segments=3
 return o
def cyl(n,loc,r,d,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r,depth=d,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(m); return o
bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,-1.25)); bpy.context.object.data.materials.append(floor)
cyl('pedestal',(0,0,-.65),.62,1.2,brass); cyl('foot',(0,0,-1.15),1.35,.18,brass)
beam=cube('balanced beam',(0,0,.22),(3.2,.13,.12),brass,.06); pivot=cyl('pivot',(0,0,.06),.24,.4,brass); pivot.rotation_euler[0]=math.radians(90)
for f,ang in [(1,-4),(110,4),(190,-1),(a.end,0)]: beam.rotation_euler[1]=math.radians(ang); beam.keyframe_insert('rotation_euler',index=1,frame=f)
for fc in beam.animation_data.action.fcurves:
 for k in fc.keyframe_points: k.interpolation='BEZIER'; k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
# Parchment pans and four volcanic markers. They remain balanced but move with the beam as a single visual argument.
for side in (-1,1):
 x=side*2.75
 pan=cube('parchment pan',(x,0,-.05),(1.05,.72,.06),paper,.05)
 for z in (-.15,.15):
  rod=cube('brass suspension',(x+side*.15,z,.20),(0.025,.025,.58),brass)
  # subtle linked sway
  for f,dy in [(1,0),(120,.05*side),(a.end,0)]: rod.location.y=z+dy; rod.keyframe_insert('location',frame=f)
 for i in range(2):
  bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3,radius=.32,location=(x+side*(.28-.2*i),(-.16+.32*i),.18)); o=bpy.context.object; o.name='island marker'; o.scale=(1.3,.7,.72); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(basalt)
# Compass-like center cap and a visual seal ring.
cyl('center seal',(0,0,.42),.36,.12,brass); cyl('center inlay',(0,0,.49),.23,.02,paper)
camd=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',camd); sc.collection.objects.link(cam); sc.camera=cam; camd.lens=54
focus=bpy.data.objects.new('Focus',None); sc.collection.objects.link(focus); focus.location=(0,0,-.1); tr=cam.constraints.new('TRACK_TO'); tr.target=focus; tr.track_axis='TRACK_NEGATIVE_Z'; tr.up_axis='UP_Y'
for f,loc in [(1,(7,-10,5.4)),(135,(8.4,-7.5,4.5)),(a.end,(6,-9,5.7))]: cam.location=loc; cam.keyframe_insert('location',frame=f)
for fc in cam.animation_data.action.fcurves:
 for k in fc.keyframe_points: k.interpolation='BEZIER'; k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
def light(n,loc,e,size,c):
 d=bpy.data.lights.new(n,'AREA'); d.energy=e; d.shape='DISK'; d.size=size; d.color=c; o=bpy.data.objects.new(n,d); sc.collection.objects.link(o); o.location=loc; o.rotation_euler=(math.radians(22),0,math.radians(30))
light('warm key',(-5,-5,8),1450,5,(1,.68,.38)); light('cool rim',(5,4,7),900,4,(.28,.5,1)); light('fill',(0,-1,5),420,3,(.9,.88,.78))
os.makedirs(a.out,exist_ok=True)
for f in range(a.start,a.end+1): sc.frame_set(f); sc.render.filepath=os.path.join(a.out,f'f_{f:04d}'); bpy.ops.render.render(write_still=True); print('rendered',f,flush=True)
