#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Package the locally converted assets as an EDuke32 mod (build/resident-duke.zip).

Inputs: hand-written CON/DEF in mod/, converted assets in build/stage/, the
user's duke3d.grp (read only). Outputs generated CON/DEF/tables under
build/stage/gen and the final zip. Generated content stays private.
"""
import json
import os
import struct
import zipfile
from pathlib import Path

from common import ROOT, ASSETS, STAGE, md3_def_scale, jill_scale, write_json
from duke_grp import Grp
from re1_item_tables import slice_items
from re1_messages import streams, glyph
import duke_map

GEN = STAGE / 'gen'
PACKAGE = ROOT / 'build/resident-duke.zip'
GRP = ROOT / 'dependencies/duke3d/duke3d.grp'

# ---------------------------------------------------------------------------
# Tile allocation. Duke uses tiles below 6144; EDuke32 allows up to 30464.
# ---------------------------------------------------------------------------
TILE_BASE = 10000


class Tiles:
    def __init__(self, base):
        self.next = base
        self.defines = []      # (name, value)
        self.images = []       # (tile, stage-relative png, centred)

    def image(self, path, define=None):
        tile = self.next; self.next += 1
        self.images.append((tile, path))
        if define:
            self.defines.append((define, tile))
        return tile

    def family(self, define, paths):
        """Contiguous tiles; CON addresses member i as define+i."""
        base = self.next
        for p in paths:
            self.image(p)
        self.defines.append((define, base))
        return base

    def reserve(self, define, count):
        base = self.next; self.next += count
        self.defines.append((define, base))
        return base


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    assert head[:8] == b'\x89PNG\r\n\x1a\n', path
    return struct.unpack('>2I', head[16:24])


def allocate(tiles):
    ui = 'graphics/reui/'
    # Frame parts: only distinct records are cropped (repeats reuse a part).
    tiles.parts = sorted({c['texture'] for c in json.loads((ASSETS / 'ui-manifest.json').read_text())['ordered']})
    tiles.family('RE_T_PART', [ui + 'part%03d.png' % i for i in tiles.parts])
    tiles.family('RE_T_TAB', [ui + 'tab%d.png' % i for i in range(4)])
    tiles.image(ui + 'radio-disabled.png', 'RE_T_RADIO_DISABLED')
    tiles.image(ui + 'tab-cursor.png', 'RE_T_TAB_CURSOR')
    tiles.family('RE_T_CURSOR', [ui + 'cursor%d.png' % i for i in range(2)])
    tiles.image(ui + 'empty.png', 'RE_T_EMPTY')
    tiles.image(ui + 'portrait.png', 'RE_T_PORTRAIT')
    # action-<state>-<count 1..8>-<part 0..3>: index ((state*8)+(count-1))*4+part
    tiles.family('RE_T_ACTIONWIN', [ui + 'action-%s-%d-%d.png' % (s, c, p)
                                   for s in ('open', 'close') for c in range(1, 9) for p in range(4)])
    tiles.family('RE_T_ACTION', [ui + 'action%d.png' % i for i in range(5)])
    tiles.family('RE_T_DIGIT', [ui + 'digit%d.png' % i for i in range(10)])
    tiles.family('RE_T_CONDITION', [ui + 'condition%d.png' % v for v in range(0, 80, 8)])
    # ASCII glyphs 32..126 in white, green and gray variants.
    tiles.family('RE_T_GLYPH', [ui + 'glyph%d.png' % c for c in range(32, 127)])
    tiles.family('RE_T_GLYPH_GREEN', [ui + 'glyph%d-green.png' % c for c in range(32, 127)])
    tiles.family('RE_T_GLYPH_GRAY', [ui + 'glyph%d-gray.png' % c for c in range(32, 127)])
    # Font cells 0..127 addressed by encoded STR stream code.
    tiles.family('RE_T_CODE', [ui + 'code%d.png' % c for c in range(128)])
    tiles.family('RE_T_CODE_GREEN', [ui + 'code%d-green.png' % c for c in range(128)])
    tiles.image(ui + 'arrow.png', 'RE_T_ARROW')
    tiles.family('RE_T_BOXPART', [ui + 'boxpart%d.png' % i for i in range(8)])
    tiles.image(ui + 'box-marker.png', 'RE_T_BOX_MARKER')
    # ECG: wave 0..19, sweep 22..132, trail 15/31 -> ((wave*111)+(sweep-22))*2+(trail==31)
    tiles.family('RE_T_ECG', [ui + 'ecg-%d-%d-%d.png' % (n, s, t)
                             for n in range(20) for s in range(22, 133) for t in (15, 31)])
    tiles.family('RE_T_HEAL', [ui + 'heal%d.png' % s for s in range(84, 176)])
    tiles.image(ui + 'black.png', 'RE_T_BLACK')
    # Flat colours for the original draw_rect/fade calls (not game art).
    tiles.image(ui + 'white.png', 'RE_T_WHITE')
    tiles.image(ui + 'yellow.png', 'RE_T_YELLOW')
    tiles.image(ui + 'typewriter.png', 'RE_T_TYPEWRITER_SCREEN')
    # Inventory icons in RE item id order of the runtime icon table.
    tiles.family('RE_T_ICON', ['graphics/%s.png' % n for n in
                               ('handgun', 'shotgun', 'ribbon', 'ammo', 'shells', 'key', 'herb', 'herb2', 'herb3')])
    death = 'graphics/redeath/'
    tiles.family('RE_T_DEATH_QUAD', [death + 'quad%d.png' % i for i in range(4)])
    tiles.family('RE_T_DEATH_COLUMN', [death + 'column%d.png' % i for i in range(256)])
    tiles.image(death + 'title-branded.png', 'RE_T_TITLE')
    tiles.family('RE_T_TITLE_OPTION', [death + 'title-option%d.png' % i for i in range(3)])
    # World billboards and effects (centre-aligned where noted in CON).
    tiles.image('sprites/chest.png', 'RE_T_CHEST')
    tiles.image('sprites/typewriter.png', 'RE_T_TYPEWRITER')
    tiles.family('RE_T_CASING', ['sprites/casing%02d.png' % i for i in range(16)])
    glints = sorted(p.name for p in (STAGE / 'sprites').glob('glint*.png'))
    tiles.family('RE_T_GLINT', ['sprites/' + g for g in glints])
    tiles.image('sprites/blood.png', 'RE_T_BLOOD')


def write_flat_colours():
    from PIL import Image
    for name, rgb in (('white', (255, 255, 255)), ('yellow', (255, 239, 0))):
        Image.new('RGBA', (64, 64), rgb + (255,)).save(STAGE / 'graphics/reui' / (name + '.png'))


def duke_defines(grp):
    """name -> value from the user's DEFS.CON (tile and sound numbers)."""
    out = {}
    for line in grp.read('DEFS.CON').decode('latin-1').splitlines():
        t = line.split()
        if len(t) >= 3 and t[0].lower() == 'define':
            try: out[t[1]] = int(t[2])
            except ValueError: pass
    return out


def write_actor_stubs(tiles, defs):
    """Bind every pickup model and effect frame tile to its CON actor state."""
    d = dict(tiles.defines)
    lines = ['// Generated by tools/build.py: actor code follows picnum, so each frame tile is bound.']
    for kind in ('CLIP', 'SHELLS', 'SHOTGUN', 'HERB', 'RIBBON', 'KEY'):
        lines.append('useractor notenemy %d 0 state re_pickup_actor enda' % d['RE_T_WORLD_' + kind])
    glints = len([p for p in (STAGE / 'sprites').glob('glint*.png')])
    for i in range(glints):
        lines.append('useractor notenemy %d 0 state re_glint_actor enda' % (d['RE_T_GLINT'] + i))
    for i in range(16):
        lines.append('useractor notenemy %d 0 state re_casing_actor enda' % (d['RE_T_CASING'] + i))
    lines.append('useractor notenemy %d 0 killit enda' % d['RE_T_REMOVED'])
    (GEN / 'actors.con').write_text('\n'.join(lines) + '\n')


def write_tile_defs(tiles):
    lines = ['// Generated by tools/build.py. Original pixels converted locally; do not redistribute.']
    for tile, path in tiles.images:
        w, h = png_size(STAGE / path)
        lines.append('dummytile %d %d %d' % (tile, w, h))
        lines.append('texture %d { pal 0 { file "%s" nocompress nodownsize } }' % (tile, path))
    (GEN / 'tiles.def').write_text('\n'.join(lines) + '\n')


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
JILL_VARIANTS = [('jill.md3', 'RE_T_POSE_ARMED'), ('jill-unarmed.md3', 'RE_T_POSE_UNARMED'),
                 ('jill-shotgun.md3', 'RE_T_POSE_SHOTGUN')]


def model_block(path, skin, scale, frames, surfaces=1, smooth=0.0):
    out = ['model "%s" {' % path, '    scale %.6f shade 0' % scale]
    for s in range(surfaces):
        out.append('    skin { pal 0 surface %d file "%s" nocompress nodownsize }' % (s, skin))
    for name, tile in frames:
        out.append('    frame { name "%s" tile %d smoothduration %.3f }' % (name, tile, smooth))
    out.append('}')
    return '\n'.join(out)


def write_models(tiles):
    blocks = ['// Generated by tools/build.py.']
    first = tiles.next
    manifest = json.loads((ASSETS / 'animation-manifest.json').read_text())
    frames = sum(m['count'] for m in manifest)
    for file, define in JILL_VARIANTS:
        base = tiles.reserve(define, frames)
        # One RE source tick per frame; a short smooth keeps 30 Hz poses fluid.
        blocks.append(model_block('models/jill/' + file, 'models/jill/skin.png', md3_def_scale(),
                                  [('pose%d' % i, base + i) for i in range(frames)], surfaces=15, smooth=0.034))
    # Item viewer models: 65 intro steps each, in convert_item_views order.
    views = json.loads((ASSETS / 'item-view-manifest.json').read_text())
    base = tiles.reserve('RE_T_ITEMVIEW', 65 * len(views))
    for i, view in enumerate(views):
        blocks.append(model_block('models/items/%s.md3' % view['file'], 'models/items/%s.png' % view['file'],
                                  md3_def_scale(), [('frame%d' % s, base + i * 65 + s) for s in range(65)]))
    world = json.loads((ASSETS / 'world-model-manifest.json').read_text())
    for entry in world['models']:
        tile = tiles.reserve('RE_T_WORLD_' + entry['actor'].upper(), 1)
        blocks.append(model_block(entry['model'], entry['skin'], md3_def_scale(), [('frame0', tile)]))
    # Model tiles need a nonzero size so sprites using them are not culled.
    tiles.reserve('RE_T_REMOVED', 1)  # runtime-spawned Duke pickups with no RE counterpart
    dummy = ['dummytilerange %d %d 64 64' % (first, tiles.next - 1)]
    (GEN / 'models.def').write_text('\n'.join(dummy + blocks) + '\n')
    return frames, views


# ---------------------------------------------------------------------------
# Tables: int32 arrays loaded with readarrayfromfile.
# ---------------------------------------------------------------------------
class Tables:
    def __init__(self):
        self.arrays = {}
        self.constants = []

    def add(self, name, values):
        values = [int(v) for v in values]
        assert values, name
        self.arrays[name] = values

    def const(self, name, value):
        self.constants.append((name, int(value)))

    def write(self, quote_base=9000):
        (GEN / 'tables').mkdir(parents=True, exist_ok=True)
        decl = ['// Generated by tools/build.py: table arrays filled from gen/tables/*.bin.']
        load = ['defstate re_load_tables']
        for i, (name, values) in enumerate(sorted(self.arrays.items())):
            (GEN / 'tables' / (name + '.bin')).write_bytes(struct.pack('<%di' % len(values), *values))
            decl.append('gamearray %s %d' % (name, len(values)))
            decl.append('definequote %d gen/tables/%s.bin' % (quote_base + i, name))
            load.append('    readarrayfromfile %s %d' % (name, quote_base + i))
        load.append('ends')
        return decl, load


def text_codes(text):
    """ASCII text as glyph-code sequence terminated by -1 (newline = 10)."""
    return [ord(c) if c != '\n' else 10 for c in text] + [-1]


def build_tables(tables, frames, views, parts):
    anim = json.loads((ASSETS / 'animation-manifest.json').read_text())
    for bank, prefix in [('W12', 'ANIM_ARMED'), ('W10', 'ANIM_UNARMED'), ('BODY', 'ANIM_BODY'), ('W13', 'ANIM_SHOTGUN')]:
        motions = [m for m in anim if m['bank'] == bank]
        tables.add(prefix + '_START', [m['first'] for m in motions])
        tables.add(prefix + '_COUNT', [m['count'] for m in motions])
    tables.add('ANIM_TIMING', [t for m in anim for t in m['timings']])

    ui = json.loads((ASSETS / 'ui-manifest.json').read_text())
    o = ui['ordered']
    for key in ('x', 'y', 'w', 'h'):
        tables.add('UI_FRAME_' + key.upper(), [c[key] for c in o])
    tables.add('UI_FRAME_PART', [parts.index(c['texture']) for c in o])
    tables.const('RE_UI_FRAMES', len(o))
    tables.add('UI_SLOT_X', [s[0] for s in ui['slots']]); tables.add('UI_SLOT_Y', [s[1] for s in ui['slots']])
    for key in ('x', 'y', 'w', 'h'):
        tables.add('UI_BOX_' + key.upper(), [b[key] for b in ui['box']])
    for i, key in enumerate(('X', 'Y', 'W', 'H')):
        tables.add('UI_MASK_' + key, [m[i] for m in ui['masks']])

    data = slice_items()
    items = data['items']
    tables.add('ITEM_ID', [it['id'] for it in items])
    tables.add('ITEM_HEAL', [it['heal'] for it in items])
    tables.add('ITEM_MAX', [it['max'] for it in items])
    tables.add('ITEM_EXAMINE_FLAG', [it['examine_flag'] for it in items])
    # Icon order matches RE_T_ICON family; view order matches item-view manifest.
    icon_order = [2, 3, 47, 11, 12, 0x33, 0x44, 0x47, 0x4a]
    view_order = [v['item'] for v in views]
    tables.add('ITEM_ICON', [icon_order.index(it['id']) for it in items])
    tables.add('ITEM_VIEW', [view_order.index(it['id']) for it in items])
    recipes = data['recipes']
    for n, key in enumerate(('A', 'B', 'NEWA', 'NEWB', 'EFFECT')):
        tables.add('RECIPE_' + key, [r[n] for r in recipes])
    tables.const('RE_RECIPES', len(recipes))
    tables.const('RE_ITEM_KINDS', len(items))

    # Strings: names/unknown names/descriptions plus fixed UI strings.
    pool = []; starts = {}

    def string(key, text):
        starts[key] = len(pool); pool.extend(text_codes(text))

    for it in items:
        string('name%d' % it['id'], it['name'])
        string('unknown%d' % it['id'], it['unknown_name'])
        string('desc%d' % it['id'], it['description'])
    for key, text in FIXED_STRINGS.items():
        string(key, text)
    tables.add('TEXT', pool)
    tables.add('ITEM_NAME_TEXT', [starts['name%d' % it['id']] for it in items])
    tables.add('ITEM_UNKNOWN_TEXT', [starts['unknown%d' % it['id']] for it in items])
    tables.add('ITEM_DESC_TEXT', [starts['desc%d' % it['id']] for it in items])
    for key in FIXED_STRINGS:
        tables.const('RE_STR_' + key.upper(), starts[key])

    # Original STR message streams (PrintText.h codes).
    msg = streams(); data_bytes = []; offs = []; lens = []; ids = []
    for gid, stream in msg:
        ids.append(gid); offs.append(len(data_bytes)); lens.append(len(stream)); data_bytes.extend(stream)
    tables.add('MSG_ID', ids); tables.add('MSG_START', offs); tables.add('MSG_LENGTH', lens); tables.add('MSG_BYTES', data_bytes)
    tables.const('RE_MESSAGES', len(ids))
    # ASCII -> STR glyph code (for item names inserted into streams).
    tables.add('ASCII_TO_CODE', [glyph(chr(c)) if 32 <= c < 127 else 27 for c in range(128)])

    casing = json.loads((ASSETS / 'casing-manifest.json').read_text())
    tables.add('CASING_HEADER', casing['headers']); tables.add('CASING_FRAME', casing['frames'])


FIXED_STRINGS = {
    'yesno': 'Yes  No',
    'save_title': 'SAVE GAME',
    'save_empty': '-----\\--\\  -----------------',
    'save_cancel': 'DO NOT SAVE',
    'save_overwrite': 'OK TO OVERWRITE THE DATA?',
    'save_yes_no': ' YES  NO ',
    'nothing': ' Nothing ',
    'cant_carry': "You can't carry any more\nitems.",
    'locked': "It's locked. A carving of a sword.",
    'take': 'Will you take the ',
    'take_end': '?',
    'move': 'Will you move the items?',
    'cant_mix': "You can't mix these herbs.",
    'save_only': 'Use a typewriter to save.',
    # Typewriter rows: "JILL \03\  HOLLYWOOD" (upstream: HANGAR for E1M1).
    'save_row': 'JILL \\',
    'save_row_end': '\\  HOLLYWOOD',
}


def write_con(tiles, tables, frames):
    decl, load = tables.write()
    lines = ['// Generated by tools/build.py. Constants for tiles, tables and map data.']
    lines += ['define %s %d' % (n, v) for n, v in tiles.defines]
    lines += ['define %s %d' % (n, v) for n, v in tables.constants]
    lines.append('define RE_POSE_FRAMES %d' % frames)
    # RE units -> Build xy = 56/1800 * 8 * jill_scale = (224 * jill_scale) / 900.
    lines.append('define RE_XY_NUM %d' % round(224 * jill_scale()))
    lines.append('define RE_XY_DEN 900')
    lines.append('define RE_SCALE_PCT %d' % round(100 * jill_scale()))
    lines += decl
    (GEN / 'data.con').write_text('\n'.join(lines) + '\n')
    (GEN / 'tables.con').write_text('\n'.join(load) + '\n')


def package():
    PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    temp = PACKAGE.with_suffix('.%d.tmp' % os.getpid())
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
        for base in (ROOT / 'mod', STAGE):
            for f in sorted(base.rglob('*')):
                if f.is_file():
                    z.write(f, f.relative_to(base).as_posix())
    os.replace(temp, PACKAGE)
    print(PACKAGE)


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    write_flat_colours()
    tiles = Tiles(TILE_BASE); tables = Tables()
    allocate(tiles)
    write_tile_defs(tiles)
    frames, views = write_models(tiles)
    build_tables(tables, frames, views, tiles.parts)
    grp = Grp(GRP)
    defs = duke_defines(grp)
    tiles.defines.append(('RE_T_DUKE_LOGO', defs['DUKENUKEM']))
    voice = sorted(v for k, v in defs.items() if k.startswith('DUKE_') or k.startswith('JIBBED_ACTOR'))
    tables.add('DUKE_VOICE', voice); tables.const('RE_DUKE_VOICE_COUNT', len(voice))
    duke_map.generate(grp, tables, tiles)
    write_actor_stubs(tiles, defs)
    write_con(tiles, tables, frames)
    write_json(ASSETS / 'tile-allocation.json', dict(tiles.defines))
    package()
    # Scene for the Blender layout editor (edit_layout.bat); never packaged.
    import editor_export
    editor_export.main()


if __name__ == '__main__':
    main()
