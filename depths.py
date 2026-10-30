#!/usr/bin/env python3
"""depths — a terminal roguelike. Procedural dungeons, permadeath, no deps but curses."""
import curses, random, os, json

SAVE = os.path.expanduser("~/.depths_save.json")
HIGH = os.path.expanduser("~/.depths_high.json")

ITEM_CHARS = {"!": "potion", "/": "weapon", "[": "armor", "$": "gold", "?": "scroll",
              "*": "food", "=": "ring", "(": "wand", "k": "key", "^": "trap"}
ENEMY_CHARS = {"g": "goblin", "o": "orc", "T": "troll", "D": "dragon", "s": "skeleton",
               "b": "bat", "W": "wraith", "a": "archer", "n": "necromancer", "m": "mimic",
               "r": "rat", "V": "vampire", "G": "golem"}
PLAYER = "@"

COLORS = {
    "wall": 8, "floor": 240, "door": 94, "stairs": 220, "secret": 94, "player": 46,
    "goblin": 34, "orc": 28, "troll": 22, "dragon": 196, "skeleton": 250,
    "bat": 95, "wraith": 141, "archer": 130, "necromancer": 99, "mimic": 214,
    "rat": 101, "vampire": 125, "golem": 242, "potion": 201, "weapon": 208,
    "armor": 33, "gold": 220, "scroll": 213, "food": 112, "ring": 219,
    "wand": 177, "key": 220, "trap": 196, "text": 255, "hp": 196, "xp": 45,
    "dim": 238, "msg": 226, "title": 51, "inv": 51, "equip": 39,
}

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    BG_FLOOR = 236
    BG_WALL = 234
    tile_colors = {"wall","floor","door","stairs","secret","player","goblin","orc","troll","dragon",
        "skeleton","bat","wraith","archer","necromancer","mimic","rat","vampire","golem",
        "potion","weapon","armor","gold","scroll","food","ring","wand","key","trap","dim"}
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

ENEMY_STATS = {
    "g": (6, 2, 3), "o": (12, 4, 6), "T": (25, 7, 12), "D": (60, 15, 40),
    "s": (8, 3, 4), "b": (4, 1, 2), "W": (18, 6, 10), "a": (10, 3, 5),
    "n": (14, 2, 8), "m": (15, 4, 6), "r": (3, 1, 1), "V": (22, 5, 12),
    "G": (40, 6, 15),
}

def make_dungeon(floor, width, height):
    grid = [["#" for _ in range(width)] for _ in range(height)]
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
                    grid[yy][xx] = "."
    for i in range(1, len(rooms)):
        x1, y1, w1, h1 = rooms[i-1]
        x2, y2, w2, h2 = rooms[i]
        cx1, cy1 = x1 + w1//2, y1 + h1//2
        cx2, cy2 = x2 + w2//2, y2 + h2//2
        if random.random() < 0.5:
            for xx in range(min(cx1, cx2), max(cx1, cx2)+1):
                if grid[cy1][xx] == "#": grid[cy1][xx] = "."
            for yy in range(min(cy1, cy2), max(cy1, cy2)+1):
                if grid[yy][cx2] == "#": grid[yy][cx2] = "."
        else:
            for yy in range(min(cy1, cy2), max(cy1, cy2)+1):
                if grid[yy][cx1] == "#": grid[yy][cx1] = "."
            for xx in range(min(cx1, cx2), max(cx1, cx2)+1):
                if grid[cy2][xx] == "#": grid[cy2][xx] = "."
    # secret doors: mark some walls adjacent to corridors as 'S' (hidden)
    for y in range(1, height-1):
        for x in range(1, width-1):
            if grid[y][x] == "#":
                # adjacent to floor on both sides horizontally or vertically
                if (grid[y-1][x] == "." and grid[y+1][x] == ".") or (grid[y][x-1] == "." and grid[y][x+1] == "."):
                    if random.random() < 0.04:
                        grid[y][x] = "S"  # secret door (hidden wall)
    return grid, rooms

def place_entities(grid, width, height, floor, player_pos):
    entities = []
    items = []
    traps = []
    n_enemies = 4 + floor*2 + random.randint(0, 3)
    candidates = []
    for y in range(1, height-1):
        for x in range(1, width-1):
            if grid[y][x] == ".":
                if abs(x-player_pos[0]) + abs(y-player_pos[1]) > 6:
                    candidates.append((x, y))
    random.shuffle(candidates)
    pool = ["g","g","g","r","r","o","s","b"]
    if floor >= 2: pool += ["o","o","a","s","W"]
    if floor >= 3: pool += ["T","n","V"]
    if floor >= 4: pool += ["T","m","G"]
    if floor >= 5: pool += ["D","n","m"]
    if floor % 5 == 0:
        pool = ["D","T","T","W","W","n","m"]
    idx = 0
    for _ in range(n_enemies):
        if idx >= len(candidates): break
        x, y = candidates[idx]; idx += 1
        ch = random.choice(pool)
        hp, atk, xp = ENEMY_STATS[ch]
        # scale with floor
        hp = int(hp * (1 + 0.12*(floor-1)))
        atk = int(atk * (1 + 0.08*(floor-1)))
        entities.append({"ch": ch, "x": x, "y": y, "hp": hp, "maxhp": hp,
                        "atk": atk, "name": ENEMY_CHARS[ch], "xp": xp})
    # mimics disguised as items: replace some item slots
    n_items = random.randint(3, 5) + floor//2
    for _ in range(n_items):
        if idx >= len(candidates): break
        x, y = candidates[idx]; idx += 1
        if random.random() < 0.15 and floor >= 2:
            # mimic
            entities.append({"ch": "m", "x": x, "y": y, "hp": ENEMY_STATS["m"][0],
                            "maxhp": ENEMY_STATS["m"][0], "atk": ENEMY_STATS["m"][1],
                            "name": "mimic", "xp": ENEMY_STATS["m"][2], "disguise": random.choice(["!","/","[","$","?","*"])})
            continue
        ch = random.choice(["!","!","*","*","/","[","$","?","?","=","("])
        items.append({"ch": ch, "x": x, "y": y, "name": ITEM_CHARS[ch]})
    # traps
    n_traps = random.randint(1, 3) + floor//3
    for _ in range(n_traps):
        if idx >= len(candidates): break
        x, y = candidates[idx]; idx += 1
        t = random.choice(["^","^","~","@","!"])
        traps.append({"ch": t, "x": x, "y": y, "revealed": False})
    # stairs
    occupied = {(e["x"],e["y"]) for e in entities} | {(it["x"],it["y"]) for it in items}
    far = [c for c in candidates if abs(c[0]-player_pos[0])+abs(c[1]-player_pos[1])>15 and c not in occupied]
    if far:
        sx, sy = random.choice(far)
        grid[sy][sx] = ">"
    # keys occasionally
    if random.random() < 0.35:
        if idx < len(candidates):
            x, y = candidates[idx]; idx += 1
            items.append({"ch": "k", "x": x, "y": y, "name": "key"})
    return entities, items, traps

class Game:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.h, self.w = stdscr.getmaxyx()
        self.mw = self.w
        self.mh = self.h - 4
        self.reset()

    def reset(self):
        self.floor = 1
        self.player = {"x":0,"y":0,"hp":24,"maxhp":24,"atk":4,"def":1,"xp":0,"level":1,
                       "gold":0,"potions":1,"scrolls":0,"food":3,"hunger":0,
                       "weapon":None,"armor":None,"ring":None,"amulet":None,
                       "inventory":[],"keys":0}
        self.messages = []
        self.explored = set()
        self.visible = set()
        self.victory = False
        self.game_over = False
        self.inventory_open = False
        self.inv_cursor = 0
        self.inv_mode = "main"  # main/use/equip
        self.new_floor()

    def new_floor(self):
        self.grid, rooms = make_dungeon(self.floor, self.mw, self.mh)
        rx, ry, rw, rh = rooms[0]
        self.player["x"] = rx + rw//2
        self.player["y"] = ry + rh//2
        self.entities, self.items, self.traps = place_entities(
            self.grid, self.mw, self.mh, self.floor, (self.player["x"], self.player["y"]))
        self.messages.append(f"--- Floor {self.floor}: {biome(self.floor)} ---")
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
            if (x,y) != (x0,y0) and self.grid[y][x] == "#":
                return False
            # secret doors block sight too
            if (x,y) != (x0,y0) and self.grid[y][x] == "S":
                return False
            e2 = 2*err
            if e2 > -dy:
                err -= dy; x += sx
            if e2 < dx:
                err += dx; y += sy

    def msg(self, text):
        self.messages.append(text)
        if len(self.messages) > 6:
            self.messages = self.messages[-6:]

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
        if cell == "#":
            self.msg("A wall blocks your path.")
            return
        if cell == "S":
            # secret door: reveal and open
            self.grid[ny][nx] = "+"
            self.msg("You found a secret door!")
            # don't move this turn? move through
        # enemy?
        for e in self.entities:
            if e["hp"]>0 and e["x"]==nx and e["y"]==ny:
                self.attack(e)
                self.end_turn()
                return
        # mimic disguised as item? handled in items below (mimics are entities)
        # item?
        for it in self.items:
            if it["x"]==nx and it["y"]==ny:
                self.pickup(it)
                self.items.remove(it)
        # trap?
        for t in self.traps:
            if t["x"]==nx and t["y"]==ny and not t.get("triggered"):
                self.trigger_trap(t)
        # stairs?
        if self.grid[ny][nx] == ">":
            if self.floor >= 15:
                self.victory = True
                self.game_over = True
                self.msg("You escaped the depths!")
                return
            self.floor += 1
            self.msg(f"You descend to floor {self.floor}.")
            self.new_floor()
            self.end_turn()
            return
        self.player["x"], self.player["y"] = nx, ny
        self.end_turn()

    def end_turn(self):
        # hunger
        self.player["hunger"] += 1
        if self.player["hunger"] >= 40 and self.player["hunger"] % 10 == 0:
            self.player["hp"] = max(1, self.player["hp"]-1)
            self.msg("You are starving.")
        # regen? no
        self.enemy_turn()
        # reveal secret doors adjacent
        self.reveal_secrets()
        self.compute_fov()

    def reveal_secrets(self):
        px, py = self.player["x"], self.player["y"]
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                x, y = px+dx, py+dy
                if 0 <= x < self.mw and 0 <= y < self.mh and self.grid[y][x] == "S":
                    if random.random() < 0.25:
                        self.grid[y][x] = "+"
                        self.msg("You notice a secret door.")

    def attack(self, e):
        patk = self.total_atk()
        dmg = max(1, patk - 1 + random.randint(-1, 2))
        # crit
        if random.random() < 0.1:
            dmg = int(dmg * 1.8)
            self.msg("Critical hit!")
        e["hp"] -= dmg
        self.msg(f"You hit {e['name']} for {dmg}.")
        if e["hp"] <= 0:
            e["hp"] = 0
            self.msg(f"{e['name']} dies.")
            self.player["xp"] += e.get("xp", 3)
            # gold drop
            if random.random() < 0.4:
                amt = random.randint(1, 6) + self.floor
                self.player["gold"] += amt
                self.msg(f"It drops {amt} gold.")
            self.check_level()
            # vampire? no
        else:
            # thorns? no
            pass

    def enemy_turn(self):
        for e in self.entities:
            if e["hp"] <= 0: continue
            # mimic reveal if adjacent? mimics act like items until player adjacent; here they're entities already
            # adjacent attack
            if abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"]) == 1:
                dmg = max(1, e["atk"] - self.total_def() + random.randint(-1, 1))
                # vampire life steal
                if e["ch"] == "V":
                    e["hp"] = min(e["maxhp"], e["hp"] + dmg//2)
                self.player["hp"] -= dmg
                self.msg(f"{e['name']} hits you for {dmg}.")
                if self.player["hp"] <= 0:
                    self.player["hp"] = 0
                    self.game_over = True
                continue
            # ranged: archer/necromancer
            if e["ch"] in ("a",) and (e["x"],e["y"]) in self.visible:
                dist = abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"])
                if 2 <= dist <= 6 and self.line_of_sight(e["x"],e["y"],self.player["x"],self.player["y"]):
                    if random.random() < 0.6:
                        dmg = max(1, e["atk"] - self.total_def() + random.randint(0,1))
                        self.player["hp"] -= dmg
                        self.msg(f"{e['name']} shoots you for {dmg}.")
                        if self.player["hp"] <= 0:
                            self.player["hp"]=0; self.game_over=True
                        continue
            if e["ch"] == "n" and (e["x"],e["y"]) in self.visible:
                # summon skeleton
                if random.random() < 0.25:
                    # find empty adjacent
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=e["x"]+dx,e["y"]+dy
                        if 0<=nx<self.mw and 0<=ny<self.mh and self.grid[ny][nx]=="." and not any(o["x"]==nx and o["y"]==ny and o["hp"]>0 for o in self.entities):
                            self.entities.append({"ch":"s","x":nx,"y":ny,"hp":8,"maxhp":8,"atk":3,"name":"skeleton","xp":4})
                            self.msg("Necromancer summons a skeleton.")
                            break
            # movement toward player
            if (e["x"],e["y"]) in self.visible or abs(e["x"]-self.player["x"])+abs(e["y"]-self.player["y"]) <= 7:
                dx = 0
                if e["x"] < self.player["x"]: dx = 1
                elif e["x"] > self.player["x"]: dx = -1
                dy = 0
                if e["y"] < self.player["y"]: dy = 1
                elif e["y"] > self.player["y"]: dy = -1
                # bats move randomly sometimes
                if e["ch"] == "b" and random.random() < 0.4:
                    dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1),(0,0)])
                nx, ny = e["x"]+dx, e["y"]+dy
                if 0<=nx<self.mw and 0<=ny<self.mh and self.grid[ny][nx] in (".","+","S") and not any(o["x"]==nx and o["y"]==ny and o["hp"]>0 for o in self.entities if o is not e) and not (nx==self.player["x"] and ny==self.player["y"]):
                    e["x"], e["y"] = nx, ny

    def trigger_trap(self, t):
        t["triggered"] = True
        ch = t["ch"]
        if ch == "^":
            dmg = random.randint(3, 8) + self.floor//2
            self.player["hp"] -= dmg
            self.msg(f"A spike trap hits you for {dmg}!")
        elif ch == "~":
            self.player["hp"] = max(1, self.player["hp"]-4)
            self.player["hunger"] += 20
            self.msg("Poison! HP -4, hunger +20.")
        elif ch == "@":
            tiles = [(x,y) for y in range(self.mh) for x in range(self.mw) if self.grid[y][x]=="." and (x,y)!=(self.player["x"],self.player["y"])]
            if tiles:
                self.player["x"],self.player["y"] = random.choice(tiles)
                self.msg("Teleport trap!")
        elif ch == "!":
            # summon enemies
            for _ in range(random.randint(1,3)):
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx,ny=self.player["x"]+dx,self.player["y"]+dy
                    if 0<=nx<self.mw and 0<=ny<self.mh and self.grid[ny][nx]=="." and not any(o["x"]==nx and o["y"]==ny and o["hp"]>0 for o in self.entities):
                        self.entities.append({"ch":"g","x":nx,"y":ny,"hp":6,"maxhp":6,"atk":2,"name":"goblin","xp":3})
                        break
            self.msg("Alarm! Enemies appear.")
        if self.player["hp"] <= 0:
            self.player["hp"]=0; self.game_over=True

    def pickup(self, it):
        ch = it["ch"]
        if ch == "!":
            self.player["potions"] += 1
            self.msg("You pick up a health potion.")
        elif ch == "*":
            self.player["food"] += 1
            self.msg("You pick up food.")
        elif ch == "/":
            # weapon item: store in inventory as equipment
            w = {"name": "weapon", "atk": 2 + self.floor//3, "type": "weapon"}
            self.player["inventory"].append({"ch":"/","name":f"weapon (+{w['atk']} ATK)","item":w,"kind":"equip"})
            self.msg("You find a weapon. (i to equip)")
        elif ch == "[":
            a = {"name":"armor","def":1 + self.floor//4, "hp":2 + self.floor//2, "type":"armor"}
            self.player["inventory"].append({"ch":"[","name":f"armor (+{a['def']} DEF)","item":a,"kind":"equip"})
            self.msg("You find armor. (i to equip)")
        elif ch == "$":
            amt = random.randint(5, 20) + self.floor*2
            self.player["gold"] += amt
            self.msg(f"You find {amt} gold.")
        elif ch == "?":
            self.player["scrolls"] += 1
            self.msg("You find a scroll.")
        elif ch == "=":
            r = {"name":"ring","atk":1,"def":1,"type":"ring"}
            self.player["inventory"].append({"ch":"=","name":"ring (+1 ATK/DEF)","item":r,"kind":"equip"})
            self.msg("You find a ring.")
        elif ch == "(":
            self.player["inventory"].append({"ch":"(","name":"wand (fireball)","item":{"type":"wand"},"kind":"wand"})
            self.msg("You find a wand.")
        elif ch == "k":
            self.player["keys"] += 1
            self.msg("You pick up a key.")

    def use_potion(self):
        if self.player["potions"] <= 0:
            self.msg("No potions.")
            return
        self.player["potions"] -= 1
        heal = random.randint(10, 16) + self.player["level"]
        self.player["hp"] = min(self.player["maxhp"], self.player["hp"]+heal)
        self.msg(f"You drink a potion. +{heal} HP.")
        self.end_turn()

    def eat_food(self):
        if self.player["food"] <= 0:
            self.msg("No food.")
            return
        self.player["food"] -= 1
        self.player["hunger"] = max(0, self.player["hunger"]-30)
        heal = 4
        self.player["hp"] = min(self.player["maxhp"], self.player["hp"]+heal)
        self.msg(f"You eat. Hunger -30, +{heal} HP.")
        self.end_turn()

    def use_scroll(self):
        if self.player["scrolls"] <= 0:
            self.msg("No scrolls.")
            return
        self.player["scrolls"] -= 1
        effect = random.choice(["reveal","fireball","teleport","heal"])
        if effect == "reveal":
            for y in range(self.mh):
                for x in range(self.mw):
                    self.explored.add((x,y))
            self.msg("The scroll reveals the floor.")
        elif effect == "fireball":
            cnt = 0
            for e in self.entities:
                if e["hp"]>0 and (e["x"],e["y"]) in self.visible:
                    e["hp"] -= 12
                    cnt += 1
                    if e["hp"]<=0:
                        e["hp"]=0; self.msg(f"{e['name']} dies.")
                        self.player["xp"] += e.get("xp",3); self.check_level()
            self.msg(f"Fireball hits {cnt} enemies.")
        elif effect == "teleport":
            tiles = [(x,y) for y in range(self.mh) for x in range(self.mw) if self.grid[y][x] in (".","+") and (x,y) not in {(e["x"],e["y"]) for e in self.entities if e["hp"]>0}]
            if tiles:
                self.player["x"], self.player["y"] = random.choice(tiles)
                self.msg("You teleport.")
        else:
            self.player["hp"] = self.player["maxhp"]
            self.msg("Full heal.")
        self.end_turn()

    def use_wand(self, inv_item):
        # fireball cone
        cnt = 0
        for e in self.entities:
            if e["hp"]>0 and (e["x"],e["y"]) in self.visible:
                d = abs(e["x"]-self.player["x"])+abs(e["y"]-self.player["y"])
                if d <= 5 and self.line_of_sight(self.player["x"],self.player["y"],e["x"],e["y"]):
                    e["hp"] -= 15
                    cnt += 1
                    if e["hp"]<=0:
                        e["hp"]=0; self.msg(f"{e['name']} dies.")
                        self.player["xp"] += e.get("xp",3); self.check_level()
        self.msg(f"Wand hits {cnt} enemies.")
        # remove one wand charge: remove item
        self.player["inventory"].remove(inv_item)
        self.end_turn()

    def check_level(self):
        need = self.player["level"] * 12
        while self.player["xp"] >= need:
            self.player["xp"] -= need
            self.player["level"] += 1
            self.player["maxhp"] += 6
            self.player["hp"] = self.player["maxhp"]
            self.player["atk"] += 1
            self.player["def"] += 1
            self.msg(f"Level up! You are level {self.player['level']}.")
            need = self.player["level"] * 12

    def search(self):
        px, py = self.player["x"], self.player["y"]
        found = 0
        for dy in range(-2,3):
            for dx in range(-2,3):
                x,y = px+dx, py+dy
                if 0<=x<self.mw and 0<=y<self.mh and self.grid[y][x]=="S":
                    self.grid[y][x] = "+"
                    found += 1
        if found:
            self.msg(f"You find {found} secret door(s).")
        else:
            self.msg("Nothing found.")
        self.end_turn()

    def open_inventory(self):
        self.inventory_open = True
        self.inv_cursor = 0
        self.inv_mode = "main"

    def close_inventory(self):
        self.inventory_open = False

    def inventory_action(self, key):
        inv = self.player["inventory"]
        if key in (27, ord('i'), ord('q')):
            self.close_inventory(); return
        if key == curses.KEY_UP or key == ord('k'):
            self.inv_cursor = max(0, self.inv_cursor-1)
        elif key == curses.KEY_DOWN or key == ord('j'):
            self.inv_cursor = min(max(0,len(inv)-1), self.inv_cursor+1)
        elif key == ord('\n') or key == 10 or key == 13:
            if not inv: return
            it = inv[self.inv_cursor]
            kind = it.get("kind")
            if kind == "equip":
                # equip
                item = it["item"]
                slot = item["type"]
                if slot == "weapon":
                    if self.player["weapon"]: self.player["inventory"].append({"ch":"/","name":self.player["weapon"]["name"],"item":self.player["weapon"],"kind":"equip"})
                    self.player["weapon"] = item
                elif slot == "armor":
                    if self.player["armor"]: self.player["inventory"].append({"ch":"[","name":self.player["armor"]["name"],"item":self.player["armor"],"kind":"equip"})
                    self.player["armor"] = item
                elif slot == "ring":
                    if self.player["ring"]: self.player["inventory"].append({"ch":"=","name":self.player["ring"]["name"],"item":self.player["ring"],"kind":"equip"})
                    self.player["ring"] = item
                self.player["inventory"].remove(it)
                self.msg(f"Equipped {item['name']}.")
            elif kind == "wand":
                self.use_wand(it)
                self.close_inventory()
                return
            elif kind == "food":
                self.eat_food()
                self.player["inventory"].remove(it)
                self.close_inventory()
                return
        elif key == ord('d'):
            if inv and 0 <= self.inv_cursor < len(inv):
                it = inv.pop(self.inv_cursor)
                self.msg(f"Dropped {it['name']}.")
                if self.inv_cursor >= len(inv): self.inv_cursor = max(0, len(inv)-1)
        elif key == ord('u'):
            # use selected as consumable if potion? handle numbers
            pass

    def handle_input(self, key):
        if self.inventory_open:
            self.inventory_action(key)
            return
        if key in (ord('q'), 27):
            return "quit"
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
        elif key == ord('c'): self.msg(self.char_sheet())
        elif key == ord('x'): self.search()
        elif key == ord('>'):
            if self.grid[self.player["y"]][self.player["x"]] == ">":
                if self.floor >= 15:
                    self.victory = True; self.game_over = True
                    self.msg("You escaped the depths!")
                    return
                self.floor += 1; self.msg(f"Descend to floor {self.floor}."); self.new_floor()
        elif key == ord('S'):
            self.save_game()

    def char_sheet(self):
        p = self.player
        return (f"LVL {p['level']}  HP {p['hp']}/{p['maxhp']}  ATK {self.total_atk()}  DEF {self.total_def()}  "
                f"XP {p['xp']}/{p['level']*12}  Gold {p['gold']}  Food {p['food']}  Hunger {p['hunger']}  "
                f"Keys {p['keys']}")

    def save_game(self):
        try:
            data = {
                "floor": self.floor, "player": self.player,
                "explored": [list(t) for t in self.explored],
                "messages": self.messages[-5:],
            }
            json.dump(data, open(SAVE,"w"))
            self.msg("Game saved.")
        except Exception as e:
            self.msg(f"Save failed: {e}")

    def load_game(self):
        try:
            data = json.load(open(SAVE))
            self.floor = data["floor"]
            self.player = data["player"]
            self.explored = set(tuple(t) for t in data["explored"])
            self.messages = data.get("messages", [])
            # rebuild floor
            self.grid, rooms = make_dungeon(self.floor, self.mw, self.mh)
            # place player
            self.player["x"] = min(self.player["x"], self.mw-1)
            self.player["y"] = min(self.player["y"], self.mh-1)
            self.entities, self.items, self.traps = place_entities(self.grid, self.mw, self.mh, self.floor, (self.player["x"], self.player["y"]))
            self.compute_fov()
            self.msg("Game loaded.")
        except Exception as e:
            self.msg(f"Load failed: {e}")

    def draw(self):
        self.stdscr.erase()
        for y in range(self.mh):
            for x in range(self.mw):
                ch = self.grid[y][x]
                if (x,y) in self.visible:
                    if ch == "#":
                        self.stdscr.addstr(y, x, " ", cp("wall"))
                    elif ch == ".":
                        self.stdscr.addstr(y, x, " ", cp("floor"))
                    elif ch == ">":
                        self.stdscr.addstr(y, x, ">", cp("stairs"))
                    elif ch in ("+","S"):
                        self.stdscr.addstr(y, x, "+", cp("door"))
                elif (x,y) in self.explored:
                    if ch == "#":
                        self.stdscr.addstr(y, x, " ", cp("dim"))
                    elif ch == "S":
                        self.stdscr.addstr(y, x, " ", cp("dim"))
                    else:
                        self.stdscr.addstr(y, x, " ", cp("dim"))
        # traps (only revealed if visible and triggered or detected? show if visible)
        for t in self.traps:
            if (t["x"],t["y"]) in self.visible and (t.get("triggered") or t["ch"]=="^"):
                # reveal traps only after triggered; hidden otherwise
                if t.get("triggered"):
                    self.stdscr.addstr(t["y"], t["x"], t["ch"], cp("trap"))
        # items
        ITEM_GLYPH = {"!":"!","*":"%","/":")","[":"]","$":"$","?":"?","=":"=","(":"/","k":"k"}
        for it in self.items:
            if (it["x"],it["y"]) in self.visible:
                col = {"!":"potion","*":"food","/":"weapon","[":"armor","$":"gold","?":"scroll","=":"ring","(":"wand","k":"key"}[it["ch"]]
                self.stdscr.addstr(it["y"], it["x"], ITEM_GLYPH[it["ch"]], cp(col))
        # mimics disguised: show as item char
        for e in self.entities:
            if e["hp"]>0 and e.get("disguise") and (e["x"],e["y"]) in self.visible:
                ITEM_GLYPH = {"!":"!","*":"%","/":")","[":"]","$":"$","?":"?","=":"=","(":"/"}
                col = {"!":"potion","*":"food","/":"weapon","[":"armor","$":"gold","?":"scroll","=":"ring","(":"wand"}[e["disguise"]]
                self.stdscr.addstr(e["y"], e["x"], ITEM_GLYPH[e["disguise"]], cp(col))
        # enemies
        for e in self.entities:
            if e["hp"]>0 and not e.get("disguise") and (e["x"],e["y"]) in self.visible:
                self.stdscr.addstr(e["y"], e["x"], e["ch"], cp(e["name"]))
        # player
        self.stdscr.addstr(self.player["y"], self.player["x"], PLAYER, cp("player") | curses.A_BOLD)
        # status
        sy = self.mh
        p = self.player
        hp_bar = f"HP:{p['hp']}/{p['maxhp']}"
        status = (f" Fl{self.floor} {biome(self.floor)}  {hp_bar}  ATK {self.total_atk()}  DEF {self.total_def()}  "
                  f"LVL {p['level']}  XP {p['xp']}/{p['level']*12}  Gold {p['gold']}  Food {p['food']}  "
                  f"Hng {p['hunger']}  Pot {p['potions']}  Scr {p['scrolls']}  Keys {p['keys']} ")
        self.stdscr.addstr(sy, 0, ("-"*(self.w-1)), cp("dim"))
        self.stdscr.addstr(sy+1, 0, status[:self.w-1], cp("text"))
        for i, m in enumerate(self.messages[-2:]):
            self.stdscr.addstr(sy+2+i, 0, m[:self.w-1], cp("msg"))
        # inventory overlay
        if self.inventory_open:
            self.draw_inventory()
        self.stdscr.refresh()

    def draw_inventory(self):
        inv = self.player["inventory"]
        h, w = self.h, self.w
        box_w = min(60, w-4)
        box_h = min(20, h-4)
        sx = (w - box_w)//2
        sy = (h - box_h)//2
        for yy in range(sy, sy+box_h):
            self.stdscr.addstr(yy, sx, " "*box_w, cp("inv"))
        self.stdscr.addstr(sy, sx, "-"*box_w, cp("inv"))
        self.stdscr.addstr(sy, sx+2, " INVENTORY ", cp("inv") | curses.A_BOLD)
        # equipment
        eq = self.player
        lines = [
            f"Weapon: {eq['weapon']['name'] if eq['weapon'] else 'none'}",
            f"Armor:  {eq['armor']['name'] if eq['armor'] else 'none'}",
            f"Ring:   {eq['ring']['name'] if eq['ring'] else 'none'}",
            "",
            "Items:",
        ]
        y = sy+1
        for l in lines:
            if y < sy+box_h-1:
                self.stdscr.addstr(y, sx+1, l[:box_w-2], cp("text")); y+=1
        # list items
        for i, it in enumerate(inv):
            if y >= sy+box_h-2: break
            mark = ">" if i == self.inv_cursor else " "
            line = f"{mark} {it['name']}"
            attr = cp("equip") if i == self.inv_cursor else cp("text")
            self.stdscr.addstr(y, sx+1, line[:box_w-2], attr)
            y += 1
        if not inv:
            if y < sy+box_h-2:
                self.stdscr.addstr(y, sx+1, "(empty)", cp("dim")); y+=1
        # help
        help_line = "Enter=equip/use  d=drop  i/q=close"
        self.stdscr.addstr(sy+box_h-1, sx+1, help_line[:box_w-2], cp("dim"))

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
        "c = stats   x = search   > = descend   S = save   q = quit",
        "",
        "Reach floor 15 to escape. Bosses every 5 floors.",
        "Secret doors, traps, mimics, ranged enemies.",
        "",
        "Press any key to begin...",
    ]
    for i, l in enumerate(info):
        stdscr.addstr(h//2 + i, max(0, w//2 - len(l)//2), l, cp("text"))
    stdscr.refresh()
    stdscr.getch()

def game_over_screen(stdscr, game):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    title = "VICTORY!" if getattr(game, "victory", False) else "GAME OVER"
    color = Color.xp if getattr(game, "victory", False) else Color.hp
    stdscr.addstr(h//2 - 2, max(0, w//2 - len(title)//2), title, curses.color_pair(color) | curses.A_BOLD)
    stats = [
        "You escaped the depths!" if getattr(game, "victory", False) else "You died in the depths.",
        f"Floor reached: {game.floor}",
        f"Level: {game.player['level']}",
        f"Gold: {game.player['gold']}",
        "",
        "Press r to retry, q to quit.",
    ]
    for i, l in enumerate(stats):
        stdscr.addstr(h//2 + i, max(0, w//2 - len(l)//2), l, cp("text"))
    stdscr.refresh()
    while True:
        k = stdscr.getch()
        if k == ord('r'): return "retry"
        if k in (ord('q'), 27): return "quit"

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    init_colors()
    title_screen(stdscr)
    while True:
        game = Game(stdscr)
        # try load? no, fresh
        game.game_over = False
        while not game.game_over:
            game.draw()
            key = stdscr.getch()
            res = game.handle_input(key)
            if res == "quit":
                return
        action = game_over_screen(stdscr, game)
        if action == "quit":
            return

if __name__ == "__main__":
    curses.wrapper(main)
