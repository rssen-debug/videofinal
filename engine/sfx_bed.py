#!/usr/bin/env python3
"""sfx_bed.py — syntetisera ALLA SFX (impacts/whooshes/risers/clicks) till EN wav.
Byter ~40 ffmpeg-inputs mot 1 => inga fd/minnes-flaskhalsar i sandboxen.
Funktion: make_bed(events, total, out) där events = [(typ, t, vol)]"""
import numpy as np, wave

SR = 44100

def _env(n, a=0.002, d=0.3):
    t = np.arange(n) / SR
    e = np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-t / d)
    return e

def _impact(dur=1.6):
    n = int(SR * dur); t = np.arange(n) / SR
    return (0.85 * np.sin(2 * np.pi * 52 * t) * np.exp(-5.5 * t) +
            0.30 * np.sin(2 * np.pi * 110 * t) * np.exp(-8 * t)) * _env(n, 0.001, 0.5)

def _whoosh(dur=1.0):
    n = int(SR * dur); t = np.arange(n) / SR
    f = 300 + 900 * np.exp(-6 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return 0.30 * np.sin(ph) * np.exp(-9 * (t - 0.35) ** 2 / 0.09)

def _riser(dur=2.4):
    n = int(SR * dur); t = np.arange(n) / SR
    x = (0.16 * np.sin(2 * np.pi * (160 + 260 * t) * t) +
         0.10 * np.sin(2 * np.pi * (90 + 40 * t) * t))
    return x * np.minimum(t / (dur * 0.92), 1.0) ** 1.5

def _click(dur=0.12):
    n = int(SR * dur); t = np.arange(n) / SR
    return (0.25 * np.sin(2 * np.pi * 1800 * t) * np.exp(-60 * t) +
            0.10 * np.sin(2 * np.pi * 900 * t) * np.exp(-30 * t))

GEN = {"impact": _impact, "whoosh": _whoosh, "riser": _riser, "click": _click}

def make_bed(events, total, out_path):
    buf = np.zeros(int(SR * (total + 1)))
    for typ, t, vol in events:
        seg = GEN[typ]() * vol
        i = int(t * SR)
        if i < 0 or i >= len(buf): continue
        end = min(i + len(seg), len(buf))
        buf[i:end] += seg[:end - i]
    peak = max(float(np.max(np.abs(buf))), 1e-6)
    if peak > 0.92: buf *= 0.92 / peak
    pcm = (buf * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path

if __name__ == "__main__":
    make_bed([("impact", 1.333, 0.6), ("whoosh", 1.0, 0.5), ("riser", 5.0, 0.5)], 8, "/tmp/test_bed.wav")
    print("sfx_bed OK")
