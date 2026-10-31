# depths

A terminal roguelike. Pure Python stdlib — zero third-party dependencies.

## Run

```sh
python3 -m depths            # play
python3 -m depths --auto     # auto-pilot plays itself
./play.sh                    # same as python3 -m depths
```

Renders with curses: colored cells, works in any terminal, 256-color or
better recommended.

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
| `depths/terminal.py`  | curses color setup |
| `depths/dungeon.py`   | dungeon generation, entity placement |
| `depths/game.py`      | `Game` — all rules, curses drawing, auto-pilot |
| `depths/scores.py`    | high scores |
| `depths/app.py`       | the main loop and screens |

`AGENTS.md` documents the schema and conventions; `.agents/skills/depths-game`
has a skill for coding agents.

## Stack
Python 3 (stdlib only). Developed on 3.14.
