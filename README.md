# Resident Duke

A fork of Drelvak's [Resident Doom](https://github.com/Drelvak/Resident-Doom) that puts Resident Evil 1's Jill Valentine and RE1 PC gameplay inside **Duke Nukem 3D**, running on **EDuke32**. You start on the rooftop of E1L1 *Hollywood Holocaust*, exactly where Duke does.

The RE1 mechanics are ported from Resident Doom's ZScript, which adapts the [RE1 PC decomp](https://github.com/ecruells/resident-evil-pc-decomp), into EDuke32's CON scripting. You get:

- tank controls;
- fixed camera angles;
- the original status screen, item box and item viewer;
- limited saves at typewriters with ink ribbons;
- herb mixing;
- Jill's original model and animations;
- the original death and title screens.

## What you need

- Duke Nukem 3D: the registered or Atomic `duke3d.grp`.
- Resident Evil 1 PC, the classic USA release. Only the GOG version has been tested.
- [EDuke32](https://www.eduke32.com/), tested with r10652 for Windows.
- Python 3.12+.

## Setup

Download and extract this project, then:

1. Put your **`duke3d.grp`** in **`dependencies/duke3d/`**.
2. **Install Resident Evil 1 normally, then copy the installed game files into `dependencies/re1/`.**
3. Unpack EDuke32 so that **`eduke32.exe`** sits in **`dependencies/eduke32/`**.

**Windows:** double-click `play.bat`.

**Linux:** run `sh play.sh`.

The first launch converts your game files locally, which takes a few minutes. Later launches start immediately.

## Controls

The controls follow the RE1 PC layout:

- **Arrows/WASD:** move and turn.
- **X:** aim.
- **C/Space/Enter:** interact, fire or confirm.
- **V/Shift:** run or cancel.
- **Tab/Z/I:** status screen.
- **Escape:** EDuke32 menu, for loading, options and quitting.

## Layout editor (Blender)

`edit_layout.bat` (or `python edit_layout.py`) opens E1L1 in Blender 4.x with Duke's textures. The scene contains:

- every generated fixed camera shot;
- the item box, typewriter and ink ribbon;
- a reference Jill.

To edit the layout:

1. Select a camera and press Numpad 0 to see the shot.
2. Move or rotate cameras and stations, or change *Jill scale* in the **Resident Duke** sidebar tab (press N).
3. Press **Save and rebuild game**.

Your changes are kept in `tools/e1l1-layout.json`.

## The opening

Duke's way off the roof works for Jill too. Aim at the explosive charge by the air vent and shoot it from a safe distance, then walk into the opened shaft. The drop through the ductwork plays as a black RE-style room transition, and you land in the street below.

## Limitations

- **One level:** only E1L1 is supported, and finishing it starts E1L1 again, as upstream loops E1M1.
- **Generated cameras:** cameras are computed from the map's geometry rather than hand-placed.
- **Your own data:** original game files are required and are not included. You must provide your own legally obtained copies.

[Setup & troubleshooting](docs/SETUP.md) · [Technical information](docs/TECHNICAL.md) · [Licenses & credits](docs/LICENSES.md) · [Contributing](CONTRIBUTING.md)
