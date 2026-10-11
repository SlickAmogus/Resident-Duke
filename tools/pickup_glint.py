#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Original RE1 type 0x0b item glint: CORE00.ESP + esp001.TIM.
CmdFunctions::cmd_item_set 0x461220 (ROOM1000 sword flags 0x8700 => depth28),
EffectSystem::effect_behavior_fire_phases 0x4101d0, Effect_AnimateSprite 0x47ce10.
"""
import struct
import numpy as np
from PIL import Image
from common import REF, STAGE, ASSETS, rgb555, save_centered, write_json, refresh_extraction_manifest

b = (REF / 'Data/CORE00.ESP').read_bytes(); slot = list(b[:8]).index(11)
p = struct.unpack_from('<I', b, len(b) - 4 - slot * 4)[0]; n = b[p + 2]; nu = b[p]
frames = [list(b[p + 8 + i * 4:p + 12 + i * 4]) for i in range(n)]
uv = [list(b[p + 8 + n * 4 + i * 4:p + 12 + n * 4 + i * 4]) for i in range(nu)]
a = p + 8 + (n + nu) * 4; q = a + b[a + 4] * 4
assert struct.unpack_from('<2I', b, q) == (1, 1)
header = list(b[q + 8:q + 32]); assert header[0] == 56 and header[5:7] == [11, 10]
t = (REF / 'Effspr/esp001.tim').read_bytes(); cs = struct.unpack_from('<I', t, 8)[0]
pal = np.frombuffer(t, dtype='<u2', count=256, offset=20); ip = 8 + cs; w, h = struct.unpack_from('<2H', t, ip + 8)
ix = np.frombuffer(t, dtype=np.uint8, count=w * 2 * h, offset=ip + 12).reshape(h, w * 2)
# Type 0xb occupies page1 V123..147; palette row 0 and tint record 7 identity.
for i, (u, v, cx, cy) in enumerate(uv):
    save_centered(Image.fromarray(rgb555(pal[ix[v + 123:v + 147, u:u + 24]])), (128 - cx, 128 - cy),
                  STAGE / ('sprites/glint%02d.png' % i))
write_json(ASSETS / 'pickup-glint-manifest.json', dict(
    source_animation='USA/Data/CORE00.ESP', source_art='USA/Effspr/esp001.tim', type=11, depth=28, record=p,
    header=header, frames=frames, uv=uv, band_y=123, active_ticks=11, hidden_ticks=[100, 110, 120, 130, 140],
    light_factor=10, host_note='Source additive billboard at the 30 Hz source tick; scaled .5 for the world'))
refresh_extraction_manifest()
print('Extracted %d original glint sprites.' % len(uv))
