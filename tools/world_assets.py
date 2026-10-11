#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Convert original IVM meshes into world pickups and crop original scenery into billboards.
No reconstructed RE object geometry or replacement textures.
"""
import runpy
import struct
import numpy as np
from PIL import Image, ImageDraw
from common import ROOT, REF, ASSETS, DECOMP, STAGE, write_md3, write_json

out = STAGE / 'models/items'; out.mkdir(parents=True, exist_ok=True)
(ASSETS / 'background-reference').mkdir(parents=True, exist_ok=True)


def readmesh(path, frame=64):
    b = path.read_bytes(); off = struct.unpack_from('<i', b, 100)[0]
    s = struct.unpack_from('<4s64s10i', b, off); nf, _, nv, nt, ot, _, ost, ox, _ = s[3:]
    v = np.array([struct.unpack_from('<3hH', b, off + ox + (frame * nv + i) * 8)[:3] for i in range(nv)], float) / 64
    uv = [struct.unpack_from('<2f', b, off + ost + i * 8) for i in range(nv)]
    tri = [struct.unpack_from('<3i', b, off + ot + i * 12) for i in range(nt)]
    return v, uv, tri


def bright_skin(source, destination, factor):
    """Bake upstream's self-lit presentation shader (texel x factor) into the skin."""
    image = np.asarray(Image.open(source).convert('RGBA')).astype('float32')
    image[:, :, :3] = np.minimum(image[:, :, :3] * factor, 255)
    Image.fromarray(image.astype('uint8')).save(destination)


# Room backgrounds use PS1 RGB555, as display_image (0x00470770) does.
# pak_view.py's RGB helper reverses R/B, so use its LZW only, not its colours.
PakDecoder = runpy.run_path(str(DECOMP / 'tools/pak_view.py'))['PakDecoder']


def decode_background(name):
    raw = PakDecoder((REF / 'Stage1' / name).read_bytes()).run()
    assert struct.unpack_from('<2I', raw) == (16, 2)
    w, h = struct.unpack_from('<2H', raw, 16)
    pixels = np.frombuffer(raw, dtype='<u2', count=w * h, offset=20).reshape(h, w)
    rgb = np.stack(((pixels & 31) * 255 // 31, ((pixels >> 5) & 31) * 255 // 31,
                    ((pixels >> 10) & 31) * 255 // 31), -1).astype('uint8')
    Image.fromarray(rgb).save(ASSETS / 'background-reference' / (name.split('.')[0] + '.png'))


for name in ['RC1181.pak', 'RC1180.pak']:
    decode_background(name)

models = []; world_measurements = []
# Pickup name -> original IVM. Upstream's per-item presentation scale/orientation retained.
for actor, file in [('clip', 'I26V'), ('herb', 'I64V'), ('shells', 'I16V'), ('shotgun', 'I02V'), ('ribbon', 'I56V')]:
    v, uv, tri = readmesh(out / (file + '.md3'))
    v /= (3 if actor == 'shotgun' else 3.2 if actor == 'herb' else 6)
    if actor == 'herb': v[:, 0] *= 1.15
    if actor == 'ribbon': v = np.stack((v[:, 2], v[:, 1], -v[:, 0]), axis=1)
    if actor == 'clip': v = np.stack((v[:, 0], -v[:, 2], v[:, 1]), axis=1)
    v[:, 2] -= v[:, 2].min(); v[:, 2] += 2
    world_measurements.append({'actor': actor, 'source': 'USA/Item_m2/' + file + '.IVM',
                               'dimensions': (v.max(axis=0) - v.min(axis=0)).tolist(), 'floor_clearance': 2})
    bright_skin(out / (file + '.png'), out / ('world-' + file + '.png'), 2.0)
    write_md3(out / ('world-' + file + '.md3'), 'world-' + file, v, uv, tri, [v], 'world-' + file + '.png')
    models.append(dict(actor=actor, model='models/items/world-' + file + '.md3',
                       skin='models/items/world-' + file + '.png'))

# Prefer the original in-room sword-key TMD over its menu-view mesh.
b = (REF / 'Stage1/ROOM1000.RDT').read_bytes()
table = struct.unpack_from('<I', b, 0x54)[0]; base, tim = struct.unpack_from('<2I', b, table)
clen = struct.unpack_from('<I', b, tim + 8)[0]; pal = np.frombuffer(b, dtype='<u2', count=256, offset=tim + 20)
p = tim + 8 + clen; ix, iy, w, h = struct.unpack_from('<4H', b, p + 4)
indices = np.frombuffer(b, dtype=np.uint8, count=w * 2 * h, offset=p + 12).reshape(h, w * 2); colours = pal[indices]
rgba = np.stack(((colours & 31) * 255 // 31, ((colours >> 5) & 31) * 255 // 31, ((colours >> 10) & 31) * 255 // 31,
                 np.where(indices == 0, 0, 255)), -1).astype('uint8')
Image.fromarray(rgba).save(out / 'world-key-raw.png')
bright_skin(out / 'world-key-raw.png', out / 'world-key.png', 2.0); (out / 'world-key-raw.png').unlink()
vp, nv, _, _, pp, nprim, _ = struct.unpack_from('<7I', b, base + 12)
verts = np.array([struct.unpack_from('<3h', b, base + 12 + vp + i * 8) for i in range(nv)], float)
points = []; uv = []; tri = []; pos = base + 12 + pp
for k in range(nprim):
    _, length, _, mode = struct.unpack_from('<4B', b, pos); assert mode == 0x34
    q = pos + 4; page = struct.unpack_from('<H', b, q + 6)[0]; start = len(points)
    for j in range(3):
        u, vv = struct.unpack_from('<2B', b, q + j * 4); vi = struct.unpack_from('<H', b, q + 14 + j * 4)[0]
        points.append(verts[vi])
        uv.append(((u + (page & 15) * 128 - ix * 2 + .5) / (w * 2), (vv + ((page >> 4) & 1) * 256 - iy + .5) / h))
    tri.extend([(start, start + 1, start + 2), (start + 2, start + 1, start)]); pos += 4 + length * 4
# Source key is a plane. Lay that original plane on the floor, 18 Doom-scale units long.
v = np.array(points); v = np.stack((v[:, 1], v[:, 2], v[:, 0]), axis=1) * (18 / (v[:, 1].max() - v[:, 1].min()))
v[:, 2] -= v[:, 2].min(); v[:, 2] += 2
write_md3(out / 'world-key.md3', 'world-key', v, uv, tri, [v], 'world-key.png')
models.append(dict(actor='key', model='models/items/world-key.md3', skin='models/items/world-key.png'))
world_measurements.append({'actor': 'key', 'source': 'USA/Stage1/ROOM1000.RDT item table0x54 slot0',
                           'dimensions': (v.max(axis=0) - v.min(axis=0)).tolist(), 'floor_clearance': 2})


# The chest and typewriter are pre-rendered artwork, not complete standalone meshes.
# Only crop and mask original pixels; never reconstruct missing geometry. The
# crop is anchored bottom-centre, which is Build's native sprite origin.
def original_sprite(source, polygon, destination, brightness=1.0):
    image = Image.open(source).convert('RGBA')
    mask = Image.new('L', image.size, 0); ImageDraw.Draw(mask).polygon(polygon, fill=255)
    image.putalpha(mask); image = image.crop(mask.getbbox())
    if brightness != 1.0:
        a = np.asarray(image).astype('float32'); a[:, :, :3] = np.minimum(a[:, :, :3] * brightness, 255)
        image = Image.fromarray(a.astype('uint8'))
    destination.parent.mkdir(parents=True, exist_ok=True); image.save(destination)
    return {'source': str(source.relative_to(ROOT)).replace('\\', '/'), 'polygon': polygon,
            'output': str(destination.relative_to(ROOT)).replace('\\', '/'), 'size': list(image.size)}


chest = original_sprite(ASSETS / 'background-reference/RC1181.png',
                        [(82, 153), (92, 150), (139, 148), (154, 151), (154, 183), (144, 193), (86, 190), (82, 184)],
                        STAGE / 'sprites/chest.png')
# Upstream's typewriter.fp presentation exposure (x1.5) is baked into the crop.
typewriter = original_sprite(ASSETS / 'background-reference/RC1180.png',
                             [(77, 134), (95, 134), (95, 145), (100, 148), (100, 153), (109, 154), (109, 158), (94, 158),
                              (92, 178), (90, 196), (97, 202), (97, 208), (91, 213), (74, 214), (69, 209), (71, 202),
                              (84, 197), (86, 180), (85, 158), (64, 157), (64, 153), (76, 151), (76, 145)],
                             STAGE / 'sprites/typewriter.png', brightness=1.5)
write_json(ASSETS / 'world-model-manifest.json', {
    'pickups': 'original IVM geometry/textures; scaled, ground-normalized and pre-brightened x2',
    'chest': chest, 'typewriter': typewriter,
    'chest_original_file': 'USA/Stage1/RC1181.pak', 'typewriter_original_file': 'USA/Stage1/RC1180.pak',
    'chest_room': 'Types.h ROOM_MANSION_STOREROOM 0x18: under east wing stairs',
    'background_decode': 'Rendering.cpp display_image 0x00470770: red bits0..4, green5..9, blue10..14',
    'world_measurements': world_measurements,
    'limitations': 'Chest body and typewriter have no complete standalone room TMD. Original RC1181/RC1180 '
                   'background pixels are masked billboards, with fixed source perspective.',
    'models': models})
print('World pickups: %d original meshes; chest and typewriter billboards.' % len(models))
