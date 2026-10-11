# SPDX-License-Identifier: GPL-3.0-only
"""Read-only access to a Duke Nukem 3D GRP and Build v7 map (de)serialisation.

The user's GRP is only ever read. Modified maps are written into build/stage.
"""
from pathlib import Path
import struct

import numpy as np

SECTOR = np.dtype([('wallptr', '<i2'), ('wallnum', '<i2'), ('ceilingz', '<i4'), ('floorz', '<i4'),
                   ('ceilingstat', '<u2'), ('floorstat', '<u2'), ('ceilingpicnum', '<i2'), ('ceilingheinum', '<i2'),
                   ('ceilingshade', 'i1'), ('ceilingpal', 'u1'), ('ceilingxpanning', 'u1'), ('ceilingypanning', 'u1'),
                   ('floorpicnum', '<i2'), ('floorheinum', '<i2'), ('floorshade', 'i1'), ('floorpal', 'u1'),
                   ('floorxpanning', 'u1'), ('floorypanning', 'u1'), ('visibility', 'u1'), ('filler', 'u1'),
                   ('lotag', '<i2'), ('hitag', '<i2'), ('extra', '<i2')])
WALL = np.dtype([('x', '<i4'), ('y', '<i4'), ('point2', '<i2'), ('nextwall', '<i2'), ('nextsector', '<i2'),
                 ('cstat', '<u2'), ('picnum', '<i2'), ('overpicnum', '<i2'), ('shade', 'i1'), ('pal', 'u1'),
                 ('xrepeat', 'u1'), ('yrepeat', 'u1'), ('xpanning', 'u1'), ('ypanning', 'u1'),
                 ('lotag', '<i2'), ('hitag', '<i2'), ('extra', '<i2')])
SPRITE = np.dtype([('x', '<i4'), ('y', '<i4'), ('z', '<i4'), ('cstat', '<u2'), ('picnum', '<i2'), ('shade', 'i1'),
                   ('pal', 'u1'), ('clipdist', 'u1'), ('filler', 'u1'), ('xrepeat', 'u1'), ('yrepeat', 'u1'),
                   ('xoffset', 'i1'), ('yoffset', 'i1'), ('sectnum', '<i2'), ('statnum', '<i2'), ('ang', '<i2'),
                   ('owner', '<i2'), ('xvel', '<i2'), ('yvel', '<i2'), ('zvel', '<i2'), ('lotag', '<i2'),
                   ('hitag', '<i2'), ('extra', '<i2')])
assert SECTOR.itemsize == 40 and WALL.itemsize == 32 and SPRITE.itemsize == 44


class Grp:
    """KenSilverman GRP archive index; file names are case-insensitive."""

    def __init__(self, path):
        self.path = Path(path)
        with open(self.path, 'rb') as f:
            head = f.read(16)
            if head[:12] != b'KenSilverman':
                raise RuntimeError(f'{self.path.name} is not a Duke Nukem 3D GRP')
            count = struct.unpack_from('<I', head, 12)[0]
            table = f.read(16 * count)
        self.entries = {}; offset = 16 + 16 * count
        for i in range(count):
            name = table[i * 16:i * 16 + 12].rstrip(b'\0').decode('ascii', 'replace').upper()
            size = struct.unpack_from('<I', table, i * 16 + 12)[0]
            self.entries[name] = (offset, size); offset += size

    def __contains__(self, name):
        return name.upper() in self.entries

    def read(self, name):
        offset, size = self.entries[name.upper()]
        with open(self.path, 'rb') as f:
            f.seek(offset); return f.read(size)


class BuildMap:
    """A Build v7 map held as NumPy record arrays."""

    def __init__(self, data):
        version, x, y, z, ang, sect = struct.unpack_from('<4i2h', data, 0)
        if version != 7:
            raise RuntimeError(f'Unsupported map version {version}; expected Build v7')
        self.start = dict(x=x, y=y, z=z, ang=ang, sectnum=sect)
        p = 20
        n = struct.unpack_from('<H', data, p)[0]; p += 2
        self.sectors = np.frombuffer(data, SECTOR, n, p).copy(); p += n * SECTOR.itemsize
        n = struct.unpack_from('<H', data, p)[0]; p += 2
        self.walls = np.frombuffer(data, WALL, n, p).copy(); p += n * WALL.itemsize
        n = struct.unpack_from('<H', data, p)[0]; p += 2
        self.sprites = np.frombuffer(data, SPRITE, n, p).copy(); p += n * SPRITE.itemsize
        if p != len(data):
            raise RuntimeError('Trailing data after map sprites')

    def to_bytes(self):
        s = self.start
        out = bytearray(struct.pack('<4i2h', 7, s['x'], s['y'], s['z'], s['ang'], s['sectnum']))
        for table in (self.sectors, self.walls, self.sprites):
            out += struct.pack('<H', len(table)) + table.tobytes()
        return bytes(out)

    # ---- geometry helpers -------------------------------------------------
    def sector_walls(self, s):
        sec = self.sectors[s]
        return range(int(sec['wallptr']), int(sec['wallptr']) + int(sec['wallnum']))

    def wall_segment(self, w):
        a = self.walls[w]; b = self.walls[int(a['point2'])]
        return (int(a['x']), int(a['y'])), (int(b['x']), int(b['y']))

    def inside(self, x, y, s):
        """Build's inside(): even-odd test over every wall loop of the sector."""
        crossings = 0
        for w in self.sector_walls(s):
            (x1, y1), (x2, y2) = self.wall_segment(w)
            y1 -= y; y2 -= y
            if (y1 ^ y2) < 0:
                x1 -= x; x2 -= x
                if (x1 ^ x2) >= 0:
                    crossings ^= x1
                else:
                    crossings ^= (x1 * y2 - x2 * y1) ^ y2
        return (crossings >> 31) & 1 == 1

    def find_sector(self, x, y, hint=None):
        order = ([hint] if hint is not None else []) + list(range(len(self.sectors)))
        for s in order:
            if s is not None and 0 <= s < len(self.sectors) and self.inside(x, y, s):
                return s
        return -1

    def floor_z(self, s, x, y):
        return self._plane_z(s, x, y, 'floor')

    def ceiling_z(self, s, x, y):
        return self._plane_z(s, x, y, 'ceiling')

    def _plane_z(self, s, x, y, which):
        """getflorzofslope/getceilzofslope for sloped (stat bit 2) planes."""
        sec = self.sectors[s]; z = int(sec[which + 'z'])
        if not (int(sec[which + 'stat']) & 2):
            return z
        w0 = int(sec['wallptr']); (x1, y1), (x2, y2) = self.wall_segment(w0)
        dx, dy = x2 - x1, y2 - y1; length = (dx * dx + dy * dy) ** .5
        if length == 0:
            return z
        # heinum 4096 = one xy unit of perpendicular travel per 16 z units (45 degrees).
        distance = (dx * (y - y1) - dy * (x - x1)) / length
        return int(z + int(sec[which + 'heinum']) * distance / 256)

    def centroid(self, s):
        pts = [self.wall_segment(w)[0] for w in self.sector_walls(s)]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
