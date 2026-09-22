#!/usr/bin/env python3
"""agents/graphics_agent.py — grafik-regissören: LLM-plan → PNG (via gfx_kit /
make_video helpers) → EPISODES/episode_<slug>.json som make_video.py exekverar.

GRAFIKTYPER som stöds (→ gfx_kit/make_assets):
  glow, lower_third, stat, tweet, timeline, chart, card, photo, circle
Anim (-> cinema-easing i make_video): slam/slideL/slideR/rise/pop/drift
"""
import os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GFX = os.path.join(ROOT, "assets", "gfx")
SRC = os.path.join(ROOT, "assets", "src")
HERE = os.path.join(ROOT, "scripts")
import sys
sys.path.insert(0, HERE)
import gfx_kit as GK
from make_video import big_card

def _g(n):
    return os.path.join(GFX, n)

def build_graphics(plan, slug, people_lookup):
    """Genererar PNGs för varje visual_plan-rad. Returnerar beats-lista + assets-lista."""
    beats, assets, used = [], [], set()
    default_layout = {(None, None): (120, 170)}

    def accent_of(v):
        a = v.get("accent")
        if isinstance(a, list) and len(a) >= 3:
            return tuple(a[:3] + [255])
        return (232, 34, 46, 255)

    for i, v in enumerate(plan.get("visual_plan", [])):
        typ = v.get("type", "card")
        name = f"{slug}_v{i}_{typ}.png"
        path = _g(name)
        try:
            if typ == "glow":
                text = v.get("text") or v.get("big") or plan.get("topic", slug).upper()
                px = v.get("px", min(170, max(90, 170 - len(text) * 2)))
                GK.glow_title(name, text, px, glow=accent_of(v))
            elif typ == "lower_third":
                main = v.get("text") or (people_lookup or [{}])[0].get("name", slug.upper())
                GK.lower_third(name, main, v.get("sub", ""), accent_of(v))
            elif typ == "stat":
                GK.stat_card(name, v.get("big", "1M+"), v.get("text") or v.get("sub", ""), accent_of(v))
            elif typ == "tweet":
                GK.tweet_ui(name, v.get("name", "source"), v.get("handle", "@source"),
                            v.get("text", ""), v.get("meta", ""), v.get("likes", ""),
                            (v.get("img") or ""), W=int(v.get("w", 940)))
            elif typ == "timeline":
                items = v.get("data") or [["2017", "start"], ["2020", "rise"],
                                          ["2024", "turn"], ["2026", "now"]]
                items = [tuple(p) for p in items]
                GK.timeline_card(name, items, accent_of(v))
            elif typ == "chart":
                data = v.get("data") or [["a", 10], ["b", 30], ["c", 60]]
                data = [(p[0], float(p[1])) for p in data]
                GK.bar_chart(name, data, accent_of(v))
            elif typ == "photo":
                img = v.get("img") or (people_lookup[0]["img"] if people_lookup else "")
                if img and os.path.exists(os.path.join(ROOT, img)):
                    from make_assets import photo_card
                    photo_card(os.path.join(ROOT, img), name)
                else:
                    raise RuntimeError("photo utan bild")
            elif typ == "circle":
                img = v.get("img") or (people_lookup[0]["img"] if people_lookup else "")
                if img and os.path.exists(os.path.join(ROOT, img)):
                    GK.circle_portrait(os.path.join(ROOT, img), name,
                                       accent_of(v)[:3] + (255,))
                else:
                    raise RuntimeError("circle utan bild")
            else:  # card (default)
                big_card(name, v.get("text") or v.get("big") or "", v.get("sub", ""),
                         accent_of(v), px=int(v.get("px", 82)))
            w = int(v.get("w") or 700)
            x = v.get("x")
            y = v.get("y")
            # make_video.py kräver numeriska x/y (annars blir overlay-uttrycket
            # "None" och ffmpeg dör med "invalid argument")
            if x is None or (isinstance(x, str) and not x.strip()):
                x = (1280 - w) // 2
            if y is None or (isinstance(y, str) and not y.strip()):
                y = 260
            beats.append({
                "block": v.get("block", "A1"),
                "asset": name,
                "at": v.get("at", 0.3),
                "until": v.get("until", "end-0.4"),
                "anim": v.get("anim", "pop"),
                "w": w,
                "x": x, "y": y,
                "impact": bool(v.get("impact")),
                "reveal": bool(v.get("reveal")),
            })
            assets.append({"type": "graphic", "file": path, "source": "synthetic",
                           "license": "ai-generated", "kind": "synthetic"})
        except Exception as e:
            # fallback: ren textkort så blocket aldrig blir tomt
            try:
                big_card(name, v.get("text") or v.get("big") or typ.upper(),
                         v.get("sub", ""), accent_of(v))
                w = int(v.get("w") or 700)
                x = v.get("x") if v.get("x") not in (None, "") else (1280 - w) // 2
                y = v.get("y") if v.get("y") not in (None, "") else 260
                beats.append({
                    "block": v.get("block", "A1"), "asset": name,
                    "at": v.get("at", 0.3), "until": v.get("until", "end-0.4"),
                    "anim": v.get("anim", "pop"), "w": w,
                    "x": x, "y": y,
                    "impact": bool(v.get("impact")), "reveal": bool(v.get("reveal"))})
                assets.append({"type": "graphic", "file": path, "source": "synthetic",
                               "license": "ai-generated", "kind": "synthetic"})
            except Exception:
                pass
    return beats, assets

def compile_episode(plan, timeline, slug, topic, beats, clip_files, out_rel,
                    people_lookup, bg_rel, keywords, style_look):
    """Bygger EPISODES/episode_<slug>.json (ingången till make_video.py)."""
    blocks = [{"id": b["id"], "text": b.get("voiceover", "")}
              for b in plan.get("blocks", [])]

    clips = []
    for c in plan.get("clip_plan", []):
        key = c.get("number", len(clips) + 1)
        fname = clip_files.get(str(key))
        if not fname:
            continue
        clips.append({
            "file": fname, "cut": float(c.get("cut", 0.0)),
            "dur": float(c.get("dur", 6)), "block": c["block"],
            "at": c.get("at", 0), "vol": float(c.get("vol", 1.0)),
            "w": int(c.get("w", 900)), "y": int(c.get("y", 64)),
        })
    if len(clips) < 3 and clip_files:
        # MANDATE: ≥3 klipp — om planen gav färre fyller vi på med befintliga
        for i, (k, fname) in enumerate(clip_files.items()):
            if len(clips) >= 3:
                break
            clips.append({"file": fname, "cut": 0, "dur": 5.0, "block": "A4",
                          "at": i * 1.5, "vol": 0.9, "w": 880, "y": 70})

    cfg = {
        "topic": topic,
        "out": out_rel,
        "look": style_look or "DEFAULT",
        "gap": plan.get("gap", 0.7),
        "tail": plan.get("tail", 2.5),
        "bg": bg_rel or "assets/src/bg_ai.png",
        "keywords": [k.lower() for k in (keywords or [])],
        "blocks": blocks,
        "people": [], "glows": [], "tweet": None, "stats": [], "cards": [],
        "beats": beats,
        "clips": clips,
        "endcard": {"text": "SUBSCRIBE", "glow": [60, 220, 120, 140]},
        "_meta": {"slug": slug, "title": plan.get("title", topic),
                  "generated_by": "sunny_auto.py"},
    }
    ep_path = os.path.join(ROOT, "EPISODES", f"episode_{slug}.json")
    with open(ep_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    return ep_path, cfg
