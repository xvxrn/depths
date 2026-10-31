# AGENTS.md — depths

A single-purpose terminal roguelike in Python. Pure stdlib: one curses
renderer, one main loop, zero third-party dependencies.

## Run

```sh
python3 -m depths          # auto-detects rendering mode
python3 -m depths --sixel  # force sixel
python3 -m depths --auto   # auto-pilot plays itself
./play.sh                  # same as python3 -m depths
```

Rendering modes, in order: kitty (if `$KITTY_WINDOW_ID`), sixel (if detected
or `--sixel`), curses fallback.

## Module map

| File                  | Contents |
|-----------------------|----------|
| `depths/constants.py` | Tile/enemy/item chars, `RGB` (true-color), `COLORS` (256-color), `ENEMY_STATS`, `ENEMY_NAMES`, `BOSSES`, `SHOP_GOODS`, map geometry (`MAP_TILES_W/H`, `SIDE_W`, `PAD`) |
| `depths/terminal.py`  | `init_colors`/`Color`/`cp`, pixel-size queries (`get_terminal_pixels`, CSI 14t), `read_key`, sixel detection |
| `depths/dungeon.py`   | `make_dungeon` (rooms + corridors + secret/locked doors), `place_entities` (enemies, items, traps, stairs, boss, merchant), `biome` |
| `depths/game.py`      | `Game` class: all rules. Movement, FOV (Bresenham), combat, enemy AI (`enemy_turn`/`enemy_act` + BFS), hunger/regen (`tick`), traps, pickups, shop, inventory, save/load, auto-pilot (`auto_step`), curses drawing |
| `depths/scores.py`    | Top-5 runs in `~/.depths_high.json` |
| `depths/app.py`       | The single curses main loop, title + game-over screens, `run()` entry |

## Conventions

- **Messages** go through `Game.msg(text, kind)`; kind is one of
  `info/danger/loot/sys/hint` and drives log coloring. Never append to
  `self.messages` directly.
- **Tutorial hints** go through `Game.hint(key, text)` — fires once per run.
- **Enemies** are plain dicts: `ch, x, y, hp, maxhp, atk, name, xp` plus
  optional `fast/slow/boss/alert/disguise`. Render coords `rx/ry` are added by
  the renderer and must be popped on floor change (`new_floor`, `load_game`).
- **Player-visible text uses `ename(e)`** ("the goblin"), never the bare char.
- Bosses come from `BOSSES` (floors 5/10/15) and block the stairs while alive
  (`Game.stairs_blocked`).
- Items on the floor are dicts `{"ch": "!"/"*"/...}`; `draw_item_glyph` has a
  shape per type — add both or neither.
- The `Game.player` dict is saved to JSON verbatim: keep new player fields
  backward-compatible (`setdefault` on load).

## Gotchas

- Real time (`tick`, 0.5 s) must be paused while any overlay is open:
  `not game.inventory_open and not game.shop_open and not game.help_open`
  in the one main loop in `app.main`.
- Never write raw `stdscr.addstr` in screens (title/game-over): use
  `app._put`, which truncates and swallows `curses.error` on small
  terminals — raw addstr on the last row/col crashes the game.
- `draw_curses` is the only renderer; `Game.draw` is a no-op without a
  stdscr (headless).
- Save/highscore paths are module attributes so tests can redirect them:
  patch `depths.game.SAVE` and `depths.scores.HIGH`.

## Testing (headless, no TTY)

```python
import random
from depths import Game
g = Game(mw=40, mh=25)   # no stdscr: curses drawing is skipped
g.tick(); g.auto_step()  # simulate real time + auto-pilot
```

`Game(mw=..., mh=...)` without `stdscr` runs the full ruleset headless.
Drive it with `tick()` + `move_player()`/`auto_step()` loops. For a real
terminal check, run the game under a pty (set winsize before exec, see
`/tmp/pty_smoke.py` pattern: fork, ioctl TIOCSWINSZ, exec, read/expect).
Always `python3 -m py_compile depths/*.py` before committing.
