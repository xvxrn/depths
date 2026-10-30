# depths

A terminal roguelike with pixel-style rendering. Procedural dungeons, permadeath, no dependencies beyond curses (stdlib).

## Play
```
python3 depths.py
```
or `depths` if installed.

## Controls
- Move: arrows / WASD / hjkl; diagonals: yubn
- `p` potion, `f` eat, `r` scroll, `i` inventory, `c` stats
- `x` search, `>` descend, `S` save, `q` quit

## Features
- 15 floors, bosses every 5, escape on 15
- 12+ enemy types, mimics, ranged enemies, necromancers
- Equipment, inventory, wands, traps, secret doors
- Hunger, food, keys, gold, save/load

## Rendering
Tiles are rendered as solid colored cells (block pixels) using background colors, for a pixel-art look in the terminal. Requires a terminal with 256-color support.

## Stack
Python 3.14, stdlib only (`curses`). Single file.
