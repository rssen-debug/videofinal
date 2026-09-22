#!/usr/bin/env python3
"""agents/thumbnail_agent.py — thumbnail-koncept (renderas med PIL + extra-fonts
eller AI om tillgänglig). Titelpaket skrivs till metadata.json.
"""
import os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(plan, topic, project_dir, video_out):
    title = plan.get("title") or topic
    concepts = _concepts(topic, title)
    thumb = _render_thumb(topic, title, os.path.join(project_dir, "thumbnail.jpg"))
    return {"title": title, "title_candidates": concepts,
            "thumbnail": thumb, "video": os.path.relpath(video_out, ROOT),
            "description": _description(topic, title, plan),
            "tags": [t.lower() for t in ([topic] + plan.get("keywords", []))[:12]],
            "language": "en"}

def _concepts(topic, title):
    return [
        title,
        f"How {topic} Took Over",
        f"The Real {topic} Story",
        f"{topic}, Explained",
        f"What Happened to {topic}",
        f"The {topic} Problem",
        f"{topic}: The Untold Story",
        f"Inside {topic}",
        f"The Fall of {topic}",
        f"Why Everyone Is Talking About {topic}",
    ]

def _render_thumb(topic, title, path):
    """Dramatisk dark-thumbnail: gradient + röd glow + Anton-titel + topic."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
        import sys
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from gfx_kit import F
        W, H = 1280, 720
        img = Image.new("RGB", (W, H), (8, 8, 12))
        d = ImageDraw.Draw(img)
        for y in range(H):
            k = y / H
            d.line([(0, y), (W, y)], fill=(int(6 + 30 * k), int(5 + 10 * k), int(8 + 22 * k)))
        blob = Image.new("RGB", (W, H), (0, 0, 0))
        bd = ImageDraw.Draw(blob)
        bd.ellipse([int(W * 0.55), int(H * 0.45), int(W * 1.05), int(H * 1.05)], fill=(88, 12, 16))
        blob = blob.filter(ImageFilter.GaussianBlur(110))
        img = Image.blend(img, blob, 0.6)
        dr = ImageDraw.Draw(img)
        word = " ".join(topic.split()[:4]).upper()
        font = F(150, "anton")
        word2 = "THE STORY" 
        f2 = F(64, "bebas")
        # shadowed text
        for off, col in [((6, 6), (0, 0, 0)), ((0, 0), (255, 255, 255))]:
            w1 = dr.textlength(word, font=font)
            dr.text(((W - w1) / 2 + off[0], 220 + off[1]), word, font=font, fill=col)
            w2 = dr.textlength(word2, font=f2)
            dr.text(((W - w2) / 2 + off[0], 440 + off[1]), word2, font=f2, fill=col)
        img.save(path, quality=93)
        return os.path.relpath(path, ROOT)
    except Exception as e:
        return None

def _description(topic, title, plan):
    bl = plan.get("blocks", [])[0].get("voiceover", "") if plan.get("blocks") else ""
    return (f"{title}. A fast-paced internet documentary about {topic}. "
            "Research-backed, citing public sources. "
            f"Hook: {bl[:140]}")

def write_metadata(meta, project_dir):
    with open(os.path.join(project_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
