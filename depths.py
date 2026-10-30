#!/usr/bin/env python3
"""depths — a tiny roguelike. Procedural dungeons, permadeath. No deps but curses."""
import curses, random, os, json, time

SAVE = os.path.expanduser("~/.depths_save.json")
HIGH = os.path.expanduser("~/.depths_high.json")

FLOOR_TILES = {".": "floor", "#": "wall", "+": "door", ">": "stairs", "<": "stairsup"}
ITEM_CHARS = {"!": "potion", "/": "weapon", "[": "armor", "$": "gold", "?": "scroll"}
ENEMY_CHARS = {"g": "goblin", "o": "orc", "T": "troll", "D": "dragon", "s": "skeleton", "b": "bat", "W": "wraith"}
PLAYER = "@"

COLORS = {
    "wall": 8, "floor": 240, "door": 94, "stairs": 220, "player": 46,
    "goblin": 34, "orc": 28, "troll": 22, "dragon": 196, "skeleton": 250,
    "bat": 95, "wraith": 141, "potion": 201, "weapon": 208, "armor": 33,
    "gold": 220, "scroll": 213, "text": 255, "hp": 196, "xp": 45,
    "dim": 238, "msg": 226, "title": 51,
}

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for name, code in COLORS.items():
        curses.init_pair(hash(name) % 200 + 1, code, -1)
    # store pair ids
    for name in COLORS:
        setattr(Color, name, hash(name) % 200 + 1)

class Color: pass

def cp(name): return curses.color_pair(getattr(Color, name))

def make_dungeon(floor, width, height):
    # grid of chars; True=walkable
    grid = [["#" for _ in range(width)] for _ in range(height)]
    rooms = []
    # generate rooms
    nrooms = random.randint(5, 9)
    attempts = 0
    while len(rooms) < nrooms and attempts < 200:
        attempts += 1
        w = random.randint(4, 9)
        h = random.randint(3, 7)
        x = random.randint(1, width - w - 2)
        y = random.randint(1, height - h - 2)
        new = (x, y, w, h)
        # check overlap
        ok = True
        for (rx, ry, rw, rh) in rooms:
            if x < rx + rw + 1 and x + w + 1 > rx and y < ry + rh + 1 and y + h + 1 > ry:
                ok = False; break
        if ok:
            rooms.append(new)
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    grid[yy][xx] = "."
    # connect rooms with corridors
    for i in range(1, len(rooms)):
        x1, y1, w1, h1 = rooms[i-1]
        x2, y2, w2, h2 = rooms[i]
        cx1, cy1 = x1 + w1//2, y1 + h1//2
        cx2, cy2 = x2 + w2//2, y2 + h2//2
        # L-shaped corridor
        if random.random() < 0.5:
            for xx in range(min(cx1, cx2), max(cx1, cx2)+1):
                grid[cy1][xx] = "."
            for yy in range(min(cy1, cy2), max(cy1, cy2)+1):
                grid[yy][cx2] = "."
        else:
            for yy in range(min(cy1, cy2), max(cy1, cy2)+1):
                grid[yy][cx1] = "."
            for xx in range(min(cx1, cx2), max(cx1, cx2)+1):
                grid[yy2 if False else cy2][xx] = "."
    # doors: place on room entrances randomly
    return grid, rooms

def place_entities(grid, width, height, floor, player_pos):
    entities = []  # list of dicts
    items = []
    # enemies count scales with floor
    n_enemies = 3 + floor*2 + random.randint(0, 3)
    # candidate floor tiles not near player
    candidates = []
    for y in range(1, height-1):
        for x in range(1, width-1):
            if grid[y][x] == ".":
                if abs(x-player_pos[0]) + abs(y-player_pos[1]) > 6:
                    candidates.append((x, y))
    random.shuffle(candidates)
    # enemy types by floor
    pool = ["g","g","o","s","b"]
    if floor >= 2: pool += ["o","T","W"]
    if floor >= 4: pool += ["T","D"]
    if floor % 5 == 0:
        pool = ["D","T","T","W","W"]
    idx = 0
    for _ in range(n_enemies):
        if idx >= len(candidates): break
        x, y = candidates[idx]; idx += 1
        ch = random.choice(pool)
        hp = {"g":6,"o":12,"T":25,"D":60,"s":8,"b":4,"W":18}[ch]
        atk = {"g":2,"o":4,"T":7,"D":15,"s":3,"b":1,"W":6}[ch]
        entities.append({"ch":ch,"x":x,"y":y,"hp":hp,"maxhp":hp,"atk":atk,"name":ENEMY_CHARS[ch]})
    # items
    n_items = random.randint(2, 4) + floor//2
    for _ in range(n_items):
        if idx >= len(candidates): break
        x, y = candidates[idx]; idx += 1
        ch = random.choice(["!","!","/","[","$","?"])
        items.append({"ch":ch,"x":x,"y":y,"name":ITEM_CHARS[ch]})
    # stairs down
    # pick a floor tile far from player
    occupied = {(e["x"],e["y"]) for e in entities} | {(it["x"],it["y"]) for it in items}
    far = [c for c in candidates if abs(c[0]-player_pos[0])+abs(c[1]-player_pos[1])>15 and c not in occupied]
    if far:
        sx, sy = random.choice(far)
        grid[sy][sx] = ">"
    return entities, items

def roll_dice(sides): return random.randint(1, sides)

class Game:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.h, self.w = stdscr.getmaxyx()
        # map dimensions
        self.mw = self.w
        self.mh = self.h - 4  # leave status rows
        self.reset()

    def reset(self):
        self.floor = 1
        self.player = {"x":0,"y":0,"hp":20,"maxhp":20,"atk":4,"def":1,"xp":0,"level":1,"gold":0,"weapon":"fists","armor":"none","potions":1,"scrolls":0}
        self.messages = []
        self.victory = False
        self.explored = set()
        self.visible = set()
        self.new_floor()

    def new_floor(self):
        self.grid, rooms = make_dungeon(self.floor, self.mw, self.mh)
        # place player in first room
        rx, ry, rw, rh = rooms[0]
        self.player["x"] = rx + rw//2
        self.player["y"] = ry + rh//2
        self.entities, self.items = place_entities(self.grid, self.mw, self.mh, self.floor, (self.player["x"], self.player["y"]))
        self.messages.append(f"--- Floor {self.floor} ---")
        self.compute_fov()

    def compute_fov(self):
        # simple radius FOV
        self.visible = set()
        px, py = self.player["x"], self.player["y"]
        R = 8
        for dy in range(-R, R+1):
            for dx in range(-R, R+1):
                if dx*dx+dy*dy > R*R: continue
                x, y = px+dx, py+dy
                if 0 <= x < self.mw and 0 <= y < self.mh:
                    # line of sight (simple: no wall blocking via bresenham-ish)
                    if self.line_of_sight(px, py, x, y):
                        self.visible.add((x,y))
                        self.explored.add((x,y))

    def line_of_sight(self, x0,y0,x1,y1):
        # bresenham
        dx = abs(x1-x0); dy = abs(y1-y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            if x == x1 and y == y1: return True
            if (x,y) != (x0,y0) and self.grid[y][x] == "#":
                return False
            e2 = 2*err
            if e2 > -dy:
                err -= dy; x += sx
            if e2 < dx:
                err += dx; y += sy

    def msg(self, text):
        self.messages.append(text)
        if len(self.messages) > 5:
            self.messages = self.messages[-5:]

    def move_player(self, dx, dy):
        nx, ny = self.player["x"]+dx, self.player["y"]+dy
        if not (0 <= nx < self.mw and 0 <= ny < self.mh): return
        # wall?
        if self.grid[ny][nx] == "#": 
            self.msg("A wall blocks your path.")
            return
        # enemy?
        for e in self.entities:
            if e["x"]==nx and e["y"]==ny and e["hp"]>0:
                self.attack(e)
                return
        # item?
        for it in self.items:
            if it["x"]==nx and it["y"]==ny:
                self.pickup(it)
                self.items.remove(it)
        # stairs?
        if self.grid[ny][nx] == ">":
            self.floor += 1
            self.msg(f"You descend to floor {self.floor}.")
            self.new_floor()
            return
        self.player["x"], self.player["y"] = nx, ny
        self.enemy_turn()
        self.compute_fov()

    def attack(self, e):
        patk = self.player["atk"]
        edef = 1
        dmg = max(1, patk - edef + random.randint(-1, 2))
        e["hp"] -= dmg
        self.msg(f"You hit {e['name']} for {dmg}.")
        if e["hp"] <= 0:
            self.msg(f"{e['name']} dies.")
            xp_gain = {"g":3,"o":6,"T":12,"D":40,"s":4,"b":2,"W":10}[e["ch"]]
            self.player["xp"] += xp_gain
            self.check_level()
            e["hp"] = 0
        else:
            # enemy counterattack happens in enemy_turn for that enemy? We'll let enemy_turn handle
            pass
        self.enemy_turn()
        self.compute_fov()

    def enemy_turn(self):
        for e in self.entities:
            if e["hp"] <= 0: continue
            # if adjacent to player, attack
            if abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"]) == 1:
                dmg = max(1, e["atk"] - self.player["def"] + random.randint(-1,1))
                self.player["hp"] -= dmg
                self.msg(f"{e['name']} hits you for {dmg}.")
                if self.player["hp"] <= 0:
                    self.player["hp"] = 0
                    self.game_over = True
                continue
            # move toward player if visible/close
            if (e["x"],e["y"]) in self.visible or abs(e["x"]-self.player["x"]) + abs(e["y"]-self.player["y"]) <= 6:
                # simple path: step toward
                dx = 0
                if e["x"] < self.player["x"]: dx = 1
                elif e["x"] > self.player["x"]: dx = -1
                dy = 0
                if e["y"] < self.player["y"]: dy = 1
                elif e["y"] > self.player["y"]: dy = -1
                # try
                nx, ny = e["x"]+dx, e["y"]+dy
                if 0<=nx<self.mw and 0<=ny<self.mh and self.grid[ny][nx] in (".",">") and not any(o["x"]==nx and o["y"]==ny and o["hp"]>0 for o in self.entities if o is not e) and not (nx==self.player["x"] and ny==self.player["y"]):
                    e["x"], e["y"] = nx, ny

    def pickup(self, it):
        ch = it["ch"]
        if ch == "!":
            self.player["potions"] += 1
            self.msg("You pick up a health potion.")
        elif ch == "/":
            self.player["atk"] += 2
            self.msg("You find a better weapon. ATK +2.")
        elif ch == "[":
            self.player["def"] += 1
            self.player["maxhp"] += 2
            self.player["hp"] = min(self.player["hp"]+2, self.player["maxhp"])
            self.msg("You find armor. DEF +1, HP +2.")
        elif ch == "$":
            amt = random.randint(5, 20)
            self.player["gold"] += amt
            self.msg(f"You find {amt} gold.")
        elif ch == "?":
            self.player["scrolls"] += 1
            self.msg("You find a scroll.")

    def use_scroll(self):
        if self.player["scrolls"] <= 0:
            self.msg("No scrolls.")
            return
        self.player["scrolls"] -= 1
        effect = random.choice(["reveal","fireball","teleport"])
        if effect == "reveal":
            for y in range(self.mh):
                for x in range(self.mw):
                    self.explored.add((x,y))
            self.msg("The scroll reveals the floor.")
        elif effect == "fireball":
            for e in self.entities:
                if e["hp"]>0 and (e["x"],e["y"]) in self.visible:
                    e["hp"] -= 10
                    self.msg(f"Fireball hits {e['name']} for 10.")
                    if e["hp"]<=0:
                        self.msg(f"{e['name']} dies.")
                        e["hp"]=0
        else:
            tiles = [(x,y) for y in range(self.mh) for x in range(self.mw) if self.grid[y][x]=="." and (x,y) not in {(e["x"],e["y"]) for e in self.entities if e["hp"]>0}]
            if tiles:
                self.player["x"], self.player["y"] = random.choice(tiles)
                self.msg("You teleport.")
        self.enemy_turn()
        self.compute_fov()

    def use_potion(self):
        if self.player["potions"] <= 0:
            self.msg("No potions.")
            return
        self.player["potions"] -= 1
        heal = random.randint(8, 14)
        self.player["hp"] = min(self.player["maxhp"], self.player["hp"]+heal)
        self.msg(f"You drink a potion. +{heal} HP.")
        self.enemy_turn()
        self.compute_fov()

    def check_level(self):
        need = self.player["level"] * 10
        while self.player["xp"] >= need:
            self.player["xp"] -= need
            self.player["level"] += 1
            self.player["maxhp"] += 5
            self.player["hp"] = self.player["maxhp"]
            self.player["atk"] += 1
            self.msg(f"Level up! You are now level {self.player['level']}.")
            need = self.player["level"] * 10

    def draw(self):
        self.stdscr.erase()
        # draw map
        for y in range(self.mh):
            for x in range(self.mw):
                ch = self.grid[y][x]
                if (x,y) in self.visible:
                    if ch == "#":
                        self.stdscr.addstr(y, x, "#", cp("wall"))
                    elif ch == ".":
                        self.stdscr.addstr(y, x, ".", cp("floor"))
                    elif ch == ">":
                        self.stdscr.addstr(y, x, ">", cp("stairs"))
                    elif ch == "+":
                        self.stdscr.addstr(y, x, "+", cp("door"))
                elif (x,y) in self.explored:
                    if ch == "#":
                        self.stdscr.addstr(y, x, "#", cp("dim"))
                    else:
                        self.stdscr.addstr(y, x, ".", cp("dim"))
        # items
        for it in self.items:
            if (it["x"],it["y"]) in self.visible:
                self.stdscr.addstr(it["y"], it["x"], it["ch"], cp(it["ch"] if False else {"!":"potion","/":"weapon","[":"armor","$":"gold","?":"scroll"}[it["ch"]]))
        # enemies
        for e in self.entities:
            if e["hp"]>0 and (e["x"],e["y"]) in self.visible:
                self.stdscr.addstr(e["y"], e["x"], e["ch"], cp(e["name"]))
        # player
        self.stdscr.addstr(self.player["y"], self.player["x"], PLAYER, cp("player") | curses.A_BOLD)
        # status bar
        sy = self.mh
        p = self.player
        hp_bar = "HP:" + str(p["hp"]) + "/" + str(p["maxhp"])
        self.stdscr.addstr(sy, 0, ("─"*(self.w-1)), cp("dim"))
        status = f" Floor {self.floor}  {hp_bar}  ATK {p['atk']}  DEF {p['def']}  LVL {p['level']}  XP {p['xp']}/{p['level']*10}  Gold {p['gold']}  Pot {p['potions']}  Scr {p['scrolls']} "
        self.stdscr.addstr(sy+1, 0, status[:self.w-1], cp("text"))
        # messages
        for i, m in enumerate(self.messages[-2:]):
            self.stdscr.addstr(sy+2+i, 0, m[:self.w-1], cp("msg"))
        self.stdscr.refresh()

    def handle_input(self, key):
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
        elif key == ord('r'): self.use_scroll()
        elif key == ord('>'): 
            if self.grid[self.player["y"]][self.player["x"]] == ">":
                if self.floor >= 10:
                    self.game_over = True
                    self.victory = True
                    self.msg("You escaped the depths!")
                    return
                self.floor += 1; self.msg(f"Descend to floor {self.floor}."); self.new_floor()
        return None

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
        stdscr.addstr(h//2 - 8 + i, max(0, w//2 - len(l)//2), l, curses.color_pair(getattr(Color,'title')) | curses.A_BOLD)
    info = [
        "A tiny roguelike. Procedural dungeons. Permadeath.",
        "",
        "Move: arrows / WASD / hjkl   Diagonals: yubn",
        "p = potion   r = scroll   > = descend   q = quit",
        "",
        "Collect gold, find weapons & armor, level up.",
        "Reach as deep as you can.",
        "",
        "Press any key to begin...",
    ]
    for i, l in enumerate(info):
        stdscr.addstr(h//2 + i, max(0, w//2 - len(l)//2), l, curses.color_pair(getattr(Color,'text')))
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
        stdscr.addstr(h//2 + i, max(0, w//2 - len(l)//2), l, curses.color_pair(getattr(Color,'text')))
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
        game.game_over = False
        while not game.game_over:
            game.draw()
            key = stdscr.getch()
            res = game.handle_input(key)
            if res == "quit":
                return
        # save high score
        try:
            best = 0
            if os.path.exists(HIGH):
                best = json.load(open(HIGH)).get("floor",0)
            if game.floor > best:
                json.dump({"floor":game.floor,"level":game.player["level"],"gold":game.player["gold"]}, open(HIGH,"w"))
        except Exception:
            pass
        action = game_over_screen(stdscr, game)
        if action == "quit":
            return

if __name__ == "__main__":
    curses.wrapper(main)
