#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Extract the original 40x30 inventory icons used by the slice. Model conversion is separate."""
import re
import numpy as np
from PIL import Image
from common import REF, DECOMP, STAGE, rgb555
from re1_item_tables import read_tables

# Rows derived from g_ItemImageLookupTable; mixed herbs use ITEM_MIX.PIX.
src = (DECOMP / 'src/Globals.cpp').read_text()
m = re.search(r'g_ItemImageLookupTable\s*\[.*?\]\s*=\s*\{(.*?)\};', src, re.S)
nums = [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]+)', re.sub(r'//[^\n]*', '', m[1]))]
s = (REF / 'Data/STATUS.TIM').read_bytes()
pal = np.frombuffer(s, dtype='<u2', count=256, offset=20 + 2 * 256 * 2)
pix = (REF / 'Data/ITEM_ALL.PIX').read_bytes()
mixed = (REF / 'Data/ITEM_MIX.PIX').read_bytes()
out = STAGE / 'graphics'; out.mkdir(parents=True, exist_ok=True)
tables = read_tables()
for item, name in [(2, 'handgun'), (3, 'shotgun'), (47, 'ribbon'), (11, 'ammo'), (12, 'shells'),
                   (0x44, 'herb'), (0x33, 'key'), (0x47, 'herb2'), (0x4a, 'herb3')]:
    row = nums[item * 4] - 1; source = pix
    if item in (0x47, 0x4a):
        row = tables['image_types'][nums[item * 4 + 1]] - 1; source = mixed
    arr = np.frombuffer(source, dtype=np.uint8, count=1200, offset=row * 1200).reshape(30, 40)
    rgba = rgb555(pal[arr]); rgba[:, :, 3] = np.where(arr == 0, 0, 255)
    Image.fromarray(rgba).save(out / (name + '.png'))
print('Extracted nine original 40x30 inventory icons.')
