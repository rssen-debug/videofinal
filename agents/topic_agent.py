#!/usr/bin/env python3
"""agents/topic_agent.py — ämnesupptäckt + ranking (TOPIC SCORING AI).

Samlar kandidater (Google Trends RSS, Google News, YouTube-autocomplete) och
poängsätter STORY-POTENTIAL, inte bara trendstorlek. LLM ger rik score-json om
nyckel finns; annars heuristik.

Output per kandidat (spec):
  {topic, why_now, story_angle, audience, competition, novelty,
   research_depth, video_potential, demand, score}
"""
import os, json, re
from research import trends as TR
from agents import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _heuristic(topic):
    t = (topic or "").lower()
    story = 0.5; potential = 0.5; demand = 0.5; novelty = 0.4
    for kw in ("vs", "drama", "controversy", "lawsuit", "exposed", "truth",
               "rise", "fall", "explained", "story", "secret", "banned",
               "feud", "beef", "broke", "empire", "problem"):
        if kw in t:
            story += 0.11; potential += 0.07
    for kw in ("update", "reaction", "clip", "stream", "episode", "highlights",
               "trailer", "official"):
        if kw in t:
            story -= 0.1
    if len(t) > 20:
        novelty += 0.15
    def clip(x):
        return max(0.0, min(1.0, x))
    return {"demand": clip(demand), "novelty": clip(novelty),
            "competition": clip(0.5 + story * 0.3),
            "story": clip(story), "research_depth": clip(0.4 + story * 0.2),
            "video_potential": clip(potential)}

def _llm_score(topic, base):
    try:
        obj = llm.fill_json(
            f"Du är ämnes-scout för en internet-dokumentär-kanal (sunnyv2-stil). "
            f"Bedöm ämnet: '{topic}'.\n"
            "Svara STRICT JSON med nycklarna: why_now (kort text), story_angle "
            "(kort text), audience (text), competition (0-1), novelty (0-1), "
            "research_depth (0-1), video_potential (0-1), demand (0-1).\n"
            "Leta efter STORY-POTENTIAL, inte bara trendstorlek.",
            max_tokens=400)
        if obj:
            for k in ("competition", "novelty", "research_depth",
                      "video_potential", "demand"):
                if k in obj:
                    try:
                        base[k] = float(obj[k])
                    except (TypeError, ValueError):
                        pass
            base["why_now"] = obj.get("why_now", "")
            base["story_angle"] = obj.get("story_angle", "")
            base["audience"] = obj.get("audience", "")
    except Exception:
        pass
    return base

def run(project_dir=None, limit=20, use_llm=None):
    cands = TR.discover_candidates(n=limit)
    use_llm = llm.is_available() if use_llm is None else use_llm
    ranked = []
    for t in cands:
        sc = _heuristic(t)
        if use_llm:
            sc = _llm_score(t, sc)
        sc["topic"] = t
        sc["score"] = round(
            0.25 * sc["video_potential"] + 0.25 * sc["story"]
            + 0.20 * sc["demand"] + 0.15 * sc["novelty"]
            + 0.15 * (1.0 - sc["competition"]), 3)
        ranked.append(sc)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "topics.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"candidates": ranked}, f, ensure_ascii=False, indent=1)
    return ranked

def pick(ranked):
    if not ranked:
        raise RuntimeError("inga kandidat-ämnen")
    return ranked[0]["topic"], ranked[0]["score"]
