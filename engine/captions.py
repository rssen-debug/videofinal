#!/usr/bin/env python3
"""engine/captions.py — tunnt lager över make_captions.py.
Kör make_captions (-> captions.ass + timings.json) MEN med topic-specifika
keywords; LLM kan dessutom begära emphasis-ord per block.
"""
import os, sys, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "scripts")

def run(keywords=None, emphasis_map=None):
    """Kör make_captions.py. keywords skrivs till keywords.txt först."""
    if keywords:
        with open(os.path.join(ROOT, "keywords.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(kw.lower() for kw in keywords if kw.strip()) + "\n")
    r = subprocess.run([sys.executable, os.path.join(HERE, "make_captions.py")],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("make_captions.py: " + r.stderr[-800:])
    return r.stdout
