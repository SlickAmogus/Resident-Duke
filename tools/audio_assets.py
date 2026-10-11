#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Copy only the original RE1 sounds and music used by the slice."""
import shutil
from common import REF, STAGE, ASSETS, write_json, refresh_extraction_manifest

# Runtime sound key -> original file. Sources: SoundSystem.cpp Jill bank slots 4/5/6;
# SoundApi.cpp handgun/shotgun bank; SoundTables.cpp room0/18 box slot32 item02,
# slot33 item01, floor footsteps 45/46.
EFFECTS = {'cursor': 'cursor', 'cancel': 'cancel', 'decide': 'decide', 'handgun': 'gun01', 'reload': 'gun02',
           'magazine': 'gun04', 'shotgun': 'shot01', 'pump': 'shot03', 'box-open': 'item02',
           'box-scroll': 'item01', 'step-a': 'ft_lina', 'step-b': 'ft_linb', 'type-a': 'type01',
           'type-b': 'type02', 'case-land': 'gun03', 'shell-land': 'shot02', 'shell-reload': 'shot04',
           'death': 'jill04', 'body-thud': 'taore_st', 'title': 'evil01'}
# BgmRoomData stage 0: corridors group 0 Bgm_00, main hall group 11 Bgm_13.
MUSIC = {'REMANS': 'bgm_00', 'REHALL': 'bgm_13'}

out = STAGE / 'sounds/re1'; out.mkdir(parents=True, exist_ok=True)
for key, name in EFFECTS.items():
    shutil.copyfile(REF / 'Sound' / (name + '.wav'), out / (key + '.wav'))
(STAGE / 'music').mkdir(parents=True, exist_ok=True)
for track, name in MUSIC.items():
    shutil.copyfile(REF / 'Sound' / (name + '.wav'), STAGE / 'music' / (track + '.wav'))
write_json(ASSETS / 'audio-manifest.json', {'effects': {k: 'USA/Sound/' + v + '.wav' for k, v in EFFECTS.items()},
                                            'music': {k: 'USA/Sound/' + v + '.wav' for k, v in MUSIC.items()}})
refresh_extraction_manifest()
print('Copied %d original effects and %d music tracks.' % (len(EFFECTS), len(MUSIC)))
