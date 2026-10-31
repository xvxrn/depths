# depths

A roguelike with pixel rendering in the terminal. Stdlib + Pillow.

## Run

```sh
python3 -m depths            # play
python3 -m depths --auto     # auto-pilot plays itself
./play.sh                    # same as python3 -m depths
```

## Rendering modes (auto-detected)
- **Kitty** (KITTY_WINDOW_ID set): true pixels via Kitty graphics protocol.
- **Sixel** (terminal supports sixel, or `--sixel`): true pixels via sixel.
- **Fallback**: colored cells (curses), works in any terminal.

Pixel modes render full-screen with sprites, damage numbers and event
banners; one main loop drives both backends.

## Controls
- Move: arrows / WASD / hjkl; diagonals: yubn
- `p` potion, `f` eat, `r` scroll, `i` inventory, `v` trade
- `c` stats, `x` search, `>` descend, `S` save, `L` load, `A` auto
- `?` help, `q` quit

## Features
- 15 floors; named bosses on 5, 10, 15 that block the stairs until slain
- 13 enemy types with names, speeds (fast bats, slow trolls/golems), alert
  memory and BFS pathfinding
- Locked doors + keys, mimics, ranged enemies, necromancers, traps, secret
  doors
- Equipment, inventory, wands, targeted fireball scrolls
- Merchant on floors 2+: spend gold on potions, scrolls, gear, max HP
- Hunger with slow regen while well-fed, food, gold, save/load, top-5 high
  scores
- Readability: goal + stairs compass in the HUD, colored log, contextual
  tutorial hints, "slain by ..." death recap, inventory stat comparison,
  help screen on `?`, event banners
- Auto-pilot (heuristic AI + BFS pathfinding)

## Layout

Single package, pure stdlib:

| Module | Role |
|--------|------|
| `depths/constants.py` | chars, colors, enemy/boss/item tables |
| `depths/terminal.py`  | curses colors, terminal pixel queries, raw input |
| `depths/render.py`    | PIL frame drawing, Kitty/sixel senders |
| `depths/dungeon.py`   | dungeon generation, entity placement |
| `depths/game.py`      | `Game` — all rules, curses drawing, auto-pilot |
| `depths/scores.py`    | high scores |
| `depths/app.py`       | one main loop, curses/pixel backends, screens |

`AGENTS.md` documents the schema and conventions; `.agents/skills/depths-game`
has a skill for coding agents.

## Stack
Python 3, stdlib + Pillow (only for pixel modes). Developed on 3.14.
