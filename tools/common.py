# SPDX-License-Identifier: GPL-3.0-only
"""Shared paths, PS1 colour decoding and MD3 writing for the local asset pipeline.

All generated files land in build/stage/, which mirrors the layout of the
packaged EDuke32 mod. Nothing generated is ever written into the source tree.
"""
from pathlib import Path
import json
import struct
import hashlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'assets/reference/USA'
ASSETS = ROOT / 'assets'
STAGE = ROOT / 'build/stage'
DECOMP = ROOT / 'resident-evil-pc-decomp-main'

# One GZDoom map unit in Resident Doom equals 56/1800 RE units. Resident Duke
# keeps the upstream converters' Doom-unit geometry and maps one Doom unit to
# BASE_DOOM_TO_BUILD Build xy units at jill_scale 1.0, which makes Jill as tall
# as Duke's own sprite (~700 xy). tools/e1l1-layout.json's jill_scale enlarges
# Jill, her movement and every RE object together. Build z is 16x finer than xy.
BASE_DOOM_TO_BUILD = 8
RE_TO_DOOM = 56 / 1800
LAYOUT = ROOT / 'tools/e1l1-layout.json'


def load_layout():
    return json.loads(LAYOUT.read_text()) if LAYOUT.exists() else {}


def jill_scale():
    return float(load_layout().get('jill_scale', 1.0))


def md3_def_scale():
    """EDuke32 draws one MD3 unit (after the format's /64) as 10.24 * scale Build
    xy units at xrepeat 64 (mdsprite.cpp: m->scale .01, /1024 world divisor)."""
    return BASE_DOOM_TO_BUILD * jill_scale() / 10.24


def stage(*parts):
    """Return a path inside build/stage, creating its parent folder."""
    path = STAGE.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def rgb555(values, transparent_zero=True):
    """PS1 15-bit colour (red in bits 0..4) to RGBA, as display_image 0x00470770."""
    v = np.asarray(values)
    alpha = np.where(v == 0, 0, 255) if transparent_zero else np.full_like(v, 255)
    return np.stack(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31,
                     ((v >> 10) & 31) * 255 // 31, alpha), axis=-1).astype('uint8')


def write_md3(path, name, points, uv, triangles, frames, skin, frame_bounds=256.0):
    """Write a single-surface MD3. Vertices are model units; the format stores x64.

    Triangles are double-sided. Item meshes keep upstream's axes: their
    original labels read correctly in EDuke32 as they are.
    """
    n = len(points); nt = len(triangles); nf = len(frames)
    ot = 108; os_ = ot + nt * 12; ost = os_ + 68; ox = ost + n * 8; end = ox + nf * n * 8
    surf = bytearray(struct.pack('<4s64s10i', b'IDP3', name.encode()[:63], 0, nf, 1, n, nt, ot, os_, ost, ox, end))
    surf.extend(b''.join(struct.pack('<3i', *t) for t in triangles))
    surf.extend(struct.pack('<64si', skin.encode(), 0))
    surf.extend(b''.join(struct.pack('<2f', *t) for t in uv))
    for frame in frames:
        q = np.clip(np.round(np.asarray(frame) * 64), -32768, 32767).astype(int)
        surf.extend(b''.join(struct.pack('<3hH', *row, 0) for row in q))
    of = 108; ot = of + nf * 56; end = ot + len(surf)
    blob = bytearray(struct.pack('<4si64s9i', b'IDP3', 15, name.encode()[:63], 0, nf, 0, 1, 0, of, ot, ot, end))
    b = frame_bounds
    for i in range(nf):
        blob.extend(struct.pack('<10f16s', -b, -b, -b, b, b, b, 0, 0, 0, b * 1.7, ('frame%d' % i).encode()))
    blob.extend(surf)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(blob)


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def refresh_extraction_manifest():
    """Record hashes of every imported original file (provenance, never published)."""
    p = ASSETS / 'extraction-manifest.json'
    m = json.loads(p.read_text())
    m['files'] = [dict(path=f.relative_to(ROOT).as_posix(), bytes=f.stat().st_size,
                       sha256=hashlib.sha256(f.read_bytes()).hexdigest())
                  for f in sorted((ASSETS / 'reference').rglob('*')) if f.is_file()]
    write_json(p, m)


def save_centered(image, anchor, destination):
    """Pad an RGBA PIL image so `anchor` (x, y) lies at its centre, then save.

    Build draws centre-aligned sprites (cstat 128) about the tile centre, so
    this preserves the original effect origin without per-tile offsets.
    """
    from PIL import Image
    ax, ay = anchor; w, h = image.size
    half_w = max(ax, w - ax); half_h = max(ay, h - ay)
    canvas = Image.new('RGBA', (int(2 * half_w), int(2 * half_h)), (0, 0, 0, 0))
    canvas.paste(image, (int(half_w - ax), int(half_h - ay)))
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
