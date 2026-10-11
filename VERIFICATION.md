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
- **Overwrite prompt:** re-saving to a used typewriter row asks OK TO OVERWRITE THE DATA?

Not yet exercised end to end:

- **Sword key:** the sword key on the red access switch.
- **Shotgun:** its reload and shell casings.
- **Herb mixing:** combining herbs.
- **Fresh-session load:** the death screen's LOAD GAME, without a save from the current session, falls back to EDuke32's load menu. This path is untested.
- **Music:** switching between the two RE tracks.
- **Linux:** Linux launching.
- **Full playthrough:** a full playthrough of E1L1.
