"""Main loops (kitty / sixel / curses), screens, entry point."""
import curses, os, sys, time
import select, tty, termios

from .constants import MAP_TILES_W, MAP_TILES_H, ename, cap
from .game import Game
from .scores import record_score
from .terminal import Color, cp, init_colors, read_key, _safe_detect_sixel


def main_kitty():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        game = Game(mw=MAP_TILES_W, mh=MAP_TILES_H)
        if "--auto" in sys.argv:
            game.auto = True
        while True:
            game.game_over = False
            last_tick = time.time()
            last_action = time.time()
            while not game.game_over:
                now = time.time()
                if now - last_tick >= 0.5 and not game.inventory_open and not game.shop_open and not game.help_open:
                    game.tick()
                    last_tick = now
                game.draw()
                r,_,_ = select.select([fd], [], [], 0.1)
                if r:
                    key = read_key(fd)
                    if key == ord('A'):
                        game.auto = not game.auto
                        game.msg("Auto-pilot: " + ("ON" if game.auto else "OFF"))
                        continue
                    if key in (ord('q'), 27):
                        return
                    res = game.handle_input(key)
                    if res == "quit":
                        return
                elif game.auto and now - last_action >= 0.3:
                    game.auto_step()
                    last_action = now
            game.record_score()
            game.draw()
            if game.auto:
                time.sleep(2)
                game = Game(mw=MAP_TILES_W, mh=MAP_TILES_H)
                game.auto = True
                continue
            # wait for r/q
            while True:
                rr,_,_ = select.select([fd], [], [], None)
                if rr:
                    k = read_key(fd)
                    if k == ord('r'):
                        game = Game(mw=MAP_TILES_W, mh=MAP_TILES_H)
                        game.auto = False
                        break
                    if k in (ord('q'), 27):
                        return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?1049l\x1b[?25h")
        sys.stdout.flush()


def main_sixel():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
        sys.stdout.flush()
        game = Game(mw=MAP_TILES_W, mh=MAP_TILES_H)
        if "--auto" in sys.argv:
            game.auto = True
        while True:
            game.game_over = False
            last_tick = time.time()
            last_action = time.time()
            while not game.game_over:
                now = time.time()
                if now - last_tick >= 0.5 and not game.inventory_open and not game.shop_open and not game.help_open:
                    game.tick()
                    last_tick = now
                game.draw()
                r,_,_ = select.select([fd], [], [], 0.05)
                if r:
                    key = read_key(fd)
                    if key == ord('A'):
                        game.auto = not game.auto
                        game.msg("Auto-pilot: " + ("ON" if game.auto else "OFF"))
                        continue
                    if key in (ord('q'), 27):
                        return
                    res = game.handle_input(key)
                    if res == "quit":
                        return
                elif game.auto and now - last_action >= 0.3:
                    game.auto_step()
                    last_action = now
            game.record_score()
            game.draw()
            if game.auto:
                time.sleep(2)
                game = Game(mw=MAP_TILES_W, mh=MAP_TILES_H)
                game.auto = True
                continue
            while True:
                rr,_,_ = select.select([fd], [], [], None)
                if rr:
                    k = read_key(fd)
                    if k == ord('r'):
                        game = Game(mw=MAP_TILES_W, mh=MAP_TILES_H)
                        game.auto = False
                        break
                    if k in (ord('q'), 27):
                        return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?1049l\x1b[?25h")
        sys.stdout.flush()


def title_screen(stdscr):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    lines = [
        "  ____  ____  ____  __  __  ____  ",
        " |  _ \\|  _ \\|  _ \\|  \\/  |/ ___| ",
        " | | | | |_) | |_) | |\\/| |\\___ \\ ",
        " | |_| |  __/|  __/| |  | | ___) |",
        " |____/|_|   |_|   |_|  |_|____/  ",
    ]
    for i, l in enumerate(lines):
        stdscr.addstr(h//2 - 9 + i, max(0, w//2 - len(l)//2), l, cp("title") | curses.A_BOLD)
    info = [
        "A roguelike. Procedural dungeons. Permadeath.",
        "",
        "Move: arrows / WASD / hjkl   Diagonals: yubn",
        "p = potion   f = eat   r = scroll   i = inventory",
        "v = trade (stand next to the merchant)",
        "c = stats   x = search   > = descend   S = save   L = load   A = auto   ? = help   q = quit",
        "",
        "Reach floor 15 and slay what guards the exit.",
        "Bosses on floors 5, 10, 15 block the stairs.",
        "Locked doors need keys; find them before the way is shut.",
        "",
        "Press any key to begin...",
    ]
    for i, l in enumerate(info):
        stdscr.addstr(h//2 + i, max(0, w//2 - len(l)//2), l, cp("text"))
    stdscr.refresh()
    stdscr.getch()


def game_over_screen(stdscr, game):
    scores = record_score(game)
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    title = "VICTORY!" if getattr(game, "victory", False) else "GAME OVER"
    color = Color.xp if getattr(game, "victory", False) else Color.hp
    stdscr.addstr(h//2 - 8, max(0, w//2 - len(title)//2), title, curses.color_pair(color) | curses.A_BOLD)
    stats = [
        "You escaped the depths!" if getattr(game, "victory", False)
        else (f"Slain by {game.killer}." if getattr(game, "killer", None) else "You died in the depths."),
        f"Floor reached: {game.floor}",
        f"Level: {game.player['level']}",
        f"Gold: {game.player['gold']}",
        "",
        "Best runs:",
    ]
    y = h//2 - 5
    for l in stats:
        stdscr.addstr(y, max(0, w//2 - len(l)//2), l, cp("text")); y += 1
    for s in scores[:5]:
        tag = "  WIN" if s.get("victory") else ""
        l = f"{s.get('date','')}  floor {s.get('floor',0)}  lvl {s.get('level',0)}  gold {s.get('gold',0)}{tag}"
        stdscr.addstr(y, max(0, w//2 - len(l)//2), l, cp("dim")); y += 1
    y += 1
    prompt = "Press r to retry, q to quit."
    stdscr.addstr(y, max(0, w//2 - len(prompt)//2), prompt, cp("text"))
    stdscr.refresh()
    while True:
        k = stdscr.getch()
        if k == ord('r'): return "retry"
        if k in (ord('q'), 27): return "quit"


def main(stdscr):
    try:
        curses.curs_set(0)
    except Exception:
        pass
    stdscr.nodelay(False)
    stdscr.keypad(True)
    init_colors()
    title_screen(stdscr)
    stdscr.timeout(50)
    while True:
        game = Game(stdscr=stdscr)
        if "--auto" in sys.argv:
            game.auto = True
        game.game_over = False
        last_tick = time.time()
        last_action = time.time()
        while not game.game_over:
            now = time.time()
            if now - last_tick >= 0.5 and not game.inventory_open and not game.shop_open and not game.help_open:
                game.tick()
                last_tick = now
            game.draw()
            key = stdscr.getch()
            if key != -1:
                if key == ord('A'):
                    game.auto = not game.auto
                    game.msg("Auto-pilot: " + ("ON" if game.auto else "OFF"))
                    continue
                res = game.handle_input(key)
                if res == "quit":
                    stdscr.timeout(-1)
                    return
            elif game.auto and now - last_action >= 0.3:
                game.auto_step()
                last_action = now
        stdscr.timeout(-1)
        action = game_over_screen(stdscr, game)
        stdscr.timeout(50)
        if action == "quit":
            stdscr.timeout(-1)
            return
        if game.auto:
            continue


def run():
    try:
        if os.environ.get("KITTY_WINDOW_ID"):
            os.environ["DEPTHS_RENDER"] = "kitty"
            main_kitty()
        elif "--sixel" in sys.argv or (sys.stdin.isatty() and _safe_detect_sixel()):
            os.environ["DEPTHS_RENDER"] = "sixel"
            main_sixel()
        else:
            curses.wrapper(main)
    except KeyboardInterrupt:
        # clean exit
        try:
            sys.stdout.write("\x1b[?1049l\x1b[?25h")
            sys.stdout.flush()
        except Exception:
            pass
        sys.exit(0)

