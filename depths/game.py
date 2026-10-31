"""Game state and rules: player, enemies, items, combat, FOV, save/load."""
import curses, json, math, os, random, time
from collections import deque

from .constants import BOSSES, PLAYER, SHOP_GOODS, SAVE, ename, cap
from .dungeon import biome, make_dungeon, place_entities
from .terminal import Color, cp
from .render import render_kitty, render_sixel


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
        if self.banner and time.time() < self.banner[1]:
            text = self.banner[0]
            bx = max(0, (self.mw - len(text)) // 2)
            by = max(0, self.mh // 2)
            try:
                self.stdscr.addstr(by, bx, text, cp("gold") | curses.A_BOLD)
            except curses.error:
                pass
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


