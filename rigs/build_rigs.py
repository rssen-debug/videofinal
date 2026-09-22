"""Build persistent cut-out rigs for the cyber duo from the approved A-pose sources.

Layers (drawn back to front): legL, legR, armL, armR, torso, head.  Arms and legs sit
behind the torso so their hidden roots can rotate under the cape / armour without gaps.
Polygons are hand-placed from a labelled grid of each source image (see CHARACTER_BIBLE.md).
Run:  python build_rigs.py   ->  rig-ninja/ , rig-assistant/  (+ _debug_<name>.jpg)
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = Path(__file__).resolve().parent

RIGS = {
    "ninja": {
        "source": "ninja-rig-source.png",
        "polys": {
            "head": [(270, 30), (500, 30), (500, 318), (270, 318)],
            "armL": [(150, 500), (205, 520), (165, 565), (150, 660), (150, 700), (148, 800), (10, 800), (10, 640), (85, 560)],
            "armR": [(617, 500), (562, 520), (602, 565), (617, 660), (617, 700), (619, 800), (757, 800), (757, 640), (682, 560)],
            "legL": [(200, 900), (392, 900), (392, 1376), (120, 1376)],
            "legR": [(392, 900), (600, 900), (660, 1376), (392, 1376)],
            "torso": [(20, 312), (747, 312), (747, 1010), (440, 1010), (440, 1120), (355, 1120), (355, 1010), (20, 1010)],
        },
        "pivots": {"head": (383, 300), "armL": (178, 510), "armR": (589, 510), "legL": (290, 930), "legR": (490, 930), "torso": (384, 930)},
        "face": {"cyber": (350, 203, 15), "eye": (413, 203, 22, 12), "mouth": (382, 268, 40, 18), "skin_at": (432, 240), "chin": 300, "center": 383, "brow": (413, 188)},
        "torso_excludes": ["armL", "armR"],
        "leg_exclude_tab": [(355, 1010), (440, 1010), (440, 1120), (355, 1120)],
    },
    "assistant": {
        "source": "assistant-rig-source.png",
        "polys": {
            "head": [(330, 30), (530, 30), (530, 280), (330, 280)],
            "armL": [(200, 350), (322, 350), (321, 440), (320, 487), (300, 527), (284, 567), (270, 607), (237, 647), (230, 687), (225, 760), (60, 760), (60, 360)],
            "armR": [(535, 350), (660, 350), (790, 360), (790, 760), (620, 760), (616, 687), (605, 647), (587, 607), (578, 567), (562, 527), (537, 487), (535, 440)],
            "legL": [(240, 650), (428, 650), (428, 1264), (150, 1264)],
            "legR": [(428, 650), (620, 650), (700, 1264), (428, 1264)],
            "torso": [(235, 276), (625, 276), (625, 350), (535, 350), (535, 440), (537, 487), (562, 527), (578, 567), (587, 607), (605, 647), (616, 687), (620, 745), (230, 745), (230, 687), (237, 647), (270, 607), (284, 567), (300, 527), (320, 487), (321, 440), (322, 350), (235, 350)],
        },
        "pivots": {"head": (430, 268), "armL": (300, 330), "armR": (556, 330), "legL": (345, 670), "legR": (505, 670), "torso": (428, 670)},
        "face": {"cyber": (393, 178, 13), "eye": (463, 176, 22, 12), "mouth": (430, 232, 38, 16), "skin_at": (470, 215), "chin": 268, "center": 430, "brow": (463, 160)},
        "torso_excludes": ["armL", "armR"],
        "leg_exclude_tab": None,
    },
}

Z = ["legL", "legR", "armL", "armR", "torso", "head"]


def alpha_from_white(rgb):
    mn = rgb.min(axis=2)
    bg_candidate = mn > 225
    lab, n = ndimage.label(bg_candidate)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    border.discard(0)
    bg = np.isin(lab, list(border))
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    ring = ndimage.binary_dilation(bg, iterations=2) & ~bg
    soft = np.clip((255 - mn.astype(int)) * 255 / 60, 0, 255).astype(np.uint8)
    alpha[ring] = np.minimum(alpha[ring], np.maximum(soft[ring], 90))
    return alpha


def poly_mask(shape, pts):
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon(pts, fill=255)
    return np.array(im) > 0


def build(name, spec):
    src = Image.open(HERE / spec["source"]).convert("RGB")
    rgb = np.array(src)
    H, W = rgb.shape[:2]
    alpha = alpha_from_white(rgb)
    masks = {k: poly_mask(rgb.shape, v) for k, v in spec["polys"].items()}
    for ex in spec["torso_excludes"]:
        masks["torso"] &= ~masks[ex]
    masks["torso"] &= ~masks["head"]
    if spec["leg_exclude_tab"]:
        tab = poly_mask(rgb.shape, spec["leg_exclude_tab"])
        masks["legL"] &= ~tab
        masks["legR"] &= ~tab
    out = HERE / f"rig-{name}"
    out.mkdir(exist_ok=True)
    parts = []
    for z, key in enumerate(Z):
        m = masks[key] & (alpha > 0)
        if not m.any():
            raise SystemExit(f"{name}: empty layer {key}")
        ys, xs = np.where(m)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        layer = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        layer[..., :3] = rgb[y0:y1, x0:x1]
        layer[..., 3] = np.where(m[y0:y1, x0:x1], alpha[y0:y1, x0:x1], 0)
        Image.fromarray(layer, "RGBA").save(out / f"{key}.png")
        px, py = spec["pivots"][key]
        parts.append({"name": key, "file": f"{key}.png", "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0), "pivot": [int(px), int(py)], "z": z})
    face = dict(spec["face"])
    sx, sy = face.pop("skin_at")
    patch = rgb[sy - 3:sy + 4, sx - 3:sx + 4].reshape(-1, 3).mean(axis=0)
    face["skin"] = [int(v) for v in patch]
    mx, my, mw, mh = face["mouth"]
    around = np.concatenate([rgb[my - mh, mx - mw // 2:mx + mw // 2], rgb[my + mh, mx - mw // 2:mx + mw // 2]]).reshape(-1, 3).mean(axis=0)
    face["mouth_skin"] = [int(v) for v in around]
    rig = {"character": name, "source": spec["source"], "width": W, "height": H, "parts": parts, "face": face,
           "order": Z, "note": "Arms and legs render behind the torso; head in front. Pivots are source-pixel coordinates."}
    (out / "rig.json").write_text(json.dumps(rig, indent=1))
    # debug sheet: tinted layers + reassembly
    tint = {"legL": (255, 0, 0), "legR": (255, 128, 0), "armL": (0, 128, 255), "armR": (0, 200, 200), "torso": (0, 200, 0), "head": (255, 0, 255)}
    dbg = Image.new("RGB", (W * 2, H), "white")
    d = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    re = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    for p in parts:
        lay = Image.open(out / p["file"]).convert("RGBA")
        col = Image.new("RGBA", lay.size, tint[p["name"]] + (0,))
        col.putalpha(lay.getchannel("A").point(lambda a: int(a * 0.85)))
        d.alpha_composite(col, (p["x"], p["y"]))
        re.alpha_composite(lay, (p["x"], p["y"]))
    dd = ImageDraw.Draw(d)
    for k, (px, py) in spec["pivots"].items():
        dd.ellipse([px - 6, py - 6, px + 6, py + 6], outline="black", width=3)
    cx, cy, cr = face["cyber"]
    ex, ey, ew, eh = face["eye"]
    dd.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], outline="lime", width=2)
    dd.ellipse([ex - ew // 2, ey - eh // 2, ex + ew // 2, ey + eh // 2], outline="yellow", width=2)
    dd.rectangle([mx - mw // 2, my - mh // 2, mx + mw // 2, my + mh // 2], outline="red", width=2)
    dbg.paste(d.convert("RGB"), (0, 0))
    dbg.paste(re.convert("RGB"), (W, 0))
    dbg = dbg.resize((dbg.width // 2, dbg.height // 2))
    dbg.save(HERE / f"_debug_{name}.jpg", quality=80)
    print(name, "layers:", [(p["name"], p["w"], p["h"]) for p in parts], "skin", face["skin"])


if __name__ == "__main__":
    for n, s in RIGS.items():
        build(n, s)
