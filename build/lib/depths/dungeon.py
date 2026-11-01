"""Procedural dungeon generation and entity placement."""
import random

from .constants import BOSSES, ENEMY_STATS


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
    if floor >= 2: pool += ["o","o","a","s"]
    if floor >= 3: pool += ["T","n","V","W"]
    if floor >= 4: pool += ["T","m","G"]
    if floor >= 5: pool += ["G","n","m","W"]
    if floor >= 7: pool += ["D"]
    if floor % 5 == 0:
        pool = ["o","s","T","W","n","m"]  # boss floors: fewer heavies, the boss is the challenge
    idx = 0
    n_enemies = 3 + floor*2 + random.randint(0, 3)
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
        ch = random.choice(["!","!","*","*","*","*","/","[","$","?","?","=","w"])
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
        if boss["ch"] == "Z":
            entities[-1]["slow"] = True
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


