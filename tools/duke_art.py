# SPDX-License-Identifier: GPL-3.0-only
"""Read Duke Nukem 3D's palette and ART tiles from the user's GRP (read only).

Used by the layout editor export to texture E1L1's walls, floors and ceilings.
"""
import struct

import numpy as np


class Art:
    def __init__(self, grp):
        pal = np.frombuffer(grp.read('PALETTE.DAT')[:768], np.uint8).reshape(256, 3).astype(np.uint16)
        self.palette = np.minimum(pal * 255 // 63, 255).astype(np.uint8)
        self.tiles = {}   # tile -> (width, height, data offset, file name)
        self.files = {}
        for n in range(64):
            name = 'TILES%03d.ART' % n
            if name not in grp:
                continue
            data = grp.read(name); self.files[name] = data
            _, _, first, last = struct.unpack_from('<4i', data, 0)
            count = last - first + 1
            sx = struct.unpack_from('<%dh' % count, data, 16)
            sy = struct.unpack_from('<%dh' % count, data, 16 + 2 * count)
            offset = 16 + 8 * count
            for i in range(count):
                self.tiles[first + i] = (sx[i], sy[i], offset, name)
                offset += sx[i] * sy[i]

    def size(self, tile):
        t = self.tiles.get(tile)
        return (t[0], t[1]) if t else (0, 0)

    def rgba(self, tile):
        """Tile as an RGBA array (palette index 255 is transparent), or None."""
        t = self.tiles.get(tile)
        if not t or t[0] <= 0 or t[1] <= 0:
            return None
        w, h, offset, name = t
        idx = np.frombuffer(self.files[name], np.uint8, w * h, offset).reshape(w, h).T   # stored column-major
        out = np.zeros((h, w, 4), np.uint8)
        out[:, :, :3] = self.palette[idx]
        out[:, :, 3] = np.where(idx == 255, 0, 255)
        return out
