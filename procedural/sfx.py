# -*- coding: utf-8 -*-
"""
sfx.py – Ljudeffekter, allt syntetiserat med numpy.

Rörelse-ljud (loopas med animationen):
  step    – fotsteg (mjukt snedd-tap, alt vänster/höger)
  boing   – studs (hopp, dans)
  thud    – landningsduns
  bonk    – träff ("slår")
  whoosh  – svep (spin, rusch)
  snore   – mjuk snarkning (sömn)

Reaktions-/miljöljud (engångshändelser):
  pop, sparkle, splash, fanfare
"""
import numpy as np

SR = 44100


def _midi(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _sweep_wave(f0, f1, dur, shape="sine", env_exp=8.0, vol=1.0):
    n = max(8, int(SR * dur))
    t = np.arange(n) / SR
    f = f0 + (f1 - f0) * t / dur
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sign(np.sin(ph)) if shape == "square" else np.sin(ph)
    return (w * np.exp(-t * env_exp) * vol).astype(np.float32)


# --------- rörelse ---------------------------------------------------------
def step(alt=0, vol=0.5):
    """Ett fotsteg. alt=0/1 ger vänster/höger karaktär."""
    rng = np.random.default_rng(40 + alt)
    n = int(SR * 0.055)
    t = np.arange(n) / SR
    f = 150 if alt else 118
    body = np.sin(2 * np.pi * f * t) * np.exp(-t * 38)
    tap = rng.uniform(-1, 1, n) * np.exp(-t * 75) * 0.55
    return ((body + tap) * vol).astype(np.float32)


def boing():
    n = int(SR * 0.34)
    t = np.arange(n) / SR
    f = 150 + 400 * (t / 0.34)
    wob = 1 + 0.06 * np.sin(2 * np.pi * 22 * t)
    ph = 2 * np.pi * np.cumsum(f * wob) / SR
    return (np.sin(ph) * np.exp(-t * 9)).astype(np.float32)


def thud():
    """Landning: låg duns + litet knäpp."""
    rng = np.random.default_rng(3)
    n = int(SR * 0.13)
    t = np.arange(n) / SR
    body = _sweep_wave(95, 52, 0.13, "sine", 22.0)
    tap = rng.uniform(-1, 1, n) * np.exp(-t * 60) * 0.35
    return (body + tap).astype(np.float32) * 0.9


def bonk():
    return _sweep_wave(270, 150, 0.10, "square", 28.0, 0.9)


def whoosh():
    rng = np.random.default_rng(7)
    n = int(SR * 0.45)
    noise = rng.uniform(-1, 1, n).astype(np.float32)
    sm = np.convolve(noise, np.ones(40, dtype=np.float32) / 40, mode="same")
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (sm * env * 6).astype(np.float32)


def snore():
    """Mys-snarkning: pihhh... pihhh..."""
    a = _sweep_wave(150, 92, 0.50, "sine", 0.0)
    b = _sweep_wave(92, 165, 0.60, "sine", 0.0)
    out = np.concatenate([a, b])
    n = len(out)
    env = np.sin(np.linspace(0, np.pi, n))
    return (out * env * 0.5).astype(np.float32)


# --------- engångshändelser -----------------------------------------------
def pop():
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    return (np.sign(np.sin(2 * np.pi * 660 * t)) * np.exp(-t * 45)).astype(np.float32) * 0.9


def _note_seq(notes, note_dur, vol=0.5):
    out = []
    for m in notes:
        n = int(SR * note_dur)
        t = np.arange(n) / SR
        f = _midi(m)
        out.append((np.sign(np.sin(2 * np.pi * f * t)) * np.exp(-t * 6) * vol).astype(np.float32))
    return np.concatenate(out) if out else np.zeros(1, dtype=np.float32)


def sparkle():
    return _note_seq([96, 100, 103, 108], 0.085, 0.35)


def fanfare():
    a = _note_seq([72, 76, 79], 0.12, 0.45)
    b = _note_seq([84], 0.34, 0.45)
    return np.concatenate([a, b])


def splash():
    rng = np.random.default_rng(11)
    n = int(SR * 0.55)
    noise = rng.uniform(-1, 1, n).astype(np.float32)
    sm = np.convolve(noise, np.ones(18, dtype=np.float32) / 18, mode="same")
    t = np.arange(n) / SR
    return (sm * np.exp(-t * 6) * 3 + np.sin(2 * np.pi * 170 * t) * np.exp(-t * 8) * 0.4).astype(np.float32)


def flame():
    """Eld-attack: sprakande brunbrus + låg vrål-bas."""
    rng = np.random.default_rng(21)
    n = int(SR * 0.60)
    noise = rng.uniform(-1, 1, n).astype(np.float32)
    sm = np.convolve(noise, np.ones(28, dtype=np.float32) / 28, mode="same")
    t = np.arange(n) / SR
    rumble = np.sin(2 * np.pi * 62 * t) * 0.8 + np.sin(2 * np.pi * 47 * t) * 0.4
    env = np.sin(np.linspace(0, np.pi, n)) ** 1.2
    crackle = noise * (rng.random(n) < 0.04) * np.exp(-t * 2)
    return ((sm * 5 + rumble) * env * 0.8 + crackle * 0.5).astype(np.float32)


def boom():
    """808-subbjänk vid impact: låg duns som väntar knäppet."""
    rng = np.random.default_rng(31)
    n = int(SR * 0.30)
    t = np.arange(n) / SR
    f = 60 - 34 * t / 0.30
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 10)
    snap = rng.uniform(-1, 1, n) * np.exp(-t * 90) * 0.5
    return ((body * 1.6 + snap) * 0.8).astype(np.float32)


def riser():
    """Laddning som suser uppåt (Shepard-aktig)."""
    n = int(SR * 1.0)
    t = np.arange(n) / SR
    f = 95 * (2.0 ** (t / 0.5))          # dubbla frekvensen var 0.5s
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sign(np.sin(ph)) * 0.35 + np.sin(ph) * 0.5
    env = np.sin(np.linspace(0, np.pi / 2, n)) ** 0.7
    return (w * env * 0.5).astype(np.float32)


def make(name):
    return {"boing": boing, "pop": pop, "whoosh": whoosh,
            "splash": splash, "sparkle": sparkle, "fanfare": fanfare,
            "thud": thud, "bonk": bonk, "snore": snore, "flame": flame,
            "boom": boom, "riser": riser}[name]()

def alarm():
    """Digitalt väckarklockes-trippel-pip."""
    t = np.linspace(0, 1.15, int(SR * 1.15), False)
    w = np.zeros_like(t)
    for k in range(3):
        b0 = int(k * SR * 0.36)
        seg = t[b0:b0 + int(SR * 0.22)]
        w[b0:b0 + int(SR * 0.22)] = np.sign(np.sin(2 * np.pi * 1568 * seg)) * 0.5
    w = w.astype(np.float32)
    w *= np.exp(-t * 0.6)
    return w


def horn():
    """Buss-tut! Slegnande tvåstavat honk i motorregister."""
    t = np.linspace(0, 0.85, int(SR * 0.85), False)
    w = (np.sign(np.sin(2 * np.pi * 233 * t)) * 0.45
         + np.sign(np.sin(2 * np.pi * 311 * t)) * 0.35) * 0.7
    env = np.ones_like(t); env[int(SR * 0.6):] *= np.exp(-(t[int(SR * 0.6):] - 0.6) * 6)
    return (w * env).astype(np.float32)


def rumble():
    """Tåg/buss-avrall: filtrerat brus-rassel."""
    n = int(SR * 2.4)
    rng = np.random.RandomState(11)
    w = rng.uniform(-1, 1, n).astype(np.float32)
    k = 240
    w = np.convolve(w, np.ones(k, dtype=np.float32) / k, mode="same")
    t = np.arange(n) / SR
    return w * 0.85 * np.exp(-t * 1.1) + 0.04 * np.sin(2 * np.pi * 46 * t)

