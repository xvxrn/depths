---
name: depths-game
description: Working on the depths terminal roguelike in this repo - running it, changing game rules, enemies, items, rendering, or testing headless. Use when the task touches depths/ code, the game's balance, graphics, or features.
---

# depths — terminal roguelike

Single-purpose Python game. Read `AGENTS.md` at the repo root first: it has
the module map, entity dict schema, and conventions that this skill assumes.

## Verify changes

There is no test framework. Verify headless (no TTY needed):

```python
import random
from depths import Game

random.seed(0)
g = Game(mw=40, mh=25)          # full ruleset, no curses needed
for _ in range(200):            # real-time simulation
    g.tick()
    if g.game_over:
        break
    g.auto_step()               # or g.move_player(dx, dy)
```

Then `python3 -m py_compile depths/*.py`. Run the real game with
`python3 -m depths` only in an interactive terminal (kitty/sixel/curses).

## Common tasks

- **New enemy type**: add stats to `ENEMY_STATS` + name to `ENEMY_NAMES` +
  spawn pool weight in `dungeon.place_entities` + colors to
  `COLORS` + an entry in the `ENEMY_COLOR` map in `game.draw_curses`.
- **New item type**: pickup branch in `Game.pickup`, a color entry in
  `game.draw_curses` item map, legend line in the side panel.
- **New boss**: entry in `BOSSES` (floors 5/10/15 are guarded) — stairs
  blocking is automatic via `Game.stairs_blocked`.
- **Balance**: enemy scaling lives in `place_entities` (hp/atk floor
  multipliers), player progression in `Game.check_level`, hunger/regen in
  `Game.tick`.

## Pitfalls

- Real-time `tick` runs in `app.main` and must pause for
  inventory/shop/help overlays — see "Gotchas" in AGENTS.md.
- `Game.player` is serialized to JSON — keep `setdefault` on load for any
  new player field.
- Use `app._put` for screens text; raw `addstr` crashes on small terminals.
