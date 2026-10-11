# Third-party provenance and notices

## Resident Doom (upstream) - GPL-3.0-only

Source: https://github.com/Drelvak/Resident-Doom (this repository's history is preserved).

Resident Duke is a fork. Upstream's ZScript gameplay port, its Python converters and its RE1-derived tables were adapted to EDuke32 CON/DEF. Copyright in upstream contributions remains with Drelvak and contributors.

## Resident Evil PC decomp - GPLv3

Source: https://github.com/ecruells/resident-evil-pc-decomp
Pinned setup reference: `15004914527567a2b9cecf34997abe8c252bcbf9`.

The gameplay, menu and effect logic under `mod/scripts/`, plus the mathematical and table adapters under `tools/`, adapt or trace this source through upstream's port. Source address and function comments retain traceability. The downloaded source keeps its own LICENSE and notices; it is not part of the published file set.

The GPL grant covers code contributions, **not** Capcom game content. Upstream relies on lawful reverse engineering and fair-use reasoning.

## EDuke32 - external runtime

https://www.eduke32.com/ - GPLv2 together with the Build engine license (Ken Silverman). No engine binary or engine source is distributed here. CON/DEF scripts use EDuke32's public scripting interfaces.

## NumPy and Pillow - local Python dependencies

https://numpy.org/doc/stable/license.html - BSD-3-Clause.
https://github.com/python-pillow/Pillow/blob/main/LICENSE - Pillow/HPND-style license and listed components.

Both are installed into `.local/venv/` and are not distributed with this source release.
