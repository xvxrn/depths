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
from depths import Game, render, terminal

random.seed(0)
g = Game(mw=40, mh=25)          # full ruleset, no curses needed
for _ in range(200):            # real-time simulation
    g.tick()
    if g.game_over:
        break
    g.auto_step()               # or g.move_player(dx, dy)

# pixel frame preview (kitty/sixel path) without a terminal:
terminal._terminal_pixels_cache = (1280, 800)
img = render._draw_frame(g)     # PIL Image; save and view it
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
- **Balance**: measure first — `python3 -m depths --sim 200` prints
  win rate / death floors / killers for headless auto-games. Knobs:
  enemy pools+scaling in `place_entities`, hunger/regen in `Game.tick`
  (hunger is per player action), boss stats in `BOSSES`.
- **Affixes/rarity**: tables in `constants.py` (`WEAPON_AFFIXES`,
  `ARMOR_AFFIXES`, `RARITIES`), rolled by `roll_item`, hooked in
  `Game.attack` (crit/lifesteal) and `enemy_act` melee (thorns).

## Pitfalls

- Real-time `tick` runs in `app.play` and must pause for
  inventory/shop/help overlays — see "Gotchas" in AGENTS.md.
- Damage numbers / projectiles / beams are the `Game.add_fx` system, drawn
  only by the pixel renderer; curses mode ignores them.
- `Game.player` is serialized to JSON — keep `setdefault` on load for any
  new player field.
- Use `app._put` for screens text; raw `addstr` crashes on small terminals.
- Kitty sender needs `C=1` and a trailing `\x1b[H` or the screen scrolls.
