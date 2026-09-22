#!/usr/bin/env python3
"""agents/llm_client.py — delad "brain": genererar production_plan.
Med LLM — rik plan. Utan LLM (--no-llm) — deterministisk plan ur research.

Detta är navet som beskrivs i arkitekturen: LLM = creative director +
researcher + editor planner; de andra agenterna utför beslut den fattat.
"""
import os, json, re
from agents import llm
from research import claims as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30

# ---------------- hjälp - utvinna entities ----------------
def _entities(research):
    ents = []
    for f in research.get("facts", [])[:200]:
        for m in re.findall(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,3}\b", f["claim"]):
            m = m.strip()
            if len(m) > 3 and m.lower() not in ("the", "and") and m not in ents:
                ents.append(m)
    return ents[:12]

def _best_num(facts, allow=("500", "million", "billion", "subscriber", "$")):
    for f in facts:
        cl = f["claim"]
        for a in allow:
            if a in cl:
                m = re.search(r"\d[\d,.]*\s*(?:million|billion)?", cl)
                if m:
                    return cl
    if facts:
        return facts[0]["claim"]
    return ""

# ---------------- LLM-PLAN ----------------
def _memory_prompt(memory):
    """LLM-minne: do-not-repeat + format-mönster från tidigare körningar."""
    if not memory:
        return ""
    avoid = memory.get("avoid_repeat", []) or []
    used = [f.get("title", "") for f in (memory.get("formats_used", []) or [])]
    weak = memory.get("weak_topics", []) or []
    good = memory.get("successful_topics", []) or []
    parts = []
    if avoid:
        parts.append("UPPREPA INTE dessa ämnen/titlar: " + ", ".join(avoid[:8]))
    if used:
        parts.append("Tidigare titlar (välj en ANNAN vinkel): " + ", ".join(used[:8]))
    if good:
        parts.append("Historik som funkat (liknande vinklar ok): " + ", ".join(good[:5]))
    if weak:
        parts.append("Svagare hittills (undvik): " + ", ".join(weak[:5]))
    if not parts:
        return ""
    return "KANAL-MINNE (följ, men gör INTE varje video till samma mall):\n" + \
           "\n".join(parts) + "\n\n"

def _llm_plan(topic, research, goal_dur, memory=None):
    facts = research["facts"][:80]
    fact_blob = json.dumps(
        [{"claim": f["claim"], "kind": f["kind"], "tier": f["tier"],
          "conf": f["confidence"]} for f in facts], ensure_ascii=False)
    blocks_n = 7
    prompt = f"""Du är creative director + manusförfattare + editor-planner i en
sunnyv2-stil dokumentärstudio (dark, cinematic, fast-paced internet-dokumentär).

SKRIV INGA DOKUMENTÄRREGLER OM — jag ger dig dem redan. Följ dem.
{_memory_prompt(memory)}
Ämne: {topic}. Mål: ~{goal_dur}s, {blocks_n} voiceover-block (A1..A{blocks_n-2}, B1, A{blocks_n-1}),
varje block 25-45 ord (350-560 tecken), storytelling-struktur:
hook(curiosity gap) -> vem -> uppgång -> vändpunkt -> eskalering -> konsekvens -> payoff+CTA.

ANVÄND ENDAST dessa research-claims (inga andra fakta):
{fact_blob}
Fler claims ryms inte här men du FÅR tolka kombinationer av dem (INFERENCE).
Varje siffra MÅSTE komma från en claim. Vid allegationer: skriv "reportedly/alleging".

Returnera STRICT JSON (inget annat):
{{
 "title":"...",
 "hook":"...",
 "keywords":["..."],
 "blocks":[
   {{"id":"A1","voiceover":"...","music":"MEDIUM","visuals":[{{"type":"clip|photo|graphic|tweet|stat|timeline|chart","text":"..."}}]}}
 ],
 "visual_plan":[
   {{"id":"v1","block":"A1","type":"stat|glow|card|lower_third|tweet|timeline|chart|photo|circle",
     "text":"...","big":"...","sub":"...","at":0.3,"until":"end-0.5","anim":"slam|slideL|slideR|rise|pop|drift",
     "w":700,"x":null,"y":null,"impact":false,"reveal":false,
     "data":null,"img":"assets/src/","handle":null,"accent":null}}
 ],
 "clip_plan":[
   {{"number":1,"block":"A4","query":"...","at":8,"dur":6,"w":900,"y":64,"vol":1.1,
     "cut":0,"crop":"","motion":null,"snap":true}}
 ],
 "caption_plan":[{{"block":"A1","emphasis":["..."]}}],
 "music_plan":[{{"from":0,"intensity":"MEDIUM"}}],
 "timeline_note":"..."
}}
Regler:
- "at"/"until" är RELATIVA blocket (float=sek in i blocket; "end","mid","end-5","mid+2").
- visual-planen ska ge 3-5 visuella beats PER block (så bilden skiftar var 2-6 s).
- Kräv minst 3 clips (MANDATE: ≥3 klipp MED ljud), lägg dem efter replik-pekare.
- précisera anim/easing ur {slam,slideL,slideR,rise,pop,drift} — inte alla effekter på allt.
- lägg impacts på stora reveals, "reveal":true på sådana (-> riser inför).
- publish-AVSNITT: minst 1 stat-kort (type stat) + minst 1 lower third (typ lower_third)."""
    try:
        obj = llm.fill_json(prompt, required_keys=["blocks"])
        if obj is None:
            return None
        # normalisera musik per block om saknas
        for b in obj.get("blocks", []):
            if "music" not in b:
                b["music"] = "MEDIUM"
            if "id" not in b:
                continue
        return obj
    except Exception:
        return None

# ---------------- OFFLINE-PLAN ----------------
def _offline_plan(topic, research, goal_dur):
    facts = research["facts"]
    ents = _entities(research)
    who = f"{topic} — {ents[0] if ents else 'internetfenomenet'}"
    # Prioritera RENA, pålitliga meningar (Wikipedia, tier<=2) för syntesen —
    # aldrig råa nyhetsrubriker med källnamn inbakade.
    clean = [f["claim"] for f in facts
             if f.get("source") == "wikipedia"
             and f["kind"] in ("FACT", "CLAIM")] or \
            [f["claim"] for f in facts if f.get("tier", 9) <= 2]
    grow = " ".join(clean[:4]) if clean else \
        "The story sits on the edge of what even the internet believes."
    stat = C.new_research(topic)
    stat_line = _best_num([f for f in facts if f["tier"] <= 2]) or _best_num(facts)
    title = f"How {topic} Took Over the Internet"
    blocks = [
        {"id": "A1", "voiceover":
         f"Everyone knows {topic}. Or thinks they do. But the real story? "
         "It's stranger than anything you've seen on your feed. Stick with me.",
         "music": "HIGH", "visuals": [{"type": "graphic", "text": topic}]},
        {"id": "A2", "voiceover":
         f"This is {who}. To understand what happened, you have to rewind. "
         "Most people never saw what was building behind the scenes.",
         "music": "LOW", "visuals": [{"type": "graphic", "text": "THE RISE"}]},
        {"id": "A3", "voiceover":
         grow[:520] if len(grow) < 560 else grow[:520],
         "music": "MEDIUM", "visuals": [{"type": "graphic", "text": "THE NUMBERS"}]},
        {"id": "A4", "voiceover":
         "And then it cracked. The headlines turned. Everything everyone "
         "thought they knew ... changed overnight. Look at this.",
         "music": "MEDIUM", "visuals": [{"type": "graphic", "text": "THE TURN"}]},
        {"id": "A5", "voiceover":
         "What happened next set the internet on fire. And it just kept coming.",
         "music": "HIGH", "visuals": [{"type": "graphic", "text": "ESCALATION"}]},
        {"id": "B1", "voiceover":
         "If the allegations are true, this is far bigger than one creator.",
         "music": "LOW", "visuals": [{"type": "graphic", "text": "CONSEQUENCES"}]},
        {"id": "A6", "voiceover":
         f"So where does {topic} go from here? Nobody knows. And that is exactly "
         "why the internet can't look away. Subscribe for what comes next.",
         "music": "IMPACT", "visuals": [{"type": "graphic", "text": "SUBSCRIBE"}]},
    ]
    # visual_beats: 2-4 per block (cards/glows/stats) + MANDATE-krav
    # (minst 1 lower third + minst 1 stat / tweet-UI som social-bevis)
    visual_plan, n = [], 0
    layouts = [(None, None), (46, 468), (200, 160), (140, 240)]
    types = ["glow", "lower_third", "card", "stat"]
    stat_value = None  # riktig siffra ur facts (tier<=2)
    m = re.search(r"\b\d[\d,.]*\s*(?:million|billion|thousand)?\b",
                  (stat_line or ""), re.IGNORECASE)
    if m:
        stat_value = m.group(0)
    for i, b in enumerate(blocks):
        for j, ty in enumerate(types):
            if j > 3:
                break
            x, y = layouts[j]
            n += 1
            geom = {"id": f"v{n}", "block": b["id"], "type": ty,
                    "at": 0.3 + j * 2.2, "until": "end-0.4",
                    "anim": ["slam", "slideL", "slideR", "pop"][j],
                    "w": [700, 760, 860, 300][j],
                    "x": x, "y": y, "impact": j in (0, 3), "reveal": j == 0}
            if ty == "glow":
                geom["text"] = topic.upper()
                geom["w"] = 560 if i else 620
            elif ty == "lower_third":
                main = (ents[0] if ents else topic).upper()
                geom["text"] = main
                geom["sub"] = "THE STORY"
                geom["w"] = 760
            elif ty == "stat":
                geom["big"] = stat_value or "1M+"
                geom["text"] = "SUBSCRIBERS" if "subscri" in (stat_line or "").lower() else "THE NUMBERS"
                geom["w"] = 300
                geom["at"] = 4.0
            else:
                geom["text"] = b["voiceover"].split(".")[0][:40]
            visual_plan.append(geom)
    # social-bevis: tweet-UI i vändpunkts-blocket
    news_like = [f for f in facts if f.get("source", "").lower() not in ("wikipedia", "wikidata", "britannica")]
    tw_body = (news_like[0]["claim"] if news_like else \
               (facts[0]["claim"] if facts else "The internet can't stop talking."))[:110]
    visual_plan.append({
        "id": f"v{n+1}", "block": "A4", "type": "tweet",
        "name": (news_like[0]["source"] if news_like else "source"),
        "handle": "@source", "text": tw_body,
        "meta": "NOW", "likes": "99K+", "img": "",
        "at": 2.0, "until": "end-1", "anim": "rise", "w": 520, "x": 380, "y": 200,
        "impact": True, "reveal": True,
    })
    clip_plan = [
        {"number": k, "block": "A4" if k == 1 else ("A5" if k == 2 else "B1"),
         "query": f"{topic} {suffix}", "at": [8, 6, 4][k - 1], "dur": 6,
         "w": 900, "y": 64, "vol": 1.1, "snap": True}
        for k, suffix in enumerate(["moment", "interview", "news"], start=1)
    ]
    return {
        "title": title,
        "hook": blocks[0]["voiceover"],
        "keywords": [topic.lower()] + [e.lower() for e in ents[:4]],
        "blocks": blocks,
        "visual_plan": visual_plan,
        "clip_plan": clip_plan,
        "caption_plan": [{"block": "A1", "emphasis": [topic.upper()]}],
        "music_plan": [{"from": 0, "intensity": "MEDIUM"}],
        "timeline_note": "offline-plan (no-llm): cards/glows/stats ur research-synthes.",
        "_offline": True,
    }

def plan(topic, research, goal_dur, no_llm=False, memory=None):
    if not no_llm and llm.is_available():
        obj = _llm_plan(topic, research, goal_dur, memory=memory)
        if obj is not None:
            obj["hook"] = obj.get("hook", "") or obj["blocks"][0]["voiceover"]
            obj["title"] = obj.get("title", "") or topic
            obj.setdefault("keywords", [topic.lower()])
            obj.setdefault("visual_plan", [])
            obj.setdefault("clip_plan", [])
            obj.setdefault("caption_plan", [])
            obj.setdefault("music_plan", [{"from": 0, "intensity": "MEDIUM"}])
            return obj
    return _offline_plan(topic, research, goal_dur)
