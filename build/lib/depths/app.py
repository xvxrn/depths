"""One main loop, two I/O backends: pixel (kitty/sixel) and curses cells."""
import curses, os, random, select, sys, termios, time, tty

from .constants import MAP_TILES_W, MAP_TILES_H
from .game import Game
from .render import render_kitty, render_sixel
from .scores import record_score
from .terminal import Color, cp, init_colors, read_key, _safe_detect_sixel

OVERLAYS_OPEN = lambda game: game.inventory_open or game.shop_open or game.help_open


def run_sim(n=200, max_ticks=15000):
    """Headless auto-play balance harness: N runs, aggregate report to stdout."""
    import statistics
    from collections import Counter
    rows = []
    for i in range(n):
        random.seed(10_000 + i)
        g = Game(mw=40, mh=25)
        g.auto = True
        ticks = 0
        while not g.game_over and ticks < max_ticks:
            g.tick()
            if g.game_over:
                break
            g.auto_step()
            ticks += 1
        rows.append({"floor": g.floor, "level": g.player["level"],
                     "gold": g.player["gold"], "killer": g.killer,
                     "victory": g.victory, "ticks": ticks, "kills": g.kills})
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{n} runs done", file=sys.stderr)

    wins = sum(r["victory"] for r in rows)
    floors = sorted(r["floor"] for r in rows)
    hist = Counter(r["floor"] for r in rows)
    killers = Counter(r["killer"] or ("escaped" if r["victory"] else "max ticks")
                      for r in rows)
    print(f"\nSIM: {n} runs")
    print(f"wins: {wins} ({100*wins/n:.1f}%)")
    print(f"death floor: median {statistics.median(floors)}  "
          f"mean {statistics.mean(floors):.1f}  p90 {floors[int(len(floors)*0.9)]}  max {max(floors)}")
    peak = max(hist.values())
    print("floor histogram:")
    for fl in sorted(hist):
        bar = "#" * max(1, int(40 * hist[fl] / peak))
        print(f"  {fl:2}: {hist[fl]:3} {bar}")
    print("killers (top):")
    for k, cnt in killers.most_common(8):
        print(f"  {k}: {100*cnt/n:.0f}%")
    print(f"avg level {statistics.mean(r['level'] for r in rows):.1f}  "
          f"avg gold {statistics.mean(r['gold'] for r in rows):.0f}  "
          f"avg kills {statistics.mean(r['kills'] for r in rows):.1f}  "
          f"avg ticks {statistics.mean(r['ticks'] for r in rows):.0f}")


def _put(stdscr, y, x, text, attr):
    """addstr that never raises on small terminals."""
    h, w = stdscr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try:
            stdscr.addnstr(y, x, text, max(0, w - x - 1), attr)
        except curses.error:
            pass


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
        _put(stdscr, h//2 - 9 + i, max(0, (w - len(l))//2), l, cp("title") | curses.A_BOLD)
    info = [
        "A roguelike. Procedural dungeons. Permadeath.",
        "",
        "Move: arrows / WASD / hjkl   Diagonals: yubn",
        "p = potion   f = eat   r = scroll   i = inventory",
        "v = trade (stand next to the merchant)",
        "c = stats   x = search   > = descend   S = save   L = load",
        "A = auto   ? = help   q = quit",
        "",
        "Reach floor 15 and slay what guards the exit.",
        "Bosses on floors 5, 10, 15 block the stairs.",
        "Locked doors need keys; find them before the way is shut.",
        "",
        "Press any key to begin...",
    ]
    for i, l in enumerate(info):
        _put(stdscr, h//2 + i, max(0, (w - len(l))//2), l, cp("text"))
    stdscr.refresh()
    stdscr.getch()


def game_over_screen(stdscr, game):
    scores = record_score(game)
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    title = "VICTORY!" if getattr(game, "victory", False) else "GAME OVER"
    color = Color.xp if getattr(game, "victory", False) else Color.hp
    _put(stdscr, h//2 - 8, max(0, w//2 - len(title)//2), title,
         curses.color_pair(color) | curses.A_BOLD)
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
        _put(stdscr, y, max(0, w//2 - len(l)//2), l, cp("text")); y += 1
    for s in scores[:5]:
        tag = "  WIN" if s.get("victory") else ""
        l = f"{s.get('date','')}  floor {s.get('floor',0)}  lvl {s.get('level',0)}  gold {s.get('gold',0)}{tag}"
        _put(stdscr, y, max(0, w//2 - len(l)//2), l, cp("dim")); y += 1
    y += 1
    prompt = "Press r to retry, q to quit."
    _put(stdscr, y, max(0, w//2 - len(prompt)//2), prompt, cp("text"))
    stdscr.refresh()
    while True:
        k = stdscr.getch()
        if k == ord('r'): return "retry"
        if k in (ord('q'), 27): return "quit"


class CursesBackend:
    """Cells renderer, input via getch."""
    def __init__(self, stdscr):
        self.stdscr = stdscr

    def new_game(self):
        return Game(stdscr=self.stdscr)

    def setup(self):
        try:
            curses.curs_set(0)
        except Exception:
            pass
        self.stdscr.keypad(True)
        init_colors()
        title_screen(self.stdscr)

    def draw(self, game):
        game.draw_curses()

    def get_key(self, timeout):
        self.stdscr.timeout(int(timeout * 1000))
        k = self.stdscr.getch()
        self.stdscr.timeout(-1)
        return None if k == -1 else k

    def game_over(self, game):
        return game_over_screen(self.stdscr, game)

    def teardown(self):
        pass


class PixelBackend:
    """Full-frame pixel renderer (kitty or sixel), raw tty input."""
    def __init__(self, renderer):
        self.renderer = renderer
        self.fd = sys.stdin.fileno()

    def new_game(self):
        return Game(mw=MAP_TILES_W, mh=MAP_TILES_H)

    def setup(self):
        self.old_attr = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        if self.renderer is render_sixel:
            sys.stdout.write("\x1b[?1049h\x1b[?25l")
            sys.stdout.flush()

    def draw(self, game):
        self.renderer(game)

    def get_key(self, timeout):
        r, _, _ = select.select([self.fd], [], [], timeout)
        return read_key(self.fd) if r else None

    def game_over(self, game):
        game.draw()
        while True:
            k = self.get_key(None)
            if k == ord('r'):
                return "retry"
            if k in (ord('q'), 27):
                return "quit"

    def teardown(self):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_attr)
        sys.stdout.write("\x1b[?1049l\x1b[?25h")
        sys.stdout.flush()


def play(backend):
    """The single main loop for every backend."""
    backend.setup()
    try:
        while True:
            game = backend.new_game()
            if "--auto" in sys.argv:
                game.auto = True
            last_tick = last_action = time.time()
            while not game.game_over:
                now = time.time()
                if now - last_tick >= 0.5 and not OVERLAYS_OPEN(game):
                    game.tick()
                    last_tick = now
                backend.draw(game)
                key = backend.get_key(0.1)
                if key is not None:
                    if key == ord('A'):
                        game.auto = not game.auto
                        game.msg("Auto-pilot: " + ("ON" if game.auto else "OFF"))
                        continue
                    res = game.handle_input(key)
                    if res == "quit":
                        return
                elif game.auto and now - last_action >= 0.3:
                    game.auto_step()
                    last_action = now
            game.record_score()
            if game.auto:
                backend.draw(game)
                time.sleep(2)
                continue
            if backend.game_over(game) == "quit":
                return
    finally:
        backend.teardown()


def run():
    try:
        if "--sim" in sys.argv:
            n = 200
            if len(sys.argv) > sys.argv.index("--sim") + 1:
                n = int(sys.argv[sys.argv.index("--sim") + 1])
            run_sim(n)
            return
        if os.environ.get("KITTY_WINDOW_ID"):
            os.environ["DEPTHS_RENDER"] = "kitty"
            play(PixelBackend(render_kitty))
        elif "--sixel" in sys.argv or (sys.stdin.isatty() and _safe_detect_sixel()):
            os.environ["DEPTHS_RENDER"] = "sixel"
            play(PixelBackend(render_sixel))
        else:
            curses.wrapper(lambda stdscr: play(CursesBackend(stdscr)))
    except KeyboardInterrupt:
        sys.exit(0)
