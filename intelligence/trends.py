#!/usr/bin/env python3
"""research/trends.py — ämnesupptäckt för `--auto`.

Samlar kandidat-ämnen (Google Trends RSS, Google News, YouTube-sökförslag)
och låter sedan en poängsättare (LLM om nyckel finns, annars heuristik) ranka
dem på story-potential snarare än rå trendstorlek.
"""
import os, re

from research import sources as S

def google_trends_rss():
    """Googles dagliga trend-RSS → ämnen."""
    xml = S.get("https://trends.google.com/trending/rss?geo=US", use_cache=True)
    import xml.etree.ElementTree as ET
    out = []
    try:
        for it in ET.fromstring(xml).iter("item"):
            out.append((it.findtext("title") or "").strip())
    except Exception:
        pass
    return out

def youtube_autocomplete(seed):
    """YouTube-sökförslag (suggestqueries) — fungerar utan API-nyckel."""
    try:
        j = S.get("http://suggestqueries.google.com/complete/search",
                  params={"client": "firefox", "ds": "yt", "q": seed},
                  json_out=True)
        flat = []
        for item in j[1] if len(j) > 1 else []:
            flat.append(item[0] if isinstance(item, list) else item)
        return flat
    except Exception:
        return []

def discover_candidates(seed_topics=None, n=20):
    """Returnerar lista av kandidat-ämnen (strängar), avduplicerade."""
    cand, seen = [], set()
    for t in (seed_topics or []):
        if t and t not in seen:
            cand.append(t); seen.add(t)
    for q in ("internet", "youtube", "streamer", "creator drama", "viral"):
        for s in youtube_autocomplete(q):
            if s and s not in seen and len(cand) < n:
                cand.append(s); seen.add(s)
    for t in google_trends_rss():
        t = t.split(",")[0].strip()
        if t and t not in seen and len(cand) < n:
            cand.append(t); seen.add(t)
    for q in ("viral story", "creator news", "controversy youtube"):
        for item in S.news_rss(q, count=5):
            title = re.sub(r"\s-\s.*$", "", item["title"]).strip()
            if title and title not in seen and len(cand) < n:
                cand.append(title); seen.add(title)
    return cand[:n]

def heuristic_score(topic, llm=None):
    """Grundpoängsättning: story-signal > trend-storlek."""
    t = (topic or "").lower()
    score = 0.5
    for kw in ("vs", "drama", "controversy", "lawsuit", "exposed", "the truth",
               "rise", "fall", "explained", "story", "secret", "banned"):
        if kw in t:
            score += 0.15
    for kw in ("update", "full episode", "reaction", "clip", "stream"):
        if kw in t:
            score -= 0.1
    # LLM får sista ordet om tillgänglig
    if llm is not None:
        try:
            extra = llm.score_topic(topic)
            score = 0.5 * score + 0.5 * extra
        except Exception:
            pass
    return max(0.0, min(1.0, score))

def pick_best(candidates, llm=None):
    """Returnerar (topic, score)."""
    if not candidates:
        raise RuntimeError("inga kandidat-ämnen hittades")
    scored = sorted(((heuristic_score(c, llm), c) for c in candidates),
                    reverse=True)
    s, topic = scored[0]
    return topic, s
