"""Terminal probing: color setup, pixel-size queries, raw key reads, sixel detect."""
import curses, os, re, select, sys, time, tty, termios


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


def get_cell_size():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[16t")
        sys.stdout.flush()
        buf = ""
        deadline = time.time() + 0.5
        while time.time() < deadline:
            r,_,_ = select.select([fd], [], [], 0.1)
            if not r: 
                if buf: break
                continue
            c = os.read(fd, 1).decode('latin1', 'replace')
            buf += c
            if c == 't':
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    m = re.search(r'\x1b\[6;(\d+);(\d+)t', buf)
    if m:
        return int(m.group(2)), int(m.group(1))
    return 8, 16


_cell_size_cache = None
_terminal_pixels_cache = None

def get_terminal_pixels():
    """Query terminal text area size in pixels (CSI 14 t). Cached."""
    global _terminal_pixels_cache
    if _terminal_pixels_cache is not None:
        return _terminal_pixels_cache
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[14t")
        sys.stdout.flush()
        buf = ""
        deadline = time.time() + 0.5
        while time.time() < deadline:
            r,_,_ = select.select([fd], [], [], 0.1)
            if not r:
                if buf: break
                continue
            c = os.read(fd, 1).decode('latin1', 'replace')
            buf += c
            if c == 't':
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    m = re.search(r'\x1b\[4;(\d+);(\d+)t', buf)
    if m:
        _terminal_pixels_cache = (int(m.group(2)), int(m.group(1)))
        return _terminal_pixels_cache
    cell_w, cell_h = get_cell_size()
    import shutil
    ts = shutil.get_terminal_size((80, 24))
    _terminal_pixels_cache = (ts.columns * cell_w, ts.lines * cell_h)
    return _terminal_pixels_cache


def get_cell_size_cached():
    global _cell_size_cache
    if _cell_size_cache is None:
        _cell_size_cache = get_cell_size()
    return _cell_size_cache


def read_key(fd):
    c = os.read(fd, 1).decode('latin1', 'replace')
    if c == '\x1b':
        # read rest with timeout
        buf = c
        while True:
            r,_,_ = select.select([fd], [], [], 0.05)
            if not r: break
            buf += os.read(fd, 1).decode('latin1', 'replace')
            if len(buf) > 8: break
        if buf == '\x1b[A': return curses.KEY_UP
        if buf == '\x1b[B': return curses.KEY_DOWN
        if buf == '\x1b[C': return curses.KEY_RIGHT
        if buf == '\x1b[D': return curses.KEY_LEFT
        if len(buf) == 1: return ord(buf)
        return ord(buf[0]) if buf else 0
    return ord(c)


def _safe_detect_sixel():
    try:
        return detect_sixel()
    except Exception:
        return False


def detect_sixel():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[c")
        sys.stdout.flush()
        buf = ""
        deadline = time.time() + 0.5
        while time.time() < deadline:
            r,_,_ = select.select([fd], [], [], 0.1)
            if not r:
                if buf: break
                continue
            c = os.read(fd, 1).decode('latin1', 'replace')
            buf += c
            if c == 'c':
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ";4;" in buf or ";4c" in buf or "4;" in buf


