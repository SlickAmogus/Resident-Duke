#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Open the Resident Duke layout editor in Blender (camera shots, stations, Jill's scale)."""
from pathlib import Path
import os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parent
SCENE = ROOT / 'build/editor/scene.json'


def find_blender():
    env = os.environ.get('BLENDER')
    if env and Path(env).is_file():
        return env
    found = shutil.which('blender')
    if found:
        return found
    bases = [Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Blender Foundation',
             Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Blender Foundation']
    for base in bases:
        for exe in sorted(base.glob('Blender*/blender.exe'), reverse=True):
            return str(exe)
    return None


def main():
    if not SCENE.is_file():
        print('Building the game package and editor scene first...', flush=True)
        result = subprocess.run([sys.executable, str(ROOT / 'setup.py'), '--build-only', '--skip-install'], cwd=ROOT)
        if result.returncode or not SCENE.is_file():
            raise RuntimeError('Run play.bat once first so the game files are converted.')
    blender = find_blender()
    if not blender:
        raise RuntimeError('Blender not found. Install Blender 4.x or set the BLENDER environment variable to blender.exe.')
    subprocess.Popen([blender, '--python', str(ROOT / 'tools/blender_editor.py')], cwd=ROOT)
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as e:
        print('Resident Duke editor:', e, file=sys.stderr); sys.exit(1)
