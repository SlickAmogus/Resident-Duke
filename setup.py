#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Import user-owned data and build locally. Never runs a commercial installer."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, struct, subprocess, sys, tarfile, urllib.request, venv, zipfile

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local'
LOCKS = json.loads((ROOT / 'tools/download-lock.json').read_text())
sys.path.insert(0, str(ROOT / 'tools'))
from re_input import index_folder, select_dataset

REQUIRED = json.loads((ROOT / 'tools/required-assets.json').read_text())
GRP = ROOT / 'dependencies/duke3d/duke3d.grp'
EDUKE32 = ROOT / 'dependencies/eduke32' / ('eduke32.exe' if os.name == 'nt' else 'eduke32')
CONVERTERS = ['convert_assets', 'convert_models', 'convert_item_views', 're1_ui_assets', 'world_assets',
              'audio_assets', 'casing_assets', 'pickup_glint', 'death_assets', 'build']


def download(entry):
    target = LOCAL / entry['filename']
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
        print('Downloading verified open-source setup dependency:', entry['filename'], flush=True)
        req = urllib.request.Request(entry['url'], headers={'User-Agent': 'Resident-Duke-local-setup'})
        with urllib.request.urlopen(req, timeout=90) as r:
            blob = r.read()
        if hashlib.sha256(blob).hexdigest() != entry['sha256']:
            raise RuntimeError('Download checksum mismatch; refusing to use ' + entry['filename'])
        target.write_bytes(blob)
    return target


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True); base = destination.resolve()

    def safe(name):
        if '\\' in name or ':' in name: raise RuntimeError('Unsafe archive member')
        if not (base / name).resolve().is_relative_to(base): raise RuntimeError('Archive path escapes setup directory')

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for m in z.infolist():
                safe(m.filename)
                if (m.external_attr >> 16) & 0o170000 == 0o120000: raise RuntimeError('Archive symlink refused')
            z.extractall(destination)
    else:
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                safe(m.name)
                if m.issym() or m.islnk(): raise RuntimeError('Archive links refused')
            t.extractall(destination, filter='data')


def dependency_source():
    dest = ROOT / 'resident-evil-pc-decomp-main'
    if not (dest / 'src/Globals.cpp').exists():
        unpack(download(LOCKS['decomp']), LOCAL / 'decomp-unpack')
        src = LOCAL / 'decomp-unpack' / ('resident-evil-pc-decomp-' + LOCKS['decomp']['commit'])
        shutil.copytree(src, dest, dirs_exist_ok=True)
    # Upstream's license/notices remain beside its locally downloaded source.
    print('RE1 source reference pinned at', LOCKS['decomp']['commit'], flush=True)


def re_source():
    folder = ROOT / 'dependencies/re1'
    if not folder.is_dir(): raise RuntimeError('Missing dependencies/re1/. Put your legally owned RE1 game files there.')
    if folder.is_symlink() or not folder.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError('RE1 input must be a real folder inside this project, not a link to another location')
    index = index_folder(folder); dataset = select_dataset(index, REQUIRED)
    if dataset: return dataset
    missing = 'Data/STATUS.TIM'
    for key in index:
        if key.endswith('data/status.tim'):
            prefix = key[:-len('data/status.tim')]
            missing = next((n.removeprefix('USA/') for n in REQUIRED
                            if prefix + n.removeprefix('USA/').casefold() not in index), 'required classic PC data')
            break
    raise RuntimeError('Missing RE1 game file: ' + missing + '. Copy the installed classic Resident Evil 1 PC game '
                       'folder into dependencies/re1/, not an installer or disc image.')


def import_re(data):
    ref = ROOT / 'assets/reference'; ref.mkdir(parents=True, exist_ok=True)
    print('Importing installed Resident Evil 1 game files.', flush=True)
    for name, path in data.items():
        dest = ref / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    (ROOT / 'assets/extraction-manifest.json').write_text(json.dumps(
        {'method': 'installed game files, inspection restricted to dependencies/re1/', 'files': []}, indent=2) + '\n')


def validate_grp(path):
    from duke_grp import Grp
    grp = Grp(path)
    for name in ('E1L1.MAP', 'GAME.CON', 'DEFS.CON', 'USER.CON'):
        if name not in grp:
            raise RuntimeError('dependencies/duke3d/duke3d.grp lacks ' + name +
                               '. Use the full registered/Atomic Duke Nukem 3D GRP, not shareware.')


def prepare_python(skip):
    if skip:
        import numpy, PIL  # noqa: F401
        return sys.executable
    envdir = LOCAL / 'venv'
    if not envdir.exists():
        try: venv.EnvBuilder(with_pip=True).create(envdir)
        except Exception as e: raise RuntimeError('Python venv support is unavailable. Install Python with venv/pip support, then retry.') from e
    python = envdir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    env = os.environ.copy()
    env.update(PIP_INDEX_URL='https://pypi.org/simple', PIP_EXTRA_INDEX_URL='', PIP_CACHE_DIR=str(LOCAL / 'pip-cache'),
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONNOUSERSITE='1')
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], cwd=ROOT, env=env, check=True)
    return str(python)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-install', action='store_true', help='Use already installed NumPy/Pillow (advanced/offline)')
    parser.add_argument('--build-only', action='store_true', help='Repackage from existing converted assets')
    args = parser.parse_args()
    if sys.version_info < (3, 12): raise RuntimeError('Python 3.12+ is required')
    LOCAL.mkdir(exist_ok=True)
    if not GRP.is_file(): raise RuntimeError('Missing dependencies/duke3d/duke3d.grp. Put your Duke Nukem 3D GRP there.')
    validate_grp(GRP)
    if not EDUKE32.is_file():
        raise RuntimeError('Missing ' + str(EDUKE32.relative_to(ROOT)) + '. Unpack an EDuke32 build into dependencies/eduke32/.')
    python = prepare_python(args.skip_install)
    steps = ['build'] if args.build_only else CONVERTERS
    if not args.build_only:
        # Inspect only the RE1 input folder.
        dataset = re_source()
        dependency_source(); import_re(dataset)
    for name in steps:
        print('Generating locally:', name, flush=True)
        subprocess.run([python, str(ROOT / 'tools' / (name + '.py'))], cwd=ROOT / 'tools', check=True)
    print('\nSetup complete.\nKeep generated game assets private; do not upload the generated package.', flush=True)


if __name__ == '__main__':
    try: main()
    except (Exception, KeyboardInterrupt) as e:
        print('\nSetup failed:', e, file=sys.stderr); sys.exit(1)
