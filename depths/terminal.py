"""Terminal setup: curses color pairs."""
import curses

from .constants import COLORS


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
    except Exception:
        pass
    BG_FLOOR = 236
    BG_WALL = 234
    tile_colors = {"wall","floor","door","stairs","secret","player","goblin","orc","troll","dragon",
        "skeleton","bat","wraith","archer","necromancer","mimic","rat","vampire","golem",
        "potion","weapon","armor","gold","scroll","food","ring","wand","key","trap","dim"}
    if curses.COLORS < 256:
        # limited color terminal: no backgrounds
        for name, code in COLORS.items():
            c8 = code % 8
            try:
                curses.init_pair(hash(name) % 200 + 1, c8, -1)
            except Exception:
                pass
    else:
        for name, code in COLORS.items():
            bg = BG_WALL if name in ("wall","secret") else (BG_FLOOR if name in tile_colors else -1)
            curses.init_pair(hash(name) % 200 + 1, code, bg)
    for name in COLORS:
        setattr(Color, name, hash(name) % 200 + 1)

class Color: pass

def cp(name): return curses.color_pair(getattr(Color, name))
