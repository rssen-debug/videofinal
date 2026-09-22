#!/usr/bin/env python3
"""engine/knowledge.py — persistent kunskapsbas över körningar.

channel_knowledge.json: hooks/ämnen/thumbnails/retention-mönster + per-projekt
index (projects/index.json). Learning-loop: varje körning lär nästa.
"""
import os, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, "channel_knowledge.json")
INDEX = os.path.join(ROOT, "projects", "index.json")

def load():
    if os.path.exists(KB):
        try:
            return json.load(open(KB, encoding="utf-8"))
        except Exception:
            pass
    return {
        "successful_topics": [], "weak_topics": [],
        "successful_hooks": [], "thumbnail_patterns": [],
        "audience_patterns": [], "retention_patterns": [],
        "formats_used": [], "avoid_repeat": [],
        "_note": ("Retention/CTR-matning sker manuellt efter publicering: "
                  "fyll i valfria success/retention-fält per projekt i "
                  "projects/index.json, så väger systemet in det framöver."),
    }

def save(kb):
    tmp = KB + ".tmp"
    json.dump(kb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, KB)

def record_run(slug, topic, meta):
    kb = load()
    kb.setdefault("successful_topics", []).append(topic)
    # heuristik: hook-kandidat sparas för återkoppling
    if meta.get("title"):
        kb.setdefault("formats_used", [])
        kb["formats_used"].append({"slug": slug, "title": meta["title"],
                                   "date": datetime.date.today().isoformat()})
        kb["formats_used"] = kb["formats_used"][-50:]
    kb["successful_topics"] = list(dict.fromkeys(kb["successful_topics"]))[-50:]
    save(kb)
    _index_append(slug, topic, meta)

def _index_append(slug, topic, meta):
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    idx = []
    if os.path.exists(INDEX):
        try:
            idx = json.load(open(INDEX, encoding="utf-8"))
        except Exception:
            idx = []
    entry = {"slug": slug, "topic": topic,
             "date": datetime.date.today().isoformat(),
             "title": meta.get("title", topic),
             "video": meta.get("video", ""),
             "thumbnail": meta.get("thumbnail", ""),
             "duration": meta.get("duration"), "qc": meta.get("qc", "?"),
             "risk": meta.get("risk", "?"),
             "youtube_id": meta.get("youtube_id", ""),
             "analytics": meta.get("analytics", {})}
    idx = [e for e in idx if e.get("slug") != slug] + [entry]
    json.dump(idx, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- ANALYTICS INGEST (learning-loop, punkt 23-24) ----------------
ANALYTICS_FIELDS = ("ctr", "avd", "retention", "likes", "comments",
                    "shares", "subs_gained", "views", "traffic_sources",
                    "sections_lost_viewers")

def ingest_analytics(slug, analytics):
    """Skriv CTR/AVD/retention/likes/... till ett projekt och uppdatera
    channel_knowledge.json (successful_topics/weak_topics/retention_patterns)."""
    data = {k: analytics[k] for k in ANALYTICS_FIELDS if k in analytics}
    if not data:
        raise ValueError("ange minst ett nyckelfält: " + ", ".join(ANALYTICS_FIELDS))
    idx = []
    if os.path.exists(INDEX):
        try:
            idx = json.load(open(INDEX, encoding="utf-8"))
        except Exception:
            idx = []
    entry = next((e for e in idx if e.get("slug") == slug), None)
    if entry is None:
        entry = {"slug": slug, "topic": slug}
        idx.append(entry)
    entry["analytics"] = data
    json.dump(idx, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # uppdatera kanals-kunskap
    kb = load()
    try:
        ctr = float(data.get("ctr", 0)) if data.get("ctr") not in (None, "") else None
        avd = float(data.get("avd", 0)) if data.get("avd") not in (None, "") else None
    except (TypeError, ValueError):
        ctr = avd = None
    if ctr is not None:
        if ctr < 4.0:
            kb.setdefault("weak_topics", []).append(entry.get("topic", slug))
            kb["weak_topics"] = list(dict.fromkeys(kb["weak_topics"]))[-20:]
        else:
            kb.setdefault("successful_topics", []).append(entry.get("topic", slug))
            kb["successful_topics"] = list(dict.fromkeys(kb["successful_topics"]))[-20:]
    if avd is not None:
        kb.setdefault("retention_patterns", []).append(
            {"topic": entry.get("topic", slug), "avd": avd, "ctr": ctr,
             "date": datetime.date.today().isoformat()})
        kb["retention_patterns"] = kb["retention_patterns"][-50:]
    if data.get("sections_lost_viewers"):
        kb.setdefault("audience_patterns", []).append(
            {"topic": entry.get("topic", slug),
             "lost_sections": data["sections_lost_viewers"]})
        kb["audience_patterns"] = kb["audience_patterns"][-50:]
    save(kb)
    return data
