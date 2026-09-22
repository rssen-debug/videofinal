#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2 PIXEL ANIME — engine. Fristående från v1 (engine.py).
Mänskliga pixelkaraktärer: hår per stil, ögon-reaktioner, mun-läppsynk
(hämtad från röstens envelope), poser: idle/walk/run/punch/hurt/point.
Scener: dock (regn + fyr + signalmast), dojo-interiör (shoji-dörr som ÖPPNAS),
tittskort / eyecatch / next-episode. Kamera: zoom, pan, shake, letterbox.
"""
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

NEAREST = Image.Resampling.NEAREST
W, H = 320, 180           # logisk duk (skalas x4 -> 1280x720)
GROUND = 150              # fötternas baslinje

# ===========================================================================
# PIXELTEXT – litet typsnitt uppskalat NEAREST = äkta pixeltypografi
# ===========================================================================
def ptext(line, scale=3, col=(255, 255, 255)):
    f = ImageFont.load_default()
    im = Image.new("RGBA", (len(line) * 7 + 4, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((2, 1), line, font=f, fill=tuple(col) + (255,))
    return im.resize((im.width * scale, im.height * scale), NEAREST)


def ptext_fit(line, col=(255, 255, 255), scales=(5, 4, 3, 2, 1), maxw=W - 20):
    for s in scales:
        im = ptext(line, s, col)
        if im.width <= maxw:
            return im
    im = ptext(line, 1, col)
    if im.width > maxw:                     # hård-golvet: krymp till maxw (annars klipps texten)
        h2 = max(4, int(im.height * maxw / im.width))
        im = im.resize((maxw, h2), NEAREST)
    return im


def ptext_center(big, line, y, scale=3, col=(255, 255, 255)):
    t = ptext(line, scale, col)
    big.alpha_composite(t, ((W * 4 - t.width) // 2 // 4, y)) if False else None
    return t


# ===========================================================================
# KROPP – 24 bred x 26 hög. Bokstäver: H=hår S=hud T=top P=byxor B=boots A=bälte
# ===========================================================================
def _rows(s):
    out = [r for r in s.strip("\n").splitlines()]
    w = max(len(r) for r in out)
    return [r.ljust(w, ".") for r in out]


ART = {}

ART["idle"] = _rows("""
........................
......HHHHHHHHH.........
......HHSSSSSSH.........
......HSSWWSSWWSH.......
......HSSWKSSWKSH.......
......HSSSSSSSSH........
......HSSSMMSSH.........
.......SSSSSSS..........
......TTTTTTTTT.........
...TTTTTTTTTTTTTTT......
...TTTTTTTTTTTTTTT......
...TTTTTTTTTTTTTTT......
...TTTTTTTTTTTTTTT......
...SSSTTTTTTTTTSSS......
...SSSTTTTTTTTTSSS......
......TTTTTTTTT.........
......TTTTTTTTT.........
......AAAAAAAAA.........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
.....BBBB...BBBBB.......
.....BBBB...BBBBB.......
""")

ART["walk1"] = _rows("""
........................
......HHHHHHHHH.........
......HHSSSSSSH.........
......HSSWWSSWWSH.......
......HSSWKSSWKSH.......
......HSSSSSSSSH........
......HSSSMMSSH.........
.......SSSSSSS..........
......TTTTTTTTT.........
...TTTTTTTTTTTTTTT......
...TTTTTTTTTTTTTTT......
...TTTTTTTTTTTTTTT......
...TTTTTTTTTTTTTTT......
...SSSTTTTTTTTTSSS......
...SSSTTTTTTTTTSSS......
......TTTTTTTTT.........
......TTTTTTTTT.........
......AAAAAAAAA.........
......PPPPPPPPP.........
.....PPPP...PPPPP.......
....PPPP.....PPPPP......
....PPP.......PPPP......
....PPP........PPP......
....PPP........PPP......
...BBBB........BBBB.....
...BBBB........BBBB.....
""")

ART["punch"] = _rows("""
........................
......HHHHHHHHH.........
......HHSSSSSSH.........
......HSSWWSSWWSH.......
......HSSWKSSWKSH.......
......HSSSSSSSSH........
......HSSSMMSSH.........
.......SSSSSSS..........
......TTTTTTTTT.........
...TTTTTTTTTTT..........
...SSTTTTTTTTTTTTTTTTTSS
...SSTTTTTTTTTTTTTTTTTSS
...TTTTTTTTTTT..........
...SSSTTTTTTTT..........
...SSSTTTTTTTT..........
......TTTTTTTTT.........
......TTTTTTTTT.........
......AAAAAAAAA.........
......PPPPPPPPP.........
.....PPPP....PPPP.......
....PPPP......PPPP......
....PPP.......PPPP......
....PPP........PPP......
....PPP........PPP......
...BBBB........BBBB.....
...BBBB........BBBB.....
""")

ART["hurt"] = _rows("""
........................
......HHHHHHHHH.........
......HHSSSSSSH.........
......HSSWWSSWWSH.......
......HSSWKSSWKSH.......
......HSSSSSSSSH........
......HSSSMMSSH.........
.......SSSSSSS..........
......TTTTTTTTT.........
.S...TTTTTTTTTTT...S....
.SS..TTTTTTTTTTT..SS....
.SS.TTTTTTTTTTTT..SS....
.S..TTTTTTTTTTT...S.....
....TTTTTTTTTTT.........
....TTTTTTTTTTT.........
......TTTTTTTTT.........
......TTTTTTTTT.........
......AAAAAAAAA.........
......PPPPPPPPP.........
.....PPPP..PPPP.........
....PPPP..PPPP..........
....PPP...PPPP..........
....PPP....PPP..........
....PPP.....PPP.........
...BBBB.....BBBB........
...BBBB.....BBBB........
""")

ART["point"] = _rows("""
........................
......HHHHHHHHH.........
......HHSSSSSSH.........
......HSSWWSSWWSH.......
......HSSWKSSWKSH.......
......HSSSSSSSSH........
......HSSSMMSSH.........
.......SSSSSSS..........
......TTTTTTTTT..S......
...TTTTTTTTTTT..SS......
...TTTTTTTTTTTSSS.......
...TTTTTTTTTTSSSS.......
...TTTTTTTTTTT..........
...SSSTTTTTTTTT.........
...SSSTTTTTTTTT.........
......TTTTTTTTT.........
......TTTTTTTTT.........
......AAAAAAAAA.........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
.....BBBB...BBBBB.......
.....BBBB...BBBBB.......
""")

ART["guard"] = _rows("""
........................
......HHHHHHHHH.........
......HHSSSSSSH.........
......HSSWWSSWWSH.......
......HSSWKSSWKSH.......
......HSSSSSSSSH........
......HSSSMMSSH.........
.......SSSSSSS..........
....SSTTTTTTTTTTSS......
....SSTTTTTTTTTTSS......
....TTT.STT.STTT........
....TTTTTTTTTTTT........
....TTTTTTTTTTTT........
......TTTTTTTTT.........
......TTTTTTTTT.........
......TTTTTTTTT.........
......TTTTTTTTT.........
......AAAAAAAAA.........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
......PPP...PPPP........
.....BBBB...BBBBB.......
.....BBBB...BBBBB.......
""")

# ---------------------------------------------------------------------------
# HÅRSTILAR (ersätter topp-raderna i huvudet; sidlock tillåtna via extra_px)
# ---------------------------------------------------------------------------
HAIR = {}
HAIR["spiky"] = _rows("""
..............H.........
....H..HH..HH.HH..H.....
....HHHHHHHHHHHHHHH.....
....HHHHHHHHHHHHHHH.....
""")
HAIR["long"] = _rows("""
.......HHHHHHH..........
.....HHHHHHHHHHH........
....HHHHHHHHHHHHH.......
....HHHHHHHHHHHHH.......
""")
HAIR["pony"] = _rows("""
...........HHHH.........
......HHHHHHHHHHH.......
......HHHHHHHHHHHH......
......HHHHHHHHHHH.......
""")
HAIR["short"] = _rows("""
........HHHHHHHH........
......HHHHHHHHHHHH......
......HHHHHHHHHHHH......
......HHHHHHHHHHHH......
""")

HAIR["hawk"] = _rows("""
........HHHHH...........
........HHHHH...........
........HHHHH...........
........HHHHH...........
""")

FACE_X, FACE_Y = 9, 3   # vänster ögats övre hörn i 24x26-biten (W startar här)


def _mk(rows, cols):
    img = Image.new("RGBA", (24, 26), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in cols:
                px[x, y] = cols[ch] + (255,)
    return img


# ---------------------------------------------------------------------------
# ANSIKTET: dynamiska overlays för ögon/mun/blåmärke – ritas ovanpå basbilden
# ---------------------------------------------------------------------------
def _face_patch(img, cols, eyes="normal", mouth="closed", bruise=False):
    """eyes: normal/blink/wide/angry/x/spark/sad  mouth: closed/open/grin/shout"""
    out = img.copy()
    d = ImageDraw.Draw(out)
    skin = cols["S"] + (255,)
    dark = cols["K"] + (255,)
    white = (255, 255, 255, 255)
    # Ansiktsregion (ögon + mun) täcks först med hud om något ska ändras
    cover = [(8, 2), (16, 6)]
    if eyes != "normal" or mouth != "closed":
        d.rectangle(cover, fill=skin)
    # ---- ögon ----
    if eyes == "blink":
        d.line([(8, 4), (10, 4)], fill=dark)
        d.line([(12, 4), (14, 4)], fill=dark)
    elif eyes == "wide":                       # chock: stora vita
        for ex in (8, 12):
            d.rectangle([ex, 2, ex + 2, 5], fill=white)
            d.point((ex + 1, 4), fill=dark)
    elif eyes == "angry":                      # arga bryn + smala ögon
        for ex in (8, 12):
            d.rectangle([ex, 3, ex + 2, 4], fill=white)
            d.point((ex + 1, 4), fill=dark)
        d.line([(8, 3), (10, 2)], fill=dark)   # vänster bryn lutar ner-in
        d.line([(14, 3), (12, 2)], fill=dark)
    elif eyes == "x":                          # X-X (oomtoold)
        for ex in (8, 12):
            d.line([(ex, 3), (ex + 2, 5)], fill=dark)
            d.line([(ex + 2, 3), (ex, 5)], fill=dark)
    elif eyes == "spark":                      # stjärn-glans
        for ex in (8, 12):
            d.point((ex + 1, 3), fill=white); d.point((ex, 4), fill=white)
            d.point((ex + 2, 4), fill=white); d.point((ex + 1, 4), fill=white)
            d.point((ex + 1, 5), fill=white)
    elif eyes == "sad":
        for ex in (8, 12):
            d.point((ex + 1, 4), fill=dark)
            d.rectangle([ex, 4, ex + 2, 4], fill=dark)
    else:                                      # normal
        for ex in (8, 12):
            d.rectangle([ex, 3, ex + 2, 4], fill=white)
            d.point((ex + 1, 4), fill=dark)
    # ---- mun ----
    if mouth == "open":
        d.rectangle([10, 6, 11, 7], fill=dark)
    elif mouth == "grin":
        d.rectangle([9, 6, 12, 6], fill=white)
        d.point((10, 7), fill=dark); d.point((11, 7), fill=dark)
    elif mouth == "shout":
        d.rectangle([9, 6, 12, 7], fill=dark)
        d.point((10, 6), fill=white)
    elif mouth == "frown":
        d.point((9, 7), fill=dark); d.line([(10, 6), (11, 6)], fill=dark)
        d.point((12, 7), fill=dark)
    else:
        d.point((10, 6), fill=dark); d.point((11, 6), fill=dark)
    if bruise:
        red = (235, 90, 90, 255)
        d.point((7, 6), fill=red); d.point((7, 7), fill=red)
        d.point((8, 7), fill=red)
    return out


class PXChar:
    """En mänsklig pixelkaraktär. Samma namn -> samma utseende, för evigt."""

    def __init__(self, name, palette, hair="spiky", scale=1.0, voice_pitch="ren"):
        self.name = name
        self.scale = scale
        self.voice_pitch = voice_pitch
        cols = dict(palette)
        cols.setdefault("W", (250, 250, 250))
        cols.setdefault("K", (24, 22, 28))
        cols.setdefault("M", (90, 30, 40))
        # håret: ersätt topprader rader 0-3
        hair_rows = HAIR[hair]
        hair_col = cols["H"]
        self.cols = cols
        self.hair_col = hair_col
        self.hair_rows = hair_rows
        self._pose_base = {}
        for pose, rows in ART.items():
            base = _mk(self._merge_hair(rows), cols)
            if scale != 1.0:
                nw, nh = int(24 * scale + 0.5), int(26 * scale + 0.5)
                base = base.resize((nw, nh), NEAREST)
            self._pose_base[pose] = base
        # walk2 = spegling av walk1 (annat ben framåt) – gratis gångfas!
        self._pose_base["walk2"] = ImageOps.mirror(self._pose_base["walk1"])

    def _merge_hair(self, rows):
        rows = list(rows)
        for hy, hrow in enumerate(self.hair_rows):
            line = list(rows[hy])
            for x, ch in enumerate(hrow):
                if ch == "H":
                    line[x] = "H"
            rows[hy] = "".join(line)
        return rows

    def get(self, pose, face_eyes="normal", face_mouth="closed", bruise=False, flip=False):
        base = self._pose_base[pose]
        im = _face_patch(base, self.cols, eyes=face_eyes, mouth=face_mouth, bruise=bruise)
        if flip:
            im = ImageOps.mirror(im)
        return im

    @property
    def w(self):
        return self._pose_base["idle"].width

    @property
    def hgt(self):
        return self._pose_base["idle"].height


# ===========================================================================
# SCEN-GRUNDER
# ===========================================================================
def _lerp(a, b, p):
    return a + (b - a) * p


def ease(p):
    return 1 - (1 - p) * (1 - p)


class Track:
    """Nyckelbilder för x-position (+ flaggor)."""
    def __init__(self, pts):
        self.pts = sorted(pts, key=lambda p: p[0])   # [(t, x, flip, pose?)]

    def at(self, t):
        if t <= self.pts[0][0]:
            return self.pts[0][1], self.pts[0][2]
        if t >= self.pts[-1][0]:
            return self.pts[-1][1], self.pts[-1][2]
        for i in range(len(self.pts) - 1):
            t0, x0 = self.pts[i][0], self.pts[i][1]
            t1, x1 = self.pts[i + 1][0], self.pts[i + 1][1]
            if t0 <= t <= t1:
                p = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                e = ease(p)
                return int(_lerp(x0, x1, e)), self.pts[i][2]
        return self.pts[-1][1], self.pts[-1][2]


class Actor:
    """Karaktär + pos-block + ansikts-block + rörelse-track inom en scen."""
    def __init__(self, char, blocks, track, faces=None, y_off=0):
        self.char = char
        self.blocks = sorted(blocks, key=lambda b: b[0])  # [(t0,t1,pose)]
        self.track = track
        self.faces = sorted(faces or [], key=lambda f: f[0])  # [(t,eyes,bruise)]
        self.y_off = y_off
        self.mouth = np.zeros(0)   # per-frame bool array sätts av v2make (lipsynk)

    def pose_at(self, t):
        for t0, t1, pose in self.blocks:
            if t0 <= t < t1:
                return pose
        return self.blocks[-1][2] if self.blocks else "idle"

    def face_at(self, t):
        eyes, bruise, smouth = "normal", False, None
        for f in self.faces:
            ft, fe, fb = f[0], f[1], f[2]
            if t >= abs(ft):
                eyes, bruise = fe, fb
                smouth = f[3] if len(f) > 3 else None
        return eyes, bruise, smouth


# ===========================================================================
# SCEN 1 – HAMNEN (regn, fyr, signalmast, lyktstolpar)
# ===========================================================================
class DockNight:
    def __init__(self, seed=0, rain=True, lights_on=False, light_event=None):
        self.rng = random.Random(seed)
        self.rain = rain
        self.light_event = light_event          # tid då hamnens ljus tänds
        self.lights_on = lights_on
        self._build()

    def _build(self):
        self.bg = Image.new("RGB", (W, H), (10, 14, 34))
        d = ImageDraw.Draw(self.bg)
        # himmel: indigo -> teal horisont
        for y in range(96):
            p = y / 95
            col = (int(_lerp(12, 26, p)), int(_lerp(16, 70, p)), int(_lerp(44, 92, p)))
            d.line([(0, y), (W, y)], fill=col)
        for _ in range(60):                     # stjärnor
            d.point((self.rng.randrange(W), self.rng.randrange(78)),
                    fill=(220, 225, 255) if self.rng.random() < .5 else (150, 160, 200))
        # v5 CEL: molnsilhuetter + mån-halo (för ritad anime-natt)
        for cxc, cyc, cw2 in ((62, 16, 26), (108, 34, 30), (302, 24, 22)):
            d.ellipse([cxc - cw2, cyc, cxc + cw2, cyc + 9], fill=(15, 22, 50))
            d.ellipse([cxc - cw2 + 9, cyc - 5, cxc + cw2 - 11, cyc + 5], fill=(15, 22, 50))
        d.ellipse([232, 0, 296, 52], fill=(17, 27, 60))
        d.ellipse([240, 4, 288, 48], fill=(22, 34, 70))
        # måne
        d.ellipse([250, 12, 278, 40], fill=(238, 236, 210))
        d.ellipse([258, 16, 282, 38], fill=(10, 14, 34, 0))  # halvmåne-känsla
        # hav
        d.rectangle([0, 96, W, 128], fill=(16, 42, 66))
        d.line([(0, 96), (W, 96)], fill=(58, 122, 148))            # v5: horisont-glans
        _rm = random.Random(11)
        for my in range(99, 125, 5):                                 # v5: månsken-pendel i sjön
            mw = _rm.randrange(5, 13)
            d.line([(264 - mw // 2, my), (264 + mw // 2, my)], fill=(110, 165, 185))
        for _ in range(160):
            x = self.rng.randrange(W); y = self.rng.randrange(98, 126)
            d.point((x, y), fill=self.rng.choice([(40, 90, 120), (30, 70, 100), (70, 130, 150)]))
        # fartyg-silhuett
        d.rectangle([36, 84, 86, 96], fill=(8, 10, 22))
        d.rectangle([48, 76, 60, 84], fill=(8, 10, 22))
        d.rectangle([70, 72, 74, 84], fill=(8, 10, 22))
        # kaj
        d.rectangle([0, 128, W, H], fill=(58, 46, 40))
        for x in range(0, W, 14):
            d.line([(x, 128), (x, H)], fill=(44, 34, 30))
        _rp = random.Random(3)                                       # v5: plank-tonvariation
        for px2 in range(0, W, 14):
            if _rp.random() < 0.45:
                yy2 = _rp.randrange(131, H - 10)
                ln = _rp.randrange(4, 9)
                d.rectangle([px2 + 1, yy2, px2 + 12, min(yy2 + ln, H - 1)], fill=(52, 40, 34))
        d.line([(0, 128), (W, 128)], fill=(90, 76, 62))
        for x in range(6, W, 48):               # pålar
            d.rectangle([x, 142, x + 5, H], fill=(38, 30, 26))
        self.tower_x = 236                      # signalmast
        tw = self.tower_x
        d.line([(tw, 128), (tw + 10, 60)], fill=(30, 30, 44))
        d.line([(tw + 16, 128), (tw + 10, 60)], fill=(30, 30, 44))
        for yy in range(66, 122, 10):
            p = (yy - 60) / 68
            d.line([(tw + int(2 * p), yy), (tw + int(16 - 2 * p), yy)], fill=(30, 30, 44))
            d.line([(tw + int(2 * p), yy), (tw + int(16 - 2 * p), yy + 7)], fill=(30, 30, 44))
        d.rectangle([tw + 6, 56, tw + 14, 62], fill=(40, 40, 56))
        self._tower_lamp = None
        # fyr (fyrtorn längst till vänster på molo)
        d.rectangle([6, 76, 20, 128], fill=(36, 34, 48))
        d.rectangle([2, 70, 24, 76], fill=(44, 42, 58))
        d.rectangle([10, 62, 16, 70], fill=(250, 240, 190))
        self.beam_origin = (13, 66)
        # lyktstolpar (släckta tills light_event)
        self.lamp_xs = [70, 150]

    def frame(self, t, lights_on):
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        # fyr-rotorstråle
        ang = t * 0.55
        ox, oy = self.beam_origin
        for da in (-3, 3):
            a2 = ang + math.radians(da)
            d.polygon([(ox, oy), (ox + int(math.cos(a2) * 190), oy + int(math.sin(a2) * 190)),
                       (ox + int(math.cos(ang) * 150), oy + int(math.sin(ang) * 150))],
                      fill=(250, 240, 190, 26))
        # signalmastens lampa: röd blink, ELLER stadiljus-läget tänt varmt
        lamp = (255, 70, 80, 255) if int(t * 2) % 2 == 0 else (80, 30, 36, 255)
        if lights_on:
            lamp = (255, 214, 130, 255)
        tw = self.tower_x
        d.ellipse([tw + 8, 57, tw + 12, 61], fill=lamp)
        if lights_on:
            d.ellipse([tw - 2, 48, tw + 22, 72], fill=(255, 214, 130, 36))
        for lx in self.lamp_xs:
            d.rectangle([lx, 96, lx + 2, 128], fill=(26, 24, 30))
            if lights_on:
                d.ellipse([lx - 3, 91, lx + 5, 99], fill=(255, 224, 150, 255))
                d.ellipse([lx - 9, 85, lx + 11, 105], fill=(255, 224, 150, 40))
                d.rectangle([lx - 2, 128, lx + 4, 132], fill=(255, 224, 150, 70))
            else:
                d.ellipse([lx - 3, 91, lx + 5, 99], fill=(40, 38, 46))
            if lights_on:                                            # v5: ljuskon på kajen
                d.polygon([(lx - 8, 134), (lx + 10, 134), (lx + 1, 99)],
                          fill=(255, 214, 140, 40))
        # stads-ljus i bakgrunden täcks upp
        if lights_on:
            for _ in range(26):
                x = self.rng_lights() if False else None
            self.rng2 = random.Random(7)
            for _ in range(30):
                d.point((self.rng2.randrange(W), self.rng2.randrange(88, 96)),
                        fill=(255, 200, 120, see := 255))
        if self.rain:
            for i in range(80):
                rng = random.Random(i)
                xx = rng.randrange(W + 40)
                sp = 180 + (i % 5) * 30
                yy = (rng.randrange(H) + t * sp) % H
                xx2 = xx - int((H - yy) * 0.18)
                d.line([(xx2, yy), (xx2 - 2, yy + 6)], fill=(160, 190, 220, 110))
            for j in range(10):                                      # v5: regn-stänk punkter
                _rj = random.Random(j * 7 + 1)
                ph = (t * 2.6 + j * 0.37) % 1.0
                if ph < 0.2:
                    d.point((_rj.randrange(W), 152 + _rj.randrange(5)),
                            fill=(190, 210, 230, 140))
        return img


# ===========================================================================
# SCEN 2 – DOJO-INTERIÖR (shoji-dörr som glider upp, boxningssäck som svarar)
# ===========================================================================
class DojoInterior:
    def __init__(self, seed=0, door_t=None, bag_hits=()):
        self.rng = random.Random(seed)
        self.door_t = door_t          # tidpunkt dörren börjar glida
        self.bag_hits = list(bag_hits)
        self._build()

    def _build(self):
        self.bg = Image.new("RGB", (W, H), (96, 70, 48))
        d = ImageDraw.Draw(self.bg)
        for y in range(0, 128, 8):    # träpanel
            d.line([(0, y), (W, y)], fill=(82, 60, 40))
        d.rectangle([0, 128, W, H], fill=(150, 118, 78))     # golv
        for x in range(0, W, 22):
            d.line([(x, 128), (x - 10, H)], fill=(126, 98, 64))
        d.rectangle([0, 126, W, 128], fill=(64, 46, 32))
        # matta
        d.rectangle([60, 132, 190, 162], fill=(64, 92, 120))
        d.rectangle([64, 136, 186, 158], fill=(74, 106, 138))
        # fönster: natt
        d.rectangle([148, 26, 216, 70], fill=(70, 52, 36))
        d.rectangle([152, 30, 212, 66], fill=(12, 18, 40))
        for _ in range(10):
            d.point((self.rng.randrange(153, 212), self.rng.randrange(31, 65)),
                    fill=(200, 205, 235))
        d.line([(182, 30), (182, 66)], fill=(70, 52, 36))
        # boxningssäck
        self.bag_x = 46
        # shoji-dörr (x4 bredd, glider åt vänster in i väggen)
        self.door = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
        dd = ImageDraw.Draw(self.door)
        dd.rectangle([0, 0, 63, 95], fill=(222, 206, 180, 255))
        for gx in range(0, 64, 16):
            dd.line([(gx, 0), (gx, 95)], fill=(140, 110, 84, 255))
        for gy in range(0, 96, 24):
            dd.line([(0, gy), (63, gy)], fill=(140, 110, 84, 255))
        dd.rectangle([0, 0, 63, 95], outline=(110, 86, 60, 255), width=2)
        dd.ellipse([56, 44, 60, 52], fill=(70, 52, 36, 255))
        self.door_rect = (236, 32, 300, 128)
        # dörröppningens mörker + yttre ljuskil
        d.rectangle(list(self.door_rect), fill=(16, 20, 38))
        # väggposter / kalligrafi-rulle
        d.rectangle([108, 30, 128, 78], fill=(228, 220, 204))
        dd2 = ImageDraw.Draw(self.bg)
        dd2.line([(118, 38), (118, 70)], fill=(30, 26, 30), width=2)
        dd2.line([(114, 46), (122, 46)], fill=(30, 26, 30))
        # bokken-ställ (vapenställ) vänster vägg
        dd2.rectangle([8, 58, 10, 96], fill=(58, 42, 30))
        for bx2, bcol in ((14, (150, 108, 70)), (18, (172, 130, 84)), (22, (128, 92, 58))):
            dd2.line([(bx2 - 6, 60), (bx2 + 6, 96)], fill=bcol, width=2)
            dd2.point((bx2 - 7, 59), fill=(200, 160, 110))
        dd2.rectangle([6, 94, 14, 98], fill=(58, 42, 30))
        # hänglykta i taket (varm glöd)
        dd2.line([(26, 0), (26, 10)], fill=(40, 34, 40))
        dd2.polygon([(19, 10), (33, 10), (30, 23), (22, 23)], fill=(238, 198, 128))
        dd2.polygon([(19, 10), (33, 10), (30, 23), (22, 23)], outline=(90, 66, 44))
        dd2.rectangle([24, 14, 28, 18], fill=(255, 240, 190))
        # signum-affisch på högra väggen
        dd2.rectangle([302, 40, 316, 78], fill=(214, 206, 190))
        dd2.rectangle([302, 40, 316, 78], outline=(120, 92, 64))
        dd2.ellipse([305, 46, 313, 56], outline=(150, 42, 44), width=2)
        dd2.line([(309, 60), (309, 72)], fill=(30, 26, 30), width=2)
        dd2.line([(305, 65), (312, 65)], fill=(30, 26, 30))
        # tatami-sömmar i golvet
        for tx in range(46, W, 58):
            dd2.line([(tx, 130), (tx + 7, H - 2)], fill=(138, 108, 70))

    def frame(self, t):
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        # boxningssäck: pendel efter träffar
        sw = 0.0
        for ht in self.bag_hits:
            if t > ht:
                sw += 14.0 * math.exp(-(t - ht) * 2.2) * math.sin((t - ht) * 7.0)
        bx = self.bag_x + int(sw)
        d.line([(bx + 7, 10), (bx + 7, 30)], fill=(30, 26, 26, 255))
        d.ellipse([bx, 30, bx + 14, 64], fill=(150, 60, 46, 255))
        d.ellipse([bx + 2, 34, bx + 6, 40], fill=(180, 84, 66, 255))
        # v5: lyktglöd-halo + månljuskil från fönstret (ämnesljus)
        d.ellipse([12, 2, 40, 30], fill=(255, 214, 130, 30))
        d.polygon([(154, 66), (212, 66), (244, 132), (196, 132)], fill=(110, 145, 200, 16))
        # dörr: glider upp under 0.9s; ljuskil strömmar in
        x0, y0, x1, y1 = self.door_rect
        p = 0.0
        if self.door_t is not None and t > self.door_t:
            p = min(1.0, (t - self.door_t) / 0.9)
            p = ease(p)
        if p > 0:
            d.polygon([(x0, y1), (x1, y1), (x1 - 20 - int(20 * p), y0)],
                      fill=(255, 232, 170, int(20 + 60 * p)))
        off = int(64 * p)
        img.alpha_composite(self.door, (x0 + off, y0))
        return img


# ===========================================================================
# KORT – titel / eyecatch / preview (helskärmar, ingen kamera)
# ===========================================================================
class Card:
    def __init__(self, bg_col=(8, 8, 16), seed=0):
        self.rng = random.Random(seed)
        self.bg_col = bg_col

    def _base(self, t):
        img = Image.new("RGBA", (W, H), self.bg_col + (255,))
        d = ImageDraw.Draw(img, "RGBA")
        for i in range(26):          # pulsande stjärnstoft
            rng = random.Random(i)
            if int(t * 8 + i) % 3 == 0:
                d.point((rng.randrange(W), rng.randrange(H)),
                        fill=(255, 240, 200, 120))
        return img, d


class TitleCard(Card):
    def __init__(self, series, episode, seed=0):
        super().__init__((6, 6, 14), seed)
        self.series = series
        self.episode = episode

    def frame(self, t):
        img, d = self._base(t)
        flick = (int(t * 11) % 7) != 3
        if flick:
            big = ptext_fit(self.series, col=(120, 230, 255), maxw=W - 16)
            img.alpha_composite(big, ((W - big.width) // 2, 42))
            glow = ptext_fit(self.series, col=(255, 255, 255), maxw=W - 20)
            img.alpha_composite(glow, ((W - glow.width) // 2 - 2, 40))
        if t > 0.9:
            sub = ptext_fit(self.episode, col=(255, 220, 150), maxw=W - 24)
            img.alpha_composite(sub, ((W - sub.width) // 2, 106))
            ln = ptext_fit("PIXEL ANIME - frame by frame, by your CPU",
                           col=(150, 150, 170), maxw=W - 6)
            img.alpha_composite(ln, ((W - ln.width) // 2, 132))
        return img


class EyecatchCard(Card):
    """Halvtidskortet! Karaktär i pose + serienamn (KonoSuba-stil)."""
    def __init__(self, pxchar, series, catchword, seed=0, dark=False):
        super().__init__((30, 8, 20) if dark else (10, 22, 50), seed)
        self.px = pxchar
        self.series = series
        self.catchword = catchword
        self.dark = dark

    def frame(self, t):
        img, d = self._base(t)
        for i in range(-4, 22):      # diagonala strålar
            col = (60, 120, 200, 70) if not self.dark else (200, 60, 80, 70)
            if i % 2 == 0:
                d.polygon([(i * 18 - int(t * 60) % 36, H), (i * 18 + 40 - int(t * 60) % 36, 0),
                           (i * 18 + 64 - int(t * 60) % 36, 0), (i * 18 + 24 - int(t * 60) % 36, H)],
                          fill=col)
        big = self.px.get_bust_scaled("angry", "grin", 5)
        if self.dark:
            from PIL import ImageOps as _IO
            big = _IO.mirror(big)
        bob = int(math.sin(t * 6) * 3)
        img.alpha_composite(big, (10, H - big.height - 6 + bob))
        nm = ptext_fit(self.series, col=(255, 255, 255), scales=(3, 2, 1), maxw=150)
        img.alpha_composite(nm, (W - nm.width - 12, 16))
        cw = ptext_fit(self.catchword, col=(150, 230, 255) if not self.dark else (255, 150, 150),
                       scales=(2, 1), maxw=150)
        img.alpha_composite(cw, (W - cw.width - 12, 16 + nm.height + 6))
        return img




class VertCard:
    """Litet vertikalt kort (90x160 logiskt): BIG + sub + small-lines."""

    def __init__(self, big, subtitle="", lines=(), tone=(14, 18, 34), seed=0):
        self.big = big; self.subtitle = subtitle; self.lines = lines
        self.tone = tone; self.rng = random.Random(seed)

    def frame(self, t):
        # 4x-supersampling: texten ritas skarp i 360x640 (sen NEAREST x3 -> 1080x1920)
        S4 = 4
        img = Image.new("RGBA", (90 * S4, 160 * S4), self.tone + (255,))
        d = ImageDraw.Draw(img, "RGBA")
        for i in range(12):
            rng2 = random.Random(i * 13)
            x = rng2.randrange(90 * S4); sp = (2 + i % 4) * S4
            y = (rng2.randrange(160 * S4) + t * sp) % (160 * S4)
            d.rectangle([x, y, x + S4 - 1, y + S4 - 1], fill=(70, 90, 120, 140))
        hb = ptext_fit(self.big, col=(140, 220, 255), scales=(16, 12, 8), maxw=82 * S4)
        img.alpha_composite(hb, ((90 * S4 - hb.width) // 2,
                                 (34 + int(-6 * min(1.0, t / 0.4))) * S4))
        if self.subtitle:
            hs = ptext_fit(self.subtitle, col=(236, 200, 110), scales=(5, 4, 3),
                           maxw=82 * S4)
            img.alpha_composite(hs, ((90 * S4 - hs.width) // 2,
                                     34 * S4 + hb.height + 12 * S4))
        y = 34 * S4 + hb.height + 40 * S4
        for ln in self.lines:
            hl = ptext_fit(ln, col=(200, 204, 214), scales=(3, 2), maxw=82 * S4)
            img.alpha_composite(hl, ((90 * S4 - hl.width) // 2, y))
            y += hl.height + 4 * S4
        return img


class PreviewCard(Card):
    def __init__(self, episode_no, title, lines, seed=0):
        super().__init__((4, 6, 14), seed)
        self.no = episode_no
        self.title = title
        self.lines = lines

    def frame(self, t):
        img, d = self._base(t)
        h1 = ptext_fit("NEXT EPISODE", col=(255, 210, 110), scales=(4, 3, 2), maxw=W - 20)
        img.alpha_composite(h1, ((W - h1.width) // 2, 26))
        h2 = ptext_fit(f"EPISODE {self.no:03d} - '{self.title}'", col=(140, 220, 255),
                       scales=(2, 1), maxw=W - 24)
        img.alpha_composite(h2, ((W - h2.width) // 2, 26 + h1.height + 10))
        y = 26 + h1.height + 30
        for ln in self.lines:
            tt = ptext_fit(ln, col=(210, 210, 220), scales=(1,), maxw=W - 30)
            img.alpha_composite(tt, ((W - tt.width) // 2, y))
            y += tt.height + 6
        fade = ptext_fit("The static is listening.", col=(120, 120, 140), maxw=W - 40)
        img.alpha_composite(fade, ((W - fade.width) // 2, y + 6))
        return img


# ===========================================================================
# FX & KAMERA
# ===========================================================================
def apply_camera(img, t, ops):
    """ops: zoom/pan/shake/letterbox. Returnerar (320x180)-bild."""
    d = ImageDraw.Draw(img, "RGBA")
    for op in ops:
        k = op["kind"]
        if k == "tilt":
            deg = op.get("deg", 2.0)
            img = img.rotate(deg, resample=NEAREST, fillcolor=(0, 0, 0, 255))
            d = ImageDraw.Draw(img, "RGBA")
        elif k == "zoom":
            z = op["z"](t) if callable(op["z"]) else op["z"]
            if z > 1.001:
                fx, fy = op.get("focus", (W // 2, H // 2))
                cw, ch = W / z, H / z
                x0 = min(max(fx - cw / 2, 0), W - cw)
                y0 = min(max(fy - ch / 2, 0), H - ch)
                img = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), NEAREST)
                d = ImageDraw.Draw(img, "RGBA")
        elif k == "shake":
            t0, t1, amp = op["t0"], op["t1"], op.get("amp", 3)
            if t0 <= t <= t1:
                dx = int(math.sin(t * 47.0) * amp)
                dy = int(math.cos(t * 39.0) * amp * 0.6)
                img = ImageOps.expand(img, border=amp, fill=(0, 0, 0, 255)).crop(
                    (amp - dx, amp - dy, amp - dx + W, amp - dy + H))
                d = ImageDraw.Draw(img, "RGBA")
    for op in ops:                       # letterbox SIST
        if op["kind"] == "letterbox":
            hgt = op.get("h", 14)
            d.rectangle([0, 0, W, hgt], fill=(0, 0, 0, 255))
            d.rectangle([0, H - hgt, W, H], fill=(0, 0, 0, 255))
    return img


def fireflies(img, t, n=9, seed=7):
    """Svävande glöd-punkter över kajen (16-bit-natt)."""
    import random as _rnd
    rnd = _rnd.Random(seed)
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(n):
        bx, by = rnd.uniform(12, 308), rnd.uniform(46, 142)
        ph, sp = rnd.uniform(0, 6.28), rnd.uniform(0.35, 0.9)
        x = bx + math.sin(t * sp + ph) * 16
        y = by + math.cos(t * sp * 0.7 + ph * 2) * 7
        a = int(110 + 110 * math.sin(t * 1.9 * sp + ph))
        if a <= 25:
            continue
        d.point((int(x), int(y)), fill=(255, 240, 170, min(255, a + 40)))
        if a > 140:
            d.point((int(x) + 1, int(y)), fill=(255, 240, 170, a - 120))




# =========================================================================== #
# MIMI — huvudkaraktärens söta katt. Liten egen rigg (14x11 px) som följer.   #
# =========================================================================== #
NEKO_W, NEKO_H = 14, 11


def _neko_paint(d, pose, tail_ph, blink=False):
    """Målar Mimi i en 14x11-canvas. pose: sit/walk1/walk2. Fötter på y=10."""
    body = (235, 150, 62, 255)
    white = (252, 244, 234, 255)
    dark = (28, 22, 18, 255)
    pink = (238, 115, 120, 255)
    # svans: upprullad, gungar med fas
    tx = 1 + int(round(tail_ph))
    d.line([(2, 6), (tx, 3)], fill=body, width=1)
    if pose != "sit":
        d.point((tx - 1, 2), fill=white)
        d.point((tx, 2), fill=body)
    # kropp
    if pose == "walk2":
        d.rectangle([3, 6, 9, 8], fill=body)
        d.rectangle([4, 8, 8, 9], fill=white)
    elif pose == "walk1":
        d.rectangle([3, 6, 9, 8], fill=body)
        d.rectangle([4, 7, 8, 9], fill=white)
    else:  # sit: högre, svansen lindad fram
        d.rectangle([3, 4, 9, 9], fill=body)
        d.rectangle([4, 7, 8, 10], fill=white)
        d.line([(9, 10), (12, 10)], fill=body)
        d.point((12, 9), fill=body)
    # ben
    if pose == "walk1":
        d.rectangle([4, 9, 4, 11], fill=body); d.rectangle([8, 9, 8, 10], fill=body)
    elif pose == "walk2":
        d.rectangle([4, 9, 4, 10], fill=body); d.rectangle([8, 9, 8, 11], fill=body)
    # huvud (framåt-höger i basläget)
    d.rectangle([8, 1, 13, 6], fill=body)                       # rundad noppe
    d.polygon([(8, 1), (9, -1), (10, 1)], fill=body)            # vänster öra
    d.polygon([(12, 1), (13, -1), (14 if False else 13, 2)], fill=body)  # höger öra
    d.point((9, 0), fill=pink)                                  # öronsnobb
    d.rectangle([8, 5, 13, 6], fill=white)                      # nos/mulle
    # ögon + nos
    if blink:
        d.point((10, 3), fill=dark); d.point((12, 3), fill=dark)
    else:
        d.rectangle([9, 2, 10, 3], fill=dark)
        d.point((9, 2), fill=(255, 255, 255, 255))              # glans!
        d.rectangle([12, 2, 12, 3], fill=dark)
        d.point((12, 2), fill=(255, 255, 255, 255))
    d.point((11, 4), fill=pink)                                 # nos
    # morrhår (en pixel-rad per sida)
    d.point((7, 4), fill=(210, 210, 220, 200))
    d.point((4, 5) if pose == "sit" else (7, 5), fill=(210, 210, 220, 160))


class Neko:
    """Söt liten katt: 2 gång-frames + sitt-idle + blink-schema."""

    def __init__(self):
        self.frames = {}
        for pose in ("sit", "walk1", "walk2"):
            for blink in (False, True):
                for tph in (-0.6, 0.6):
                    k = (pose, blink, tph)
                    c = Image.new("RGBA", (NEKO_W + 1, NEKO_H + 1), (0, 0, 0, 0))
                    dd = ImageDraw.Draw(c)
                    _neko_paint(dd, pose, tph, blink)
                    self.frames[k] = c
        self.seed = 0.7

    def sprite(self, t, moving):
        ph = t * 7.0
        pose = "sit"
        if moving:
            pose = "walk1" if int(ph) % 2 == 0 else "walk2"
        cyc = (t + self.seed) % 3.4
        blink = cyc < 0.14
        tph = 0.6 if int(t * 2.2) % 2 == 0 else -0.6
        return self.frames[(pose, blink, tph)]


def px_heart(img, x, y, col=(245, 110, 130, 255)):
    """3x2-pixelhjärta (mild vänskap-ikon över Mimi)."""
    d = ImageDraw.Draw(img, "RGBA")
    d.point((x, y), fill=col); d.point((x + 2, y), fill=col)
    d.point((x - 1, y + 1), fill=col); d.point((x, y + 1), fill=col)
    d.point((x + 1, y + 1), fill=col); d.point((x + 3, y + 1), fill=col)
    d.point((x, y + 2), fill=col); d.point((x + 2, y + 2), fill=col)
    d.point((x + 1, y + 3), fill=col)




# =========================================================================== #
# 9-5-MILJÖER: lägenhet, tågperrong, kontor, gatan (buss!), void              #
# =========================================================================== #
def portal(img, x, y, t, seed=0):
    """Pulserande grön multiversum-portal (BAKOM aktörer). Logiska koordinater."""
    d = ImageDraw.Draw(img, "RGBA")
    ph = t * 6.0 + seed * 2.1
    for i, rr in enumerate((30, 22, 14)):
        rx = rr + int(3 * math.sin(ph + i * 1.7))
        ry = int(rx * 1.5)
        col = ((40, 235, 130, 120), (90, 255, 170, 90), (160, 255, 210, 60))[i]
        d.ellipse([x - rx, y - ry, x + rx, y + ry], outline=col, width=2)
    for k in range(8):                            # swirl-damm i ellipsbana
        a = ph * 0.5 + k * 0.785
        d.point((x + int(math.cos(a) * 18), y + int(math.sin(a) * 27)),
                fill=(210, 255, 220, 200))
    d.ellipse([x - 9, y - 13, x + 9, y + 13], fill=(30, 90, 60, 70))


DINO_W, DINO_H = 76, 48


def _dino_paint(d, step, jaw, downed):
    """Cartoon T-rex som jagar HÖGER (spegla för vänster)."""
    G = (92, 130, 60); DG = (54, 84, 34); BG = (160, 180, 100)
    WT = (240, 240, 235); RD = (200, 60, 50)
    if downed:                                           # knockout: på sidan
        d.ellipse([10, 26, 58, 44], fill=G, outline=DG)  # kropp liggande
        d.polygon([(14, 36), (0, 30), (2, 40), (16, 42)], fill=G, outline=DG)  # svans
        d.rectangle([52, 20, 74, 34], fill=G, outline=DG)                      # huvud
        d.rectangle([62, 28, 76, 34], fill=G, outline=DG)                      # nos
        d.line([(56, 24), (59, 27)], fill=DG); d.line([(59, 24), (56, 27)], fill=DG)  # X-öga
        for k, (sx, sy) in enumerate(((64, 14), (70, 10), (58, 10))):          # svimmelstjärnor
            d.point((sx, sy), fill=(255, 235, 130, 255))
            d.point((sx + 1, sy + 1), fill=(255, 235, 130, 200))
        d.rectangle([20, 44, 30, 46], fill=DG)           # ben i vädret
        d.rectangle([36, 44, 46, 46], fill=DG)
        return
    d.polygon([(16, 26), (0, 18), (2, 30), (16, 32)], fill=G, outline=DG)      # svans
    d.ellipse([16, 14, 54, 34], fill=G, outline=DG)                            # kropp
    d.ellipse([22, 22, 50, 36], fill=BG)                                       # buk-patch
    for sx in (24, 32, 40):                                                    # ryggrand
        d.line([(sx, 15), (sx + 2, 20)], fill=DG)
    d.rectangle([46, 10, 56, 24], fill=G, outline=DG)                          # nacke
    d.rectangle([50, 2, 72, 15], fill=G, outline=DG)                           # huvud
    d.rectangle([62, 6, 76, 13], fill=G, outline=DG)                           # nos
    if jaw:                                                                    # öppet käk-gap!
        d.polygon([(62, 13), (76, 19), (74, 21), (62, 17)], fill=(150, 50, 44),
                  outline=DG)
        d.point((66, 18), fill=RD)                                             # tunga
        for tx in range(64, 74, 3):
            d.point((tx, 19), fill=WT)                                         # undertänder
    else:
        d.line([(62, 14), (75, 15)], fill=DG)
    for tx in range(64, 74, 3):                                                # överkäkständer
        d.point((tx, 13), fill=WT)
    d.rectangle([54, 4, 58, 8], fill=WT)                                       # öga
    d.rectangle([56, 5, 57, 6], fill=(16, 14, 18, 255))
    d.line([(53, 3), (60, 5)], fill=DG)                                        # arg bryn
    d.rectangle([46, 24, 49, 28], fill=G, outline=DG)                          # mini-arm!
    d.point((48, 29), fill=DG)
    s0 = -2 if step else 0; s1 = 0 if step else -2                             # ben-hopp
    d.rectangle([24, 34 + s0, 29, 44 + s0], fill=G, outline=DG)
    d.rectangle([22, 42 + s0, 30, 46 + s0], fill=G, outline=DG)
    d.rectangle([36, 34 + s1, 41, 44 + s1], fill=G, outline=DG)
    d.rectangle([34, 42 + s1, 42, 46 + s1], fill=G, outline=DG)


class Dino:
    """T-rex-jagare: 2 stegfaser x käke x nedslagen, cachade sprites."""

    def __init__(self):
        self.frames = {}
        for down in (False, True):
            for step in (0, 1):
                for jaw in (0, 1):
                    c = Image.new("RGBA", (DINO_W + 2, DINO_H + 2), (0, 0, 0, 0))
                    dd = ImageDraw.Draw(c)
                    _dino_paint(dd, step, jaw, down)
                    self.frames[(down, step, jaw)] = c

    def sprite(self, t, moving, roar=False, downed=False):
        step = int(t * 9) % 2 if moving else 0
        jaw = 1 if roar else (1 if (moving and int(t * 2) % 3 == 0) else 0)
        return self.frames[(downed, step, jaw)]


class ApartmentMorning:
    """Sovsälja: säng, rödh inte väckarklockan, fönstergryning."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self._build()

    def _build(self):
        self.bg = Image.new("RGB", (W, H), (58, 47, 40))
        d = ImageDraw.Draw(self.bg)
        for y in range(0, 128, 7):                     # gammal panel
            d.line([(0, y), (W, y)], fill=(50, 41, 34))
        d.rectangle([0, 128, W, H], fill=(96, 76, 56)) # mörgolv
        # säng (vänster)
        d.rectangle([8, 100, 88, 140], fill=(74, 88, 120))
        d.rectangle([8, 96, 18, 100], fill=(88, 102, 138))
        d.rectangle([14, 92, 44, 102], fill=(206, 200, 188))   # kudde
        d.rectangle([44, 98, 88, 136], fill=(60, 76, 110))     # täcke
        d.line([(8, 136), (88, 136)], fill=(30, 28, 34))
        # natthstands + väckarklocka (röda siffror)
        d.rectangle([94, 108, 116, 140], fill=(78, 60, 44))
        d.rectangle([100, 98, 110, 108], fill=(30, 30, 36))
        # fönster: förmorn-mörk med lampa på hus bortan
        d.rectangle([150, 22, 214, 70], fill=(64, 48, 36))
        d.rectangle([154, 26, 210, 66], fill=(14, 20, 44))
        for _ in range(8):
            d.point((self.rng.randrange(156, 210), self.rng.randrange(28, 66)), fill=(180, 188, 220))
        d.line([(182, 26), (182, 66)], fill=(64, 48, 36))
        # väggklocka (02:00-ish — trötthet)
        d.ellipse([262, 18, 282, 38], fill=(200, 196, 188), outline=(40, 36, 40))
        d.line([(272, 28), (272, 20)], fill=(30, 30, 34))
        d.line([(272, 28), (277, 30)], fill=(30, 30, 34))
        # poster: bordslandskap han aldrig ser (ironi)
        d.rectangle([236, 52, 272, 84], fill=(96, 130, 150))
        d.ellipse([246, 58, 262, 72], fill=(238, 224, 170))

    def frame(self, t):
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        # väckarklocka blinkar 06:00 i rött
        if int(t * 2) % 2 == 0:
            d.rectangle([102, 101, 108, 105], fill=(255, 60, 50, 255))
        else:
            d.rectangle([102, 101, 108, 105], fill=(120, 30, 28, 255))
        # dimmsoltråd från fönstret
        d.polygon([(154, 66), (210, 66), (232, 132), (180, 132)], fill=(150, 170, 220, 14))
        return img


class TrainPlatform:
    """Perrong: gult säkerhetsstreck, skylt 7:42, tåg som glider förbi."""

    def __init__(self, seed=0, train_t=None):
        self.rng = random.Random(seed)
        self.train_t = train_t          # när tåget sveper förbi (0.0-None)
        self._build()

    def _build(self):
        self.bg = Image.new("RGB", (W, H), (36, 40, 52))
        d = ImageDraw.Draw(self.bg)
        # tak + glödlampor
        d.rectangle([0, 0, W, 16], fill=(24, 26, 36))
        for lx in range(30, W, 60):
            d.line([(lx, 16), (lx, 20)], fill=(60, 62, 74))
            d.ellipse([lx - 3, 20, lx + 3, 26], fill=(250, 240, 190))
        # perrong-golv
        d.rectangle([0, 16, W, 152], fill=(66, 68, 82))
        d.rectangle([0, 130, W, 152], fill=(52, 54, 66))
        for x in range(0, W, 22):
            d.line([(x, 16), (x, 130)], fill=(56, 58, 70))
        # gul säkerhetslinje
        d.rectangle([0, 126, W, 130], fill=(214, 184, 60))
        # spår-aby
        d.rectangle([0, 152, W, H], fill=(18, 20, 28))
        for x in range(8, W, 26):
            d.rectangle([x, 152, x + 12, 160], fill=(30, 32, 42))
        d.line([(0, 158), (W, 158)], fill=(120, 122, 140), width=2)
        # skylt: 7:42 — alltid
        d.rectangle([220, 26, 284, 58], fill=(16, 20, 34), outline=(100, 108, 140), width=2)
        t = ptext("LINE 7 - 07:42", 2, (140, 200, 235))
        self.bg.paste(t, (228, 34), t)
        # affisch: semester irriterande nog
        d.rectangle([44, 30, 104, 86], fill=(206, 196, 180))
        d.polygon([(48, 76), (70, 46), (92, 76)], fill=(86, 120, 140))
        d.ellipse([56, 34, 74, 50], fill=(238, 224, 160))
        # bänk
        d.rectangle([140, 108, 186, 112], fill=(96, 82, 60))
        for bx in (142, 180):
            d.line([(bx, 112), (bx, 124)], fill=(72, 60, 44))

    def frame(self, t):
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        # tåget: glider in höger->vänster 0.55s fönster, gungar perr-bubblan
        if self.train_t is not None and self.train_t - 0.1 <= t <= self.train_t + 2.6:
            p = (t - self.train_t + 0.1) / 2.7
            xx = int(W + 20 - (W + 300) * p)
            # vagnkropp
            d.rectangle([xx, 40, xx + 240, 152], fill=(52, 70, 96))
            d.rectangle([xx, 40, xx + 240, 84], fill=(56, 82, 116))
            for wx in range(xx + 8, xx + 236, 18):
                d.rectangle([wx, 48, wx + 12, 74], fill=(224, 216, 180))
                if (wx // 18) % 3 == 0:                       # tomma vs fulla säten
                    d.rectangle([wx, 48, wx + 12, 74], fill=(40, 50, 72))
            for wx in range(xx + 8, xx + 236, 18):            # röret mellan fönster
                d.line([(wx + 14, 84), (wx + 14, 152)], fill=(40, 54, 76))
            d.rectangle([xx, 84, xx + 240, 152], outline=(30, 40, 58))
            d.rectangle([xx, 144, xx + 240, 152], fill=(36, 48, 66))
            # gung till perrong-märket som försvinner åt vänster
            d.ellipse([xx + 250, 92, xx + 262, 104], fill=(240, 238, 200))
        return img


class OfficeGrid:
    """Kontor: kubikelysning, rutinutskrifter, väggklocka med halvåldrande."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self._build()

    def _build(self):
        self.bg = Image.new("RGB", (W, H), (96, 100, 112))
        d = ImageDraw.Draw(self.bg)
        # kubik-skärmväggar
        for x in range(0, W, 40):
            d.rectangle([x + 2, 76, x + 38, 130], fill=(78, 82, 96))
            d.rectangle([x + 2, 76, x + 38, 130], outline=(64, 68, 80))
        # skärmkyн glowing
        self.screens = []
        for x in range(6, W - 24, 40):
            self.screens.append((x, 84))
            d.rectangle([x, 84, x + 22, 106], fill=(30, 40, 56))
            d.rectangle([x, 84, x + 22, 86], fill=(70, 90, 130))
        # stora fönstret höger: kvällsjus bortom
        d.rectangle([252, 8, 304, 60], fill=(76, 84, 108))
        d.rectangle([256, 12, 300, 56], fill=(18, 24, 46))
        for _ in range(12):
            d.point((self.rng.randrange(258, 300), self.rng.randrange(14, 54)),
                    fill=(200, 205, 235))
        d.line([(278, 12), (278, 56)], fill=(76, 84, 108))
        # väggklocka: 16:58, kort till fredag
        d.ellipse([30, 12, 56, 38], fill=(212, 208, 200), outline=(40, 40, 48))
        d.line([(43, 25), (43, 15)], fill=(34, 34, 40))
        d.line([(43, 25), (50, 28)], fill=(34, 34, 40))
        # taklamprör
        for lx in range(24, W, 56):
            d.line([(lx, 0), (lx, 10)], fill=(120, 124, 140))
            d.rectangle([lx - 8, 10, lx + 8, 14], fill=(240, 244, 250))

    def frame(self, t):
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        # skärmar flimrar (olika hastighet per monitor)
        for i, (x, y) in enumerate(self.screens):
            blink = (i * 131 + int(t * 3)) % 7
            if blink < 2:
                d.rectangle([x, y, x + 22, y + 22], fill=(24, 34, 48))
            d.line([(x + 2, y + 10), (x + rngline(x, i, t), y + 10)], fill=(90, 140, 190))
        # golvljusreflektion (platt plast)
        d.rectangle([0, 130, W, 152], fill=(86, 90, 102))
        return img


def rngline(x0, i, t):
    return x0 + 8 + (i * 5 + int(t * 4)) % 12


class StreetRain:
    """Kvällsgata: trottoar (ground=150=korsvägsl nedre?) + bussen vid t_hit."""

    def __init__(self, seed=0, hit_t=None, rain=True, green_t=None):
        self.rng = random.Random(seed)
        self.hit_t = hit_t
        self.rain = rain
        self.green_t = green_t          # explicit grönt-ljus-tid (oberoende av buss)
        self._build()

    def _build(self):
        self.bg = Image.new("RGB", (W, H), (14, 20, 34))
        d = ImageDraw.Draw(self.bg)
        # himmel: blåsvart
        for y in range(70):
            p = y / 69
            col = (int(_lerp(10, 22, p)), int(_lerp(16, 42, p)), int(_lerp(30, 58, p)))
            d.line([(0, y), (W, y)], fill=col)
        # hus-silhuetter + fönsterprickar
        for bx in range(0, W, 42):
            bh = self.rng.randrange(28, 56)
            d.rectangle([bx, 70 - bh, bx + 34, 74], fill=(22, 28, 42))
            for fy in range(70 - bh + 4, 68, 7):
                for fx in range(bx + 3, bx + 32, 6):
                    if self.rng.random() < 0.3:
                        d.point((fx, fy), fill=(240, 224, 160))
        # trottoar (där folk går: ground 150)
        d.rectangle([0, 74, W, 152], fill=(64, 60, 66))
        for x in range(0, W, 18):
            d.line([(x, 74), (x, 152)], fill=(54, 50, 56))
        # korsning: zebra från x=60 till 128 (buss banne landsväg)
        for zy in range(76, 150, 9):
            d.rectangle([60, zy, 128, zy + 5], fill=(210, 208, 202))
        # trafikljus på trottoaren (rött->grönt blink)
        d.line([(36, 74), (36, 108)], fill=(40, 40, 46))
        d.rectangle([30, 60, 42, 92], fill=(28, 28, 34), outline=(52, 52, 58))
        self.sig_x = 36
        # väg (under munnen 152)
        d.rectangle([0, 152, W, H], fill=(34, 34, 42))
        for x in range(20, W, 44):
            d.rectangle([x, 166, x + 16, 170], fill=(220, 220, 210))
        # gatlyktglöd
        d.line([(196, 74), (196, 110)], fill=(40, 40, 46))
        d.ellipse([192, 106, 200, 114], fill=(255, 240, 190))

    def frame(self, t):
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        # trafik: explicit green_t vinner; annars röd fram till hit-0.4
        if self.green_t is not None:
            is_red = t < self.green_t
        elif self.hit_t is not None:
            is_red = t < self.hit_t - 0.4
        else:
            is_red = False
        d.ellipse([32, 62, 40, 70],
                  fill=(235, 64, 54) if is_red else (60, 220, 90))
        # BUSSEN: rullar in höger->vänster vid hit_t-0.9, stannar INTE
        if self.hit_t is not None and self.hit_t - 0.95 <= t <= self.hit_t + 0.5:
            p = (t - (self.hit_t - 0.95)) / 1.45
            xx = int(W + 30 - (W + 420) * p)
            d.rectangle([xx, 86, xx + 240, 152], fill=(96, 148, 178))
            d.rectangle([xx, 86, xx + 240, 152], outline=(50, 86, 118), width=2)
            d.rectangle([xx, 86, xx + 240, 120], fill=(60, 104, 136))
            for wx in range(xx + 10, xx + 232, 20):
                d.rectangle([wx, 92, wx + 14, 114], fill=(236, 228, 190))
                if (wx // 20) % 4 == 0:
                    d.rectangle([wx, 92, wx + 14, 114], fill=(26, 34, 46))
            d.rectangle([xx + 230, 122, xx + 240, 152], fill=(70, 120, 150))   # förarens fönster
            for wx in (xx + 8, xx + 200):
                d.ellipse([wx, 146, wx + 14, 152], fill=(20, 22, 26))
            # strålkastare: raseri-kon
            d.polygon([(xx - 2, 116), (xx - 46, 150), (xx - 46, 128)], fill=(255, 236, 160, 90))
            d.point((xx + 2, 116), fill=(255, 250, 210))
        if self.rain:
            for i in range(80):
                rng = random.Random(i)
                xx = rng.randrange(W + 40); sp = 190 + (i % 5) * 30
                yy = (rng.randrange(H) + t * sp) % H
                xx2 = xx - int((H - yy) * 0.18)
                d.line([(xx2, yy), (xx2 - 2, yy + 6)], fill=(160, 190, 220, 110))
        return img


class VoidWhite:
    """Reboot-rummet: allt vitt, en enda glödande pil/"orb"."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def frame(self, t):
        img = Image.new("RGB", (W, H), (238, 240, 246))
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy = 160, 90
        r0 = 120 - min(40, int(t * 14))
        # mjuk cirkel-glow
        for rr in range(r0, 0, -18):
            d.ellipse([cx - rr, cy - rr // 2, cx + rr, cy + rr // 2],
                      fill=(226, 232, 244, 12))
        # flytande punkter (damm-stjärnor)
        for i in range(24):
            rng2 = random.Random(i * 7)
            xx = (rng2.randrange(W) + int(t * (4 + i % 3))) % W
            yy = rng2.randrange(H)
            d.point((xx, yy), fill=(190, 200, 220, 130))
        return img.convert("RGBA")


def speedlines(img, cx, cy, n=26, col=(255, 255, 255, 120)):
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(n):
        a = i * (2 * math.pi / n) + 0.13
        r0 = 26 + (i % 4) * 7
        r1 = r0 + 40 + (i % 5) * 12
        d.line([(cx + int(math.cos(a) * r0), cy + int(math.sin(a) * r0)),
                (cx + int(math.cos(a) * r1), cy + int(math.sin(a) * r1))], fill=col, width=1)


def kiai(img, cx, cy, n=12):
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(n):
        a = i * (2 * math.pi / n)
        r0, r1 = 30, 90 + (i % 3) * 20
        col = [(255, 120, 60, 160), (255, 200, 90, 150), (255, 255, 255, 140)][i % 3]
        d.line([(cx + int(math.cos(a) * r0), cy + int(math.sin(a) * r0)),
                (cx + int(math.cos(a) * r1), cy + int(math.sin(a) * r1))], fill=col, width=3)


def aura(img, x, y_base, hgt, t, hue="violet"):
    """Eld-flamma runt karaktären: rader med flicker, genomskinlig = hjälten syns."""
    d = ImageDraw.Draw(img, "RGBA")
    pal = {"violet": [(150, 90, 235, 120), (190, 140, 255, 100), (245, 230, 255, 165)],
           "gold":   [(255, 170, 60, 120), (255, 215, 110, 100), (255, 248, 210, 165)]}[hue]
    rows = int(hgt)
    for i, c in enumerate(pal):
        wscale = (9 - i * 3) * 1.15
        step = 2
        for r in range(0, rows, step):
            p = r / rows
            base_w = wscale * (1.0 - p ** 1.5) + 1.5
            fl = math.sin(t * 11.0 + r * 0.35 + i * 2.4) * (1.5 + p * 3.0)
            xx = x + int(math.sin(t * 7 + r * 0.2) * p * 2.0)
            wdt = max(1, int(base_w + fl))
            y0 = y_base - r - step
            d.rectangle([xx - wdt, y0, xx + wdt, y0 + step - 1], fill=c)
        for k in range(3):
            rng = random.Random(k * 7 + int(t * 6))
            tip = y_base - int(hgt * (0.5 + 0.45 * rng.random()))
            xo = x + rng.randrange(-6, 7)
            d.line([(xo, tip + 8), (xo + rng.randrange(-3, 4), tip)], fill=c, width=2)
    for i in range(6):
        rng = random.Random(i)
        yy = y_base - ((t * 34 + rng.randrange(int(hgt))) % (hgt + 10))
        d.point((x + rng.randrange(-9, 9), yy), fill=(255, 255, 255, 210))




def blood(img, x, y, t0, t):
    """Stiliserad anime-blodskvätt: radiala partiklar + kvarvarande fläck på marken.
    t0..t0+0.38: explosion; därefter bestående spill + pool under fallets plats."""
    d = ImageDraw.Draw(img, "RGBA")
    dark = (128, 16, 22, 230)
    mid = (186, 24, 30, 220)
    hot = (224, 52, 44, 200)
    dt = t - t0
    if dt < 0:
        return
    p = min(1.0, dt / 0.38)
    rng = random.Random(9)
    # partiklar utåt (buss: flest uppåt-åt-skadad sida)
    for i in range(30):
        ang = -math.pi * 0.85 + (i / 29) * math.pi * 1.2
        dist = (14 + rng.random() * 30) * (0.25 + p * 0.97)
        xx = x + int(math.cos(ang) * dist)
        yy = y - int(abs(math.sin(ang)) * dist * 0.8)
        col = hot if i % 3 == 0 else (mid if i % 2 == 0 else dark)
        sz = 1 + (1 if (i + int(dt * 20)) % 5 == 0 else 0)
        d.rectangle([xx, yy, xx + sz, yy + sz], fill=col)
    # stänk på bussjем/ytan (persistens efter 0.15s)
    if dt > 0.15:
        for k in range(9):
            xo = x - 12 + (k * 7) % 20
            yo = y - 6 - (k * 11) % 22
            d.rectangle([xo, yo, xo + 2, yo + 2], fill=dark)
        d.ellipse([x - 3, y + 1, x + 16, y + 7], fill=(118, 14, 18, 200))   # pool börjar

def dust(img, x, y, n=7):
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(n):
        rng = random.Random(i * 7)
        x0 = x + rng.randrange(-16, 14)
        y0 = y + rng.randrange(-9, 3)
        d.ellipse([x0, y0, x0 + 5, y0 + 4], fill=(120, 110, 100, 90))


def slash(img, x, y, t0, t):
    if not (t0 <= t <= t0 + 0.35):
        return
    d = ImageDraw.Draw(img, "RGBA")
    p = (t - t0) / 0.35
    ln = int(60 * math.sin(math.pi * min(1.0, p * 1.35)))
    d.line([(x - ln, y + ln // 2), (x + ln, y - ln // 2)], fill=(255, 255, 255, 230), width=2)
    d.line([(x - ln, y + ln // 2 + 2), (x + ln, y - ln // 2 + 2)], fill=(150, 230, 255, 150), width=1)


def word_burst(img, word, x, y, t0, t, col=(255, 235, 120)):
    if not (t0 <= t <= t0 + 0.9):
        return
    p = (t - t0) / 0.9
    scl = max(1, int(_lerp(2, 5, min(1.0, p * 4)) + math.sin(p * 26)))
    tt = ptext(word, scale=scl, col=col)
    img.alpha_composite(tt, (x - tt.width // 2 + int(math.sin(p * 33) * 2),
                             y - tt.height // 2 + int(p * 6)))


def impact_flash(img, t0, t, invert=False):
    p = (t - t0) / 0.22
    if 0 <= p <= 1:
        if invert and p < 0.5:
            rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
            Image.fromarray(255 - rgb, "RGB").convert("RGBA")
            arr = Image.fromarray(255 - rgb, "RGB").convert("RGBA")
            return Image.blend(img.convert("RGB"), arr.convert("RGB"), min(1.0, p * 2)).convert("RGBA")
        white = Image.new("RGBA", img.size, (255, 255, 255, 255))
        return Image.blend(img, white, (1 - p) * 0.92)
    return img


# ===========================================================================
# v3 REAL ANIME RIG – skelett-kapsel-kropp (animeproportioner, INTE chibi)
# + detaljerat animehuvud (iris, glans, ögonfrans, bryn, näsa)
# ===========================================================================
from PIL import ImageChops

BODY_CV_W, BODY_CV_H = 56, 92
GROUND_CV = 88            # lokala y=0 (golv) mappar hit
JW, JW2 = 5, 4            # kapseltjocklekar


def _cap(d, p0, p1, col, wdt, outl):
    if outl:
        d.line([(p0[0], p0[1]), (p1[0], p1[1])], fill=outl, width=wdt + 2)
    d.line([(p0[0], p0[1]), (p1[0], p1[1])], fill=col, width=wdt)
    r = wdt / 2
    for p in (p0, p1):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)


def _stand():
    """Lokala leder, +x = framåt (höger), +y = UPPÅT från golvyta 0."""
    return {
        "footL": (-5, 0), "footR": (5, 0),
        "kneeL": (-5, 15), "kneeR": (5, 15),
        "hipL": (-3, 29), "hipR": (3, 29),
        "pelvis": (0, 30),
        "shoulderL": (-8, 54), "shoulderR": (8, 54),
        "elbowL": (-10, 42), "elbowR": (10, 42),
        "handL": (-10, 31), "handR": (10, 31),
        "neck": (0, 56),
    }


def _mid(a, b, f=0.5):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def joints_for(pose, t):
    j = _stand()
    if pose in ("walk", "run"):
        run = pose == "run"
        ph = 2 * math.pi * (t * (2.0 if run else 1.25))
        sw = 11.0 if run else 7.0
        j["footL"] = (-5 + sw * math.sin(ph), max(0.0, 2.6 * math.cos(ph - 0.5)))
        j["footR"] = (5 - sw * math.sin(ph), max(0.0, 2.6 * math.cos(ph + math.pi - 0.5)))
        for side in ("L", "R"):
            hip = j["hip" + side]; foot = j["foot" + side]
            kneed = _mid(hip, foot)
            j["knee" + side] = (kneed[0] - (3.0 if not run else 4.5),
                                kneed[1] + 1.5 + foot[1] * 0.4)
        j["handL"] = (-10 - sw * 0.8 * math.sin(ph), 31 + 2 * math.sin(ph))
        j["handR"] = (10 + sw * 0.8 * math.sin(ph), 31 + 2 * math.sin(ph + math.pi))
        j["elbowL"] = _mid(j["shoulderL"], j["handL"], 0.55)
        j["elbowR"] = _mid(j["shoulderR"], j["handR"], 0.55)
        bob = (2.6 if run else 1.4) * abs(math.sin(ph))
        for k in ("pelvis", "shoulderL", "shoulderR", "hipL", "hipR", "neck",
                  "elbowL", "elbowR", "handL", "handR"):
            j[k] = (j[k][0], j[k][1] - bob)
        if run:
            for k in ("shoulderL", "shoulderR", "neck"):
                j[k] = (j[k][0] + 4, j[k][1] - 1)
    elif pose == "punch":
        j["elbowR"] = (11, 56)
        j["handR"] = (23, 57)
        j["handL"] = (2, 43)
        j["elbowL"] = (-6, 46)
        for k in ("shoulderL", "shoulderR", "neck", "pelvis"):
            j[k] = (j[k][0] + 3, j[k][1])
        j["footR"] = (10, 0)
        j["kneeR"] = (6, 14)
    elif pose == "hurt":
        j["handL"] = (-15, 60)
        j["handR"] = (3, 66)
        j["elbowL"] = (-12, 52)
        j["elbowR"] = (6, 58)
        for k in ("shoulderL", "shoulderR", "neck"):
            j[k] = (j[k][0] - 4, j[k][1] + (2 if k == "neck" else 0))
        j["footR"] = (11, 0)
        j["kneeR"] = (8, 13)
    elif pose == "point":
        j["handR"] = (15, 64)
        j["elbowR"] = (11, 59)
    elif pose == "guard":
        j["handL"] = (4, 50)
        j["handR"] = (0, 52)
        j["elbowL"] = (-11, 45)
        j["elbowR"] = (11, 46)
    else:  # idle: andning
        b = math.sin(t * 2.0) * 0.8
        for k in ("shoulderL", "shoulderR", "neck"):
            j[k] = (j[k][0], j[k][1] - b)
    return j


class Suit:
    """Outfit-färger + KROPPSBYGGNAD per person (muskler/kurvor/siluett)."""
    def __init__(self, jacket, pants, boots, skin, outl=(18, 16, 24),
                 arm_w=5, leg_t=1.0, tor_w=11, hips=8, bust=0, pads=0):
        self.jacket, self.pants, self.boots, self.skin, self.outl = \
            jacket, pants, boots, skin, outl
        self.arm_w, self.leg_t = arm_w, leg_t      # arm/ben-tjocklek (muskler)
        self.tor_w, self.hips = tor_w, hips        # torso-bredd / höft-bredd
        self.bust, self.pads = bust, pads          # byst (0/1/2) / axelpads


def _dk(c, f=0.62):
    """Skugg-ton: 16-bit hue-shift — drar mot KALLT (blå-lila) när den mörknar."""
    r, g, b = c[:3]
    return (max(0, int(r * f * 0.92)),
            max(0, int(g * f * 0.96)),
            min(255, int(b * f + (255 - b) * 0.055)))


def draw_body(img, suit, j, scale=1.0):
    """Ritar kapsel-kroppen i en 56x92-canvas. Bakre->främre."""
    # v6: SILHUETT-förändring av ledena själva (ingen overlay-linje = rena former)
    jm = dict(j)
    if suit.bust >= 1:                      # TIMGLAS: höfter/lår ut, axlar in
        for k in ("hipL", "hipR"):
            xx, yy = jm[k]; jm[k] = (xx - 3 if k.endswith("L") else xx + 3, yy)
        for k in ("kneeL", "kneeR"):
            xx, yy = jm[k]; jm[k] = (xx - 2 if k.endswith("L") else xx + 2, yy)
        for k in ("shoulderL", "shoulderR"):
            xx, yy = jm[k]; jm[k] = (xx + 2 if k.endswith("L") else xx - 2, yy)
    elif suit.arm_w >= 6:                   # V-SILHUETT: smala höfter, breda axlar
        for k in ("shoulderL", "shoulderR"):
            xx, yy = jm[k]; jm[k] = (xx - 2 if k.endswith("L") else xx + 2, yy)
        for k in ("hipL", "hipR"):
            xx, yy = jm[k]; jm[k] = (xx + 1 if k.endswith("L") else xx - 1, yy)
    j = jm
    d = ImageDraw.Draw(img)
    ox, oy = BODY_CV_W // 2, GROUND_CV

    def P(name):
        x, y = j[name]
        return (ox + int(x * scale), oy - int(y * scale))

    out = suit.outl
    shL, shR = P("shoulderL"), P("shoulderR")
    hipL, hipR = P("hipL"), P("hipR")
    knL, knR = P("kneeL"), P("kneeR")
    ftL, ftR = P("footL"), P("footR")
    # ben: bakre (vänster) mörkare
    for (hip, kn, ft, colp) in ((hipL, knL, ftL, _dk(suit.pants)),
                                (hipR, knR, ftR, suit.pants)):
        _cap(d, hip, kn, colp, int(JW * suit.leg_t * scale), out)
        _cap(d, kn, ft, colp, int(JW2 * suit.leg_t * scale), out)
        # boot: box + tå
        bx, by = ft
        d.rectangle([bx - 3, by - 5, bx + 4, by], fill=out)
        d.rectangle([bx - 2, by - 4, bx + 3, by - 1], fill=suit.boots)
        d.rectangle([bx + 3, by - 4, bx + 6 + (1 if ft is ftR else 0), by - 2], fill=suit.boots)
        d.line([(bx + 3, by - 3), (bx + 6, by - 2)], fill=out)
    # bälte/bäcken
    d.ellipse([P("pelvis")[0] - suit.hips, P("pelvis")[1] - 4,
               P("pelvis")[0] + suit.hips, P("pelvis")[1] + 4], fill=suit.pants)
    # torso (kapsel-axlar + kapsel-kropp, bredd per karaktär)
    _cap(d, hipL, hipR, suit.jacket, int(max(4, suit.tor_w - 2) * scale), out)
    _cap(d, shL, shR, suit.jacket, int(max(4, suit.tor_w - 3) * scale), out)
    _cap(d, P("pelvis"), P("neck"), suit.jacket, int(suit.tor_w * scale), out)
    # BYST-kurvor (valfritt, nivå 1-2): större/rundare lobes + klyft + toppglans
    if suit.bust >= 1:
        cx0 = (shL[0] + shR[0]) // 2
        cy0 = shL[1] + 7
        rr = 3 + suit.bust
        for bx0 in (cx0 - 4, cx0 + 4):
            d.ellipse([bx0 - rr, cy0 - rr, bx0 + rr, cy0 + rr - 1],
                      fill=suit.jacket, outline=out)
            d.point((bx0 - rr // 2, cy0 - rr + 1),
                    fill=tuple(min(255, int(v * 1.35)) for v in suit.jacket[:3]))
        d.line([(cx0, cy0 - rr + 2), (cx0, cy0 + 1)], fill=_dk(suit.jacket, 0.58))
    # PEC-linje for stora killarna (2 subtila skaror under kragen)
    if suit.arm_w >= 6 and suit.bust == 0:
        pcx = (shL[0] + shR[0]) // 2
        pc0 = shL[1] + 7
        for pxx in (pcx - 3, pcx + 2):
            d.line([(pxx, pc0), (pxx + 2, pc0)], fill=_dk(suit.jacket, 0.66))
    # AXELPADS (valfritt, skurk-rymbd)
    if suit.pads:
        for shx in (shL[0], shR[0]):
            d.rectangle([shx - 4, shL[1] - 7, shx + 4, shL[1] - 1],
                        fill=_dk(suit.jacket, 0.9), outline=out)
            d.point((shx - 4, shL[1] - 7), fill=suit.boots)
    # 3-tons-rampa: höger sida mörkare, vänster kant glans (ljus från vänster)
    _cap(d, (P("pelvis")[0] + 7, P("pelvis")[1]), (shR[0] + 2, shR[1]),
         _dk(suit.jacket, 0.8), int(6 * scale), _dk(suit.jacket, 0.8))
    _cap(d, (P("pelvis")[0] - 8, P("pelvis")[1] + 1), (shL[0] + 1, shL[1] + 1),
         tuple(min(255, int(v * 1.22)) for v in suit.jacket[:3]), int(3 * scale),
         tuple(min(255, int(v * 1.22)) for v in suit.jacket[:3]))
    # ärm-muddar + skärp + spänne + stövelkanter (16-bit-trim)
    cuff = tuple(min(255, int(v * 1.35)) for v in suit.jacket[:3])
    for hx, hy in (P("handL"), P("handR")):
        d.line([(hx - 3, hy - 3), (hx + 3, hy - 3)], fill=cuff)
    pvx, pvy = P("pelvis")
    d.line([(pvx - suit.hips, pvy - 2), (pvx + suit.hips, pvy - 2)],
           fill=_dk(suit.pants, 0.7))
    d.point((pvx, pvy - 2), fill=(214, 192, 122))                    # spänne
    for ftx, fty in (ftL, ftR):
        d.line([(ftx - 3, fty - 5), (ftx + 4, fty - 5)],
               fill=tuple(min(255, int(v * 1.3)) for v in suit.boots[:3]))
    # krage + dragkedja
    nx, ny = P("neck")
    d.polygon([(nx - 5, ny + 2), (nx, ny - 3), (nx + 5, ny + 2)], fill=_dk(suit.jacket, 0.8))
    d.line([(nx, ny + 2), (nx, P("pelvis")[1] + 2)], fill=_dk(suit.jacket, 0.7))
    # armar (tjocklek = muskler per karaktär)
    aw = int(suit.arm_w * scale)
    for (sh, el, hd, cols_) in ((shL, P("elbowL"), P("handL"), _dk(suit.jacket)),
                                (shR, P("elbowR"), P("handR"), suit.jacket)):
        _cap(d, sh, el, cols_, aw, out)
        _cap(d, el, hd, cols_, max(2, aw - 1), out)
        hx, hy = hd
        d.rectangle([hx - 2, hy - 2, hx + 2, hy + 2], fill=suit.skin)
        d.rectangle([hx - 2, hy - 2, hx + 2, hy + 2], outline=out)



# ---------------------------------------------------------------------------
# ANIMEHUVUD 26x24 – ansiktsupplägg ritas dynamiskt per frame
# ---------------------------------------------------------------------------
def _lt(c, f=1.25):
    """Ljus-ton: 16-bit hue-shift — drar mot VARMT (gult) när den ljusnar."""
    r, g, b = c[:3]
    return (min(255, int(r * f + (255 - r) * 0.07)),
            min(255, int(g * f + (255 - g) * 0.05)),
            max(0, int(b * f * 0.90)))


def _base_head(skin, out):
    # canvas 34x34 (+5 pixlar ovanför gamla 30-ramen: hårtopparna får plats)
    h = Image.new("RGBA", (34, 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(h)
    dk = _dk(skin, 0.82)
    d.polygon([(17, 33), (8, 30), (5, 23), (5, 13), (29, 13), (29, 23), (26, 30)], fill=skin)
    # skugg-sida (höger kant, ljuset kommer vänsterifrån) + käkskugga
    d.polygon([(27, 14), (29, 14), (28, 21), (28, 26), (27, 26)], fill=dk)
    d.polygon([(23, 28), (26, 30), (17, 33)], fill=dk)
    d.line([(9, 30), (16, 32)], fill=dk)
    # öra
    d.rectangle([4, 17, 5, 21], fill=skin)
    d.point((4, 18), fill=dk)
    return h


def _hair(d, style, col, out):
    dk = _dk(col, 0.78)
    lt = _lt(col)
    if style == "spiky":
        d.polygon([(2, 16), (4, 7), (8, 11), (11, 4), (15, 10), (18, 3), (21, 9),
                   (25, 4), (28, 10), (31, 6), (33, 15), (30, 11), (17, 8), (4, 11)], fill=col)
        d.polygon([(4, 11), (17, 8), (30, 11), (32, 14), (30, 13), (17, 10), (5, 13), (2, 16)],
                  fill=dk)
        d.line([(6, 14), (10, 12)], fill=dk)
        d.line([(24, 12), (28, 14)], fill=dk)
        d.point((12, 7), fill=lt); d.point((19, 6), fill=lt)
        # slingor (strå-detaljer)
        d.line([(7, 9), (9, 5)], fill=lt)
        d.line([(16, 10), (17, 5)], fill=dk)
        d.line([(26, 10), (24, 5)], fill=lt)
    elif style == "long":
        d.polygon([(1, 17), (4, 6), (17, 3), (30, 6), (33, 17), (29, 12), (17, 9), (5, 12)],
                  fill=col)
        d.polygon([(1, 17), (5, 12), (5, 32), (2, 29)], fill=dk)
        d.polygon([(33, 17), (29, 12), (29, 32), (32, 29)], fill=dk)
        d.polygon([(5, 12), (17, 9), (29, 12), (28, 13), (17, 11), (6, 13)], fill=dk)
        d.line([(12, 8), (12, 12)], fill=dk)
        d.line([(22, 8), (22, 12)], fill=dk)
        # slingor
        d.line([(8, 10), (7, 18)], fill=lt)
        d.line([(26, 10), (27, 18)], fill=dk)
        d.line([(15, 11), (15, 15)], fill=lt)
        d.line([(4, 20), (4, 27)], fill=lt)
        d.line([(30, 20), (30, 27)], fill=dk)
    elif style == "pony":
        d.polygon([(2, 16), (4, 6), (17, 3), (30, 6), (32, 16), (28, 11), (17, 8), (6, 11)],
                  fill=col)
        d.polygon([(3, 8), (-1, 15), (0, 29), (4, 25), (4, 15)], fill=dk)
        d.polygon([(29, 9), (33, 14), (32, 17)], fill=col)
        d.polygon([(6, 11), (17, 8), (28, 11), (27, 12), (17, 10), (7, 12)], fill=dk)
        d.line([(8, 12), (12, 10)], fill=dk)
        d.point((14, 7), fill=lt)
        # slingor
        d.line([(6, 12), (4, 18)], fill=lt)
        d.line([(17, 9), (17, 12)], fill=dk)
        d.line([(1, 16), (1, 24)], fill=lt)
    elif style == "hawk":
        d.polygon([(11, 13), (12, 2), (17, 0), (22, 2), (23, 13), (20, 8), (14, 8)], fill=col)
        d.line([(13, 5), (21, 5)], fill=dk)
        d.point((18, 3), fill=lt)
        d.line([(14, 7), (13, 12)], fill=lt)
        d.line([(20, 7), (21, 12)], fill=dk)


EK_SHAPES = {
    # hw=halvbredd box, top/bot vertikala gränser, iw=irisbredd, lash=övre-frans-typ
    "default": dict(hw=3, top=-4, bot=3, iw=2, lash="line"),
    "sharp":   dict(hw=3, top=-3, bot=2, iw=2, lash="slant"),
    "big":     dict(hw=4, top=-5, bot=4, iw=3, lash="thick"),
    "soft":    dict(hw=3, top=-4, bot=4, iw=3, lash="none"),
    "small":   dict(hw=2, top=-2, bot=2, iw=2, lash="ridge"),
    "slit":    dict(hw=3, top=-1, bot=1, iw=0, lash="slit"),
}


def make_head_images(cols, hair_style, iris, eyes_kind="default", gaze=0):
    skin, out = cols["S"], cols["K"]
    white = (255, 255, 255, 255)
    ek = EK_SHAPES.get(eyes_kind, EK_SHAPES["default"])
    hw, etop, ebot, iw, lash = ek["hw"], ek["top"], ek["bot"], ek["iw"], ek["lash"]

    heads = {}
    for state in ("normal", "blink", "wide", "angry", "x", "spark", "sad", "whiteout",
                  "happy"):
        im = _base_head(skin, out)
        d = ImageDraw.Draw(im)
        # v5.1: SOLID månad/topp så INGET genomskinligt "hål" kan uppstå i frisen
        d.rectangle([3, 1, 31, 13], fill=cols["H"] + (255,))
        _hair(d, hair_style, cols["H"], out)
        # hårfäst-skugga (anime-tell): mörk hudrand längs frisans
        # kort hårfäst-skugga direkt under luggen (inte grå-rand över hela pannan!)
        d.line([(8, 13), (26, 13)], fill=_dk(cols["H"], 0.55) + (255,))
        # v5: anime-hårskimra (cel ljusbåge, dubbelgradig)
        d.arc([5, 1, 27, 17], 195, 340, fill=_lt(cols["H"], 1.5) + (255,), width=2)
        d.arc([8, 3, 24, 14], 210, 330, fill=_lt(cols["H"], 1.22) + (255,), width=1)

        def rm_eye(cx, cy, side):
            """Rick&Morty-öga: stor vit oval + liten pupill som vandrar med gaze."""
            dx = int(gaze) * 2
            if state == "blink":
                d.line([(cx - 4, cy), (cx + 3, cy)], fill=out, width=1)
                return
            if state == "x":
                d.line([(cx - 3, cy - 3), (cx + 2, cy + 3)], fill=out)
                d.line([(cx + 2, cy - 3), (cx - 3, cy + 3)], fill=out)
                return
            if state == "happy":
                d.arc([cx - 4, cy - 4, cx + 3, cy + 3], 190, 350, fill=out, width=1)
                return
            if state == "spark":
                for ddx, ddy in ((0, -4), (-3, -1), (2, -1), (-2, 2), (1, 2), (0, 4)):
                    d.point((cx + ddx, cy + ddy), fill=(120, 220, 255, 255))
                return
            ry = 5 if state in ("wide", "whiteout") else 4
            d.ellipse([cx - 4, cy - ry, cx + 3, cy + ry], fill=white, outline=out)
            if state == "angry":
                d.line([(cx - 4, cy - ry), (cx + 3, cy - 1 - ry // 2)], fill=out)
            if state == "sad":
                d.line([(cx - 4, cy - ry), (cx + 3, cy - ry + 3)], fill=out)
            if state != "whiteout":                       # RM-pupill: litet svart kludd
                d.rectangle([cx + dx - 1, cy - 1, cx + dx, cy + 1],
                            fill=(16, 14, 18, 255))
                d.point((cx + dx - 1, cy - 1), fill=(70, 70, 80, 255))

        def eye(cx, cy, side):
            if eyes_kind == "rm":
                rm_eye(cx, cy, side)
                return
            if state == "blink":
                d.line([(cx - 3, cy), (cx + 2, cy)], fill=out, width=1)
                return
            if state == "x":
                d.line([(cx - 3, cy - 3), (cx + 2, cy + 3)], fill=out)
                d.line([(cx + 2, cy - 3), (cx - 3, cy + 3)], fill=out)
                return
            if state == "happy":                    # ^^ skrattbågar
                d.arc([cx - 3, cy - 4, cx + 3, cy + 2], 190, 350, fill=out, width=1)
                return
            if state == "spark":
                for dx, dy in ((0, -4), (-3, -1), (2, -1), (-2, 2), (1, 2), (0, 4)):
                    d.point((cx + dx, cy + dy), fill=white)
                return
            # ögon SLITS (hood): bara linje + svag glans
            if lash == "slit" and state in ("normal", "wide", "angry", "sad"):
                d.line([(cx - 3, cy), (cx + 3, cy)], fill=out)
                d.point((cx + 1, cy - 1), fill=(150, 155, 175, 220))
                return
            tall = 1 if state == "wide" else 0
            # öga: vitor + iris + glans + frans — GEOMETRI per karaktärsprofil
            if state == "whiteout":            # One Piece: tomma vita ögon m. pupillprick
                d.rectangle([cx - 3, cy - 5, cx + 3, cy + 3], fill=white)
                d.point((cx - 1, cy + 1), fill=out)
                d.line([(cx - 3, cy - 5), (cx + 3, cy - 5)], fill=out)
            else:
                d.rectangle([cx - hw, cy + etop - tall, cx + hw, cy + ebot], fill=white)
                # GAZE: iris CENTRERAD som default (gaze=-1/0/+1). Förr: klistrad
                # VÄNSTER via cx-max(1,iw-1) => "creepy-stirr åt sidan"-buggen.
                ix0 = cx - iw // 2 + max(-1, min(1, gaze)) + 1
                d.rectangle([ix0 - 1, cy + etop + 1 - tall, ix0 + iw - 2, cy + ebot],
                            fill=iris + (255,))
                # v5 ANIME-iris: lockskugga upptill, bas-glans nedtill, pupill, DUBBEL glans
                d.line([(ix0 - 1, cy + etop + 1 - tall), (ix0 + iw - 2, cy + etop + 1 - tall)],
                       fill=_dk(iris, 0.5) + (255,))
                d.rectangle([ix0, cy, ix0, cy + ebot], fill=_dk(iris, 0.55) + (255,))
                d.line([(ix0 - 1, cy + ebot), (ix0 + iw - 2, cy + ebot)],
                       fill=_lt(iris, 1.3) + (255,))
                py2 = min(cy + etop + 4, cy + ebot - 1)
                d.point((ix0, py2), fill=(16, 14, 18, 255))                    # pupill
                d.point((ix0 - 1, cy + etop + 1 - tall), fill=white)           # GLANS 1 (stor)
                d.point((ix0 + iw - 2, min(cy + ebot - 1, cy + 1)), fill=white)  # GLANS 2
                if lash in ("thick", "soft"):                                  # frans-flick ytterhörn
                    ox2 = cx + (hw + 1) * side
                    d.point((ox2, cy + etop - tall - 1), fill=out)
                if state == "angry":
                    d.rectangle([cx - hw, cy + etop - tall, cx + hw,
                                 cy + etop + (2 if etop <= -4 else 1)], fill=out)
                if lash == "line":
                    d.line([(cx - hw, cy + etop - tall), (cx + hw, cy + etop - tall)],
                           fill=out)
                elif lash == "thick":
                    d.rectangle([cx - hw, cy + etop - tall, cx + hw, cy + etop + 1 - tall],
                                fill=out)
                elif lash == "slant":
                    d.line([(cx - hw, cy + etop - tall), (cx + hw, cy + etop + 1 - tall)],
                           fill=out)
                elif lash == "ridge":
                    d.rectangle([cx - hw - 1, cy + etop - 2 - tall, cx + hw + 1,
                                 cy + etop - 1], fill=out)
                else:
                    d.line([(cx - hw, cy + etop - tall), (cx + hw, cy + etop - tall)],
                           fill=_dk(out, 0.5))
                d.point((cx - 2, cy + 4), fill=_dk(skin, 0.65))                # nedre frans
        eye(10, 19, 1)
        eye(23, 19, -1)
        # bryn
        if state == "angry":
            d.line([(6, 15), (12, 17)], fill=out, width=1)
            d.line([(27, 15), (21, 17)], fill=out, width=1)
            d.line([(6, 14), (12, 15)], fill=_dk(out, 0.7))
        elif state == "happy":
            pass
        elif state == "sad":
            d.line([(6, 17), (12, 15)], fill=out)
            d.line([(27, 17), (21, 15)], fill=out)
        elif state in ("normal", "wide", "spark") and eyes_kind != "rm":
            d.line([(7, 15), (12, 15)], fill=_dk(cols["H"], 0.5))
            d.line([(22, 15), (27, 15)], fill=_dk(cols["H"], 0.5))
        # näsa
        d.line([(16, 22), (17, 24)], fill=_dk(skin, 0.7))
        if state == "angry":
            d.point((14, 24), fill=_dk(skin, 0.6))
        heads[state] = im

    def with_mouth(im, mouth, addons=()):
        out_im = im.copy()
        d = ImageDraw.Draw(out_im)
        mc = (28, 16, 22, 255)
        teeth = (250, 250, 246, 255)
        tongue = (200, 80, 90, 255)
        if mouth == "open":
            d.rectangle([13, 26, 21, 29], fill=mc)
            d.rectangle([14, 28, 20, 29], fill=tongue)
            d.line([(13, 26), (21, 26)], fill=teeth)
        elif mouth == "grin":
            d.rectangle([12, 26, 22, 28], fill=teeth)
            d.line([(12, 28), (22, 28)], fill=out)
            d.line([(17, 26), (17, 28)], fill=_dk((250, 250, 246), 0.7))
            d.point((11, 26), fill=out); d.point((23, 26), fill=out)
        elif mouth == "shout":
            d.rectangle([12, 25, 22, 30], fill=mc)
            d.rectangle([12, 25, 22, 26], fill=teeth)
            d.rectangle([14, 29, 20, 30], fill=tongue)
        elif mouth == "grit":                    # One Piece-argbest: knäppt tänder
            d.rectangle([11, 25, 23, 29], fill=teeth)
            for gx in (14, 17, 20):
                d.line([(gx, 25), (gx, 29)], fill=_dk((250, 250, 246), 0.55))
            d.line([(11, 27), (23, 27)], fill=_dk((250, 250, 246), 0.5))
            d.rectangle([11, 25, 11, 29], outline=out)
        elif mouth == "smile":                   # le: mjuk uppåtbåge
            d.line([(13, 27), (21, 26)], fill=_dk(skin, 0.55))
            d.point((21, 25), fill=_dk(skin, 0.55))
        elif mouth == "smirk":                   # smyg/SMIRK: enda mungipan upp
            d.line([(14, 27), (20, 27)], fill=_dk(skin, 0.55))
            d.line([(20, 27), (22, 25)], fill=_dk(skin, 0.55))
        elif mouth == "laugh":                   # skratt: öppen + tänder + tunga
            d.rectangle([12, 25, 22, 29], fill=mc)
            d.rectangle([12, 25, 22, 26], fill=teeth)
            d.rectangle([14, 27, 20, 29], fill=tongue)
        elif mouth == "frown":
            d.line([(13, 28), (21, 27)], fill=out)
            d.point((12, 29), fill=out); d.point((22, 27), fill=out)
        else:
            d.line([(14, 27), (20, 27)], fill=_dk(skin, 0.6))
        # anime-ikoner: svett / vredesåder / rodnad
        if "sweat" in addons:
            for i, (sx, sy) in enumerate(((29, 14), (31, 19), (4, 15))):
                d.rectangle([sx, sy, sx + 1, sy + 2], fill=(170, 220, 250, 255))
                d.point((sx, sy), fill=white)
        if "vein" in addons:
            vx, vy = 27, 9
            d.line([(vx - 2, vy), (vx + 2, vy)], fill=out)
            d.line([(vx, vy - 2), (vx, vy + 2)], fill=out)
            d.line([(vx - 3, vy + 2), (vx + 3, vy - 2)], fill=_dk(out, 0.6))
        if "blush" in addons:
            for bx in (7, 26):
                d.point((bx, 23), fill=(245, 140, 150, 200))
                d.point((bx + 1, 23), fill=(245, 140, 150, 200))
        if "bruise" in addons:
            d.point((27, 25), fill=(230, 90, 90, 255)); d.point((27, 26), fill=(230, 90, 90, 255))
            d.point((28, 26), fill=(230, 90, 90, 255))
        return out_im

    return heads, with_mouth


class AnimeChar:
    """Skelett-animehjälte. draw() renderar kropp+huvud som EN bild (cachad)."""

    def __init__(self, name, palette, hair="spiky", iris=(200, 120, 40),
                 suit=None, scale=1.0, voice_pitch="ren", scale_x=1.0, scale_y=1.0,
                 eyes_kind="default"):
        self.name = name
        self.scale = scale
        self.scale_x, self.scale_y = scale_x, scale_y
        self.ground_px = int(GROUND_CV * scale * scale_y)
        self.voice_pitch = voice_pitch
        self.suit = suit or Suit(jacket=palette.get("T", (50, 60, 120)),
                                 pants=palette.get("P", (50, 50, 60)),
                                 boots=palette.get("B", (60, 45, 35)),
                                 skin=palette["S"])
        # BLICK-VARIANTER: iris vänster/mitt/höger (levande ögon)
        self.heads_g = {}
        self._wm_g = {}
        for _g in (-1, 0, 1):
            _h, _wm = make_head_images(palette, hair, iris, eyes_kind, gaze=_g)
            self.heads_g[_g] = _h
            self._wm_g[_g] = _wm
        self.heads, self._with_mouth = self.heads_g[0], self._wm_g[0]
        self._cache = {}
        self.hair_style = hair
        self.dark = palette.get("__dark__", False)

    def full(self, pose, t, eyes="normal", mouth="closed", bruise=False, addons=(),
             gaze=0):
        gaze = max(-1, min(1, int(gaze)))
        key = (pose, round(t * (6.0 if pose in ("walk", "run") else 2.0), 2),
               eyes, mouth, bruise, addons, gaze)
        if key in self._cache:
            return self._cache[key]
        img = Image.new("RGBA", (BODY_CV_W, BODY_CV_H), (0, 0, 0, 0))
        j = joints_for("walk" if pose == "mov" else pose,
                       t if pose in ("walk", "run", "idle", "mov") else 0.0)
        draw_body(img, self.suit, j, scale=1.0)
        # huvud: neck-led (0,56) -> huvudets nederdel ditsätts
        hg = self.heads_g[gaze]
        head = hg.get(eyes, hg["normal"])
        head = self._wm_g[gaze](head, mouth, addons)
        if bruise:
            hd = ImageDraw.Draw(head)
            hd.point((20, 16), fill=(235, 90, 90, 255))
            hd.point((20, 17), fill=(235, 90, 90, 255))
        hscale = 1.38
        head = head.resize((int(head.width * hscale), int(head.height * hscale)), NEAREST)
        nx = BODY_CV_W // 2 + int(j["neck"][0])
        ny = GROUND_CV - int(j["neck"][1])
        img.alpha_composite(head, (nx - head.width // 2, ny - head.height + 8))
        if (self.scale, self.scale_x, self.scale_y) != (1.0, 1.0, 1.0):
            img = img.resize((int(BODY_CV_W * self.scale * self.scale_x),
                              int(BODY_CV_H * self.scale * self.scale_y)), NEAREST)
        self._cache[key] = img
        return img

    def bust(self, eyes="angry", mouth="grin", addons=()):
        """Bröstbild: huvud + axelparti (anime-byst). addons: sweat/vein/blush/bruise."""
        head = self._with_mouth(self.heads.get(eyes, self.heads["normal"]), mouth, addons)
        b = Image.new("RGBA", (44, 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(b)
        out = self.suit.outl
        d.polygon([(0, 39), (3, 31), (12, 29), (22, 27), (32, 29), (41, 31), (44, 39)],
                  fill=self.suit.jacket)
        d.polygon([(0, 39), (3, 31), (12, 29), (22, 27), (32, 29), (41, 31), (44, 39)],
                  outline=out)
        d.rectangle([21, 28, 22, 39], fill=_dk(self.suit.jacket, 0.7))
        d.rectangle([20, 26, 23, 28], fill=self.suit.skin)
        b.alpha_composite(head, (5, 3))
        return b

    def get_bust_scaled(self, eyes, mouth, n, addons=()):
        return self.bust(eyes, mouth, addons).resize((44 * n, 40 * n), NEAREST)


def cutin(img, char, t_since, side, name, chip_col, mood="normal", addons=()):
    """Närbilds-insättning vid replik: dämpad scen + strålvifte + stor byst."""
    ov = Image.new("RGBA", img.size, (6, 8, 18, 150))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img, "RGBA")
    cw, ch2 = img.size
    cx = cw - 240 if side else 240
    for i in range(14):
        a = i * math.pi / 14 + math.pi / 24
        col = tuple(min(255, c + 46) for c in chip_col[:3]) + (58,)
        d.polygon([(cx, ch2), (cx + int(math.cos(a - 0.02) * 900), 0),
                   (cx + int(math.cos(a + 0.02) * 900), 0)], fill=col)
    slide = int(max(0.0, (0.14 - t_since)) * 900)
    faces = {"normal": ("angry", "grin"), "grit": ("angry", "grit"),
             "rage": ("whiteout", "shout"), "hurt": ("x", "open")}
    fv, fm = faces.get(mood, ("angry", "grin"))
    bust = char.get_bust_scaled(fv, fm, 9, addons)
    if not side:
        from PIL import ImageOps as _IO
        bust = _IO.mirror(bust)
    bx = img.width - bust.width - 80 + slide if side else 80 - slide
    img.alpha_composite(bust, (bx, img.height - bust.height - 46))
    nm = ptext(name.upper(), scale=4, col=(255, 255, 255))
    bar = Image.new("RGBA", (nm.width + 26, nm.height + 14), tuple(chip_col[:3]) + (255,))
    bar.alpha_composite(nm, (13, 7))
    tx = img.width - bar.width - 80 if side else 80
    img.alpha_composite(bar, (tx, img.height - bar.height - 46))
    return img


def faceoff(img, charA, charB, active, chip_a, chip_b, name_a, name_b, t_since):
    """DUELL-SPLIT: två stora byster från varsin kant, diagonalblixt mellan dem."""
    ov = Image.new("RGBA", img.size, (6, 8, 18, 165))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img, "RGBA")
    cw, ch2 = img.size
    # diagonal skiljelinje (blixt)
    zx = cw // 2
    pts = [(zx + 10, 0), (zx - 16, ch2 // 2), (zx - 2, ch2 // 2), (zx - 18, ch2),
           (zx + 4, ch2 // 2), (zx + 10, ch2 // 2), (zx + 22, 0)]
    # fartlinjer bakom varje byst (chip-färg), som strålviften i cutin
    import math as _m
    _cen = ((-40 + 44 * 9 // 2, -1, chip_a), (img.width - 44 * 9 // 2 + 40, 1, chip_b))
    for cx, back, cc in _cen:
        col = tuple(min(255, c + 80) for c in cc[:3]) + (95,)
        cy = ch2 - 40 * 9 - 40 + 110
        for k in range(12):
            a = _m.pi + back * (k - 5.5) * 0.20
            x2 = cx + int(_m.cos(a) * 560); y2 = cy + int(_m.sin(a) * 420)
            d.line((cx, cy, x2, y2), fill=col, width=5)
    # glid-in från respektive kant (0.14 s ease)
    prog = min(1.0, max(0.0, t_since / 0.14))
    off = int((1.0 - (1 - prog) ** 2) * -460 + 460) if prog < 1.0 else 0
    bA = charA.get_bust_scaled("angry", "grit", 9)
    bB = charB.get_bust_scaled("angry" if active != "B" else "whiteout",
                               "grit" if active != "B" else "shout", 9)
    xA = -40 - off; xB = img.width - bB.width + 40 + off
    img.alpha_composite(bA, (xA, img.height - bA.height - 40))
    from PIL import ImageOps as _IO
    bB = _IO.mirror(bB)
    img.alpha_composite(bB, (xB, img.height - bB.height - 40))
    # blixt-skiljelinjen OVANPÅ bysterna (One Piece-stil)
    d = ImageDraw.Draw(img, "RGBA")
    d.polygon(pts, fill=(255, 255, 255, 235))
    d.polygon([(p[0] - 7, p[1]) for p in pts], fill=(255, 205, 90, 200))
    for nm, cc, xx in ((name_a, chip_a, 30), (name_b, chip_b, None)):
        lit = ptext(nm.upper(), scale=4, col=(255, 255, 255))
        bar = Image.new("RGBA", (lit.width + 24, lit.height + 12), tuple(cc[:3]) + (255,))
        bar.alpha_composite(lit, (12, 6))
        img.alpha_composite(bar, (xx if xx is not None else img.width - bar.width - 30, 26))
    return img
