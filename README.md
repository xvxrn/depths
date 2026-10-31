# depths

A roguelike with pixel rendering in the terminal.

## Rendering modes (auto-detected)
- **Kitty** (KITTY_WINDOW_ID set): true pixels via Kitty graphics protocol.
- **Sixel** (terminal supports sixel, or `--sixel`): true pixels via sixel. Use `--sixel` to force.
- **Fallback**: solid colored cells (curses, 256 colors). Works everywhere.

All pixel modes render full-screen.

## Play
```
python3 depths.py            # auto-detect
python3 depths.py --sixel    # force sixel
python3 depths.py --auto     # auto-play
```
or `depths`.

## Controls
- Move: arrows / WASD / hjkl; diagonals: yubn
- `p` potion, `f` eat, `r` scroll, `i` inventory, `c` stats
- `x` search, `>` descend, `S` save, `L` load, `A` auto, `q` quit

## Features
- 15 floors; named bosses on 5, 10, 15 that block the stairs until slain
- 13 enemy types with names, speeds (fast bats, slow trolls/golems), alert memory and BFS pathfinding
- Locked doors + keys, mimics, ranged enemies, necromancers, traps, secret doors
- Equipment, inventory, wands, targeted fireball scrolls
- Merchant on floors 2+: spend gold on potions, scrolls, gear, max HP
- Hunger with slow regen while well-fed, food, gold, save/load
- Juice: floating damage numbers, arrows/beams/explosions, smooth movement,
  damage flash, event banners, item memory on the map, top-5 high scores
- Auto-pilot (heuristic AI + BFS pathfinding)

## Stack
Python 3.14, stdlib + Pillow. Single file.
