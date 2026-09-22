#!/usr/bin/env python3
"""engine/timeline.py — bygger publisher-timelinen runt faktisk röst-duration.

Princip (audio-driven):
  VO -> block-start/duration från wav-längder -> beats/clips/grafiker utplacerade
  RELATIVT block -> abs tider. Allt synkas till 90 BPM-slag där set flag.

timeline.json: {blocks, segments, beats, clips, graphics, music, sfx, captions,
                total, fps}
"""
import os, json, math, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
BPM = 90
BEAT = 60.0 / BPM          # 0.6667 s

def beat(t):
    return round(t / BEAT) * BEAT

def wav_dur(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()

def _num(v):
    return float(v) if isinstance(v, (int, float)) else None

def _resolve(t, b0, b1, snap=False):
    """Relativa tider: -2=absolut från blockets slut +N, 'end'=b1,
    'mid'=mitt; float = b0+float (offset in i blocket)."""
    if isinstance(t, (int, float)):
        v = b0 + float(t)
    else:
        s = str(t).strip()
        if s == "end":
            v = b1
        elif s.startswith("end-"):
            v = b1 - float(s[4:])
        elif s.startswith("mid+"):
            v = (b0 + b1) / 2 + float(s[4:])
        elif s.startswith("mid"):
            v = (b0 + b1) / 2
        else:
            v = b0 + float(s)
    return beat(v) if snap else v

def build_timeline(production_plan):
    """Viktigaste funktionen. Returnerar full timeline-dict.

    production_plan (från LLM):
      blocks: [{id, voiceover, visuals, duration_est, music, reveal_prompt}]
      visuals / graphics: [{block, type, text, at, until, w, x, y, anim,
                            impact, reveal}]
      clips: [{number, block, at, dur, query, w, y, vol, crop, motion}]
    """
    audio_dir = os.path.join(ROOT, "audio")
    blocks = production_plan.get("blocks", [])
    gap = float(production_plan.get("gap", 0.7))
    tail = float(production_plan.get("tail", 2.5))

    segments, missing = [], []
    t = 0.0
    BS = {}
    for b in blocks:
        p = os.path.join(audio_dir, f"{b['id']}.wav")
        if not os.path.exists(p):
            missing.append(b["id"]); continue
        d = wav_dur(p)
        seg = {"id": b["id"], "text": b.get("voiceover", b.get("text", "")),
               "start": round(t, 3), "dur": round(d, 3), "speech": round(d, 3)}
        segments.append(seg)
        BS[b["id"]] = (seg["start"], seg["start"] + seg["dur"])
        t += d + gap
    if missing:
        raise RuntimeError("saknar voiceover för: " + ", ".join(missing))
    total = round(t - gap + tail, 3)

    graphics = []
    for g in production_plan.get("visual_plan", []):
        if not g.get("block") or g["block"] not in BS:
            continue
        b0, b1 = BS[g["block"]]
        g0 = _resolve(g.get("at", 0), b0, b1, snap=bool(g.get("snap")))
        until = _resolve(g.get("until", g.get("until", "end")), b0, b1) \
            if g.get("until") is not None else g0 + float(g.get("dur", 5))
        g1 = until if isinstance(until, float) else g0 + float(g.get("dur", 5))
        if g0 < 1.2 and g.get("at", 0) != 0:
            g0 = min(g0, b1 - 1)
        graphics.append({
            "id": g.get("id", f"g{len(graphics)}"),
            "block": g["block"], "type": g.get("type", "card"),
            "text": g.get("text", ""), "sub": g.get("sub", ""),
            "T0": round(g0, 3), "T1": round(g1, 3),
            "w": g.get("w", 700), "x": g.get("x", None), "y": g.get("y", None),
            "anim": g.get("anim", "pop"), "impact": bool(g.get("impact")),
            "reveal": bool(g.get("reveal")), "accent": g.get("accent"),
            "asset": g.get("asset"),
            "kind": g.get("kind"), "data": g.get("data"),
            "img": g.get("img"), "handle": g.get("handle"),
            "likes": g.get("likes"), "meta": g.get("meta"),
        })

    clips = []
    for c in production_plan.get("clip_plan", []):
        if not c.get("block") or c["block"] not in BS:
            continue
        b0, b1 = BS[c["block"]]
        c0 = _resolve(c.get("at", 0), b0, b1, snap=bool(c.get("snap")))
        dur = float(c.get("dur", 6))
        clips.append({
            "number": c.get("number", len(clips) + 1),
            "block": c["block"], "query": c.get("query", ""),
            "T0": round(c0, 3), "T1": round(c0 + dur, 3),
            "dur": dur, "w": c.get("w", 900), "y": c.get("y", 64),
            "vol": c.get("vol", 1.0), "cut": c.get("cut", 0.0),
            "crop": c.get("crop", ""), "motion": c.get("motion"),
            "file": c.get("file"), "license": c.get("license"),
        })

    music = production_plan.get("music_plan", [])
    captions = production_plan.get("caption_plan", [])
    return {
        "blocks": blocks, "segments": segments, "graphics": graphics,
        "clips": clips, "music": music, "captions": captions,
        "total": total, "fps": FPS, "bpm": BPM,
        "gap": gap, "tail": tail,
    }
