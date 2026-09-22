#!/usr/bin/env python3
"""agents/licensing.py — licens-/upphovsrättslager.

Varje asset → {source, license, tier, risk, allowed|review|reject}.
Tier 1 = fri användning · tier 2 = villkorad · tier 3 = granska · 4/5 = demo/ej publicera.
"""
import os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LICENSES = {
    "public domain": (1, "allowed", "public domain"),
    "pd": (1, "allowed", "public domain"),
    "cc0": (1, "allowed", "CC0"),
    "cc-by": (1, "allowed", "CC BY (attribute)"),
    "cc-by 2.0": (1, "allowed", "CC BY 2.0"),
    "cc-by 3.0": (1, "allowed", "CC BY 3.0"),
    "cc-by 4.0": (1, "allowed", "CC BY 4.0"),
    "cc-by-sa": (2, "review", "CC BY-SA (share-alike)"),
    "cc by-sa": (2, "review", "CC BY-SA"),
    "cc-by-sa 2.0": (2, "review", "CC BY-SA 2.0"),
    "cc-by-sa 3.0": (2, "review", "CC BY-SA 3.0"),
    "cc-by-sa 4.0": (2, "review", "CC BY-SA 4.0"),
    "gfdl": (2, "review", "GFDL"),
    "cc-by-nc": (3, "review", "CC BY-NC (icke-kommersiell)"),
    "cc-by-nd": (3, "review", "CC BY-ND"),
    "youtube": (4, "review", "YouTube — fair use-beslut krävs, demo/utbildning"),
    "ai-generated": (1, "allowed", "AI-genererad (egen)"),
    "synthetic": (1, "allowed", "syntetisk"),
    "original": (1, "allowed", "eget original"),
}

def classify(license_tag="", source="", kind=""):
    key = (license_tag or "").lower().strip()
    hit = None
    for k, v in LICENSES.items():
        if key.startswith(k) or k.startswith(key):
            hit = v
            break
    if hit:
        tier, status, label = hit
    elif "creative commons" in key or "cc" in key:
        tier, status, label = 2, "review", key or "Creative Commons"
    elif key == "" and kind == "synthetic":
        tier, status, label = 1, "allowed", "syntetisk"
    else:
        tier, status, label = 3, "review", (license_tag or "okänd") + " (granska)"
    # sources som är kända public-domain-arkiv
    if source and any(s in source.lower() for s in ("wikimedia", "commons")):
        if tier <= 2:
            tier = min(tier, 2)
    return {"license": license_tag, "tier": tier, "status": status,
            "label": label, "source": source}

def manifest(project_dir, assets):
    """assets: lista av dicts {type, file, source, license}. Skriver assets.json."""
    out = []
    for a in assets:
        cl = classify(a.get("license", ""), a.get("source", ""), a.get("kind", ""))
        out.append({"type": a.get("type"), "file": a.get("file"),
                    "source": a.get("source", ""), **cl})
    with open(os.path.join(project_dir, "assets.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out
