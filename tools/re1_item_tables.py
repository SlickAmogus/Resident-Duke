# SPDX-License-Identifier: GPL-3.0-only
"""Read the normal USA item tables from the supplied decomp, without evaluating C++."""
import re
from common import DECOMP

# Items represented in this slice: handgun, shotgun, clip, shells, ink ribbon,
# sword key, green herb, G+G herb and G+G+G herb.
SUPPORTED = (2, 3, 11, 12, 47, 0x33, 0x44, 0x47, 0x4a)


def array(source, name):
    match = re.search(r'\b' + name + r'\s*\[.*?\]\s*=\s*\{(.*?)\};', source, re.S)
    if not match:
        raise ValueError(f'Missing source table: {name}')
    body = re.sub(r'//[^\n]*', '', match[1])
    return [int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]+)', body)]


def read_tables():
    base = DECOMP / 'src'
    globals_source = (base / 'Globals.cpp').read_text()
    menu_source = (base / 'game/MenuData.cpp').read_text()
    lookup = array(globals_source, 'g_ItemImageLookupTable')
    heal = array(menu_source, 'g_ItemHealTable')
    maximum = array(menu_source, 'g_ItemMaxQty')
    data = array(menu_source, 'g_ItemCombineData')
    image_types = array(menu_source, 'g_ItemImageTypeTable')
    ptr = re.search(r'g_ItemCombinePtrs\s*\[.*?\]\s*=\s*\{(.*?)\};', menu_source, re.S)[1]
    offsets = [int(x) for x in re.findall(r'g_ItemCombineData\s*\+\s*(\d+)', ptr)]
    recipes = []
    for item in SUPPORTED:
        table_index = lookup[item * 4 + 1]
        if table_index >= len(offsets):
            continue  # 0x80 sentinel: no combine table for this item.
        offset = offsets[table_index]
        for n in range(data[offset]):
            other, new_a, new_b, effect = data[offset + 1 + n * 4:offset + 5 + n * 4]
            if other in SUPPORTED:
                assert new_a in (*SUPPORTED, 0) and new_b in (*SUPPORTED, 0)
                recipes.append((item, other, new_a, new_b, effect))
    return dict(ids=SUPPORTED, heal=[heal[i] & 15 for i in SUPPORTED],
                maximum=[maximum[i * 4] for i in SUPPORTED], recipes=recipes,
                lookup=lookup, image_types=image_types)


def slice_items():
    """Everything the runtime needs about the supported items, as plain data."""
    tables = read_tables()
    globals_source = (DECOMP / 'src/Globals.cpp').read_text()
    menu_source = (DECOMP / 'src/game/MenuData.cpp').read_text()
    strings = {name: value.replace(r'\\n', '\n').replace(r'\n', '\n')
               for name, value in re.findall(r'static constexpr auto (s_idesc\d+) = STR\("(.*?)"\);', globals_source)}
    ptrs = re.search(r'g_ItemDescriptions\s*\[.*?\]\s*=\s*\{(.*?)\};', globals_source, re.S)
    if ptrs is None:
        raise ValueError('Missing original item description pointers')
    refs = re.findall(r'\(unsigned char\*\)(s_idesc\d+)\.bytes', ptrs[1])
    # Rendering.cpp message_item_name_lookup selects the generic category until
    # the corresponding original examination flag is set.
    names = {name: value.replace(r'\x07', '')
             for name, value in re.findall(r'static constexpr auto (s_item\w+)\s*= STR\("(.*?)"\);', menu_source)}

    def pointers(table):
        body = re.search(r'\b' + table + r'\s*\[.*?\]\s*=\s*\{(.*?)\};', menu_source, re.S)[1]
        return re.findall(r'\(unsigned char\*\)(s_item\w+)\.bytes', body)

    known = pointers('g_ItemNamePointers'); unknown = pointers('g_UnknownItemNamePointers')
    items = []
    for i, item in enumerate(SUPPORTED):
        flag = tables['lookup'][item * 4 + 2]
        items.append(dict(id=item, heal=tables['heal'][i], max=tables['maximum'][i], examine_flag=flag,
                          name=names[known[item - 1]],
                          unknown_name=names[unknown[flag]] if flag < 128 else names[known[item - 1]],
                          description=strings[refs[item - 1]]))
    return dict(items=items, recipes=tables['recipes'])
