# SPDX-License-Identifier: GPL-3.0-only
"""Generate the playable E1L1 from the user's GRP, plus its RE camera and placement tables.

The original geometry, enemies and effectors are kept byte-for-byte. Changes:
  * Duke pickups become RE pickups (same positions), unused ones are removed;
  * the red access card becomes the sword key;
  * the RE item box, typewriter and an ink ribbon are placed on the rooftop;
  * one unreachable black sector is appended to host the item viewer and
    death-screen scenes (the equivalent of upstream's menu scene sector).
Fixed cameras are generated per sector from the geometry (see duke_cameras),
with optional hand-authored overrides in tools/e1l1-layout.json.
"""
import json
import math

import numpy as np

from common import ROOT, STAGE, ASSETS, write_json, jill_scale, load_layout
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
# Default E1L1 rooftop placements relative to the player start: `ahead` along
# the start heading and `left` across it (Build xy units at jill_scale 1). The
# item box and typewriter then snap back against the nearest solid wall, and
# the ribbon sits beside the typewriter. tools/e1l1-layout.json "stations"
# entries ({"x", "y", "ang"}) override any of them exactly.
STATIONS = [
    dict(kind='typewriter', ahead=760, left=0, wall=True),
    dict(kind='itembox', ahead=760, left=480, wall=True),
    dict(kind='ribbon', beside='typewriter', offset=260),
]
WALL_SEARCH = 900          # only snap when a blocking edge is this close
SPAWN_CLEAR = 520          # keep stations this far from the player start
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


# Duke's step-up limit: eye height (38<<8) minus clipmove's floor allowance
# (20<<8) = 4608 z. Higher ledges need a jump, which Jill (RE) cannot do.
STEP_UP = 4608


def off_ledge(m, x, y, sect):
    """If (x, y) sits on a jump-only ledge, return a point just off it on the
    highest reachable neighbouring floor (pushed 320 units past the shared
    wall), else None."""
    floor = m.floor_z(sect, x, y); best = None
    for w in m.sector_walls(sect):
        n = int(m.walls[w]['nextsector'])
        if n < 0:
            continue
        (ax, ay), (bx, by) = m.wall_segment(w)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        nf = m.floor_z(n, mx, my)
        if nf - floor <= STEP_UP:
            return None  # an ordinary step leads onto this sector
        # Outward normal of a Build wall: walls run clockwise around their sector.
        dx, dy = bx - ax, by - ay; length = (dx * dx + dy * dy) ** .5 or 1
        px, py = mx + dy / length * 320, my - dx / length * 320
        cand = (nf, int(px), int(py), n)
        if m.find_sector(int(px), int(py), n) == n and (best is None or nf < best[0]):
            best = cand
    return None if best is None else best[1:]


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
            moved = off_ledge(m, int(s['x']), int(s['y']), int(s['sectnum']))
            if moved:
                s['x'], s['y'], s['sectnum'] = moved
                report.setdefault('moved_off_ledges', []).append(kind)
            s['z'] = m.floor_z(int(s['sectnum']), int(s['x']), int(s['y']))
            report['converted'][kind] = report['converted'].get(kind, 0) + 1
        elif pic in DUKE_REMOVED:
            report['removed'] += 1
            continue
        kept.append(s)
    return np.array(kept, SPRITE), report


def nearest_solid_wall(m, x, y, sect, limit=WALL_SEARCH):
    """Closest blocking edge for a point standing in `sect`: a one-sided wall, or
    a sector edge whose far side rises more than Duke's step (a parapet, a box).
    Returns (distance, closest point, unit normal pointing back toward the point)."""
    floor = m.floor_z(sect, x, y); best = None
    for w in range(len(m.walls)):
        (ax, ay), (bx, by) = m.wall_segment(w)
        dx, dy = bx - ax, by - ay; length2 = dx * dx + dy * dy
        if not length2:
            continue
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
        cx, cy = ax + dx * t, ay + dy * t; dist = math.hypot(x - cx, y - cy)
        if dist > limit or (best is not None and dist >= best[0]):
            continue
        nxt = int(m.walls[w]['nextsector'])
        if nxt >= 0 and floor - m.floor_z(nxt, cx, cy) <= STEP_UP:
            continue   # an ordinary passable edge
        if m.find_sector(int(x), int(y), sect) != sect:
            continue
        n = math.sqrt(dist * dist) or 1
        best = (dist, (cx, cy), ((x - cx) / n, (y - cy) / n))
    return best


def place_stations(m, sprites, defines):
    start = m.start; out = []; placed = {}
    overrides = load_layout().get('stations', {})
    k = jill_scale(); a = start['ang'] * math.pi / 1024
    for st in STATIONS:
        kind = st['kind']; o = overrides.get(kind)
        if o:
            x, y = int(o['x']), int(o['y']); ang = int(o.get('ang', 0)) & 2047
        elif 'beside' in st:
            bx, by, bang = placed[st['beside']]
            ra = bang * math.pi / 1024 - math.pi / 2   # along the wall, away from the item box
            x, y, ang = int(bx + math.cos(ra) * st['offset'] * k), int(by + math.sin(ra) * st['offset'] * k), bang
        else:
            # Build angles grow clockwise (y points south); "left" is heading - 90 degrees.
            x = start['x'] + st['ahead'] * math.cos(a) + st['left'] * math.sin(a)
            y = start['y'] + st['ahead'] * math.sin(a) - st['left'] * math.cos(a)
            ang = (start['ang'] + 1024) & 2047
            sect = m.find_sector(int(x), int(y), start['sectnum'])
            wall = nearest_solid_wall(m, x, y, sect) if st.get('wall') and sect >= 0 else None
            if wall:
                _, (cx, cy), (nx, ny) = wall
                back = (160 if kind == 'typewriter' else 260) * k   # half depth of the billboard
                sx, sy = cx + nx * back, cy + ny * back
                if math.hypot(sx - start['x'], sy - start['y']) >= SPAWN_CLEAR * k:
                    x, y = sx, sy
                    ang = int(math.atan2(ny, nx) * 1024 / math.pi) & 2047   # facing out of the wall
            x, y = int(x), int(y)
        sect = m.find_sector(x, y, start['sectnum'])
        if sect < 0:
            raise RuntimeError('Station %s at (%d, %d) is outside the map' % (kind, x, y))
        z = m.floor_z(sect, x, y); placed[kind] = (x, y, ang)
        st_report = dict(kind=kind, x=x, y=y, ang=ang, sector=sect); STATION_REPORT.append(st_report)
        if kind == 'itembox':
            spr = _sprite(x, y, z, defines['RE_T_CHEST'], sect, ang, cstat=1, xrepeat=round(27 * k), yrepeat=round(22 * k), shade=-12)
        elif kind == 'typewriter':
            spr = _sprite(x, y, z, defines['RE_T_TYPEWRITER'], sect, ang, cstat=1, xrepeat=round(20 * k), yrepeat=round(24 * k), shade=-12)
        else:
            spr = _sprite(x, y, z, defines['RE_T_WORLD_' + kind.upper()], sect, ang, lotag=PICKUP_KINDS.index(kind))
        out.append(spr)
    return np.concatenate([sprites, np.array(out, SPRITE)])


STATION_REPORT = []


def append_viewer_sector(m, black):
    """An unreachable black box far outside the level for the model-view scenes."""
    cx, cy = VIEWER_CENTRE; h = VIEWER_HALF
    sect = len(m.sectors); w0 = len(m.walls)
    walls = np.zeros(4, WALL)
    for i, (x, y) in enumerate([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]):
        walls[i]['x'], walls[i]['y'] = x, y
        walls[i]['point2'] = w0 + (i + 1) % 4
        walls[i]['nextwall'] = walls[i]['nextsector'] = -1
        walls[i]['picnum'] = black; walls[i]['xrepeat'] = walls[i]['yrepeat'] = 8
    sec = np.zeros(1, SECTOR)[0]
    sec['wallptr'], sec['wallnum'] = w0, 4
    sec['floorz'], sec['ceilingz'] = VIEWER_FLOOR, VIEWER_CEILING
    # Black texture at full brightness: Duke adds a sector's floor shade to its
    # sprites, so the scene must stay lit for the item/corpse models.
    sec['floorpicnum'] = sec['ceilingpicnum'] = black
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
    viewer = append_viewer_sector(m, defines['RE_T_BLACK'])
    (STAGE / 'E1L1.MAP').write_bytes(m.to_bytes())

    # Runtime tables shared with CON.
    for i, kind in enumerate(PICKUP_KINDS):
        tables.const('RE_PICKUP_' + kind.upper(), i)
    tables.add('PICKUP_TILE', [tiles_by_kind[k] for k in PICKUP_KINDS])
    duke = sorted(DUKE_TO_RE); tables.add('DUKE_PICKUP_TILE', duke)
    tables.add('DUKE_PICKUP_KIND', [PICKUP_KINDS.index(DUKE_TO_RE[t]) for t in duke])
    tables.add('DUKE_REMOVED_TILE', sorted(DUKE_REMOVED))
    tables.const('RE_DUKE_PICKUPS', len(duke)); tables.const('RE_DUKE_REMOVED', len(DUKE_REMOVED))
    # Music: open-sky sectors use the main hall theme, interiors the corridors theme.
    tables.add('SECTOR_MUSIC', [1 if int(m.sectors[s]['ceilingstat']) & 1 else 0 for s in range(playable_sectors)] + [0])
    tables.const('RE_VIEWER_SECTOR', viewer)
    tables.const('RE_VIEWER_X', VIEWER_CENTRE[0]); tables.const('RE_VIEWER_Y', VIEWER_CENTRE[1])
    tables.const('RE_VIEWER_Z', 0)

    cams = duke_cameras.generate(m, playable_sectors, load_layout().get('cameras', {}))
    for key in ('x', 'y', 'z', 'ang', 'horiz', 'sect'):
        tables.add('CAM_' + key.upper(), [c[key] for c in cams['cameras']])
    sz = cams['sector_zone'] + [dict(start=0, x0=0, y0=0, cols=1, rows=1)]  # viewer sector -> dummy
    for key in ('start', 'x0', 'y0', 'cols', 'rows'):
        tables.add('SECTOR_ZONE_' + key.upper(), [z[key] for z in sz])
    tables.add('ZONE_CAMERA', cams['zones'])
    tables.const('RE_ZONE_CELL', duke_cameras.CELL)
    tables.const('RE_CAMERAS', len(cams['cameras']))
    write_json(ASSETS / 'e1l1-map-report.json', dict(pickups=report, stations=STATION_REPORT, viewer_sector=viewer,
                                                     cameras=len(cams['cameras'])))
    write_json(ASSETS / 'e1l1-cameras.json', cams)
    print('E1L1: %s; %d cameras.' % (report, len(cams['cameras'])))
