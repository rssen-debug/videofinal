#!/usr/bin/env python3
"""GFX KIT v2 — "million dollar studio"-assets (Pillow).
Bygger: glow-titlar, lower thirds, tweet/UI-mockups, stat-kort, HUD, light leak.
FONTER: Anton / Archivo Black / Bebas Neue (assets/fonts) med DejaVu-fallback.

Användning: importera funktioner i din builder ELLER kör för Drake-POC-standardassets.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GFX = os.path.join(ROOT, "assets", "gfx")
FDIR = os.path.join(ROOT, "assets", "fonts")
os.makedirs(GFX, exist_ok=True)
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def F(px, which="anton"):
    p = {"anton": os.path.join(FDIR, "Anton-Regular.ttf"),
         "archivo": os.path.join(FDIR, "ArchivoBlack-Regular.ttf"),
         "bebas": os.path.join(FDIR, "BebasNeue-Regular.ttf"),
         "dejavu": DEJAVU}.get(which, DEJAVU)
    try:
        return ImageFont.truetype(p, px)
    except Exception:
        return ImageFont.truetype(DEJAVU, px)

def _tsize(draw, text, font, stroke=0):
    bb = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return bb[2] - bb[0], bb[3] - bb[1]

# ---------------- GLOW TITEL (neon-dokumentär-look) ----------------
def glow_title(out, text, px=170, fill=(255, 255, 255, 255),
               glow=(232, 34, 46, 160), stroke=10, pad=140):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    f = F(px, "anton")
    w, h = _tsize(tmp, text, f, stroke)
    W, H = w + pad * 2, h + px + pad
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x, y = (W - w) // 2, pad // 2 + int(px * 0.18)
    # glow-lager: bred mjuk + tät
    for radius, alpha in [(34, glow[3]), (12, min(255, glow[3] + 60))]:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((x, y), text, font=f, fill=glow[:3] + (alpha,),
                                   stroke_width=stroke, stroke_fill=glow[:3] + (alpha,))
        layer = layer.filter(ImageFilter.GaussianBlur(radius))
        canvas = Image.alpha_composite(canvas, layer)
    d = ImageDraw.Draw(canvas)
    d.text((x, y), text, font=f, fill=fill, stroke_width=stroke,
           stroke_fill=(8, 8, 10, 255))
    canvas.save(os.path.join(GFX, out))
    print("glow_title:", out)

# ---------------- LOWER THIRD (namn/reveal-bar) ----------------
def lower_third(out, main, sub="", accent=(232, 34, 46, 255), W=1080):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fm, fs = F(72, "archivo"), F(40, "bebas")
    mw, mh = _tsize(d0, main, fm)
    sw, sh = (_tsize(d0, sub, fs) if sub else (0, 0))
    H = 36 + mh + (14 + sh if sub else 0) + 34
    card = Image.new("RGBA", (W, H + 20), (0, 0, 0, 0))
    dr = ImageDraw.Draw(card)
    dr.rounded_rectangle([26, 10, W - 6, H + 6], 14, fill=(12, 12, 14, 208))
    dr.rounded_rectangle([26, 10, 40, H + 6], 7, fill=accent)
    ox = 64
    dr.text((ox, 24), main, font=fm, fill=(255, 255, 255, 255))
    if sub:
        dr.text((ox, 24 + mh + 12), sub, font=fs, fill=(190, 190, 196, 235))
    card.save(os.path.join(GFX, out))
    print("lower_third:", out)

# ---------------- TWEET / SOCIAL UI MOCKUP ----------------
def _heart(dr, cx, cy, r, fill):
    dr.ellipse([cx - r, cy - r, cx, cy], fill=fill)
    dr.ellipse([cx, cy - r, cx + r, cy], fill=fill)
    dr.polygon([(cx - r, cy - r * 0.35), (cx + r, cy - r * 0.35), (cx, cy + r)], fill=fill)

def tweet_ui(out, name, handle, body, meta, likes, avatar_path, W=940):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fn, fh, fb, fm = F(44, "archivo"), F(36, "bebas"), F(46, "archivo"), F(34, "bebas")
    # radbryt body
    words, lines, cur = body.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if _tsize(d0, t, fb)[0] > W - 120:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    av = 92
    H = 40 + av + 26 + len(lines) * (58 + 8) + 30 + 46 + 34
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(card)
    dr.rounded_rectangle([0, 0, W - 1, H - 1], 26, fill=(21, 24, 28, 242),
                         outline=(70, 76, 84, 255), width=2)
    # avatar (cirkelbeskuren)
    if os.path.exists(avatar_path):
        a = ImageOps.fit(Image.open(avatar_path).convert("RGB"), (av, av), Image.LANCZOS)
        m = Image.new("L", (av, av), 0)
        ImageDraw.Draw(m).ellipse([0, 0, av, av], fill=255)
        card.paste(a, (40, 40), m)
    nx = 40 + av + 26
    dr.text((nx, 44), name, font=fn, fill=(255, 255, 255, 255))
    nw = _tsize(dr, name, fn)[0]
    dr.text((nx + nw + 16, 52), handle, font=fh, fill=(120, 128, 138, 255))
    y = 40 + av + 26
    for ln in lines:
        dr.text((40, y), ln, font=fb, fill=(232, 234, 238, 255))
        y += 58 + 8
    y += 12
    dr.text((40, y), meta, font=fm, fill=(110, 118, 128, 255))
    # hjärta + likes
    hy = y + 66
    _heart(dr, 56, hy, 16, (249, 24, 128, 255))
    dr.text((84, hy - 18), likes, font=fh, fill=(249, 24, 128, 255))
    card.save(os.path.join(GFX, out))
    print("tweet_ui:", out, f"{W}x{H}")

# ---------------- STAT-KORT (data-viz slam) ----------------
def stat_card(out, big, label, accent=(232, 34, 46, 255)):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fb, fl = F(200, "anton"), F(46, "bebas")
    bw, bh = _tsize(d0, big, fb)
    lw, lh = _tsize(d0, label, fl)
    W = max(bw, lw) + 160
    H = 30 + bh + 18 + lh + 40
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(c)
    dr.rectangle([(W - min(bw, 420)) // 2, 18, (W + min(bw, 420)) // 2, 24], fill=accent)
    dr.text(((W - bw) // 2, 40), big, font=fb, fill=(255, 255, 255, 255),
            stroke_width=8, stroke_fill=(8, 8, 10, 255))
    dr.text(((W - lw) // 2, 40 + bh + 18), label, font=fl, fill=(205, 205, 212, 245))
    c.save(os.path.join(GFX, out))
    print("stat_card:", out)

# ---------------- HUD-ram (hörn + ticks, subtil) ----------------
def hud_frame(out, W=1280, H=720, alpha=70):
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(c)
    L, m, col = 46, 26, (255, 255, 255, alpha)
    for (x, y, dx, dy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        dr.line([(x, y), (x + dx * L, y)], fill=col, width=3)
        dr.line([(x, y), (x, y + dy * L)], fill=col, width=3)
    for cx in (W // 2,):
        dr.line([(cx - 14, 24), (cx + 14, 24)], fill=col, width=2)
        dr.line([(cx - 14, H - 24), (cx + 14, H - 24)], fill=col, width=2)
    c.save(os.path.join(GFX, out))
    print("hud:", out)

# ---------------- LIGHT LEAK (varm ljusläcka, lägg överst) ----------------
def light_leak(out, W=1280, H=720):
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    blob = Image.new("L", (W, H), 0)
    db = ImageDraw.Draw(blob)
    db.ellipse([-W * 0.25, H * 0.55, W * 0.45, H * 1.35], fill=46)
    db.ellipse([W * 0.72, -H * 0.25, W * 1.25, H * 0.35], fill=26)
    blob = blob.filter(ImageFilter.GaussianBlur(90))
    warm = Image.new("RGBA", (W, H), (255, 128, 60, 0))
    warm.putalpha(blob)
    c = Image.alpha_composite(c, warm)
    c.save(os.path.join(GFX, out))
    print("light_leak:", out)

if __name__ == "__main__":
    import glob
    SRC = os.path.join(ROOT, "assets", "src")
    # Drake-POC + fullvideo-assets
    glow_title("glow_drake.png", "DRAKE", 200, glow=(232, 34, 46, 150))
    glow_title("glow_bark.png", '"WOULD YOU BARK?"', 110, glow=(120, 220, 255, 140))
    glow_title("glow_subscribe.png", "SUBSCRIBE", 170, glow=(60, 220, 120, 140))
    glow_title("glow_gothsplan.png", "GOTH'S PLAN", 130, glow=(232, 34, 46, 160))
    lower_third("lt_drake.png", "DRAKE", "THE BIGGEST RAPPER ALIVE · 9TH STAKE ANNIVERSARY")
    lower_third("lt_pink.png", "PINKCHYU", "LIN LAMAR · 23 · GOTH CREATOR · 2M+ FOLLOWERS",
                accent=(200, 60, 220, 255))
    lower_third("lt_tmz.png", "TMZ INTERVIEW", "A SECOND CELEB BARKED IN HER DMS",
                accent=(0, 160, 255, 255))
    avatars = glob.glob(os.path.join(SRC, "pinkchyu.jpg"))
    tweet_ui("tweet_ryan.png",
             "ryan", "@scubaryan_",
             "Drake instantly folded and started barking after this goth baddie told him to",
             "9:12 PM · Aug 8, 2026", "4.1M", avatars[0] if avatars else "")
    stat_card("stat_1m.png", "1M+", "VIEWS IN HOURS")
    stat_card("stat_98.png", "98", "ROOMS · CASA LOMA")
    hud_frame("hud.png")
    light_leak("lightleak.png")
    print("GFX KIT v2 KLART ->", GFX)

# ================= v2.1: UI-KIT + DATA-VIZ + AI-CUTOUT =================
def discord_ui(out, channel, name, body, time, avatar_path, W=920):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fn, fb, ft = F(42, "archivo"), F(42, "archivo"), F(32, "bebas")
    words, lines, cur = body.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if _tsize(d0, t, fb)[0] > W - 140: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    av = 80
    H = 34 + av + 24 + len(lines) * 60 + 30
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    dr.rounded_rectangle([0, 0, W - 1, H - 1], 24, fill=(28, 30, 36, 240),
                         outline=(64, 68, 76, 255), width=2)
    if avatar_path and os.path.exists(avatar_path):
        a = ImageOps.fit(Image.open(avatar_path).convert("RGB"), (av, av), Image.LANCZOS)
        m = Image.new("L", (av, av), 0); ImageDraw.Draw(m).ellipse([0, 0, av, av], fill=255)
        c.paste(a, (36, 34), m)
    nx = 36 + av + 22
    dr.text((nx, 40), name, font=fn, fill=(255, 255, 255, 255))
    nw = _tsize(dr, name, fn)[0]
    dr.text((nx + nw + 14, 48), time, font=ft, fill=(114, 120, 130, 255))
    y = 34 + av + 24
    for ln in lines:
        dr.text((36, y), ln, font=fb, fill=(220, 223, 229, 255)); y += 60
    c.save(os.path.join(GFX, out)); print("discord_ui:", out)

def youtube_ui(out, title, channel, views, age, avatar_path, thumb_path=None, W=1040):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    ft, fm = F(46, "archivo"), F(34, "bebas")
    th_h = 300
    tw, th = _tsize(d0, title, ft)
    H = 30 + th_h + 22 + th + 14 + 44 + 26
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    dr.rounded_rectangle([0, 0, W - 1, H - 1], 22, fill=(16, 16, 18, 244),
                         outline=(70, 70, 76, 255), width=2)
    if thumb_path and os.path.exists(thumb_path):
        t = ImageOps.fit(Image.open(thumb_path).convert("RGB"), (W - 60, th_h), Image.LANCZOS)
        c.paste(t, (30, 30))
        dr.rectangle([30, 30, 30 + W - 60, 30 + th_h], outline=(90, 90, 96, 255), width=2)
    y = 30 + th_h + 22
    if avatar_path and os.path.exists(avatar_path):
        a = ImageOps.fit(Image.open(avatar_path).convert("RGB"), (64, 64), Image.LANCZOS)
        m = Image.new("L", (64, 64), 0); ImageDraw.Draw(m).ellipse([0, 0, 64, 64], fill=255)
        c.paste(a, (30, y), m)
    dr.text((110, y + 2), title, font=ft, fill=(255, 255, 255, 255)); y += th + 12
    dr.text((110, y), f"{channel}  ·  {views}  ·  {age}", font=fm, fill=(150, 152, 158, 255))
    c.save(os.path.join(GFX, out)); print("youtube_ui:", out)

def phone_chat(out, contact, lines, W=620):
    """lines: [(side 'me'/'them', text)]"""
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fh, fb = F(38, "archivo"), F(36, "archivo")
    bubbles, y = [], 26 + 54 + 20
    for side, text in lines:
        words, ls, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if _tsize(d0, t, fb)[0] > W - 150: ls.append(cur); cur = w
            else: cur = t
        ls.append(cur)
        bh = len(ls) * 52 + 26
        bubbles.append((side, ls, bh)); y += bh + 14
    H = y + 16
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    dr.rounded_rectangle([0, 0, W - 1, H - 1], 34, fill=(9, 10, 12, 246),
                         outline=(60, 62, 70, 255), width=2)
    cw = _tsize(dr, contact, fh)[0]
    dr.text((W // 2 - cw // 2, 26), contact, font=fh, fill=(235, 235, 240, 255))
    dr.line([20, 90, W - 20, 90], fill=(60, 62, 70, 255), width=2)
    y = 106
    for side, ls, bh in bubbles:
        bw = max(_tsize(dr, l, fb)[0] for l in ls) + 52
        x = W - 30 - bw if side == "me" else 30
        col = (28, 88, 58, 245) if side == "me" else (34, 36, 42, 245)
        dr.rounded_rectangle([x, y, x + bw, y + bh], 20, fill=col)
        ty = y + 12
        for l in ls:
            dr.text((x + 26, ty), l, font=fb, fill=(240, 240, 244, 255)); ty += 52
        y += bh + 14
    c.save(os.path.join(GFX, out)); print("phone_chat:", out, f"{W}x{H}")

def timeline_card(out, items, accent=(232, 34, 46, 255), W=1240):
    """items: [(date, label)]"""
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fd, fl = F(40, "bebas"), F(34, "bebas")
    y0, H = 130, 330
    step = (W - 160) // max(len(items) - 1, 1)
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    dr.line([80, y0, W - 80, y0], fill=(200, 200, 206, 180), width=4)
    for i, (date, label) in enumerate(items):
        x = 80 + i * step
        dr.ellipse([x - 13, y0 - 13, x + 13, y0 + 13], fill=accent)
        dw = _tsize(dr, date, fd)[0]
        dr.text((x - dw // 2, y0 - 68), date, font=fd, fill=(255, 255, 255, 255))
        lw = _tsize(dr, label, fl)[0]
        dr.text((max(10, x - lw // 2), y0 + 28), label, font=fl, fill=(206, 206, 212, 240))
    c.save(os.path.join(GFX, out)); print("timeline:", out)

def bar_chart(out, data, accent=(232, 34, 46, 255), W=1000, H=620):
    """data: [(label, value)]"""
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    fb, fl = F(44, "anton"), F(36, "bebas")
    mx = max(v for _, v in data)
    n, gap = len(data), 40
    bw = (W - 120 - gap * (n - 1)) // n
    base = H - 90
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(c)
    for i, (lab, v) in enumerate(data):
        x = 60 + i * (bw + gap)
        bh = int((H - 260) * v / mx)
        dr.rounded_rectangle([x, base - bh, x + bw, base], 10, fill=accent)
        vw = _tsize(dr, str(v), fb)[0]
        dr.text((x + bw // 2 - vw // 2, base - bh - 56), str(v), font=fb,
                fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(8, 8, 10, 255))
        lw = _tsize(dr, lab, fl)[0]
        dr.text((x + bw // 2 - lw // 2, base + 14), lab, font=fl, fill=(206, 206, 212, 240))
    c.save(os.path.join(GFX, out)); print("bar_chart:", out)

def key_white(src_path, out_name, thresh=238, blur=1.6):
    """AI-bild med ljus/plan bakgrund -> transparent cutout (nyckla ut person)."""
    import numpy as np
    im = ImageOps.exif_transpose(Image.open(src_path).convert("RGB"))
    a = np.array(im).astype(np.int16)
    mn = a.min(axis=2)
    alpha = np.clip((thresh - mn) * 8, 0, 255).astype(np.uint8)
    al = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(blur))
    outim = im.convert("RGBA"); outim.putalpha(al)
    outim.save(os.path.join(GFX, out_name)); print("cutout:", out_name)

def circle_portrait(src_path, out_name, ring=(255, 255, 255, 255), size=1000):
    """sunnyv2-cirkelporträtt: beskär -> cirkelmask -> skugga + ring."""
    img = ImageOps.exif_transpose(Image.open(src_path).convert("RGB"))
    w, h = img.size
    s = min(w, h)
    left = (w - s) // 2
    top = int((h - s) * 0.05) if h > w else 0
    img = img.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)
    pad = 60
    canvas = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([pad + 10, pad + 26, pad + size + 10, pad + size + 26],
                               fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    canvas = Image.alpha_composite(canvas, sh)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    canvas.paste(img, (pad, pad), mask)
    d = ImageDraw.Draw(canvas)
    bw = 22
    d.ellipse([pad - bw // 2, pad - bw // 2, pad + size + bw // 2, pad + size + bw // 2],
              outline=ring, width=bw)
    canvas.save(os.path.join(GFX, out_name))
    print("circle_portrait:", out_name)
