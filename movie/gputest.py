import bpy, time
bpy.ops.wm.read_factory_settings(use_empty=True)
prefs = bpy.context.preferences.addons["cycles"].preferences
for t in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = t; prefs.get_devices(); break
    except Exception as e: print("no", t, e)
for d in prefs.devices: d.use = d.type != "CPU"; print("device", d.name, d.type, d.use)
sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "GPU"; sc.cycles.samples = 32; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1920, 804
bpy.ops.mesh.primitive_cube_add(size=2); bpy.ops.object.light_add(type="SUN", location=(3,3,5))
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); cam.location=(6,-6,4); cam.rotation_euler=(1.0,0,0.785); sc.camera=cam
sc.render.filepath = "/tmp/gputest.png"; t=time.time(); bpy.ops.render.render(write_still=True); print("render s", round(time.time()-t,2))
