#!/usr/bin/env python3
"""agents/visual_agent.py — visuell regissör för stillbilder: porträtt/foton
via Wikimedia (tier 1-2), fallback = mörk gradient-bakgrund (PIL).

Bygger:
  assets/src/<slug>_portrait.jpg  (huvudperson, om hittad)
  assets/src/<slug>_bg.png        (mörk dokumentär-bakgrund, alltid)
Returnerar people-lista till grafik-kompilatorn.
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "src")
from research import sources as S

def _entities(research):
    ents = []
    for f in research.get("facts", [])[:150]:
        for m in re.findall(r"\b([A-Z][a-z]+(?:\s(?:[A-Z][a-z]+|van|de|von)){1,3})\b", f["claim"]):
            if len(m) > 3 and m not in ents:
                ents.append(m)
    return ents[:8]

def _gradient_bg(path, W=1280, H=720):
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", (W, H), (10, 8, 12))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        r = int(8 + 40 * k); g = int(6 + 12 * k); b = int(10 + 26 * k)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    # röd glow-fläck + partiklar
    blob = Image.new("RGB", (W, H), (0, 0, 0))
    bd = ImageDraw.Draw(blob)
    bd.ellipse([int(W * 0.62), int(H * 0.5), int(W * 1.1), int(H * 1.1)], fill=(70, 10, 14))
    bd.ellipse([int(W * 0.2), int(H * 0.16), int(W * 0.5), int(H * 0.4)], fill=(18, 20, 34))
    blob = blob.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, blob, 0.55)
    import random
    rnd = random.Random(7)
    for _ in range(80):
        x, y = rnd.randrange(W), rnd.randrange(H)
        r = rnd.uniform(1, 2.4)
        bd2 = ImageDraw.Draw(img)
        bd2.ellipse([x - r, y - r, x + r, y + r], fill=(255, 244, 240))
    img.save(path, quality=92)

def run(topic, research, project_dir, slug):
    os.makedirs(SRC, exist_ok=True)
    people, assets = [], []
    bg = os.path.join(SRC, f"{slug}_bg.png")
    _gradient_bg(bg)
    assets.append({"type": "bg", "file": bg, "source": "synthetic",
                   "license": "ai-generated", "kind": "synthetic"})

    # huvudporträtt
    portrait = None
    for q in (f"{topic}", f"{topic} portrait"):
        try:
            for im in S.wikimedia_search(q, limit=4):
                if im["mime"].startswith("image/") and im["width"] >= 300:
                    dest = os.path.join(SRC, f"{slug}_portrait{im['mime'][6:] and '.' + im['mime'].split('/')[1]}")
                    S.download(im["url"], dest)
                    portrait = dest
                    assets.append({"type": "photo", "file": dest,
                                   "source": "wikimedia", "license": im["license"]})
                    break
        except Exception:
            pass
        if portrait:
            break
    if portrait:
        people.append({"key": "main", "img": f"assets/src/{os.path.basename(portrait)}",
                       "name": topic.upper(), "sub": "THE STORY", "accent": [232, 34, 46, 255]})

    # ev. bipersoner
    for ent in _entities(research):
        if ent.lower() in topic.lower() or len(people) >= 3:
            continue
        try:
            for im in S.wikimedia_search(ent, limit=3):
                if im["mime"].startswith("image/") and im["width"] >= 250:
                    ext = "." + im["mime"].split("/")[1]
                    dest = os.path.join(SRC, f"{slug}_{re.sub(r'[^a-z0-9]+','_',ent.lower())}{ext}")
                    S.download(im["url"], dest)
                    people.append({"key": ent.lower().replace(" ", "_"),
                                   "img": f"assets/src/{os.path.basename(dest)}",
                                   "name": ent.upper(), "sub": "MENTIONED IN THE STORY",
                                   "accent": [200, 60, 220, 255]})
                    assets.append({"type": "photo", "file": dest,
                                   "source": "wikimedia", "license": im["license"]})
                    break
        except Exception:
            continue

    with open(os.path.join(project_dir, "visuals.json"), "w", encoding="utf-8") as f:
        json.dump({"people": people, "bg": f"assets/src/{os.path.basename(bg)}",
                   "assets": assets}, f, ensure_ascii=False, indent=1)
    return {"people": people, "bg": f"assets/src/{os.path.basename(bg)}", "assets": assets}
