#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build on first launch, then run the locally generated prototype in EDuke32."""
from pathlib import Path
import os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / 'build/resident-duke.zip'
RUNTIME = ROOT / 'build/runtime'
EXE = ROOT / 'dependencies/eduke32' / ('eduke32.exe' if os.name == 'nt' else 'eduke32')
GRP = ROOT / 'dependencies/duke3d/duke3d.grp'

# First-run EDuke32 configuration: windowed OpenGL (Polymost), the RE slice's
# own menu keys come from controls.cfg (executed as autoexec.cfg every launch).
DEFAULT_CONFIG = """[Setup]
ForceSetup = 0
NoAutoLoad = 1
SelectedGRP = "duke3d.grp"

[Updates]
CheckForUpdates = 0

[Screen Setup]
Polymer = 0
ScreenBPP = 32
ScreenMode = 0
ScreenWidth = 1280
ScreenHeight = 720
"""


def prepare_runtime():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for name in ('logs', 'saves'):
        (ROOT / name).mkdir(exist_ok=True)
    config = RUNTIME / 'eduke32.cfg'
    if not config.exists():
        config.write_text(DEFAULT_CONFIG)
    # Controls are reapplied each launch so EDuke32's saved binds cannot drift.
    shutil.copyfile(ROOT / 'controls.cfg', RUNTIME / 'autoexec.cfg')


# EDuke32 reads files from the package on demand for the whole session, so it
# runs from a private copy: rebuilding build/resident-duke.zip mid-session
# would otherwise corrupt the running game (missing art, crashes).
RUNTIME_PACKAGE = RUNTIME / 'resident-duke.zip'


def snapshot_package():
    try:
        if not RUNTIME_PACKAGE.exists() or RUNTIME_PACKAGE.stat().st_mtime < PACKAGE.stat().st_mtime                 or RUNTIME_PACKAGE.stat().st_size != PACKAGE.stat().st_size:
            temp = RUNTIME_PACKAGE.with_suffix('.tmp')
            shutil.copyfile(PACKAGE, temp); os.replace(temp, RUNTIME_PACKAGE)
    except PermissionError:
        raise RuntimeError('Resident Duke appears to be running already; close it before starting another copy.')


def command(extra):
    return [str(EXE), '-usecwd', '-nosetup', '-j', str(GRP.parent), '-gamegrp', GRP.name, '-g', str(RUNTIME_PACKAGE),
            '-x', 'RDUKE.CON', '-h', 'RDUKE.DEF', '-v1', '-l1', '-s2', *extra]


def main():
    args = sys.argv[1:]
    debug = '--debug' in args
    args = [a for a in args if a != '--debug']
    if not PACKAGE.is_file():
        print('First launch: checking your game files and preparing Resident Duke...', flush=True)
        # Setup checks all three input folders before installing/building.
        result = subprocess.run([sys.executable, str(ROOT / 'setup.py')], cwd=ROOT)
        if result.returncode: return result.returncode
        if not PACKAGE.is_file(): raise RuntimeError('Setup did not create the game build. Check the setup output above.')
    # Repeat launches never inspect RE1 input or rerun setup.
    if not EXE.is_file(): raise RuntimeError('Missing EDuke32; unpack it into dependencies/eduke32/')
    if not GRP.is_file(): raise RuntimeError('Missing dependencies/duke3d/duke3d.grp')
    prepare_runtime()
    snapshot_package()
    # Developer trace (CON addlog lines in build/runtime/eduke32.log).
    marker = RUNTIME / 'resident-duke-debug.bin'
    if debug: marker.write_bytes(bytes([1, 0, 0, 0]))
    else: marker.unlink(missing_ok=True)
    print('Starting Resident Duke...', flush=True)
    with (ROOT / 'logs/launch.log').open('w') as log:
        result = subprocess.run(command(args), cwd=RUNTIME, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode: raise RuntimeError('EDuke32 exited with an error; see logs/launch.log and build/runtime/eduke32.log')
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as e:
        print('Resident Duke:', e, file=sys.stderr); sys.exit(1)
