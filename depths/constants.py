"""depths — shared constants and small helpers."""
import os

SAVE = os.path.expanduser("~/.depths_save.json")

HIGH = os.path.expanduser("~/.depths_high.json")

ITEM_CHARS = {"!": "potion", "/": "weapon", "[": "armor", "$": "gold", "?": "scroll",
              "*": "food", "=": "ring", "(": "wand", "k": "key", "^": "trap", "w": "wand"}

ENEMY_CHARS = {"g": "goblin", "o": "orc", "T": "troll", "D": "dragon", "s": "skeleton",
               "b": "bat", "W": "wraith", "a": "archer", "n": "necromancer", "m": "mimic",
               "r": "rat", "V": "vampire", "G": "golem"}

PLAYER = "@"

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
    "g": (6, 2, 3), "o": (12, 4, 6), "T": (25, 7, 12), "D": (45, 9, 40),
    "s": (8, 3, 4), "b": (4, 1, 2), "W": (18, 6, 10), "a": (10, 3, 5),
    "n": (14, 2, 8), "m": (15, 4, 6), "r": (3, 1, 1), "V": (22, 5, 12),
    "G": (40, 6, 15),
}

ENEMY_NAMES = {"g": "the goblin", "o": "the orc", "T": "the troll", "D": "the dragon",
               "s": "the skeleton", "b": "the bat", "W": "the wraith", "a": "the archer",
               "n": "the necromancer", "m": "the mimic", "r": "the rat",
               "V": "the vampire", "G": "the golem"}

BOSSES = {
    5:  {"ch": "B", "name": "the Goblin King",      "hp": 48,  "atk": 7,  "xp": 60,  "color": "bossB"},
    10: {"ch": "Z", "name": "the Bone Colossus",    "hp": 100, "atk": 13, "xp": 150, "color": "bossZ"},
    15: {"ch": "L", "name": "the Lich of the Depths","hp": 130, "atk": 14, "xp": 300, "color": "bossL"},
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

MAP_TILES_W = 40

MAP_TILES_H = 25

SIDE_W = 290

PAD = 10

