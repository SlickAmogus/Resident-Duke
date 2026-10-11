#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Extract original type5 casing sprites and both native animation chains.
Source: Globals.cpp g_weaponMuzzleFlash 0x4c0e68; PlayerAnimations.cpp autoaim_fire
0x4580f0; EffectSystem behaviours 11/8/10/9 and Effect_AnimateSprite.
"""
import struct
import numpy as np
from PIL import Image
from common import REF, STAGE, ASSETS, rgb555, save_centered, write_json, refresh_extraction_manifest

b = (REF / 'Data/CORE00.ESP').read_bytes(); slot = list(b[:8]).index(5)
p = struct.unpack_from('<I', b, len(b) - 4 - slot * 4)[0]; n = b[p + 2]; nu = b[p]; a = p + 8 + (n + nu) * 4
frames = [list(b[p + 8 + i * 4:p + 12 + i * 4]) for i in range(n)]
uv = [list(b[p + 8 + n * 4 + i * 4:p + 12 + n * 4 + i * 4]) for i in range(nu)]
phases = []
for d in [0, 1]:
    q = a + b[a + d] * 4; assert struct.unpack_from('<I', b, q)[0] == 1; q += 4
    count = struct.unpack_from('<I', b, q)[0]; q += 4
    phases.append([list(b[q + k * 24:q + (k + 1) * 24]) for k in range(count)])
t = (REF / 'Effspr/esp000.tim').read_bytes(); cs = struct.unpack_from('<I', t, 8)[0]
pal = np.frombuffer(t, dtype='<u2', count=256, offset=20); ip = 8 + cs; w, h = struct.unpack_from('<2H', t, ip + 8)
ix = np.frombuffer(t, dtype=np.uint8, count=w * 2 * h, offset=ip + 12).reshape(h, w * 2)
for i, (u, v, cx, cy) in enumerate(uv[:16]):
    c = pal[ix[v:v + 16, u:u + 16]]
    # Source sprite origin is (128-cx, 128-cy) inside its 16x16 cell.
    save_centered(Image.fromarray(rgb555(c)), (128 - cx, 128 - cy), STAGE / ('sprites/casing%02d.png' % i))
write_json(ASSETS / 'casing-manifest.json', dict(
    source_animation='USA/Data/CORE00.ESP', source_art='USA/Effspr/esp000.tim', type=5, depths=[0, 9],
    fire_frames=[3, 25], body_offsets=[[370, -2570, -220], [360, -2050, -440]],
    headers=[v for gun in phases for phase in gun[:5] for v in phase], frames=[v for f in frames for v in f],
    phases=phases, uv=uv[:16]))
refresh_extraction_manifest()
print('Extracted 16 original casing sprites and %d animation frames.' % len(frames))
