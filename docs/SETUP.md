# Detailed setup and troubleshooting

## Before you start

Download the project ZIP and extract it into a writable folder. You need:

- your own registered or Atomic **Duke Nukem 3D** GRP;
- the **original classic USA Resident Evil 1 PC** game;
- an **EDuke32** build;
- **Python 3.12+** with pip/venv support. Windows users should install the Python launcher if offered.

The RE1 HD Remaster and other-language/console editions are not supported.

First setup needs internet access. It downloads a checksum-pinned RE1 decomp source reference, and installs NumPy and Pillow into a virtual environment inside this project. It does not install software system-wide.

## The three drop folders

- **`dependencies/duke3d/duke3d.grp`**: your Duke Nukem 3D GRP. It must contain `E1L1.MAP`, `GAME.CON`, `DEFS.CON` and `USER.CON`; shareware lacks these. The GRP is only read. The playable map is generated from it into the local package.
- **`dependencies/re1/`**: install Resident Evil 1 normally, then copy or drag the installed game files here.
  - The folder can contain `USA/`, or the contents of `USA/`.
  - Filenames are matched case-insensitively.
  - Only this folder is inspected.
- **`dependencies/eduke32/`**: unpack an EDuke32 build here so that `eduke32.exe` (Linux: `eduke32`) sits directly in the folder.
  - Tested with r10652.
  - The OpenGL renderer (Polymost, EDuke32's default) is required, because Jill and the RE items are 3D models.

Setup imports only the [53 required RE1 files](../tools/required-assets.json), converts them, generates the E1L1 variant and its camera tables, and packages `build/resident-duke.zip`. Converting and choosing cameras takes a few minutes.

## Run

**Windows:** double-click `play.bat`.

**Linux:** open a terminal in the project folder and run `sh play.sh`.

EDuke32 runs with its configuration, saves and logs inside `build/runtime/`. The first run opens a 1280x720 window; change the resolution or switch to fullscreen in EDuke32's options. Key bindings are reapplied from `controls.cfg` at every launch.

`python play.py --debug` additionally writes a developer trace (position, input and behaviour state) to `build/runtime/eduke32.log`.

## Saving and loading

Saving is done at typewriters only and spends one ink ribbon, as in RE1. The native save menu refuses with "Use a typewriter to save."

Each typewriter save writes an ordinary EDuke32 save. Load it from EDuke32's menu (Escape, then Load Game), or choose *Continue* on the death screen. The eight typewriter rows and their counters are kept in `build/runtime/resident-duke-typewriter.bin`.

## Layout and scale

`tools/e1l1-layout.json` holds hand tuning that survives rebuilds:

- `jill_scale`: default 1.5. It scales Jill, her movement and the RE objects together.
- Station positions.
- Per-zone camera shots.

Edit it with the Blender editor (`edit_layout.bat`) or by hand, then rebuild with `python setup.py --build-only`. The game always runs from its own copy of the package, so rebuilding while it runs is safe; restart the game to see the changes.

## Rebuilding

- **Repackage after editing scripts:** `python setup.py --build-only` repackages from the existing converted assets.
- **Full conversion:** `python setup.py` reruns the whole conversion.
- **Checking scripts:** `python tools/con_lint.py` checks the CON scripts for shared scratch variables that a nested state call could overwrite.

## If something is missing

- **Missing GRP:** place `duke3d.grp` in `dependencies/duke3d/`.
- **Missing EDuke32:** put `eduke32.exe` and its DLLs directly in `dependencies/eduke32/`.
- **Missing RE1 file:** copy the entire installed classic PC game folder into `dependencies/re1/`. The error names the missing file.
- **Python missing:** install Python 3.12+ with pip/venv support, then run Play again.
- **Game launch error:** see `logs/launch.log` and `build/runtime/eduke32.log`.

Do not redistribute the generated package or imported game data.
