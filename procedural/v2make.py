#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2 PIXEL ANIME – v2make: regissören som monterar en riktig anime-episod på CPU.
Episod-anatomi (research): avant-title -> OP-kort -> A-part (mini-cliff) ->
EYECATCH (2 kort) -> B-part (fight!) -> C-part-tease -> NEXT EPISODE.
Munnar läppsynkas från röstens envelope; ögon visar reaktioner; dörrar öppnas;
slag gör ont (knockback + X-ögon + blåmärke).
"""
import argparse
import json
import math
import os
import random
import subprocess
import time

import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter

import voice as voicemod
import sfx as sfxmod
import music as musicmod
import tts as ttsmod
import v2engine as E

NEAREST = E.NEAREST

FPSS = 12
SCALE = 6                      # research: exakt 6x NEAREST -> 1080p
VERT = False                   # 9:16-läge (default av)
TTS_MODE = False               # riktig TTS-röst istf pixel-pip (per-line wavs i tts/)
TTS_DIR = "/home/user/pixeltube/tts"   # per-ep TTS-katalog (tts910 för portal fight)
_VIG = None


def hi_post(img, f, chroma=False):
    """HD-2D 'wow-passet' (VERT @60fps): bloom på ljus/stamps, vignette, chunky
    film-grain, kromatisk aberration vid impakt/shake. ~90ms/frame, CPU-vänligt."""
    global _VIG
    im = img.convert("RGB")
    W, H = im.size
    if _VIG is None or _VIG.shape[:2] != (H, W):
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.72)) ** 2)
        _VIG = (1.0 - 0.30 * np.clip(r - 0.55, 0, 1) ** 1.6)[..., None]
    small = im.resize((W // 8, H // 8), Image.BILINEAR)
    sa = np.asarray(small).astype(np.float32)
    lum = sa.max(axis=2, keepdims=True)
    bright = sa * (lum > 200)
    b = Image.fromarray(bright.astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    b = b.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
    arr = np.asarray(im).astype(np.float32) + np.asarray(b).astype(np.float32) * 0.38
    arr *= _VIG
    rng = np.random.RandomState(f)
    g = rng.normal(0, 3.8, (H // 8, W // 8))
    g = np.asarray(Image.fromarray(g.astype(np.float32)).resize((W, H), Image.NEAREST))[..., None]
    arr += g
    if chroma:
        arr[:, :, 0] = np.roll(arr[:, :, 0], 4, axis=1)
        arr[:, :, 2] = np.roll(arr[:, :, 2], -4, axis=1)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
VERT_STAMPS_OUT = False        # VERT: stamps ritas på output-koordinater                       # 320x180 -> 1280x720
OUTW, OUTH = E.W * SCALE, E.H * SCALE

SERIES = "VOLT BREAKER"

# -------------------------------------------------------------------------- #
# ROLLLISTA (v2 – människor!)                                               #
# -------------------------------------------------------------------------- #
def build_cast():
    return {
        # REN — atletisk medelfighter (baslinjen)
        "ren":  E.AnimeChar("ren",  {"H": (245, 130, 40), "S": (255, 215, 175), "T": (42, 64, 150),
                                     "P": (48, 48, 66), "B": (72, 52, 40), "K": (24, 22, 28)},
                              hair="spiky", iris=(200, 120, 40), voice_pitch="ren", eyes_kind="default",
                              scale_x=0.98, scale_y=1.0,
                              suit=E.Suit((42, 64, 150), (48, 48, 66), (72, 52, 40), (255, 215, 175),
                                          arm_w=6, tor_w=11, hips=7)),
        # YUKI — lång smal fäktare
        "yuki": E.AnimeChar("yuki", {"H": (234, 236, 248), "S": (252, 226, 200), "T": (52, 54, 64),
                                     "P": (30, 30, 44), "B": (40, 36, 40), "K": (24, 22, 28)},
                              hair="long", iris=(110, 190, 235), voice_pitch="yuki", eyes_kind="sharp",
                              scale_x=0.90, scale_y=1.06,
                              suit=E.Suit((52, 54, 64), (30, 30, 44), (40, 36, 40), (252, 226, 200),
                                          arm_w=4, leg_t=0.9, tor_w=9, hips=6)),
        # MIKA — kurvig, breda höfter
        "mika": E.AnimeChar("mika", {"H": (245, 120, 170), "S": (255, 218, 185), "T": (186, 50, 78),
                                     "P": (60, 60, 90), "B": (90, 50, 66), "K": (24, 22, 28)},
                              hair="pony", iris=(210, 80, 150), voice_pitch="mika", eyes_kind="big",
                              scale_x=0.90, scale_y=1.0,
                              suit=E.Suit((186, 50, 78), (60, 60, 90), (90, 50, 66), (255, 218, 185),
                                          arm_w=4, leg_t=0.85, tor_w=9, hips=10, bust=2)),
        # KABA — muskelmassiv skurk med axelpads
        "kaba": E.AnimeChar("kaba", {"H": (44, 44, 54), "S": (192, 196, 206), "T": (110, 30, 42),
                                     "P": (40, 40, 48), "B": (30, 28, 30), "K": (20, 16, 22)},
                              hair="hawk", iris=(200, 60, 60), voice_pitch="kaba", eyes_kind="small",
                              scale_x=1.22, scale_y=1.12,
                              suit=E.Suit((110, 30, 42), (40, 40, 48), (30, 28, 30), (192, 196, 206),
                                          arm_w=8, leg_t=1.25, tor_w=14, hips=10, pads=1)),
        # HOOD — spöklik lång
        "hood": E.AnimeChar("hood", {"H": (22, 22, 30), "S": (34, 34, 44), "T": (26, 26, 38),
                                     "P": (24, 24, 34), "B": (22, 22, 32), "K": (10, 10, 16)},
                              hair="long", iris=(90, 90, 120), voice_pitch="narr", eyes_kind="slit",
                              scale_x=0.88, scale_y=1.08,
                              suit=E.Suit((26, 26, 38), (24, 24, 34), (22, 22, 32), (34, 34, 44),
                                          arm_w=3, tor_w=8, hips=6)),
        # NAYA — petite, lätta kurvor
        "naya": E.AnimeChar("naya", {"H": (120, 220, 230), "S": (235, 230, 240), "T": (38, 78, 96),
                                     "P": (50, 54, 72), "B": (30, 40, 48), "K": (16, 20, 28)},
                              hair="long", iris=(150, 240, 240), voice_pitch="naya", eyes_kind="soft",
                              scale_x=0.86, scale_y=0.97,
                              suit=E.Suit((38, 78, 96), (50, 54, 72), (30, 40, 48), (235, 230, 240),
                                          arm_w=3, leg_t=0.8, tor_w=8, hips=8, bust=1)),
    }


# -------------------------------------------------------------------------- #
# LÄPPSYNK: röstens envelope -> per-frame öppen/stängd mun                   #
# -------------------------------------------------------------------------- #
def mouth_track(wave, fps=FPSS):
    a = np.abs(np.asarray(wave, dtype=np.float32))
    if a.size == 0:
        return np.zeros(0, bool)
    per = int(voicemod.SR / fps)
    n = (a.size + per - 1) // per
    pad = np.zeros(n * per, np.float32); pad[:a.size] = a
    amp = pad.reshape(n, per).max(axis=1)
    nz = amp[amp > 0.004]
    if nz.size < 2:
        return np.zeros(n, bool)
    thr = max(0.02, np.percentile(nz, 38))
    open_ = amp > thr
    # mjuka upp: undvik 1-frame blinkfladder
    for i in range(1, n - 1):
        if open_[i - 1] and open_[i + 1]:
            open_[i] = True
    return open_


# -------------------------------------------------------------------------- #
# SUBTITLES (namn-chip + piller)                                            #
# -------------------------------------------------------------------------- #
CHIP_COLS = {"ren": (245, 130, 40), "yuki": (200, 205, 225), "mika": (245, 130, 178),
             "kaba": (160, 70, 80), "narr": (140, 140, 160), "hood": (120, 120, 150),
             "naya": (130, 220, 230)}
DISP = {"ren": "REN", "yuki": "YUKI", "mika": "MIKA", "kaba": "KABA",
        "tom": "TOM", "col": "COL", "narr": "NARR",
        "narr": "", "hood": "???", "naya": "NAYA"}


def draw_sub(pil_img, text, who=None):
    d = ImageDraw.Draw(pil_img, "RGBA")
    _sub_sc = 4 if OUTH > OUTW else 5                # vertikal: STORA captions
    t = E.ptext(text, scale=_sub_sc, col=(255, 255, 255))     # TIKTOK-STORA subs
    pad_x, pad_y = 30, 22
    bw, bh = t.width + pad_x * 2 + 8, t.height + pad_y * 2
    x0 = (OUTW - bw) // 2
    y0 = int(OUTH * (0.62 if OUTH > OUTW else 1.0)) - bh - (0 if OUTH > OUTW else 0)         if OUTH > OUTW else OUTH - bh - 22
    d.rectangle([x0 + 4, y0 + 5, x0 + bw + 4, y0 + bh + 5], fill=(0, 0, 0, 110))
    d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=(12, 12, 20, 200),
                outline=(90, 90, 120, 220), width=3)
    x_text = x0 + pad_x
    if who and DISP.get(who):
        chip = E.ptext(DISP[who], scale=(2 if OUTH > OUTW else 3), col=(20, 20, 26))
        cw = chip.width + 16
        ch_col = CHIP_COLS.get(who, (150, 150, 150))
        d.rectangle([x0, y0 - chip.height - 10, x0 + cw + 10, y0 - 2], fill=ch_col + (255,))
        pil_img.alpha_composite(chip, (x0 + 8, y0 - chip.height - 6))
    pil_img.alpha_composite(t, (x_text + 4, y0 + pad_y))


def draw_sub_sync(pil_img, text, who, prog):
    """RWJ word-sync captions (VERT): 2-4 ord i taget, enorma, på 62% höjd.
    prog = 0..1 genom replikens riktiga ljud (char-viktad fras-timing)."""
    words = (text or "").split()
    if not words:
        return
    phrases, cur = [], ""
    for w_ in words:
        if len((cur + " " + w_).strip()) <= 13:
            cur = (cur + " " + w_).strip()
        else:
            phrases.append(cur); cur = w_
    if cur:
        phrases.append(cur)
    total_w = sum(max(3, len(p)) for p in phrases)
    cp = min(1.0, max(0.0, prog))
    acc, idx2 = 0.0, len(phrases) - 1
    for i3, p3 in enumerate(phrases):
        acc += max(3, len(p3)) / total_w
        if cp <= acc:
            idx2 = i3
            break
    d = ImageDraw.Draw(pil_img, "RGBA")
    t = E.ptext(phrases[idx2], scale=5, col=(255, 255, 255))
    pad_x, pad_y = 34, 24
    bw, bh = t.width + pad_x * 2 + 8, t.height + pad_y * 2
    x0 = (OUTW - bw) // 2
    y0 = int(OUTH * 0.62) - bh
    d.rectangle([x0 + 5, y0 + 6, x0 + bw + 5, y0 + bh + 6], fill=(0, 0, 0, 120))
    d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=(12, 12, 20, 205),
                outline=(90, 90, 120, 225), width=3)
    pil_img.alpha_composite(t, (x0 + pad_x + 4, y0 + pad_y))


# -------------------------------------------------------------------------- #
# EPISOD 1 – REGIBOKEN. Tider är scen-lokala (sekunder).                    #
# -------------------------------------------------------------------------- #
def episode_001(cast):
    """Returnerar scendirektiv-lista. Varje dict: env, dur, actors, lines,
    events (audio + fx), cam."""
    scenes = []
    # ============ 0) COLD OPEN – hamnen i regn, berättarröst ============== #
    scenes.append({
        "env": ("dock", {}), "dur": 11.6, "letterbox": 14, "fadein": 0.7,
        "cam": [{"kind": "zoom", "z": lambda t: 1.12 + t * 0.006, "focus": (160, 100)}],
        "actors": {
            "ren": {"track": [(0.0, -34, False), (2.4, 148, False), (11.6, 152, False)],
                    "blocks": [(0, 2.5, "mov"), (2.5, 99, "idle")],
                    "faces": [(3.1, "angry", False)]},
            "hood": {"track": [(6.4, 26, False), (11.6, 26, False)], "y_off": -78,
                     "blocks": [(6.4, 99, "idle")], "faces": []},
        },
        "lines": [(1.0, "narr", "Port Kaminari. Midnight. The sea stopped answering."),
                  (5.2, "ren", "Who turned off the ocean?"),
                  (8.3, "narr", "No boats. No gulls. Only the tower... counting.")],
        "audio": [(0.3, "boom", 0.45), (4.7, "riser", 0.35)],
    })
    # ============ 1) OP-TITELKORT ========================================= #
    scenes.append({"env": ("title", {"series": SERIES,
                                     "episode": "EPISODE 001 - The Night the Sea Went Silent"}),
                   "dur": 4.2, "audio": [(0.15, "boom", 0.9), (0.9, "riser", 0.7)]})
    # ============ 2) A-PART: DOJON – dörren ÖPPNAS ======================== #
    scenes.append({
        "env": ("dojo", {"door_t": 4.4, "bag_hits": (0.75, 1.6, 2.5)}), "dur": 13.4,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 if t < 5.2 else 1.18, "focus": (150, 96)}],
        "actors": {
            "ren": {"track": [(0, 72, True), (8.0, 72, True), (8.3, 120, False), (13.4, 122, False)],
                    "blocks": [(0.55, 0.82, "punch"), (0.82, 1.4, "idle"),
                               (1.4, 1.68, "punch"), (1.68, 2.3, "idle"),
                               (2.3, 2.58, "punch"), (2.58, 8.2, "idle"),
                               (8.2, 10.6, "point"), (10.6, 99, "idle")],
                    "faces": [(0.3, "angry", False, "grit"), (4.2, "normal", False),
                              (8.2, "angry", False)]},
            "mika": {"track": [(0, 288, False), (4.4, 244, True), (6.2, 172, True), (13.4, 174, True)],
                     "blocks": [(0, 4.4, "none"), (4.4, 6.3, "mov"), (6.3, 99, "point")],
                     "faces": []},
        },
        "lines": [(5.5, "mika", "Ren! Every lamp at the harbor just went out - at once!"),
                  (9.0, "ren", "Then we wake every single one back up.")],
        "audio": [(0.72, "thud", 0.8), (1.57, "thud", 0.8), (2.47, "thud", 0.9),
                  (4.4, "whoosh", 0.5), (8.9, "riser", 0.3)],
    })
    # ============ 3) A-PART: SKURKEN LANDAR (mini-cliffhanger) ============ #
    scenes.append({
        "env": ("dock", {}), "dur": 12.6,
        "cam": [{"kind": "zoom", "z": lambda t: 1.05 if t < 3.4 else 1.16, "focus": (190, 100)},
                {"kind": "shake", "t0": 3.2, "t1": 3.7, "amp": 4}],
        "actors": {
            "ren": {"track": [(0, -34, False), (1.6, 84, False), (12.6, 84, False)],
                    "blocks": [(0, 1.7, "mov"), (1.7, 7.6, "idle"), (7.6, 99, "point")],
                    "faces": [(3.6, "angry", False)]},
            "yuki": {"track": [(0, -70, False), (2.0, 40, False), (12.6, 40, False)],
                     "blocks": [(0, 2.1, "mov"), (2.1, 99, "idle")], "faces": []},
            "mika": {"track": [(0, -100, False), (2.4, 220, True), (12.6, 220, True)],
                     "blocks": [(0, 2.5, "mov"), (2.5, 99, "idle")], "faces": []},
            "kaba": {"track": [(0, 226, True), (12.6, 226, True)],
                     "blocks": [(0, 2.0, "none"), (2.0, 3.55, "hurt"), (3.55, 8.6, "guard"),
                                (8.6, 99, "point")],
                     "faces": [(4.2, "angry", False)],
                     "drop": (3.2, -180)},
        },
        "lines": [(4.6, "kaba", "The signal tower answers to ME now. Crawl home, kids."),
                  (8.6, "ren", "Kids?! KIDS?!"),
                  (10.6, "kaba", "Thunder belongs to the strong, little spark.")],
        "audio": [(3.2, "boom", 0.95), (4.5, "riser", 0.4), (10.5, "riser", 0.55)],
        "dust_at": (3.2, 226),
    })
    # ============ 4) EYECATCH (halvtidskorten!) =========================== #
    scenes.append({"env": ("eyecatch", {"who": "ren"}), "dur": 1.5,
                   "audio": [(0.05, "sparkle", 0.8)]})
    scenes.append({"env": ("eyecatch", {"who": "kaba"}), "dur": 1.5,
                   "audio": [(0.05, "boom", 0.5)]})
    # ============ 5) B-PART: FIGHT! ======================================= #
    scenes.append({
        "env": ("dock", {}), "dur": 21.4, "lights_on_at": 15.4,
        "cam": [{"kind": "zoom",
                 "z": lambda t: 1.1 if t < 5.0 else (1.25 if t < 12.9 else 1.08),
                 "focus": (170, 96)},
                {"kind": "shake", "t0": 0.75, "t1": 1.15, "amp": 4},
                {"kind": "shake", "t0": 12.3, "t1": 12.95, "amp": 6}],
        "actors": {
            "ren": {"track": [(0, 84, False), (1.0, 56, False), (2.2, 60, False),
                              (5.0, 96, False), (11.9, 96, False), (12.15, 196, False),
                              (13.0, 200, False), (21.4, 204, False)],
                    "blocks": [(0, 0.75, "idle"), (0.75, 2.1, "hurt"), (2.1, 4.9, "idle"),
                               (4.9, 6.1, "point"), (6.1, 11.9, "idle"),
                               (11.9, 12.15, "mov"), (12.15, 12.5, "punch"),
                               (12.5, 12.75, "idle"), (12.75, 13.05, "punch"),
                               (13.05, 99, "idle")],
                    "faces": [(0.75, "x", True), (2.1, "sad", True), (4.9, "angry", False),
                              (16.0, "spark", False, "smirk")]},
            "yuki": {"track": [(0, 40, False), (2.15, 162, False), (3.4, 172, False),
                               (21.4, 172, False)],
                     "blocks": [(0, 2.1, "idle"), (2.1, 2.5, "punch"), (2.5, 99, "guard")],
                     "faces": [(2.1, "angry", False, "smirk")]},
            "mika": {"track": [(0, 226, True), (10.0, 110, True), (21.4, 112, True)],
                     "blocks": [(0, 6.4, "guard"), (6.4, 8.6, "mov"), (8.6, 99, "idle")],
                     "faces": [(15.4, "happy", False, "laugh")]},
            "kaba": {"track": [(0, 230, True), (0.45, 150, True), (0.62, 112, True),
                               (1.7, 112, True), (2.3, 188, True), (4.4, 236, True),
                               (13.1, 236, True), (13.65, 340, True), (21.4, 360, True)],
                     "blocks": [(0, 0.55, "guard"), (0.55, 0.75, "mov"), (0.75, 1.0, "punch"),
                                (1.0, 2.3, "guard"), (2.3, 3.4, "hurt"), (3.4, 12.9, "guard"),
                                (12.9, 13.5, "hurt"), (13.5, 99, "hurt")],
                     "faces": [(2.3, "x", True), (3.4, "angry", False), (12.3, "x", True)]},
        },
        "lines": [(1.2, "ren", "Rgh- cheap shot!"),
                  (4.0, "yuki", "My turn, spark-stealer."),
                  (5.2, "ren", "Mika said wake them up..."),
                  (8.3, "ren", "SO WE WAKE THEM UP."),
                  (15.8, "mika", "Look - the harbor is breathing again!"),
                  (18.9, "ren", "Whoever dimmed it owes me a sandwich.")],
        "audio": [(0.75, "boom", 0.85), (2.3, "whoosh", 0.9), (2.55, "thud", 0.7),
                  (4.9, "riser", 0.75), (8.3, "riser", 0.9), (11.9, "whoosh", 0.8),
                  (12.2, "thud", 0.9), (12.4, "boom", 1.0), (12.8, "boom", 0.9),
                  (15.4, "fanfare", 0.8), (15.6, "sparkle", 0.6)],
        "fx": [
            {"kind": "impact", "t": 0.75, "x": 92, "y": 92, "invert": True},
            {"kind": "kiai", "t": 0.75, "x": 92, "y": 92},
            {"kind": "slash", "t": 2.3, "x": 184, "y": 92},
            {"kind": "kiai", "t": 2.45, "x": 190, "y": 92},
            {"kind": "aura", "t0": 4.9, "t1": 11.9, "x_track": "ren", "hue": "gold"},
            {"kind": "impact", "t": 12.3, "x": 220, "y": 90, "invert": True, "word": "BAAM"},
            {"kind": "kiai", "t": 12.3, "x": 220, "y": 90},
            {"kind": "speedwin", "t0": 11.9, "t1": 12.6, "cx": 160, "cy": 92},
            {"kind": "speedwin", "t0": 12.75, "t1": 13.3, "cx": 216, "cy": 90},
        ],
        "dust_at": (13.5, 246),
    })
    # ============ 6) C-PART TEASE ========================================= #
    scenes.append({
        "env": ("dock", {"lights_on": True}), "dur": 7.2, "letterbox": 15,
        "cam": [{"kind": "zoom", "z": lambda t: 1.1 + min(1.0, t / 6.0) * 0.55,
                 "focus": (24, 70)}],
        "actors": {
            "hood": {"track": [(0, 26, False), (7.2, 26, False)], "y_off": -78,
                     "blocks": [(0, 2.2, "idle"), (2.2, 99, "point")], "faces": []},
            "ren": {"track": [(0, 150, True), (7.2, 150, True)],
                    "blocks": [(0, 99, "idle")], "faces": [(2.4, "wide", False)]},
        },
        "lines": [(1.2, "narr", "On the lighthouse, someone applauded. Slowly."),
                  (4.4, "ren", "...I heard that. Show yourself!")],
        "audio": [(2.2, "boom", 0.4)],
    })
    # ============ 7) NEXT EPISODE (jikai yokoku) ========================== #
    scenes.append({
        "env": ("preview", {"no": 2, "title": "The Girl in the Fog",
                            "lines": ["She dodged thunder once. Once was enough.",
                                      "Ren loses his sandwich. War is declared.",
                                      "Yuki draws his sword on the mist itself."]}),
        "dur": 6.4, "fadeout": 0.8,
        "lines": [(0.4, "narr", "Next time on Volt Breaker!")],
        "audio": [(0.2, "sparkle", 0.5)],
    })
    return scenes




def episode_002(cast):
    """EP002 'The Girl in the Fog'. Hook->OP->brief->skurk->eyecatch->fight->cpart->preview."""
    scenes = []
    # 0) COLD OPEN – statisk dimma, flickan ur tomrummet
    scenes.append({
        "env": ("dock", {}), "dur": 11.0, "letterbox": 14, "fadein": 0.7,
        "cam": [{"kind": "zoom", "z": lambda t: 1.1 + t * 0.008, "focus": (170, 100)}],
        "actors": {
            "ren": {"track": [(0.0, -30, False), (2.6, 96, False), (11.0, 96, False)],
                    "blocks": [(0, 2.6, "mov"), (2.6, 99, "idle")],
                    "faces": [(4.0, "wide", False)]},
            "mika": {"track": [(0.0, -70, False), (3.0, 140, False), (11.0, 140, False)],
                     "blocks": [(0, 3.0, "mov"), (3.0, 99, "idle")], "faces": []},
            "naya": {"track": [(3.0, 252, True), (11.0, 252, True)],
                     "blocks": [(0, 3.0, "none"), (3.0, 7.4, "idle"), (7.4, 99, "none")],
                     "faces": []},
            "hood": {"track": [(8.6, 296, True), (11.0, 296, True)], "y_off": -78,
                     "blocks": [(8.6, 99, "idle")], "faces": []},
        },
        "lines": [(1.0, "narr", "Morning came wrapped in static. The fog had a heartbeat."),
                  (5.0, "naya", "You should not hum the tower's lullaby back. It learns you."),
                  (8.4, "ren", "Okay. THAT was ominous. Even for this town.")],
        "audio": [(0.3, "boom", 0.4), (2.9, "sparkle", 0.5), (5.0, "riser", 0.35)],
    })
    # 1) OP-TITEL
    scenes.append({"env": ("title", {"series": SERIES,
                                     "episode": "EPISODE 002 - The Girl in the Fog"}),
                   "dur": 4.2, "audio": [(0.15, "boom", 0.9), (0.9, "riser", 0.7)]})
    # 2) A-PART: DOJON – smörgåstragedin + plan
    scenes.append({
        "env": ("dojo", {"door_t": 3.8, "bag_hits": (0.7, 1.5, 2.3)}), "dur": 13.6,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 if t < 5.0 else 1.16, "focus": (150, 96)}],
        "actors": {
            "ren": {"track": [(0, 72, True), (3.6, 72, True), (4.0, 88, False), (13.6, 100, False)],
                    "blocks": [(0.5, 0.78, "punch"), (0.78, 1.35, "idle"),
                               (1.35, 1.62, "punch"), (1.62, 2.2, "idle"),
                               (2.2, 2.48, "punch"), (2.48, 99, "idle")],
                    "faces": [(0.3, "angry", False, "grit"), (4.2, "normal", False),
                              (6.0, "sad", False)]},
            "mika": {"track": [(0, 288, False), (3.8, 210, True), (13.6, 200, True)],
                     "blocks": [(0, 3.8, "none"), (3.8, 5.4, "mov"), (5.4, 99, "point")],
                     "faces": [(5.4, "wide", False)]},
            "yuki": {"track": [(0, 150, False), (13.6, 150, False)],
                     "blocks": [(0, 99, "idle")], "faces": [(9.6, "angry", False)]},
        },
        "lines": [(4.4, "mika", "The tower's relay woke the fog. Naya says it eats voices."),
                  (8.8, "ren", "It ate my SANDWICH. It was on the dock. War is declared."),
                  (11.2, "yuki", "Good. Then we cut the fog. Literally.")],
        "audio": [(0.68, "thud", 0.8), (1.45, "thud", 0.8), (2.28, "thud", 0.9),
                  (3.8, "whoosh", 0.5), (8.7, "riser", 0.4)],
    })
    # 3) A-PART: KAJEN – skurken landar IGEN (mini-cliffhanger)
    scenes.append({
        "env": ("dock", {}), "dur": 12.8,
        "cam": [{"kind": "zoom", "z": lambda t: 1.05 if t < 3.4 else 1.14, "focus": (190, 100)},
                {"kind": "shake", "t0": 3.2, "t1": 3.7, "amp": 4}],
        "actors": {
            "ren": {"track": [(0, -34, False), (1.7, 84, False), (12.8, 84, False)],
                    "blocks": [(0, 1.8, "mov"), (1.8, 99, "idle")],
                    "faces": [(4.4, "angry", False)]},
            "yuki": {"track": [(0, -70, False), (2.0, 44, False), (12.8, 44, False)],
                     "blocks": [(0, 2.1, "mov"), (2.1, 99, "guard")], "faces": []},
            "naya": {"track": [(0, 252, True), (12.8, 230, True)],
                     "blocks": [(0, 99, "idle")], "faces": [(6.6, "sad", False)]},
            "kaba": {"track": [(0, 226, True), (12.8, 226, True)],
                     "blocks": [(0, 2.0, "none"), (2.0, 3.55, "hurt"), (3.55, 99, "guard")],
                     "faces": [(4.2, "angry", False)],
                     "drop": (3.2, -180)},
        },
        "lines": [(4.6, "kaba", "Back for the encore? The tower sings on MY frequency now."),
                  (8.8, "naya", "It swallowed my whole town, Kaba. Every voice in it."),
                  (11.4, "kaba", "Then hum along, ghost girl.")],
        "audio": [(3.2, "boom", 0.95), (4.5, "riser", 0.4), (11.3, "riser", 0.5)],
        "dust_at": (3.2, 226),
    })
    # 4-5) EYECATCH
    scenes.append({"env": ("eyecatch", {"who": "ren"}), "dur": 1.5,
                   "audio": [(0.05, "sparkle", 0.8)]})
    scenes.append({"env": ("eyecatch", {"who": "naya"}), "dur": 1.5,
                   "audio": [(0.05, "boom", 0.5)]})
    # 6) B-PART: DIM-FIGHT!
    scenes.append({
        "env": ("dock", {}), "dur": 20.5, "lights_on_at": 15.2,
        "cam": [{"kind": "zoom",
                 "z": lambda t: 1.1 if t < 5.0 else (1.22 if t < 13.2 else 1.08),
                 "focus": (170, 96)},
                {"kind": "shake", "t0": 0.75, "t1": 1.15, "amp": 4},
                {"kind": "shake", "t0": 12.5, "t1": 13.1, "amp": 6}],
        "actors": {
            "ren": {"track": [(0, 84, False), (1.0, 58, False), (4.8, 90, False),
                              (12.0, 96, False), (12.2, 196, False), (20.5, 200, False)],
                    "blocks": [(0, 0.75, "idle"), (0.75, 2.0, "hurt"), (2.0, 4.9, "idle"),
                               (4.9, 6.2, "point"), (6.2, 12.0, "idle"),
                               (12.0, 12.35, "mov"), (12.35, 12.65, "punch"),
                               (12.65, 12.9, "idle"), (12.9, 13.2, "punch"),
                               (13.2, 99, "idle")],
                    "faces": [(0.75, "x", True), (2.0, "sad", True), (4.9, "angry", False),
                              (15.6, "spark", False, "smirk")]},
            "naya": {"track": [(0, 250, True), (2.4, 150, True), (3.4, 250, True),
                               (20.5, 236, True)],
                     "blocks": [(0, 2.3, "idle"), (2.3, 2.9, "mov"), (2.9, 3.5, "mov"),
                                (3.5, 99, "point")],
                     "faces": [(1.2, "wide", False)]},
            "yuki": {"track": [(0, 40, False), (2.35, 162, False), (20.5, 172, False)],
                     "blocks": [(0, 2.3, "guard"), (2.3, 2.7, "punch"), (2.7, 99, "guard")],
                     "faces": [(2.3, "angry", False, "smirk")]},
            "mika": {"track": [(0, -60, False), (10.4, 112, True), (20.5, 112, True)],
                     "blocks": [(0, 6.6, "none"), (6.6, 8.8, "mov"), (8.8, 99, "idle")],
                     "faces": [(15.2, "happy", False, "laugh")]},
            "kaba": {"track": [(0, 228, True), (0.45, 150, True), (0.62, 112, True),
                               (1.7, 112, True), (2.3, 188, True), (13.0, 234, True),
                               (13.7, 330, True), (20.5, 350, True)],
                     "blocks": [(0, 0.75, "guard"), (0.75, 1.0, "punch"), (1.0, 2.3, "guard"),
                                (2.3, 3.4, "hurt"), (3.4, 12.8, "guard"),
                                (12.8, 13.4, "hurt"), (13.4, 99, "hurt")],
                     "faces": [(2.3, "x", True), (3.4, "angry", False), (12.5, "x", True)]},
        },
        "lines": [(1.2, "ren", "You owe this town an apology-"),
                  (3.8, "kaba", "Make me-"),
                  (5.0, "ren", "-AND A SANDWICH."),
                  (8.2, "naya", "Cover your ears. When the lullaby bends - DODGE."),
                  (15.6, "mika", "Lamps, round two. Port Kaminari - LIGHT UP."),
                  (18.8, "ren", "Next verse. Same punch.")],
        "audio": [(0.75, "boom", 0.85), (2.3, "whoosh", 0.9), (2.55, "thud", 0.7),
                  (4.9, "riser", 0.75), (5.0, "boom", 0.6), (12.0, "whoosh", 0.8),
                  (12.4, "thud", 0.9), (12.6, "boom", 1.0), (13.0, "boom", 0.9),
                  (15.2, "fanfare", 0.8), (15.4, "sparkle", 0.6)],
        "fx": [
            {"kind": "impact", "t": 0.75, "x": 92, "y": 92, "invert": True},
            {"kind": "kiai", "t": 0.75, "x": 92, "y": 92},
            {"kind": "slash", "t": 2.45, "x": 184, "y": 92},
            {"kind": "slash", "t": 3.1, "x": 200, "y": 88},
            {"kind": "aura", "t0": 4.9, "t1": 12.0, "x_track": "ren", "hue": "gold"},
            {"kind": "impact", "t": 12.55, "x": 220, "y": 90, "invert": True, "word": "BAAM"},
            {"kind": "kiai", "t": 12.55, "x": 220, "y": 90},
            {"kind": "speedwin", "t0": 12.0, "t1": 12.7, "cx": 160, "cy": 92},
            {"kind": "speedwin", "t0": 12.9, "t1": 13.5, "cx": 216, "cy": 90},
        ],
        "dust_at": (13.6, 244),
    })
    # 7) C-PART: tornet räknar hennes namn
    scenes.append({
        "env": ("dock", {"lights_on": True}), "dur": 7.4, "letterbox": 15,
        "cam": [{"kind": "zoom", "z": lambda t: 1.1 + min(1.0, t / 6.2) * 0.5,
                 "focus": (30, 72)}],
        "actors": {
            "hood": {"track": [(0, 30, False), (7.4, 30, False)], "y_off": -78,
                     "blocks": [(0, 2.4, "idle"), (2.4, 99, "point")], "faces": []},
            "naya": {"track": [(0, 140, False), (7.4, 140, False)],
                     "blocks": [(0, 99, "idle")], "faces": [(2.6, "sad", False)]},
            "ren": {"track": [(0, 190, True), (7.4, 190, True)],
                    "blocks": [(0, 99, "idle")], "faces": [(2.8, "wide", False)]},
        },
        "lines": [(1.2, "narr", "High above the harbor, the applause had learned a name."),
                  (4.6, "naya", "He counted my name once. He counts all of ours.")],
        "audio": [(2.2, "boom", 0.4)],
    })
    # 8) PREVIEW EP3
    scenes.append({
        "env": ("preview", {"no": 3, "title": "The Clockwork Tower",
                            "lines": ["The tower takes its first step. Villagers rate it zero stars.",
                                      "Kaba learns a new chord. Nobody asked for a solo.",
                                      "Naya's name is crossed off a very long list."]}),
        "dur": 6.4, "fadeout": 0.8,
        "lines": [(0.4, "narr", "Next time on Volt Breaker!")],
        "audio": [(0.2, "sparkle", 0.5)],
    })
    return scenes


def episode_003(cast):
    """EP003 'The Clockwork Tower' – stormningen av tornet."""
    scenes = []
    # 0) COLD OPEN mid-action: hjältarna springer, tornet GÅR
    scenes.append({
        "env": ("dock", {}), "dur": 10.8, "fadein": 0.5,
        "cam": [{"kind": "zoom", "z": lambda t: 1.14 + t * 0.005, "focus": (160, 100)},
                {"kind": "shake", "t0": 0.4, "t1": 2.2, "amp": 2}],
        "actors": {
            "ren": {"track": [(0, -30, False), (2.2, 120, False), (10.8, 150, False)],
                    "blocks": [(0, 99, "mov")], "faces": [(0.6, "angry", False)]},
            "yuki": {"track": [(0, -70, False), (2.6, 60, False), (10.8, 90, False)],
                     "blocks": [(0, 99, "mov")], "faces": []},
            "naya": {"track": [(0, -100, False), (3.0, 190, True), (10.8, 210, True)],
                     "blocks": [(0, 99, "mov")], "faces": [(4.0, "sad", False)]},
        },
        "lines": [(1.0, "narr", "Six steps. By dawn the tower had taken six steps toward town."),
                  (5.4, "ren", "Since when does the scary building do CARDIO?!"),
                  (8.2, "naya", "It is not walking. It is hunting a rhythm.")],
        "audio": [(0.35, "boom", 0.7), (1.2, "boom", 0.55), (5.3, "riser", 0.45)],
    })
    # 1) OP-TITEL
    scenes.append({"env": ("title", {"series": SERIES,
                                     "episode": "EPISODE 003 - The Clockwork Tower"}),
                   "dur": 4.2, "audio": [(0.15, "boom", 0.9), (0.9, "riser", 0.7)]})
    # 2) A-PART: DOJON – slagplanen
    scenes.append({
        "env": ("dojo", {"door_t": 3.4}), "dur": 12.4,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 if t < 4.6 else 1.16, "focus": (160, 96)}],
        "actors": {
            "mika": {"track": [(0, 288, False), (3.4, 200, True), (12.4, 196, True)],
                     "blocks": [(0, 3.4, "none"), (3.4, 5.0, "mov"), (5.0, 99, "point")],
                     "faces": [(5.0, "wide", False)]},
            "ren": {"track": [(0, 100, False), (12.4, 104, False)],
                    "blocks": [(0, 99, "idle")], "faces": [(6.6, "angry", False, "smirk")]},
            "yuki": {"track": [(0, 150, False), (12.4, 150, False)],
                     "blocks": [(0, 99, "guard")], "faces": [(9.0, "angry", False)]},
        },
        "lines": [(5.2, "mika", "Kaba's chord drives the legs. Kill the chord, drop the tower."),
                  (8.6, "yuki", "Good. I have been meaning to cut a chord."),
                  (10.8, "ren", "And I punch the tall parts. Team synergy.")],
        "audio": [(3.4, "whoosh", 0.5), (8.5, "riser", 0.35)],
    })
    # 3) A-PART: SKURK-ACKORDET (mini-cliffhanger)
    scenes.append({
        "env": ("dock", {}), "dur": 12.0,
        "cam": [{"kind": "zoom", "z": lambda t: 1.05 if t < 3.4 else 1.18, "focus": (190, 100)},
                {"kind": "shake", "t0": 3.2, "t1": 3.8, "amp": 5}],
        "actors": {
            "ren": {"track": [(0, -34, False), (1.6, 84, False), (12.0, 84, False)],
                    "blocks": [(0, 1.7, "mov"), (1.7, 99, "guard")],
                    "faces": [(4.2, "angry", False)]},
            "naya": {"track": [(0, 250, True), (2.0, 250, True), (3.6, 302, True),
                               (12.0, 302, True)],
                     "blocks": [(0, 2.1, "idle"), (2.1, 3.6, "mov"), (3.6, 99, "idle")],
                     "faces": [(8.4, "sad", False)]},
            "kaba": {"track": [(0, 226, True), (12.0, 226, True)],
                     "blocks": [(0, 2.0, "none"), (2.0, 3.55, "hurt"), (3.55, 99, "point")],
                     "faces": [(4.0, "angry", False)],
                     "drop": (3.2, -200)},
        },
        "lines": [(4.4, "kaba", "You brought the ghost to my concert? Front row seat, spark."),
                  (9.0, "kaba", "THE TOWER TAKES REQUESTS NOW. CHORD ONE: OBLITERATE.")],
        "audio": [(3.2, "boom", 0.95), (4.3, "riser", 0.4), (8.9, "boom", 0.9),
                  (9.4, "whoosh", 0.8)],
        "fx": [{"kind": "slash", "t": 9.6, "x": 190, "y": 92}],
        "dust_at": (3.2, 226),
    })
    # 4-5) EYECATCH
    scenes.append({"env": ("eyecatch", {"who": "ren"}), "dur": 1.5,
                   "audio": [(0.05, "sparkle", 0.8)]})
    scenes.append({"env": ("eyecatch", {"who": "kaba"}), "dur": 1.5,
                   "audio": [(0.05, "boom", 0.5)]})
    # 6) B-PART: TORNFIGHTEN
    scenes.append({
        "env": ("dock", {}), "dur": 21.0, "lights_on_at": 14.8,
        "cam": [{"kind": "zoom",
                 "z": lambda t: 1.12 if t < 5.0 else (1.25 if t < 13.4 else 1.06),
                 "focus": (170, 96)},
                {"kind": "shake", "t0": 0.75, "t1": 1.2, "amp": 4},
                {"kind": "shake", "t0": 12.7, "t1": 13.4, "amp": 7}],
        "actors": {
            "ren": {"track": [(0, 84, False), (1.0, 56, False), (4.9, 92, False),
                              (12.4, 96, False), (12.6, 196, False), (21.0, 200, False)],
                    "blocks": [(0, 0.75, "guard"), (0.75, 2.0, "hurt"), (2.0, 4.9, "idle"),
                               (4.9, 6.2, "point"), (6.2, 12.4, "guard"),
                               (12.4, 12.7, "mov"), (12.7, 13.0, "punch"),
                               (13.0, 13.3, "idle"), (13.3, 13.6, "punch"),
                               (13.6, 99, "idle")],
                    "faces": [(0.75, "x", True), (2.0, "sad", True), (4.9, "angry", False),
                              (15.0, "spark", False, "smirk")]},
            "naya": {"track": [(0, 248, True), (6.8, 128, True), (21.0, 128, True)],
                     "blocks": [(0, 6.6, "idle"), (6.6, 7.6, "mov"), (7.6, 99, "point")],
                     "faces": [(4.2, "wide", False)]},
            "yuki": {"track": [(0, 42, False), (2.35, 162, False), (21.0, 172, False)],
                     "blocks": [(0, 2.3, "guard"), (2.3, 2.75, "punch"), (2.75, 99, "guard")],
                     "faces": [(2.3, "angry", False, "smirk")]},
            "mika": {"track": [(0, -60, False), (10.8, 112, True), (21.0, 112, True)],
                     "blocks": [(0, 7.0, "none"), (7.0, 9.2, "mov"), (9.2, 99, "idle")],
                     "faces": [(14.8, "happy", False, "laugh")]},
            "kaba": {"track": [(0, 228, True), (0.45, 150, True), (0.62, 112, True),
                               (1.7, 112, True), (2.3, 188, True), (13.2, 232, True),
                               (13.9, 334, True), (21.0, 352, True)],
                     "blocks": [(0, 0.75, "guard"), (0.75, 1.05, "punch"), (1.05, 2.3, "guard"),
                                (2.3, 3.4, "hurt"), (3.4, 13.0, "guard"),
                                (13.0, 13.6, "hurt"), (13.6, 99, "hurt")],
                     "faces": [(2.3, "x", True), (3.4, "angry", False), (12.7, "x", True)]},
        },
        "lines": [(1.2, "ren", "Rgh- that chord HURTS!"),
                  (4.2, "naya", "Two verses, Ren. Then his strings go flat."),
                  (8.6, "ren", "Then we burn both verses-"),
                  (10.4, "ren", "-TOGETHER. VOLT BREAKER."),
                  (15.2, "mika", "The chord is cut. Kaminari - encore of LIGHT."),
                  (18.6, "ren", "Audience of one stays outs. Static stays gone.")],
        "audio": [(0.75, "boom", 0.85), (2.3, "whoosh", 0.9), (2.55, "thud", 0.7),
                  (4.9, "riser", 0.75), (10.4, "riser", 0.95), (12.4, "whoosh", 0.8),
                  (12.9, "thud", 0.9), (13.1, "boom", 1.0), (13.5, "boom", 0.9),
                  (14.8, "fanfare", 0.9), (15.0, "sparkle", 0.6)],
        "fx": [
            {"kind": "impact", "t": 0.75, "x": 92, "y": 92, "invert": True},
            {"kind": "kiai", "t": 0.75, "x": 92, "y": 92},
            {"kind": "slash", "t": 2.45, "x": 184, "y": 92},
            {"kind": "kiai", "t": 2.65, "x": 190, "y": 92},
            {"kind": "aura", "t0": 4.9, "t1": 12.4, "x_track": "ren", "hue": "gold"},
            {"kind": "aura", "t0": 0.0, "t1": 13.0, "x_track": "kaba", "hue": "violet"},
            {"kind": "impact", "t": 12.9, "x": 220, "y": 90, "invert": True, "word": "KRAKOOM"},
            {"kind": "kiai", "t": 12.9, "x": 220, "y": 90},
            {"kind": "speedwin", "t0": 12.4, "t1": 13.1, "cx": 160, "cy": 92},
            {"kind": "speedwin", "t0": 13.3, "t1": 13.9, "cx": 216, "cy": 90},
        ],
        "dust_at": (13.7, 242),
    })
    # 7) C-PART: tornet räknar BAKLÄNGES
    scenes.append({
        "env": ("dock", {"lights_on": True}), "dur": 7.4, "letterbox": 15,
        "cam": [{"kind": "zoom", "z": lambda t: 1.1 + min(1.0, t / 6.2) * 0.55,
                 "focus": (24, 70)}],
        "actors": {
            "hood": {"track": [(0, 26, False), (7.4, 26, False)], "y_off": -78,
                     "blocks": [(0, 2.4, "idle"), (2.4, 99, "point")], "faces": []},
            "ren": {"track": [(0, 152, True), (7.4, 152, True)],
                    "blocks": [(0, 99, "idle")], "faces": [(2.6, "wide", False)]},
            "naya": {"track": [(0, 116, False), (7.4, 116, False)],
                     "blocks": [(0, 99, "idle")], "faces": [(3.0, "sad", False)]},
        },
        "lines": [(1.2, "narr", "The tower slept. But somewhere, something still counted - backwards."),
                  (4.6, "ren", "...You again. Seriously - WHO are you?!")],
        "audio": [(2.2, "boom", 0.4)],
    })
    # 8) PREVIEW EP4
    scenes.append({
        "env": ("preview", {"no": 4, "title": "The Static Answers",
                            "lines": ["Countdown: four. Something big clears its throat.",
                                      "Yuki's sword hums at night. Swords should not hum.",
                                      "Ren names the hood 'Steve'. Steve does not object."]}),
        "dur": 6.4, "fadeout": 0.8,
        "lines": [(0.4, "narr", "Next time on Volt Breaker!")],
        "audio": [(0.2, "sparkle", 0.5)],
    })
    return scenes


# -------------------------------------------------------------------------- #
# RENDERER                                                                  #
# -------------------------------------------------------------------------- #
def _mood_for_line(who, text):
    """(eyes, mouth_open, mouth_closed, addons) medan repliken pågår.
    GRUNDREGEL: lugnt prat = mjuk neutral mun. Tänder (grit) bara vid hetta —
    annars ser ALLA arga ut hela tiden."""
    t = text or ""
    if "cheap shot" in t or "owes me" in t or "HURTS" in t:
        return ("sad", "open", "frown", ("sweat",))
    if "My turn" in t:
        return ("angry", "open", "smirk", ())
    if any(k in t for k in ("KIDS", "WAKE THEM", "Show yourself", "SANDWICH",
                            "wake them up", "Activate", "activating", "OBLITERATE")):
        return ("whiteout", "shout", "grit", ())
    TALK = {  # lugnt samtal: neutral läppsynk, personlighets-ögon
        "ren":  ("wide", "open", "closed", ()),
        "yuki": ("normal", "open", "frown", ()),
        "mika": ("wide", "open", "smile", ()),
        "kaba": ("angry", "open", "grit", ("vein",)),   # skurken FÅR behålla tänderna
        "naya": ("sad", "open", "closed", ()),
        "hood": ("normal", "closed", "closed", ()),
    }
    return TALK.get(who, ("wide", "open", "closed", ()))


def _shot_plan(lwins):
    """Shot-lista ur replikerna ((t0,t1,kind,who)) — anime-standardprogression:
    paus->breather(wide), skurk->low-angle, heta repliker->ECU+flash, resten MCU."""
    plan = []
    prev_end = -9.0
    for (who, text, t0, t1) in lwins:
        if who in ("narr", "hood"):
            prev_end = t1
            continue
        if t0 - prev_end >= 1.4 and prev_end > -5:
            plan.append((prev_end, t0, "breather", None))
        hot = any(k in (text or "") for k in ("KIDS", "WAKE THEM", "Show yourself",
                                              "SANDWICH", "ACTIVAT"))
        shot = "low" if who == "kaba" else ("ecu" if hot else "mcu")
        plan.append((t0, t1, shot, who))
        prev_end = t1
    return plan


class Renderer:
    def __init__(self, cast):
        self.cast = cast

    # -- per scen byggda aktörer (Actor = poser + track + faces + mun) ------
    def _mk_actors(self, scene, mouths):
        actors = {}
        for name, a in scene.get("actors", {}).items():
            act = E.Actor(self.cast[name], a["blocks"], E.Track(a["track"]), a.get("faces"))
            act.y_off = a.get("y_off", 0)
            act.drop = a.get("drop")
            act.mouth = mouths.get(name, np.zeros(0))
            act.mouth_off = 0
            actors[name] = act
        return actors

    def scene_frame(self, scene, env, actors, local_t):
        # miljö
        if isinstance(env, E.DockNight):
            lights = scene.get("lights_on_at") is not None and local_t >= scene["lights_on_at"] \
                     or getattr(env, "lights_on", False)
            img = env.frame(local_t, lights)
            E.fireflies(img, local_t)
        else:
            img = env.frame(local_t)
        d = ImageDraw.Draw(img, "RGBA")
        # damm vid landning
        if scene.get("dust_at"):
            dt, dx = scene["dust_at"]
            if dt <= local_t <= dt + 0.8:
                E.dust(img, dx, 140)
        # UNIVERSUM-TINT: färgfilter per värld (billig PIL-blend, CPU-vänlig)
        if scene.get("tint"):
            img = Image.blend(img.convert("RGB"),
                              Image.new("RGB", img.size, scene["tint"]), 0.22
                              ).convert("RGBA")
            d = ImageDraw.Draw(img, "RGBA")
        # AURA-FLAMMOR + PORTALER först (energi hör BAKOM karaktären)
        for fx in scene.get("fx", []):
            if fx["kind"] == "portal" and fx["t0"] <= local_t <= fx["t1"]:
                E.portal(img, fx["x"], fx["y"], local_t, seed=fx.get("seed", 0))
            elif fx["kind"] == "aura" and fx["t0"] <= local_t <= fx["t1"]:
                ax = actors[fx["x_track"]].track.at(local_t)[0] if fx.get("x_track") else fx["x"]
                E.aura(img, ax, E.GROUND, 96, local_t, fx.get("hue", "violet"))
        # BLICK: vem talar, var står denne?
        gwho, gx = None, None
        for lm in getattr(self, "line_moods", ()):
            mw, t0m, t1m = lm[0], lm[1], lm[2]
            if t0m <= local_t <= t1m and mw in actors:
                gwho = mw; gx = actors[mw].track.at(local_t)[0]; break
        # AUTO-SEPARATION: röriga gruppmoments: aldrig arm-i-arm när allt är lugn
        sep = {}
        order0 = sorted(actors.items(), key=lambda kv: kv[1].track.at(local_t)[0])
        for i2 in range(len(order0)):
            for j2 in range(i2 + 1, len(order0)):
                na, nb = order0[i2][0], order0[j2][0]
                xa = actors[na].track.at(local_t)[0]; xb = actors[nb].track.at(local_t)[0]
                pa = actors[na].pose_at(local_t); pb = actors[nb].pose_at(local_t)
                if pa in ("idle", "mov") and pb in ("idle", "mov"):
                    gap = abs(xb - xa)
                    if gap < 26:
                        push = (26 - gap) / 2 if gap > 0.5 else 13.0
                        sep[na] = sep.get(na, 0.0) - push
                        sep[nb] = sep.get(nb, 0.0) + push
        # DINO-JAGAREN: följer en aktör med fördröjning (försvinner aldrig helt)
        dn = scene.get("dino")
        if dn and dn.get("follow") in actors:
            if not hasattr(self, "_dino"):
                self._dino = E.Dino()
            ref = actors[dn.get("follow")]
            lt2 = max(0.0, local_t - dn.get("delay", 1.1))
            x_ref, fl_ref = ref.track.at(lt2)
            pose_ref = ref.pose_at(lt2)
            moving = pose_ref in ("mov", "walk1", "walk2")
            dx = x_ref + dn.get("xoff", -48)
            if dn.get("enter") and local_t < dn["enter"]:
                p = local_t / dn["enter"]
                dx = int(E._lerp(-80, dx, p * p))          # sprintar in från vänster
            hit_t = dn.get("hit_t")
            downed = hit_t is not None and local_t >= hit_t
            if downed:
                dx = dn.get("hit_x", dx)
            roar = any(r0 <= local_t <= r1 for r0, r1 in dn.get("roar", ()))
            spr = self._dino.sprite(local_t, moving and not downed, roar, downed)
            if fl_ref:                      # spriten är målad åt höger
                from PIL import ImageOps as _IO3
                spr = _IO3.mirror(spr)
            hop = int(abs(math.sin(local_t * 11)) * 4) if moving and not downed else 0
            img.alpha_composite(spr, (int(dx - spr.width * 0.55),
                                      E.GROUND - spr.height + 2 - hop))
            if downed and local_t < hit_t + 0.5:
                E.dust(img, int(dx), 138)
        # aktörer
        order = sorted(actors.items(), key=lambda kv: kv[1].track.at(local_t)[0])
        for name, act in order:
            pose = act.pose_at(local_t)
            if pose == "none":
                continue
            x, flip = act.track.at(local_t)
            if name in sep:
                x = int(round(x + sep[name]))
            # BLICK: idle-åhörare vänder sig alltid mot talaren (inte in i väggen!)
            if gwho and name != gwho and gx is not None and pose in ("idle",):
                flip = gx < x
            if pose == "mov":
                pose = "walk1" if int(local_t * 6) % 2 == 0 else "walk2"
            # auto-blink: 0.24s >= 2 frames @12fps (0.13s försvann mellan sampel)
            eyes, bruise, smouth = act.face_at(local_t)
            rng = random.Random(hash(name) & 0xffff)
            cyc = 2.4 + rng.random() * 1.9
            ph = rng.random() * cyc
            want_blink = ((local_t + ph) % cyc) < 0.24
            # mun: läppsynk har företräde, annars normal/stängd
            mouth = "closed"
            fi = int(local_t * FPSS)
            if fi < act.mouth.size and act.mouth[fi]:
                mouth = "open"
            if smouth and mouth == "closed":      # regisserad vilomun (smirk/laugh etc.)
                mouth = smouth
            # ---- DIREKTREAKTION: talarens ansikte byter mood i scenen ----
            addons = ()
            for (mw, t0m, t1m, meyes, mo_open, mo_closed, madd) in getattr(
                    self, "line_moods", ()):
                if mw == name and t0m <= local_t <= t1m:
                    if eyes == "normal":
                        eyes = meyes
                    mouth = mo_open if mouth == "open" else mo_closed
                    addons = madd
                    break
            # blink SLUTLIGEN: slår över lugna tillstånd även efter mood-override
            if want_blink and eyes in ("normal", "sad", "angry"):
                eyes = "blink"
            # BLICK (screen-space): gåendes åt färdhållet; lyssnare mot talaren;
            # annars lever blicken (L/C/R var ~3:e sek, seedat per karaktär)
            if pose in ("mov", "walk1", "walk2", "run"):
                gaze_scr = -1 if flip else 1
            elif gwho and name != gwho and gx is not None:
                gaze_scr = 1 if gx > x else -1
            else:
                r2 = random.Random((hash(name) & 0xffff) ^ 5150)
                cyc2 = 2.6 + r2.random() * 1.4
                step2 = int((local_t + r2.random() * cyc2) / cyc2)
                gaze_scr = random.Random(((hash(name) & 0xffff) ^ 91) + step2).choice(
                    (0, 0, -1, 1, 0))
            gaze_can = -gaze_scr if flip else gaze_scr     # bilden speglas efter full()
            # aura bakom karaktären hanteras av fx nedan (ordning: aura pre-actors)
            rig_pose = {"mov": "walk", "walk1": "walk", "walk2": "walk"}.get(pose, pose)
            ch_img = act.char.full(rig_pose, local_t, eyes, mouth, bruise, addons,
                                   gaze=gaze_can)
            if flip:
                from PIL import ImageOps as _IO
                ch_img = _IO.mirror(ch_img)
            bx = x - ch_img.width // 2
            by = E.GROUND - getattr(act.char, "ground_px", E.GROUND_CV) + act.y_off
            if act.drop and local_t < act.drop[0]:
                p = max(0.0, local_t / act.drop[0])
                by += int((1 - (p * p)) * act.drop[1])
            if eyes == "x" and pose == "hurt":      # knock-vibration
                bx += int(math.sin(local_t * 60) * 1.5)
            img.alpha_composite(ch_img, (bx, by))
            # idle-andning
        # ---- MIMI (Rens katt) — auto-följare med söt-SE --------------------
        if "ren" in actors and actors["ren"].pose_at(local_t) != "none":
            if not hasattr(self, "_neko"):
                self._neko = E.Neko()
            from PIL import ImageOps as _IO2
            rx0, _rf0 = actors["ren"].track.at(local_t)
            rx1, rf1 = actors["ren"].track.at(max(0.0, local_t - 0.55))
            speed = abs(rx0 - rx1) / 0.55 if local_t > 0.55 else 0.0
            moving = speed > 2.0
            cx = rx1 + (-16 if not rf1 else 16)          # hänger bakom Rens riktning
            spr = self._neko.sprite(local_t, moving)
            if not rf1:
                spr = _IO2.mirror(spr)
            hop = int(abs(math.sin(local_t * 7.0)) * 2.5) if moving else 0
            img.alpha_composite(spr, (int(cx - spr.width // 2),
                                      int(E.GROUND - spr.height + 1 - hop)))
            if not moving and local_t % 7 < 0.8:           # vänskap-hjärta var 7:e sekund
                E.px_heart(img, int(cx), int(E.GROUND - spr.height - 14
                                             - int(2 * math.sin(local_t * 6))))
        # fx-lager
        for fx in scene.get("fx", []):
            k = fx["kind"]
            if k == "impact" and fx["t"] <= local_t <= fx["t"] + 0.25:
                img = E.impact_flash(img, fx["t"], local_t, invert=fx.get("invert", False))
                d = ImageDraw.Draw(img, "RGBA")
                if fx.get("word"):
                    E.word_burst(img, fx["word"], fx["x"], fx["y"] - 30, fx["t"], local_t)
            elif k == "kiai" and fx["t"] <= local_t <= fx["t"] + 0.45:
                E.kiai(img, fx["x"], fx["y"])
            elif k == "slash":
                E.slash(img, fx["x"], fx["y"], fx["t"], local_t)
            elif k == "stamp" and fx["t0"] <= local_t <= fx["t1"] and not VERT_STAMPS_OUT:
                st = E.ptext(fx["text"], fx.get("scale", 2), fx.get("color", (246, 240, 200)))
                d.rectangle([fx["x"] - 4, fx["y"] - 3, fx["x"] + st.width + 6,
                             fx["y"] + st.height + 3], fill=(18, 20, 30, 190))
                img.alpha_composite(st, (fx["x"], fx["y"]))
            elif k == "speedwin" and fx["t0"] <= local_t <= fx["t1"]:
                E.speedlines(img, fx["cx"], fx["cy"])
            elif k == "blood" and fx["t"] <= local_t:
                E.blood(img, fx["x"], fx["y"], fx["t"], local_t)
        return img   # logisk 320x180 UBEN undertext (ritas efter kamera)

    def card_frame(self, card, local_t):
        return card.frame(local_t).resize((OUTW, OUTH), NEAREST)


# -------------------------------------------------------------------------- #
# MAIN                                                                      #
# -------------------------------------------------------------------------- #


# =========================================================================== #
# 9-5 — Säsongspiloten "Day 9413"                                           #
# =========================================================================== #
def build_cast95():
    base = build_cast()
    tom = E.AnimeChar("tom", {"H": (122, 84, 50), "S": (250, 215, 180), "T": (168, 152, 128),
                              "P": (52, 54, 64), "B": (70, 58, 50), "K": (24, 22, 28)},
                      hair="long", iris=(96, 84, 60), voice_pitch="tom", eyes_kind="soft",
                      scale_x=0.99, scale_y=1.02,
                      suit=E.Suit((168, 152, 128), (52, 54, 64), (70, 58, 50), (250, 215, 180),
                                  arm_w=5, leg_t=0.95, tor_w=10, hips=7))
    col = E.AnimeChar("col", {"H": (60, 60, 70), "S": (240, 205, 175), "T": (60, 90, 150),
                              "P": (44, 46, 56), "B": (66, 54, 44), "K": (24, 22, 28)},
                      hair="hawk", iris=(90, 120, 90), voice_pitch="col", eyes_kind="default",
                      scale_x=1.0, scale_y=1.0,
                      suit=E.Suit((60, 90, 150), (44, 46, 56), (66, 54, 44), (240, 205, 175),
                                  arm_w=6, tor_w=12, hips=8))
    return {"tom": tom, "col": col, "narr": base["hood"]}


def episode_905(cast):
    sc = []
    # 0) TITLE
    sc.append({"env": ("title", {"series": "9-5", "episode": "EP001 - DAY 9413"}),
               "dur": 4.2, "audio": [(0.3, "boom", 0.5), (3.0, "riser", 0.5)], "mood": "title"})
    # 1) STREET cold hook (återskådeskuggan av bussen!)
    sc.append({
        "env": ("street", {"hit_t": None}), "dur": 8.4, "letterbox": 15, "fadein": 0.8,
        "mood": "ominous",
        "cam": [{"kind": "pan", "x": lambda t: 196 - t * 7.6}],
        "actors": {
            "tom": {"track": [(0, 236, True), (2.6, 148, True), (8.4, 104, True)],
                    "blocks": [(0, 8.4, "mov")], "faces": [(2.0, "sad", True)]},
        },
        "lines": [(0.8, "narr", "Day 9 413. Alarm city. Monday, again."),
                  (4.7, "tom", "The rain did not ask permission. Neither did I.")],
        "audio": [(0.6, "boom", 0.4), (7.1, "riser", 0.4)]})
    # 2) MORGON Day 1 (lägenheten)
    sc.append({
        "env": ("apartment", {}), "dur": 8.6, "mood": "cozy",
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.017, "focus": (96, 96)}],
        "actors": {
            "tom": {"track": [(0, 34, False), (2.0, 34, False), (5.0, 96, False), (8.6, 100, False)],
                    "blocks": [(0, 2.0, "idle"), (2.0, 5.0, "walk1"), (5.0, 8.6, "idle")],
                    "faces": [(0.4, "sad", False), (6.2, "normal", False)]},
        },
        "fx": [{"kind": "stamp", "t0": 0.5, "t1": 3.6, "text": "DAY 1", "x": 20, "y": 22}],
        "lines": [(1.2, "tom", "Day 1. The alarm chose violence."),
                  (5.6, "tom", "Shower is a threat, not a place.")],
        "audio": [(0.05, "alarm", 0.9), (0.5, "alarm", 0.7), (1.1, "thud", 0.6)]})
    # 3) DAY 243 (samma lägenhet)
    sc.append({
        "env": ("apartment", {}), "dur": 4.4, "mood": "cozy",
        "actors": {
            "tom": {"track": [(0, 34, False), (2.0, 96, False), (4.4, 98, False)],
                    "blocks": [(0, 0.8, "idle"), (0.8, 2.0, "walk1"), (2.0, 4.4, "idle")],
                    "faces": [(1.6, "sad", False)]},
        },
        "fx": [{"kind": "stamp", "t0": 0.3, "t1": 3.2, "text": "DAY 243", "x": 20, "y": 22}],
        "lines": [(1.1, "narr", "Day 243. The coffee tasted like screenshots.")],
        "audio": [(0.05, "alarm", 0.7)]})
    # 4) DAY 9412 (samma lägenhet)
    sc.append({
        "env": ("apartment", {}), "dur": 3.8, "mood": "cozy",
        "actors": {
            "tom": {"track": [(0, 34, False), (1.6, 96, False), (3.8, 96, False)],
                    "blocks": [(0, 0.6, "idle"), (0.6, 1.6, "walk1"), (1.6, 3.8, "idle")],
                    "faces": [(0.2, "sad", False)]},
        },
        "fx": [{"kind": "stamp", "t0": 0.2, "t1": 2.6, "text": "DAY 9 412", "x": 20, "y": 22}],
        "lines": [(0.7, "narr", "Day 9,412... still counting.")],
        "audio": [(0.05, "alarm", 0.6)]})
    # 5) PERRONG: tåget sveper förbi
    sc.append({
        "env": ("platform", {"train_t": 3.4}), "dur": 9.2, "mood": "ominous",
        "cam": [{"kind": "pan", "x": lambda t: 148 + t * 2.2}],
        "actors": {
            "tom": {"track": [(0, 168, False), (9.2, 168, False)],
                    "blocks": [(0, 9.2, "idle")],
                    "faces": [(0.4, "sad", False), (6.4, "normal", False)]},
        },
        "lines": [(0.7, "narr", "Same train. Same seat. Same song stuck to the seat."),
                  (6.2, "tom", "I move numbers. Nobody knows where to.")],
        "audio": [(3.3, "rumble", 0.95), (5.4, "whoosh", 0.7)]})
    # 6) KONTOR
    sc.append({
        "env": ("office", {}), "dur": 9.4, "mood": "mystery",
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.013, "focus": (200, 96)}],
        "actors": {
            "tom": {"track": [(0, 204, False), (9.4, 206, False)],
                    "blocks": [(0, 9.4, "idle")],
                    "faces": [(1.4, "normal", False), (5.8, "wide", False),
                              (6.6, "sad", False)]},
            "col": {"track": [(5.6, -34, False), (7.8, 250, False), (9.4, 292, False)],
                    "blocks": [(0, 5.6, "none"), (5.6, 9.4, "mov")],
                    "faces": [(6.0, "happy", False)]},
        },
        "fx": [],
        "lines": [(0.8, "narr", "Day 9 413. His job: move numbers from left to right."),
                  (5.6, "col", "Hey Tom!"),
                  (6.4, "tom", "..."),
                  (7.6, "narr", "The hello arrived one desk too late.")],
        "audio": []})
    # 7) GATAN + BUSSEN (hit!)
    sc.append({
        "env": ("street", {"hit_t": 6.2}), "dur": 10.0, "letterbox": 13, "fadeout": 0.55,
        "mood": "menace",
        "cam": [{"kind": "pan", "x": lambda t: 140 - t * 4.6},
                {"kind": "shake", "t0": 6.2, "t1": 6.8, "amp": 5}],
        "actors": {
            "tom": {"track": [(0, 148, True), (2.0, 66, True), (4.6, 66, True),
                              (5.2, 76, False), (6.0, 94, False), (6.15, 96, False),
                              (6.9, 96, False), (10, 96, False)],
                    "blocks": [(0, 2.0, "mov"), (2.0, 4.6, "idle"), (4.8, 5.6, "walk1"),
                               (6.2, 6.5, "hurt"), (6.5, 10, "fall")],
                    "faces": [(0.4, "normal", True), (2.2, "sad", True),
                              (5.1, "wide", False), (6.2, "whiteout", False)]},
        },
        "lines": [(0.8, "narr", "The 42 never honked before. It knew him by heart."),
                  (3.4, "tom", "Green again. Story of my li-")],
        "fx": [{"kind": "impact", "t": 6.2, "x": 102, "y": 96, "invert": True},
               {"kind": "blood", "t": 6.22, "x": 96, "y": 140},
               {"kind": "stamp", "t0": 4.85, "t1": 6.18, "text": "!!", "scale": 4,
                "x": 88, "y": 44, "color": (235, 60, 50)}],
        "audio": [(4.9, "horn", 1.0), (5.6, "rumble", 0.9), (6.2, "boom", 1.0)]})
    # 8) VOID: reboot
    sc.append({
        "env": ("void", {}), "dur": 9.2, "fadein": 0.9, "mood": "mystery",
        "actors": {
            "tom": {"track": [(0, 160, False), (9.2, 160, False)],
                    "blocks": [(0, 9.2, "idle")],
                    "faces": [(0.3, "wide", False), (2.8, "spark", False),
                              (5.4, "normal", False)]},
        },
        "lines": [(1.0, "narr", "Then: nothing. And then: this clean, white room."),
                  (4.2, "tom", "...this is not the 42."),
                  (6.6, "narr", "CONTINUE?")],
        "fx": [{"kind": "stamp", "t0": 6.8, "t1": 9.2, "text": "PLAYER 2 READY",
                "x": 108, "y": 24, "color": (140, 170, 220)}],
        "audio": [(0.2, "sparkle", 0.5), (6.6, "sparkle", 0.6)]})
    # 9) PREVIEW
    sc.append({"env": ("preview", {"no": 2, "title": "LEVEL 0 - THE TUTORIAL",
                                   "lines": ["tom wakes in an RPG world",
                                              "a cat deity picks the save file",
                                              "bus-kun returns... RUN"]}),
               "dur": 5.6, "fadein": 0.4, "mood": "happy"})
    return sc




def episode_905v(cast):
    """9-5 VERT v3 — RAY-WILLIAM-JOHNSON storytime. 10 berättar-repliker,
    orsak->verkan: 5-min-hook -> loopen -> Dave-gag -> grönt ljus -> bussen ->
    void-twist (livet var tutorialn). Word-sync captions + levande ögon.
    Tider låsta mot uppmätta TTS-längder (tts/line00-09, stretch x0.82)."""
    sc = []
    # 0) HOOK (0-5.5): "five minutes to live" — countdown-retention
    sc.append({
        "env": ("street", {"hit_t": None, "green_t": None}), "dur": 5.5, "fadein": 0.25,
        "mood": "ominous",
        "actors": {
            "tom": {"track": [(0, 250, True), (3.2, 150, True), (5.5, 110, True)],
                    "blocks": [(0, 5.5, "mov")], "faces": [(1.4, "sad", False)]},
        },
        "lines": [(0.35, "narr", "This is Tom. Tom has exactly five minutes to live.")],
        "audio": [(0.15, "boom", 0.35), (4.35, "horn", 0.2)]})
    # 1) LOOPEN (5.5-12.0): samma morgon, DAY 1
    sc.append({
        "env": ("apartment", {}), "dur": 6.5, "mood": "cozy",
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.016, "focus": (96, 96)}],
        "actors": {
            "tom": {"track": [(0, 34, False), (1.8, 34, False), (4.4, 96, False),
                              (6.5, 98, False)],
                    "blocks": [(0, 1.8, "idle"), (1.8, 4.4, "walk1"), (4.4, 6.5, "idle")],
                    "faces": [(0.4, "sad", False), (4.0, "normal", False)]},
        },
        "fx": [{"kind": "stamp", "t0": 0.5, "t1": 4.4, "text": "DAY 1", "scale": 7,
                "x": 403, "y": 170}],
        "lines": [(0.45, "narr",
                   "Every morning is the same morning. Alarm. Coffee. Coat. Repeat.")],
        "audio": [(0.05, "alarm", 0.9), (0.5, "alarm", 0.7), (2.0, "thud", 0.6)]})
    # 2) ESKALATION (12.0-16.6): DAY 9 412, punch-zoom + shake
    sc.append({
        "env": ("apartment", {}), "dur": 4.6, "mood": "cozy",
        "cam": [{"kind": "zoom", "z": lambda t: 1.14, "focus": (96, 96)},
                {"kind": "shake", "t0": 0.0, "t1": 0.35, "amp": 3}],
        "actors": {
            "tom": {"track": [(0, 34, False), (1.4, 96, False), (4.6, 96, False)],
                    "blocks": [(0, 0.5, "idle"), (0.5, 1.4, "walk1"), (1.4, 4.6, "idle")],
                    "faces": [(0.3, "sad", False)]},
        },
        "fx": [{"kind": "stamp", "t0": 0.25, "t1": 3.2, "text": "DAY", "scale": 7,
                "x": 452, "y": 150},
               {"kind": "stamp", "t0": 0.25, "t1": 3.2, "text": "9 412", "scale": 6,
                "x": 423, "y": 330}],
        "lines": [(0.35, "narr", "Nine thousand. Four hundred. And twelve.")],
        "audio": [(0.05, "alarm", 0.8)]})
    # 3) TÅGET (16.6-23.4)
    sc.append({
        "env": ("platform", {"train_t": 2.2}), "dur": 6.8, "mood": "ominous",
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.02, "focus": (168, 96)}],
        "actors": {
            "tom": {"track": [(0, 168, False), (6.8, 168, False)],
                    "blocks": [(0, 6.8, "idle")],
                    "faces": [(0.4, "sad", False), (4.6, "normal", False)]},
        },
        "lines": [(0.5, "narr",
                   "Same train. Same seat. Same guy humming. Every single day.")],
        "audio": [(2.1, "rumble", 0.95), (3.5, "whoosh", 0.7)]})
    # 4) KONTORET + DAVE-GAGEN (23.4-36.3): vinkar -> ignoreras -> går hängd
    sc.append({
        "env": ("office", {}), "dur": 12.9, "mood": "mystery",
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.012, "focus": (204, 96)}],
        "actors": {
            "tom": {"track": [(0, 204, False), (12.9, 206, False)],
                    "blocks": [(0, 12.9, "idle")], "faces": [(1.0, "normal", False)]},
            "col": {"track": [(6.5, -34, False), (7.4, 176, False), (8.0, 180, False),
                              (9.1, 178, True), (11.5, -40, True)],
                    "blocks": [(0, 6.5, "none"), (6.5, 7.4, "mov"), (7.4, 7.7, "idle"),
                               (7.7, 8.3, "point"), (8.3, 8.9, "idle"),
                               (8.9, 11.5, "mov")],
                    "faces": [(6.0, "happy", False), (9.2, "sad", False)]},
        },
        "lines": [(0.4, "narr",
                   "At work, Tom moves numbers from one box... to another box. It means nothing."),
                  (6.4, "narr",
                   "This is Dave. Dave waves at Tom every day. Tom has NEVER waved back.")],
        "audio": [(7.6, "pop", 0.45), (7.95, "bonk", 0.4)]})
    # 5) NEDRÄKNING (36.3-41.8): grönt ljus (green_t 1.9 ~ "goes green"-ordet)
    sc.append({
        "env": ("street", {"hit_t": None, "green_t": 1.9}), "dur": 5.5, "mood": "menace",
        "cam": [{"kind": "zoom", "z": lambda t: 1.05 + t * 0.01, "focus": (90, 96)}],
        "actors": {
            "tom": {"track": [(0, 150, True), (1.7, 66, True), (5.5, 66, True)],
                    "blocks": [(0, 1.7, "mov"), (1.7, 5.5, "idle")],
                    "faces": [(2.0, "normal", False)]},
        },
        "lines": [(0.5, "narr",
                   "Five oh one PM. The light goes green. It's always green.")],
        "audio": [(1.9, "sparkle", 0.5)]})
    # 6) BUSSEN (41.8-47.8): talet tar slut 4.4 -> hit 4.52 = andhämtningen man hinner
    sc.append({
        "env": ("street", {"hit_t": 4.52, "green_t": 0.0}), "dur": 6.0,
        "music_vol": 0.85, "mood": "menace", "fadeout": 0.5,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.03, "focus": (85, 96)},
                {"kind": "shake", "t0": 4.52, "t1": 5.1, "amp": 5}],
        "actors": {
            "tom": {"track": [(0, 70, True), (3.6, 70, True), (4.3, 92, False),
                              (6.0, 94, False)],
                    "blocks": [(0, 3.6, "idle"), (3.6, 4.3, "walk1"), (4.3, 4.52, "idle"),
                               (4.52, 4.9, "hurt"), (4.9, 99, "fall")],
                    "faces": [(3.5, "wide", False), (4.52, "whiteout", True)]},
        },
        "lines": [(0.4, "narr", "But today? The number forty two bus has other plans.")],
        "fx": [{"kind": "impact", "t": 4.52, "x": 100, "y": 96, "invert": True},
               {"kind": "blood", "t": 4.54, "x": 94, "y": 140},
               {"kind": "stamp", "t0": 3.7, "t1": 4.49, "text": "!!", "scale": 14,
                "x": 400, "y": 520, "color": (235, 60, 50)}],
        "audio": [(3.2, "horn", 1.0), (3.55, "rumble", 0.9), (4.52, "boom", 1.0)]})
    # 7) VOID (47.8-61.3): nästan-tyst pattern interrupt -> twist: livet = tutorialn
    sc.append({
        "env": ("void", {}), "dur": 13.5, "fadein": 0.8, "mood": "mystery",
        "music_vol": 0.2,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.007, "focus": (160, 90)}],
        "actors": {
            "tom": {"track": [(0, 160, False), (13.5, 160, False)],
                    "blocks": [(0, 13.5, "idle")],
                    "faces": [(0.3, "wide", False), (2.8, "sad", False),
                              (4.8, "normal", False), (11.8, "spark", False),
                              (13.0, "normal", False)]},
        },
        "lines": [(1.0, "narr", "Then? Nothing. No alarm. No Dave. Just... white."),
                  (6.9, "narr",
                   "Turns out Tom's whole life... was the tutorial. Level one starts NOW.")],
        "fx": [{"kind": "stamp", "t0": 7.0, "t1": 9.3, "text": "LEVEL 0", "scale": 8,
                "x": 328, "y": 240, "color": (140, 170, 220)},
               {"kind": "stamp", "t0": 12.2, "t1": 13.5, "text": "CONTINUE?", "scale": 7,
                "x": 300, "y": 240, "color": (140, 170, 220)},
               {"kind": "stamp", "t0": 12.2, "t1": 13.5, "text": "Y / N", "scale": 7,
                "x": 410, "y": 420, "color": (246, 240, 200)}],
        "audio": [(0.3, "sparkle", 0.35), (7.1, "riser", 0.4), (12.3, "sparkle", 0.55)]})
    # 8) LOOPBAIT-KORT (61.3-63.3)
    sc.append({"env": ("vcard", {"big": "9-5", "subtitle": "LIFE WAS LEVEL 0",
                                  "lines": ["day 9413: he quit", "the bus remembers",
                                            "follow for part 2"],
                                  "tone": (26, 34, 62)}),
               "dur": 2.0, "fadein": 0.25, "mood": "sting",
               "audio": [(0.1, "pop", 0.5)]})
    return sc


# =========================================================================== #
# PORTAL FIGHT — Rick&Morty-inspirerad multiversum-jakt                       #
# =========================================================================== #
def build_cast_rm():
    rex = E.AnimeChar("rex", {"H": (140, 190, 225), "S": (245, 235, 225),
                              "T": (238, 238, 244), "P": (110, 98, 74),
                              "B": (58, 54, 48), "K": (24, 22, 28)},
                      hair="spiky", iris=(20, 20, 26), voice_pitch="ren",
                      eyes_kind="rm", scale_x=1.0, scale_y=1.03,
                      suit=E.Suit((238, 238, 244), (110, 98, 74), (58, 54, 48),
                                  (245, 235, 225), arm_w=4, tor_w=10, hips=7))
    milo = E.AnimeChar("milo", {"H": (110, 80, 45), "S": (250, 215, 180),
                                "T": (250, 210, 55), "P": (78, 108, 160),
                                "B": (70, 60, 50), "K": (24, 22, 28)},
                       hair="short", iris=(20, 20, 26), voice_pitch="mika",
                       eyes_kind="rm", scale_x=0.97, scale_y=0.94,
                       suit=E.Suit((250, 210, 55), (78, 108, 160), (70, 60, 50),
                                   (250, 215, 180), arm_w=4, tor_w=9, hips=7))
    return {"rex": rex, "milo": milo, "narr": rex}


def episode_910portal(cast):
    """PORTAL FIGHT ep001 — de springer genom universum, raptorn jagar,
    bussen från 9-5 löser det. Brainrot-takt: zoom-punch var 2-3s, stamps,
    dinos head-fakes, K.O. Tider låsas mot uppmätta TTS-wavs (tts910/)."""
    sc = []
    # 0) KALLSTART: ut ur portalen in i voiden
    sc.append({
        "env": ("void", {}), "dur": 5.4, "mood": "mystery", "music_vol": 1.2,
        "fadein": 0.1, "anchor_off": -48,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.012 + max(0.0, 0.22 - t * 0.5),
                 "focus": (170, 96)}],
        "actors": {
            "rex": {"track": [(0, 126, False), (2.4, 262, False), (5.4, 266, False)],
                    "blocks": [(0, 2.4, "mov"), (2.4, 5.4, "idle")],
                    "faces": [(0.3, "wide", False), (3.0, "normal", False)]},
            "milo": {"track": [(0, 100, False), (2.4, 236, False), (5.4, 240, False)],
                     "blocks": [(0, 2.4, "mov"), (2.4, 5.4, "idle")],
                     "faces": [(0.4, "wide", False)]},
        },
        "fx": [{"kind": "portal", "t0": 0.0, "t1": 5.4, "x": 132, "y": 96, "seed": 1},
               {"kind": "stamp", "t0": 1.0, "t1": 2.2, "text": "STOLEN GOODS",
                "scale": 6, "x": 300, "y": 150}],
        "lines": [(0.4, "narr", "So they stole a portal gun. The multiverse objected.")],
        "audio": [(0.15, "whoosh", 0.9), (0.3, "boom", 0.5), (2.6, "rumble", 0.5),
                  (0.2, "sparkle", 0.6)]})
    # 1) DOCK-REGNET: teaser!
    sc.append({
        "env": ("dock", {}), "dur": 5.6, "mood": "menace", "music_vol": 1.2,
        "fadein": 0.1, "anchor_off": -48,
        "cam": [{"kind": "zoom", "z": lambda t: 1.03 + t * 0.015, "focus": (150, 96)}],
        "actors": {
            "rex": {"track": [(0, -10, False), (5.05, 258, False), (5.6, 258, False)],
                    "blocks": [(0, 5.05, "mov"), (5.05, 5.6, "idle")],
                    "faces": [(0.5, "wide", False), (2.6, "normal", False)]},
            "milo": {"track": [(0, -46, False), (5.05, 222, False), (5.6, 222, False)],
                     "blocks": [(0, 5.05, "mov"), (5.05, 5.6, "idle")],
                     "faces": [(0.5, "wide", False)]},
        },
        "dino": {"follow": "milo", "delay": 0.55, "xoff": -32, "enter": 0.9,
                "roar": [(1.6, 2.3)]},
        "fx": [{"kind": "portal", "t0": 2.6, "t1": 5.6, "x": 268, "y": 96, "seed": 2},
               {"kind": "impact", "t": 5.05, "x": 252, "y": 92, "invert": True},
               {"kind": "stamp", "t0": 0.5, "t1": 1.7, "text": "TEETH POPULATION: 1",
                "scale": 6, "x": 270, "y": 150}],
        "lines": [(0.5, "narr", "First stop: rain city. Population... teeth.")],
        "audio": [(1.6, "rumble", 0.8), (4.95, "whoosh", 0.9), (5.05, "boom", 0.8)]})
    # 2) KONTORS-DJUNGELN: HR vs raptor
    sc.append({
        "env": ("office", {}), "dur": 6.5, "mood": "mystery", "music_vol": 1.1,
        "tint": (30, 70, 34), "fadein": 0.1, "anchor_off": -42,
        "cam": [{"kind": "zoom", "z": lambda t: 1.04 + t * 0.012, "focus": (170, 96)}],
        "actors": {
            "rex": {"track": [(0, -10, False), (3.4, 170, False), (5.85, 240, False),
                              (6.5, 240, False)],
                    "blocks": [(0, 5.85, "mov"), (5.85, 6.5, "idle")],
                    "faces": [(0.4, "wide", False), (3.0, "normal", False)]},
            "milo": {"track": [(0, -46, False), (3.4, 134, False), (5.85, 204, False),
                               (6.5, 204, False)],
                     "blocks": [(0, 5.85, "mov"), (5.85, 6.5, "idle")],
                     "faces": [(0.4, "wide", False)]},
        },
        "dino": {"follow": "milo", "delay": 0.5, "xoff": -34, "enter": 0.8,
                "roar": [(2.0, 2.6)]},
        "fx": [{"kind": "portal", "t0": 3.4, "t1": 6.5, "x": 262, "y": 96, "seed": 3},
               {"kind": "impact", "t": 5.9, "x": 240, "y": 92, "invert": True},
               {"kind": "stamp", "t0": 0.4, "t1": 1.6, "text": "JUNGLE HR",
                "scale": 6, "x": 320, "y": 140},
               {"kind": "stamp", "t0": 2.8, "t1": 4.0, "text": "RAPTORS > HR",
                "scale": 5, "x": 300, "y": 300}],
        "lines": [(0.5, "narr",
                   "This universe has HR. And raptors. The raptors are nicer.")],
        "audio": [(2.0, "rumble", 0.7), (2.1, "boing", 0.5), (5.8, "whoosh", 0.9),
                  (5.9, "boom", 0.8)]})
    # 3) GATAN: bussen från 9-5 hittar sin sanna kallelse (DINON!)
    sc.append({
        "env": ("street", {"hit_t": 3.55, "green_t": 0.0}), "dur": 5.4,
        "mood": "menace", "music_vol": 1.1, "fadein": 0.1, "anchor_off": -35,
        "cam": [{"kind": "zoom", "z": lambda t: 1.05 + t * 0.01, "focus": (110, 96)},
                {"kind": "shake", "t0": 3.55, "t1": 4.1, "amp": 5}],
        "actors": {
            "rex": {"track": [(0, 160, False), (3.2, 160, False), (5.4, 160, True)],
                    "blocks": [(0, 3.3, "idle"), (3.3, 4.3, "point"), (4.3, 5.4, "idle")],
                    "faces": [(3.4, "happy", False)]},
            "milo": {"track": [(0, 124, True), (5.4, 124, True)],
                     "blocks": [(0, 5.4, "idle")],
                     "faces": [(0.3, "wide", False), (3.6, "happy", False)]},
        },
        "dino": {"follow": "milo", "delay": 0.7, "xoff": -20, "enter": 1.6,
                "roar": [(2.2, 2.8)], "hit_t": 3.55, "hit_x": 96},
        "lines": [(0.4, "narr",
                   "Then the bus found its true calling. Dinosaurs.")],
        "fx": [{"kind": "impact", "t": 3.55, "x": 100, "y": 110, "invert": True},
               {"kind": "blood", "t": 3.57, "x": 96, "y": 140},
               {"kind": "stamp", "t0": 3.75, "t1": 5.3, "text": "K.O.", "scale": 10,
                "x": 430, "y": 160, "color": (120, 255, 140)}],
        "audio": [(2.95, "horn", 0.9), (3.3, "horn", 0.8), (3.2, "rumble", 0.8),
                  (3.55, "boom", 1.0)]})
    # 4) VOID-FINAL: portalerna multipliceras
    sc.append({
        "env": ("void", {}), "dur": 6.1, "mood": "mystery", "music_vol": 0.5,
        "fadein": 0.1,
        "cam": [{"kind": "zoom", "z": lambda t: 1.0 + t * 0.014, "focus": (160, 96)},
                {"kind": "shake", "t0": 4.8, "t1": 5.3, "amp": 3}],
        "actors": {
            "rex": {"track": [(0, 150, False), (6.1, 150, False)],
                    "blocks": [(0, 6.1, "idle")],
                    "faces": [(0.4, "wide", False), (3.9, "sad", False)]},
            "milo": {"track": [(0, 176, False), (6.1, 176, False)],
                     "blocks": [(0, 6.1, "idle")],
                     "faces": [(0.4, "wide", False), (2.2, "sad", False)]},
        },
        "fx": [{"kind": "portal", "t0": 0.3, "t1": 6.1, "x": 120, "y": 96, "seed": 4},
               {"kind": "portal", "t0": 0.6, "t1": 6.1, "x": 165, "y": 96, "seed": 5},
               {"kind": "portal", "t0": 0.9, "t1": 6.1, "x": 210, "y": 96, "seed": 6},
               {"kind": "stamp", "t0": 0.4, "t1": 2.0, "text": "MULTIVERSE.EXE",
                "scale": 6, "x": 300, "y": 140},
               {"kind": "stamp", "t0": 2.0, "t1": 4.2, "text": "NOT RESPONDING",
                "scale": 6, "x": 300, "y": 300, "color": (255, 120, 100)}],
        "lines": [(0.5, "narr",
                   "Bad news. The raptors downloaded the portal app. Part two?")],
        "audio": [(0.4, "sparkle", 0.5), (0.7, "sparkle", 0.5), (1.0, "sparkle", 0.5),
                  (3.9, "riser", 0.5), (4.8, "boom", 0.6)]})
    # 5) LOOPBAIT-KORT
    sc.append({"env": ("vcard", {"big": "PORTAL", "subtitle": "FIGHT - part 2?",
                                  "lines": ["the raptors have wifi",
                                            "dino.exe downloaded",
                                            "follow or get chased"],
                                  "tone": (18, 42, 26)}),
               "dur": 1.6, "fadein": 0.1, "mood": "sting", "music_vol": 1.2,
               "audio": [(0.1, "pop", 0.6)]})
    return sc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", type=int, default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument("--vertical", action="store_true")
    ap.add_argument("--tts", action="store_true")
    args = ap.parse_args()

    if getattr(args, "vertical", False) or args.ep == 910:
        globals()["VERT"] = True
        globals()["VERT_STAMPS_OUT"] = True
        globals()["OUTW"], globals()["OUTH"] = 1080, 1920
    if getattr(args, "tts", False):
        globals()["TTS_MODE"] = True
        print("   🎙 TTS MODE: tts/line00-NN.wav används som röster")
    cast = (build_cast_rm() if args.ep == 910 else
            build_cast95() if args.ep in (905,) else build_cast())
    if args.ep == 905:
        globals()["SERIES"] = "9-5"
        globals()["CAST95"] = True
    if args.ep == 910:
        globals()["SERIES"] = "PORTAL FIGHT"
        globals()["TTS_DIR"] = "/home/user/pixeltube/tts910"
    if args.ep == 910:
        ep_fn = episode_910portal
    elif args.ep == 905 and getattr(args, "vertical", False):
        ep_fn = episode_905v
    else:
        ep_fn = {1: episode_001, 2: episode_002, 3: episode_003, 905: episode_905}.get(args.ep, episode_001)
    scenes = ep_fn(cast)

    # ---------------- LJUD: röster + envelope-läppar ----------------------
    np.random.seed(0)
    total = sum(s["dur"] for s in scenes)
    print(f"   ▶ {SERIES}  episod {args.ep}  ({total:.1f}s, {len(scenes)} segment)")
    mix = np.zeros(int((total + 0.6) * voicemod.SR), dtype=np.float32)

    def put(t0, arr, vol=1.0):
        off = int(t0 * voicemod.SR)
        seg = arr.astype(np.float32) * vol
        end = min(len(mix), off + len(seg))
        if end > off:
            mix[off:end] += seg[: end - off]

    # ADAPTIV MUSIK: sektion per scen-mood (tension/cozy/action/mystery/...)
    def _scene_mood(sc):
        if "mood" in sc:
            return sc["mood"]
        ek = sc["env"][0]
        if ek == "title":
            return "title"
        if ek == "eyecatch":
            return "sting"
        if ek == "preview":
            return "happy"
        fxk = {f.get("kind") for f in sc.get("fx", [])}
        if "impact" in fxk:
            return "action"
        if any("kaba" in a for a in sc.get("actors", {})) and sc.get("lines"):
            return "menace"
        if ek == "dojo":
            return "cozy"
        if sc.get("letterbox") and sc["env"][1].get("lights_on"):
            return "mystery"
        if sc.get("letterbox"):
            return "ominous"
        return "ominous"   # dock+natt utan spårr = spänd stämning, aldrig "glad"

    msegs = []
    for i2, s2 in enumerate(scenes):
        seg = musicmod.section(_scene_mood(s2), s2["dur"] + 0.02, seed=77 + i2 * 37)
        mv = s2.get("music_vol", 1.0)
        if mv != 1.0:
            seg = (seg * mv).astype(np.float32)     # tystnad som pattern-interrupt
        msegs.append(seg)
    track = np.concatenate(msegs) if msegs else np.zeros(8, dtype=np.float32)
    put(0.0, track, 0.55)
    print("   🎵 moods:", [_scene_mood(s2) for s2 in scenes])

    # per scen: röster+läppar+sfx
    scene_starts, cur = [], 0.0
    tts_used = []
    mouth_per = {}          # (scene_idx, name) -> bool array lokala frames
    lines_global = []       # (scene_idx, who, text, t0_local, t1_local)
    for i, s in enumerate(scenes):
        scene_starts.append(cur)
        local, tcur = [], 0.0
        for (lt, who, text) in sorted(s.get("lines", []), key=lambda l: l[0]):
            sp = cast.get(who, E.PXChar("n", {"H": (0, 0, 0), "S": (0, 0, 0), "T": (0, 0, 0),
                                              "P": (0, 0, 0), "B": (0, 0, 0), "A": (0, 0, 0)},
                                        "spiky")).voice_pitch
            if who == "narr" or who == "hood":
                sp = "narr"
            tts_path = f"{TTS_DIR}/line{len(tts_used):02d}.wav"
            if TTS_MODE and os.path.exists(tts_path):
                import wave as _wav
                with _wav.open(tts_path, "rb") as _wf:
                    _sr = _wf.getframerate()
                    _n = _wf.getnframes()
                    _ch = _wf.getnchannels()
                    _raw = np.frombuffer(_wf.readframes(_n), dtype="<i2").astype(np.float32) / 32767
                if _ch > 1:
                    _raw = _raw[::_ch]
                if _sr != voicemod.SR:
                    _xx = np.linspace(0, 1, len(_raw))
                    _interp = np.interp(np.linspace(0, 1, int(len(_raw) * voicemod.SR / _sr)), _xx, _raw)
                    arr = _interp.astype(np.float32)
                else:
                    arr = _raw.astype(np.float32)
            else:
                arr = voicemod.speak(text, species=sp, seed=301 * 57 + i * 13 + int(lt * 10))
            tts_used.append(tts_path)
            put(cur + lt, arr, 0.9)
            dur = len(arr) / voicemod.SR
            lines_global.append((i, who, text, lt, lt + max(dur, 0.5) + 0.65))
            if who in cast and who not in ("narr", "hood"):
                mo = mouth_track(arr)
                pre = np.zeros(int(lt * FPSS), bool)
                post = np.zeros(int((s["dur"]) * FPSS) - pre.size - mo.size, bool)
                if post.size < 0:
                    post = np.zeros(0, bool)
                full = np.concatenate([pre, mo, post])
                if (i, who) in mouth_per:
                    mouth_per[(i, who)] |= full[: len(mouth_per[(i, who)])]
                else:
                    mouth_per[(i, who)] = full
        for (lt, name, vol) in s.get("audio", []):
            fn = getattr(sfxmod, name, None)
            if fn:
                put(cur + lt, fn(), vol)
        cur += s["dur"]

    # normalisera
    peak = np.max(np.abs(mix)) or 1.0
    if peak > 0.98:
        mix *= 0.98 / peak

    # ---------------- VIDEO-RENDER -----------------------------------------
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if args.out:
        out = args.out
    elif args.ep == 905 and getattr(args, "vertical", False):
        out = "/home/user/pixeltube/out/nine-five-ep001-vertical.mp4"
    elif args.ep == 910:
        out = "/home/user/pixeltube/out/portal-fight-ep001-vertical.mp4"
    elif args.ep == 905:
        out = "/home/user/pixeltube/out/nine-five-ep001.mp4"
    else:
        out = f"/home/user/pixeltube/out/volt-breaker-ep{args.ep:03d}.mp4"
    os.makedirs(os.path.dirname(out), exist_ok=True)

    renderer = Renderer(cast)
    t0 = time.time()
    tmp_silent = out.replace(".mp4", "_silent.mp4")

    # steg 1: bildrender till silent-mp4; ljudet muxas i steg 2
    pipe = subprocess.Popen(
        [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUTW}x{OUTH}",
         "-r", str(60 if VERT else FPSS * 2), "-i", "-", "-an", "-c:v", "libx264",
         "-pix_fmt", "yuv420p",
         "-preset", "slow" if VERT else "medium",
         "-crf", "16" if VERT else "18", tmp_silent],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    lwins_all = {}
    for (ii, who, text, t0, t1) in lines_global:
        lwins_all.setdefault(ii, []).append((who, text, t0, t1))
    for kk in range(len(scenes)):
        lwins_all.setdefault(kk, [])

    SAMP = 60 if VERT else FPSS          # VERT = äkta 60fps-sampling (butter)
    nframes = int(total * SAMP)
    for f in range(nframes):
        tg = f / SAMP
        idx = 0
        for j, st in enumerate(scene_starts):
            if tg >= st:
                idx = j
        s = scenes[idx]
        lt = tg - scene_starts[idx]
        env_kind, env_args = s["env"]
        if not hasattr(Renderer, "_envcache"):
            Renderer._envcache = {}
        ck = idx
        if ck not in Renderer._envcache:
            if env_kind == "dock":
                Renderer._envcache[ck] = E.DockNight(seed=301 + idx, **{k: v for k, v in env_args.items() if k != "rain"})
            elif env_kind == "dojo":
                Renderer._envcache[ck] = E.DojoInterior(seed=301 + idx, **env_args)
            elif env_kind == "title":
                Renderer._envcache[ck] = E.TitleCard(env_args["series"], env_args["episode"], seed=301)
            elif env_kind == "eyecatch":
                who = env_args["who"]
                Renderer._envcache[ck] = E.EyecatchCard(pxchar=cast[who], series=SERIES,
                                                        catchword=("THUNDER SEASON 1" if who == "ren"
                                                                   else "static grins back"),
                                                        seed=301, dark=(who != "ren"))
            elif env_kind == "vcard":
                Renderer._envcache[ck] = E.VertCard(**env_args, seed=301 + idx)
            elif env_kind == "apartment":
                Renderer._envcache[ck] = E.ApartmentMorning(seed=301 + idx)
            elif env_kind == "platform":
                Renderer._envcache[ck] = E.TrainPlatform(seed=301 + idx, **env_args)
            elif env_kind == "office":
                Renderer._envcache[ck] = E.OfficeGrid(seed=301 + idx)
            elif env_kind == "street":
                Renderer._envcache[ck] = E.StreetRain(seed=301 + idx, **env_args)
            elif env_kind == "void":
                Renderer._envcache[ck] = E.VoidWhite(seed=301 + idx)
            elif env_kind == "preview":
                Renderer._envcache[ck] = E.PreviewCard(env_args["no"], env_args["title"], env_args["lines"], seed=301)
        env = Renderer._envcache[ck]
        if not hasattr(Renderer, "_lwins"):
            Renderer._lwins = {}
        mouths = {name: mouth_per.get((idx, name), np.zeros(0)) for name in s.get("actors", {})}
        if env_kind in ("dock", "dojo", "apartment", "platform", "office", "street", "void"):
            if not hasattr(Renderer, "_actcache"):
                Renderer._actcache = {}
            if ck not in Renderer._actcache:
                Renderer._actcache[ck] = renderer._mk_actors(s, mouths)
            actors = Renderer._actcache[ck]
            for nm, ac in actors.items():
                ac.mouth = mouths.get(nm, np.zeros(0))
            lwins = [(who, text, t0, t1) for (ii, who, text, t0, t1) in lines_global if ii == idx]
            renderer.line_moods = [
                (who, t0, t1) + _mood_for_line(who, text) for (who, text, t0, t1) in lwins]
            small = renderer.scene_frame(s, env, actors, lt)
        else:
            small = env.frame(lt)          # kort lever redan på logisk nivå
        # ---- kamera & letterbox på logisk nivå (320x180) -------------------
        # SHOT LANGUAGE: etablerande->MCU->shot-reverse-shot->low-angle->ECU-flash
        ops = list(s.get("cam", []))
        flash = False
        if env_kind in ("dock", "dojo", "apartment", "platform", "office", "street", "void"):
            if not hasattr(Renderer, "_plans"):
                Renderer._plans = {}
            if idx not in Renderer._plans:
                Renderer._plans[idx] = _shot_plan(lwins_all[idx])
            seg = None
            for t0p, t1p, kind, who2 in Renderer._plans[idx]:
                if t0p <= lt <= t1p:
                    seg = (t0p, t1p, kind, who2)
                    break
            if seg:
                # shot-plan ERSÄTTER scenens egna zoom-ops (annars dubbel-croppas fokus)
                ops = [o2 for o2 in ops if o2["kind"] != "zoom"]
                t0p, t1p, kind, who2 = seg
                fxp = int(actors[who2].track.at(lt)[0]) if (who2 and who2 in actors) else 150
                dt = lt - t0p
                pin = 0.14 if kind == "ecu" else 0.22
                ease = 1 - (1 - min(1.0, dt / pin)) ** 2
                if kind == "breather":
                    ops.append({"kind": "zoom", "z": 1.02 + 0.04 * min(1.0, dt / 0.5),
                                "focus": (150, 94)})
                elif kind == "low":        # low-angle: skurk-makt, dutch-vinkel
                    ops.append({"kind": "tilt", "deg": 2.2})
                    ops.append({"kind": "zoom", "z": 1.0 + 0.52 * ease, "focus": (fxp, 108)})
                elif kind == "ecu":        # extrem närbild + vit-blixt + mikroskak
                    ops.append({"kind": "zoom", "z": 1.0 + 0.85 * ease, "focus": (fxp, 86)})
                    ops.append({"kind": "shake", "t0": t0p, "t1": t0p + 0.2, "amp": 2})
                    if dt < 0.17:
                        flash = True
                else:                      # mcu: medium close-up på talaren
                    ops.append({"kind": "zoom", "z": 1.0 + 0.42 * ease, "focus": (fxp, 92)})
        if s.get("letterbox"):
            ops.append({"kind": "letterbox", "h": s["letterbox"]})
        if ops:
            small = E.apply_camera(small, lt, ops)
        if VERT and small.width > 90 and env_kind in ("dock", "dojo", "apartment",
                                                      "platform", "office", "street", "void"):
            # 9:16-crop: 90x160 logiskt fönster som följer huvudpersonen (kort croppas aldrig)
            fx_anchor = 160
            try:
                for a_nm in ("rex", "tom", "ren"):
                    if a_nm in actors:
                        fx_anchor = int(actors[a_nm].track.at(lt)[0]) + s.get("anchor_off", 0)
                        break
            except Exception:
                fx_anchor = 160
            cx0 = max(0, min(E.W - 90, fx_anchor - 45))
            small = small.crop((cx0, 20, cx0 + 90, 180))
        img = small.resize((OUTW, OUTH), NEAREST)
        if flash:
            img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 195)))
        # ---- VERT: stamp-fx ritas direkt på OUTPUT-px (TikTok-text-lyft) ----
        if VERT_STAMPS_OUT:
            d_tmp = ImageDraw.Draw(img, "RGBA")
            for fx2 in s.get("fx", []):
                if fx2.get("kind") == "stamp" and fx2["t0"] <= lt <= fx2["t1"]                         and fx2.get("x", 0) >= 0:
                    st2 = E.ptext(fx2["text"], fx2.get("scale", 2),
                                  fx2.get("color", (246, 240, 200)))
                    d_tmp.rectangle([fx2["x"] - 14, fx2["y"] - 12,
                                     fx2["x"] + st2.width + 16, fx2["y"] + st2.height + 12],
                                    fill=(14, 16, 26, 175))
                    img.alpha_composite(st2, (fx2["x"], fx2["y"]))
        # ---- undertext EFTER kamera (aldrig croppad av zoom) ---------------
        if env_kind in ("dock", "dojo", "apartment", "platform", "office", "street", "void"):
            for who, text, t0, t1 in lwins_all[idx]:
                if t0 <= lt <= t1:
                    if VERT:
                        aud = max(0.4, t1 - t0 - 0.65)     # riktig tal-längd (utan svans)
                        draw_sub_sync(img, text, who, (lt - t0) / aud)
                    else:
                        draw_sub(img, text, who)
                    break
        # HD-2D WOW-PASS (VERT @60fps): bloom+vignette+grain, chroma vid smällar
        if VERT:
            chroma = any(fx2.get("kind") == "impact" and abs(lt - fx2["t"]) < 0.35
                         or fx2.get("kind") == "blood" and 0 <= lt - fx2["t"] < 0.5
                         for fx2 in s.get("fx", []))
            chroma = chroma or any(o2.get("kind") == "shake"
                                   and o2["t0"] <= lt <= o2["t1"] for o2 in ops)
            img = hi_post(img, f, chroma)
        # fades
        if s.get("fadein") and lt < s["fadein"]:
            p = lt / s["fadein"]
            img = Image.blend(Image.new("RGBA", img.size, (0, 0, 0, 255)), img, p)
        if s.get("fadeout") and lt > s["dur"] - s["fadeout"]:
            p = max(0.0, (s["dur"] - lt) / s["fadeout"])
            img = Image.blend(Image.new("RGBA", img.size, (0, 0, 0, 255)), img, p)
        pipe.stdin.write(img.convert("RGB").tobytes())   # VERT: äkta 60fps (1 write/frame)
        if not VERT:
            pipe.stdin.write(img.convert("RGB").tobytes())   # landskap: on twos -> 24fps
        if f % 120 == 0:
            print(f"\r   renderar {100*f/nframes:5.1f}%", end="", flush=True)
    pipe.stdin.close(); pipe.wait()
    print(f"\r   renderar 100% ({time.time()-t0:.0f}s)")

    # steg 2: ljud-wav + mux
    wav = out.replace(".mp4", ".wav")
    musicmod.save_wav16(wav, mix)
    subprocess.run([ffmpeg, "-y", "-i", tmp_silent, "-i", wav, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", out],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for junk in (tmp_silent, wav):
        try: os.remove(junk)
        except OSError: pass
    size = os.path.getsize(out) / 1e6
    print(f"   ✅ KLART: {out} ({size:.1f} MB)")
    meta = {"title": (f"{SERIES} - Episode 001 - Day 9413" if args.ep == 905
                      else (f"{SERIES} - EP001 - The Multiverse Objected" if args.ep == 910
                            else f"{SERIES} - Episode {args.ep:03d}")),
            "seed": 301, "madeForKids": False, "language": "en"}
    json.dump(meta, open(out.replace(".mp4", ".json"), "w"), indent=2)


if __name__ == "__main__":
    main()
