# -*- coding: utf-8 -*-
"""
music.py – ADAPTIV generativ chiptune-motor (16-bit/NES-inspirerad).
Scensektioner i olika moods: ominous/title/cozy/menace/action/happy/mystery/sting.
2 pulse-kanaler + triangelbas + noise-trummor (äkta NES-arkitektur).
100 % egen komposition -> noll upphovsrättsproblem på YouTube.
"""
import random
import wave

import numpy as np

SR = 44100


def _midi(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _env(n, atk=0.006, rel=0.05):
    e = np.ones(n, dtype=np.float32)
    a = max(1, int(atk * SR))
    r = max(1, int(rel * SR))
    if a < n:
        e[:a] = np.linspace(0, 1, a)
    if r < n:
        e[-r:] = np.linspace(1, 0, r)
    return e


def square(freq, dur, duty=0.5, rel=0.05):
    n = max(1, int(SR * dur))
    t = np.arange(n) / SR
    ph = (t * freq) % 1.0
    return ((ph < duty) * 2.0 - 1.0).astype(np.float32) * _env(n, 0.004, rel)


def tri(freq, dur, rel=0.08):
    n = max(1, int(SR * dur))
    t = np.arange(n) / SR
    ph = (t * freq) % 1.0
    return ((2 * np.abs(2 * ph - 1) - 1) * _env(n, 0.01, rel)).astype(np.float32)


def _noise(n, decay=7.0):
    rng = np.random.default_rng(n % 7919 + 13)
    return (rng.uniform(-1, 1, n) * np.exp(-np.linspace(0, decay, n))).astype(np.float32)


def kick(dur=0.12):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 120 * np.exp(-t * 30) + 45
    ph = np.cumsum(2 * np.pi * f / SR)
    return (np.sin(ph) * np.exp(-t * 18)).astype(np.float32)


def snare(dur=0.09):
    return _noise(int(SR * dur), 30) * 0.8 + square(196, dur, 0.3, 0.04) * 0.25


def hat(dur=0.035):
    return _noise(int(SR * dur), 60)


# -------------------------------------------------------------------------- #
# MOOD-STILAR: (bpm, ackord-rötter midi, skala midi, bass/lead/trum-stil)    #
# -------------------------------------------------------------------------- #
STYLES = {
    # skrämmande lugn (cold open): drone + glest klockljud
    "ominous": dict(bpm=70, roots=[45, 45, 44, 43], scale=[57, 60, 62, 64],
                    bass="drone", lead="bell", drums="none", duty=0.5),
    # titel/fanfar: kort, stolt, majorn
    "title":   dict(bpm=128, roots=[48, 43, 45, 50], scale=[60, 64, 67, 72, 76, 79],
                    bass="roots4", lead="fanfare", drums="rock", duty=0.6),
    # hemmamys (dojo): lätt majorpentatonik, mjukt
    "cozy":    dict(bpm=96, roots=[48, 45, 41, 43], scale=[60, 62, 64, 67, 69, 72],
                    bass="pulse4", lead="wander", drums="light", duty=0.5),
    # glädje/vinst: I-V-vi-IV, livfull arp
    "happy":   dict(bpm=112, roots=[36, 43, 45, 41], scale=[60, 62, 64, 67, 69, 72, 74, 76],
                    bass="pulse8", lead="wander", drums="light", duty=0.55),
    # skurk: D-moll, halvnots-stabs + 3-slag virvel
    "menace":  dict(bpm=104, roots=[38, 34, 36, 42], scale=[62, 65, 69, 72],
                    bass="stab2", lead="sparse", drums="snare3", duty=0.7),
    # ACTION: 154 BPM E-moll, 16-delars arp + 4/4-kick + snare 3
    "action":  dict(bpm=154, roots=[40, 36, 38, 47], scale=[64, 67, 69, 71, 72, 76, 79],
                    bass="pulse8", lead="arp16", drums="action", duty=0.6),
    # C-part-mysterium: långsamma maj7-arper, skimrande
    "mystery": dict(bpm=80, roots=[45, 47, 43, 42], scale=[69, 71, 74, 76, 81, 83],
                    bass="drone", lead="bell", drums="none", duty=0.5),
    # eyecatch-sting
    "sting":   dict(bpm=140, roots=[48], scale=[60, 64, 67, 72, 76, 79, 84],
                    bass="roots4", lead="fanfare", drums="rock", duty=0.6),
}


def section(mood, seconds, seed=0):
    """Renderar en musiksektion i valt mood. Returnerar float32-mono."""
    st = STYLES.get(mood, STYLES["happy"])
    rng = random.Random(seed * 131 + 7)
    bpm = st["bpm"]
    beat = 60.0 / bpm
    eighth = beat / 2.0
    total = int(seconds * SR) + SR // 2

    bass = np.zeros(total, dtype=np.float32)
    lead = np.zeros(total, dtype=np.float32)
    drums = np.zeros(total, dtype=np.float32)

    roots, scale = st["roots"], st["scale"]
    bs, ls, ds = st["bass"], st["lead"], st["drums"]

    def place(buf, pos, wave_, vol):
        end = min(total, pos + len(wave_))
        if end > pos:
            buf[pos:end] += wave_[: end - pos] * vol

    i, pos = 0, 0
    mel_idx = len(scale) // 2
    while pos < total:
        bar = (pos // int(round(beat * 4 * SR))) % len(roots)
        chord = roots[int(bar)]
        # ---------- BAS ----------
        if bs == "drone" and pos % int(round(beat * 8 * SR)) == 0:
            place(bass, pos, tri(_midi(chord - 12), beat * 8, 0.3), 0.55)
        elif bs == "pulse8":
            for st2 in range(2):
                place(bass, pos + st2 * int(round(eighth * SR)),
                      tri(_midi(chord), eighth * 0.85), 0.75)
        elif bs == "pulse4":
            if pos % int(round(beat * SR)) == 0:
                place(bass, pos, tri(_midi(chord), beat * 0.9), 0.7)
        elif bs == "stab2":
            if pos % int(round(beat * 2 * SR)) == 0:
                place(bass, pos, square(_midi(chord - 12), beat * 1.8, st["duty"], 0.2), 0.6)
        elif bs == "roots4":
            if pos % int(round(beat * SR)) == 0:
                place(bass, pos, square(_midi(chord - 12), beat * 0.85, st["duty"]), 0.55)
        # ---------- LEAD ----------
        if ls == "bell" and rng.random() < 0.16:
            nn = rng.choice(scale)
            place(lead, pos, tri(_midi(nn + 12), beat * rng.uniform(1.5, 3.0), 1.6), 0.16)
        elif ls == "wander":
            if rng.random() < 0.85:
                mel_idx = max(0, min(len(scale) - 1,
                                     mel_idx + rng.choice([-2, -1, -1, 1, 1, 2])))
                ln = eighth * (1.9 if rng.random() < 0.2 else 0.95)
                place(lead, pos, square(_midi(scale[mel_idx]), ln, st["duty"]), 0.26)
        elif ls == "sparse":
            if rng.random() < 0.38:
                nn = rng.choice(scale)
                place(lead, pos, square(_midi(nn), beat * 0.9, st["duty"], 0.12), 0.24)
        elif ls == "fanfare":
            if i % 2 == 0 and mel_idx < len(scale):
                place(lead, pos, square(_midi(scale[min(mel_idx, len(scale) - 1)]),
                                        eighth * 0.9, st["duty"]), 0.3)
                mel_idx += 1
                if mel_idx >= len(scale):
                    mel_idx = 0
        elif ls == "arp16":      # snabba boss-arper (16-delar)
            for st2 in range(2):
                nn = scale[(i * 2 + st2 * 3) % len(scale)]
                place(lead, pos + st2 * int(round(eighth / 2 * SR)),
                      square(_midi(nn + 12), eighth * 0.5, st["duty"], 0.06), 0.22)
            if rng.random() < 0.25:
                nn = scale[rng.randrange(len(scale))]
                place(lead, pos, square(_midi(nn + 12), eighth * 1.8, st["duty"], 0.18), 0.2)
        # ---------- TRUMMOR ----------
        if ds == "action":
            if pos % int(round(beat * SR)) == 0:                       # 4/4-kick
                place(drums, pos, kick(), 0.8)
            if (pos // int(round(beat * SR))) % 2 == 1 and \
               pos % int(round(beat * 2 * SR)) < int(round(eighth * SR)):
                place(drums, pos, snare(), 0.6)
            place(drums, pos + int(round(eighth * SR)), hat(), 0.10)   # 16-hat offbeat
        elif ds == "rock":
            if pos % int(round(beat * SR)) == 0:
                place(drums, pos, kick(), 0.7)
            if (pos // int(round(beat * SR))) % 4 == 2 and \
               pos % int(round(beat * SR)) < 100:
                place(drums, pos, snare(), 0.55)
            if i % 2 == 0:
                place(drums, pos, hat(), 0.09)
        elif ds == "light":
            if i % 2 == 1:
                place(drums, pos, hat(), 0.08)
        elif ds == "snare3":
            if (pos // int(round(beat * SR))) % 4 == 2 and \
               pos % int(round(beat * SR)) < 100:
                place(drums, pos, snare(), 0.6)
            if pos % int(round(beat * SR)) == 0 and rng.random() < 0.5:
                place(drums, pos, kick(), 0.5)
        pos += int(round(eighth * SR))
        i += 1

    mix = bass * 0.34 + lead + drums * 0.5
    mix = np.tanh(mix * 1.3).astype(np.float32) * 0.8
    out = mix[: int(seconds * SR)]
    # mjuk kant (klickfri sektionsgräns)
    e = max(1, int(0.03 * SR))
    if len(out) > 2 * e:
        out[:e] *= np.linspace(0, 1, e)
        out[-e:] *= np.linspace(1, 0, e)
    return out


def chip(seed, seconds, bpm=116):   # bakåtkompatibelt anrop
    return section("happy", seconds, seed)


def save_wav16(path, data):
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
