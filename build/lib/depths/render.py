"""Pixel rendering: PIL frame drawing, Kitty graphics protocol, sixel."""
import base64, io, math, os, re, select, shutil, sys, time

from .constants import RGB, MAP_TILES_W, MAP_TILES_H, SIDE_W, PAD, SHOP_GOODS, ename, cap, RARITY_TEXT
from .dungeon import biome
from .scores import load_scores
from .terminal import get_terminal_pixels

# ---------- Kitty pixel rendering ----------
TILE = 16



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
            rar = it["item"].get("rarity") if it.get("kind") == "equip" else None
            if i == game.inv_cursor:
                col = RGB["title"]
            elif rar and rar != "common":
                col = RARITY_TEXT[rar]
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
            rar = it["item"].get("rarity") if it.get("kind") == "equip" else None
            if i == game.inv_cursor:
                col = RGB["title"]
            elif rar and rar != "common":
                col = RARITY_TEXT[rar]
            else:
                col = RGB["text"]
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


