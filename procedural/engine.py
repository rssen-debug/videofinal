# -*- coding: utf-8 -*-
"""
engine.py – Pixelmotorn. Hela sagovärlden ritas proceduellt på CPU.

v3:
  • KARAKTÄRSREGISTER: samma namn = alltid samma karaktär (art + färg),
    i varje scen, varje avsnitt. "Doris är alltid samma Doris."
  • Arter: dino, apa, kanin. Flera karaktärer kan vara i samma scen.
  • Action per karaktär: walk, run, jump, dance, spin, hit, duck, wave, sleep.
"""
import hashlib
import math
import random

from PIL import Image, ImageDraw, ImageOps

W, H = 320, 180
GROUND_Y = 150
CHAR_X = 82
CHAR_SCALE = 2
ACTOR_GAP = 52

NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")
ACTIONS = ("walk", "run", "jump", "dance", "spin", "hit", "duck", "wave", "sleep",
           "fire", "shock", "fall", "flex", "powerup")
LAND = frozenset(["forest", "night", "beach", "space", "snow", "candy", "city"])


def _rows(s):
    lines = [ln.rstrip() for ln in s.strip("\n").splitlines()]
    w = max(len(ln) for ln in lines)
    return [ln.ljust(w, ".") for ln in lines]


def _sprite_image(rows, colors, blink=False):
    h, w = len(rows), max(len(r) for r in rows)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in colors:
                continue
            c = colors[ch]
            if blink and ch == "W":
                c = colors.get("O", c)
            px[x, y] = c
    return img


def _lighter(c, f=1.28):
    return tuple(min(255, int(v * f + 14)) for v in c[:3])


# ---------------------------------------------------------------------------
# SPRITES
# O=kropp  D=mörk fläck  B=mage/nos  E=öra  W=öga  K=pupill
# ---------------------------------------------------------------------------
DINO_A = _rows("""
............OOOO......
..........OOOOOOOO....
..........OOOOWWOO....
..........OOOOWKOO....
..........OOOOOOO.....
........OOOOOOOO......
.....OODOODOOOO.......
...OODOODOOOOBBB......
.OOOOOOOOOOBBBB.......
OOOOOOOOOOBBBBB.......
OOOOOOOBBBBBBB........
.OOOOBBBBBBB..........
....OOOOBBBB..........
.....OOOOOBB..........
.....OO...OO..........
.....OO...OO..........
.....OO...OO..........
....OOO...OOO.........
""")

DINO_B = _rows("""
............OOOO......
..........OOOOOOOO....
..........OOOOWWOO....
..........OOOOWKOO....
..........OOOOOOO.....
........OOOOOOOO......
.....OODOODOOOO.......
...OODOODOOOOBBB......
.OOOOOOOOOOBBBB.......
OOOOOOOOOOBBBBB.......
OOOOOOOBBBBBBB........
.OOOOBBBBBBB..........
....OOOOBBBB..........
.....OOOOOBB..........
.....OO...OO..........
....OOO...OO..........
....OO....OOO.........
""")

APE_A = _rows("""
............MMMM......
.........MMMMMMMM.....
........EMMMWWMMME....
........EMMMWKMMME....
.........MMMBBBM......
.........MMMBBM.......
..M.....MMMMMMMM......
..MM..MMMMMMMMDMMM....
..MM.MMMMMMMMMBBMMM...
..MMM.MMMMMMMBBB......
...MMMMMMMMBBBBB......
....MMMMMMBBBBB.......
.....MMMMMBBB.........
......MMMMM...........
......MM...MM.........
......MM...MM.........
......MM...MM.........
.....MMM...MMM........
""")

APE_B = _rows("""
............MMMM......
.........MMMMMMMM.....
........EMMMWWMMME....
........EMMMWKMMME....
.........MMMBBBM......
.........MMMBBM.......
..M.....MMMMMMMM......
..MM..MMMMMMMMDMMM....
..MM.MMMMMMMMMBBMMM...
..MMM.MMMMMMMBBB......
...MMMMMMMMBBBBB......
....MMMMMMBBBBB.......
.....MMMMMBBB.........
......MMMMM...........
......MM...MM.........
.....MM.....MM........
.....MM....MMM........
""")

BUNNY_A = _rows("""
..........OO.OO.......
..........OEOEO.......
..........OEOEO.......
..........OOOOO.......
..........OOOOOO......
..........OOOWWOO.....
..........OOOWKOO.....
..........OOOOB.......
.....OOOOOOOO.........
..WWOOOOOOOBB.........
..WWOOOOOOOBBB........
...OOOOOOBBBBB........
....OOOOBBBBB.........
.....OOOOBB...........
.....O....O...........
....O......O..........
....OO....OOO.........
..OOOO..OOOOO.........
""")

BUNNY_B = _rows("""
..........OO.OO.......
..........OEOEO.......
..........OEOEO.......
..........OOOOO.......
..........OOOOOO......
..........OOOWWOO.....
..........OOOWKOO.....
..........OOOOB.......
.....OOOOOOOO.........
..WWOOOOOOOBB.........
..WWOOOOOOOBBB........
...OOOOOOBBBBB........
....OOOOBBBBB.........
.....OOOOBB...........
.....O....O...........
....O......O..........
....OO......OO........
..OOOO....OOOO........
""")

FAGEL_A = _rows("""
.k...k.
.kk.kk.
..kkk..
""")
FAGEL_B = _rows("""
..kkk..
.kk.kk.
.k...k.
""")

# --- Mysteriet: "The Watcher" – en liten mörk figur i bakgrunden ---
WATCHER = _rows("""
...kkk...
..kkkkk..
..kkkkk..
..k.k.k..
..kkkkk..
..kkkkk..
..kkkkk..
.kkkkkkk.
kkkkkkkkk
""")

# --- Nya props ---
TORCH = _rows("""
...yy...
..yoyy..
..yooy..
..yyyy..
...kk...
....k...
....k...
....k...
....k...
...kk...
""")
PORTAL = _rows("""
.....pppppp.....
...ppvvvvvvpp...
..pvccccccccvp..
.pvccggggggccvp.
pvcgckkkkkcgcvp
pvcgckkkkkcgcvp
pvcgckkkkkcgcvp
pvcgckkkkkcgcvp
.pvccggggggccvp.
..pvccccccccvp..
...ppvvvvvvpp...
.....pppppp.....
""")
UFO = _rows("""
.....dd.....
...dddddd...
..ssssssss..
.ssssssssss.
swwswwswwswws
..ssssssss..
.....ss.....
""")
BOULDER = _rows("""
....gggggg....
..gggggggggg..
.ggccggggcggg.
gggcgggggggggg
ggggggcggccggg
gggggggggggggg
.ggcggggcgggg.
..gggggggggg..
....gggggg....
""")
SWORD = _rows("""
...yy...
..yyyy..
..yggk..
..gggg..
..kggg..
...g....
...g....
...g....
...g....
..gg....
..gg....
.kggk...
""")

# --- Uttrycks-märken (humor genom överdrift!) ---
_NOTE = _rows("""
....##..
....##..
....###.
....#...
....#...
.##.#...
#####...
.###....
""")
_ANGERX = _rows("""
#...#
.#.#.
..#..
.#.#.
#...#
""")
_SWEAT = _rows("""
..c..
..cc.
.ccc.
.ccc.
..c..
""")

def _rim_light(img, side):
    """Ljusstrimma på kant mot ljuskällan (uppe ifrån + åt ena hållet)."""
    a = img.getchannel("A")
    up = Image.new("L", img.size, 0)
    up.paste(a, (0, 1))
    lat = Image.new("L", img.size, 0)
    lat.paste(a, (side, 0))
    from PIL import ImageChops
    edge = ImageChops.subtract(a, up)
    edge = ImageChops.lighter(edge, ImageChops.subtract(a, lat))
    edge = ImageChops.multiply(edge, a.point(lambda v: 210 if v else 0))
    rim = Image.new("RGBA", img.size, (0, 0, 0, 0))
    warm = Image.new("RGBA", img.size, (255, 246, 214, 0))
    warm.putalpha(edge)
    rim.alpha_composite(warm)
    out = img.copy()
    out.alpha_composite(rim)
    return out


_TINT_CACHE = {}


def scene_tint(character, ambient):
    """Blendkaraktärens frames ~16% mot scenambienten – ljuset smittar!"""
    key = (character.species, character.tint, ambient)
    if key not in _TINT_CACHE:
        out = {}
        for fk, fimg in character._base_frames.items():
            wash = Image.new("RGBA", fimg.size, ambient + (0,))
            m = fimg.getchannel("A").point(lambda v: int(v * 0.16))
            wash.putalpha(m)
            img = fimg.copy()
            img.alpha_composite(wash)
            out[fk] = img
        _TINT_CACHE[key] = out
    character.frames = _TINT_CACHE[key]


# ---------------------------------------------------------------------------
# KARAKTÄRSREGISTER – samma namn, samma karaktär. För evigt.
# ---------------------------------------------------------------------------
DINO_TINTS = {
    "orange": {"O": (244, 132, 42),  "D": (210, 96, 28),  "B": (255, 213, 148)},
    "grön":   {"O": (104, 190, 78),  "D": (66, 145, 46),  "B": (215, 245, 178)},
    "teal":   {"O": (62, 186, 174),  "D": (34, 138, 128), "B": (192, 244, 236)},
    "lila":   {"O": (158, 110, 230), "D": (116, 74, 180), "B": (226, 206, 255)},
    "rosa":   {"O": (240, 120, 160), "D": (196, 78, 122), "B": (255, 205, 224)},
    "crimson":{"O": (214, 72, 86),   "D": (162, 44, 58),  "B": (255, 196, 160)},
}
APE_TINTS = {
    # "M" = kroppen (BUGGFIX: utan denna nyckel ritades apan osynlig!),
    # "D" = mörka fläckar, "B" = mage/ansikte, "E" = öron
    "brun":    {"O": (150, 100, 58), "M": (150, 100, 58), "D": (112, 72, 40),  "B": (230, 196, 152), "E": (230, 196, 152)},
    "gyllene": {"O": (205, 150, 60), "M": (205, 150, 60), "D": (160, 112, 40), "B": (250, 224, 168), "E": (250, 224, 168)},
    "grå":     {"O": (140, 145, 155), "M": (140, 145, 155), "D": (105, 110, 120), "B": (215, 220, 228), "E": (215, 220, 228)},
    "kolnatt": {"O": (94, 96, 118), "M": (94, 96, 118), "D": (62, 64, 84), "B": (216, 212, 228), "E": (216, 212, 228)},
}
BUNNY_TINTS = {
    "vit":  {"O": (236, 236, 242), "D": (204, 204, 216), "B": (255, 255, 255), "E": (255, 165, 195)},
    "grå":  {"O": (165, 168, 178), "D": (130, 133, 145), "B": (228, 230, 236), "E": (255, 165, 195)},
    "rosa": {"O": (248, 175, 195), "D": (220, 138, 162), "B": (255, 222, 232), "E": (255, 255, 255)},
    "brun": {"O": (190, 145, 95),  "D": (150, 110, 66),  "B": (235, 205, 165), "E": (255, 190, 205)},
    "blå":  {"O": (96, 140, 220),  "D": (58, 94, 166),   "B": (196, 222, 255), "E": (255, 180, 205)},
}

MECH_A = _rows("""
.........E...........
.........D...........
.....OOOOOOOOOOO.....
.....OWWWWWWWWO.....
.....OWWWWKWWWWO.....
......DDDDDDDDD......
...DD.OOOOOOOOOO.DD...
...DD.OOOBBBBOOO.DD...
...DD.OOOBBBBOOO.DD...
...DD.OOOBBBBOOO.DD...
...DD.OOOOOOOOOO.DD...
......DOOOOOOOOD.....
......OOOOOOOOOO.....
.......OOO..OOO......
.......OOO..OOO......
.......OOO..OOO......
......OOOO..OOOO.....
""")

MECH_B = _rows("""
.........E...........
.........D...........
.....OOOOOOOOOOO.....
.....OWWWWWWWWO.....
.....OWWWWKWWWWO.....
......DDDDDDDDD......
...DD.OOOOOOOOOO.DD...
...DD.OOOBBBBOOO.DD...
...DD.OOOBBBBOOO.DD...
...DD.OOOBBBBOOO.DD...
...DD.OOOOOOOOOO.DD...
......DOOOOOOOOD.....
......OOOOOOOOOO.....
.......OOO..OOO......
.......OOO..OOO......
......OOO...OOO......
.....OOOO...OOOO.....
""")

# B = glödande reaktorkärna; visiren (W) "blinkar" automatiskt som en robot ska
MECH_TINTS = {
    "krom":    {"O": (176, 184, 202), "D": (112, 120, 146), "B": (110, 228, 255)},
    "midnatt": {"O": (74, 82, 112),   "D": (46, 52, 76),    "B": (255, 140, 70)},
}

SPECIES_MAPS = {"dino": (DINO_A, DINO_B), "apa": (APE_A, APE_B), "kanin": (BUNNY_A, BUNNY_B),
                "mech": (MECH_A, MECH_B)}
SPECIES_TINTS = {"dino": DINO_TINTS, "apa": APE_TINTS, "kanin": BUNNY_TINTS,
                  "mech": MECH_TINTS}

# Fast rollista (key -> (art, färg, visningsnamn, alias som hör till samma karaktär))
REGISTRY = {
    "doris": ("dino", "rosa",   "Doris"),
    "boris": ("dino", "teal",   "Boris"),
    "leo":   ("dino", "orange", "Leo"),
    "nova":  ("dino", "lila",   "Nova"),
    "trix":  ("dino", "grön",   "Trix"),
    "puff":  ("dino", "lila",   "Puff"),
    "milo":  ("dino", "orange", "Milo"),
    "zia":   ("dino", "teal",   "Zia"),
    "apa":   ("apa",  "brun",   "Rico"),
    "apan":  ("apa",  "brun",   "Rico"),
    "bosse": ("apa",  "gyllene", "Bosco"),
    "kanin": ("kanin", "vit",   "Hops"),
    "kaninen": ("kanin", "vit", "Hops"),
    "kurre": ("kanin", "grå",   "Ash"),
    "stina": ("kanin", "rosa",  "Pix"),
    # ----- KNOX HOLLOW (pixel-anime-ensemblen) -----
    "jun":   ("dino",  "crimson", "Jun"),     # hetlevrad shonen-hjälte
    "mira":  ("kanin", "blå",     "Mira"),    # kylig strateg
    "knox":  ("mech",  "krom",    "Knox"),    # uråldrig väktarmecha (comic relief)
    "grim":  ("apa",   "kolnatt", "Grim"),    # rivalen med hederskodex
}


def _canon(name):
    return REGISTRY.get(str(name).strip().lower())


def resolve_character(name):
    """namn -> (art, tint, visningsnamn). Okända namn får stabil hash-identitet."""
    key = str(name).strip().lower()
    hit = _canon(key)
    if hit:
        sp, tint, disp = hit
        return key, sp, tint, disp
    digest = hashlib.md5(key.encode("utf-8")).digest()
    sp = ("dino", "dino", "apa", "kanin")[digest[0] % 4]
    tints = sorted(SPECIES_TINTS[sp])
    tint = tints[digest[1] % len(tints)]
    disp = str(name).strip().capitalize()
    return key, sp, tint, disp


def alias_group(name):
    """Alla namn/alias som pekar på samma karaktär (för verb-parsern)."""
    key, sp, tint, disp = resolve_character(name)
    group = {key, disp.lower()}
    for k, v in REGISTRY.items():
        if v[0] == sp and v[1] == tint:
            group.add(k)
            group.add(v[2].lower())
    return {g for g in group if g}


_FRAME_CACHE = {}


class Character:
    """En persistent karaktär. Character('doris') ser ALLTID likadan ut."""

    def __init__(self, name="leo"):
        self.key, self.species, self.tint, self.display = resolve_character(name)
        cache_key = (self.species, self.tint)
        if cache_key not in _FRAME_CACHE:
            cols = dict(SPECIES_TINTS[self.species][self.tint])
            cols.setdefault("W", (255, 255, 255))
            cols.setdefault("K", (28, 28, 32))
            cols.setdefault("E", cols["B"])
            a, b = SPECIES_MAPS[self.species]
            frames = {}
            for tag, rows_ in (("A", a), ("B", b)):
                for blink, suf in ((False, ""), (True, "_b")):
                    img = _sprite_image(rows_, cols, blink=blink)
                    frames[tag + suf] = img.resize(
                        (img.width * CHAR_SCALE, img.height * CHAR_SCALE), NEAREST)
                    frames[tag + suf + "f"] = frames[tag + suf].transpose(
                        Image.FLIP_LEFT_RIGHT)
            for fk, fimg in list(frames.items()):      # v9: warm rim light
                side = -1 if fk.endswith("f") else 1
                frames[fk] = _rim_light(fimg, side)
            _FRAME_CACHE[cache_key] = frames
        self.frames = _FRAME_CACHE[cache_key]
        self._base_frames = self.frames
        self.w = self.frames["A"].width
        self.h = self.frames["A"].height
        self.hopping = self.species == "kanin"


# ---------------------------------------------------------------------------
# v9: ord-burst, fisheye, scen-wipes
# ---------------------------------------------------------------------------
def _word_burst(img, word, pos, pop, age):
    """Pixlad BAM/BAAM som poppar fram och darrar (anime sound-effect shot)."""
    fx, fy = pos or (130, 60)
    sc = 3 if pop < 1 else 4
    fs = 24 if pop < 1 else 28
    wimg = _pixel_word(word, fs)
    jitter = int(2 * math.sin(age * 40)) if age > 0.12 else 0
    out = img.copy()
    out.paste(wimg, (fx - wimg.width // 2, fy - wimg.height // 2 + jitter), wimg)
    return out


_WORD_FONT_CACHE = {}


def _pixel_word(word, fs):
    if (word, fs) in _WORD_FONT_CACHE:
        return _WORD_FONT_CACHE[(word, fs)]
    import PIL.ImageFont
    font = PIL.ImageFont.load_default()
    timg = Image.new("RGBA", (len(word) * 9 + 8, 13), (0, 0, 0, 0))
    td = ImageDraw.Draw(timg)
    td.text((2, 2), word, fill=(255, 255, 255, 255), font=font)
    timg = timg.crop(timg.getbbox())
    timg = timg.resize((timg.width * fs // 8, timg.height * fs // 8), NEAREST)
    out = Image.new("RGBA", (timg.width + 8, timg.height + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):
        d.bitmap((4 + ox, 4 + oy), timg, fill=(28, 12, 30, 255))
    out.paste(timg, (4, 4), timg)
    _WORD_FONT_CACHE[(word, fs)] = out
    return out


def _fisheye(img, amount):
    """Tunn cylindrisk lins: anamorfisk öppningsbild."""
    bands = 12
    out = Image.new("RGB", (W, H), (0, 0, 0))
    bh = H // bands
    for b in range(bands):
        y0 = b * bh
        y1 = H if b == bands - 1 else y0 + bh
        cy = (b + 0.5) / bands
        f = 1.0 - amount * (abs(cy - 0.5) * 2) ** 1.6
        seg = img.crop((0, y0, W, y1))
        nw = max(16, int(W * f))
        seg = seg.resize((nw, y1 - y0), NEAREST)
        out.paste(seg, ((W - nw) // 2, y0))
    return out


def _draw_wipe(d2, style, p):
    """Svart täcke som dras undan – linjevändning, jalusi eller iris."""
    if style == 0:                                  # diagonal linje-wipe
        edge = int((W + 90) * (1 - p)) - 45
        d2.polygon([(0, 0), (edge + 45, 0), (edge - 45, H), (0, H)], fill=(8, 6, 14))
    elif style == 1:                                # venetian-jalusi
        slats = 6
        for s in range(slats):
            y0 = s * H // slats
            hh = int((H // slats) * (1 - p))
            if hh > 0:
                d2.rectangle([0, y0, W, y0 + hh], fill=(8, 6, 14))
    else:                                           # iris: växande cirkelreveal
        cx, cy = W // 2, H // 2
        rr = max(1, int(240 * p))
        top_, bot_ = max(0, cy - rr), min(H, cy + rr)
        d2.rectangle([0, 0, W, top_], fill=(8, 6, 14))
        d2.rectangle([0, bot_, W, H], fill=(8, 6, 14))
        lft = max(0, cx - rr)
        d2.rectangle([0, top_, lft, bot_], fill=(8, 6, 14))
        d2.rectangle([min(W, cx + rr), top_, W, bot_], fill=(8, 6, 14))


# ---------------------------------------------------------------------------
# Reaktionssymboler + POW-stjärna
# ---------------------------------------------------------------------------
_BANG = _rows(".##.\n.##.\n.##.\n.##.\n....\n.##.")
_QUES = _rows(".###.\n#...#\n....#\n..##.\n..#..\n.....\n..#..")
_HEART = _rows(".##.##.\n#######\n#######\n.#####.\n..###..\n...#...")
_STAR = _rows("...#...\n..###..\n#######\n.#####.\n..#.#..")
_ZED = _rows("####\n...#\n..#.\n.#..\n####")
_POW = _rows("..y...y..\n.yyy.yyy.\n..yyyyy..\nyyyyyyyyy\n..yyyyy..\n.yyy.yyy.\n..y...y..")

REACTIONS = {"!": (_BANG, (232, 60, 60)), "?": (_QUES, (70, 140, 235)),
             "♥": (_HEART, (240, 90, 130)), "★": (_STAR, (245, 200, 60))}


def _bubble(sym_rows, color, scale=2):
    sw, sh = len(sym_rows[0]), len(sym_rows)
    bw, bh = sw * scale + 8, sh * scale + 8
    img = Image.new("RGBA", (bw, bh + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=4,
                        fill=(255, 255, 255, 245), outline=(58, 58, 68, 255), width=1)
    d.polygon([(3, bh - 1), (9, bh - 1), (3, bh + 3)], fill=(255, 255, 255, 245))
    sym = _sprite_image(sym_rows, {"#": color})
    sym = sym.resize((sw * scale, sh * scale), NEAREST)
    img.paste(sym, (4, 4), sym)
    return img


# ---------------------------------------------------------------------------
# OBJEKTBIBLIOTEKET
# ---------------------------------------------------------------------------
MUSHROOM = _rows("""
...rrrr...
..rwwrrwr..
.rrrrrrrr.
rrrrrrrrrr
...wwww...
...wwww...
...wwww...
""")
HOUSE = _rows("""
......r......
.....rrr.....
....rrrrr....
...rrrrrrr...
..rrrrrrrrr..
.bbbbbbbbbbb.
.bbyybbbyybb.
.bbyybbbyybb.
.bbbbbddbbbb.
.bbbbbddbbbb.
.bbbbbddbbbb.
""")
ROCKET = _rows("""
.....rrr.....
....rrrrr....
....sssss....
....swwws....
....swwws....
....sssss....
....sssss....
....sssss....
...fsssssf...
..ffsssssff..
..fsssssssf..
..gsssssssg..
""")
SNOWMAN = _rows("""
...wwww...
..wwwwww..
..wkwkww..
..wwowww..
..wwwwww..
...rrrr...
..wwwwww..
.wwwwwwww.
.wwkwwkww.
wwwwwwwwww
""")
FISH_A = _rows("""
....oooo..
t..oooooo.
ttoooooowo
t..oooooo.
....oooo..
""")
FISH_B = _rows("""
....oooo..
tt.oooooo.
.toooooowo
tt.oooooo.
....oooo..
""")
CRAB = _rows("""
.k.....k.
.kk...kk.
..rrrrr..
rrrrrrrrr
r.rrrrr.r
..r.r.r..
.r..r..r.
""")
SHELL = _rows("""
...pp...
..pppp..
.pwpwpp.
pppppppp
pwwppwwp
""")
CAKE = _rows("""
......y.....
......c.....
...ffffff...
..ffffffff..
..pppppppp..
..pwppppwp..
..pppppppp..
.pppppppppp.
.pwwpwwpwwp.
.pppppppppp.
""")
ICECREAM = _rows("""
...pppp...
..pppppp..
.pppppppp.
.pwwppwwp.
.pppppppp.
..pppppp..
...oooo...
...oooo...
....oo....
....oo....
.....o....
""")
BALLOON = _rows("""
...rrrr...
..rrrrrr..
.rrrrrrrr.
.rrwrrrrr.
.rrrrrrrr.
..rrrrrr..
...rrrr...
....rr....
....s.....
....s.....
...s......
""")
GSTAR = _rows("""
...y...
..yyy..
yyyyyyy
.yyyyy.
..y.y..
.y...y.
""")
GEM = _rows("""
...cccc...
..cwwccc..
.cccccccc.
cccccccccc
.cccccccc.
..cccccc..
...cccc...
....cc....
""")
CHEST = _rows("""
..KKKKKKKKK..
.KKKKKKKKKKK.
.KGKKKKKGKKK.
KKKKKYYYKKKKK
.KGKKKKKGKKK.
.KGKKKKKGKKK.
.KKKKKKKKKKK.
""")
BUSH = _rows("""
...gggg...
..grgggg..
.gggggrgg.
gggggggggg
.grgggggg.
..gggrgg..
""")
FROG = _rows("""
wkw...wkw
.ww...ww.
.ggggggg.
ggggggggg
ggggggggg
.gg...gg.
.g.....g.
""")
BIGFLOWER = _rows("""
..ppp..
.ppppp.
.ppypp.
.ppppp.
..ppp..
...g...
..gg...
...g...
..g.g..
...g...
""")

_FISH_COLORS = [(255, 140, 40), (90, 190, 255), (255, 210, 60), (255, 90, 120)]
_BALLOON_COLORS = [(240, 80, 90), (90, 170, 255), (255, 205, 70), (150, 230, 120)]


def _rainbow_img():
    img = Image.new("RGBA", (74, 42), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cols = [(255, 90, 90), (255, 175, 60), (255, 230, 90), (120, 220, 110), (95, 165, 255)]
    for i, c in enumerate(cols):
        r = 33 - i * 3
        d.arc([37 - r, 42 - r, 37 + r, 42 + r], 180, 360, fill=c + (215,), width=3)
    return img


def _prop_entry(img_fn, zone, settings, kw):
    return {"img": img_fn, "zone": zone, "settings": settings, "kw": kw}


PROPS = {
    "svamp": _prop_entry(lambda r: _sprite_image(MUSHROOM, {"r": (225, 60, 60), "w": (245, 238, 220)}),
                         "ground", LAND, ["svamp", "mushroom"]),
    "hus": _prop_entry(lambda r: _sprite_image(HOUSE, {"r": (205, 80, 60), "b": (250, 235, 205),
                                                       "y": (150, 200, 230), "d": (120, 70, 35)}),
                       "ground", LAND, ["hus ", "house", "hemma"]),
    "raket": _prop_entry(lambda r: _sprite_image(ROCKET, {"r": (230, 70, 60), "s": (210, 215, 225),
                                                          "w": (110, 210, 235), "f": (200, 60, 60),
                                                          "g": (120, 125, 135)}),
                         "ground", LAND, ["raket", "rocket"]),
    "snögubbe": _prop_entry(lambda r: _sprite_image(SNOWMAN, {"w": (245, 250, 255), "k": (40, 40, 45),
                                                              "o": (240, 140, 40), "r": (220, 60, 70)}),
                            "ground", {"snow"}, ["snögubbe", "snowman"]),
    "fisk": _prop_entry(lambda r: r.choice(_FISH_COLORS), "water-swim", {"underwater"},
                        ["fisk", "fiskar", "fish"]),
    "krabba": _prop_entry(lambda r: _sprite_image(CRAB, {"k": (40, 40, 45), "r": (225, 70, 60)}),
                          "ground", {"beach", "underwater"}, ["krabba", "crab"]),
    "snäcka": _prop_entry(lambda r: _sprite_image(SHELL, {"p": (255, 175, 195), "w": (255, 235, 240)}),
                          "ground", {"beach", "underwater"}, ["snäcka", "sjösnäcka", "seashell", "shell"]),
    "tårta": _prop_entry(lambda r: _sprite_image(CAKE, {"y": (255, 220, 90), "c": (255, 120, 120),
                                                        "f": (255, 245, 225), "p": (240, 140, 175),
                                                        "w": (255, 255, 255)}),
                         "ground", LAND, ["tårta", "tårtor", "cake", "födelsedag"]),
    "glass": _prop_entry(lambda r: _sprite_image(ICECREAM, {"p": r.choice([(255, 170, 200), (170, 230, 180), (255, 220, 160)]),
                                                            "w": (255, 255, 255), "o": (224, 184, 130)}),
                         "ground", LAND, ["glass", "glassar", "ice cream"]),
    "ballong": _prop_entry(lambda r: r.choice(_BALLOON_COLORS), "sky-float",
                           LAND, ["ballong", "ballonger", "balloon"]),
    "stjärna": _prop_entry(lambda r: _sprite_image(GSTAR, {"y": (255, 225, 90)}),
                           "ground", LAND, ["stjärna", "star"]),
    "ädelsten": _prop_entry(lambda r: _sprite_image(GEM, {"c": (60, 220, 235), "w": (255, 255, 255)}),
                            "ground", LAND, ["ädelsten", "diamant", "kristall", "gem", "diamond", "crystal"]),
    "kista": _prop_entry(lambda r: _sprite_image(CHEST, {"K": (130, 80, 35), "G": (255, 205, 80),
                                                         "Y": (255, 225, 120)}),
                         "ground", LAND, ["skattkista", "kista", "treasure chest"]),
    "bär": _prop_entry(lambda r: _sprite_image(BUSH, {"g": (50, 130, 60), "r": (230, 60, 70)}),
                       "ground", LAND, ["bär", "berries", "berry"]),
    "groda": _prop_entry(lambda r: _sprite_image(FROG, {"w": (255, 255, 255), "k": (40, 40, 45),
                                                        "g": (90, 190, 80)}),
                         "hop", LAND, ["groda", "padda", "frog"]),
    "blomma": _prop_entry(lambda r: _sprite_image(BIGFLOWER, {"p": r.choice([(255, 130, 170), (255, 200, 90), (190, 150, 255)]),
                                                              "y": (255, 230, 110), "g": (70, 150, 70)}),
                          "ground", LAND, ["blomma", "blommor", "flower"]),
    "regnbåge": _prop_entry(lambda r: _rainbow_img(), "sky-static",
                            {"forest", "beach", "snow", "candy"}, ["regnbåge", "rainbow"]),
    "fackla": _prop_entry(lambda r: _sprite_image(TORCH, {"o": (255, 150, 40), "y": (255, 228, 120),
                                                          "k": (110, 72, 40)}),
                          "ground", LAND, ["torch", "fackla"]),
    "portal": _prop_entry(lambda r: _sprite_image(PORTAL, {"p": (150, 80, 220), "v": (95, 45, 160),
                                                           "c": (80, 220, 235), "g": (140, 240, 170),
                                                           "k": (18, 14, 40)}),
                          "ground", LAND, ["portal", "gateway", "wormhole"]),
    "ufo": _prop_entry(lambda r: _sprite_image(UFO, {"d": (140, 230, 255), "s": (200, 205, 215),
                                                     "w": (255, 225, 90)}),
                       "ground", {"space", "night"}, ["ufo", "flying saucer", "mothership"]),
    "bumling": _prop_entry(lambda r: _sprite_image(BOULDER, {"g": (150, 152, 160), "c": (105, 106, 115)}),
                           "ground", LAND, ["boulder", "bumling", "big rock", "rocks"]),
    "svärd": _prop_entry(lambda r: _sprite_image(SWORD, {"y": (255, 205, 80), "g": (198, 200, 208),
                                                         "k": (120, 122, 135)}),
                         "ground", LAND, ["svärd", "sword", "blade"]),
}

NAME_ALIASES = {"mushroom": "svamp", "house": "hus", "rocket": "raket", "snowman": "snögubbe",
                "fish": "fisk", "crab": "krabba", "shell": "snäcka", "cake": "tårta",
                "icecream": "glass", "ice cream": "glass", "balloon": "ballong", "star": "stjärna",
                "gem": "ädelsten", "diamond": "ädelsten", "crystal": "ädelsten",
                "chest": "kista", "treasure": "kista", "berries": "bär", "frog": "groda",
                "flower": "blomma", "rainbow": "regnbåge",
                "torch": "fackla", "portal": "portal", "wormhole": "portal",
                "ufo": "ufo", "boulder": "bumling", "rock": "bumling", "sword": "svärd"}


def normalize_prop_names(props):
    if not props:
        return []
    if isinstance(props, str):
        props = [p.strip() for p in props.split(",")]
    out = []
    for p in props:
        p = NAME_ALIASES.get(str(p).strip().lower(), str(p).strip().lower())
        if p in PROPS and p not in out:
            out.append(p)
    return out


def props_for_text(text, setting):
    low = " " + (text or "").lower() + " "
    ground, other = [], []
    for name, spec in PROPS.items():
        if setting not in spec["settings"]:
            continue
        if any(k in low for k in spec["kw"]):
            (ground if spec["zone"] == "ground" else other).append(name)
    return ground[:3] + other[:3]


# ---------------------------------------------------------------------------
# Världar
# ---------------------------------------------------------------------------
SCHEMES = {
    "forest": {
        "sky": ((122, 196, 232), (214, 240, 214)), "celest": ("sun", (262, 30, 13)),
        "hills": (((150, 205, 130), 128, 16, 120), ((104, 168, 92), 142, 10, 84)),
        "tree": "pine", "tree_cols": ((30, 92, 54), (56, 140, 84)), "rays": True,
        "ground": ((150, 110, 66), (96, 158, 80)),
        "dots": [(90, 150, 74), (120, 180, 92), (200, 150, 90)],
        "flowers": True, "particles": "leaf", "clouds": 3, "bird": True,
    },
    "night": {
        "sky": ((18, 26, 58), (52, 60, 104)), "celest": ("moon", (250, 30, 12)),
        "hills": (((24, 50, 44), 128, 15, 120), ((16, 36, 34), 142, 10, 84)),
        "tree": "pine", "tree_cols": ((10, 28, 26), (18, 40, 34)),
        "ground": ((40, 62, 54), (30, 48, 44)), "dots": [(34, 54, 48), (48, 74, 62)],
        "particles": "firefly", "clouds": 1, "stars": 46,
    },
    "beach": {
        "sky": ((110, 196, 240), (255, 244, 205)), "celest": ("sun", (262, 30, 13)),
        "hills": None, "sea": True, "tree": "palm", "tree_cols": ((36, 130, 70), (52, 160, 86)),
        "ground": ((236, 214, 160), (226, 204, 146)), "dots": [(206, 178, 118), (244, 226, 178)],
        "particles": None, "clouds": 3, "bird": True,
    },
    "space": {
        "sky": ((8, 8, 30), (40, 22, 64)), "celest": ("planet", (60, 36, 22)),
        "hills": None, "tree": "crystal", "tree_cols": ((96, 54, 160), (150, 96, 220)),
        "ground": ((96, 90, 112), (76, 70, 92)), "dots": [(70, 64, 86), (110, 104, 128)],
        "particles": "mote", "clouds": 0, "stars": 78,
    },
    "snow": {
        "sky": ((176, 210, 236), (244, 248, 252)), "celest": ("sun", (262, 30, 12)),
        "hills": (((206, 224, 240), 130, 12, 110), ((170, 198, 222), 144, 9, 80)),
        "tree": "pine", "tree_cols": ((52, 102, 72), (88, 150, 104)), "snowy": True,
        "ground": ((246, 250, 254), (224, 236, 246)), "dots": [(198, 216, 234), (214, 228, 242)],
        "particles": "snow", "clouds": 2,
    },
    "underwater": {
        "sky": ((14, 78, 148), (66, 158, 212)), "celest": None,
        "hills": None, "rays": True, "weeds": True,
        "tree": "coral", "coral_cols": [(255, 120, 110), (255, 170, 80), (200, 110, 200)],
        "tree_cols": ((255, 120, 110), (255, 170, 80)),
        "ground": ((228, 206, 158), (214, 190, 140)), "dots": [(240, 225, 190), (198, 178, 138)],
        "particles": "bubbla", "clouds": 0,
    },
    "city": {     # KNOX HOLLOW – neon-skymning, gatljus och fönster som aldrig släcks
        "sky": ((30, 24, 66), (232, 116, 80)), "celest": ("moon", (62, 44, 17)),
        "hills": (((44, 34, 92), 84, 20, 130), ((28, 22, 64), 102, 14, 96)),
        "tree": "building", "tree_cols": ((34, 30, 74), (54, 44, 110)),
        "ground": ((66, 60, 78), (44, 40, 54)),
        "dots": [(94, 86, 110), (74, 78, 102), (252, 182, 96)],
        "particles": "mote", "clouds": 1, "stars": 30,
    },
    "candy": {
        "sky": ((255, 186, 214), (255, 240, 247)), "celest": ("sun", (262, 30, 13)),
        "hills": (((255, 196, 224), 130, 14, 110), ((255, 164, 206), 144, 10, 80)),
        "tree": "lollipop", "rays": True,
        "loli_cols": [(255, 130, 170), (255, 160, 90), (170, 230, 140), (150, 200, 255)],
        "ground": ((255, 240, 226), (255, 214, 168)),
        "dots": [(255, 120, 170), (140, 220, 250), (255, 220, 90), (170, 240, 140)],
        "particles": "glitter", "clouds": 3,
    },
}


# Scen-ambient: färgad ljusinbäddning så karaktärer SITTER I världen (v9)
AMBIENTS = {
    "forest": (150, 200, 150), "night": (60, 75, 140), "beach": (255, 236, 190),
    "space": (128, 92, 190), "snow": (205, 225, 244), "underwater": (52, 130, 185),
    "candy": (255, 205, 225), "city": (186, 136, 196),
}

# ---------------------------------------------------------------------------
# Miljöritare
# ---------------------------------------------------------------------------
def _gradient(top, bottom, w, h):
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        f = y / max(1, h - 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3))
    return img.resize((w, h))


def _cloud_img(rng):
    w = rng.randint(36, 66)
    h = max(12, w * 2 // 5)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(4, 6)):
        bw = rng.randint(w // 4, w // 2)
        bh = max(4, bw * 2 // 5)
        bx = rng.randint(2, max(3, w - bw - 2))
        by = rng.randint(h // 4, max(h // 4 + 1, h - bh - 2))
        d.ellipse([bx, by, bx + bw, by + bh], fill=(255, 255, 255, 210))
    d.rectangle([4, h - 6, w - 4, h - 1], fill=(255, 255, 255, 185))
    return img


def _tower(d, x, base_y, rng, dark, light):
    """Neon-Stad: tornhus med tända fönster + antenn med rött blinkljus."""
    w = rng.randint(16, 30)
    hgt = rng.randint(38, 106)
    x0 = x - w // 2
    mid = tuple(int((a + b) / 2) for a, b in zip(dark, light))
    body = rng.choice([dark, light, mid])
    d.rectangle([x0, base_y - hgt, x0 + w, base_y + 3], fill=body + (255,))
    neon = [(255, 205, 120), (120, 230, 255), (255, 120, 200), (140, 255, 170)]
    dk = tuple(int(v * 0.62) for v in body)
    for wy in range(base_y - hgt + 4, base_y - 5, 7):
        for wx in range(x0 + 3, x0 + w - 4, 6):
            if rng.random() < 0.26:
                d.rectangle([wx, wy, wx + 2, wy + 3], fill=rng.choice(neon) + (255,))
            else:
                d.rectangle([wx, wy, wx + 2, wy + 3], fill=dk + (255,))
    if rng.random() < 0.45:
        ax = x0 + rng.randint(2, max(3, w - 3))
        ah = rng.randint(6, 14)
        d.line([(ax, base_y - hgt), (ax, base_y - hgt - ah)], fill=body + (255,))
        d.point((ax, base_y - hgt - ah), fill=(255, 80, 90, 255))


def _pine(d, x, base, s, dark, light, snowy=False):
    x, base = int(x), int(base)
    d.rectangle([x - s, base - 5 * s, x + max(1, s) - 1, base], fill=(104, 70, 42))
    yy = base - 4 * s
    for i, (hw, hh) in enumerate(((13, 10), (10, 9), (7, 8))):
        hw, hh = int(hw * s), int(hh * s)
        top = snowy and i == 2
        c = (240, 246, 252) if top else light
        cd = (196, 210, 228) if top else dark
        d.polygon([(x - hw, yy), (x, yy - hh), (x + hw, yy)], fill=c)
        d.polygon([(x - hw, yy), (x, yy - hh), (x, yy)], fill=cd)
        yy -= int(6 * s)


def _palm(d, x, base, s, dark, light):
    x, base = int(x), int(base)
    seg = 8
    xx = x
    for i in range(seg):
        yy = base - 6 * i * s
        xx = x + int(i * i * 0.30 * s)
        d.rectangle([xx - 2 * s, yy - 6 * s, xx + s, yy - 1], fill=(150, 105, 60))
    tx, ty = xx, base - 6 * seg * s
    d.ellipse([tx - 3 * s, ty, tx, ty + 3 * s], fill=(110, 72, 40))
    d.ellipse([tx + s, ty, tx + 4 * s, ty + 3 * s], fill=(110, 72, 40))
    for ang in (200, 245, 295, 340, 160, 20):
        r = math.radians(ang)
        mx = tx + int(math.cos(r) * 16 * s)
        my = ty + int(math.sin(r) * 7 * s)
        ex = tx + int(math.cos(r) * 27 * s)
        ey = ty + int(math.sin(r) * 12 * s) + 6 * s
        d.line([(tx, ty), (mx, my), (ex, ey)], fill=light, width=int(max(2, 3 * s)))
        d.line([(tx, ty + s), (mx, my + s), (ex, ey + s)], fill=dark, width=int(max(1, int(s))))


def _crystal(d, x, base, s, dark, light):
    hgt = int(20 * s) + 6
    w2 = max(2, int(hgt * 0.32))
    d.polygon([(x - w2, base), (x, base - hgt), (x + w2, base)], fill=light)
    d.polygon([(x, base), (x, base - hgt), (x + w2, base)], fill=dark)
    d.point((x, base - hgt), fill=(255, 255, 255))
    d.point((x - w2 - 2, base - 3), fill=dark)
    d.point((x + w2 + 2, base - 5), fill=light)


def _lollipop(d, x, base, s, crown):
    x, base = int(x), int(base)
    hgt = int(20 * s)
    for i, yy in enumerate(range(base - hgt, base, 3)):
        col = (255, 255, 255) if i % 2 == 0 else (255, 150, 190)
        d.rectangle([x - 1, yy, x + 1, min(yy + 2, base)], fill=col)
    r = int(9 * s)
    cy = base - hgt - r + 3
    d.ellipse([x - r, cy - r, x + r, cy + r], fill=crown)
    d.ellipse([x - r + 3, cy - r + 3, x + r - 3, cy + r - 3], outline=_lighter(crown), width=2)
    d.ellipse([x - 2, cy - 2, x + 2, cy + 2], fill=(255, 255, 255))


def _coral(d, x, base, col, hgt=14):
    x, base = int(x), int(base)
    d.line([(x, base), (x, base - hgt)], fill=col, width=2)
    for ang, le in ((-38, 8), (32, 9), (-14, 6), (58, 6)):
        r = math.radians(ang - 90)
        x2 = x + int(math.cos(r) * le)
        y2 = base - hgt + int(math.sin(r) * le)
        d.line([(x, base - hgt), (x2, y2)], fill=col, width=2)
        d.point((x2, y2), fill=_lighter(col))
    d.ellipse([x - 2, base - hgt - 2, x + 2, base - hgt + 1], fill=_lighter(col))


# ---------------------------------------------------------------------------
# Scenen
# ---------------------------------------------------------------------------
class Scene:
    """En levande pixelscen. actors = [(Character, action|None), ...] (max 3)."""

    def __init__(self, setting="forest", seed=0, actors=None, text=None,
                 props=None, reaction=None, mystery=None, cam=None, dur=10.0):
        self.setting = setting if setting in SCHEMES else "forest"
        self.rng = random.Random(seed)
        self.pal = SCHEMES[self.setting]
        self.cam = cam or []
        self.dur = dur
        if not actors:
            actors = [(Character("leo"), None)]
        self.actors = []
        for a in actors[:4]:
            ch, spec = (a if isinstance(a, tuple) else (a, None))
            if isinstance(spec, list):            # v7: beatsegment
                segs = spec
            else:
                act = spec if spec in ACTIONS else None
                segs = [{"t0": 0.0, "t1": None, "act": act}]
            self.actors.append((ch, segs))
        self.reaction = reaction if reaction in REACTIONS else None
        self.mystery_wanted = mystery

        names = normalize_prop_names(props)
        if not names and text:
            names = props_for_text(text, self.setting)
        names = [n for n in names if self.setting in PROPS[n]["settings"]]

        self._build_sky()
        self._build_hills()
        self._build_trees()
        self._build_ground()
        self._bake_props(names)
        self._build_clouds()
        self._build_particles()
        self._setup_animals(names)
        self._build_reaction()

        # uttrycks-tillbehör (musiknoter, ilskemärke, svett, stjärna, !!)
        self.note_img = _sprite_image(_NOTE, {"#": (110, 220, 255)})
        self.note_img = self.note_img.resize((self.note_img.width * 2, self.note_img.height * 2), NEAREST)
        self.anger_img = _sprite_image(_ANGERX, {"#": (255, 70, 90)})
        self.anger_img = self.anger_img.resize((self.anger_img.width * 2, self.anger_img.height * 2), NEAREST)
        self.sweat_img = _sprite_image(_SWEAT, {"c": (150, 205, 255)})
        self.sweat_img = self.sweat_img.resize((self.sweat_img.width * 2, self.sweat_img.height * 2), NEAREST)
        self.star_img = _sprite_image(_STAR, {"#": (255, 225, 90)})
        self.star_img = self.star_img.resize((self.star_img.width * 2, self.star_img.height * 2), NEAREST)
        self.bang_bubble = _bubble(_BANG, (232, 60, 60))
        self._build_mystery()
        self._build_foreground()
        for ch, _segs in self.actors:
            scene_tint(ch, AMBIENTS.get(self.setting, (160, 160, 170)))

        self.bird = bool(self.pal.get("bird")) and self.rng.random() < 0.85
        self.bird_y = self.rng.randint(30, 62)
        self.bird_speed = self.rng.uniform(20, 30)
        self.bird_off = self.rng.uniform(0, 200)
        self.bird_imgs = (_sprite_image(FAGEL_A, {"k": (70, 66, 84)}),
                          _sprite_image(FAGEL_B, {"k": (70, 66, 84)}))
        self.pow = _sprite_image(_POW, {"y": (255, 222, 80)})
        self.pow = self.pow.resize((self.pow.width * 2, self.pow.height * 2), NEAREST)

    # -- uppbyggnad ------------------------------------------------------
    def _build_sky(self):
        top, bot = self.pal["sky"]
        self.sky = _gradient(top, bot, W, H)
        n = self.pal.get("stars", 0)
        self.stars = [(self.rng.randrange(W), self.rng.randrange(GROUND_Y - 46),
                       self.rng.uniform(0, 6.28), self.rng.uniform(1.5, 4.0))
                      for _ in range(n)]
        self.rays = None
        if self.pal.get("rays"):
            r = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(r)
            for x0 in (26, 128, 226):
                d.polygon([(x0, 0), (x0 + 24, 0), (x0 + 66, GROUND_Y), (x0 + 32, GROUND_Y)],
                          fill=(255, 255, 255, 15))
            self.rays = r

    def _build_hills(self):
        spec = self.pal.get("hills")
        if not spec:
            self.hills = None
            return
        img = Image.new("RGBA", (2 * W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for color, base, amp, wl in spec:
            ph = self.rng.uniform(0, 6.28)
            pts = [(x, base + amp * math.sin(ph + x / wl)) for x in range(0, 2 * W + 8, 8)]
            d.polygon(pts + [(2 * W, H), (0, H)], fill=color + (255,))
        for _ in range(26):
            x = self.rng.randrange(2 * W)
            c, b, a, wl = spec[-1]
            y = b + a * math.sin(x / wl) + 2
            dark = self.pal.get("tree_cols", ((30, 60, 40),))[0]
            td = tuple(int(v * 0.8) for v in dark)
            d.polygon([(x - 4, y), (x, y - 9), (x + 4, y)], fill=td + (255,))
        self.hills = img

    def _build_trees(self):
        img = Image.new("RGBA", (2 * W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        kind = self.pal.get("tree")
        if not kind:
            self.trees = None
            return
        dark, light = self.pal.get("tree_cols", ((40, 80, 50), (60, 120, 70)))
        snowy = bool(self.pal.get("snowy"))
        spacing = {"palm": self.rng.randint(120, 200), "coral": self.rng.randint(70, 110),
                   "lollipop": self.rng.randint(56, 84),
                   "building": self.rng.randint(30, 50)}.get(kind, self.rng.randint(44, 70))
        x = self.rng.randint(0, 30)
        while x < W + 40:
            for xx in (x, x + W):
                if kind == "pine":
                    _pine(d, xx, GROUND_Y + 2, self.rng.uniform(0.9, 1.4), dark, light, snowy)
                elif kind == "palm":
                    _palm(d, xx, GROUND_Y + 3, self.rng.uniform(0.9, 1.2), dark, light)
                elif kind == "crystal":
                    _crystal(d, xx, GROUND_Y + 2, self.rng.uniform(0.7, 1.2), dark, light)
                elif kind == "coral":
                    _coral(d, xx, GROUND_Y + 4, self.rng.choice(self.pal.get(
                        "coral_cols", [(255, 120, 110)])), hgt=self.rng.randint(10, 20))
                elif kind == "lollipop":
                    _lollipop(d, xx, GROUND_Y + 2, self.rng.uniform(0.9, 1.3),
                              self.rng.choice(self.pal.get("loli_cols", [(255, 130, 170)])))
                elif kind == "building":
                    _tower(d, xx, GROUND_Y + 1, self.rng, dark, light)
            x += spacing + self.rng.randint(-14, 22)
        self.trees = img

    def _build_ground(self):
        ground, top = self.pal["ground"]
        img = Image.new("RGBA", (2 * W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, GROUND_Y, 2 * W, H], fill=ground + (255,))
        d.rectangle([0, GROUND_Y, 2 * W, GROUND_Y + 3], fill=top + (255,))
        for _ in range(110):
            x = self.rng.randrange(2 * W)
            y = self.rng.randrange(GROUND_Y + 6, H)
            d.point((x, y), fill=self.rng.choice(self.pal["dots"]) + (255,))
        if self.pal.get("flowers"):
            for _ in range(14):
                x = self.rng.randrange(2 * W)
                y = self.rng.randrange(GROUND_Y + 8, H - 4)
                d.line([(x, y), (x, y - 4)], fill=(60, 130, 60, 255))
                d.point((x, y - 5), fill=self.rng.choice(
                    [(255, 130, 150, 255), (255, 230, 120, 255), (255, 255, 255, 255),
                     (200, 150, 255, 255)]))
        if self.setting == "space":
            for _ in range(7):
                x = self.rng.randrange(2 * W)
                y = self.rng.randrange(GROUND_Y + 8, H - 4)
                r = self.rng.randint(3, 8)
                d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=self.pal["dots"][0] + (255,))
        self.ground = img

    def _bake_props(self, names):
        for name in names:
            spec = PROPS[name]
            if spec["zone"] == "ground":
                img = spec["img"](self.rng)
                for _ in range(2 if name in ("svamp", "blomma", "snäcka") else 1):
                    x = self.rng.randint(6, 2 * W - img.width - 6)
                    self.ground.paste(img, (x, GROUND_Y - img.height + 2), img)
            elif spec["zone"] == "sky-static" and self.hills is not None:
                img = spec["img"](self.rng)
                x = self.rng.randint(W // 2, W - img.width // 2)
                self.hills.paste(img, (x, 16), img)

    def _setup_animals(self, names):
        self.swimmers, self.hoppers, self.floaters = [], [], []
        n_fish = (3 if self.setting == "underwater" else 0) + names.count("fisk") * 2
        for _ in range(min(5, n_fish)):
            col = self.rng.choice(_FISH_COLORS)
            cols = {"o": col, "t": tuple(int(v * 0.75) for v in col), "w": (255, 255, 255)}
            self.swimmers.append({"imgs": (_sprite_image(FISH_A, cols), _sprite_image(FISH_B, cols)),
                                  "y": self.rng.uniform(46, GROUND_Y - 26),
                                  "speed": self.rng.uniform(18, 34),
                                  "off": self.rng.uniform(0, 400),
                                  "ph": self.rng.uniform(0, 6.28)})
        for _ in range(names.count("groda")):
            self.hoppers.append({"img": PROPS["groda"]["img"](self.rng),
                                 "off": self.rng.uniform(0, 300),
                                 "ph": self.rng.uniform(0, 6.28)})
        for _ in range(min(2, names.count("ballong"))):
            col = PROPS["ballong"]["img"](self.rng)
            self.floaters.append({"img": _sprite_image(
                BALLOON, {"r": col, "w": (255, 255, 255), "s": (120, 120, 130)}),
                "y": self.rng.uniform(26, 62), "speed": self.rng.uniform(4, 8),
                "off": self.rng.uniform(0, 300), "ph": self.rng.uniform(0, 6.28)})
        self.weeds = []
        if self.pal.get("weeds"):
            for _ in range(7):
                self.weeds.append({"x": self.rng.randint(4, W - 4),
                                   "h": self.rng.randint(14, 34),
                                   "ph": self.rng.uniform(0, 6.28),
                                   "col": self.rng.choice([(28, 140, 90), (40, 172, 110), (22, 110, 76)])})

    def _build_clouds(self):
        self.clouds = []
        for _ in range(self.pal.get("clouds", 0)):
            ci = _cloud_img(self.rng)
            self.clouds.append([ci, self.rng.uniform(0, W + 160),
                                self.rng.randint(8, 62), self.rng.uniform(2.0, 5.0)])

    def _build_particles(self):
        kind = self.pal.get("particles")
        count = {"leaf": 12, "snow": 32, "firefly": 9, "mote": 16,
                 "bubbla": 18, "glitter": 22}.get(kind or "", 0)
        self.parts = []
        for _ in range(count):
            self.parts.append({"x": self.rng.uniform(0, W), "y": self.rng.uniform(0, GROUND_Y),
                               "v": self.rng.uniform(6, 18), "sway": self.rng.uniform(3, 10),
                               "ph": self.rng.uniform(0, 6.28), "sp": self.rng.uniform(1.5, 4),
                               "r": self.rng.choice([1, 1, 2])})
        self.part_kind = kind

    def _build_reaction(self):
        self.bubble_img = None
        if self.reaction:
            rows, col = REACTIONS[self.reaction]
            self.bubble_img = _bubble(rows, col)
        self.zz = _sprite_image(_ZED, {"#": (205, 225, 255)})
        self.zz = self.zz.resize((self.zz.width * 2, self.zz.height * 2), NEAREST)

    def _build_mystery(self):
        """'The Watcher' – seriens löpande mysterium. Liten figur, långt bort."""
        self.watcher = None
        wanted = bool(self.mystery_wanted) if self.mystery_wanted is not None \
            else self.rng.random() < 0.12
        if wanted:
            wimg = _sprite_image(WATCHER, {"k": (16, 12, 28)})
            self.watcher = {"img": wimg, "x": self.rng.randint(240, W - 20),
                            "ph": self.rng.uniform(0, 6.28)}

    def _build_foreground(self):
        """FÖRGRUND: mörka nära silhuetter passerar FRAMFÖR aktörerna (djup!)."""
        img = Image.new("RGBA", (2 * W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        g1, g2 = self.pal["ground"]
        dark = tuple(max(0, int(v * 0.5)) for v in g2) + (225,)
        dark2 = tuple(max(0, int(v * 0.42)) for v in g1) + (235,)
        for _ in range(self.rng.randint(26, 38)):                    # grässtrån
            x = self.rng.randrange(2 * W)
            hgt = self.rng.randint(12, 34)
            sway = self.rng.randint(-4, 4)
            d.polygon([(x, H + 2), (x + sway, H - hgt), (x + 3, H + 2)], fill=dark)
        for _ in range(self.rng.randint(4, 7)):                      # nära buskage stenar
            x = self.rng.randrange(2 * W)
            r = self.rng.randint(7, 13)
            d.ellipse([x - r, H - r // 2, x + r, H + r // 2], fill=dark2)
        if self.setting == "city":                                  # gatubelysning
            lx = self.rng.randint(8, 60)
            while lx < 2 * W - 6:
                top = H - self.rng.randint(62, 86)
                d.rectangle([lx, top, lx + 2, H + 2], fill=dark2)
                d.rectangle([lx - 4, top, lx + 6, top + 3], fill=dark2)
                d.point((lx + 2, top + 5), fill=(255, 224, 150, 255))
                lx += self.rng.randint(74, 124)
        if self.setting in ("forest", "night", "snow"):              # stam-kant ibland
            if self.rng.random() < 0.5:
                x = self.rng.choice([self.rng.randint(2, 26), self.rng.randint(2 * W - 30, 2 * W - 6)])
                w_tr = self.rng.randint(14, 22)
                d.rectangle([x, H - self.rng.randint(60, 110), x + w_tr, H + 2], fill=dark2)
        self.fg = img

    def _draw_foreground(self, img, t):
        self._paste_wrapped(img, self.fg, t * 27.0)

    def _draw_watcher(self, img, t):
        if not self.watcher:
            return
        w = self.watcher
        y = 120 - w["img"].height                     # horisonten, långt bort
        img.paste(w["img"], (w["x"], y), w["img"])
        glow = 0.5 + 0.5 * math.sin(t * 0.8 + w["ph"])
        if glow > 0.3:                                # ögonen blinkar svagt rött
            v = int(110 + 140 * glow)
            d = ImageDraw.Draw(img)
            d.point((w["x"] + 2, y + 3), fill=(v, 36, 46))
            d.point((w["x"] + 4, y + 3), fill=(v, 36, 46))

    # -- per frame ---------------------------------------------------------
    def _paste_wrapped(self, base, layer, dx):
        ox = int(dx) % W
        crop = layer.crop((ox, 0, ox + W, H))
        base.paste(crop, (0, 0), crop)

    def _draw_stars(self, img, t):
        px = img.load()
        for x, y, ph, sp in self.stars:
            b = 0.5 + 0.5 * math.sin(t * sp + ph)
            if b < 0.12:
                continue
            v = int(90 + 165 * b)
            px[x, y] = (v, v, min(255, v + 25))

    def _draw_celestial(self, img, t):
        spec = self.pal.get("celest")
        if not spec:
            return
        kind, (x, y, r) = spec
        bob = int(math.sin(t * 0.5) * 1.5)
        d = ImageDraw.Draw(img)
        if kind == "sun":
            d.ellipse([x - r - 5, y - r - 5 + bob, x + r + 5, y + r + 5 + bob], fill=(255, 240, 150))
            d.ellipse([x - r, y - r + bob, x + r, y + r + bob], fill=(255, 206, 80))
        elif kind == "moon":
            d.ellipse([x - r, y - r + bob, x + r, y + r + bob], fill=(238, 234, 214))
            for cx, cy, cr in ((x - 4, y - 3, 3), (x + 3, y + 2, 2), (x - 1, y + 5, 2)):
                d.ellipse([cx - cr, cy - cr + bob, cx + cr, cy + cr + bob], fill=(206, 200, 178))
        elif kind == "planet":
            d.ellipse([x - r, y - r + bob, x + r, y + r + bob], fill=(146, 88, 200))
            d.rectangle([x - r, y - 4 + bob, x + r, y + 2 + bob], fill=(120, 66, 170))
            d.ellipse([x - r - 14, y - r // 2 + bob, x + r + 14, y + r // 2 + bob],
                      outline=(210, 160, 240))

    def _draw_clouds(self, img, t):
        for ci, x0, y, spd in self.clouds:
            w = ci.width
            x = int((x0 - t * spd) % (W + w + 80)) - w - 40
            img.paste(ci, (x, y), ci)

    def _draw_sea(self, img, t):
        d = ImageDraw.Draw(img)
        d.rectangle([0, 100, W, GROUND_Y - 2], fill=(62, 150, 205))
        d.line([0, 100, W, 100], fill=(222, 246, 255))
        for yb, ph in ((116, 0.0), (130, 2.1)):
            pts = [(x, yb + 2 * math.sin(x / 14.0 + t * 2.2 + ph)) for x in range(0, W + 1, 4)]
            d.line(pts, fill=(168, 218, 244))

    def _draw_weeds(self, img, t):
        d = ImageDraw.Draw(img)
        for wd in self.weeds:
            pts = []
            for yy in range(0, wd["h"], 4):
                xo = 2.2 * math.sin(t * 1.3 + wd["ph"] + yy / 7.0)
                pts.append((wd["x"] + xo, GROUND_Y + 2 - yy))
            if len(pts) > 1:
                d.line(pts, fill=wd["col"], width=2)

    def _draw_bird(self, img, t):
        im = self.bird_imgs[int(t * 6) % 2]
        span = W + 60
        x = int(span - ((t * self.bird_speed + self.bird_off) % span)) - 30
        y = int(self.bird_y + 4 * math.sin(t * 1.3))
        img.paste(im, (x, y), im)

    def _draw_swimmers(self, img, t):
        for f in self.swimmers:
            im = f["imgs"][int(t * 6) % 2]
            span = W + im.width + 40
            x = int(((t * f["speed"] + f["off"]) % span)) - im.width - 20
            y = int(f["y"] + 4 * math.sin(t * 1.6 + f["ph"]))
            img.paste(im, (x, y), im)

    def _draw_hoppers(self, img, t):
        for hp in self.hoppers:
            im = hp["img"]
            span = W + im.width + 60
            x = int((hp["off"] - t * 14.0) % span) - 30
            y = GROUND_Y - im.height + 2 - abs(int(6 * math.sin(t * 5.2 + hp["ph"])))
            img.paste(im, (x, y), im)

    def _draw_floaters(self, img, t):
        for fl in self.floaters:
            im = fl["img"]
            span = W + im.width + 80
            x = int((fl["off"] + t * fl["speed"]) % span) - 40
            y = int(fl["y"] + 4 * math.sin(t * 0.9 + fl["ph"]))
            img.paste(im, (x, y), im)

    # -- v7: blocking, fysik & regi ------------------------------------------
    @staticmethod
    def _ease(x):
        x = max(0.0, min(1.0, x))
        return x * x * (3 - 2 * x)

    def _seg_for(self, segs, t):
        for s in segs:
            t1 = s.get("t1")
            if s["t0"] <= t < (self.dur + 1 if t1 is None else t1):
                return s
        return segs[-1]

    def _ghost(self, spr, f):
        # Genomskinlig efterbild av en sprite (anime-afterimage)
        g = spr.copy()
        a = g.getchannel("A").point(lambda v: int(v * f))
        g.putalpha(a)
        return g

    def _move_pos(self, move, i, p, ch):
        """Ger (x, riktning, fortfarande-på-väg?) under ett move-segment."""
        base_x = CHAR_X + i * ACTOR_GAP
        if move == "enter_l":
            e_ = self._ease(p)
            return int((-ch.w - 12) + (base_x + ch.w + 12) * e_), 1, p < 0.985
        if move == "enter_r":
            e_ = self._ease(p)
            return int((W + 12) - (W + 12 - base_x) * e_), -1, p < 0.985
        return base_x, 0, False

    def _draw_actors(self, img, t):
        d = ImageDraw.Draw(img, "RGBA")
        for i, (ch, segs) in enumerate(self.actors):
            seg = self._seg_for(segs, t)
            act = seg.get("act") if seg.get("act") in ACTIONS else None
            move = seg.get("move")
            t1 = seg.get("t1")
            span = max(0.05, (min(self.dur, t1) if t1 is not None else self.dur) - seg["t0"])
            p = min(1.0, max(0.0, (t - seg["t0"]) / span))
            tt = (t - seg["t0"]) + i * 0.31

            x, dirn, en_route = self._move_pos(move, i, p, ch)
            if not dirn:
                dirn = seg.get("face") or (-1 if i >= 1 else 1)
            if en_route and act in (None, "walk", "run"):
                act = "run"

            d.ellipse([x - 6, GROUND_Y - 2, x + ch.w + 6, GROUND_Y + 5], fill=(0, 0, 0, 70))
            speed = 12 if act == "run" else 7
            fr = "A" if int(tt * speed) % 2 == 0 else "B"
            if act == "sleep":
                fr = "A"
            blink = act != "sleep" and (tt % 3.7) < 0.12
            spr = ch.frames[fr + ("_b" if blink else "") + ("f" if dirn < 0 else "")]
            feet = GROUND_Y + 2 + i
            xoff = 0
            tilt = 0.0
            squash = 1.0
            lunge = 0

            if act == "run":
                tilt = -7.0 * dirn
                feet -= abs(int(2 * math.sin(tt * 12)))
            elif act == "jump":                 # v7-fysik: anticipation -> båge -> squash
                ph = (tt % 1.15) / 1.15
                if ph < 0.26:
                    squash = 1.0 - 0.18 * math.sin(math.pi * ph / 0.26)
                elif ph < 0.70:
                    q = (ph - 0.26) / 0.44
                    feet -= int(60 * math.sin(math.pi * q))
                    tilt = -6.0 * dirn * math.sin(math.pi * q)
                else:
                    q = (ph - 0.70) / 0.30
                    squash = 1.0 - 0.15 * math.sin(math.pi * min(1.0, q))
                    if q < 0.6:
                        d.ellipse([x - 4, GROUND_Y + 1, x + ch.w + 4, GROUND_Y + 5],
                                  fill=(0, 0, 0, int(50 * (1 - q))))
            elif act == "dance":
                feet -= abs(int(3 * math.sin(tt * 9)))
                xoff = int(3 * math.sin(tt * 4.5))
                tilt = -10 * dirn * math.sin(tt * 4.5)
            elif act == "spin":
                tilt = -(tt % 1.0) * 360.0
            elif act == "wave":
                tilt = 12 * dirn * math.sin(tt * 8)
                feet -= abs(int(2 * math.sin(tt * 8)))
            elif act == "hit":                  # v7: drag upp först (wind-up)
                c = (tt % 0.9) / 0.9
                if c < 0.10:
                    xoff -= int(5 * (c / 0.10)) * dirn
                lunge = int(9 * max(0.0, 1.0 - abs(c - 0.2) / 0.14))
                xoff += lunge * dirn
            elif act == "duck":
                c = (tt % 1.6) / 1.6
                if c < 0.55:
                    squash = 1.0 - 0.42 * math.sin(math.pi * c / 0.55)
            elif act == "sleep":
                tilt = 6.0 * dirn
                for k in range(3):
                    rise = (tt * 16 + k * 14) % 42
                    zy = int(feet - ch.h + ch.h - 6 - rise)
                    if zy > 4:
                        zx = x - 4 - k * 7 if dirn < 0 else x + ch.w - 2 + k * 7
                        img.paste(self.zz, (int(zx + 3 * math.sin(tt + k)), zy), self.zz)
            elif act == "fire":
                tilt = -9.0 * dirn
                fr = "B" if int(tt * 8) % 2 == 0 else "A"
                spr = ch.frames[fr + ("f" if dirn < 0 else "")]
            elif act == "shock":
                c = (tt % 1.2) / 1.2
                pop_ = math.sin(c * math.pi)
                xoff -= int(8 * pop_) * dirn
                feet -= int(6 * pop_)
                squash = 1.0 + 0.15 * pop_
            elif act == "fall":
                c = (tt % 1.9) / 1.9
                if c < 0.22:
                    p2 = c / 0.22
                    xoff += int(9 * p2) * dirn
                    feet -= int(5 * math.sin(p2 * math.pi))
                    tilt = -78.0 * p2 * p2 * dirn
                else:
                    tilt = -78.0 * dirn
            elif act == "powerup":              # v9: transformationen!
                cy = (tt % 2.8) / 2.8
                if cy < 0.32:                     # samla kraft: darrar o squaschar
                    squash = 1.0 - 0.10 * math.sin(math.pi * cy / 0.32)
                    xoff += int(1.5 * math.sin(tt * 31))
                else:                             # svävar med aura!
                    feet -= int(4 + 2 * math.sin(tt * 9))
                    squash = 1.0 + 0.06 * abs(math.sin(tt * 13))
            elif act == "flex":
                bounce = abs(math.sin(tt * 5.0))
                squash = 1.0 + 0.10 * bounce
                tilt = -5.0 * dirn * math.sin(tt * 5.0)
            else:  # walk / idle – PERSONLIGHET i gångarten!
                if ch.hopping:                      # kanin: skuttar
                    feet -= abs(int(2 * math.sin(tt * 7)))
                elif ch.species == "apa":           # apa: hoppig smyg-march
                    tilt = -4.0 * dirn
                    feet -= abs(int(2 * math.sin(tt * 9)))
                else:                               # dino: tungt stamp, axel-gunga
                    if fr == "B":
                        feet -= CHAR_SCALE
                    xoff += int(1.2 * math.sin(tt * 7))

            if squash != 1.0:
                spr = spr.resize((spr.width, max(6, int(spr.height * squash))), NEAREST)
            if tilt != 0.0:
                spr = spr.rotate(tilt, resample=NEAREST, expand=True, fillcolor=(0, 0, 0, 0))

            px = x + xoff + (ch.w - spr.width) // 2
            py = feet - spr.height
            if act == "run":                    # KANADA-EFTERBILDER vid fartspridning
                img.paste(self._ghost(spr, 0.35), (px - dirn * 14, py), self._ghost(spr, 0.35))
                img.paste(self._ghost(spr, 0.20), (px - dirn * 26, py), self._ghost(spr, 0.20))
            if act == "hit" and 0.05 < ((tt % 0.9) / 0.9) < 0.30:   # smear-frame!
                sm = spr.resize((int(spr.width * 1.55) if dirn > 0 else spr.width, spr.height), NEAREST)
                if dirn < 0:
                    sm = sm.resize((spr.width, spr.height), NEAREST).transpose(Image.FLIP_LEFT_RIGHT)
                    sm = sm.resize((int(spr.width * 1.55), spr.height), NEAREST).transpose(Image.FLIP_LEFT_RIGHT)
                else:
                    sm = spr.resize((int(spr.width * 1.55), spr.height), NEAREST)
                img.paste(self._ghost(sm, 0.45), (px - dirn * 9, py), self._ghost(sm, 0.45))
            img.paste(spr, (px, py), spr)
            if lunge > 6:
                pwx = px - self.pow.width - 2 if dirn < 0 else px + spr.width + 2
                img.paste(self.pow, (pwx, int(feet - ch.h * 0.75)), self.pow)

            # --- humor-overlayar (riktningsmedvetna) ---
            head_xc = px + spr.width // 2
            head_y = py + spr.height // 3
            mouth_x = px + (spr.width - 4 if dirn > 0 else 4)
            if act == "dance":
                ny = max(1, py - self.note_img.height - 2 + int(2 * math.sin(tt * 3)))
                img.paste(self.note_img,
                          (head_xc + dirn * 4 + int(3 * math.sin(tt * 2.5)), ny), self.note_img)
            elif act == "hit":
                img.paste(self.anger_img, (head_xc - 8, max(1, py - self.anger_img.height)),
                          self.anger_img)
            elif act == "fire":
                # SAKUGA-BEAM: laddning (aura+ring) -> full stråle över skärmen -> rök
                cyc = (tt % 2.2) / 2.2
                fy = head_y + int(1.5 * math.sin(tt * 11))
                if cyc < 0.27:                          # CHARGE: aura-pulver stiger
                    chp = cyc / 0.27
                    for k in range(7):                  # stigande aura-partiklar
                        ax = head_xc + int(8 * math.sin(tt * 6 + k * 0.9))
                        ay = int(feet - ((tt * 34 + k * 9) % 30))
                        d.rectangle([ax - 1, ay - 2, ax, ay], fill=(255, 190 - k * 12, 60, 190))
                    ring = int(4 + 3 * math.sin(tt * 14))       # pulserande ring
                    d.ellipse([x - 4 - ring, GROUND_Y - 1, x + ch.w + 4 + ring, GROUND_Y + 4],
                              outline=(255, 170, 60, 160))
                    rb = 3 + int(7 * chp)                     # liten växande kärna i munnen
                    d.ellipse([mouth_x - rb, fy - rb, mouth_x + rb, fy + rb],
                              fill=(255, 238, 170, 235))
                elif cyc < 0.74:                        # BEAM! full-bredd flicker-stråle
                    bp = (cyc - 0.27) / 0.47
                    hgt = max(2, 5 + int(4 * math.sin(tt * 43) + 3 * math.sin(tt * 27)))
                    edge = W if dirn > 0 else -1
                    # glöd, kropp, kärna (3 lager)
                    d.rectangle([min(mouth_x, edge), fy - hgt - 4, max(mouth_x, edge), fy + hgt + 4],
                                fill=(255, 120, 40, 70))
                    d.rectangle([min(mouth_x, edge), fy - hgt, max(mouth_x, edge), fy + hgt],
                                fill=(255, 150, 55, 200))
                    d.rectangle([min(mouth_x, edge), fy - max(2, hgt // 2), max(mouth_x, edge),
                                 fy + max(2, hgt // 2)], fill=(255, 244, 190, 240))
                    rb = 10 + int(3 * math.sin(tt * 31))          # energikula i munnen
                    for rr, cf in ((rb + 5, (255, 120, 40, 90)), (rb, (255, 180, 70, 210)),
                                   (rb // 2, (255, 248, 190, 240))):
                        d.ellipse([mouth_x - rb, fy - rb, mouth_x + rb, fy + rb], fill=cf)
                    for k in range(5):                           # gnistor vid strålen
                        yy2 = fy + int((hgt + 8) * math.sin(tt * 17 + k * 1.3))
                        xx2 = int(((tt * 220 + k * 47) % (W - 20))) + 10
                        d.point((xx2, yy2), fill=(255, 235, 150, 220))
                else:                                            # röksättning
                    for k in range(3):
                        ry = fy - int((tt * 8 + k * 5) % 14)
                        rx = mouth_x + dirn * (6 + k * 4)
                        d.ellipse([rx - 3, ry - 2, rx + 3, ry + 2], fill=(160, 160, 172, 90))
            elif act == "shock":
                c2 = (tt % 1.2) / 1.2
                if 0.1 < c2 < 0.75:
                    by2 = max(1, py - self.bang_bubble.height + int(1.5 * math.sin(tt * 20)))
                    bx = px + spr.width - 2 if dirn > 0 else px - self.bang_bubble.width + 2
                    img.paste(self.bang_bubble, (bx, by2), self.bang_bubble)
                if c2 > 0.5:
                    img.paste(self.sweat_img, (head_xc - dirn * 10, max(1, head_y - 6)),
                              self.sweat_img)
            elif act == "fall":
                c2 = (tt % 1.9) / 1.9
                if c2 >= 0.22:
                    d.ellipse([px - 4, GROUND_Y - 1, px + spr.width + 4, GROUND_Y + 5],
                              fill=(0, 0, 0, 60))
                    for k in range(3):
                        a = tt * 5.0 + k * 2.094
                        sx = int(head_xc - 8 + 13 * math.cos(a))
                        sy = int(py - 2 + 5 * math.sin(a))
                        d.rectangle([sx, sy, sx + 2, sy + 2], fill=(255, 230, 120, 220))
            elif act == "powerup":
                cy = (tt % 2.8) / 2.8
                if cy < 0.32:                     # laddning: mörk uppsamling
                    for k in range(8):
                        ax = head_xc + int(11 * math.sin(tt * 5 + k * 0.8))
                        ay = int(feet - ((tt * 40 + k * 11) % 34))
                        d.point((ax, ay), fill=(150, 90, 220, 200))
                    ring = int(5 + 4 * math.sin(tt * 14))
                    d.ellipse([x - 6 - ring, GROUND_Y - 2, x + ch.w + 6 + ring, GROUND_Y + 4],
                              outline=(170, 100, 235, 160))
                else:                             # AURA-PELARE + svävning + debris
                    for j, (ox, wid) in enumerate(((-9, 7), (0, 11), (9, 7))):
                        top = py - 8 - int(14 * math.sin(tt * 17 + j * 2.1)) - j * 3
                        for rr, cf in ((wid, (255, 120, 50, 110)), (max(2, wid - 3), (255, 175, 80, 190)),
                                       (max(1, wid - 5), (255, 238, 170, 230))):
                            d.rectangle([px + spr.width // 2 + ox - rr, top,
                                         px + spr.width // 2 + ox + rr, GROUND_Y], fill=cf)
                    for k in range(6):            # stenflis som tappar tyngdkraften
                        dx2 = int((k * 17 + 11 * math.sin(k)) % 40) - 20
                        dy2 = int((tt * 26 + k * 13) % 26)
                        d.point((head_xc + dx2, GROUND_Y + 3 - dy2), fill=(120, 100, 140, 220))
                    for k in (0, 1):              # sprickor i marken
                        sx2 = x + (4 if k == 0 else ch.w - 8)
                        d.line([(sx2, GROUND_Y + 2), (sx2 - 7 + 14 * k, GROUND_Y + 5),
                                (sx2 - 11 + 22 * k, GROUND_Y + 7)],
                               fill=(20, 14, 26, 200), width=1)
            elif act == "flex":
                blink2 = int(tt * 4) % 2 == 0
                sy2 = max(1, py - self.star_img.height + 2 + int(2 * abs(math.sin(tt * 5))))
                img.paste(self.star_img, (head_xc + dirn * (2 if blink2 else 6), sy2),
                          self.star_img)

        if self.bubble_img and self.actors and 0.55 <= t <= 3.0:
            ch0, _segs0 = self.actors[0]
            by = max(2, GROUND_Y + 2 - ch0.h - self.bubble_img.height - 4 +
                     int(2 * math.sin(t * 2.2)))
            img.paste(self.bubble_img, (CHAR_X + ch0.w - 6, by), self.bubble_img)

    # -- v7: kamera -----------------------------------------------------------
    def _zoom(self, img, z, focus=(160, 96)):
        if z <= 1.001:
            return img
        w0, h0 = max(32, int(W / z)), max(18, int(H / z))
        fx, fy = focus
        x0 = max(0, min(W - w0, int(fx - w0 * 0.5)))
        y0 = max(0, min(H - h0, int(fy - h0 * 0.6)))
        return img.crop((x0, y0, x0 + w0, y0 + h0)).resize((W, H), NEAREST)

    def _apply_camera(self, img, t):
        if not self.cam:
            return img
        dx = dy = 0
        for op in self.cam:
            k = op.get("kind")
            if k == "push":
                dd = max(1.0, op.get("dur", self.dur) - 0.2)
                z = 1.0 + op.get("z", 0.22) * min(1.0, t / dd)
                img = self._zoom(img, z, op.get("focus", (160, 96)))
            elif k == "punch":                    # slagzoom på gag-ögonblicket
                at = op.get("at", 1.0)
                hold = op.get("hold", 2.4)
                if t >= at:
                    rise = min(1.0, (t - at) / 0.22)
                    rel = fall = 0.0
                    if t > at + hold:
                        fall = min(1.0, (t - at - hold) / 0.7)
                    z = 1.0 + op.get("z", 0.4) * (self._ease(rise) - self._ease(fall))
                    img = self._zoom(img, max(1.0, z), op.get("focus", (176, 92)))
            elif k == "shake":
                at = op.get("at", 1.0)
                amp = op.get("amp", 4)
                if at <= t < at + 0.55:
                    kk = 1 - (t - at) / 0.55
                    dx += int(amp * kk * math.sin(t * 91))
                    dy += int(amp * 0.7 * kk * math.cos(t * 83))
        if dx or dy:
            base = Image.new("RGB", (W, H), (0, 0, 0))
            base.paste(img, (dx, dy))
            img = base

        # ============ SAKUGA POST-FX ============
        d2 = ImageDraw.Draw(img, "RGBA")
        for op in self.cam:
            k = op.get("kind")
            if k == "burst":                     # radiator-wedges bakom träff-ögonblicket
                at = op.get("at", 1.0); ddz = op.get("dur", 0.7)
                if at <= t < at + ddz:
                    q = (t - at) / ddz
                    fx, fy = op.get("focus", (170, 90))
                    rng2 = random.Random(int(at * 977))
                    n2 = 14
                    for wdg in range(n2):
                        a0 = (wdg / n2) * 6.283 + q * 0.6
                        col = (255, 240, 150, 120) if wdg % 2 == 0 else (255, 90, 60, 120)
                        R = 260
                        p1 = (fx + int(math.cos(a0 - 0.06) * 14), fy + int(math.sin(a0 - 0.06) * 14))
                        p2 = (fx + int(math.cos(a0 + 0.06) * 14), fy + int(math.sin(a0 + 0.06) * 14))
                        p3 = (fx + int(math.cos(a0 + 0.11 * (1 - q)) * R), fy + int(math.sin(a0 + 0.11 * (1 - q)) * R))
                        p4 = (fx + int(math.cos(a0 - 0.11 * (1 - q)) * R), fy + int(math.sin(a0 - 0.11 * (1 - q)) * R))
                        d2.polygon([p1, p2, p3, p4], fill=col)
            elif k == "speedlines":              # speed lines: horiz (rusch) / ring (impact)
                t0, t1 = op.get("t0", 0.0), op.get("t1", self.dur)
                if t0 <= t < t1:
                    mode = op.get("mode", "horiz")
                    rng3 = random.Random(int(t0 * 131 + (97 if int(t * 12) % 2 else 0)) + 11)
                    if mode == "horiz":
                        for _ in range(9):
                            yy3 = rng3.randint(18, GROUND_Y - 8)
                            L = rng3.randint(30, 90)
                            drift = int((t * 260) % (W + L)) - L
                            if rng3.random() < 0.55:
                                yy3 = GROUND_Y - 8 - yy3 % (GROUND_Y - 30)
                            d2.line([(drift, yy3), (min(W, drift + L), yy3)],
                                    fill=(255, 255, 255, 70), width=1)
                    else:
                        fx, fy = op.get("focus", (170, 92))
                        for wdg in range(22):
                            a0 = wdg / 22 * 6.283
                            r_in = 46 + (wdg % 5) * 7
                            r_out = r_in + 30 + (wdg % 3) * 15
                            d2.line([(fx + int(math.cos(a0) * r_in), fy + int(math.sin(a0) * r_in)),
                                     (fx + int(math.cos(a0) * r_out), fy + int(math.sin(a0) * r_out))],
                                    fill=(255, 255, 255, 110), width=1)
            elif k == "impactflash":             # IMPACT FRAME: invert -> vitt (1-2 frames)
                at = op.get("at", 1.0)
                if at <= t < at + 0.083:
                    img = ImageOps.invert(img.convert("RGB"))
                    d2 = ImageDraw.Draw(img, "RGBA")
                elif at + 0.083 <= t < at + 0.167:
                    img.paste((255, 250, 235), [0, 0, W, H])
                    d2 = ImageDraw.Draw(img, "RGBA")
            elif k == "dutch":                   # snett kaos-perspektiv
                img = img.rotate(op.get("angle", -5), resample=NEAREST,
                                 expand=False, fillcolor=(0, 0, 0))
                d2 = ImageDraw.Draw(img, "RGBA")
        # ============ V9 CINEMA-FX ============
        for op in self.cam:
            k = op.get("kind")
            if k == "slowmo":                    # Matrix-dodge: mörk vignett
                t0, t1 = op.get("t0", 0.0), op.get("t1", 1.0)
                if t0 <= t < t1:
                    d2.rectangle([0, 0, W, 10], fill=(0, 0, 20, 150))
                    d2.rectangle([0, H - 10, W, H], fill=(0, 0, 20, 150))
                    d2.rectangle([0, 0, 12, H], fill=(0, 0, 20, 110))
                    d2.rectangle([W - 12, 0, W, H], fill=(0, 0, 20, 110))
            elif k == "shockring":               # utvidgande stötvågsring
                at = op.get("at", 1.0)
                if at <= t < at + 0.85:
                    q = (t - at) / 0.85
                    fx, fy = op.get("focus", (160, GROUND_Y - 10))
                    rr2 = int(8 + 130 * q)
                    for off, al in ((0, 200), (4, 120), (8, 60)):
                        d2.ellipse([fx - rr2 - off, fy - (rr2 + off) // 3,
                                    fx + rr2 + off, fy + (rr2 + off) // 3],
                                   outline=(255, 240, 190, int(al * (1 - q))))
            elif k == "word":                    # klassisk onomatopoetik-burst
                at = op.get("at", 1.0)
                if at <= t < at + 0.85:
                    q = min(1.0, (t - at) / 0.12)
                    img = _word_burst(img, op.get("word", "BAM"), op.get("pos"),
                                      q, (t - at))
                    d2 = ImageDraw.Draw(img, "RGBA")
            elif k == "fisheye":                 # öppning: världen vecklas ut
                if op.get("t0", 0.0) <= t < op.get("t1", 1.2):
                    img = _fisheye(img, 0.35)
                    d2 = ImageDraw.Draw(img, "RGBA")
            elif k == "wipe":                    # anime-övergång mellan scener
                ln = op.get("len", 0.28)
                p = min(1.0, t / ln) if t < ln else 1.0
                if p < 1.0:
                    _draw_wipe(d2, op.get("style", 0), p)

        # letterbox SIST (breven ovanpå allt)
        bars = None
        for op in self.cam:
            if op.get("kind") == "letterbox":
                bars = op.get("h", 13)
        if bars:
            d2.rectangle([0, 0, W, bars], fill=(0, 0, 0))
            d2.rectangle([0, H - bars, W, H], fill=(0, 0, 0))
        return img

    def _draw_particles(self, img, t):
        d = ImageDraw.Draw(img)
        kind = self.part_kind
        for p in self.parts:
            if kind == "leaf":
                x = int((p["x"] - t * 9 + p["sway"] * math.sin(t * 2 + p["ph"])) % (W + 16)) - 8
                y = int((p["y"] + t * (4 + p["v"] * 0.4)) % (GROUND_Y - 6)) + 2
                col = ((255, 196, 66), (255, 150, 60), (140, 200, 90))[int(p["ph"]) % 3]
                d.rectangle([x, y, x + 1, y + 1], fill=col)
            elif kind == "snow":
                x = int((p["x"] + p["sway"] * math.sin(t + p["ph"]) - t * 2) % W)
                y = int((p["y"] + t * (3 + p["v"] * 0.3)) % (GROUND_Y - 4)) + 1
                d.point((x, y), fill=(255, 255, 255))
                d.point((x + 1, y), fill=(235, 242, 250))
            elif kind == "firefly":
                x = int(p["x"] + 18 * math.sin(t * 0.7 + p["ph"]))
                y = int(60 + p["y"] * 0.5 + 8 * math.sin(t * 1.1 + p["ph"] * 2))
                if 0.5 + 0.5 * math.sin(t * p["sp"] + p["ph"]) > 0.35:
                    d.point((x, y), fill=(190, 255, 120))
                    d.point((x + 1, y), fill=(140, 200, 90))
            elif kind == "mote":
                x = int((p["x"] - t * 6) % W)
                y = int((p["y"] + t * 2) % GROUND_Y)
                b = 0.5 + 0.5 * math.sin(t * p["sp"] + p["ph"])
                v = int(120 + 100 * b)
                d.point((x, y), fill=(v, v // 2, min(255, v + 60)))
            elif kind == "bubbla":
                y = GROUND_Y - ((p["y"] + t * p["v"]) % (GROUND_Y - 14)) - 2
                x = int(p["x"] + 2.5 * math.sin(t * 1.7 + p["ph"]))
                r = p["r"]
                d.ellipse([x - r, y - r, x + r, y + r], outline=(185, 225, 250))
            elif kind == "glitter":
                x = int((p["x"] + p["sway"] * math.sin(t + p["ph"])) % W)
                y = int((p["y"] + t * (3 + p["v"] * 0.2)) % (GROUND_Y - 4)) + 1
                col = [(255, 255, 255), (255, 230, 120), (255, 170, 210),
                       (170, 235, 255)][int(t * 2 + p["ph"]) % 4]
                d.point((x, y), fill=col)

    def _warp_t(self, t):
        """Tidskrökning: 'hold' = fryst, 'slowmo' = Matrix-tempo i fönstret."""
        events = []
        for op in self.cam:
            k = op.get("kind")
            if k == "hold":
                events.append((op.get("at", 1.0), op.get("at", 1.0) + op.get("len", 0.28), 0.0))
            elif k == "slowmo":
                events.append((op.get("t0", 0.0), op.get("t1", 1.0), op.get("scale", 0.35)))
        events.sort()
        adj = 0.0
        for a, b, s in events:
            if t <= a:
                break
            if t <= b:
                return a - adj + (t - a) * s
            adj += (b - a) * (1 - s)
        return t - adj

    def frame(self, t):
        t = self._warp_t(t)
        img = self.sky.copy()
        self._draw_stars(img, t)
        if self.rays is not None:
            img.paste(self.rays, (0, 0), self.rays)
        self._draw_celestial(img, t)
        self._draw_clouds(img, t)
        self._draw_floaters(img, t)
        if self.bird:
            self._draw_bird(img, t)
        if self.hills is not None:
            self._paste_wrapped(img, self.hills, t * 3.0)
        self._draw_watcher(img, t)
        if self.pal.get("sea"):
            self._draw_sea(img, t)
        if self.trees is not None:
            self._paste_wrapped(img, self.trees, t * 9.0)
        if self.weeds:
            self._draw_weeds(img, t)
        self._paste_wrapped(img, self.ground, t * 16.0)
        self._draw_swimmers(img, t)
        self._draw_actors(img, t)
        self._draw_hoppers(img, t)
        self._draw_particles(img, t)
        self._draw_foreground(img, t)      # FÖRGRUND sist av världslagren = djup
        return self._apply_camera(img, t)
