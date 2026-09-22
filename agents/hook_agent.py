#!/usr/bin/env python3
"""agents/hook_agent.py — HOOK-MOTORN (separat från script-agenten).

Genererar: N hooks · opening-sekvenser · curiosity gaps · cold opens.
Väljer den hook som matchar storyn + research (payload-värde högst, koppling
till en faktisk claim). Skriver hooks.json.

Första sekunderna är centrala (YT: leverera på titel/thumbnail-löftet snabbt).
"""
import os, json
from agents import llm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _offline_hooks(topic, research):
    facts = [f["claim"] for f in research.get("facts", []) if f.get("tier", 9) <= 2]
    surprise = facts[0] if facts else f"what {topic} actually did"
    T = topic
    hooks = [
        f"Nobody saw this coming. {surprise} This is {T}.",
        f"{T} looks simple. The truth is stranger than anyone knows.",
        f"Here's the part of the {T} story they don't tell you.",
        f"How did {T} pull this off? The answer changes everything.",
        f"What started as nothing became the internet's biggest story.",
        f"Every fact you know about {T} ... is about to change.",
    ]
    opens = [
        f"{surprise} And then, silence.",
        f"There's one moment in the {T} story that explains everything.",
    ]
    gaps = [
        f"You know {T}. But you don't know THIS.",
        f"Why is everyone suddenly talking about {T}?",
    ]
    cold = [
        f"This isn't about {T}. It's about what comes next.",
    ]
    return hooks, opens, gaps, cold

def run(topic, research, project_dir, n_hooks=20, use_llm=None):
    use_llm = llm.is_available() if use_llm is None else use_llm
    hooks, opens, gaps, cold = _offline_hooks(topic, research)
    if use_llm:
        try:
            facts = [f["claim"] for f in research.get("facts", [])][:12]
            obj = llm.fill_json(
                f"Du är hook-författare för en internet-dokumentär om '{topic}'.\n"
                f"Research-claims (använd ENDAST dessa som faktagrund):\n"
                f"{json.dumps(facts, ensure_ascii=False)[:3000]}\n"
                "Generera JSON: {\"hooks\":[20 hooks, korta, curiosity gap, "
                "stark, inga os­tödda siffror], \"openings\":[5], "
                "\"curiosity_gaps\":[5], \"cold_opens\":[5], \"pick\":\"<bästa "
                "hooken verbatim>\"}\nRegler: varje hook 5-22 ord; siffror måste "
                "komma från claims; öppna med det mest chockerande.",
                max_tokens=2200)
            if obj:
                hooks = obj.get("hooks", hooks)
                opens = obj.get("openings", opens)
                gaps = obj.get("curiosity_gaps", gaps)
                cold = obj.get("cold_opens", cold)
                pick = obj.get("pick")
                if pick:
                    hooks = [pick] + [h for h in hooks if h != pick]
        except Exception:
            pass
    hooks = hooks[:max(4, min(n_hooks, len(hooks)))]
    best = hooks[0]
    payload = {"topic": topic, "pick": best, "hooks": hooks,
               "openings": opens, "curiosity_gaps": gaps,
               "cold_opens": cold}
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "hooks.json"), "w",
                  encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    return payload
