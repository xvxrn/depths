# depths

A roguelike. Two rendering modes:

- **Kitty (pixels):** if run inside the kitty terminal, the game renders as a true pixel image via the Kitty graphics protocol (PIL + PNG). Web-quality graphics in the terminal.
- **Fallback (solid cells):** in other terminals, tiles are solid colored cells (256-color background). Still readable.

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

## Stack
Python 3.14, stdlib + Pillow (PIL) for kitty mode. Single file.
