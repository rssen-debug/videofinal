#!/usr/bin/env python3
"""agents/story_agent.py — story-arkitekt (vinklar) som driver hook-motorn.

Flöde:
  topic -> N vinklar -> research-fit -> bästa konceptet (story.json)
       -> hook-agenten (separat: hooks/openings/gaps/cold opens) -> hooks.json

Här samlas story.json med den vinnande vinkeln + vald hook.
"""
import os, json
from agents import llm
from agents import hook_agent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(topic, research, project_dir, use_llm=None):
    facts = research["facts"]
    use_llm = llm.is_available() if use_llm is None else use_llm

    variants = [
        f"The Story of {topic}",
        f"How {topic} Built an Empire Nobody Saw Coming",
        f"The Problem With {topic}",
        f"{topic}: Rise and Fall",
        f"What Really Happened to {topic}",
        f"The Dark Side of {topic}",
        f"Why the Internet Turned on {topic}",
        f"The Untold Truth About {topic}",
        f"Inside the {topic} Machine",
        f"The Moment {topic} Changed Everything",
    ]
    # research-fit: hur många claims stödjer varje vinkel + liten vikt för konflikt
    def sup(t):
        t2 = t.lower()
        keys = [w for w in ("problem", "dark", "turn", "fall", "untold",
                            "moment", "inside", "empire", "story", "rise")
                if w in t2]
        n = sum(1 for f in facts if any(k in f["claim"].lower() for k in keys))
        return n + (0.5 if keys else 0)
    scored = sorted(((sup(t), t) for t in variants), reverse=True)
    chosen = scored[0][1]

    story = {
        "topic": topic,
        "angle": chosen,
        "angle_candidates": [t for _, t in scored],
        "audience": "internet-dokumentär / true-story publik",
        "why_now": "",
    }
    if use_llm:
        try:
            obj = llm.fill_json(
                f"Story-meta för en dokumentär om '{topic}' givet claims:\n"
                f"{json.dumps([f['claim'] for f in facts[:15]], ensure_ascii=False)}\n"
                "Svara JSON: {angle, why_now, audience, curiosity_gap}",
                max_tokens=600)
            if obj:
                for k in ("angle", "why_now", "audience"):
                    if obj.get(k):
                        story[k] = obj[k]
                story["curiosity_gap"] = obj.get("curiosity_gap", "")
        except Exception:
            pass

    # hook-motor (separat)
    hooks = hook_agent.run(topic, research, project_dir, use_llm=use_llm)
    story["hook"] = hooks["pick"]

    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "story.json"), "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=1)
    return story
