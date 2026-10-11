#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Developer check for the mod's CON: scratch registers read after a nested
`state` call that may overwrite them.

CON states take no parameters, so the scripts pass values through shared
scratch variables (re_a, re_tmp, ...). A caller that keeps a value in one of
them across `state X` silently breaks when X (or anything X calls) writes it.
This is a linear, flow-insensitive scan: it can over-report, never misses a
direct clobber. Run: python tools/con_lint.py
"""
import re
import sys
from pathlib import Path

SCRATCH = {'re_a', 're_b', 're_c', 're_d', 're_tmp', 're_tmp2', 're_tmp3', 're_i', 're_j', 're_k',
           're_px', 're_py', 're_pz', 're_psect'}
# Commands whose first operand is written.
WRITE_FIRST = {'set', 'add', 'sub', 'mul', 'div', 'mod', 'and', 'or', 'xor', 'shiftl', 'shiftr', 'rand', 'randvar',
               'setvar', 'addvar', 'ldist', 'dist', 'getangle', 'getincangle', 'calchypotenuse', 'sqrt', 'sin', 'cos',
               'for'}
WRITE_LAST = {'cansee'}  # result is the 9th operand
SCRIPTS = Path(__file__).resolve().parents[1] / 'mod/scripts'


def tokens(text):
    """Tokens with line numbers; a line ending in "// lint: ok" is skipped
    (used where branch structure makes a linear-scan report a false alarm)."""
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        if line.rstrip().endswith('// lint: ok'):
            continue
        line = line.split('//')[0]
        for t in re.findall(r'[A-Za-z_][\w.\[\]]*|-?\d+|\{|\}', line):
            out.append((t, ln))
    return out


def parse(files):
    states = {}
    for f in files:
        toks = tokens(f.read_text())
        i = 0
        while i < len(toks):
            if toks[i][0] == 'defstate':
                name = toks[i + 1][0]; j = i + 2; body = []
                while toks[j][0] != 'ends':
                    body.append(toks[j]); j += 1
                states[name] = (f.name, body); i = j
            i += 1
    return states


def writes(body):
    w = set(); calls = set()
    for k, (t, _) in enumerate(body):
        base = t.split('[')[0]
        if base in WRITE_FIRST and k + 1 < len(body) and body[k + 1][0] in SCRATCH:
            w.add(body[k + 1][0])
        if t.startswith('get') and '.' in t:
            # getactor[x].field VAR -> VAR written
            if k + 1 < len(body) and body[k + 1][0] in SCRATCH: w.add(body[k + 1][0])
        if base in WRITE_LAST:
            # cansee x y z s x y z s RESULT
            if k + 9 < len(body) and body[k + 9][0] in SCRATCH: w.add(body[k + 9][0])
        if t == 'state' and k + 1 < len(body): calls.add(body[k + 1][0])
        if t == 'for' and k + 1 < len(body) and body[k + 1][0] in SCRATCH: w.add(body[k + 1][0])
    return w, calls


def main():
    states = parse(sorted(SCRIPTS.glob('*.con')))
    direct = {n: writes(b) for n, (_, b) in states.items()}
    closure = {}

    def clob(n, seen=()):
        if n in closure: return closure[n]
        if n not in direct or n in seen: return set()
        w, calls = direct[n]; out = set(w)
        for c in calls: out |= clob(c, seen + (n,))
        closure[n] = out; return out

    problems = 0
    for name, (fname, body) in states.items():
        clobbered = {}
        for k, (t, ln) in enumerate(body):
            if t == 'state' and k + 1 < len(body):
                for v in clob(body[k + 1][0]): clobbered[v] = body[k + 1][0]
                continue
            if k > 0 and body[k - 1][0] == 'state': continue
            v = t.split('[')[0]
            inner = re.findall(r'\[(\w+)\]', t)
            reads = ([v] if v in SCRATCH else []) + [x for x in inner if x in SCRATCH]
            prev = body[k - 1][0].split('[')[0] if k else ''
            written_here = v in SCRATCH and (prev in WRITE_FIRST and prev not in ('add', 'sub', 'mul', 'div', 'mod', 'and', 'or', 'xor', 'shiftl', 'shiftr')
                                              or (prev.startswith('get') and '.' in body[k - 1][0]))
            for r in reads:
                if r in clobbered and not (written_here and r == v):
                    print('%s:%d %s reads %s after state %s may overwrite it' % (fname, ln, name, r, clobbered[r]))
                    problems += 1; clobbered.pop(r)
            if written_here: clobbered.pop(v, None)
    print('%d possible clobbers' % problems)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
