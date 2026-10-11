#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Export the generated E1L1, its camera shots and RE stations for the Blender
layout editor (tools/blender_editor.py). Written to build/editor/.

Units: one Blender unit = 512 Build xy units = 8192 Build z units; Blender Y
is Build -y and Blender Z is Build -z (Build y points south, z points down).
"""
import json
import struct

import numpy as np
from PIL import Image

from common import ROOT, STAGE, ASSETS, jill_scale, BASE_DOOM_TO_BUILD
from duke_grp import Grp, BuildMap
from duke_art import Art

OUT = ROOT / 'build/editor'
XY, ZS = 512.0, 8192.0


def bl(x, y, z):
    return [round(x / XY, 4), round(-y / XY, 4), round(-z / ZS, 4)]


def loops(m, s):
    """Wall loops of a sector as lists of wall indices (first loop is the outline)."""
    out = []; seen = set()
    for w in m.sector_walls(s):
        if w in seen:
            continue
        loop = []; cur = w
        while cur not in seen:
            seen.add(cur); loop.append(cur); cur = int(m.walls[cur]['point2'])
        out.append(loop)
    return out


def wall_quads(m, art, used):
    quads = []
    for s in range(len(m.sectors) - 1):          # last sector is the hidden viewer scene
        for w in m.sector_walls(s):
            wall = m.walls[w]; (ax, ay), (bx, by) = m.wall_segment(w)
            length = ((bx - ax) ** 2 + (by - ay) ** 2) ** .5
            if not length:
                continue
            f0, f1 = m.floor_z(s, ax, ay), m.floor_z(s, bx, by)
            c0, c1 = m.ceiling_z(s, ax, ay), m.ceiling_z(s, bx, by)
            n = int(wall['nextsector'])
            pieces = []
            if n < 0:
                pieces.append((c0, c1, f0, f1, int(wall['picnum'])))
            else:
                nf0, nf1 = m.floor_z(n, ax, ay), m.floor_z(n, bx, by)
                nc0, nc1 = m.ceiling_z(n, ax, ay), m.ceiling_z(n, bx, by)
                if nf0 < f0 or nf1 < f1:     # neighbour floor higher: lower step
                    pieces.append((nf0, nf1, f0, f1, int(wall['picnum'])))
                sky = int(m.sectors[s]['ceilingstat']) & 1 and int(m.sectors[n]['ceilingstat']) & 1
                if (nc0 > c0 or nc1 > c1) and not sky:   # neighbour ceiling lower: upper wall
                    tile = int(wall['overpicnum']) if int(wall['cstat']) & 2 else int(wall['picnum'])
                    pieces.append((c0, c1, nc0, nc1, int(wall['picnum'])))
            tw, th = art.size(int(wall['picnum']))
            for top0, top1, bot0, bot1, tile in pieces:
                if top0 >= bot0 and top1 >= bot1:
                    continue
                tw, th = art.size(tile); tw = tw or 64; th = th or 64
                u1 = int(wall['xrepeat']) * 8 / tw
                vs = int(wall['yrepeat']) / 2048 / th
                ref = top0
                quads.append(dict(tile=tile, shade=int(wall['shade']), v=[bl(ax, ay, top0), bl(bx, by, top1), bl(bx, by, bot1), bl(ax, ay, bot0)],
                                  uv=[[0, -(top0 - ref) * vs], [u1, -(top1 - ref) * vs], [u1, -(bot1 - ref) * vs], [0, -(bot0 - ref) * vs]]))
                used.add(tile)
    return quads


def planes(m, art, used):
    out = []
    for s in range(len(m.sectors) - 1):
        sec = m.sectors[s]; lp = loops(m, s)
        for which in ('floor', 'ceiling'):
            if which == 'ceiling' and int(sec['ceilingstat']) & 1:
                continue   # parallaxed sky: left open so the editor view is not boxed in
            tile = int(sec[which + 'picnum']); tw, th = art.size(tile); tw = tw or 64; th = th or 64
            zf = m.floor_z if which == 'floor' else m.ceiling_z
            pts = [[bl(*m.wall_segment(w)[0], zf(s, *m.wall_segment(w)[0])) for w in loop] for loop in lp]
            uv = [[[m.wall_segment(w)[0][0] / 16 / tw, -m.wall_segment(w)[0][1] / 16 / th] for w in loop] for loop in lp]
            out.append(dict(sector=s, kind=which, tile=tile, shade=int(sec[which + 'shade']), loops=pts, uv=uv))
            used.add(tile)
    return out


def jill_obj(path):
    """Jill's first armed idle pose (MD3 frame 0) as an OBJ in Blender units at jill_scale 1."""
    b = (STAGE / 'models/jill/jill.md3').read_bytes()
    _, _, _, _, nf, _, ns, _, _, _, os_, _ = struct.unpack_from('<4si64s9i', b, 0)
    unit = BASE_DOOM_TO_BUILD / XY   # Doom-scale model units -> Blender units
    lines = ['# Jill (RE1 CHAR11.EMD, armed idle) for the Resident Duke layout editor', 'mtllib jill.mtl', 'usemtl jill']
    vbase = 1; p = os_
    for _ in range(ns):
        h = struct.unpack_from('<4s64s10i', b, p); _, _, _, nfr, _, nv, nt, ot, _, ost, ox, end = h
        xyz = np.frombuffer(b, '<i2', nv * 4, p + ox).reshape(nv, 4)[:, :3] / 64.0
        st = np.frombuffer(b, '<f4', nv * 2, p + ost).reshape(nv, 2)
        tri = np.frombuffer(b, '<i4', nt * 3, p + ot).reshape(nt, 3)
        for x, y, z in xyz:
            # MD3 x forward / y left / z up -> Blender (Build y south is Blender -y).
            lines.append('v %.4f %.4f %.4f' % (x * unit, y * unit, z * unit))
        for u, v in st:
            lines.append('vt %.5f %.5f' % (u, 1 - v))
        for a, b2, c in tri:
            lines.append('f %d/%d %d/%d %d/%d' % (a + vbase, a + vbase, b2 + vbase, b2 + vbase, c + vbase, c + vbase))
        vbase += nv; p += end
    path.write_text('\n'.join(lines) + '\n')
    (path.parent / 'jill.mtl').write_text('newmtl jill\nmap_Kd jill-skin.png\n')
    (path.parent / 'jill-skin.png').write_bytes((STAGE / 'models/jill/skin.png').read_bytes())


def main():
    OUT.mkdir(parents=True, exist_ok=True); (OUT / 'tiles').mkdir(exist_ok=True)
    grp = Grp(ROOT / 'dependencies/duke3d/duke3d.grp'); art = Art(grp)
    m = BuildMap((STAGE / 'E1L1.MAP').read_bytes())
    used = set()
    walls = wall_quads(m, art, used); flats = planes(m, art, used)
    for t in sorted(used):
        img = art.rgba(t)
        if img is not None:
            Image.fromarray(img).save(OUT / 'tiles' / ('%d.png' % t))
    cams = json.loads((ASSETS / 'e1l1-cameras.json').read_text())
    zone_keys = {}
    for s, sz in enumerate(cams['sector_zone']):
        for row in range(sz['rows']):
            for col in range(sz['cols']):
                zone_keys.setdefault(cams['zones'][sz['start'] + row * sz['cols'] + col], []).append('%d:%d:%d' % (s, col, row))
    cameras = []
    for i, c in enumerate(cams['cameras']):
        cameras.append(dict(index=i, keys=zone_keys.get(i, []), pos=bl(c['x'], c['y'], c['z']), ang=c['ang'], horiz=c['horiz'],
                            sector=c['sector']))
    report = json.loads((ASSETS / 'e1l1-map-report.json').read_text())
    stations = []
    for st in report['stations']:
        z = m.floor_z(st['sector'], st['x'], st['y'])
        image = {'itembox': 'chest.png', 'typewriter': 'typewriter.png'}.get(st['kind'])
        if image:
            (OUT / image).write_bytes((STAGE / 'sprites' / image).read_bytes())
        stations.append(dict(kind=st['kind'], pos=bl(st['x'], st['y'], z), ang=st['ang'], image=image))
    jill_obj(OUT / 'jill.obj')
    s = m.start
    scene = dict(units=dict(xy=XY, z=ZS), jill_scale=jill_scale(), start=bl(s['x'], s['y'], m.floor_z(s['sectnum'], s['x'], s['y'])),
                 start_ang=s['ang'], walls=walls, planes=flats, cameras=cameras, stations=stations,
                 station_repeat=dict(itembox=[27, 22], typewriter=[20, 24]),
                 layout=str((ROOT / 'tools/e1l1-layout.json').resolve()), root=str(ROOT.resolve()))
    (OUT / 'scene.json').write_text(json.dumps(scene))
    print('Layout editor scene: %d walls, %d planes, %d cameras, %d textures.' % (len(walls), len(flats), len(cameras), len(used)))


if __name__ == '__main__':
    main()
