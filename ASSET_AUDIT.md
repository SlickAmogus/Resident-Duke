# Publication audit

| Classification | Material | Publication treatment |
| --- | --- | --- |
| Project-specific work | EDuke32 CON/DEF port, camera and map generators, packager, launchers, controls | Source only; GPL-3.0-only with RE1 derivation attribution |
| RE1 decomp adaptations | Input/movement, aim/fire, menus/inventory/storage/save/death/effects, source-table adapters | Adapted code with source references; upstream source fetched locally, not bundled |
| Capcom proprietary data | Installed RE1 files and everything converted from them (PNG/MD3/WAV, UI, glyphs, animation and message tables) | Excluded; 53 filenames only are listed for local import |
| 3D Realms/Gearbox proprietary data | `duke3d.grp`, its CON files, art, sounds and the generated `E1L1.MAP` variant | Excluded; the map is generated locally from the user's GRP, which is only read |
| Runtime | EDuke32 binaries | Excluded; supplied by the user |
| Private/development material | Logs, saves, screenshots, caches, local config | Ignored by Git |

No image, model, audio, map, executable, archive or generated game-content table is intentionally published. The generated `build/resident-duke.zip` is private local output, not a release asset.
