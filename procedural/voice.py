# -*- coding: utf-8 -*-
"""
voice.py – Karaktärsröster! Ingen TTS, inget mänskligt tal – karaktärerna
"pratar" med pixel-pip (som i gamla TV-spel). Varje ART har sin egen
grundhöjd, så Doris låter som Doris i alla avsnitt:

    dino  -> mollare pip (0.95x)
    apa   -> högre, kvickare pip (1.35x)
    kanin -> pipigast av alla (1.65x)

Undertexterna berättar vad de säger. Rytmen = textens ord och skiljetecken.
"""
import random
import re

import numpy as np

SR = 44100
BASE_FREQ = 380.0
SPECIES_PITCH = { "tom": 0.78, "col": 1.05,        # trött man, mörkare yaw
    "dino": 0.95, "apa": 1.35, "kanin": 1.65, "mech": 0.55,   # mecha = djup robot
                   "ren": 0.85, "yuki": 0.62, "mika": 1.45, "kaba": 0.45, "narr": 0.72, "naya": 1.28}  # v2: människor + berättare


def _bleep(freq, dur, vol=0.42):
    n = max(8, int(SR * dur))
    t = np.arange(n) / SR
    w = np.sign(np.sin(2 * np.pi * freq * t)).astype(np.float32)
    a = max(1, int(0.004 * SR))
    r = max(1, int(0.012 * SR))
    env = np.ones(n, dtype=np.float32)
    if a < n:
        env[:a] = np.linspace(0, 1, a)
    if r < n:
        env[-r:] = np.linspace(1, 0, r)
    return w * env * vol


def speak(text, species="dino", seed=0):
    """Returnerar float32-ljud: texten som pixel-pip. Längden följer texten."""
    rng = random.Random(seed)
    base = BASE_FREQ * SPECIES_PITCH.get(species, 1.1)
    gap_word = 0.030 if species == "apa" else 0.050
    out = []
    tokens = re.findall(r"\w+|[^\w\s]", text or "", flags=re.UNICODE)
    for tok in tokens:
        if tok in ",;:":
            out.append(np.zeros(int(SR * 0.10), dtype=np.float32))
            continue
        if tok in ".!?…–-'\"":
            out.append(np.zeros(int(SR * 0.15), dtype=np.float32))
            continue
        n_syl = max(1, min(4, len(tok) // 3))
        for k in range(n_syl):
            f = base * rng.uniform(0.92, 1.12)
            if k == n_syl - 1 and rng.random() < 0.55:
                f *= 1.07                     # liten intonations-knick på slutet
            out.append(_bleep(f, 0.050 + rng.uniform(0, 0.025)))
            out.append(np.zeros(int(SR * 0.020), dtype=np.float32))
        out.append(np.zeros(int(SR * gap_word), dtype=np.float32))
    if not out:
        return np.zeros(int(SR * 0.4), dtype=np.float32)
    # utandnings-svans: ett mjukt fallande slutpip
    tail = _bleep(base * 0.9, 0.10, vol=0.30)
    out.append(tail)
    return np.concatenate(out).astype(np.float32)
