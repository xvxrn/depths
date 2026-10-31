#!/usr/bin/env python3
"""depths — a terminal roguelike. Pixel rendering via Kitty protocol (fallback: solid cells)."""
import curses, random, os, json, sys, base64, io, re, select, tty, termios, time, math

SAVE = os.path.expanduser("~/.depths_save.json")
HIGH = os.path.expanduser("~/.depths_high.json")

ITEM_CHARS = {"!": "potion", "/": "weapon", "[": "armor", "$": "gold", "?": "scroll",
              "*": "food", "=": "ring", "(": "wand", "k": "key", "^": "trap", "w": "wand"}
ENEMY_CHARS = {"g": "goblin", "o": "orc", "T": "troll", "D": "dragon", "s": "skeleton",
               "b": "bat", "W": "wraith", "a": "archer", "n": "necromancer", "m": "mimic",
               "r": "rat", "V": "vampire", "G": "golem"}
PLAYER = "@"

# RGB colors for kitty image rendering
RGB = {
    "wall": (31,41,55), "wallHi": (55,65,81),
    "floor": (15,31,23), "floorHi": (26,46,34),
    "door": (124,90,42), "stairs": (245,158,11), "secret": (31,41,55),
    "player": (63,185,80), "playerEye": (13,17,23),
    "goblin": (34,197,94), "orc": (22,163,74), "troll": (21,128,61), "dragon": (220,38,38),
    "skeleton": (229,231,235), "bat": (167,139,250), "wraith": (192,132,252),
    "archer": (249,115,22), "necromancer": (168,85,247), "mimic": (251,191,36),
    "rat": (146,64,14), "vampire": (190,18,60), "golem": (107,114,128),
    "potion": (236,72,153), "food": (132,204,22), "weapon": (245,158,11), "armor": (59,130,246),
    "gold": (250,204,21), "scroll": (232,121,249), "ring": (244,114,182), "wand": (196,181,253),
    "key": (253,224,71), "trap": (239,68,68), "fog": (0,0,0), "dim": (8,12,20),
    "bossB": (253,224,71), "bossZ": (226,232,240), "bossL": (168,85,247),
    "bg": (10,14,20), "panel": (22,27,34), "text": (201,209,217), "hp": (63,185,80),
    "title": (88,166,255),
}

COLORS = {
    "wall": 8, "floor": 240, "door": 94, "stairs": 220, "secret": 94, "player": 46,
    "goblin": 34, "orc": 28, "troll": 22, "dragon": 196, "skeleton": 250,
    "bat": 95, "wraith": 141, "archer": 130, "necromancer": 99, "mimic": 214,
    "rat": 101, "vampire": 125, "golem": 242, "potion": 201, "weapon": 208,
    "armor": 33, "gold": 220, "scroll": 213, "food": 112, "ring": 219,
    "wand": 177, "key": 220, "trap": 196, "text": 255, "hp": 196, "xp": 45,
    "bossB": 226, "bossZ": 255, "bossL": 129,
    "dim": 238, "msg": 226, "title": 51, "inv": 51, "equip": 39,
}

ENEMY_STATS = {
    "g": (6, 2, 3), "o": (12, 4, 6), "T": (25, 7, 12), "D": (60, 15, 40),
    "s": (8, 3, 4), "b": (4, 1, 2), "W": (18, 6, 10), "a": (10, 3, 5),
    "n": (14, 2, 8), "m": (15, 4, 6), "r": (3, 1, 1), "V": (22, 5, 12),
    "G": (40, 6, 15),
}

ENEMY_NAMES = {"g": "the goblin", "o": "the orc", "T": "the troll", "D": "the dragon",
               "s": "the skeleton", "b": "the bat", "W": "the wraith", "a": "the archer",
               "n": "the necromancer", "m": "the mimic", "r": "the rat",
               "V": "the vampire", "G": "the golem"}

BOSSES = {
    5:  {"ch": "B", "name": "the Goblin King",      "hp": 55,  "atk": 8,  "xp": 60,  "color": "bossB"},
    10: {"ch": "Z", "name": "the Bone Colossus",    "hp": 100, "atk": 13, "xp": 150, "color": "bossZ"},
    15: {"ch": "L", "name": "the Lich of the Depths","hp": 150, "atk": 16, "xp": 300, "color": "bossL"},
}

def ename(e):
    if e.get("boss"):
        return e.get("name", "the boss")
    return ENEMY_NAMES.get(e["ch"], e["ch"])

def cap(s):
    return s[0].upper() + s[1:] if s else s

SHOP_GOODS = [
    {"ch": "*", "name": "food",         "base": 10},
    {"ch": "!", "name": "health potion","base": 15},
    {"ch": "k", "name": "key",          "base": 20},
    {"ch": "?", "name": "scroll",       "base": 25},
    {"ch": "[", "name": "plate armor",  "base": 35},
    {"ch": "/", "name": "steel weapon", "base": 40},
    {"ch": "@", "name": "+10 max HP",   "base": 60},
]

def load_scores():
    try:
        with open(HIGH) as f:
            return json.load(f)
    except Exception:
        return []

def score_key(s):
    return (1 if s.get("victory") else 0, s.get("floor", 0), s.get("level", 0), s.get("gold", 0))

def record_score(game):
    """Record a finished run once; returns the current top-5."""
    if getattr(game, "_scored", False):
        return getattr(game, "_scores", load_scores())
    game._scored = True
    entry = {"floor": game.floor, "level": game.player["level"], "gold": game.player["gold"],
             "victory": bool(getattr(game, "victory", False)),
             "date": time.strftime("%Y-%m-%d %H:%M")}
    scores = load_scores()
    scores.append(entry)
    scores.sort(key=score_key, reverse=True)
    scores = scores[:5]
    try:
        json.dump(scores, open(HIGH, "w"))
    except Exception:
        pass
    game._scores = scores
    return scores

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

def biome(floor):
    if floor <= 3: return "Dungeon"
    if floor <= 6: return "Caves"
    if floor <= 9: return "Crypt"
    return "Abyss"

def make_dungeon(floor, width, height):
    grid = [[0 for _ in range(width)] for _ in range(height)]  # 0 wall
    rooms = []
    nrooms = random.randint(6, 10)
    attempts = 0
    while len(rooms) < nrooms and attempts < 300:
        attempts += 1
        w = random.randint(4, 10)
        h = random.randint(3, 7)
        x = random.randint(1, width - w - 2)
        y = random.randint(1, height - h - 2)
        ok = True
        for (rx, ry, rw, rh) in rooms:
            if x < rx + rw + 2 and x + w + 2 > rx and y < ry + rh + 2 and y + h + 2 > ry:
                ok = False; break
        if ok:
            rooms.append((x, y, w, h))
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    grid[yy][xx] = 1  # floor
    for i in range(1, len(rooms)):
        x1, y1, w1, h1 = rooms[i-1]
        x2, y2, w2, h2 = rooms[i]
        cx1, cy1 = x1 + w1//2, y1 + h1//2
        cx2, cy2 = x2 + w2//2, y2 + h2//2
        if random.random() < 0.5:
            for xx in range(min(cx1, cx2), max(cx1, cx2)+1):
                if 0 <= cy1 < height and 0 <= xx < width: grid[cy1][xx] = 1
            for yy in range(min(cy1, cy2), max(cy1, cy2)+1):
                if 0 <= yy < height and 0 <= cx2 < width: grid[yy][cx2] = 1
        else:
            for yy in range(min(cy1, cy2), max(cy1, cy2)+1):
                if 0 <= yy < height and 0 <= cx1 < width: grid[yy][cx1] = 1
            for xx in range(min(cx1, cx2), max(cx1, cx2)+1):
                if 0 <= cy2 < height and 0 <= xx < width: grid[cy2][xx] = 1
    # secret doors
    for y in range(1, height-1):
        for x in range(1, width-1):
            if grid[y][x] == 0:
                if (grid[y-1][x] == 1 and grid[y+1][x] == 1) or (grid[y][x-1] == 1 and grid[y][x+1] == 1):
                    if random.random() < 0.04:
                        grid[y][x] = 4  # secret
    return grid, rooms

def place_entities(grid, width, height, floor, player_pos, rooms=None):
    entities = []
    items = []
    traps = []
    cands = []
    for y in range(1, height-1):
        for x in range(1, width-1):
            if grid[y][x] == 1:
                if abs(x-player_pos[0]) + abs(y-player_pos[1]) > 6:
                    cands.append((x, y))
    random.shuffle(cands)
    pool = ["g","g","g","r","r","o","s","b"]
    if floor >= 2: pool += ["o","o","a","s","W"]
    if floor >= 3: pool += ["T","n","V"]
    if floor >= 4: pool += ["T","m","G"]
    if floor >= 5: pool += ["D","n","m"]
    if floor % 5 == 0:
        pool = ["o","s","T","W","n","m"]  # boss floors: fewer heavies, the boss is the challenge
    idx = 0
    n_enemies = 4 + floor*2 + random.randint(0, 3)
    for _ in range(n_enemies):
        if idx >= len(cands): break
        x, y = cands[idx]; idx += 1
        ch = random.choice(pool)
        hp, atk, xp = ENEMY_STATS[ch]
        hp = int(hp * (1 + 0.12*(floor-1)))
        atk = int(atk * (1 + 0.08*(floor-1)))
        ent = {"ch": ch, "x": x, "y": y, "hp": hp, "maxhp": hp,
               "atk": atk, "name": ch, "xp": xp}
        if ch == "b":
            ent["fast"] = True
        if ch in ("T", "G"):
            ent["slow"] = True
        entities.append(ent)
    n_items = random.randint(3, 5) + floor//2
    for _ in range(n_items):
        if idx >= len(cands): break
        x, y = cands[idx]; idx += 1
        if random.random() < 0.15 and floor >= 2:
            hp = ENEMY_STATS["m"][0]
            entities.append({"ch": "m", "x": x, "y": y, "hp": hp, "maxhp": hp,
                            "atk": ENEMY_STATS["m"][1], "name": "m", "xp": ENEMY_STATS["m"][2],
                            "disguise": random.choice(["!","/","[","$","?","*"])})
            continue
        ch = random.choice(["!","!","*","*","/","[","$","?","?","=","w"])
        items.append({"ch": ch, "x": x, "y": y})
    n_traps = random.randint(1, 3) + floor//3
    for _ in range(n_traps):
        if idx >= len(cands): break
        x, y = cands[idx]; idx += 1
        traps.append({"ch": random.choice(["^","^","~","@","!"]), "x": x, "y": y, "triggered": False})
    # stairs
    occupied = {(e["x"],e["y"]) for e in entities} | {(it["x"],it["y"]) for it in items}
    far = [c for c in cands if abs(c[0]-player_pos[0])+abs(c[1]-player_pos[1])>15 and c not in occupied]
    if far:
        sx, sy = random.choice(far)
        grid[sy][sx] = 3  # stairs
    # locked doors on corridor chokepoints, with one key per door
    n_locks = 0
    if floor >= 2:
        choke = []
        for y in range(1, height-1):
            for x in range(1, width-1):
                if grid[y][x] == 0:
                    if (grid[y-1][x] == 1 and grid[y+1][x] == 1) or (grid[y][x-1] == 1 and grid[y][x+1] == 1):
                        choke.append((x, y))
        random.shuffle(choke)
        for x, y in choke[:2]:
            grid[y][x] = 5
            n_locks += 1
    for _ in range(n_locks):
        if idx < len(cands):
            x, y = cands[idx]; idx += 1
            items.append({"ch": "k", "x": x, "y": y})
        else:
            break
    # floor boss, lurking near the stairs
    boss = BOSSES.get(floor)
    if boss:
        spot = None
        if far:
            near = [c for c in cands if c not in occupied and c != (sx, sy)
                    and abs(c[0]-sx) + abs(c[1]-sy) <= 7]
            if near:
                spot = random.choice(near)
        if spot is None and cands:
            spot = cands[-1]
        if spot:
            entities.append({"ch": boss["ch"], "x": spot[0], "y": spot[1],
                             "hp": boss["hp"], "maxhp": boss["hp"], "atk": boss["atk"],
                             "name": boss["name"], "xp": boss["xp"], "boss": True})
    # merchant in a room away from the player's start
    merchant = None
    if floor >= 2 and rooms and len(rooms) > 1:
        occ = occupied | {(t["x"], t["y"]) for t in traps}
        cand_rooms = [r for r in rooms
                      if not (r[0] <= player_pos[0] < r[0]+r[2] and r[1] <= player_pos[1] < r[1]+r[3])]
        random.shuffle(cand_rooms)
        for (rx, ry, rw, rh) in cand_rooms:
            spots = [(x, y) for y in range(ry, ry+rh) for x in range(rx, rx+rw)
                     if grid[y][x] == 1 and (x, y) not in occ]
            if spots:
                mx, my = random.choice(spots)
                merchant = {"x": mx, "y": my}
                break
    return entities, items, traps, merchant
    if random.random() < 0.35 and idx < len(cands):
        x, y = cands[idx]; idx += 1
        items.append({"ch": "k", "x": x, "y": y})
    return entities, items, traps

class Game:
    def __init__(self, stdscr=None, mw=None, mh=None):
        self.stdscr = stdscr
        if stdscr is not None:
            h, w = stdscr.getmaxyx()
            self.mw = w if mw is None else mw
            self.mh = (h - 4) if mh is None else mh
        else:
            self.mw = mw if mw is not None else 40
            self.mh = mh if mh is not None else 25
        self.reset()

    def reset(self):
        self.floor = 1
        self.player = {"x":0,"y":0,"hp":24,"maxhp":24,"atk":4,"def":1,"xp":0,"level":1,
                       "gold":0,"potions":1,"scrolls":0,"food":3,"hunger":0,
                       "weapon":None,"armor":None,"ring":None,"inventory":[],"keys":0}
        self.messages = []
        self.explored = set()
        self.visible = set()
        self.victory = False
        self.game_over = False
        self.inventory_open = False
        self.inv_cursor = 0
        self.auto = False
        self.tick_count = 0
        self.starve_acc = 0
        self.hungry_warned = False
        self.banner = None       # (text, expiry time)
        self.flash_until = 0.0   # red screen edge on player damage
        self.merchant = None
        self.shop_open = False
        self.shop_cursor = 0
        self.effects = []        # transient visuals: dmg numbers, projectiles...
        self._draw_t = 0.0
        self.hints_shown = set()
        self.killer = None       # what finished the run, for the death recap
        self.help_open = False
        self.new_floor()
        self.hint("move", "Arrows/WASD to move. Press ? for help.")

    def set_banner(self, text, secs=2.5):
        self.banner = (text, time.time() + secs)

    def hint(self, key, text):
        """One-shot contextual tutorial hint."""
        if key in self.hints_shown:
            return
        self.hints_shown.add(key)
        self.msg(text, "hint")
        self.set_banner(text, 2.5)

    def stairs_pos(self):
        for y in range(self.mh):
            for x in range(self.mw):
                if self.grid[y][x] == 3:
                    return (x, y)
        return None

    def item_delta(self, inv_item):
        """Stat change if this inventory item replaces the equipped one."""
        item = inv_item["item"]
        if item["type"] == "weapon":
            cur = self.player["weapon"].get("atk", 0) if self.player["weapon"] else 0
            return item.get("atk", 0) - cur
        if item["type"] == "armor":
            cur = self.player["armor"].get("def", 0) if self.player["armor"] else 0
            return item.get("def", 0) - cur
        return None

    def new_floor(self):
        self.grid, rooms = make_dungeon(self.floor, self.mw, self.mh)
        rx, ry, rw, rh = rooms[0]
        self.player["x"] = rx + rw//2
        self.player["y"] = ry + rh//2
        self.entities, self.items, self.traps, self.merchant = place_entities(
            self.grid, self.mw, self.mh, self.floor, (self.player["x"], self.player["y"]), rooms)
        for e in self.entities + [self.player]:
            e.pop("rx", None); e.pop("ry", None)
        self.msg(f"--- Floor {self.floor}: {biome(self.floor)} ---", "sys")
        boss = BOSSES.get(self.floor)
        if boss:
            self.msg(f"{cap(boss['name'])} lurks on this floor!", "sys")
            self.set_banner(f"BOSS: {cap(boss['name'])}", 3.0)
        self.compute_fov()

    def compute_fov(self):
        self.visible = set()
        px, py = self.player["x"], self.player["y"]
        R = 8
        for dy in range(-R, R+1):
            for dx in range(-R, R+1):
                if dx*dx+dy*dy > R*R: continue
                x, y = px+dx, py+dy
                if 0 <= x < self.mw and 0 <= y < self.mh:
                    if self.line_of_sight(px, py, x, y):
                        self.visible.add((x,y))
                        self.explored.add((x,y))

    def line_of_sight(self, x0,y0,x1,y1):
        dx = abs(x1-x0); dy = abs(y1-y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            if x == x1 and y == y1: return True
            if (x,y) != (x0,y0) and self.grid[y][x] in (0,4,5):
                return False
            e2 = 2*err
            if e2 > -dy:
                err -= dy; x += sx
            if e2 < dx:
                err += dx; y += sy

    def msg(self, text, kind="info"):
        self.messages.append({"t": text, "k": kind})
        if len(self.messages) > 8:
            self.messages = self.messages[-8:]

    def total_atk(self):
        base = self.player["atk"]
        if self.player["weapon"]: base += self.player["weapon"].get("atk",0)
        if self.player["ring"]: base += self.player["ring"].get("atk",0)
        return base

    def total_def(self):
        base = self.player["def"]
        if self.player["armor"]: base += self.player["armor"].get("def",0)
        if self.player["ring"]: base += self.player["ring"].get("def",0)
        return base

    def move_player(self, dx, dy):
        if self.inventory_open:
            return
        nx, ny = self.player["x"]+dx, self.player["y"]+dy
        if not (0 <= nx < self.mw and 0 <= ny < self.mh): return
        cell = self.grid[ny][nx]
        if cell == 0:
            self.msg("A wall blocks your path.")
            return
        if cell == 5:
            if self.player["keys"] > 0:
                self.player["keys"] -= 1
                self.grid[ny][nx] = 2
                self.msg("You unlock the door.", "sys")
            else:
                self.msg("The door is locked. You need a key.", "sys")
                self.hint("locked", "Locked doors need a key. Look for keys on the floor.")
                return
        if cell == 4:
            self.grid[ny][nx] = 2
            self.msg("You found a secret door!", "sys")
        m = self.merchant
        if m and nx == m["x"] and ny == m["y"]:
            self.msg("The merchant greets you. (v to trade)")
            return
        for e in self.entities:
            if e["hp"]>0 and e["x"]==nx and e["y"]==ny:
                self.attack(e)
                self.compute_fov()
                return
        for it in self.items:
            if it["x"]==nx and it["y"]==ny:
                self.pickup(it)
                self.items.remove(it)
        for t in self.traps:
            if t["x"]==nx and t["y"]==ny and not t.get("triggered"):
                self.trigger_trap(t)
        if self.grid[ny][nx] == 3:
            self.msg("You stand on the stairs. Press > to descend.", "sys")
        self.player["x"], self.player["y"] = nx, ny
        if self.merchant_adjacent():
            self.hint("trade", "Press v to trade with the merchant.")
        self.reveal_secrets()
        self.compute_fov()
        sp = self.stairs_pos()
        if sp and sp in self.visible:
            self.hint("stairs", "Stand on > and press > to descend.")

    def tick(self):
        # real-time enemy turn + hunger + regen
        self.tick_count += 1
        p = self.player
        p["hunger"] = min(120, p["hunger"] + 0.2)
        if p["hunger"] >= 80:
            self.starve_acc += 1
            if self.starve_acc >= 25:  # ~12s of real time per starvation point
                self.starve_acc = 0
                p["hp"] -= 1
                self.killer = "starvation"
                self.msg("You are starving!", "danger")
                if p["hp"] <= 0:
                    p["hp"] = 0
                    self.game_over = True
                    self.msg("You starved to death.")
        elif p["hunger"] >= 50:
            if not self.hungry_warned:
                self.msg("You are getting hungry.")
                self.hungry_warned = True
        else:
            self.hungry_warned = False
            # slow regen while well fed and out of immediate danger
            if (p["hp"] < p["maxhp"] and self.tick_count % 10 == 0
                    and not any(e["hp"] > 0 and abs(e["x"]-p["x"]) + abs(e["y"]-p["y"]) <= 2
                                for e in self.entities)):
                p["hp"] += 1
        if p["hp"] < p["maxhp"] * 0.4 and p["potions"] > 0:
            self.hint("lowhp", "Low HP! Press p to drink a potion.")
        self.enemy_turn()
        self.reveal_secrets()
        self.compute_fov()

    def reveal_secrets(self):
        px, py = self.player["x"], self.player["y"]
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                x, y = px+dx, py+dy
                if 0 <= x < self.mw and 0 <= y < self.mh and self.grid[y][x] == 4:
                    if random.random() < 0.25:
                        self.grid[y][x] = 2
                        self.msg("You notice a secret door.", "sys")

    def attack(self, e):
        patk = self.total_atk()
        dmg = max(1, patk - 1 + random.randint(-1, 2))
        crit = random.random() < 0.1
        if crit:
            dmg = int(dmg * 1.8)
            self.msg("Critical hit!")
        e["hp"] -= dmg
        self.msg(f"You hit {ename(e)} for {dmg}.")
        self.add_fx("dmg", x=e["x"], y=e["y"], txt=str(dmg), life=0.7,
                    color=(255,90,70) if crit else (255,255,255))
        if e["hp"] <= 0:
            e["hp"] = 0
            self.add_fx("poof", x=e["x"], y=e["y"], life=0.5)
            self.msg(f"{cap(ename(e))} dies!", "sys")
            if e.get("boss"):
                self.msg("The way to the stairs is clear.", "sys")
                self.set_banner(f"{cap(ename(e))} is slain!", 3.0)
            self.player["xp"] += e.get("xp", 3)
            if random.random() < 0.4:
                amt = random.randint(1, 6) + self.floor
                self.player["gold"] += amt
                self.msg(f"It drops {amt} gold.")
            self.check_level()

    def enemy_turn(self):
        for e in self.entities:
            if e["hp"] <= 0:
                continue
            acts = 2 if e.get("fast") else 1
            if e.get("slow") and self.tick_count % 2:
                acts = 0
            for _ in range(acts):
                if self.game_over or e["hp"] <= 0:
                    break
                self.enemy_act(e)

    def enemy_act(self, e):
        p = self.player
        px, py = p["x"], p["y"]
        ex, ey = e["x"], e["y"]
        dist = abs(ex-px) + abs(ey-py)
        sees = (ex, ey) in self.visible or (dist <= 8 and self.line_of_sight(ex, ey, px, py))
        if sees and dist <= 8:
            e["alert"] = True
        if dist == 1:
            dmg = max(1, e["atk"] - self.total_def() + random.randint(-1, 1))
            if random.random() < 0.05:
                dmg = int(dmg * 1.7)
                self.msg(f"{cap(ename(e))} lands a brutal blow for {dmg}!", "danger")
            else:
                self.msg(f"{cap(ename(e))} hits you for {dmg}.", "danger")
            if e["ch"] == "V":
                e["hp"] = min(e["maxhp"], e["hp"] + dmg//2)
            self.killer = ename(e)
            p["hp"] -= dmg
            self.flash_until = time.time() + 0.25
            self.add_fx("dmg", x=px, y=py, txt=str(dmg), life=0.7, color=(239,68,68))
            if p["hp"] <= 0:
                p["hp"] = 0
                self.game_over = True
                self.msg(f"You were slain by {ename(e)}.", "danger")
            return
        if e["ch"] == "a" and sees and 2 <= dist <= 6:
            if random.random() < 0.6:
                dmg = max(1, e["atk"] - self.total_def() + random.randint(0, 1))
                self.add_fx("proj", x0=ex, y0=ey, x1=px, y1=py, life=0.22, color=(249,115,22))
                self.killer = ename(e)
                p["hp"] -= dmg
                self.flash_until = time.time() + 0.25
                self.add_fx("dmg", x=px, y=py, txt=str(dmg), life=0.7, color=(239,68,68))
                self.msg(f"{cap(ename(e))} shoots you for {dmg}.", "danger")
                if p["hp"] <= 0:
                    p["hp"] = 0; self.game_over = True
                    self.msg(f"You were shot by {ename(e)}.", "danger")
            return
        if e["ch"] == "n" and sees and random.random() < 0.25:
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = ex+dx, ey+dy
                if 0 <= nx < self.mw and 0 <= ny < self.mh and self.grid[ny][nx] == 1 \
                        and not any(o["x"] == nx and o["y"] == ny and o["hp"] > 0 for o in self.entities):
                    self.entities.append({"ch": "s", "x": nx, "y": ny, "hp": 8, "maxhp": 8,
                                          "atk": 3, "name": "s", "xp": 4})
                    self.msg("The necromancer summons a skeleton!", "danger")
                    break
        # movement
        if e.get("boss") or e.get("alert"):
            step = self.bfs_next((ex, ey), (px, py))
            if step:
                e["x"], e["y"] = step
                return
        if sees or dist <= 7:
            e["alert"] = True
            dx = 0
            if ex < px: dx = 1
            elif ex > px: dx = -1
            dy = 0
            if ey < py: dy = 1
            elif ey > py: dy = -1
            if e["ch"] == "b" and random.random() < 0.4:
                dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1),(0,0)])
            nx, ny = ex+dx, ey+dy
            if 0 <= nx < self.mw and 0 <= ny < self.mh and self.grid[ny][nx] in (1, 2, 3) \
                    and not any(o["x"] == nx and o["y"] == ny and o["hp"] > 0 for o in self.entities if o is not e) \
                    and not (nx == px and ny == py):
                e["x"], e["y"] = nx, ny
        elif random.random() < 0.2:
            dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1)])
            nx, ny = ex+dx, ey+dy
            if 0 <= nx < self.mw and 0 <= ny < self.mh and self.grid[ny][nx] == 1 \
                    and not any(o["x"] == nx and o["y"] == ny and o["hp"] > 0 for o in self.entities if o is not e) \
                    and not (nx == px and ny == py):
                e["x"], e["y"] = nx, ny

    def trigger_trap(self, t):
        t["triggered"] = True
        ch = t["ch"]
        if ch == "^":
            dmg = random.randint(3, 8) + self.floor//2
            self.player["hp"] -= dmg
            self.killer = "the spike trap"
            self.msg(f"A spike trap hits you for {dmg}!", "danger")
        elif ch == "~":
            self.player["hp"] = max(1, self.player["hp"]-4)
            self.player["hunger"] += 20
            self.msg("Poison! HP -4, hunger +20.", "danger")
        elif ch == "@":
            tiles = [(x,y) for y in range(self.mh) for x in range(self.mw) if self.grid[y][x]==1 and (x,y)!=(self.player["x"],self.player["y"])]
            if tiles:
                self.player["x"],self.player["y"] = random.choice(tiles)
                self.msg("Teleport trap!")
        elif ch == "!":
            for _ in range(random.randint(1,3)):
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx,ny = self.player["x"]+dx, self.player["y"]+dy
                    if 0<=nx<self.mw and 0<=ny<self.mh and self.grid[ny][nx]==1 and not any(o["x"]==nx and o["y"]==ny and o["hp"]>0 for o in self.entities):
                        self.entities.append({"ch":"g","x":nx,"y":ny,"hp":6,"maxhp":6,"atk":2,"name":"g","xp":3})
                        break
            self.msg("Alarm! Enemies appear.", "danger")
        if self.player["hp"] <= 0:
            self.player["hp"]=0; self.game_over=True

    def pickup(self, it):
        ch = it["ch"]
        if ch == "!":
            self.player["potions"] += 1
            self.msg("You pick up a health potion.", "loot")
            self.hint("potion", "Press p to drink a potion.")
        elif ch == "*":
            self.player["food"] += 1
            self.msg("You pick up food.", "loot")
            self.hint("eat", "Press f to eat when hungry.")
        elif ch == "/":
            wname = f"weapon (+{2+self.floor//3} ATK)"
            self.player["inventory"].append({"ch":"/","name":wname,"item":{"type":"weapon","atk":2+self.floor//3,"name":wname},"kind":"equip"})
            self.msg("You find a weapon. (i to equip)", "loot")
            self.hint("equip", "Press i to open inventory and equip.")
        elif ch == "[":
            aname = f"armor (+{1+self.floor//4} DEF)"
            self.player["inventory"].append({"ch":"[","name":aname,"item":{"type":"armor","def":1+self.floor//4,"hp":2+self.floor//2,"name":aname},"kind":"equip"})
            self.msg("You find armor.", "loot")
        elif ch == "$":
            amt = random.randint(5, 20) + self.floor*2
            self.player["gold"] += amt
            self.msg(f"You find {amt} gold.", "loot")
        elif ch == "?":
            self.player["scrolls"] += 1
            self.msg("You find a scroll.", "loot")
            self.hint("scroll", "Press r to read a scroll.")
        elif ch == "=":
            self.player["inventory"].append({"ch":"=","name":"ring (+1 ATK/DEF)","item":{"type":"ring","atk":1,"def":1,"name":"ring (+1 ATK/DEF)"},"kind":"equip"})
            self.msg("You find a ring.", "loot")
        elif ch == "w":
            self.player["inventory"].append({"ch":"w","name":"wand (fireball)","item":{"type":"wand"},"kind":"wand"})
            self.msg("You find a wand.", "loot")
        elif ch == "k":
            self.player["keys"] += 1
            self.msg("You pick up a key.", "loot")

    def use_potion(self):
        if self.player["potions"] <= 0:
            self.msg("No potions."); return
        self.player["potions"] -= 1
        heal = random.randint(10, 16) + self.player["level"]
        self.player["hp"] = min(self.player["maxhp"], self.player["hp"]+heal)
        self.add_fx("dmg", x=self.player["x"], y=self.player["y"], txt=f"+{heal}", life=0.7, color=(63,185,80))
        self.msg(f"You drink a potion. +{heal} HP.")
        self.compute_fov()

    def eat_food(self):
        if self.player["food"] <= 0:
            self.msg("No food."); return
        self.player["food"] -= 1
        self.player["hunger"] = max(0, self.player["hunger"]-40)
        self.player["hp"] = min(self.player["maxhp"], self.player["hp"]+5)
        self.msg("You eat. Hunger -40, +5 HP.")
        self.compute_fov()

    def use_scroll(self):
        if self.player["scrolls"] <= 0:
            self.msg("No scrolls."); return
        effect = random.choice(["reveal","fireball","teleport","heal"])
        if effect == "fireball":
            targets = [e for e in self.entities
                       if e["hp"] > 0 and (e["x"], e["y"]) in self.visible]
            if not targets:
                self.msg("No target in sight for the fireball.")
                return  # scroll not wasted
        self.player["scrolls"] -= 1
        if effect == "reveal":
            for y in range(self.mh):
                for x in range(self.mw):
                    self.explored.add((x,y))
            self.msg("The scroll reveals the floor.")
        elif effect == "fireball":
            targets = [e for e in self.entities
                       if e["hp"] > 0 and (e["x"], e["y"]) in self.visible]
            targets.sort(key=lambda e: abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"]))
            t = targets[0]
            self.add_fx("boom", x=t["x"], y=t["y"], life=0.45)
            self.msg("A fireball erupts!")
            for e in list(targets):
                d = abs(e["x"]-t["x"]) + abs(e["y"]-t["y"])
                if d <= 1:
                    dmg = 14 if d == 0 else 7
                    e["hp"] -= dmg
                    self.add_fx("dmg", x=e["x"], y=e["y"], txt=str(dmg), life=0.7, color=(255,140,0))
                    if e["hp"] <= 0:
                        e["hp"] = 0
                        self.add_fx("poof", x=e["x"], y=e["y"], life=0.5)
                        self.msg(f"{cap(ename(e))} dies!", "sys")
                        self.player["xp"] += e.get("xp", 3)
                        self.check_level()
        elif effect == "teleport":
            tiles = [(x,y) for y in range(self.mh) for x in range(self.mw) if self.grid[y][x] in (1,2,3) and not any(e["x"]==x and e["y"]==y and e["hp"]>0 for e in self.entities)]
            if tiles:
                self.player["x"], self.player["y"] = random.choice(tiles)
                self.msg("You teleport.")
                self.compute_fov()
        else:
            self.player["hp"] = self.player["maxhp"]
            self.msg("Full heal.")
        self.compute_fov()

    def use_wand(self, inv_item):
        cnt = 0
        for e in self.entities:
            if e["hp"]>0 and (e["x"],e["y"]) in self.visible:
                d = abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"])
                if d <= 5 and self.line_of_sight(self.player["x"],self.player["y"],e["x"],e["y"]):
                    self.add_fx("beam", x0=self.player["x"], y0=self.player["y"],
                                x1=e["x"], y1=e["y"], life=0.3)
                    self.add_fx("dmg", x=e["x"], y=e["y"], txt="15", life=0.7, color=(196,181,253))
                    e["hp"] -= 15; cnt += 1
                    if e["hp"]<=0:
                        e["hp"]=0
                        self.add_fx("poof", x=e["x"], y=e["y"], life=0.5)
                        self.msg(f"{cap(ename(e))} dies!", "sys")
                        self.player["xp"] += e.get("xp",3); self.check_level()
        self.msg(f"The wand zaps {cnt} enemies.")
        self.player["inventory"] = [i for i in self.player["inventory"] if i is not inv_item]
        self.compute_fov()

    def check_level(self):
        need = self.player["level"] * 12
        while self.player["xp"] >= need:
            self.player["xp"] -= need
            self.player["level"] += 1
            self.player["maxhp"] += 6
            self.player["hp"] = self.player["maxhp"]
            self.player["atk"] += 1
            self.player["def"] += 1
            self.msg(f"Level up! You are level {self.player['level']}.", "sys")
            self.set_banner("LEVEL UP!", 1.5)
            need = self.player["level"] * 12

    def search(self):
        px, py = self.player["x"], self.player["y"]
        found = 0
        for dy in range(-2,3):
            for dx in range(-2,3):
                x,y = px+dx, py+dy
                if 0<=x<self.mw and 0<=y<self.mh and self.grid[y][x]==4:
                    self.grid[y][x] = 2; found += 1
        self.msg(f"You find {found} secret door(s)." if found else "Nothing found.")
        self.compute_fov()

    def open_inventory(self):
        self.inventory_open = True
        self.inv_cursor = 0

    def close_inventory(self):
        self.inventory_open = False

    def add_fx(self, kind, **kw):
        kw["kind"] = kind
        kw["t"] = time.time()
        self.effects.append(kw)
        if len(self.effects) > 200:
            self.effects = self.effects[-200:]

    def merchant_adjacent(self):
        m = self.merchant
        return bool(m) and abs(m["x"]-self.player["x"]) + abs(m["y"]-self.player["y"]) <= 1

    def shop_price(self, g):
        return g["base"] + self.floor * 3

    def open_shop(self):
        self.shop_open = True
        self.shop_cursor = 0

    def shop_action(self, key):
        if key in (27, ord('v'), ord('q')):
            self.shop_open = False
            return
        if key in (curses.KEY_UP, ord('k')):
            self.shop_cursor = max(0, self.shop_cursor - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            self.shop_cursor = min(len(SHOP_GOODS)-1, self.shop_cursor + 1)
        elif key in (10, 13):
            self.shop_buy()

    def shop_buy(self):
        g = SHOP_GOODS[self.shop_cursor]
        price = self.shop_price(g)
        p = self.player
        if p["gold"] < price:
            self.msg("Not enough gold.")
            return
        ch = g["ch"]
        if ch == "!":
            p["potions"] += 1
        elif ch == "?":
            p["scrolls"] += 1
        elif ch == "*":
            p["food"] += 1
        elif ch == "k":
            p["keys"] += 1
        elif ch == "/":
            self.equip_item({"type": "weapon", "atk": 3+self.floor//2,
                             "name": f"steel weapon (+{3+self.floor//2} ATK)"})
        elif ch == "[":
            self.equip_item({"type": "armor", "def": 2+self.floor//4, "hp": 4+self.floor//2,
                             "name": f"plate armor (+{2+self.floor//4} DEF)"})
        elif ch == "@":
            p["maxhp"] += 10
            p["hp"] += 10
        p["gold"] -= price
        self.msg(f"Bought {g['name']} for {price} gold.")

    def equip_item(self, item):
        slot = item["type"]
        if slot == "weapon":
            if self.player["weapon"]:
                self.player["inventory"].append({"ch":"/","name":self.player["weapon"].get("name","weapon"),"item":self.player["weapon"],"kind":"equip"})
            self.player["weapon"] = item
        elif slot == "armor":
            if self.player["armor"]:
                self.player["maxhp"] -= self.player["armor"].get("hp",0)
                self.player["hp"] = min(self.player["hp"], self.player["maxhp"])
                self.player["inventory"].append({"ch":"[","name":self.player["armor"].get("name","armor"),"item":self.player["armor"],"kind":"equip"})
            self.player["armor"] = item
            self.player["maxhp"] += item.get("hp",0)
            self.player["hp"] = min(self.player["hp"]+item.get("hp",0), self.player["maxhp"])
        elif slot == "ring":
            if self.player["ring"]:
                self.player["inventory"].append({"ch":"=","name":self.player["ring"].get("name","ring"),"item":self.player["ring"],"kind":"equip"})
            self.player["ring"] = item

    def inventory_action(self, key):
        inv = self.player["inventory"]
        if key in (27, ord('i'), ord('q')):
            self.close_inventory(); return
        if key in (curses.KEY_UP, ord('k')):
            self.inv_cursor = max(0, self.inv_cursor-1)
        elif key in (curses.KEY_DOWN, ord('j')):
            self.inv_cursor = min(max(0,len(inv)-1), self.inv_cursor+1)
        elif key in (10, 13):
            if not inv: return
            it = inv[self.inv_cursor]
            if it["kind"] == "equip":
                item = it["item"]
                self.equip_item(item)
                self.player["inventory"].remove(it)
                self.msg(f"Equipped {item.get('name', item['type'])}.")
            elif it["kind"] == "wand":
                self.use_wand(it)
                self.close_inventory()
                return
        elif key == ord('d'):
            if inv and 0 <= self.inv_cursor < len(inv):
                it = inv.pop(self.inv_cursor)
                self.msg(f"Dropped {it['name']}.")
                if self.inv_cursor >= len(inv):
                    self.inv_cursor = max(0, len(inv)-1)

    def handle_input(self, key):
        if self.help_open:
            self.help_open = False
            return
        if self.shop_open:
            self.shop_action(key)
            return
        if self.inventory_open:
            self.inventory_action(key)
            return
        if key in (ord('q'), 27):
            return "quit"
        if key == ord('A'):
            self.auto = not self.auto
            self.msg("Auto-pilot: " + ("ON" if self.auto else "OFF"))
            return
        if key == ord('?'):
            self.help_open = True
            return
        if key in (curses.KEY_UP, ord('k'), ord('w')): self.move_player(0,-1)
        elif key in (curses.KEY_DOWN, ord('j'), ord('s')): self.move_player(0,1)
        elif key in (curses.KEY_LEFT, ord('h'), ord('a')): self.move_player(-1,0)
        elif key in (curses.KEY_RIGHT, ord('l'), ord('d')): self.move_player(1,0)
        elif key == ord('y'): self.move_player(-1,-1)
        elif key == ord('u'): self.move_player(1,-1)
        elif key == ord('b'): self.move_player(-1,1)
        elif key == ord('n'): self.move_player(1,1)
        elif key == ord('p'): self.use_potion()
        elif key == ord('f'): self.eat_food()
        elif key == ord('r'): self.use_scroll()
        elif key == ord('i'): self.open_inventory()
        elif key == ord('v'):
            if self.merchant_adjacent():
                self.open_shop()
            else:
                self.msg("No merchant nearby.")
        elif key == ord('c'): self.msg(self.char_sheet())
        elif key == ord('x'): self.search()
        elif key == ord('>'): self.move_stairs()
        elif key == ord('S'): self.save_game()
        elif key == ord('L'): self.load_game()

    def stairs_blocked(self):
        for e in self.entities:
            if e.get("boss") and e["hp"] > 0:
                return e
        return None

    def move_stairs(self):
        if self.grid[self.player["y"]][self.player["x"]] == 3:
            boss = self.stairs_blocked()
            if boss:
                self.msg(f"{cap(ename(boss))} blocks the stairs!")
                self.set_banner(f"{cap(ename(boss))} guards the stairs!", 2.0)
                return
            if self.floor >= 15:
                self.victory = True; self.game_over = True
                self.msg("You escaped the depths!", "sys")
                return
            self.floor += 1
            self.msg(f"You descend to floor {self.floor}.", "sys")
            self.new_floor()

    def load_game(self):
        try:
            with open(SAVE) as f:
                data = json.load(f)
        except Exception:
            self.msg("No save found.")
            return
        self.floor = data["floor"]
        self.player = data["player"]
        for k, v in (("keys",0),("food",0),("potions",0),("scrolls",0),("hunger",0),
                     ("inventory",[]),("weapon",None),("armor",None),("ring",None)):
            self.player.setdefault(k, v)
        self.explored = set(tuple(t) for t in data["explored"])
        self.messages = [{"t": t, "k": "info"} for t in data.get("messages", [])]
        self.grid, rooms = make_dungeon(self.floor, self.mw, self.mh)
        self.entities, self.items, self.traps, self.merchant = place_entities(
            self.grid, self.mw, self.mh, self.floor, (self.player["x"], self.player["y"]), rooms)
        for e in self.entities + [self.player]:
            e.pop("rx", None); e.pop("ry", None)
        if self.grid[self.player["y"]][self.player["x"]] not in (1, 2, 3):
            rx, ry, rw, rh = rooms[0]
            self.player["x"], self.player["y"] = rx + rw//2, ry + rh//2
        self.game_over = False
        self.victory = False
        self.msg("Game loaded.", "sys")
        self.compute_fov()

    def char_sheet(self):
        p = self.player
        return (f"LVL {p['level']}  HP {p['hp']}/{p['maxhp']}  ATK {self.total_atk()}  DEF {self.total_def()}  "
                f"XP {p['xp']}/{p['level']*12}  Gold {p['gold']}  Food {p['food']}  Hunger {p['hunger']}  "
                f"Keys {p['keys']}")

    def save_game(self):
        try:
            json.dump({"floor":self.floor,"player":self.player,
                       "explored":[list(t) for t in self.explored],
                       "messages":[m["t"] for m in self.messages[-5:]]},
                      open(SAVE,"w"))
            self.msg("Game saved.", "sys")
        except Exception as e:
            self.msg(f"Save failed: {e}")

    def bfs_next(self, start, goal):
        from collections import deque
        if start == goal:
            return None
        occupied = {(e["x"], e["y"]) for e in self.entities if e["hp"] > 0}
        occupied.discard(goal)
        occupied.discard(start)
        def walkable(x, y):
            if not (0 <= x < self.mw and 0 <= y < self.mh):
                return False
            if self.grid[y][x] in (0, 4, 5):
                return False
            if (x, y) in occupied:
                return False
            return True
        q = deque([start])
        prev = {start: None}
        while q:
            x, y = q.popleft()
            if (x, y) == goal:
                break
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x+dx, y+dy
                if (nx, ny) not in prev and walkable(nx, ny):
                    prev[(nx, ny)] = (x, y)
                    q.append((nx, ny))
        if goal not in prev:
            return None
        cur = goal
        path = []
        while cur is not None and cur != start:
            path.append(cur)
            cur = prev[cur]
        if not path:
            return None
        path.reverse()
        return path[0]

    def auto_step(self):
        if self.game_over:
            return
        if self.inventory_open or self.shop_open or self.help_open:
            self.close_inventory()
            self.shop_open = False
            self.help_open = False
            return
        # heal
        if self.player["hp"] < self.player["maxhp"] * 0.35 and self.player["potions"] > 0:
            self.use_potion(); return
        if self.player["hunger"] > 55 and self.player["food"] > 0:
            self.eat_food(); return
        # adjacent enemy -> attack
        for e in self.entities:
            if e["hp"] > 0 and abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"]) == 1:
                self.move_player(e["x"]-self.player["x"], e["y"]-self.player["y"])
                return
        # choose target
        target = None
        boss = self.stairs_blocked()
        if boss:
            target = (boss["x"], boss["y"])
        else:
            enemies = [e for e in self.entities if e["hp"] > 0 and (e["x"], e["y"]) in self.visible]
            if enemies:
                enemies.sort(key=lambda e: abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"]))
                target = (enemies[0]["x"], enemies[0]["y"])
            else:
                vis_items = [it for it in self.items if (it["x"], it["y"]) in self.visible]
                if vis_items:
                    vis_items.sort(key=lambda it: abs(it["x"]-self.player["x"]) + abs(it["y"]-self.player["y"]))
                    target = (vis_items[0]["x"], vis_items[0]["y"])
                else:
                    for y in range(self.mh):
                        for x in range(self.mw):
                            if self.grid[y][x] == 3:
                                target = (x, y)
                    if target is None:
                        # nearest unexplored floor tile
                        best = None; bestd = 10**9
                        for y in range(self.mh):
                            for x in range(self.mw):
                                if (x, y) not in self.explored and self.grid[y][x] in (1, 2):
                                    d = abs(x-self.player["x"]) + abs(y-self.player["y"])
                                    if d < bestd:
                                        bestd = d; best = (x, y)
                        target = best
        if target is None:
            return
        if (self.player["x"], self.player["y"]) == target and self.grid[self.player["y"]][self.player["x"]] == 3:
            self.move_stairs(); return
        step = self.bfs_next((self.player["x"], self.player["y"]), target)
        if step:
            self.move_player(step[0]-self.player["x"], step[1]-self.player["y"])
            return
        # fallback random
        for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
            nx, ny = self.player["x"]+dx, self.player["y"]+dy
            if 0 <= nx < self.mw and 0 <= ny < self.mh and self.grid[ny][nx] in (1,2,3) and not any(e["x"]==nx and e["y"]==ny and e["hp"]>0 for e in self.entities):
                self.move_player(dx, dy); return

    def draw(self):
        if self.stdscr is None:
            if os.environ.get("DEPTHS_RENDER") == "sixel":
                render_sixel(self)
            else:
                render_kitty(self)
        else:
            self.draw_curses()

    def draw_curses(self):
        self.stdscr.erase()
        for y in range(self.mh):
            for x in range(self.mw):
                ch = self.grid[y][x]
                if (x,y) in self.visible:
                    if ch == 0:
                        self.stdscr.addstr(y, x, " ", cp("wall"))
                    elif ch == 1:
                        self.stdscr.addstr(y, x, " ", cp("floor"))
                    elif ch == 3:
                        self.stdscr.addstr(y, x, ">", cp("stairs"))
                    elif ch in (2,4):
                        self.stdscr.addstr(y, x, "+", cp("door"))
                elif (x,y) in self.explored:
                    if ch == 5:
                        self.stdscr.addstr(y, x, "+", cp("key"))
                    else:
                        self.stdscr.addstr(y, x, " ", cp("dim"))
        for t in self.traps:
            if (t["x"],t["y"]) in self.visible and t.get("triggered"):
                self.stdscr.addstr(t["y"], t["x"], t["ch"], cp("trap"))
        for it in self.items:
            if (it["x"],it["y"]) in self.visible:
                col = {"!":"potion","*":"food","/":"weapon","[":"armor","$":"gold","?":"scroll","=":"ring","w":"wand","k":"key"}[it["ch"]]
                self.stdscr.addstr(it["y"], it["x"], it["ch"], cp(col))
            elif (it["x"],it["y"]) in self.explored:
                self.stdscr.addstr(it["y"], it["x"], it["ch"], cp("dim"))
        for e in self.entities:
            if e["hp"]>0 and e.get("disguise") and (e["x"],e["y"]) in self.visible:
                col = {"!":"potion","*":"food","/":"weapon","[":"armor","$":"gold","?":"scroll","=":"ring"}[e["disguise"]]
                self.stdscr.addstr(e["y"], e["x"], e["disguise"], cp(col))
        ENEMY_COLOR = {"g":"goblin","o":"orc","T":"troll","D":"dragon","s":"skeleton",
            "b":"bat","W":"wraith","a":"archer","n":"necromancer","m":"mimic","r":"rat",
            "V":"vampire","G":"golem","B":"bossB","Z":"bossZ","L":"bossL"}
        for e in self.entities:
            if e["hp"]>0 and not e.get("disguise") and (e["x"],e["y"]) in self.visible:
                attr = cp(ENEMY_COLOR.get(e["ch"], "goblin"))
                if e.get("boss"):
                    attr |= curses.A_BOLD
                self.stdscr.addstr(e["y"], e["x"], e["ch"], attr)
        if self.merchant and (self.merchant["x"], self.merchant["y"]) in self.visible:
            self.stdscr.addstr(self.merchant["y"], self.merchant["x"], "M", cp("gold") | curses.A_BOLD)
        self.stdscr.addstr(self.player["y"], self.player["x"], PLAYER, cp("player"))
        sy = self.mh
        p = self.player
        hp_bar = f"HP:{p['hp']}/{p['maxhp']}"
        sp = self.stairs_pos()
        if sp and sp in self.explored:
            ddx, ddy = sp[0]-p["x"], sp[1]-p["y"]
            ang = ("E","SE","S","SW","W","NW","N","NE")[
                int(((math.degrees(math.atan2(ddy, ddx)) % 360) + 22.5) // 45) % 8]
            stairs_txt = f"{ang}:{abs(ddx)+abs(ddy)}"
        else:
            stairs_txt = "?"
        status = (f" Fl{self.floor}/15 {biome(self.floor)}  {hp_bar}  stairs {stairs_txt}  "
                  f"ATK {self.total_atk()}  DEF {self.total_def()}  "
                  f"LVL {p['level']}  XP {p['xp']}/{p['level']*12}  Gold {p['gold']}  Food {p['food']}  "
                  f"Hng {p['hunger']}  Pot {p['potions']}  Scr {p['scrolls']}  Keys {p['keys']} ")
        self.stdscr.addstr(sy, 0, ("-"*(self.mw-1)), cp("dim"))
        self.stdscr.addstr(sy+1, 0, status[:self.mw-1], cp("text"))
        msg_col = {"info": "text", "danger": "hp", "loot": "gold", "sys": "title", "hint": "player"}
        for i, m in enumerate(self.messages[-2:]):
            self.stdscr.addstr(sy+2+i, 0, m["t"][:self.mw-1], cp(msg_col.get(m["k"], "text")))
        if self.inventory_open:
            self.draw_inventory_curses()
        if self.shop_open:
            self.draw_shop_curses()
        if self.help_open:
            self.draw_help_curses()
        self.stdscr.refresh()

    def draw_help_curses(self):
        h, w = self.stdscr.getmaxyx()
        box_w = min(64, w-4)
        box_h = min(16, h-4)
        sx = (w - box_w)//2
        sy = (h - box_h)//2
        for yy in range(sy, sy+box_h):
            self.stdscr.addstr(yy, sx, " "*box_w, cp("inv"))
        self.stdscr.addstr(sy, sx, "-"*box_w, cp("inv"))
        self.stdscr.addstr(sy, sx+2, " HELP ", cp("inv"))
        lines = [
            "Goal: descend 15 floors. Slay the boss guarding the stairs.",
            "Locked doors need keys. Mimics look like items.",
            "Stand on > and press > to descend.",
            "",
            "Move: arrows / WASD / hjkl, diagonals yubn",
            "p potion  f eat  r scroll  i inventory  v trade",
            "x search  c stats  S save  L load  A auto",
            "? this help   q quit",
            "",
            "Press any key to close.",
        ]
        y = sy+1
        for l in lines:
            if y >= sy+box_h-1: break
            self.stdscr.addstr(y, sx+1, l[:box_w-2], cp("text")); y += 1

    def draw_shop_curses(self):
        h, w = self.stdscr.getmaxyx()
        box_w = min(50, w-4)
        box_h = min(16, h-4)
        sx = (w - box_w)//2
        sy = (h - box_h)//2
        for yy in range(sy, sy+box_h):
            self.stdscr.addstr(yy, sx, " "*box_w, cp("gold"))
        self.stdscr.addstr(sy, sx, "-"*box_w, cp("gold"))
        self.stdscr.addstr(sy, sx+2, f" MERCHANT  Gold: {self.player['gold']} ", cp("gold"))
        y = sy+1
        for i, g in enumerate(SHOP_GOODS):
            if y >= sy+box_h-2: break
            price = self.shop_price(g)
            mark = ">" if i == self.shop_cursor else " "
            attr = cp("equip") if i == self.shop_cursor else cp("text")
            self.stdscr.addstr(y, sx+1, f"{mark} {g['name'][:20]:<20} {price}g"[:box_w-2], attr)
            y += 1
        self.stdscr.addstr(sy+box_h-1, sx+1, "Enter=buy  v/q=close"[:box_w-2], cp("dim"))

    def draw_inventory_curses(self):
        inv = self.player["inventory"]
        h, w = self.stdscr.getmaxyx()
        box_w = min(60, w-4)
        box_h = min(20, h-4)
        sx = (w - box_w)//2
        sy = (h - box_h)//2
        for yy in range(sy, sy+box_h):
            self.stdscr.addstr(yy, sx, " "*box_w, cp("inv"))
        self.stdscr.addstr(sy, sx, "-"*box_w, cp("inv"))
        self.stdscr.addstr(sy, sx+2, " INVENTORY ", cp("inv"))
        lines = [f"Weapon: {self.player['weapon']['name'] if self.player['weapon'] and 'name' in self.player['weapon'] else (self.player['weapon']['type'] if self.player['weapon'] else 'none')}",
                 f"Armor:  {self.player['armor']['type'] if self.player['armor'] else 'none'}",
                 f"Ring:   {self.player['ring']['type'] if self.player['ring'] else 'none'}",
                 "", "Items:"]
        y = sy+1
        for l in lines:
            if y < sy+box_h-1:
                self.stdscr.addstr(y, sx+1, l[:box_w-2], cp("text")); y+=1
        for i, it in enumerate(inv):
            if y >= sy+box_h-2: break
            mark = ">" if i == self.inv_cursor else " "
            d = self.item_delta(it)
            if i == self.inv_cursor:
                attr = cp("equip")
            elif d is not None and d > 0:
                attr = cp("player")
            elif d is not None and d < 0:
                attr = cp("hp")
            else:
                attr = cp("text")
            extra = f" ({d:+d})" if d is not None and d != 0 else ""
            self.stdscr.addstr(y, sx+1, f"{mark} {it['name']}{extra}"[:box_w-2], attr)
            y += 1
        if not inv and y < sy+box_h-2:
            self.stdscr.addstr(y, sx+1, "(empty)", cp("dim")); y+=1
        self.stdscr.addstr(sy+box_h-1, sx+1, "Enter=equip/use  d=drop  i/q=close"[:box_w-2], cp("dim"))

# ---------- Kitty pixel rendering ----------
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

def send_kitty(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    data = base64.b64encode(buf.getvalue()).decode('ascii')
    # delete previous images
    import shutil
    ts = shutil.get_terminal_size((80, 24))
    sys.stdout.write("\x1b[?25l")
    sys.stdout.write("\x1b_Ga=d,d=A\x1b\\")
    sys.stdout.write("\x1b[2J\x1b[H")
    # display scaled to full terminal grid (c cols, r rows) -> no scroll
    hdr = "\x1b_Ga=T,f=100,C=1,c=%d,r=%d" % (ts.columns, ts.lines)
    chunk_size = 4096
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    if not chunks:
        sys.stdout.flush(); return
    if len(chunks) == 1:
        sys.stdout.write(f"\x1b_Ga=T,f=100,C=1;{chunks[0]}\x1b\\")
    else:
        sys.stdout.write(f"\x1b_Ga=T,f=100,C=1,m=1;{chunks[0]}\x1b\\")
        for ch in chunks[1:-1]:
            sys.stdout.write(f"\x1b_Gm=1;{ch}\x1b\\")
        sys.stdout.write(f"\x1b_Gm=0;{chunks[-1]}\x1b\\")
    sys.stdout.flush()

TILE = 16
MAP_TILES_W = 40
MAP_TILES_H = 25
SIDE_W = 290
PAD = 10

def draw_item_glyph(draw, cx, cy, ch, col, u=1.0, dim=False):
    """Distinguishable item glyph centered at (cx, cy); u scales with tile size."""
    dark = (0, 0, 0)
    if dim:
        col = tuple(v//3 for v in col)
    w = max(2, int(1.5*u))
    if ch == "!":  # potion flask
        draw.rectangle([cx-int(1.5*u), cy-int(6*u), cx+int(1.5*u), cy-int(2*u)], fill=col, outline=dark)
        draw.ellipse([cx-int(4*u), cy-int(2*u), cx+int(4*u), cy+int(5*u)], fill=col, outline=dark)
        draw.ellipse([cx-int(2*u), cy, cx-int(0), cy+int(2*u)], fill=(255,255,255))
    elif ch == "/":  # sword
        draw.line([(cx-int(4*u), cy+int(5*u)), (cx+int(4*u), cy-int(5*u))], fill=col, width=max(2, int(2*u)))
        draw.line([(cx-int(2*u), cy-int(1*u)), (cx+int(2*u), cy+int(2*u))], fill=dark, width=1)
        draw.ellipse([cx-int(6*u), cy+int(4*u), cx-int(3*u), cy+int(7*u)], fill=col, outline=dark)
    elif ch == "[":  # shield
        draw.polygon([(cx, cy-int(5*u)), (cx+int(4*u), cy-int(3*u)), (cx+int(4*u), cy+int(1*u)),
                      (cx, cy+int(5*u)), (cx-int(4*u), cy+int(1*u)), (cx-int(4*u), cy-int(3*u))],
                     fill=col, outline=dark)
        draw.line([(cx, cy-int(3*u)), (cx, cy+int(3*u))], fill=dark, width=1)
    elif ch == "$":  # coin stack
        draw.ellipse([cx-int(4*u), cy, cx+int(4*u), cy+int(5*u)], fill=col, outline=dark)
        draw.ellipse([cx-int(4*u), cy-int(4*u), cx+int(4*u), cy+int(1*u)], fill=col, outline=dark)
        draw.line([(cx, cy-int(3*u)), (cx, cy)], fill=dark, width=1)
    elif ch == "?":  # scroll
        draw.rectangle([cx-int(4*u), cy-int(3*u), cx+int(4*u), cy+int(3*u)], fill=col, outline=dark)
        draw.line([(cx-int(2*u), cy-2), (cx+int(2*u), cy-2)], fill=dark, width=1)
        draw.line([(cx-int(2*u), cy+1), (cx+int(2*u), cy+1)], fill=dark, width=1)
    elif ch == "*":  # apple
        draw.ellipse([cx-int(4*u), cy-int(3*u), cx+int(4*u), cy+int(5*u)], fill=col, outline=dark)
        draw.line([(cx, cy-int(3*u)), (cx+int(1*u), cy-int(5*u))], fill=(102,64,20), width=max(1, int(u)))
        draw.ellipse([cx+u, cy-int(5*u), cx+int(3*u), cy-int(3*u)], fill=(102,64,20))
    elif ch == "=":  # ring
        draw.ellipse([cx-int(3*u), cy-int(1*u), cx+int(3*u), cy+int(5*u)], outline=col, width=w)
        draw.ellipse([cx-int(1*u), cy-int(4*u), cx+int(1*u), cy-int(2*u)], fill=(255,80,200), outline=dark)
    elif ch in ("(", "w"):  # wand
        draw.line([(cx-int(3*u), cy+int(5*u)), (cx+int(2*u), cy-int(3*u))], fill=col, width=max(2, int(2*u)))
        draw.ellipse([cx, cy-int(6*u), cx+int(3*u), cy-int(3*u)], fill=(255,255,255), outline=dark)
    elif ch == "k":  # key
        draw.ellipse([cx-int(5*u), cy-int(5*u), cx-int(1*u), cy-int(1*u)], outline=col, width=w)
        draw.line([(cx-int(1*u), cy-int(1*u)), (cx+int(5*u), cy+int(5*u))], fill=col, width=w)
        draw.line([(cx+int(5*u), cy+int(5*u)), (cx+int(3*u), cy+int(5*u))], fill=col, width=w)
        draw.line([(cx+int(3*u), cy+int(3*u)), (cx+int(5*u), cy+int(3*u))], fill=col, width=max(1, int(u)))
    else:
        draw.ellipse([cx-int(4*u), cy-int(4*u), cx+int(4*u), cy+int(4*u)], fill=col, outline=dark)

def _draw_frame(game):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    img_w, img_h = get_terminal_pixels()
    global TILE
    TILE = max(8, min((img_w - SIDE_W - PAD*2)//MAP_TILES_W, (img_h - PAD*2)//MAP_TILES_H))
    img = Image.new('RGB', (img_w, img_h), RGB["bg"])
    draw = ImageDraw.Draw(img)
    # smooth movement: ease render coords toward logical cell coords
    now = time.time()
    dt = min(0.1, now - game._draw_t) if game._draw_t else 0.016
    game._draw_t = now
    lerp = min(1.0, dt * 12)
    for e in game.entities:
        if "rx" not in e:
            e["rx"], e["ry"] = float(e["x"]), float(e["y"])
        e["rx"] += (e["x"] - e["rx"]) * lerp
        e["ry"] += (e["y"] - e["ry"]) * lerp
    pl = game.player
    if "rx" not in pl:
        pl["rx"], pl["ry"] = float(pl["x"]), float(pl["y"])
    pl["rx"] += (pl["x"] - pl["rx"]) * lerp
    pl["ry"] += (pl["y"] - pl["ry"]) * lerp
    # font
    font_path = None
    for p in ("/usr/share/fonts/TTF/JetBrainsMonoNerdFontMono-Regular.ttf",
              "/usr/share/fonts/TTF/JetBrainsMonoNerdFontMono-Bold.ttf",
              "/usr/share/fonts/noto/NotoSansMono-Regular.ttf"):
        if os.path.exists(p):
            font_path = p; break
    try:
        font = ImageFont.truetype(font_path, 12) if font_path else ImageFont.load_default()
        font_small = ImageFont.truetype(font_path, 10) if font_path else ImageFont.load_default()
        font_big = ImageFont.truetype(font_path, 14) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default(); font_small = font; font_big = font

    ox, oy = PAD, PAD
    # map
    for y in range(MAP_TILES_H):
        for x in range(MAP_TILES_W):
            if x >= game.mw or y >= game.mh:
                continue
            rx = ox + x * TILE
            ry = oy + y * TILE
            key = (x, y)
            explored = key in game.explored
            visible = key in game.visible
            cell = game.grid[y][x] if (y < len(game.grid) and x < len(game.grid[y])) else 0
            if not explored:
                col = RGB["bg"]
            elif not visible:
                col = RGB["dim"]
            else:
                if cell == 0: col = RGB["wall"]
                elif cell == 1: col = RGB["floor"] if ((x+y)%2==0) else RGB["floorHi"]
                elif cell == 3: col = RGB["stairs"]
                elif cell == 5: col = (66,52,30)
                elif cell in (2,4): col = RGB["door"]
                else: col = RGB["floor"]
            draw.rectangle([rx, ry, rx+TILE-1, ry+TILE-1], fill=col)
            if explored and visible and cell == 3:
                draw.text((rx+TILE//2-3, ry+TILE//2-6), ">", fill=RGB["stairs"], font=font_big)
            if explored and visible and cell in (2,4):
                draw.text((rx+TILE//2-3, ry+TILE//2-6), "+", fill=RGB["door"], font=font_big)
            if explored and cell == 5:
                draw.rectangle([rx+1, ry+1, rx+TILE-2, ry+TILE-2], outline=RGB["key"])
                draw.text((rx+TILE//2-3, ry+TILE//2-6), "+", fill=RGB["key"], font=font_big)

    # traps triggered
    for t in game.traps:
        if (t["x"],t["y"]) in game.visible and t.get("triggered") and t["x"] < MAP_TILES_W and t["y"] < MAP_TILES_H:
            rx = ox + t["x"]*TILE; ry = oy + t["y"]*TILE
            draw.text((rx+TILE//2-3, ry+TILE//2-6), t["ch"], fill=RGB["trap"], font=font_big)

    # items (remembered dimly when explored but not visible)
    item_colmap = {"!":RGB["potion"],"*":RGB["food"],"/":RGB["weapon"],"[":RGB["armor"],"$":RGB["gold"],"?":RGB["scroll"],"=":RGB["ring"],"w":RGB["wand"],"k":RGB["key"]}
    for it in game.items:
        if it["x"] >= MAP_TILES_W or it["y"] >= MAP_TILES_H:
            continue
        key = (it["x"], it["y"])
        if key in game.visible:
            dim = False
        elif key in game.explored:
            dim = True
        else:
            continue
        cx = ox + it["x"]*TILE + TILE//2
        cy = oy + it["y"]*TILE + TILE//2
        draw_item_glyph(draw, cx, cy, it["ch"], item_colmap.get(it["ch"], (255,255,255)),
                        u=TILE/16.0, dim=dim)

    # mimics
    for e in game.entities:
        if e["hp"]<=0 or not e.get("disguise"): continue
        if (e["x"],e["y"]) in game.visible and e["x"] < MAP_TILES_W and e["y"] < MAP_TILES_H:
            colmap = {"!":RGB["potion"],"*":RGB["food"],"/":RGB["weapon"],"[":RGB["armor"],"$":RGB["gold"],"?":RGB["scroll"],"=":RGB["ring"]}
            mcx = ox + int(round(e["rx"]*TILE)) + TILE//2
            mcy = oy + int(round(e["ry"]*TILE)) + TILE//2
            draw_item_glyph(draw, mcx, mcy, e["disguise"], colmap.get(e["disguise"], (255,255,255)), u=TILE/16.0)

    # enemies
    enemy_color = {"g":RGB["goblin"],"o":RGB["orc"],"T":RGB["troll"],"D":RGB["dragon"],"s":RGB["skeleton"],
                   "b":RGB["bat"],"W":RGB["wraith"],"a":RGB["archer"],"n":RGB["necromancer"],"m":RGB["mimic"],
                   "r":RGB["rat"],"V":RGB["vampire"],"G":RGB["golem"],
                   "B":RGB["bossB"],"Z":RGB["bossZ"],"L":RGB["bossL"]}
    for e in game.entities:
        if e["hp"]<=0 or e.get("disguise"): continue
        if (e["x"],e["y"]) in game.visible and e["x"] < MAP_TILES_W and e["y"] < MAP_TILES_H:
            rx = ox + int(round(e["rx"]*TILE))
            ry = oy + int(round(e["ry"]*TILE))
            c = enemy_color.get(e["ch"], (239,68,68))
            cx = rx + TILE//2; cy = ry + TILE//2
            ch = e["ch"]
            if e.get("boss"):
                draw.rectangle([rx, ry, rx+TILE-1, ry+TILE-1], fill=c, outline=RGB["key"], width=2)
                draw.polygon([(cx-4, ry-5), (cx-4, ry+1), (cx, ry-2), (cx+4, ry+1), (cx+4, ry-5)], fill=RGB["key"])
            elif ch in ("g","r"):
                draw.ellipse([rx+3, ry+3, rx+TILE-4, ry+TILE-4], fill=c)
            elif ch in ("o","V"):
                draw.ellipse([rx+2, ry+2, rx+TILE-3, ry+TILE-3], fill=c)
                draw.ellipse([rx+6, ry+6, rx+TILE-7, ry+TILE-7], fill=(0,0,0))
            elif ch in ("T","G","D","m"):
                draw.rectangle([rx+2, ry+2, rx+TILE-3, ry+TILE-3], fill=c, outline=(0,0,0))
            elif ch in ("s",):
                pts = [(cx, ry+2), (rx+TILE-3, cy), (cx, ry+TILE-3), (rx+2, cy)]
                draw.polygon(pts, fill=c)
            elif ch in ("b",):
                pts = [(cx, ry+4), (rx+TILE-5, cy), (cx, ry+TILE-5), (rx+4, cy)]
                draw.polygon(pts, fill=c)
            elif ch in ("W",):
                draw.ellipse([rx+3, ry+2, rx+TILE-4, ry+TILE-5], fill=c)
                draw.polygon([(rx+3, ry+TILE-5), (cx, ry+TILE-2), (rx+TILE-4, ry+TILE-5)], fill=c)
            elif ch in ("a",):
                pts = [(rx+3, ry+3), (rx+TILE-3, cy), (rx+3, ry+TILE-3)]
                draw.polygon(pts, fill=c)
            elif ch in ("n",):
                draw.ellipse([rx+3, ry+3, rx+TILE-4, ry+TILE-4], fill=c)
            else:
                draw.rectangle([rx+3, ry+3, rx+TILE-4, ry+TILE-4], fill=c)
            # hp bar
            pct = e["hp"]/e["maxhp"]
            if e.get("boss"):
                draw.rectangle([rx, ry+TILE-3, rx+TILE-1, ry+TILE-1], fill=(0,0,0))
                draw.rectangle([rx, ry+TILE-3, rx+int(TILE*pct), ry+TILE-1], fill=RGB["hp"])
            else:
                draw.rectangle([rx+3, ry+1, rx+TILE-4, ry+3], fill=(0,0,0))
                draw.rectangle([rx+3, ry+1, rx+3+int((TILE-7)*pct), ry+3], fill=RGB["hp"])
            draw.text((rx+TILE//2-4, ry+TILE//2-7), e["ch"], fill=(255,255,255), font=font_big)

    # merchant
    m = game.merchant
    if m and (m["x"], m["y"]) in game.visible and m["x"] < MAP_TILES_W and m["y"] < MAP_TILES_H:
        mrx = ox + m["x"]*TILE
        mry = oy + m["y"]*TILE
        mcx = mrx + TILE//2
        draw.polygon([(mrx+2, mry+TILE-1), (mcx, mry+4), (mrx+TILE-2, mry+TILE-1)],
                     fill=(196,148,58), outline=(0,0,0))
        draw.ellipse([mcx-3, mry+1, mcx+3, mry+8], fill=(253,224,71), outline=(0,0,0))
        draw.text((mrx+2, mry+TILE-9), "v", fill=(255,255,255), font=font_small)

    # player
    px = ox + int(round(game.player["rx"]*TILE))
    py = oy + int(round(game.player["ry"]*TILE))
    draw.ellipse([px+2, py+2, px+TILE-3, py+TILE-3], fill=RGB["player"])
    draw.ellipse([px+7, py+7, px+10, py+10], fill=RGB["playerEye"])
    draw.ellipse([px+13, py+7, px+16, py+10], fill=RGB["playerEye"])
    ppct = game.player["hp"]/game.player["maxhp"]
    draw.rectangle([px+2, py+1, px+TILE-3, py+3], fill=(0,0,0))
    draw.rectangle([px+2, py+1, px+2+int((TILE-5)*ppct), py+3], fill=RGB["hp"])

    # transient effects: damage numbers, projectiles, beams, explosions, poofs
    game.effects = [fx for fx in game.effects if now - fx["t"] < fx.get("life", 0.7)]
    for fx in game.effects:
        age = now - fx["t"]
        prog = min(1.0, age / fx.get("life", 0.7))
        def fade(c, p=prog):
            return tuple(int(v * (1 - p)) for v in c)
        if fx["kind"] == "dmg":
            cx = ox + fx["x"]*TILE + TILE//2
            cy = oy + fx["y"]*TILE + TILE//2 - int(age*18)
            tw = draw.textlength(fx["txt"], font=font_big)
            draw.text((cx - tw/2, cy), fx["txt"], fill=fade(fx["color"]), font=font_big)
        elif fx["kind"] == "proj":
            t0 = prog
            cx = ox + int((fx["x0"] + (fx["x1"]-fx["x0"])*t0) * TILE) + TILE//2
            cy = oy + int((fx["y0"] + (fx["y1"]-fx["y0"])*t0) * TILE) + TILE//2
            draw.line([(cx-4, cy-4), (cx+4, cy+4)], fill=fx["color"], width=3)
        elif fx["kind"] == "beam":
            draw.line([(ox + fx["x0"]*TILE + TILE//2, oy + fx["y0"]*TILE + TILE//2),
                       (ox + fx["x1"]*TILE + TILE//2, oy + fx["y1"]*TILE + TILE//2)],
                      fill=fade(RGB["wand"]), width=2)
        elif fx["kind"] == "boom":
            r = int(TILE * (0.6 + prog*1.6))
            cx = ox + fx["x"]*TILE + TILE//2
            cy = oy + fx["y"]*TILE + TILE//2
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=fade((255,140,0)), width=3)
        elif fx["kind"] == "poof":
            r = int(TILE * (0.3 + prog*0.8))
            cx = ox + fx["x"]*TILE + TILE//2
            cy = oy + fx["y"]*TILE + TILE//2
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fade((120,120,120)))

    # fog overlay for non-visible explored
    for y in range(MAP_TILES_H):
        for x in range(MAP_TILES_W):
            if (x,y) in game.explored and (x,y) not in game.visible:
                rx = ox + x*TILE; ry = oy + y*TILE
                draw.rectangle([rx, ry, rx+TILE-1, ry+TILE-1], fill=(0,0,0,0) )  # already dim

    # side panel
    sx = ox + MAP_TILES_W*TILE + PAD
    sy = oy
    draw.rectangle([sx-PAD//2, oy-PAD//2, img_w-PAD//2, img_h-PAD//2], fill=RGB["panel"])
    # title
    draw.text((sx, sy), "DEPTH S", fill=RGB["title"], font=font_big)
    sy += 20
    p = game.player
    lines = [
        f"Floor {game.floor}/15  {biome(game.floor)}",
        f"HP {p['hp']}/{p['maxhp']}",
        f"ATK {game.total_atk()}  DEF {game.total_def()}",
        f"Level {p['level']}  XP {p['xp']}/{p['level']*12}",
        f"Gold {p['gold']}  Food {p['food']}",
        f"Hunger {p['hunger']}",
        f"Potions {p['potions']}  Scrolls {p['scrolls']}",
        f"Keys {p['keys']}",
    ]
    near = [e for e in game.entities
            if e["hp"] > 0 and not e.get("disguise") and (e["x"], e["y"]) in game.visible]
    if near:
        near.sort(key=lambda e: abs(e["x"]-p["x"]) + abs(e["y"]-p["y"]))
        e0 = near[0]
        lines.append(f"Near: {cap(ename(e0))} {e0['hp']}/{e0['maxhp']}")
    else:
        lines.append("No enemies in sight")
    boss = next((e for e in game.entities if e.get("boss") and e["hp"] > 0), None)
    if boss:
        lines.append(f"{cap(ename(boss))}")
        lines.append(f"  {boss['hp']}/{boss['maxhp']} HP")
    if game.merchant and game.merchant_adjacent():
        lines.append("v: trade with merchant")
    for l in lines:
        col = RGB["text"]
        if l.startswith("Near:"):
            col = RGB["trap"]
        elif l == "No enemies in sight":
            col = (110, 116, 124)
        draw.text((sx, sy), l, fill=col, font=font)
        sy += 20
    # compass to the stairs (the current goal)
    sp = game.stairs_pos()
    if sp and sp in game.explored:
        ddx, ddy = sp[0]-p["x"], sp[1]-p["y"]
        dist = abs(ddx) + abs(ddy)
        draw.text((sx, sy), f"Stairs: {dist} steps", fill=RGB["stairs"], font=font)
        ang = math.atan2(ddy, ddx)
        acx, acy = sx + 130, sy + 7
        tip = (acx + 8*math.cos(ang), acy + 8*math.sin(ang))
        bax, bay = acx - 5*math.cos(ang), acy - 5*math.sin(ang)
        nx_, ny_ = -math.sin(ang), math.cos(ang)
        draw.polygon([tip, (bax+5*nx_, bay+5*ny_), (bax-5*nx_, bay-5*ny_)], fill=RGB["stairs"])
    else:
        draw.text((sx, sy), "Stairs: explore to find", fill=(139,148,158), font=font)
    sy += 20
    sy += 6
    draw.text((sx, sy), "Log", fill=RGB["title"], font=font)
    sy += 16
    log_col = {"info": RGB["text"], "danger": RGB["trap"], "loot": RGB["gold"],
               "sys": RGB["title"], "hint": RGB["player"]}
    for m in game.messages[-10:]:
        draw.text((sx, sy), m["t"][:34], fill=log_col.get(m["k"], RGB["text"]), font=font_small)
        sy += 16
    sy += 6
    draw.text((sx, sy), "Inventory (I)", fill=RGB["title"], font=font)
    sy += 16
    if game.inventory_open:
        for i, it in enumerate(game.player["inventory"][:12]):
            mark = ">" if i == game.inv_cursor else " "
            d = game.item_delta(it)
            if i == game.inv_cursor:
                col = RGB["title"]
            elif d is not None and d > 0:
                col = RGB["player"]
            elif d is not None and d < 0:
                col = RGB["trap"]
            else:
                col = RGB["text"]
            extra = f" ({d:+d})" if d is not None and d != 0 else ""
            draw.text((sx, sy), f"{mark} {it['name'][:26]}{extra}", fill=col, font=font_small)
            sy += 13
        if not game.player["inventory"]:
            draw.text((sx, sy), "(empty)", fill=(139,148,158), font=font_small)
            sy += 13
        draw.text((sx, sy+4), "Enter equip  d drop  i close", fill=(139,148,158), font=font_small)
    else:
        draw.text((sx, sy), "Press I to open", fill=(139,148,158), font=font_small)
    sy += 24
    draw.text((sx, sy), "Arrows move  > descend", fill=(139,148,158), font=font_small)
    sy += 12
    draw.text((sx, sy), "p potion  f eat  r scroll", fill=(139,148,158), font=font_small)
    sy += 12
    draw.text((sx, sy), "x search  c stats  S save", fill=(139,148,158), font=font_small)
    sy += 14
    draw.text((sx, sy), "! potion  $ gold  * food", fill=(139,148,158), font=font_small)
    sy += 12
    draw.text((sx, sy), "[ armor   / weapon = ring", fill=(139,148,158), font=font_small)
    sy += 12
    draw.text((sx, sy), "? scroll  w wand  k key", fill=(139,148,158), font=font_small)

    # inventory overlay
    if game.inventory_open:
        bx = (img_w - 420)//2
        by = (img_h - 320)//2
        draw.rectangle([bx, by, bx+420, by+320], fill=RGB["panel"])
        draw.rectangle([bx, by, bx+420, by+2], fill=RGB["title"])
        draw.text((bx+12, by+8), "INVENTORY", fill=RGB["title"], font=font_big)
        inv = game.player["inventory"]
        y = by + 36
        for l in [f"Weapon: {game.player['weapon']['type'] if game.player['weapon'] else 'none'}",
                  f"Armor:  {game.player['armor']['type'] if game.player['armor'] else 'none'}",
                  f"Ring:   {game.player['ring']['type'] if game.player['ring'] else 'none'}",
                  "", "Items:"]:
            draw.text((bx+12, y), l, fill=RGB["text"], font=font)
            y += 16
        for i, it in enumerate(inv[:14]):
            mark = ">" if i == game.inv_cursor else " "
            col = RGB["title"] if i == game.inv_cursor else RGB["text"]
            draw.text((bx+12, y), f"{mark} {it['name'][:34]}", fill=col, font=font_small)
            y += 14
        if not inv:
            draw.text((bx+12, y), "(empty)", fill=(139,148,158), font=font_small)
            y += 14
        draw.text((bx+12, by+300), "Enter=equip/use  d=drop  i/q=close", fill=(139,148,158), font=font_small)

    # damage flash (screen edge)
    if time.time() < game.flash_until:
        draw.rectangle([0, 0, img_w-1, 5], fill=RGB["trap"])
        draw.rectangle([0, img_h-6, img_w-1, img_h-1], fill=RGB["trap"])
        draw.rectangle([0, 0, 5, img_h-1], fill=RGB["trap"])
        draw.rectangle([img_w-6, 0, img_w-1, img_h-1], fill=RGB["trap"])

    # event banner over the map
    if game.banner and time.time() < game.banner[1]:
        text = game.banner[0]
        tw = draw.textlength(text, font=font_big)
        bx = ox + (MAP_TILES_W*TILE - tw)/2
        by = oy + MAP_TILES_H*TILE//2 - 20
        draw.rectangle([bx-10, by-6, bx+tw+10, by+22], fill=(0,0,0))
        draw.rectangle([bx-10, by-6, bx+tw+10, by-4], fill=RGB["title"])
        draw.rectangle([bx-10, by+20, bx+tw+10, by+22], fill=RGB["title"])
        draw.text((bx, by), text, fill=RGB["title"], font=font_big)

    # shop overlay
    if game.shop_open:
        bx = (img_w - 420)//2
        by = (img_h - 320)//2
        draw.rectangle([bx, by, bx+420, by+320], fill=RGB["panel"])
        draw.rectangle([bx, by, bx+420, by+2], fill=RGB["gold"])
        draw.text((bx+12, by+8), "MERCHANT", fill=RGB["gold"], font=font_big)
        draw.text((bx+290, by+12), f"Gold: {game.player['gold']}", fill=RGB["gold"], font=font)
        y = by + 42
        for i, g in enumerate(SHOP_GOODS):
            price = game.shop_price(g)
            mark = ">" if i == game.shop_cursor else " "
            afford = game.player["gold"] >= price
            col = RGB["title"] if i == game.shop_cursor else (RGB["text"] if afford else (110,116,124))
            draw.text((bx+12, y), f"{mark} {g['name'][:24]:<24} {price}g", fill=col, font=font)
            y += 24
        draw.text((bx+12, by+300), "Enter=buy   v/Esc=close", fill=(139,148,158), font=font_small)

    # help overlay
    if game.help_open:
        bx = (img_w - 480)//2
        by = (img_h - 300)//2
        draw.rectangle([bx, by, bx+480, by+300], fill=RGB["panel"])
        draw.rectangle([bx, by, bx+480, by+2], fill=RGB["title"])
        draw.text((bx+12, by+8), "HELP", fill=RGB["title"], font=font_big)
        hl = [
            ("GOAL: descend 15 floors.", RGB["stairs"]),
            ("Slay the boss guarding the stairs on boss floors.", RGB["stairs"]),
            ("Locked doors need keys. Mimics look like items.", RGB["text"]),
            ("Follow the compass to the stairs.", RGB["text"]),
            ("", None),
            ("Move: arrows / WASD / hjkl, diagonals yubn", RGB["text"]),
            ("p potion   f eat   r scroll   i inventory", RGB["text"]),
            ("v trade    x search  > descend   c stats", RGB["text"]),
            ("S save     L load   A auto-pilot   ? help   q quit", RGB["text"]),
            ("", None),
            ("Press any key to close.", (139,148,158)),
        ]
        y = by + 40
        for l, c in hl:
            if c is not None:
                draw.text((bx+12, y), l, fill=c, font=font)
            y += 21

    # game over overlay
    if game.game_over:
        draw.rectangle([0, 0, img_w, img_h], fill=(0,0,0))
        title = "VICTORY!" if game.victory else "GAME OVER"
        col = RGB["hp"] if game.victory else RGB["trap"]
        draw.text((img_w//2-60, img_h//2-20), title, fill=col, font=font_big)
        if not game.victory and game.killer:
            kt = f"Slain by {game.killer}"
            draw.text((img_w//2 - draw.textlength(kt, font=font)/2, img_h//2-2), kt,
                      fill=(200,120,120), font=font)
        draw.text((img_w//2-120, img_h//2+10), f"Floor {game.floor}  Level {game.player['level']}  Gold {game.player['gold']}", fill=RGB["text"], font=font)
        draw.text((img_w//2-100, img_h//2+34), "Auto-restarts in auto mode" if game.auto else "Press r to retry, q to quit", fill=(139,148,158), font=font_small)
        scores = getattr(game, "_scores", None) or load_scores()
        sy = img_h//2 + 70
        draw.text((img_w//2-60, sy), "BEST RUNS", fill=RGB["title"], font=font)
        sy += 22
        for s in scores[:5]:
            tag = "  WIN" if s.get("victory") else ""
            line = f"{s.get('date','')}  floor {s.get('floor',0)}  lvl {s.get('level',0)}  gold {s.get('gold',0)}{tag}"
            tw = draw.textlength(line, font=font_small)
            draw.text((img_w//2 - tw/2, sy), line, fill=RGB["text"], font=font_small)
            sy += 16

    return img

def image_to_sixel(img):
    from PIL import Image
    w, h = img.size
    qimg = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    palette = qimg.getpalette()
    out = []
    out.append("\x1bPq\"1;1;%d;%d" % (w, h))
    for band_y in range(0, h, 6):
        col_values = {}
        for x in range(w):
            for dy in range(6):
                yy = band_y + dy
                if yy >= h:
                    continue
                ci = qimg.getpixel((x, yy))
                if ci not in col_values:
                    col_values[ci] = [0]*w
                col_values[ci][x] |= (1 << dy)
        for ci, vals in col_values.items():
            if not any(vals):
                continue
            if palette is not None:
                r = palette[ci*3]; g = palette[ci*3+1]; b = palette[ci*3+2]
                out.append("#%d;2;%d;%d;%d" % (ci, r*100//255, g*100//255, b*100//255))
            out.append("#%d" % ci)
            line = ""
            i = 0
            n = len(vals)
            while i < n:
                j = i
                while j < n and vals[j] == vals[i]:
                    j += 1
                run = j - i
                ch = chr(63 + vals[i])
                if run > 3:
                    line += "!%d%s" % (run, ch)
                else:
                    line += ch * run
                i = j
            out.append(line)
            out.append("$")
        out.append("-")
    out.append("\x1b\\" )
    return "".join(out)

def send_sixel(img):
    data = image_to_sixel(img)
    sys.stdout.write("\x1b[?25l")
    sys.stdout.write("\x1b[?7l")   # disable auto-wrap to avoid scroll
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.write(data)
    sys.stdout.write("\x1b[?7h")   # re-enable
    sys.stdout.flush()

def render_kitty(game):
    try:
        from PIL import Image
    except Exception:
        return
    img = _draw_frame(game)
    # send via kitty
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    data = base64.b64encode(buf.getvalue()).decode('ascii')
    import shutil
    ts = shutil.get_terminal_size((80, 24))
    sys.stdout.write("\x1b[?25l")
    sys.stdout.write("\x1b_Ga=d,d=A\x1b\\")
    sys.stdout.write("\x1b[2J\x1b[H")
    hdr = "\x1b_Ga=T,f=100,C=1,c=%d,r=%d" % (ts.columns, ts.lines)
    chunk_size = 4096
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    if not chunks:
        sys.stdout.flush(); return
    if len(chunks) == 1:
        sys.stdout.write("%s;%s\x1b\\" % (hdr, chunks[0]))
    else:
        sys.stdout.write("%s,m=1;%s\x1b\\" % (hdr, chunks[0]))
        for ch in chunks[1:-1]:
            sys.stdout.write("\x1b_Gm=1;%s\x1b\\" % ch)
        sys.stdout.write("\x1b_Gm=0;%s\x1b\\" % chunks[-1])
    # keep the cursor parked at home: an image filling the whole grid would
    # otherwise push the cursor past the last row and scroll the screen
    sys.stdout.write("\x1b[H")
    sys.stdout.flush()

def render_sixel(game):
    try:
        from PIL import Image
    except Exception:
        return
    img = _draw_frame(game)
    send_sixel(img)

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

# ---------- Input helpers for kitty mode ----------
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

if __name__ == "__main__":
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
