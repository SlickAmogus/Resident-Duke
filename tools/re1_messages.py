# SPDX-License-Identifier: GPL-3.0-only
"""Compile the slice's original STR message streams using PrintText.h encoding."""
import json
import re
from common import DECOMP

PUNCT = {' ': 0, '!': 26, '"': 25, ',': 24, '.': 121, ':': 22, ';': 23, '?': 27, "'": 58,
         '(': 55, ')': 57, '-': 59, '/': 56, '\\': 56}
# Global messages used by pickups, the sword key, herbs and the typewriter.
MESSAGE_IDS = (0, 2, 3, 7, 30, 31, 53)


def glyph(ch):
    """STR pft_encode_char: font cell index for one printable character."""
    if 'A' <= ch <= 'Z': return ord(ch) - 65 + 29
    if 'a' <= ch <= 'z': return ord(ch) - 97 + 61
    if '0' <= ch <= '9': return ord(ch) - 48 + 12
    return PUNCT.get(ch, 27)


def encode(text):
    out = []; i = 0
    while i < len(text):
        ch = text[i]; i += 1
        if ch == '\\':
            code = text[i]; i += 1
            if code == 'i': out.extend([5, 1, 6, 0, 5, 0]); continue
            if code == 'x': out.append(int(text[i:i + 2], 16)); i += 2; continue
            out.append({'n': 2, 'p': 3, 'c': 8, 'q': 10}[code]); continue
        out.append(glyph(ch))
    return out + [1, 0]


def streams():
    """Return [(global message id, encoded byte stream)] for the slice."""
    src = (DECOMP / 'src/Globals.cpp').read_text()
    result = []
    for n in MESSAGE_IDS:
        raw = re.search(r's_gm%02d = STR\("(.*?)"\);' % n, src)[1]
        result.append((n, encode(json.loads('"' + raw + '"'))))
    return result
