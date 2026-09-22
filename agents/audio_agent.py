#!/usr/bin/env python3
"""agents/audio_agent.py — röst + musik + SFX-planering.

1) TTS varje block -> audio/<ID>.wav  (timeline byggs sedan runt VERKLIG dur)
2) voice_profile.json = den röst som används (för reproducerbarhet)
"""
import os, json
from engine import audio as AU

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(plan, project_dir, voice="auto", skip_existing=True):
    os.makedirs(os.path.join(ROOT, "audio"), exist_ok=True)
    profile = {"engine": "edge-tts", "voice": voice, "blocks": {}}
    durations = {}
    for b in plan.get("blocks", []):
        bid = b.get("id")
        vo = b.get("voiceover", "").strip() or b.get("text", "").strip()
        if not vo:
            continue
        out_path = os.path.join(ROOT, "audio", f"{bid}.wav")
        path, dur = AU.synth(vo, bid, voice=voice)
        durations[bid] = round(dur, 3)
        profile["blocks"][bid] = {"path": os.path.relpath(path, ROOT),
                                  "duration": round(dur, 3)}
    profile["note"] = ("Röst sparas per block. kör med --voice <voice> för annan "
                       "röst; --no-llm påverkar inte TTS.")
    with open(os.path.join(project_dir, "voice_profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=1)
    return durations, profile
