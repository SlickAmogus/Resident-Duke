# SPDX-License-Identifier: GPL-3.0-only
"""Generate the playable E1L1 from the user's GRP, plus its RE camera and placement tables.

The original geometry, enemies and effectors are kept byte-for-byte. Changes:
  * Duke pickups become RE pickups (same positions), unused ones are removed;
  * the red access card becomes the sword key;
  * the RE item box, typewriter and an ink ribbon are placed on the rooftop;
  * one unreachable black sector is appended to host the item viewer and
    death-screen scenes (the equivalent of upstream's menu scene sector).
Fixed cameras are generated per sector from the geometry (see duke_cameras),
with optional hand-authored overrides in tools/e1l1-cameras.json.
"""
import json
import math

import numpy as np

from common import ROOT, STAGE, ASSETS, write_json
from duke_grp import BuildMap, SPRITE, SECTOR, WALL
import duke_cameras

# Duke tile numbers (DEFS.CON).
APLAYER = 1405
ACCESSCARD = 60
ACCESSSWITCH, ACCESSSWITCH2 = 130, 170
# Duke pickup tile -> RE pickup kind. Kinds index RE_PICKUP_* in CON.
PICKUP_KINDS = ['clip', 'shells', 'shotgun', 'herb', 'ribbon', 'key']
DUKE_TO_RE = {
    40: 'clip',       # AMMO
    21: 'clip',       # FIRSTGUNSPRITE
    49: 'shells',     # SHOTGUNAMMO
    28: 'shotgun',    # SHOTGUNSPRITE (only the first one stays a shotgun; see below)
    51: 'herb',       # COLA
    52: 'herb',       # SIXPAK
    53: 'herb',       # FIRSTAID
    100: 'herb',      # ATOMICHEALTH
    1348: 'ribbon',   # HOLODUKE
    60: 'key',        # ACCESSCARD (red card in E1L1)
}
# Duke pickups with no RE counterpart in this slice are removed.
DUKE_REMOVED = {22, 23, 24, 25, 26, 27, 29, 32, 37, 41, 42, 44, 45, 46, 47, 54, 55, 56, 57, 59, 61, 26, 2545}
# Map-specific placements on the E1L1 rooftop near the start (Build xy, angle).
STATIONS = [
    dict(kind='itembox', dx=-512, dy=-1100, ang=512),
    dict(kind='typewriter', dx=180, dy=-1100, ang=512),
    dict(kind='ribbon', dx=-150, dy=-900, ang=0),
]
VIEWER_CENTRE = (-80000, -40000)
VIEWER_HALF = 8192
VIEWER_FLOOR, VIEWER_CEILING = 65536, -65536
MODEL_REPEAT = 64


def _sprite(x, y, z, picnum, sect, ang=0, cstat=0, xrepeat=MODEL_REPEAT, yrepeat=MODEL_REPEAT, lotag=0, pal=0, shade=0):
    s = np.zeros(1, SPRITE)[0]
    s['x'], s['y'], s['z'] = x, y, z
    s['picnum'], s['sectnum'], s['ang'], s['cstat'] = picnum, sect, ang, cstat
    s['xrepeat'], s['yrepeat'], s['clipdist'] = xrepeat, yrepeat, 32
    s['owner'], s['lotag'], s['pal'], s['shade'] = -1, lotag, pal, shade
    return s


def convert_pickups(m, tiles_by_kind):
    """Rewrite Duke pickups in place; returns (kept sprite records, report)."""
    kept = []; report = {'converted': {}, 'removed': 0}; shotgun_used = False
    for s in m.sprites:
        pic = int(s['picnum'])
        if pic in DUKE_TO_RE:
            kind = DUKE_TO_RE[pic]
            if kind == 'shotgun':
                if shotgun_used:
                    kind = 'shells'
                shotgun_used = True
            s = s.copy()
            s['picnum'] = tiles_by_kind[kind]; s['lotag'] = PICKUP_KINDS.index(kind)
            s['xrepeat'] = s['yrepeat'] = MODEL_REPEAT; s['cstat'] = 0; s['pal'] = 0
            s['z'] = m.floor_z(int(s['sectnum']), int(s['x']), int(s['y']))
            report['converted'][kind] = report['converted'].get(kind, 0) + 1
        elif pic in DUKE_REMOVED:
            report['removed'] += 1
            continue
        kept.append(s)
    return np.array(kept, SPRITE), report


def place_stations(m, sprites, defines):
    start = m.start; out = []
    for st in STATIONS:
        x, y = start['x'] + st['dx'], start['y'] + st['dy']
        sect = m.find_sector(x, y, start['sectnum'])
        if sect < 0:
            raise RuntimeError('Station %s falls outside the map' % st['kind'])
        z = m.floor_z(sect, x, y)
        if st['kind'] == 'itembox':
            spr = _sprite(x, y, z, defines['RE_T_CHEST'], sect, st['ang'], cstat=1, xrepeat=27, yrepeat=22)
        elif st['kind'] == 'typewriter':
            spr = _sprite(x, y, z, defines['RE_T_TYPEWRITER'], sect, st['ang'], cstat=1, xrepeat=20, yrepeat=24)
        else:
            spr = _sprite(x, y, z, defines['RE_T_WORLD_' + st['kind'].upper()], sect, st['ang'],
                          lotag=PICKUP_KINDS.index(st['kind']))
        out.append(spr)
    return np.concatenate([sprites, np.array(out, SPRITE)])


def append_viewer_sector(m):
    """An unreachable black box far outside the level for the model-view scenes."""
    cx, cy = VIEWER_CENTRE; h = VIEWER_HALF
    sect = len(m.sectors); w0 = len(m.walls)
    walls = np.zeros(4, WALL)
    for i, (x, y) in enumerate([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]):
        walls[i]['x'], walls[i]['y'] = x, y
        walls[i]['point2'] = w0 + (i + 1) % 4
        walls[i]['nextwall'] = walls[i]['nextsector'] = -1
        walls[i]['shade'] = 127; walls[i]['xrepeat'] = walls[i]['yrepeat'] = 8
    sec = np.zeros(1, SECTOR)[0]
    sec['wallptr'], sec['wallnum'] = w0, 4
    sec['floorz'], sec['ceilingz'] = VIEWER_FLOOR, VIEWER_CEILING
    sec['floorshade'] = sec['ceilingshade'] = 127
    m.walls = np.concatenate([m.walls, walls])
    m.sectors = np.concatenate([m.sectors, np.array([sec], SECTOR)])
    return sect


def generate(grp, tables, tiles):
    defines = dict(tiles.defines)
    original = grp.read('E1L1.MAP')
    m = BuildMap(original)
    playable_sectors = len(m.sectors)
    tiles_by_kind = {k: defines['RE_T_WORLD_' + {'clip': 'CLIP', 'shells': 'SHELLS', 'shotgun': 'SHOTGUN',
                                                 'herb': 'HERB', 'ribbon': 'RIBBON', 'key': 'KEY'}[k]]
                     for k in PICKUP_KINDS}
    sprites, report = convert_pickups(m, tiles_by_kind)
    sprites = place_stations(m, sprites, defines)
    m.sprites = sprites
    viewer = append_viewer_sector(m)
    (STAGE / 'E1L1.MAP').write_bytes(m.to_bytes())

    # Runtime tables shared with CON.
    for i, kind in enumerate(PICKUP_KINDS):
        tables.const('RE_PICKUP_' + kind.upper(), i)
    tables.add('PICKUP_TILE', [tiles_by_kind[k] for k in PICKUP_KINDS])
    duke = sorted(DUKE_TO_RE); tables.add('DUKE_PICKUP_TILE', duke)
    tables.add('DUKE_PICKUP_KIND', [PICKUP_KINDS.index(DUKE_TO_RE[t]) for t in duke])
    tables.add('DUKE_REMOVED_TILE', sorted(DUKE_REMOVED))
    tables.const('RE_VIEWER_SECTOR', viewer)
    tables.const('RE_VIEWER_X', VIEWER_CENTRE[0]); tables.const('RE_VIEWER_Y', VIEWER_CENTRE[1])
    tables.const('RE_VIEWER_Z', 0)

    cams = duke_cameras.generate(m, playable_sectors, ROOT / 'tools/e1l1-cameras.json')
    for key in ('x', 'y', 'z', 'ang', 'horiz', 'sect'):
        tables.add('CAM_' + key.upper(), [c[key] for c in cams['cameras']])
    tables.add('SECTOR_CAMERA', cams['sector_camera'] + [0])  # viewer sector -> dummy
    tables.const('RE_CAMERAS', len(cams['cameras']))
    write_json(ASSETS / 'e1l1-map-report.json', dict(pickups=report, stations=STATIONS, viewer_sector=viewer,
                                                     cameras=len(cams['cameras'])))
    write_json(ASSETS / 'e1l1-cameras.json', cams)
    print('E1L1: %s; %d cameras.' % (report, len(cams['cameras'])))
