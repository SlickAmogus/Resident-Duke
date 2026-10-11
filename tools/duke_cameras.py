# SPDX-License-Identifier: GPL-3.0-only
"""Fixed RE-style cameras for a Build map, generated from its geometry.

Upstream hand-authored camera zones for Doom's E1M1. E1L1 has 325 sectors, so
each sector instead gets one static camera chosen by a visibility search:
candidate anchors near the sector's corners, high in the room, scored by how
much of the sector floor they can see (Build cansee() semantics) and by
framing distance. The runtime keeps a camera while it still frames Jill and
only cuts to the current sector's camera when it loses her, which merges the
many small Build sectors into stable RE-like shots.

tools/e1l1-cameras.json may override any sector: {"<sector>": {"x":..,"y":..,
"z":.., "look": [x, y, z]}}.
"""
import json
import math

# Build z is 16x finer than xy. Jill stands ~11000 z tall.
JILL_MID = 6000          # z above floor used as the visibility target
CAMERA_RISE = 22000      # preferred camera height above floor (z)
CEILING_MARGIN = 1536
MIN_FRAMING = 900        # xy: closer sample points are not framed well
HORIZ_SCALE = 128        # Build horiz pixels per unit tan(pitch) (verified in game)


def lintersect(x1, y1, z1, x2, y2, z2, x3, y3, x4, y4):
    """Build lintersect(): segment (1-2) against wall (3-4); returns point or None."""
    x21, y21 = x2 - x1, y2 - y1; x34, y34 = x3 - x4, y3 - y4
    bot = x21 * y34 - y21 * x34
    if bot == 0:
        return None
    x31, y31 = x3 - x1, y3 - y1
    topt = x31 * y34 - y31 * x34
    if bot > 0:
        if topt < 0 or topt >= bot: return None
        topu = x21 * y31 - y21 * x31
        if topu < 0 or topu >= bot: return None
    else:
        if topt > 0 or topt <= bot: return None
        topu = x21 * y31 - y21 * x31
        if topu > 0 or topu <= bot: return None
    t = topt / bot
    return x1 + x21 * t, y1 + y21 * t, z1 + (z2 - z1) * t


class Sight:
    def __init__(self, m):
        self.m = m
        self.walls = [list(m.sector_walls(s)) for s in range(len(m.sectors))]

    def cansee(self, x1, y1, z1, s1, x2, y2, z2, s2):
        """Port of Build cansee(): flood through portals the ray passes."""
        if s1 < 0 or s2 < 0:
            return False
        if s1 == s2 and abs(x1 - x2) + abs(y1 - y2) == 0:
            return True
        m = self.m; seen = [s1]; i = 0
        while i < len(seen):
            sect = seen[i]; i += 1
            for w in self.walls[sect]:
                (ax, ay), (bx, by) = m.wall_segment(w)
                hit = lintersect(x1, y1, z1, x2, y2, z2, ax, ay, bx, by)
                if hit is None:
                    continue
                ix, iy, iz = hit
                nexts = int(m.walls[w]['nextsector'])
                if nexts < 0 or (int(m.walls[w]['cstat']) & 32):
                    return False
                for s in (sect, nexts):
                    if iz <= m.ceiling_z(s, ix, iy) or iz >= m.floor_z(s, ix, iy):
                        return False
                if nexts not in seen:
                    seen.append(nexts)
        return s2 in seen


CELL = 4096               # zone grid for large sectors (xy units)
FRAME_DIST = 2800         # preferred camera-to-zone-centre distance


def zone_grid(m, s):
    pts = [m.wall_segment(w)[0] for w in m.sector_walls(s)]
    x0 = min(p[0] for p in pts); y0 = min(p[1] for p in pts)
    cols = max(1, -(-(max(p[0] for p in pts) - x0) // CELL))
    rows = max(1, -(-(max(p[1] for p in pts) - y0) // CELL))
    return x0, y0, cols, rows


def zone_samples(m, s, x0, y0, col, row, count=4):
    out = []
    for i in range(count):
        for j in range(count):
            x = int(x0 + (col + (i + .5) / count) * CELL); y = int(y0 + (row + (j + .5) / count) * CELL)
            if m.inside(x, y, s):
                out.append((x, y))
    return out


def zone_candidates(m, s, cx, cy):
    out = []
    for k in range(16):
        a = k * math.pi / 8
        for d in (FRAME_DIST * .7, FRAME_DIST, FRAME_DIST * 1.4):
            out.append((cx + math.cos(a) * d, cy + math.sin(a) * d))
    for w in m.sector_walls(s):
        (x, y), _ = m.wall_segment(w)
        if math.hypot(x - cx, y - cy) < FRAME_DIST * 2.2:
            dx, dy = cx - x, cy - y; d = math.hypot(dx, dy) or 1
            out.append((x + dx / d * 256, y + dy / d * 256))
    return out


def choose_zone(m, sight, s, samples):
    targets = [(x, y, m.floor_z(s, x, y) - JILL_MID) for x, y in samples]
    cx = sum(t[0] for t in targets) / len(targets); cy = sum(t[1] for t in targets) / len(targets)
    best = None
    for px, py in zone_candidates(m, s, cx, cy):
        cs = m.find_sector(int(px), int(py), s)
        if cs < 0:
            continue
        cz = camera_z(m, cs, px, py)
        visible = [t for t in targets if sight.cansee(int(px), int(py), cz, cs, t[0], t[1], int(t[2]), s)]
        if not visible:
            continue
        dist = math.hypot(px - cx, py - cy)
        score = len(visible) / len(targets) * 10 - abs(dist - FRAME_DIST) / FRAME_DIST * 2 + (0.5 if cs == s else 0)
        if best is None or score > best[0]:
            lx = sum(t[0] for t in visible) / len(visible); ly = sum(t[1] for t in visible) / len(visible)
            lz = sum(t[2] for t in visible) / len(visible)
            best = (score, px, py, cz, cs, lx, ly, lz)
    return best


def polygon_samples(m, s, count=5):
    """Interior sample points on a grid over the sector's bounding box."""
    pts = [m.wall_segment(w)[0] for w in m.sector_walls(s)]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    out = []
    for i in range(count):
        for j in range(count):
            x = min(xs) + (max(xs) - min(xs)) * (i + .5) / count
            y = min(ys) + (max(ys) - min(ys)) * (j + .5) / count
            if m.inside(int(x), int(y), s):
                out.append((int(x), int(y)))
    if not out:
        cx, cy = m.centroid(s); out.append((int(cx), int(cy)))
    return out


def candidates(m, s):
    cx, cy = m.centroid(s)
    out = [(cx, cy)]
    for w in m.sector_walls(s):
        (x, y), _ = m.wall_segment(w)
        dx, dy = cx - x, cy - y; d = math.hypot(dx, dy) or 1
        inset = min(max(d * .2, 192), 1024)
        out.append((x + dx / d * inset, y + dy / d * inset))
    return out


def camera_z(m, s, x, y):
    floor = m.floor_z(s, x, y); ceiling = m.ceiling_z(s, x, y)
    return int(max(ceiling + CEILING_MARGIN, floor - CAMERA_RISE)) if floor - ceiling > 2 * CEILING_MARGIN \
        else int((floor + ceiling) / 2)


def choose(m, sight, s):
    samples = polygon_samples(m, s)
    targets = [(x, y, m.floor_z(s, x, y) - JILL_MID) for x, y in samples]
    best = None
    for cx, cy in candidates(m, s):
        cs = m.find_sector(int(cx), int(cy), s)
        if cs < 0:
            continue
        cz = camera_z(m, cs, cx, cy)
        visible = [t for t in targets if sight.cansee(int(cx), int(cy), cz, cs, t[0], t[1], int(t[2]), s)]
        if not visible:
            continue
        framed = sum(1 for t in visible if math.hypot(t[0] - cx, t[1] - cy) >= MIN_FRAMING)
        score = len(visible) * 2 + framed + (0.5 if cs == s else 0)
        if best is None or score > best[0]:
            lx = sum(t[0] for t in visible) / len(visible); ly = sum(t[1] for t in visible) / len(visible)
            lz = sum(t[2] for t in visible) / len(visible)
            best = (score, cx, cy, cz, cs, lx, ly, lz)
    return best


def orient(x, y, z, look):
    lx, ly, lz = look
    dx, dy = lx - x, ly - y; dist = math.hypot(dx, dy) or 1
    ang = int(round(math.atan2(dy, dx) * 1024 / math.pi)) & 2047
    # Build z grows downward; looking down means lz > z, which lowers horiz.
    tan_down = (lz - z) / 16 / dist
    horiz = int(round(100 - HORIZ_SCALE * tan_down))
    return ang, max(-99, min(299, horiz))


def generate(m, sector_count, overrides_path):
    """One camera per zone; zones are CELL-sized grid cells of each sector."""
    sight = Sight(m)
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    cameras = []; zones = []; sector_zone = []
    for s in range(sector_count):
        x0, y0, cols, rows = zone_grid(m, s)
        sector_zone.append(dict(start=len(zones), x0=x0, y0=y0, cols=cols, rows=rows))
        fallback = None
        for row in range(rows):
            for col in range(cols):
                key = '%d:%d:%d' % (s, col, row)
                o = overrides.get(key) or (overrides.get(str(s)) if cols * rows == 1 else None)
                samples = zone_samples(m, s, x0, y0, col, row)
                best = None
                if o:
                    best = (0, o['x'], o['y'], o['z'], m.find_sector(o['x'], o['y'], s), *o['look'])
                elif samples:
                    best = choose_zone(m, sight, s, samples)
                if best is None:
                    zones.append(-1); continue
                _, x, y, z, cs, lx, ly, lz = best
                ang, horiz = orient(x, y, z, (lx, ly, lz))
                zones.append(len(cameras)); fallback = len(cameras)
                cameras.append(dict(x=int(x), y=int(y), z=int(z), ang=ang, horiz=horiz, sect=int(cs), sector=s,
                                    zone=[col, row]))
        if fallback is None:  # tiny/sealed sector: whole-sector search
            best = choose(m, sight, s)
            if best is None:
                cx, cy = m.centroid(s); best = (0, cx, cy, int(m.floor_z(s, cx, cy) - CAMERA_RISE), s, cx + 1, cy, m.floor_z(s, cx, cy))
            _, x, y, z, cs, lx, ly, lz = best
            ang, horiz = orient(x, y, z, (lx, ly, lz))
            fallback = len(cameras)
            cameras.append(dict(x=int(x), y=int(y), z=int(z), ang=ang, horiz=horiz, sect=int(cs), sector=s, zone=None))
        st = sector_zone[-1]['start']
        for k in range(st, len(zones)):
            if zones[k] < 0: zones[k] = fallback
    return dict(cameras=cameras, zones=zones, sector_zone=sector_zone)
