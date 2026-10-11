#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Convert the original IVM menu models with their 64-step intro rotation.
Camera basis C=(-x,-z,-y), focal length 192 and centre 112,76 are from MainMenu.
Output geometry is in Doom-scale units (RE x 56/1800), as upstream.
"""
import struct
import numpy as np
from PIL import Image
from common import REF, STAGE, ASSETS, write_md3, write_json
from re1_model_math import rotation, apply_vertices

OUT = STAGE / 'models/items'; OUT.mkdir(parents=True, exist_ok=True)
# Item id -> IVM file. Order is the runtime's viewer slot order.
ITEM_VIEWS = [(2, 'I00V'), (3, 'I02V'), (47, 'I56V'), (11, 'I26V'), (12, 'I16V'),
              (0x33, 'I30V'), (0x44, 'I64V'), (0x47, 'I67V'), (0x4a, 'I71V')]


def read_ivm(file):
    """Return (points, uv, triangles, texture RGBA) for an original IVM file."""
    b = (REF / 'Item_m2' / (file + '.IVM')).read_bytes()
    clen = struct.unpack_from('<I', b, 8)[0]; p = 8 + clen
    w, h = struct.unpack_from('<2H', b, p + 8); base = p + struct.unpack_from('<I', b, p)[0]
    pal = np.frombuffer(b, dtype='<u2', count=256, offset=20)
    raw = np.frombuffer(b, dtype=np.uint8, count=w * 2 * h, offset=p + 12).reshape(h, w * 2)
    v = pal[raw]
    rgba = np.stack(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31,
                     np.where(raw == 0, 0, 255)), axis=-1).astype('uint8')
    # One extra opaque row: flat (mode 0x30) primitives sample it as their colour.
    rgba = np.concatenate((rgba, np.full((1, w * 2, 4), (11, 11, 11, 255), dtype=np.uint8)))
    assert struct.unpack_from('<3I', b, base) == (65, 0, 1)
    vp, nv, _, _, pp, nprim, _ = struct.unpack_from('<7I', b, base + 12)
    verts = np.array([struct.unpack_from('<3h', b, base + 12 + vp + i * 8) for i in range(nv)], float)
    pos = base + 12 + pp; points = []; uv = []; triangles = []
    for _ in range(nprim):
        _, ilen, _, mode = struct.unpack_from('<4B', b, pos); assert mode in (0x30, 0x34, 0x3c)
        q = pos + 4; start = len(points); num = 4 if mode == 0x3c else 3
        for j in range(num):
            u, vv = struct.unpack_from('<2B', b, q + j * 4) if mode != 0x30 else (0, h)
            vi = struct.unpack_from('<H', b, q + (num * 4 if mode != 0x30 else 4) + 2 + j * 4)[0]
            points.append(verts[vi]); uv.append(((u + .5) / (w * 2), (vv + .5) / (h + 1)))
        for tri in [(0, 1, 2)] + ([(1, 3, 2)] if num == 4 else []):
            t = tuple(start + k for k in tri); triangles.extend([t, t[::-1]])
        pos += 4 + ilen * 4
    return np.array(points), uv, triangles, rgba, dict(vertices=nv, primitives=nprim)


if __name__ == '__main__':
    manifest = []
    for item, file in ITEM_VIEWS:
        points, uv, triangles, rgba, info = read_ivm(file)
        Image.fromarray(rgba).save(OUT / (file + '.png'))
        frames = []
        for step in range(65):
            # Entry 0 before the intro; entry 64 reaches identity (three yaw/two roll turns).
            r = rotation((0, step * 0xc0, step * 0x80)); v = apply_vertices(r, points)
            frames.append(np.stack((-v[:, 0], -v[:, 2], -v[:, 1]), axis=1) * 56 / 1800)
        write_md3(OUT / (file + '.md3'), file, points, uv, triangles, frames, file + '.png')
        manifest.append(dict(item=item, file=file, intro_steps=64, **info))
    write_json(ASSETS / 'item-view-manifest.json', manifest)
    print('Converted nine original IVM models, 65 intro frames each.')
