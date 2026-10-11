# SPDX-License-Identifier: GPL-3.0-only
"""Resident Duke layout editor for Blender (4.x).

Run with edit_layout.bat (or: blender --python tools/blender_editor.py). It
loads build/editor/scene.json (written by tools/editor_export.py during every
build) and creates:
  * E1L1 with Duke's own textures (collection "Level");
  * every generated fixed camera shot (collection "Cameras"), one camera per
    shot, named "Cam <n>"; select one and press Numpad 0 to look through it;
  * the RE item box, typewriter and ink ribbon (collection "Stations");
  * a reference Jill at the start ("Jill"): scale her to change jill_scale.
The "Resident Duke" tab in the 3D view sidebar (press N) saves your changes
into tools/e1l1-layout.json and can rebuild the game package.

Units: one Blender unit = 512 Build xy = 8192 Build z; Blender Y = Build -y.
"""
import json
import math
import os
import subprocess
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE_DIR = os.path.normpath(os.path.join(HERE, '..', 'build', 'editor'))
XY, ZS = 512.0, 8192.0
GAME_HFOV = 2 * math.atan(math.tan(math.radians(45)) * (16 / 9) / (4 / 3))   # EDuke32 Hor+ at 16:9


def to_build(v):
    return round(v.x * XY), round(-v.y * XY), round(-v.z * ZS)


def heading_to_ang(theta):
    return round(-theta * 1024 / math.pi) & 2047


def ang_to_heading(ang):
    return -ang * math.pi / 1024


# ---------------------------------------------------------------------------
# Scene construction
# ---------------------------------------------------------------------------
def collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def tile_material(tile, cache):
    if tile in cache:
        return cache[tile]
    mat = bpy.data.materials.new('tile %d' % tile)
    mat.use_nodes = True
    path = os.path.join(SCENE_DIR, 'tiles', '%d.png' % tile)
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if os.path.exists(path) and bsdf:
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(path, check_existing=True)
        tex.interpolation = 'Closest'
        mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        mat.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        bsdf.inputs['Roughness'].default_value = 1.0
        mat.blend_method = 'CLIP' if hasattr(mat, 'blend_method') else None
    cache[tile] = mat
    return mat


def build_level(scene, col):
    mesh = bpy.data.meshes.new('E1L1')
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    mats = {}; mat_index = {}

    def mat_slot(tile):
        if tile not in mat_index:
            mat_index[tile] = len(mat_index); tile_material(tile, mats)
        return mat_index[tile]

    for q in scene['walls']:
        verts = [bm.verts.new(v) for v in q['v']]
        try:
            f = bm.faces.new(verts)
        except ValueError:
            continue
        f.material_index = mat_slot(q['tile'])
        for loop, t in zip(f.loops, q['uv']):
            loop[uv].uv = t
    for p in scene['planes']:
        edges = []; uvmap = {}
        for loop, uvs in zip(p['loops'], p['uv']):
            vs = [bm.verts.new(v) for v in loop]
            for v, t in zip(vs, uvs):
                uvmap[v] = t
            for i in range(len(vs)):
                edges.append(bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
        res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
        for f in [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)]:
            f.material_index = mat_slot(p['tile'])
            for loop in f.loops:
                loop[uv].uv = uvmap.get(loop.vert, (0, 0))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.to_mesh(mesh); bm.free()
    for tile in sorted(mat_index, key=mat_index.get):
        mesh.materials.append(mats[tile])
    obj = bpy.data.objects.new('E1L1', mesh)
    col.objects.link(obj)
    obj.hide_select = True
    return obj


def make_camera(col, c):
    data = bpy.data.cameras.new('Cam %d' % c['index'])
    data.sensor_fit = 'HORIZONTAL'; data.angle = GAME_HFOV
    data.clip_start = 0.05; data.clip_end = 500
    data.display_size = 0.6
    obj = bpy.data.objects.new('Cam %d' % c['index'], data)
    col.objects.link(obj)
    obj.location = c['pos']
    heading = ang_to_heading(c['ang'])
    down = math.atan((100 - c['horiz']) / 128)       # Build horiz: 128 per unit tangent
    obj.rotation_euler = (math.radians(90) - down, 0, heading - math.radians(90))
    obj['shot_index'] = c['index']
    obj['zone_keys'] = ','.join(c['keys'])
    obj['orig'] = list(obj.location) + list(obj.rotation_euler)
    obj.hide_render = False
    return obj


def make_station(col, st, scene):
    k = scene['jill_scale']
    if st['image']:
        img = bpy.data.images.load(os.path.join(SCENE_DIR, st['image']), check_existing=True)
        rx, ry = scene['station_repeat'][st['kind']]
        w = img.size[0] * rx * k / 4 / XY; h = img.size[1] * ry * k / 4 / XY   # Build sprite size
        mesh = bpy.data.meshes.new(st['kind'])
        mesh.from_pydata([(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, 0, h), (-w / 2, 0, h)], [], [(0, 1, 2, 3)])
        uvl = mesh.uv_layers.new(name='UVMap')
        for i, t in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            uvl.data[i].uv = t
        mat = bpy.data.materials.new(st['kind'])
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes['Principled BSDF']
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Closest'
        mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        mat.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        mesh.materials.append(mat)
        obj = bpy.data.objects.new(st['kind'], mesh)
    else:
        obj = bpy.data.objects.new(st['kind'], None)
        obj.empty_display_type = 'CUBE'; obj.empty_display_size = 0.15 * k
    col.objects.link(obj)
    obj.location = st['pos']
    obj.rotation_euler = (0, 0, ang_to_heading(st['ang']) + math.radians(90))
    obj['station'] = st['kind']
    obj.lock_rotation = (True, True, False)
    return obj


def make_jill(scene):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=os.path.join(SCENE_DIR, 'jill.obj'), forward_axis='Y', up_axis='Z')
    parts = [o for o in bpy.data.objects if o not in before]
    for o in parts:
        o.select_set(True)
    if len(parts) > 1:
        bpy.context.view_layer.objects.active = parts[0]; bpy.ops.object.join()
    jill = bpy.context.view_layer.objects.active or parts[0]
    jill.name = 'Jill'
    for mat in jill.data.materials:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                node.interpolation = 'Closest'
    jill.location = scene['start']
    jill.rotation_euler = (0, 0, ang_to_heading(scene['start_ang']))
    s = scene['jill_scale']; jill.scale = (s, s, s)
    jill['note'] = 'Scale uniformly to change jill_scale; move her to preview shots.'
    return jill


def build():
    with open(os.path.join(SCENE_DIR, 'scene.json')) as f:
        scene = json.load(f)
    # Start from an empty scene.
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    level = collection('Level'); cams = collection('Cameras'); stations = collection('Stations')
    build_level(scene, level)
    for c in scene['cameras']:
        make_camera(cams, c)
    for st in scene['stations']:
        make_station(stations, st, scene)
    jill = make_jill(scene)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc['resident_duke_layout'] = scene['layout']; sc['resident_duke_root'] = scene['root']
    sc['jill_base_scale'] = scene['jill_scale']
    sc.rd_jill_scale = scene['jill_scale']
    # Pick the shot nearest Jill's start as the active camera.
    best = min((o for o in cams.objects), key=lambda o: (o.location - jill.location).length)
    sc.camera = best
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'; space.shading.color_type = 'TEXTURE'
                    space.clip_start = 0.05; space.clip_end = 1000
                    space.region_3d.view_perspective = 'CAMERA'


# ---------------------------------------------------------------------------
# Saving back to tools/e1l1-layout.json
# ---------------------------------------------------------------------------
def save_layout():
    sc = bpy.context.scene
    path = sc['resident_duke_layout']
    layout = {}
    if os.path.exists(path):
        with open(path) as f:
            layout = json.load(f)
    jill = bpy.data.objects.get('Jill')
    if jill:
        layout['jill_scale'] = round(jill.scale.x, 3)
    stations = layout.setdefault('stations', {})
    for o in bpy.data.objects:
        if 'station' in o:
            x, y, _ = to_build(o.location)
            stations[o['station']] = dict(x=x, y=y, ang=heading_to_ang(o.rotation_euler.z - math.radians(90)))
    cams = layout.setdefault('cameras', {})
    changed = 0
    for o in bpy.data.objects:
        if 'shot_index' not in o:
            continue
        cur = list(o.location) + list(o.rotation_euler)
        if max(abs(a - b) for a, b in zip(cur, o['orig'])) < 1e-4:
            continue
        x, y, z = to_build(o.location)
        forward = o.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        lx, ly, lz = to_build(o.location + forward * 2)
        for key in str(o['zone_keys']).split(','):
            if key:
                cams[key] = dict(x=x, y=y, z=z, look=[lx, ly, lz]); changed += 1
    with open(path, 'w') as f:
        json.dump(layout, f, indent=2); f.write('\n')
    return changed


class RD_OT_save(bpy.types.Operator):
    bl_idname = 'resident_duke.save_layout'
    bl_label = 'Save layout'
    bl_description = 'Write Jill scale, station positions and moved cameras to tools/e1l1-layout.json'

    def execute(self, context):
        n = save_layout()
        self.report({'INFO'}, 'Saved layout (%d camera zone overrides).' % n)
        return {'FINISHED'}


class RD_OT_rebuild(bpy.types.Operator):
    bl_idname = 'resident_duke.rebuild'
    bl_label = 'Save and rebuild game'
    bl_description = 'Save the layout, then run setup.py --build-only in a console window'

    def execute(self, context):
        save_layout()
        root = context.scene['resident_duke_root']
        flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
        # The project's own virtual environment (made by setup) has NumPy/Pillow.
        venv = os.path.join(root, '.local', 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python.exe' if os.name == 'nt' else 'python')
        py = [venv] if os.path.exists(venv) else (['py', '-3'] if os.name == 'nt' else ['python3'])
        subprocess.Popen(py + [os.path.join(root, 'setup.py'), '--build-only', '--skip-install'], cwd=root, creationflags=flags)
        self.report({'INFO'}, 'Rebuilding in a console window; restart Blender editing afterwards to see new cameras.')
        return {'FINISHED'}


class RD_OT_look(bpy.types.Operator):
    bl_idname = 'resident_duke.look'
    bl_label = 'Look through selected camera'

    def execute(self, context):
        o = context.active_object
        if not o or o.type != 'CAMERA':
            self.report({'WARNING'}, 'Select a camera first.'); return {'CANCELLED'}
        context.scene.camera = o
        context.space_data.region_3d.view_perspective = 'CAMERA'
        return {'FINISHED'}


class RD_OT_nearest(bpy.types.Operator):
    bl_idname = 'resident_duke.nearest'
    bl_label = 'Camera nearest Jill'
    bl_description = 'Select and look through the generated shot closest to the Jill reference'

    def execute(self, context):
        jill = bpy.data.objects.get('Jill')
        cams = [o for o in bpy.data.objects if 'shot_index' in o]
        if not jill or not cams:
            return {'CANCELLED'}
        best = min(cams, key=lambda o: (o.location - jill.location).length)
        for o in context.selected_objects:
            o.select_set(False)
        best.select_set(True); context.view_layer.objects.active = best
        context.scene.camera = best
        context.space_data.region_3d.view_perspective = 'CAMERA'
        return {'FINISHED'}


class RD_PT_panel(bpy.types.Panel):
    bl_label = 'Resident Duke'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Resident Duke'

    def draw(self, context):
        col = self.layout.column(align=True)
        jill = bpy.data.objects.get('Jill')
        if jill:
            col.prop(context.scene, 'rd_jill_scale')
        col.operator('resident_duke.nearest')
        col.operator('resident_duke.look')
        col.separator()
        col.operator('resident_duke.save_layout')
        col.operator('resident_duke.rebuild')
        col.separator()
        col.label(text='Move/rotate cameras and stations,')
        col.label(text='scale Jill uniformly (S), then save.')


CLASSES = (RD_OT_save, RD_OT_rebuild, RD_OT_look, RD_OT_nearest, RD_PT_panel)


def _jill_scale_update(self, context):
    jill = bpy.data.objects.get('Jill')
    if jill:
        jill.scale = (self.rd_jill_scale,) * 3


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.rd_jill_scale = bpy.props.FloatProperty(
        name='Jill scale', description='Jill, her movement and RE objects scale together in game',
        default=1.0, min=0.5, max=3.0, update=_jill_scale_update)


if __name__ == '__main__':
    register()
    build()
