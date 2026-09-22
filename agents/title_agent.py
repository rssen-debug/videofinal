#!/usr/bin/env python3
"""agents/title_agent.py — TITLE-MOTORN (separat från thumbnail).

Typer: Curiosity / Conflict / Transformation / Mystery / Unexpected / Failure /
Rise / Fall / Investigation.

Efter generation -> verifiering:
  * matchar titeln videon (ämnet/nyckelord)?
  * håller den löftet (inte överdriven clickbait)?
  * längd < 100 tecken?
  * upprepar den inte tidigare titlar (channel memory)?

Returnerar {title, candidates:[{title,type,verdict,reasons}], chosen}.
"""
import os, json, re
from agents import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TYPES = ("Curiosity", "Conflict", "Transformation", "Mystery", "Unexpected",
         "Failure", "Rise", "Fall", "Investigation")

CLICKBAIT = re.compile(
    r"\b(you won.t believe|shocking|gone wrong|what happens next will|"
    r"insane|unbelievable|mind-blowing|jaw-dropping)\b", re.IGNORECASE)

def _candidates(topic, title):
    t = topic.strip()
    out = [
        (f"The Story of {t}", "Rise"),
        (f"How {t} Built an Empire Nobody Thought Was Possible", "Transformation"),
        (f"The Problem With {t}", "Conflict"),
        (f"What Really Happened to {t}", "Investigation"),
        (f"The Dark Side of {t}", "Mystery"),
        (f"{t}: Rise and Fall", "Rise"),
        (f"Why the Internet Turned on {t}", "Fall"),
        (f"The Untold Truth About {t}", "Mystery"),
        (f"{t}, Explained", "Investigation"),
        (f"Inside the {t} Machine", "Investigation"),
    ]
    if title and title not in [c for c, _ in out]:
        out.insert(0, (title, "Curiosity"))
    return out

def _verdict(cand, topic, keyword_set, prev_topics, z):
    reasons = []
    low = cand.lower()
    if topic.split() and topic.split()[0].lower() not in low:
        reasons.append("nämner inte ämnet direkt")
    if len(cand) > 100:
        reasons.append("för lång (>100)")
    if CLICKBAIT.search(cand):
        reasons.append("clickbait-ord")
    if any(cand.lower() == p.lower() for p in prev_topics):
        reasons.append("upprepar tidigare titel")
    # löftes-koll: finns det ett "innehålls-säkert" laddat ord?
    if re.search(r"^(the |how |why |what |inside |the problem|the dark)", low):
        reasons.append("tydligt löfte ✓")
    verdict = "PASS" if len(reasons) <= 1 else "REVIEW"
    if any(r.startswith("upprepar") for r in reasons):
        verdict = "REJECT"
    return verdict, reasons

def run(plan, topic, project_dir, memory=None, use_llm=None):
    use_llm = llm.is_available() if use_llm is None else use_llm
    prev_topics = []
    if memory:
        prev_topics = memory.get("avoid_repeat", []) or []
        prev_topics += [f.get("title", "") for f in memory.get("formats_used", [])]
    title = plan.get("title", "") or plan.get("topic", topic)
    cands = _candidates(topic, title)
    if use_llm:
        try:
            obj = llm.fill_json(
                f"Generera 10 titlar (olika typer ur {list(TYPES)}) för en "
                f"internet-dokumentär om '{topic}'. Undvik clickbait, max 100 "
                f"tecken, leverera ett löfte videon faktiskt håller. "
                f"Tidigare titlar att INTE upprepa: {prev_topics[:10]}.\n"
                "Svara JSON: {\"titles\":[{\"title\":\"...\",\"type\":\"...\"}]}",
                max_tokens=1200)
            if obj and obj.get("titles"):
                cands = [(c["title"], c.get("type", "Mystery"))
                         for c in obj["titles"]] or cands
        except Exception:
            pass
    kwset = set((plan.get("keywords") or []))
    verified = []
    for c, ty in cands:
        v, r = _verdict(c, topic, kwset, prev_topics, ty)
        verified.append({"title": c, "type": ty, "verdict": v, "reasons": r})
    passed = [x for x in verified if x["verdict"] == "PASS"]
    chosen = (passed[0]["title"] if passed else
              (verified[0]["title"] if verified else title))
    out = {"title": chosen, "candidates": verified, "chosen": chosen}
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "titles.json"), "w",
                  encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    return out
