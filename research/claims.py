#!/usr/bin/env python3
"""research/claims.py — påstående-typologi, källhierarki och research.json.

Varje claim:
  claim, source, url, date, evidence, confidence, kind, tier

kind i {FACT, CLAIM, ALLEGATION, OPINION, INFERENCE, RUMOR}
tier i 1..5 (krav: tier 4-5 får bara användas för lead-discovery, inte som bevis).
"""
import os, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLAIM_KINDS = ("FACT", "CLAIM", "ALLEGATION", "OPINION", "INFERENCE", "RUMOR")

THEORY_TIERS = {
    1: "official/court/company/government/direct-interview",
    2: "major reputable news / established publications",
    3: "specialist publications",
    4: "reddit/x/forums (lead discovery only)",
    5: "random websites (lead discovery only)",
}

# typ av källa → default-tier
SOURCE_TIER_HINTS = {
    "wikipedia": 2, "forbes": 2, "reuters": 2, "ap": 2, "bbc": 2, "bloomberg": 2,
    "nytimes": 2, "wsj": 2, "washingtonpost": 2, "time": 2, "theguardian": 2,
    "cnn": 2, "cnbc": 2, "businessinsider": 2, "latimes": 2, "variety": 2,
    "hollywoodreporter": 2, "youtube": 1, "twitter": 4, "x.com": 4,
    "reddit": 4, "news.google": 3, "wikipedia.org": 2, "": 4,
}

_NUM_RE = re.compile(
    r"\b(?:\$|€|£)?\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"
    r"|\b\d+(?:\.\d+)?\s?(?:million|billion|thousand|%|percent|dollars|subscribers|views|hours|years)\b"
    r"|\b\d{4}\b", re.IGNORECASE)

def make_claim(claim, source, url="", date="", evidence="", confidence=0.7,
               kind="CLAIM", tier=None, query=""):
    if tier is None:
        t = source.lower()
        tier = SOURCE_TIER_HINTS.get(t, 3)
        for k, v in SOURCE_TIER_HINTS.items():
            if k and k in t:
                tier = v
                break
    return {"id": "c%d" % (int(abs(hash(claim)) % 1_000_000_000)),
            "claim": claim, "source": source, "url": url, "date": date,
            "evidence": evidence, "confidence": round(float(confidence), 3),
            "kind": kind if kind in CLAIM_KINDS else "CLAIM",
            "tier": int(tier), "query": query}

def save_research(path, payload):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

def load_research(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def numbers_in(text):
    """Alla siffror/datum/siffror-med-enhet i ett block (för fact-check)."""
    return [m.group(0) for m in _NUM_RE.finditer(text or "")]

def claim_mentions_number(claim, num):
    hay = (claim.get("claim", "") + " " + claim.get("evidence", "")
           + " " + (claim.get("source", "") or "")).lower()
    return num.lower() in hay

def unsupported_numbers(block_text, covered_claims):
    """Returnerar siffror i blocket som inte backas upp av någon claim."""
    bad = []
    for n in numbers_in(block_text):
        if not any(claim_mentions_number(c, n) for c in covered_claims):
            if n not in bad:
                bad.append(n)
    return bad

def new_research(topic):
    return {"schema": "sunny.research/1", "topic": topic,
            "generated": "", "facts": [], "sources": []}
