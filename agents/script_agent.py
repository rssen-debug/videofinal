#!/usr/bin/env python3
"""agents/script_agent.py — skriver script.json från production_plan.
Tar blockens voiceover, delar i scener och skickar vidare till factcheck.
"""
import os, json, re

def run(plan, project_dir):
    blocks = []
    for b in plan.get("blocks", []):
        vid = b.get("block", b.get("id", "?"))
        blocks.append({
            "id": b.get("id", vid),
            "voiceover": b.get("voiceover", ""),
            "duration_est": round(len(b.get("voiceover", "")) / 15.0, 1),
            "music": b.get("music", "MEDIUM"),
            "visuals": b.get("visuals", [{
                "type": "graphic", "text": b["id"]}]),
        })
    script = {"topic": plan.get("title", ""), "hook": plan.get("hook", ""),
              "blocks": blocks}
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=1)
    return script
