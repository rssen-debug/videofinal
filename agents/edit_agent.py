#!/usr/bin/env python3
"""agents/edit_agent.py — editorn: samlar plan -> production_plan.json
(den "enda" filen som beskriver hela videon). Lämnar själva renderingen till
make_video/gfx_kit/cinema/captions (se compilation i sunny_auto.py).
"""
import os, json

def run(plan, timeline, check_report, project_dir):
    production = {
        "schema": "sunny.production/1",
        "topic": plan.get("title", ""),
        "hook": plan.get("hook", ""),
        "title": plan.get("title", ""),
        "keywords": plan.get("keywords", []),
        "gap": plan.get("gap", 0.7),
        "tail": plan.get("tail", 2.5),
        "blocks": plan.get("blocks", []),
        "visual_plan": plan.get("visual_plan", []),
        "clip_plan": plan.get("clip_plan", []),
        "caption_plan": plan.get("caption_plan", []),
        "music_plan": plan.get("music_plan", [{"from": 0, "intensity": "MEDIUM"}]),
        "timeline": timeline,
        "factcheck": {
            "safe": check_report.get("safe", False),
            "flags": [b for b in check_report.get("blocks", []) if b.get("flags")],
        },
        "voice_durations": {s["id"]: s["dur"] for s in timeline.get("segments", [])},
    }
    with open(os.path.join(project_dir, "production_plan.json"), "w",
              encoding="utf-8") as f:
        json.dump(production, f, ensure_ascii=False, indent=1)
    return production
