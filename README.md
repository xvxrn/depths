# depths

A roguelike in two forms:

- **Terminal** (Python, curses): `python3 depths.py` — classic ASCII roguelike.
- **Pixel** (HTML/Canvas): open `index.html` in a browser — same game with pixel graphics.

## Play (pixel)
Open `index.html` in any modern browser. No build step, no server.

## Play (terminal)
```
python3 depths.py
```

## Controls
- Move: arrows / WASD / hjkl; diagonals: yubn
- `p` potion, `f` eat, `r` scroll, `i` inventory, `c` stats
- `x` search, `>` descend, `S` save, `q` quit

## Features
- 15 floors, bosses every 5, escape on 15
- 12+ enemy types, mimics, ranged enemies, necromancers
- Equipment, inventory, wands, traps, secret doors
- Hunger, food, keys, gold, save/load, high score

## Stack
- Terminal: Python 3.14, stdlib only (`curses`).
- Pixel: vanilla HTML/CSS/JS, Canvas API. No dependencies.
