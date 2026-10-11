# Technical information

Resident Duke keeps Resident Doom's architecture: user-supplied game data, local Python converters, and a thin runtime port of the RE1 decomp's gameplay. The runtime is now EDuke32 CON/DEF instead of GZDoom ZScript.

## Layout

| Path | Contents |
| --- | --- |
| `mod/RDUKE.CON`, `mod/scripts/*.con` | Hand-written gameplay port: Jill's state machine, inventory, prompts, status screen, item box, typewriter, death/title, casings, cameras, presentation. |
| `mod/RDUKE.DEF` | Includes the generated tile and model definitions. |
| `tools/*.py` | Converters for the RE1 data (TIM/PIX/EMD/EMW/IVM/RDT/ESP/WAV), map generation, camera generation, the packager (`build.py`) and a CON linter. |
| `build/stage/` | Everything generated locally (art, models, sounds, tables, `E1L1.MAP`, generated CON/DEF). Never committed. |
| `build/resident-duke.zip` | The package EDuke32 loads with `-g`. |
| `build/runtime/` | EDuke32's config, saves, screenshots and log. |

## How upstream mechanisms map to EDuke32

- **Jill's model.**
  - Every original skeletal frame (778 per weapon set) is baked into an MD3 frame and mapped to its own tile.
  - EDuke32's model frame smoothing stands in for upstream's live Joint_move joint blending; frame choice and timing are unchanged.
  - Jill is a model sprite that follows the hidden Duke player, who still provides collision, gravity, stairs, teleporters and damage.
- **Tank movement.**
  - Fixed RE turn increments and walk/run/backstep speeds are applied once per Duke game tic. One tic is 33.3 ms, against RE's 33 ms source tick.
  - Movement uses Build's `clipmove`, which slides along walls; upstream retried each axis separately.
  - Duke's own movement, turning, weapons, HUD and voice are suppressed.
- **Fixed cameras.**
  - `tools/duke_cameras.py` splits each E1L1 sector into 4096-unit zones. For each zone it picks a static shot by testing Build `cansee()` visibility from candidate positions around it.
  - At runtime a shot is kept while it still frames Jill. The camera cuts to her zone's shot when she leaves its view, its field of view or its framing distance.
  - Upstream hand-authored E1M1 camera zones. Per-zone overrides can be added in `tools/e1l1-cameras.json`.
- **World freeze.**
  - RE menus freeze the world. EDuke32's pause would also stop the input event that drives those menus.
  - Instead, active status lists (actors, projectiles, effectors…) are parked on unused status numbers while a menu is open.
- **Item viewer and death scene.**
  - These are rendered with `showview` from an unreachable black sector appended to the map, the same idea as upstream's camera-texture scene sector.
  - View distances are scaled by the RE focal length ratio.
- **UI.**
  - Original 320x240 art is drawn with `rotatesprite` at native RE pixel coordinates, scaled uniformly and centred.
  - Tables from the decomp are loaded from generated binary arrays.
- **Damage.**
  - Hits from Duke enemies are doubled, matching upstream's balance for Doom monsters; hazards and explosions are unchanged.
  - Duke's own death never triggers. Jill's RE death sequence runs instead.
- **Saves.** Typewriters write native EDuke32 saves. The eight RE rows persist in a small table file.

## E1L1 changes

The original geometry, enemies and effectors are kept. Duke pickups become RE pickups at the same positions:

| Duke pickup | RE item |
| --- | --- |
| Pistol ammo | Handgun clip |
| Shotgun ammo | Shells |
| First shotgun | Shotgun (later shotguns become shells) |
| Health items | Green herbs |
| Holodukes | Ink ribbons |
| Red access card | Sword key |

Items with no RE counterpart are removed. Enemy drops are converted the same way at runtime.

The sword key operates E1L1's red access switch. The item box, a typewriter and an ink ribbon are placed in Jill's opening shot on the roof.

**Explosive objects.** E1L1 is entered by shooting the explosive charge beside the roof vent. RE auto-aim therefore also targets Duke's explosive objects (charges, barrels, extinguishers) when no enemy is in view, and aims each shot at its target's middle.

## Known gaps

- **Animation blending:** Joint_move blend weights are approximated by engine frame smoothing.
- **Item box lid:** the lid animation is not reproduced, as upstream.
- **Free rotation:** free examination rotation in the item viewer is not implemented, as upstream.
- **Typewriter rows:** rows are not tied one-to-one to EDuke32 save files. Load through EDuke32's list.
- **Death music fade:** RE's music fade on death is replaced by stopping the music, because CON has no music volume control.
- **Cameras:** generated cameras can produce awkward shots in tight vents or steep spaces.
