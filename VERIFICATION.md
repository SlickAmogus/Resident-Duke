# Verification notes

Checked on Windows 11 with EDuke32 r10652 (32-bit, OpenGL/Polymost), the GOG classic RE1 USA data and an Atomic-era `duke3d.grp`:

- **Setup:** setup imported all 53 required RE1 files, converted them, generated E1L1 and 500 zone cameras, and packaged the mod.
- **Compilation:** the CON compiles with 0 errors, and `tools/con_lint.py` reports no scratch-variable clobbers.
- **Title and start:** the RE1 title screen appears, then Jill starts on the E1L1 rooftop in a fixed camera shot.
- **Movement:** tank movement and turning run at RE speeds. Jill's model faces her heading and holds the Beretta in her right hand.
- **Pickups and saving:** the ink ribbon pickup shows the 3D item view and the original prompt. The typewriter flow spends a ribbon, writes a native save and plays the row reveal; typewriter rows persist between launches.
- **Menus:** the status screen and the item box store and retrieve items.
- **Opening route:** shooting the rooftop charge opens the vent, and the shaft drop teleports Jill to the street.
- **Combat:** the aim/fire behaviours killed an Assault Trooper with handgun fire.
- **Death:** lethal damage plays the RE death sequence (flash, YOU DIED) and returns to the title.
- **After death:** NEW GAME restarts E1L1, and LOAD GAME restores the session's typewriter save.
- **Herbs:** a green herb is picked up and used from the status screen. It heals a third of 96 HP, and the ECG changes from Danger to Fine with the heal sweep.
- **Shotgun:** the shotgun is equipped from the status screen. It fires 7 shells on the original fire frames, reloads from shells when empty, and the shell count is displayed.
- **Herb mixing:** two green herbs mix into MIXED HERBS through the original prompt.
- **Status button:** the status button closes the screen from any status sub-state.
- **Sword key:** at the red access switch the key shows "You have used the MANSION KEY." and "This key is useless now. Discard?", and Duke's switch then operates. Tested from a developer start at the switch (debug level 5); the walk there was not tested.
- **Screen flashes:** Duke's red damage flashes and first-person hands are suppressed.
- **Overwrite prompt:** re-saving to a used typewriter row asks OK TO OVERWRITE THE DATA?

Developer aids used for these checks:

- `python play.py --debug` writes a trace to the log.
- Debug levels 2, 3, 4 and 5 give a low-health start, invulnerability, a shotgun/herb kit, and a start at the red switch with the sword key. They are set through the `resident-duke-debug.bin` marker and are off in normal play.

Not yet exercised end to end:

- **Sword key route:** walking from the street to the sword key and the switch, including doors and the elevator.
- **Shell casings:** casing effects, checked only in code; screenshots are too small to judge them.
- **Fresh-session load:** the death screen's LOAD GAME, without a save from the current session, falls back to EDuke32's load menu. This path is untested.
- **Music:** switching between the two RE tracks.
- **Linux:** Linux launching.
- **Full playthrough:** a full playthrough of E1L1.
