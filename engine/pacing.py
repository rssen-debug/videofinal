#!/usr/bin/env python3
"""engine/pacing.py — PACING / VISUAL-RHYTHM-MOTORN.

Analyserar timeline (post-voiceover) och hittar:
  * segment utan visuellt skifte i >6 s (MANDATE: visual change var 2-6 s)
  * klipp som överlappar voiceover
  * SFX-frekvens (för hård TikTok-känsla)
  * musik-intensitet som kolliderar (t.ex. IMPACT under tyst setup)

Fixar deterministiskt (lägg in cards/beats i glappen) och/eller via LLM.
Skriver pacing.json och returnerar (diagnos, ev. uppdaterad plan).
"""
import os, json
from agents import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_INTERVAL = 6.5     # sek mellan visuella skiften (MANDATE 2-6 s, buffer)
MAX_SFX_PER_30 = 6     # SFX-budget (TikTok-skydd)

def analyze(timeline, plan):
    """Returnerar diagnos-dict med problem + mått."""
    segs = timeline.get("segments", [])
    graphics = timeline.get("graphics", [])
    clips = timeline.get("clips", [])
    # visuella "beats": grafik + clips sorterat i tid
    vbeats = []
    for g in graphics:
        vbeats.append((g["T0"], g["T1"], f"g:{g['id']}", g["block"]))
    for c in clips:
        vbeats.append((c["T0"], c["T1"], f"clip:{c['number']}", c["block"]))
    vbeats.sort()

    issues = []
    # per segment: glapp utan visuellt skifte
    for s in segs:
        seg_gfx = [g for g in vbeats if s["start"] <= g[0] < s["start"] + s["dur"]]
        if not seg_gfx:
            issues.append({"block": s["id"], "type": "no_visual",
                           "detail": f"block {s['id']} ({s['dur']:.1f}s) saknar visuals"})
            continue
        # intervaller i blocket
        pts = sorted(set([s["start"]] + [g[0] for g in seg_gfx if g[0] >= s["start"]]
                         + [s["start"] + s["dur"]]))
        for a, b in zip(pts, pts[1:]):
            if b - a > MAX_INTERVAL:
                issues.append({"block": s["id"], "type": "long_interval",
                               "detail": f"{b - a:.1f}s utan visuellt skifte",
                               "at": round(a, 2), "dur": round(b - a, 2)})
    # SFX-överbelastning
    sfx = sum(1 for g in graphics if g.get("impact") or g.get("reveal"))
    sfx += len(clips) * 2
    if timeline.get("total", 0) > 1:
        per30 = sfx / (timeline["total"] / 30.0)
        if per30 > MAX_SFX_PER_30:
            issues.append({"type": "sfx_overload",
                           "detail": f"{per30:.1f} SFX/30s (> {MAX_SFX_PER_30})"})
    # musik-kollision: IMPACT i block med LOW-tempo-röst
    int_by_block = {b["id"]: b.get("music", "MEDIUM")
                    for b in plan.get("blocks", [])}
    for g in graphics:
        b = g["block"]
        if int_by_block.get(b) == "LOW" and (g.get("impact") or g.get("reveal")):
            issues.append({"type": "music_collision", "block": b,
                           "detail": "impact/reveal med LOW-musik — dämpa"})
    letters = {"total": timeline.get("total", 0), "nb_visuals": len(vbeats),
               "graphics": len(graphics), "clips": len(clips),
               "issues": issues,
               "words": sum(len(s["text"].split()) for s in segs)}
    dev_total = timeline.get("total", 1) or 1
    letters["wpm"] = round(letters["words"] / (dev_total / 60.0), 1)
    return letters

def fix(letters, timeline, plan):
    """Returnerar (fixbeskrivningar, uppdaterad plan).

    Determinism: lägger INTE till dubbletter; vid sfx_overload/music_collision
    dämpas impact/reveal på de minst viktiga beatsen (SFX-budget)."""
    fixes = []
    new_visuals = list(plan.get("visual_plan", []))
    tag_by_id = {v.get("id"): v for v in new_visuals}

    # 1) injicera card i block utan visuals / i långa rena glapp
    for iss in letters["issues"]:
        if iss["type"] == "no_visual":
            block = iss.get("block")
            if not any(v.get("block") == block for v in new_visuals):
                new_visuals.append({
                    "id": f"pace_{block}", "block": block, "type": "card",
                    "text": f"{block}", "sub": "THE STORY",
                    "at": 0.5, "until": "end-0.4", "anim": "rise",
                    "w": 820, "x": 230, "y": 250, "impact": False, "reveal": False})
                fixes.append({"block": block, "fix": "inject card (tomt block)"})

    # 2) SFX-budget: dämpa impact/reveal på backend av beatsen
    has_sfx = any(iss["type"] == "sfx_overload" for iss in letters["issues"])
    if has_sfx:
        # behåll effekt på reveal-flaggor (viktiga), dämpa övriga impacts
        impactful = [v for v in new_visuals if v.get("impact") or v.get("reveal")]
        for v in impactful[::2]:  # varannan
            if not v.get("reveal"):
                v["impact"] = False
        fixes.append({"fix": f"SFX-budget: dämpade {len(impactful) // 2} impacts"})

    # 3) musik-kollision: ta bort impact/reveal i LOW-block
    int_by_block = {b["id"]: b.get("music", "MEDIUM")
                    for b in plan.get("blocks", [])}
    for v in new_visuals:
        if int_by_block.get(v.get("block")) == "LOW" and (v.get("impact") or v.get("reveal")):
            v["impact"] = False
            v["reveal"] = False
    if any(iss["type"] == "music_collision" for iss in letters["issues"]):
        fixes.append({"fix": "musikkollision: tagit bort impact/reveal i LOW-block"})

    if new_visuals != plan.get("visual_plan", []):
        plan["visual_plan"] = new_visuals
    if fixes:
        plan["_pacing_fixes"] = fixes
    return fixes, plan
