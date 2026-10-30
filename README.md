# depths

A terminal roguelike. Procedural dungeons, permadeath, no dependencies beyond curses (stdlib).

## Play
```
depths
```
or `python3 depths.py`.

## Controls
- Move: arrows / WASD / hjkl; diagonals: yubn
- `p` potion, `f` eat, `r` scroll, `i` inventory, `c` stats
- `x` search (reveal secret doors), `>` descend, `S` save, `q` quit

## Features
- 15 floors, bosses every 5, escape on 15
- 12 enemy types: goblins, orcs, trolls, dragons, skeletons, bats, wraiths, archers, necromancers, mimics, rats, vampires, golems
- Equipment (weapon/armor/ring), inventory, wands
- Traps (spike, poison, teleport, alarm), secret doors
- Hunger, food, keys, gold
- Fog of war, procedural rooms and corridors
- Save/load, high score

## Stack
Python 3.14, stdlib only (`curses`). Single file.
